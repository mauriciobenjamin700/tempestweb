"""OpenAPI 3.x → typed tempestweb API client (dataclasses + service classes).

Pure and deterministic: :func:`generate` takes a parsed OpenAPI document and
returns a ``{relative_path: file_contents}`` map plus the list of tags — no I/O.
The emitted client uses only constructs the tempestweb transpiler and both
runtime modes accept: ``@dataclass`` models and calls to
:func:`tempestweb.native.http.request`.

**The emitted source is written to pass ``tempestweb check`` as-is.** Every
generated file opens with "do not edit", so a lint or type error inside it is an
error its owner is not allowed to fix — which is why projects ended up excluding
the client from the gate and losing type checking exactly at the API boundary.
The emitter therefore does the formatter's work itself, without shelling out to
any tool: double-quoted literals, imports limited to what the file uses and
ordered the way isort orders them, ``__all__`` in ruff's isort-style order, no
``noqa`` that suppresses nothing, and every construct it controls wrapped at
:data:`LINE_LIMIT` columns exactly the way ``ruff format`` would wrap it.

It also reads a **required** property with ``data["x"]`` instead of
``data.get("x")``. ``dict.get`` types the value ``Any | None``, so every required
field of every model used to be an ``arg-type`` error at the call site, and a
truncated response silently built the dataclass with ``None`` inside a ``str``.
``data["x"]`` types as ``Any`` and fails loudly, at the boundary, on the missing
key.
"""

from __future__ import annotations

import json
import keyword
import re
import textwrap
from typing import Any

__all__ = ["LINE_LIMIT", "generate"]

HTTP_METHODS: tuple[str, ...] = ("get", "post", "put", "patch", "delete")

LINE_LIMIT: int = 88
"""Column budget the emitter wraps at — ruff's default ``line-length``."""

_INDENT: str = "    "


def ref_name(ref: str) -> str:
    """Return the component name from a ``$ref``.

    Args:
        ref: A JSON reference like ``#/components/schemas/User``.

    Returns:
        The trailing component name (``User``).
    """
    return ref[ref.rfind("/") + 1 :]


def _tag_slug(tag: str) -> str:
    """Slug a tag into a package/identifier-safe base.

    Args:
        tag: The OpenAPI tag (e.g. ``"User Profiles"``).

    Returns:
        A lowercase, underscore-joined slug (``"user_profiles"``).
    """
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", tag.strip()).strip("_").lower()
    return slug or "default"


def _pascal(text: str) -> str:
    """Convert a slug to PascalCase.

    Args:
        text: A slug such as ``"user_profiles"``.

    Returns:
        ``"UserProfiles"``.
    """
    return "".join(
        part[:1].upper() + part[1:] for part in re.split(r"[^a-zA-Z0-9]+", text) if part
    )


def _snake(text: str) -> str:
    """Convert an identifier to a safe snake_case name.

    Args:
        text: Any identifier-ish string (operationId, path segment).

    Returns:
        A snake_case identifier, suffixed with ``_`` if it collides with a
        Python keyword.
    """
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_")
    cleaned = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", cleaned).lower()
    if not cleaned:
        cleaned = "op"
    if cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    if keyword.iskeyword(cleaned):
        cleaned = f"{cleaned}_"
    return cleaned


def _dunder_all_key(name: str) -> tuple[int, str]:
    """Return the sort key ruff's RUF022 "isort-style" order uses.

    Names are bucketed before being compared: ``SCREAMING_SNAKE_CASE`` first,
    then ``CamelCase``, then everything else, each bucket alphabetical.

    Args:
        name: An exported name.

    Returns:
        A ``(bucket, name)`` tuple to sort by.
    """
    stripped = name.lstrip("_")
    if stripped.isupper():
        return (0, name)
    if stripped[:1].isupper():
        return (1, name)
    return (2, name)


def _sorted_exports(names: list[str]) -> list[str]:
    """Order exported names the way ruff's RUF022 expects ``__all__`` ordered.

    Args:
        names: The names to export.

    Returns:
        A new list in isort-style order.
    """
    return sorted(names, key=_dunder_all_key)


def _render_sequence(
    indent: str,
    head: str,
    items: list[str],
    *,
    open_char: str = "(",
    close_char: str = ")",
    tail: str = "",
) -> list[str]:
    """Render a bracketed construct on one line, or exploded when it is too long.

    Mirrors ``ruff format``: the single-line form wins whenever it fits in
    :data:`LINE_LIMIT`; otherwise every item goes on its own line with a magic
    trailing comma, which is also what keeps the formatter from collapsing it
    back.

    Args:
        indent: The leading whitespace for the construct.
        head: Everything between the indent and the opening bracket.
        items: The comma-separated items.
        open_char: The opening bracket.
        close_char: The closing bracket.
        tail: Everything after the closing bracket (e.g. ``" -> int:"``).

    Returns:
        The rendered source lines.
    """
    single = f"{indent}{head}{open_char}{', '.join(items)}{close_char}{tail}"
    if not items or len(single) <= LINE_LIMIT:
        return [single]
    lines = [f"{indent}{head}{open_char}"]
    lines.extend(f"{indent}{_INDENT}{item}," for item in items)
    lines.append(f"{indent}{close_char}{tail}")
    return lines


