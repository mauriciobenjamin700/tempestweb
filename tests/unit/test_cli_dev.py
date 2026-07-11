"""Tests for ``tempestweb dev`` session wiring (cli.commands.dev)."""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator, Sequence
from pathlib import Path

import pytest

from tempestweb.cli import (
    DevError,
    DevSession,
    StubTransport,
    create_dev_session,
    scaffold_project,
)
from tempestweb.cli.commands.dev import serve_dev


def _project(tmp_path: Path) -> Path:
    return scaffold_project("devme", parent=tmp_path).root


def test_create_dev_session_wires_components(tmp_path: Path) -> None:
    root = _project(tmp_path)
    session = create_dev_session(root, mode="wasm")
    assert isinstance(session, DevSession)
    assert isinstance(session.transport, StubTransport)
    assert session.mode == "wasm"
    assert session.watcher.signal is session.signal


def test_dev_session_triggering_signal_reaches_transport(tmp_path: Path) -> None:
    root = _project(tmp_path)
    session = create_dev_session(root, mode="server")
    assert session.transport.reloads == []
    event = session.signal.trigger(paths=["app.py"])
    assert session.transport.reloads == [event]


def test_dev_session_watcher_change_reaches_transport(tmp_path: Path) -> None:
    root = _project(tmp_path)
    session = create_dev_session(root)
    session.watcher.handle_batch([str(root / "app.py")])
    assert len(session.transport.reloads) == 1
    assert session.transport.reloads[0].paths == ("app.py",)


async def test_dev_session_run_loop_records_reloads(tmp_path: Path) -> None:
    root = _project(tmp_path)
    session = create_dev_session(root)

    async def stream() -> AsyncIterator[Sequence[str]]:
        yield [str(root / "app.py")]
        yield [str(root / "README.md")]  # not a watched suffix -> ignored

    await session.watcher.run(stream())
    assert len(session.transport.reloads) == 1


def test_create_dev_session_invalid_mode_raises(tmp_path: Path) -> None:
    root = _project(tmp_path)
    with pytest.raises(DevError, match="invalid mode"):
        create_dev_session(root, mode="native")


def test_create_dev_session_missing_entrypoint_raises(tmp_path: Path) -> None:
    with pytest.raises(DevError, match="entrypoint not found"):
        create_dev_session(tmp_path, mode="wasm")


def test_create_dev_session_skip_verify(tmp_path: Path) -> None:
    # With verify=False the session builds even without a loadable entrypoint.
    session = create_dev_session(tmp_path, mode="wasm", verify=False)
    assert isinstance(session, DevSession)


async def test_serve_dev_missing_server_extra_raises_friendly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Setting the module to None makes its import raise ImportError, simulating
    # an install without the [server] extra (no Starlette/uvicorn).
    root = _project(tmp_path)
    monkeypatch.setitem(sys.modules, "tempestweb.devserver", None)
    with pytest.raises(DevError, match=r"'server' extra"):
        await serve_dev(root, mode="wasm")


async def test_serve_dev_server_mode_reaches_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`dev --mode server` passes the guard and reaches the server build step."""
    root = _project(tmp_path)

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("sentinel-server-build")

    # Get past the guard, then fail at the build so we never bind uvicorn.
    monkeypatch.setattr(
        "tempestweb.cli.commands.build.build_artifact", _boom, raising=True
    )
    with pytest.raises(DevError, match=r"initial build failed: sentinel-server-build"):
        await serve_dev(root, mode="server")


def test_load_server_app_returns_fastapi_app(tmp_path: Path) -> None:
    """`_load_server_app` imports the built artifact and returns its ASGI app."""
    from tempestweb.cli.commands.build import build_artifact
    from tempestweb.cli.commands.dev import _load_server_app

    root = _project(tmp_path)
    result = build_artifact(root, mode="server")
    app = _load_server_app(result.out_dir)
    assert callable(app)
    # A FastAPI/Starlette app exposes its route table.
    assert hasattr(app, "routes")


def test_load_server_app_reloads_fresh_module_after_rebuild(tmp_path: Path) -> None:
    """A rebuild is re-imported fresh (the stale module is purged first)."""
    from tempestweb.cli.commands.build import build_artifact
    from tempestweb.cli.commands.dev import _load_server_app

    root = _project(tmp_path)
    out_dir = build_artifact(root, mode="server").out_dir
    first = _load_server_app(out_dir)
    build_artifact(root, mode="server", out_dir=out_dir)
    second = _load_server_app(out_dir)
    # Fresh import each time — not the same cached object.
    assert first is not second


def test_load_server_app_missing_raises(tmp_path: Path) -> None:
    """`_load_server_app` raises DevError when there is no built server."""
    from tempestweb.cli.commands.dev import _load_server_app

    with pytest.raises(DevError, match=r"(cannot|failed to) import built server"):
        _load_server_app(tmp_path)


async def test_serve_dev_accepts_transpile_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`dev --mode transpile` passes the mode guard and reaches the build step."""
    root = _project(tmp_path)

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("sentinel-build")

    # Get past the guard, then fail at the build so we don't bind a socket.
    monkeypatch.setattr(
        "tempestweb.cli.commands.build.build_artifact", _boom, raising=True
    )
    with pytest.raises(DevError, match=r"initial build failed: sentinel-build"):
        await serve_dev(root, mode="transpile")
