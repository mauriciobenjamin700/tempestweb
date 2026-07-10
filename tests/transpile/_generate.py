"""Regenerate the Mode C transpile goldens from the example apps.

Run as a module whenever the transpiler's output intentionally changes::

    python -m tests.transpile._generate

The golden test (:mod:`.test_counter`) asserts the committed `.gen.js` equals
what the transpiler produces now, so a drift fails until the golden is
regenerated and reviewed.
"""

from __future__ import annotations

from pathlib import Path

from tempestweb.transpile import transpile_file

ROOT = Path(__file__).resolve().parents[2]

COUNTER_SOURCE = "examples/counter/app.py"
COUNTER_GEN = "client/transpile/counter.gen.js"
COUNTER_BANNER = (
    "// counter.gen.js — GENERATED from examples/counter/app.py (Mode C transpile)."
)


def write_counter() -> Path:
    """Regenerate the counter golden and write it to disk.

    Returns:
        The path the golden was written to.
    """
    generated = transpile_file(ROOT / COUNTER_SOURCE, banner=COUNTER_BANNER)
    out = ROOT / COUNTER_GEN
    out.write_text(generated, encoding="utf-8")
    return out


def main() -> None:
    """Regenerate every transpile golden and print its path."""
    print(f"wrote {write_counter()}")


if __name__ == "__main__":
    main()
