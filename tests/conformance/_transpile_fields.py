"""Regenerate the Mode C invalid-field fixture from the real core.

Run as a module to (re)write the golden::

    python -m tests.conformance._transpile_fields

The style table the Mode C builders read is the **resting** style per
variant/size/scheme, which is enough for every widget but one: a field carrying
an ``error`` message is *invalid*, and the core repaints its border and its text
in the ``error`` role at build time. That rule lives in the built style, not in
the stylesheet, so a Mode C field with a validation message rendered as if it
were fine.

``Input`` is the only primitive with both an ``error`` prop and a field variant,
so this matrix pins it across the three treatments (the flushed one carries a
``SideBorder``, not a ``Border``), the sizes, the schemes, and the interaction
with a caller-supplied style.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tempest_core import Color, Input, Style, build
from tempestweb.runtime.wasm import serialize_node

FIXTURES_DIR: Path = Path(__file__).resolve().parents[1] / "fixtures"
FIELDS_FIXTURE: Path = FIXTURES_DIR / "transpile_field_samples.json"


def _cases() -> dict[str, Input]:
    """Return the sample field builds keyed by a scenario name.

    Returns:
        A scenario name → ``Input`` map covering the valid/invalid pair on each
        field treatment, plus the size, scheme and caller-style axes that the
        invalid override has to survive.
    """
    return {
        "field_outline_valid": Input(value="a", key="f"),
        "field_outline_invalid": Input(value="a", error="obrigatório", key="f"),
        "field_filled_valid": Input(value="a", field_variant="filled", key="f"),
        "field_filled_invalid": Input(
            value="a", field_variant="filled", error="obrigatório", key="f"
        ),
        "field_flushed_valid": Input(value="a", field_variant="flushed", key="f"),
        "field_flushed_invalid": Input(
            value="a", field_variant="flushed", error="obrigatório", key="f"
        ),
        "field_invalid_lg_secondary": Input(
            value="a", size="lg", color_scheme="secondary", error="x", key="f"
        ),
        "field_invalid_sm_error_scheme": Input(
            value="a", size="sm", color_scheme="error", error="x", key="f"
        ),
        "field_invalid_keeps_caller_style": Input(
            value="a",
            error="x",
            style=Style(background=Color(r=1, g=2, b=3), radius=3.0),
            key="f",
        ),
        "field_invalid_caller_border_wins": Input(
            value="a",
            error="x",
            style=Style(color=Color(r=9, g=9, b=9)),
            key="f",
        ),
    }


def build_samples() -> dict[str, Any]:
    """Build each sample field to its serialized IR.

    Returns:
        A scenario → serialized IR node map.
    """
    return {name: serialize_node(build(widget)) for name, widget in _cases().items()}


def render_fixture_text() -> str:
    """Render the invalid-field fixture as canonical JSON text."""
    return (
        json.dumps(build_samples(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )


def write_fixture() -> Path:
    """Write the invalid-field fixture to disk and return its path."""
    FIELDS_FIXTURE.write_text(render_fixture_text(), encoding="utf-8")
    return FIELDS_FIXTURE


def main() -> None:
    """Regenerate the invalid-field fixture and print its path."""
    print(f"wrote {write_fixture()}")


if __name__ == "__main__":
    main()
