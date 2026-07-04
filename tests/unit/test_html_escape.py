"""Unit tests for the HTML escaping helpers (``tempestweb.html.escape``)."""

from __future__ import annotations

from tempestweb.html import escape_attr, escape_text


def test_escape_text_escapes_angle_brackets_and_amp() -> None:
    assert (
        escape_text("<script>a & b</script>")
        == "&lt;script&gt;a &amp; b&lt;/script&gt;"
    )


def test_escape_text_leaves_quotes_untouched() -> None:
    # Quotes are safe inside a text node, so escape_text must not touch them.
    assert escape_text("a \"b\" 'c'") == "a \"b\" 'c'"


def test_escape_text_none_is_empty_string() -> None:
    assert escape_text(None) == ""


def test_escape_text_coerces_non_strings() -> None:
    assert escape_text(42) == "42"


def test_escape_attr_escapes_quotes_and_angle_brackets() -> None:
    assert escape_attr('a"b<c>&') == "a&quot;b&lt;c&gt;&amp;"


def test_escape_attr_none_is_empty_string() -> None:
    assert escape_attr(None) == ""


def test_escape_attr_coerces_non_strings() -> None:
    assert escape_attr(7) == "7"