def _render_import(module: str, names: list[str]) -> list[str]:
    """Render a ``from <module> import a, b`` statement, wrapping when too long.

    Args:
        module: The module the names come from.
        names: The imported names, already ordered.

    Returns:
        The single-line form when it fits, otherwise isort's vertical-hanging
        form with a magic trailing comma.
    """
    single = f"from {module} import {', '.join(names)}"
    if len(single) <= LINE_LIMIT:
        return [single]
    return [
        f"from {module} import (",
        *(f"{_INDENT}{name}," for name in names),
        ")",
    ]


def _top_level_index(expression: str, token: str) -> int:
    """Find ``token`` in ``expression`` outside every bracket and string literal.

    Args:
        expression: The Python expression to scan.
        token: The literal token to look for (e.g. ``" if "``).

    Returns:
        The index of the first top-level occurrence, or ``-1``.
    """
    depth = 0
    quote: str | None = None
    index = 0
    while index < len(expression):
        char = expression[index]
        if quote is not None:
            if char == quote:
                quote = None
            index += 1
            continue
        if char in "\"'":
            quote = char
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif depth == 0 and expression.startswith(token, index):
            return index
        index += 1
    return -1


def _split_ternary(expression: str) -> tuple[str, str, str] | None:
    """Split ``head if condition else alternative`` at the top level.

    Args:
        expression: The Python expression to split.

    Returns:
        The three parts, or None when the expression is not a conditional.
    """
    if_at = _top_level_index(expression, " if ")
    if if_at < 0:
        return None
    head = expression[:if_at]
    rest = expression[if_at + 4 :]
    else_at = _top_level_index(rest, " else ")
    if else_at < 0:
        return None
    return head, rest[:else_at], rest[else_at + 6 :]


def _split_comprehension(expression: str) -> tuple[str, str] | None:
    """Split ``element for name in iterable`` at the top-level ``for``.

    Args:
        expression: The comprehension body, without its brackets.

    Returns:
        The element and the ``for`` clause, or None when there is no top-level
        ``for``.
    """
    for_at = _top_level_index(expression, " for ")
    if for_at < 0:
        return None
    return expression[:for_at], expression[for_at + 1 :]


def _split_call(expression: str) -> tuple[str, list[str]] | None:
    """Split ``callee(arg, ...)`` into its callee and top-level arguments.

    Args:
        expression: The Python expression to split.

    Returns:
        A ``(callee, args)`` tuple, or None when the expression is not a call
        with at least one argument.
    """
    if not expression.endswith(")"):
        return None
    open_at = expression.find("(")
    if open_at <= 0:
        return None
    inner = expression[open_at + 1 : -1]
    if not inner:
        return None
    args: list[str] = []
    remaining = inner
    while True:
        comma = _top_level_index(remaining, ", ")
        if comma < 0:
            args.append(remaining)
            break
        args.append(remaining[:comma])
        remaining = remaining[comma + 2 :]
    return expression[:open_at], args


def _render_ternary_head(indent: str, prefix: str, head: str) -> list[str]:
    """Render the branch-free head of a split conditional expression.

    Args:
        indent: The leading whitespace.
        prefix: The element head (``"id": `` or ``id=``).
        head: The expression evaluated when the condition holds.

    Returns:
        One line, or the head's call exploded over its arguments — the shape
        ``ruff format`` produces when the head alone overflows.
    """
    line = f"{indent}{prefix}{head}"
    if len(line) <= LINE_LIMIT:
        return [line]
    call = _split_call(head)
    if call is None:
        return [line]
    callee, args = call
    return [
        f"{indent}{prefix}{callee}(",
        *(f"{indent}{_INDENT}{arg}" for arg in args),
        f"{indent})",
    ]


def _render_comprehension(indent: str, expression: str) -> list[str]:
    """Render a comprehension body, splitting before ``for`` when it overflows.

    Args:
        indent: The leading whitespace.
        expression: The comprehension body, without its brackets.

    Returns:
        The rendered lines.
    """
    line = f"{indent}{expression}"
    if len(line) <= LINE_LIMIT:
        return [line]
    split = _split_comprehension(expression)
    if split is None:
        return [line]
    element, clause = split
    return [f"{indent}{element}", f"{indent}{clause}"]


def _render_entry(indent: str, prefix: str, expression: str) -> list[str]:
    """Render one ``key: value,`` / ``name=value,`` element of an exploded literal.

    The shapes mirror ``ruff format``: a conditional expression splits in place
    before ``if``/``else`` (the formatter adds no parentheses around it), and a
    list comprehension splits inside its brackets, before ``for``.

    A line can still overflow when a *single spec identifier* is long enough:
    ``"<36-char property>": self.<36-char field>,`` already costs 94 columns and
    has nothing left to split. ``ruff format`` leaves that line long too, so the
    only alternative would be a ``noqa`` that suppresses a real measurement.

    Args:
        indent: The leading whitespace.
        prefix: The element head (``"id": `` or ``id=``).
        expression: The value expression.

    Returns:
        The rendered lines.
    """
    single = f"{indent}{prefix}{expression},"
    if len(single) <= LINE_LIMIT:
        return [single]
    ternary = _split_ternary(expression)
    if ternary is not None:
        head, condition, alternative = ternary
        return [
            *_render_ternary_head(indent, prefix, head),
            f"{indent}if {condition}",
            f"{indent}else {alternative},",
        ]
    if expression.startswith("[") and expression.endswith("]"):
        return [
            f"{indent}{prefix}[",
            *_render_comprehension(indent + _INDENT, expression[1:-1]),
            f"{indent}],",
        ]
    return [single]


