"""The wire contract is frozen: a shape change has to be deliberate.

The golden fixtures pin the wire, and they are **regenerable from the core** — so
they catch accidental drift but cannot tell "I regenerated because the core moved"
from "I changed the contract" (tempestweb#121). A third-party client had nothing to
lean on, which is one of the two things the repo listed as a 1.0 prerequisite.

The digest closes it. Values may move freely (a fixture regenerated with a new
count, a different colour); keys and types may not, and when they do this test
names the choice the author owes: additive change, or version bump plus migration
note. The one place a *value* is a shape change — a nullable field that gains one —
is pinned below, so it reads as a decision instead of a surprise.
"""

from __future__ import annotations

import json
from pathlib import Path

from tempestweb.contract import (
    WIRE_CONTRACT_VERSION,
    WIRE_SHAPE_DIGEST,
    _shape_of,
    wire_shape,
    wire_shape_digest,
)

FIXTURES: Path = Path(__file__).resolve().parents[1] / "fixtures"


def test_the_wire_shape_matches_the_frozen_digest() -> None:
    """The wire's shape is what the frozen digest says it is."""
    assert wire_shape_digest() == WIRE_SHAPE_DIGEST, (
        "the wire contract's SHAPE changed (a key added, renamed, removed or "
        "retyped; a new envelope kind; a new event type).\n\n"
        "This is a compatibility decision, not a refactor:\n"
        "  • additive (new optional key / new envelope kind / new event type): keep "
        f"WIRE_CONTRACT_VERSION at {WIRE_CONTRACT_VERSION}, update "
        "WIRE_SHAPE_DIGEST, and say so in the CHANGELOG.\n"
        "  • breaking (renamed/removed/retyped key, changed patch semantics): bump "
        "WIRE_CONTRACT_VERSION, update WIRE_SHAPE_DIGEST, and write the migration "
        "note docs/stability.md promises.\n\n"
        f"new digest: {wire_shape_digest()}"
    )


def test_the_shape_carries_types_and_no_values() -> None:
    """The shape records types; no fixture value survives into it.

    That is the point of digesting the *shape*: the fixtures are derived from the
    live core, so their values move with it. Only keys and types are the contract.
    """
    shape = wire_shape()
    serialized = json.dumps(shape)
    # No fixture value leaks into the shape: the counter label, its colours and
    # its numbers are all absent.
    assert "Count: 0" not in serialized
    assert "#6750a4" not in serialized
    # What is left is type names. (No fixture carries a boolean today, which is
    # why "bool" is not asserted: the shape reports what the wire has.)
    for leaf in ("str", "int", "float", "null"):
        assert leaf in serialized


def test_every_envelope_kind_and_event_type_is_covered() -> None:
    """The shape carries the routing tables a client dispatches on."""
    shape = wire_shape()
    assert "patches" in shape["envelope_kinds"]
    assert "navigate" in shape["envelope_kinds"]
    assert shape["event_types"]["click"] == ["on_click"]
    assert shape["event_types"]["toggle"] == ["on_change"]


def test_a_nullable_field_gaining_a_value_is_a_shape_change() -> None:
    """A field that was ``null`` and now has a type moves the digest, on purpose.

    This is the one case where a *value* is a shape change, and it is pinned here
    so the next person to hit it reads a decision instead of guessing at a bug:
    the fixture is all this module can see, so ``null`` is recorded as the type
    ``null``. A client that had only ever seen nothing there now has something to
    parse — worth a look, and worth saying out loud that the reverse holds too: a
    field that stays ``null`` everywhere has its declared type unpinned.
    """
    node = json.loads(
        (FIXTURES / "node_initial.json").read_text(encoding="utf-8"),
    )
    assert node["key"] is None, "this test needs a nullable field that is null"

    with_value = {**node, "key": "root"}

    assert _shape_of(node) != _shape_of(with_value)
    assert _shape_of(node)["key"] == "null"
    assert _shape_of(with_value)["key"] == "str"
