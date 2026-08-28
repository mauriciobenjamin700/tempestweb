"""Unit tests for server-side WebPush (P3).

Covers ``tempestweb.server.webpush``: VAPID config, the in-memory subscription
store and the VAPID-signed sender. The pywebpush callable is mocked so these run
without the (lazy) dependency installed.

**The mock was also the blind spot.** Every send test injected a sender raising
``WebPushError``, so the branch that prunes a dead endpoint always matched — and
the real sender, which raises ``pywebpush``'s own ``WebPushException``, never did.
Measured against FCM on 2026-08-27: an unsubscribed endpoint answers ``410 Gone``
and the subscription stayed in the store, send after send. The tests at the end
of this file cover the translation that closes it.

**And an assert can be a blind spot too.** The first version of
``test_a_successful_send_reports_the_status_the_service_answered`` fed the fake a
``201`` and asserted ``201`` — exactly the constant the code used to hard-code, so
the test passed against the broken module. It now uses ``202``, a status the
constant never was.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import time
from typing import Any

import pytest

from tempestweb.server.webpush import (
    InMemorySubscriptionStore,
    SendOutcome,
    VapidConfig,
    WebPushError,
    WebPushService,
    _default_sender,
    generate_vapid_keys,
    webpush_router,
)

VAPID = VapidConfig(
    public_key="pub-key",
    private_key="priv-key",
    subject="mailto:dev@example.com",
)


def _sub(endpoint: str) -> dict[str, Any]:
    """Build a minimal subscription JSON.

    Args:
        endpoint: The push endpoint URL.

    Returns:
        A subscription dict with keys.
    """
    return {"endpoint": endpoint, "keys": {"p256dh": "p", "auth": "a"}}


def test_vapid_from_env(monkeypatch: Any) -> None:
    """VapidConfig.from_env reads the prefixed environment variables."""
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "PUB")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "PRIV")
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:x@y.z")
    cfg = VapidConfig.from_env()
    assert cfg.public_key == "PUB"
    assert cfg.enabled is True
    assert cfg.subject == "mailto:x@y.z"


def test_vapid_disabled_without_private_key() -> None:
    """An empty private key disables sending."""
    assert VapidConfig(public_key="pub").enabled is False


def test_store_add_dedups_by_endpoint() -> None:
    """Re-subscribing the same endpoint replaces, never duplicates."""
    store = InMemorySubscriptionStore()
    store.add("u1", _sub("https://push/e1"))
    store.add("u1", _sub("https://push/e1"))
    store.add("u1", _sub("https://push/e2"))
    assert len(store.list_for("u1")) == 2
    assert store.list_for("u2") == []
    assert len(store.all()) == 2


def test_store_remove() -> None:
    """remove returns True only when an endpoint existed."""
    store = InMemorySubscriptionStore()
    store.add("u1", _sub("https://push/e1"))
    assert store.remove("https://push/e1") is True
    assert store.remove("https://push/e1") is False
    assert store.list_for("u1") == []


def test_send_signs_and_serializes_payload() -> None:
    """send invokes the sender with the VAPID key and a JSON-encoded payload.

    This sender returns nothing, so there is no status to report: ``status_code``
    stays ``None``. It used to come back as ``201`` — a status nobody answered,
    fabricated by an ``or 201`` fallback.
    """
    calls: list[dict[str, Any]] = []

    def fake_sender(**kwargs: Any) -> None:
        """Record the kwargs and return nothing, exposing no response."""
        calls.append(kwargs)

    svc = WebPushService(VAPID, sender=fake_sender)
    outcome = svc.send(_sub("https://push/e1"), {"title": "Hi", "badge_count": 2})
    assert outcome.ok is True
    assert outcome.status_code is None
    assert calls[0]["vapid_private_key"] == "priv-key"
    assert calls[0]["vapid_claims"] == {"sub": "mailto:dev@example.com"}
    assert json.loads(calls[0]["data"]) == {"title": "Hi", "badge_count": 2}


def test_send_prunes_dead_endpoint_on_410() -> None:
    """A 410 Gone marks the outcome gone and removes the subscription."""

    def gone_sender(**kwargs: Any) -> None:
        raise WebPushError("gone", status_code=410)

    store = InMemorySubscriptionStore()
    store.add("u1", _sub("https://push/dead"))
    svc = WebPushService(VAPID, store=store, sender=gone_sender)
    outcome = svc.send(_sub("https://push/dead"), {"title": "x"})
    assert outcome.ok is False
    assert outcome.gone is True
    assert outcome.status_code == 410
    assert store.all() == [], "dead endpoint pruned"


def test_send_reports_generic_failure_without_pruning() -> None:
    """A non-410 failure is reported but the subscription is kept."""

    def boom(**kwargs: Any) -> None:
        raise WebPushError("boom", status_code=500)

    store = InMemorySubscriptionStore()
    store.add("u1", _sub("https://push/keep"))
    svc = WebPushService(VAPID, store=store, sender=boom)
    outcome = svc.send(_sub("https://push/keep"), {"title": "x"})
    assert outcome.ok is False
    assert outcome.gone is False
    assert len(store.all()) == 1, "kept on transient failure"


def test_send_noop_when_vapid_disabled() -> None:
    """Sending degrades to a clean failure outcome when VAPID is disabled."""

    def must_not_call(**kwargs: Any) -> None:
        raise AssertionError("sender must not be called when disabled")

    svc = WebPushService(VapidConfig(public_key="pub"), sender=must_not_call)
    outcome = svc.send(_sub("https://push/e1"), {"title": "x"})
    assert outcome.ok is False
    assert "disabled" in (outcome.error or "")


def test_send_to_owner_and_broadcast() -> None:
    """send_to_owner and broadcast fan out; empty owner returns []."""
    sent: list[str] = []

    def sender(**kwargs: Any) -> None:
        sent.append(kwargs["subscription_info"]["endpoint"])

    store = InMemorySubscriptionStore()
    store.add("u1", _sub("https://push/a"))
    store.add("u1", _sub("https://push/b"))
    store.add("u2", _sub("https://push/c"))
    svc = WebPushService(VAPID, store=store, sender=sender)

    owner_outcomes = svc.send_to_owner("u1", {"title": "hi"})
    assert all(isinstance(o, SendOutcome) and o.ok for o in owner_outcomes)
    assert sorted(sent) == ["https://push/a", "https://push/b"]
    assert svc.send_to_owner("ghost", {"title": "x"}) == []

    sent.clear()
    broadcast = svc.broadcast({"title": "all"})
    assert len(broadcast) == 3
    assert len(sent) == 3


def test_subscribe_unsubscribe_endpoints() -> None:
    """add_subscription/remove_subscription drive the store (endpoint handlers)."""
    svc = WebPushService(VAPID)
    svc.add_subscription("u1", _sub("https://push/e1"))
    assert len(svc.store.list_for("u1")) == 1
    assert svc.remove_subscription("https://push/e1") is True
    assert svc.store.list_for("u1") == []


def _b64url_len(value: str) -> int:
    """Decode an unpadded base64url string and return its byte length."""
    return len(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))


def test_generate_vapid_keys_shape() -> None:
    """A generated keypair is a 65-byte uncompressed point + 32-byte scalar."""
    keys = generate_vapid_keys()
    assert _b64url_len(keys.public_key) == 65
    assert base64.urlsafe_b64decode(keys.public_key + "==")[0] == 0x04
    assert _b64url_len(keys.private_key) == 32
    # Two calls produce distinct keys (not a constant).
    assert generate_vapid_keys().private_key != keys.private_key


def test_webpush_router_end_to_end() -> None:
    """The router wires subscribe -> send -> unsubscribe over HTTP."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    sent: list[str] = []

    def sender(**kwargs: Any) -> Any:
        sent.append(kwargs["subscription_info"]["endpoint"])
        return type("R", (), {"status_code": 201})()

    svc = WebPushService(VAPID, store=InMemorySubscriptionStore(), sender=sender)
    app = FastAPI()
    app.include_router(webpush_router(svc))
    client = TestClient(app)

    assert client.get("/webpush/vapid-public-key").json() == {"public_key": "pub-key"}
    assert client.post("/webpush/subscribe", json=_sub("https://push/e1")).json() == {
        "ok": True
    }
    assert client.post("/webpush/send", json={"title": "Hi"}).json() == {
        "sent": 1,
        "total": 1,
    }
    assert sent == ["https://push/e1"]
    assert client.post(
        "/webpush/unsubscribe", json={"endpoint": "https://push/e1"}
    ).json() == {"removed": True}
    assert client.post("/webpush/send", json={"title": "Hi"}).json() == {
        "sent": 0,
        "total": 0,
    }