def _clean_text(text: object) -> str:
    """Normalize spec prose into a single docstring-safe sentence.

    Args:
        text: The raw ``summary``/``description`` value from the spec.

    Returns:
        Whitespace-collapsed text with backslashes dropped and double quotes
        downgraded to single ones, terminated by a period. Empty when the input
        carried no prose.
    """
    if not isinstance(text, str):
        return ""
    collapsed = " ".join(text.replace("\\", "").replace('"', "'").split())
    if not collapsed:
        return ""
    return collapsed if collapsed.endswith((".", "!", "?")) else f"{collapsed}."


def _wrap(text: str, width: int, *, hanging: bool = False) -> list[str]:
    """Wrap docstring prose to a width, never splitting a word.

    Args:
        text: The prose to wrap.
        width: The available width (the column budget minus the indent).
        hanging: When True, indent continuation lines by four spaces (the
            Google-style continuation of an ``Args:`` entry).

    Returns:
        The wrapped lines, relative to the docstring indent.
    """
    wrapped = textwrap.wrap(
        text,
        width=max(width, 20),
        initial_indent=_INDENT if hanging else "",
        subsequent_indent=_INDENT * 2 if hanging else "",
        break_long_words=False,
        break_on_hyphens=False,
    )
    return wrapped or ([f"{_INDENT}{text}"] if hanging else [text])


def _render_docstring(indent: str, summary: str, blocks: list[list[str]]) -> list[str]:
    """Render a Google-style docstring.

    Args:
        indent: The leading whitespace for the docstring.
        summary: The one-line summary.
        blocks: Further paragraphs/sections, each a list of lines relative to
            ``indent``; a blank line is inserted between blocks.

    Returns:
        The rendered docstring lines.
    """
    if not blocks:
        single = f'{indent}"""{summary}"""'
        if len(single) <= LINE_LIMIT:
            return [single]
    lines = [f'{indent}"""{summary}']
    for block in blocks:
        lines.append("")
        lines.extend(f"{indent}{line}" if line else "" for line in block)
    lines.append(f'{indent}"""')
    return lines


def _method_name(op: dict[str, Any], method: str, path: str) -> str:
    """Derive a method name for an operation.

    Args:
        op: The operation object.
        method: The HTTP method (lowercase).
        path: The route path.

    Returns:
        A snake_case method name from ``operationId`` when present, else from
        the method and path segments.
    """
    operation_id = op.get("operationId")
    if operation_id:
        return _snake(operation_id)
    segments = [seg.replace("{", "").replace("}", "") for seg in path.split("/") if seg]
    return _snake("_".join([method, *segments]))


def _is_nullable(schema: dict[str, Any]) -> bool:
    """Report whether a schema admits ``null``.

    Args:
        schema: The schema node.

    Returns:
        True for OpenAPI 3.0 ``nullable`` or 3.1 ``type`` arrays including
        ``"null"``.
    """
    if schema.get("nullable") is True:
        return True
    node_type = schema.get("type")
    return isinstance(node_type, list) and "null" in node_type


def _primary_type(schema: dict[str, Any]) -> str | None:
    """Return the primary (non-null) type of a schema.

    Args:
        schema: The schema node.

    Returns:
        The single type string, or the first non-null entry of a 3.1 type
        array, or None.
    """
    node_type = schema.get("type")
    if isinstance(node_type, list):
        return next((t for t in node_type if t != "null"), None)
    return node_type if isinstance(node_type, str) else None


def _effective(schema: object) -> tuple[dict[str, Any], bool]:
    """Unwrap the nullable wrappers a spec puts around an optional model.

    Pydantic v2 renders ``Role | None`` as ``anyOf: [{$ref}, {type: null}]``, so
    the ``$ref`` is one level down. Without unwrapping, the annotation said
    ``Role | None`` while ``from_dict`` handed back the raw ``dict`` — a nested
    model that was never reconstructed.

    Args:
        schema: The property schema node.

    Returns:
        A tuple ``(inner, nullable)``: the meaningful sub-schema and whether the
        wrapper admitted ``null``.
    """
    if not isinstance(schema, dict):
        return {}, False
    nullable = _is_nullable(schema)
    variants = schema.get("anyOf") or schema.get("oneOf")
    if isinstance(variants, list) and variants:
        non_null = [
            variant
            for variant in variants
            if isinstance(variant, dict) and _primary_type(variant) != "null"
        ]
        if len(non_null) == 1:
            inner, inner_nullable = _effective(non_null[0])
            return inner, nullable or inner_nullable or len(non_null) != len(variants)
        return schema, nullable
    all_of = schema.get("allOf")
    if isinstance(all_of, list) and len(all_of) == 1:
        inner, inner_nullable = _effective(all_of[0])
        return inner, nullable or inner_nullable
    return schema, nullable


def _py_type(schema: dict[str, Any] | None) -> str:
    """Map a schema node to a Python type annotation string.

    Args:
        schema: The schema node, or None.

    Returns:
        A Python annotation (e.g. ``"str"``, ``"list[User]"``,
        ``"str | None"``). References resolve to their generated class name.
    """
    if not isinstance(schema, dict):
        return "Any"
    if "$ref" in schema:
        return ref_name(schema["$ref"])
    if isinstance(schema.get("allOf"), list) and schema["allOf"]:
        return _py_type(schema["allOf"][0])
    variants = schema.get("anyOf") or schema.get("oneOf")
    if isinstance(variants, list) and variants:
        parts: list[str] = []
        for variant in variants:
            rendered = _py_type(variant)
            if rendered not in parts:
                parts.append(rendered)
        return " | ".join(parts)
    enum = schema.get("enum")
    if isinstance(enum, list) and enum and all(isinstance(v, str) for v in enum):
        literals = ", ".join(_py_literal(v) for v in enum)
        base = f"Literal[{literals}]"
        return f"{base} | None" if _is_nullable(schema) else base

    kind = _primary_type(schema)
    if kind == "string":
        base = "str"
    elif kind == "integer":
        base = "int"
    elif kind == "number":
        base = "float"
    elif kind == "boolean":
        base = "bool"
    elif kind == "null":
        return "None"
    elif kind == "array":
        base = f"list[{_py_type(schema.get('items'))}]"
    else:
        extra = schema.get("additionalProperties")
        base = (
            f"dict[str, {_py_type(extra)}]"
            if isinstance(extra, dict)
            else "dict[str, Any]"
        )
    return f"{base} | None" if _is_nullable(schema) else base


