"""``tempestweb run`` — build then serve the app locally.

``run`` is ``build`` followed by serving the produced artifact. :func:`prepare_run`
produces the artifact and the bind plan (:class:`RunPlan`); :func:`serve_run`
serves it. **Mode B (server)** is live: it imports the built ``server.py`` (the
real FastAPI WS/SSE host) and runs it under uvicorn — the same artifact a
deployment would run. **Mode A (wasm)** serving still depends on the Pyodide
bootstrap glue owned by Track T3, so :func:`serve_run` reports that and stops.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from tempestweb.cli.commands.build import BuildResult, build_artifact
from tempestweb.cli.config import ProjectConfig, load_config

__all__ = ["RunError", "RunPlan", "prepare_run", "serve_run"]


class RunError(RuntimeError):
    """Raised when a run cannot be prepared."""


@dataclass(slots=True)
class RunPlan:
    """A built artifact plus the bind plan for serving it.

    Attributes:
        build: The artifact produced for this run.
        host: The bind address (``127.0.0.1`` for local; ``0.0.0.0`` for LAN).
        port: The bind port.
    """

    build: BuildResult
    host: str
    port: int

    @property
    def url(self) -> str:
        """Return the local URL the served app will be reachable at.

        Returns:
            An ``http://host:port`` URL string.
        """
        return f"http://{self.host}:{self.port}"


def prepare_run(
    project_root: str | Path,
    *,
    mode: str | None = None,
    host: str | None = None,
    port: int | None = None,
) -> RunPlan:
    """Build the artifact and compute the bind plan for serving it.

    Args:
        project_root: The project directory.
        mode: ``"wasm"`` or ``"server"``. Defaults to the project config's mode.
        host: Override the bind address. Defaults to the project config's host.
        port: Override the bind port. Defaults to the project config's port.

    Returns:
        A :class:`RunPlan` with the built artifact and bind address.

    Raises:
        RunError: If the build fails.
    """
    config: ProjectConfig = load_config(project_root)
    try:
        build = build_artifact(project_root, mode=mode)
    except Exception as exc:  # noqa: BLE001 - normalize to RunError
        raise RunError(str(exc)) from exc

    return RunPlan(
        build=build,
        host=host or config.host,
        port=port if port is not None else config.port,
    )


def _load_artifact_server(out_dir: Path) -> ModuleType:
    """Import the built ``server.py`` module from a server artifact.

    Args:
        out_dir: The server artifact root (contains ``server.py``).

    Returns:
        The imported artifact server module (exposing ``app`` and ``run``).

    Raises:
        RunError: If the module cannot be located or imported.
    """
    server_path = out_dir / "server.py"
    spec = importlib.util.spec_from_file_location(
        "tempestweb_artifact_server", server_path
    )
    if spec is None or spec.loader is None:
        raise RunError(f"cannot import built server at {server_path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - surface any import-time failure
        raise RunError(f"failed to import built server: {exc}") from exc
    return module


def serve_run(plan: RunPlan) -> None:
    """Serve a built artifact according to its bind plan (blocking).

    For **server** mode this imports the artifact's ``server.py`` — the real
    FastAPI WS/SSE host — and runs it under uvicorn at ``plan.host:plan.port``.
    The call blocks until the server is stopped (Ctrl-C).

    Args:
        plan: The run plan produced by :func:`prepare_run`.

    Raises:
        RunError: If the artifact is not a server artifact (wasm serving is owned
            by Track T3) or the built server cannot be imported.
    """
    if plan.build.mode != "server":
        raise RunError(
            f"serving mode {plan.build.mode!r} is not available yet "
            "(wasm Pyodide bootstrap is owned by Track T3)"
        )
    server = _load_artifact_server(plan.build.out_dir)
    server.run(plan.host, plan.port)
