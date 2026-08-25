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
    IconSpec,
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
    "layouts.js",
    "events.js",
    "focus.js",
    "gestures.js",
    "lists.js",
    "media.js",
    "pages.js",
    "transport.js",
    "virtualize.js",
    "router.js",
    "camera-widgets.js",
    "constants.js",
)

# Mode C (transpile) native-runtime modules (client/transpile/*.js): the diff,
# the IR widget builders, and the State/App runtime. Copied into a transpile/
# subdir of the artifact's client/, next to the generated app module.
_TRANSPILE_ASSETS: tuple[str, ...] = (
    "runtime.js",
    "widgets.js",
    "widgets.gen.js",
    "values.gen.js",
    "widget-support.js",
    "components.js",
    "component-styles.gen.js",
    "spacing.gen.js",
    "diff.js",
    "widget-styles.gen.js",
    "native.js",
    "validators.js",
    "nav.js",
    "i18n.js",
    "theme.js",
    "motion.js",
    "animation.js",
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

# Native capability bridge modules (client/native/*.js), copied into every
# artifact that mounts the client so ``native/index.js`` — which the WebSocket
# transport and the wasm bootstrap both import — resolves its full closure. This
# list MUST cover every module ``native/index.js`` imports; a stale subset 404s
# in the browser and the whole app fails to mount. ``test_native_assets_cover_
# index_imports`` keeps it exhaustive.
_NATIVE_ASSETS: tuple[str, ...] = (
    "audio.js",
    "badge.js",
    "battery.js",
    "bgsync.js",
    "bluetooth.js",
    "camera.js",
    "clipboard.js",
    "contacts.js",
    "cookies.js",
    "eyedropper.js",
    "file.js",
    "filesystem.js",
    "fullscreen.js",
    "gamepad.js",
    "geolocation.js",
    "hid.js",
    "http.js",
    "idb-kv.js",
    "idle.js",
    "index.js",
    "install.js",
    "midi.js",
    "network.js",
    "nfc.js",
    "notifications.js",
    "offline.js",
    "onnx.js",
    "orientation.js",
    "payment.js",
    "pip.js",
    "pointerlock.js",
    "quota.js",
    "recorder.js",
    "sensors.js",
    "serial.js",
    "share.js",
    "speech.js",
    "storage.js",
    "sync.js",
    "tabs.js",
    "usb.js",
    "vibration.js",
    "visibility.js",
    "wakelock.js",
    "webaudio.js",
    "webauthn.js",
)
# Offline client modules shipped under client/offline/. store.js + sync.js back
# native/offline.js's imports; pull.js (read-side delta-sync), sync-status.js
# (sync store + controller), sw-bridge.js (SW->page routing) and asset-cache.js
# (large-binary caching) are opt-in modules an app imports directly.
_OFFLINE_ASSETS: tuple[str, ...] = (
    "store.js",
    "sync.js",
    "pull.js",
    "sync-status.js",
    "sw-bridge.js",
    "asset-cache.js",
)

# Subpackages of ``tempestweb`` the Mode A runtime needs in the browser. The
# server/CLI/devserver stacks (and their Starlette/uvicorn deps) are omitted —
# Pyodide neither has them nor needs them to run ``view()`` in the tab. The
# renderer-agnostic core lives in the separate ``tempest_core`` package, bundled
# alongside (see :func:`_zip_package`).
_WASM_PACKAGE_PARTS: tuple[str, ...] = (
    "__init__.py",
    # Shared constants (SSE/native-call defaults) the runtime and native layers
    # import. Left out, the artifact booted as far as `import app` and then died
    # on `No module named 'tempestweb.core'` — a browser-only failure no Python
    # test could see, since the test process has the whole package installed.
    "core",
    "runtime",
    "transports",
    "native",
    "components",
    # The theme → CSS emitter. Mode B puts those custom properties in the page
    # head at render time; Mode A's page is static, so the app's palette can only
    # reach the sheet from inside the browser — which means this module has to be
    # in the bundle. Pure Python over the core's tokens, no extra dependency.
    "html",
)

#: The single icon a Mode B artifact emits, purely so the tab has a favicon (the
#: server artifact is not a PWA: no manifest, no service worker). It sits beside
#: the client rather than under ``static/icons/``, which holds the *icon widget's*
#: JS modules.
_SERVER_FAVICON: IconSpec = IconSpec("favicon.png", 192)

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
    *(f"client/offline/{asset}" for asset in _OFFLINE_ASSETS),
    "client/push/web-push-client.js",
    "client/pwa/install-prompt.js",
    "client/pwa/connectivity-banner.js",
    "client/pwa/post-install-redirect.js",
)

