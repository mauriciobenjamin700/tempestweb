"""``tempestweb build`` — produce a deployable artifact for a mode.

Two artifact shapes share the same application code; only the transport and the
surrounding shell differ:

- **wasm** (Mode A, plan §A3): a static folder servable by any CDN/host —
  ``index.html`` + a bootstrap that loads Pyodide, the vendored core and the
  project's ``app.py``, plus the shared JS client.
- **server** (Mode B, plan §B0): a runnable FastAPI app folder — a ``server.py``
  entrypoint, the project's ``app.py`` and the shared JS client served as static
  assets.

The **wasm** artifact is live: it loads Pyodide + ``tempest_core`` and runs the
app in the browser, and ships the full PWA layer (``manifest.webmanifest``, icons,
and a service worker whose app-shell precache is injected at build time) so the
shell installs and opens offline. The **server** artifact's live FastAPI host is
carried on a separate track and is still stubbed here.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from tempestweb.cli.config import VALID_MODES, ProjectConfig, load_config
from tempestweb.cli.loader import load_app, render_initial_tree
from tempestweb.core.constants import WASM_PACKAGE_ARCHIVE, WASM_PYODIDE_VERSION
from tempestweb.pwa import ManifestOptions, emit_icons, write_manifest

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
    "virtualize.js",
    "router.js",
    "constants.js",
)

# Native capability bridge modules (client/native/*.js), copied into the wasm
# artifact so the in-process FFI dispatch (geolocation/clipboard/http/…) resolves.
_NATIVE_ASSETS: tuple[str, ...] = (
    "index.js",
    "audio.js",
    "camera.js",
    "clipboard.js",
    "geolocation.js",
    "http.js",
    "notifications.js",
    "share.js",
    "storage.js",
)

# Subpackages of ``tempestweb`` the Mode A runtime needs in the browser. The
# server/CLI/devserver stacks (and their Starlette/uvicorn deps) are omitted —
# Pyodide neither has them nor needs them to run ``view()`` in the tab. The
# renderer-agnostic core lives in the separate ``tempest_core`` package, bundled
# alongside (see :func:`_zip_package`).
_WASM_PACKAGE_PARTS: tuple[str, ...] = (
    "__init__.py",
    "runtime",
    "transports",
    "native",
    "components",
    "_core",
)

# PWA assets emitted into every artifact (manifest + service worker + icons).
_PWA_ICON_FILES: tuple[str, ...] = (
    "icon-192.png",
    "icon-512.png",
    "maskable-192.png",
    "maskable-512.png",
    "apple-touch-icon.png",
)
_PWA_FILES: tuple[str, ...] = (
    "manifest.webmanifest",
    "sw.js",
    "register.js",
    *(f"icons/{icon}" for icon in _PWA_ICON_FILES),
)

# Files a wasm artifact must contain, relative to the artifact root.
WASM_ARTIFACT_FILES: tuple[str, ...] = (
    "index.html",
    "app.py",
    "bootstrap.js",
    WASM_PACKAGE_ARCHIVE,
    *_PWA_FILES,
    *(f"client/{asset}" for asset in (*_CLIENT_ASSETS, "transport-wasm.js")),
    *(f"client/native/{asset}" for asset in _NATIVE_ASSETS),
    "client/push/web-push-client.js",
)

# Files a server artifact must contain, relative to the artifact root.
SERVER_ARTIFACT_FILES: tuple[str, ...] = (
    "server.py",
    "app.py",
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
    """Locate the shared pure-JS ``client/`` directory.

    Prefers the copy shipped inside the installed package (``tempestweb/_client``,
    force-included into the wheel); falls back to the repo-root ``client/`` when
    running from a source checkout.

    Returns:
        The absolute path to the client asset directory.

    Raises:
        BuildError: If neither location exists.
    """
    here = Path(__file__).resolve()
    packaged = here.parents[2] / "_client"  # tempestweb/_client (installed wheel)
    if packaged.is_dir():
        return packaged
    source = here.parents[3] / "client"  # repo-root client/ (dev checkout)
    if source.is_dir():
        return source
    raise BuildError(f"client assets not found (looked in {packaged} and {source})")


def _package_dir() -> Path:
    """Locate the installed ``tempestweb`` package directory.

    Returns:
        The absolute path to the ``tempestweb`` package (the parent of this
        ``cli/commands`` module, two levels up).
    """
    # tempestweb/cli/commands/build.py -> the package root is two parents up.
    return Path(__file__).resolve().parents[2]


def _tempest_core_dir() -> Path:
    """Locate the installed ``tempest_core`` package directory.

    Returns:
        The absolute path to the ``tempest_core`` package.

    Raises:
        BuildError: If ``tempest_core`` is not importable.
    """
    try:
        import tempest_core
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise BuildError(f"tempest_core is not installed: {exc}") from exc
    file = tempest_core.__file__
    if file is None:  # pragma: no cover - namespace package guard
        raise BuildError("tempest_core has no __init__ to locate")
    return Path(file).resolve().parent


def _zip_tree(
    archive: zipfile.ZipFile,
    root: Path,
    top: str,
    parts: tuple[str, ...] | None,
) -> None:
    """Write a package subtree into ``archive`` under ``top/``.

    Args:
        archive: The open zip archive to write into.
        root: The package's parent directory (entries are relative to it).
        top: The top-level package name the entries live under (e.g. ``tempestweb``).
        parts: Either ``None`` (the whole ``root/top`` tree) or the part names
            under ``root/top`` to include.

    Raises:
        BuildError: If an expected part is missing.
    """
    names = [top] if parts is None else [f"{top}/{part}" for part in parts]
    for name in names:
        source = root / name
        if not source.exists():
            raise BuildError(f"missing package part: {source}")
        if source.is_file():
            archive.write(source, name)
            continue
        for path in sorted(source.rglob("*")):
            if path.is_dir() or "__pycache__" in path.parts:
                continue
            archive.write(path, str(path.relative_to(root)))


def _zip_package(dest: Path) -> None:
    """Zip the Mode A Python payload (tempestweb subset + tempest_core) into ``dest``.

    The archive carries the Mode A subset of ``tempestweb``
    (:data:`_WASM_PACKAGE_PARTS`) and the whole ``tempest_core`` package, excluding
    ``__pycache__``. The Pyodide bootstrap unpacks it into the virtual filesystem's
    working directory (on ``sys.path``), so ``import tempestweb`` and
    ``import tempest_core`` both resolve in the browser.

    Args:
        dest: The ``.zip`` path to write.

    Raises:
        BuildError: If an expected package part is missing.
    """
    tempestweb_root = _package_dir().parent
    tempest_core_root = _tempest_core_dir().parent
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as archive:
        _zip_tree(archive, tempestweb_root, "tempestweb", _WASM_PACKAGE_PARTS)
        _zip_tree(archive, tempest_core_root, "tempest_core", None)


def _build_pwa(out: Path, client: Path, name: str, precache: tuple[str, ...]) -> None:
    """Emit the PWA layer (manifest + icons + service worker) into ``out``.

    Writes ``manifest.webmanifest`` and the icon set, then copies the shared
    service worker with its build-time placeholders filled: ``__CACHE_VERSION__``
    becomes a content hash of the precache list and ``"__PRECACHE_MANIFEST__"``
    becomes the JSON app-shell list the worker caches on install. ``register.js``
    is copied verbatim for the page to register the worker.

    Args:
        out: The artifact root.
        client: The shared ``client/`` directory.
        name: The project name (manifest ``name``/``short_name``).
        precache: The app-shell URLs the service worker precaches (cache-first).

    Raises:
        BuildError: If the service worker source is missing.
    """
    write_manifest(
        out / "manifest.webmanifest",
        ManifestOptions(name=name, short_name=name[:12]),
    )
    emit_icons(out / "icons")

    sw_source = client / "sw" / "sw.js"
    register_source = client / "sw" / "register.js"
    if not sw_source.is_file() or not register_source.is_file():
        raise BuildError(f"missing service worker sources under {client / 'sw'}")

    version = "tw-" + hashlib.sha1("|".join(precache).encode("utf-8")).hexdigest()[:12]
    sw = sw_source.read_text(encoding="utf-8")
    sw = sw.replace("__CACHE_VERSION__", version)
    # Replace the quoted placeholder with a JS string literal carrying the JSON
    # array, so the worker's ``JSON.parse(injected)`` yields the app-shell list.
    sw = sw.replace('"__PRECACHE_MANIFEST__"', json.dumps(json.dumps(list(precache))))
    (out / "sw.js").write_text(sw, encoding="utf-8")
    shutil.copyfile(register_source, out / "register.js")


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
    <link rel="manifest" href="./manifest.webmanifest" />
    <meta name="theme-color" content="#111111" />
    <link rel="apple-touch-icon" href="./icons/apple-touch-icon.png" />
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="./bootstrap.js"></script>
    <script type="module">
      import {{ registerServiceWorker }} from "./register.js";
      if ("serviceWorker" in navigator) {{
        registerServiceWorker({{ url: "/sw.js" }});
      }}
    </script>
  </body>
</html>
"""


