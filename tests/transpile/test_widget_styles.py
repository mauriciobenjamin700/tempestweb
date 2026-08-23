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
    # A solid/md/primary button resolves a filled background (the canonical case),
    # in each mode — and the two differ, which is the point of the mode axis: a
    # table baked from one theme made every Mode C widget render light (#106).
    solid = button["solid"]["md"]["primary"]
    assert set(solid) == {"light", "dark"}
    for mode in ("light", "dark"):
        assert "background" in solid[mode]
        assert "color" in solid[mode]
    assert solid["light"]["background"] != solid["dark"]["background"]


def test_mode_free_component_tables_really_are_mode_free() -> None:
    """The two scale tables carry no colour, so they ship without a mode axis.

    ``SHAPE_STEPS`` and ``TYPOGRAPHY`` are emitted flat on that basis. The day the
    core makes a radius or a type step depend on the theme mode, this fails —
    instead of Mode C quietly resolving the light one forever.
    """
    from tempest_core import Theme, ThemeMode
    from tests.conformance._transpile_component_styles import shape_steps, typography

    light, dark = Theme(mode=ThemeMode.LIGHT), Theme(mode=ThemeMode.DARK)
    assert shape_steps(light) == shape_steps(dark)
    assert typography(light) == typography(dark)
