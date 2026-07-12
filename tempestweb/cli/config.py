"""Read a tempestweb project's ``tempestweb.toml`` configuration.

The config is intentionally tiny: it names the entrypoint module and the default
dev/build mode and bind address. Every field has a default so a project without a
``tempestweb.toml`` (or with a partial one) still works.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from tempestweb.cli.quality import DEFAULT_STRICTNESS, VALID_STRICTNESS, Strictness
from tempestweb.core.constants import VALID_MODES

__all__ = [
    "VALID_MODES",
    "ConfigError",
    "ProjectConfig",
    "PwaConfig",
    "WasmConfig",
    "load_config",
]


class ConfigError(RuntimeError):
    """Raised when a ``tempestweb.toml`` is present but invalid."""


@dataclass(slots=True)
class PwaConfig:
    """Web-App-Manifest overrides a project declares under ``[pwa]``.

    Every field is optional: a project with no ``[pwa]`` section still ships an
    installable-shaped manifest (the manifest emitter fills the defaults). These
    feed :class:`tempestweb.pwa.ManifestOptions` at build time so the installed
    app carries the project's own name, colors and display mode.

    Attributes:
        name: Full application name. Falls back to the project name when unset.
        short_name: Home-screen label. Falls back to a trimmed project name.
        description: Human-readable description shown in the install UI.
        theme_color: Toolbar / status-bar color (any CSS color).
        background_color: Splash-screen background (any CSS color).
        display: Installable display mode
            (``"standalone"`` | ``"fullscreen"`` | ``"minimal-ui"``).
        orientation: Optional preferred orientation (e.g. ``"portrait"``).
        lang: BCP-47 language tag for the manifest.
        categories: App-store categories (e.g. ``["productivity"]``).
    """

    name: str | None = None
    short_name: str | None = None
    description: str | None = None
    theme_color: str = "#111111"
    background_color: str = "#ffffff"
    display: str = "standalone"
    orientation: str | None = None
    lang: str = "pt-BR"
    categories: list[str] = field(default_factory=list)


@dataclass(slots=True)
class WasmConfig:
    """Mode A (WASM) build extras a project declares under ``[wasm]``.

    A vanilla counter needs none of these — the defaults are all empty, so a
    project without a ``[wasm]`` section builds exactly as before. A real app
    that pulls extra Pyodide packages (numpy, pillow), ships its own Python
    modules beside ``app.py``, bundles static assets (ONNX models), or loads a
    third-party JS library (onnxruntime-web) declares them here.

    Attributes:
        packages: Extra Pyodide packages to ``loadPackage`` alongside the core's
            own ``pydantic`` (e.g. ``["numpy", "pillow"]``). Resolved from the
            Pyodide lock for offline builds.
        modules: Project-relative paths (files or package directories) to bundle
            into the Mode A package archive next to ``app.py``, so the app can
            ``import`` them in the browser (e.g. ``["famacha"]``).
        assets: Project-relative glob patterns of static files copied verbatim
            into the artifact, preserving their relative path, and added to the
            service-worker precache (e.g. ``["models/*.onnx", "vendor/ort/*"]``).
        scripts: URLs or artifact-relative paths injected as classic ``<script>``
            tags in ``index.html`` ``<head>`` before the bootstrap module, so a
            global library (``window.ort``) is ready when Python boots.
    """

    packages: list[str] = field(default_factory=list)
    modules: list[str] = field(default_factory=list)
    assets: list[str] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)


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
        wasm: Mode A build extras (extra packages, bundled modules, static
            assets, injected scripts). Empty by default.
        pwa: Web-App-Manifest overrides. Installable-shaped defaults otherwise.
        typing_strictness: How strictly the quality commands (``lint``/``type``/
            ``check``) enforce typing — ``"lenient"`` | ``"standard"`` |
            ``"strict"``. Read from ``[quality] typing_strictness``.
    """

    root: Path
    name: str
    entrypoint: str = "app.py"
    mode: str = "wasm"
    host: str = "127.0.0.1"
    port: int = 8000
    wasm: WasmConfig = field(default_factory=WasmConfig)
    pwa: PwaConfig = field(default_factory=PwaConfig)
    typing_strictness: Strictness = DEFAULT_STRICTNESS

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

    quality = raw.get("quality", {})
    strictness = str(quality.get("typing_strictness", DEFAULT_STRICTNESS))
    if strictness not in VALID_STRICTNESS:
        raise ConfigError(
            f"invalid typing_strictness {strictness!r} in {config_path}; "
            f"expected one of {sorted(VALID_STRICTNESS)}"
        )

    return ProjectConfig(
        root=root_path,
        name=str(project.get("name", name)),
        entrypoint=str(project.get("entrypoint", "app.py")),
        mode=mode,
        host=str(dev.get("host", "127.0.0.1")),
        port=int(dev.get("port", 8000)),
        wasm=_parse_wasm(raw.get("wasm", {}), config_path),
        pwa=_parse_pwa(raw.get("pwa", {}), config_path),
        typing_strictness=cast("Strictness", strictness),
    )


