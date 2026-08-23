"""Generate the manifest of members each served Mode C value actually carries.

``_served.py`` answers "does the client export this name?". It cannot answer
"does that name have this method?", and the gap is the same failure with a
different shape: ``Color.from_hex(...)`` and ``Theme.from_seed(...)`` compile,
parse, load — and throw ``is not a function`` at mount, with a blank page and a
single line in the console. ``node --check`` cannot see it, because it parses
without executing.

This introspects the client in Node — the only honest source, since the JS is
what the browser loads — and writes
:mod:`tempestweb.transpile._members`, so the compiler refuses an unported member
at build time with a ``file:line``.

Only the *own* properties of an exported function or class count: a factory's
attached helpers (``Edge.all``) and a class's statics (``Theme.from_seed``,
when it exists). Nothing else on the object is part of the contract.

Run as a module to (re)write it::

    python -m tests.conformance._transpile_value_members
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from tempestweb.cli.commands.build import _TRANSPILE_ASSETS

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
CLIENT_DIR: Path = REPO_ROOT / "client" / "transpile"
MEMBERS_MODULE: Path = REPO_ROOT / "tempestweb" / "transpile" / "_members.py"

#: Properties every JS function carries, which say nothing about the port.
_INTRINSIC: frozenset[str] = frozenset(
    {"length", "name", "prototype", "caller", "arguments"}
)

_INTROSPECT = """
const modules = {modules};
const out = {{}};
for (const file of modules) {{
  const mod = await import(`{client}/${{file}}`);
  for (const [name, value] of Object.entries(mod)) {{
    if (typeof value !== "function") continue;
    const own = Object.getOwnPropertyNames(value).filter(
      (k) => !["length", "name", "prototype", "caller", "arguments"].includes(k),
    );
    out[name] = [...new Set([...(out[name] ?? []), ...own])].sort();
  }}
}}
console.log(JSON.stringify(out));
"""


def collect() -> dict[str, list[str]]:
    """Introspect the client for every exported value's own members.

    Returns:
        A name → sorted member list map, for the exports that carry any.

    Raises:
        RuntimeError: If node is unavailable or the introspection fails.
    """
    if shutil.which("node") is None:
        raise RuntimeError("node is required to introspect the Mode C client")
    script = _INTROSPECT.format(
        client=CLIENT_DIR.as_posix(),
        modules=json.dumps(sorted(_TRANSPILE_ASSETS)),
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"introspection failed:\n{result.stderr}")
    members: dict[str, list[str]] = json.loads(result.stdout)
    return {name: sorted(set(ms) - _INTRINSIC) for name, ms in sorted(members.items())}


def render_module_text() -> str:
    """Render the Python manifest source."""
    entries = "\n".join(
        '    "{name}": frozenset({{{members}}}),'.format(
            name=name, members=", ".join(f'"{m}"' for m in members)
        )
        for name, members in collect().items()
        if members
    )
    return (
        '"""GENERATED from the Mode C client.\n'
        "\n"
        "Regenerate: ``python -m tests.conformance._transpile_value_members``.\n"
        "\n"
        "The members each served value carries in the JS. A call on anything else\n"
        "is refused at build time, because it would compile, load and then throw\n"
        "``is not a function`` at mount — the failure ``node --check`` cannot see.\n"
        "Do not edit by hand.\n"
        '"""\n'
        "\n"
        "from __future__ import annotations\n"
        "\n"
        '__all__: list[str] = ["VALUE_MEMBERS"]\n'
        "\n"
        "#: Served name -> the members the client's own object carries.\n"
        "VALUE_MEMBERS: dict[str, frozenset[str]] = {\n"
        f"{entries}\n"
        "}\n"
    )


def write_module() -> Path:
    """Write the manifest to disk and return its path."""
    MEMBERS_MODULE.write_text(render_module_text(), encoding="utf-8")
    return MEMBERS_MODULE


def main() -> None:
    """Regenerate the manifest and print its path."""
    print(f"wrote {write_module()}")


if __name__ == "__main__":
    main()