def _optional_type(annotation: str) -> str:
    """Widen an annotation so it also admits ``None``.

    Args:
        annotation: The rendered annotation of a property.

    Returns:
        The annotation itself when it already accepts ``None`` (or is ``Any``),
        otherwise the annotation unioned with ``None``.
    """
    if annotation in {"Any", "None"} or annotation.endswith(" | None"):
        return annotation
    return f"{annotation} | None"


def _py_literal(value: object) -> str:
    """Render a Python literal for a JSON scalar.

    Strings are emitted double-quoted (``json.dumps``) rather than through
    ``repr``, which prefers single quotes and would make every generated file
    fail ``ruff format --check``.

    Args:
        value: A JSON scalar (str/bool/int/float/None).

    Returns:
        Its Python source representation.
    """
    if isinstance(value, str):
        return json.dumps(value)
    return repr(value)


def _collect_refs(
    node: object, schemas: dict[str, Any], acc: set[str], seen: set[str]
) -> set[str]:
    """Collect the component names referenced (transitively) by a node.

    Args:
        node: A schema (sub)node to scan.
        schemas: The component-schema map.
        acc: Accumulator of found names (mutated).
        seen: Guard against cyclic recursion (mutated).

    Returns:
        The accumulator ``acc``.
    """
    if not isinstance(node, dict):
        if isinstance(node, list):
            for item in node:
                _collect_refs(item, schemas, acc, seen)
        return acc
    if "$ref" in node:
        name = ref_name(node["$ref"])
        acc.add(name)
        if name not in seen:
            seen.add(name)
            _collect_refs(schemas.get(name), schemas, acc, seen)
        return acc
    for value in node.values():
        if isinstance(value, (dict, list)):
            _collect_refs(value, schemas, acc, seen)
    return acc


def _is_object(schema: dict[str, Any] | None) -> bool:
    """Report whether a schema declares object properties.

    Args:
        schema: The schema node, or None.

    Returns:
        True when the schema has a ``properties`` map.
    """
    return isinstance(schema, dict) and isinstance(schema.get("properties"), dict)


def _success_schema(op: dict[str, Any]) -> dict[str, Any] | None:
    """Return the success (2xx) JSON response schema of an operation.

    Args:
        op: The operation object.

    Returns:
        The response schema node, or None when there is no JSON success body.
    """
    responses = op.get("responses") or {}
    code = next(
        (c for c in ("200", "201", "202", "2XX") if c in responses),
        next((c for c in responses if c.startswith("2")), None),
    )
    if code is None:
        return None
    content = (responses[code] or {}).get("content") or {}
    schema = (content.get("application/json") or {}).get("schema")
    return schema if isinstance(schema, dict) else None


def _body_schema(op: dict[str, Any]) -> dict[str, Any] | None:
    """Return the JSON request-body schema of an operation.

    Args:
        op: The operation object.

    Returns:
        The request-body schema node, or None.
    """
    content = ((op.get("requestBody") or {}).get("content")) or {}
    schema = (content.get("application/json") or {}).get("schema")
    return schema if isinstance(schema, dict) else None


def _ref_class(schema: dict[str, Any], object_names: set[str]) -> str | None:
    """Return the generated dataclass name a schema points at, when it does.

    Args:
        schema: An already-unwrapped schema node.
        object_names: Names emitted as dataclasses.

    Returns:
        The class name, or None when the node is not a reference to one.
    """
    if "$ref" not in schema:
        return None
    name = ref_name(schema["$ref"])
    return name if name in object_names else None


def _field_line(prop_name: str, prop: dict[str, Any], *, required: bool) -> str:
    """Render one dataclass field declaration.

    A property the spec did not mark required is declared ``T | None = None``
    (or an empty-list factory for a plain array). Declaring it ``T = None``, as
    earlier versions did, is an ``assignment`` error in every type checker and
    lies about what the API guarantees.

    Args:
        prop_name: The JSON property name.
        prop: The property schema.
        required: Whether the spec lists the property as required.

    Returns:
        The field source line.
    """
    annotation = _py_type(prop)
    name = _snake(prop_name)
    if required:
        return f"{_INDENT}{name}: {annotation}"
    inner, nullable = _effective(prop)
    if _primary_type(inner) == "array" and not nullable:
        return f"{_INDENT}{name}: {annotation} = field(default_factory=list)"
    return f"{_INDENT}{name}: {_optional_type(annotation)} = None"


