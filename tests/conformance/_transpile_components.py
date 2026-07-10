"""Regenerate the Mode C component-parity fixture from the real core.

Run as a module to (re)write the golden::

    python -m tests.conformance._transpile_components

The portable layout components (``HStack`` / ``VStack``) are hand-authored in
``client/transpile/components.js`` (they expand to a plain Row/Column). This
fixture pins their expected IR — built from the *real* core — so a JS test can
assert the hand-authored builders still match the core (order- and key-agnostic).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tempest_core import Text, build
from tempest_core.components import HStack, VStack

FIXTURES_DIR: Path = Path(__file__).resolve().parents[1] / "fixtures"
COMPONENTS_FIXTURE: Path = FIXTURES_DIR / "transpile_component_samples.json"


def _cases() -> dict[str, Any]:
    """Return the sample component builds keyed by a scenario name."""
    child = Text(content="a", key="a")
    return {
        "hstack_default": HStack(children=[child]),
        "hstack_lg_between": HStack(children=[], gap="lg", justify="space-between"),
        "hstack_float": HStack(children=[], gap=8.0),
        "vstack_sm": VStack(children=[child], gap="sm"),
        "vstack_start": VStack(children=[child], align="start"),
    }


def build_samples() -> dict[str, Any]:
    """Build each sample to its serialized IR (the component's own key dropped).

    The auto-assigned component key is dropped so the fixture pins the *shape and
    style* the builder must reproduce, not the core's incidental keying.

    Returns:
        A scenario → serialized IR node map.
    """
    samples: dict[str, Any] = {}
    for name, widget in _cases().items():
        node = build(widget).model_dump(mode="json")
        node["key"] = None
        samples[name] = node
    return samples


def render_fixture_text() -> str:
    """Render the component-parity fixture as canonical JSON text."""
    return (
        json.dumps(build_samples(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )


def write_fixture() -> Path:
    """Write the component-parity fixture to disk and return its path."""
    COMPONENTS_FIXTURE.write_text(render_fixture_text(), encoding="utf-8")
    return COMPONENTS_FIXTURE


def main() -> None:
    """Regenerate the component-parity fixture and print its path."""
    print(f"wrote {write_fixture()}")


if __name__ == "__main__":
    main()
