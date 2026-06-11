"""The reconciler: ``build`` widgets into IR nodes, then ``diff`` into patches.

This is the backbone of correctness and the *same* code on desktop and device —
only the leaf renderer that applies the patches differs. It is pure: data in,
patches out, no side effects and no renderer knowledge.

Diffing strategy (v1):

* Same position, same ``(type, key)`` → recurse, emitting an :class:`Update`
  for changed props.
* Differing ``type`` or ``key`` at a position → :class:`Replace` the subtree.
* Child lists are diffed **positionally** by default (:class:`Insert` /
  :class:`Remove` at the tail).
* When both child lists are **fully keyed with unique keys**, a keyed diff runs:
  removed keys → :class:`Remove` (descending), the surviving keys are realigned
  to their new relative order with a single :class:`Reorder`, added keys →
  :class:`Insert` at their final indices (ascending), and matched keys recurse
  (:class:`Update` / :class:`Replace`). This handles mixed insert + remove +
  reorder in one pass — a pure permutation is just the no-add/no-remove case.
  Patches compose under sequential application: every index is valid against the
  live child list at the moment its patch applies.
"""

from __future__ import annotations

from typing import Any

from tempestweb._core.core.ir import (
    Insert,
    Node,
    Patch,
    Path,
    Remove,
    Reorder,
    Replace,
    Scene,
    Update,
)
from tempestweb._core.widgets import Component, Widget

__all__ = ["build", "diff", "build_scene", "diff_scene"]

#: The reserved leading path step that addresses the overlay layer of a
#: :class:`Scene`. A patch whose path starts with this token targets an overlay
#: rather than the root tree.
OVERLAY_STEP = "overlay"


def build(widget: Widget) -> Node:
    """Normalize a widget tree into an IR node tree.

    A :class:`Component` is expanded first — replaced by the primitive tree its
    :meth:`Component.render` returns — so the IR (and therefore both renderers)
    only ever contains primitive widgets. Children come from
    :meth:`Widget.child_nodes`; everything else on the widget (except ``key`` and
    the declared child slots) becomes a prop.

    Args:
        widget: The root widget to normalize.

    Returns:
        The root IR node.
    """
    if isinstance(widget, Component):
        return build(widget.render())
    children = [build(child) for child in widget.child_nodes()]
    skip = widget.child_field_names
    props: dict[str, Any] = {}
    for name in type(widget).model_fields:
        if name == "key" or name in skip:
            continue
        props[name] = getattr(widget, name)
    return Node(
        type=widget.widget_type,
        key=widget.key,
        props=props,
        children=children,
    )


def diff(old: Node, new: Node) -> list[Patch]:
    """Diff two IR node trees into an ordered list of patches.

    Patches are ordered so a renderer can apply them sequentially: a node's own
    update/reorder precedes its descendants' patches, and within a child list
    removals run tail-first before insertions.

    Args:
        old: The previously rendered tree.
        new: The freshly built tree.

    Returns:
        The patches that transform ``old`` into ``new`` (empty if identical).
    """
    patches: list[Patch] = []
    _reconcile(old, new, (), patches)
    return patches


def build_scene(
    widget: Widget, overlays: list[tuple[str, Widget, bool]]
) -> Scene:
    """Build a full :class:`Scene` from a root widget plus an overlay layer.

    Each overlay is given as a ``(id, widget, barrier)`` tuple: the ``id``
    becomes the overlay node's stable ``key`` (so the keyed diff matches it
    across rebuilds), and ``barrier`` is recorded as a ``barrier`` prop on the
    overlay node so a renderer knows whether to draw a touch-blocking scrim.

    Args:
        widget: The root screen widget.
        overlays: The overlay layer, in ascending z-order, as
            ``(overlay_id, widget, barrier)`` tuples.

    Returns:
        The built scene (root node + overlay nodes).
    """
    root = build(widget)
    overlay_nodes: list[Node] = []
    for overlay_id, overlay_widget, barrier in overlays:
        node = build(overlay_widget)
        props = dict(node.props)
        props["barrier"] = barrier
        overlay_nodes.append(
            node.model_copy(update={"key": overlay_id, "props": props})
        )
    return Scene(root=root, overlays=overlay_nodes)


def diff_scene(old: Scene, new: Scene) -> list[Patch]:
    """Diff two scenes into an ordered patch list.

    The root tree is diffed exactly as :func:`diff` does (paths unchanged, so
    every existing renderer consumer is unaffected). The overlay layer is diffed
    as a fully-keyed child list (each overlay's ``key`` is its stable id) under
    the reserved ``("overlay",)`` path prefix, so overlay add/remove/reorder
    reuse the existing :class:`Insert`/:class:`Remove`/:class:`Reorder`/
    :class:`Update`/:class:`Replace` patch kinds — no new patch kind is needed.

    Args:
        old: The previously rendered scene.
        new: The freshly built scene.

    Returns:
        The patches transforming ``old`` into ``new`` (empty if identical).
    """
    patches: list[Patch] = []
    _reconcile(old.root, new.root, (), patches)
    _reconcile_overlays(old.overlays, new.overlays, patches)
    return patches


