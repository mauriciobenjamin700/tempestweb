"""tempestweb.runtime — per-connection session and wire serialization (Mode B).

Re-exports the runtime building blocks the server host and transports compose:

- :class:`~tempestweb.runtime.session.AppSession` — per-connection lifecycle.
- The serialization helpers that lower the IR to the wire format and resolve
  handlers from client events.

See ``docs/plan.md`` (Trilho B) and ``docs/contract.md``.
"""

from __future__ import annotations

from tempestweb.runtime.serialize import (
    EVENT_TYPE_TO_HANDLER_PROPS,
    node_to_wire,
    patch_to_wire,
    patches_to_wire,
    resolve_handler,
    scene_to_initial_patches,
)
from tempestweb.runtime.session import AppSession

__all__ = [
    "AppSession",
    "EVENT_TYPE_TO_HANDLER_PROPS",
    "node_to_wire",
    "patch_to_wire",
    "patches_to_wire",
    "resolve_handler",
    "scene_to_initial_patches",
]
