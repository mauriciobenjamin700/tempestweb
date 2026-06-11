"""tempestweb.server — Mode B FastAPI host (WebSocket + SSE) and WebPush.

Re-exports the server factory/class and the WebPush service (P3). See
``docs/plan.md`` (Trilhos B e P) and ``docs/contract.md`` for the wire format
carried over both transports.
"""

from __future__ import annotations

from tempestweb.server.app import TempestWebServer, create_app
from tempestweb.server.webpush import (
    InMemorySubscriptionStore,
    SendOutcome,
    SubscriptionStore,
    VapidConfig,
    WebPushError,
    WebPushService,
)

__all__ = [
    "InMemorySubscriptionStore",
    "SendOutcome",
    "SubscriptionStore",
    "TempestWebServer",
    "VapidConfig",
    "WebPushError",
    "WebPushService",
    "create_app",
]
