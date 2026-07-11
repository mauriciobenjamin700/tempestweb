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


def test_dev_parser_accepts_server_mode() -> None:
    parser = build_parser()
    args = parser.parse_args(["dev", "--mode", "server"])
    assert args.command == "dev"
    assert args.mode == "server"


def test_version_flag_prints_and_exits(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert out.startswith("tempestweb ")


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


def test_run_dispatch_builds_and_plans(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert main(["new", "r", "--into", str(tmp_path)]) == 0
    project = tmp_path / "r"

    # Serving binds a blocking uvicorn server; stub it so the dispatch returns
    # after building + planning (the bind plan is asserted via the captured plan).
    served: dict[str, object] = {}

    def fake_serve_run(plan: object) -> None:
        served["plan"] = plan

    # The cli package re-exports the `main` function, shadowing the `main`
    # submodule attribute, so reach the module via sys.modules.
    import sys

    main_module = sys.modules["tempestweb.cli.main"]
    monkeypatch.setattr(main_module, "serve_run", fake_serve_run)
    rc = main(["run", "--mode", "wasm", "--path", str(project), "--port", "5555"])
    assert rc == 0
    assert (project / "dist" / "wasm" / "index.html").is_file()
    assert served.get("plan") is not None
    assert getattr(served["plan"], "port", None) == 5555


def test_run_dispatch_is_not_deprecated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`run` is the no-watcher serve command — it must not warn as deprecated."""
    assert main(["new", "keep", "--into", str(tmp_path)]) == 0
    project = tmp_path / "keep"

    import sys

    main_module = sys.modules["tempestweb.cli.main"]
    monkeypatch.setattr(main_module, "serve_run", lambda plan: None)
    rc = main(["run", "--mode", "wasm", "--path", str(project)])
    assert rc == 0
    combined = capsys.readouterr()
    assert "deprecated" not in (combined.out + combined.err).lower()


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