def _str_list(value: Any, key: str, config_path: Path) -> list[str]:  # noqa: ANN401 - raw TOML value
    """Coerce a ``[wasm]`` field into a list of strings.

    Args:
        value: The raw TOML value (expected to be a list of strings).
        key: The field name, for error messages.
        config_path: The config file path, for error messages.

    Returns:
        The value as a list of strings, or ``[]`` when absent.

    Raises:
        ConfigError: If the value is not a list of strings.
    """
    if not value:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(
            f"invalid wasm.{key} in {config_path}; expected a list of strings"
        )
    return list(value)


def _parse_wasm(raw: Any, config_path: Path) -> WasmConfig:  # noqa: ANN401 - raw TOML table
    """Parse the ``[wasm]`` table into a :class:`WasmConfig`.

    Args:
        raw: The raw ``[wasm]`` table (a dict), or an empty dict when absent.
        config_path: The config file path, for error messages.

    Returns:
        The resolved :class:`WasmConfig`; all fields empty when the table is absent.

    Raises:
        ConfigError: If the table or any field has the wrong type.
    """
    if not raw:
        return WasmConfig()
    if not isinstance(raw, dict):
        raise ConfigError(f"invalid [wasm] table in {config_path}")
    return WasmConfig(
        packages=_str_list(raw.get("packages"), "packages", config_path),
        modules=_str_list(raw.get("modules"), "modules", config_path),
        assets=_str_list(raw.get("assets"), "assets", config_path),
        scripts=_str_list(raw.get("scripts"), "scripts", config_path),
    )


_INSTALLABLE_DISPLAYS: frozenset[str] = frozenset(
    {"standalone", "fullscreen", "minimal-ui"}
)


def _opt_str(value: Any, key: str, config_path: Path) -> str | None:  # noqa: ANN401 - raw TOML value
    """Coerce an optional ``[pwa]`` string field, or ``None`` when absent.

    Args:
        value: The raw TOML value (expected to be a string or absent).
        key: The field name, for error messages.
        config_path: The config file path, for error messages.

    Returns:
        The string, or ``None`` when the key is absent.

    Raises:
        ConfigError: If the value is present but not a string.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"invalid pwa.{key} in {config_path}; expected a string")
    return value


def _parse_pwa(raw: Any, config_path: Path) -> PwaConfig:  # noqa: ANN401 - raw TOML table
    """Parse the ``[pwa]`` table into a :class:`PwaConfig`.

    Args:
        raw: The raw ``[pwa]`` table (a dict), or an empty dict when absent.
        config_path: The config file path, for error messages.

    Returns:
        The resolved :class:`PwaConfig`; all defaults when the table is absent.

    Raises:
        ConfigError: If the table or any field has the wrong type, or ``display``
            is not an installable value.
    """
    if not raw:
        return PwaConfig()
    if not isinstance(raw, dict):
        raise ConfigError(f"invalid [pwa] table in {config_path}")
    display = str(raw.get("display", "standalone"))
    if display not in _INSTALLABLE_DISPLAYS:
        raise ConfigError(
            f"invalid pwa.display {display!r} in {config_path}; "
            f"expected one of {sorted(_INSTALLABLE_DISPLAYS)}"
        )
    defaults = PwaConfig()
    return PwaConfig(
        name=_opt_str(raw.get("name"), "name", config_path),
        short_name=_opt_str(raw.get("short_name"), "short_name", config_path),
        description=_opt_str(raw.get("description"), "description", config_path),
        theme_color=str(raw.get("theme_color", defaults.theme_color)),
        background_color=str(raw.get("background_color", defaults.background_color)),
        display=display,
        orientation=_opt_str(raw.get("orientation"), "orientation", config_path),
        lang=str(raw.get("lang", defaults.lang)),
        categories=_str_list(raw.get("categories"), "categories", config_path),
    )
