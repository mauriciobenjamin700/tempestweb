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
from dataclasses import dataclass, field
from pathlib import Path

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
    """Build, serve and livereload a static project until stopped (blocking).

    Builds the static bundle once (Mode A **wasm** or Mode C **transpile**),
    serves it over the dev HTTP app with a browser livereload channel, and runs
    the file watcher. On every reload-worthy change the bundle is rebuilt
    **before** the browser is told to reload, so the tab always picks up the fresh
    build. A rebuild that fails (e.g. a syntax error or an out-of-subset construct
    in the edited app) is reported and skipped — the last good bundle keeps
    serving.

    Args:
        project_root: The project directory.
        mode: Execution mode. Serves the static modes — ``"wasm"`` and
            ``"transpile"`` — here; ``"server"`` (Mode B) is served by
            ``tempestweb run --mode server`` (the built FastAPI host).
        host: Override the bind address. Defaults to the project config's host.
        port: Override the bind port. Defaults to the project config's port.

    Raises:
        DevError: If the mode is invalid/unsupported or the initial build fails.
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

    config = load_config(project_root)
    resolved_mode = mode or config.mode
    if resolved_mode not in VALID_MODES:
        raise DevError(f"invalid mode {resolved_mode!r}; expected one of {VALID_MODES}")
    if resolved_mode not in ("wasm", "transpile"):
        raise DevError(
            "dev livereload serves the static modes (wasm, transpile); for Mode B "
            "use `tempestweb run --mode server` (uvicorn hosts the built app)."
        )

    try:
        result = build_artifact(project_root, mode=resolved_mode)
    except Exception as exc:  # noqa: BLE001 - normalize to DevError
        raise DevError(f"initial build failed: {exc}") from exc
    out_dir = result.out_dir

    signal = ReloadSignal()

    def rebuild(event: ReloadEvent) -> None:
        """Rebuild the bundle into the served dir before the browser reloads."""
        try:
            build_artifact(project_root, mode=resolved_mode, out_dir=out_dir)
        except BuildError as exc:
            print(f"tempestweb dev: rebuild failed, keeping last build: {exc}")

    # Subscribed (not a waiter): trigger() runs callbacks before resolving the
    # livereload SSE waiters, so the rebuild completes before the tab reloads.
    signal.subscribe(rebuild)

    app = create_dev_app(out_dir, signal)
    bind_host = host or config.host
    bind_port = port if port is not None else config.port
    server = make_server(app, bind_host, bind_port)
    watcher = FileWatcher(config.root, signal)

    print(
        f"tempestweb dev: serving {config.name} at http://{bind_host}:{bind_port} "
        f"(mode={resolved_mode}); edit a file to reload. Ctrl-C to stop."
    )
    await asyncio.gather(server.serve(), watcher.run())
