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
    assert "constructor(opts = {}) {" in js
    assert "super(opts);" in js
    # The field takes an override from opts, falling back to its default.
    assert "this.value = opts.value !== undefined ? opts.value : 0;" in js
    assert 'import { State } from "./runtime.js";' in js


def test_dataclass_constructs_with_field_overrides() -> None:
    """`Foo(x=5)` -> `new Foo({ x: 5 })`, and the ctor honors the override."""
    js = gen(
        "@dataclass\nclass Foo:\n    x: int = 0\n\n"
        "def make_state() -> Foo:\n    return Foo(x=5)\n"
    )
    assert "return new Foo({ x: 5 });" in js
    assert "this.x = opts.x !== undefined ? opts.x : 0;" in js


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
    assert "[...xs].filter((x) => x).map((x) => Text({ content: x }))" in js


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
    # `total` is augmented, so it hoists to a `let` — a `const` would throw on
    # the first `+=` (assignment to a constant).
    assert "let total;" in js
    assert "total = 0;" in js
    assert "const total" not in js


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


def test_i18n_imports_and_module_const() -> None:
    """`t`/`Locale` route to ./i18n.js; a module-level table becomes a const."""
    js = gen(
        "from tempest_core import Locale, t\n\n"
        'MESSAGES = {"pt": {"hi": "Olá"}}\n\n'
        "def view(app):\n"
        '    loc = Locale(language="pt")\n'
        '    return t("hi", locale=loc, translations=MESSAGES)\n'
    )
    assert 'import { Locale, t } from "./i18n.js";' in js
    assert 'const MESSAGES = { "pt": { "hi":' in js
    assert 'const loc = new Locale({ language: "pt" });' in js
    assert 't("hi", { locale: loc, translations: MESSAGES })' in js


def test_i18n_fixture_matches_core() -> None:
    """The i18n parity fixture byte-matches a fresh core render."""
    from tests.conformance import _transpile_i18n as gen_i

    on_disk = gen_i.I18N_FIXTURE.read_text(encoding="utf-8")
    assert on_disk == gen_i.render_fixture_text()


def test_theme_imports_map_to_theme_module() -> None:
    """`Theme`/`ThemeMode`/`MediaQueryData` route to ./theme.js; class calls new."""
    js = gen(
        "from tempest_core import Theme, ThemeMode\n\n"
        "def view(app):\n"
        "    t = Theme(mode=ThemeMode.DARK)\n"
        "    return app.theme.is_dark("
        "platform_dark_mode=app.media.platform_dark_mode)\n"
    )
    assert 'from "./theme.js"' in js
    assert "new Theme({ mode: ThemeMode.DARK })" in js
    assert "app.theme.is_dark({ platform_dark_mode:" in js


def test_motion_imports_map_to_motion_module() -> None:
    """`Transition`/`Curve` route to ./motion.js (no `new` — a Style value)."""
    js = gen(
        "from tempest_core.style import Curve, Transition\n\n"
        "def view(app):\n"
        "    return Transition(duration_ms=300, curve=Curve.EASE)\n"
    )
    assert 'from "./motion.js"' in js
    assert "Transition({ duration_ms: 300, curve: Curve.EASE })" in js


def test_animation_imports_map_to_animation_module() -> None:
    """`AnimationController`/`Tween` route to ./animation.js; class calls new."""
    js = gen(
        "from tempest_core import AnimationController, Tween\n"
        "from tempest_core.style import Curve\n\n"
        "def view(app):\n"
        "    c = AnimationController(0.4, curve=Curve.EASE_OUT)\n"
        "    return Tween(begin=0.0, end=1.0).at(c.value)\n"
    )
    assert 'from "./animation.js"' in js
    assert "new AnimationController(0.4, { curve: Curve.EASE_OUT })" in js
    assert "new Tween({ begin: 0.0, end: 1.0 }).at(c.value)" in js


def test_route_fixture_matches_core() -> None:
    """The routes_from_path parity fixture byte-matches a fresh core render."""
    from tests.conformance import _transpile_routes as gen_r

    on_disk = gen_r.ROUTES_FIXTURE.read_text(encoding="utf-8")
    assert on_disk == gen_r.render_fixture_text()


def test_native_import_rejects_non_native_symbol() -> None:
    """`from tempestweb import` only allows `native`."""
    with pytest.raises(TranspileError, match="only `native`"):
        transpile_source("from tempestweb import server\n", filename="app.py")


def test_set_literal() -> None:
    """A set literal becomes `new Set([...])`."""
    assert "new Set([" in gen("def f():\n    return {1, 2, 3}\n")


def test_tuple_literal_becomes_array() -> None:
    """A tuple literal becomes a JS array (no tuple type in JS)."""
    js = gen("def f():\n    return (1, 2)\n")
    assert "return [" in js and "1," in js and "2," in js


def test_dict_comprehension() -> None:
    """A dict comprehension becomes `Object.fromEntries(...map(...))`."""
    js = gen("def f(it):\n    return {k: k * 2 for k in it if k}\n")
    assert "Object.fromEntries(" in js
    assert ".filter((k) => k)" in js
    assert ".map((k) => [k, (k * 2)])" in js


def test_fstring_fixed_point_spec() -> None:
    """`f'{x:.2f}'` maps to `(x).toFixed(2)`."""
    js = gen("def f(x):\n    return f'{x:.2f}'\n")
    assert "${(x).toFixed(2)}" in js


def test_fstring_conversions() -> None:
    """`!s`/`!r` map to `String(...)`/`JSON.stringify(...)`."""
    assert "${String(x)}" in gen("def f(x):\n    return f'{x!s}'\n")
    assert "${JSON.stringify(x)}" in gen("def f(x):\n    return f'{x!r}'\n")


