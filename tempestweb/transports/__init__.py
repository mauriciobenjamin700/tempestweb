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
from tempestweb.transports.sse import SSETransport
from tempestweb.transports.wasm import WasmTransport
from tempestweb.transports.websocket import WebSocketTransport

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
