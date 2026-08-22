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
import time
from collections import deque
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "Credentials",
    "RateLimiter",
    "SecurityConfig",
    "jwt_authenticator",
    "resolve_client_ip",
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
    client_ip: str | None = None


@dataclass(slots=True)
class SecurityConfig:
    """Opt-in security controls for the Mode B host.

    Attributes:
        authenticate: Run on every WS upgrade / SSE request before a session is
            created; a falsy return or a raised error rejects the connection.
            ``None`` (default) leaves the host open — dev only.
        trusted_proxies: Peer addresses whose ``X-Forwarded-For`` header may be
            believed — the reverse proxies actually in front of this host, or
            ``["*"]`` to trust every peer. ``None`` (default) ignores the header
            entirely and uses the socket's peer address, because a client can put
            anything in it: with the header trusted unconditionally, a flood needs
            only a fresh fake value per request to be counted as a fresh client,
            which defeats every per-IP limit below.
        allowed_origins: If set, the exact ``Origin`` values allowed to connect
            (installs CORS for HTTP/SSE and checks the WS upgrade). ``["*"]``
            allows any origin (CORS wildcard; the WS check is skipped).
        max_connections: Cap on concurrent live sessions (WS + SSE combined). A
            connection over the cap is refused (WS close ``1013``; SSE ``503``).
            ``None`` = unbounded (S2).
        max_message_bytes: Reject an SSE ``POST`` body larger than this many
            bytes with ``413`` (S2). ``None`` = unbounded.
        max_connections_per_minute: Per-client-IP cap on new connections in a
            rolling 60s window; a flood is refused (WS ``1013`` / SSE ``429``).
            The address comes from the socket's peer, or from
            ``X-Forwarded-For`` when ``trusted_proxies`` says the header may be
            believed. ``None`` = no per-IP limit (S2). Pair with a reverse-proxy
            limiter for defense in depth.
        max_events_per_minute: Per-client-IP cap on *inbound envelopes* in a
            rolling 60s window — clicks, input, ``native_result`` frames — counted
            across both legs: an SSE ``POST /sse/{id}`` over budget answers
            ``429``, and a WebSocket frame over budget closes the socket with
            ``1013``. Separate from ``max_connections_per_minute`` because the
            budgets differ by orders of magnitude: one connection per client, but
            one envelope per interaction. ``None`` = unbounded (S2). Size it above
            the busiest legitimate interaction rate of your app.
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
    trusted_proxies: list[str] | None = field(default=None)
    allowed_origins: list[str] | None = field(default=None)
    max_connections: int | None = None
    max_message_bytes: int | None = None
    max_connections_per_minute: int | None = None
    max_events_per_minute: int | None = None
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
            headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
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


def resolve_client_ip(
    headers: Mapping[str, str],
    peer: str | None,
    trusted_proxies: list[str] | None,
) -> str | None:
    """Resolve the address a per-IP limit should be charged to.

    ``X-Forwarded-For`` is client-supplied data. It is read only when the peer is
    a proxy the deployment declared trustworthy, and then from the **right**: a
    proxy appends the address it saw, so the right-most entry that is not itself
    a trusted proxy is the furthest hop this deployment can actually vouch for.
    Anything the client prepended sits to the left of that and is ignored.

    Args:
        headers: The request headers (lower-cased keys).
        peer: The socket's peer address, if known.
        trusted_proxies: Peer addresses whose header may be believed, ``["*"]``
            for any peer, or ``None`` to ignore the header.

    Returns:
        The resolved client address, or ``None`` when nothing is known.
    """
    if not trusted_proxies:
        return peer
    wildcard = "*" in trusted_proxies
    if not wildcard and peer not in trusted_proxies:
        return peer
    forwarded = headers.get("x-forwarded-for")
    if not forwarded:
        return peer
    hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
    if not hops:
        return peer
    if wildcard:
        return hops[0]
    for hop in reversed(hops):
        if hop not in trusted_proxies:
            return hop
    return peer


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
    require_expiry: bool = True,
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
        require_expiry: Refuse a token that carries no ``exp`` claim. PyJWT only
            checks an expiry that is *present*, so without this a token minted
            without ``exp`` is accepted forever — which is not what "verifies
            the expiry" can mean. Set ``False`` only for a token whose lifetime
            something else bounds.

    Returns:
        The verified claims.

    Raises:
        RuntimeError: If PyJWT is not installed.
        ValueError: If the token is invalid, expired, missing a required claim,
            or fails a claim check.
    """
    try:
        import jwt  # type: ignore[import-not-found]  # optional [auth] extra
    except ImportError as exc:  # pragma: no cover - exercised via the error path
        raise RuntimeError(
            "PyJWT is required for verify_jwt; install "
            'tempest-fastapi-sdk[auth] or "pyjwt".'
        ) from exc
    required: list[str] = ["exp"] if require_expiry else []
    try:
        return dict(
            jwt.decode(
                token,
                key,
                algorithms=list(algorithms),
                audience=audience,
                issuer=issuer,
                options={"require": required},
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
    require_expiry: bool = True,
) -> Authenticate:
    """Build an ``authenticate`` callable that verifies a bearer JWT (S3).

    Args:
        key: The signing key / secret.
        algorithms: Accepted signing algorithms.
        audience: Expected ``aud`` claim, if any.
        issuer: Expected ``iss`` claim, if any.
        require_expiry: Refuse a token with no ``exp`` claim (see
            :func:`verify_jwt`).

    Returns:
        A predicate that accepts a connection with a valid, unexpired JWT.
    """

    def _authenticate(credentials: Credentials) -> bool:
        """Accept the connection when its bearer token is a valid JWT.

        A missing token is refused without attempting verification. Both
        failures ``verify_jwt`` can raise — a malformed or expired token
        (``ValueError``) and a missing signing dependency (``RuntimeError``) —
        are answered as "not authenticated" rather than propagating, so the
        handshake never turns into a 500 for an unauthenticated client.

        Args:
            credentials: The connection's token, origin, headers and query.

        Returns:
            ``True`` when the token verifies against the enclosing key.
        """
        if not credentials.token:
            return False
        try:
            verify_jwt(
                credentials.token,
                key,
                algorithms=algorithms,
                audience=audience,
                issuer=issuer,
                require_expiry=require_expiry,
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
        """Accept the connection when its bearer token equals the shared secret.

        The comparison is constant-time, so a rejected token leaks nothing about
        how much of it was right. An empty enclosing secret short-circuits to
        ``True``, which is the documented dev-only way to disable the gate.

        Args:
            credentials: The connection's token, origin, headers and query.

        Returns:
            ``True`` when the gate is disabled or the token matches.
        """
        if not secret:
            return True
        token = credentials.token or ""
        return hmac.compare_digest(token, secret)

    return _authenticate


class RateLimiter:
    """A per-key rolling-window rate limiter (S2 — per-IP connection flood).

    Allows at most ``limit`` events per ``window`` seconds per key. A key's own
    timestamps are pruned when it is touched, and every ``sweep_every`` calls the
    whole map is swept for keys that have gone quiet — without that sweep the map
    keeps one entry per address ever seen, which is memory a flood of distinct
    (or forged) addresses can grow at will. Uses a monotonic clock; not shared
    across processes (per-worker).
    """

    #: Calls between full sweeps of the map for keys whose window has passed.
    DEFAULT_SWEEP_EVERY: int = 256

    def __init__(
        self,
        limit: int,
        *,
        window: float = 60.0,
        sweep_every: int = DEFAULT_SWEEP_EVERY,
    ) -> None:
        """Initialize the limiter.

        Args:
            limit: Max events allowed per key within ``window``.
            window: The rolling window in seconds.
            sweep_every: How many calls between full sweeps for quiet keys.
        """
        self._limit: int = limit
        self._window: float = window
        self._sweep_every: int = max(1, sweep_every)
        self._calls: int = 0
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str, *, now: float | None = None) -> bool:
        """Record an event for ``key`` and report whether it is within the limit.

        Args:
            key: The client key (e.g. an IP address).
            now: Override the current monotonic time (tests).

        Returns:
            ``True`` if the event is allowed, ``False`` if it exceeds the limit.
        """
        current = time.monotonic() if now is None else now
        self._calls += 1
        if self._calls % self._sweep_every == 0:
            self._sweep(current)
        cutoff = current - self._window
        bucket = self._hits.get(key)
        if bucket is None:
            bucket = self._hits[key] = deque()
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= self._limit:
            return False
        bucket.append(current)
        return True

    def _sweep(self, now: float) -> None:
        """Drop every key whose most recent event has fallen out of the window.

        Args:
            now: The current monotonic time.
        """
        cutoff = now - self._window
        stale = [
            key for key, hits in self._hits.items() if not hits or hits[-1] <= cutoff
        ]
        for key in stale:
            del self._hits[key]

    def tracked_keys(self) -> int:
        """How many keys the limiter currently holds state for."""
        return len(self._hits)
