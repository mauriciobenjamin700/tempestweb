"""The CI performance gate (Track S — S9).

``bench_reconcile.py`` measures the hot path and prints numbers; nothing ran it in
CI, so a change that doubled the cost of ``diff`` passed every gate this repo has —
ruff, mypy, pytest and jsdom all check correctness, none checks time
(tempestweb#120).

The hard part of a perf gate is not measuring, it is **not being a flake**. A
shared CI runner varies by more than the regressions worth catching, so an absolute
threshold either fires on noise (and gets disabled in the first week) or is set so
loose it catches nothing. This gate therefore asserts three things that survive a
slow runner:

1. **Scale.** Doubling the row count must not more than ~2.6x the cost. An
   accidental ``O(n^2)`` shows up as ~4x, and the ratio is immune to how fast the
   machine is — both measurements run on the same one, back to back.
   The same idea covers Mode B: N sessions must sustain roughly the **total**
   throughput of one, because the loop is single-threaded and the rebuild is
   CPU-bound. A drop there is contention, not load.
2. **The minimal patch.** One changed row must still produce two patches. That is
   the reconciler's contract, and the cheapest way to make ``diff`` look fast is to
   stop being correct.
3. **Relative cost.** ``diff`` normalized by a calibration loop measured in the
   same process, compared against a versioned baseline with a wide tolerance. The
   calibration divides out CPU speed, so what is left is the algorithm.

Run it locally exactly as CI does::

    uv run python benchmarks/perf_gate.py
    uv run python benchmarks/perf_gate.py --update-baseline   # after a real change
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from benchmarks.bench_ws_throughput import measure as ws_throughput
from tempest_core import Button, Column, Row, Style, Text, build, diff

BASELINE: Path = Path(__file__).resolve().parent / "baseline.json"

#: Rows for the two scale points. The pair is what makes the ratio meaningful.
SMALL_ROWS: int = 200
LARGE_ROWS: int = 400

#: Rounds per measurement; the **fastest** of these is what the gate reads. One
#: sample is a coin flip on a shared runner, and the median is not enough either:
#: interference can hold for most of a window. Since noise only ever *adds* time,
#: the minimum is the least-biased estimate of what the code actually costs — and
#: the ratio between two sizes measured that way is what the scale check needs.
#: Measured: a CI runner reported a median diff ratio of **2.85x** (over the 2.6
#: limit, so the job failed) on the same tree that scales **2.01–2.04x** locally
#: across three runs — its 400-row window was preempted, and half the rounds
#: carried it, so the median carried it too.
ROUNDS: int = 5

#: Iterations inside one round. A build costs ~50x a diff, so they do not get the
#: same count — the gate has to finish inside a PR's patience.
ITERS_BUILD: int = 12
ITERS_DIFF: int = 120

#: Doubling the rows may cost at most this much more. Linear is 2.0; the headroom
#: absorbs allocator and cache effects. An O(n^2) lands near 4.0.
MAX_SCALE_RATIO: float = 2.6

#: How much worse than the baseline a normalized cost may be before failing. Wide
#: on purpose: the calibration removes CPU speed, not every source of variance.
#: Measured on three GitHub runners with the same code, one build cost 975.8,
#: 1130.9 and 1206.9 units against the 667.7 baseline taken on a developer
#: machine — and the run whose calibration unit was *fastest* (64 us against
#: 104 us) reported the *highest* cost, which is the calibration loop and the
#: reconciler not scaling together across machines. At 1.8 the check sat 0.4%
#: from red on a green tree, so it is a coarse tripwire by construction: 2.5x
#: still catches a doubling, and MAX_SCALE_RATIO above is the half of the gate
#: that is machine-invariant.
MAX_RELATIVE_REGRESSION: float = 2.5

#: Sessions and events for the Mode B throughput check (see bench_ws_throughput).
SESSIONS: int = 4
SESSION_EVENTS: int = 40
SESSION_ROWS: int = 30

#: Total throughput with N sessions, as a fraction of one session alone. Mode B is
#: a single event loop and the rebuild is CPU-bound, so the *total* stays roughly
#: flat while the per-session share divides — that is the shape being pinned. A
#: drop below this means real contention was added (a global lock, per-session
#: work that is not per-session), not just more clients.
MIN_CONCURRENT_RATIO: float = 0.6


def _view(rows: int, selected: int) -> Column:
    """Build the benchmark's list UI.

    Args:
        rows: How many rows to build.
        selected: Which row renders as picked (the single change the diff sees).

    Returns:
        The column of rows.
    """
    return Column(
        style=Style(gap=4.0),
        children=[
            Row(
                key=f"row-{i}",
                style=Style(gap=8.0),
                children=[
                    Text(content=f"Item {i}", key=f"label-{i}"),
                    Button(label="pick" if i != selected else "picked", key=f"btn-{i}"),
                ],
            )
            for i in range(rows)
        ],
    )


def _fastest_us(operation: Callable[[], object], iters: int) -> float:
    """Fastest microseconds per operation over :data:`ROUNDS` rounds.

    The minimum, not the median: a preempted round can only be *slower* than the
    code is, never faster, so the fastest round is the least-biased estimate of
    the real cost — and the one that keeps the scale ratio meaningful on a shared
    runner (see :data:`ROUNDS`).

    Args:
        operation: The callable to time.
        iters: Iterations inside each round.

    Returns:
        The fastest cost per call, in microseconds.
    """
    samples: list[float] = []
    for _ in range(ROUNDS):
        start = time.perf_counter()
        for _ in range(iters):
            operation()
        samples.append((time.perf_counter() - start) / iters * 1e6)
    return min(samples)


def _calibration_us() -> float:
    """Time a fixed unit of pure-Python work, to divide out CPU speed.

    The gate compares ``diff`` against *this machine's* speed rather than against
    a wall-clock number recorded on someone else's. A runner that is 3x slower
    scales both sides.

    Returns:
        The fastest cost of one calibration unit, in microseconds.
    """

    def unit() -> int:
        total = 0
        for i in range(2000):
            total += i * i % 7
        return total

    return _fastest_us(unit, ITERS_DIFF)


def measure() -> dict[str, Any]:
    """Measure the reconciler's hot path.

    Returns:
        The measurements: per-op fastest rounds, the scale ratios, the patch count for a
        single-row change, and the calibrated (unit-free) costs.
    """
    small_old = build(_view(SMALL_ROWS, 0))
    small_new = build(_view(SMALL_ROWS, SMALL_ROWS // 2))
    large_old = build(_view(LARGE_ROWS, 0))
    large_new = build(_view(LARGE_ROWS, LARGE_ROWS // 2))

    calibration = _calibration_us()
    build_small = _fastest_us(lambda: build(_view(SMALL_ROWS, 0)), ITERS_BUILD)
    build_large = _fastest_us(lambda: build(_view(LARGE_ROWS, 0)), ITERS_BUILD)
    diff_small = _fastest_us(lambda: diff(small_old, small_new), ITERS_DIFF)
    diff_large = _fastest_us(lambda: diff(large_old, large_new), ITERS_DIFF)
    throughput = asyncio.run(ws_throughput(SESSION_ROWS, SESSION_EVENTS, SESSIONS))

    return {
        "calibration_us": calibration,
        "build_us": {"small": build_small, "large": build_large},
        "diff_us": {"small": diff_small, "large": diff_large},
        "scale": {
            "build": build_large / build_small,
            "diff": diff_large / diff_small,
        },
        "calibrated": {
            "build": build_small / calibration,
            "diff": diff_small / calibration,
        },
        "patches_for_one_change": len(diff(small_old, small_new)),
        "throughput": throughput,
    }


def check(measured: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    """Compare a measurement against the baseline and the invariants.

    Args:
        measured: The output of :func:`measure`.
        baseline: The versioned baseline (``benchmarks/baseline.json``).

    Returns:
        The failures, empty when the gate passes.
    """
    failures: list[str] = []

    for label, ratio in measured["scale"].items():
        if ratio > MAX_SCALE_RATIO:
            failures.append(
                f"{label} scales {ratio:.2f}x for 2x the rows "
                f"(limit {MAX_SCALE_RATIO}) — that is super-linear, and the "
                f"usual cause is an accidental O(n^2)"
            )

    expected_patches = baseline["patches_for_one_change"]
    if measured["patches_for_one_change"] != expected_patches:
        failures.append(
            f"a single-row change produced {measured['patches_for_one_change']} "
            f"patch(es), not {expected_patches} — the reconciler stopped emitting "
            "the minimal patch, which is the contract the whole wire rests on"
        )

    ratio = (
        measured["throughput"]["concurrent_eps"] / measured["throughput"]["single_eps"]
    )
    if ratio < MIN_CONCURRENT_RATIO:
        failures.append(
            f"{SESSIONS} sessions together sustain only {ratio:.2f}x the total "
            f"throughput of one alone (floor {MIN_CONCURRENT_RATIO}) — the loop is "
            "single-threaded, so the total should stay roughly flat; a drop means "
            "contention was added, not that there are more clients"
        )

    for label, calibrated in measured["calibrated"].items():
        recorded = baseline["calibrated"][label]
        allowed = recorded * MAX_RELATIVE_REGRESSION
        if calibrated > allowed:
            failures.append(
                f"{label} costs {calibrated:.1f} calibration units, baseline "
                f"{recorded:.1f} (limit {allowed:.1f}) — {calibrated / recorded:.2f}x "
                "slower relative to this machine's own speed"
            )

    return failures


def report(measured: dict[str, Any], baseline: dict[str, Any] | None) -> None:
    """Print the measurement in a form a human can compare across runs.

    Args:
        measured: The output of :func:`measure`.
        baseline: The baseline, or None when there is none yet.
    """
    print(f"calibration unit: {measured['calibration_us']:.1f} us\n")
    for label in ("build", "diff"):
        small = measured[f"{label}_us"]["small"]
        large = measured[f"{label}_us"]["large"]
        calibrated = measured["calibrated"][label]
        recorded = None if baseline is None else baseline["calibrated"][label]
        against = "" if recorded is None else f"  (baseline {recorded:.1f})"
        print(
            f"{label:6} {SMALL_ROWS:4} rows: {small:9.1f} us | "
            f"{LARGE_ROWS:4} rows: {large:9.1f} us | "
            f"scale {measured['scale'][label]:.2f}x | "
            f"{calibrated:.1f} units{against}"
        )
    print(f"\nsingle-row change → {measured['patches_for_one_change']} patch(es)")
    throughput = measured["throughput"]
    print(
        f"Mode B: one session {throughput['single_eps']:,.0f} events/s | "
        f"{SESSIONS} together {throughput['concurrent_eps']:,.0f} events/s total "
        f"({throughput['per_session_eps']:,.0f} each)"
    )


def main() -> int:
    """Run the gate.

    Returns:
        The process exit code: 0 when the gate passes.
    """
    parser = argparse.ArgumentParser(description="tempestweb performance gate")
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="record this run as the new baseline (review the diff!)",
    )
    args = parser.parse_args()

    measured = measure()
    baseline = (
        json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else None
    )
    report(measured, baseline)

    if args.update_baseline or baseline is None:
        BASELINE.write_text(
            json.dumps(
                {
                    "calibrated": {
                        key: round(value, 2)
                        for key, value in measured["calibrated"].items()
                    },
                    "patches_for_one_change": measured["patches_for_one_change"],
                    "rows": {"small": SMALL_ROWS, "large": LARGE_ROWS},
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"\nbaseline written to {BASELINE}")
        return 0

    failures = check(measured, baseline)
    if failures:
        print("\nperformance gate FAILED:\n")
        for failure in failures:
            print(f"  • {failure}")
        print(
            "\nIf the change is deliberate and the new cost is justified, rerun with "
            "--update-baseline and say why in the PR."
        )
        return 1

    print("\nperformance gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
