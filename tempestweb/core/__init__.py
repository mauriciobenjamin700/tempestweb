"""tempestweb.core — cross-cutting constants shared across the framework.

The renderer-agnostic engine lives in the external ``tempest_core`` package; this
``core`` package holds tempestweb's own framework-wide values (execution modes,
build/transport/dev defaults) in one place, re-exported by the modules that use
them so there is a single source of truth.
"""

from __future__ import annotations

from tempestweb.core.constants import (
    DEFAULT_MODE,
    DEFAULT_SSE_PING_INTERVAL,
    DEFAULT_SSE_REPLAY_BUFFER,
    DEFAULT_WATCH_SUFFIXES,
    VALID_MODES,
    WASM_PACKAGE_ARCHIVE,
    WASM_PYODIDE_VERSION,
)

__all__ = [
    "DEFAULT_MODE",
    "DEFAULT_SSE_PING_INTERVAL",
    "DEFAULT_SSE_REPLAY_BUFFER",
    "DEFAULT_WATCH_SUFFIXES",
    "VALID_MODES",
    "WASM_PACKAGE_ARCHIVE",
    "WASM_PYODIDE_VERSION",
]
