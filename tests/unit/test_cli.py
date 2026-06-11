"""The CLI parser is wired and dispatches each subcommand to its handler."""

from __future__ import annotations

from pathlib import Path

import pytest

from tempestweb.cli.main import build_parser, main


def test_parser_builds() -> None:
    parser = build_parser()
    args = parser.parse_args(["build", "--mode", "server"])
    assert args.command == "build"
    assert args.mode == "server"


def test_main_no_command_returns_zero() -> None:
    assert main([]) == 0


def test_new_dispatch_creates_project(tmp_path: Path) -> None:
    rc = main(["new", "cliapp", "--into", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "cliapp" / "app.py").is_file()
    assert (tmp_path / "cliapp" / "tempestweb.toml").is_file()


def test_new_dispatch_reports_failure(tmp_path: Path) -> None:
    target = tmp_path / "taken"
    target.mkdir()
    (target / "keep.txt").write_text("x", encoding="utf-8")
    rc = main(["new", "taken", "--into", str(tmp_path)])
    assert rc == 1


def test_build_dispatch_writes_artifact(tmp_path: Path) -> None:
    assert main(["new", "b", "--into", str(tmp_path)]) == 0
    project = tmp_path / "b"
    rc = main(["build", "--mode", "wasm", "--path", str(project)])
    assert rc == 0
    assert (project / "dist" / "wasm" / "index.html").is_file()


def test_build_dispatch_custom_out(tmp_path: Path) -> None:
    assert main(["new", "b2", "--into", str(tmp_path)]) == 0
    project = tmp_path / "b2"
    out = tmp_path / "artifact"
    rc = main(["build", "--mode", "server", "--path", str(project), "--out", str(out)])
    assert rc == 0
    assert (out / "server.py").is_file()


def test_build_dispatch_reports_failure(tmp_path: Path) -> None:
    assert main(["new", "broken", "--into", str(tmp_path)]) == 0
    project = tmp_path / "broken"
    (project / "app.py").write_text("def x( =", encoding="utf-8")
    rc = main(["build", "--mode", "wasm", "--path", str(project)])
    assert rc == 1


def test_run_dispatch_builds_and_plans(tmp_path: Path) -> None:
    assert main(["new", "r", "--into", str(tmp_path)]) == 0
    project = tmp_path / "r"
    rc = main(["run", "--mode", "wasm", "--path", str(project), "--port", "5555"])
    assert rc == 0
    assert (project / "dist" / "wasm" / "index.html").is_file()


def test_dev_dispatch_runs_watch_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert main(["new", "d", "--into", str(tmp_path)]) == 0
    project = tmp_path / "d"

    ran: dict[str, object] = {}

    def fake_run(coro: object) -> None:
        ran["called"] = True
        # Close the unawaited coroutine to avoid a warning.
        getattr(coro, "close", lambda: None)()

    monkeypatch.setattr("asyncio.run", fake_run)
    rc = main(["dev", "--mode", "wasm", "--path", str(project)])
    assert rc == 0
    assert ran.get("called") is True


def test_dev_dispatch_reports_failure(tmp_path: Path) -> None:
    # No project here -> entrypoint missing -> handled error.
    rc = main(["dev", "--mode", "wasm", "--path", str(tmp_path)])
    assert rc == 1
