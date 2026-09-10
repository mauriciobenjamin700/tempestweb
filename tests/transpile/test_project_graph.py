"""Multi-module Mode C: the local import graph, and what it unlocks.

A Mode C app was one file — the emitter refused every import that was not
``tempest_core`` / ``tempestweb.components`` / ``tempestweb.native``. That is
why the typed client ``tempestweb gen api`` writes, which is a package, could
not be imported by an app at all.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tempestweb.cli.openapi import generate as generate_client
from tempestweb.transpile import TranspileError, transpile_project

APP = """\
\"\"\"Entrypoint.\"\"\"

from dataclasses import dataclass

from tempest_core import App, Column, Text, Widget

from pkg.models import Row
from pkg.labels import TITLE


@dataclass
class S:
    \"\"\"State.\"\"\"

    row: Row


def make_state() -> S:
    \"\"\"Build state.\"\"\"
    return S(row=Row(name="x"))


def view(app: App[S]) -> Widget:
    \"\"\"Render.\"\"\"
    return Column(children=[Text(content=TITLE), Text(content=app.state.row.name)])
"""

MODELS = """\
\"\"\"Models.\"\"\"

from dataclasses import dataclass


@dataclass
class Row:
    \"\"\"A row.\"\"\"

    name: str
"""

LABELS = '"""Labels."""\n\nTITLE = "Rows"\n'


def _project(tmp_path: Path) -> Path:
    """Write the three-module sample project.

    Args:
        tmp_path: The pytest temporary directory.

    Returns:
        The path to the entrypoint.
    """
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text(
        "from pkg.models import Row as Row\n", encoding="utf-8"
    )
    (tmp_path / "pkg" / "models.py").write_text(MODELS, encoding="utf-8")
    (tmp_path / "pkg" / "labels.py").write_text(LABELS, encoding="utf-8")
    entry = tmp_path / "app.py"
    entry.write_text(APP, encoding="utf-8")
    return entry


def test_a_local_import_becomes_a_sibling_es_module(tmp_path: Path) -> None:
    """Each project module is emitted next to the entrypoint and imported."""
    entry = _project(tmp_path)
    output = transpile_project(entry, tmp_path)
    assert set(output) == {"app.gen.js", "pkg.models.gen.js", "pkg.labels.gen.js"}
    app = output["app.gen.js"]
    assert 'import { Row } from "./pkg.models.gen.js";' in app
    assert 'import { TITLE } from "./pkg.labels.gen.js";' in app


def test_a_module_constant_is_exported_so_a_sibling_can_read_it(
    tmp_path: Path,
) -> None:
    """A constant is the one top-level name that used not to be exported."""
    entry = _project(tmp_path)
    output = transpile_project(entry, tmp_path)
    assert 'export const TITLE = "Rows";' in output["pkg.labels.gen.js"]


def test_a_class_imported_from_a_sibling_is_constructed_with_new(
    tmp_path: Path,
) -> None:
    """Calling an emitted JS class without `new` is a hard TypeError."""
    entry = _project(tmp_path)
    output = transpile_project(entry, tmp_path)
    assert "new Row(" in output["app.gen.js"]


def test_a_class_re_exported_through_a_package_is_still_a_class(
    tmp_path: Path,
) -> None:
    """A package's `__init__` declares nothing, so its exports must propagate."""
    entry = _project(tmp_path)
    entry.write_text(APP.replace("from pkg.models import Row", "from pkg import Row"))
    output = transpile_project(entry, tmp_path)
    assert "new Row(" in output["app.gen.js"]


def test_a_relative_import_inside_a_package_resolves_to_that_package(
    tmp_path: Path,
) -> None:
    """One dot in an `__init__.py` means the package itself, not its parent."""
    entry = _project(tmp_path)
    (tmp_path / "pkg" / "__init__.py").write_text(
        "from .models import Row as Row\n", encoding="utf-8"
    )
    entry.write_text(APP.replace("from pkg.models import Row", "from pkg import Row"))
    output = transpile_project(entry, tmp_path)
    assert "new Row(" in output["app.gen.js"]


def test_a_cycle_between_local_modules_is_refused(tmp_path: Path) -> None:
    """An emitted cycle throws on a temporal dead zone neither module names."""
    entry = _project(tmp_path)
    (tmp_path / "pkg" / "labels.py").write_text(
        "from pkg.models import Row\n\nTITLE = 'Rows'\n", encoding="utf-8"
    )
    (tmp_path / "pkg" / "models.py").write_text(
        MODELS + "\nfrom pkg.labels import TITLE\n", encoding="utf-8"
    )
    with pytest.raises(TranspileError, match="cycle"):
        transpile_project(entry, tmp_path)


