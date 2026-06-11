"""Wire serialization and handler resolution for Mode B.

The reconciler (in :mod:`tempest_core`) produces :class:`~tempest_core.Node`
trees and :class:`~tempest_core.Patch` operations whose ``props`` may carry
**live handler objects** (the Python callables wired by the app's ``view``). Those
callables are not JSON-serializable and must never cross the wire — the client only
needs to know a widget *has* a handler by its stable ``key``, then routes the event
back so the Python side invokes the real callable.

This module is the seam-agnostic bridge between the in-process IR and the
JSON-able wire format documented in ``docs/contract.md``:

- :func:`patches_to_wire` lowers a list of patches to JSON-able dicts, replacing
  every non-JSON-able prop value (handlers) with ``None``.
- :func:`scene_to_initial_patches` turns a freshly built scene into the initial
  patch batch a client applies to mount the screen from an empty root.
- :func:`resolve_handler` walks the *live* current scene to find the callable a
  client event targets, by widget ``key`` and event ``type``.

Both the WebSocket transport (B1) and the SSE transport (B5) reuse these helpers,
so the two transports carry an identical patch stream.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from tempest_core import Insert, Node, Patch, Remove, Replace, Scene, Update

__all__ = [
    "EVENT_TYPE_TO_HANDLER_PROPS",
    "node_to_wire",
    "patch_to_wire",
    "patches_to_wire",
    "scene_to_initial_patches",
    "resolve_handler",
    "find_node_type",
]

#: Maps a wire event ``type`` (``docs/contract.md``) to the candidate handler prop
#: names a node may declare for it, in priority order. The client sends short DOM
#: event names; widgets declare ``on_<verb>`` props (see each widget's
#: ``event_schemas`` in :mod:`tempest_core`). The first prop present on the
#: target node (and non-``None``) wins.
EVENT_TYPE_TO_HANDLER_PROPS: dict[str, tuple[str, ...]] = {
    "click": ("on_click",),
    "input": ("on_change",),
    "change": ("on_change",),
    "submit": ("on_submit",),
    "select": ("on_select",),
    "toggle": ("on_change",),
    "dismiss": ("on_dismiss",),
    "validate": ("on_validate",),
    "scan": ("on_scan",),
}


def _json_safe(value: Any) -> Any:  # noqa: ANN401 — walks arbitrary IR prop values
    """Recursively replace non-JSON-able values (handlers) with ``None``.

    The IR carries live handler callables in ``props``; this strips them to
    ``None`` so the result is JSON-serializable while preserving every other
    prop (style dicts, strings, numbers, nested structures) untouched.

    Args:
        value: Any prop value drawn from a node's ``props``.

    Returns:
        A JSON-able value: callables become ``None``; dicts and lists are walked
        recursively; everything else is returned unchanged.
    """
    if callable(value):
        return None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def node_to_wire(node: Node) -> dict[str, Any]:
    """Lower an IR node to its JSON-able wire shape.

    The node is dumped with Pydantic (``mode="json"`` for styles, enums, colors),
    then its ``props`` are walked to replace any live handler callable with
    ``None`` — handlers never cross the boundary (see ``docs/contract.md``).

    Args:
        node: The IR node to serialize.

    Returns:
        A JSON-able ``{"type", "key", "props", "children"}`` dict.
    """
    return {
        "type": node.type,
        "key": node.key,
        "props": {name: _json_safe(value) for name, value in node.props.items()},
        "children": [node_to_wire(child) for child in node.children],
    }


def patch_to_wire(patch: Patch) -> dict[str, Any]:
    """Lower a single patch to its JSON-able wire shape.

    Each patch kind is built explicitly rather than via a blanket
    ``model_dump`` — the IR carries **live handler callables** inside
    ``Update.set_props`` and inside the ``node`` of
    :class:`~tempest_core.Insert` / :class:`~tempest_core.Replace`, which
    Pydantic cannot serialize. :func:`node_to_wire` and :func:`_json_safe` strip
    those handlers to ``None`` (see ``docs/contract.md``). ``path`` tuples become
    lists.

    Args:
        patch: An IR patch produced by ``diff`` / ``diff_scene``.

    Returns:
        A JSON-able patch dict matching ``docs/contract.md``.
    """
    path: list[Any] = list(patch.path)
    if isinstance(patch, Update):
        return {
            "path": path,
            "set_props": {
                name: _json_safe(value) for name, value in patch.set_props.items()
            },
            "unset_props": list(patch.unset_props),
        }
    if isinstance(patch, Insert):
        return {"path": path, "index": patch.index, "node": node_to_wire(patch.node)}
    if isinstance(patch, Replace):
        return {"path": path, "node": node_to_wire(patch.node)}
    if isinstance(patch, Remove):
        return {"path": path, "index": patch.index}
    # Reorder is the only remaining kind.
    return {"path": path, "order": list(patch.order)}


def patches_to_wire(patches: list[Patch]) -> list[dict[str, Any]]:
    """Lower a coalesced patch batch to JSON-able wire dicts.

    Args:
        patches: The tick's patches, in apply order. May be empty.

    Returns:
        The JSON-able patch dicts, in the same order (empty list when empty).
    """
    return [patch_to_wire(patch) for patch in patches]


def scene_to_initial_patches(scene: Scene) -> list[dict[str, Any]]:
    """Build the initial patch batch that mounts a scene from an empty root.

    The client mounts by applying patches to an empty document. We model the
    initial mount as a single :class:`~tempest_core.Replace` at the root
    (``path == []``) carrying the whole built tree, which the DOM renderer (W1)
    applies to materialize the screen. Overlays, when present, follow as inserts
    under the reserved ``"overlay"`` path.

    Args:
        scene: The freshly built scene (``App.start()`` result).

    Returns:
        The JSON-able initial patch batch.
    """
    patches: list[dict[str, Any]] = [{"path": [], "node": node_to_wire(scene.root)}]
    for index, overlay in enumerate(scene.overlays):
        patches.append(
            {"path": ["overlay"], "index": index, "node": node_to_wire(overlay)}
        )
    return patches


def _find_node_by_key(node: Node, key: str) -> Node | None:
    """Depth-first search for the node carrying ``key``.

    Args:
        node: The root node to search from.
        key: The widget key to match.

    Returns:
        The first node whose ``key`` equals ``key``, or ``None`` if none match.
    """
    if node.key == key:
        return node
    for child in node.children:
        found = _find_node_by_key(child, key)
        if found is not None:
            return found
    return None


def find_node_type(scene: Scene, key: str) -> str | None:
    """Return the widget type tag of the keyed node in a scene.

    Searches the root tree then the overlay layer, mirroring
    :func:`resolve_handler`, so an event's payload can be coerced into the typed
    event the matched widget declares.

    Args:
        scene: The session's current scene.
        key: The widget key the event addresses.

    Returns:
        The node's ``type`` tag, or ``None`` when no node matches the key.
    """
    target = _find_node_by_key(scene.root, key)
    if target is None:
        for overlay in scene.overlays:
            target = _find_node_by_key(overlay, key)
            if target is not None:
                break
    return target.type if target is not None else None


def resolve_handler(
    scene: Scene, key: str, event_type: str
) -> Callable[..., Any] | None:
    """Resolve the live handler callable a client event targets.

    Walks the *current* scene (root then overlays) for the node with ``key``,
    then looks up the handler prop for ``event_type`` using
    :data:`EVENT_TYPE_TO_HANDLER_PROPS`, falling back to a literal ``on_<type>``
    prop name. Handlers live in the node's ``props`` as real Python callables
    (they are only stripped to ``None`` when serialized for the wire).

    Args:
        scene: The session's current scene (``App.current_tree``).
        key: The ``key`` of the widget that emitted the event.
        event_type: The wire event type (``"click"``, ``"change"``, ...).

    Returns:
        The handler callable to invoke, or ``None`` when no node matches the key
        or the matched node declares no handler for that event type.
    """
    target = _find_node_by_key(scene.root, key)
    if target is None:
        for overlay in scene.overlays:
            target = _find_node_by_key(overlay, key)
            if target is not None:
                break
    if target is None:
        return None
    candidates = EVENT_TYPE_TO_HANDLER_PROPS.get(event_type, (f"on_{event_type}",))
    for prop_name in candidates:
        handler = target.props.get(prop_name)
        if callable(handler):
            return cast("Callable[..., Any]", handler)
    return None