def _bootstrap_js(name: str) -> str:
    """Render the live wasm bootstrap entrypoint (Mode A, Pyodide).

    The emitted module loads Pyodide + ``pydantic`` from the CDN, unpacks the
    zipped ``tempestweb`` package and writes ``app.py`` into the Pyodide virtual
    filesystem, builds the app in-process via
    :func:`tempestweb.runtime.wasm_main.bootstrap`, and mounts the shared client
    onto ``#app`` through ``transport-wasm.js`` — Python runs in the same tab, so
    the transport is an in-process bridge with no network.

    Args:
        name: The project name.

    Returns:
        The bootstrap module source.
    """
    return f"""\
// bootstrap.js — live wasm artifact entrypoint for "{name}" (Mode A, Pyodide).
//
// Loads Pyodide + pydantic, installs the tempestweb package and app.py into the
// Pyodide virtual FS, builds the app in-process and mounts the shared client.
import {{ mount }} from "./client/tempestweb.js";
import {{ createWasmTransport }} from "./client/transport-wasm.js";
import {{ installNativeBridge }} from "./client/native/index.js";

const PYODIDE_BASE = "https://cdn.jsdelivr.net/pyodide/{WASM_PYODIDE_VERSION}/full/";

// Python entry: build the app and hand back a _start(on_patches, dispatch) hook.
const PY_GLUE = `
import app
from tempestweb.runtime.wasm_main import bootstrap

def _start(on_patches, dispatch, on_navigate):
    return bootstrap(
        app.make_state(), app.view, on_patches, dispatch, on_navigate
    )

_start
`;

export async function boot() {{
  const root = document.getElementById("app");

  // 1. Load Pyodide and pydantic (the vendored core's only hard dependency).
  const {{ loadPyodide }} = await import(PYODIDE_BASE + "pyodide.mjs");
  const pyodide = await loadPyodide({{ indexURL: PYODIDE_BASE }});
  await pyodide.loadPackage(["pydantic"]);

  // 2. Install the tempestweb package + the app module into the virtual FS.
  const pkgZip = await (await fetch("./{WASM_PACKAGE_ARCHIVE}")).arrayBuffer();
  pyodide.unpackArchive(pkgZip, "zip");
  const appSource = await (await fetch("./app.py")).text();
  pyodide.FS.writeFile("app.py", appSource, {{ encoding: "utf8" }});

  // 3. Build the app in Python; _start wires on_patches and returns the handle.
  const start = pyodide.runPython(PY_GLUE);

  // 4. In-process bridge: Python delivers patches as a JSON string; events go
  //    back as JSON strings. No network — Python runs in this tab.
  let deliverToTransport = null;
  const onPatches = (patchesJson) => {{
    if (deliverToTransport) deliverToTransport(JSON.parse(patchesJson));
  }};
  // View -> URL: push the new path when the app navigates (no popstate fires, so
  // no loop with the router's URL -> view reporting).
  const onNavigate = (path) => {{
    if (path && location.pathname !== path) {{
      history.pushState({{}}, "", path);
    }}
  }};

  // Native capabilities (geolocation/clipboard/http/…): expose the in-process
  // dispatch on window, and bridge it to Python as a JSON-string seam (so the
  // envelope crosses the FFI cleanly, no proxy conversion).
  installNativeBridge(globalThis);
  const onNative = async (envelopeJson) => {{
    const result = await globalThis.__tempestweb_native__(JSON.parse(envelopeJson));
    return JSON.stringify(result);
  }};

  const handle = start(onPatches, onNative, onNavigate);

  const bridge = {{
    onDeliver(handler) {{
      deliverToTransport = handler;
    }},
    pushEvent(event) {{
      handle.push_event_json(JSON.stringify(event));
    }},
    close() {{
      handle.close();
    }},
  }};

  const transport = createWasmTransport(bridge);
  const initialNode = JSON.parse(handle.initial_node_json());
  mount(root, transport, initialNode);
}}

boot();
"""


