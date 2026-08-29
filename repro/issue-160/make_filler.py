"""Generate the filler assets that stretch the service-worker precache.

The reproduction declares ``[wasm] assets = ["filler/*.json"]``, which puts every
file here into the artifact **and** into the worker's precache. 300 of them take
the precache from 93 to 393 entries, which is what makes ``cache.addAll`` still be
running when the app mounts — the overlap the "precache disputa conexões com o
boot" hypothesis needs, and which 93 assets on localhost never produce.

They are generated rather than committed: 300 near-identical files are noise in a
diff, and the only thing that matters about them is the count and that each one
answers 200.

Run:
    uv run --frozen python repro/issue-160/make_filler.py [count]
"""

from __future__ import annotations

import sys
from pathlib import Path

#: How many filler assets to write when the caller names no count.
DEFAULT_COUNT: int = 300

#: Bytes of padding in each file, so the request has a body worth reading.
PAD: str = "x" * 512


def main() -> None:
    """Write ``count`` filler JSON files under ``app/filler/``."""
    count = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_COUNT
    target = Path(__file__).parent / "app" / "filler"
    target.mkdir(parents=True, exist_ok=True)
    for existing in target.glob("chunk-*.json"):
        existing.unlink()
    for index in range(count):
        (target / f"chunk-{index:03d}.json").write_text(
            f'{{"filler": {index}, "pad": "{PAD}"}}', encoding="utf-8"
        )
    print(f"wrote {count} filler assets to {target}")


if __name__ == "__main__":
    main()
