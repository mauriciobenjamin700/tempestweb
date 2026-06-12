"""Dev HTTP server: serve a built artifact with browser livereload (Mode A).

``tempestweb dev`` builds the wasm artifact once, serves it over this app, and
watches the project. On a file change the dev loop rebuilds the artifact and
triggers the shared :class:`~tempestweb.devserver.reload.ReloadSignal`; this
app's ``/__livereload`` SSE endpoint pushes a ``reload`` event, and the injected
``/__livereload.js`` snippet reloads the browser tab so the fresh bundle takes
effect.

The same app (without a signal) also backs ``tempestweb run --mode wasm`` — a
plain static host for the bundle, no livereload. Mode B keeps serving the built
``server.py`` directly (it is already a live FastAPI host).

This module depends on Starlette (the ``server`` extra), so it is imported lazily
by the CLI — a Mode A *build* never needs it, only *serving* does.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import (
    HTMLResponse,
    PlainTextResponse,
    Response,
    StreamingResponse,
)
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from tempestweb.devserver.reload import ReloadSignal

if TYPE_CHECKING:
    import uvicorn

__all__ = [
    "create_dev_app",
    "inject_livereload",
    "livereload_frames",
    "make_server",
    "serve",
]

#: The script tag injected before ``</body>`` so the served page auto-reloads.
_LIVERELOAD_TAG = '<script type="module" src="/__livereload.js"></script>'


async def livereload_frames(signal: ReloadSignal) -> AsyncIterator[str]:
    """Yield SSE frames for the livereload stream: open comment, then reloads.

    Emits an initial ``": connected"`` comment frame so the client knows the
    stream is open, then one ``reload`` event per :meth:`ReloadSignal.trigger`,
    carrying the reload generation as the SSE ``data``. Runs until the consumer
    (the HTTP response) is closed.

    Args:
        signal: The reload hub to await reloads from.

    Yields:
        SSE wire text blocks (``": connected"`` first, then ``event: reload`` +
        ``data: <generation>`` blocks).
    """
    yield ": connected\n\n"
    while True:
        event = await signal.wait()
        yield f"event: reload\ndata: {event.generation}\n\n"


def _livereload_js() -> str:
    """Return the bundled livereload client snippet.

    Resolves ``client/livereload.js`` through the same locator the build uses
    (packaged ``tempestweb/_client`` first, repo ``client/`` in a checkout).

    Returns:
        The JavaScript source of the livereload client.
    """
    from tempestweb.cli.commands.build import _client_dir

    return (_client_dir() / "livereload.js").read_text(encoding="utf-8")


def inject_livereload(html: str) -> str:
    """Inject the livereload script tag into an HTML document.

    Inserts the tag immediately before the closing ``</body>`` so the snippet
    loads after the app's own scripts. Falls back to appending when no ``</body>``
    is present (a malformed or fragment document).

    Args:
        html: The original HTML source.

    Returns:
        The HTML with the livereload script tag injected.
    """
    if "</body>" in html:
        return html.replace("</body>", f"  {_LIVERELOAD_TAG}\n  </body>", 1)
    return html + f"\n{_LIVERELOAD_TAG}\n"


def create_dev_app(
    out_dir: str | Path, signal: ReloadSignal | None = None
) -> Starlette:
    """Build a Starlette app that serves ``out_dir`` with optional livereload.

    When ``signal`` is provided the app exposes ``/__livereload`` (an SSE stream
    that emits a ``reload`` event on every signal trigger) and ``/__livereload.js``
    (the browser snippet), and injects the snippet's ``<script>`` tag into the
    served ``index.html``. Without a signal it is a plain static host for the
    bundle (used by ``run --mode wasm``).

    Args:
        out_dir: The built artifact directory to serve at ``/``.
        signal: The reload hub to bridge to the browser. ``None`` disables
            livereload (static-only serving).

    Returns:
        A configured :class:`~starlette.applications.Starlette` app.
    """
    root = Path(out_dir)
    live = signal is not None

    async def index(request: Request) -> Response:
        """Serve the artifact's ``index.html``, injecting livereload in dev."""
        html = (root / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(inject_livereload(html) if live else html)

    async def livereload_js(request: Request) -> Response:
        """Serve the livereload client snippet (dev only)."""
        return PlainTextResponse(_livereload_js(), media_type="application/javascript")

    async def livereload_stream(request: Request) -> Response:
        """Stream a ``reload`` SSE event on every reload signal (dev only)."""
        assert signal is not None  # guarded by `live` route registration
        return StreamingResponse(
            livereload_frames(signal),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    routes: list[Route | Mount] = [Route("/", index, methods=["GET"])]
    if live:
        routes.append(Route("/index.html", index, methods=["GET"]))
        routes.append(Route("/__livereload", livereload_stream, methods=["GET"]))
        routes.append(Route("/__livereload.js", livereload_js, methods=["GET"]))
    # Everything else (bundle assets, icons, sw.js, the zip) is served statically.
    routes.append(Mount("/", app=StaticFiles(directory=str(root)), name="static"))
    return Starlette(routes=routes)


def make_server(app: Starlette, host: str, port: int) -> uvicorn.Server:
    """Build a non-started uvicorn server for ``app`` bound to ``host:port``.

    Splitting construction from running lets the dev loop drive ``server.serve()``
    concurrently with the file watcher under one event loop, and lets tests assert
    the bind config without opening a socket.

    Args:
        app: The Starlette app to serve.
        host: The bind address.
        port: The bind port.

    Returns:
        A configured (but not started) :class:`uvicorn.Server`.
    """
    import uvicorn

    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    return uvicorn.Server(config)


def serve(app: Starlette, host: str, port: int) -> None:
    """Serve ``app`` under uvicorn until stopped (blocking).

    Args:
        app: The Starlette app to serve.
        host: The bind address.
        port: The bind port.
    """
    make_server(app, host, port).run()
