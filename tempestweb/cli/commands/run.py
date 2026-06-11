"""``tempestweb run`` — build then serve the app locally.

``run`` is ``build`` followed by serving the produced artifact. The build half is
real today; the serving half differs by mode (a static file server for wasm, the
FastAPI host for server) and is owned by Tracks T3 / T2. :func:`prepare_run`
produces the artifact and the bind plan (:class:`RunPlan`); a real server plugs
into that plan to do the actual serving.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tempestweb.cli.commands.build import BuildResult, build_artifact
from tempestweb.cli.config import ProjectConfig, load_config

__all__ = ["RunError", "RunPlan", "prepare_run"]


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
