"""``tempestweb build`` — produce a deployable artifact for a mode.

Two artifact shapes share the same application code; only the transport and the
surrounding shell differ:

- **wasm** (Mode A, plan §A3): a static folder servable by any CDN/host —
  ``index.html`` + a bootstrap that loads Pyodide, the vendored core and the
  project's ``app.py``, plus the shared JS client.
- **server** (Mode B, plan §B0): a runnable FastAPI app folder — a ``server.py``
  entrypoint, the project's ``app.py`` and the shared JS client served as static
  assets.

Both artifacts are live. The **wasm** artifact loads Pyodide + ``tempest_core`` and
runs the app in the browser, ships the native-capability bridge and the full PWA
layer (``manifest.webmanifest``, icons, and a service worker whose app-shell
precache is injected at build time) so the shell installs and opens offline. The
**server** artifact's ``server.py`` builds the real FastAPI host from
:func:`tempestweb.server.create_app` (WebSocket + SSE), serves the shared client
under ``/static`` and an ``index.html`` shell at ``/`` that mounts the app over a
WebSocket transport — ``python server.py`` (or ``uvicorn server:app``) serves it.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from tempestweb.cli.config import VALID_MODES, ProjectConfig, WasmConfig, load_config
from tempestweb.cli.loader import load_app, render_initial_tree
from tempestweb.core.constants import WASM_PACKAGE_ARCHIVE, WASM_PYODIDE_VERSION
from tempestweb.pwa import (
    ManifestOptions,
    emit_icons,
    pyodide_cdn_base,
    vendor_pyodide,
    write_manifest,
)

#: Pyodide packages the vendored core needs at runtime (its only hard dependency).
#: An offline build vendors the closure of these from the Pyodide lock file.
WASM_RUNTIME_PACKAGES: tuple[str, ...] = ("pydantic",)

__all__ = [
    "WASM_ARTIFACT_FILES",
    "SERVER_ARTIFACT_FILES",
    "TRANSPILE_ARTIFACT_FILES",
    "BuildError",
    "BuildResult",
    "build_artifact",
]

# Client assets copied into every artifact (the shared leaf renderer).
_CLIENT_ASSETS: tuple[str, ...] = (
    "tempestweb.js",
    "dom.js",
    "style.js",
    "theme.js",
    "events.js",
    "transport.js",
    "virtualize.js",
    "router.js",
    "constants.js",
)

# Mode C (transpile) native-runtime modules (client/transpile/*.js): the diff,
# the IR widget builders, and the State/App runtime. Copied into a transpile/
# subdir of the artifact's client/, next to the generated app module.
_TRANSPILE_ASSETS: tuple[str, ...] = (
    "runtime.js",
    "widgets.js",
    "widgets.gen.js",
    "widget-support.js",
    "components.js",
    "spacing.gen.js",
    "diff.js",
    "widget-styles.gen.js",
    "native.js",
)

#: The generated app module's filename inside the transpile artifact.
_TRANSPILE_APP_MODULE: str = "app.gen.js"

# Icon set modules (client/icons/*.js): the resolver plus the vendored Lucide and
# Material Symbols path data. Imported by dom.js (`./icons/index.js`), so they are
# copied alongside the other client assets in both modes.
_ICON_ASSETS: tuple[str, ...] = (
    "index.js",
    "lucide.js",
    "material.js",
)

# Native capability bridge modules (client/native/*.js), copied into the wasm
# artifact so the in-process FFI dispatch (geolocation/clipboard/http/…) resolves.
_NATIVE_ASSETS: tuple[str, ...] = (
    "index.js",
    "audio.js",
    "camera.js",
    "clipboard.js",
    "cookies.js",
    "file.js",
    "geolocation.js",
    "http.js",
    "install.js",
    "notifications.js",
    "onnx.js",
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
    *(f"client/icons/{asset}" for asset in _ICON_ASSETS),
    *(f"client/native/{asset}" for asset in _NATIVE_ASSETS),
    "client/push/web-push-client.js",
    "client/pwa/install-prompt.js",
)

# Files a server artifact must contain, relative to the artifact root.
SERVER_ARTIFACT_FILES: tuple[str, ...] = (
    "server.py",
    "app.py",
    "index.html",
    *(f"static/{asset}" for asset in (*_CLIENT_ASSETS, "transport-ws.js")),
    *(f"static/icons/{asset}" for asset in _ICON_ASSETS),
)

# Files a transpile artifact must contain, relative to the artifact root. No
# Python and no transport: the generated app module runs on the native runtime,
# which builds its own in-process transport.
TRANSPILE_ARTIFACT_FILES: tuple[str, ...] = (
    "index.html",
    *(f"client/{asset}" for asset in _CLIENT_ASSETS),
    *(f"client/icons/{asset}" for asset in _ICON_ASSETS),
    *(f"client/transpile/{asset}" for asset in _TRANSPILE_ASSETS),
    f"client/transpile/{_TRANSPILE_APP_MODULE}",
    # Native capability tree — the facade (transpile/native.js) routes to it.
    *(f"client/native/{asset}" for asset in _NATIVE_ASSETS),
    "client/push/web-push-client.js",
    "client/pwa/install-prompt.js",
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


def _is_vendored(candidate: Path) -> bool:
    """Tell whether ``candidate`` is a usable vendored module/package.

    A single file counts. A directory counts only if it holds at least one
    bundlable file (anything outside ``__pycache__``) — so a stale directory
    left holding only ``__pycache__`` after the real source was deleted does
    **not** shadow the installed package and silently bundle nothing.

    Args:
        candidate: The ``project_root/module`` path to test.

    Returns:
        ``True`` if the path is a file or a directory with real content.
    """
    if candidate.is_file():
        return True
    if not candidate.is_dir():
        return False
    return any(
        path.is_file() and "__pycache__" not in path.parts
        for path in candidate.rglob("*")
    )


def _resolve_module(module: str, project_root: Path | None) -> tuple[Path, str]:
    """Resolve a ``[wasm].modules`` entry to its ``(root, top)`` for bundling.

    Resolution order:

    1. A **vendored copy** under ``project_root`` (``project_root/module``) that
       carries real content — preserves the historical behavior where a copy
       sitting beside ``app.py`` wins. A stale directory holding only
       ``__pycache__`` is skipped (see :func:`_is_vendored`).
    2. An **installed** package or module on ``sys.path`` (resolved via
       ``importlib``) — so a dependency declared in the project's environment
       (e.g. an ``uv``-managed ``.venv``) is pulled straight from site-packages
       with no vendored copy committed to the repository.

    Args:
        module: The top-level module or package name from ``[wasm].modules``.
        project_root: The project directory, when available.

    Returns:
        A ``(root, top)`` pair where ``root`` is the parent directory archive
        entries are made relative to and ``top`` is the file or directory name
        under it — fed straight into :func:`_zip_tree`.

    Raises:
        BuildError: If the module is neither vendored under ``project_root`` nor
            importable from the current environment.
    """
    if project_root is not None and _is_vendored(project_root / module):
        return project_root, module

    try:
        spec = importlib.util.find_spec(module)
    except (ImportError, ValueError):
        spec = None
    if spec is not None:
        locations = list(spec.submodule_search_locations or ())
        if locations:
            package_dir = Path(locations[0]).resolve()
            return package_dir.parent, module
        if spec.origin and spec.origin not in ("built-in", "frozen"):
            origin = Path(spec.origin).resolve()
            return origin.parent, origin.name

    vendored = f"{project_root / module}" if project_root is not None else "<none>"
    raise BuildError(
        f"wasm module {module!r} not found: no vendored copy at {vendored} "
        f"and not importable from the current environment"
    )


def _zip_package(
    dest: Path,
    *,
    project_root: Path | None = None,
    modules: tuple[str, ...] = (),
) -> None:
    """Zip the Mode A Python payload (tempestweb subset + tempest_core) into ``dest``.

    The archive carries the Mode A subset of ``tempestweb``
    (:data:`_WASM_PACKAGE_PARTS`) and the whole ``tempest_core`` package, excluding
    ``__pycache__``. The Pyodide bootstrap unpacks it into the virtual filesystem's
    working directory (on ``sys.path``), so ``import tempestweb`` and
    ``import tempest_core`` both resolve in the browser. Any project ``modules``
    (files or package directories declared under ``[wasm]``) are bundled too, so
    ``app.py`` can ``import`` them in the browser.

    Args:
        dest: The ``.zip`` path to write.
        project_root: The project directory the ``modules`` are relative to.
            Required when ``modules`` is non-empty.
        modules: Names (files or package dirs) to bundle next to ``app.py``
            (e.g. ``("famacha",)``). Each is resolved by :func:`_resolve_module`:
            a vendored copy under ``project_root`` wins, otherwise the module is
            pulled from the installed environment (site-packages) via importlib —
            so a dependency declared in the project's ``.venv`` need not be
            vendored into the repository.

    Raises:
        BuildError: If an expected package part is missing, or a declared module
            is neither vendored nor importable.
    """
    tempestweb_root = _package_dir().parent
    tempest_core_root = _tempest_core_dir().parent
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as archive:
        _zip_tree(archive, tempestweb_root, "tempestweb", _WASM_PACKAGE_PARTS)
        _zip_tree(archive, tempest_core_root, "tempest_core", None)
        for module in modules:
            root, top = _resolve_module(module, project_root)
            _zip_tree(archive, root, top, None)


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
    # The icon resolver + vendored sets live in an icons/ subdir, imported by
    # dom.js as `./icons/index.js`; preserve that layout next to the flat assets.
    icons_dest = dest / "icons"
    icons_dest.mkdir(parents=True, exist_ok=True)
    for asset in _ICON_ASSETS:
        source = client / "icons" / asset
        if not source.is_file():
            raise BuildError(f"missing icon asset: {source}")
        shutil.copyfile(source, icons_dest / asset)
        written.append(f"icons/{asset}")
    return written


def _copy_client_no_transport(client: Path, dest: Path) -> list[str]:
    """Copy the shared client assets (no transport) plus icons into ``dest``.

    Like :func:`_copy_client` but omits the mode-specific transport file — Mode C
    (transpile) needs no transport, since the native runtime builds its own
    in-process one.

    Args:
        client: The repository's ``client/`` directory.
        dest: The artifact subdirectory to copy assets into.

    Returns:
        The asset filenames that were copied.

    Raises:
        BuildError: If an expected client asset is missing.
    """
    dest.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for asset in _CLIENT_ASSETS:
        source = client / asset
        if not source.is_file():
            raise BuildError(f"missing client asset: {source}")
        shutil.copyfile(source, dest / asset)
        written.append(asset)
    icons_dest = dest / "icons"
    icons_dest.mkdir(parents=True, exist_ok=True)
    for asset in _ICON_ASSETS:
        source = client / "icons" / asset
        if not source.is_file():
            raise BuildError(f"missing icon asset: {source}")
        shutil.copyfile(source, icons_dest / asset)
        written.append(f"icons/{asset}")
    return written


def _index_html(name: str, scripts: tuple[str, ...] = ()) -> str:
    """Render the static ``index.html`` shell for a wasm artifact.

    Args:
        name: The project name (page title).
        scripts: URLs/paths injected as classic ``<script>`` tags in ``<head>``
            before the bootstrap module, so a global library (e.g. ``window.ort``
            from onnxruntime-web) is loaded and ready when Python boots.

    Returns:
        The HTML document that boots the app in the browser.
    """
    script_tags = "".join(f'\n    <script src="{src}"></script>' for src in scripts)
    return f"""\
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{name}</title>
    <link rel="manifest" href="./manifest.webmanifest" />
    <meta name="theme-color" content="#111111" />
    <link rel="apple-touch-icon" href="./icons/apple-touch-icon.png" />{script_tags}
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


