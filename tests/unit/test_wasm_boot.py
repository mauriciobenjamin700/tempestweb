"""The Mode A boot path: client bundle, parallel downloads, loading screen, caching.

A wasm artifact used to load the client as a tree of ~80 static ES-module imports
that had to resolve before the bootstrap could even request Pyodide, then ran
every download strictly in series, with a blank page throughout. These tests pin
the shape that replaced it:

- the client ships as one release-time bundle, and that bundle is never stale
  against the sources it was built from;
- the bootstrap starts every download before its first ``await``, and the shell
  hints all of them from the HTML;
- a pure HTML/CSS loading screen is painted at once and can be turned off;
- content-hashed names, listed in ``tempestweb-cache.json``, are the contract a
  server reads to cache them as immutable.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tempestweb.cli import build_artifact, scaffold_project
from tempestweb.cli.config import ConfigError, load_config
from tempestweb.core.constants import (
    WASM_CACHE_MANIFEST,
    WASM_IMMUTABLE_CACHE_CONTROL,
    WASM_PYODIDE_VERSION,
)

REPO = Path(__file__).resolve().parents[2]
CLIENT = REPO / "client"
BUNDLE = CLIENT / "bundle" / "tempestweb-wasm.js"
BUNDLE_MANIFEST = CLIENT / "bundle" / "tempestweb-wasm.json"

#: Names the generated bootstrap and the shell's inline script import from the
#: client module. The bundle and its entry must export every one of them.
SHELL_IMPORTS: frozenset[str] = frozenset(
    {
        "mount",
        "createWasmTransport",
        "installNativeBridge",
        "applyThemeMode",
        "mountConnectivityBanner",
    }
)


def _project(tmp_path: Path, toml_extra: str = "") -> Path:
    """Scaffold a wasm project, optionally appending to its ``tempestweb.toml``.

    Args:
        tmp_path: The pytest temporary directory.
        toml_extra: TOML text appended to the scaffolded config.

    Returns:
        The project root.
    """
    root = scaffold_project("bootme", parent=tmp_path).root
    if toml_extra:
        config = root / "tempestweb.toml"
        config.write_text(
            config.read_text(encoding="utf-8") + "\n" + toml_extra, encoding="utf-8"
        )
    return root


def _bundle_exports(source: str) -> set[str]:
    """The exported names of an esbuild ESM bundle (its final ``export{…}``).

    Args:
        source: The bundle text.

    Returns:
        The public names, after any ``as`` alias.
    """
    match = re.search(r"export\{([^}]*)\};?\s*$", source)
    assert match, "bundle has no trailing export list"
    return {part.split(" as ")[-1].strip() for part in match.group(1).split(",")}


def test_bundle_is_fresh_against_its_sources() -> None:
    """Every module the bundle was built from still has the hash it was built at.

    Editing a client module without ``npm run bundle`` would ship the old code in
    every wasm artifact while the node tests, which load the sources, stay green.
    """
    manifest = json.loads(BUNDLE_MANIFEST.read_text(encoding="utf-8"))
    stale = [
        rel
        for rel, digest in manifest["inputs"].items()
        if hashlib.sha256((CLIENT / rel).read_bytes()).hexdigest() != digest
    ]
    assert not stale, f"client/bundle is stale (run `npm run bundle`): {stale}"
    assert hashlib.sha256(BUNDLE.read_bytes()).hexdigest() == manifest["bundle_sha256"]
    assert manifest["entry"] == "wasm-entry.js"


def test_bundle_and_entry_export_what_the_shell_imports() -> None:
    """The bundle and its unbundled entry both export the shell's imports."""
    exports = _bundle_exports(BUNDLE.read_text(encoding="utf-8"))
    assert SHELL_IMPORTS.issubset(exports)
    entry = (CLIENT / "wasm-entry.js").read_text(encoding="utf-8")
    entry_exports = set(re.findall(r"export \{ (\w+) \}", entry))
    assert entry_exports == SHELL_IMPORTS


def test_build_ships_the_bundle_under_its_content_hash(tmp_path: Path) -> None:
    """The client is one file whose directory name is its own content hash."""
    result = build_artifact(_project(tmp_path), mode="wasm")
    bundles = [p for p in result.immutable if p.endswith("tempestweb-wasm.js")]
    assert len(bundles) == 1
    shipped = (result.out_dir / bundles[0]).read_bytes()
    assert shipped == BUNDLE.read_bytes()
    digest = hashlib.sha256(shipped).hexdigest()[:16]
    assert bundles[0] == f"client-{digest}/tempestweb-wasm.js"
    assert not (result.out_dir / "client" / "tempestweb.js").exists()


