"""Guard: everything the transpiler emits must parse as an ES module.

The golden tests compare the generated JS as *text*, so they lock drift but say
nothing about validity — the transpiler could emit a module the browser refuses
to load and the whole suite would stay green. That is exactly what happened: a
state dataclass named ``State`` (the name ``tempestweb new`` scaffolds) produced
``import { State } … export class State extends State``, and Mode C died on
``SyntaxError: Identifier 'State' has already been declared`` with an empty page.

``node --check`` parses without executing or resolving imports, so this covers
the scaffold templates and every example app cheaply.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tempestweb.cli.scaffold import TEMPLATES, render_files
from tempestweb.transpile import TranspileError, transpile_file, transpile_source

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is required to parse the emitted JS"
)


def assert_parses(js: str, label: str, tmp_path: Path) -> None:
    """Assert `js` parses as an ES module.

    Args:
        js: The generated JavaScript source.
        label: Identifier for the failure message (the source it came from).
        tmp_path: Directory to write the module into.

    Raises:
        AssertionError: If node reports a syntax error.
    """
    module = tmp_path / "generated.mjs"
    module.write_text(js, encoding="utf-8")
    result = subprocess.run(
        ["node", "--check", str(module)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"{label} emits unparsable JS:\n{result.stderr}"


@pytest.mark.parametrize("template", TEMPLATES)
def test_scaffold_template_transpiles_to_parsable_js(
    template: str, tmp_path: Path
) -> None:
    """`tempestweb new` + `build --mode transpile` must not ship a broken page."""
    source = render_files("smoke", template=template)["app.py"]
    assert_parses(transpile_source(source, "app.py"), f"scaffold:{template}", tmp_path)


def example_apps() -> list[Path]:
    """Return every example app module, sorted for a stable test order."""
    return sorted((ROOT / "examples").glob("*/app.py"))


@pytest.mark.parametrize("app", example_apps(), ids=lambda p: p.parent.name)
def test_example_transpiles_to_parsable_js(app: Path, tmp_path: Path) -> None:
    """Every example the transpiler accepts emits JS the browser can load.

    An example outside the Mode C subset is skipped, not failed: rejecting
    unsupported Python is the transpiler working, and this guard is about what
    it emits when it does accept a module.
    """
    try:
        js = transpile_file(app)
    except TranspileError as exc:
        pytest.skip(f"outside the Mode C subset: {exc}")
    assert_parses(js, str(app.relative_to(ROOT)), tmp_path)
