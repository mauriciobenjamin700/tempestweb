"""Generate the manifest of the native facade Mode C serves in-process.

``from tempestweb.native import get_position`` is the same import as
``from tempestweb import native`` followed by ``native.geolocation.get_position``
— Python spells it two ways and means one thing. The compiler needs to map the
submodule form onto the facade, and to refuse a name the facade does not carry
**by that name**, so this writes :mod:`tempestweb.transpile._native`: the facade's
shape, taken from ``client/transpile/native.js`` itself, crossed with what the
Python package re-exports.

Two sources, on purpose:

* the **JS** decides what exists at runtime — it is what the browser loads, and a
  member the facade lacks is a dead call no matter what Python says;
* the **Python package** decides how a flat name resolves — ``get_position`` is a
  top-level re-export of ``tempestweb.native.geolocation``, and only the package
  knows which group owns a bare name.

Regenerate: ``python -m tests.conformance._transpile_native``.
"""

from __future__ import annotations

import enum
import inspect
import json
import shutil
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any

import tempestweb.native as native_pkg

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
CLIENT_DIR: Path = REPO_ROOT / "client" / "transpile"
NATIVE_MODULE: Path = REPO_ROOT / "tempestweb" / "transpile" / "_native.py"

_INTROSPECT = """
import * as facade from "{facade}";
const members = {{}};
for (const [group, ns] of Object.entries(facade.native)) {{
  members[group] = Object.keys(ns).sort();
}}
console.log(JSON.stringify({{ exports: Object.keys(facade).sort(), members }}));
"""


def facade_shape() -> dict[str, Any]:
    """Read the facade's shape by loading the JS the artifact ships.

    Returns:
        A mapping with ``exports`` (the module's top-level exports) and
        ``members`` (group name to sorted member names).

    Raises:
        RuntimeError: If node is unavailable or the module fails to load.
    """
    if shutil.which("node") is None:
        raise RuntimeError("node is required to introspect the native facade")
    script = _INTROSPECT.format(facade=(CLIENT_DIR / "native.js").as_posix())
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"native.js failed to load:\n{result.stderr}")
    shape: dict[str, Any] = json.loads(result.stdout)
    return shape


def _group_of(obj: object) -> str | None:
    """Return the native group a re-exported object comes from.

    Args:
        obj: The object bound to a name in ``tempestweb.native``.

    Returns:
        The submodule's last dotted part, or ``None`` when it is not defined in
        a ``tempestweb.native`` submodule.
    """
    module = getattr(obj, "__module__", None)
    if module is None or not module.startswith("tempestweb.native."):
        return None
    return module.rsplit(".", 1)[-1]


def collect() -> dict[str, Any]:
    """Cross the facade's shape with what the Python package re-exports.

    Returns:
        A mapping with ``exports``, ``members``, ``flat`` (bare name to
        ``"group.member"``), ``enums`` (string enum to its members, which do
        carry a value), ``types`` (group to class names, which carry no runtime
        value in Mode C) and ``groups`` (every Python submodule name).
    """
    shape = facade_shape()
    members: dict[str, list[str]] = shape["members"]
    flat: dict[str, str] = {}
    types: dict[str, set[str]] = {}
    enums: dict[str, dict[str, str]] = {}
    groups: set[str] = set()
    for name in native_pkg.__all__:
        obj: object = getattr(native_pkg, name)
        if isinstance(obj, ModuleType):
            groups.add(name)
            continue
        group = _group_of(obj)
        if group is None:
            continue
        groups.add(group)
        if inspect.isclass(obj):
            types.setdefault(group, set()).add(name)
            if issubclass(obj, enum.Enum) and all(
                isinstance(member.value, str) for member in obj
            ):
                enums[name] = {member.name: member.value for member in obj}
        elif name in members.get(group, []):
            flat[name] = f"{group}.{name}"
    return {
        "exports": shape["exports"],
        "members": members,
        "enums": enums,
        "flat": flat,
        "types": {group: sorted(names) for group, names in types.items()},
        "groups": sorted(groups),
    }


