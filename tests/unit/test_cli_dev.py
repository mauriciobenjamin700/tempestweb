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


async def test_serve_dev_rejects_server_mode(tmp_path: Path) -> None:
    """`dev` serves the static modes; Mode B is redirected to `run --mode server`."""
    root = _project(tmp_path)
    with pytest.raises(DevError, match=r"static modes"):
        await serve_dev(root, mode="server")


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