# ---------------------------------------------------------------------------
# The real sender: pywebpush's exception, translated
# ---------------------------------------------------------------------------


class _Response:
    """A stand-in for the ``requests`` response pywebpush carries."""

    def __init__(self, status_code: int) -> None:
        """Initialize the response.

        Args:
            status_code: The HTTP status the push service answered.
        """
        self.status_code = status_code


def test_default_sender_translates_pywebpush_failure_into_web_push_error(
    monkeypatch: Any,
) -> None:
    """A push service rejection arrives as WebPushError, carrying its status."""
    pywebpush = pytest.importorskip("pywebpush")

    def reject(**kwargs: Any) -> None:
        error = pywebpush.WebPushException("Push failed: 410 Gone")
        error.response = _Response(410)
        raise error

    monkeypatch.setattr(pywebpush, "webpush", reject)

    with pytest.raises(WebPushError) as raised:
        _default_sender()(subscription_info=_sub("https://push/dead"), data="{}")

    assert raised.value.status_code == 410


def test_a_real_410_prunes_the_subscription(monkeypatch: Any) -> None:
    """The measured production path: FCM says 410, the store loses the endpoint.

    This is the test the file was missing. With the sender injected by every
    other test, the pruning branch matched on a fake exception; the real sender
    raised ``pywebpush.WebPushException``, which fell through to the generic
    branch with no status, and the dead endpoint survived every send.
    """
    pywebpush = pytest.importorskip("pywebpush")

    def reject(**kwargs: Any) -> None:
        error = pywebpush.WebPushException("Push failed: 410 Gone")
        error.response = _Response(410)
        raise error

    monkeypatch.setattr(pywebpush, "webpush", reject)

    store = InMemorySubscriptionStore()
    store.add("u1", _sub("https://push/dead"))
    service = WebPushService(VAPID, store=store)

    outcome = service.send(_sub("https://push/dead"), {"title": "x"})

    assert outcome.gone is True
    assert outcome.status_code == 410
    assert store.all() == [], "a 410 Gone must prune the dead subscription"