def _from_dict_expr(
    prop_name: str, prop: dict[str, Any], object_names: set[str], *, required: bool
) -> str:
    """Build the ``from_dict`` value expression for one field.

    A required property is read with ``data[key]`` — typed ``Any``, so it fits
    the declared field type, and raising ``KeyError`` at the boundary instead of
    storing ``None`` under a non-optional annotation.

    Args:
        prop_name: The JSON property name.
        prop: The property schema.
        object_names: Names emitted as dataclasses.
        required: Whether the spec lists the property as required.

    Returns:
        A Python expression reading the decoded payload, reconstructing nested
        generated models and lists of them.
    """
    key = _py_literal(prop_name)
    inner, nullable = _effective(prop)
    optional = (not required) or nullable
    read = f"data.get({key})" if optional else f"data[{key}]"

    ref = _ref_class(inner, object_names)
    if ref is not None:
        if optional:
            return f"{ref}.from_dict(data[{key}]) if {read} is not None else None"
        return f"{ref}.from_dict({read})"

    if _primary_type(inner) == "array":
        items, _ = _effective(inner.get("items") or {})
        item_ref = _ref_class(items, object_names)
        source = f"(data.get({key}) or [])" if optional else read
        if item_ref is not None:
            return f"[{item_ref}.from_dict(item) for item in {source}]"
        if optional and not nullable:
            return f"data.get({key}) or []"
    return read


def _to_dict_expr(
    prop_name: str, prop: dict[str, Any], object_names: set[str], *, required: bool
) -> str:
    """Build the ``to_dict`` value expression for one field.

    The mirror of :func:`_from_dict_expr`. It exists because the request body
    cannot be built with ``dataclasses.asdict``: Mode C serves no such function
    (the call compiled and then died with a `ReferenceError` on the click), and
    ``asdict`` would key the payload by the *snake_case field* rather than the
    property name the API declared — so any camelCase property was sent under a
    name the server does not read.

    Args:
        prop_name: The JSON property name.
        prop: The property schema.
        object_names: Names emitted as dataclasses.
        required: Whether the spec lists the property as required.

    Returns:
        A Python expression reading ``self.<field>``, unwrapping nested
        generated models and lists of them.
    """
    field_name = _snake(prop_name)
    inner, nullable = _effective(prop)
    optional = (not required) or nullable

    ref = _ref_class(inner, object_names)
    if ref is not None:
        if optional:
            return (
                f"self.{field_name}.to_dict() "
                f"if self.{field_name} is not None else None"
            )
        return f"self.{field_name}.to_dict()"

    if _primary_type(inner) == "array":
        items, _ = _effective(inner.get("items") or {})
        if _ref_class(items, object_names) is not None:
            source = f"(self.{field_name} or [])" if optional else f"self.{field_name}"
            return f"[item.to_dict() for item in {source}]"
    return f"self.{field_name}"


def _emit_dataclass(name: str, schema: dict[str, Any], object_names: set[str]) -> str:
    """Emit a ``@dataclass`` for an object component schema.

    Fields without a default come first (dataclass ordering); optional fields
    default to ``None`` (or an empty list for arrays). A ``from_dict``
    classmethod reconstructs the model, recursing one level into nested
    generated models and lists of them.

    Args:
        name: The component / class name.
        schema: The object schema node.
        object_names: Names of all schemas emitted as dataclasses (for nested
            reconstruction).

    Returns:
        The dataclass source.
    """
    properties: dict[str, Any] = schema.get("properties") or {}
    required: set[str] = set(schema.get("required") or [])

    ordered: list[tuple[str, Any, bool]] = [
        (prop_name, prop, True)
        for prop_name, prop in properties.items()
        if prop_name in required
    ]
    ordered += [
        (prop_name, prop, False)
        for prop_name, prop in properties.items()
        if prop_name not in required
    ]

    title = (
        _clean_text(schema.get("description"))
        or "Generated from the OpenAPI component."
    )
    lines = ["@dataclass", f"class {name}:"]
    lines.extend(_render_docstring(_INDENT, title, []))
    lines.append("")
    lines.extend(
        _field_line(prop_name, prop, required=req) for prop_name, prop, req in ordered
    )
    if ordered:
        lines.append("")

    body_indent = _INDENT * 2
    lines.append(f"{_INDENT}@classmethod")
    lines.append(f"{_INDENT}def from_dict(cls, data: dict[str, Any]) -> {name}:")
    lines.extend(
        _render_docstring(
            body_indent,
            "Build the model from a decoded JSON object.",
            [
                [
                    "Args:",
                    *_wrap(
                        "data: The decoded JSON object.",
                        LINE_LIMIT - len(body_indent),
                        hanging=True,
                    ),
                ],
                ["Returns:", f"{_INDENT}The reconstructed model."],
            ],
        )
    )
    if not ordered:
        lines.append(f"{body_indent}return cls()")
    else:
        lines.append(f"{body_indent}return cls(")
        for prop_name, prop, req in ordered:
            expression = _from_dict_expr(prop_name, prop, object_names, required=req)
            lines.extend(
                _render_entry(_INDENT * 3, f"{_snake(prop_name)}=", expression)
            )
        lines.append(f"{body_indent})")

    lines.append("")
    lines.append(f"{_INDENT}def to_dict(self) -> dict[str, Any]:")
    lines.extend(
        _render_docstring(
            body_indent,
            "Return the model as the JSON object the API expects.",
            [
                [
                    "Returns:",
                    f"{_INDENT}The payload keyed by the property names the spec uses.",
                ]
            ],
        )
    )
    if not ordered:
        lines.append(f"{body_indent}return {{}}")
        return "\n".join(lines)
    lines.append(f"{body_indent}return {{")
    for prop_name, prop, req in ordered:
        expression = _to_dict_expr(prop_name, prop, object_names, required=req)
        lines.extend(
            _render_entry(_INDENT * 3, f"{_py_literal(prop_name)}: ", expression)
        )
    lines.append(f"{body_indent}}}")
    return "\n".join(lines)


