"""tempestweb.pwa — PWA build artifacts (manifest + icons). Track P, P0/P5.

This package owns the *Python* side of the PWA: emitting a spec-compliant,
installable ``manifest.webmanifest`` and the icon set during ``tempestweb build``
(both Mode A and Mode B). The *shape* of the manifest mirrors the pure-JS
``client/pwa/manifest.js`` so the two never drift; this module is the build-time
emitter that writes files to disk.

See ``docs/plan.md`` §7 P0/P5 for the contract.
"""

from __future__ import annotations

from tempestweb.pwa.icons import (
    DEFAULT_ICON_SPECS,
    IconSpec,
    emit_icons,
    placeholder_png,
)
from tempestweb.pwa.manifest import (
    DEFAULT_ICONS,
    ManifestOptions,
    build_manifest,
    emit_manifest,
    validate_installable,
    write_manifest,
)

__all__: list[str] = [
    "DEFAULT_ICONS",
    "DEFAULT_ICON_SPECS",
    "IconSpec",
    "ManifestOptions",
    "build_manifest",
    "emit_icons",
    "emit_manifest",
    "placeholder_png",
    "validate_installable",
    "write_manifest",
]