def test_fstring_grouped_and_percent_specs() -> None:
    """Thousands `,`, grouped `,.Nf` and percent `.N%` specs map to JS."""
    assert 'toLocaleString("en-US")' in gen("def f(x):\n    return f'{x:,}'\n")
    grouped = gen("def f(x):\n    return f'{x:,.2f}'\n")
    assert "minimumFractionDigits: 2" in grouped
    assert '((x) * 100).toFixed(1) + "%"' in gen("def f(x):\n    return f'{x:.1%}'\n")


def test_while_loop_with_counter() -> None:
    """`while` transpiles; a re-bound / augmented counter hoists to `let`."""
    js = gen("def f(n):\n    i = 0\n    while i < n:\n        i += 1\n    return i\n")
    assert "let i;" in js
    assert "i = 0;" in js  # plain (hoisted), not `const i = 0`
    assert "while (i < n) {" in js
    assert "i += 1;" in js


def test_break_and_continue() -> None:
    """`break` / `continue` map straight through."""
    js = gen(
        "def f(xs):\n    for x in xs:\n        if x:\n            continue\n"
        "        break\n"
    )
    assert "continue;" in js
    assert "break;" in js


def test_try_except_finally() -> None:
    """`try`/`except`/`finally` maps to JS try/catch/finally.

    A typed `except` matches by class name and re-raises otherwise (Python's
    selectivity, preserved for A/B/C parity); its bound name aliases the error.
    """
    js = gen(
        "def f():\n    try:\n        go()\n    except ValueError as e:\n"
        "        log(e)\n    finally:\n        done()\n"
    )
    assert "try {" in js
    assert "} catch (_err) {" in js
    assert 'if (_err.name === "ValueError") {' in js
    assert "const e = _err;" in js
    assert "throw _err;" in js
    assert "} finally {" in js


def test_single_broad_except_catches_all() -> None:
    """A lone `except Exception` catches everything (no type check)."""
    js = gen(
        "def f():\n    try:\n        go()\n    except Exception as e:\n        h(e)\n"
    )
    assert "} catch (e) {" in js
    assert "_err" not in js


def test_try_bare_except_binds_placeholder() -> None:
    """A bare `except:` binds a `_err` placeholder (JS needs a binding)."""
    js = gen("def f():\n    try:\n        go()\n    except Exception:\n        pass\n")
    assert "} catch (_err) {" in js


def test_string_and_list_method_renames() -> None:
    """Common string/list methods map to their JS equivalents."""
    assert "s.toUpperCase()" in gen("def f(s):\n    return s.upper()\n")
    assert "s.toLowerCase()" in gen("def f(s):\n    return s.lower()\n")
    assert "s.trim()" in gen("def f(s):\n    return s.strip()\n")
    assert 's.startsWith("x")' in gen("def f(s):\n    return s.startswith('x')\n")
    assert "xs.push(1)" in gen("def f(xs):\n    xs.append(1)\n")


def test_dict_view_methods() -> None:
    """`.items()`/`.keys()`/`.values()` become `Object.entries/keys/values`."""
    entries = gen("def f(d):\n    return [k for k, v in d.items()]\n")
    assert "Object.entries(d)" in entries
    assert "Object.keys(d)" in gen("def f(d):\n    return d.keys()\n")
    assert "Object.values(d)" in gen("def f(d):\n    return d.values()\n")


def test_join_swaps_receiver_and_argument() -> None:
    """`sep.join(it)` becomes `it.join(sep)`."""
    assert 'xs.join(", ")' in gen("def f(xs):\n    return ', '.join(xs)\n")


def test_runtime_methods_pass_through_unmapped() -> None:
    """Runtime/facade methods are emitted unchanged (no false mapping)."""
    # `app.replace` is the nav method, NOT string.replace.
    assert "app.replace(" in gen("def view(app):\n    app.replace(r)\n")
    # `native.storage.get` is the storage capability, NOT dict.get — and the
    # facade is recognized by what the module imported, not by the bare name.
    js = gen(
        "from tempestweb import native\n\n"
        "def f():\n    return native.storage.get('k')\n"
    )
    assert "native.storage.get(" in js


def test_tuple_unpacking_assignment() -> None:
    """`a, b = pair` becomes array destructuring."""
    assert "const [a, b] = p;" in gen("def f(p):\n    a, b = p\n    return a\n")


def test_for_tuple_target() -> None:
    """`for k, v in items:` destructures each element."""
    js = gen("def f(items):\n    for k, v in items:\n        use(k, v)\n")
    assert "for (const [k, v] of items) {" in js


def test_enumerate_and_zip() -> None:
    """`enumerate`/`zip` pair elements for tuple-target iteration."""
    en = gen("def f(xs):\n    return [i for i, x in enumerate(xs)]\n")
    assert "map((_v, _i) => [_i, _v])" in en
    assert "map(([i, x]) =>" in en
    zp = gen("def f(a, b):\n    return [x for x, y in zip(a, b)]\n")
    assert "map((_v, _i) => [_v, b[_i]])" in zp


def test_power_and_floor_division() -> None:
    """`**` maps to JS `**`; `//` to `Math.floor(a / b)`."""
    assert "(n ** 2)" in gen("def f(n):\n    return n ** 2\n")
    assert "Math.floor(n / 2)" in gen("def f(n):\n    return n // 2\n")


def test_slices() -> None:
    """`x[a:b]`/`x[a:]` map to `.slice(...)`; a step is rejected."""
    assert "x.slice(1, 3)" in gen("def f(x):\n    return x[1:3]\n")
    assert "x.slice(2)" in gen("def f(x):\n    return x[2:]\n")
    assert "x.slice(0, 3)" in gen("def f(x):\n    return x[:3]\n")


