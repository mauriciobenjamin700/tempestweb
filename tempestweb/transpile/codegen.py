"""AST → JavaScript code generation for the Mode C transpiler (spike / C0).

Transcribes the *app layer* of a typed-Python tempestweb module into a native
ES-module: `@dataclass` state classes, the `view(app)` builder, event-handler
closures, and widget constructor calls. The generated module imports the shared
native runtime (`./runtime.js`) and widget IR builders (`./widgets.js`) — the
whole reconciler/renderer stays native JS (see docs/modo-c-transpile.md).

The subset is deliberately small (enough for the counter): dataclasses with
defaulted scalar fields, top-level and nested `def`s, `return`, `f"..."`,
attribute/name/number/string/BinOp expressions, keyword-only widget calls, and
`app.set_state(lambda s: setattr(s, "field", expr))`. Anything else raises
:class:`TranspileError` with a ``file:line`` diagnostic.
"""

from __future__ import annotations

import ast
import builtins
import json
import re
from typing import Any

import tempest_core
import tempestweb.components as tempestweb_components
from tempestweb.transpile._members import VALUE_MEMBERS
from tempestweb.transpile._native import (
    NATIVE_ENUMS,
    NATIVE_EXPORTS,
    NATIVE_FLAT,
    NATIVE_GROUPS,
    NATIVE_MEMBERS,
    NATIVE_TYPES,
)
from tempestweb.transpile._served import SERVED_NAMES
from tempestweb.transpile.errors import TranspileError

__all__: list[str] = ["generate"]

# Imported names that resolve to the native runtime rather than a widget builder.
_RUNTIME_NAMES: frozenset[str] = frozenset({"App", "State"})
# The alias the injected dataclass base is imported under when the module
# declares its own `State`. `$` is legal in a JS identifier but never in a
# Python one, so this alias cannot collide with a transpiled name.
_STATE_BASE_ALIAS: str = "State$"
# What `./native.js` exports. Every form Python spells for a native
# capability lands on this one module, so the facade is imported once.
_NATIVE_NAMES: frozenset[str] = NATIVE_EXPORTS
# The namespace `from tempestweb import native` binds.
_NATIVE_NAMESPACE: str = "native"
# The alias the facade is imported under when the module reached it through
# a submodule import. `$` is legal in a JS identifier and never in a Python
# one, so an app that binds its own `native` cannot collide with it.
_NATIVE_FACADE_ALIAS: str = "native$"
# The package whose submodules are capability groups (`tempestweb.native.http`).
_NATIVE_MODULE: str = "tempestweb.native"
# Navigation primitives, imported from `./nav.js` in Mode C.
_NAV_NAMES: frozenset[str] = frozenset({"Route", "NavStack", "routes_from_path"})
# Localization helpers, imported from `./i18n.js` in Mode C.
_I18N_NAMES: frozenset[str] = frozenset({"translate", "t", "Locale"})
# Theme + responsiveness primitives, imported from `./theme.js` in Mode C.
_THEME_NAMES: frozenset[str] = frozenset(
    {"Theme", "ThemeMode", "MediaQueryData", "Breakpoints"}
)
# Declarative animation values, imported from `./motion.js` in Mode C.
_MOTION_NAMES: frozenset[str] = frozenset({"Transition", "Curve"})
# Imperative animation primitives, imported from `./animation.js` in Mode C.
_ANIM_NAMES: frozenset[str] = frozenset({"AnimationController", "Tween", "Spring"})
# Imported JS classes that must be constructed with `new` (Route(...) -> new Route).
_JS_CLASSES: frozenset[str] = frozenset(
    {
        "Route",
        "NavStack",
        "Locale",
        "Theme",
        "MediaQueryData",
        "Breakpoints",
        "AnimationController",
        "Tween",
        "Spring",
    }
)
# Pure field validators (from tempest_core.validators), ported to ./validators.js.
_VALIDATOR_NAMES: frozenset[str] = frozenset(
    {
        "validate_cpf",
        "validate_cnpj",
        "validate_email",
        "validate_phone",
        "EMAIL_PATTERN",
    }
)
# Type-only imports that carry no runtime value and are dropped from the output.
_TYPE_ONLY_NAMES: frozenset[str] = frozenset({"Widget"})
# Modules whose names exist only in annotations, which the emitter drops. The
# import carries no runtime value, so nothing is emitted for it — but a name from
# here used as a *value* is refused, because a bare identifier with no import is
# a `ReferenceError` the browser raises only when the line runs.
_TYPE_ONLY_MODULES: frozenset[str] = frozenset({"collections.abc", "typing"})
# The component facade this package re-exports the core's components through. Of
# the 77 names it exports, 63 are the core object itself (identity-equal), so
# they route exactly like a `tempest_core` import; the rest are this repo's own
# layer and are refused by name against the served manifest.
_COMPONENT_MODULE: str = "tempestweb.components"

# Stdlib modules Mode C can serve, with the JS each member maps to. A module is
# reachable by either import form (`import re` / `from math import ceil`), and a
# member outside its table is refused by name — the browser has no `re.escape`,
# and pretending otherwise ships a page that dies on the line that calls it.
_MODULE_CALLS: dict[str, dict[str, str]] = {
    "json": {"dumps": "JSON.stringify", "loads": "JSON.parse"},
    "math": {
        "ceil": "Math.ceil",
        "cos": "Math.cos",
        "exp": "Math.exp",
        "fabs": "Math.abs",
        "floor": "Math.floor",
        "hypot": "Math.hypot",
        "isfinite": "Number.isFinite",
        "isnan": "Number.isNaN",
        "log": "Math.log",
        "log10": "Math.log10",
        "log2": "Math.log2",
        "pow": "Math.pow",
        "sin": "Math.sin",
        "sqrt": "Math.sqrt",
        "tan": "Math.tan",
        "trunc": "Math.trunc",
    },
    "base64": {"b64encode": "btoa", "b64decode": "atob"},
    # Runtime helpers, imported from ./runtime.js under a `$` alias.
    "asyncio": {"sleep": "@sleep"},
    "re": {
        "compile": "@compile",
        "findall": "@reFindall",
        "fullmatch": "@reFullmatch",
        "match": "@reMatch",
        "search": "@reSearch",
        "sub": "@reSub",
    },
}

#: Module-level constants, by module and name.
_MODULE_CONSTANTS: dict[str, dict[str, str]] = {
    "math": {
        "e": "Math.E",
        "inf": "Infinity",
        "nan": "NaN",
        "pi": "Math.PI",
        "tau": "(2 * Math.PI)",
    },
}

#: Helpers the emitted code calls, imported from ``./runtime.js`` aliased with a
#: `$` — illegal in a Python identifier, so an app's own ``sleep`` cannot collide.
_RUNTIME_HELPERS: frozenset[str] = frozenset(
    {
        "dictPop",
        "formValidate",
        "reFindall",
        "reFullmatch",
        "reMatch",
        "reSearch",
        "reSub",
        "sleep",
        "toDict",
    }
)

#: Methods of a compiled pattern, and the helper each maps to. Only a name bound
#: to `re.compile(...)` is treated this way — mapping every `.match(...)` in the
#: module would catch an app's own method of the same name.
_PATTERN_METHODS: dict[str, str] = {
    "findall": "reFindall",
    "fullmatch": "reFullmatch",
    "match": "reMatch",
    "search": "reSearch",
    "sub": "reSub",
}

#: The widget methods Mode C ports, and the helper each routes to. The client
#: carries every widget's *builder* and none of its class's Python methods, so
#: this table is the exception list — a method absent from it is refused, which
#: is what keeps a page from compiling and then dying. `Form.validate` is here
#: because its inputs survive: `validators` never crosses a wire in Mode C, so
#: the live functions are on the node when the helper runs.
_WIDGET_METHODS: dict[str, str] = {"validate": "formValidate"}

#: Bases that turn a class into a frozen JS object of its members.
_ENUM_BASES: frozenset[str] = frozenset({"Enum", "IntEnum", "StrEnum"})

#: Modules refused on purpose, with what to do instead. Listing the alternative
#: is the difference between a diagnostic and a dead end.
_REFUSED_MODULES: dict[str, str] = {
    "datetime": (
        "there is no equivalent in the browser without shipping an "
        "implementation; format the value in your state and pass the string"
    ),
    "functools": (
        "`partial` is a lambda and `reduce` is `.reduce`; write them inline "
        "(a render-time cache like `lru_cache` has no meaning here)"
    ),
    "collections": "use a plain dict or list",
    "itertools": "use a comprehension or a `for` loop",
    "os": "an artifact has no filesystem; use `tempestweb.native` capabilities",
    "pathlib": "an artifact has no filesystem; use `tempestweb.native` capabilities",
    "random": "seeded randomness is not portable; compute the value in your state",
    "time": "use `asyncio.sleep`, or keep the timestamp in your state",
}

# Builtin names a type alias may mention besides the type-only ones themselves
# (`list[str]`, `dict[str, int]`, `tuple[int, ...]`).
_BUILTIN_NAMES: frozenset[str] = frozenset(dir(builtins))


# `@dataclass` options that change nothing about the emitted JS: the generated
# class has no `repr`, no ordering and no equality of its own, and `frozen`/`slots`
# have no counterpart. Refusing them was conservatism, not a limit.
_IGNORED_DATACLASS_OPTIONS: frozenset[str] = frozenset(
    {"frozen", "slots", "eq", "order", "repr", "init", "unsafe_hash", "kw_only"}
)
# `field(...)` options with the same property: they shape Python-side behaviour
# the emitted constructor does not have.
_IGNORED_FIELD_OPTIONS: frozenset[str] = frozenset(
    {"init", "repr", "compare", "hash", "kw_only", "metadata"}
)


def _is_none(node: ast.expr) -> bool:
    """Whether an expression is the literal ``None``.

    Args:
        node: The expression to inspect.

    Returns:
        Whether it is ``None``.
    """
    return isinstance(node, ast.Constant) and node.value is None


# API identifiers renamed from Python's snake_case to the JS client's camelCase.
_NAME_MAP: dict[str, str] = {
    "make_state": "makeState",
    "set_state": "setState",
    "on_click": "onClick",
    "on_change": "onChange",
    "color_scheme": "colorScheme",
    "field_variant": "fieldVariant",
    "max_length": "maxLength",
    "leading_icon": "leadingIcon",
    "trailing_icon": "trailingIcon",
    # A dataclass method's `self` receiver is JS's `this`.
    "self": "this",
}
_INDENT: str = "  "

# Python methods that map to a JS method with the SAME arguments. Kept to names
# with no realistic collision with a runtime/facade method (e.g. `.replace` is
# omitted — it clashes with `app.replace(route)`; `.get` clashes with
# `native.storage.get(...)` — use subscript instead).
# `str` predicates with no JS counterpart: each is a full-string pattern test.
# Emitting `c.isdigit()` shipped a call to a method the browser does not have.
#: `str` predicates and the ASCII pattern each is a full match against. The case
#: predicates need "at least one cased character, none of the other case" —
#: `"1".isupper()` is False in Python, and a naive `[A-Z]*` would say True. The
#: patterns are ASCII like the rest of this table, which the docs state.
_STRING_TESTS: dict[str, tuple[str, str]] = {
    "isdigit": ("[0-9]+", "reFullmatch"),
    "isalpha": ("[A-Za-z]+", "reFullmatch"),
    "isalnum": ("[A-Za-z0-9]+", "reFullmatch"),
    "isspace": ("\\s+", "reFullmatch"),
    "isupper": ("[^a-z]*[A-Z][^a-z]*", "reFullmatch"),
    "islower": ("[^A-Z]*[a-z][^A-Z]*", "reFullmatch"),
}

_METHOD_RENAMES: dict[str, str] = {
    "upper": "toUpperCase",
    "lower": "toLowerCase",
    "strip": "trim",
    "lstrip": "trimStart",
    "rstrip": "trimEnd",
    "startswith": "startsWith",
    "endswith": "endsWith",
    "append": "push",
}


def _is_main_guard(test: ast.expr) -> bool:
    """Return whether `test` is the `__name__ == "__main__"` script guard.

    Both spellings count, since the comparison reads either way round. The block
    it guards never runs when the file is imported as a module, which is exactly
    how Mode C compiles it — so recognising it here is fidelity, not a shortcut.

    Args:
        test: The `if` test expression.

    Returns:
        True when the test compares `__name__` against `"__main__"`.
    """
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return False
    if not isinstance(test.ops[0], ast.Eq):
        return False
    sides = (test.left, test.comparators[0])
    named = any(isinstance(s, ast.Name) and s.id == "__name__" for s in sides)
    literal = any(isinstance(s, ast.Constant) and s.value == "__main__" for s in sides)
    return named and literal


def _js_name(name: str) -> str:
    """Map a Python identifier to its JS spelling (API camelCase renames)."""
    return _NAME_MAP.get(name, name)


def _camel_name(name: str) -> str:
    """Camelize a core widget's field name the way its JS builder spells it.

    The generated builders (``widgets.gen.js``) destructure every prop in
    camelCase, so a widget kwarg has to be renamed by rule and not by table: a
    hand-kept list covered ``on_click``/``on_change`` and quietly dropped
    ``on_drop``, ``on_submit``, ``drag_data``, ``min_value`` and every other
    multi-word field, because the builder simply ignores a key it does not name.

    Args:
        name: The Python field name.

    Returns:
        The camelCase spelling (``drag_data`` → ``dragData``).
    """
    head, *rest = name.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in rest)


