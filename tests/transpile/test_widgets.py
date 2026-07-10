"""Golden tests: the generated Mode C widget builders match the live core.

``client/transpile/widgets.gen.js`` (one IR builder per buildable core widget)
and ``widget-styles.gen.js`` are introspected from the real ``tempest_core`` (see
:mod:`tests.conformance._transpile_widgets` and
:mod:`tests.conformance._transpile_widget_styles`). If the core's widget surface
or resolved styles drift, these fail until the modules are regenerated and
reviewed — the same regenerable-golden guarantee the wire fixtures use.
"""

from __future__ import annotations

from tests.conformance import _transpile_widget_styles as styles_gen
from tests.conformance import _transpile_widgets as widgets_gen
from tests.conformance._widgetspec import buildable_widgets


def test_widgets_module_matches_core() -> None:
    """The committed widgets.gen.js byte-matches a fresh render from the core."""
    on_disk = widgets_gen.WIDGETS_MODULE.read_text(encoding="utf-8")
    assert on_disk == widgets_gen.render_module_text(), (
        "widgets.gen.js is stale — regenerate with "
        "`python -m tests.conformance._transpile_widgets` and review the diff"
    )


def test_widget_styles_module_matches_core() -> None:
    """The committed widget-styles.gen.js byte-matches a fresh render."""
    on_disk = styles_gen.STYLES_MODULE.read_text(encoding="utf-8")
    assert on_disk == styles_gen.render_module_text(), (
        "widget-styles.gen.js is stale — regenerate with "
        "`python -m tests.conformance._transpile_widget_styles` and review the diff"
    )


def test_covers_the_common_widgets() -> None:
    """The generated set covers the everyday layout/display/input widgets."""
    names = set(buildable_widgets())
    expected = {
        "Text",
        "Column",
        "Row",
        "Container",
        "Button",
        "Input",
        "TextArea",
        "Switch",
        "Checkbox",
        "Icon",
        "Image",
        "Stack",
        "Wrap",
        "ScrollView",
    }
    missing = expected - names
    assert not missing, f"missing builders for: {sorted(missing)}"
    # A broad port: dozens of widgets, not a handful.
    assert len(names) >= 40, f"only {len(names)} widgets covered"


def test_every_builder_is_emitted() -> None:
    """widgets.gen.js exports a builder function for every buildable widget."""
    source = widgets_gen.WIDGETS_MODULE.read_text(encoding="utf-8")
    for name in buildable_widgets():
        assert f"export function {name}(" in source, name