def test_package_archive_name_is_its_content_hash(tmp_path: Path) -> None:
    """The Python payload's name is derived from its bytes, not the version."""
    result = build_artifact(_project(tmp_path), mode="wasm")
    archive = result.package_archive
    assert archive is not None
    digest = hashlib.sha256((result.out_dir / archive).read_bytes()).hexdigest()
    assert archive == f"tempestweb-pkg.{digest[:16]}.zip"
    assert not (result.out_dir / "tempestweb-pkg.zip").exists()


def test_cache_manifest_lists_exactly_the_hashed_files(tmp_path: Path) -> None:
    """``tempestweb-cache.json`` is the server contract: exact hashed paths."""
    result = build_artifact(_project(tmp_path), mode="wasm")
    manifest = json.loads(
        (result.out_dir / WASM_CACHE_MANIFEST).read_text(encoding="utf-8")
    )
    assert manifest["schema"] == 1
    assert manifest["generator"].startswith("tempestweb")
    assert manifest["immutable_cache_control"] == WASM_IMMUTABLE_CACHE_CONTROL
    assert manifest["revalidate_cache_control"] == "no-cache"
    assert manifest["immutable"] == sorted(result.immutable)
    for rel in manifest["immutable"]:
        assert not rel.startswith("/")
        assert (result.out_dir / rel).is_file(), rel
    for fixed in ("index.html", "bootstrap.js", "app.py", WASM_CACHE_MANIFEST):
        assert fixed not in manifest["immutable"]


def test_shell_hints_every_boot_download(tmp_path: Path) -> None:
    """The head preloads the bundle, the payload, app.py and Pyodide's files."""
    result = build_artifact(_project(tmp_path), mode="wasm")
    html = (result.out_dir / "index.html").read_text(encoding="utf-8")
    head = html.split("</head>")[0]
    base = f"https://cdn.jsdelivr.net/pyodide/{WASM_PYODIDE_VERSION}/full/"
    for rel in result.immutable:
        assert f'href="./{rel}"' in head, rel
    assert '<link rel="preload" href="./app.py" as="fetch"' in head
    for name in ("pyodide.mjs", "pyodide.asm.mjs"):
        assert f'<link rel="modulepreload" href="{base}{name}"' in head
    for name in ("pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"):
        assert f'<link rel="preload" href="{base}{name}" as="fetch"' in head
    assert '<script type="module" src="./bootstrap.js"></script>' in head
    assert 'crossorigin="anonymous"' in head


def test_bootstrap_has_no_static_import_and_starts_downloads_first(
    tmp_path: Path,
) -> None:
    """Nothing gates the boot: every download starts before the first ``await``."""
    result = build_artifact(_project(tmp_path), mode="wasm")
    bootstrap = (result.out_dir / "bootstrap.js").read_text(encoding="utf-8")
    assert not re.search(r"^import\s[^\n]*\bfrom\s+\"", bootstrap, re.MULTILINE)
    bundle = next(p for p in result.immutable if p.endswith(".js"))
    assert f'const CLIENT_URL = "./{bundle}";' in bootstrap
    assert f'const PACKAGE_URL = "./{result.package_archive}";' in bootstrap
    boot = bootstrap[bootstrap.index("export async function boot()") :]
    first_await = boot.index("await ")
    for started in (
        'import(PYODIDE_BASE + "pyodide.mjs")',
        "warmPackages()",
        "fetchOk(PACKAGE_URL)",
        'fetchOk("./app.py")',
        "import(CLIENT_URL)",
    ):
        assert boot.index(started) < first_await, started


