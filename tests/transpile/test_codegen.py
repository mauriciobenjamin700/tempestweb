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
    # `native.storage.get` is the storage capability, NOT dict.get.
    js = gen("def f():\n    return native.storage.get('k')\n")
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