def _bootstrap_js(name: str, pyodide_base: str, packages: tuple[str, ...] = ()) -> str:
    """Render the live wasm bootstrap entrypoint (Mode A, Pyodide).

    The emitted module loads Pyodide + ``pydantic`` from ``pyodide_base``, unpacks
    the zipped ``tempestweb`` package and writes ``app.py`` into the Pyodide
    virtual filesystem, builds the app in-process via
    :func:`tempestweb.runtime.wasm_main.bootstrap`, and mounts the shared client
    onto ``#app`` through ``transport-wasm.js`` — Python runs in the same tab, so
    the transport is an in-process bridge with no network.

    Args:
        name: The project name.
        pyodide_base: The base URL Pyodide is loaded from — the jsdelivr CDN by
            default, or the artifact-relative ``"./pyodide/"`` for an offline
            build (vendored runtime + wheels, precached by the service worker).
        packages: Extra Pyodide packages to ``loadPackage`` alongside the core's
            own ``pydantic`` (e.g. ``("numpy", "pillow")``), declared under
            ``[wasm]``.

    Returns:
        The bootstrap module source.
    """
    package_list_js = json.dumps(["pydantic", *packages])
    return f"""\
// bootstrap.js — live wasm artifact entrypoint for "{name}" (Mode A, Pyodide).
//
// Loads Pyodide + pydantic, installs the tempestweb package and app.py into the
// Pyodide virtual FS, builds the app in-process and mounts the shared client.
import {{ mount }} from "./client/tempestweb.js";
import {{ createWasmTransport }} from "./client/transport-wasm.js";
import {{ installNativeBridge }} from "./client/native/index.js";

const PYODIDE_BASE = "{pyodide_base}";

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

  // 1. Load Pyodide + the configured packages (pydantic is the core's only hard
  //    dependency; a project's [wasm] packages — e.g. numpy/pillow — join here).
  const {{ loadPyodide }} = await import(PYODIDE_BASE + "pyodide.mjs");
  const pyodide = await loadPyodide({{ indexURL: PYODIDE_BASE }});
  await pyodide.loadPackage({package_list_js});

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
    offline: bool = False,
) -> BuildResult:
    """Build a deployable artifact for ``mode`` from a project.

    Args:
        project_root: The project directory (must contain the entrypoint).
        mode: ``"wasm"`` or ``"server"``. Defaults to the project config's mode.
        out_dir: Where to write the artifact. Defaults to
            ``<project_root>/dist/<mode>``.
        clean: When ``True`` (default), remove an existing ``out_dir`` first.
        offline: When ``True`` (wasm only), vendor the Pyodide runtime + package
            wheels into the artifact so it boots fully offline (the service worker
            precaches them). Requires network *at build time* to download them.
            Ignored for server mode.

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
        files = _build_wasm(
            out,
            client,
            config.name,
            app_source,
            offline=offline,
            project_root=config.root,
            wasm=config.wasm,
        )
    elif resolved_mode == "transpile":
        files = _build_transpile(
            out, client, config.name, app_source, config.entrypoint_path.name
        )
    else:
        files = _build_server(out, client, config.name, app_source)

    return BuildResult(mode=resolved_mode, out_dir=out, files=files)


