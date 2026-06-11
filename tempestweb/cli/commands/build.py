"""``tempestweb build`` — produce a deployable artifact for a mode.

Two artifact shapes share the same application code; only the transport and the
surrounding shell differ:

- **wasm** (Mode A, plan §A3): a static folder servable by any CDN/host —
  ``index.html`` + a bootstrap that loads Pyodide, the vendored core and the
  project's ``app.py``, plus the shared JS client.
- **server** (Mode B, plan §B0): a runnable FastAPI app folder — a ``server.py``
  entrypoint, the project's ``app.py`` and the shared JS client served as static
  assets.

The **server** artifact is live: its ``server.py`` builds the real FastAPI host
from :func:`tempestweb.server.create_app` (WebSocket + SSE), serves the shared
client under ``/static`` and an ``index.html`` shell at ``/`` that mounts the app
over a WebSocket transport — ``python server.py`` (or ``uvicorn server:app``)
serves a working app. The **wasm** artifact's Pyodide bootstrap glue is still
owned by Track T3 and is stubbed here with a clearly-marked placeholder.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from tempestweb.cli.config import VALID_MODES, ProjectConfig, load_config
from tempestweb.cli.loader import load_app, render_initial_tree

__all__ = [
    "WASM_ARTIFACT_FILES",
    "SERVER_ARTIFACT_FILES",
    "BuildError",
    "BuildResult",
    "build_artifact",
]

# Client assets copied into every artifact (the shared leaf renderer).
_CLIENT_ASSETS: tuple[str, ...] = (
    "tempestweb.js",
    "dom.js",
    "style.js",
    "events.js",
    "transport.js",
)

# Files a wasm artifact must contain, relative to the artifact root.
WASM_ARTIFACT_FILES: tuple[str, ...] = (
    "index.html",
    "app.py",
    "bootstrap.js",
    *(f"client/{asset}" for asset in (*_CLIENT_ASSETS, "transport-wasm.js")),
)

# Files a server artifact must contain, relative to the artifact root.
SERVER_ARTIFACT_FILES: tuple[str, ...] = (
    "server.py",
    "app.py",
    "index.html",
    *(f"static/{asset}" for asset in (*_CLIENT_ASSETS, "transport-ws.js")),
)


class BuildError(RuntimeError):
    """Raised when a build cannot produce a valid artifact."""


@dataclass(slots=True)
class BuildResult:
    """The outcome of a build.

    Attributes:
        mode: The execution mode that was built (``"wasm"`` or ``"server"``).
        out_dir: The artifact root directory.
        files: Artifact-relative paths that were written, in a stable order.
    """

    mode: str
    out_dir: Path
    files: tuple[str, ...] = field(default_factory=tuple)


def _client_dir() -> Path:
    """Locate the repository's shared ``client/`` directory.

    Returns:
        The absolute path to the ``client/`` directory shipped with tempestweb.

    Raises:
        BuildError: If the client directory cannot be found.
    """
    # tempestweb/cli/commands/build.py -> repo root is three parents up.
    candidate = Path(__file__).resolve().parents[3] / "client"
    if not candidate.is_dir():
        raise BuildError(f"shared client directory not found at {candidate}")
    return candidate


def _copy_client(client: Path, dest: Path, transport: str) -> list[str]:
    """Copy the shared client assets plus a mode-specific transport into ``dest``.

    Args:
        client: The repository's ``client/`` directory.
        dest: The artifact subdirectory to copy assets into.
        transport: The mode-specific transport filename (e.g. ``transport-wasm.js``).

    Returns:
        The asset filenames that were copied.

    Raises:
        BuildError: If an expected client asset is missing.
    """
    dest.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for asset in (*_CLIENT_ASSETS, transport):
        source = client / asset
        if not source.is_file():
            raise BuildError(f"missing client asset: {source}")
        shutil.copyfile(source, dest / asset)
        written.append(asset)
    return written


def _index_html(name: str) -> str:
    """Render the static ``index.html`` shell for a wasm artifact.

    Args:
        name: The project name (page title).

    Returns:
        The HTML document that boots the app in the browser.
    """
    return f"""\
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{name}</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="./bootstrap.js"></script>
  </body>
</html>
"""


def _bootstrap_js(name: str) -> str:
    """Render the wasm bootstrap entrypoint.

    The live Pyodide loading is owned by Track T3 (Mode A); this placeholder
    pins the artifact's entrypoint shape so the layout is verifiable today.

    Args:
        name: The project name.

    Returns:
        The bootstrap module source.
    """
    return f"""\
// bootstrap.js — wasm artifact entrypoint for "{name}".
//
// PHASE A3 (Track T3): load Pyodide, install the vendored core wheel, run
// app.py, then mount() the shared client onto #app via transport-wasm.js.
import {{ mount }} from "./client/tempestweb.js";

export async function boot() {{
  throw new Error("A3: Pyodide bootstrap is provided by Track T3");
}}

void mount;
"""


def _index_html_server(name: str) -> str:
    """Render the ``index.html`` shell for a server artifact (Mode B).

    The shell mounts the shared client over a WebSocket transport pointed at the
    same origin's ``/ws`` endpoint. ``mount`` is called without an initial node:
    the server sends the initial scene as the first patch batch (a root
    ``Replace``), which the client consumes as the initial tree.

    Args:
        name: The project name (page title).

    Returns:
        The HTML document that boots the app in the browser.
    """
    return f"""\
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{name}</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module">
      import {{ mount }} from "./static/tempestweb.js";
      import {{ createWebSocketTransport }} from "./static/transport-ws.js";

      const scheme = location.protocol === "https:" ? "wss://" : "ws://";
      const transport = createWebSocketTransport(scheme + location.host + "/ws");
      mount(document.getElementById("app"), transport);
    </script>
  </body>
