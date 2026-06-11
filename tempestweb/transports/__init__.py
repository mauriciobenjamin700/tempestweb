"""tempestweb.transports — the single seam separating Mode A and Mode B.

See ``docs/plan.md`` and ``docs/contract.md``. The :class:`PatchTransport`
Protocol is the fronteira; :class:`WasmTransport` is the Mode A (in-process,
``pyodide.ffi``) implementation.
"""

from tempestweb.transports.base import (
    Event,
    Patch,
    PatchTransport,
    TransportClosedError,
)
from tempestweb.transports.wasm import WasmTransport

__all__ = [
    "Event",
    "Patch",
    "PatchTransport",
    "TransportClosedError",
    "WasmTransport",
]
