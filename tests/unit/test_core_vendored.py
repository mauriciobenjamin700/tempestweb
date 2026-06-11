"""Foundation test: the vendored core imports and the engine works headless."""

from __future__ import annotations

from tempestweb._core import Column, Style, Text, build, diff


def test_vendored_core_build_and_diff() -> None:
    """build + diff over a small tree produces the expected Update patch."""
    a = build(Column(children=[Text(content="x", key="t")]))
    b = build(Column(children=[Text(content="y", key="t")]))
    patches = diff(a, b)
    assert len(patches) == 1
    dumped = patches[0].model_dump(mode="json")
    assert dumped["set_props"] == {"content": "y"}


def test_style_dump_shape() -> None:
    """Style serializes Color as rgba dict — the client contract."""
    from tempestweb._core.style import Color

    s = Style(gap=8.0, color=Color.from_hex("#111111"))
    d = s.model_dump(mode="json")
    assert d["gap"] == 8.0
    assert d["color"] == {"r": 17, "g": 17, "b": 17, "a": 1.0}
