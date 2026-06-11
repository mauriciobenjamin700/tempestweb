"""Unit tests for the Python PWA build emitter (P0/P5).

Covers ``tempestweb.pwa``: the manifest builder/validator and the stdlib-only
icon emitter. These mirror the install criteria of ``client/pwa/manifest.js``.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

from tempestweb.pwa import (
    DEFAULT_ICON_SPECS,
    ManifestOptions,
    build_manifest,
    emit_icons,
    emit_manifest,
    placeholder_png,
    validate_installable,
    write_manifest,
)


def test_default_manifest_is_installable() -> None:
    """The default manifest is installable-shaped with no overrides."""
    manifest = build_manifest()
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/"
    assert manifest["id"] == "/"
    assert validate_installable(manifest) == []


def test_default_manifest_has_required_fields() -> None:
    """The default manifest carries the install-critical fields."""
    manifest = build_manifest()
    for f in ("name", "short_name", "start_url", "scope", "display", "icons"):
        assert f in manifest
    assert len(manifest["icons"]) >= 2


def test_icons_include_maskable_and_any() -> None:
    """Default icons include both maskable and 'any' purposes."""
    manifest = build_manifest()
    purposes = {str(i.get("purpose", "any")) for i in manifest["icons"]}
    assert any("maskable" in p for p in purposes)
    assert any("any" in p.split() for p in purposes)


def test_overrides_and_p5_extras_pass_through() -> None:
    """Project overrides win and P5 shortcuts/share_target/file_handlers pass."""
    manifest = build_manifest(
        ManifestOptions(
            name="Conformância",
            short_name="Conf",
            start_url="/start",
            scope="/app/",
            shortcuts=[{"name": "New", "url": "/new"}],
            share_target={"action": "/share", "method": "POST"},
            file_handlers=[{"action": "/open", "accept": {"text/csv": [".csv"]}}],
        )
    )
    assert manifest["name"] == "Conformância"
    assert manifest["start_url"] == "/start"
    assert manifest["id"] == "/app/"
    assert manifest["shortcuts"][0]["url"] == "/new"
    assert manifest["share_target"]["method"] == "POST"
    assert manifest["file_handlers"][0]["action"] == "/open"
    assert validate_installable(manifest) == []


def test_display_coerced_to_standalone_when_invalid() -> None:
    """A non-installable display is coerced back to standalone."""
    manifest = build_manifest(ManifestOptions(display="browser"))
    assert manifest["display"] == "standalone"


def test_emit_manifest_is_valid_json_with_unicode() -> None:
    """emit_manifest produces valid JSON preserving accented characters."""
    text = emit_manifest(build_manifest(ManifestOptions(name="Conformância")))
    parsed = json.loads(text)
    assert parsed["name"] == "Conformância"
    assert "Conform\\u" not in text  # ensure_ascii=False keeps the accent literal


def test_write_manifest_round_trips(tmp_path: Path) -> None:
    """write_manifest writes a parseable, installable manifest file."""
    dest = tmp_path / "build" / "manifest.webmanifest"
    out = write_manifest(dest)
    assert out == dest and dest.is_file()
    parsed = json.loads(dest.read_text(encoding="utf-8"))
    assert validate_installable(parsed) == []


def test_validator_catches_broken_manifest() -> None:
    """The validator flags a non-installable manifest."""
    errors = validate_installable({"display": "browser", "icons": []})
    assert "start_url is required" in errors
    assert "a 192x192 icon is required" in errors


def _read_png_dimensions(data: bytes) -> tuple[int, int]:
    """Parse width/height from a PNG's IHDR chunk.

    Args:
        data: PNG file bytes.

    Returns:
        The (width, height) tuple.
    """
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    # IHDR data begins at byte 16 (8 sig + 4 len + 4 tag).
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def test_placeholder_png_is_valid_and_sized() -> None:
    """placeholder_png emits a byte-valid PNG of the requested size."""
    png = placeholder_png(192)
    assert _read_png_dimensions(png) == (192, 192)
    # The IDAT must decompress to size*size*4 + size filter bytes.
    # Roughly verify it is a parseable RGBA raster.
    assert png[12:16] == b"IHDR"
    assert png.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82")


def test_emit_icons_writes_full_set(tmp_path: Path) -> None:
    """emit_icons writes every default spec with correct dimensions."""
    out = emit_icons(tmp_path / "icons")
    assert len(out) == len(DEFAULT_ICON_SPECS)
    by_name = {p.name: p for p in out}
    assert "icon-192.png" in by_name
    assert "maskable-512.png" in by_name
    assert "apple-touch-icon.png" in by_name
    assert _read_png_dimensions(by_name["icon-512.png"].read_bytes()) == (512, 512)


def test_maskable_icon_has_inset() -> None:
    """A maskable icon differs from a plain one of the same size (safe zone)."""
    plain = placeholder_png(192, inset=0)
    masked = placeholder_png(192, inset=round(192 * 0.1))
    assert plain != masked
    # Both remain byte-valid PNGs of the same dimensions.
    assert _read_png_dimensions(plain) == _read_png_dimensions(masked) == (192, 192)
