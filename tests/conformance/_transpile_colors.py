"""Regenerate the Mode C `Color.from_hex` fixture from the real core.

Run as a module to (re)write the golden::

    python -m tests.conformance._transpile_colors

`Color.from_hex` is how an app writes a literal color — 65 call sites across the
examples — and Mode C's `Color` was a bare factory, so `Color.from_hex("#b3261e")`
compiled, loaded, and threw ``Color.from_hex is not a function`` at mount: a blank
page. The parse has three shapes (``#RGB``, ``#RRGGBB``, ``#RRGGBBAA``), an
optional ``#``, and an alpha channel scaled by 255, so the port is pinned against
the core rather than re-derived by eye.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tempest_core import Color

FIXTURES_DIR: Path = Path(__file__).resolve().parents[1] / "fixtures"
COLORS_FIXTURE: Path = FIXTURES_DIR / "transpile_color_samples.json"

HEX_SAMPLES: tuple[str, ...] = (
    "#b3261e",
    "b3261e",
    "#49454f",
    "#fff",
    "#000",
    "abc",
    "#11223344",
    "#ffffff00",
    "#0A0B0C",
)

INVALID_SAMPLES: tuple[str, ...] = ("", "#", "#12", "#12345", "#1234567", "#zzzzzz")


def build_samples() -> dict[str, Any]:
    """Build the hex → channels map, plus the strings the core rejects.

    Returns:
        A mapping with ``parsed`` (hex string → serialized ``Color``) and
        ``invalid`` (the strings ``from_hex`` raises on).
    """
    parsed = {
        value: Color.from_hex(value).model_dump(mode="json") for value in HEX_SAMPLES
    }
    invalid = []
    for value in INVALID_SAMPLES:
        try:
            Color.from_hex(value)
        except ValueError:
            invalid.append(value)
    return {"parsed": parsed, "invalid": invalid}


def render_fixture_text() -> str:
    """Render the color fixture as canonical JSON text."""
    return (
        json.dumps(build_samples(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )


def write_fixture() -> Path:
    """Write the color fixture to disk and return its path."""
    COLORS_FIXTURE.write_text(render_fixture_text(), encoding="utf-8")
    return COLORS_FIXTURE


def main() -> None:
    """Regenerate the color fixture and print its path."""
    print(f"wrote {write_fixture()}")


if __name__ == "__main__":
    main()