def test_a_rotated_vapid_key_is_reported_and_the_subscription_kept(
    monkeypatch: Any,
) -> None:
    """403 is the push service refusing the signature, not a dead endpoint.

    Measured against FCM: sending with a rotated key answers ``403`` and *the
    subscription is still good*. Pruning it would drop a live subscriber over a
    server-side key mistake.
    """
    pywebpush = pytest.importorskip("pywebpush")

    def reject(**kwargs: Any) -> None:
        error = pywebpush.WebPushException("Push failed: 403 Forbidden")
        error.response = _Response(403)
        raise error

    monkeypatch.setattr(pywebpush, "webpush", reject)

    store = InMemorySubscriptionStore()
    store.add("u1", _sub("https://push/live"))
    service = WebPushService(VAPID, store=store)

    outcome = service.send(_sub("https://push/live"), {"title": "x"})

    assert outcome.ok is False
    assert outcome.gone is False
    assert outcome.status_code == 403
    assert len(store.all()) == 1


def test_a_successful_send_reports_the_status_the_service_answered(
    monkeypatch: Any,
) -> None:
    """The status comes from the push service's response, not from a constant.

    ``202 Accepted`` on purpose: it is a real answer (``pywebpush`` only raises
    above 202) **and** a value the removed ``status_code=201`` constant never
    produced, so this test fails against the pre-fix module. Asserting ``201``
    here — the first version of this test — could not fail.
    """
    pywebpush = pytest.importorskip("pywebpush")
    monkeypatch.setattr(pywebpush, "webpush", lambda **kwargs: _Response(202))

    service = WebPushService(VAPID, store=InMemorySubscriptionStore())
    outcome = service.send(_sub("https://push/live"), {"title": "x"})

    assert outcome.ok is True
    assert outcome.status_code == 202


