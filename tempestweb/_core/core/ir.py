"""Intermediate representation: normalized nodes and patch operations.

The reconciler does not diff widget objects directly. It first **builds** each
widget tree into a uniform :class:`Node` — type tag, flat ``props`` map, and an
ordered child list — then **diffs** two node trees into a list of **patches**.
Both halves live here so the reconciler and every leaf renderer share one
vocabulary, fully decoupled from concrete widget classes.

A node is addressed by a **path**: a tuple of steps from the root. A step is a
child index, except the reserved leading token ``"overlay"`` which addresses the
:class:`Scene` overlay layer. ``()`` is the root, ``(0, 2)`` is the third child
of the first child, and ``("overlay", 0, 1)`` is the second child of the first
overlay.
"""

from __future__ import annotations

from typing import Any, TypeAlias

from pydantic import BaseModel, ConfigDict

__all__ = [
    "Path",
    "Node",
    "Scene",
    "Replace",
    "Update",
    "Insert",
    "Remove",
    "Reorder",
    "Patch",
]

#: A node address: steps from the root (``()`` is the root). A step is a child
#: index (``int``), except the reserved leading ``"overlay"`` token (``str``)
#: that addresses the :class:`Scene` overlay layer (``("overlay", i, ...)``
#: targets overlay ``i``). All non-overlay paths are ``tuple[int, ...]``, a
#: subset of this alias, so existing diffs/renderers stay backward-compatible.
Path: TypeAlias = tuple[int | str, ...]


class _IRModel(BaseModel):
    """Base for IR models: shared Pydantic config.

    Props and nodes may carry arbitrary handler objects, so every IR model
    allows arbitrary types.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)


class Node(_IRModel):
    """A normalized, renderer-agnostic UI node.

    Attributes:
        type: The widget type tag (e.g. ``"Text"``, ``"Column"``).
        key: Optional stable identity used to match nodes across rebuilds.
        props: Renderable properties (style, text, label, handlers, ...),
            excluding children. Values are compared by equality during diffing.
        children: Ordered child nodes.
    """

    type: str
    key: str | None = None
    props: dict[str, Any] = {}
    children: list[Node] = []


class Scene(_IRModel):
    """A full UI document: the root tree plus a z-ordered overlay layer.

    A scene is the unit the runtime builds and diffs once overlays exist. The
    ``root`` is the ordinary screen tree; ``overlays`` is the floating layer
    (dialogs, sheets, toasts, menus) rendered above it in ascending z-order.
    Each overlay node carries its stable overlay id as its ``key`` so the keyed
    diff can match overlays across rebuilds. An empty ``overlays`` list reduces a
    scene to its root tree, so the no-overlay path is unchanged.

    Attributes:
        root: The root screen node.
        overlays: The floating overlay nodes, in ascending z-order. Each node's
            ``key`` is its stable overlay id.
    """

    root: Node
    overlays: list[Node] = []


class Replace(_IRModel):
    """Replace the whole subtree at ``path`` with ``node``.

    Emitted when the node type or key changes — the old subtree cannot be
    updated in place, so the renderer rebuilds it from scratch.

    Attributes:
        path: Address of the node to replace.
        node: The new subtree.
    """

    path: Path
    node: Node


class Update(_IRModel):
    """Update the props of the node at ``path`` in place.

    Attributes:
        path: Address of the node to update.
        set_props: Props to add or overwrite.
        unset_props: Prop names to remove (reset to the renderer default).
    """

    path: Path
    set_props: dict[str, Any] = {}
    unset_props: list[str] = []


class Insert(_IRModel):
    """Insert ``node`` as a new child at ``index`` under ``path``.

    Attributes:
        path: Address of the parent node.
        index: Position among the parent's children for the new node.
        node: The subtree to insert.
    """

    path: Path
    index: int
    node: Node


class Remove(_IRModel):
    """Remove the child at ``index`` under ``path``.

    Attributes:
        path: Address of the parent node.
        index: Position of the child to remove.
    """

    path: Path
    index: int


class Reorder(_IRModel):
    """Reorder the children under ``path`` according to ``order``.

    Attributes:
        path: Address of the parent node.
        order: A permutation where ``order[i]`` is the *old* index of the child
            that must end up at *new* index ``i``. The renderer rebuilds the
            child list as ``[old_children[order[i]] for i in ...]``.
    """

    path: Path
    order: list[int]


#: Any single reconciliation operation.
Patch: TypeAlias = Replace | Update | Insert | Remove | Reorder
