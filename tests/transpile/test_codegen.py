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
    assert "s.value = (s.value + 1);" in js


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


def test_arithmetic_operators() -> None:
    """`*`, `/`, `%` transpile (parenthesized) alongside `+`/`-`."""
    js = gen("def f(a, b):\n    return a * b % 2\n")
    assert "((a * b) % 2)" in js


def test_comparison_and_boolean_and_unary() -> None:
    """Comparisons, boolean and unary operators map to JS forms."""
    js = gen("def f(a, b):\n    return a >= b and not a\n")
    assert "(a >= b && !a)" in js


def test_ternary_conditional_expression() -> None:
    """`a if c else b` becomes a JS conditional expression."""
    js = gen('def f(x):\n    return "hi" if x else "bye"\n')
    assert '(x ? "hi" : "bye")' in js


def test_list_comprehension_becomes_map() -> None:
    """A list comprehension becomes a chained `.filter().map()`."""
    js = gen("def f(xs):\n    return [Text(content=x) for x in xs if x]\n")
    assert "xs.filter((x) => x).map((x) => Text({ content: x }))" in js


def test_membership_uses_includes() -> None:
    """`x in xs` becomes `xs.includes(x)`."""
    js = gen("def f(x, xs):\n    return x in xs\n")
    assert "xs.includes(x)" in js


def test_if_elif_else_statement() -> None:
    """`if`/`elif`/`else` chains map to JS `if`/`else if`/`else`."""
    js = gen(
        "def f(x):\n"
        "    if x > 0:\n        y = 1\n"
        "    elif x < 0:\n        y = 2\n"
        "    else:\n        y = 3\n"
    )
    assert "if (x > 0) {" in js
    assert "} else if (x < 0) {" in js
    assert "} else {" in js


def test_for_loop_and_augmented_assignment() -> None:
    """`for x in it:` becomes `for (const x of it)`, `+=` stays `+=`."""
    js = gen(
        "def f(items):\n    total = 0\n    for item in items:\n        total += item\n"
    )
    assert "for (const item of items) {" in js
    assert "total += item;" in js
    assert "const total = 0;" in js


def test_subscript_index() -> None:
    """`xs[i]` transpiles to `xs[i]`."""
    js = gen("def f(xs, i):\n    return xs[i]\n")
    assert "return xs[i];" in js


def test_dataclass_method_becomes_js_method() -> None:
    """A dataclass method becomes a JS class method (self -> this, dropped param)."""
    js = gen(
        "@dataclass\n"
        "class Counter:\n"
        "    value: int = 0\n"
        "    def increment(self) -> None:\n"
        "        self.value += 1\n"
    )
    assert "increment() {" in js
    assert "this.value += 1;" in js
    assert "(self)" not in js  # the receiver is dropped


def test_expression_lambda_calls_state_method() -> None:
    """A non-setattr lambda body becomes a concise expression arrow."""
    js = gen(
        "def view(app):\n"
        "    def inc() -> None:\n"
        "        app.set_state(lambda s: s.increment())\n"
    )
    assert "app.setState((s) => s.increment());" in js


def test_async_def_and_await() -> None:
    """`async def` → `async` arrow; `await` → `await`."""
    js = gen(
        "def view(app):\n    async def go() -> None:\n        x = await fetch_it()\n"
    )
    assert "const go = async () => {" in js
    assert "const x = await fetch_it();" in js


def test_native_import_maps_to_facade() -> None:
    """`from tempestweb import native` imports the Mode C native facade."""
    js = gen(
        "from tempestweb import native\n\n"
        "def view(app):\n"
        "    async def go() -> None:\n"
        '        await native.storage.put("k", "v")\n'
    )
    assert 'import { native } from "./native.js";' in js
    assert 'await native.storage.put("k", "v");' in js


def test_mixed_positional_and_keyword_call() -> None:
    """Positional + keyword args → positional args then a trailing options object."""
    js = gen(
        "from tempestweb import native\n\n"
        "def view(app):\n"
        "    async def go() -> None:\n"
        '        await native.http.request("GET", "/x", json=None, headers={})\n'
    )
    assert 'native.http.request("GET", "/x", { json: null, headers: {} })' in js


def test_dict_literal_becomes_object() -> None:
    """A dict literal with string keys becomes a JS object."""
    js = gen('def view(app):\n    return f({"a": 1, "b": app.state.x})\n')
    assert 'f({ "a": 1, "b": app.state.x })' in js


def test_validators_import_maps_to_validators_module() -> None:
    """`from tempest_core.validators import ...` routes to ./validators.js."""
    js = gen(
        "from tempest_core.validators import validate_email\n\n"
        "def view(app):\n"
        "    return validate_email(app.state.x)\n"
    )
    assert 'import { validate_email } from "./validators.js";' in js
    assert "return validate_email(app.state.x);" in js


def test_validator_fixture_matches_core() -> None:
    """The validator-parity fixture byte-matches a fresh core render."""
    from tests.conformance import _transpile_validators as gen_v

    on_disk = gen_v.VALIDATORS_FIXTURE.read_text(encoding="utf-8")
    assert on_disk == gen_v.render_fixture_text()


def test_navigation_imports_map_to_nav_module() -> None:
    """`Route`/`NavStack` route to ./nav.js; nav calls transpile."""
    js = gen(
        "from tempest_core import App, Route, Widget\n\n"
        "def view(app):\n"
        '    app.push(Route(name="/about"))\n'
        "    return app.nav.top.name\n"
    )
    assert 'import { Route } from "./nav.js";' in js
    assert 'app.push(new Route({ name: "/about" }));' in js
    assert "return app.nav.top.name;" in js


def test_builtins_map_to_js_idioms() -> None:
    """`len`/`str`/`abs` map to JS idioms."""
    assert "x.length" in gen("def f(x):\n    return len(x)\n")
    assert "String(x)" in gen("def f(x):\n    return str(x)\n")
    assert "Math.abs(x)" in gen("def f(x):\n    return abs(x)\n")


def test_route_fixture_matches_core() -> None:
    """The routes_from_path parity fixture byte-matches a fresh core render."""
    from tests.conformance import _transpile_routes as gen_r

    on_disk = gen_r.ROUTES_FIXTURE.read_text(encoding="utf-8")
    assert on_disk == gen_r.render_fixture_text()


def test_native_import_rejects_non_native_symbol() -> None:
    """`from tempestweb import` only allows `native`."""
    with pytest.raises(TranspileError, match="only `native`"):
        transpile_source("from tempestweb import server\n", filename="app.py")


def test_unsupported_construct_raises() -> None:
    """A construct still outside the subset is a compile error."""
    with pytest.raises(TranspileError):
        gen("def f(a):\n    return {k: v for k, v in a}\n")  # dict comprehension
