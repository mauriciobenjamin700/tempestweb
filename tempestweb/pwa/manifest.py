"""Web App Manifest emitter (P0/P5).

Builds an installable-shaped ``manifest.webmanifest`` at build time. The field
set and install criteria mirror the pure-JS emitter in
``client/pwa/manifest.js`` so the build-time output and any client-side checks
never drift.

Installable-shaped means (Chromium/Lighthouse baseline):
    - ``name`` or ``short_name``
    - ``start_url``
    - ``display`` in {"standalone", "fullscreen", "minimal-ui"}
    - ``icons`` includes a 192x192 and a 512x512 PNG, and at least one icon with
      purpose containing "any".
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

INSTALLABLE_DISPLAYS: frozenset[str] = frozenset(
    {"standalone", "fullscreen", "minimal-ui"}
)

#: Default icon set: plain "any" 192/512 + maskable 192/512. References only;
#: ``tempestweb.pwa.icons.emit_icons`` writes the actual files.
DEFAULT_ICONS: list[dict[str, str]] = [
    {
        "src": "/icons/icon-192.png",
        "sizes": "192x192",
        "type": "image/png",
        "purpose": "any",
    },
    {
        "src": "/icons/icon-512.png",
        "sizes": "512x512",
        "type": "image/png",
        "purpose": "any",
    },
    {
        "src": "/icons/maskable-192.png",
        "sizes": "192x192",
        "type": "image/png",
        "purpose": "maskable",
    },
    {
        "src": "/icons/maskable-512.png",
        "sizes": "512x512",
        "type": "image/png",
        "purpose": "maskable",
    },
]


@dataclass(slots=True)
class ManifestOptions:
    """Project overrides for the generated manifest.

    Every field defaults to an installable-shaped value; a project's
    ``tempestweb`` config overrides what it needs.

    Attributes:
        name: Full application name.
        short_name: Home-screen label.
        description: Human description.
        start_url: URL opened on launch.
        scope: Navigation scope.
        display: One of the installable display modes.
        theme_color: Toolbar color (CSS color).
        background_color: Splash background (CSS color).
        lang: BCP-47 language tag.
        dir: Text direction ("ltr" | "rtl" | "auto").
        orientation: Optional preferred orientation.
        app_id: Stable app identity; defaults to ``scope`` when None.
        icons: Icon set; defaults to ``DEFAULT_ICONS`` when empty.
        categories: App-store categories.
        shortcuts: P5 app shortcuts.
        share_target: P5 share target descriptor.
        file_handlers: P5 file handler descriptors.
    """

    name: str = "tempestweb app"
    short_name: str = "tempestweb"
    description: str = "A tempestweb application."
    start_url: str = "/"
    scope: str = "/"
    display: str = "standalone"
    theme_color: str = "#111111"
    background_color: str = "#ffffff"
    lang: str = "pt-BR"
    dir: str = "auto"
    orientation: str | None = None
    app_id: str | None = None
    icons: list[dict[str, str]] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    shortcuts: list[dict[str, Any]] = field(default_factory=list)
    share_target: dict[str, Any] | None = None
    file_handlers: list[dict[str, Any]] = field(default_factory=list)


def build_manifest(options: ManifestOptions | None = None) -> dict[str, Any]:
    """Build a manifest object from options, filling installable defaults.

    Args:
        options: Project overrides. ``None`` uses every default.

    Returns:
        A JSON-able manifest object ready for ``emit_manifest``.
    """
    opts = options or ManifestOptions()
    display = opts.display if opts.display in INSTALLABLE_DISPLAYS else "standalone"
    icons = opts.icons if opts.icons else DEFAULT_ICONS

    manifest: dict[str, Any] = {
        "name": opts.name,
        "short_name": opts.short_name,
        "description": opts.description,
        "start_url": opts.start_url,
        "scope": opts.scope,
        "display": display,
        "theme_color": opts.theme_color,
        "background_color": opts.background_color,
        "lang": opts.lang,
        "dir": opts.dir,
        "icons": [dict(icon) for icon in icons],
    }

    # Stable app identity defaults to the scope.
    manifest["id"] = opts.app_id if opts.app_id is not None else manifest["scope"]

    if opts.orientation:
        manifest["orientation"] = opts.orientation
    if opts.categories:
        manifest["categories"] = list(opts.categories)

    # P5 extras pass through untouched when present.
    if opts.shortcuts:
        manifest["shortcuts"] = [dict(s) for s in opts.shortcuts]
    if opts.share_target:
        manifest["share_target"] = dict(opts.share_target)
    if opts.file_handlers:
        manifest["file_handlers"] = [dict(h) for h in opts.file_handlers]

    return manifest


def emit_manifest(manifest: dict[str, Any], indent: int = 2) -> str:
    """Serialize a manifest object to JSON text for ``manifest.webmanifest``.

    Args:
        manifest: A manifest object (typically from ``build_manifest``).
        indent: Spaces of indentation (0 for minified).

    Returns:
        The JSON string. ``ensure_ascii`` is False so accented names survive.
    """
    return json.dumps(manifest, indent=indent or None, ensure_ascii=False)


def write_manifest(
    dest: Path,
    options: ManifestOptions | None = None,
    indent: int = 2,
) -> Path:
    """Build and write ``manifest.webmanifest`` to ``dest``.

    Args:
        dest: Output file path (parent dirs are created).
        options: Project overrides.
        indent: JSON indentation.

    Returns:
        The path written.
    """
    manifest = build_manifest(options)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(emit_manifest(manifest, indent=indent) + "\n", encoding="utf-8")
    return dest


def validate_installable(manifest: dict[str, Any]) -> list[str]:
    """Return install-criteria errors for a manifest ([] when installable).

    Mirrors ``validateInstallable`` in ``client/pwa/manifest.js``.

    Args:
        manifest: A parsed manifest object.

    Returns:
        Human-readable problems; empty when installable.
    """
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["manifest must be an object"]
    if not manifest.get("name") and not manifest.get("short_name"):
        errors.append("name or short_name is required")
    if not manifest.get("start_url"):
        errors.append("start_url is required")
    if manifest.get("display") not in INSTALLABLE_DISPLAYS:
        errors.append('display must be "standalone", "fullscreen" or "minimal-ui"')

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


def default_extras() -> dict[str, Any]:
    """Return the default P5 manifest extras a scaffolded app ships.

    A "Home" shortcut, a POST share target and a CSV file handler. References
    only — the host app wires the routes (share_target pairs with native.share).

    Returns:
        A dict with ``shortcuts``, ``share_target`` and ``file_handlers``.
    """
    return {
        "shortcuts": [
            {
                "name": "Home",
                "short_name": "Home",
                "url": "/",
                "description": "Open the app home",
            }
        ],
        "share_target": {
            "action": "/share-target",
            "method": "POST",
            "enctype": "multipart/form-data",
            "params": {"title": "title", "text": "text", "url": "url"},
        },
        "file_handlers": [{"action": "/open", "accept": {"text/csv": [".csv"]}}],
    }


def validate_extras(manifest: dict[str, Any]) -> list[str]:
    """Validate the P5 manifest extras (shortcuts/share_target/file_handlers).

    Progressive enhancements with uneven browser support, so this is a shape
    check, not an install requirement. Mirrors ``validateExtras`` in
    ``client/pwa/manifest.js``.

    Args:
        manifest: A manifest (or extras) object.

    Returns:
        Human-readable problems; empty when present extras are well-formed.
    """
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["manifest must be an object"]

    shortcuts = manifest.get("shortcuts")
    if shortcuts is not None:
        if not isinstance(shortcuts, list):
            errors.append("shortcuts must be an array")
        else:
            for i, s in enumerate(shortcuts):
                if not isinstance(s, dict) or not isinstance(s.get("name"), str):
                    errors.append(f"shortcuts[{i}].name is required")
                if not isinstance(s, dict) or not isinstance(s.get("url"), str):
                    errors.append(f"shortcuts[{i}].url is required")

    share_target = manifest.get("share_target")
    if share_target is not None:
        if not isinstance(share_target, dict):
            errors.append("share_target must be an object")
        else:
            if not isinstance(share_target.get("action"), str):
                errors.append("share_target.action is required")
            method = str(share_target.get("method", "GET")).upper()
            if method == "POST" and not isinstance(share_target.get("enctype"), str):
                errors.append("share_target with method POST requires an enctype")

    file_handlers = manifest.get("file_handlers")
    if file_handlers is not None:
        if not isinstance(file_handlers, list):
            errors.append("file_handlers must be an array")
        else:
            for i, h in enumerate(file_handlers):
                if not isinstance(h, dict) or not isinstance(h.get("action"), str):
                    errors.append(f"file_handlers[{i}].action is required")
                if not isinstance(h, dict) or not isinstance(h.get("accept"), dict):
                    errors.append(f"file_handlers[{i}].accept is required")

    return errors
