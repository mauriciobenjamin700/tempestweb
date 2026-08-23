"""The wire contract is frozen: a shape change has to be deliberate.

The golden fixtures pin the wire, and they are **regenerable from the core** — so
they catch accidental drift but cannot tell "I regenerated because the core moved"
from "I changed the contract" (tempestweb#121). A third-party client had nothing to
lean on, which is one of the two things the repo listed as a 1.0 prerequisite.

The digest closes it. Values may move freely (a fixture regenerated with a new
count, a different colour); keys and types may not, and when they do this test
names the choice the author owes: additive change, or version bump plus migration
note.
"""

from __future__ import annotations

import json

from tempestweb.contract import (
    WIRE_CONTRACT_VERSION,
    WIRE_SHAPE_DIGEST,
    wire_shape,
    wire_shape_digest,
)


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


def test_the_shape_ignores_values_so_a_regenerated_fixture_is_free() -> None:
    """Regenerating a fixture with different values does not move the digest.

    That is the whole point of digesting the *shape*: the fixtures are derived
    from the live core, so their values move with it. Only keys and types are the
    contract.
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
