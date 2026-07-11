"""Server-side WebPush: VAPID config, subscription store and sender (P3).

The **server owns the endpoint and the subscription store**; the browser client
(``client/push/web-push-client.js``) owns the subscribe flow and POSTs the raw
subscription here. This module mirrors the ``tempest-fastapi-sdk[webpush]``
patterns (pywebpush + VAPID), but keeps the heavy dependency lazy so importing
``tempestweb.server.webpush`` never requires ``pywebpush`` to be installed — the
dependency is only touched at first send.

VAPID keys / secrets are read from the environment and **never committed**. An
empty private key disables sending (dev-only), matching the framework's
"empty secret disables auth" convention.

Endpoints a host app wires (the framework does not dictate the schema):
    POST   /webpush/subscribe   -> WebPushService.add_subscription
    DELETE /webpush/my          -> WebPushService.remove_subscription

Dead endpoints (HTTP 410 Gone from the push service) are pruned automatically on
send.
"""

from __future__ import annotations

import base64
import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

#: A subscription's primary key is its push endpoint URL (globally unique).
SubscriptionInfo = dict[str, Any]


def _b64url(raw: bytes) -> str:
    """Base64url-encode bytes without padding (the WebPush/VAPID convention)."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


@dataclass(slots=True)
class VapidKeys:
    """A freshly generated VAPID keypair (base64url, unpadded).

    Attributes:
        public_key: The application server key the browser subscribes with
            (65-byte uncompressed P-256 point).
        private_key: The signing key the server keeps secret (32-byte scalar).
    """

    public_key: str
    private_key: str


def generate_vapid_keys() -> VapidKeys:
    """Generate a P-256 VAPID keypair for WebPush.

    The public key is the browser ``applicationServerKey`` and the private key
    signs push requests server-side. Store the private key as a secret (env var)
    — never commit it.

    Returns:
        The base64url-encoded :class:`VapidKeys`.

    Raises:
        RuntimeError: If ``cryptography`` is not installed.
    """
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
    except ImportError as exc:  # pragma: no cover - exercised via the error path
        raise RuntimeError(
            "cryptography is required to generate VAPID keys; install "
            'tempest-fastapi-sdk[webpush] or "cryptography".'
        ) from exc
    private = ec.generate_private_key(ec.SECP256R1())
    public_point = private.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    private_scalar = private.private_numbers().private_value.to_bytes(32, "big")
    return VapidKeys(
        public_key=_b64url(public_point),
        private_key=_b64url(private_scalar),
    )


@dataclass(slots=True)
class VapidConfig:
    """VAPID credentials and contact for signing WebPush requests.

    Attributes:
        public_key: Base64url VAPID public key (shared with the browser client).
        private_key: Base64url VAPID private key (secret; empty disables sending).
        subject: VAPID ``sub`` claim — a ``mailto:`` or ``https:`` contact.
    """

    public_key: str = ""
    private_key: str = ""
    subject: str = "mailto:admin@example.com"

    @property
    def enabled(self) -> bool:
        """Whether sending is enabled (a private key is configured).

        Returns:
            True when a non-empty private key is present.
        """
        return bool(self.private_key)

    @classmethod
    def from_env(cls, prefix: str = "VAPID_") -> VapidConfig:
        """Build a config from environment variables.

        Reads ``<prefix>PUBLIC_KEY``, ``<prefix>PRIVATE_KEY`` and
        ``<prefix>SUBJECT``. Missing values fall back to the dataclass defaults.

        Args:
            prefix: Environment variable prefix.

        Returns:
            The populated config.
        """
        return cls(
            public_key=os.environ.get(f"{prefix}PUBLIC_KEY", ""),
            private_key=os.environ.get(f"{prefix}PRIVATE_KEY", ""),
            subject=os.environ.get(f"{prefix}SUBJECT", "mailto:admin@example.com"),
        )


class SubscriptionStore(Protocol):
    """Storage protocol for push subscriptions keyed by endpoint.

    A host app supplies a real implementation (SQLAlchemy, Redis, …); the default
    ``InMemorySubscriptionStore`` covers tests and single-process dev.
    """

    def add(self, owner: str, subscription: SubscriptionInfo) -> None:
        """Persist a subscription for an owner."""
        ...

    def remove(self, endpoint: str) -> bool:
        """Remove a subscription by endpoint. Returns whether one was removed."""
        ...

    def list_for(self, owner: str) -> list[SubscriptionInfo]:
        """Return all subscriptions for an owner ([] when none)."""
        ...

    def all(self) -> list[SubscriptionInfo]:
        """Return every stored subscription ([] when none)."""
        ...


@dataclass(slots=True)
class InMemorySubscriptionStore:
    """A simple in-memory subscription store (dev/tests).

    Subscriptions are keyed by their push ``endpoint`` so re-subscribing the same
    browser replaces, never duplicates. Each stored record carries its ``owner``.

    Attributes:
        _by_endpoint: Internal endpoint -> {owner, subscription} mapping.
    """

    _by_endpoint: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add(self, owner: str, subscription: SubscriptionInfo) -> None:
        """Persist (or replace) a subscription for an owner.

        Args:
            owner: The owning user/topic identifier.
            subscription: The browser push subscription JSON (needs ``endpoint``).

        Raises:
            ValueError: If the subscription has no ``endpoint``.
        """
        endpoint = subscription.get("endpoint")
        if not endpoint:
            raise ValueError("subscription must include an endpoint")
        self._by_endpoint[endpoint] = {"owner": owner, "subscription": subscription}

    def remove(self, endpoint: str) -> bool:
        """Remove a subscription by endpoint.

        Args:
            endpoint: The push endpoint URL.

        Returns:
            True when a subscription was removed, False when absent.
        """
        return self._by_endpoint.pop(endpoint, None) is not None

    def list_for(self, owner: str) -> list[SubscriptionInfo]:
        """Return all subscriptions for an owner.

        Args:
            owner: The owning identifier.

        Returns:
            The subscriptions ([] when the owner has none).
        """
        return [
            rec["subscription"]
            for rec in self._by_endpoint.values()
            if rec["owner"] == owner
        ]

    def all(self) -> list[SubscriptionInfo]:
        """Return every stored subscription.

        Returns:
            All subscriptions ([] when empty).
        """
        return [rec["subscription"] for rec in self._by_endpoint.values()]


@dataclass(slots=True)
class SendOutcome:
    """The result of attempting to send to one subscription.

    Attributes:
        endpoint: The target push endpoint.
        ok: Whether the push was accepted.
        status_code: The push service HTTP status (when known).
        gone: Whether the endpoint is dead (HTTP 410/404) and was pruned.
        error: A human-readable error when ``ok`` is False.
    """

    endpoint: str
    ok: bool
    status_code: int | None = None
    gone: bool = False
    error: str | None = None


#: A sender callable matching ``pywebpush.webpush``'s essential signature. It is
#: injected so tests can mock it; production resolves the real ``pywebpush.webpush``.
WebPushSender = Callable[..., Any]


def _default_sender() -> WebPushSender:
    """Resolve the real ``pywebpush.webpush`` callable, lazily.

    Returns:
        The ``pywebpush.webpush`` function.

    Raises:
        RuntimeError: If ``pywebpush`` is not installed.
    """
    try:
        from pywebpush import webpush as _webpush
    except ImportError as exc:  # pragma: no cover - exercised via mock in tests
        raise RuntimeError(
            "pywebpush is required to send WebPush; install "
            'tempest-fastapi-sdk[webpush] or "pywebpush".'
        ) from exc
    sender: WebPushSender = _webpush
    return sender


class WebPushError(Exception):
    """Raised by a sender to signal a push delivery failure.

    Attributes:
        status_code: The push service HTTP status, when available.
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Initialize the error.

        Args:
            message: The failure message.
            status_code: The push service HTTP status, when known.
        """
        super().__init__(message)
        self.status_code = status_code


class WebPushService:
    """Owns the subscription store and sends VAPID-signed push messages.

    Args:
        vapid: The VAPID configuration.
        store: The subscription store (defaults to in-memory).
        sender: The push sender callable (defaults to ``pywebpush.webpush``,
            resolved lazily on first send; injected in tests).
    """

    def __init__(
        self,
        vapid: VapidConfig,
        store: SubscriptionStore | None = None,
        sender: WebPushSender | None = None,
    ) -> None:
        """Initialize the service."""
        self.vapid = vapid
        self.store: SubscriptionStore = store or InMemorySubscriptionStore()
        self._sender = sender

    def _resolve_sender(self) -> WebPushSender:
        """Return the configured sender, resolving the default lazily.

        Returns:
            The sender callable.
        """
        if self._sender is None:
            self._sender = _default_sender()
        return self._sender

    def add_subscription(self, owner: str, subscription: SubscriptionInfo) -> None:
        """Persist a browser push subscription for an owner (POST /webpush/subscribe).

        Args:
            owner: The owning user/topic identifier.
            subscription: The browser push subscription JSON.
        """
        self.store.add(owner, subscription)

    def remove_subscription(self, endpoint: str) -> bool:
        """Remove a subscription by endpoint (DELETE /webpush/my).

        Args:
            endpoint: The push endpoint URL.

        Returns:
            Whether a subscription was removed.
        """
        return self.store.remove(endpoint)

    def send(
        self, subscription: SubscriptionInfo, payload: dict[str, Any]
    ) -> SendOutcome:
        """Send one VAPID-signed push to a single subscription.

        A dead endpoint (HTTP 410/404) is pruned from the store and reported with
        ``gone=True``. Sending is a no-op success-free outcome when VAPID is
        disabled (no private key), so dev environments degrade cleanly.

        Args:
            subscription: The target subscription JSON (needs ``endpoint``).
            payload: The JSON-able notification payload (title/body/data/...).

        Returns:
            The send outcome.
        """
        endpoint = str(subscription.get("endpoint", ""))
        if not self.vapid.enabled:
            return SendOutcome(
                endpoint=endpoint, ok=False, error="VAPID disabled (no private key)"
            )

        sender = self._resolve_sender()
        try:
            sender(
                subscription_info=subscription,
                data=json.dumps(payload),
                vapid_private_key=self.vapid.private_key,
                vapid_claims={"sub": self.vapid.subject},
            )
        except WebPushError as exc:
            gone = exc.status_code in (404, 410)
            if gone:
                self.store.remove(endpoint)
            return SendOutcome(
                endpoint=endpoint,
                ok=False,
                status_code=exc.status_code,
                gone=gone,
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001 - report any sender failure
            return SendOutcome(endpoint=endpoint, ok=False, error=str(exc))
        return SendOutcome(endpoint=endpoint, ok=True, status_code=201)

    def send_to_owner(self, owner: str, payload: dict[str, Any]) -> list[SendOutcome]:
        """Send a push to every subscription an owner has.

        Returns [] when the owner has no subscriptions (never an error).

        Args:
            owner: The owning identifier.
            payload: The notification payload.

        Returns:
            One outcome per subscription ([] when the owner has none).
        """
        return [self.send(sub, payload) for sub in self.store.list_for(owner)]

    def broadcast(self, payload: dict[str, Any]) -> list[SendOutcome]:
        """Send a push to every stored subscription.

        Args:
            payload: The notification payload.

        Returns:
            One outcome per subscription ([] when the store is empty).
        """
        return [self.send(sub, payload) for sub in self.store.all()]


def webpush_router(
    service: WebPushService,
    *,
    owner: str = "default",
    prefix: str = "/webpush",
) -> Any:  # noqa: ANN401 - a FastAPI APIRouter (imported lazily)
    """Build a FastAPI router exposing the WebPush subscribe/send endpoints.

    Mount it on a host app with ``app.include_router(webpush_router(service))``.
    Endpoints (all JSON):

    - ``GET  {prefix}/vapid-public-key`` → ``{"public_key": ...}`` for the client
      to subscribe with.
    - ``POST {prefix}/subscribe`` (body: the browser subscription JSON) → stores
      it under ``owner``.
    - ``POST {prefix}/unsubscribe`` (body: ``{"endpoint": ...}``) → removes it.
    - ``POST {prefix}/send`` (body: the notification payload) → pushes to every
      subscription of ``owner``; returns ``{"sent", "total"}``.

    A single fixed ``owner`` keeps the default multi-tenant-free; an app with
    real users wires its own routes around the same :class:`WebPushService`,
    resolving the owner from auth.

    Args:
        service: The WebPush service (store + sender).
        owner: The owner every subscription is filed under (default ``"default"``).
        prefix: The route prefix.

    Returns:
        A configured ``fastapi.APIRouter``.

    Raises:
        RuntimeError: If FastAPI is not installed.
    """
    try:
        from fastapi import APIRouter, Body
    except ImportError as exc:  # pragma: no cover - server extra always ships it
        raise RuntimeError(
            "FastAPI is required for webpush_router; install "
            "tempest-fastapi-sdk or the server extra."
        ) from exc

    router = APIRouter(prefix=prefix, tags=["webpush"])

    @router.get("/vapid-public-key")
    async def vapid_public_key() -> dict[str, str]:
        """Return the VAPID public key the browser subscribes with."""
        return {"public_key": service.vapid.public_key}

    @router.post("/subscribe")
    async def subscribe(
        subscription: SubscriptionInfo = Body(...),  # noqa: B008 - FastAPI param
    ) -> dict[str, bool]:
        """Persist a browser push subscription under the router's owner."""
        service.add_subscription(owner, subscription)
        return {"ok": True}

    @router.post("/unsubscribe")
    async def unsubscribe(
        body: dict[str, Any] = Body(...),  # noqa: B008 - FastAPI param
    ) -> dict[str, bool]:
        """Remove a subscription by its endpoint."""
        removed = service.remove_subscription(str(body.get("endpoint", "")))
        return {"removed": removed}

    @router.post("/send")
    async def send(
        payload: dict[str, Any] = Body(...),  # noqa: B008 - FastAPI param
    ) -> dict[str, int]:
        """Push a notification payload to every subscription of the owner."""
        outcomes = service.send_to_owner(owner, payload)
        return {"sent": sum(1 for o in outcomes if o.ok), "total": len(outcomes)}

    return router
