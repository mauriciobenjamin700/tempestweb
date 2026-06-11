"""Generate ``public/manifest.json`` — the file list the WASM bootstrap loads.

Mode A has **no build step**: the browser bootstrap (``public/index.html``) loads
Pyodide and then writes the ``tempestweb`` Python package into Pyodide's virtual
filesystem by fetching each source file over HTTP. To do that it needs to know
which files exist; this script produces that list as a flat JSON array of
repo-relative paths.

Run it whenever the Python package's file set changes (added/removed modules)::

    python public/gen_manifest.py

It walks ``tempestweb/`` for ``*.py`` files (skipping ``__pycache__``) plus the
example app, and writes ``public/manifest.json``. The bootstrap fetches every
listed path relative to the repo root and writes it into the Pyodide FS, so the
vendored core imports exactly as it does locally.
"""

from __future__ import annotations

import json
from pathlib import Path

#: Repo root (the parent of this ``public/`` directory).
ROOT = Path(__file__).resolve().parent.parent

#: Directories whose ``*.py`` files the bootstrap needs in the Pyodide FS.
INCLUDE_DIRS: tuple[str, ...] = ("tempestweb",)

#: Standalone files (e.g. the example app) the bootstrap also loads.
INCLUDE_FILES: tuple[str, ...] = ("examples/counter/app.py",)


def collect() -> list[str]:
    """Collect the repo-relative paths the bootstrap must fetch.

    Returns:
        Sorted repo-relative POSIX paths of every Python file the bootstrap
        loads (the ``tempestweb`` package, skipping ``__pycache__``, plus the
        standalone example files).
    """
    paths: list[str] = []
    for directory in INCLUDE_DIRS:
        for path in sorted((ROOT / directory).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            paths.append(path.relative_to(ROOT).as_posix())
    paths.extend(INCLUDE_FILES)
    return paths


def main() -> None:
    """Write ``public/manifest.json`` from the collected file list."""
    manifest = collect()
    out = ROOT / "public" / "manifest.json"
    out.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {out} ({len(manifest)} files)")


if __name__ == "__main__":
    main()
