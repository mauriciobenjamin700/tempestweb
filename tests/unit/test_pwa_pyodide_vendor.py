"""Tests for offline Pyodide vendoring — tempestweb.pwa.pyodide_vendor.

Covers the dependency-closure resolver (normalization, transitive deps, missing
package) and :func:`vendor_pyodide` with an injected fetcher, so neither touches
the network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tempestweb.pwa import (
    PYODIDE_CORE_FILES,
    pyodide_cdn_base,
    resolve_package_files,
    vendor_pyodide,
)

# A tiny lock standing in for pyodide-lock.json: pydantic depends on
# pydantic_core (note the separator mismatch) and annotated-types.
_LOCK: dict[str, object] = {
    "packages": {
        "pydantic": {
            "name": "pydantic",
            "file_name": "pydantic-2.12.5-py3-none-any.whl",
            "depends": ["pydantic_core", "annotated-types"],
        },
        "pydantic-core": {
            "name": "pydantic_core",  # underscore here, hyphen in the key/depends
            "file_name": "pydantic_core-2.41.5-cp314.whl",
            "depends": ["typing-extensions"],
        },
        "annotated-types": {
            "name": "annotated_types",
            "file_name": "annotated_types-0.7.0-py3-none-any.whl",
            "depends": [],
        },
        "typing-extensions": {
            "name": "typing_extensions",
            "file_name": "typing_extensions-4.15.0-py3-none-any.whl",
            "depends": [],
        },
        "unused": {
            "name": "unused",
            "file_name": "unused-1.0.whl",
            "depends": [],
        },
    }
}


def test_pyodide_cdn_base_builds_full_url() -> None:
    assert pyodide_cdn_base("v314.0.0") == (
        "https://cdn.jsdelivr.net/pyodide/v314.0.0/full/"
    )


def test_resolve_closure_includes_transitive_deps_and_skips_unused() -> None:
    files = resolve_package_files(_LOCK, ("pydantic",))
    assert files == [
        "annotated_types-0.7.0-py3-none-any.whl",
        "pydantic-2.12.5-py3-none-any.whl",
        "pydantic_core-2.41.5-cp314.whl",
        "typing_extensions-4.15.0-py3-none-any.whl",
    ]
    assert "unused-1.0.whl" not in files


def test_resolve_normalizes_separator_mismatch() -> None:
    # The root passed with an underscore must still match the hyphenated key.
    files = resolve_package_files(_LOCK, ("pydantic_core",))
    assert "pydantic_core-2.41.5-cp314.whl" in files
    assert "typing_extensions-4.15.0-py3-none-any.whl" in files


def test_resolve_raises_for_unknown_package() -> None:
    with pytest.raises(KeyError):
        resolve_package_files(_LOCK, ("nope",))


def test_vendor_pyodide_writes_runtime_and_wheels(tmp_path: Path) -> None:
    requested: list[str] = []

    def fake_fetch(url: str) -> bytes:
        requested.append(url)
        if url.endswith("pyodide-lock.json"):
            return json.dumps(_LOCK).encode("utf-8")
        return b"BYTES:" + url.rsplit("/", 1)[-1].encode("utf-8")

    dest = tmp_path / "pyodide"
    written = vendor_pyodide(
        dest, version="v314.0.0", packages=("pydantic",), fetch=fake_fetch
    )

    # Every core runtime file plus the resolved wheel closure is written on disk.
    for core in PYODIDE_CORE_FILES:
        assert (dest / core).is_file()
    assert (dest / "pydantic-2.12.5-py3-none-any.whl").is_file()
    assert (dest / "typing_extensions-4.15.0-py3-none-any.whl").is_file()

    # The lock is written from the bytes fetched once (not re-downloaded).
    assert written[0] == "pyodide-lock.json"
    assert requested.count(pyodide_cdn_base("v314.0.0") + "pyodide-lock.json") == 1

    # The wasm binary content came straight from the fetcher.
    assert (dest / "pyodide.asm.wasm").read_bytes() == b"BYTES:pyodide.asm.wasm"