def test_a_module_named_after_a_client_asset_is_refused(tmp_path: Path) -> None:
    """`widgets.py` would write over the renderer's own `widgets.gen.js`."""
    entry = _project(tmp_path)
    (tmp_path / "widgets.py").write_text(LABELS, encoding="utf-8")
    entry.write_text(
        APP.replace("from pkg.labels import TITLE", "from widgets import TITLE")
    )
    with pytest.raises(TranspileError, match="already ships"):
        transpile_project(entry, tmp_path, reserved=frozenset({"widgets.gen.js"}))


def test_a_star_import_from_a_sibling_is_refused(tmp_path: Path) -> None:
    """A star hides what the module binds, so the emitter cannot name it."""
    entry = _project(tmp_path)
    entry.write_text(
        APP.replace("from pkg.labels import TITLE", "from pkg.labels import *")
    )
    with pytest.raises(TranspileError, match="import \\*"):
        transpile_project(entry, tmp_path)


SPEC: dict[str, object] = {
    "openapi": "3.1.0",
    "info": {"title": "t", "version": "1"},
    "paths": {
        "/api/tasks": {
            "get": {
                "tags": ["tasks"],
                "operationId": "list_tasks",
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"$ref": "#/components/schemas/Task"},
                                }
                            }
                        }
                    }
                },
            },
            "post": {
                "tags": ["tasks"],
                "operationId": "create_task",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/TaskCreate"}
                        }
                    }
                },
                "responses": {
                    "201": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Task"}
                            }
                        }
                    }
                },
            },
        }
    },
    "components": {
        "schemas": {
            "Task": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "title": {"type": "string"},
                },
                "required": ["id", "title"],
            },
            "TaskCreate": {
                "type": "object",
                "properties": {"title": {"type": "string"}},
                "required": ["title"],
            },
        }
    },
}

CLIENT_APP = """\
\"\"\"An app driving the generated client.\"\"\"

from dataclasses import dataclass, field

from tempest_core import App, Button, Column, Text, Widget

from api.tasks import Task, TaskCreate, TasksService

SERVICE = TasksService()


@dataclass
class S:
    \"\"\"State.\"\"\"

    rows: list[Task] = field(default_factory=list)


def make_state() -> S:
    \"\"\"Build state.\"\"\"
    return S()


def view(app: App[S]) -> Widget:
    \"\"\"Render.\"\"\"

    async def load() -> None:
        rows = await SERVICE.list_tasks()
        app.set_state(lambda s: setattr(s, "rows", rows))

    async def add() -> None:
        await SERVICE.create_task(TaskCreate(title="x"))
        await load()

    return Column(
        children=[
            Button(label="load", on_click=load),
            Button(label="add", on_click=add),
            Text(content=str(len(app.state.rows))),
        ]
    )
"""


def test_the_generated_openapi_client_transpiles(tmp_path: Path) -> None:
    """The whole point: `tempestweb gen api` output runs under Mode C.

    Three separate defects used to make this impossible — the client is a
    package (Mode C took one file), it built request bodies with
    `dataclasses.asdict` (no counterpart in JS, and it keyed the payload by the
    snake_case field rather than the property), and it parsed responses with a
    `@classmethod`. Each is checked below by what the emitted JS must contain.
    """
    files, _tags = generate_client(json.loads(json.dumps(SPEC)))
    for relative, content in files.items():
        target = tmp_path / "api" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    entry = tmp_path / "app.py"
    entry.write_text(CLIENT_APP, encoding="utf-8")

    output = transpile_project(entry, tmp_path)

    # `Task` is referenced only in an annotation, which the emitter drops, so
    # the import line carries exactly the two names the output uses.
    assert (
        'import { TaskCreate, TasksService } from "./api.tasks.gen.js";'
        in (output["app.gen.js"])
    )
    assert "new TasksService()" in output["app.gen.js"]
    service = output["api.tasks.service.gen.js"]
    assert "response.json_body" in service
    assert "toDict()" in service or "to_dict()" in service
    schemas = output["api.tasks.schemas.gen.js"]
    assert "static from_dict(" in schemas