</html>
"""


def _server_py(name: str) -> str:
    """Render the server artifact's FastAPI entrypoint (Mode B, live).

    The emitted module imports the sibling ``app.py``, builds the real FastAPI
    host via :func:`tempestweb.server.create_app` (WebSocket + SSE routes), mounts
    the shared client under ``/static`` and serves ``index.html`` at ``/``. It is
    runnable directly (``python server.py``) or via ``uvicorn server:app``.

    Args:
        name: The project name.

    Returns:
        The server entrypoint source.
    """
    return f'''\
"""server.py — server artifact entrypoint for "{name}" (Mode B).

Builds the FastAPI host that drives ``app.view`` over WebSocket/SSE (the
tempestweb server engine), serves the shared client under ``/static`` and the
``index.html`` shell at ``/``. Run with ``python server.py`` or
``uvicorn server:app``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from tempestweb.server import create_app

_HERE = Path(__file__).resolve().parent
# The project's ``app.py`` sits next to this file; import it by name.
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import app as _project  # noqa: E402


def build() -> FastAPI:
    """Build the FastAPI app: WS/SSE engine + static client + index shell.

    Returns:
        The configured FastAPI application.
    """
    api = create_app(_project.make_state, _project.view, title="{name}")
    api.mount(
        "/static",
        StaticFiles(directory=str(_HERE / "static")),
        name="static",
    )

    @api.get("/")
    async def index() -> FileResponse:
        """Serve the app shell that mounts the client over WebSocket."""
        return FileResponse(str(_HERE / "index.html"))

    return api


app = build()


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Serve the app over HTTP + WebSocket.

    Args:
        host: Bind address (127.0.0.1 for local; 0.0.0.0 for LAN access).
        port: Bind port.
    """
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run()
'''


def build_artifact(
    project_root: str | Path,
    *,
    mode: str | None = None,
    out_dir: str | Path | None = None,
    clean: bool = True,
) -> BuildResult:
    """Build a deployable artifact for ``mode`` from a project.

    Args:
        project_root: The project directory (must contain the entrypoint).
        mode: ``"wasm"`` or ``"server"``. Defaults to the project config's mode.
        out_dir: Where to write the artifact. Defaults to
            ``<project_root>/dist/<mode>``.
        clean: When ``True`` (default), remove an existing ``out_dir`` first.

    Returns:
        A :class:`BuildResult` describing the artifact.

    Raises:
        BuildError: If the mode is invalid or the project's view fails to render.
    """
    config: ProjectConfig = load_config(project_root)
    resolved_mode = mode or config.mode
    if resolved_mode not in VALID_MODES:
        raise BuildError(
            f"invalid mode {resolved_mode!r}; expected one of {VALID_MODES}"
        )

    # A build is only valid if the project actually renders an initial tree.
    try:
        loaded = load_app(config.entrypoint_path)
        render_initial_tree(loaded)
    except Exception as exc:  # noqa: BLE001 - turn any load/render error into BuildError
        raise BuildError(f"project failed to build: {exc}") from exc

    out = (
        Path(out_dir).resolve()
        if out_dir is not None
        else (config.root / "dist" / resolved_mode).resolve()
    )
    if clean and out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    client = _client_dir()
    app_source = config.entrypoint_path.read_text(encoding="utf-8")

    if resolved_mode == "wasm":
        files = _build_wasm(out, client, config.name, app_source)
    else:
        files = _build_server(out, client, config.name, app_source)

    return BuildResult(mode=resolved_mode, out_dir=out, files=files)


def _build_wasm(out: Path, client: Path, name: str, app_source: str) -> tuple[str, ...]:
    """Write the wasm (static) artifact layout into ``out``.

    Args:
        out: The artifact root.
        client: The shared ``client/`` directory.
        name: The project name.
        app_source: The project's ``app.py`` source to embed.

    Returns:
        The artifact-relative paths written, sorted.
    """
    (out / "index.html").write_text(_index_html(name), encoding="utf-8")
    (out / "bootstrap.js").write_text(_bootstrap_js(name), encoding="utf-8")
    (out / "app.py").write_text(app_source, encoding="utf-8")
    _copy_client(client, out / "client", "transport-wasm.js")
    return tuple(sorted(WASM_ARTIFACT_FILES))


def _build_server(
    out: Path, client: Path, name: str, app_source: str
) -> tuple[str, ...]:
    """Write the server (FastAPI) artifact layout into ``out``.

    Args:
        out: The artifact root.
        client: The shared ``client/`` directory.
        name: The project name.
        app_source: The project's ``app.py`` source to embed.

    Returns:
        The artifact-relative paths written, sorted.
    """
    (out / "server.py").write_text(_server_py(name), encoding="utf-8")
    (out / "app.py").write_text(app_source, encoding="utf-8")
    (out / "index.html").write_text(_index_html_server(name), encoding="utf-8")
    _copy_client(client, out / "static", "transport-ws.js")
    return tuple(sorted(SERVER_ARTIFACT_FILES))