def _render_str_set(names: list[str], indent: str) -> str:
    """Render a sorted set literal body.

    Args:
        names: The names to render.
        indent: The indentation each entry carries.

    Returns:
        The rendered lines, one name per line.
    """
    return "\n".join(f'{indent}"{name}",' for name in sorted(names))


def _render_mapping(mapping: dict[str, list[str]]) -> str:
    """Render a ``str -> frozenset[str]`` mapping literal body.

    Args:
        mapping: The mapping to render.

    Returns:
        The rendered entries, one group per block.
    """
    blocks: list[str] = []
    for group, names in sorted(mapping.items()):
        entries = _render_str_set(names, " " * 12)
        blocks.append(
            f'    "{group}": frozenset(\n        {{\n{entries}\n        }}\n    ),'
        )
    return "\n".join(blocks)


def render_module_text() -> str:
    """Render the Python manifest source.

    Returns:
        The full ``_native.py`` source.
    """
    data = collect()
    exports = _render_str_set(data["exports"], " " * 8)
    members = _render_mapping(data["members"])
    types = _render_mapping(data["types"])
    groups = _render_str_set(data["groups"], " " * 8)
    flat = "\n".join(
        f'    "{name}": "{path}",' for name, path in sorted(data["flat"].items())
    )
    enums = "\n".join(
        f'    "{name}": {{\n'
        + "\n".join(
            f'        "{member}": "{value}",' for member, value in sorted(body.items())
        )
        + "\n    },"
        for name, body in sorted(data["enums"].items())
    )
    return f'''"""GENERATED from the Mode C client and the native package.

Regenerate: ``python -m tests.conformance._transpile_native``.

The shape of the native facade ``client/transpile/native.js`` exposes, plus how
a bare name re-exported by ``tempestweb.native`` resolves onto it. The compiler
maps every import form onto the same facade and refuses an unknown member by its
own name. Do not edit by hand.
"""

from __future__ import annotations

from collections.abc import Mapping

__all__: list[str] = [
    "NATIVE_ENUMS",
    "NATIVE_EXPORTS",
    "NATIVE_FLAT",
    "NATIVE_GROUPS",
    "NATIVE_MEMBERS",
    "NATIVE_TYPES",
]

#: Top-level exports of ``native.js`` — importable straight from the module.
NATIVE_EXPORTS: frozenset[str] = frozenset(
    {{
{exports}
    }}
)

#: Facade group to the members it serves, by generation from the JS itself.
NATIVE_MEMBERS: Mapping[str, frozenset[str]] = {{
{members}
}}

#: Bare name re-exported by ``tempestweb.native`` to its ``group.member`` path.
NATIVE_FLAT: Mapping[str, str] = {{
{flat}
}}

#: Group to the classes it exports, which carry no runtime value in Mode C:
#: the facade returns plain objects, so these names are annotation-only.
NATIVE_TYPES: Mapping[str, frozenset[str]] = {{
{types}
}}

#: String enum the package exports to its members. The facade speaks JSON, so
#: these cross the wire as their value and Mode C emits them as a frozen table.
NATIVE_ENUMS: Mapping[str, Mapping[str, str]] = {{
{enums}
}}

#: Every capability group the Python package has, served or not — so a real
#: group the facade does not carry is refused by name instead of by module.
NATIVE_GROUPS: frozenset[str] = frozenset(
    {{
{groups}
    }}
)
'''


def write_module() -> Path:
    """Write the manifest to disk.

    Returns:
        The path written.
    """
    NATIVE_MODULE.write_text(render_module_text(), encoding="utf-8")
    return NATIVE_MODULE


def main() -> None:
    """Regenerate the manifest and print its path."""
    print(f"wrote {write_module()}")


if __name__ == "__main__":
    main()
