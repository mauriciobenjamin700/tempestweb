"""tempestweb.server — Mode B FastAPI host (WebSocket + SSE) and WebPush.

Re-exports the server factory/class and the WebPush service (P3). See
``docs/plan.md`` (Trilhos B e P) and ``docs/contract.md`` for the wire format
carried over both transports.
"""

from __future__ import annotations

from tempestweb.server.app import TempestWebServer, create_app
from tempestweb.server.security import (
    Credentials,
    SecurityConfig,
    jwt_authenticator,
    token_authenticator,
    verify_jwt,
)
from tempestweb.server.sessions import (
    InProcessRouter,
    RedisSessionRouter,
    SessionRouter,
)
from tempestweb.server.webpush import (
    InMemorySubscriptionStore,
    SendOutcome,
    SubscriptionStore,
    VapidConfig,
    VapidKeys,
    WebPushError,
    WebPushService,
    generate_vapid_keys,
    webpush_router,
)

__all__ = [
    "Credentials",
    "InMemorySubscriptionStore",
    "InProcessRouter",
    "RedisSessionRouter",
    "SecurityConfig",
    "SessionRouter",
    "SendOutcome",
    "SubscriptionStore",
    "TempestWebServer",
    "VapidConfig",
    "VapidKeys",
    "WebPushError",
    "WebPushService",
    "create_app",
    "generate_vapid_keys",
    "jwt_authenticator",
    "token_authenticator",
    "verify_jwt",
    "webpush_router",
]
