"""``tempestweb dev`` — watch the project, rebuild, and livereload the browser.

Wires a :class:`~tempestweb.devserver.FileWatcher` to a
:class:`~tempestweb.devserver.ReloadSignal`. :func:`serve_dev` is the live Mode A
loop: it builds the wasm bundle, serves it over the dev HTTP app (with a browser
livereload channel), and on every watched change rebuilds the bundle and pushes a
reload to the tab. :func:`create_dev_session` keeps the lighter watch-only wiring
(a :class:`StubTransport` that records reloads) for unit tests and for inspecting
the watch loop without binding a socket.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from fastapi import FastAPI

from tempestweb.cli.config import VALID_MODES, ProjectConfig, load_config
from tempestweb.cli.loader import load_app
from tempestweb.devserver import FileWatcher, ReloadEvent, ReloadSignal

__all__ = [
    "DevError",
    "DevSession",
    "StubTransport",
    "create_dev_session",
    "serve_dev",
]


class DevError(RuntimeError):
    """Raised when a dev session cannot be started."""


@dataclass(slots=True)
class StubTransport:
    """A transport-agnostic reload sink used until a real transport plugs in.

    Records every reload it receives. A real transport (browser reload for Mode
    A, session restart for Mode B) replaces this by subscribing to the same
    :class:`ReloadSignal`.

    Attributes:
        mode: The execution mode this transport stands in for.
        reloads: Every reload event received, in order.
    """

    mode: str
    reloads: list[ReloadEvent] = field(default_factory=list)

    def on_reload(self, event: ReloadEvent) -> None:
        """Handle a reload event by recording it.

        Args:
            event: The reload event emitted by the signal.
        """
        self.reloads.append(event)


@dataclass(slots=True)
class DevSession:
    """A ready-to-run dev session: watcher + signal + transport, all wired.

    Attributes:
        config: The resolved project config.
        mode: The execution mode for this session.
        signal: The reload hub the watcher triggers.
        watcher: The file watcher observing the project root.
        transport: The reload sink (a :class:`StubTransport` until T2/T3 land).
    """

    config: ProjectConfig
    mode: str
    signal: ReloadSignal
    watcher: FileWatcher
    transport: StubTransport


def create_dev_session(
    project_root: str | Path,
    *,
    mode: str | None = None,
    verify: bool = True,
) -> DevSession:
    """Build a wired dev session for a project without starting the watch loop.

    The session is fully connected — triggering the signal (or feeding the
    watcher a change batch) reaches the transport — but the blocking file-watch
    loop is started separately via ``await session.watcher.run()``. Splitting
    construction from the loop keeps the session unit-testable.

    Args:
        project_root: The project directory.
        mode: ``"wasm"`` or ``"server"``. Defaults to the project config's mode.
        verify: When ``True`` (default), confirm the entrypoint loads before
            wiring the session.

    Returns:
        A wired :class:`DevSession`.

    Raises:
        DevError: If the mode is invalid or (when verifying) the project fails to
            load.
    """
    config = load_config(project_root)
    resolved_mode = mode or config.mode
    if resolved_mode not in VALID_MODES:
        raise DevError(f"invalid mode {resolved_mode!r}; expected one of {VALID_MODES}")

    if verify:
        entrypoint = config.entrypoint_path
        if not Path(entrypoint).is_file():
            raise DevError(f"entrypoint not found: {entrypoint}")
        try:
            load_app(entrypoint)
        except Exception as exc:  # noqa: BLE001 - normalize to DevError
            raise DevError(str(exc)) from exc

    signal = ReloadSignal()
    transport = StubTransport(mode=resolved_mode)
    signal.subscribe(transport.on_reload)
    watcher = FileWatcher(config.root, signal)

    return DevSession(
        config=config,
        mode=resolved_mode,
        signal=signal,
        watcher=watcher,
        transport=transport,
    )


async def serve_dev(
    project_root: str | Path,
    *,
    mode: str | None = None,
    host: str | None = None,
    port: int | None = None,
) -> None:
    """Build, serve and reload the app locally until stopped (blocking).

    Serves the app in any mode. The static modes (Mode A **wasm**, Mode C
    **transpile**) get browser livereload; **server** mode (Mode B) runs the
    built FastAPI host under uvicorn and restarts it on change. On every
    reload-worthy change the artifact is rebuilt; a rebuild that fails (e.g. a
    syntax error in the edited app) is reported and the last good build keeps
    serving.

    Args:
        project_root: The project directory.
        mode: Execution mode — ``"wasm"``, ``"server"`` or ``"transpile"``.
            Defaults to the project config's mode.
        host: Override the bind address. Defaults to the project config's host.
        port: Override the bind port. Defaults to the project config's port.

    Raises:
        DevError: If the mode is invalid or the initial build fails.
    """
    config = load_config(project_root)
    resolved_mode = mode or config.mode
    if resolved_mode not in VALID_MODES:
        raise DevError(f"invalid mode {resolved_mode!r}; expected one of {VALID_MODES}")
    bind_host = host or config.host
    bind_port = port if port is not None else config.port

    if resolved_mode == "server":
        await _serve_dev_server(config, bind_host, bind_port)
    else:
        await _serve_dev_static(config, resolved_mode, bind_host, bind_port)


async def _serve_dev_static(
    config: ProjectConfig, mode: str, host: str, port: int
) -> None:
    """Serve a static-mode bundle (wasm/transpile) with browser livereload.

    Builds the bundle once, serves it over the dev HTTP app with a livereload
    channel, and rebuilds into the served dir **before** telling the tab to
    reload, so it always picks up the fresh build.

    Args:
        config: The resolved project config.
        mode: The static execution mode (``"wasm"`` or ``"transpile"``).
        host: The bind address.
        port: The bind port.

    Raises:
        DevError: If the ``server`` extra is missing or the initial build fails.
    """
    from tempestweb.cli.commands.build import BuildError, build_artifact

    try:
        from tempestweb.devserver import create_dev_app, make_server
    except ImportError as exc:  # noqa: TRY003 - actionable install hint
        raise DevError(
            "the dev server needs the 'server' extra (Starlette + uvicorn). "
            "Install it with: uv add 'tempestweb[server]' "
            "(or pip install 'tempestweb[server]'). The built static artifact "
            "itself never embeds a server — this is only for local serving."
        ) from exc

    try:
        # dev=True: skip the caching service worker and inject the cache
        # kill-switch, so every reload serves the freshly rebuilt bundle (no
        # stale SW/cache headaches). Production builds keep the caching SW.
        result = build_artifact(config.root, mode=mode, dev=True)
    except Exception as exc:  # noqa: BLE001 - normalize to DevError
        raise DevError(f"initial build failed: {exc}") from exc
    out_dir = result.out_dir

    signal = ReloadSignal()

    def rebuild(event: ReloadEvent) -> None:
        """Rebuild the bundle into the served dir before the browser reloads."""
        try:
            build_artifact(config.root, mode=mode, out_dir=out_dir, dev=True)
        except BuildError as exc:
            print(f"tempestweb dev: rebuild failed, keeping last build: {exc}")

    # Subscribed (not a waiter): trigger() runs callbacks before resolving the
    # livereload SSE waiters, so the rebuild completes before the tab reloads.
    signal.subscribe(rebuild)

    app = create_dev_app(out_dir, signal)
    server = make_server(app, host, port)
    # Ignore the build output dir: the rebuild writes into it, and without this
    # those writes would retrigger the watcher in an endless rebuild loop.
    watcher = FileWatcher(config.root, signal, ignore=[out_dir])

    print(
        f"tempestweb dev: serving {config.name} at http://{host}:{port} "
        f"(mode={mode}); edit a file to reload. Ctrl-C to stop."
    )
    await asyncio.gather(server.serve(), watcher.run())


def _load_server_app(out_dir: Path) -> FastAPI:
    """Import a freshly-built server artifact and return its FastAPI ``app``.

    Purges any modules previously imported from ``out_dir`` (the artifact's
    ``server.py`` and the copied ``app.py``) from ``sys.modules`` first, so a
    rebuild's edits actually take effect on re-import instead of serving a stale
    cached module.

    Args:
        out_dir: The server artifact root (contains ``server.py`` and ``app.py``).

    Returns:
        The artifact's FastAPI application object (an ASGI app).

    Raises:
        DevError: If the built server cannot be imported.
    """
    import importlib.util

    out_resolved = out_dir.resolve()
    for name in list(sys.modules):
        module = sys.modules.get(name)
        file = getattr(module, "__file__", None)
        if file and out_resolved in Path(file).resolve().parents:
            del sys.modules[name]

    server_path = out_dir / "server.py"
    spec = importlib.util.spec_from_file_location(
        "tempestweb_dev_artifact_server", server_path
    )
    if spec is None or spec.loader is None:
        raise DevError(f"cannot import built server at {server_path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - normalize to DevError
        raise DevError(f"failed to import built server: {exc}") from exc
    return cast("FastAPI", module.app)


async def _serve_dev_server(config: ProjectConfig, host: str, port: int) -> None:
    """Serve Mode B (server) under uvicorn, rebuilding + restarting on change.

    Builds the server artifact, runs it under a :class:`uvicorn.Server`, and
    watches the project. On every change it stops the server, rebuilds the
    artifact and restarts — a failed rebuild keeps the last good build serving.

    Args:
        config: The resolved project config.
        host: The bind address.
        port: The bind port.

    Raises:
        DevError: If uvicorn is missing or the initial build fails.
    """
    from tempestweb.cli.commands.build import BuildError, build_artifact

    try:
        import uvicorn
    except ImportError as exc:  # noqa: TRY003 - actionable install hint
        raise DevError(
            "serving Mode B needs the 'server' extra (FastAPI + uvicorn). "
            "Install it with: uv add 'tempestweb[server]' "
            "(or pip install 'tempestweb[server]')."
        ) from exc

    try:
        result = build_artifact(config.root, mode="server")
    except Exception as exc:  # noqa: BLE001 - normalize to DevError
        raise DevError(f"initial build failed: {exc}") from exc
    out_dir = result.out_dir

    signal = ReloadSignal()
    restart = asyncio.Event()
    signal.subscribe(lambda event: restart.set())
    # Ignore the build output dir so rebuilds don't retrigger the watcher.
    watcher = FileWatcher(config.root, signal, ignore=[out_dir])
    watcher_task = asyncio.create_task(watcher.run())

    print(
        f"tempestweb dev: serving {config.name} at http://{host}:{port} "
        "(mode=server); edit a file to restart. Ctrl-C to stop."
    )
    try:
        while True:
            app = _load_server_app(out_dir)
            server = uvicorn.Server(
                uvicorn.Config(app, host=host, port=port, log_level="warning")
            )
            restart.clear()
            serve_task = asyncio.create_task(server.serve())
            restart_task = asyncio.create_task(restart.wait())
            done, _pending = await asyncio.wait(
                {serve_task, restart_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if restart_task not in done:
                # The server stopped on its own (Ctrl-C or a fatal error).
                restart_task.cancel()
                break
            # A change fired: shut the server down, rebuild, then loop to restart.
            server.should_exit = True
            await serve_task
            try:
                build_artifact(config.root, mode="server", out_dir=out_dir)
                print("tempestweb dev: change detected — restarting server.")
            except BuildError as exc:
                print(
                    f"tempestweb dev: rebuild failed, restarting last good build: {exc}"
                )
    finally:
        watcher_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await watcher_task
