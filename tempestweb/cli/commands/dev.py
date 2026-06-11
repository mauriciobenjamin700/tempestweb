"""``tempestweb dev`` — watch the project and trigger reloads.

Wires a :class:`~tempestweb.devserver.FileWatcher` to a
:class:`~tempestweb.devserver.ReloadSignal` and attaches a *reload handler*. The
handler is the only mode-specific seam: in Mode A it reloads the browser tab, in
Mode B it restarts the server session. Until those transports land (Tracks T3 /
T2), the CLI attaches a :class:`StubTransport` that records reloads, so the dev
loop is fully exercisable and testable today.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from tempestweb.cli.config import VALID_MODES, ProjectConfig, load_config
from tempestweb.cli.loader import load_app
from tempestweb.devserver import FileWatcher, ReloadEvent, ReloadSignal

__all__ = ["DevError", "DevSession", "StubTransport", "create_dev_session"]


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
        raise DevError(
            f"invalid mode {resolved_mode!r}; expected one of {VALID_MODES}"
        )

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
