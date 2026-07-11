"""Server-side security for Mode B (Track S — S0/S1/S3).

The Mode B host is unauthenticated and same-origin-agnostic by default. This
module adds the pieces a public deployment needs, all opt-in via
:class:`SecurityConfig` passed to :func:`tempestweb.server.create_app`:

- **S0 — auth gate:** an ``authenticate`` callable is run on every WebSocket
  upgrade and every SSE request *before* a session is created; a falsy result
  (or a raised error) rejects the connection (WS close ``1008`` / HTTP ``401``).
- **S1 — origin allowlist:** ``allowed_origins`` both installs Starlette's
  ``CORSMiddleware`` (for the HTTP/SSE surface) and hard-checks the ``Origin``
  header on the WebSocket upgrade (CORS middleware does *not* guard WebSockets).
- **S3 — server-side JWT:** :func:`verify_jwt` checks a token's **signature and
  expiry** (unlike the client-side ``observability.auth.decode_jwt``, which only
  reads claims). :func:`jwt_authenticator` / :func:`token_authenticator` build
  ready-made ``authenticate`` callables.

Heavy deps stay lazy: importing this module never requires PyJWT — it is only
touched when :func:`verify_jwt` runs.
"""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "Credentials",
    "SecurityConfig",
    "jwt_authenticator",
    "token_authenticator",
    "verify_jwt",
]

#: An auth predicate: given the connection's credentials, allow (True) or reject
#: (False). May be sync or async; raising is treated as a rejection.
Authenticate = Callable[["Credentials"], bool | Awaitable[bool]]


@dataclass(slots=True)
class Credentials:
    """The authentication material extracted from a connection.

    Attributes:
        token: The bearer token — from ``Authorization: Bearer <t>``, the
            ``?token=`` query parameter, or ``None`` when absent.
        origin: The request ``Origin`` header, or ``None``.
        headers: The request headers (lower-cased keys).
        query: The request query parameters.
    """

    token: str | None
    origin: str | None
    headers: Mapping[str, str]
    query: Mapping[str, str]


@dataclass(slots=True)
class SecurityConfig:
    """Opt-in security controls for the Mode B host.

    Attributes:
        authenticate: Run on every WS upgrade / SSE request before a session is
            created; a falsy return or a raised error rejects the connection.
            ``None`` (default) leaves the host open — dev only.
        allowed_origins: If set, the exact ``Origin`` values allowed to connect
            (installs CORS for HTTP/SSE and checks the WS upgrade). ``["*"]``
            allows any origin (CORS wildcard; the WS check is skipped).
        max_connections: Cap on concurrent live sessions (WS + SSE combined). A
            connection over the cap is refused (WS close ``1013``; SSE ``503``).
            ``None`` = unbounded (S2).
        max_message_bytes: Reject an SSE ``POST`` body larger than this many
            bytes with ``413`` (S2). ``None`` = unbounded.
        security_headers: When ``True``, add hardening response headers
            (``X-Content-Type-Options``, ``Referrer-Policy``, ``X-Frame-Options``)
            to every HTTP response (S6).
        hsts: When ``True`` (implies ``security_headers``), also send
            ``Strict-Transport-Security`` — enable only behind HTTPS.
        content_security_policy: An explicit ``Content-Security-Policy`` value to
            send when set (app-specific; the shell uses inline module scripts, so
            a strict CSP needs a nonce/hash you supply here).
    """

    authenticate: Authenticate | None = None
    allowed_origins: list[str] | None = field(default=None)
    max_connections: int | None = None
    max_message_bytes: int | None = None
    security_headers: bool = False
    hsts: bool = False
    content_security_policy: str | None = None

    @property
    def wants_headers(self) -> bool:
        """Whether any response-header hardening is enabled (S6)."""
        return (
            self.security_headers
            or self.hsts
            or self.content_security_policy is not None
        )

    def header_values(self) -> dict[str, str]:
        """The hardening response headers implied by this config (S6)."""
        headers: dict[str, str] = {}
        if self.security_headers or self.hsts:
            headers["X-Content-Type-Options"] = "nosniff"
            headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            headers["X-Frame-Options"] = "DENY"
        if self.hsts:
            headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains"
            )
        if self.content_security_policy is not None:
            headers["Content-Security-Policy"] = self.content_security_policy
        return headers

    @property
    def origins_wildcard(self) -> bool:
        """Whether the origin allowlist is the ``*`` wildcard."""
        return self.allowed_origins is not None and "*" in self.allowed_origins

    def origin_allowed(self, origin: str | None) -> bool:
        """Whether ``origin`` may connect under this config.

        Args:
            origin: The request ``Origin`` header value, or ``None``.

        Returns:
            ``True`` when no allowlist is configured, the allowlist is ``*``, or
            ``origin`` is explicitly listed.
        """
        if self.allowed_origins is None or self.origins_wildcard:
            return True
        return origin in self.allowed_origins