def _emit_alias(name: str, schema: dict[str, Any]) -> str:
    """Emit a type alias for a non-object component (enum / scalar).

    Args:
        name: The component name.
        schema: The schema node.

    Returns:
        A ``Name = <type>`` alias line.
    """
    return f"{name} = {_py_type(schema)}"


def _return_lines(response: dict[str, Any] | None, object_names: set[str]) -> list[str]:
    """Build the return statement(s) for a service method.

    A method with no JSON success body returns nothing at all: an explicit
    ``return None`` under a ``-> None`` annotation is what RET501/PLR1711 flag.
    A raw JSON body lands in an annotated local first, because
    ``HttpResponse.json_body`` is ``Any`` and returning it directly is a
    ``warn_return_any`` error under ``mypy --strict``.

    Args:
        response: The success response schema, or None.
        object_names: Names emitted as dataclasses.

    Returns:
        The source lines closing the method body (possibly empty).
    """
    indent = _INDENT * 2
    if response is None:
        return []
    inner, _ = _effective(response)
    ref = _ref_class(inner, object_names)
    if ref is not None:
        return [f"{indent}return {ref}.from_dict(response.json_body)"]
    if _primary_type(inner) == "array":
        items, _ = _effective(inner.get("items") or {})
        item_ref = _ref_class(items, object_names)
        if item_ref is not None:
            expression = f"[{item_ref}.from_dict(item) for item in response.json_body]"
            single = f"{indent}return {expression}"
            if len(single) <= LINE_LIMIT:
                return [single]
            return [
                f"{indent}return [",
                f"{indent}{_INDENT}{expression[1:-1]}",
                f"{indent}]",
            ]
    annotation = _py_type(response)
    return [
        f"{indent}payload: {annotation} = response.json_body",
        f"{indent}return payload",
    ]


