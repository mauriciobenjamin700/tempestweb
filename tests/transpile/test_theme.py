"""Mode C reads the app's declared ``THEME``, and the shell carries it over.

The compiler already transcribed a module-level ``THEME`` — it is an ordinary
module constant — but nothing ever read the transcription: the shell imported
``{ makeState, view }`` by name, so the palette an app declared was compiled into
a constant no one touched (tempestweb#206).

Two things are pinned here, both cheap to break by hand:

* the transcription itself, so the constant the runtime looks for keeps existing;
* the shell handing the **whole module** to ``mountApp``. Naming ``THEME`` in the
  import list is not an option: an ES module import of a name the module does not
  export is a *link-time* error, so every app that declares no theme would fail to
  boot with a blank page.

The colours themselves are pinned across the three modes by
``tests/conformance/test_theme_parity.py`` and ``tests/client/transpile-theme.test.js``.
"""

from __future__ import annotations

from pathlib import Path

from tempestweb.cli import build_artifact, scaffold_project
from tempestweb.transpile import transpile_source

THEMED: str = (
    "from tempest_core import Text, Theme, ThemeMode, Widget\n"
    "\n"
    "THEME: Theme = Theme(mode=ThemeMode.DARK)\n"
    "\n"
    "\n"
    "def view(app) -> Widget:\n"
    '    return Text(content="hi", key="t")\n'
)

UNTHEMED: str = (
    "from tempest_core import Text, Widget\n"
    "\n"
    "\n"
    "def view(app) -> Widget:\n"
    '    return Text(content="hi", key="t")\n'
)


def test_a_declared_theme_is_transcribed_as_a_module_constant() -> None:
    """``THEME: Theme = Theme(mode=ThemeMode.DARK)`` survives the compile."""
    js = transpile_source(THEMED, banner="")
    assert "export const THEME = new Theme({ mode: ThemeMode.DARK });" in js
    assert 'import { Theme, ThemeMode } from "./theme.js";' in js


def test_an_app_that_declares_no_theme_emits_no_constant() -> None:
    """No ``THEME`` in, no ``THEME`` out — the runtime then keeps the default."""
    js = transpile_source(UNTHEMED, banner="")
    assert "THEME" not in js


def _shell(tmp_path: Path) -> str:
    """Build a Mode C artifact from the scaffold and read its shell.

    Args:
        tmp_path: The pytest temporary directory.

    Returns:
        The emitted ``index.html``.
    """
    project = scaffold_project("themed", parent=tmp_path).root
    out = tmp_path / "dist"
    build_artifact(project, mode="transpile", out_dir=out)
    return (out / "index.html").read_text(encoding="utf-8")


def test_the_shell_hands_the_whole_module_to_mount_app(tmp_path: Path) -> None:
    """The shell namespace-imports the app module, so ``THEME`` travels with it.

    Args:
        tmp_path: The pytest temporary directory.
    """
    html = _shell(tmp_path)
    assert 'import * as app$ from "./client/transpile/app.gen.js";' in html
    assert 'mountApp(document.getElementById("app"), app$);' in html


def test_the_shell_never_imports_theme_by_name(tmp_path: Path) -> None:
    """A named import would be a link-time error for every unthemed app.

    Args:
        tmp_path: The pytest temporary directory.
    """
    html = _shell(tmp_path)
    assert "import { makeState" not in html
    assert "THEME }" not in html
