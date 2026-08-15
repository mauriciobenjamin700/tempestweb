"""Guards on what the distribution actually ships."""

from __future__ import annotations

from pathlib import Path

import tempestweb


def test_package_ships_the_py_typed_marker() -> None:
    """Without ``py.typed`` every symbol reaches the consuming app as ``Any``.

    The package is fully annotated, but PEP 561 makes that invisible to a type
    checker unless the marker is present: mypy then treats ``tempestweb`` as
    untyped, and an app loses checking exactly where it errs most — assembling
    the widget tree, where a wrong ``Style`` field or handler signature simply
    goes through. ``tempest_core`` ships the marker, which is what made the
    absence here surprising rather than obvious.
    """
    root = Path(tempestweb.__file__).resolve().parent
    assert (root / "py.typed").is_file()
