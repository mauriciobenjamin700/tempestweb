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
from collections.abc import AsyncIterator, Callable
from typing import Any, Generic, TypeVar

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.websockets import WebSocket
from tempest_core import App, Widget

from tempestweb.runtime.session import AppSession
from tempestweb.transports.base import PatchTransport
from tempestweb.transports.sse import SSETransport
from tempestweb.transports.websocket import WebSocketTransport

__all__ = ["TempestWebServer", "create_app"]

S = TypeVar("S")


class TempestWebServer(Generic[S]):
    """Holds the app definition and the live SSE session registry.

    Type Args:
        S: The application state type.

    Attributes:
        api: The FastAPI application instance with the routes mounted.
    """

    def __init__(
        self,
        state_factory: Callable[[], S],
        view: Callable[[App[S]], Widget],
        *,
        title: str = "tempestweb",
    ) -> None:
        """Build the server and register the WebSocket and SSE routes.

        Args:
            state_factory: Builds a fresh state per connection (isolation).
            view: The shared ``view`` function rendered for each session.
            title: OpenAPI title for the FastAPI app.
        """
        self._state_factory: Callable[[], S] = state_factory
        self._view: Callable[[App[S]], Widget] = view
        self._sse_sessions: dict[str, _SSESession[S]] = {}
        self.api: FastAPI = FastAPI(title=title)
        self._register_routes()

    def _new_session(self, transport: PatchTransport) -> AppSession[S]:
        """Create an isolated session bound to a transport.

        Args:
            transport: The per-connection transport (WS or SSE).

        Returns:
            A fresh :class:`AppSession` for this connection.
        """
        return AppSession(self._state_factory, self._view, transport)

    def _register_routes(self) -> None:
        """Mount the ``/ws``, ``/sse`` and ``/sse/{id}`` routes on ``self.api``."""

        @self.api.websocket("/ws")
        async def ws_endpoint(websocket: WebSocket) -> None:
            """Serve one client over a WebSocket until it disconnects."""
            await websocket.accept()
            transport = WebSocketTransport(websocket)
            session = self._new_session(transport)
            await session.run()

        @self.api.get("/sse")
        async def sse_endpoint(request: Request, session: str) -> Response:
            """Open (or resume) the SSE patch stream for ``session``."""
            return await self._open_sse(request, session)

        @self.api.post("/sse/{session_id}")
        async def sse_post(session_id: str, request: Request) -> Response:
            """Receive one client envelope (event / native_result) for a session."""
            return await self._handle_sse_post(session_id, request)

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
            self._sse_sessions.pop(session_id, None)

    async def _handle_sse_post(self, session_id: str, request: Request) -> Response:
        """Route one POSTed client envelope into its SSE session.

        Args:
            session_id: The session id from the URL path.
            request: The request whose JSON body is the wire envelope.

        Returns:
            ``204 No Content`` on success, ``404`` if the session is unknown.
        """
        sse = self._sse_sessions.get(session_id)
        if sse is None:
            return JSONResponse({"error": "unknown session"}, status_code=404)
        envelope: dict[str, Any] = await request.json()
        sse.transport.feed_inbound(envelope)
        return Response(status_code=204)

    async def _drop_sse(self, session_id: str) -> None:
        """Close and forget an SSE session.

        Args:
            session_id: The session id to tear down.
        """
        sse = self._sse_sessions.pop(session_id, None)
        if sse is not None:
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
) -> FastAPI:
    """Build a Mode B FastAPI app for a ``view`` and state factory.

    Args:
        state_factory: Builds a fresh state per connection (isolation).
        view: The shared ``view`` function rendered for each session.
        title: OpenAPI title for the FastAPI app.

    Returns:
        The configured FastAPI application with WS and SSE routes mounted.
    """
    return TempestWebServer(state_factory, view, title=title).api