# Files a server artifact must contain, relative to the artifact root. Both Mode
# B transports ship: the shell mounts the WebSocket one, and transport-sse.js
# covers the /sse routes the same host serves. Each imports ``native/index.js``,
# which eagerly loads the whole native tree (+ offline queue, push and the
# install prompt), so the server artifact must ship the same client closure the
# wasm artifact does — otherwise the browser 404s on those modules and the app
# never mounts.
SERVER_ARTIFACT_FILES: tuple[str, ...] = (
    "server.py",
    "app.py",
    "index.html",
    *(
        f"static/{asset}"
        for asset in (*_CLIENT_ASSETS, "transport-ws.js", "transport-sse.js")
    ),
    *(f"static/icons/{asset}" for asset in _ICON_ASSETS),
    *(f"static/native/{asset}" for asset in _NATIVE_ASSETS),
    *(f"static/offline/{asset}" for asset in _OFFLINE_ASSETS),
    "static/push/web-push-client.js",
    "static/pwa/install-prompt.js",
    "static/pwa/connectivity-banner.js",
    "static/pwa/post-install-redirect.js",
    "static/favicon.png",
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
    *(f"client/offline/{asset}" for asset in _OFFLINE_ASSETS),
    "client/push/web-push-client.js",
    "client/pwa/install-prompt.js",
    "client/pwa/update-prompt.js",
    "client/pwa/connectivity-banner.js",
    "client/pwa/post-install-redirect.js",
    # PWA layer: manifest, service worker + registration, icons. Mode C is a
    # first-class installable, offline-capable PWA (static bundle).
    *_PWA_FILES,
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


def _manifest_options(config: ProjectConfig) -> ManifestOptions:
    """Build the manifest options from a project's ``[pwa]`` config.

    Unset ``[pwa]`` names fall back to the project name (full and trimmed), so a
    project with no ``[pwa]`` section still gets a sensibly-named installable
    manifest.

    Args:
        config: The resolved project config.

    Returns:
        The :class:`ManifestOptions` to emit for this project.
    """
    pwa = config.pwa
    name = pwa.name or config.name
    return ManifestOptions(
        name=name,
        short_name=pwa.short_name or name[:12],
        description=pwa.description or f"{name} — a tempestweb app.",
        theme_color=pwa.theme_color,
        background_color=pwa.background_color,
        display=pwa.display,
        orientation=pwa.orientation,
        lang=pwa.lang,
        categories=list(pwa.categories),
    )


#: The worker's imports, as written in the repo → as the artifact needs them. The
#: source lives at ``client/sw/sw.js`` and imports its siblings relatively so the
#: node tests load it unchanged; the emitted worker sits at the artifact root with
#: the client under ``./client/``, so the same specifiers have to move up a level.
#: A static specifier cannot be computed at runtime, and a service worker may not
#: use a dynamic ``import()`` at all — the spec forbids it on
#: ServiceWorkerGlobalScope (tempestweb#118) — so the rewrite happens here.
_SW_IMPORT_REWRITES: tuple[tuple[str, str], ...] = (
    ('from "../offline/store.js"', 'from "./client/offline/store.js"'),
    ('from "../offline/sync.js"', 'from "./client/offline/sync.js"'),
)


def _rewrite_sw_imports(source: str) -> str:
    """Point the worker's static imports at the artifact's client directory.

    Args:
        source: The ``client/sw/sw.js`` source, with repo-relative specifiers.

    Returns:
        The same source with every specifier rewritten for the artifact layout.

    Raises:
        BuildError: If a specifier is missing — the worker's imports moved and the
            emitted worker would fail to load its queue modules at runtime.
    """
    for repo_specifier, artifact_specifier in _SW_IMPORT_REWRITES:
        if repo_specifier not in source:
            raise BuildError(
                f"service worker no longer imports {repo_specifier} — the rewrite "
                "table _SW_IMPORT_REWRITES is stale, and the emitted worker would "
                "fail to load its queue modules"
            )
        source = source.replace(repo_specifier, artifact_specifier)
    return source


def _build_pwa(
    out: Path,
    client: Path,
    manifest: ManifestOptions,
    precache: tuple[str, ...],
    *,
    with_manifest: bool = True,
    with_service_worker: bool = True,
) -> None:
    """Emit the PWA layer (manifest + icons + service worker) into ``out``.

    Writes ``manifest.webmanifest`` and the icon set, then copies the shared
    service worker with its build-time placeholders filled: ``__CACHE_VERSION__``
    becomes a content hash of the precache list and ``"__PRECACHE_MANIFEST__"``
    becomes the JSON app-shell list the worker caches on install. ``register.js``
    is copied verbatim for the page to register the worker.

    Each half can be turned off from ``[pwa]``. Icons are emitted either way —
    the shell links them as favicon and apple-touch-icon whether or not a
    manifest exists.

    Turning the worker off still writes ``sw.js``, but the teardown worker
    (``client/sw/sw-teardown.js``) instead of the caching one. Emitting nothing
    would leave every browser that already registered the caching worker serving
    the app shell from a precache the deploy has moved past, with no way to
    reach them; a worker that clears its caches and unregisters itself retires
    the old one on their next visit.

    Args:
        out: The artifact root.
        client: The shared ``client/`` directory.
        manifest: The manifest options (name, colors, display) to emit.
        precache: The app-shell URLs the service worker precaches (cache-first).
        with_manifest: Whether to write ``manifest.webmanifest``.
        with_service_worker: Whether to emit the caching worker + ``register.js``.
            When ``False``, ``sw.js`` is the teardown worker and no
            ``register.js`` is written.

    Raises:
        BuildError: If a service worker source is missing.
    """
    if with_manifest:
        write_manifest(out / "manifest.webmanifest", manifest)
    emit_icons(out / "icons")

    if not with_service_worker:
        teardown_source = client / "sw" / "sw-teardown.js"
        if not teardown_source.is_file():
            raise BuildError(f"missing service worker source: {teardown_source}")
        shutil.copyfile(teardown_source, out / "sw.js")
        return

    sw_source = client / "sw" / "sw.js"
    register_source = client / "sw" / "register.js"
    if not sw_source.is_file() or not register_source.is_file():
        raise BuildError(f"missing service worker sources under {client / 'sw'}")

    version = "tw-" + hashlib.sha1("|".join(precache).encode("utf-8")).hexdigest()[:12]
    sw = _rewrite_sw_imports(sw_source.read_text(encoding="utf-8"))
    sw = sw.replace("__CACHE_VERSION__", version)
    # Replace the quoted placeholder with a JS string literal carrying the JSON
    # array, so the worker's ``JSON.parse(injected)`` yields the app-shell list.
    sw = sw.replace('"__PRECACHE_MANIFEST__"', json.dumps(json.dumps(list(precache))))
    (out / "sw.js").write_text(sw, encoding="utf-8")
    shutil.copyfile(register_source, out / "register.js")


def _copy_offline(client: Path, out: Path) -> None:
    """Copy the offline-queue client modules into ``out/client/offline/``.

    ``client/native/offline.js`` imports ``../offline/{store,sync}.js``, so any
    artifact that ships the native tree (its ``index.js`` eagerly loads
    ``offline.js``) must ship these too.

    Args:
        out: The artifact root.
        client: The shared ``client/`` directory.

    Raises:
        BuildError: If an offline module is missing.
    """
    offline_dest = out / "client" / "offline"
    offline_dest.mkdir(parents=True, exist_ok=True)
    for asset in _OFFLINE_ASSETS:
        source = client / "offline" / asset
        if not source.is_file():
            raise BuildError(f"missing offline asset: {source}")
        shutil.copyfile(source, offline_dest / asset)


def _copy_client_extras(client: Path, base: Path) -> None:
    """Copy the native-bridge closure into an artifact's client base dir.

    ``native/index.js`` — imported by both the wasm bootstrap and the WebSocket
    transport — eagerly loads the entire native tree, which in turn pulls in the
    offline queue (``../offline/{store,sync}.js``), the WebPush client
    (``../push/web-push-client.js``) and the install prompt
    (``../pwa/install-prompt.js``). The connectivity banner
    (``../pwa/connectivity-banner.js``), which the shell mounts and which itself
    imports ``../native/network.js``, ships alongside them. Every artifact that
    mounts the client must ship all of them under the same base (``client/`` for
    wasm, ``static/`` for server), or the browser 404s mid-module-load and the
    app never mounts.

    Args:
        client: The shared ``client/`` directory.
        base: The artifact's client base dir (e.g. ``out/client`` or
            ``out/static``).

    Raises:
        BuildError: If any expected module is missing from the source tree.
    """
    native_dest = base / "native"
    native_dest.mkdir(parents=True, exist_ok=True)
    for asset in _NATIVE_ASSETS:
        source = client / "native" / asset
        if not source.is_file():
            raise BuildError(f"missing native asset: {source}")
        shutil.copyfile(source, native_dest / asset)

    offline_dest = base / "offline"
    offline_dest.mkdir(parents=True, exist_ok=True)
    for asset in _OFFLINE_ASSETS:
        source = client / "offline" / asset
        if not source.is_file():
            raise BuildError(f"missing offline asset: {source}")
        shutil.copyfile(source, offline_dest / asset)

    push_source = client / "push" / "web-push-client.js"
    if not push_source.is_file():
        raise BuildError(f"missing push asset: {push_source}")
    push_dest = base / "push"
    push_dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(push_source, push_dest / "web-push-client.js")

    pwa_dest = base / "pwa"
    pwa_dest.mkdir(parents=True, exist_ok=True)
    for pwa_asset in (
        "install-prompt.js",
        "connectivity-banner.js",
        "post-install-redirect.js",
    ):
        pwa_source = client / "pwa" / pwa_asset
        if not pwa_source.is_file():
            raise BuildError(f"missing pwa asset: {pwa_source}")
        shutil.copyfile(pwa_source, pwa_dest / pwa_asset)


def _copy_client(client: Path, dest: Path, *transports: str) -> list[str]:
    """Copy the shared client assets plus the mode's transports into ``dest``.

    The icon resolver and its vendored sets live in an ``icons/`` subdir, imported
    by ``dom.js`` as ``./icons/index.js``; that layout is preserved next to the
    flat assets.

    Args:
        client: The repository's ``client/`` directory.
        dest: The artifact subdirectory to copy assets into.
        *transports: The transport filenames the mode can mount (e.g.
            ``transport-wasm.js``). A mode may ship more than one — a server
            artifact carries both ``transport-ws.js`` and ``transport-sse.js``,
            since its host answers on ``/ws`` and ``/sse`` alike.

    Returns:
        The asset filenames that were copied.

    Raises:
        BuildError: If an expected client asset is missing.
    """
    dest.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for asset in (*_CLIENT_ASSETS, *transports):
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


# Dev-mode cache kill-switch injected instead of the caching service worker.
# `tempestweb dev` must always serve the freshly rebuilt bundle, so it unregisters
# any service worker, drops every cache, and reloads once if a worker was
# controlling the page (guarded by a sessionStorage flag against reload loops).
# Production builds (`run` / `build` / `deploy`) keep the caching SW for speed.
_DEV_CACHE_KILL_SWITCH = """\
    <script type="module">
      // Dev: never serve stale. Kill any service worker + caches, then reload
      // once if a worker was controlling this page so the fresh bundle shows up.
      (async () => {
        let hadController = false;
        if ("serviceWorker" in navigator) {
          hadController = Boolean(navigator.serviceWorker.controller);
          const regs = await navigator.serviceWorker.getRegistrations();
          await Promise.all(regs.map((r) => r.unregister()));
        }
        if (self.caches) {
          const keys = await caches.keys();
          await Promise.all(keys.map((k) => caches.delete(k)));
        }
        if (hadController && !sessionStorage.getItem("tw-dev-sw-cleared")) {
          sessionStorage.setItem("tw-dev-sw-cleared", "1");
          location.reload();
        }
      })();
    </script>"""

# Production service-worker registration for the wasm shell.
_WASM_SW_REGISTER = """\
    <script type="module">
      import { registerServiceWorker } from "./register.js";
      import { mountConnectivityBanner } from "./client/pwa/connectivity-banner.js";
      mountConnectivityBanner();
      if ("serviceWorker" in navigator) {
        registerServiceWorker({ url: "/sw.js" });
      }
    </script>"""

# Production service-worker registration for the transpile (Mode C) shell.
_TRANSPILE_SW_REGISTER = """\
    <script type="module">
      import { registerServiceWorker } from "./register.js";
      import { showUpdatePrompt } from "./client/pwa/update-prompt.js";
      import { mountConnectivityBanner } from "./client/pwa/connectivity-banner.js";
      mountConnectivityBanner();
      if ("serviceWorker" in navigator) {
        registerServiceWorker({
          url: "./sw.js",
          onUpdate: (registration) => showUpdatePrompt(registration),
        });
      }
    </script>"""

# What the shell keeps when ``[pwa] service_worker = false``: the connectivity
# banner is about the network, not about precaching, so an app that opts out of
# the worker still tells the user when it goes offline.
_NO_SW_REGISTER = """\
    <script type="module">
      import { mountConnectivityBanner } from "./client/pwa/connectivity-banner.js";
      mountConnectivityBanner();
    </script>"""


def _manifest_link(with_manifest: bool) -> str:
    """The manifest ``<link>`` line for a shell, or nothing when it is off.

    Args:
        with_manifest: Whether the build emits ``manifest.webmanifest``.

    Returns:
        The link tag with its trailing newline, or ``""`` — linking a manifest a
        build did not write is a 404 on every load.
    """
    if not with_manifest:
        return ""
    return '    <link rel="manifest" href="./manifest.webmanifest" />\n'


def _index_html(
    name: str,
    scripts: tuple[str, ...] = (),
    theme_color: str = "#111111",
    *,
    dev: bool = False,
    with_manifest: bool = True,
    with_service_worker: bool = True,
) -> str:
    """Render the static ``index.html`` shell for a wasm artifact.

    Args:
        name: The project name (page title).
        scripts: URLs/paths injected as classic ``<script>`` tags in ``<head>``
            before the bootstrap module, so a global library (e.g. ``window.ort``
            from onnxruntime-web) is loaded and ready when Python boots.
        theme_color: The manifest theme color, mirrored into the ``theme-color``
            meta so the browser chrome matches the installed app.
        dev: When ``True`` (the ``tempestweb dev`` loop), inject the cache
            kill-switch instead of registering the caching service worker, so
            every reload serves the freshly rebuilt bundle.
        with_manifest: Whether the build emits a manifest to link.
        with_service_worker: Whether the shell registers the caching worker. When
            ``False`` the connectivity banner still mounts — it reports the
            network, not the precache.

    Returns:
        The HTML document that boots the app in the browser.
    """
    script_tags = "".join(f'\n    <script src="{src}"></script>' for src in scripts)
    if dev:
        sw_block = _DEV_CACHE_KILL_SWITCH
    elif with_service_worker:
        sw_block = _WASM_SW_REGISTER
    else:
        sw_block = _NO_SW_REGISTER
    return f"""\
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{name}</title>
{_manifest_link(with_manifest)}\
    <meta name="theme-color" content="{theme_color}" />
    <link rel="icon" href="./icons/icon-192.png" />
    <link rel="apple-touch-icon" href="./icons/apple-touch-icon.png" />{script_tags}
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="./bootstrap.js"></script>
{sw_block}
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

    The emitted module also wires ``onTheme``, which marks the document with the
    app's resolved theme mode. That is the theme's other half: the colours ride in
    each widget's inline style, but the page, the field surfaces and the
    hover/focus states are CSS, so the base sheet needs the mode on the document
    to pick its token block.

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
import {{ applyThemeMode }} from "./client/theme.js";

const PYODIDE_BASE = "{pyodide_base}";

// Python entry: build the app and hand back a _start(on_patches, dispatch) hook.
// `app.THEME` is optional: an app that declares one gets its palette into the
// tree (components resolve their colours in Python) and into the page (the CSS
// tokens the base sheet reads).
const PY_GLUE = `
import app
from tempestweb.runtime.wasm_main import bootstrap

def _start(on_patches, dispatch, on_navigate, on_theme, subscribe, unsubscribe):
    return bootstrap(
        app.make_state(), app.view, on_patches, dispatch, on_navigate,
        subscribe, unsubscribe, getattr(app, "THEME", None), on_theme=on_theme,
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
  //    A batch delivered before the transport exists is BUFFERED, never dropped:
  //    Python starts its rebuild loop inside start(), so a batch that lands in
  //    the gap used to vanish with no error, and the mounted tree silently missed
  //    whatever it carried (tempestweb#160).
  let deliverToTransport = null;
  const bootPatches = [];
  const onPatches = (patchesJson) => {{
    const patches = JSON.parse(patchesJson);
    if (deliverToTransport) {{
      deliverToTransport(patches);
    }} else {{
      bootPatches.push(patches);
    }}
  }};
  // View -> URL: push the new path when the app navigates (no popstate fires, so
  // no loop with the router's URL -> view reporting).
  const onNavigate = (path) => {{
    if (path && location.pathname !== path) {{
      history.pushState({{}}, "", path);
    }}
  }};
  const onTheme = (mode) => applyThemeMode(mode);

  // Native capabilities (geolocation/clipboard/http/…): expose the in-process
  // dispatch on window, and bridge it to Python as a JSON-string seam (so the
  // envelope crosses the FFI cleanly, no proxy conversion).
  //    Streaming capabilities (geolocation.watch, sensors.*, …) travel the same
  //    seam through the subscribe/unsubscribe pair. Both wrappers are `async` on
  //    purpose: the underlying calls are synchronous, and Python awaits whatever
  //    comes back — an async function hands it a promise instead of `undefined`.
  //    The `emit` argument is a BORROWED PyProxy: Pyodide destroys it when the
  //    async call returns, and a subscription emits long after that ("This
  //    borrowed proxy was automatically destroyed" on the first event). So copy
  //    it into a proxy this glue owns, keyed by sub_id, and destroy that copy on
  //    unsubscribe — otherwise every watch() leaks a proxy per subscription.
  installNativeBridge(globalThis);
  const onNative = async (envelopeJson) => {{
    const result = await globalThis.__tempestweb_native__(JSON.parse(envelopeJson));
    return JSON.stringify(result);
  }};
  const emitProxies = new Map();
  const onNativeSubscribe = async (envelopeJson, emit) => {{
    const persistent = typeof emit.copy === "function" ? emit.copy() : emit;
    emitProxies.set(JSON.parse(envelopeJson).sub_id, persistent);
    globalThis.__tempestweb_native_subscribe__(envelopeJson, persistent);
  }};
  const onNativeUnsubscribe = async (subId) => {{
    globalThis.__tempestweb_native_unsubscribe__(subId);
    const persistent = emitProxies.get(subId);
    emitProxies.delete(subId);
    if (persistent && typeof persistent.destroy === "function") {{
      persistent.destroy();
    }}
  }};

  const handle = start(
    onPatches,
    onNative,
    onNavigate,
    onTheme,
    onNativeSubscribe,
    onNativeUnsubscribe,
  );

  const bridge = {{
    onDeliver(handler) {{
      deliverToTransport = handler;
      while (bootPatches.length > 0) {{
        deliverToTransport(bootPatches.shift());
      }}
    }},
    pushEvent(event) {{
      handle.push_event_json(JSON.stringify(event));
    }},
    close() {{
      handle.close();
    }},
  }};

  // The app's palette, as the `--tw-*` tokens the base sheet reads. Injected
  // before the mount so the first paint is already themed — Mode B puts these in
  // the page head at render time, but this page is static and the app only exists
  // once Pyodide is up. Empty when the app declares no THEME.
  const themeCss = handle.theme_css();
  if (themeCss) {{
    const style = document.createElement("style");
    style.id = "tw-app-theme";
    style.textContent = themeCss;
    document.head.appendChild(style);
  }}

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
    <link rel="icon" href="./static/favicon.png" />
  </head>
  <body>
    <div id="app"></div>
    <script type="module">
      import {{ mount }} from "./static/tempestweb.js";
      import {{ createWebSocketTransport }} from "./static/transport-ws.js";
      import {{ mountConnectivityBanner }} from "./static/pwa/connectivity-banner.js";

      mountConnectivityBanner();
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

from fastapi import FastAPI, Response
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
    api = create_app(
        _project.make_state,
        _project.view,
        title="{name}",
        # Optional: an app that declares a palette gets it into every component
        # (they resolve colours in Python) and into the page's CSS tokens.
        theme=getattr(_project, "THEME", None),
    )
    api.mount(
        "/static",
        StaticFiles(directory=str(_HERE / "static")),
        name="static",
    )

    @api.get("/")
    async def index() -> FileResponse:
        """Serve the app shell that mounts the client over WebSocket."""
        return FileResponse(str(_HERE / "index.html"))

    @api.get("/favicon.ico")
    async def favicon() -> Response:
        """Answer the browser's default favicon probe (avoids a noisy 404)."""
        return Response(status_code=204)

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
    dev: bool = False,
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
        dev: When ``True`` (the ``tempestweb dev`` loop), the wasm/transpile shell
            skips the caching service worker and injects a cache kill-switch, so
            every reload serves the freshly rebuilt bundle. Production builds
            (``run`` / ``build`` / ``deploy``) leave it ``False`` and keep the
            caching SW for fast repeat loads.

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
    manifest = _manifest_options(config)

    if resolved_mode == "wasm":
        files = _build_wasm(
            out,
            client,
            config.name,
            app_source,
            offline=offline,
            project_root=config.root,
            wasm=config.wasm,
            manifest=manifest,
            dev=dev,
            with_manifest=config.pwa.manifest,
            with_service_worker=config.pwa.service_worker,
        )
    elif resolved_mode == "transpile":
        files = _build_transpile(
            out,
            client,
            config.name,
            app_source,
            config.entrypoint_path.name,
            manifest=manifest,
            dev=dev,
            with_manifest=config.pwa.manifest,
            with_service_worker=config.pwa.service_worker,
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


def _unemitted_pwa_files(
    *, with_manifest: bool, with_service_worker: bool
) -> frozenset[str]:
    """The artifact-relative names the PWA switches keep the build from writing.

    ``sw.js`` is never in here: with the worker off it is the teardown worker
    rather than the caching one, so the file exists and does a different job.

    Args:
        with_manifest: Whether ``manifest.webmanifest`` is written.
        with_service_worker: Whether ``register.js`` is written.

    Returns:
        The names no file will exist for.
    """
    skipped: set[str] = set()
    if not with_manifest:
        skipped.add("manifest.webmanifest")
    if not with_service_worker:
        skipped.add("register.js")
    return frozenset(skipped)


def _pwa_artifact_files(
    files: tuple[str, ...], *, with_manifest: bool, with_service_worker: bool
) -> list[str]:
    """Drop from a fixed artifact file list what the PWA switches did not emit.

    Args:
        files: The artifact's full file list (the PWA-complete case).
        with_manifest: Whether ``manifest.webmanifest`` was written.
        with_service_worker: Whether ``register.js`` was written.

    Returns:
        The list with the unwritten entries removed.
    """
    skipped = _unemitted_pwa_files(
        with_manifest=with_manifest, with_service_worker=with_service_worker
    )
    return [name for name in files if name not in skipped]


def _pwa_precache(
    precache: tuple[str, ...], *, with_manifest: bool, with_service_worker: bool
) -> tuple[str, ...]:
    """Drop from the app shell what the PWA switches kept the build from writing.

    The worker installs with ``cache.addAll``, which rejects the **whole batch**
    when any one request fails. So a precache naming a file the build did not
    write does not degrade — the install rejects, the registration is discarded,
    and the app is left with no worker and an empty cache. Silently: the page
    still mounts, and nothing reaches the console.

    That is exactly what ``[pwa] manifest = false`` did while the worker stayed
    on, until the app shell learned to follow the switches too.

    Args:
        precache: The app-shell URLs for the PWA-complete case.
        with_manifest: Whether ``manifest.webmanifest`` was written.
        with_service_worker: Whether ``register.js`` was written.

    Returns:
        The app shell with the unwritten URLs removed.
    """
    skipped = {
        f"/{name}"
        for name in _unemitted_pwa_files(
            with_manifest=with_manifest, with_service_worker=with_service_worker
        )
    }
    return tuple(url for url in precache if url not in skipped)


def _build_wasm(
    out: Path,
    client: Path,
    name: str,
    app_source: str,
    *,
    offline: bool = False,
    project_root: Path | None = None,
    wasm: WasmConfig | None = None,
    manifest: ManifestOptions | None = None,
    dev: bool = False,
    with_manifest: bool = True,
    with_service_worker: bool = True,
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
        manifest: The Web-App-Manifest options; defaults to a name-only manifest.
        dev: When ``True``, inject the dev cache kill-switch into the shell
            instead of registering the caching service worker.
        with_manifest: Whether to emit ``manifest.webmanifest`` and link it
            (``[pwa] manifest``).
        with_service_worker: Whether to emit and register the caching worker
            (``[pwa] service_worker``). When ``False``, ``sw.js`` is the teardown
            worker and no ``register.js`` is written.

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

    theme_color = (manifest or ManifestOptions(name=name)).theme_color
    (out / "index.html").write_text(
        _index_html(
            name,
            scripts,
            theme_color,
            dev=dev,
            with_manifest=with_manifest,
            with_service_worker=with_service_worker,
        ),
        encoding="utf-8",
    )
    (out / "bootstrap.js").write_text(
        _bootstrap_js(name, pyodide_base, extra_packages), encoding="utf-8"
    )
    (out / "app.py").write_text(app_source, encoding="utf-8")
    _zip_package(out / WASM_PACKAGE_ARCHIVE, project_root=project_root, modules=modules)
    _copy_client(client, out / "client", "transport-wasm.js")
    # Native capability bridge + offline/push/pwa closure that the bootstrap's
    # native/index.js eagerly imports (geolocation/clipboard/http/…).
    _copy_client_extras(client, out / "client")
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
        # Icon resolver + vendored sets: dom.js statically imports ./icons/index.js
        # at boot, so they are part of the app shell and must precache (cache-first)
        # or a true offline boot fails to load dom.js's icon dependency.
        *(f"/client/icons/{asset}" for asset in _ICON_ASSETS),
        *(f"/client/native/{asset}" for asset in _NATIVE_ASSETS),
        *(f"/client/offline/{asset}" for asset in _OFFLINE_ASSETS),
        # native/index.js eagerly imports the push client (via notifications.js) and
        # the install prompt (via install.js); both are boot-critical shell modules.
        "/client/push/web-push-client.js",
        "/client/pwa/install-prompt.js",
        # The shell's inline script imports the connectivity banner at boot, so it
        # must precache too for a true offline boot.
        "/client/pwa/connectivity-banner.js",
        "/client/pwa/post-install-redirect.js",
        # PWA icons referenced by the manifest + apple-touch-icon link.
        *(f"/icons/{icon}" for icon in _PWA_ICON_FILES),
        *(f"/{asset}" for asset in assets),
        *(s if s.startswith("/") else f"/{s}" for s in local_scripts),
        *(f"/pyodide/{file_name}" for file_name in vendored),
    )
    _build_pwa(
        out,
        client,
        manifest or ManifestOptions(name=name),
        _pwa_precache(
            precache,
            with_manifest=with_manifest,
            with_service_worker=with_service_worker,
        ),
        with_manifest=with_manifest,
        with_service_worker=with_service_worker,
    )
    return tuple(
        sorted(
            [
                *_pwa_artifact_files(
                    WASM_ARTIFACT_FILES,
                    with_manifest=with_manifest,
                    with_service_worker=with_service_worker,
                ),
                *assets,
                *(f"pyodide/{f}" for f in vendored),
            ]
        )
    )


def _build_server(
    out: Path, client: Path, name: str, app_source: str
) -> tuple[str, ...]:
    """Write the server (FastAPI) artifact layout into ``out``.

    Both Mode B transports are shipped under ``static/``: the generated shell
    mounts ``transport-ws.js``, while ``transport-sse.js`` covers the ``/sse``
    routes the same host already serves — infrastructure that blocks WebSocket
    only needs its own shell, not a second build.

    Both import ``native/index.js``, which eagerly loads the whole native tree
    (+ offline queue, push and the install prompt), so the artifact must ship
    that closure too — otherwise the browser 404s on those modules and the app
    never mounts. It is the same closure the wasm artifact ships, under
    ``static/`` instead of ``client/``.

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
    _copy_client(client, out / "static", "transport-ws.js", "transport-sse.js")
    _copy_client_extras(client, out / "static")
    # A tab icon, from the same generator the PWA modes use. Without it the
    # browser asks for /favicon.ico on every load, the artifact answers 404, and
    # every deployment's console opens with an error it cannot do anything about.
    emit_icons(out / "static", (_SERVER_FAVICON,))
    return tuple(sorted(SERVER_ARTIFACT_FILES))


def _index_html_transpile(
    name: str,
    theme_color: str = "#111111",
    *,
    dev: bool = False,
    with_manifest: bool = True,
    with_service_worker: bool = True,
) -> str:
    """Render the ``index.html`` shell for a transpile artifact (Mode C).

    The shell imports the native runtime and the generated app module and mounts
    the app with :func:`mountApp` — no transport, no Python, no network. It also
    links the Web App Manifest and registers the cache-first service worker, so
    the static bundle is an installable, offline-capable PWA.

    The tab icon is linked explicitly. The manifest names icons, but a browser
    does not read it for the tab: without ``rel="icon"`` it probes
    ``/favicon.ico`` and a static bundle has no route to answer, so every load of
    every Mode C deployment opened its console with a 404 nobody can act on. The
    other two modes were fixed for this; this one was missed.

    Args:
        name: The project name (page title).
        theme_color: The manifest theme color, mirrored into the ``theme-color``
            meta so the browser chrome matches the installed app.
        dev: When ``True`` (the ``tempestweb dev`` loop), inject the cache
            kill-switch instead of registering the caching service worker.
        with_manifest: Whether the build emits a manifest to link.
        with_service_worker: Whether the shell registers the caching worker.

    Returns:
        The HTML document that boots the transpiled app in the browser.
    """
    if dev:
        sw_block = _DEV_CACHE_KILL_SWITCH
    elif with_service_worker:
        sw_block = _TRANSPILE_SW_REGISTER
    else:
        sw_block = _NO_SW_REGISTER
    return f"""\
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{name}</title>
{_manifest_link(with_manifest)}\
    <meta name="theme-color" content="{theme_color}" />
    <link rel="icon" href="./icons/icon-192.png" />
    <link rel="apple-touch-icon" href="./icons/apple-touch-icon.png" />
  </head>
  <body>
    <div id="app"></div>
    <script type="module">
      import {{ mountApp }} from "./client/transpile/runtime.js";
      import {{ makeState, view }} from "./client/transpile/{_TRANSPILE_APP_MODULE}";

      mountApp(document.getElementById("app"), {{ makeState, view }});
    </script>
{sw_block}
  </body>
</html>
"""


def _build_transpile(
    out: Path,
    client: Path,
    name: str,
    app_source: str,
    entry_name: str,
    *,
    manifest: ManifestOptions | None = None,
    dev: bool = False,
    with_manifest: bool = True,
    with_service_worker: bool = True,
) -> tuple[str, ...]:
    """Write the transpile (native-JS static) artifact layout into ``out`` (Mode C).

    Transcribes the project's Python app layer to a native ES module and copies
    the shared client plus the native runtime (diff/widgets/runtime) into
    ``client/transpile/``. The result is a fully static bundle — zero Python at
    runtime — servable by any host/CDN, and a first-class **PWA**: the manifest,
    icons and a cache-first service worker precaching the whole shell are emitted
    so the app installs and opens offline after the first load.

    Args:
        out: The artifact root.
        client: The shared ``client/`` directory.
        name: The project name.
        app_source: The project's entrypoint source to transpile.
        entry_name: The entrypoint file name (for the generated banner).
        manifest: The Web-App-Manifest options; defaults to a name-only manifest.
        dev: When ``True``, inject the dev cache kill-switch into the shell
            instead of registering the caching service worker.
        with_manifest: Whether to emit ``manifest.webmanifest`` and link it
            (``[pwa] manifest``).
        with_service_worker: Whether to emit and register the caching worker
            (``[pwa] service_worker``). When ``False``, ``sw.js`` is the teardown
            worker and no ``register.js`` is written.

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
    for rel in (
        "push/web-push-client.js",
        "pwa/install-prompt.js",
        "pwa/update-prompt.js",
        "pwa/connectivity-banner.js",
        "pwa/post-install-redirect.js",
    ):
        source = client / rel
        if not source.is_file():
            raise BuildError(f"missing native dependency: {source}")
        dest = out / "client" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
    # Offline-queue modules native/offline.js imports (../offline/{store,sync}).
    _copy_offline(client, out)

    # App-shell precache: the whole static bundle. Absolute, root-relative URLs
    # so the service worker's exact-path match (see chooseStrategy) is cache-first
    # for every shell asset — the app opens with no network after the first load.
    precache = (
        "/",
        "/index.html",
        "/manifest.webmanifest",
        "/register.js",
        *(f"/client/{asset}" for asset in _CLIENT_ASSETS),
        *(f"/client/icons/{asset}" for asset in _ICON_ASSETS),
        *(f"/client/transpile/{asset}" for asset in _TRANSPILE_ASSETS),
        f"/client/transpile/{_TRANSPILE_APP_MODULE}",
        *(f"/client/native/{asset}" for asset in _NATIVE_ASSETS),
        *(f"/client/offline/{asset}" for asset in _OFFLINE_ASSETS),
        "/client/push/web-push-client.js",
        "/client/pwa/install-prompt.js",
        "/client/pwa/update-prompt.js",
        "/client/pwa/connectivity-banner.js",
        "/client/pwa/post-install-redirect.js",
        *(f"/icons/{icon}" for icon in _PWA_ICON_FILES),
    )
    manifest_options = manifest or ManifestOptions(name=name)
    _build_pwa(
        out,
        client,
        manifest_options,
        _pwa_precache(
            precache,
            with_manifest=with_manifest,
            with_service_worker=with_service_worker,
        ),
        with_manifest=with_manifest,
        with_service_worker=with_service_worker,
    )

    (out / "index.html").write_text(
        _index_html_transpile(
            name,
            manifest_options.theme_color,
            dev=dev,
            with_manifest=with_manifest,
            with_service_worker=with_service_worker,
        ),
        encoding="utf-8",
    )
    return tuple(
        sorted(
            _pwa_artifact_files(
                TRANSPILE_ARTIFACT_FILES,
                with_manifest=with_manifest,
                with_service_worker=with_service_worker,
            )
        )
    )
