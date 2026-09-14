"""Regenerate the three-mode theme-parity fixture from the real core.

Run as a module to (re)write the golden::

    python -m tests.conformance._transpile_theme

An app declares its palette once, as a module-level ``THEME``. Modes A and B read
it — ``bootstrap(..., getattr(app, "THEME", None))`` and
``create_app(..., theme=...)`` — and Mode C did not, so the same screen came out
legible on the server and unreadable transpiled (tempestweb#206).

This fixture is what the three modes are held to. It carries, per case:

* ``attribute``: the ``data-tw-theme`` value the document ends up with at mount.
  ``None`` means the document is left unmarked — the base stylesheet's own tokens
  *are* the light palette, so a first ``light`` says nothing and is skipped.
* ``node``: the serialized IR the core builds for :func:`view` under that theme,
  which is where every resolved colour lives (a widget carries its fill inline).

The scene is deliberately mixed: a primitive whose style comes from the generated
widget table (``Button``), a field whose style comes from the field table
(``Input``), and three components whose colours come from the component tables
(``Card``, ``Breadcrumb``, ``ListTile``). Nothing in it passes ``theme=``
anywhere — inheriting the app's palette without being handed it is the whole
behaviour under test.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tempest_core import (
    App,
    Breadcrumb,
    Button,
    Card,
    Column,
    Input,
    ListTile,
    Text,
    Theme,
    ThemeMode,
    Widget,
)
from tempestweb.runtime import serialize_node

FIXTURE: Path = (
    Path(__file__).resolve().parents[1] / "fixtures" / "transpile_theme_samples.json"
)

#: The declared ``THEME`` per case, by the name the fixture files it under.
#: ``no_theme`` is the app that declares nothing, and is the regression guard:
#: it must come out exactly as it did before any theme was read.
CASES: dict[str, Theme | None] = {
    "no_theme": None,
    "light": Theme(mode=ThemeMode.LIGHT),
    "dark": Theme(mode=ThemeMode.DARK),
}


class ThemeState:
    """The scene's state: empty, because the tree is static.

    A parity fixture wants the same tree every time; state would only add a way
    for the two ports to disagree about something that is not the theme.
    """


def make_state() -> ThemeState:
    """Build the scene's initial state.

    Returns:
        A fresh, empty state.
    """
    return ThemeState()


def view(app: App[ThemeState]) -> Widget:
    """Build the parity scene, passing ``theme`` to nothing.

    Args:
        app: The application handle (unused: the scene is static).

    Returns:
        The root widget of the scene.
    """
    del app
    return Column(
        key="root",
        children=[
            Breadcrumb(items=["home", "docs", "ui"], key="crumbs"),
            Card(
                key="card",
                children=[
                    Text(content="Relatório", key="title"),
                    Button(label="Salvar", key="save"),
                    Input(placeholder="nome", key="name"),
                ],
            ),
            ListTile(title="Maria", subtitle="admin", key="row"),
        ],
    )


def expected_attribute(theme: Theme | None) -> str | None:
    """The ``data-tw-theme`` the document carries after mounting under ``theme``.

    Resolved the way a widget resolves it (``Theme.is_dark()``, no platform flag),
    because the attribute exists to make the stylesheet agree with the colours
    already inline in the tree.

    Args:
        theme: The app's declared theme, or ``None``.

    Returns:
        ``"dark"``, or ``None`` when the document is left unmarked.
    """
    if theme is not None and theme.is_dark():
        return "dark"
    return None


def build_samples() -> dict[str, Any]:
    """Build the parity sample for every case, from the real core.

    Returns:
        The case name → ``{"attribute", "node"}`` map.
    """
    samples: dict[str, Any] = {}
    for name, theme in CASES.items():
        app: App[ThemeState] = (
            App(state=make_state(), view=view, apply_patches=_ignore)
            if theme is None
            else App(state=make_state(), view=view, apply_patches=_ignore, theme=theme)
        )
        samples[name] = {
            "attribute": expected_attribute(theme),
            "node": serialize_node(app.start().root),
        }
    return samples


def _ignore(patches: Any) -> None:  # noqa: ANN401 — the core's patch list
    """Drop a patch batch.

    The fixture only needs the initial build, so nothing has to be delivered.

    Args:
        patches: The patches the core produced.
    """
    del patches


def render_fixture_text() -> str:
    """Render the theme-parity fixture as canonical JSON text.

    Returns:
        The fixture's exact on-disk content.
    """
    return (
        json.dumps(build_samples(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )


def write_fixture() -> Path:
    """Write the theme-parity fixture to disk.

    Returns:
        The path written.
    """
    FIXTURE.write_text(render_fixture_text(), encoding="utf-8")
    return FIXTURE


def main() -> None:
    """Regenerate the theme-parity fixture and print its path."""
    print(f"wrote {write_fixture()}")


if __name__ == "__main__":
    main()