def test_bootstrap_still_parses(tmp_path: Path) -> None:
    """The rewritten bootstrap is JS Node accepts."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    result = build_artifact(_project(tmp_path), mode="wasm")
    completed = subprocess.run(
        [node, "--check", str(result.out_dir / "bootstrap.js")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_loading_screen_is_on_by_default(tmp_path: Path) -> None:
    """The shell paints a stage-aware loading screen before any script runs."""
    result = build_artifact(_project(tmp_path), mode="wasm")
    html = (result.out_dir / "index.html").read_text(encoding="utf-8")
    body = html.split("<body>")[1]
    assert body.index('id="tw-boot"') < body.index('id="app"')
    assert 'data-stage="runtime"' in body
    assert 'role="status"' in body
    assert "prefers-color-scheme:dark" in html
    assert "prefers-reduced-motion:reduce" in html
    bootstrap = (result.out_dir / "bootstrap.js").read_text(encoding="utf-8")
    for stage in ('setBootStage("runtime")', 'setBootStage("python")'):
        assert stage in bootstrap
    assert 'setBootStage("app")' in bootstrap
    assert 'document.getElementById("tw-boot")?.remove();' in bootstrap
    assert "failBoot(error)" in bootstrap


def test_loading_screen_can_be_disabled(tmp_path: Path) -> None:
    """``[loading] enabled = false`` drops the markup and its stylesheet."""
    root = _project(tmp_path, "[loading]\nenabled = false\n")
    result = build_artifact(root, mode="wasm")
    html = (result.out_dir / "index.html").read_text(encoding="utf-8")
    assert "tw-boot" not in html


def test_loading_screen_texts_and_colours_are_configurable(tmp_path: Path) -> None:
    """Custom texts land escaped; colours override both schemes."""
    root = _project(
        tmp_path,
        "[loading]\n"
        'title = "Painel <beta>"\n'
        'runtime_text = "Baixando o runtime…"\n'
        'python_text = "Iniciando o Python…"\n'
        'app_text = "Montando o app…"\n'
        'error_text = "Falhou."\n'
        'background = "#0b1220"\n'
        'accent = "rgb(80, 160, 255)"\n',
    )
    result = build_artifact(root, mode="wasm")
    html = (result.out_dir / "index.html").read_text(encoding="utf-8")
    assert "Painel &lt;beta&gt;" in html
    assert "Painel <beta>" not in html
    assert 'data-python="Iniciando o Python…"' in html
    assert 'data-app="Montando o app…"' in html
    assert 'data-error="Falhou."' in html
    assert '<p id="tw-boot-stage">Baixando o runtime…</p>' in html
    assert "#tw-boot{--tw-boot-bg:#0b1220;--tw-boot-accent:rgb(80, 160, 255);}" in html


def test_loading_title_falls_back_to_the_pwa_name(tmp_path: Path) -> None:
    """Without ``[loading] title`` the screen names the app like its manifest."""
    root = _project(tmp_path, '[pwa]\nname = "Meu Painel"\n')
    result = build_artifact(root, mode="wasm")
    html = (result.out_dir / "index.html").read_text(encoding="utf-8")
    assert '<p class="tw-boot-title">Meu Painel</p>' in html


@pytest.mark.parametrize(
    ("toml", "message"),
    [
        ("[loading]\nenable = false\n", "unknown key"),
        ('[loading]\nenabled = "no"\n', "loading.enabled"),
        ("[loading]\ntitle = 3\n", "loading.title"),
        ('[loading]\nbackground = "red;} body{display:none"\n', "loading.background"),
        ('[loading]\naccent = "</style>"\n', "loading.accent"),
    ],
)
def test_loading_config_rejects_bad_values(
    tmp_path: Path, toml: str, message: str
) -> None:
    """A wrong key or value is a config error, never a silent default."""
    root = _project(tmp_path, toml)
    with pytest.raises(ConfigError, match=message):
        load_config(root)


def test_dev_build_loads_the_unbundled_entry(tmp_path: Path) -> None:
    """The dev loop serves the readable sources, so client edits are live."""
    result = build_artifact(_project(tmp_path), mode="wasm", dev=True)
    bootstrap = (result.out_dir / "bootstrap.js").read_text(encoding="utf-8")
    assert 'const CLIENT_URL = "./client/wasm-entry.js";' in bootstrap
    assert (result.out_dir / "client" / "wasm-entry.js").is_file()
    assert (result.out_dir / "client" / "native" / "index.js").is_file()
    assert not any(p.startswith("client-") for p in result.files)
    assert all(p.endswith(".zip") for p in result.immutable)


def test_service_worker_precaches_the_bundle_and_its_queue_modules(
    tmp_path: Path,
) -> None:
    """The caching worker precaches the bundle, not the old module tree."""
    result = build_artifact(_project(tmp_path), mode="wasm")
    sw = (result.out_dir / "sw.js").read_text(encoding="utf-8")
    start = sw.index('"[')
    end = sw.index(']"', start) + 2
    precache = json.loads(json.loads(sw[start:end]))
    for rel in result.immutable:
        assert f"/{rel}" in precache
    client_entries = sorted(p for p in precache if p.startswith("/client/"))
    assert client_entries == ["/client/offline/store.js", "/client/offline/sync.js"]
    for entry in client_entries:
        assert (result.out_dir / entry.lstrip("/")).is_file()
    assert 'from "./client/offline/store.js"' in sw


def test_no_worker_means_no_loose_client_files(tmp_path: Path) -> None:
    """Without the caching worker, the bundle is the only client file shipped."""
    root = _project(tmp_path, "[pwa]\nservice_worker = false\n")
    result = build_artifact(root, mode="wasm")
    assert not (result.out_dir / "client").exists()
    html = (result.out_dir / "index.html").read_text(encoding="utf-8")
    bundle = next(p for p in result.immutable if p.endswith(".js"))
    assert f'import {{ mountConnectivityBanner }} from "./{bundle}";' in html
    assert "register.js" not in html
