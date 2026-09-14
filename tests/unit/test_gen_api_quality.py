"""The client ``tempestweb gen api`` writes must pass ``tempestweb check``.

A generated file opens with "do not edit", so a lint or type error inside it is
an error its owner is not allowed to fix: the only way out is excluding the
client from the gate, which turns off type checking exactly at the boundary with
the API. Nothing exercised that before — which is how the emitter drifted into
79 ruff errors and 72 mypy errors on a nine-tag spec.

These tests generate a client from :data:`SPEC_PATH` and run the **real** tools
over it, at every strictness level :mod:`tempestweb.cli.quality` offers, plus a
call site that consumes the client — the ``arg-type`` errors only surface from
the caller, because it is the caller that pins the types.

Where the tools cannot be resolved the subprocess tests skip; the text
assertions in :mod:`tests.unit.test_openapi_gen` still pin the shapes those
errors came from.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tempestweb.cli import quality
from tempestweb.cli.openapi import generate

SPEC_PATH: Path = (
    Path(__file__).resolve().parents[1] / "fixtures" / "openapi_gen_spec.json"
)
"""The OpenAPI document the regression client is generated from."""

LEVELS: tuple[quality.Strictness, ...] = ("lenient", "standard", "strict")
"""Every strictness level ``tempestweb check`` accepts."""

_BASE_RUFF_SELECT: str = "F,E,W,I,UP,RUF,RET,PL"
"""Rule families a project realistically turns on above ruff's defaults."""

_CALL_SITE: str = '''"""A call site that consumes the generated client.

The models are only pinned to concrete types here, in the caller — which is
where ``data.get(...)`` used to surface as ``Argument "name" has incompatible
type "Any | None"``.
"""

from __future__ import annotations

from api.catalog import CatalogService, Item, ItemCreate, ItemKind, ItemPage, Owner
from api.reporting_summaries import (
    OrganisationMonthlySummary,
    ReportingSummariesService,
)


async def run() -> tuple[str, float, str]:
    """Drive a few generated calls and read typed fields back.

    Returns:
        A tuple of an item name, a variant price and an organisation id.

    Raises:
        IndexError: When the fixture API answers with an empty page.
    """
    catalog = CatalogService(base_url="http://127.0.0.1:8000")
    page: ItemPage = await catalog.list_items({"limit": 5})
    total: int = page.total
    first: Item = page.items[0]
    name: str = first.name
    kind: ItemKind = first.kind
    created: str = first.created_at
    owner: Owner | None = first.owner
    owner_id: str = owner.id if owner is not None else ""
    price: float = first.variants[0].price if first.variants else 0.0
    made: Item = await catalog.create_item(ItemCreate(name=name, kind=kind))
    await catalog.delete_item(made.id)

    reporting = ReportingSummariesService(base_url="http://127.0.0.1:8000")
    summary: OrganisationMonthlySummary = (
        await reporting.fetch_organisation_monthly_summary("org-1")
    )
    organisation: str = summary.organisation_identifier
    category: str = summary.monthly_revenue_breakdown[0].category
    return f"{name}{kind}{created}{owner_id}{total}{category}", price, organisation
'''


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate the client plus its call site into a throwaway project.

    Args:
        tmp_path_factory: pytest's session-scoped temp directory factory.

    Returns:
        The project root holding ``api/`` and ``app.py``.
    """
    root = tmp_path_factory.mktemp("gen_api_project")
    document: dict[str, Any] = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    files, tags = generate(document)
    assert tags, "the fixture spec must produce at least one route group"
    for relative, contents in files.items():
        target = root / "api" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents, encoding="utf-8")
    (root / "app.py").write_text(_CALL_SITE, encoding="utf-8")
    return root


def _tool(executable: str) -> list[str] | None:
    """Resolve a checking tool the way the quality gate resolves it.

    Args:
        executable: ``"ruff"`` or ``"mypy"``.

    Returns:
        An argv prefix, or None when the tool cannot be reached.
    """
    direct = shutil.which(executable)
    if direct is not None:
        return [direct]
    module = shutil.which(sys.executable)
    if module is not None:
        return [sys.executable, "-m", executable]
    return None


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a checking tool and capture its output.

    Args:
        argv: The full command line.
        cwd: The working directory.

    Returns:
        The completed process, with stdout and stderr decoded.
    """
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False)


@pytest.mark.parametrize("level", LEVELS)
def test_generated_client_passes_ruff(project: Path, level: quality.Strictness) -> None:
    """``ruff check`` finds nothing in the generated client, at every level.

    Args:
        project: The generated project root.
        level: The strictness level whose ANN rules are layered on.
    """
    ruff = _tool("ruff")
    if ruff is None:
        pytest.skip("ruff is not reachable in this environment")
    argv = [*ruff, "check", "--isolated", "--no-cache", "--select", _BASE_RUFF_SELECT]
    codes = quality.ruff_ann_select(level)
    if codes:
        argv += ["--extend-select", ",".join(codes)]
    argv.append("api")
    result = _run(argv, project)
    assert result.returncode == 0, result.stdout + result.stderr


def test_generated_client_is_already_formatted(project: Path) -> None:
    """``ruff format`` has nothing to rewrite in the generated client.

    Args:
        project: The generated project root.
    """
    ruff = _tool("ruff")
    if ruff is None:
        pytest.skip("ruff is not reachable in this environment")
    result = _run([*ruff, "format", "--isolated", "--check", "api"], project)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("level", LEVELS)
def test_generated_client_passes_mypy_from_a_call_site(
    project: Path, level: quality.Strictness
) -> None:
    """``mypy`` finds nothing in the client *or* in the app that imports it.

    Args:
        project: The generated project root.
        level: The strictness level whose mypy flags are layered on.
    """
    mypy = _tool("mypy")
    if mypy is None:
        pytest.skip("mypy is not reachable in this environment")
    config = project / "mypy.ini"
    config.write_text("[mypy]\n", encoding="utf-8")
    argv = [
        *mypy,
        "--config-file",
        str(config),
        "--no-incremental",
        "--follow-imports=silent",
        *quality.mypy_flags(level),
        "app.py",
        "api",
    ]
    result = _run(argv, project)
    assert result.returncode == 0, result.stdout + result.stderr


def test_no_generated_line_exceeds_the_column_budget() -> None:
    """Every emitted line fits ruff's default ``line-length``.

    E501 is not autofixable, so the emitter has to wrap what it writes. The only
    lines it cannot save are the ones where a single spec identifier is already
    wider than the budget — the fixture stays inside that bound on purpose.
    """
    document: dict[str, Any] = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    files, _ = generate(document)
    too_long = [
        f"{relative}:{number}: {line}"
        for relative, contents in files.items()
        for number, line in enumerate(contents.splitlines(), start=1)
        if len(line) > 88
    ]
    assert too_long == []
