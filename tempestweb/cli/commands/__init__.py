"""tempestweb CLI commands — ``new`` / ``dev`` / ``build`` / ``run``.

Each command module owns one verb and exposes a pure, testable entrypoint that
does the real work without touching ``argv`` or the process. The thin
:mod:`tempestweb.cli.main` parser dispatches to these. Public symbols are
re-exported here so callers import at the package level.
"""

from tempestweb.cli.commands.build import (
    SERVER_ARTIFACT_FILES,
    WASM_ARTIFACT_FILES,
    BuildError,
    BuildResult,
    build_artifact,
)
from tempestweb.cli.commands.dev import (
    DevError,
    DevSession,
    StubTransport,
    create_dev_session,
    serve_dev,
)
from tempestweb.cli.commands.new import NewError, create_project
from tempestweb.cli.commands.run import RunError, RunPlan, prepare_run, serve_run
from tempestweb.cli.commands.sync import SyncError, SyncResult, sync_modules

__all__ = [
    "SERVER_ARTIFACT_FILES",
    "WASM_ARTIFACT_FILES",
    "BuildError",
    "BuildResult",
    "DevError",
    "DevSession",
    "NewError",
    "RunError",
    "RunPlan",
    "StubTransport",
    "SyncError",
    "SyncResult",
    "build_artifact",
    "create_dev_session",
    "create_project",
    "prepare_run",
    "serve_dev",
    "serve_run",
    "sync_modules",
]
