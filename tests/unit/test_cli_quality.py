"""Tests for the quality-gate commands (cli.quality + their CLI dispatch)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tempestweb.cli import quality
from tempestweb.cli.main import main


def test_ruff_ann_select_scales_with_level() -> None:
    assert quality.ruff_ann_select("lenient") == []
    # standard enforces return + first-arg annotations.
    assert "ANN201" in quality.ruff_ann_select("standard")
    assert "ANN001" in quality.ruff_ann_select("standard")
    # strict additionally enforces *args/**kwargs annotations (ANN002/ANN003).
    assert "ANN002" not in quality.ruff_ann_select("standard")
    assert "ANN002" in quality.ruff_ann_select("strict")
    assert "ANN003" in quality.ruff_ann_select("strict")
    # ANN401 (disallow Any) is never enabled — Any is a valid annotation.
    assert "ANN401" not in quality.ruff_ann_select("strict")


def test_mypy_flags_scale_with_level() -> None:
    assert quality.mypy_flags("lenient") == []
    assert quality.mypy_flags("strict") == ["--strict"]


def test_run_pytest_coerces_no_tests_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    """pytest's exit 5 (no tests collected) must not fail the command."""
    monkeypatch.setattr(quality, "_execute", lambda *_a, **_k: 5)
    assert quality.run_pytest(None) == 0
    monkeypatch.setattr(quality, "_execute", lambda *_a, **_k: 1)
    assert quality.run_pytest(None) == 1


def test_run_full_check_order_and_short_circuit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gate runs ruff -> ruff format -> mypy -> pytest, stopping on failure."""
    calls: list[str] = []

    def fake_execute(executable: str, args: list[str]) -> int:
        # Record the executable and its first arg (the ruff subcommand).
        calls.append(f"{executable}:{args[0] if args else ''}")
        return 1 if executable == "mypy" else 0

    monkeypatch.setattr(quality, "_execute", fake_execute)
    code = quality.run_full_check(".", level="standard")
    assert code == 1
    # ruff check -> ruff format --check -> mypy (fails) -> pytest never runs.
    assert [c.split(":")[0] for c in calls] == ["ruff", "ruff", "mypy"]
    assert calls[0] == "ruff:check"
    assert calls[1] == "ruff:format"
    assert not any(c.startswith("pytest") for c in calls)


def test_run_full_check_all_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(quality, "_execute", lambda *_a, **_k: 0)
    assert quality.run_full_check(".", level="lenient") == 0


def test_lint_dispatch_invokes_ruff_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert main(["new", "q", "--into", str(tmp_path)]) == 0
    project = tmp_path / "q"
    seen: dict[str, object] = {}

    def fake_check(target: str, *, level: str) -> int:
        seen["target"] = target
        seen["level"] = level
        return 0

    monkeypatch.setattr(quality, "run_ruff_check", fake_check)
    rc = main(["lint", "--path", str(project)])
    assert rc == 0
    assert seen["target"] == str(project)
    # The scaffold writes typing_strictness = "standard".
    assert seen["level"] == "standard"


def test_strictness_flag_overrides_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert main(["new", "q2", "--into", str(tmp_path)]) == 0
    project = tmp_path / "q2"
    seen: dict[str, object] = {}

    def fake_mypy(target: str, *, level: str) -> int:
        seen["level"] = level
        return 0

    monkeypatch.setattr(quality, "run_mypy", fake_mypy)
    rc = main(["type", "--path", str(project), "--strictness", "strict"])
    assert rc == 0
    assert seen["level"] == "strict"


def test_check_dispatch_runs_full_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert main(["new", "q3", "--into", str(tmp_path)]) == 0
    project = tmp_path / "q3"
    ran: dict[str, object] = {}

    def fake_full_check(target: str, *, level: str) -> int:
        ran["target"] = target
        return 0

    monkeypatch.setattr(quality, "run_full_check", fake_full_check)
    rc = main(["check", "--path", str(project)])
    assert rc == 0
    assert ran["target"] == str(project)


def test_missing_tool_returns_127(monkeypatch: pytest.MonkeyPatch) -> None:
    """When neither the tool nor uv is on PATH, _execute reports 127."""
    monkeypatch.setattr(quality.shutil, "which", lambda _name: None)
    assert quality._execute("ruff", ["check", "."]) == 127