def _server_py(name: str) -> str:
    """Render the server artifact's FastAPI entrypoint.

    The live WebSocket host is owned by Track T2 (Mode B); this placeholder pins
    the artifact's entrypoint shape so the layout is verifiable today.

    Args:
        name: The project name.

    Returns:
        The server entrypoint source.
    """
    return f'''\
"""server.py — server artifact entrypoint for "{name}".

PHASE B0 (Track T2): build the FastAPI app (tempest-fastapi-sdk patterns),
mount the WebSocket endpoint that drives `app.view`, and serve ./static.
"""

from __future__ import annotations


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Serve the app over HTTP + WebSocket.

    Args:
        host: Bind address (127.0.0.1 for local; 0.0.0.0 for LAN access).
        port: Bind port.

    Raises:
        NotImplementedError: The live host is provided by Track T2.
    """
    raise NotImplementedError("B0: server host is provided by Track T2")


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
    _zip_package(out / WASM_PACKAGE_ARCHIVE)
    _copy_client(client, out / "client", "transport-wasm.js")
    # Native capability bridge (geolocation/clipboard/http/…) for the in-process
    # FFI dispatch the bootstrap installs.
    native_dest = out / "client" / "native"
    native_dest.mkdir(parents=True, exist_ok=True)
    for asset in _NATIVE_ASSETS:
        source = client / "native" / asset
        if not source.is_file():
            raise BuildError(f"missing native asset: {source}")
        shutil.copyfile(source, native_dest / asset)
    # The notifications bridge imports the WebPush client from client/push/.
    push_source = client / "push" / "web-push-client.js"
    if not push_source.is_file():
        raise BuildError(f"missing push asset: {push_source}")
    push_dest = out / "client" / "push"
    push_dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(push_source, push_dest / "web-push-client.js")
    # App-shell the service worker precaches for an offline second load. The
    # Pyodide runtime itself loads from the CDN (cross-origin) and is out of scope
    # for this precache; the local shell + package payload are cached.
    precache = (
        "/",
        "/index.html",
        "/manifest.webmanifest",
        "/bootstrap.js",
        "/register.js",
        "/app.py",
        f"/{WASM_PACKAGE_ARCHIVE}",
        *(f"/client/{asset}" for asset in (*_CLIENT_ASSETS, "transport-wasm.js")),
    )
    _build_pwa(out, client, name, precache)
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
    _copy_client(client, out / "static", "transport-ws.js")
    return tuple(sorted(SERVER_ARTIFACT_FILES))