def test_subscribe_without_an_endpoint_answers_400_not_500() -> None:
    """A malformed body is the caller's mistake, and says so.

    The store raises ``ValueError`` for a subscription with no endpoint; nothing
    caught it, so the client got a 500 with a traceback in the server log.
    """
    fastapi = pytest.importorskip("fastapi")
    testclient = pytest.importorskip("fastapi.testclient")

    service = WebPushService(VAPID, store=InMemorySubscriptionStore())
    app = fastapi.FastAPI()
    app.include_router(webpush_router(service))
    client = testclient.TestClient(app)

    response = client.post("/webpush/subscribe", json={"keys": {"p256dh": "p"}})

    assert response.status_code == 400
    assert "endpoint" in response.json()["detail"]


def test_a_404_prunes_like_a_410(monkeypatch: Any) -> None:
    """404 is a dead subscription too, and the grouping is fixed by a test.

    A push service answers 404 for a subscription it no longer knows, so keeping
    the row makes every later send retry an endpoint that can never receive
    again. The module docstring records the trade **and** its known risk (a proxy
    answering its own 404 for a wrong path prunes a live subscriber); this test
    makes the decision explicit instead of incidental — the device measurement
    only exercised 201/403/410.
    """
    pywebpush = pytest.importorskip("pywebpush")

    def reject(**kwargs: Any) -> None:
        """Answer 404, as a push service does for a subscription it forgot."""
        error = pywebpush.WebPushException("Push failed: 404 Not Found")
        error.response = _Response(404)
        raise error

    monkeypatch.setattr(pywebpush, "webpush", reject)

    store = InMemorySubscriptionStore()
    store.add("u1", _sub("https://push/unknown"))
    service = WebPushService(VAPID, store=store)

    outcome = service.send(_sub("https://push/unknown"), {"title": "x"})

    assert outcome.gone is True
    assert outcome.status_code == 404
    assert store.all() == [], "a 404 prunes like a 410"


# ---------------------------------------------------------------------------
# The prune is isolated: a broken store cannot cancel delivery
# ---------------------------------------------------------------------------


class _StoreThatFailsToPrune:
    """A store whose ``remove`` raises, like a real DB losing its connection.

    ``add``/``list_for``/``all`` work; only the write the prune needs fails.
    That is the realistic shape of a host-supplied SQLAlchemy or Redis store
    under load, and the prune only became reachable in production with this
    branch.

    Attributes:
        remove_calls: How many times ``remove`` was attempted.
    """

    def __init__(self) -> None:
        """Initialize an empty store."""
        self._inner = InMemorySubscriptionStore()
        self.remove_calls = 0

    def add(self, owner: str, subscription: dict[str, Any]) -> None:
        """Persist a subscription for an owner.

        Args:
            owner: The owning identifier.
            subscription: The subscription JSON.
        """
        self._inner.add(owner, subscription)

    def remove(self, endpoint: str) -> bool:
        """Fail the way a dropped database connection does.

        Args:
            endpoint: The endpoint the caller wanted removed.

        Returns:
            Never returns.

        Raises:
            RuntimeError: Always — this is the failure under test.
        """
        self.remove_calls += 1
        raise RuntimeError("OperationalError: server closed the connection")

    def list_for(self, owner: str) -> list[dict[str, Any]]:
        """Return the owner's subscriptions.

        Args:
            owner: The owning identifier.

        Returns:
            The subscriptions ([] when none).
        """
        return self._inner.list_for(owner)

    def all(self) -> list[dict[str, Any]]:
        """Return every stored subscription.

        Returns:
            All subscriptions ([] when empty).
        """
        return self._inner.all()


def _dead_first_sender(seen: list[str]) -> Any:
    """Build a sender that 410s on ``/dead`` and accepts everything else.

    Args:
        seen: A list the sender appends each attempted endpoint to.

    Returns:
        The sender callable.
    """

    def sender(**kwargs: Any) -> Any:
        """Reject the dead endpoint with a 410, accept the rest with a 201."""
        endpoint = str(kwargs["subscription_info"]["endpoint"])
        seen.append(endpoint)
        if endpoint.endswith("/dead"):
            raise WebPushError("Push failed: 410 Gone", status_code=410)
        return _Response(201)

    return sender


