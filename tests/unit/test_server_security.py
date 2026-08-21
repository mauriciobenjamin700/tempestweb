"""Tests for Mode B server security (Track S — S0/S1/S3).

Covers the auth gate, origin allowlist and the JWT helpers wired through
``create_app`` — the WebSocket upgrade is rejected (close 1008 → connect raises)
and the SSE endpoints return 401 when the connection is not authorized. PyJWT is
optional; the JWT paths assert graceful degradation when it is absent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tempest_core import Text, Widget
from tempestweb.server import (
    Credentials,
    SecurityConfig,
    create_app,
    jwt_authenticator,
    token_authenticator,
    verify_jwt,
)


@dataclass
class _State:
    """Trivial state."""


def _view(app: Any) -> Widget:  # noqa: ANN401 - App[_State], kept loose for the test
    return Text(content="hi", key="t")


def _client(**security: Any) -> TestClient:
    app = create_app(lambda: _State(), _view, security=SecurityConfig(**security))
    return TestClient(app)


def _ws_ok(client: TestClient, url: str, headers: dict[str, str] | None = None) -> bool:
    """Whether a WebSocket connection succeeds (vs is rejected on the upgrade)."""
    try:
        with client.websocket_connect(url, headers=headers or {}):
            return True
    except Exception:
        return False


# -- open (no security) -------------------------------------------------------


def test_open_host_accepts_ws() -> None:
    """With no SecurityConfig the host stays open (dev)."""
    assert _ws_ok(TestClient(create_app(lambda: _State(), _view)), "/ws")


# -- S0: auth gate ------------------------------------------------------------


def test_token_gate_rejects_and_accepts_ws() -> None:
    client = _client(authenticate=token_authenticator("sesame"))
    assert _ws_ok(client, "/ws") is False  # no token
    assert _ws_ok(client, "/ws?token=nope") is False  # wrong token
    assert _ws_ok(client, "/ws?token=sesame") is True  # right token


def test_token_gate_reads_bearer_header() -> None:
    client = _client(authenticate=token_authenticator("sesame"))
    assert _ws_ok(client, "/ws", {"authorization": "Bearer sesame"}) is True
    assert _ws_ok(client, "/ws", {"authorization": "Bearer nope"}) is False


def test_empty_secret_disables_gate() -> None:
    """An empty shared secret allows everything (dev)."""
    client = _client(authenticate=token_authenticator(""))
    assert _ws_ok(client, "/ws") is True


def test_sse_endpoints_401_when_unauthorized() -> None:
    client = _client(authenticate=token_authenticator("sesame"))
    assert client.get("/sse", params={"session": "s1"}).status_code == 401
    assert client.post("/sse/s1", json={"type": "x"}).status_code == 401
    # With the token the SSE POST reaches routing (404 = unknown session, past gate).
    ok = client.post("/sse/s1", params={"token": "sesame"}, json={"type": "x"})
    assert ok.status_code == 404


def test_authenticate_error_is_a_rejection() -> None:
    """A raising authenticate predicate rejects rather than 500s."""

    def _boom(credentials: Credentials) -> bool:
        raise RuntimeError("db down")

    assert _ws_ok(_client(authenticate=_boom), "/ws") is False


async def test_async_authenticate_supported() -> None:
    async def _auth(credentials: Credentials) -> bool:
        return credentials.token == "ok"

    client = _client(authenticate=_auth)
    assert _ws_ok(client, "/ws?token=ok") is True
    assert _ws_ok(client, "/ws?token=bad") is False


# -- S1: origin allowlist -----------------------------------------------------


def test_origin_allowlist_ws() -> None:
    client = _client(allowed_origins=["https://ok.example"])
    assert _ws_ok(client, "/ws", {"origin": "https://ok.example"}) is True
    assert _ws_ok(client, "/ws", {"origin": "https://evil.example"}) is False
    assert _ws_ok(client, "/ws") is False  # no origin


def test_origin_wildcard_allows_any() -> None:
    client = _client(allowed_origins=["*"])
    assert _ws_ok(client, "/ws", {"origin": "https://anything.example"}) is True
    assert _ws_ok(client, "/ws") is True  # wildcard skips the WS origin check


# -- S3: JWT helpers ----------------------------------------------------------


def _pyjwt_installed() -> bool:
    try:
        import jwt  # noqa: F401

        return True
    except ImportError:
        return False


def test_verify_jwt_requires_pyjwt_when_absent() -> None:
    if _pyjwt_installed():
        pytest.skip("PyJWT installed; the missing-dep path is not exercised")
    with pytest.raises(RuntimeError, match="PyJWT is required"):
        verify_jwt("a.b.c", "secret")


def test_jwt_authenticator_rejects_without_valid_token() -> None:
    """The JWT gate rejects an empty/garbage token (and degrades if PyJWT is absent)."""
    gate = jwt_authenticator("secret")
    empty = Credentials(token=None, origin=None, headers={}, query={})
    garbage = Credentials(token="garbage", origin=None, headers={}, query={})
    assert gate(empty) is False
    assert gate(garbage) is False


# -- S2: limits / anti-DoS ----------------------------------------------------


def test_max_connections_caps_websockets() -> None:
    """A WS over the concurrent-session cap is refused; freeing a slot re-allows."""
    client = _client(max_connections=1)
    with client.websocket_connect("/ws"):  # slot 1
        assert _ws_ok(client, "/ws") is False  # over cap -> refused
    # First closed -> slot free again.
    assert _ws_ok(client, "/ws") is True


def test_per_ip_rate_limit_refuses_flood() -> None:
    """More than max_connections_per_minute from one IP is refused; slot frees."""
    client = _client(max_connections_per_minute=2)
    assert _ws_ok(client, "/ws") is True
    assert _ws_ok(client, "/ws") is True
    assert _ws_ok(client, "/ws") is False  # 3rd within the window -> rate limited


def test_rate_limiter_windowing() -> None:
    """The RateLimiter allows up to `limit` per window and prunes old hits."""
    from tempestweb.server.security import RateLimiter

    limiter = RateLimiter(2, window=60.0)
    assert limiter.allow("ip", now=100.0) is True
    assert limiter.allow("ip", now=100.0) is True
    assert limiter.allow("ip", now=100.0) is False
    assert limiter.allow("ip", now=161.0) is True  # window elapsed
    assert limiter.allow("other", now=100.0) is True  # per-key


def test_a_forged_forwarded_for_cannot_buy_a_fresh_rate_budget() -> None:
    """X-Forwarded-For is client data: untrusted, it must not reset the per-IP budget.

    Regression: the header was believed unconditionally, so a flood only had to
    vary it per request — every connection looked like a brand-new client, and
    the limit never fired. It also left one limiter entry per forged value.
    """
    client = _client(max_connections_per_minute=2)
    assert _ws_ok(client, "/ws", {"X-Forwarded-For": "9.9.9.1"}) is True
    assert _ws_ok(client, "/ws", {"X-Forwarded-For": "9.9.9.2"}) is True
    assert _ws_ok(client, "/ws", {"X-Forwarded-For": "9.9.9.3"}) is False
    assert _ws_ok(client, "/ws", {"X-Forwarded-For": "9.9.9.4"}) is False


def test_forwarded_for_is_honored_behind_a_declared_proxy() -> None:
    """With the peer declared trusted, each forwarded client gets its own budget."""
    client = _client(max_connections_per_minute=1, trusted_proxies=["*"])
    assert _ws_ok(client, "/ws", {"X-Forwarded-For": "9.9.9.1"}) is True
    assert _ws_ok(client, "/ws", {"X-Forwarded-For": "9.9.9.1"}) is False
    assert _ws_ok(client, "/ws", {"X-Forwarded-For": "9.9.9.2"}) is True


def test_resolve_client_ip_reads_the_chain_from_the_right() -> None:
    """Only hops a trusted proxy vouches for count; prepended ones are ignored."""
    from tempestweb.server.security import resolve_client_ip

    headers = {"x-forwarded-for": "1.1.1.1, 203.0.113.7, 10.0.0.2"}

    # No trust configured: the header is ignored entirely.
    assert resolve_client_ip(headers, "10.0.0.1", None) == "10.0.0.1"

    # The peer is not a declared proxy: still ignored.
    assert resolve_client_ip(headers, "10.0.0.1", ["10.0.0.9"]) == "10.0.0.1"

    # Declared proxies: the right-most hop that is not itself a proxy wins, so a
    # client-prepended "1.1.1.1" cannot impersonate anyone.
    assert (
        resolve_client_ip(headers, "10.0.0.1", ["10.0.0.1", "10.0.0.2"])
        == "203.0.113.7"
    )

    # The wildcard trusts any peer and takes the left-most (classic) hop.
    assert resolve_client_ip(headers, "10.0.0.1", ["*"]) == "1.1.1.1"

    # Nothing forwarded: fall back to the peer.
    assert resolve_client_ip({}, "10.0.0.1", ["*"]) == "10.0.0.1"


def test_rate_limiter_sweeps_keys_that_went_quiet() -> None:
    """The limiter must not keep one entry per address it has ever seen.

    Regression: buckets were only pruned when their own key was touched again, so
    a flood of distinct (or forged) addresses grew the map without bound — and the
    docstring claimed the opposite.
    """
    from tempestweb.server.security import RateLimiter

    limiter = RateLimiter(5, window=60.0, sweep_every=8)
    for index in range(64):
        limiter.allow(f"10.0.0.{index}", now=100.0)
    assert limiter.tracked_keys() > 0

    # Every window has long passed; the next sweep must clear them out.
    for _ in range(8):
        limiter.allow("current", now=10_000.0)
    assert limiter.tracked_keys() == 1


def test_max_message_bytes_rejects_large_sse_post() -> None:
    client = _client(max_message_bytes=50)
    small = client.post("/sse/s1", json={"type": "x"})  # valid JSON under the limit
    assert small.status_code == 404  # past the size gate; unknown session
    big = client.post("/sse/s1", content=b"x" * 200)
    assert big.status_code == 413  # size gate fires before parsing


def test_max_message_bytes_holds_without_a_content_length() -> None:
    """The size cap must survive a chunked body, which declares no length.

    Regression: the gate read ``Content-Length`` alone, so a client that streamed
    its body under chunked transfer encoding — legal HTTP/1.1, and what an
    attacker would reach for — sailed past the check and had the whole body read
    into memory. The limit is now enforced while reading.
    """
    client = _client(max_message_bytes=50)

    def chunks() -> Any:
        for _ in range(20):
            yield b"x" * 100

    response = client.post("/sse/s1", content=chunks())
    assert "content-length" not in {k.lower() for k in response.request.headers}
    assert response.status_code == 413


def test_max_events_per_minute_throttles_sse_posts() -> None:
    """Inbound envelopes are budgeted per IP, not just new connections."""
    client = _client(max_events_per_minute=2)
    assert client.post("/sse/s1", json={"kind": "event"}).status_code == 404
    assert client.post("/sse/s1", json={"kind": "event"}).status_code == 404
    assert client.post("/sse/s1", json={"kind": "event"}).status_code == 429


@pytest.mark.asyncio
async def test_websocket_transport_closes_a_flooding_peer() -> None:
    """A frame over the inbound budget closes the socket with 1013.

    The same budget applies to WebSocket frames as to SSE POSTs, so holding an
    accepted socket open is no way around it. Driven at the transport (with a
    socket double) rather than through the app so a regression fails instead of
    blocking on a receive that never comes.
    """
    from tempestweb.transports.websocket import WebSocketTransport

    class _Socket:
        """A WebSocket double replaying canned frames, recording the close code.

        Mirrors Starlette's ``receive`` contract (an ASGI message dict, with
        disconnect as a message rather than an exception), which is what the
        transport reads so it can accept a binary frame and drop an undecodable
        one without ending the connection.
        """

        def __init__(self, frames: list[dict[str, Any]]) -> None:
            self.frames: list[dict[str, Any]] = frames
            self.closed_with: int | None = None

        async def receive(self) -> dict[str, Any]:
            if not self.frames:
                return {"type": "websocket.disconnect", "code": 1000}
            return {
                "type": "websocket.receive",
                "text": json.dumps(self.frames.pop(0)),
            }

        async def close(self, code: int = 1000) -> None:
            self.closed_with = code

    def event(key: str) -> dict[str, Any]:
        return {"kind": "event", "data": {"type": "click", "key": key, "payload": {}}}

    budget = iter([True, False])
    socket = _Socket([event("a"), event("b")])
    transport = WebSocketTransport(
        socket,  # type: ignore[arg-type]
        allow_inbound=lambda: next(budget),
    )

    assert (await transport.recv_event())["key"] == "a"
    with pytest.raises(Exception, match="disconnected"):
        await transport.recv_event()
    assert socket.closed_with == 1013


# -- S6: security headers -----------------------------------------------------


def test_security_headers_on_responses() -> None:
    client = _client(security_headers=True, hsts=True)
    # The SSE POST returns a normal (non-streaming) response the middleware wraps.
    resp = client.post("/sse/unknown", json={"type": "x"})
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert "max-age=" in resp.headers["strict-transport-security"]


def test_csp_header_when_set() -> None:
    client = _client(content_security_policy="default-src 'self'")
    resp = client.post("/sse/unknown", json={"type": "x"})
    assert resp.headers["content-security-policy"] == "default-src 'self'"


def test_no_headers_by_default() -> None:
    client = TestClient(create_app(lambda: _State(), _view))
    resp = client.post("/sse/unknown", json={"type": "x"})
    assert "x-frame-options" not in resp.headers


# -- S4: health probe ---------------------------------------------------------


def test_health_probe() -> None:
    """`/health` is unauthenticated, cheap, and reports readiness."""
    client = _client(authenticate=token_authenticator("sesame"))
    resp = client.get("/health")  # no token needed
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["sessions"] == 0
    assert body["ready"] is True


def test_health_ready_flag_follows_capacity() -> None:
    client = _client(max_connections=1)
    with client.websocket_connect("/ws"):
        assert client.get("/health").json()["ready"] is False  # full
    assert client.get("/health").json()["ready"] is True  # slot freed


# -- S8: metrics --------------------------------------------------------------


def test_metrics_disabled_by_default() -> None:
    client = TestClient(create_app(lambda: _State(), _view))
    assert client.get("/metrics").status_code == 404


def test_metrics_counters() -> None:
    app = create_app(
        lambda: _State(),
        _view,
        security=SecurityConfig(authenticate=token_authenticator("sesame")),
        metrics=True,
    )
    client = TestClient(app)
    # One accepted WS, one rejected (no token).
    with client.websocket_connect("/ws?token=sesame"):
        body = client.get("/metrics").text
        assert "tempestweb_sessions_live 1" in body
    _ws_ok(client, "/ws")  # rejected
    body = client.get("/metrics").text
    assert "tempestweb_sessions_opened_total 1" in body
    assert "tempestweb_connections_rejected_total 1" in body
    assert "tempestweb_sessions_live 0" in body


def test_open_host_warns_that_it_is_open(caplog: pytest.LogCaptureFixture) -> None:
    """Serving with no SecurityConfig says so, rather than looking configured.

    An open host takes a WebSocket from any origin (CORS does not guard the
    upgrade), authenticates nobody and caps nothing. That is the right default
    for `tempestweb dev`, and a dangerous one to reach production silently.
    """
    with caplog.at_level("WARNING", logger="tempestweb.server"):
        create_app(lambda: _State(), _view)
    assert "without a SecurityConfig" in caplog.text


def test_configured_host_does_not_warn(caplog: pytest.LogCaptureFixture) -> None:
    """A host given a SecurityConfig stays quiet."""
    with caplog.at_level("WARNING", logger="tempestweb.server"):
        create_app(lambda: _State(), _view, security=SecurityConfig())
    assert "without a SecurityConfig" not in caplog.text