def _param_names(args: ast.arguments, node: ast.AST, filename: str) -> list[str]:
    """Return a function's positional parameter names, rejecting the rest.

    Variadic (``*args``/``**kwargs``), keyword-only and positional-only params
    are outside the subset — they would be silently dropped, so raise instead.

    Args:
        args: The function's ``ast.arguments``.
        node: The owning node (for the error location).
        filename: The source file name (for the diagnostic).

    Returns:
        The plain positional parameter names.

    Raises:
        TranspileError: If the signature uses an unsupported parameter form.
    """
    if args.vararg is not None or args.kwarg is not None:
        raise TranspileError(
            "variadic parameters (*args / **kwargs) are not supported",
            node,
            filename,
        )
    if args.kwonlyargs or getattr(args, "posonlyargs", []):
        raise TranspileError(
            "keyword-only / positional-only parameters are not supported",
            node,
            filename,
        )
    return [a.arg for a in args.args]


def _reject_fn_decorators(
    node: ast.FunctionDef | ast.AsyncFunctionDef, filename: str
) -> None:
    """Raise if a function carries a decorator (unsupported in the subset)."""
    if node.decorator_list:
        raise TranspileError("function decorators are not supported", node, filename)


def _child_blocks(stmt: ast.stmt) -> list[list[ast.stmt]]:
    """Return the nested statement blocks of a compound statement.

    Args:
        stmt: The statement to inspect.

    Returns:
        Each nested block (empty for a simple statement). Nested ``def``/``class``
        scopes are excluded — they own their own bindings.
    """
    if isinstance(stmt, (ast.If, ast.For, ast.While)):
        return [stmt.body, stmt.orelse]
    if isinstance(stmt, ast.Try):
        return [
            stmt.body,
            stmt.orelse,
            stmt.finalbody,
            *(handler.body for handler in stmt.handlers),
        ]
    if isinstance(stmt, ast.With):
        return [stmt.body]
    return []