def test_assert_throws_assertion_error() -> None:
    """`assert cond, msg` throws an AssertionError when the condition is false."""
    js = gen("def f(x):\n    assert x > 0, 'must be positive'\n")
    assert "if (!(x > 0)) {" in js
    assert '{ name: "AssertionError" }' in js


def test_raise_throws_named_error() -> None:
    """`raise Exc(msg)` throws an Error with .message and .name = the class."""
    js = gen("def f(x):\n    raise ValueError('bad')\n")
    assert 'throw Object.assign(new Error("bad"), { name: "ValueError" });' in js


def test_raise_class_without_args() -> None:
    """`raise Exc` (no call) throws a named Error with an empty message."""
    js = gen("def f():\n    raise StopError\n")
    assert 'throw Object.assign(new Error(""), { name: "StopError" });' in js


def test_bare_raise_reraises_caught_error() -> None:
    """A bare `raise` inside `except` re-throws the caught error."""
    js = gen(
        "def f():\n    try:\n        go()\n    except Exception:\n        cleanup()\n"
        "        raise\n"
    )
    # The lone catch-all binds `_err`; bare raise re-throws it.
    assert "throw _err;" in js


def test_raise_then_except_matches_by_name() -> None:
    """A raised exception's name is what a later `except` dispatches on."""
    js = gen(
        "def f():\n    try:\n        raise KeyError('k')\n"
        "    except KeyError:\n        h()\n    except Exception:\n        other()\n"
    )
    assert '{ name: "KeyError" }' in js
    assert 'if (_err.name === "KeyError") {' in js


def test_multiple_except_dispatches_by_name() -> None:
    """Several `except` clauses dispatch by exception class name, else re-raise."""
    js = gen(
        "def f():\n    try:\n        go()\n"
        "    except ValueError as e:\n        h1(e)\n"
        "    except (KeyError, IndexError):\n        h2()\n"
    )
    assert 'if (_err.name === "ValueError") {' in js
    assert "const e = _err;" in js
    assert '["KeyError", "IndexError"].includes(_err.name)' in js
    assert "throw _err;" in js  # no catch-all -> re-raise


def test_multiple_except_with_broad_fallback() -> None:
    """A trailing `except Exception` becomes the `else` (no re-raise)."""
    js = gen(
        "def f():\n    try:\n        go()\n"
        "    except ValueError:\n        h1()\n"
        "    except Exception:\n        h2()\n"
    )
    assert "} else {" in js
    assert "throw _err;" not in js


def test_dataclass_inheritance() -> None:
    """A dataclass inheriting another extends it; super() chains the base ctor."""
    js = gen(
        "@dataclass\nclass Base:\n    a: int = 1\n\n"
        "@dataclass\nclass Derived(Base):\n    b: int = 2\n"
    )
    assert "export class Base extends State {" in js
    assert "export class Derived extends Base {" in js
    assert js.count("super(opts);") == 2
    assert "this.b = opts.b !== undefined ? opts.b : 2;" in js


def test_with_uses_enter_exit_protocol() -> None:
    """`with cm as x:` calls __enter__/__exit__ and hoists the leaked target."""
    js = gen("def view(app):\n    with cm() as h:\n        use(h)\n    return h\n")
    assert "let h;" in js  # leaks to function scope like Python
    assert "const _cm = cm();" in js
    assert "h = _cm.__enter__();" in js
    assert "} finally {" in js
    assert "_cm.__exit__(null, null, null);" in js


def test_range_materializes_to_array() -> None:
    """`range(...)` becomes an `Array.from(...)` (JS has no lazy range)."""
    assert "Array.from({ length: 3 }, (_, i) => i)" in gen(
        "def f():\n    return range(3)\n"
    )
    two = gen("def f():\n    return range(1, 5)\n")
    assert "Array.from({ length: Math.max(0, Math.ceil((5 - 1) / 1)) }" in two


def test_numeric_builtins() -> None:
    """`round`/`min`/`max`/`sum` map to their JS idioms."""
    assert "Math.round(x)" in gen("def f(x):\n    return round(x)\n")
    assert "Number((x).toFixed(2))" in gen("def f(x):\n    return round(x, 2)\n")
    assert "Math.min(1, x)" in gen("def f(x):\n    return min(1, x)\n")
    assert "Math.max(...it)" in gen("def f(it):\n    return max(it)\n")
    assert "reduce((a, b) => a + b, 0)" in gen("def f(it):\n    return sum(it)\n")


