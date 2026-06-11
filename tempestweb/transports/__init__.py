"""tempestweb.transports — the single seam separating Mode A and Mode B.

Re-exports the transport contract and both modes' implementations. The wire
format every transport carries is documented in ``docs/contract.md`` and pinned
by the golden fixtures under ``tests/fixtures/``.

- :class:`~tempestweb.transports.base.PatchTransport` — the Protocol both modes satisfy.
- :class:`~tempestweb.transports.wasm.WasmTransport` — Mode A (``pyodide.ffi``).
- :class:`~tempestweb.transports.websocket.WebSocketTransport` — Mode B over WS.
- :class:`~tempestweb.transports.sse.SSETransport` — Mode B over SSE + HTTP POST.
- Envelope encoders and the ``Envelope``/``Patch``/``Event`` type aliases.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tempestweb.transports.base import (
    Envelope,
    EnvelopeKind,
    Event,
    NativeCall,
    NativeResult,
    Patch,
    PatchTransport,
    TransportClosedError,
    encode_event,
    encode_native_call,
    encode_native_result,
    encode_patches,
)
from tempestweb.transports.wasm import WasmTransport

if TYPE_CHECKING:
    # Mode B transports depend on Starlette (the ``server`` extra). Import them
    # under TYPE_CHECKING for static tooling; at runtime they are loaded lazily by
    # ``__getattr__`` below so importing the WASM transport (Mode A, e.g. inside
    # Pyodide where Starlette is absent) never pulls the server stack.
    from tempestweb.transports.sse import SSETransport
    from tempestweb.transports.websocket import WebSocketTransport

# Symbols loaded lazily on first access, keyed to their defining submodule.
_LAZY: dict[str, str] = {
    "SSETransport": "tempestweb.transports.sse",
    "WebSocketTransport": "tempestweb.transports.websocket",
}


def __getattr__(name: str) -> Any:  # noqa: ANN401 - PEP 562 lazy re-export seam
    """Lazily import the Mode B (Starlette-backed) transports on first access.

    Args:
        name: The attribute being accessed on the package.

    Returns:
        The resolved transport class.

    Raises:
        AttributeError: If ``name`` is not a known lazy export.
    """
    module_path = _LAZY.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    attr = getattr(importlib.import_module(module_path), name)
    globals()[name] = attr  # cache so subsequent lookups skip __getattr__
    return attr


__all__ = [
    "Envelope",
    "EnvelopeKind",
    "Event",
    "NativeCall",
    "NativeResult",
    "Patch",
    "PatchTransport",
    "SSETransport",
    "TransportClosedError",
    "WasmTransport",
    "WebSocketTransport",
    "encode_event",
    "encode_native_call",
    "encode_native_result",
    "encode_patches",
]
