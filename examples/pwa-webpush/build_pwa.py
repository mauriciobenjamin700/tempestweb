"""PWA build script — emit manifest.webmanifest + icon set for pwa-webpush.

Run this script from the repository root to generate the ``build/`` directory
for the pwa-webpush example::

    python examples/pwa-webpush/build_pwa.py

The script:

1. Calls :func:`~tempestweb.pwa.write_manifest` to produce
   ``build/manifest.webmanifest`` with metadata tailored to this example.
2. Calls :func:`~tempestweb.pwa.emit_icons` to write the full icon set under
   ``build/icons/``.
3. Reads the manifest back, calls
   :func:`~tempestweb.pwa.validate_installable`, and prints the result — an
   empty list means the app is fully installable.

The ``build_pwa.main(dest)`` function is importable so the test suite can drive
it into a ``tmp_path`` without touching the real ``build/`` directory.
"""

from __future__ import annotations

import json
from pathlib import Path

from tempestweb.pwa import (
    ManifestOptions,
    emit_icons,
    validate_installable,
    write_manifest,
)

#: App metadata for this demo.
OPTIONS: ManifestOptions = ManifestOptions(
    name="PWA WebPush Demo",
    short_name="WebPush",
    description="A tempestweb demo that shows PWA install and WebPush notifications.",
    start_url="/",
    scope="/",
    display="standalone",
    theme_color="#111827",
    background_color="#f9fafb",
    lang="pt-BR",
    categories=["utilities"],
)


def main(dest: Path | None = None) -> dict[str, list[str | Path]]:
    """Emit the manifest and icon set into ``dest``, then validate installability.

    Args:
        dest: Output root directory. Defaults to ``<repo_root>/build``.

    Returns:
        A dict with keys ``"manifest"`` (list with the written manifest path)
        and ``"icons"`` (list of written icon paths).  The dict is for
        programmatic callers; the script also prints the
        :func:`validate_installable` result to stdout.
    """
    if dest is None:
        dest = Path(__file__).resolve().parents[2] / "build"

    # ------------------------------------------------------------------ #
    # 1. Write manifest.webmanifest
    # ------------------------------------------------------------------ #
    manifest_path = write_manifest(dest / "manifest.webmanifest", options=OPTIONS)

    # ------------------------------------------------------------------ #
    # 2. Emit icon set
    # ------------------------------------------------------------------ #
    icon_paths = emit_icons(dest / "icons")

    # ------------------------------------------------------------------ #
    # 3. Validate installability (must return [])
    # ------------------------------------------------------------------ #
    manifest_dict = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = validate_installable(manifest_dict)

    print(f"manifest  -> {manifest_path}")
    print(f"icons     -> {len(icon_paths)} files under {dest / 'icons'}")
    print(f"installable? {errors if errors else '✓ yes (no errors)'}")

    return {
        "manifest": [manifest_path],
        "icons": icon_paths,
    }


if __name__ == "__main__":
    main()
