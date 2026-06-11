"""Wire serialization and handler resolution for Mode B.

The reconciler (in :mod:`tempestweb._core`) produces :class:`~tempestweb._core.Node`
trees and :class:`~tempestweb._core.Patch` operations whose ``props`` may carry
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

from tempestweb._core import Insert, Node, Patch, Replace, Scene, Update

__all__ = [
    "EVENT_TYPE_TO_HANDLER_PROPS",
    "node_to_wire",
    "patch_to_wire",
    "patches_to_wire",
    "scene_to_initial_patches",
    "resolve_handler",
]

#: Maps a wire event ``type`` (``docs/contract.md``) to the candidate handler prop
#: names a node may declare for it, in priority order. The client sends short DOM
#: event names; widgets declare ``on_<verb>`` props (see each widget's
#: ``event_schemas`` in :mod:`tempestweb._core`). The first prop present on the
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

    For :class:`~tempestweb._core.Insert` / :class:`~tempestweb._core.Replace`
    the embedded ``node`` is re-serialized through :func:`node_to_wire`; for
    :class:`~tempestweb._core.Update` the ``set_props`` are stripped of handlers.
    ``path`` tuples become lists (per the contract).

    Args:
        patch: An IR patch produced by ``diff`` / ``diff_scene``.

    Returns:
        A JSON-able patch dict matching ``docs/contract.md``.
    """
    dumped: dict[str, Any] = patch.model_dump(mode="json")
    dumped["path"] = list(dumped.get("path", []))
    if isinstance(patch, (Insert, Replace)):
        dumped["node"] = node_to_wire(patch.node)
    elif isinstance(patch, Update):
        dumped["set_props"] = {
            name: _json_safe(value) for name, value in patch.set_props.items()
        }
    return dumped


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
    initial mount as a single :class:`~tempestweb._core.Replace` at the root
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
