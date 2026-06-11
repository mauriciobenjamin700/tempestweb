"""A minimal, deterministic reference DOM and patch applicator.

This mirrors the behavior the JS client (``client/dom.js``) must implement, per
``docs/contract.md``. It exists in pure Python so the A-vs-B guarantee is fully
automatable under pytest without a browser: a transport delivers patch batches,
this applicator mutates the tree, and two transports' resulting trees are
compared for equality.

The reference is intentionally simple — it models the *structure* the contract
defines (type, key, props, children) and the *five patch semantics*, not real
CSS. It is the contract's executable specification, not a renderer.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DomNode:
    """A rendered node mirroring the serialized IR shape.

    Attributes:
        type: The widget type name (e.g. ``"Column"``, ``"Text"``).
        key: The stable reconciliation key, or ``None``.
        props: The widget props as a JSON-able mapping.
        children: The child nodes, in document order.
    """

    type: str
    key: str | None
    props: dict[str, Any]
    children: list[DomNode] = field(default_factory=list)

    @classmethod
    def from_ir(cls, ir: dict[str, Any]) -> DomNode:
        """Build a :class:`DomNode` tree from a serialized IR node.

        Args:
            ir: A JSON-able node dict (``{type, key, props, children}``).

        Returns:
            The equivalent :class:`DomNode` tree (a deep, independent copy).
        """
        return cls(
            type=ir["type"],
            key=ir.get("key"),
            props=copy.deepcopy(ir.get("props", {})),
            children=[cls.from_ir(child) for child in ir.get("children", [])],
        )

    def to_ir(self) -> dict[str, Any]:
        """Serialize this node back to the JSON-able IR shape.

        Returns:
            A node dict equivalent to what the core's ``Node.model_dump`` emits.
        """
        return {
            "type": self.type,
            "key": self.key,
            "props": copy.deepcopy(self.props),
            "children": [child.to_ir() for child in self.children],
        }


def patch_kind(patch: dict[str, Any]) -> str:
    """Classify a patch by the contract's key-presence rules.

    Per ``docs/contract.md``: ``set_props``->update, ``node``+``index``->insert,
    only ``index``->remove, ``order``->reorder, ``node`` without ``index``->replace.

    Args:
        patch: A JSON-able patch dict.

    Returns:
        One of ``"update"``, ``"insert"``, ``"remove"``, ``"reorder"``,
        ``"replace"``.

    Raises:
        ValueError: If the patch matches no known shape.
    """
    if "set_props" in patch:
        return "update"
    if "order" in patch:
        return "reorder"
    if "node" in patch and "index" in patch:
        return "insert"
    if "node" in patch:
        return "replace"
    if "index" in patch:
        return "remove"
    raise ValueError(f"Unrecognized patch shape: {sorted(patch)}")


def _resolve(root: DomNode, path: list[int]) -> DomNode:
    """Walk ``path`` from ``root`` to the target node.

    Args:
        root: The tree root.
        path: A list of child indices (``[]`` is the root itself).

    Returns:
        The node at ``path``.

    Raises:
        IndexError: If the path leaves the tree.
    """
    node = root
    for index in path:
        node = node.children[index]
    return node


def apply_patch(root: DomNode, patch: dict[str, Any]) -> DomNode:
    """Apply a single patch to the tree, returning the (possibly new) root.

    The root is mutated in place for child-targeting patches; a Replace at the
    empty path returns a brand-new root. Callers should always rebind to the
    return value.

    Args:
        root: The current tree root.
        patch: A JSON-able patch dict (any of the five kinds).

    Returns:
        The resulting tree root.

    Raises:
        ValueError: If the patch shape is unrecognized.
    """
    kind = patch_kind(patch)
    path: list[int] = patch["path"]

    if kind == "update":
        target = _resolve(root, path)
        for prop_key, value in patch["set_props"].items():
            target.props[prop_key] = copy.deepcopy(value)
        for prop_key in patch.get("unset_props", []):
            target.props.pop(prop_key, None)
        return root

    if kind == "insert":
        parent = _resolve(root, path)
        parent.children.insert(patch["index"], DomNode.from_ir(patch["node"]))
        return root

    if kind == "remove":
        parent = _resolve(root, path)
        del parent.children[patch["index"]]
        return root

    if kind == "reorder":
        parent = _resolve(root, path)
        order: list[int] = patch["order"]
        parent.children = [parent.children[old] for old in order]
        return root

    # replace
    new_node = DomNode.from_ir(patch["node"])
    if not path:
        return new_node
    parent = _resolve(root, path[:-1])
    parent.children[path[-1]] = new_node
    return root


def apply_batch(root: DomNode, patches: list[dict[str, Any]]) -> DomNode:
    """Apply a coalesced batch of patches (one tick) in order.

    Args:
        root: The current tree root.
        patches: The patch batch, in apply order. May be empty.

    Returns:
        The resulting tree root after the whole batch.
    """
    for patch in patches:
        root = apply_patch(root, patch)
    return root