def _copy_assets(project_root: Path, out: Path, patterns: tuple[str, ...]) -> list[str]:
    """Copy declared static assets into the artifact, preserving relative paths.

    Each pattern is a project-relative glob (e.g. ``"models/*.onnx"``); every
    matching file is copied to the same relative path under ``out``. Used to
    bundle ONNX models and a vendored JS library into a Mode A artifact.

    Args:
        project_root: The project directory the patterns are relative to.
        out: The artifact root.
        patterns: Project-relative glob patterns.

    Returns:
        The artifact-relative POSIX paths written, sorted, deduplicated.

    Raises:
        BuildError: If a pattern matches no files (a likely typo).
    """
    written: set[str] = set()
    for pattern in patterns:
        matches = [p for p in sorted(project_root.glob(pattern)) if p.is_file()]
        if not matches:
            raise BuildError(f"wasm asset pattern matched no files: {pattern!r}")
        for source in matches:
            rel = source.relative_to(project_root).as_posix()
            dest = out / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
            written.add(rel)
    return sorted(written)


def _build_wasm(
    out: Path,
    client: Path,
    name: str,
    app_source: str,
    *,
    offline: bool = False,
    project_root: Path | None = None,
    wasm: WasmConfig | None = None,
) -> tuple[str, ...]:
    """Write the wasm (static) artifact layout into ``out``.

    Args:
        out: The artifact root.
        client: The shared ``client/`` directory.
        name: The project name.
        app_source: The project's ``app.py`` source to embed.
        offline: When ``True``, vendor the Pyodide runtime + package wheels under
            ``out/pyodide/``, point the bootstrap at that local copy, and precache
            it so the app boots offline after the first load.
        project_root: The project directory (source of ``[wasm]`` modules/assets).
        wasm: The project's ``[wasm]`` extras (packages, modules, assets, scripts).

    Returns:
        The artifact-relative paths written, sorted.
    """
    wasm = wasm or WasmConfig()
    extra_packages = tuple(wasm.packages)
    modules = tuple(wasm.modules)
    scripts = tuple(wasm.scripts)

    # Offline: vendor Pyodide same-origin so the service worker can precache it;
    # otherwise the bootstrap loads it from the (cross-origin) jsdelivr CDN. The
    # project's extra packages (numpy/pillow) join the vendored closure.
    vendored: list[str] = []
    if offline:
        vendored = vendor_pyodide(
            out / "pyodide",
            version=WASM_PYODIDE_VERSION,
            packages=(*WASM_RUNTIME_PACKAGES, *extra_packages),
        )
        pyodide_base = "./pyodide/"
    else:
        pyodide_base = pyodide_cdn_base(WASM_PYODIDE_VERSION)

    (out / "index.html").write_text(_index_html(name, scripts), encoding="utf-8")
    (out / "bootstrap.js").write_text(
        _bootstrap_js(name, pyodide_base, extra_packages), encoding="utf-8"
    )
    (out / "app.py").write_text(app_source, encoding="utf-8")
    _zip_package(out / WASM_PACKAGE_ARCHIVE, project_root=project_root, modules=modules)
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
    # The install capability imports the soft install-prompt controller.
    install_source = client / "pwa" / "install-prompt.js"
    if not install_source.is_file():
        raise BuildError(f"missing pwa asset: {install_source}")
    pwa_dest = out / "client" / "pwa"
    pwa_dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(install_source, pwa_dest / "install-prompt.js")
    # Project static assets (ONNX models, vendored JS libs) copied verbatim,
    # preserving their relative path, and precached for the offline second load.
    assets: list[str] = []
    if project_root is not None and wasm.assets:
        assets = _copy_assets(project_root, out, tuple(wasm.assets))
    # Artifact-relative scripts (not external URLs) are part of the shell too.
    local_scripts = [
        s.lstrip(".") if s.startswith("./") else s
        for s in scripts
        if not s.startswith(("http://", "https://"))
    ]
    # App-shell the service worker precaches for an offline second load. With an
    # offline build the vendored Pyodide runtime + wheels are same-origin and join
    # the precache, so the app boots with no network at all; a CDN build precaches
    # only the local shell + package payload (Pyodide stays cross-origin).
    precache = (
        "/",
        "/index.html",
        "/manifest.webmanifest",
        "/bootstrap.js",
        "/register.js",
        "/app.py",
        f"/{WASM_PACKAGE_ARCHIVE}",
        *(f"/client/{asset}" for asset in (*_CLIENT_ASSETS, "transport-wasm.js")),
        *(f"/{asset}" for asset in assets),
        *(s if s.startswith("/") else f"/{s}" for s in local_scripts),
        *(f"/pyodide/{file_name}" for file_name in vendored),
    )
    _build_pwa(out, client, name, precache)
    return tuple(
        sorted(
            [
                *WASM_ARTIFACT_FILES,
                *assets,
                *(f"pyodide/{f}" for f in vendored),
            ]
        )
    )


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