def _reconcile_overlays(
    old: list[Node], new: list[Node], patches: list[Patch]
) -> None:
    """Diff the overlay layer under the reserved ``("overlay",)`` path prefix.

    Overlays are always keyed by their stable id, so a fully-keyed diff applies
    when both layers are non-empty; otherwise the positional path handles the
    empty-to-N and N-to-empty transitions. All emitted paths start with the
    reserved ``"overlay"`` token.

    Args:
        old: The old overlay nodes.
        new: The new overlay nodes.
        patches: The accumulator to append patches to.
    """
    _reconcile_children(old, new, (OVERLAY_STEP,), patches)


def _reconcile(
    old: Node,
    new: Node,
    path: Path,
    patches: list[Patch],
) -> None:
    """Reconcile one node against another at ``path``, appending patches.

    Args:
        old: The old node at this position.
        new: The new node at this position.
        path: The address of this node.
        patches: The accumulator to append patches to.
    """
    if old.type != new.type or old.key != new.key:
        patches.append(Replace(path=path, node=new))
        return

    set_props, unset_props = _diff_props(old.props, new.props)
    if set_props or unset_props:
        patches.append(
            Update(path=path, set_props=set_props, unset_props=unset_props)
        )

    _reconcile_children(old.children, new.children, path, patches)


def _reconcile_children(
    old: list[Node],
    new: list[Node],
    path: Path,
    patches: list[Patch],
) -> None:
    """Reconcile two child lists under ``path``.

    Args:
        old: The old children.
        new: The new children.
        path: The address of the parent node.
        patches: The accumulator to append patches to.
    """
    if old and new and _fully_keyed(old) and _fully_keyed(new):
        _reconcile_keyed(old, new, path, patches)
        return

    common = min(len(old), len(new))
    for index in range(common):
        _reconcile(old[index], new[index], path + (index,), patches)
    for index in range(len(old) - 1, common - 1, -1):
        patches.append(Remove(path=path, index=index))
    for index in range(common, len(new)):
        patches.append(Insert(path=path, index=index, node=new[index]))


def _fully_keyed(nodes: list[Node]) -> bool:
    """Report whether every node carries a key and all keys are unique.

    Args:
        nodes: The child nodes to inspect.

    Returns:
        ``True`` when no key is ``None`` and no key repeats.
    """
    keys = [node.key for node in nodes]
    return None not in keys and len(set(keys)) == len(keys)


def _reconcile_keyed(
    old: list[Node],
    new: list[Node],
    path: Path,
    patches: list[Patch],
) -> None:
    """Diff two fully-keyed child lists into a minimal patch sequence.

    Emits, in order: :class:`Remove` for keys gone from ``new`` (descending
    index), a single :class:`Reorder` realigning the survivors to their new
    relative order, :class:`Insert` for keys new to the list (ascending final
    index), then recurses each matched key at its final index. Applying the
    patches in this order is correct because each index is valid against the live
    child list at the moment its patch runs: removals shrink from the tail,
    the reorder permutes the survivors, ascending inserts land at final slots,
    and the matched survivors end up at their new indices for the recursion.

    Args:
        old: The old children (fully keyed, unique).
        new: The new children (fully keyed, unique).
        path: The address of the parent node.
        patches: The accumulator to append patches to.
    """
    new_keys = {node.key for node in new}
    old_keys = {node.key for node in old}

    # 1. Remove keys gone from `new`, descending so lower indices stay valid.
    for index in range(len(old) - 1, -1, -1):
        if old[index].key not in new_keys:
            patches.append(Remove(path=path, index=index))

    # 2. Realign the survivors (old order) to their new relative order.
    survivor_index = {
        node.key: index
        for index, node in enumerate(node for node in old if node.key in new_keys)
    }
    order = [survivor_index[node.key] for node in new if node.key in old_keys]
    if order != list(range(len(order))):
        patches.append(Reorder(path=path, order=order))

    # 3. Insert keys new to the list at their final indices, ascending.
    for index, node in enumerate(new):
        if node.key not in old_keys:
            patches.append(Insert(path=path, index=index, node=node))

    # 4. Recurse matched keys at their final (new) indices.
    old_by_key = {node.key: node for node in old}
    for index, node in enumerate(new):
        if node.key in old_keys:
            _reconcile(old_by_key[node.key], node, path + (index,), patches)


def _diff_props(
    old: dict[str, Any],
    new: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Compute the prop changes between two prop maps.

    Args:
        old: The old props.
        new: The new props.

    Returns:
        A ``(set_props, unset_props)`` pair: props to add/overwrite, and prop
        names that were removed.
    """
    set_props = {
        key: value
        for key, value in new.items()
        if key not in old or old[key] != value
    }
    unset_props = [key for key in old if key not in new]
    return set_props, unset_props
