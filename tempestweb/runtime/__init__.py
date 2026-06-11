"""tempestweb.runtime — execution-mode glue, session and wire serialization.

Mode A (WASM/Pyodide): :class:`WasmRuntime` drives the core's rebuild loop over a
:class:`~tempestweb.transports.base.PatchTransport`. Mode B (server):
:class:`~tempestweb.runtime.session.AppSession` is the per-connection lifecycle,
with serialization helpers that lower the IR to the wire format and resolve
handlers from client events.

See ``docs/plan.md`` (Trilhos A e B) and ``docs/contract.md``.
"""

from __future__ import annotations

from tempestweb.runtime.events import apply_scroll, coerce_event
from tempestweb.runtime.serialize import (
    EVENT_TYPE_TO_HANDLER_PROPS,
    find_node_type,
    node_to_wire,
    patch_to_wire,
    patches_to_wire,
    resolve_handler,
    scene_to_initial_patches,
)
from tempestweb.runtime.session import AppSession, NativeCallError
from tempestweb.runtime.wasm import WasmRuntime, serialize_node, serialize_patches
from tempestweb.runtime.wasm_main import WasmAppHandle, bootstrap

__all__ = [
    "AppSession",
    "EVENT_TYPE_TO_HANDLER_PROPS",
    "NativeCallError",
    "WasmAppHandle",
    "WasmRuntime",
    "apply_scroll",
    "bootstrap",
    "coerce_event",
    "find_node_type",
    "node_to_wire",
    "patch_to_wire",
    "patches_to_wire",
    "resolve_handler",
    "scene_to_initial_patches",
    "serialize_node",
    "serialize_patches",
]
