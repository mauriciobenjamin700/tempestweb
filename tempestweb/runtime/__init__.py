"""tempestweb.runtime — execution-mode glue around the vendored core.

See ``docs/plan.md``. :class:`WasmRuntime` is the Mode A (WASM/Pyodide) glue that
drives the core's rebuild loop over a
:class:`~tempestweb.transports.base.PatchTransport`.
"""

from tempestweb.runtime.wasm import (
    WasmRuntime,
    serialize_node,
    serialize_patches,
)

__all__ = [
    "WasmRuntime",
    "serialize_node",
    "serialize_patches",
]
