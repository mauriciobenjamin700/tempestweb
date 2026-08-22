"""Golden tests: the generated Mode C widget builders match the live core.

``client/transpile/widgets.gen.js`` (one IR builder per buildable core widget)
and ``widget-styles.gen.js`` are introspected from the real ``tempest_core`` (see
:mod:`tests.conformance._transpile_widgets` and
:mod:`tests.conformance._transpile_widget_styles`). If the core's widget surface
or resolved styles drift, these fail until the modules are regenerated and
reviewed — the same regenerable-golden guarantee the wire fixtures use.
"""

from __future__ import annotations

import re
from pathlib import Path

from tempestweb.cli.commands import build as build_cmd
from tempestweb.transpile._served import SERVED_NAMES
from tempestweb.transpile.codegen import _camel_name
from tests.conformance import _transpile_components as components_gen
from tests.conformance import _transpile_served as served_gen
from tests.conformance import _transpile_spacing as spacing_gen
from tests.conformance import _transpile_values as values_gen
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


def test_spacing_module_matches_core() -> None:
    """The committed spacing.gen.js byte-matches a fresh render from the core."""
    on_disk = spacing_gen.SPACING_MODULE.read_text(encoding="utf-8")
    assert on_disk == spacing_gen.render_module_text(), (
        "spacing.gen.js is stale — regenerate with "
        "`python -m tests.conformance._transpile_spacing`"
    )


def test_component_samples_fixture_matches_core() -> None:
    """The HStack/VStack parity fixture byte-matches a fresh core render."""
    on_disk = components_gen.COMPONENTS_FIXTURE.read_text(encoding="utf-8")
    assert on_disk == components_gen.render_fixture_text(), (
        "transpile_component_samples.json is stale — regenerate with "
        "`python -m tests.conformance._transpile_components`"
    )


def test_layout_components_are_available() -> None:
    """The ergonomic layout components are re-exported for apps to import."""
    widgets_js = (Path(widgets_gen.WIDGETS_MODULE).parent / "widgets.js").read_text(
        encoding="utf-8"
    )
    assert "HStack" in widgets_js
    assert "VStack" in widgets_js


def test_every_builder_takes_the_core_child_slot() -> None:
    """A builder's child parameter is the core's field name, not always ``children``.

    The IR node carries one flat ``children`` array, which is why every builder
    used to *accept* only ``children`` — and why a view written the way the core
    demands (``Container(child=...)``, ``Form(fields=...)``) silently lost its
    subtree in Mode C while working in Modes A and B. The parameter list is the
    contract with the transpiler, so it is asserted against the live core.
    """
    source = widgets_gen.WIDGETS_MODULE.read_text(encoding="utf-8")
    missing: list[str] = []
    for name, spec in buildable_widgets().items():
        signature = source.split(f"export function {name}({{", 1)
        if len(signature) < 2:
            continue
        params = signature[1].split("} = {}) {", 1)[0]
        for field_name, is_list in spec.child_fields:
            camel = widgets_gen._camel(field_name)
            default = "[]" if is_list else "null"
            if f"{camel} = {default}" not in params:
                missing.append(f"{name} does not take `{camel} = {default}`")
    assert not missing, "\n".join(missing)


def test_the_child_slot_lands_in_the_ir_children_array() -> None:
    """Whatever the slot is called, the emitted node folds it into ``children``.

    ``RouteDrawer`` is the case that pins the order: the core builds
    ``[child, drawer]``, so a builder that concatenated them the other way would
    render a drawer where the body belongs.
    """
    source = widgets_gen.WIDGETS_MODULE.read_text(encoding="utf-8")
    for name, spec in buildable_widgets().items():
        if not spec.child_fields:
            continue
        body = source.split(f"export function {name}({{", 1)
        if len(body) < 2:
            continue
        emitted = body[1].split("\n}", 1)[0]
        expected = f"children: {widgets_gen._children_expr(spec)},"
        assert expected in emitted, f"{name} does not fold its slots as {expected}"


def test_every_core_field_is_reachable_from_the_builder() -> None:
    """A field the builder does not declare cannot be set from Mode C at all.

    The transpiler camelizes a widget kwarg by rule, so this is the assertion
    that ties the two sides together: if the core grows ``on_hover`` and the
    builders are not regenerated, the transpiled call emits ``onHover`` into an
    object nobody destructures and the handler is silently dead.

    ``theme`` and ``media`` are the documented exception: they feed the Material
    3 style resolution the builder runs itself (``resolveWidgetStyle``), so they
    are inputs to generation, not props a caller passes.
    """
    source = widgets_gen.WIDGETS_MODULE.read_text(encoding="utf-8")
    resolved_by_the_builder = {"theme", "media"}
    unreachable: list[str] = []
    for name, spec in buildable_widgets().items():
        chunk = source.split(f"export function {name}({{", 1)
        if len(chunk) < 2:
            continue
        params = chunk[1].split("} = {}) {", 1)[0]
        declared = set(re.findall(r"([A-Za-z_$][\w$]*)\s*(?:=|,|$)", params))
        for field_name in spec.cls.model_fields:
            if field_name in resolved_by_the_builder:
                continue
            if _camel_name(field_name) not in declared:
                unreachable.append(f"{name}.{field_name}")
    assert not unreachable, "unreachable from Mode C: " + ", ".join(unreachable)


def test_values_module_matches_core() -> None:
    """The committed values.gen.js byte-matches a fresh render from the core."""
    on_disk = values_gen.VALUES_MODULE.read_text(encoding="utf-8")
    assert on_disk == values_gen.render_module_text(), (
        "values.gen.js is stale — regenerate with "
        "`python -m tests.conformance._transpile_values` and review the diff"
    )


def test_served_manifest_matches_the_client() -> None:
    """The shipped manifest byte-matches a fresh render from the client JS.

    The compiler refuses a name this manifest does not list, so a stale manifest
    either rejects something that works or admits an import the browser cannot
    resolve.
    """
    on_disk = served_gen.SERVED_MODULE.read_text(encoding="utf-8")
    assert on_disk == served_gen.render_module_text(), (
        "tempestweb/transpile/_served.py is stale — regenerate with "
        "`python -m tests.conformance._transpile_served`"
    )


def test_the_values_module_is_copied_into_the_artifact() -> None:
    """A generated client module nobody copies simply does not exist in a build.

    ``values.gen.js`` is imported by ``widgets.js``, so leaving it out of the
    asset list would break every artifact at load time rather than at build.
    """
    assert "values.gen.js" in build_cmd._TRANSPILE_ASSETS


def test_the_core_value_surface_is_served() -> None:
    """The enums, value objects and tokens a view uses resolve in Mode C.

    These are the names that used to compile into an import of something the
    client does not export: a blank page, with the goldens green.
    """
    for name in (
        "TextAlign",
        "FontWeight",
        "AlignItems",
        "JustifyContent",
        "KeyboardType",
        "Semantics",
        "Border",
        "Shadow",
        "Gradient",
        "ACCENT",
        "ON_SURFACE",
        "HOVER_OPACITY",
    ):
        assert name in SERVED_NAMES, f"{name} is not served by the Mode C client"
