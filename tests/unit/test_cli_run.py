"""Tests for ``tempestweb run`` (build + bind plan) — cli.commands.run."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tempestweb.cli import RunError, RunPlan, prepare_run, scaffold_project
from tempestweb.cli.commands.run import serve_run


def _project(tmp_path: Path) -> Path:
    return scaffold_project("runme", parent=tmp_path).root


def test_prepare_run_builds_and_plans(tmp_path: Path) -> None:
    root = _project(tmp_path)
    plan = prepare_run(root, mode="wasm")
    assert isinstance(plan, RunPlan)
    assert plan.build.mode == "wasm"
    assert (plan.build.out_dir / "index.html").is_file()
    assert plan.host == "127.0.0.1"
    assert plan.port == 8000
    assert plan.url == "http://127.0.0.1:8000"


def test_prepare_run_overrides_host_and_port(tmp_path: Path) -> None:
    root = _project(tmp_path)
    plan = prepare_run(root, mode="server", host="0.0.0.0", port=9999)
    assert plan.build.mode == "server"
    assert plan.host == "0.0.0.0"
    assert plan.port == 9999
    assert plan.url == "http://0.0.0.0:9999"


def test_prepare_run_uses_config_defaults(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "tempestweb.toml").write_text(
        '[dev]\nmode = "wasm"\nhost = "127.0.0.1"\nport = 4321\n',
        encoding="utf-8",
    )
    plan = prepare_run(root)
    assert plan.port == 4321


def test_prepare_run_propagates_build_failure(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "app.py").write_text("def broken( =", encoding="utf-8")
    with pytest.raises(RunError):
        prepare_run(root, mode="wasm")


def test_serve_run_wasm_missing_server_extra_raises_friendly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Setting the module to None makes its import raise ImportError, simulating
    # an install without the [server] extra (no Starlette/uvicorn).
    root = _project(tmp_path)
    plan = prepare_run(root, mode="wasm")
    monkeypatch.setitem(sys.modules, "tempestweb.devserver.http", None)
    with pytest.raises(RunError, match=r"'server' extra"):
        serve_run(plan)
