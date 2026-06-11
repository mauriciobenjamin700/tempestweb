"""Pin the Python<->client wire format against regenerable golden fixtures.

These tests lock the *shape* of what the real core emits: the serialized node IR,
the five patch kinds, and the per-tick patch batches. The goldens are derived from
the core (see :mod:`._generate`); if the core's wire format drifts, these tests
fail until the goldens are regenerated and reviewed — exactly the "regenerable
golden" guarantee.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tempestweb._core import Button, Column, Text, build, diff
from tests.conformance._dom import patch_kind
from tests.conformance._generate import CONFORMANCE_FIXTURE, render_fixture_text
from tests.conformance._scenarios import SCENARIOS, scenario_to_fixture

FIXTURES_DIR: Path = Path(__file__).resolve().parents[1] / "fixtures"


def _load(name: str) -> Any:
    """Load a JSON golden fixture from ``tests/fixtures/``.

    Args:
        name: The fixture file name.

    Returns:
        The parsed JSON payload.
    """
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_conformance_fixture_is_committed() -> None:
    """The conformance golden file exists on disk."""
    assert CONFORMANCE_FIXTURE.exists(), (
        "conformance_scenarios.json missing — run "
        "`python -m tests.conformance._generate`"
    )


def test_conformance_fixture_matches_core() -> None:
    """The committed golden equals a fresh render from the real core.

    This is the regenerable-golden lock: the on-disk fixture must byte-match what
    :func:`render_fixture_text` produces now. If the core changes the wire shape,
    this fails until the goldens are regenerated.
    """
    on_disk: str = CONFORMANCE_FIXTURE.read_text(encoding="utf-8")
    assert on_disk == render_fixture_text(), (
        "conformance_scenarios.json is stale — regenerate with "
        "`python -m tests.conformance._generate` and review the diff"
    )


def test_node_ir_shape() -> None:
    """Each serialized node carries exactly the contract's four top-level keys."""
    node = build(Column(key="root", children=[Text(content="x", key="t")]))
    dumped = node.model_dump(mode="json")
    assert sorted(dumped) == ["children", "key", "props", "type"]
    assert dumped["type"] == "Column"
    assert dumped["key"] == "root"
    assert isinstance(dumped["props"], dict)
    assert isinstance(dumped["children"], list)


def test_text_props_carry_content() -> None:
    """Text props expose ``content`` and a nullable ``style`` per the contract."""
    node = build(Text(content="Count: 0", key="label"))
    props = node.model_dump(mode="json")["props"]
    assert props["content"] == "Count: 0"
    assert "style" in props and props["style"] is None


def test_button_props_carry_label_and_handler_ref() -> None:
    """Button props expose ``label`` and a nullable ``on_click`` handler ref."""
    node = build(Button(label="+", key="inc"))
    props = node.model_dump(mode="json")["props"]
    assert props["label"] == "+"
    assert "on_click" in props and props["on_click"] is None


def test_all_five_patch_kinds_are_emitted_and_classified() -> None:
    """The core emits all five patch kinds and each classifies as the contract says."""

    def first_patch(older: Column, newer: Column) -> dict[str, Any]:
        """Diff two trees and return the first emitted patch, serialized."""
        return diff(build(older), build(newer))[0].model_dump(mode="json")

    def texts(*items: str) -> Column:
        """Build a Column of keyed Text children (key == content)."""
        return Column(children=[Text(content=i, key=i) for i in items])

    emitted: dict[str, dict[str, Any]] = {
        "update": first_patch(
            texts("0"), Column(children=[Text(content="1", key="0")])
        ),
        "insert": first_patch(texts("a"), texts("a", "b")),
        "remove": first_patch(texts("a", "b"), texts("a")),
        "reorder": first_patch(texts("a", "b"), texts("b", "a")),
        "replace": first_patch(
            Column(children=[Text(content="a", key="x")]),
            Column(children=[Button(label="a", key="x")]),
        ),
    }

    for expected_kind, patch in emitted.items():
        assert patch_kind(patch) == expected_kind, (
            f"{expected_kind} patch {patch} classified as {patch_kind(patch)}"
        )

    # Spot-check the discriminating keys the client relies on.
    assert "set_props" in emitted["update"] and "unset_props" in emitted["update"]
    assert {"index", "node", "path"} <= set(emitted["insert"])
    assert set(emitted["remove"]) == {"index", "path"}
    assert "order" in emitted["reorder"]
    assert "node" in emitted["replace"] and "index" not in emitted["replace"]


def test_patch_paths_are_index_lists() -> None:
    """Every emitted patch carries ``path`` as a list of integer indices."""
    patches = diff(
        build(Column(children=[Text(content="0", key="t")])),
        build(Column(children=[Text(content="1", key="t")])),
    )
    for patch in patches:
        dumped = patch.model_dump(mode="json")
        assert isinstance(dumped["path"], list)
        assert all(isinstance(i, int) for i in dumped["path"])


@pytest.mark.parametrize("scenario_name", sorted(SCENARIOS))
def test_scenario_ticks_match_golden(scenario_name: str) -> None:
    """Each scenario's per-tick patch batches match the committed golden.

    Args:
        scenario_name: The scenario under test.
    """
    golden = _load("conformance_scenarios.json")[scenario_name]
    fresh = scenario_to_fixture(scenario_name, SCENARIOS[scenario_name])
    assert fresh["ticks"] == golden["ticks"]
    assert fresh["initial"] == golden["initial"]
    assert fresh["final"] == golden["final"]


def test_legacy_patches_all_kinds_fixture_still_matches_core() -> None:
    """The pre-existing patches_all_kinds.json shapes still match the live core.

    Guards the original contract fixture against core drift without editing it.
    """
    legacy = _load("patches_all_kinds.json")
    for kind in ("update", "insert", "remove", "reorder", "replace"):
        assert kind in legacy, f"legacy fixture missing {kind}"
        assert patch_kind(legacy[kind][0]) == kind
