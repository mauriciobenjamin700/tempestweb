"""Unit tests for the PWA manifest emitter (P0).

The manifest emitter lives in ``client/pwa/manifest.js`` (pure JS, no build step).
These tests exercise it through Node so the Python gate
(``pytest tests/unit/test_pwa*.py``) also covers the installable shape, and add a
pure-Python validator that mirrors the JS install criteria for environments where
Node is unavailable.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PWA_DIR = REPO_ROOT / "client" / "pwa"
MANIFEST_JS = PWA_DIR / "manifest.js"

INSTALLABLE_DISPLAYS = {"standalone", "fullscreen", "minimal-ui"}


def _node() -> str:
    """Return the Node executable path, skipping the test if it is missing.

    Returns:
        The resolved path to the ``node`` executable.
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to run the manifest emitter")
    return node


def _emit_manifest(options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Invoke the JS manifest emitter and return the parsed manifest object.

    Args:
        options: Project overrides passed to ``buildManifest``.

    Returns:
        The parsed manifest object emitted by ``client/pwa/manifest.js``.

    Raises:
        AssertionError: If the Node subprocess fails.
    """
    node = _node()
    payload = json.dumps(options or {})
    script = (
        "import { buildManifest, emitManifest } from "
        f"{json.dumps(str(MANIFEST_JS))};"
        f"const opts = JSON.parse({json.dumps(payload)});"
        "process.stdout.write(emitManifest(buildManifest(opts)));"
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def validate_installable(manifest: dict[str, Any]) -> list[str]:
    """Return install-criteria errors for a manifest object ([] when installable).

    Mirrors ``validateInstallable`` in ``client/pwa/manifest.js``.

    Args:
        manifest: A parsed manifest object.

    Returns:
        A list of human-readable problems; empty when the manifest is installable.
    """
    errors: list[str] = []
    if not manifest.get("name") and not manifest.get("short_name"):
        errors.append("name or short_name is required")
    if not manifest.get("start_url"):
        errors.append("start_url is required")
    if manifest.get("display") not in INSTALLABLE_DISPLAYS:
        errors.append("display must be installable")

    icons = manifest.get("icons") or []

    def has_size(size: str) -> bool:
        return any(size in str(icon.get("sizes", "")).split() for icon in icons)

    if not has_size("192x192"):
        errors.append("a 192x192 icon is required")
    if not has_size("512x512"):
        errors.append("a 512x512 icon is required")
    if not any("any" in str(icon.get("purpose", "any")).split() for icon in icons):
        errors.append('at least one icon must have purpose "any"')
    return errors


def test_manifest_js_exists() -> None:
    """The manifest emitter module exists."""
    assert MANIFEST_JS.is_file()


def test_default_manifest_is_valid_json_and_installable() -> None:
    """The default manifest is valid JSON and installable-shaped."""
    manifest = _emit_manifest()
    assert isinstance(manifest, dict)
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/"
    assert validate_installable(manifest) == []


def test_manifest_has_required_install_fields() -> None:
    """The default manifest carries the install-critical fields."""
    manifest = _emit_manifest()
    for field in ("name", "short_name", "start_url", "scope", "display", "icons"):
        assert field in manifest
    assert isinstance(manifest["icons"], list) and len(manifest["icons"]) >= 2


def test_manifest_icons_include_maskable_and_any() -> None:
    """Icons include both a maskable and an 'any' purpose at 192 and 512."""
    manifest = _emit_manifest()
    purposes = {str(icon.get("purpose", "any")) for icon in manifest["icons"]}
    assert any("maskable" in p for p in purposes)
    assert any("any" in p.split() for p in purposes)


def test_overrides_pass_through() -> None:
    """Project overrides win and P5 extras pass through."""
    manifest = _emit_manifest(
        {
            "name": "Conformância",
            "short_name": "Conf",
            "start_url": "/start",
            "scope": "/app/",
            "shortcuts": [{"name": "New", "url": "/new"}],
            "share_target": {"action": "/share", "method": "POST"},
        }
    )
    assert manifest["name"] == "Conformância"
    assert manifest["start_url"] == "/start"
    assert manifest["scope"] == "/app/"
    assert manifest["id"] == "/app/"
    assert manifest["shortcuts"][0]["url"] == "/new"
    assert manifest["share_target"]["method"] == "POST"
    assert validate_installable(manifest) == []


def test_validator_catches_broken_manifest() -> None:
    """The Python validator flags a non-installable manifest."""
    broken = {"display": "browser", "icons": []}
    errors = validate_installable(broken)
    assert "start_url is required" in errors
    assert "a 192x192 icon is required" in errors


def test_manifest_has_launch_handler_and_display_override() -> None:
    """The JS emitter defaults to focus-existing launch + display fallbacks."""
    manifest = _emit_manifest()
    assert manifest["launch_handler"]["client_mode"][0] == "focus-existing"
    assert manifest["display_override"] == ["standalone", "minimal-ui"]


def test_python_emitter_matches_launch_handler_and_display_override() -> None:
    """The Python build emitter (tempestweb.pwa.manifest) carries the same fields."""
    from tempestweb.pwa.manifest import ManifestOptions, build_manifest

    manifest = build_manifest(ManifestOptions())
    assert manifest["launch_handler"]["client_mode"][0] == "focus-existing"
    assert manifest["display_override"] == ["standalone", "minimal-ui"]
    custom = build_manifest(ManifestOptions(display_override=["fullscreen"]))
    assert custom["display_override"] == ["fullscreen"]