def _bearer_token(headers: Mapping[str, str], query: Mapping[str, str]) -> str | None:
    """Extract a bearer token from an ``Authorization`` header or ``?token=``."""
    auth = headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip()
    token = query.get("token")
    return token or None


def verify_jwt(
    token: str,
    key: str,
    *,
    algorithms: tuple[str, ...] = ("HS256",),
    audience: str | None = None,
    issuer: str | None = None,
) -> dict[str, Any]:
    """Verify a JWT's signature and expiry, returning its claims.

    Unlike ``observability.auth.decode_jwt`` (which only base64url-decodes the
    payload), this validates the signature and standard time claims.

    Args:
        token: The compact-serialization JWT.
        key: The signing key / secret.
        algorithms: Accepted signing algorithms.
        audience: Expected ``aud`` claim, if any.
        issuer: Expected ``iss`` claim, if any.

    Returns:
        The verified claims.

    Raises:
        RuntimeError: If PyJWT is not installed.
        ValueError: If the token is invalid, expired, or fails a claim check.
    """
    try:
        import jwt  # type: ignore[import-not-found]  # optional [auth] extra
    except ImportError as exc:  # pragma: no cover - exercised via the error path
        raise RuntimeError(
            "PyJWT is required for verify_jwt; install "
            'tempest-fastapi-sdk[auth] or "pyjwt".'
        ) from exc
    try:
        return dict(
            jwt.decode(
                token,
                key,
                algorithms=list(algorithms),
                audience=audience,
                issuer=issuer,
            )
        )
    except jwt.PyJWTError as exc:
        raise ValueError(f"invalid token: {exc}") from exc


def jwt_authenticator(
    key: str,
    *,
    algorithms: tuple[str, ...] = ("HS256",),
    audience: str | None = None,
    issuer: str | None = None,
) -> Authenticate:
    """Build an ``authenticate`` callable that verifies a bearer JWT (S3).

    Args:
        key: The signing key / secret.
        algorithms: Accepted signing algorithms.
        audience: Expected ``aud`` claim, if any.
        issuer: Expected ``iss`` claim, if any.

    Returns:
        A predicate that accepts a connection with a valid, unexpired JWT.
    """

    def _authenticate(credentials: Credentials) -> bool:
        if not credentials.token:
            return False
        try:
            verify_jwt(
                credentials.token,
                key,
                algorithms=algorithms,
                audience=audience,
                issuer=issuer,
            )
        except (ValueError, RuntimeError):
            return False
        return True

    return _authenticate


def token_authenticator(secret: str) -> Authenticate:
    """Build an ``authenticate`` callable for a shared-secret token.

    Compares the connection's bearer token to ``secret`` with a constant-time
    check (the ``X-Token`` convention). An **empty** secret disables the gate
    (always allows) — dev-only, matching the framework's "empty secret disables
    auth" rule.

    Args:
        secret: The shared secret; empty disables the gate.

    Returns:
        A predicate that accepts a connection whose token equals ``secret``.
    """

    def _authenticate(credentials: Credentials) -> bool:
        if not secret:
            return True
        token = credentials.token or ""
        return hmac.compare_digest(token, secret)

    return _authenticate
