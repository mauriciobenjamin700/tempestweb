"""Vendor the Pyodide runtime + package wheels for offline Mode A boot.

By default a wasm artifact loads Pyodide and its packages from the jsdelivr CDN
(cross-origin), so the service worker cannot precache them and a cold start needs
the network. An **offline** build instead downloads the Pyodide runtime and the
closure of package wheels the app needs into the artifact's ``pyodide/`` dir, so
everything is same-origin, the service worker precaches it, and the app boots
fully offline after the first load.

The closure is resolved from Pyodide's own ``pyodide-lock.json``: each requested
package contributes its wheel plus, transitively, every package it ``depends`` on
(names normalized so ``pydantic_core`` and ``pydantic-core`` match). Downloads go
through an injectable ``fetch`` so the resolver and layout are unit-testable
without the network.

Every wheel is checked against the ``sha256`` its lock entry declares — the lock
publishes those digests and ignoring them means writing whatever bytes came back
into the artifact and shipping them to users. It bounds what a truncated
download or a swapped file can do; it is not a defence against a lock that is
itself wrong, since the lock comes from the same host.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.request import urlopen

__all__ = [
    "PYODIDE_CORE_FILES",
    "Fetcher",
    "package_digests",
    "pyodide_cdn_base",
    "resolve_package_files",
    "vendor_pyodide",
]

#: Runtime files the loader needs relative to its ``indexURL``: the ESM entry
#: (``pyodide.mjs``), the Emscripten JS glue it dynamically imports
#: (``pyodide.asm.mjs`` — current releases renamed the old ``pyodide.asm.js``),
#: the wasm binary, the stdlib zip and the package lock.
PYODIDE_CORE_FILES: tuple[str, ...] = (
    "pyodide.mjs",
    "pyodide.asm.mjs",
    "pyodide.asm.wasm",
    "python_stdlib.zip",
    "pyodide-lock.json",
)

#: A function that downloads ``url`` and returns its bytes.
Fetcher = Callable[[str], bytes]


def pyodide_cdn_base(version: str) -> str:
    """Return the jsdelivr base URL for a Pyodide release.

    Args:
        version: The Pyodide release tag (e.g. ``"v314.0.0"``).

    Returns:
        The ``full/`` base URL, with a trailing slash.
    """
    return f"https://cdn.jsdelivr.net/pyodide/{version}/full/"


def _default_fetch(url: str) -> bytes:
    """Download ``url`` over HTTP and return its bytes.

    Args:
        url: The absolute URL to fetch.

    Returns:
        The response body.
    """
    with urlopen(url, timeout=120) as response:  # noqa: S310 - fixed https CDN host
        return bytes(response.read())


def package_digests(lock: dict[str, Any]) -> dict[str, str]:
    """Map each wheel file name in the lock to the ``sha256`` it declares.

    Args:
        lock: The parsed ``pyodide-lock.json`` document.

    Returns:
        ``{file_name: sha256}`` for every entry that publishes a digest.
    """
    packages: dict[str, Any] = lock.get("packages", {})
    return {
        str(entry["file_name"]): str(entry["sha256"])
        for entry in packages.values()
        if entry.get("file_name") and entry.get("sha256")
    }


def _verify_digest(file_name: str, payload: bytes, expected: str) -> None:
    """Check downloaded bytes against the digest the lock declares.

    Args:
        file_name: The file being vendored (for the error message).
        payload: The downloaded bytes.
        expected: The ``sha256`` hex digest from the lock entry.

    Raises:
        ValueError: If the bytes do not hash to ``expected``.
    """
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected.lower():
        raise ValueError(
            f"tempestweb: checksum mismatch vendoring {file_name} "
            f"(lock declares {expected}, downloaded {actual})"
        )


def _normalize(name: str) -> str:
    """Normalize a package name for lock lookup (lowercase, unified separators).

    Args:
        name: A package name as it appears in ``depends`` or a lock entry.

    Returns:
        The normalized key (lowercase, ``_`` folded to ``-``).
    """
    return name.lower().replace("_", "-")


def resolve_package_files(lock: dict[str, Any], roots: tuple[str, ...]) -> list[str]:
    """Resolve the wheel files for ``roots`` and their transitive dependencies.

    Walks the dependency graph in ``pyodide-lock.json`` from each root package,
    collecting every reachable package's ``file_name``.

    Args:
        lock: The parsed ``pyodide-lock.json`` document.
        roots: The package names the app imports (e.g. ``("pydantic",)``).

    Returns:
        The sorted, de-duplicated list of wheel file names to vendor.

    Raises:
        KeyError: If a required package is absent from the lock file.
    """
    packages: dict[str, Any] = lock["packages"]
    by_norm: dict[str, Any] = {_normalize(e["name"]): e for e in packages.values()}
    seen: set[str] = set()
    files: list[str] = []
    stack: list[str] = list(roots)
    while stack:
        key = _normalize(stack.pop())
        if key in seen:
            continue
        seen.add(key)
        entry = by_norm.get(key)
        if entry is None:
            raise KeyError(f"package {key!r} not in pyodide lock")
        files.append(str(entry["file_name"]))
        stack.extend(entry.get("depends", []))
    return sorted(files)


def vendor_pyodide(
    out_dir: str | Path,
    *,
    version: str,
    packages: tuple[str, ...],
    fetch: Fetcher | None = None,
) -> list[str]:
    """Download the Pyodide runtime + ``packages`` closure into ``out_dir``.

    Writes the core runtime files and every resolved wheel as siblings in
    ``out_dir`` (the artifact's ``pyodide/`` directory). The lock file is fetched
    once and reused to resolve the package closure, then written alongside the
    rest so the offline ``indexURL`` is self-contained.

    Args:
        out_dir: The directory to write the vendored files into (created if
            absent).
        version: The Pyodide release tag to vendor.
        packages: The package names the app imports (their closure is vendored).
        fetch: Download function (injected in tests). Defaults to an HTTP fetch.

    Returns:
        The file names written, in fetch order (lock first, then the remaining
        core files, then the wheels).

    Raises:
        ValueError: If a downloaded wheel does not match the ``sha256`` its lock
            entry declares.
    """
    downloader: Fetcher = fetch or _default_fetch
    base = pyodide_cdn_base(version)
    dest = Path(out_dir)
    dest.mkdir(parents=True, exist_ok=True)

    lock_bytes = downloader(base + "pyodide-lock.json")
    (dest / "pyodide-lock.json").write_bytes(lock_bytes)
    lock = json.loads(lock_bytes.decode("utf-8"))

    wheels = resolve_package_files(lock, packages)
    digests = package_digests(lock)
    remaining = [f for f in PYODIDE_CORE_FILES if f != "pyodide-lock.json"] + wheels
    for file_name in remaining:
        payload = downloader(base + file_name)
        expected = digests.get(file_name)
        if expected is not None:
            _verify_digest(file_name, payload, expected)
        (dest / file_name).write_bytes(payload)

    return ["pyodide-lock.json", *remaining]
