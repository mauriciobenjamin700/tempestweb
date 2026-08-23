"""The wire contract's version, and the digest that makes a change deliberate.

``docs/stability.md`` promises the wire contract as part of the stable surface for
1.0. It was pinned by golden fixtures — which catch **accidental** drift but are
regenerable from the core, so they cannot tell "I regenerated because the core
moved" from "I changed the contract" (tempestweb#121). A third-party client had
nothing to lean on.

This module closes that gap with two values and one rule:

* :data:`WIRE_CONTRACT_VERSION` — the contract's own version, independent of the
  package version. A client can read it and know what it is talking to.
* :data:`WIRE_SHAPE_DIGEST` — a digest of the wire's **shape** (every key and its
  type, not its value). Regenerating a fixture with new values leaves it alone;
  adding, renaming, removing or retyping a key changes it, and the freeze test
  fails until the author says which kind of change it was.

The shape covers what a client parses: the IR node, the five patch kinds, the
serialized ``Style``, the envelope kinds and the event types that route to a
handler. Anything a client does not parse is not in here.

What is compatible, and what is not:

* **Additive** (no version bump): a new optional key with a default a client can
  ignore; a new envelope ``kind`` (an unknown kind is skipped by every client in
  this repo); a new event ``type``.
* **Breaking** (major, and a migration note): renaming or removing a key,
  changing a key's type, changing what a patch kind means, or making a key
  required.

Either way the digest moves, and the test spells out which action the author owes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

__all__ = [
    "WIRE_CONTRACT_VERSION",
    "WIRE_SHAPE_DIGEST",
    "wire_shape",
    "wire_shape_digest",
]

#: The wire contract's version, bumped only for a **breaking** shape change (see
#: the module docstring). Independent of the package version: a client pins this.
WIRE_CONTRACT_VERSION: int = 1

#: SHA-256 of :func:`wire_shape`, frozen. Update it in the same commit that
#: changes the shape, together with the CHANGELOG entry the change deserves.
WIRE_SHAPE_DIGEST: str = (
    "34367004565e4796261ac3d967e3b95d862e21a10ce3d682ab8078800b85416d"
)

_FIXTURES: Path = Path(__file__).resolve().parents[1] / "tests" / "fixtures"

#: The golden fixtures whose shape is the contract, in a stable order.
_SHAPE_FIXTURES: tuple[str, ...] = (
    "node_initial.json",
    "patches_all_kinds.json",
    "style_sample.json",
)


def _shape_of(value: Any) -> Any:  # noqa: ANN401 — walks arbitrary wire JSON
    """Reduce a JSON value to its shape: keys and types, never values.

    A list collapses to the **union** of its items' shapes, so the five patch
    kinds in one fixture all count, and reordering them does not register as a
    change. A scalar becomes its type name.

    Args:
        value: Any JSON-able value from a fixture.

    Returns:
        The shape: nested dicts of key → shape, a one-element list holding the
        union shape of the items, or a type name.
    """
    if isinstance(value, dict):
        return {key: _shape_of(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        merged: dict[str, Any] = {}
        others: list[Any] = []
        for item in value:
            shape = _shape_of(item)
            if isinstance(shape, dict):
                for key, sub in shape.items():
                    merged[key] = sub if key not in merged else _widen(merged[key], sub)
            elif shape not in others:
                others.append(shape)
        if merged:
            return [dict(sorted(merged.items()))]
        return [sorted(others, key=str)] if others else []
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    return "null"


def _widen(left: Any, right: Any) -> Any:  # noqa: ANN401 — shape values are wire-shaped
    """Merge two shapes seen under the same key.

    Two items of one list may legitimately disagree — a patch carries ``node``
    only in some kinds, and a nullable field is a type in one item and ``null`` in
    another. Merging keeps every key seen and records a disagreement as a sorted
    union, so the digest is stable regardless of the fixture's item order.

    Args:
        left: The shape recorded so far.
        right: The shape just seen.

    Returns:
        The merged shape.
    """
    if left == right:
        return left
    if isinstance(left, dict) and isinstance(right, dict):
        keys = sorted(set(left) | set(right))
        return {
            key: _widen(left.get(key, "null"), right.get(key, "null")) for key in keys
        }
    options: list[Any] = []
    for shape in (left, right):
        if isinstance(shape, list) and len(shape) == 1 and isinstance(shape[0], list):
            options.extend(shape[0])
        else:
            options.append(shape)
    return sorted({json.dumps(option, sort_keys=True) for option in options})


def wire_shape() -> dict[str, Any]:
    """Build the contract's shape from the goldens and the routing tables.

    Returns:
        ``{"fixtures": {name: shape}, "envelope_kinds": [...],
        "event_types": {...}}`` — everything a client parses, and nothing else.
    """
    from tempestweb.runtime.serialize import EVENT_TYPE_TO_HANDLER_PROPS
    from tempestweb.transports.base import EnvelopeKind

    fixtures = {
        name: _shape_of(json.loads((_FIXTURES / name).read_text(encoding="utf-8")))
        for name in _SHAPE_FIXTURES
    }
    return {
        "fixtures": fixtures,
        "envelope_kinds": sorted(EnvelopeKind.__args__),  # type: ignore[attr-defined]
        "event_types": {
            event: sorted(props)
            for event, props in sorted(EVENT_TYPE_TO_HANDLER_PROPS.items())
        },
    }


def wire_shape_digest() -> str:
    """Digest the contract's shape.

    Returns:
        The SHA-256 hex digest of the canonical JSON of :func:`wire_shape`.
    """
    canonical = json.dumps(wire_shape(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