def _index_html_transpile(name: str) -> str:
    """Render the ``index.html`` shell for a transpile artifact (Mode C).

    The shell imports the native runtime and the generated app module and mounts
    the app with :func:`mountApp` — no transport, no Python, no network. The app
    runs entirely as native JavaScript in the tab.

    Args:
        name: The project name (page title).

    Returns:
        The HTML document that boots the transpiled app in the browser.
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
      import {{ mountApp }} from "./client/transpile/runtime.js";
      import {{ makeState, view }} from "./client/transpile/{_TRANSPILE_APP_MODULE}";

      mountApp(document.getElementById("app"), {{ makeState, view }});
    </script>
  </body>
</html>
"""


def _build_transpile(
    out: Path, client: Path, name: str, app_source: str, entry_name: str
) -> tuple[str, ...]:
    """Write the transpile (native-JS static) artifact layout into ``out`` (Mode C).

    Transcribes the project's Python app layer to a native ES module and copies
    the shared client plus the native runtime (diff/widgets/runtime) into
    ``client/transpile/``. The result is a fully static bundle — zero Python at
    runtime — servable by any host/CDN.

    Args:
        out: The artifact root.
        client: The shared ``client/`` directory.
        name: The project name.
        app_source: The project's entrypoint source to transpile.
        entry_name: The entrypoint file name (for the generated banner).

    Returns:
        The artifact-relative paths written, sorted.

    Raises:
        BuildError: If the app source falls outside the transpilable subset or a
            required client/transpile asset is missing.
    """
    from tempestweb.transpile import TranspileError, transpile_source

    banner = (
        f"// {_TRANSPILE_APP_MODULE} — GENERATED from {entry_name} "
        "by tempestweb transpile (Mode C). Do not edit."
    )
    try:
        generated = transpile_source(app_source, filename=entry_name, banner=banner)
    except TranspileError as exc:
        raise BuildError(f"transpile failed: {exc}") from exc

    # Shared client assets (the leaf renderer) with no transport — the native
    # runtime supplies its own in-process transport.
    written = _copy_client_no_transport(client, out / "client")

    # The native runtime trio + the generated app module under client/transpile/.
    transpile_src = client / "transpile"
    transpile_dest = out / "client" / "transpile"
    transpile_dest.mkdir(parents=True, exist_ok=True)
    for asset in _TRANSPILE_ASSETS:
        source = transpile_src / asset
        if not source.is_file():
            raise BuildError(f"missing transpile asset: {source}")
        shutil.copyfile(source, transpile_dest / asset)
        written.append(f"transpile/{asset}")
    (transpile_dest / _TRANSPILE_APP_MODULE).write_text(generated, encoding="utf-8")
    written.append(f"transpile/{_TRANSPILE_APP_MODULE}")

    # Native capability tree — the transpile/native.js facade routes to it. Shipped
    # alongside so `await native.http.request(...)` etc. resolve in the browser.
    native_dest = out / "client" / "native"
    native_dest.mkdir(parents=True, exist_ok=True)
    for asset in _NATIVE_ASSETS:
        source = client / "native" / asset
        if not source.is_file():
            raise BuildError(f"missing native asset: {source}")
        shutil.copyfile(source, native_dest / asset)
    for rel in ("push/web-push-client.js", "pwa/install-prompt.js"):
        source = client / rel
        if not source.is_file():
            raise BuildError(f"missing native dependency: {source}")
        dest = out / "client" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)

    (out / "index.html").write_text(_index_html_transpile(name), encoding="utf-8")
    return tuple(sorted(TRANSPILE_ARTIFACT_FILES))