# Every out-of-subset construct must fail loud with a TranspileError (file:line),
# never silently mis-transpile or crash — the graduation-quality guarantee.
_UNSUPPORTED: dict[str, str] = {
    "while_else": "def f(x):\n    while x:\n        pass\n    else:\n        pass\n",
    "try_else": (
        "def f():\n    try:\n        go()\n    except Exception:\n        pass\n"
        "    else:\n        ok()\n"
    ),
    "with_multiple_items": "def f():\n    with a() as x, b() as y:\n        pass\n",
    "with_non_name_target": "def f():\n    with a() as obj.attr:\n        pass\n",
    "dataclass_multiple_bases": (
        "@dataclass\nclass A:\n    x: int = 0\n\n"
        "@dataclass\nclass B:\n    y: int = 0\n\n"
        "@dataclass\nclass C(A, B):\n    z: int = 0\n"
    ),
    "dataclass_unknown_base": "@dataclass\nclass C(Unknown):\n    z: int = 0\n",
    "global": "def f():\n    global g\n",
    "yield": "def f():\n    yield 1\n",
    "walrus": "def f(x):\n    return (y := x)\n",
    "raise_from": "def f():\n    raise ValueError('x') from KeyError()\n",
    "bare_raise_outside_except": "def f():\n    raise\n",
    "slice_step": "def f(x):\n    return x[::2]\n",
    "starred_unpack": "def f(p):\n    a, *rest = p\n    return a\n",
    "del": "def f(x):\n    del x\n",
    "starargs": "def f(*args):\n    return args\n",
    "kwargs": "def f(**kw):\n    return kw\n",
    "fn_decorator": "@deco\ndef f():\n    pass\n",
    "class_decorator": "@deco\nclass C:\n    x: int = 0\n",
    "fstring_align_spec": "def f(x):\n    return f'{x:>5}'\n",
    "fstring_sign_spec": "def f(x):\n    return f'{x:+.2f}'\n",
    "fstring_hex_spec": "def f(x):\n    return f'{x:x}'\n",
    "fstring_precision_no_type": "def f(x):\n    return f'{x:.3}'\n",
    "fstring_dynamic_spec": "def f(x, n):\n    return f'{x:.{n}f}'\n",
    "fstring_ascii_conv": "def f(x):\n    return f'{x!a}'\n",
    "multiloop_comp": "def f(a, b):\n    return [x for x in a for y in b]\n",
    "plain_import": "import os\n",
}


@pytest.mark.parametrize("name", sorted(_UNSUPPORTED))
def test_out_of_subset_fails_loud(name: str) -> None:
    """Each unsupported construct raises a located TranspileError (no crash)."""
    with pytest.raises(TranspileError) as exc:
        transpile_source(_UNSUPPORTED[name], filename="app.py")
    assert "app.py:" in str(exc.value), name


def test_annotated_local_keeps_its_value() -> None:
    """A typed local emits its assignment (regression: it emitted nothing).

    ``ast.AnnAssign`` was grouped with ``pass``, so a local written the way this
    repo's style rules ask for — annotated — vanished from the generated module.
    Nothing failed at transpile time; the browser raised
    ``ReferenceError: <name> is not defined`` when the view ran.
    """
    js = gen("def view(app):\n    total: int = 1 + 2\n    return total\n")
    assert "const total = (1 + 2);" in js


def test_annotated_local_holding_a_conditional() -> None:
    """The shape that exposed the bug: a typed local built by a ternary."""
    js = gen(
        "def view(app):\n"
        "    wide: bool = app.media.width >= 700\n"
        "    layout: str = 'row' if wide else 'column'\n"
        "    return layout\n"
    )
    assert "const wide = app.media.width >= 700;" in js
    assert 'const layout = (wide ? "row" : "column");' in js


def test_annotated_attribute_assignment() -> None:
    """An annotated attribute target assigns, like its unannotated twin."""
    js = gen("def view(app):\n    app.state.count: int = 3\n    return app\n")
    assert "app.state.count = 3;" in js


def test_bare_annotation_emits_nothing() -> None:
    """A declaration with no value is a type statement; there is nothing to run."""
    js = gen("def view(app):\n    total: int\n    return 0\n")
    assert "total" not in js


def test_dataclass_named_state_aliases_the_runtime_base() -> None:
    """A state class named ``State`` transpiles to a module that parses.

    Regression: the base was hard-coded to the bare name ``State``, so a module
    declaring its own ``State`` emitted both ``import { State }`` and
    ``export class State extends State`` — two declarations of one identifier,
    which is a ``SyntaxError`` that takes the whole module down. Nothing failed
    at transpile time; the browser logged ``Identifier 'State' has already been
    declared`` and the app never mounted. ``tempestweb new`` scaffolds its state
    dataclass under exactly this name, so Mode C was broken out of the box.
    """
    js = gen("@dataclass\nclass State:\n    value: int = 0\n")
    assert 'import { State as State$ } from "./runtime.js";' in js
    assert "export class State extends State$ {" in js
    assert 'import { State } from "./runtime.js";' not in js


def test_state_alias_is_unreachable_from_python() -> None:
    """The alias holds a ``$``, which no Python identifier can contain.

    That is what makes the alias collision-proof rather than merely unlikely:
    the transpiler cannot be handed a class whose name shadows it.
    """
    js = gen("@dataclass\nclass State:\n    value: int = 0\n")
    assert "State$" in js
    with pytest.raises(SyntaxError):
        compile("class State$:\n    pass\n", "<test>", "exec")


def test_dataclass_named_state_still_takes_field_overrides() -> None:
    """Aliasing the base leaves the constructor contract untouched."""
    js = gen("@dataclass\nclass State:\n    value: int = 3\n")
    assert "super(opts);" in js
    assert "this.value = opts.value !== undefined ? opts.value : 3;" in js


def test_a_class_shadowing_a_widget_drops_the_widget_import() -> None:
    """A local class wins over the import of the same name, as in Python.

    Emitting both would be the same double declaration as the ``State`` case,
    for any name the module happens to reuse.
    """
    js = gen("@dataclass\nclass Text:\n    value: int = 0\n")
    assert "export class Text extends State {" in js
    assert 'from "./widgets.js"' not in js


def test_dataclass_inheriting_a_state_named_base_uses_the_local_class() -> None:
    """Explicit inheritance still names the transpiled class, not the alias."""
    js = gen(
        "@dataclass\nclass State:\n    value: int = 0\n\n\n"
        "@dataclass\nclass Extra(State):\n    other: int = 1\n"
    )
    assert "export class State extends State$ {" in js
    assert "export class Extra extends State {" in js


