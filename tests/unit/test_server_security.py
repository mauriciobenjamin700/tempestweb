"""Tests for Mode B server security (Track S — S0/S1/S3).

Covers the auth gate, origin allowlist and the JWT helpers wired through
``create_app`` — the WebSocket upgrade is rejected (close 1008 → connect raises)
and the SSE endpoints return 401 when the connection is not authorized. PyJWT is
optional; the JWT paths assert graceful degradation when it is absent.
"""

from __future__ import annotations

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
