"""Read a tempestweb project's ``tempestweb.toml`` configuration.

The config is intentionally tiny: it names the entrypoint module and the default
dev/build mode and bind address. Every field has a default so a project without a
``tempestweb.toml`` (or with a partial one) still works.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tempestweb.core.constants import VALID_MODES

__all__ = ["VALID_MODES", "ConfigError", "ProjectConfig", "load_config"]


class ConfigError(RuntimeError):
    """Raised when a ``tempestweb.toml`` is present but invalid."""


@dataclass(slots=True)
class ProjectConfig:
    """Resolved configuration for a tempestweb project.

    Attributes:
        root: The project directory the config was read from.
        name: The project name.
        entrypoint: The project-relative path to the app module.
        mode: The default execution mode (``"wasm"`` or ``"server"``).
        host: The default dev/run bind address.
        port: The default dev/run port.
    """

    root: Path
    name: str
    entrypoint: str = "app.py"
    mode: str = "wasm"
    host: str = "127.0.0.1"
    port: int = 8000

    @property
    def entrypoint_path(self) -> Path:
        """Return the absolute path to the entrypoint module.

        Returns:
            ``root / entrypoint`` resolved to an absolute path.
        """
        return (self.root / self.entrypoint).resolve()


def load_config(root: str | Path) -> ProjectConfig:
    """Load ``tempestweb.toml`` from a project root, falling back to defaults.

    Args:
        root: The project directory.

    Returns:
        A :class:`ProjectConfig`. If no ``tempestweb.toml`` exists, every field
        takes its default and ``name`` is the directory name.

    Raises:
        ConfigError: If a ``tempestweb.toml`` exists but is malformed, or names
            an invalid mode.
    """
    root_path = Path(root).resolve()
    config_path = root_path / "tempestweb.toml"
    name = root_path.name

    if not config_path.is_file():
        return ProjectConfig(root=root_path, name=name)

    try:
        raw: dict[str, Any] = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid {config_path}: {exc}") from exc

    project = raw.get("project", {})
    dev = raw.get("dev", {})
    mode = str(dev.get("mode", "wasm"))
    if mode not in VALID_MODES:
        raise ConfigError(
            f"invalid mode {mode!r} in {config_path}; expected one of {VALID_MODES}"
        )

    return ProjectConfig(
        root=root_path,
        name=str(project.get("name", name)),
        entrypoint=str(project.get("entrypoint", "app.py")),
        mode=mode,
        host=str(dev.get("host", "127.0.0.1")),
        port=int(dev.get("port", 8000)),
    )