def test_a_broken_store_does_not_cancel_delivery_to_the_live_endpoints() -> None:
    """A store that raises while pruning must not abort the batch.

    The dead endpoint is stored first, so the prune runs before the live
    endpoint is attempted at all. With the prune unprotected, the store's
    exception propagated out of ``send`` → ``send_to_owner``: the live
    subscription was never tried, and the endpoint that this branch finally made
    reachable in production became a way to lose deliveries.
    """
    attempted: list[str] = []
    store = _StoreThatFailsToPrune()
    store.add("u1", _sub("https://push/dead"))
    store.add("u1", _sub("https://push/live"))
    svc = WebPushService(VAPID, store=store, sender=_dead_first_sender(attempted))

    outcomes = svc.send_to_owner("u1", {"title": "x"})

    assert [o.endpoint for o in outcomes] == [
        "https://push/dead",
        "https://push/live",
    ]
    assert outcomes[0].gone is True, "dead is dead even when the store is broken"
    assert outcomes[0].status_code == 410
    assert outcomes[1].ok is True, "the live endpoint still got its notification"
    assert attempted == ["https://push/dead", "https://push/live"]
    assert store.remove_calls == 1, "the prune was attempted, then ignored"


def test_the_send_route_answers_200_when_pruning_fails() -> None:
    """/webpush/send reports the batch instead of 500-ing on a broken store.

    ``raise_server_exceptions=False`` on purpose: it makes the client behave
    like a real server, turning an escaped exception into the **500** the
    browser would see instead of re-raising it into the test. Measured against
    the unprotected prune, that is exactly what came back.
    """
    fastapi = pytest.importorskip("fastapi")
    testclient = pytest.importorskip("fastapi.testclient")

    attempted: list[str] = []
    store = _StoreThatFailsToPrune()
    store.add("default", _sub("https://push/dead"))
    store.add("default", _sub("https://push/live"))
    svc = WebPushService(VAPID, store=store, sender=_dead_first_sender(attempted))
    app = fastapi.FastAPI()
    app.include_router(webpush_router(svc))
    client = testclient.TestClient(app, raise_server_exceptions=False)

    response = client.post("/webpush/send", json={"title": "x"})

    assert response.status_code == 200, "a broken store must not become a 500"
    assert response.json() == {"sent": 1, "total": 2}
    assert attempted == ["https://push/dead", "https://push/live"]


# ---------------------------------------------------------------------------
# The send is bounded, and it runs off the event loop
# ---------------------------------------------------------------------------


def test_send_bounds_the_push_request_with_a_timeout() -> None:
    """Every send carries an explicit timeout, and the caller can choose it.

    ``pywebpush.webpush`` declares ``timeout: float | None = None`` and forwards
    that ``None`` to ``requests.post`` (``WebPusher.send``'s
    ``kwargs.pop("timeout", 10000)`` never applies, because the key is always
    present), so nothing bounded the request: an endpoint that accepts the TCP
    connection and never answers hung the send forever.
    """
    calls: list[dict[str, Any]] = []

    def sender(**kwargs: Any) -> Any:
        """Record the kwargs and answer 201."""
        calls.append(kwargs)
        return _Response(201)

    WebPushService(VAPID, sender=sender).send(_sub("https://push/e1"), {"title": "x"})
    WebPushService(VAPID, sender=sender, timeout=2.5).send(
        _sub("https://push/e1"), {"title": "x"}
    )

    assert calls[0]["timeout"] == 10.0, "a bounded default, not None"
    assert calls[1]["timeout"] == 2.5


def test_the_timeout_reaches_pywebpush(monkeypatch: Any) -> None:
    """The default sender forwards the timeout to ``pywebpush.webpush`` itself."""
    pywebpush = pytest.importorskip("pywebpush")
    seen: list[dict[str, Any]] = []

    def record(**kwargs: Any) -> Any:
        """Record what pywebpush would have posted with."""
        seen.append(kwargs)
        return _Response(201)

    monkeypatch.setattr(pywebpush, "webpush", record)

    WebPushService(VAPID, timeout=3.0).send(_sub("https://push/e1"), {"title": "x"})

    assert seen[0]["timeout"] == 3.0


