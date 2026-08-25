"""The performance gate's rules, and proof that each one bites.

A perf gate nobody has seen fail is a perf gate nobody knows works — and this one
is deliberately built out of ratios rather than wall-clock numbers, so its rules
are worth testing directly instead of hoping a slow runner exercises them.

Each test feeds ``check`` a measurement shaped like a real one and asserts the
failure it should produce. The measurement itself (``measure``) is what CI runs;
timing it here would make the suite slow and flaky for no gain.
"""

from __future__ import annotations

import json
from typing import Any

from benchmarks.perf_gate import BASELINE, MAX_SCALE_RATIO, check


def _baseline() -> dict[str, Any]:
    """The committed baseline.

    Returns:
        The parsed ``benchmarks/baseline.json``.
    """
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def _healthy(baseline: dict[str, Any]) -> dict[str, Any]:
    """A measurement that should pass, shaped like a real one.

    Args:
        baseline: The committed baseline to match.

    Returns:
        The measurement dict ``check`` consumes.
    """
    return {
        "calibration_us": 90.0,
        "build_us": {"small": 50_000.0, "large": 101_000.0},
        "diff_us": {"small": 1_800.0, "large": 3_650.0},
        "scale": {"build": 2.02, "diff": 2.03},
        "calibrated": dict(baseline["calibrated"]),
        "patches_for_one_change": baseline["patches_for_one_change"],
        "throughput": {
            "single_eps": 1000.0,
            "concurrent_eps": 980.0,
            "per_session_eps": 245.0,
            "degradation": 4.08,
        },
    }


def test_a_healthy_measurement_passes() -> None:
    """The committed baseline plus linear scaling is a pass."""
    baseline = _baseline()
    assert check(_healthy(baseline), baseline) == []


def test_a_quadratic_diff_fails_on_scale() -> None:
    """Doubling the rows and quadrupling the cost is the O(n^2) signature."""
    baseline = _baseline()
    measured = _healthy(baseline)
    measured["scale"]["diff"] = 4.1

    failures = check(measured, baseline)

    assert len(failures) == 1
    assert "diff scales 4.10x" in failures[0]
    assert "O(n^2)" in failures[0]


def test_scaling_just_under_the_limit_is_allowed() -> None:
    """The limit is a limit, not a target: 2.5x passes, 2.7x does not."""
    baseline = _baseline()
    ok = _healthy(baseline)
    ok["scale"]["build"] = MAX_SCALE_RATIO - 0.1
    assert check(ok, baseline) == []

    bad = _healthy(baseline)
    bad["scale"]["build"] = MAX_SCALE_RATIO + 0.1
    assert len(check(bad, baseline)) == 1


def test_losing_the_minimal_patch_fails() -> None:
    """A diff that stops emitting the minimal patch fails, however fast it got.

    The cheapest way to make a reconciler look quick is to stop being right — a
    full replace is one patch and no comparison. The gate refuses to reward it.
    """
    baseline = _baseline()
    measured = _healthy(baseline)
    measured["patches_for_one_change"] = 1

    failures = check(measured, baseline)

    assert len(failures) == 1
    assert "minimal patch" in failures[0]


def test_a_relative_slowdown_beyond_the_tolerance_fails() -> None:
    """Three times the calibrated cost is a regression, not runner noise."""
    baseline = _baseline()
    measured = _healthy(baseline)
    measured["calibrated"]["diff"] = baseline["calibrated"]["diff"] * 3.0

    failures = check(measured, baseline)

    assert len(failures) == 1
    assert "calibration units" in failures[0]
    assert "3.00x" in failures[0]


def test_noise_within_the_tolerance_passes() -> None:
    """The spread between machines must not fail the build.

    1.81x is not hypothetical: it is what a CI runner reported for the very build
    the developer machine measured into the baseline, on identical code. Pinning
    it here means a future tightening of MAX_RELATIVE_REGRESSION fails this test
    instead of turning main red on the next merge.
    """
    baseline = _baseline()
    measured = _healthy(baseline)
    measured["calibrated"]["build"] = baseline["calibrated"]["build"] * 1.81

    assert check(measured, baseline) == []


def test_contention_between_sessions_fails() -> None:
    """N sessions must sustain the total throughput of one.

    Mode B is one event loop and the rebuild is CPU-bound, so the total stays
    roughly flat while the per-session share divides. A total that collapses means
    contention was added — a lock held across a rebuild, per-session work that is
    not per-session.
    """
    baseline = _baseline()
    measured = _healthy(baseline)
    measured["throughput"]["concurrent_eps"] = 300.0

    failures = check(measured, baseline)

    assert len(failures) == 1
    assert "sessions together sustain only 0.30x" in failures[0]
    assert "contention" in failures[0]


def test_the_committed_baseline_has_the_shape_the_gate_reads() -> None:
    """A baseline missing a key would make the gate crash instead of judge."""
    baseline = _baseline()
    assert set(baseline["calibrated"]) == {"build", "diff"}
    assert baseline["patches_for_one_change"] == 2
    assert baseline["rows"] == {"small": 200, "large": 400}
