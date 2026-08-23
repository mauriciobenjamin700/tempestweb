"""Unit + integration + security tests for the static HTML renderer.

Covers ``tempestweb.html.render_to_html`` / ``render_document``: the Node -> HTML
mapping (tags, void elements, controls, a11y, the ``tag``/``attrs`` escape
hatch), HTML-injection safety, component expansion, and the document wrapper.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tempest_core import (
    Autocomplete,
    Burger,
    Button,
    Canvas,
    Checkbox,
    Color,
    Column,
    Component,
    Container,
    DatePicker,
    Dropdown,
    Edge,
    FilePicker,
    Icon,
    IconButton,
    Icons,
    Image,
    Input,
    MaskedInput,
    PinInput,
    ProgressBar,
    RangeSlider,
    RouteDrawer,
    Row,
    Semantics,
    Slider,
    Spinner,
    Stack,
    Style,
    Switch,
    TabBar,
    TabView,
    Text,
    TextArea,
    TimePicker,
    Widget,
    build,
)
from tempestweb.html import render_document, render_to_html
from tempestweb.html.renderer import _TAG_BY_TYPE

# ---------------------------------------------------------------------------
# Unit — primitive type -> tag
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("widget", "opening"),
    [
        (Column(children=[]), "<div"),
        (Row(children=[]), "<div"),
        (Container(child=None), "<div"),
        (Stack(children=[]), "<div"),
        (Text(content="x"), "<span"),
        (Button(label="x"), "<button"),
    ],
)
def test_primitive_type_maps_to_expected_tag(widget: Widget, opening: str) -> None:
    assert render_to_html(widget).startswith(opening)


def test_input_is_a_void_input_element() -> None:
    html = render_to_html(Input(value=""))
    assert html.startswith("<input")
    assert html.endswith("/>")
    assert "</input>" not in html


def test_image_is_a_void_img_element() -> None:
    html = render_to_html(Image(src="/a.png"))
    assert html.startswith("<img")
    assert html.endswith("/>")


def test_checkbox_is_a_label_wrapper() -> None:
    html = render_to_html(Checkbox(label="ok"))
    assert html.startswith("<label")
    assert html.endswith("</label>")


def test_unknown_type_falls_back_to_div() -> None:
    # Stack maps explicitly, but a fabricated node with an unknown type falls back.
    node = build(Text(content="x"))
    node.type = "SomethingNew"  # type: ignore[misc]
    from tempestweb.html.renderer import _node_to_html

    assert _node_to_html(node).startswith("<div")


# ---------------------------------------------------------------------------
# Security — escaping + attribute-injection guard
# ---------------------------------------------------------------------------


def test_text_content_is_escaped() -> None:
    html = render_to_html(Text(content="<script>alert(1)</script>"))
    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_attr_value_with_quote_and_angle_is_escaped() -> None:
    html = render_to_html(Container(attrs={"data-x": 'a"><b'}))
    assert 'data-x="a&quot;&gt;&lt;b"' in html
    assert '"a"><b"' not in html


@pytest.mark.parametrize("bad_key", ["onload x", "a>b", "a b", "1abc", 'x"y', "a=b"])
def test_invalid_attr_key_raises(bad_key: str) -> None:
    with pytest.raises(ValueError, match="invalid HTML attribute name"):
        render_to_html(Container(attrs={bad_key: "x"}))


@pytest.mark.parametrize(
    "handler_key", ["onclick", "onerror", "ONLOAD", "onmouseover", "onfocus"]
)
def test_inline_event_handler_attr_raises(handler_key: str) -> None:
    """An ``on*`` attribute is script, which escaping cannot make safe.

    ``attrs`` is an escape hatch for markup the app owns. A widget built from
    data the app did not write (a row label, a remote field) must not be able to
    ship executable code into the page; the DOM renderer refuses the same names,
    so a tree behaves the same whichever renderer draws it.
    """
    with pytest.raises(ValueError, match="inline event-handler attribute"):
        render_to_html(Container(attrs={handler_key: "alert(1)"}))


@pytest.mark.parametrize(
    "ok_key", ["id", "data-x", "hx-get", "aria-label", "x:y", "a_b"]
)
def test_valid_attr_keys_are_accepted(ok_key: str) -> None:
    html = render_to_html(Container(attrs={ok_key: "v"}))
    assert f'{ok_key}="v"' in html


# ---------------------------------------------------------------------------
# Escape hatch — tag override + arbitrary attrs
# ---------------------------------------------------------------------------


def test_tag_override_and_attrs_render() -> None:
    html = render_to_html(
        Container(
            tag="section",
            attrs={"id": "c", "class": "card", "hx-get": "/x"},
            child=Text(content="hi"),
        )
    )
    assert html == (
        '<section id="c" class="card" hx-get="/x"><span>hi</span></section>'
    )


# ---------------------------------------------------------------------------
# A11y — semantics + focus
# ---------------------------------------------------------------------------


def test_semantics_map_to_aria() -> None:
    html = render_to_html(
        Text(content="x", semantics={"label": "L", "role": "note", "hint": "H"})
    )
    assert 'aria-label="L"' in html
    assert 'role="note"' in html
    assert 'aria-description="H"' in html


def test_focusable_true_sets_tabindex_zero() -> None:
    assert 'tabindex="0"' in render_to_html(Text(content="x", focusable=True))


def test_focusable_false_sets_tabindex_minus_one() -> None:
    assert 'tabindex="-1"' in render_to_html(Text(content="x", focusable=False))


def test_focus_order_sets_explicit_tabindex() -> None:
    assert 'tabindex="3"' in render_to_html(Text(content="x", focus_order=3))


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------


def test_input_control_attributes() -> None:
    html = render_to_html(Input(value="v", placeholder="p", max_length=5, secure=False))
    assert 'type="text"' in html
    assert 'value="v"' in html
    assert 'placeholder="p"' in html
    assert 'maxlength="5"' in html


def test_secure_input_is_password_type() -> None:
    assert 'type="password"' in render_to_html(Input(value="", secure=True))


def test_image_src_and_alt() -> None:
    html = render_to_html(Image(src="/a.png", alt="pic"))
    assert 'src="/a.png"' in html
    assert 'alt="pic"' in html


def test_checkbox_checked_and_caption_structure() -> None:
    html = render_to_html(Checkbox(label="agree", checked=True))
    assert '<input type="checkbox" checked>' in html
    assert html.endswith("agree</label>")


def test_checkbox_unchecked_has_no_checked_attribute() -> None:
    html = render_to_html(Checkbox(label="agree", checked=False))
    assert '<input type="checkbox">' in html
    assert "checked" not in html


# ---------------------------------------------------------------------------
# Known limitations — Icon / Canvas placeholders (documented, never crash)
# ---------------------------------------------------------------------------


def test_icon_renders_placeholder() -> None:
    assert render_to_html(Icon(name="home")) == '<span data-tw-type="Icon"></span>'


def test_canvas_renders_empty_placeholder() -> None:
    assert render_to_html(Canvas(width=10, height=10)) == "<canvas></canvas>"


# ---------------------------------------------------------------------------
# Integration — components + realistic nested page
# ---------------------------------------------------------------------------


class NavBar(Component):
    """A composite that expands to a semantic <nav><ul><li> tree."""

    items: list[str]

    def render(self) -> Widget:
        """Lower the nav into primitive widgets with semantic tags."""
        return Container(
            tag="nav",
            attrs={"aria-label": "primary"},
            child=Column(
                tag="ul",
                children=[
                    Container(tag="li", child=Text(tag="a", content=item))
                    for item in self.items
                ],
            ),
        )


def test_component_expands_via_build_into_semantic_html() -> None:
    html = render_to_html(NavBar(items=["Home", "Docs"]))
    # The <ul> is a Column, so it keeps its flex styling by type even under a tag
    # override — the tag changes the element, not the layout semantics.
    assert html == (
        '<nav aria-label="primary">'
        '<ul style="display: flex; flex-direction: column">'
        "<li><a>Home</a></li>"
        "<li><a>Docs</a></li>"
        "</ul>"
        "</nav>"
    )


def test_styled_nested_tree_round_trips() -> None:
    tree = Container(
        tag="main",
        style=Style(padding=Edge.all(16), background=Color(r=255, g=255, b=255, a=1.0)),
        child=Row(
            children=[
                Text(content="A"),
                Button(label="Go"),
            ]
        ),
    )
    html = render_to_html(tree)
    assert html.startswith(
        '<main style="padding: 16px 16px 16px 16px; '
        'background: rgba(255, 255, 255, 1)">'
    )
    assert '<div style="display: flex; flex-direction: row">' in html
    assert "<span>A</span>" in html
    assert "Go</button>" in html
    assert html.endswith("</div></main>")


# ---------------------------------------------------------------------------
# Integration — render_document
# ---------------------------------------------------------------------------


def test_render_document_structure_and_escaped_title() -> None:
    doc = render_document(Text(content="hi"), title="<x>", lang="en")
    assert doc.startswith("<!doctype html>")
    assert '<html lang="en">' in doc
    assert '<meta charset="utf-8">' in doc
    assert "<title>&lt;x&gt;</title>" in doc
    assert "<body><span>hi</span></body>" in doc
    assert doc.endswith("</html>")


def test_render_document_htmx_toggle() -> None:
    with_htmx = render_document(Text(content="x"), title="t", htmx=True)
    without = render_document(Text(content="x"), title="t", htmx=False)
    assert "htmx.org@2" in with_htmx
    assert "htmx" not in without


def test_render_document_css_reset_toggle() -> None:
    assert "box-sizing" in render_document(Text(content="x"), title="t")
    assert "box-sizing" not in render_document(
        Text(content="x"), title="t", css_reset=False
    )


def test_render_document_injects_head_markup() -> None:
    doc = render_document(
        Text(content="x"), title="t", head='<meta name="author" content="me">'
    )
    assert '<meta name="author" content="me">' in doc


# ---------------------------------------------------------------------------
# Unit — progress indicators
# ---------------------------------------------------------------------------


def test_determinate_bar_ships_a_sized_fill() -> None:
    """A server-rendered bar shows its fraction before any JavaScript runs."""
    html = render_to_html(ProgressBar(value=0.42))

    assert "height: 4px" in html
    assert 'data-tw-part="fill"' in html
    assert "width: 42%" in html


def test_determinate_bar_reports_its_value_to_a_screen_reader() -> None:
    """The ARIA trio is what makes the div a progressbar rather than a box."""
    html = render_to_html(ProgressBar(value=0.5))

    assert 'role="progressbar"' in html
    assert 'aria-valuemin="0"' in html
    assert 'aria-valuemax="1"' in html
    assert 'aria-valuenow="0.5"' in html


def test_indeterminate_bar_claims_no_value() -> None:
    """Work whose progress nobody measures must not report a number."""
    html = render_to_html(ProgressBar(indeterminate=True))

    assert "data-tw-indeterminate" in html
    assert "aria-valuenow" not in html
    assert "width: 40%" in html


def test_the_color_family_travels_as_the_attribute_the_sheet_keys_off() -> None:
    """The renderer resolves ``color_scheme``; the core leaves it unresolved."""
    html = render_to_html(ProgressBar(value=0.1, color_scheme="error"))

    assert 'data-tw-scheme="error"' in html


def test_spinner_is_an_empty_themed_box() -> None:
    """A spinner has no inner content — the stylesheet draws the ring."""
    html = render_to_html(Spinner(size=32.0))

    assert "width: 32px" in html
    assert "border-top-color: currentColor" in html
    assert 'role="progressbar"' in html
    assert "data-tw-part" not in html


def test_icon_button_is_a_named_button_not_an_anonymous_box() -> None:
    """An ``IconButton`` is a real ``<button>`` carrying its accessible name.

    The ``div`` fallback made the static page ship a 48x48 box with nothing in
    it: no tag semantics, no name, no text — unfocusable and unannounced, while
    a mouse click still worked in the hydrated page.
    """
    html = render_to_html(
        IconButton(icon=Icons.MENU, on_click=lambda: None, label="menu", key="burger")
    )
    assert html.startswith('<button data-tw-type="IconButton" type="button"')
    assert 'aria-label="menu"' in html
    assert html.endswith("</button>")


def test_icon_button_semantics_label_wins_over_the_icon_label() -> None:
    """An app that names the control keeps its own name."""
    html = render_to_html(
        IconButton(
            icon=Icons.X,
            on_click=lambda: None,
            label="clear",
            semantics=Semantics(label="Limpar busca"),
            key="c",
        )
    )
    assert 'aria-label="Limpar busca"' in html
    assert 'aria-label="clear"' not in html


def test_a_burger_component_lowers_to_the_named_button() -> None:
    """The core's ``Burger`` is an ``IconButton``, so it inherits the fix."""
    html = render_to_html(Burger(on_click=lambda: None, key="burger"))
    assert '<button data-tw-type="IconButton"' in html
    assert 'aria-label="menu"' in html


