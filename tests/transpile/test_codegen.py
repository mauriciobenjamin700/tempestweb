"""Unit tests for the Mode C codegen mappings (Python construct → JS)."""

from __future__ import annotations

import pytest

from tempestweb.transpile import TranspileError, transpile_source

BARE = ""  # empty banner keeps assertions focused on the body


def gen(source: str) -> str:
    """Transpile `source` with an empty banner, returning the JS body."""
    return transpile_source(source, banner=BARE).strip()


def test_dataclass_becomes_state_subclass() -> None:
    """A defaulted dataclass field becomes a constructor assignment."""
    js = gen("@dataclass\nclass S:\n    value: int = 0\n")
    assert "export class S extends State {" in js
    assert "super();" in js
    assert "this.value = 0;" in js
    assert 'import { State } from "./runtime.js";' in js


def test_make_state_and_new_class() -> None:
    """`make_state` renames to `makeState`; a class call gets `new`."""
    js = gen("class S:\n    x: int = 1\n\ndef make_state() -> S:\n    return S()\n")
    assert "export function makeState() {" in js
    assert "return new S();" in js


def test_set_state_lambda_setattr_to_assignment() -> None:
    """`set_state(lambda s: setattr(s, 'v', s.v + 1))` → block arrow assignment."""
    js = gen(
        "def view(app):\n"
        "    def inc() -> None:\n"
        '        app.set_state(lambda s: setattr(s, "value", s.value + 1))\n'
    )
    assert "const inc = () => {" in js
    assert "app.setState((s) => {" in js
    assert "s.value = s.value + 1;" in js


def test_fstring_becomes_template_literal() -> None:
    """An f-string becomes a JS template literal."""
    js = gen('def view(app):\n    return Text(content=f"Count: {app.state.value}")\n')
    assert "Text({ content: `Count: ${app.state.value}` })" in js


def test_kwargs_become_object_arg_and_on_click_renames() -> None:
    """Keyword-only widget calls become an object arg; `on_click` → `onClick`."""
    js = gen('def view(app):\n    return Button(label="+", on_click=inc, key="inc")\n')
    assert 'Button({ label: "+", onClick: inc, key: "inc" })' in js


def test_unsupported_import_raises_with_location() -> None:
    """An import outside tempest_core is a compile error with file:line."""
    with pytest.raises(TranspileError) as exc:
        transpile_source("import os\n", filename="app.py")
    assert "app.py:1:" in str(exc.value)


def test_unsupported_operator_raises() -> None:
    """An operator outside the subset is a compile error."""
    with pytest.raises(TranspileError):
        gen("def f(a, b):\n    return a * b\n")
