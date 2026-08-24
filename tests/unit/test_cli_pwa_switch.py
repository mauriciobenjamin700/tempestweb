"""The ``[pwa]`` switches decide whether each half of the PWA layer is emitted.

Every build used to emit the service worker and register it, with no way to say
no (``PwaConfig`` only customized the manifest). An app behind a login, served by
a control plane, gains nothing from offline precache and pays for it: stale
assets after a deploy until the worker updates, and ~90 files competing with boot
for connections. The only way out was stripping the artifact after the build with
a regex over generated HTML (tempestweb#161).

These pin both halves, in both static modes, plus the teardown worker that
retires an already-registered caching worker.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tempestweb.cli import build_artifact, scaffold_project

MODES = ("wasm", "transpile")


def _project(tmp_path: Path, pwa_table: str) -> Path:
    """Scaffold a project whose ``tempestweb.toml`` carries a ``[pwa]`` table.

    Args:
        tmp_path: The pytest temporary directory.
        pwa_table: The body of the ``[pwa]`` table (may be empty).

    Returns:
        The project root.
    """
    root = scaffold_project("switchme", parent=tmp_path).root
    body = '[project]\nname = "switchme"\n'
    if pwa_table:
        body += f"\n[pwa]\n{pwa_table}"
    (root / "tempestweb.toml").write_text(body, encoding="utf-8")
    return root


@pytest.mark.parametrize("mode", MODES)
def test_the_default_build_still_ships_the_whole_pwa_layer(
    tmp_path: Path, mode: str
) -> None:
    """A project that says nothing keeps exactly the behaviour it had."""
    out = build_artifact(_project(tmp_path, ""), mode=mode).out_dir
    assert (out / "manifest.webmanifest").is_file()
    assert (out / "sw.js").is_file()
    assert (out / "register.js").is_file()
    html = (out / "index.html").read_text(encoding="utf-8")
    assert 'rel="manifest"' in html
    assert "registerServiceWorker" in html


@pytest.mark.parametrize("mode", MODES)
def test_enabled_false_emits_no_registration_and_no_manifest(
    tmp_path: Path, mode: str
) -> None:
    """``[pwa] enabled = false`` turns both halves off at once."""
    out = build_artifact(_project(tmp_path, "enabled = false\n"), mode=mode).out_dir
    assert not (out / "manifest.webmanifest").exists()
    assert not (out / "register.js").exists()
    html = (out / "index.html").read_text(encoding="utf-8")
    assert 'rel="manifest"' not in html
    assert "registerServiceWorker" not in html
    assert "register.js" not in html


@pytest.mark.parametrize("mode", MODES)
def test_turning_the_worker_off_leaves_the_manifest_alone(
    tmp_path: Path, mode: str
) -> None:
    """The two halves are separate axes: a manifest is useful without a worker.

    It is what makes the app installable and names it on the home screen, which
    an admin panel may well want while wanting nothing to do with precache.
    """
    root = _project(tmp_path, "service_worker = false\n")
    out = build_artifact(root, mode=mode).out_dir
    assert (out / "manifest.webmanifest").is_file()
    assert not (out / "register.js").exists()
    html = (out / "index.html").read_text(encoding="utf-8")
    assert 'rel="manifest"' in html
    assert "registerServiceWorker" not in html


@pytest.mark.parametrize("mode", MODES)
def test_turning_the_manifest_off_leaves_the_worker_alone(
    tmp_path: Path, mode: str
) -> None:
    """And the other way round: precache without an install prompt."""
    out = build_artifact(_project(tmp_path, "manifest = false\n"), mode=mode).out_dir
    assert not (out / "manifest.webmanifest").exists()
    assert (out / "register.js").is_file()
    html = (out / "index.html").read_text(encoding="utf-8")
    assert 'rel="manifest"' not in html
    assert "registerServiceWorker" in html


@pytest.mark.parametrize("mode", MODES)
def test_the_disabled_worker_is_a_teardown_worker_not_a_missing_file(
    tmp_path: Path, mode: str
) -> None:
    """Emitting nothing would strand everyone who already registered one.

    A registered worker keeps serving the app shell from its precache until it is
    replaced, and nothing in a deploy can reach it — except a worker at the same
    URL. So ``sw.js`` is still written, as one that clears every cache and
    unregisters itself.
    """
    out = build_artifact(
        _project(tmp_path, "service_worker = false\n"), mode=mode
    ).out_dir
    sw = (out / "sw.js").read_text(encoding="utf-8")
    assert "registration.unregister()" in sw
    assert "caches.delete(name)" in sw
    assert "__PRECACHE_MANIFEST__" not in sw
    assert "PRECACHE_ASSETS" not in sw


@pytest.mark.parametrize("mode", MODES)
def test_the_disabled_build_still_reports_what_it_wrote(
    tmp_path: Path, mode: str
) -> None:
    """``BuildResult.files`` must not claim files the build did not write.

    It is what the deploy command uploads, so a phantom entry is a failed deploy
    rather than a cosmetic inaccuracy.
    """
    result = build_artifact(_project(tmp_path, "enabled = false\n"), mode=mode)
    assert "manifest.webmanifest" not in result.files
    assert "register.js" not in result.files
    assert "sw.js" in result.files
    for rel in result.files:
        assert (result.out_dir / rel).exists(), rel


@pytest.mark.parametrize("mode", MODES)
def test_the_shell_still_reports_the_network_without_a_worker(
    tmp_path: Path, mode: str
) -> None:
    """The connectivity banner is about the network, not about precaching."""
    out = build_artifact(
        _project(tmp_path, "service_worker = false\n"), mode=mode
    ).out_dir
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "mountConnectivityBanner" in html


def test_the_teardown_worker_parses(tmp_path: Path) -> None:
    """It runs in a browser with no build step, so it has to be valid JS."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not available")
    out = build_artifact(
        _project(tmp_path, "service_worker = false\n"), mode="wasm"
    ).out_dir
    completed = subprocess.run(
        [node, "--check", str(out / "sw.js")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
