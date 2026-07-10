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

from tempestweb.transpile.errors import TranspileError

__all__: list[str] = ["generate"]

# Imported names that resolve to the native runtime rather than a widget builder.
_RUNTIME_NAMES: frozenset[str] = frozenset({"App", "State"})
# Type-only imports that carry no runtime value and are dropped from the output.
_TYPE_ONLY_NAMES: frozenset[str] = frozenset({"Widget"})
# API identifiers renamed from Python's snake_case to the JS client's camelCase.
_NAME_MAP: dict[str, str] = {
    "make_state": "makeState",
    "set_state": "setState",
    "on_click": "onClick",
}
_INDENT: str = "  "


def _js_name(name: str) -> str:
    """Map a Python identifier to its JS spelling (API camelCase renames)."""
    return _NAME_MAP.get(name, name)


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
            return self._list(node, indent)
        if isinstance(node, ast.Call):
            return self._call(node, indent)
        if isinstance(node, ast.Lambda):
            return self._lambda(node, indent)
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
                parts.append(f"${{{self.expr(value.value, indent)}}}")
            else:
                raise TranspileError("unsupported f-string part", value, self.filename)
        return "`" + "".join(parts) + "`"

    def _binop(self, node: ast.BinOp, indent: int) -> str:
        """Emit a binary operation (only + and - in the subset)."""
        ops: dict[type[ast.operator], str] = {ast.Add: "+", ast.Sub: "-"}
        op = ops.get(type(node.op))
        if op is None:
            raise TranspileError(
                f"operator {type(node.op).__name__} is not supported",
                node,
                self.filename,
            )
        return f"{self.expr(node.left, indent)} {op} {self.expr(node.right, indent)}"

    def _list(self, node: ast.List, indent: int) -> str:
        """Emit an array literal, multiline when it holds elements."""
        if not node.elts:
            return "[]"
        inner = indent + 1
        pad = _INDENT * inner
        items = ",\n".join(f"{pad}{self.expr(el, inner)}" for el in node.elts)
        return "[\n" + items + ",\n" + _INDENT * indent + "]"

    def _call(self, node: ast.Call, indent: int) -> str:
        """Emit a call: keyword-only → object arg; positional → plain args."""
        func = self.expr(node.func, indent)
        if node.keywords and not node.args:
            return self._object_call(func, node, indent)
        args = ", ".join(self.expr(a, indent) for a in node.args)
        is_class = isinstance(node.func, ast.Name) and node.func.id in self.class_names
        prefix = "new " if is_class else ""
        return f"{prefix}{func}({args})"

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
        multiline = any("\n" in value for _, value in pairs)
        if not multiline:
            body = ", ".join(f"{key}: {value}" for key, value in pairs)
            return f"{func}({{ {body} }})"
        inner = indent + 1
        pad = _INDENT * inner
        lines = ",\n".join(f"{pad}{key}: {value}" for key, value in pairs)
        return f"{func}({{\n{lines},\n{_INDENT * indent}}})"

    def _lambda(self, node: ast.Lambda, indent: int) -> str:
        """Emit an arrow function.

        The only supported body is ``setattr(obj, "name", value)`` (an in-place
        state mutation), emitted as a block arrow with a single assignment.
        """
        params = ", ".join(a.arg for a in node.args.args)
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
        raise TranspileError(
            'only `setattr(obj, "name", value)` lambdas are supported',
            node,
            self.filename,
        )

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
        if isinstance(node, ast.FunctionDef):
            return self._nested_def(node, indent)
        if isinstance(node, ast.Expr):
            return [f"{_INDENT * indent}{self.expr(node.value, indent)};"]
        if isinstance(node, (ast.Pass, ast.AnnAssign)):
            return []
        raise TranspileError(
            f"statement {type(node).__name__} is not supported", node, self.filename
        )

    def _return(self, node: ast.Return, indent: int) -> list[str]:
        """Emit a return statement."""
        if node.value is None:
            return [f"{_INDENT * indent}return;"]
        return [f"{_INDENT * indent}return {self.expr(node.value, indent)};"]

    def _nested_def(self, node: ast.FunctionDef, indent: int) -> list[str]:
        """Emit a nested `def` as a `const name = (params) => {...}` arrow."""
        params = ", ".join(a.arg for a in node.args.args)
        pad = _INDENT * indent
        lines = [f"{pad}const {_js_name(node.name)} = ({params}) => {{"]
        lines.extend(self._body(node.body, indent + 1))
        lines.append(f"{pad}}};")
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
            elif isinstance(node, ast.FunctionDef):
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
            else:
                assert isinstance(node, ast.FunctionDef)
                bodies.append(self._function(node))

        imports = self._imports(self.referenced & importable)
        return "\n\n".join([imports, *bodies]) + "\n"

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
        if not module.startswith("tempest_core"):
            raise TranspileError(
                f"import from {module!r} is not supported (only tempest_core)",
                node,
                self.filename,
            )
        for alias in node.names:
            name = alias.asname or alias.name
            if name not in _TYPE_ONLY_NAMES:
                importable.add(name)
        importable.add("State")

    def _imports(self, used: set[str]) -> str:
        """Emit the fixed runtime + widgets import lines for the used names."""
        runtime = sorted(used & _RUNTIME_NAMES)
        widgets = sorted(used - _RUNTIME_NAMES)
        lines: list[str] = []
        if runtime:
            lines.append(f'import {{ {", ".join(runtime)} }} from "./runtime.js";')
        if widgets:
            lines.append(f'import {{ {", ".join(widgets)} }} from "./widgets.js";')
        return "\n".join(lines)

    def _class(self, node: ast.ClassDef) -> str:
        """Emit a `@dataclass` as `export class X extends State { constructor }`."""
        fields: list[tuple[str, str]] = []
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                if stmt.value is None:
                    raise TranspileError(
                        "dataclass fields must have a default in the subset",
                        stmt,
                        self.filename,
                    )
                fields.append((stmt.target.id, self.expr(stmt.value, 2)))
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                continue  # class docstring
            else:
                raise TranspileError(
                    "only annotated fields are supported in a dataclass",
                    stmt,
                    self.filename,
                )
        lines = [f"export class {node.name} extends State {{"]
        lines.append(f"{_INDENT}constructor() {{")
        lines.append(f"{_INDENT * 2}super();")
        for name, value in fields:
            lines.append(f"{_INDENT * 2}this.{name} = {value};")
        lines.append(f"{_INDENT}}}")
        lines.append("}")
        return "\n".join(lines)

    def _function(self, node: ast.FunctionDef) -> str:
        """Emit a top-level `def` as `export function name(params) {...}`."""
        params = ", ".join(a.arg for a in node.args.args)
        lines = [f"export function {_js_name(node.name)}({params}) {{"]
        lines.extend(self._body(node.body, 1))
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
