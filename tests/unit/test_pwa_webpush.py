"""Unit tests for server-side WebPush (P3).

Covers ``tempestweb.server.webpush``: VAPID config, the in-memory subscription
store and the VAPID-signed sender. The pywebpush callable is mocked so these run
without the (lazy) dependency installed.
"""

from __future__ import annotations

import json
from typing import Any

from tempestweb.server.webpush import (
    InMemorySubscriptionStore,
    SendOutcome,
    VapidConfig,
    WebPushError,
    WebPushService,
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
