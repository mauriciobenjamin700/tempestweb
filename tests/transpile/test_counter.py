"""Golden test: the Mode C transpiler reproduces the committed counter.gen.js.

The committed `client/transpile/counter.gen.js` is a regenerable golden derived
from `examples/counter/app.py`. If the transpiler's output drifts from it, this
fails until the golden is regenerated (`python -m tests.transpile._generate`) and
reviewed — the same guarantee the wire-contract fixtures use.
"""

from __future__ import annotations

from pathlib import Path

from tempestweb.transpile import transpile_file
from tests.transpile._generate import COUNTER_BANNER, COUNTER_GEN, COUNTER_SOURCE

ROOT = Path(__file__).resolve().parents[2]


def test_counter_matches_committed_golden() -> None:
    """The transpiler output byte-matches the committed counter.gen.js."""
    generated = transpile_file(ROOT / COUNTER_SOURCE, banner=COUNTER_BANNER)
    on_disk = (ROOT / COUNTER_GEN).read_text(encoding="utf-8")
    assert generated == on_disk, (
        f"{COUNTER_GEN} is stale — regenerate with "
        "`python -m tests.transpile._generate` and review the diff"
    )
