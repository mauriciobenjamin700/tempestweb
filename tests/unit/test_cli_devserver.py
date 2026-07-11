"""Tests for the transport-agnostic dev server (devserver.reload + watcher)."""

from __future__ import annotations

import asyncio
import contextlib
import functools
from collections.abc import AsyncIterator, Sequence
from importlib.util import find_spec
from pathlib import Path

import pytest

from tempestweb.devserver import (
    DEFAULT_WATCH_SUFFIXES,
    FileWatcher,
    ReloadEvent,
    ReloadKind,
    ReloadSignal,
)
from tempestweb.devserver.watcher import _watchfiles_stream

requires_watchfiles = pytest.mark.skipif(
    find_spec("watchfiles") is None,
    reason="watchfiles is only installed with the [cli] extra",
)


def test_signal_subscribe_receives_event() -> None:
    signal = ReloadSignal()
    seen: list[ReloadEvent] = []
    signal.subscribe(seen.append)
    event = signal.trigger(paths=["app.py"])
    assert seen == [event]
    assert event.kind is ReloadKind.RESTART
    assert event.paths == ("app.py",)


def test_signal_generation_increments() -> None:
    signal = ReloadSignal()
    assert signal.generation == 0
    first = signal.trigger()
    second = signal.trigger()
    assert first.generation == 1
    assert second.generation == 2
    assert signal.generation == 2


def test_signal_unsubscribe_stops_delivery() -> None:
    signal = ReloadSignal()
    seen: list[ReloadEvent] = []
    unsubscribe = signal.subscribe(seen.append)
    signal.trigger()
    unsubscribe()
    signal.trigger()
    assert len(seen) == 1


def test_signal_manual_reload_has_empty_paths() -> None:
    signal = ReloadSignal()
    event = signal.trigger()
    assert event.paths == ()


async def test_signal_wait_resolves_on_trigger() -> None:
    signal = ReloadSignal()
    waiter = asyncio.ensure_future(signal.wait())
    await asyncio.sleep(0)  # let the waiter register
    event = signal.trigger(paths=["x.py"])
    resolved = await waiter
    assert resolved is event


def test_watcher_handle_batch_filters_by_suffix(tmp_path: Path) -> None:
    signal = ReloadSignal()
    watcher = FileWatcher(tmp_path, signal)
    # A non-watched suffix is ignored entirely.
    assert watcher.handle_batch([str(tmp_path / "notes.txt")]) is None
    assert signal.generation == 0


def test_watcher_handle_batch_triggers_on_python(tmp_path: Path) -> None:
    signal = ReloadSignal()
    watcher = FileWatcher(tmp_path, signal)
    event = watcher.handle_batch([str(tmp_path / "app.py")])
    assert event is not None
    assert event.paths == ("app.py",)
    assert signal.generation == 1


def test_watcher_relativizes_and_sorts_paths(tmp_path: Path) -> None:
    signal = ReloadSignal()
    watcher = FileWatcher(tmp_path, signal)
    event = watcher.handle_batch(
        [str(tmp_path / "z.py"), str(tmp_path / "a.py"), str(tmp_path / "a.py")]
    )
    assert event is not None
    assert event.paths == ("a.py", "z.py")


def test_watcher_custom_suffixes(tmp_path: Path) -> None:
    signal = ReloadSignal()
    watcher = FileWatcher(tmp_path, signal, suffixes=(".css",))
    assert watcher.handle_batch([str(tmp_path / "app.py")]) is None
    event = watcher.handle_batch([str(tmp_path / "style.css")])
    assert event is not None


def test_watcher_ignores_configured_dir(tmp_path: Path) -> None:
    """Paths under an ignored dir (the build output) never trigger a reload."""
    signal = ReloadSignal()
    dist = tmp_path / "dist"
    watcher = FileWatcher(tmp_path, signal, ignore=[dist])
    # A rebuild writing into dist/ must not retrigger the watcher.
    assert watcher.handle_batch([str(dist / "wasm" / "app.py")]) is None
    assert watcher.handle_batch([str(dist / "wasm" / "client" / "dom.js")]) is None
    # A real source edit outside dist/ still triggers.
    event = watcher.handle_batch([str(tmp_path / "app.py")])
    assert event is not None


def test_default_suffixes_cover_web_assets() -> None:
    assert ".py" in DEFAULT_WATCH_SUFFIXES
    assert ".html" in DEFAULT_WATCH_SUFFIXES
    assert ".css" in DEFAULT_WATCH_SUFFIXES
    assert ".js" in DEFAULT_WATCH_SUFFIXES


async def test_watcher_run_consumes_stream(tmp_path: Path) -> None:
    signal = ReloadSignal()
    seen: list[ReloadEvent] = []
    signal.subscribe(seen.append)
    watcher = FileWatcher(tmp_path, signal)

    batches: list[Sequence[str]] = [
        [str(tmp_path / "app.py")],
        [str(tmp_path / "ignore.txt")],
        [str(tmp_path / "view.py")],
    ]

    async def stream() -> AsyncIterator[Sequence[str]]:
        for batch in batches:
            yield batch

    await watcher.run(stream())
    # Two relevant batches -> two reloads (the .txt batch is filtered).
    assert len(seen) == 2
    assert seen[0].paths == ("app.py",)
    assert seen[1].paths == ("view.py",)


async def test_watcher_run_rejects_both_stream_and_factory(tmp_path: Path) -> None:
    signal = ReloadSignal()
    watcher = FileWatcher(tmp_path, signal)

    async def stream() -> AsyncIterator[Sequence[str]]:
        if False:  # pragma: no cover - empty async generator
            yield []

    raised = False
    try:
        await watcher.run(stream(), stream_factory=lambda _root: stream())
    except ValueError:
        raised = True
    assert raised


@requires_watchfiles
async def test_watcher_run_reloads_on_real_file_write(tmp_path: Path) -> None:
    # Drive the PRODUCTION stream factory (_watchfiles_stream -> watchfiles.awatch)
    # with a real on-disk write, proving the full reload loop end to end rather
    # than just the injected-stream path.
    signal = ReloadSignal()
    seen: list[ReloadEvent] = []
    signal.subscribe(seen.append)
    watcher = FileWatcher(tmp_path, signal)

    target = tmp_path / "app.py"
    target.write_text("x = 1\n")

    # Force the polling backend so the test is deterministic regardless of the
    # host filesystem's native-notification support (network mounts, WSL, etc.).
    # functools.partial keeps the Callable[[Path], ChangeStream] factory shape.
    factory = functools.partial(_watchfiles_stream, force_polling=True)
    run_task = asyncio.ensure_future(watcher.run(stream_factory=factory))
    # Let awatch establish its filesystem watch before we touch the file.
    await asyncio.sleep(0.5)

    try:
        # Keep rewriting until at least one reload lands. Re-writing each tick
        # makes the test robust against any single poll window being missed
        # during the watch's startup, without relying on native FS events.
        for tick in range(100):
            if seen:
                break
            target.write_text(f"x = {tick}\n")
            await asyncio.sleep(0.1)
    finally:
        run_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await run_task

    assert seen, "a real file write did not produce a reload event"
    assert seen[-1].kind is ReloadKind.RESTART
    assert any("app.py" in path for event in seen for path in event.paths)