# ---------------------------------------------------------------------------
# Unit — the controls of #142/#143, which this renderer had never learned
# ---------------------------------------------------------------------------


def test_textarea_is_a_real_textarea_holding_its_value() -> None:
    html = render_to_html(TextArea(value="a note", rows=4, placeholder="Write…"))
    assert html.startswith("<textarea")
    assert 'rows="4"' in html
    assert 'placeholder="Write…"' in html
    assert html.endswith("a note</textarea>")


def test_masked_input_carries_its_mask() -> None:
    html = render_to_html(MaskedInput(value="", mask="999.999.999-99"))
    assert html.startswith("<input")
    assert 'data-tw-mask="999.999.999-99"' in html


def test_pin_input_asks_for_the_one_time_code() -> None:
    html = render_to_html(PinInput(value="", length=6))
    assert 'inputmode="numeric"' in html
    assert 'autocomplete="one-time-code"' in html
    assert 'maxlength="6"' in html


def test_switch_is_a_label_wrapping_a_switch_role_checkbox() -> None:
    html = render_to_html(Switch(label="Notifications", checked=True))
    assert html.startswith("<label")
    assert '<input type="checkbox" role="switch" checked>' in html
    assert html.endswith("Notifications</label>")


def test_slider_is_a_range_over_its_scale() -> None:
    html = render_to_html(Slider(value=70.0, min_value=10.0, max_value=90.0, step=5.0))
    assert 'type="range"' in html
    assert 'min="10.0"' in html
    assert 'max="90.0"' in html
    assert 'value="70.0"' in html


