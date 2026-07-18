"""OpenAPI 3.x → typed tempestweb API client (dataclasses + service classes).

Pure and deterministic: :func:`generate` takes a parsed OpenAPI document and
returns a ``{relative_path: file_contents}`` map plus the list of tags — no I/O.
The emitted client uses only constructs the tempestweb transpiler and both
runtime modes accept: ``@dataclass`` models and calls to
:func:`tempestweb.native.http.request`.
"""

from __future__ import annotations

import keyword
import re
from typing import Any

__all__ = ["generate"]

HTTP_METHODS: tuple[str, ...] = ("get", "post", "put", "patch", "delete")


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
    return node_type


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
        parts = []
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


def _py_literal(value: object) -> str:
    """Render a Python literal for a JSON scalar.

    Args:
        value: A JSON scalar (str/bool/int/float/None).

    Returns:
        Its Python source representation.
    """
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

    required_fields: list[tuple[str, Any]] = []
    optional_fields: list[tuple[str, Any]] = []
    for prop_name, prop in properties.items():
        (required_fields if prop_name in required else optional_fields).append(
            (prop_name, prop)
        )

    lines = [
        "@dataclass",
        f"class {name}:",
        '    """Generated from the OpenAPI component."""',
    ]
    if not properties:
        lines.append("    pass")

    for prop_name, prop in required_fields:
        lines.append(f"    {_snake(prop_name)}: {_py_type(prop)}")
    for prop_name, prop in optional_fields:
        annotation = _py_type(prop)
        if _primary_type(prop) == "array":
            lines.append(
                f"    {_snake(prop_name)}: {annotation} = field(default_factory=list)"
            )
        else:
            lines.append(f"    {_snake(prop_name)}: {annotation} = None")

    lines.append("")
    lines.append("    @classmethod")
    lines.append(f'    def from_dict(cls, data: dict[str, Any]) -> "{name}":')
    lines.append('        """Build the model from a decoded JSON object."""')
    if not properties:
        lines.append("        return cls()")
        return "\n".join(lines)
    lines.append("        return cls(")
    for prop_name, prop in [*required_fields, *optional_fields]:
        value = _from_dict_expr(prop_name, prop, object_names)
        lines.append(f"            {_snake(prop_name)}={value},")
    lines.append("        )")
    return "\n".join(lines)


def _from_dict_expr(
    prop_name: str, prop: dict[str, Any], object_names: set[str]
) -> str:
    """Build the ``from_dict`` value expression for one field.

    Args:
        prop_name: The JSON property name.
        prop: The property schema.
        object_names: Names emitted as dataclasses.

    Returns:
        A Python expression reading ``data[...]``, reconstructing nested
        generated models and lists of them.
    """
    key = _py_literal(prop_name)
    if isinstance(prop, dict) and "$ref" in prop:
        ref = ref_name(prop["$ref"])
        if ref in object_names:
            return (
                f"{ref}.from_dict(data[{key}]) if data.get({key}) is not None else None"
            )
    if isinstance(prop, dict) and _primary_type(prop) == "array":
        items = prop.get("items") or {}
        if (
            isinstance(items, dict)
            and "$ref" in items
            and ref_name(items["$ref"]) in object_names
        ):
            ref = ref_name(items["$ref"])
            return f"[{ref}.from_dict(item) for item in (data.get({key}) or [])]"
    return f"data.get({key})"


def _emit_alias(name: str, schema: dict[str, Any]) -> str:
    """Emit a type alias for a non-object component (enum / scalar).

    Args:
        name: The component name.
        schema: The schema node.

    Returns:
        A ``Name = <type>`` alias line.
    """
    return f"{name} = {_py_type(schema)}"


