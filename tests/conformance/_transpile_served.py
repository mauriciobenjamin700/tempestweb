"""Generate the manifest of names Mode C's JS actually exports.

The transpiler routes every ``tempest_core`` name a module references to an
import in the emitted JS. Nothing checked that the target exists, so a view
using a name the client does not export compiled cleanly into a module the
browser refuses to load — a blank page with an import error, which no test
could see: ``node --check`` parses without resolving imports, and the goldens
compare text.

This writes :mod:`tempestweb.transpile._served`, the frozen set of identifiers
the artifact's client modules export, so the compiler can refuse the name at
build time with a ``file:line`` instead of shipping a dead import. The manifest
lives in the package (it ships in the wheel) and is regenerated from the JS
itself, which is the only honest source: the JS is what the browser loads.
"""

from __future__ import annotations

import re
from pathlib import Path

from tempestweb.cli.commands.build import _TRANSPILE_ASSETS

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
CLIENT_DIR: Path = REPO_ROOT / "client" / "transpile"
SERVED_MODULE: Path = REPO_ROOT / "tempestweb" / "transpile" / "_served.py"

_DECLARATION = re.compile(
    r"^export (?:function|const|class|let|var) ([A-Za-z_$][\w$]*)", re.M
)
_NAMED_BLOCK = re.compile(r"^export \{([^}]*)\}", re.M)
_STAR = re.compile(r'^export \* from "\./([\w.-]+)"', re.M)


def _exports(module: str, seen: set[str] | None = None) -> set[str]:
    """Every identifier a client module exports, following star re-exports.

    Args:
        module: The module's file name inside ``client/transpile/``.
        seen: Modules already walked, guarding against a re-export cycle.

    Returns:
        The exported identifiers.
    """
    seen = seen if seen is not None else set()
    if module in seen:
        return set()
    seen.add(module)
    path = CLIENT_DIR / module
    if not path.exists():
        return set()
    text = path.read_text(encoding="utf-8")
    names = set(_DECLARATION.findall(text))
    for block in _NAMED_BLOCK.findall(text):
        names |= {
            part.split(" as ")[-1].strip() for part in block.split(",") if part.strip()
        }
    for star in _STAR.findall(text):
        names |= _exports(star, seen)
    return names


def collect() -> set[str]:
    """The names every Mode C artifact can resolve.

    Returns:
        The union of the exports of the modules the build copies into the
        artifact.
    """
    names: set[str] = set()
    for module in _TRANSPILE_ASSETS:
        names |= _exports(module)
    return names


def render_module_text() -> str:
    """Render the Python manifest source.

    Returns:
        The full ``_served.py`` source.
    """
    entries = "\n".join(f'        "{name}",' for name in sorted(collect()))
    return (
        '"""GENERATED from the Mode C client.\n'
        "\n"
        "Regenerate: ``python -m tests.conformance._transpile_served``.\n"
        "\n"
        "The identifiers ``client/transpile/`` exports, which is exactly what a\n"
        "transpiled module may import. The compiler refuses any other name instead\n"
        "of emitting an import the browser cannot resolve. Do not edit by hand.\n"
        '"""\n'
        "\n"
        "from __future__ import annotations\n"
        "\n"
        '__all__: list[str] = ["SERVED_NAMES"]\n'
        "\n"
        "#: Names the Mode C client exports, by generation from the JS itself.\n"
        "SERVED_NAMES: frozenset[str] = frozenset(\n"
        "    {\n"
        f"{entries}\n"
        "    }\n"
        ")\n"
    )


def write_module() -> Path:
    """Write the manifest to disk.

    Returns:
        The path written.
    """
    SERVED_MODULE.write_text(render_module_text(), encoding="utf-8")
    return SERVED_MODULE


def main() -> None:
    """Regenerate the manifest and print its path."""
    print(f"wrote {write_module()}")


if __name__ == "__main__":
    main()
