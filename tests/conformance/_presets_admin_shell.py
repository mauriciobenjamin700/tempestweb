"""Regenerate the ``admin_shell`` preset fixture from the real presets.

Run as a module to (re)write the golden::

    python -m tests.conformance._presets_admin_shell

``tests/fixtures/presets_admin_shell.json`` is the wire tree the composed admin
shell produces, and ``tests/client/layouts.test.js`` renders it to prove the
layout roles survive into the DOM. It existed before this module did, with the
scene written inline in ``tests/unit/test_presets.py`` and the JSON updated by
hand — so the scene and the golden were two copies of the same intent, and a
core change that legitimately reshaped the tree left no honest way to refresh
one without retyping the other.

The scene now lives here, the test imports :func:`scene`, and the fixture is
whatever this module writes. A change of shape is then a one-command refresh
with a reviewable diff, instead of hand-edited JSON.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tempest_core import Widget, build
from tempestweb.presets import (
    NavItem,
    TableColumn,
    admin_shell,
    list_page,
)
from tempestweb.runtime.serialize import node_to_wire

FIXTURE: Path = (
    Path(__file__).resolve().parents[1] / "fixtures" / "presets_admin_shell.json"
)


def scene() -> Widget:
    """Compose the admin shell the fixture pins.

    A shell with a branded sidebar, two nav items (one badged) and an active
    selection, wrapping a list page with a searched, two-column table — enough
    surface that a dropped layout role or a reshaped row shows up as a diff.

    Returns:
        The composed widget tree.
    """
    return admin_shell(
        title="Painel",
        brand="ACME",
        nav=[
            NavItem("Visão geral", "overview"),
            NavItem("Usuários", "users", badge="3"),
        ],
        active="users",
        on_navigate=lambda _value: None,
        on_toggle_sidebar=lambda: None,
        body=list_page(
            title="Usuários",
            subtitle="12 ativos",
            columns=[TableColumn("Nome"), TableColumn("Saldo", align="end")],
            rows=[["Ana", "R$ 10"], ["Bo", "R$ 4"]],
            search="",
            on_search=lambda _text: None,
        ),
    )


def build_fixture() -> dict[str, Any]:
    """Build the wire tree the fixture stores.

    Returns:
        The serialized node tree of :func:`scene`.
    """
    wire: dict[str, Any] = node_to_wire(build(scene()))
    return wire


def main() -> None:
    """Write the fixture to disk."""
    FIXTURE.write_text(
        json.dumps(build_fixture(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {FIXTURE}")


if __name__ == "__main__":
    main()