def test_range_slider_renders_both_thumbs() -> None:
    html = render_to_html(RangeSlider(low=20.0, high=80.0))
    assert 'data-tw-part="low"' in html
    assert 'data-tw-part="high"' in html
    assert html.count('type="range"') == 2


def test_dropdown_is_a_select_with_its_options_and_placeholder() -> None:
    html = render_to_html(Dropdown(options=["Light", "Dark"], value="Dark"))
    assert html.startswith("<select")
    assert '<option value="Light">Light</option>' in html
    assert 'disabled data-tw-part="placeholder"' in html


def test_autocomplete_ships_the_datalist_its_input_points_at() -> None:
    html = render_to_html(Autocomplete(key="q", options=["ana", "bia"], value="an"))
    assert 'list="tw-list-q"' in html
    assert '<datalist id="tw-list-q">' in html
    assert '<option value="bia">bia</option>' in html


def test_date_and_time_pickers_use_the_native_controls() -> None:
    date_html = render_to_html(DatePicker(value="2026-08-23", label="Departure"))
    time_html = render_to_html(TimePicker(value="10:30", label="Boarding"))
    assert '<input type="date" value="2026-08-23">Departure</label>' in date_html
    assert '<input type="time" value="10:30">Boarding</label>' in time_html


def test_file_picker_reflects_the_value_it_cannot_assign() -> None:
    html = render_to_html(FilePicker(label="Attach", value="cv.pdf"))
    assert 'data-tw-value="cv.pdf"' in html
    assert '<input type="file">Attach</label>' in html


