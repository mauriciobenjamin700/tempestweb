"""Reconciliation microbenchmark (Track S — S9).

Times the hot path shared by every mode: ``build(view)`` → ``diff(old, new)``.
Run it directly::

    uv run python benchmarks/bench_reconcile.py
    uv run python benchmarks/bench_reconcile.py --rows 500 --iters 2000

It prints ops/sec for a full build and for a diff between two states of a
moderate list UI. It is a **runnable** benchmark, not a CI gate — a regression
gate (storing a baseline) is a Track-S follow-up.
"""

from __future__ import annotations

import argparse
import time

from tempest_core import Button, Column, Row, Style, Text, build, diff


def _view(rows: int, selected: int) -> Column:
    """Build a list-of-rows UI; ``selected`` toggles one row's style."""
    return Column(
        style=Style(gap=4.0),
        children=[
            Row(
                key=f"row-{i}",
                style=Style(gap=8.0),
                children=[
                    Text(content=f"Item {i}", key=f"label-{i}"),
                    Button(
                        label="pick" if i != selected else "picked",
                        key=f"btn-{i}",
                    ),
                ],
            )
            for i in range(rows)
        ],
    )


def _timed(label: str, iters: int, fn: object) -> None:
    """Run ``fn`` ``iters`` times and print ops/sec."""
    start = time.perf_counter()
    for _ in range(iters):
        fn()  # type: ignore[operator]
    elapsed = time.perf_counter() - start
    per_op_us = elapsed / iters * 1e6
    print(f"{label:28} {iters / elapsed:12,.0f} ops/s  ({per_op_us:8.2f} µs/op)")


def main() -> None:
    """Parse args and run the build + diff benchmarks."""
    parser = argparse.ArgumentParser(description="tempestweb reconcile benchmark")
    parser.add_argument("--rows", type=int, default=200, help="list rows")
    parser.add_argument("--iters", type=int, default=1000, help="iterations")
    args = parser.parse_args()

    old_tree = build(_view(args.rows, 0))
    new_tree = build(_view(args.rows, args.rows // 2))

    print(f"tempestweb reconcile benchmark — {args.rows} rows, {args.iters} iters\n")
    _timed("build(view)", args.iters, lambda: build(_view(args.rows, 0)))
    _timed("diff(old, new)", args.iters, lambda: diff(old_tree, new_tree))
    patches = diff(old_tree, new_tree)
    print(f"\ndiff produced {len(patches)} patch(es) for a single-row change.")


if __name__ == "__main__":
    main()