def test_a_widget_refuses_a_kwarg_the_core_does_not_declare() -> None:
    """Mode C answers what the core would answer, at build time.

    Nothing revalidates the call at runtime — the generated builder destructures
    the object and ignores what it does not name — so an undeclared kwarg would
    be silence in Mode C and a ``ValidationError`` in Modes A and B.
    """
    with pytest.raises(TranspileError) as excinfo:
        gen(
            "from tempest_core import Container, Text\n\n\n"
            "def panel() -> Container:\n"
            '    return Container(key="box", children=[Text(content="x")])\n'
        )
    message = str(excinfo.value)
    assert "does not accept `children`" in message
    assert "its child slot is `child`" in message


def test_the_child_slot_transpiles_and_reaches_the_builder() -> None:
    """The form the core demands is the form that survives to the JS call."""
    js = gen(
        "from tempest_core import Container, Text\n\n\n"
        "def panel() -> Container:\n"
        '    return Container(key="box", child=Text(content="x"))\n'
    )
    assert 'Container({ key: "box", child: Text({ content: "x" }) })' in js


def test_a_value_object_is_checked_too() -> None:
    """The check is about core models, not only widgets."""
    with pytest.raises(TranspileError, match="`Style` does not accept `padding_x`"):
        gen(
            "from tempest_core import Style\n\n\n"
            "def style() -> Style:\n    return Style(padding_x=8.0)\n"
        )


def test_an_aliased_import_is_still_checked() -> None:
    """The model is resolved by its core name, not by the local alias."""
    with pytest.raises(TranspileError, match="`Box` does not accept `children`"):
        gen(
            "from tempest_core import Container as Box, Text\n\n\n"
            "def panel() -> Box:\n"
            '    return Box(children=[Text(content="x")])\n'
        )


def test_a_local_class_shadowing_a_widget_keeps_its_own_fields() -> None:
    """A module that declares ``Container`` means its own, so nothing is checked."""
    js = gen(
        '@dataclass\nclass Container:\n    label: str = ""\n\n\n'
        'def make() -> Container:\n    return Container(label="x")\n'
    )
    assert 'new Container({ label: "x" })' in js


def test_a_core_helper_call_is_left_alone() -> None:
    """Only a model with declared fields is checked; a function is not."""
    js = gen(
        "from tempest_core import t\n\n\n"
        "def label() -> str:\n"
        '    return t("hello", locale="pt-BR", translations={})\n'
    )
    assert 'return t("hello", { locale: "pt-BR", translations: {} });' in js


def test_a_renamed_list_slot_passes_the_check() -> None:
    """``Form`` declares ``fields``, and the builder now takes that name.

    The builder used to have no child parameter at all, so every field of a
    transpiled form was dropped on the floor.
    """
    js = gen(
        "from tempest_core import Form, FormField\n\n\n"
        "def signup() -> Form:\n"
        '    return Form(key="signup", fields=[FormField(name="email")])\n'
    )
    assert "fields: [" in js
    assert 'FormField({ name: "email" }),' in js


def test_a_widget_prop_is_camelized_by_rule_not_by_table() -> None:
    """Every multi-word widget field has to reach its builder's parameter.

    A hand-kept rename table covered ``on_click``/``on_change`` and silently
    dropped the rest: ``on_drop``, ``on_submit``, ``drag_data``, ``min_value``
    and 30-odd more were emitted as snake_case into an object whose builder
    destructures camelCase, so the prop simply did not exist at runtime.
    """
    js = gen(
        "from tempest_core import Draggable, Text\n\n\n"
        "def card() -> Draggable:\n"
        '    return Draggable(key="c", drag_data="c7", child=Text(content="x"))\n'
    )
    assert 'dragData: "c7"' in js
    assert "drag_data" not in js


def test_a_style_keeps_the_wire_snake_case_keys() -> None:
    """``Style`` is the wire shape itself, so its keys must not be camelized."""
    js = gen(
        "from tempest_core import Style\n\n\n"
        "def styled() -> Style:\n    return Style(font_size=14.0, max_width=200.0)\n"
    )
    assert "font_size: 14.0" in js
    assert "max_width: 200.0" in js
    assert "fontSize" not in js


def test_a_name_the_client_cannot_serve_is_refused() -> None:
    """A component outside the subset must fail the build, not the page load.

    ``DataTable`` composes its tree from the rows it is handed, so there is no
    fixed composition to port to a Python-free runtime — unlike ``Card`` and the
    other structural components, which are ported. The transpiler used to emit
    the import anyway — one the browser cannot resolve, so the module never
    evaluates and the page stays blank with nothing in the build log.
    """
    with pytest.raises(TranspileError, match="`DataTable` is not available in Mode C"):
        gen(
            "from tempest_core import DataTable\n\n\n"
            "def grid() -> DataTable:\n"
            "    return DataTable(columns=[], data=[])\n"
        )


def test_an_enum_and_a_value_object_now_reach_the_client() -> None:
    """The core's enums and wire fragments are served, so they may be used."""
    js = gen(
        "from tempest_core import Semantics, Style, Text, TextAlign\n\n\n"
        "def label() -> Text:\n"
        "    return Text(\n"
        '        content="x",\n'
        "        style=Style(text_align=TextAlign.CENTER),\n"
        '        semantics=Semantics(label="titulo"),\n'
        "    )\n"
    )
    assert "TextAlign.CENTER" in js
    assert 'Semantics({ label: "titulo" })' in js
    assert 'from "./widgets.js"' in js


def test_a_type_only_import_is_never_emitted() -> None:
    """An event type used in an annotation costs no import.

    Annotations are dropped, so the name is never referenced and the
    availability check never sees it — which is what keeps typing a handler
    free.
    """
    js = gen(
        "from tempest_core import DragEvent, Text\n\n\n"
        "def handle(event: DragEvent) -> Text:\n"
        '    return Text(content="x")\n'
    )
    assert "DragEvent" not in js
    assert 'import { Text } from "./widgets.js";' in js