async def test_the_send_route_does_not_stall_the_event_loop() -> None:
    """A slow push service must not freeze the loop that streams patches.

    ``pywebpush`` posts with ``requests``: the call blocks. Called inline from
    this ``async`` route, three subscriptions against a sender that takes 0.3 s
    each stall the loop for the whole 0.90 s — the same loop that serves the
    WebSocket patch stream, so every connected app freezes with it. Measured
    against the pre-fix route, this heartbeat got **zero** ticks in that window
    (with a 1 s sender: zero ticks over 3.00 s); through ``run_in_threadpool``
    it ticks 89 times with a worst lateness of 0.01 s.
    """
    httpx = pytest.importorskip("httpx")
    fastapi = pytest.importorskip("fastapi")

    def slow_sender(**kwargs: Any) -> Any:
        """Take 0.3 s to answer, like a push service under load."""
        time.sleep(0.3)
        return _Response(201)

    store = InMemorySubscriptionStore()
    for index in range(3):
        store.add("default", _sub(f"https://push/e{index}"))
    app = fastapi.FastAPI()
    app.include_router(
        webpush_router(WebPushService(VAPID, store=store, sender=slow_sender))
    )

    gaps: list[float] = []

    async def heartbeat() -> None:
        """Tick every 10 ms, recording how late each tick actually was."""
        previous = time.perf_counter()
        while True:
            await asyncio.sleep(0.01)
            now = time.perf_counter()
            gaps.append(now - previous)
            previous = now

    beat = asyncio.create_task(heartbeat())
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://tw"
        ) as client:
            response = await client.post("/webpush/send", json={"title": "x"})
    finally:
        beat.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await beat

    assert response.json() == {"sent": 3, "total": 3}
    assert gaps, "the heartbeat must have ticked during the request"
    assert max(gaps) < 0.4, f"the loop stalled for {max(gaps):.2f}s"


# ---------------------------------------------------------------------------
# /unsubscribe is scoped to the router's owner
# ---------------------------------------------------------------------------


def test_unsubscribe_refuses_another_owners_endpoint() -> None:
    """A router removes only what its own owner holds.

    Two routers over one service is the shape the signature offers
    (``webpush_router(svc, owner="alice", prefix="/webpush/alice")``), and the
    store is keyed by endpoint alone — so an unscoped remove let alice's route
    delete bob's subscription and answer ``{"removed": true}``.
    """
    fastapi = pytest.importorskip("fastapi")
    testclient = pytest.importorskip("fastapi.testclient")

    service = WebPushService(VAPID, store=InMemorySubscriptionStore())
    service.add_subscription("bob", _sub("https://push/bob"))
    app = fastapi.FastAPI()
    app.include_router(webpush_router(service, owner="alice", prefix="/webpush/alice"))
    app.include_router(webpush_router(service, owner="bob", prefix="/webpush/bob"))
    client = testclient.TestClient(app)

    stolen = client.post(
        "/webpush/alice/unsubscribe", json={"endpoint": "https://push/bob"}
    )

    assert stolen.status_code == 200
    assert stolen.json() == {"removed": False}, "and no hint that bob holds it"
    assert len(service.store.list_for("bob")) == 1, "bob keeps his subscription"

    own = client.post("/webpush/bob/unsubscribe", json={"endpoint": "https://push/bob"})

    assert own.json() == {"removed": True}
    assert service.store.list_for("bob") == []


def test_unsubscribe_without_an_endpoint_answers_400() -> None:
    """A body with no endpoint is the caller's mistake, as in /subscribe.

    It used to fall through to ``remove("")`` and answer ``{"removed": false}``
    — a malformed request reported as a successful no-op, while ``/subscribe``
    already answered 400 to the very same body.
    """
    fastapi = pytest.importorskip("fastapi")
    testclient = pytest.importorskip("fastapi.testclient")

    service = WebPushService(VAPID, store=InMemorySubscriptionStore())
    app = fastapi.FastAPI()
    app.include_router(webpush_router(service))
    client = testclient.TestClient(app)

    response = client.post("/webpush/unsubscribe", json={})

    assert response.status_code == 400
    assert "endpoint" in response.json()["detail"]