def _add_names(accumulator: set[str], *sources: str) -> None:
    """Record every identifier appearing in generated code fragments.

    Args:
        accumulator: The set to add to (mutated).
        *sources: Code fragments (annotations, statements) to scan. Docstrings
            are deliberately not scanned.
    """
    for source in sources:
        accumulator.update(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", source))


def _render_url_assignment(indent: str, interpolated_path: str) -> list[str]:
    """Render ``url = f"{self.base_url}<path>"``, splitting a path that overflows.

    ``ruff format`` never breaks a string literal, so a route long enough to
    push the assignment past :data:`LINE_LIMIT` has to be emitted already split
    into implicitly concatenated pieces — which the formatter then leaves alone
    (it only joins them back when the joined form fits).

    Args:
        indent: The leading whitespace.
        interpolated_path: The route path with its placeholders already renamed
            to the Python parameter names.

    Returns:
        The rendered lines.
    """
    single = f'{indent}url = f"{{self.base_url}}{interpolated_path}"'
    if len(single) <= LINE_LIMIT:
        return [single]
    piece_indent = indent + _INDENT
    budget = LINE_LIMIT - len(piece_indent) - 3
    segments = [f"/{segment}" for segment in interpolated_path.split("/") if segment]
    pieces: list[str] = ["{self.base_url}"]
    for segment in segments:
        if len(pieces[-1]) + len(segment) <= budget:
            pieces[-1] += segment
        else:
            pieces.append(segment)
    return [
        f"{indent}url = (",
        *(f'{piece_indent}f"{piece}"' for piece in pieces),
        f"{indent})",
    ]


def _emit_service_method(
    method: str,
    path: str,
    op: dict[str, Any],
    object_names: set[str],
    used_names: set[str],
    referenced: set[str],
) -> str:
    """Emit one async service method for an operation.

    Args:
        method: HTTP method (lowercase).
        path: Route path.
        op: The operation object.
        object_names: Names emitted as dataclasses.
        used_names: Method names already used in this service (mutated for
            de-duplication).
        referenced: Component names the emitted *code* mentions (mutated). A
            name only a docstring mentions must not be imported — that is the
            F401 the service modules used to carry.

    Returns:
        The method source.
    """
    name = _method_name(op, method, path)
    if name in used_names:
        suffix = 2
        while f"{name}_{suffix}" in used_names:
            suffix += 1
        name = f"{name}_{suffix}"
    used_names.add(name)

    parameters = op.get("parameters") or []
    path_params = [p for p in parameters if p.get("in") == "path"]
    query_params = [p for p in parameters if p.get("in") == "query"]
    body = _body_schema(op)
    response = _success_schema(op)

    doc_indent = _INDENT * 2
    doc_width = LINE_LIMIT - len(doc_indent)
    args = ["self"]
    arg_docs: list[str] = []
    for param in path_params:
        annotation = _py_type(param.get("schema") or {"type": "string"})
        args.append(f"{_snake(str(param['name']))}: {annotation}")
        raw_name = str(param["name"])
        described = _clean_text(param.get("description"))
        fallback = f"The ``{raw_name}`` path parameter."
        arg_docs.extend(
            _wrap(
                f"{_snake(raw_name)}: {described or fallback}",
                doc_width,
                hanging=True,
            )
        )

    body_inner, _ = _effective(body) if body is not None else ({}, False)
    body_class = _ref_class(body_inner, object_names) if body is not None else None
    if body is not None:
        args.append(f"body: {_py_type(body) if body_class else 'Any'}")
        body_doc = (
            "body: The JSON request body."
            if body_class is None
            else f"body: The ``{body_class}`` request body."
        )
        arg_docs.extend(_wrap(body_doc, doc_width, hanging=True))
    if query_params:
        args.append("params: dict[str, Any] | None = None")
        declared = ", ".join(f"``{p['name']}``" for p in query_params)
        arg_docs.extend(
            _wrap(
                "params: Query parameters appended to the URL; the route "
                f"declares {declared}.",
                doc_width,
                hanging=True,
            )
        )

    interpolated = re.sub(r"{([^}]+)}", lambda m: "{" + _snake(m.group(1)) + "}", path)
    return_type = _py_type(response) if response is not None else "None"
    _add_names(referenced, " ".join(args), return_type)

    blocks: list[list[str]] = []
    described = _clean_text(op.get("summary")) or _clean_text(op.get("description"))
    if described:
        blocks.append(_wrap(described, doc_width))
    if arg_docs:
        blocks.append(["Args:", *arg_docs])
    if return_type != "None":
        returns_doc = f"The decoded ``{return_type}`` response body."
        blocks.append(["Returns:", *_wrap(returns_doc, doc_width, hanging=True)])
    blocks.append(
        [
            "Raises:",
            *_wrap(
                "ApiError: When the API answers with a non-2xx status.",
                doc_width,
                hanging=True,
            ),
        ]
    )

    lines = _render_sequence(
        _INDENT,
        f"async def {name}",
        args,
        tail=f" -> {return_type}:",
    )
    summary = f"Call ``{method.upper()} {path}``."
    if len(doc_indent) + 3 + len(summary) > LINE_LIMIT:
        blocks.insert(0, _wrap(summary, doc_width))
        summary = f"Call the ``{method.upper()}`` route of this group."
    lines.extend(_render_docstring(doc_indent, summary, blocks))
    lines.extend(_render_url_assignment(doc_indent, interpolated))
    if query_params:
        lines.append(f"{doc_indent}url += _encode_query(params or {{}})")
    call_args = [f'"{method.upper()}"', "url"]
    if body is not None:
        call_args.append("json=body.to_dict()" if body_class else "json=body")
    call_args.append("headers=self.headers")
    lines.extend(_render_sequence(doc_indent, "response = await request", call_args))
    lines.append(f"{doc_indent}if not response.ok:")
    lines.extend(
        _render_sequence(
            _INDENT * 3,
            "raise ApiError",
            [
                'f"HTTP {response.status}: {response.text}"',
                "response.status",
                "response.json_body",
            ],
        )
    )
    return_lines = _return_lines(response, object_names)
    _add_names(referenced, *return_lines)
    lines.extend(return_lines)
    return "\n".join(lines)


_RUNTIME_MODULE = '''"""Shared runtime for the generated API client.

Generated by `tempestweb gen api` — do not edit.
"""

from __future__ import annotations

from typing import Any

__all__ = ["ApiError", "encode_query"]


class ApiError(Exception):
    """Raised when the API returns a non-2xx response.

    The message comes first because Mode C keeps only that argument: a
    transpiled `raise` throws an `Error` carrying the first argument as its
    message and the class name as `name`, so `status` and `body` are readable
    under Modes A and B only.
    """

    def __init__(self, message: str, status: int = 0, body: Any = None) -> None:
        """Initialize the error.

        Args:
            message: The human-readable summary (status and response text).
            status: The HTTP status code.
            body: The decoded JSON body, when present.
        """
        self.status = status
        self.body = body
        super().__init__(message)


def encode_query(params: dict[str, Any]) -> str:
    """Encode a query-string from a params map, skipping ``None`` values.

    Args:
        params: Query parameters.

    Returns:
        A ``"?a=1&b=2"`` string, or ``""`` when nothing remains.
    """
    parts: list[str] = []
    for key, value in params.items():
        if value is None:
            continue
        rendered = ("true" if value else "false") if isinstance(value, bool) else value
        parts.append(f"{key}={rendered}")
    return "?" + "&".join(parts) if parts else ""
'''


def _module_header(summary: str) -> str:
    """Render the module docstring every generated file opens with.

    Args:
        summary: The one-line summary of the module.

    Returns:
        The docstring source, terminated by a blank line.
    """
    return f'"""{summary}\n\nGenerated by `tempestweb gen api` — do not edit.\n"""\n'


def _typing_imports(body: str) -> list[str]:
    """Return the ``typing`` names a generated body actually mentions.

    Args:
        body: The already-rendered module body.

    Returns:
        The subset of ``Any``/``Literal`` referenced, in import order. Emitting
        the full pair unconditionally is what produced the F401 flood.
    """
    return [name for name in ("Any", "Literal") if re.search(rf"\b{name}\b", body)]


def _emit_schemas_module(tag: str, blocks: list[str]) -> str:
    """Render a tag's ``schemas.py``.

    Args:
        tag: The OpenAPI tag the group came from.
        blocks: The rendered dataclass/alias sources.

    Returns:
        The module source.
    """
    body = "\n\n\n".join(blocks)
    header = _module_header(f"Models for the '{_clean_text(tag).rstrip('.')}' routes.")
    if not blocks:
        return f"{header}"
    imports = ["from __future__ import annotations", ""]
    if re.search(r"@dataclass\b", body):
        needed = ["dataclass"]
        if re.search(r"\bfield\(", body):
            needed.append("field")
        imports.append(f"from dataclasses import {', '.join(needed)}")
    typing_names = _typing_imports(body)
    if typing_names:
        imports.append(f"from typing import {', '.join(typing_names)}")
    return f"{header}\n" + "\n".join(imports) + f"\n\n\n{body}\n"


def generate(doc: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    """Generate the per-tag client files from a parsed OpenAPI document.

    Args:
        doc: The parsed OpenAPI 3.x document.

    Returns:
        A tuple ``(files, tags)`` where ``files`` maps relative paths to file
        contents and ``tags`` lists the tags that produced a group.
    """
    schemas: dict[str, Any] = (doc.get("components") or {}).get("schemas") or {}
    object_names = {name for name, schema in schemas.items() if _is_object(schema)}

    groups: dict[str, dict[str, Any]] = {}
    for path, item in (doc.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method in HTTP_METHODS:
            op = item.get(method)
            if not isinstance(op, dict):
                continue
            tag = (op.get("tags") or ["default"])[0]
            slug = _tag_slug(tag)
            group = groups.setdefault(slug, {"tag": tag, "slug": slug, "ops": []})
            group["ops"].append({"method": method, "path": path, "op": op})

    files: dict[str, str] = {}
    tags: list[str] = []
    files["_runtime.py"] = _RUNTIME_MODULE

    for group in groups.values():
        slug = group["slug"]
        tag = group["tag"]
        tags.append(tag)
        service_class = f"{_pascal(slug)}Service"

        used: set[str] = set()
        for entry in group["ops"]:
            for schema in (_body_schema(entry["op"]), _success_schema(entry["op"])):
                if schema:
                    _collect_refs(schema, schemas, used, set())
        used_sorted = sorted(used)

        blocks: list[str] = [
            _emit_alias(cname, schemas.get(cname) or {})
            for cname in used_sorted
            if not _is_object(schemas.get(cname) or {})
        ]
        blocks += [
            _emit_dataclass(cname, schemas.get(cname) or {}, object_names)
            for cname in used_sorted
            if _is_object(schemas.get(cname) or {})
        ]
        files[f"{slug}/schemas.py"] = _emit_schemas_module(tag, blocks)

        used_method_names: set[str] = set()
        referenced: set[str] = set()
        methods = [
            _emit_service_method(
                entry["method"],
                entry["path"],
                entry["op"],
                object_names,
                used_method_names,
                referenced,
            )
            for entry in group["ops"]
        ]
        service_imports = [name for name in used_sorted if name in referenced]
        body = "\n\n".join(methods)

        header = _module_header(
            f"Service for the '{_clean_text(tag).rstrip('.')}' routes."
        )
        import_lines = ["from __future__ import annotations", ""]
        import_lines.append("from dataclasses import dataclass, field")
        typing_names = _typing_imports(body)
        if typing_names:
            import_lines.append(f"from typing import {', '.join(typing_names)}")
        import_lines.append("")
        import_lines.append("from tempestweb.native.http import request")
        import_lines.append("")
        import_lines.append("from .._runtime import ApiError")
        if "_encode_query(" in body:
            import_lines.append("from .._runtime import encode_query as _encode_query")
        if service_imports:
            import_lines.extend(_render_import(".schemas", service_imports))

        service_doc = _render_docstring(
            _INDENT,
            f"Client for the '{_clean_text(tag).rstrip('.')}' routes.",
            [
                [
                    "Attributes:",
                    *_wrap(
                        "base_url: Base URL prefix prepended to every route. Give it "
                        "without a trailing slash — the routes carry their own.",
                        LINE_LIMIT - len(_INDENT),
                        hanging=True,
                    ),
                    *_wrap(
                        "headers: Default headers sent with every request.",
                        LINE_LIMIT - len(_INDENT),
                        hanging=True,
                    ),
                ]
            ],
        )
        service_lines = [
            "@dataclass",
            f"class {service_class}:",
            *service_doc,
            "",
            '    base_url: str = ""',
            "    headers: dict[str, str] = field(default_factory=dict)",
            "",
            "",
        ]
        files[f"{slug}/service.py"] = (
            f"{header}\n"
            + "\n".join(import_lines)
            + "\n\n\n"
            + "\n".join(service_lines)
            + body
            + "\n"
        )

        exported = _sorted_exports([*used_sorted, service_class])
        init_lines = [
            *(f"from .schemas import {name} as {name}" for name in used_sorted),
            f"from .service import {service_class} as {service_class}",
            "",
        ]
        files[f"{slug}/__init__.py"] = (
            _module_header(f"The '{_clean_text(tag).rstrip('.')}' route group.")
            + "\n"
            + "\n".join(init_lines)
            + "\n"
            + "\n".join(
                _render_sequence(
                    "",
                    "__all__ = ",
                    [_py_literal(n) for n in exported],
                    open_char="[",
                    close_char="]",
                )
            )
            + "\n"
        )

    slugs = sorted(group["slug"] for group in groups.values())
    root_lines = [f"from . import {slug} as {slug}" for slug in slugs]
    if not root_lines:
        files["__init__.py"] = ""
        return files, tags
    files["__init__.py"] = (
        _module_header("Typed API client generated from an OpenAPI document.")
        + "\n"
        + "\n".join(root_lines)
        + "\n\n"
        + "\n".join(
            _render_sequence(
                "",
                "__all__ = ",
                [_py_literal(slug) for slug in _sorted_exports(slugs)],
                open_char="[",
                close_char="]",
            )
        )
        + "\n"
    )
    return files, tags
