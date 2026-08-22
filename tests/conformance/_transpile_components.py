"""Regenerate the Mode C component-parity fixture from the real core.

Run as a module to (re)write the golden::

    python -m tests.conformance._transpile_components

The Mode C components are hand-authored in ``client/transpile/components.js``:
the composition is rewritten per component, and the *output* of the core's pure
style resolvers travels as a generated table. Nothing checks that a rewrite is
faithful — so this fixture pins the expected IR, built from the **real** core
over a matrix of props, and a JS test diffs the hand-authored builder against it
(order- and key-agnostic).

The matrix matters: a single sample per component would pin the happy path and
let every variant, scheme, size and elevation drift silently, which is exactly
how a resolved style goes wrong.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tempest_core import (
    AppBar,
    Button,
    Card,
    Chip,
    Divider,
    HStack,
    RadioGroup,
    Scaffold,
    SegmentedControl,
    Text,
    VStack,
    build,
)
from tempestweb.runtime.wasm import serialize_node

FIXTURES_DIR: Path = Path(__file__).resolve().parents[1] / "fixtures"
COMPONENTS_FIXTURE: Path = FIXTURES_DIR / "transpile_component_samples.json"


def _noop(_: int) -> None:
    """Absorb a selection callback.

    Args:
        _: The selected index.
    """
    return None


def _cases() -> dict[str, Any]:
    """Return the sample component builds keyed by a scenario name.

    Returns:
        A scenario name → component instance map covering, per component, the
        axes that change its resolved style: variant, color scheme, size,
        elevation, the token steps, and the presence of each optional slot.
    """
    child = Text(content="a", key="a")
    cases: dict[str, Any] = {
        "hstack_default": HStack(children=[child]),
        "hstack_lg_between": HStack(children=[], gap="lg", justify="space-between"),
        "hstack_float": HStack(children=[], gap=8.0),
        "vstack_sm": VStack(children=[child], gap="sm"),
        "vstack_start": VStack(children=[child], align="start"),
        "card_default": Card(children=[child]),
        "card_filled_primary": Card(
            children=[child], variant="filled", color_scheme="primary"
        ),
        "card_outlined_error_flat": Card(
            children=[child], variant="outlined", color_scheme="error", elevation=0
        ),
        "card_elevated_level_4": Card(children=[child], elevation=4),
        "card_steps": Card(
            children=[child], padding_step="lg", radius_step="xl", gap_step="none"
        ),
        "divider_default": Divider(),
        "divider_token_thickness": Divider(thickness="xs"),
        "divider_tinted": Divider(color_scheme="primary"),
        "chip_static": Chip(label="tag"),
        "chip_selected": Chip(label="tag", selected=True),
        "chip_clickable_lg_success": Chip(
            label="tag", on_click=lambda: None, size="lg", color_scheme="success"
        ),
        "segmented_default": SegmentedControl(options=["a", "b"], on_select=_noop),
        "segmented_second_lg": SegmentedControl(
            options=["a", "b", "c"], selected=1, on_select=_noop, size="lg"
        ),
        "segmented_secondary": SegmentedControl(
            options=["a"], on_select=_noop, color_scheme="secondary"
        ),
        "appbar_title_only": AppBar(title="Home"),
        "appbar_filled_with_slots": AppBar(
            title="Home",
            variant="filled",
            leading=Button(label="<", on_click=lambda: None, key="back"),
            actions=[Button(label="+", on_click=lambda: None, key="add")],
        ),
        "appbar_outlined_primary_level_2": AppBar(
            title="Home", variant="outlined", color_scheme="primary", elevation=2
        ),
        "radio_default": RadioGroup(options=["a", "b"], on_select=_noop),
        "radio_second_sm_warning": RadioGroup(
            options=["a", "b"],
            selected=1,
            on_select=_noop,
            size="sm",
            color_scheme="warning",
        ),
        "scaffold_body_only": Scaffold(body=child),
        "scaffold_full": Scaffold(
            app_bar=AppBar(title="Home"), body=child, bottom_bar=Divider()
        ),
        "scaffold_scroll": Scaffold(body=child, scroll=True),
        "scaffold_empty": Scaffold(),
    }
    return cases


def build_samples() -> dict[str, Any]:
    """Build each sample to its serialized IR (the component's own key dropped).

    The auto-assigned component key is dropped so the fixture pins the *shape and
    style* the builder must reproduce, not the core's incidental keying. The wire
    serializer is the runtime's own, so a handler prop is ``null`` here exactly as
    it is on the wire — which is what the JS builders emit.

    Returns:
        A scenario → serialized IR node map.
    """
    samples: dict[str, Any] = {}
    for name, widget in _cases().items():
        node = serialize_node(build(widget))
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