def test_a_stdlib_annotation_source_costs_no_import() -> None:
    """`collections.abc`/`typing` names annotate handlers and emit nothing.

    Eleven example apps stopped at this import while the name they wanted was
    only ever written in an annotation — which the emitter drops.
    """
    js = gen(
        "from collections.abc import Awaitable, Callable\n"
        "from typing import Any\n"
        "from tempest_core import Text\n\n\n"
        "def handle(fetch: Callable[[], Awaitable[str]], extra: Any) -> Text:\n"
        '    return Text(content="x")\n'
    )
    assert "Callable" not in js
    assert "Awaitable" not in js
    assert "Any" not in js
    assert "collections" not in js
    assert 'import { Text } from "./widgets.js";' in js


def test_a_module_level_type_alias_is_dropped() -> None:
    """`Fetcher = Callable[...]` is an alias, not a constant, so nothing is emitted.

    It reads as an assignment, so emitting it would declare a `const` whose value
    references identifiers nothing imports — a `ReferenceError` at load.
    """
    js = gen(
        "from collections.abc import Awaitable, Callable\n"
        "from tempest_core import Text\n\n"
        "Fetcher = Callable[[], Awaitable[list[str]]]\n"
        "LIMIT = 3\n\n\n"
        "def handle(fetch: Fetcher) -> Text:\n"
        "    return Text(content=str(LIMIT))\n"
    )
    assert "Fetcher" not in js
    assert "const LIMIT = 3;" in js


def test_a_type_only_name_used_as_a_value_is_refused() -> None:
    """Using an annotation-only name as a value is an error, not a dead identifier.

    Without the guard the emitter wrote a bare `Any` with no import, so the module
    loaded and died on the line that ran it. A module-level `X = Any` is not this
    case: that reads as a type alias in Python too, so it is dropped.
    """
    with pytest.raises(TranspileError) as excinfo:
        gen(
            "from typing import Any\nfrom tempest_core import Text\n\n\n"
            "def describe() -> str:\n"
            "    return str(Any)\n"
        )
    assert "type-only name" in str(excinfo.value)


def test_a_constant_built_from_a_runtime_name_is_still_emitted() -> None:
    """A `const` whose value carries a real term is not mistaken for an alias."""
    js = gen(
        "from typing import Any\n\n"
        "BASE = 10\n"
        "LIMIT = BASE\n\n\n"
        "def read(x: Any) -> int:\n"
        "    return LIMIT\n"
    )
    assert "const LIMIT = BASE;" in js


def test_the_component_facade_routes_like_the_core() -> None:
    """`from tempestweb.components import Card` reaches the same served builder.

    Of the 77 names the facade exports, 63 are the core object itself, and it is
    the import the tutorial teaches — while Mode C used to refuse the module
    outright.
    """
    js = gen(
        "from tempestweb.components import Card, Text\n\n\n"
        "def view(app):\n"
        '    return Card(children=[Text(content="x", key="t")], key="c")\n'
    )
    assert 'import { Card, Text } from "./widgets.js";' in js


def test_a_facade_name_the_client_cannot_serve_is_refused_by_name() -> None:
    """A component the facade re-exports but the client lacks is refused by name.

    The distinction matters: the module is legal, the name is what is missing, so
    the diagnostic points at the component instead of the import path.
    ``DataTable`` is the standing example — its tree shape depends on the rows it
    is handed, so it is deliberately not ported.
    """
    with pytest.raises(TranspileError) as excinfo:
        gen(
            "from tempestweb.components import DataTable\n\n\n"
            "def view(app):\n"
            '    return DataTable(key="t")\n'
        )
    message = str(excinfo.value)
    assert "DataTable" in message
    assert "is not available in Mode C" in message


def test_the_repos_own_field_layer_is_served() -> None:
    """`tempestweb.components`' own fields and forms route to the client."""
    js = gen(
        "from tempestweb.components import EmailField, LoginForm\n\n\n"
        "def view(app):\n"
        "    return Column(\n"
        '        children=[EmailField(key="e"), LoginForm(key="l")], key="c"\n'
        "    )\n"
    )
    assert 'import { EmailField, LoginForm } from "./widgets.js";' in js


def test_a_starred_element_spreads_in_a_literal() -> None:
    """`[a, *rest]` is the immutable-state idiom, and JS spreads the same way."""
    js = gen("def f(state):\n    return [state.head, *state.tail]\n")
    assert "...state.tail," in js


def test_a_nested_loop_target_destructures() -> None:
    """`for i, (q, a) in enumerate(pairs)` binds the nested pair."""
    js = gen(
        "def f(pairs):\n"
        "    for idx, (question, answer) in enumerate(pairs):\n"
        "        print(idx, question, answer)\n"
    )
    assert "for (const [idx, [question, answer]] of" in js


def test_a_nested_assignment_target_destructures() -> None:
    """`first, (second, third) = value` binds every leaf."""
    js = gen("def f(value):\n    first, (second, third) = value\n    return first\n")
    assert "const [first, [second, third]] = value;" in js


def test_is_none_uses_loose_equality_and_identity_otherwise() -> None:
    """`is None` answers "no value"; `is` on anything else is identity.

    `== null` is the one correct use of loose equality here: a field a JS object
    never assigned is `undefined`, and Python's `is None` has to answer True for
    it just as it does for an explicit `None`.
    """
    js = gen(
        "def f(state):\n"
        "    a = state.dialog is not None\n"
        "    b = state.other is None\n"
        "    c = state.x is state.y\n"
        "    d = state.x is not state.y\n"
        "    return a\n"
    )
    assert "state.dialog != null" in js
    assert "state.other == null" in js
    assert "state.x === state.y" in js
    assert "state.x !== state.y" in js


