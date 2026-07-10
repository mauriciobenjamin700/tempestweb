"""Golden test: the Mode C widget-style table matches the live core.

``client/transpile/widget-styles.gen.js`` is introspected from the real core (see
:mod:`tests.conformance._transpile_widget_styles`). If the core's resolved widget
styles drift, this fails until the table is regenerated and reviewed — the same
regenerable-golden guarantee the wire fixtures use.
"""

from __future__ import annotations

from tests.conformance._transpile_widget_styles import (
    STYLES_MODULE,
    build_table,
    render_module_text,
)


def test_widget_styles_module_matches_core() -> None:
    """The committed style module byte-matches a fresh render from the core."""
    on_disk = STYLES_MODULE.read_text(encoding="utf-8")
    assert on_disk == render_module_text(), (
        "widget-styles.gen.js is stale — regenerate with "
        "`python -m tests.conformance._transpile_widget_styles` and review the diff"
    )


def test_table_covers_button_combinations() -> None:
    """The table carries a resolved style for every Button variant/size/scheme."""
    table = build_table()
    button = table["Button"]
    assert set(button) == {"solid", "outline", "ghost", "link"}
    # A solid/md/primary button resolves a filled background (the canonical case).
    solid = button["solid"]["md"]["primary"]
    assert "background" in solid
    assert "color" in solid
