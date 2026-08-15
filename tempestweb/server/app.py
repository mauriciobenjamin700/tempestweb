"""FastAPI host for Mode B — Python on the server, thin JS client.

Exposes one application ``view`` (the identical function Mode A runs in the
browser) over two transports that carry the same wire format:

- ``GET /ws`` — a WebSocket; the duplex
  :class:`~tempestweb.transports.websocket.WebSocketTransport` channel.
- ``GET /sse?session=<id>`` + ``POST /sse/{session_id}`` — the
  :class:`~tempestweb.transports.sse.SSETransport` pair (patches down the event
  stream, events/native-results up via POST).

Each connection drives its own :class:`~tempestweb.runtime.session.AppSession`,
so state is fully isolated between clients. For SSE, sessions are tracked in a
registry keyed by the client-chosen ``session`` id so the POST endpoint can route
inbound envelopes and a dropped stream can reconnect with ``Last-Event-ID``.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable, Mapping
from typing import Any, Generic, TypeVar

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.websockets import WebSocket

from tempest_core import App, Widget
from tempestweb.runtime.session import AppSession
from tempestweb.server.security import (
    Credentials,
    RateLimiter,
    SecurityConfig,
    _bearer_token,
)
from tempestweb.server.sessions import InProcessRouter, SessionRouter, Teardown
from tempestweb.transports.base import PatchTransport
from tempestweb.transports.sse import SSETransport
from tempestweb.transports.websocket import WebSocketTransport

__all__ = ["TempestWebServer", "create_app"]

S = TypeVar("S")


async def _authorize(security: SecurityConfig, credentials: Credentials) -> bool:
    """Run the origin allowlist + auth predicate for a connection.

    Args:
        security: The active security config.
        credentials: The connection's extracted credentials.

    Returns:
        ``True`` when the connection is allowed, ``False`` otherwise. A raised
        error from a custom ``authenticate`` is treated as a rejection.
    """
    if not security.origin_allowed(credentials.origin):
        return False
    if security.authenticate is None:
        return True
    try:
        result = security.authenticate(credentials)
        if isinstance(result, bool):
            return result
        return bool(await result)
    except Exception:  # noqa: BLE001 - any auth error is a rejection, not a 500
        return False


def _credentials_from_headers(
    headers: Mapping[str, str],
    query: Mapping[str, str],
    peer: str | None = None,
) -> Credentials:
    """Build :class:`Credentials` from request headers + query params.

    ``client_ip`` is the first ``X-Forwarded-For`` hop (set by the reverse proxy)
    or the direct peer address.
    """
    lowered = {k.lower(): v for k, v in headers.items()}
    forwarded = lowered.get("x-forwarded-for")
    client_ip = forwarded.split(",")[0].strip() if forwarded else peer
    return Credentials(
        token=_bearer_token(lowered, query),
        origin=lowered.get("origin"),
        headers=lowered,
        query=dict(query),
        client_ip=client_ip,
    )


class TempestWebServer(Generic[S]):
    """Holds the app definition and the live SSE session registry.

    ``S`` is the application state type.

    Attributes:
        api: The FastAPI application instance with the routes mounted.
    """

    def __init__(
        self,
        state_factory: Callable[[], S],
        view: Callable[[App[S]], Widget],
        *,
        title: str = "tempestweb",
        security: SecurityConfig | None = None,
        metrics: bool = False,
        sse_backend: SessionRouter | None = None,
        concurrent_dispatch: bool = False,
    ) -> None:
        """Build the server and register the WebSocket and SSE routes.

        Args:
            state_factory: Builds a fresh state per connection (isolation).
            view: The shared ``view`` function rendered for each session.
            title: OpenAPI title for the FastAPI app.
            security: Opt-in auth + origin controls (Track S). ``None`` leaves
                the host open (dev).
            metrics: When ``True``, mount ``GET /metrics`` (Prometheus text) with
                connection counters (Track S — S8).
            sse_backend: Router for SSE inbound events (Track S — S4). ``None``
                uses the in-process router (needs sticky sessions across
                instances); a :class:`RedisSessionRouter` drops that requirement.
            concurrent_dispatch: Run each event's handler as its own task instead
                of awaiting it before the next event is read. Events for the same
                widget key keep their arrival order; handlers for different keys
                overlap, so one slow handler no longer freezes the connection.
                Off by default — see :class:`~tempestweb.runtime.AppSession`.
        """
        self._router: SessionRouter = sse_backend or InProcessRouter()
        self._state_factory: Callable[[], S] = state_factory
        self._view: Callable[[App[S]], Widget] = view
        self._sse_sessions: dict[str, _SSESession[S]] = {}
        self._concurrent_dispatch: bool = concurrent_dispatch
        self._security: SecurityConfig = security or SecurityConfig()
        self._live: int = 0  # concurrent live sessions (S2 cap)
        self._metrics_enabled: bool = metrics
        self._opened: int = 0  # total sessions ever accepted
        self._rejected: int = 0  # total connections refused (auth/origin/cap)
        rpm = self._security.max_connections_per_minute
        self._rate: RateLimiter | None = RateLimiter(rpm) if rpm else None
        epm = self._security.max_events_per_minute
        self._event_rate: RateLimiter | None = RateLimiter(epm) if epm else None
        self.api: FastAPI = FastAPI(title=title)
        self._install_cors()
        self._install_security_headers()
        self._register_routes()

    def _prometheus(self) -> str:
        """Render the connection counters as Prometheus text (S8)."""
        cap = self._security.max_connections
        lines = [
            "# HELP tempestweb_sessions_live Currently connected sessions.",
            "# TYPE tempestweb_sessions_live gauge",
            f"tempestweb_sessions_live {self._live}",
            "# HELP tempestweb_sessions_opened_total Sessions accepted since start.",
            "# TYPE tempestweb_sessions_opened_total counter",
            f"tempestweb_sessions_opened_total {self._opened}",
            "# HELP tempestweb_connections_rejected_total Connections refused.",
            "# TYPE tempestweb_connections_rejected_total counter",
            f"tempestweb_connections_rejected_total {self._rejected}",
        ]
        if cap is not None:
            lines += [
                "# HELP tempestweb_sessions_max Configured max concurrent sessions.",
                "# TYPE tempestweb_sessions_max gauge",
                f"tempestweb_sessions_max {cap}",
            ]
        return "\n".join(lines) + "\n"

    def _install_security_headers(self) -> None:
        """Add hardening response headers to every HTTP response (S6)."""
        if not self._security.wants_headers:
            return
        headers = self._security.header_values()

        @self.api.middleware("http")
        async def _headers(request: Request, call_next: Any) -> Response:  # noqa: ANN401
            response: Response = await call_next(request)
            for name, value in headers.items():
                response.headers.setdefault(name, value)
            return response

    def _at_capacity(self) -> bool:
        """Whether the concurrent-session cap is reached (S2)."""
        cap = self._security.max_connections
        return cap is not None and self._live >= cap

    def _rate_ok(self, credentials: Credentials) -> bool:
        """Whether the client IP is within the per-minute connection rate (S2)."""
        if self._rate is None:
            return True
        return self._rate.allow(credentials.client_ip or "unknown")

    def _event_rate_ok(self, credentials: Credentials) -> bool:
        """Whether the client IP is within the per-minute inbound-envelope rate (S2).

        Counts every envelope the client sends on either leg — an SSE ``POST`` or
        a WebSocket frame — against ``max_events_per_minute``. Distinct from
        :meth:`_rate_ok`, which budgets *connections*.

        Args:
            credentials: The credentials extracted from the request or upgrade.

        Returns:
            ``True`` when the envelope is within budget (or no limit is set).
        """
        if self._event_rate is None:
            return True
        return self._event_rate.allow(credentials.client_ip or "unknown")

    def _install_cors(self) -> None:
        """Install CORS for the HTTP/SSE surface when an allowlist is set (S1)."""
        origins = self._security.allowed_origins
        if origins is None:
            return
        from starlette.middleware.cors import CORSMiddleware

        self.api.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
            allow_credentials=not self._security.origins_wildcard,
        )

    def _new_session(self, transport: PatchTransport) -> AppSession[S]:
        """Create an isolated session bound to a transport.

        Args:
            transport: The per-connection transport (WS or SSE).

        Returns:
            A fresh :class:`AppSession` for this connection.
        """
        return AppSession(
            self._state_factory,
            self._view,
            transport,
            concurrent_dispatch=self._concurrent_dispatch,
        )

    def _register_routes(self) -> None:
        """Mount the ``/health``, ``/ws``, ``/sse`` and ``/sse/{id}`` routes."""

        @self.api.get("/health")
        async def health() -> dict[str, Any]:
            """Liveness/readiness probe (S4): unauthenticated, cheap, no session.

            Returns ``ok`` plus the live session count and, when a cap is set,
            whether the host still has capacity — for load-balancer draining.
            """
            cap = self._security.max_connections
            return {
                "status": "ok",
                "sessions": self._live,
                "ready": cap is None or self._live < cap,
            }

        if self._metrics_enabled:

            @self.api.get("/metrics")
            async def metrics() -> Response:
                """Prometheus-format connection counters (S8)."""
                return Response(
                    content=self._prometheus(),
                    media_type="text/plain; version=0.0.4",
                )

        @self.api.websocket("/ws")
        async def ws_endpoint(websocket: WebSocket) -> None:
            """Serve one client over a WebSocket until it disconnects.

            The auth gate + origin allowlist (Track S) run on the upgrade before
            a session is created; a rejected connection is closed with ``1008``
            (policy violation) and never mounts.
            """
            peer = websocket.client.host if websocket.client else None
            credentials = _credentials_from_headers(
                websocket.headers, websocket.query_params, peer
            )
            if not self._rate_ok(credentials):
                self._rejected += 1
                await websocket.close(code=1013)  # rate limited
                return
            if not await _authorize(self._security, credentials):
                self._rejected += 1
                await websocket.close(code=1008)
                return
            if self._at_capacity():
                self._rejected += 1
                await websocket.close(code=1013)  # try again later
                return
            await websocket.accept()
            self._live += 1
            self._opened += 1
            transport = WebSocketTransport(
                websocket,
                allow_inbound=lambda: self._event_rate_ok(credentials),
            )
            session = self._new_session(transport)
            try:
                await session.run()
            finally:
                self._live -= 1

        @self.api.get("/sse")
        async def sse_endpoint(request: Request, session: str) -> Response:
            """Open (or resume) the SSE patch stream for ``session``."""
            credentials = self._request_credentials(request)
            new_session = session not in self._sse_sessions
            if new_session and not self._rate_ok(credentials):
                self._rejected += 1
                return JSONResponse({"error": "rate limited"}, status_code=429)
            if not await _authorize(self._security, credentials):
                self._rejected += 1
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            if new_session and self._at_capacity():
                self._rejected += 1
                return JSONResponse({"error": "at capacity"}, status_code=503)
            return await self._open_sse(request, session)

        @self.api.post("/sse/{session_id}")
        async def sse_post(session_id: str, request: Request) -> Response:
            """Receive one client envelope (event / native_result) for a session."""
            if not await self._authorize_request(request):
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            if not self._event_rate_ok(self._request_credentials(request)):
                self._rejected += 1
                return JSONResponse({"error": "rate limited"}, status_code=429)
            if self._declared_too_large(request):
                return JSONResponse({"error": "payload too large"}, status_code=413)
            body = await self._read_body(request)
            if body is None:
                return JSONResponse({"error": "payload too large"}, status_code=413)
            return await self._handle_sse_post(session_id, body)

    def _declared_too_large(self, request: Request) -> bool:
        """Whether the *declared* body size already exceeds ``max_message_bytes``.

        A cheap pre-check on ``Content-Length`` that rejects an oversized body
        before a single byte is read. It is not sufficient on its own — the
        header is optional under chunked transfer encoding — so
        :meth:`_read_body` enforces the same limit while reading (S2).

        Args:
            request: The incoming request.

        Returns:
            ``True`` when the declared length is over the limit.
        """
        limit = self._security.max_message_bytes
        if limit is None:
            return False
        raw = request.headers.get("content-length")
        try:
            return raw is not None and int(raw) > limit
        except ValueError:
            return False

    async def _read_body(self, request: Request) -> bytes | None:
        """Read the request body, aborting past ``max_message_bytes`` (S2).

        The body is consumed chunk by chunk and the running total is checked
        against the limit, so a client that omits ``Content-Length`` (legal under
        chunked transfer encoding) cannot stream an unbounded body into memory —
        the read stops at the first chunk that crosses the limit.

        Args:
            request: The incoming request.

        Returns:
            The body bytes, or ``None`` when the limit was exceeded.
        """
        limit = self._security.max_message_bytes
        if limit is None:
            return await request.body()
        chunks: list[bytes] = []
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > limit:
                return None
            chunks.append(chunk)
        return b"".join(chunks)

    def _request_credentials(self, request: Request) -> Credentials:
        """Extract credentials (incl. client IP) from an HTTP request."""
        peer = request.client.host if request.client else None
        return _credentials_from_headers(request.headers, request.query_params, peer)

    async def _authorize_request(self, request: Request) -> bool:
        """Run the Track-S auth gate for an HTTP (SSE) request."""
        return await _authorize(self._security, self._request_credentials(request))

    async def _open_sse(self, request: Request, session_id: str) -> Response:
        """Open or resume an SSE session and return the streaming response.

        Args:
            request: The incoming request (for ``Last-Event-ID``).
            session_id: The client-chosen stable session id.

        Returns:
            A ``text/event-stream`` streaming response.
        """
        sse = self._sse_sessions.get(session_id)
        if sse is None:
            transport = SSETransport()
            app_session = self._new_session(transport)
            sse = _SSESession(transport=transport, session=app_session)
            self._sse_sessions[session_id] = sse
            self._live += 1
            self._opened += 1
            # Route cross-instance inbound events (S4): no-op in-process, Redis
            # pub/sub when configured — so a POST on another instance is delivered.
            sse.teardown = await self._router.bind(session_id, transport)
            sse.task = asyncio.ensure_future(self._run_sse(session_id, app_session))

        last_event_id = _parse_last_event_id(request.headers.get("last-event-id"))

        async def body() -> AsyncIterator[str]:
            """Stream SSE frames, cleaning up the session when the client leaves."""
            try:
                async for chunk in sse.transport.stream(last_event_id):
                    yield chunk
            finally:
                await self._drop_sse(session_id)

        return StreamingResponse(
            body(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    async def _run_sse(self, session_id: str, session: AppSession[S]) -> None:
        """Drive an SSE-backed session's lifecycle.

        Args:
            session_id: The session id (for cleanup on exit).
            session: The session to mount and run.
        """
        try:
            await session.run()
        finally:
            await self._drop_sse(session_id)

    async def _handle_sse_post(self, session_id: str, body: bytes) -> Response:
        """Route one POSTed client envelope into its SSE session.

        The router feeds a local transport directly, or hands the envelope off to
        the instance holding the stream (Redis); an unroutable session is a
        ``404``.

        Args:
            session_id: The session id from the URL path.
            body: The raw request body, already size-checked, holding the wire
                envelope as JSON.

        Returns:
            ``204 No Content`` on success, ``400`` on malformed JSON, ``404`` if
            the session is unknown.
        """
        try:
            envelope: dict[str, Any] = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            return JSONResponse({"error": "invalid JSON"}, status_code=400)
        sse = self._sse_sessions.get(session_id)
        local = sse.transport if sse is not None else None
        if not await self._router.deliver(session_id, envelope, local):
            return JSONResponse({"error": "unknown session"}, status_code=404)
        return Response(status_code=204)

    async def _drop_sse(self, session_id: str) -> None:
        """Close and forget an SSE session.

        Args:
            session_id: The session id to tear down.
        """
        sse = self._sse_sessions.pop(session_id, None)
        if sse is not None:
            self._live -= 1
            if sse.teardown is not None:
                await sse.teardown()
            await sse.transport.close()
            await sse.session.close()


class _SSESession(Generic[S]):
    """Bookkeeping for one live SSE session (transport + session + task)."""

    def __init__(self, transport: SSETransport, session: AppSession[S]) -> None:
        """Bind the transport, session, and (later) the driving task.

        Args:
            transport: The SSE transport for this session.
            session: The app session driven over the transport.
        """
        self.transport: SSETransport = transport
        self.session: AppSession[S] = session
        self.task: asyncio.Task[None] | None = None
        self.teardown: Teardown | None = None


def _parse_last_event_id(raw: str | None) -> int | None:
    """Parse a ``Last-Event-ID`` header value into a tick id.

    Args:
        raw: The raw header value, or ``None``.

    Returns:
        The integer tick id, or ``None`` if absent or malformed.
    """
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def create_app(
    state_factory: Callable[[], S],
    view: Callable[[App[S]], Widget],
    *,
    title: str = "tempestweb",
    security: SecurityConfig | None = None,
    metrics: bool = False,
    sse_backend: SessionRouter | None = None,
    concurrent_dispatch: bool = False,
) -> FastAPI:
    """Build a Mode B FastAPI app for a ``view`` and state factory.

    Args:
        state_factory: Builds a fresh state per connection (isolation).
        view: The shared ``view`` function rendered for each session.
        title: OpenAPI title for the FastAPI app.
        security: Opt-in auth + origin controls (Track S — S0/S1/S3). ``None``
            leaves the host open (dev); pass a :class:`SecurityConfig` with an
            ``authenticate`` predicate and/or ``allowed_origins`` for production.
        metrics: When ``True``, mount ``GET /metrics`` (Prometheus text) — S8.
        sse_backend: SSE inbound router (Track S — S4). ``None`` is in-process
            (sticky sessions); a ``RedisSessionRouter`` scales SSE without sticky.
        concurrent_dispatch: Dispatch each event as its own task (ordered per
            widget key) instead of one at a time, so a slow handler cannot freeze
            the connection. Off by default; ``tempestweb.runtime.spawn`` handles
            the common case without changing dispatch semantics.

    Returns:
        The configured FastAPI application with WS and SSE routes mounted.
    """
    return TempestWebServer(
        state_factory,
        view,
        title=title,
        security=security,
        metrics=metrics,
        sse_backend=sse_backend,
        concurrent_dispatch=concurrent_dispatch,
    ).api
