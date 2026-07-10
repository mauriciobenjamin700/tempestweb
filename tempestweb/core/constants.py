"""Framework-wide constants for tempestweb.

The single home for cross-cutting values that more than one module (or the public
API and the tests) depend on: the execution modes, and the wasm-build, SSE and
dev-loop defaults. Domain-local, private implementation constants (e.g. a module's
asset list or handler prefix) stay next to their use — only shared/public values
live here, re-exported by their original modules for a stable import surface.
"""

from __future__ import annotations

#: The execution modes a project can build/run as. ``transpile`` (experimental)
#: transcribes the Python app layer to native JS — a static bundle with no
#: Python runtime (see :mod:`tempestweb.transpile`).
VALID_MODES: tuple[str, ...] = ("wasm", "server", "transpile")

#: The mode a freshly scaffolded project defaults to.
DEFAULT_MODE: str = "wasm"

#: Pyodide release the wasm bootstrap loads from the CDN (CPython 3.14.2; ships a
#: prebuilt emscripten pydantic_core wheel). See docs/agents/reports/NOTES-T3.md.
WASM_PYODIDE_VERSION: str = "v314.0.0"

#: Filename of the zipped tempestweb/tempest_core payload unpacked into the Pyodide
#: virtual filesystem by the wasm bootstrap.
WASM_PACKAGE_ARCHIVE: str = "tempestweb-pkg.zip"

#: Heartbeat interval (seconds) between ``ping`` events on the SSE stream.
DEFAULT_SSE_PING_INTERVAL: float = 15.0

#: How many recent envelopes to retain for SSE ``Last-Event-ID`` replay.
DEFAULT_SSE_REPLAY_BUFFER: int = 256

#: File suffixes whose changes trigger a dev-loop reload (editors write swap/temp
#: files constantly; restricting suffixes keeps the loop quiet).
DEFAULT_WATCH_SUFFIXES: tuple[str, ...] = (".py", ".html", ".css", ".js")

__all__ = [
    "DEFAULT_MODE",
    "DEFAULT_SSE_PING_INTERVAL",
    "DEFAULT_SSE_REPLAY_BUFFER",
    "DEFAULT_WATCH_SUFFIXES",
    "VALID_MODES",
    "WASM_PACKAGE_ARCHIVE",
    "WASM_PYODIDE_VERSION",
]
