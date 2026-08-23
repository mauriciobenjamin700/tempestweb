"""Unit + integration + security tests for the static HTML renderer.

Covers ``tempestweb.html.render_to_html`` / ``render_document``: the Node -> HTML
mapping (tags, void elements, controls, a11y, the ``tag``/``attrs`` escape
hatch), HTML-injection safety, component expansion, and the document wrapper.
"""

from __future__ import annotations

import pytest

from tempest_core import (
    Burger,
    Button,
    Canvas,
    Checkbox,
    Color,
    Column,
    Component,
    Container,
    Edge,
    Icon,
    IconButton,
    Icons,
    Image,
    Input,
    ProgressBar,
    Row,
    Semantics,
    Spinner,
    Stack,
    Style,
    Text,
    Widget,
    build,
)
from tempestweb.html import render_document, render_to_html

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