def test_a_zero_padded_int_keeps_the_sign_outside_the_padding() -> None:
    """`f"{n:05d}"` matches Python for negatives, which `padStart` alone does not.

    `String(-42).padStart(5, "0")` is `"00-42"`; Python's is `"-0042"`. The
    emitted arrow also takes its argument once, so an interpolated call is not
    evaluated twice.
    """
    js = gen('def f(n):\n    return f"{n:05d}"\n')
    assert 'String(-v).padStart(4, "0")' in js
    assert 'String(v).padStart(5, "0")' in js
    # Applied once: the value is not re-evaluated by the sign branch.
    assert js.count(")(n)") == 1


def test_an_unsupported_format_spec_still_names_what_is_supported() -> None:
    """The diagnostic lists the specs that work, `0Nd` included."""
    with pytest.raises(TranspileError) as excinfo:
        gen('def f(n):\n    return f"{n:>5}"\n')
    assert "`0Nd`" in str(excinfo.value)


def test_a_field_without_a_default_is_undefined_not_an_error() -> None:
    """A required field is `undefined` until `make_state` fills it.

    Four examples stopped here, and the emitted class has no notion of a
    required field: the constructor takes overrides, so the honest translation
    of "no default" is `undefined`.
    """
    js = gen("@dataclass\nclass S:\n    items: list[int]\n")
    assert "this.items = opts.items !== undefined ? opts.items : undefined;" in js


def test_a_parameterized_dataclass_decorator_is_accepted() -> None:
    """`@dataclass(frozen=True)` emits the same class as a bare `@dataclass`.

    `frozen`/`slots`/`eq` describe Python-side behaviour the generated JS class
    does not have, so accepting and ignoring them is faithful; three examples in
    this repo are written that way.
    """
    js = gen("@dataclass(frozen=True, slots=True)\nclass S:\n    value: int = 0\n")
    assert "export class S extends State {" in js
    assert "this.value = opts.value !== undefined ? opts.value : 0;" in js


def test_an_unknown_dataclass_option_is_refused_by_name() -> None:
    """An option that is not a known no-op is refused, not dropped in silence."""
    with pytest.raises(TranspileError) as excinfo:
        gen("@dataclass(weird=True)\nclass S:\n    value: int = 0\n")
    assert "'weird'" in str(excinfo.value)


def test_a_custom_default_factory_is_called() -> None:
    """`field(default_factory=fresh)` calls the factory, like the dataclass does."""
    js = gen(
        "@dataclass\nclass S:\n"
        "    log: list[str] = field(default_factory=fresh)\n"
        "    tags: list[str] = field(default_factory=list)\n"
    )
    assert "opts.log !== undefined ? opts.log : (fresh)();" in js
    assert "opts.tags !== undefined ? opts.tags : [];" in js


def test_a_field_option_that_shapes_python_only_is_ignored() -> None:
    """`repr`/`compare`/`init` shape behaviour the emitted constructor lacks."""
    js = gen(
        "@dataclass\nclass S:\n"
        '    note: str = field(default="", repr=False)\n'
        "    seq: int = field(init=False)\n"
    )
    assert 'opts.note !== undefined ? opts.note : "";' in js
    assert "opts.seq !== undefined ? opts.seq : undefined;" in js


def test_an_unknown_field_option_is_refused_by_name() -> None:
    """A `field(...)` option that could change the value is refused."""
    with pytest.raises(TranspileError) as excinfo:
        gen("@dataclass\nclass S:\n    value: int = field(converter=int)\n")
    assert "'converter'" in str(excinfo.value)


def test_a_lambda_default_factory_is_applied_not_stored() -> None:
    """`field(default_factory=lambda: list(SEED))` holds the list, not the arrow.

    Measured in Chrome before the parentheses: `core-app-shell` compiled, the
    page loaded, and the first render died on `state.items.map is not a
    function`, because the field held the function.
    """
    js = gen(
        "@dataclass\nclass S:\n"
        "    items: list[int] = field(default_factory=lambda: list(SEED))\n"
    )
    assert "(() => [...SEED])()" in js


def test_container_builtins_convert_instead_of_calling_a_missing_name() -> None:
    """`list(xs)` emitted a call to an undefined `list` — a blank page.

    `node --check` parses it and the golden compares text, so nothing caught it
    until a browser ran the line.
    """
    js = gen(
        "def f(xs, pairs):\n"
        "    a = list(xs)\n"
        "    b = tuple(xs)\n"
        "    c = set(xs)\n"
        "    d = dict(pairs)\n"
        "    e = list()\n"
        "    return a\n"
    )
    assert "const a = [...xs];" in js
    assert "const b = [...xs];" in js
    assert "const c = new Set(xs);" in js
    assert "const d = Object.fromEntries(pairs);" in js
    assert "const e = [];" in js


def test_a_served_module_is_reachable_by_either_import_form() -> None:
    """`import json` and `from math import ceil` both resolve."""
    js = gen(
        "import json\nfrom math import ceil\n\n\n"
        "def f(payload, total):\n"
        "    return json.dumps({'pages': ceil(total / 10)})\n"
    )
    assert "JSON.stringify(" in js
    assert "Math.ceil(" in js
    # Neither module leaves an import behind: both map to a JS global.
    assert "json" not in js
    assert "ceil(" not in js.replace("Math.ceil(", "")


def test_a_module_constant_reads_as_a_value() -> None:
    """`math.pi` is a constant, not a call."""
    js = gen("import math\n\n\ndef f(r):\n    return math.pi * r * r\n")
    assert "Math.PI" in js