def _emit_service_method(
    method: str,
    path: str,
    op: dict[str, Any],
    object_names: set[str],
    used_names: set[str],
) -> str:
    """Emit one async service method for an operation.

    Args:
        method: HTTP method (lowercase).
        path: Route path.
        op: The operation object.
        object_names: Names emitted as dataclasses.
        used_names: Method names already used in this service (mutated for
            de-duplication).

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

    args = ["self"]
    for param in path_params:
        annotation = _py_type(param.get("schema") or {"type": "string"})
        args.append(f"{_snake(param['name'])}: {annotation}")
    body_is_model = bool(
        body and "$ref" in body and ref_name(body["$ref"]) in object_names
    )
    if body is not None:
        args.append(f"body: {_py_type(body) if body_is_model else 'Any'}")
    if query_params:
        args.append("params: dict[str, Any] | None = None")

    interpolated = re.sub(r"{([^}]+)}", lambda m: "{" + _snake(m.group(1)) + "}", path)
    url_literal = f'f"{{self._base_url}}{interpolated}"'

    return_type = _py_type(response) if response is not None else "None"

    summary = op.get("summary") or ""
    doc = f"{method.upper()} {path}" + (f" — {summary}" if summary else "")

    lines = [
        f"    async def {name}({', '.join(args)}) -> {return_type}:",
        f'        """{doc}"""',
        f"        url = {url_literal}",
    ]
    if query_params:
        lines.append("        url += _encode_query(params or {})")
    call_args = [f'"{method.upper()}"', "url"]
    if body is not None:
        call_args.append("json=asdict(body)" if body_is_model else "json=body")
    call_args.append("headers=self._headers")
    lines.append(f"        response = await request({', '.join(call_args)})")
    lines.append("        if not response.ok:")
    lines.append(
        "            raise ApiError(response.status, response.text, response.json_body)"
    )
    lines.append(_return_expr(response, object_names))
    return "\n".join(lines)


def _return_expr(response: dict[str, Any] | None, object_names: set[str]) -> str:
    """Build the return statement for a service method.

    Args:
        response: The success response schema, or None.
        object_names: Names emitted as dataclasses.

    Returns:
        A ``return ...`` line reconstructing the typed response.
    """
    if response is None:
        return "        return None"
    if "$ref" in response and ref_name(response["$ref"]) in object_names:
        ref = ref_name(response["$ref"])
        return f"        return {ref}.from_dict(response.json_body)"
    if _primary_type(response) == "array":
        items = response.get("items") or {}
        if (
            isinstance(items, dict)
            and "$ref" in items
            and ref_name(items["$ref"]) in object_names
        ):
            ref = ref_name(items["$ref"])
            return (
                f"        return [{ref}.from_dict(item) for item in response.json_body]"
            )
    return "        return response.json_body"


_RUNTIME_MODULE = '''"""Shared runtime for the generated API client."""

from __future__ import annotations

from typing import Any

__all__ = ["ApiError", "encode_query"]


class ApiError(Exception):
    """Raised when the API returns a non-2xx response."""

    def __init__(self, status: int, message: str, body: Any = None) -> None:
        """Initialize the error.

        Args:
            status: The HTTP status code.
            message: The response body text.
            body: The decoded JSON body, when present.
        """
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status}: {message}")


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
        if isinstance(value, bool):
            value = "true" if value else "false"
        parts.append(f"{key}={value}")
    return "?" + "&".join(parts) if parts else ""
'''


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

        blocks: list[str] = []
        for cname in used_sorted:
            cschema = schemas.get(cname) or {}
            if _is_object(cschema):
                blocks.append(_emit_dataclass(cname, cschema, object_names))
            else:
                blocks.append(_emit_alias(cname, cschema))
        schema_body = (
            "\n\n\n".join(blocks)
            if blocks
            else "# no components referenced by this tag"
        )
        files[f"{slug}/schemas.py"] = (
            "# Generated by `tempestweb gen api` — do not edit.\n"
            "from __future__ import annotations\n\n"
            "from dataclasses import dataclass, field\n"
            "from typing import Any, Literal\n\n\n"
            f"{schema_body}\n"
        )

        used_method_names: set[str] = set()
        methods = [
            _emit_service_method(
                entry["method"],
                entry["path"],
                entry["op"],
                object_names,
                used_method_names,
            )
            for entry in group["ops"]
        ]
        model_imports = list(used_sorted)
        schema_import = (
            f"from .schemas import {', '.join(model_imports)}\n"
            if model_imports
            else ""
        )
        files[f"{slug}/service.py"] = (
            "# Generated by `tempestweb gen api` — do not edit.\n"
            "from __future__ import annotations\n\n"
            "from dataclasses import asdict\n"
            "from typing import Any\n\n"
            "from tempestweb.native.http import request\n\n"
            "from .._runtime import ApiError, encode_query as _encode_query\n"
            f"{schema_import}\n\n"
            f"class {service_class}:\n"
            f'    """Generated service for the "{tag}" routes."""\n\n'
            '    def __init__(self, base_url: str = "", '
            "headers: dict[str, str] | None = None) -> None:\n"
            '        """Initialize the service.\n\n'
            "        Args:\n"
            "            base_url: Base URL prefix prepended to every route.\n"
            "            headers: Default headers sent with every request.\n"
            '        """\n'
            '        self._base_url = base_url.rstrip("/")\n'
            "        self._headers = headers or {}\n\n" + "\n\n".join(methods) + "\n"
        )

        files[f"{slug}/__init__.py"] = (
            "from .schemas import *  # noqa: F401,F403\n"
            f"from .service import {service_class}  # noqa: F401\n"
        )

    root_lines = [
        f"from . import {group['slug']} as {group['slug']}  # noqa: F401"
        for group in groups.values()
    ]
    files["__init__.py"] = "\n".join(root_lines) + "\n" if root_lines else ""
    return files, tags