def _hoisted_names(stmts: list[ast.stmt]) -> set[str]:
    """Collect the names that must be a function-top ``let`` rather than ``const``.

    A name may stay ``const`` only when it is bound **exactly once, at the top
    level, by a plain assignment**. Every other assigned name is hoisted to a
    single ``let`` at the function top so the emitted JS stays valid:

    - assigned inside an ``if``/``for``/``while``/``try`` block (a ``const`` there
      would be trapped in the JS block, but Python keeps it function-scoped);
    - the target of an augmented assignment (``+=`` etc.) — it mutates a binding,
      so both the binding and the mutation need ``let``;
    - assigned more than once (a re-binding — ``const`` would throw).

    Nested ``def``/``class`` scopes are not descended into.

    Args:
        stmts: The function's top-level statements.

    Returns:
        The names to declare with a hoisted ``let``.
    """
    hoisted: set[str] = set()
    seen_top: set[str] = set()

    def walk(block: list[ast.stmt], *, top: bool) -> None:
        """Visit one statement block, reporting each name it binds.

        ``top`` is what distinguishes a binding in the function body from one
        inside an ``if``/``for``/``while``/``try``; it is passed as ``False``
        into every nested block, because such a binding is function-scoped in
        Python but would be block-scoped in JS.

        Args:
            block: The statements to visit.
            top: Whether this block is the function's own body.
        """
        for stmt in block:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        _note(target.id, top=top)
                    elif isinstance(target, (ast.Tuple, ast.List)):
                        for elt in target.elts:
                            if isinstance(elt, ast.Name):
                                _note(elt.id, top=top)
            elif (
                isinstance(stmt, ast.AnnAssign)
                and isinstance(stmt.target, ast.Name)
                and stmt.value is not None
            ):
                _note(stmt.target.id, top=top)
            elif isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
                hoisted.add(stmt.target.id)
            elif not isinstance(
                stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                # A `with ... as x` binding leaks to the function scope in Python,
                # so always hoist its target to a `let`.
                if isinstance(stmt, ast.With):
                    for item in stmt.items:
                        if isinstance(item.optional_vars, ast.Name):
                            hoisted.add(item.optional_vars.id)
                for child in _child_blocks(stmt):
                    walk(child, top=False)

    def _note(name: str, *, top: bool) -> None:
        """Record one binding, hoisting the name when ``const`` would not do.

        Two cases force a hoisted ``let``: a binding made inside a nested block,
        which JS would scope to that block; and a second binding of a name
        already seen at the top level, which ``const`` would reject as a
        redeclaration. A name bound exactly once at the top level needs neither.

        Args:
            name: The bound identifier.
            top: Whether the binding sits in the function's own body.
        """
        if not top or name in seen_top:
            hoisted.add(name)
        seen_top.add(name)

    walk(stmts, top=True)
    return hoisted


class _Generator:
    """Single-module AST-to-JS emitter.

    One instance transcribes one module. It tracks the class names it has seen so
    a bare ``Foo()`` call becomes ``new Foo()``.
    """

    def __init__(self, filename: str) -> None:
        """Initialize the generator.

        Args:
            filename: Source file name, used in :class:`TranspileError` messages.
        """
        self.filename: str = filename
        self.class_names: set[str] = set()
        # The name the implicit dataclass base is emitted under: the runtime
        # `State`, or `_STATE_BASE_ALIAS` when the module declares its own.
        self.state_base: str = "State"
        # Identifiers actually referenced in the emitted JS, so imports reflect
        # what the output uses (not merely what the Python source imported).
        self.referenced: set[str] = set()
        # Per-function set of names hoisted to a `let` at the function top, so an
        # assignment inside an `if`/`for` block stays visible afterwards (Python
        # scoping) instead of being trapped in the JS block by `const`.
        self._scopes: list[set[str]] = []
        # Stack of the caught-error variable names while emitting `except` bodies,
        # so a bare `raise` (re-raise) can `throw` the current exception.
        self._exc_vars: list[str] = []
        # Local name → the `tempest_core` attribute it was imported from, so a
        # keyword-only call can be checked against the real model's fields even
        # when the import was aliased (`from tempest_core import Column as Col`).
        self.core_imports: dict[str, str] = {}
        # Local name → the import statement that introduced it, so refusing a
        # name the client cannot serve can point at a line.
        self.import_nodes: dict[str, ast.ImportFrom] = {}
        # Names that exist only in annotations: imported from a type-only module,
        # or bound to a type alias built from one. Referencing them as a value is
        # refused instead of emitting an identifier nothing imports.
        self.type_only: set[str] = set()
        # Local name → stdlib module it stands for (`import re`, `import re as r`).
        self.module_aliases: dict[str, str] = {}
        # Local name → the (module, member) it was imported from
        # (`from math import ceil`).
        self.member_aliases: dict[str, tuple[str, str]] = {}
        # Local name → the identifier `./native.js` exports for it, so the
        # facade import carries an `as` when the app renamed it.
        self.native_imports: dict[str, str] = {}
        # Every field name the module's dataclasses declare. An attribute the
        # source declared as a field is an attribute, so it wins over the dict
        # mapping: a state carrying an injected `get` callable read
        # `app.state.get(key)` as `app.state[key]`, which compiles and returns
        # undefined instead of calling it (measured in `examples/file-storage`).
        self.field_names: set[str] = set()
        # Local name → the native string enum it stands for. The facade speaks
        # JSON, so the enum crosses as its value and is emitted as a frozen table
        # next to the imports, the way the core's own enums travel.
        self.native_enums: dict[str, str] = {}
        # Local name → the facade path it stands for, so both submodule forms
        # (`from tempestweb.native import get_position`,
        # `from tempestweb.native.storage import put`) reach the same object
        # `from tempestweb import native` reaches by attribute.
        self.native_aliases: dict[str, str] = {}
        # Runtime helpers the emitted code ended up calling, so the import line
        # carries exactly what is used.
        self.runtime_helpers: set[str] = set()
        # Local names bound to an `enum` base, which make a class a frozen object.
        self.enum_bases: set[str] = set()
        # Local names bound to `re.compile(...)`, so their pattern methods route
        # to the helpers instead of emitting `RegExp.match`, which does not exist.
        self.regex_names: set[str] = set()
        # Local names bound to a core widget call. Mode C ports each widget's
        # *builder*, not its Python methods, so calling one is refused at build
        # time rather than emitting a call that dies on the first render.
        self.widget_names: dict[str, str] = {}

    # -- expressions --------------------------------------------------------

    def expr(self, node: ast.expr, indent: int) -> str:
        """Emit a JS expression for `node`.

        Args:
            node: The expression AST node.
            indent: Current indentation depth (for expressions that span lines).

        Returns:
            The JS source for the expression (may contain newlines).

        Raises:
            TranspileError: If the expression is outside the subset.
        """
        if isinstance(node, ast.Constant):
            return self._constant(node)
        if isinstance(node, ast.Name):
            path = self.native_aliases.get(node.id)
            if path is not None:
                self.referenced.add(path.split(".", 1)[0])
                return path
            if node.id in self.type_only:
                raise TranspileError(
                    f"{node.id!r} is a type-only name (annotations are dropped), "
                    "so it cannot be used as a value",
                    node,
                    self.filename,
                )
            self.referenced.add(node.id)
            return _js_name(node.id)
        if isinstance(node, ast.Attribute):
            constant = self._module_constant_js(node)
            if constant is not None:
                return constant
            return f"{self.expr(node.value, indent)}.{_js_name(node.attr)}"
        if isinstance(node, ast.JoinedStr):
            return self._template(node, indent)
        if isinstance(node, ast.BinOp):
            return self._binop(node, indent)
        if isinstance(node, ast.List):
            return self._array(node.elts, indent)
        if isinstance(node, ast.Tuple):
            return self._array(node.elts, indent)
        if isinstance(node, ast.Set):
            return f"new Set({self._array(node.elts, indent)})"
        if isinstance(node, ast.Dict):
            return self._dict(node, indent)
        if isinstance(node, ast.DictComp):
            return self._dictcomp(node, indent)
        if isinstance(node, ast.Call):
            return self._call(node, indent)
        if isinstance(node, ast.Lambda):
            return self._lambda(node, indent)
        if isinstance(node, ast.Await):
            return f"await {self.expr(node.value, indent)}"
        if isinstance(node, ast.Compare):
            return self._compare(node, indent)
        if isinstance(node, ast.BoolOp):
            return self._boolop(node, indent)
        if isinstance(node, ast.UnaryOp):
            return self._unaryop(node, indent)
        if isinstance(node, ast.IfExp):
            return self._ifexp(node, indent)
        if isinstance(node, (ast.ListComp, ast.GeneratorExp)):
            return self._listcomp(node, indent)
        if isinstance(node, ast.Subscript):
            return self._subscript(node, indent)
        raise TranspileError(
            f"expression {type(node).__name__} is not supported", node, self.filename
        )

    def _module_constant_js(self, node: ast.Attribute) -> str | None:
        """Emit a stdlib module constant (``math.pi``), or None if not one.

        Args:
            node: The attribute expression.

        Returns:
            The JS source, or ``None`` when the attribute is not a module member.

        Raises:
            TranspileError: If the module is served but has no such member — a
                bare ``math.gamma`` would otherwise emit an attribute read on an
                identifier nothing imports.
        """
        if not isinstance(node.value, ast.Name):
            return None
        module = self.module_aliases.get(node.value.id)
        if module is None:
            return None
        mapped = _MODULE_CONSTANTS.get(module, {}).get(node.attr)
        if mapped is not None:
            return mapped
        if node.attr in _MODULE_CALLS.get(module, {}):
            return None
        raise TranspileError(
            f"`{module}.{node.attr}` is not available in Mode C",
            node,
            self.filename,
        )

    def _constant(self, node: ast.Constant) -> str:
        """Emit a JS literal for a constant (str/bool/None/int/float)."""
        value = node.value
        if isinstance(value, str):
            return json.dumps(value)
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "null"
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            return repr(value)
        raise TranspileError(
            f"literal of type {type(value).__name__} is not supported",
            node,
            self.filename,
        )

    def _template(self, node: ast.JoinedStr, indent: int) -> str:
        """Emit a template literal for an f-string."""
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value.replace("`", "\\`").replace("$", "\\$"))
            elif isinstance(value, ast.FormattedValue):
                parts.append(self._formatted_value(value, indent))
            else:
                raise TranspileError("unsupported f-string part", value, self.filename)
        return "`" + "".join(parts) + "`"

    def _formatted_value(self, node: ast.FormattedValue, indent: int) -> str:
        """Emit a ``${...}`` interpolation for one f-string ``{expr}`` slot.

        Supports the common formatting cases and rejects the rest with a located
        error:

        - ``{x!s}`` → ``String(x)``; ``{x!r}`` → ``JSON.stringify(x)``.
        - ``{x:.Nf}`` → ``(x).toFixed(N)`` (fixed-point float formatting).

        Args:
            node: The ``FormattedValue`` node.
            indent: The current indentation depth.

        Returns:
            The JS template-literal substitution (``${...}``).

        Raises:
            TranspileError: For unsupported conversions/specs (``!a``, dynamic
                specs, or any spec other than ``.Nf``).
        """
        expr = self.expr(node.value, indent)
        conversion = node.conversion
        spec = node.format_spec
        if spec is not None:
            if conversion not in (-1, None):
                raise TranspileError(
                    "combining a conversion and a format spec (e.g. `{x!r:>5}`) "
                    "is not supported",
                    node,
                    self.filename,
                )
            return f"${{{self._format_spec_js(expr, self._const_spec(spec), node)}}}"
        if conversion in (-1, None):
            return f"${{{expr}}}"
        if conversion == ord("s"):
            return f"${{String({expr})}}"
        if conversion == ord("r"):
            return f"${{JSON.stringify({expr})}}"
        raise TranspileError(
            "f-string conversion `!a` (ascii) is not supported", node, self.filename
        )

    def _format_spec_js(self, expr: str, text: str, node: ast.AST) -> str:
        """Map a Python numeric format spec to an equivalent JS expression.

        Supported specs (a focused, faithful subset):

        - ``.Nf`` → ``(x).toFixed(N)`` — fixed-point.
        - ``,.Nf`` → ``(x).toLocaleString("en-US", {min/maxFractionDigits: N})``
          — grouped thousands with fixed decimals.
        - ``,`` → ``(x).toLocaleString("en-US")`` — grouped thousands.
        - ``.N%`` → ``((x) * 100).toFixed(N) + "%"`` — percent (``N`` defaults 0).
        - ``d`` / ``,d`` → truncated integer, optionally grouped.
        - ``0Nd`` → zero-padded integer, the spec every clock, counter and
          scoreboard needs. A bare ``padStart`` is **wrong** for a negative
          value: Python pads after the sign (``f"{-42:05d}"`` is ``"-0042"``)
          while ``String(-42).padStart(5, "0")`` gives ``"00-42"``. The emitted
          arrow keeps the sign outside the padding, and takes its argument once
          so an interpolated call is not evaluated twice.
        - ``+`` before any of the above → forces the sign on a positive, which is
          how a delta reads (``+12.3%``). The value is formatted **first** and the
          prefix decided from the result, because prepending ``"+"`` to a negative
          would give ``"+-3.0"``. Negative zero keeps its sign the way Python does,
          which ``toFixed`` alone drops. Not combinable with ``0Nd``: Python counts
          the sign inside that width and layering would give one character too
          many.

        Args:
            expr: The already-emitted JS for the interpolated value.
            text: The literal format-spec text (without the leading ``:``).
            node: The owning node, for the error location.

        Returns:
            The JS expression producing the formatted string.

        Raises:
            TranspileError: For any spec outside the supported subset (e.g.
                alignment/fill, sign, binary/hex, exponent).
        """
        if text.startswith("+"):
            rest = text[1:]
            if re.fullmatch(r"0(\d+)d", rest):
                raise TranspileError(
                    "f-string format spec '+0Nd' is not supported: Python counts "
                    "the sign inside the padded width, so the two cannot be "
                    "layered (use `+d` or `0Nd`)",
                    node,
                    self.filename,
                )
            formatted = self._format_spec_js("v", rest, node)
            return (
                f'((v) => {{ const s = {formatted}; return s.startsWith("-") ? s '
                f': (Object.is(v, -0) ? "-" : "+") + s; }})({expr})'
            )
        zero_pad = re.fullmatch(r"0(\d+)d", text)
        if zero_pad:
            width = int(zero_pad.group(1))
            return (
                f'((v) => v < 0 ? "-" + String(-v).padStart({max(width - 1, 0)}, "0")'
                f' : String(v).padStart({width}, "0"))({expr})'
            )
        match = re.fullmatch(r"(,)?(?:\.(\d+))?([fF%d])?", text)
        grouped = bool(match and match.group(1))
        precision = match.group(2) if match else None
        kind = match.group(3) if match else None
        if match is None or not (grouped or precision is not None or kind):
            raise TranspileError(
                f"f-string format spec {text!r} is not supported "
                "(supported: `.Nf`, `,`, `,.Nf`, `.N%`, `d`, `,d`, `0Nd`, and `+` "
                "before any of them)",
                node,
                self.filename,
            )
        if kind in ("f", "F"):
            if precision is None:
                raise TranspileError(
                    "fixed-point spec needs a precision (e.g. `.2f`)",
                    node,
                    self.filename,
                )
            if grouped:
                return (
                    f'({expr}).toLocaleString("en-US", '
                    f"{{ minimumFractionDigits: {precision}, "
                    f"maximumFractionDigits: {precision} }})"
                )
            return f"({expr}).toFixed({precision})"
        if kind == "%":
            digits = precision if precision is not None else "0"
            return f'(({expr}) * 100).toFixed({digits}) + "%"'
        if precision is not None:
            raise TranspileError(
                f"format spec {text!r} sets a precision without a float type "
                "(use `.Nf` or `.N%`)",
                node,
                self.filename,
            )
        if kind == "d":
            trunc = f"Math.trunc({expr})"
            return f'{trunc}.toLocaleString("en-US")' if grouped else f"String({trunc})"
        return f'({expr}).toLocaleString("en-US")'

    def _const_spec(self, spec: ast.expr) -> str:
        """Return the text of a constant f-string format spec.

        Args:
            spec: The ``format_spec`` node (a ``JoinedStr``).

        Returns:
            The literal spec text (e.g. ``".2f"``).

        Raises:
            TranspileError: If the spec interpolates a value (``{x:.{n}f}``).
        """
        if (
            isinstance(spec, ast.JoinedStr)
            and len(spec.values) == 1
            and isinstance(spec.values[0], ast.Constant)
            and isinstance(spec.values[0].value, str)
        ):
            return spec.values[0].value
        raise TranspileError(
            "dynamic f-string format specs (e.g. `{x:.{n}f}`) are not supported",
            spec,
            self.filename,
        )

    def _binop(self, node: ast.BinOp, indent: int) -> str:
        """Emit an arithmetic binary operation.

        ``**`` maps to JS ``**`` and ``//`` (floor division) to
        ``Math.floor(a / b)``.
        """
        left = self.expr(node.left, indent)
        right = self.expr(node.right, indent)
        if isinstance(node.op, ast.FloorDiv):
            return f"Math.floor({left} / {right})"
        ops: dict[type[ast.operator], str] = {
            ast.Add: "+",
            ast.Sub: "-",
            ast.Mult: "*",
            ast.Div: "/",
            ast.Mod: "%",
            ast.Pow: "**",
        }
        op = ops.get(type(node.op))
        if op is None:
            raise TranspileError(
                f"operator {type(node.op).__name__} is not supported",
                node,
                self.filename,
            )
        return f"({left} {op} {right})"

    def _compare(self, node: ast.Compare, indent: int) -> str:
        """Emit a comparison. Chained comparisons are joined with ``&&``.

        ``in`` / ``not in`` become ``.includes(...)`` membership tests.

        ``is`` / ``is not`` against ``None`` use the loose ``== null`` /
        ``!= null``, which is the one place loose equality is the *correct*
        translation: it answers "no value" for both `null` and `undefined`, and a
        field a JS object never assigned is `undefined`. Against any other
        operand, identity is `===` / `!==`.
        """
        ops: dict[type[ast.cmpop], str] = {
            ast.Eq: "===",
            ast.NotEq: "!==",
            ast.Lt: "<",
            ast.LtE: "<=",
            ast.Gt: ">",
            ast.GtE: ">=",
        }
        parts: list[str] = []
        left = node.left
        for op, right in zip(node.ops, node.comparators, strict=True):
            left_js = self.expr(left, indent)
            right_js = self.expr(right, indent)
            if isinstance(op, ast.In):
                parts.append(f"{right_js}.includes({left_js})")
            elif isinstance(op, ast.NotIn):
                parts.append(f"!{right_js}.includes({left_js})")
            elif isinstance(op, (ast.Is, ast.IsNot)):
                against_none = _is_none(left) or _is_none(right)
                if against_none:
                    symbol = "==" if isinstance(op, ast.Is) else "!="
                else:
                    symbol = "===" if isinstance(op, ast.Is) else "!=="
                parts.append(f"{left_js} {symbol} {right_js}")
            else:
                mapped = ops.get(type(op))
                if mapped is None:
                    raise TranspileError(
                        f"comparison {type(op).__name__} is not supported",
                        node,
                        self.filename,
                    )
                parts.append(f"{left_js} {mapped} {right_js}")
            left = right
        return parts[0] if len(parts) == 1 else "(" + " && ".join(parts) + ")"

    def _boolop(self, node: ast.BoolOp, indent: int) -> str:
        """Emit a boolean operation (``and`` → ``&&``, ``or`` → ``||``)."""
        op = "&&" if isinstance(node.op, ast.And) else "||"
        joined = f" {op} ".join(self.expr(value, indent) for value in node.values)
        return f"({joined})"

    def _unaryop(self, node: ast.UnaryOp, indent: int) -> str:
        """Emit a unary operation (``not`` → ``!``, unary ``-``/``+``)."""
        ops: dict[type[ast.unaryop], str] = {
            ast.Not: "!",
            ast.USub: "-",
            ast.UAdd: "+",
        }
        op = ops.get(type(node.op))
        if op is None:
            raise TranspileError(
                f"unary operator {type(node.op).__name__} is not supported",
                node,
                self.filename,
            )
        return f"{op}{self.expr(node.operand, indent)}"

    def _ifexp(self, node: ast.IfExp, indent: int) -> str:
        """Emit a conditional expression (``a if c else b`` → ``c ? a : b``)."""
        test = self.expr(node.test, indent)
        body = self.expr(node.body, indent)
        orelse = self.expr(node.orelse, indent)
        return f"({test} ? {body} : {orelse})"

    def _listcomp(self, node: ast.ListComp | ast.GeneratorExp, indent: int) -> str:
        """Emit a list comprehension as chained ``.filter().map()``.

        ``[expr for x in it if cond]`` → ``it.filter((x) => cond).map((x) => expr)``.
        Only a single ``for`` clause (with optional ``if``s) is supported.

        A generator expression takes the same path. JS has no lazy generator, so
        the array is materialized — a difference in cost, not in result, and every
        corpus site feeds one straight into ``any()``/``all()``/``sum()``.
        """
        if len(node.generators) != 1:
            raise TranspileError(
                "only single-loop comprehensions are supported", node, self.filename
            )
        gen = node.generators[0]
        var = self._loop_target(gen.target)
        # Spread, because Python iterates anything: `for c in str(value)` walks
        # the characters, and a JS string has no `.map`. Emitting the chain
        # straight on the expression shipped `String(value).map(...)`, which the
        # page only discovers when the line runs.
        iterable = f"[...{self.expr(gen.iter, indent)}]"
        result = iterable
        for cond in gen.ifs:
            result = f"{result}.filter(({var}) => {self.expr(cond, indent)})"
        element = self.expr(node.elt, indent)
        return f"{result}.map(({var}) => {element})"

    def _subscript(self, node: ast.Subscript, indent: int) -> str:
        """Emit an index/subscript access or a slice.

        ``x[i]`` → ``x[i]``; ``x[a:b]`` → ``x.slice(a, b)`` (bounds default to the
        ends). A slice ``step`` is unsupported.
        """
        value = self.expr(node.value, indent)
        if isinstance(node.slice, ast.Slice):
            if node.slice.step is not None:
                raise TranspileError(
                    "a slice step is not supported", node, self.filename
                )
            lower = self.expr(node.slice.lower, indent) if node.slice.lower else "0"
            if node.slice.upper is not None:
                upper = self.expr(node.slice.upper, indent)
                return f"{value}.slice({lower}, {upper})"
            return f"{value}.slice({lower})"
        return f"{value}[{self.expr(node.slice, indent)}]"

    def _array(self, elts: list[ast.expr], indent: int) -> str:
        """Emit a JS array literal, multiline when it holds elements.

        Backs Python ``list`` **and** ``tuple`` literals — JS has no tuple type,
        so a tuple becomes a plain (mutable) array; its immutability is not
        enforced in the transpiled output.

        Args:
            elts: The element expressions.
            indent: The current indentation depth.

        Returns:
            The JS array source.
        """
        if not elts:
            return "[]"
        inner = indent + 1
        pad = _INDENT * inner
        items = ",\n".join(f"{pad}{self._element(el, inner)}" for el in elts)
        return "[\n" + items + ",\n" + _INDENT * indent + "]"

    def _element(self, node: ast.expr, indent: int) -> str:
        """Emit one element of a literal, spreading a starred one.

        ``[a, *rest]`` is the idiom for "new list without mutating", so it shows
        up in any app that keeps immutable state; JS spreads with the same
        syntax, which is why the element is the only place that has to know.

        Args:
            node: The element expression.
            indent: The current indentation depth.

        Returns:
            The JS source for the element.
        """
        if isinstance(node, ast.Starred):
            return f"...{self.expr(node.value, indent)}"
        return self.expr(node, indent)

    def _dict(self, node: ast.Dict, indent: int) -> str:
        """Emit a dict literal as a JS object.

        String-constant keys become plain object keys (``"k": v``); any other key
        expression becomes a computed key (``[expr]: v``). A ``**spread`` key
        (which the AST gives as a ``None`` key) becomes an object spread — the
        idiom for replacing one entry without mutating the dict the state still
        holds. Position is preserved, because in both languages a later key wins.
        """
        if not node.keys:
            return "{}"
        pairs: list[str] = []
        for key, value in zip(node.keys, node.values, strict=True):
            if key is None:
                pairs.append(f"...{self.expr(value, indent)}")
                continue
            val = self.expr(value, indent)
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                pairs.append(f"{json.dumps(key.value)}: {val}")
            else:
                pairs.append(f"[{self.expr(key, indent)}]: {val}")
        return "{ " + ", ".join(pairs) + " }"

    def _dictcomp(self, node: ast.DictComp, indent: int) -> str:
        """Emit a dict comprehension via ``Object.fromEntries``.

        ``{k: v for x in it if cond}`` →
        ``Object.fromEntries(it.filter((x) => cond).map((x) => [k, v]))``.
        Only a single ``for`` clause (with optional ``if``s) over a plain-name
        target is supported.
        """
        if len(node.generators) != 1:
            raise TranspileError(
                "only single-loop comprehensions are supported", node, self.filename
            )
        gen = node.generators[0]
        var = self._loop_target(gen.target)
        result = self.expr(gen.iter, indent)
        for cond in gen.ifs:
            result = f"{result}.filter(({var}) => {self.expr(cond, indent)})"
        key = self.expr(node.key, indent)
        value = self.expr(node.value, indent)
        return f"Object.fromEntries({result}.map(({var}) => [{key}, {value}]))"

    def _call(self, node: ast.Call, indent: int) -> str:
        """Emit a call.

        Keyword-only → a single object arg (the widget-builder convention).
        Positional-only → plain args. Mixed (positional + keyword, e.g.
        ``native.http.request("GET", url, json=body)``) → the positional args
        followed by a trailing options object holding the keywords.
        """
        self._refuse_unported_member(node)
        pattern = self._pattern_method(node, indent)
        if pattern is not None:
            return pattern
        stdlib = self._stdlib_call(node, indent)
        if stdlib is not None:
            return stdlib
        builtin = self._builtin_call(node, indent)
        if builtin is not None:
            return builtin
        method = self._method_call(node, indent)
        if method is not None:
            return method
        func = self.expr(node.func, indent)
        if node.keywords and not node.args:
            return self._object_call(func, node, indent)
        parts = [self.expr(a, indent) for a in node.args]
        if node.keywords:
            pairs = []
            for kw in node.keywords:
                if kw.arg is None:
                    raise TranspileError(
                        "**kwargs is not supported", node, self.filename
                    )
                pairs.append(f"{_js_name(kw.arg)}: {self.expr(kw.value, indent)}")
            parts.append("{ " + ", ".join(pairs) + " }")
        args = ", ".join(parts)
        is_class = isinstance(node.func, ast.Name) and (
            node.func.id in self.class_names or node.func.id in _JS_CLASSES
        )
        prefix = "new " if is_class else ""
        return f"{prefix}{func}({args})"

    def _builtin_call(self, node: ast.Call, indent: int) -> str | None:
        """Emit a Python builtin that maps to a JS idiom, or None if not a builtin.

        Supports the pure builtins a ``view`` commonly uses:

        - single-arg casts/measures: ``len(x)`` → ``x.length``, ``str`` →
          ``String``, ``int``/``float`` → ``Number``, ``bool`` → ``Boolean``,
          ``abs`` → ``Math.abs``;
        - ``round(x)`` → ``Math.round(x)``, ``round(x, n)`` →
          ``Number((x).toFixed(n))``;
        - ``min``/``max`` — variadic (``Math.min(a, b)``) or over one iterable
          (``Math.min(...it)``);
        - ``sum(it)`` → ``it.reduce((a, b) => a + b, 0)``;
        - ``range(stop)`` / ``range(start, stop[, step])`` → a materialized array
          (so a comprehension's ``.map``/``.filter`` chain has something to run
          on — JS has no lazy ``range``).

        Keyword arguments are never a builtin here (returns ``None``).
        """
        if not isinstance(node.func, ast.Name) or node.keywords:
            return None
        name = node.func.id
        args = [self.expr(a, indent) for a in node.args]
        count = len(args)
        if name == "range" and count in (1, 2, 3):
            return self._range(args)
        if name == "len" and count == 1:
            return f"{args[0]}.length"
        if name == "round" and count == 1:
            return f"Math.round({args[0]})"
        if name == "round" and count == 2:
            return f"Number(({args[0]}).toFixed({args[1]}))"
        if name == "sum" and count == 1:
            return f"{args[0]}.reduce((a, b) => a + b, 0)"
        if name == "any" and count == 1:
            return f"{args[0]}.some(Boolean)"
        if name == "all" and count == 1:
            return f"{args[0]}.every(Boolean)"
        if name == "enumerate" and count == 1:
            # Python yields (index, value); pair as [index, value] so
            # `for i, v in enumerate(xs)` destructures correctly.
            return f"{args[0]}.map((_v, _i) => [_i, _v])"
        if name == "zip" and count == 2:
            return f"{args[0]}.map((_v, _i) => [_v, {args[1]}[_i]])"
        if name in ("min", "max"):
            js = "Math.min" if name == "min" else "Math.max"
            if count == 1:
                return f"{js}(...{args[0]})"
            if count >= 2:
                return f"{js}({', '.join(args)})"
        if count == 1:
            simple: dict[str, str] = {
                "str": "String",
                "int": "Number",
                "float": "Number",
                "bool": "Boolean",
                "abs": "Math.abs",
            }
            if name in simple:
                return f"{simple[name]}({args[0]})"
            # Container conversions. Without these, `list(xs)` emitted a call to
            # an undefined `list`: the module parsed, the page loaded, and the
            # first render died — a blank screen from a green build.
            if name in ("list", "tuple"):
                return f"[...{args[0]}]"
            if name == "set":
                return f"new Set({args[0]})"
            if name == "dict":
                # A mapping copy and a build-from-pairs are the same call in
                # Python and different operations in JS, and which one it is is
                # only knowable at runtime.
                self.runtime_helpers.add("toDict")
                return f"toDict$({args[0]})"
        if count == 0 and name in ("list", "tuple", "dict", "set"):
            empty = {"list": "[]", "tuple": "[]", "dict": "{}", "set": "new Set()"}
            return empty[name]
        return None

    def _note_regex_binding(self, target: ast.expr, value: ast.expr | None) -> None:
        """Remember a name bound to ``re.compile(...)``.

        A compiled pattern is emitted as a `RegExp`, and `RegExp` has no
        `.match`/`.sub`. Knowing which names hold one is what lets the pattern
        methods route to the helpers without hijacking an unrelated `.match()`.

        Args:
            target: The assignment target.
            value: The assigned expression, if any.
        """
        if not isinstance(target, ast.Name) or not isinstance(value, ast.Call):
            return
        resolved = self._stdlib_target(value.func)
        if resolved == ("re", "compile"):
            self.regex_names.add(target.id)
            return
        if isinstance(value.func, ast.Name):
            origin = self.core_imports.get(value.func.id)
            if origin is not None and getattr(tempest_core, origin, None) is not None:
                self.widget_names[target.id] = origin

    def _pattern_method(self, node: ast.Call, indent: int) -> str | None:
        """Emit a compiled pattern's method call, or None when it is not one.

        Args:
            node: The call node.
            indent: The current indentation depth.

        Returns:
            The JS source, or ``None`` to fall through.

        Raises:
            TranspileError: If the method is not one Mode C maps.
        """
        func = node.func
        if not isinstance(func, ast.Attribute) or not isinstance(func.value, ast.Name):
            return None
        if func.value.id not in self.regex_names:
            return None
        helper = _PATTERN_METHODS.get(func.attr)
        if helper is None:
            raise TranspileError(
                f"`Pattern.{func.attr}` is not available in Mode C "
                f"(mapped: {', '.join(sorted(_PATTERN_METHODS))})",
                node,
                self.filename,
            )
        self.runtime_helpers.add(helper)
        args = [func.value.id, *(self.expr(a, indent) for a in node.args)]
        return f"{helper}$({', '.join(args)})"

    def _stdlib_target(self, func: ast.expr) -> tuple[str, str] | None:
        """Resolve a call target to a ``(module, member)`` pair, or None.

        Covers both import forms: ``re.sub(...)`` through :attr:`module_aliases`
        and ``ceil(...)`` through :attr:`member_aliases`.

        Args:
            func: The callee expression.

        Returns:
            The pair, or ``None`` when this is not a stdlib call.
        """
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            module = self.module_aliases.get(func.value.id)
            if module is not None:
                return (module, func.attr)
        if isinstance(func, ast.Name):
            return self.member_aliases.get(func.id)
        return None

    def _stdlib_call(self, node: ast.Call, indent: int) -> str | None:
        """Emit a stdlib call, or None when the callee is not one.

        Args:
            node: The call node.
            indent: The current indentation depth.

        Returns:
            The JS source, or ``None`` to fall through to the normal path.

        Raises:
            TranspileError: If the module has no such member in Mode C, or the
                call uses keyword arguments the mapping cannot carry.
        """
        target = self._stdlib_target(node.func)
        if target is None:
            return None
        module, member = target
        mapped = _MODULE_CALLS.get(module, {}).get(member)
        if mapped is None:
            raise TranspileError(
                f"`{module}.{member}` is not available in Mode C",
                node,
                self.filename,
            )
        if node.keywords:
            raise TranspileError(
                f"`{module}.{member}` takes no keyword arguments in Mode C",
                node,
                self.filename,
            )
        args = [self.expr(a, indent) for a in node.args]
        if mapped == "@compile":
            if len(args) != 1:
                raise TranspileError(
                    "`re.compile` takes the pattern only (flags are not translated)",
                    node,
                    self.filename,
                )
            return f"new RegExp({args[0]})"
        if mapped.startswith("@"):
            helper = mapped[1:]
            self.runtime_helpers.add(helper)
            return f"{helper}$({', '.join(args)})"
        return f"{mapped}({', '.join(args)})"

    def _refuse_unported_member(self, node: ast.Call) -> None:
        """Refuse `Name.member(...)` when the client's own object lacks `member`.

        ``_served.py`` answers "does the client export this name?"; it cannot
        answer "does that name have this method?". The gap is the same failure
        with a different shape: ``Theme.from_seed(...)`` compiles, parses, loads
        and throws ``is not a function`` at mount — a blank page and one console
        line, which ``node --check`` cannot see because it parses without
        executing.

        Only a bare name imported from the core (or the component facade) is
        checked, and only when it is called as a receiver: a method on a value the
        app built (``app.push``, ``ctrl.forward``) is somebody else's contract.

        Args:
            node: The call node.

        Raises:
            TranspileError: When the member is not in the generated manifest.
        """
        func = node.func
        if not isinstance(func, ast.Attribute) or not isinstance(func.value, ast.Name):
            return
        local = func.value.id
        if local in self.class_names or local not in self.core_imports:
            return
        origin = self.core_imports[local]
        if origin not in SERVED_NAMES:
            return
        if func.attr in VALUE_MEMBERS.get(origin, frozenset()):
            return
        carried = sorted(VALUE_MEMBERS.get(origin, frozenset()))
        has = f" (it carries {', '.join(carried)})" if carried else ""
        raise TranspileError(
            f"`{origin}.{func.attr}()` is not available in Mode C: "
            "the client's own object carries no such member" + has,
            node,
            self.filename,
        )

    def _refuse_widget_method(self, node: ast.Call) -> None:
        """Refuse a method call on a core widget, which Mode C does not carry.

        The client ports each widget's *builder* — a function returning the IR
        node — and none of the Python methods the widget class also has. So a
        method call type-checks, transpiles, and then throws
        ``… is not a function`` on the first render. Compiling something that dies
        is worse than refusing it, which is the whole point of the served-name
        check.

        The exception is :data:`_WIDGET_METHODS`, the methods the client does
        carry: those are routed to their helper instead of refused.

        Args:
            node: The call node.

        Raises:
            TranspileError: When the receiver is a name bound to a core widget.
        """
        func = node.func
        if not isinstance(func, ast.Attribute) or not isinstance(func.value, ast.Name):
            return
        widget = self.widget_names.get(func.value.id)
        if widget is None or func.attr in _WIDGET_METHODS:
            return
        raise TranspileError(
            f"`{widget}.{func.attr}()` is not available in Mode C: the client "
            "ports each widget's builder, not the widget's Python methods",
            node,
            self.filename,
        )

    def _facade_rooted(self, node: ast.expr) -> bool:
        """Whether an expression is rooted at the native-capability facade.

        `native.storage.get(name)` and `native.geolocation.get()` are real facade
        calls, so the dict mapping below must not touch them.

        Args:
            node: The receiver expression.

        Returns:
            Whether its root name is the facade namespace.
        """
        current = node
        while True:
            if isinstance(current, ast.Call):
                current = current.func
            elif isinstance(current, (ast.Attribute, ast.Subscript)):
                current = current.value
            else:
                break
        if not isinstance(current, ast.Name):
            return False
        return current.id in self.native_imports or current.id in self.native_aliases

    def _dict_get(self, node: ast.Call, indent: int) -> str | None:
        """Map `d.get(key)` / `d.get(key, default)` to an indexed read.

        A dict is emitted as a plain object, which has no `.get`, so
        `state.errors.get("email", "")` shipped a page that died on the first
        render (measured in `signup-wizard`). `??` and not `||`, because
        Python's `.get` returns a stored falsy value — `0`, `""` — rather than
        the default.

        A `get` the module declares as a dataclass field is an attribute and not
        a dict read: `examples/file-storage` injects `storage.get` into its state
        and calls `app.state.get(key)`, which this mapping turned into
        `app.state[key]` — valid JS that silently returns undefined.

        Args:
            node: The call node.
            indent: The current indentation depth.

        Returns:
            The JS source, or ``None`` when this is not a dict read.
        """
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "get":
            return None
        if len(node.args) not in (1, 2) or self._facade_rooted(func.value):
            return None
        if func.attr in self.field_names:
            return None
        receiver = self.expr(func.value, indent)
        key = self.expr(node.args[0], indent)
        if len(node.args) == 1:
            return f"{receiver}[{key}]"
        default = self.expr(node.args[1], indent)
        return f"({receiver}[{key}] ?? {default})"

    def _method_call(self, node: ast.Call, indent: int) -> str | None:
        """Map a Python stdlib method call to its JS idiom, or None to pass through.

        Handles string/list methods that rename cleanly (``s.upper()`` →
        ``s.toUpperCase()``, ``xs.append(x)`` → ``xs.push(x)``), dict views
        (``d.items()`` → ``Object.entries(d)``, ``.keys``/``.values``) and
        ``sep.join(it)`` → ``it.join(sep)`` (receiver/argument swap). Any other
        method call returns ``None`` so it emits unchanged — runtime/facade
        methods (``app.push``, ``native.storage.get``, ``ctrl.forward``) are left
        alone.
        """
        if not isinstance(node.func, ast.Attribute) or node.keywords:
            return None
        mapping = self._dict_get(node, indent)
        if mapping is not None:
            return mapping
        self._refuse_widget_method(node)
        method = node.func.attr
        receiver = self.expr(node.func.value, indent)
        args = [self.expr(a, indent) for a in node.args]
        if method in _WIDGET_METHODS and len(args) == 1:
            helper = _WIDGET_METHODS[method]
            self.runtime_helpers.add(helper)
            return f"{helper}$({receiver}, {args[0]})"
        if method == "pop" and len(args) == 2:
            # `dict.pop(key, default)`. A dict is a plain object, so the name
            # resolved to nothing at all and threw on the first call.
            self.runtime_helpers.add("dictPop")
            return f"dictPop$({receiver}, {args[0]}, {args[1]})"
        if method in _METHOD_RENAMES:
            return f"{receiver}.{_METHOD_RENAMES[method]}({', '.join(args)})"
        if not args and method in _STRING_TESTS:
            pattern, helper = _STRING_TESTS[method]
            self.runtime_helpers.add(helper)
            return f"{helper}$({pattern!r}, {receiver}) !== null".replace("'", '"')
        if not args and method in ("items", "keys", "values"):
            js = "entries" if method == "items" else method
            return f"Object.{js}({receiver})"
        if method == "join" and len(args) == 1:
            return f"{args[0]}.join({receiver})"
        return None

    @staticmethod
    def _range(args: list[str]) -> str:
        """Materialize a Python ``range(...)`` as a JS array.

        Args:
            args: The already-emitted JS for 1–3 range arguments
                (``stop`` | ``start, stop`` | ``start, stop, step``).

        Returns:
            An ``Array.from(...)`` expression producing the same integers.
        """
        if len(args) == 1:
            return f"Array.from({{ length: {args[0]} }}, (_, i) => i)"
        start, stop = args[0], args[1]
        step = args[2] if len(args) == 3 else "1"
        length = f"Math.max(0, Math.ceil(({stop} - {start}) / {step}))"
        return f"Array.from({{ length: {length} }}, (_, i) => {start} + i * {step})"

    def _core_target(self, node: ast.Call) -> object | None:
        """Resolve the ``tempest_core`` object a bare-name call refers to.

        Args:
            node: The call being emitted.

        The name is looked up on ``tempest_core`` first and then on
        ``tempestweb.components``, because the facade both re-exports the core's
        components *and* adds this repo's own (``LoginForm``, ``TextField``).
        Missing the second lookup meant a facade-only component resolved to
        nothing: its props kept the wire's snake_case, the generated builder
        destructures camelCase, and every handler was dropped in silence.

        Returns:
            The live component object, or ``None`` when the call is not a bare
            name imported from one of those modules (a locally declared class
            wins over the import, exactly as in Python).
        """
        if not isinstance(node.func, ast.Name):
            return None
        local = node.func.id
        if local in self.class_names or local not in self.core_imports:
            return None
        origin = self.core_imports[local]
        target = getattr(tempest_core, origin, None)
        if target is None:
            target = getattr(tempestweb_components, origin, None)
        return target

    def _check_core_kwargs(self, node: ast.Call, target: object | None) -> None:
        """Refuse a keyword the called core model does not declare.

        Mode C has no Python at runtime, so nothing revalidates the call: the
        generated builder destructures the object it is handed and ignores every
        key it does not name. A kwarg the core would refuse therefore turns into
        silence — ``Container(children=[...])`` renders an empty box in Mode C
        and raises ``ValidationError`` the moment the same view is served by
        Mode A or B. Checking here restores the core's answer at build time,
        where it costs nothing at runtime and names the file and line.

        Only a bare-name call of something imported from ``tempest_core`` is
        checked, and only when it resolves to a model with declared fields; a
        helper function (``t``, ``material_icon``) and a locally declared class
        are somebody else's contract.

        Args:
            node: The call being emitted.
            target: The core object the call resolves to, or ``None``.

        Raises:
            TranspileError: If a keyword is not a field of the model, listing
                the widget's real child slot when that is what was meant.
        """
        if target is None or not isinstance(node.func, ast.Name):
            return
        local = node.func.id
        origin = self.core_imports.get(local, local)
        if origin not in SERVED_NAMES:
            self._refuse_unserved(origin, node)
        fields: Any = getattr(target, "model_fields", None)
        if not isinstance(fields, dict) or not fields:
            return
        accepted = set(fields)
        for finfo in fields.values():
            alias = getattr(finfo, "alias", None)
            if isinstance(alias, str):
                accepted.add(alias)
        slots = sorted(getattr(target, "child_field_names", ()) or ())
        for kw in node.keywords:
            if kw.arg is None or kw.arg in accepted:
                continue
            hint = ""
            if kw.arg in {"child", "children"} and slots:
                slot_list = ", ".join(f"`{slot}`" for slot in slots)
                hint = f" (its child slot is {slot_list})"
            raise TranspileError(
                f"`{local}` does not accept `{kw.arg}`{hint}",
                node,
                self.filename,
            )

    def _object_call(self, func: str, node: ast.Call, indent: int) -> str:
        """Emit a widget-style call whose kwargs become a single object arg.

        Multiline when a keyword's value spans lines (e.g. a non-empty `children`
        list); inline otherwise.
        """
        target = self._core_target(node)
        self._check_core_kwargs(node, target)
        # A widget's props are camelCase in its generated builder; `Style`/`Color`
        # keep the wire's snake_case keys, so only widgets are renamed by rule.
        camel = isinstance(target, type) and issubclass(target, tempest_core.Widget)
        pairs: list[tuple[str, str]] = []
        for kw in node.keywords:
            if kw.arg is None:
                raise TranspileError("**kwargs is not supported", node, self.filename)
            key = _camel_name(kw.arg) if camel else _js_name(kw.arg)
            pairs.append((key, self.expr(kw.value, indent + 1)))
        # A keyword-only call of a class (a dataclass, or an imported JS class like
        # Route) is a constructor — `new Route({ name })`, not `Route({ name })`.
        is_class = isinstance(node.func, ast.Name) and (
            node.func.id in self.class_names or node.func.id in _JS_CLASSES
        )
        prefix = "new " if is_class else ""
        multiline = any("\n" in value for _, value in pairs)
        if not multiline:
            body = ", ".join(f"{key}: {value}" for key, value in pairs)
            return f"{prefix}{func}({{ {body} }})"
        inner = indent + 1
        pad = _INDENT * inner
        lines = ",\n".join(f"{pad}{key}: {value}" for key, value in pairs)
        return f"{prefix}{func}({{\n{lines},\n{_INDENT * indent}}})"

    def _lambda(self, node: ast.Lambda, indent: int) -> str:
        """Emit an arrow function.

        A ``setattr(obj, "name", value)`` body (an in-place state mutation) is
        emitted as a block arrow with a single assignment; any other supported
        expression body becomes a concise expression arrow — e.g.
        ``lambda s: s.increment()`` → ``(s) => s.increment()``.
        """
        params = ", ".join(_param_names(node.args, node, self.filename))
        body = node.body
        if (
            isinstance(body, ast.Call)
            and isinstance(body.func, ast.Name)
            and body.func.id == "setattr"
            and len(body.args) == 3
            and isinstance(body.args[1], ast.Constant)
            and isinstance(body.args[1].value, str)
        ):
            target = self.expr(body.args[0], indent)
            attr = body.args[1].value
            value = self.expr(body.args[2], indent)
            inner = _INDENT * (indent + 1)
            close = _INDENT * indent
            return f"({params}) => {{\n{inner}{target}.{attr} = {value};\n{close}}}"
        return f"({params}) => {self.expr(body, indent)}"

    # -- statements ---------------------------------------------------------

    def stmt(self, node: ast.stmt, indent: int) -> list[str]:
        """Emit JS lines for a statement.

        Args:
            node: The statement AST node.
            indent: Current indentation depth.

        Returns:
            The emitted JS lines (already indented).

        Raises:
            TranspileError: If the statement is outside the subset.
        """
        if isinstance(node, ast.Return):
            return self._return(node, indent)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return self._nested_def(node, indent)
        if isinstance(node, ast.Expr):
            return [f"{_INDENT * indent}{self.expr(node.value, indent)};"]
        if isinstance(node, ast.If):
            return self._if(node, indent)
        if isinstance(node, ast.For):
            return self._for(node, indent)
        if isinstance(node, ast.While):
            return self._while(node, indent)
        if isinstance(node, (ast.With, ast.AsyncWith)):
            return self._with(node, indent)
        if isinstance(node, ast.Try):
            return self._try(node, indent)
        if isinstance(node, ast.Raise):
            return self._raise(node, indent)
        if isinstance(node, ast.Assert):
            return self._assert(node, indent)
        if isinstance(node, ast.Break):
            return [f"{_INDENT * indent}break;"]
        if isinstance(node, ast.Continue):
            return [f"{_INDENT * indent}continue;"]
        if isinstance(node, ast.Assign):
            return self._assign(node, indent)
        if isinstance(node, ast.AugAssign):
            return self._augassign(node, indent)
        if isinstance(node, ast.AnnAssign):
            return self._annassign(node, indent)
        if isinstance(node, ast.Pass):
            return []
        raise TranspileError(
            f"statement {type(node).__name__} is not supported", node, self.filename
        )

    def _if(self, node: ast.If, indent: int) -> list[str]:
        """Emit an ``if`` / ``elif`` / ``else`` chain as JS if / else-if / else."""
        pad = _INDENT * indent
        lines = [f"{pad}if ({self.expr(node.test, indent)}) {{"]
        lines.extend(self._body(node.body, indent + 1))
        orelse = node.orelse
        # A single nested If in orelse is an ``elif`` — chain it as ``else if``.
        while len(orelse) == 1 and isinstance(orelse[0], ast.If):
            elif_node = orelse[0]
            lines.append(f"{pad}}} else if ({self.expr(elif_node.test, indent)}) {{")
            lines.extend(self._body(elif_node.body, indent + 1))
            orelse = elif_node.orelse
        if orelse:
            lines.append(f"{pad}}} else {{")
            lines.extend(self._body(orelse, indent + 1))
        lines.append(f"{pad}}}")
        return lines

    def _loop_target(self, target: ast.expr) -> str:
        """Return the JS binding for a for/comprehension target.

        A plain name binds directly (``x``); a tuple/list unpacks with array
        destructuring (``[k, v]``).
        """
        return self._target_pattern(target)

    def _target_pattern(self, target: ast.expr) -> str:
        """Return the JS destructuring pattern for a binding target.

        Nested as deep as the Python target goes, because
        ``for i, (question, answer) in enumerate(pairs)`` is how an app walks a
        table of pairs — and JS destructures it with the same shape.

        Args:
            target: A ``Name``, or a ``Tuple``/``List`` of targets.

        Returns:
            The JS pattern (``x`` or ``[i, [question, answer]]``).

        Raises:
            TranspileError: If a leaf is not a plain name.
        """
        if isinstance(target, ast.Name):
            return target.id
        if isinstance(target, (ast.Tuple, ast.List)):
            inner = ", ".join(self._target_pattern(elt) for elt in target.elts)
            return f"[{inner}]"
        raise TranspileError(
            "a binding target must be a name, or a tuple/list of them",
            target,
            self.filename,
        )

    def _for(self, node: ast.For, indent: int) -> list[str]:
        """Emit a ``for x in it:`` as ``for (const x of it) {...}``.

        A tuple target (``for k, v in items``) destructures each element.
        """
        if node.orelse:
            raise TranspileError("for/else is not supported", node, self.filename)
        pad = _INDENT * indent
        binding = self._loop_target(node.target)
        iterable = self.expr(node.iter, indent)
        lines = [f"{pad}for (const {binding} of {iterable}) {{"]
        lines.extend(self._body(node.body, indent + 1))
        lines.append(f"{pad}}}")
        return lines

    @staticmethod
    def _exc_class_name(node: ast.expr) -> str | None:
        """Return the exception class name of a ``raise`` target, or None."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return None

    def _raise(self, node: ast.Raise, indent: int) -> list[str]:
        """Emit a ``raise`` as a JS ``throw``.

        ``raise Exc("msg")`` / ``raise Exc`` throw an ``Error`` whose ``message``
        is the first argument (empty otherwise) and whose ``name`` is the
        exception class name — so a matching ``except Exc`` (which dispatches on
        ``err.name``) catches it. A bare ``raise`` re-throws the exception the
        enclosing ``except`` caught. ``raise ... from ...`` is unsupported.
        """
        pad = _INDENT * indent
        if node.exc is None:
            if not self._exc_vars:
                raise TranspileError(
                    "bare `raise` is only valid inside an `except` block",
                    node,
                    self.filename,
                )
            return [f"{pad}throw {self._exc_vars[-1]};"]
        if node.cause is not None:
            raise TranspileError(
                "`raise ... from ...` is not supported", node, self.filename
            )
        exc = node.exc
        if isinstance(exc, ast.Call):
            name = self._exc_class_name(exc.func)
            message = self.expr(exc.args[0], indent) if exc.args else '""'
        else:
            name = self._exc_class_name(exc)
            message = '""'
        if name is None:
            raise TranspileError(
                "`raise` expects an exception class (name)", node, self.filename
            )
        error = f'Object.assign(new Error({message}), {{ name: "{name}" }})'
        return [f"{pad}throw {error};"]

    def _assert(self, node: ast.Assert, indent: int) -> list[str]:
        """Emit ``assert cond[, msg]`` as ``if (!(cond)) throw AssertionError``."""
        pad = _INDENT * indent
        test = self.expr(node.test, indent)
        message = self.expr(node.msg, indent) if node.msg is not None else '""'
        error = f'Object.assign(new Error({message}), {{ name: "AssertionError" }})'
        inner = _INDENT * (indent + 1)
        return [f"{pad}if (!({test})) {{", f"{inner}throw {error};", f"{pad}}}"]

    def _while(self, node: ast.While, indent: int) -> list[str]:
        """Emit a ``while cond:`` loop as ``while (cond) {...}``.

        ``while/else`` is unsupported (the ``else`` runs only when the loop is not
        broken — a rare form with no clean JS equivalent).
        """
        if node.orelse:
            raise TranspileError("while/else is not supported", node, self.filename)
        pad = _INDENT * indent
        lines = [f"{pad}while ({self.expr(node.test, indent)}) {{"]
        lines.extend(self._body(node.body, indent + 1))
        lines.append(f"{pad}}}")
        return lines

    def _with(self, node: ast.With | ast.AsyncWith, indent: int) -> list[str]:
        """Emit a ``with cm as x:`` via the context-manager protocol.

        Mirrors Python faithfully for managers that expose ``__enter__`` /
        ``__exit__`` (a transpiled dataclass with those methods qualifies):
        ``x = cm.__enter__()`` then a ``try/finally`` whose ``finally`` calls
        ``cm.__exit__(null, null, null)``. An ``async with`` awaits both. Only a
        single context manager is supported; ``as`` must bind a plain name.
        """
        if len(node.items) != 1:
            raise TranspileError(
                "only a single context manager is supported in `with`",
                node,
                self.filename,
            )
        item = node.items[0]
        is_async = isinstance(node, ast.AsyncWith)
        awaited = "await " if is_async else ""
        enter = "__aenter__" if is_async else "__enter__"
        exit_ = "__aexit__" if is_async else "__exit__"
        pad = _INDENT * indent
        inner = indent + 1
        ipad = _INDENT * inner
        manager = self.expr(item.context_expr, indent)
        lines = [f"{pad}{{", f"{ipad}const _cm = {manager};"]
        if item.optional_vars is not None:
            if not isinstance(item.optional_vars, ast.Name):
                raise TranspileError(
                    "`with ... as <name>` must bind a plain name",
                    node,
                    self.filename,
                )
            target = _js_name(item.optional_vars.id)
            lines.append(f"{ipad}{target} = {awaited}_cm.{enter}();")
        else:
            lines.append(f"{ipad}{awaited}_cm.{enter}();")
        lines.append(f"{ipad}try {{")
        lines.extend(self._body(node.body, inner + 1))
        lines.append(f"{ipad}}} finally {{")
        lines.append(f"{_INDENT * (inner + 1)}{awaited}_cm.{exit_}(null, null, null);")
        lines.append(f"{ipad}}}")
        lines.append(f"{pad}}}")
        return lines

    @staticmethod
    def _is_catch_all(handler: ast.ExceptHandler) -> bool:
        """Whether an ``except`` clause catches everything (bare / broad)."""
        return handler.type is None or (
            isinstance(handler.type, ast.Name)
            and handler.type.id in ("Exception", "BaseException")
        )

    def _exc_name(self, local: str) -> str:
        """Return the name an exception class carries at runtime.

        Args:
            local: The name the module refers to the class by.

        Returns:
            The exported name it was imported from, or the local name when the
            module declares the class itself.
        """
        return self.native_imports.get(local) or self.core_imports.get(local, local)

    def _exc_condition(self, type_node: ast.expr, var: str) -> str:
        """Build the JS test matching an ``except`` type against a caught error.

        Match is by exception **class name** (``err.name === "ValueError"`` /
        ``["A","B"].includes(err.name)``) — JS has no Python exception classes,
        so a browser/JS error (whose ``name`` is e.g. ``"TypeError"``) only
        matches when the names coincide. The name compared is the one the class
        carries at runtime, so ``except NativeError as Failure`` still matches:
        an aliased import tested against its local name never fired.
        """
        if isinstance(type_node, ast.Name):
            return f'{var}.name === "{self._exc_name(type_node.id)}"'
        if isinstance(type_node, ast.Tuple) and all(
            isinstance(elt, ast.Name) for elt in type_node.elts
        ):
            names = ", ".join(
                f'"{self._exc_name(elt.id)}"'
                for elt in type_node.elts
                if isinstance(elt, ast.Name)
            )
            return f"[{names}].includes({var}.name)"
        raise TranspileError(
            "unsupported except type; use `except Name` or `except (A, B)`",
            type_node,
            self.filename,
        )

    def _catch(self, handlers: list[ast.ExceptHandler], indent: int) -> list[str]:
        """Emit the ``} catch (...) { ... }`` block for a try's handlers.

        A single ``except`` catches any error (the declared type is
        informational — pragmatic for Mode C, where errors are JS errors).
        Multiple ``except`` clauses dispatch by exception class name, in order,
        with a trailing broad/bare clause as the ``else`` — or ``throw`` to
        re-raise when none matches (faithful propagation).
        """
        pad = _INDENT * indent
        body_indent = indent + 1
        bpad = _INDENT * body_indent
        if len(handlers) == 1 and self._is_catch_all(handlers[0]):
            handler = handlers[0]
            var = handler.name or "_err"
            lines = [f"{pad}}} catch ({var}) {{"]
            lines.extend(self._handler_body(handler.body, body_indent, var))
            return lines

        alias_pad = _INDENT * (body_indent + 1)
        lines = [f"{pad}}} catch (_err) {{"]
        catch_all = next((h for h in handlers if self._is_catch_all(h)), None)
        typed = [h for h in handlers if not self._is_catch_all(h)]
        keyword = "if"
        for handler in typed:
            # `typed` excludes catch-all handlers, so the type is always present.
            assert handler.type is not None
            cond = self._exc_condition(handler.type, "_err")
            lines.append(f"{bpad}{keyword} ({cond}) {{")
            if handler.name:
                lines.append(f"{alias_pad}const {handler.name} = _err;")
            lines.extend(self._handler_body(handler.body, body_indent + 1, "_err"))
            keyword = "} else if"
        lines.append(f"{bpad}}} else {{")
        if catch_all is not None:
            if catch_all.name:
                lines.append(f"{alias_pad}const {catch_all.name} = _err;")
            lines.extend(self._handler_body(catch_all.body, body_indent + 1, "_err"))
        else:
            lines.append(f"{alias_pad}throw _err;")
        lines.append(f"{bpad}}}")
        return lines

    def _handler_body(
        self, body: list[ast.stmt], indent: int, exc_var: str
    ) -> list[str]:
        """Emit an ``except`` body with its caught-error var on the re-raise stack.

        Args:
            body: The handler statements.
            indent: The body indentation depth.
            exc_var: The JS variable bound to the caught error (for a bare
                ``raise`` inside the handler).

        Returns:
            The emitted lines.
        """
        self._exc_vars.append(exc_var)
        try:
            return self._body(body, indent)
        finally:
            self._exc_vars.pop()

    def _try(self, node: ast.Try, indent: int) -> list[str]:
        """Emit a ``try/except/finally`` as JS ``try/catch/finally``.

        A single ``except`` catches everything (type informational); multiple
        clauses dispatch by exception class name (see :meth:`_catch`).
        ``try/else`` (runs only when no exception fired) is unsupported.
        """
        if node.orelse:
            raise TranspileError("try/else is not supported", node, self.filename)
        pad = _INDENT * indent
        lines = [f"{pad}try {{"]
        lines.extend(self._body(node.body, indent + 1))
        if node.handlers:
            lines.extend(self._catch(node.handlers, indent))
        if node.finalbody:
            lines.append(f"{pad}}} finally {{")
            lines.extend(self._body(node.finalbody, indent + 1))
        lines.append(f"{pad}}}")
        return lines

    def _target_names(self, target: ast.expr) -> list[str]:
        """Return the plain names bound by a tuple/list unpacking target.

        Args:
            target: A ``Tuple``/``List`` of ``Name`` elements.

        Returns:
            The bound names, in order.

        Raises:
            TranspileError: If an element is not a plain name (nested/starred
                unpacking is unsupported).
        """
        names: list[str] = []
        for elt in target.elts:  # type: ignore[attr-defined]
            if isinstance(elt, ast.Name):
                names.append(elt.id)
            elif isinstance(elt, (ast.Tuple, ast.List)):
                names.extend(self._target_names(elt))
            else:
                raise TranspileError(
                    "unpacking binds plain names, nested as deep as you like, "
                    f"but not a {type(elt).__name__}",
                    target,
                    self.filename,
                )
        return names

    def _assign(self, node: ast.Assign, indent: int) -> list[str]:
        """Emit an assignment.

        A single ``Name`` target is ``const`` (or a plain assign when hoisted);
        an attribute/subscript target is a plain assignment. A tuple/list target
        (``a, b = pair``) becomes array destructuring. Chained assignment
        (``a = b = 1``) assigns each target to the same value.
        """
        value = self.expr(node.value, indent)
        pad = _INDENT * indent
        lines: list[str] = []
        for target in node.targets:
            self._note_regex_binding(target, node.value)
            lines.extend(self._assign_target(target, value, pad, indent))
        return lines

    def _assign_target(
        self, target: ast.expr, value: str, pad: str, indent: int
    ) -> list[str]:
        """Emit one assignment of ``value`` to a single target."""
        if isinstance(target, ast.Name):
            # A hoisted name (function-top `let`) is assigned plainly; otherwise
            # `const`.
            if self._scopes and target.id in self._scopes[-1]:
                return [f"{pad}{target.id} = {value};"]
            return [f"{pad}const {target.id} = {value};"]
        if isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Slice):
            return [self._slice_assign(target, value, pad, indent)]
        if isinstance(target, (ast.Attribute, ast.Subscript)):
            return [f"{pad}{self.expr(target, indent)} = {value};"]
        if isinstance(target, (ast.Tuple, ast.List)):
            names = self._target_names(target)
            pattern = self._target_pattern(target)
            hoisted = self._scopes and all(n in self._scopes[-1] for n in names)
            if hoisted:
                # Destructuring assignment (no declaration) must be parenthesized.
                return [f"{pad}({pattern} = {value});"]
            return [f"{pad}const {pattern} = {value};"]
        raise TranspileError(
            f"assignment target {type(target).__name__} is not supported",
            target,
            self.filename,
        )

    def _slice_assign(
        self, target: ast.Subscript, value: str, pad: str, indent: int
    ) -> str:
        """Emit ``xs[:] = value`` as an in-place replacement.

        A slice *reads* as ``.slice(...)``, so routing the assignment through the
        expression emitter produced ``xs.slice(0) = [...]``. That parses — which
        is why ``node --check`` passed — and throws ``Invalid left-hand side in
        assignment`` on the first run: measured in ``examples/router-drawer``,
        whose drawer navigation silently did nothing.

        Only the whole slice is supported. A partial one (``xs[1:3] = [...]``)
        can grow or shrink the list, and quietly getting that wrong is worse than
        refusing it.

        Args:
            target: The subscript being assigned to.
            value: The already-emitted JS for the right-hand side.
            pad: The current indentation prefix.
            indent: The current indentation depth.

        Returns:
            The JS statement replacing the list's contents.

        Raises:
            TranspileError: For a slice with bounds or a step.
        """
        piece = target.slice
        assert isinstance(piece, ast.Slice)
        if piece.lower is not None or piece.upper is not None or piece.step is not None:
            raise TranspileError(
                "a partial slice assignment (`xs[a:b] = …`) is not supported "
                "(assign the whole slice, `xs[:] = …`, or rebind the name)",
                target,
                self.filename,
            )
        seq = self.expr(target.value, indent)
        return f"{pad}{seq}.splice(0, {seq}.length, ...{value});"

    def _annassign(self, node: ast.AnnAssign, indent: int) -> list[str]:
        """Emit an annotated assignment (``total: int = 0`` → ``const total = 0;``).

        The annotation itself has no JS counterpart and is dropped; the *value*
        must not be. This used to be grouped with ``pass`` and emitted nothing at
        all, so a typed local — which this repo's own style rules ask for — was
        silently deleted from the generated module and only surfaced in the
        browser as ``ReferenceError: <name> is not defined``.

        A bare declaration with no value (``total: int``) is a type statement
        with nothing to run, so it still emits nothing.

        The annotated form also records the same bindings the bare one does —
        which name holds a compiled pattern, which holds a core widget — because
        a typed local is the spelling this repo's style rules ask for, and losing
        the binding meant emitting a method call that dies at runtime.

        Args:
            node: The annotated assignment.
            indent: The current indentation depth.

        Returns:
            The emitted JS lines (empty for a value-less declaration).
        """
        if node.value is None:
            return []
        # The annotated form is what this repo's own style rules ask for, so it
        # has to feed the same bindings the bare one does — otherwise a typed
        # `re.Pattern` or `Form` local is invisible and its methods emit raw JS
        # that dies on the first call.
        self._note_regex_binding(node.target, node.value)
        value = self.expr(node.value, indent)
        return self._assign_target(node.target, value, _INDENT * indent, indent)

    def _augassign(self, node: ast.AugAssign, indent: int) -> list[str]:
        """Emit an augmented assignment (``x += 1`` → ``x += 1;``)."""
        ops: dict[type[ast.operator], str] = {
            ast.Add: "+=",
            ast.Sub: "-=",
            ast.Mult: "*=",
            ast.Div: "/=",
            ast.Mod: "%=",
        }
        op = ops.get(type(node.op))
        if op is None:
            raise TranspileError(
                f"augmented operator {type(node.op).__name__} is not supported",
                node,
                self.filename,
            )
        pad = _INDENT * indent
        target = self.expr(node.target, indent)
        value = self.expr(node.value, indent)
        return [f"{pad}{target} {op} {value};"]

    def _return(self, node: ast.Return, indent: int) -> list[str]:
        """Emit a return statement."""
        if node.value is None:
            return [f"{_INDENT * indent}return;"]
        return [f"{_INDENT * indent}return {self.expr(node.value, indent)};"]

    def _nested_def(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, indent: int
    ) -> list[str]:
        """Emit a nested `def` as a `const name = (params) => {...}` arrow.

        An `async def` becomes an `async` arrow, so `await` inside it is valid.
        """
        _reject_fn_decorators(node, self.filename)
        params = ", ".join(_param_names(node.args, node, self.filename))
        pad = _INDENT * indent
        prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
        lines = [f"{pad}const {_js_name(node.name)} = {prefix}({params}) => {{"]
        lines.extend(self._emit_fn_body(node.body, indent + 1))
        lines.append(f"{pad}}};")
        return lines

    def _emit_fn_body(self, body: list[ast.stmt], indent: int) -> list[str]:
        """Emit a function body, hoisting its assigned names to a top `let`.

        Names assigned inside ``if``/``for`` blocks are declared once at the top
        so they follow Python's function scoping rather than being trapped in a
        JS block by ``const``. Top-level-only names stay ``const``. Nested
        function scopes are not descended into.

        Args:
            body: The function's statements.
            indent: The body indentation depth.

        Returns:
            The emitted lines, a leading ``let`` declaration first when needed.
        """
        stmts = self._strip_docstring(body)
        names = sorted(_hoisted_names(stmts))
        self._scopes.append(set(names))
        lines: list[str] = []
        if names:
            lines.append(f"{_INDENT * indent}let {', '.join(names)};")
        for stmt in stmts:
            lines.extend(self.stmt(stmt, indent))
        self._scopes.pop()
        return lines

    def _body(self, body: list[ast.stmt], indent: int) -> list[str]:
        """Emit the statements of a block, dropping a leading docstring."""
        stmts = self._strip_docstring(body)
        lines: list[str] = []
        for stmt in stmts:
            lines.extend(self.stmt(stmt, indent))
        return lines

    @staticmethod
    def _strip_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
        """Return `body` without a leading string-expression docstring."""
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            return body[1:]
        return body

    # -- top level ----------------------------------------------------------

    def module(self, tree: ast.Module) -> str:
        """Emit the whole module: imports, then classes and functions.

        A class declared here shadows the import of the same name: emitting both
        would declare the identifier twice, which is a JS ``SyntaxError`` that
        takes the whole module down. The local declaration wins, matching Python,
        so shadowed names are dropped from the import list. The injected dataclass
        base is the one name that cannot simply be dropped — it is still needed as
        the base — so a module declaring its own ``State`` imports the runtime one
        under :data:`_STATE_BASE_ALIAS`.

        Args:
            tree: The parsed module AST.

        Returns:
            The complete generated JS source (trailing newline included).
        """
        # `State` is the injected base of every emitted dataclass — always
        # importable regardless of what the source module imported.
        importable: set[str] = {"State"}
        top_level: list[ast.stmt] = []
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                self._collect_imports(node, importable)
            elif isinstance(node, ast.ClassDef):
                self.class_names.add(node.name)
                self.field_names.update(
                    stmt.target.id
                    for stmt in node.body
                    if isinstance(stmt, ast.AnnAssign)
                    and isinstance(stmt.target, ast.Name)
                )
                top_level.append(node)
            elif isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.Assign, ast.AnnAssign),
            ):
                top_level.append(node)
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                continue  # module docstring
            elif isinstance(node, ast.If) and _is_main_guard(node.test):
                if node.orelse:
                    raise TranspileError(
                        'the `else` of an `if __name__ == "__main__":` guard runs '
                        "on import, so Mode C cannot drop it with the guard "
                        "(move it to module level)",
                        node,
                        self.filename,
                    )
                continue  # a script guard: dead in a module, in Python too
            else:
                raise TranspileError(
                    f"top-level {type(node).__name__} is not supported",
                    node,
                    self.filename,
                )

        if "State" in self.class_names:
            self.state_base = _STATE_BASE_ALIAS
        importable -= self.class_names

        # Emit bodies first so `referenced` reflects what the output actually
        # uses; `State` is the injected base of every emitted dataclass.
        bodies: list[str] = []
        for node in top_level:
            if isinstance(node, ast.ClassDef):
                bodies.append(self._class(node))
                self.referenced.add(self.state_base)
            elif isinstance(node, ast.Assign | ast.AnnAssign):
                if self._is_type_alias(node):
                    continue
                bodies.append(self._module_const(node))
            else:
                assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                bodies.append(self._function(node))

        imports = self._imports(self.referenced & importable)
        tables = [
            self._native_enum(local, name)
            for local, name in sorted(self.native_enums.items())
            if local in self.referenced
        ]
        return "\n\n".join([imports, *tables, *bodies]) + "\n"

    def _native_enum(self, local: str, name: str) -> str:
        """Emit a native string enum as the frozen table Mode C compares against.

        The facade returns the raw JSON value — ``"granted"``, not a Python
        member — so ``perm is NotificationPermission.GRANTED`` is a string
        comparison once both sides are emitted. The table is what makes the
        member name resolvable.

        Args:
            local: The name the module bound it to.
            name: The enum as the native package spells it.

        Returns:
            The ``const X = Object.freeze({...});`` source.
        """
        members = "\n".join(
            f"{_INDENT}{member}: {json.dumps(value)},"
            for member, value in sorted(NATIVE_ENUMS[name].items())
        )
        return f"const {local} = Object.freeze({{\n{members}\n}});"

    def _module_const(self, node: ast.Assign | ast.AnnAssign) -> str:
        """Emit a module-level constant (e.g. a translations table) as `const`.

        A single ``NAME = value`` or annotated ``NAME: T = value`` becomes a
        top-level ``const NAME = value;``. Tuple/multiple targets are unsupported.
        """
        target: ast.expr
        value: ast.expr | None
        if isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
            self._note_regex_binding(target, value)
        else:
            if len(node.targets) != 1:
                raise TranspileError(
                    "multiple assignment targets are not supported",
                    node,
                    self.filename,
                )
            target, value = node.targets[0], node.value
            self._note_regex_binding(target, value)
        if not isinstance(target, ast.Name) or value is None:
            raise TranspileError(
                "only a single named module constant with a value is supported",
                node,
                self.filename,
            )
        return f"const {target.id} = {self.expr(value, 0)};"

    def _is_type_alias(self, node: ast.Assign | ast.AnnAssign) -> bool:
        """Whether a module-level assignment is a type alias, and record it.

        A module that annotates handlers writes aliases like
        ``Fetcher = Callable[[], Awaitable[list[str]]]``. That is an assignment of
        runtime syntax built out of type-only names and builtin generics, so
        emitting it would reference identifiers nothing imports. The target joins
        :attr:`type_only`, which keeps it usable in the annotations the emitter
        drops and refused in a value position.

        A name that is neither type-only nor a builtin means the value carries a
        real runtime term, so the assignment is a constant and not an alias —
        ``LIMIT = MAX_ROWS`` stays an emitted ``const``. A native string enum is
        tolerated as a leaf, because ``Callable[[], Awaitable[Permission]]`` is
        annotation syntax whichever way its parameter is spelled; it takes a
        type-only head for the assignment to be read as an alias at all, so a
        real constant built from an enum member is still emitted.

        Args:
            node: The module-level assignment.

        Returns:
            Whether the assignment is a type alias (and was recorded as one).
        """
        value = node.value
        if value is None:
            return False
        names = {n.id for n in ast.walk(value) if isinstance(n, ast.Name)}
        if not names & self.type_only:
            return False
        if names - self.type_only - _BUILTIN_NAMES - set(self.native_enums):
            return False
        targets = [node.target] if isinstance(node, ast.AnnAssign) else node.targets
        for target in targets:
            if isinstance(target, ast.Name):
                self.type_only.add(target.id)
        return True

    def _bind_module(self, module: str, local: str, node: ast.stmt) -> None:
        """Bind a module name for `import x` / `import x as y`.

        Args:
            module: The imported module's dotted name.
            local: The local name it binds.
            node: The import node, for the diagnostic's line.

        Raises:
            TranspileError: If Mode C serves no such module. A module that is
                refused on purpose says what to do instead — a diagnostic that
                only lists what is allowed leaves the reader stuck.
        """
        if module in _MODULE_CALLS or module in _MODULE_CONSTANTS:
            self.module_aliases[local] = module
            return
        if module == "tempestweb" or module.startswith(f"{_NATIVE_MODULE}"):
            raise TranspileError(
                f"`import {module}` is not supported in Mode C: import the "
                "capability by name — `from tempestweb import native`, or "
                "`from tempestweb.native import get_position`",
                node,
                self.filename,
            )
        hint = _REFUSED_MODULES.get(module)
        if hint is not None:
            raise TranspileError(
                f"`import {module}` is not available in Mode C: {hint}",
                node,
                self.filename,
            )
        raise TranspileError(
            f"`import {module}` is not available in Mode C "
            f"(served: {', '.join(sorted(_MODULE_CALLS))})",
            node,
            self.filename,
        )

    def _collect_imports(
        self, node: ast.Import | ast.ImportFrom, importable: set[str]
    ) -> None:
        """Validate imports and record names that carry a runtime value.

        Args:
            node: The import node.
            importable: Accumulator of names the module is allowed to reference
                from the native modules (`State` is always allowed as the
                injected dataclass base).
        """
        if isinstance(node, ast.Import):
            for alias in node.names:
                self._bind_module(alias.name, alias.asname or alias.name, node)
            return
        module = node.module or ""
        if module in {"__future__", "dataclasses"}:
            return
        # `from tempestweb import native` — the native-capability namespace, which
        # Mode C serves from its in-process JS facade (./native.js).
        if module == "tempestweb":
            for alias in node.names:
                if alias.name != _NATIVE_NAMESPACE:
                    raise TranspileError(
                        f"`from tempestweb import {alias.name}` is not supported "
                        "(only `native`)",
                        node,
                        self.filename,
                    )
                self.native_imports[alias.asname or alias.name] = _NATIVE_NAMESPACE
            return
        if module == _NATIVE_MODULE:
            self._import_native_root(node)
            return
        if module.startswith(f"{_NATIVE_MODULE}."):
            self._import_native_group(module[len(_NATIVE_MODULE) + 1 :], node)
            return
        if module == "enum":
            for alias in node.names:
                name = alias.name
                if name not in _ENUM_BASES:
                    raise TranspileError(
                        f"`from enum import {name}` is not supported "
                        f"(only {', '.join(sorted(_ENUM_BASES))})",
                        node,
                        self.filename,
                    )
                self.enum_bases.add(alias.asname or name)
            return
        if module in _MODULE_CALLS or module in _MODULE_CONSTANTS:
            for alias in node.names:
                member = alias.name
                known = member in _MODULE_CALLS.get(
                    module, {}
                ) or member in _MODULE_CONSTANTS.get(module, {})
                if not known:
                    raise TranspileError(
                        f"`{module}.{member}` is not available in Mode C",
                        node,
                        self.filename,
                    )
                self.member_aliases[alias.asname or member] = (module, member)
            return
        # Annotation-only sources: record the names and emit nothing for them.
        if module in _TYPE_ONLY_MODULES:
            for alias in node.names:
                self.type_only.add(alias.asname or alias.name)
            return
        if not (module.startswith("tempest_core") or module == _COMPONENT_MODULE):
            hint = _REFUSED_MODULES.get(module)
            if hint is not None:
                raise TranspileError(
                    f"`from {module} import …` is not available in Mode C: {hint}",
                    node,
                    self.filename,
                )
            raise TranspileError(
                f"import from {module!r} is not supported "
                "(only tempest_core, `tempestweb.components` "
                "and `tempestweb.native`)",
                node,
                self.filename,
            )
        for alias in node.names:
            name = alias.asname or alias.name
            if name not in _TYPE_ONLY_NAMES:
                importable.add(name)
            self.core_imports[name] = alias.name
            self.import_nodes[name] = node
        importable.add("State")

    def _bind_native(self, local: str, path: str) -> None:
        """Bind a local name to a path on the Mode C native facade.

        Args:
            local: The name the module binds.
            path: The path below the facade namespace (``"storage"``,
                ``"geolocation.get_position"``).
        """
        self.native_imports[_NATIVE_FACADE_ALIAS] = _NATIVE_NAMESPACE
        self.native_aliases[local] = f"{_NATIVE_FACADE_ALIAS}.{path}"

    def _refuse_native_group(self, group: str, node: ast.stmt) -> None:
        """Raise for a capability group the in-process facade does not carry.

        Args:
            group: The capability group as Python spells it.
            node: The import node, for the diagnostic's line.

        Raises:
            TranspileError: Always, when called.
        """
        raise TranspileError(
            f"`{group}` is not served in Mode C: the facade in `native.js` has "
            f"no `{group}`, so the capability needs Mode A (Pyodide) or Mode B "
            "(server)",
            node,
            self.filename,
        )

    def _import_native_root(self, node: ast.ImportFrom) -> None:
        """Bind `from tempestweb.native import …` onto the facade.

        The package re-exports both the capability groups (``storage``) and the
        flat helpers (``get_position``), and Mode C reaches every one of them
        through the same ``./native.js`` object — so this is the same import as
        ``from tempestweb import native``, spelled the other way.

        Args:
            node: The import node.

        Raises:
            TranspileError: If the facade carries no such name, naming what was
                asked for rather than the module it came from.
        """
        types = {name for names in NATIVE_TYPES.values() for name in names}
        for alias in node.names:
            name = alias.name
            local = alias.asname or name
            if name in NATIVE_EXPORTS:
                self.native_imports[local] = name
                self.import_nodes[local] = node
            elif name in NATIVE_MEMBERS:
                self._bind_native(local, name)
            elif name in NATIVE_FLAT:
                self._bind_native(local, NATIVE_FLAT[name])
            elif name in NATIVE_GROUPS:
                self._refuse_native_group(name, node)
            elif name in NATIVE_ENUMS:
                self.native_enums[local] = name
            elif name in types:
                self.type_only.add(local)
            else:
                raise TranspileError(
                    f"`tempestweb.native.{name}` is not available in Mode C "
                    "(the facade in `native.js` exports no such name)",
                    node,
                    self.filename,
                )

    def _import_native_group(self, group: str, node: ast.ImportFrom) -> None:
        """Bind `from tempestweb.native.<group> import …` onto the facade.

        Args:
            group: The capability group the import addresses.
            node: The import node.

        Raises:
            TranspileError: If the group is not served, or the group serves no
                such member — named, with what it does serve.
        """
        members = NATIVE_MEMBERS.get(group)
        if members is None:
            if group in NATIVE_GROUPS:
                self._refuse_native_group(group, node)
            raise TranspileError(
                f"`tempestweb.native.{group}` is not a capability group",
                node,
                self.filename,
            )
        types = NATIVE_TYPES.get(group, frozenset())
        for alias in node.names:
            name = alias.name
            local = alias.asname or name
            if name in members:
                self._bind_native(local, f"{group}.{name}")
            elif name in NATIVE_ENUMS and name in types:
                self.native_enums[local] = name
            elif name in types:
                self.type_only.add(local)
            else:
                raise TranspileError(
                    f"`{group}.{name}` is not available in Mode C "
                    f"(served: {', '.join(sorted(members))})",
                    node,
                    self.filename,
                )

    def _refuse_unserved(self, origin: str, node: ast.AST | None) -> None:
        """Raise when the Mode C client exports no such name.

        Args:
            origin: The ``tempest_core`` name as the core spells it.
            node: The node to blame in the diagnostic.

        Raises:
            TranspileError: Always, when called.
        """
        raise TranspileError(
            f"`{origin}` is not available in Mode C "
            "(the transpile client exports no such name)",
            node,
            self.filename,
        )

    def _check_served(self, used: set[str]) -> None:
        """Refuse a referenced name the Mode C client cannot resolve.

        The emitted module imports every core name it references. Nothing
        verified the target existed, so a view using ``Card`` or ``Scaffold``
        (composition living in ``tempest_core.components``, outside the Mode C
        subset) compiled into a module whose very first import fails — the
        browser refuses to evaluate it and the page stays blank, with the
        goldens green and ``node --check`` happy, because parsing never resolves
        an import.

        Only *referenced* names are checked, so importing an event or handler
        type for an annotation stays free: annotations are dropped, the name is
        never referenced, and no import is emitted for it.

        Args:
            used: The importable names the emitted bodies actually reference.

        Raises:
            TranspileError: If a referenced name is not exported by the client.
        """
        for name in sorted(used):
            origin = self.core_imports.get(name, name)
            if origin in SERVED_NAMES or name in SERVED_NAMES:
                continue
            self._refuse_unserved(origin, self.import_nodes.get(name))

    def _imports(self, used: set[str]) -> str:
        """Emit the runtime + widgets + native + validators import lines.

        Args:
            used: Importable names the emitted bodies actually reference.

        Returns:
            The import lines, one per source module, aliasing the dataclass base
            when :attr:`state_base` says the module declares its own ``State``.
        """
        self._check_served(used)
        runtime = sorted(used & _RUNTIME_NAMES)
        if self.state_base != "State":
            runtime.append(f"State as {self.state_base}")
        # `$` is legal in a JS identifier and never in a Python one, so an app's
        # own `sleep` cannot collide with the helper it calls.
        runtime.extend(
            f"{helper} as {helper}$" for helper in sorted(self.runtime_helpers)
        )
        native = [
            export if local == export else f"{export} as {local}"
            for local, export in sorted(self.native_imports.items())
            if local in self.referenced
        ]
        nav = sorted(used & _NAV_NAMES)
        i18n = sorted(used & _I18N_NAMES)
        theme = sorted(used & _THEME_NAMES)
        motion = sorted(used & _MOTION_NAMES)
        anim = sorted(used & _ANIM_NAMES)
        validators = sorted(used & _VALIDATOR_NAMES)
        widgets = sorted(
            used
            - _RUNTIME_NAMES
            - _NATIVE_NAMES
            - _NAV_NAMES
            - _I18N_NAMES
            - _THEME_NAMES
            - _MOTION_NAMES
            - _ANIM_NAMES
            - _VALIDATOR_NAMES
        )
        lines: list[str] = []
        if runtime:
            lines.append(f'import {{ {", ".join(runtime)} }} from "./runtime.js";')
        if widgets:
            lines.append(f'import {{ {", ".join(widgets)} }} from "./widgets.js";')
        if native:
            lines.append(f'import {{ {", ".join(native)} }} from "./native.js";')
        if nav:
            lines.append(f'import {{ {", ".join(nav)} }} from "./nav.js";')
        if i18n:
            lines.append(f'import {{ {", ".join(i18n)} }} from "./i18n.js";')
        if theme:
            lines.append(f'import {{ {", ".join(theme)} }} from "./theme.js";')
        if motion:
            lines.append(f'import {{ {", ".join(motion)} }} from "./motion.js";')
        if anim:
            lines.append(f'import {{ {", ".join(anim)} }} from "./animation.js";')
        if validators:
            module = "./validators.js"
            lines.append(f'import {{ {", ".join(validators)} }} from "{module}";')
        return "\n".join(lines)

    def _field_default(self, value: ast.expr) -> str:
        """Emit a dataclass field's default, resolving ``dataclasses.field(...)``.

        ``field(default=X)`` → ``X``; ``field(default_factory=list)`` → ``[]`` and
        ``default_factory=dict`` → ``{}`` (the common mutable-default forms). A
        plain value is emitted as-is.

        A factory that names a class — a nested dataclass, or an imported JS class
        — is constructed with ``new``: calling a JS class without it is a hard
        ``TypeError``, so ``(Address)()`` compiled and then died on the first
        ``makeState()``.

        Args:
            value: The field's default expression.

        Returns:
            The JS initializer source.

        Raises:
            TranspileError: If a ``field(...)`` form is not one of the above.
        """
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and (value.func.id == "field")
        ):
            factories = {"list": "[]", "dict": "{}", "set": "new Set()"}
            for kw in value.keywords:
                if kw.arg == "default":
                    return self.expr(kw.value, 2)
                if kw.arg == "default_factory":
                    if isinstance(kw.value, ast.Name) and kw.value.id in factories:
                        return factories[kw.value.id]
                    if isinstance(kw.value, ast.Name) and (
                        kw.value.id in self.class_names or kw.value.id in _JS_CLASSES
                    ):
                        return f"new {self.expr(kw.value, 2)}()"
                    # Parenthesized: an arrow (`lambda: …`) is not callable
                    # without it, and `() => x()` would store the function.
                    return f"({self.expr(kw.value, 2)})()"
            for kw in value.keywords:
                if kw.arg not in _IGNORED_FIELD_OPTIONS:
                    raise TranspileError(
                        f"dataclass field(...) option {kw.arg!r} is not supported "
                        "(use default= or default_factory=)",
                        value,
                        self.filename,
                    )
            return "undefined"
        return self.expr(value, 2)

    def _check_dataclass_options(self, decorator: ast.Call) -> None:
        """Refuse a ``@dataclass(...)`` option that would change the emitted class.

        ``frozen``/``slots``/``eq`` and friends describe Python-side behaviour the
        generated JS class does not have, so they are accepted and ignored — a
        module written ``@dataclass(frozen=True)`` (three examples in this repo)
        transpiles to the same class as a bare ``@dataclass``. Anything else is
        refused by name, because silently dropping an option the author *did*
        mean is how a subtle divergence between modes starts.

        Args:
            decorator: The decorator call node.

        Raises:
            TranspileError: For an option outside
                :data:`_IGNORED_DATACLASS_OPTIONS`, or a positional argument.
        """
        if decorator.args:
            raise TranspileError(
                "@dataclass takes only keyword options",
                decorator,
                self.filename,
            )
        for kw in decorator.keywords:
            if kw.arg not in _IGNORED_DATACLASS_OPTIONS:
                raise TranspileError(
                    f"@dataclass option {kw.arg!r} is not supported in Mode C",
                    decorator,
                    self.filename,
                )

    def _enum_class(self, node: ast.ClassDef) -> str:
        """Emit an `Enum` subclass as a frozen object of its members.

        An app enum is a table of constants, which is exactly what
        ``values.gen.js`` already ships for the core's own enums. Members keep
        their value, so `phase == Phase.CLEAR` stays a plain comparison.

        Args:
            node: The class node.

        Returns:
            The `export const X = Object.freeze({...});` source.

        Raises:
            TranspileError: If a member has no value, or the body holds anything
                but members and a docstring (a method on an enum would need a
                class, and the frozen object is what makes it a constant table).
        """
        members: list[str] = []
        for stmt in node.body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                continue
            target: ast.expr | None = None
            assigned: ast.expr | None = None
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                target, assigned = stmt.targets[0], stmt.value
            elif isinstance(stmt, ast.AnnAssign):
                target, assigned = stmt.target, stmt.value
            if not isinstance(target, ast.Name) or assigned is None:
                raise TranspileError(
                    "an enum body holds `NAME = value` members only",
                    stmt,
                    self.filename,
                )
            members.append(f"{_INDENT}{target.id}: {self.expr(assigned, 1)},")
        body = "\n".join(members)
        inner = f"\n{body}\n" if members else ""
        return f"export const {node.name} = Object.freeze({{{inner}}});"

    def _class(self, node: ast.ClassDef) -> str:
        """Emit a `@dataclass` as `export class X extends <base> { … }`.

        Annotated fields become constructor assignments; methods become JS class
        methods (the ``self`` receiver maps to ``this`` and is dropped from the
        parameter list). A dataclass with no base extends :attr:`state_base` —
        the runtime ``State``, or its alias when this module shadows the name;
        a dataclass inheriting another transpiled dataclass extends it directly
        (``super()`` chains the parent constructor, then the subclass's own field
        defaults are assigned — overriding an inherited default when they clash).
        """
        if any(
            isinstance(base, ast.Name) and base.id in self.enum_bases
            for base in node.bases
        ):
            return self._enum_class(node)
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                name: str | None = decorator.id
            elif isinstance(decorator, ast.Call) and isinstance(
                decorator.func, ast.Name
            ):
                name = decorator.func.id
                self._check_dataclass_options(decorator)
            else:
                name = None
            if name != "dataclass":
                raise TranspileError(
                    "only the @dataclass decorator is supported on a class",
                    node,
                    self.filename,
                )
        base = self.state_base
        if node.bases:
            if len(node.bases) != 1 or not isinstance(node.bases[0], ast.Name):
                raise TranspileError(
                    "a dataclass may inherit at most one base, "
                    "another @dataclass in this module",
                    node,
                    self.filename,
                )
            base = node.bases[0].id
            if base not in self.class_names:
                raise TranspileError(
                    f"unknown base class {base!r}; a dataclass can only inherit "
                    "another @dataclass defined in the same module",
                    node,
                    self.filename,
                )
        fields: list[tuple[str, str]] = []
        methods: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                default = (
                    "undefined"
                    if stmt.value is None
                    else self._field_default(stmt.value)
                )
                fields.append((stmt.target.id, default))
            elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(stmt)
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                continue  # class docstring
            else:
                raise TranspileError(
                    "only annotated fields and methods are supported in a dataclass",
                    stmt,
                    self.filename,
                )
        # The constructor takes an options object so a dataclass can be built
        # with field overrides (`Doubler(n=5)` -> `new Doubler({ n: 5 })`); a
        # missing key falls back to the field default. `super(opts)` threads the
        # overrides to an inherited base (State's implicit ctor ignores them).
        lines = [f"export class {node.name} extends {base} {{"]
        lines.append(f"{_INDENT}constructor(opts = {{}}) {{")
        lines.append(f"{_INDENT * 2}super(opts);")
        for name, value in fields:
            lines.append(
                f"{_INDENT * 2}this.{name} = "
                f"opts.{name} !== undefined ? opts.{name} : {value};"
            )
        lines.append(f"{_INDENT}}}")
        for method in methods:
            lines.append("")
            lines.extend(self._method(method))
        lines.append("}")
        return "\n".join(lines)

    def _method(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
        """Emit a dataclass method as a JS class method (drops the `self` param)."""
        _reject_fn_decorators(node, self.filename)
        params = _param_names(node.args, node, self.filename)
        if params and params[0] == "self":
            params = params[1:]
        pad = _INDENT
        prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
        lines = [f"{pad}{prefix}{_js_name(node.name)}({', '.join(params)}) {{"]
        lines.extend(self._emit_fn_body(node.body, 2))
        lines.append(f"{pad}}}")
        return lines

    def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Emit a top-level `def` as `export function name(params) {...}`."""
        _reject_fn_decorators(node, self.filename)
        params = ", ".join(_param_names(node.args, node, self.filename))
        prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
        lines = [f"export {prefix}function {_js_name(node.name)}({params}) {{"]
        lines.extend(self._emit_fn_body(node.body, 1))
        lines.append("}")
        return "\n".join(lines)


def generate(
    source: str, filename: str = "<source>", *, banner: str | None = None
) -> str:
    """Transpile a Python module source string into native-JS module source.

    Args:
        source: The Python source to transpile.
        filename: The source file name (used in error diagnostics and the banner).
        banner: Optional leading comment line; when omitted a default GENERATED
            banner naming `filename` is emitted.

    Returns:
        The generated JavaScript module source, banner included.

    Raises:
        TranspileError: If the module uses a construct outside the subset.
    """
    tree = ast.parse(source, filename=filename)
    body = _Generator(filename).module(tree)
    default_banner = (
        f"// GENERATED from {filename} by tempestweb transpile (Mode C). Do not edit."
    )
    head = banner if banner is not None else default_banner
    return f"{head}\n\n{body}"
