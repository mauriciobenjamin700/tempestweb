"""Mode B server entry-point — the counter example running on the server.

This module demonstrates how the *exact same* ``view`` function that runs inside
the browser (Mode A / Pyodide) can be served from a FastAPI host over WebSocket
and SSE without any change to the application code.

Usage::

    # Start the server (development):
    python examples/server-mode/serve.py

    # Then open the thin JS client in your browser at http://127.0.0.1:8000.
    # WebSocket endpoint: ws://127.0.0.1:8000/ws
    # SSE endpoints:      GET  http://127.0.0.1:8000/sse?session=<id>
    #                     POST http://127.0.0.1:8000/sse/<id>

The ``app`` symbol is importable by uvicorn / ASGI runners::

    uvicorn examples.server_mode.serve:app
"""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from examples.counter.app import make_state, view
from tempestweb.server import create_app

# ---------------------------------------------------------------------------
# Module-level ASGI app — importable by any ASGI runner.
# ---------------------------------------------------------------------------

app: FastAPI = create_app(
    make_state,
    view,
    title="tempestweb — Mode B counter demo",
)


def run() -> None:
    """Launch the Mode B demo server programmatically.

    Binds to ``127.0.0.1:8000`` (internal-only; change to ``0.0.0.0`` when a
    separate origin needs to reach this host).
    """
    uvicorn.run(
        "examples.server_mode.serve:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    run()
