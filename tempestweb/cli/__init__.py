"""tempestweb.cli — the ``tempestweb`` command-line tool.

The CLI drives the whole developer loop in typed Python: ``new`` scaffolds a
runnable project, ``dev`` watches and triggers reloads, ``build`` emits a
mode-specific artifact, and ``run`` builds then serves. See ``docs/plan.md`` §5.

Public symbols (the parser, every command entrypoint, the config/loader/scaffold
helpers) are re-exported here so callers import at the package level rather than
reaching into submodules.
"""

from tempestweb.cli.commands import (
    SERVER_ARTIFACT_FILES,
    WASM_ARTIFACT_FILES,
    BuildError,
    BuildResult,
    DevError,
    DevSession,
    NewError,
    RunError,
    RunPlan,
    StubTransport,
    build_artifact,
    create_dev_session,
    create_project,
    prepare_run,
)
from tempestweb.cli.config import (
    VALID_MODES,
    ConfigError,
    ProjectConfig,
    load_config,
)
from tempestweb.cli.loader import (
    LoadedApp,
    ProjectLoadError,
    load_app,
    render_initial_tree,
)
from tempestweb.cli.main import build_parser, main
from tempestweb.cli.scaffold import (
    DEFAULT_MODE,
    PROJECT_FILES,
    ProjectExistsError,
    ScaffoldResult,
    render_files,
    scaffold_project,
)

__all__ = [
    "DEFAULT_MODE",
    "PROJECT_FILES",
    "SERVER_ARTIFACT_FILES",
    "VALID_MODES",
    "WASM_ARTIFACT_FILES",
    "BuildError",
    "BuildResult",
    "ConfigError",
    "DevError",
    "DevSession",
    "LoadedApp",
    "NewError",
    "ProjectConfig",
    "ProjectExistsError",
    "ProjectLoadError",
    "RunError",
    "RunPlan",
    "ScaffoldResult",
    "StubTransport",
    "build_artifact",
    "build_parser",
    "create_dev_session",
    "create_project",
    "load_app",
    "load_config",
    "main",
    "prepare_run",
    "render_files",
    "render_initial_tree",
    "scaffold_project",
]
