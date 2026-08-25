"""A server-rendered ``ScrollView`` scrolls without a stylesheet.

The DOM client takes the overflow from the base sheet; a static page ships no
stylesheet at all, only a reset, so the same widget would be the plain ``div``
this exists to fix — the page scrolling instead of the box. The declarations are
inline here for the same reason an indicator's track is.
"""

from __future__ import annotations

from tempest_core import ScrollView, Style, Text
from tempestweb.html import render_to_html


def test_a_scroll_view_scrolls_on_its_vertical_axis() -> None:
    """The default axis is vertical, and the cross axis is clipped."""
    html = render_to_html(ScrollView(key="body", children=[Text(content="x")]))

    assert "overflow-y: auto" in html
    assert "overflow-x: hidden" in html


def test_the_minimum_that_lets_it_shrink_is_there() -> None:
    """A flex item's automatic minimum is its content.

    Without this the scroller grows inside a bounded column instead of
    scrolling, which looks like the fix working right up until the content is
    taller than the frame.
    """
    html = render_to_html(
        ScrollView(key="body", style=Style(grow=1.0), children=[Text(content="x")]),
    )

    assert "min-height: 0" in html


def test_a_horizontal_scroll_view_flips_both_axes() -> None:
    """A strip scrolls sideways and clips vertically, never both ways."""
    html = render_to_html(
        ScrollView(key="strip", horizontal=True, children=[Text(content="x")]),
    )

    assert "overflow-x: auto" in html
    assert "overflow-y: hidden" in html
    assert "min-width: 0" in html


def test_the_app_style_still_follows_the_scroll_declarations() -> None:
    """The app's own style is written last, so it wins on a conflict."""
    html = render_to_html(
        ScrollView(key="body", style=Style(grow=1.0), children=[Text(content="x")]),
    )
    style = html.split('style="', 1)[1].split('"', 1)[0]

    assert style.index("overflow-y") < style.index("flex-grow")
