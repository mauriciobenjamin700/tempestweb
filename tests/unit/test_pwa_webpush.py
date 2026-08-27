"""Unit tests for server-side WebPush (P3).

Covers ``tempestweb.server.webpush``: VAPID config, the in-memory subscription
store and the VAPID-signed sender. The pywebpush callable is mocked so these run
without the (lazy) dependency installed.

**The mock was also the blind spot.** Every send test injected a sender raising
``WebPushError``, so the branch that prunes a dead endpoint always matched — and
the real sender, which raises ``pywebpush``'s own ``WebPushException``, never did.
Measured against FCM on 2026-08-27: an unsubscribed endpoint answers ``410 Gone``
and the subscription stayed in the store, send after send. The tests at the end of
this file cover the translation that closes it.
"""

from __future__ import annotations

import base64
import json
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
    """send invokes the sender with the VAPID key and a JSON-encoded payload."""
    calls: list[dict[str, Any]] = []

    def fake_sender(**kwargs: Any) -> None:
        calls.append(kwargs)

    svc = WebPushService(VAPID, sender=fake_sender)
    outcome = svc.send(_sub("https://push/e1"), {"title": "Hi", "badge_count": 2})
    assert outcome.ok is True
    assert outcome.status_code == 201
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
    """201 comes from the push service's response, not from a constant."""
    pywebpush = pytest.importorskip("pywebpush")
    monkeypatch.setattr(pywebpush, "webpush", lambda **kwargs: _Response(201))

    service = WebPushService(VAPID, store=InMemorySubscriptionStore())
    outcome = service.send(_sub("https://push/live"), {"title": "x"})

    assert outcome.ok is True
    assert outcome.status_code == 201


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
