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
import json
import re

from tempestweb.transpile.errors import TranspileError

__all__: list[str] = ["generate"]

# Imported names that resolve to the native runtime rather than a widget builder.
_RUNTIME_NAMES: frozenset[str] = frozenset({"App", "State"})
# The native-capability namespace, imported from `./native.js` in Mode C.
_NATIVE_NAMES: frozenset[str] = frozenset({"native"})
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


def _js_name(name: str) -> str:
    """Map a Python identifier to its JS spelling (API camelCase renames)."""
    return _NAME_MAP.get(name, name)


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
        for stmt in block:
            if isinstance(stmt, ast.Assign):
                targets = [t for t in stmt.targets if isinstance(t, ast.Name)]
                for target in targets:
                    _note(target.id, top=top)
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
                for child in _child_blocks(stmt):
                    walk(child, top=False)

    def _note(name: str, *, top: bool) -> None:
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
        # Identifiers actually referenced in the emitted JS, so imports reflect
        # what the output uses (not merely what the Python source imported).
        self.referenced: set[str] = set()
        # Per-function set of names hoisted to a `let` at the function top, so an
        # assignment inside an `if`/`for` block stays visible afterwards (Python
        # scoping) instead of being trapped in the JS block by `const`.
        self._scopes: list[set[str]] = []

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
            self.referenced.add(node.id)
            return _js_name(node.id)
        if isinstance(node, ast.Attribute):
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
        if isinstance(node, ast.ListComp):
            return self._listcomp(node, indent)
        if isinstance(node, ast.Subscript):
            return self._subscript(node, indent)
        raise TranspileError(
            f"expression {type(node).__name__} is not supported", node, self.filename
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
        match = re.fullmatch(r"(,)?(?:\.(\d+))?([fF%d])?", text)
        grouped = bool(match and match.group(1))
        precision = match.group(2) if match else None
        kind = match.group(3) if match else None
        if match is None or not (grouped or precision is not None or kind):
            raise TranspileError(
                f"f-string format spec {text!r} is not supported "
                "(supported: `.Nf`, `,`, `,.Nf`, `.N%`, `d`, `,d`)",
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
        """Emit an arithmetic binary operation."""
        ops: dict[type[ast.operator], str] = {
            ast.Add: "+",
            ast.Sub: "-",
            ast.Mult: "*",
            ast.Div: "/",
            ast.Mod: "%",
        }
        op = ops.get(type(node.op))
        if op is None:
            raise TranspileError(
                f"operator {type(node.op).__name__} is not supported",
                node,
                self.filename,
            )
        left = self.expr(node.left, indent)
        right = self.expr(node.right, indent)
        return f"({left} {op} {right})"

    def _compare(self, node: ast.Compare, indent: int) -> str:
        """Emit a comparison. Chained comparisons are joined with ``&&``.

        ``in`` / ``not in`` become ``.includes(...)`` membership tests.
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
            else:
                symbol = ops.get(type(op))
                if symbol is None:
                    raise TranspileError(
                        f"comparison {type(op).__name__} is not supported",
                        node,
                        self.filename,
                    )
                parts.append(f"{left_js} {symbol} {right_js}")
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

    def _listcomp(self, node: ast.ListComp, indent: int) -> str:
        """Emit a list comprehension as chained ``.filter().map()``.

        ``[expr for x in it if cond]`` → ``it.filter((x) => cond).map((x) => expr)``.
        Only a single ``for`` clause (with optional ``if``s) is supported.
        """
        if len(node.generators) != 1:
            raise TranspileError(
                "only single-loop comprehensions are supported", node, self.filename
            )
        gen = node.generators[0]
        if not isinstance(gen.target, ast.Name):
            raise TranspileError(
                "comprehension target must be a plain name", node, self.filename
            )
        var = gen.target.id
        iterable = self.expr(gen.iter, indent)
        result = iterable
        for cond in gen.ifs:
            result = f"{result}.filter(({var}) => {self.expr(cond, indent)})"
        element = self.expr(node.elt, indent)
        return f"{result}.map(({var}) => {element})"

    def _subscript(self, node: ast.Subscript, indent: int) -> str:
        """Emit an index/subscript access (``x[i]`` → ``x[i]``)."""
        value = self.expr(node.value, indent)
        if isinstance(node.slice, ast.Slice):
            raise TranspileError("slices are not supported", node, self.filename)
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
        items = ",\n".join(f"{pad}{self.expr(el, inner)}" for el in elts)
        return "[\n" + items + ",\n" + _INDENT * indent + "]"

    def _dict(self, node: ast.Dict, indent: int) -> str:
        """Emit a dict literal as a JS object.

        String-constant keys become plain object keys (``"k": v``); any other key
        expression becomes a computed key (``[expr]: v``). ``**spread`` keys
        (a ``None`` key) are unsupported.
        """
        if not node.keys:
            return "{}"
        pairs: list[str] = []
        for key, value in zip(node.keys, node.values, strict=True):
            if key is None:
                raise TranspileError(
                    "dict unpacking (**) is not supported", node, self.filename
                )
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
        if not isinstance(gen.target, ast.Name):
            raise TranspileError(
                "comprehension target must be a plain name", node, self.filename
            )
        var = gen.target.id
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
        builtin = self._builtin_call(node, indent)
        if builtin is not None:
            return builtin
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

    def _object_call(self, func: str, node: ast.Call, indent: int) -> str:
        """Emit a widget-style call whose kwargs become a single object arg.

        Multiline when a keyword's value spans lines (e.g. a non-empty `children`
        list); inline otherwise.
        """
        pairs: list[tuple[str, str]] = []
        for kw in node.keywords:
            if kw.arg is None:
                raise TranspileError("**kwargs is not supported", node, self.filename)
            pairs.append((_js_name(kw.arg), self.expr(kw.value, indent + 1)))
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
        if isinstance(node, ast.Try):
            return self._try(node, indent)
        if isinstance(node, ast.Break):
            return [f"{_INDENT * indent}break;"]
        if isinstance(node, ast.Continue):
            return [f"{_INDENT * indent}continue;"]
        if isinstance(node, ast.Assign):
            return self._assign(node, indent)
        if isinstance(node, ast.AugAssign):
            return self._augassign(node, indent)
        if isinstance(node, (ast.Pass, ast.AnnAssign)):
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

    def _for(self, node: ast.For, indent: int) -> list[str]:
        """Emit a ``for x in it:`` loop as ``for (const x of it) {...}``."""
        if node.orelse:
            raise TranspileError("for/else is not supported", node, self.filename)
        if not isinstance(node.target, ast.Name):
            raise TranspileError(
                "for-loop target must be a plain name", node, self.filename
            )
        pad = _INDENT * indent
        iterable = self.expr(node.iter, indent)
        lines = [f"{pad}for (const {node.target.id} of {iterable}) {{"]
        lines.extend(self._body(node.body, indent + 1))
        lines.append(f"{pad}}}")
        return lines

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

    def _try(self, node: ast.Try, indent: int) -> list[str]:
        """Emit a ``try/except/finally`` as JS ``try/catch/finally``.

        JS has a single catch binding, so only one ``except`` clause is
        supported; its exception type is informational (JS catches everything).
        ``try/else`` (the ``else`` runs when no exception fired) is unsupported.
        The caught error binds to the handler's name, or ``_err`` when anonymous.
        """
        if node.orelse:
            raise TranspileError("try/else is not supported", node, self.filename)
        if len(node.handlers) > 1:
            raise TranspileError(
                "only a single except clause is supported", node, self.filename
            )
        pad = _INDENT * indent
        lines = [f"{pad}try {{"]
        lines.extend(self._body(node.body, indent + 1))
        if node.handlers:
            handler = node.handlers[0]
            name = handler.name or "_err"
            lines.append(f"{pad}}} catch ({name}) {{")
            lines.extend(self._body(handler.body, indent + 1))
        if node.finalbody:
            lines.append(f"{pad}}} finally {{")
            lines.extend(self._body(node.finalbody, indent + 1))
        lines.append(f"{pad}}}")
        return lines

    def _assign(self, node: ast.Assign, indent: int) -> list[str]:
        """Emit an assignment.

        A single ``Name`` target is declared with ``const``; an attribute or
        subscript target is a plain assignment (the object already exists).
        Multiple/tuple targets are unsupported.
        """
        if len(node.targets) != 1:
            raise TranspileError(
                "multiple assignment targets are not supported", node, self.filename
            )
        target = node.targets[0]
        value = self.expr(node.value, indent)
        pad = _INDENT * indent
        if isinstance(target, ast.Name):
            # If the name was hoisted to a function-top `let` (so it stays visible
            # outside an if/for block — Python scoping), assign plainly; otherwise
            # declare it with `const`.
            if self._scopes and target.id in self._scopes[-1]:
                return [f"{pad}{target.id} = {value};"]
            return [f"{pad}const {target.id} = {value};"]
        if isinstance(target, (ast.Attribute, ast.Subscript)):
            return [f"{pad}{self.expr(target, indent)} = {value};"]
        raise TranspileError(
            f"assignment target {type(target).__name__} is not supported",
            node,
            self.filename,
        )

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
                top_level.append(node)
            elif isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.Assign, ast.AnnAssign),
            ):
                top_level.append(node)
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                continue  # module docstring
            else:
                raise TranspileError(
                    f"top-level {type(node).__name__} is not supported",
                    node,
                    self.filename,
                )

        # Emit bodies first so `referenced` reflects what the output actually
        # uses; `State` is the injected base of every emitted dataclass.
        bodies: list[str] = []
        for node in top_level:
            if isinstance(node, ast.ClassDef):
                bodies.append(self._class(node))
                self.referenced.add("State")
            elif isinstance(node, ast.Assign | ast.AnnAssign):
                bodies.append(self._module_const(node))
            else:
                assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                bodies.append(self._function(node))

        imports = self._imports(self.referenced & importable)
        return "\n\n".join([imports, *bodies]) + "\n"

    def _module_const(self, node: ast.Assign | ast.AnnAssign) -> str:
        """Emit a module-level constant (e.g. a translations table) as `const`.

        A single ``NAME = value`` or annotated ``NAME: T = value`` becomes a
        top-level ``const NAME = value;``. Tuple/multiple targets are unsupported.
        """
        target: ast.expr
        value: ast.expr | None
        if isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        else:
            if len(node.targets) != 1:
                raise TranspileError(
                    "multiple assignment targets are not supported",
                    node,
                    self.filename,
                )
            target, value = node.targets[0], node.value
        if not isinstance(target, ast.Name) or value is None:
            raise TranspileError(
                "only a single named module constant with a value is supported",
                node,
                self.filename,
            )
        return f"const {target.id} = {self.expr(value, 0)};"

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
            raise TranspileError(
                "plain `import x` is not supported; use `from ... import ...`",
                node,
                self.filename,
            )
        module = node.module or ""
        if module in {"__future__", "dataclasses"}:
            return
        # `from tempestweb import native` — the native-capability namespace, which
        # Mode C serves from its in-process JS facade (./native.js).
        if module == "tempestweb":
            for alias in node.names:
                name = alias.asname or alias.name
                if name in _NATIVE_NAMES:
                    importable.add(name)
                else:
                    raise TranspileError(
                        f"`from tempestweb import {name}` is not supported "
                        "(only `native`)",
                        node,
                        self.filename,
                    )
            return
        if not module.startswith("tempest_core"):
            raise TranspileError(
                f"import from {module!r} is not supported "
                "(only tempest_core and `tempestweb.native`)",
                node,
                self.filename,
            )
        for alias in node.names:
            name = alias.asname or alias.name
            if name not in _TYPE_ONLY_NAMES:
                importable.add(name)
        importable.add("State")

    def _imports(self, used: set[str]) -> str:
        """Emit the runtime + widgets + native + validators import lines."""
        runtime = sorted(used & _RUNTIME_NAMES)
        native = sorted(used & _NATIVE_NAMES)
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
                if (
                    kw.arg == "default_factory"
                    and isinstance(kw.value, ast.Name)
                    and kw.value.id in factories
                ):
                    return factories[kw.value.id]
            raise TranspileError(
                "unsupported dataclass field(...) — use default= or "
                "default_factory=list/dict",
                value,
                self.filename,
            )
        return self.expr(value, 2)

    def _class(self, node: ast.ClassDef) -> str:
        """Emit a `@dataclass` as `export class X extends State { … }`.

        Annotated fields become constructor assignments; methods become JS class
        methods (the ``self`` receiver maps to ``this`` and is dropped from the
        parameter list).
        """
        for decorator in node.decorator_list:
            name = decorator.id if isinstance(decorator, ast.Name) else None
            if name != "dataclass":
                raise TranspileError(
                    "only the @dataclass decorator is supported on a class",
                    node,
                    self.filename,
                )
        fields: list[tuple[str, str]] = []
        methods: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                if stmt.value is None:
                    raise TranspileError(
                        "dataclass fields must have a default in the subset",
                        stmt,
                        self.filename,
                    )
                fields.append((stmt.target.id, self._field_default(stmt.value)))
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
        lines = [f"export class {node.name} extends State {{"]
        lines.append(f"{_INDENT}constructor() {{")
        lines.append(f"{_INDENT * 2}super();")
        for name, value in fields:
            lines.append(f"{_INDENT * 2}this.{name} = {value};")
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