def test_asyncio_sleep_converts_seconds_to_milliseconds() -> None:
    """Python counts seconds and `setTimeout` counts milliseconds."""
    js = gen("import asyncio\n\n\nasync def f():\n    await asyncio.sleep(0.5)\n")
    assert "sleep$(0.5)" in js
    assert 'import { sleep as sleep$ } from "./runtime.js";' in js


def test_a_helper_import_cannot_collide_with_an_app_name() -> None:
    """The `$` alias is illegal in Python, so an app's own `sleep` is safe."""
    js = gen(
        "import asyncio\n\n\n"
        "def sleep(seconds):\n"
        "    return seconds\n\n\n"
        "async def f():\n"
        "    await asyncio.sleep(1)\n"
        "    return sleep(2)\n"
    )
    assert "sleep as sleep$" in js
    assert "export function sleep(seconds)" in js
    assert "await sleep$(1)" in js
    assert "return sleep(2)" in js


def test_a_compiled_pattern_keeps_python_re_semantics() -> None:
    """`Pattern.match` anchors at the start; `RegExp` has no `.match` at all.

    Emitting `_RE.match(s)` straight through shipped a call to a method the
    browser does not have — the page loads and dies on the line that runs it.
    """
    js = gen(
        'import re\n\n_RE = re.compile(r"[a-z]+")\n\n\n'
        "def f(value):\n"
        "    return [_RE.match(value), _RE.search(value), _RE.sub('x', value)]\n"
    )
    assert "new RegExp(" in js
    assert "reMatch$(_RE, value)" in js
    assert "reSearch$(_RE, value)" in js
    assert 'reSub$(_RE, "x", value)' in js


def test_re_sub_replaces_every_occurrence() -> None:
    """Python's `re.sub` is global; a JS `replace` with a string is not."""
    js = gen('import re\n\n\ndef f(text):\n    return re.sub(r"\\D", "", text)\n')
    assert 'reSub$("\\\\D", "", text)' in js


def test_a_str_enum_becomes_a_frozen_object() -> None:
    """An app enum is a constant table, which is what the core's enums ship as."""
    js = gen(
        "from enum import StrEnum\n\n\n"
        "class Phase(StrEnum):\n"
        '    """Phase."""\n\n'
        '    INBOX = "inbox"\n'
        '    CLEAR = "clear"\n'
    )
    assert "export const Phase = Object.freeze({" in js
    assert 'INBOX: "inbox",' in js
    assert 'CLEAR: "clear",' in js


def test_a_generator_expression_takes_the_comprehension_path() -> None:
    """`any(x for x in xs)` is a comprehension without the brackets."""
    js = gen("def f(rows):\n    return any(len(r) > 0 for r in rows)\n")
    assert "[...rows].map((r) => r.length > 0).some(Boolean)" in js


def test_a_comprehension_over_a_string_iterates_characters() -> None:
    """Python iterates a string; a JS string has no `.map`.

    `String(value).map(...)` parsed, passed the golden, and threw in the browser.
    """
    js = gen("def f(value):\n    return [c for c in str(value)]\n")
    assert "[...String(value)]" in js


def test_a_string_predicate_becomes_a_pattern_test() -> None:
    """`c.isdigit()` has no JS counterpart, so it routes to a full match."""
    js = gen("def f(c):\n    return c.isdigit()\n")
    assert 'reFullmatch$("[0-9]+", c) !== null' in js


def test_a_refused_module_says_what_to_do_instead() -> None:
    """A diagnostic that only lists what is allowed leaves the reader stuck."""
    with pytest.raises(TranspileError) as excinfo:
        gen("import datetime\n")
    message = str(excinfo.value)
    assert "format the value in your state" in message
    with pytest.raises(TranspileError) as from_form:
        gen("from functools import partial\n")
    assert "write them inline" in str(from_form.value)


def test_an_unknown_module_member_is_refused_by_name() -> None:
    """`re.escape` does not exist in the browser, and silence would ship a bug."""
    with pytest.raises(TranspileError) as excinfo:
        gen("import re\n\n\ndef f(s):\n    return re.escape(s)\n")
    assert "`re.escape`" in str(excinfo.value)


def test_a_dict_get_reads_the_key_with_its_default() -> None:
    """A dict is a plain object, which has no `.get`.

    `state.errors.get("email", "")` shipped a page that died on the first
    render. `??` and not `||`, so a stored `0`/`""` is not replaced.
    """
    js = gen(
        "def view(app):\n"
        '    a = app.state.errors.get("email", "")\n'
        '    b = app.state.answers.get("q1")\n'
        "    return [a, b]\n"
    )
    assert 'const a = (app.state.errors["email"] ?? "");' in js
    assert 'const b = app.state.answers["q1"];' in js


def test_the_native_facade_keeps_its_own_get() -> None:
    """`native.storage.get(name)` is a real facade call, not a dict read."""
    js = gen(
        "from tempestweb import native\n\n\n"
        "async def load():\n"
        '    return await native.storage.get("key")\n'
    )
    assert 'await native.storage.get("key")' in js


def test_a_core_widget_method_is_refused_at_build_time() -> None:
    """Mode C ports a widget's builder, not the widget's Python methods.

    `form.validate(values)` transpiled cleanly and then threw
    `form1.validate is not a function` on the first render — measured in
    `examples/signup-wizard`. Compiling something that dies is worse than
    refusing it.
    """
    with pytest.raises(TranspileError) as excinfo:
        gen(
            "from tempest_core import Form, Text\n\n"
            "form1 = Form(fields=[])\n\n\n"
            "def view(app):\n"
            "    return Text(content=str(form1.validate({})))\n"
        )
    message = str(excinfo.value)
    assert "`Form.validate()`" in message
    assert "not the widget's Python methods" in message