def test_tab_bar_renders_a_tablist_with_the_active_tab_selected() -> None:
    html = render_to_html(TabBar(tabs=["Posts", "About"], active=1))
    assert 'role="tablist"' in html
    assert html.count('role="tab"') == 2
    assert 'data-tw-value="1" aria-selected="true"' in html
    assert 'data-tw-value="0" aria-selected="false"' in html


def test_tab_view_is_a_panel_named_after_its_active_tab() -> None:
    html = render_to_html(
        TabView(tabs=["Posts", "About"], active=1, child=Text(content="x"))
    )
    assert 'role="tabpanel"' in html
    assert 'aria-label="About"' in html


def test_route_drawer_says_whether_it_is_open() -> None:
    closed = render_to_html(
        RouteDrawer(child=Text(content="main"), drawer=Text(content="side"), open=False)
    )
    opened = render_to_html(
        RouteDrawer(child=Text(content="main"), drawer=Text(content="side"), open=True)
    )
    assert 'aria-expanded="false"' in closed
    assert "data-tw-open" not in closed
    assert 'aria-expanded="true"' in opened
    assert 'data-tw-open=""' in opened


def test_ssr_tag_table_matches_the_dom_renderer() -> None:
    """Both renderers agree on every tag that is not the div fallback.

    Two hand-kept tables of the same mapping is the drift this issue is about:
    this renderer was five widgets behind the client (#142's fields never
    arrived), so the same tree was a typable field in the browser and a dead box
    in a static page. Only non-``div`` entries are compared, since ``div`` is what
    an absent entry falls back to anyway.
    """
    dom = (Path(__file__).resolve().parents[2] / "client" / "dom.js").read_text(
        encoding="utf-8"
    )
    start = dom.index("const TAG_BY_TYPE = Object.freeze({")
    table = dom[start : dom.index("});", start)]
    client_tags = {
        name: tag
        for name, tag in re.findall(r'^\s*(\w+): "(\w+)"', table, re.M)
        if tag != "div"
    }
    drift = {
        name: (tag, _TAG_BY_TYPE.get(name, "div"))
        for name, tag in client_tags.items()
        if _TAG_BY_TYPE.get(name, "div") != tag
    }
    assert not drift, (
        "the SSR renderer disagrees with client/dom.js on "
        f"{sorted(drift)} (client, ssr): {drift}"
    )
