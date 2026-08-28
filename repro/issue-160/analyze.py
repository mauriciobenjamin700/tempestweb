"""Summarize the issue #160 reproduction runs into one table plus the evidence.

Reads each ``<label>.json`` the harness wrote and the matching ``req-<label>.log``
the backend wrote, and prints, per run: port, whether the service worker
registered, boot time to Pyodide-ready, how many assets it precached, when the
precache finished relative to the login click, and whether the client tree came
out intact or truncated.

Every ``patch path out of range`` line found is printed in full, together with
the client-tree outline the debug flag dumped next to it, because that is the
evidence the issue asks for.

Usage:
    uv run --frozen python analyze.py <results-dir> <label> [<label> ...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

#: The container child counts a healthy panel run must show. ``table_columns`` is
#: not here: the ``drain`` arm legitimately grows a ninth column at tick 3.
EXPECTED: dict[str, int] = {"filters_children": 4, "table_rows": 41}


def load(path: Path) -> dict[str, Any]:
    """Load one harness result file.

    Args:
        path: The ``<label>.json`` path.

    Returns:
        The parsed result, or an empty dict when the file is missing.
    """
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def precache_window(log: Path) -> tuple[float, float, int]:
    """Report when the service worker's precache traffic ran.

    Args:
        log: The backend's request log (one JSON object per line).

    Returns:
        ``(first, last, count)`` timestamps of requests whose ``Service-Worker``
        or ``Sec-Fetch-Dest`` marks them as worker-issued, and how many there
        were. ``(0.0, 0.0, 0)`` when none are found.
    """
    if not log.is_file():
        return (0.0, 0.0, 0)
    stamps: list[float] = []
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("dest") in {"", "empty"} and entry.get("path", "").startswith(
            ("/client/", "/icons/", "/app.py", "/bootstrap.js", "/register.js")
        ):
            stamps.append(float(entry["t"]))
    if not stamps:
        return (0.0, 0.0, 0)
    return (min(stamps), max(stamps), len(stamps))


def failed_patches(result: dict[str, Any]) -> list[str]:
    """Collect every console line reporting a patch the renderer refused.

    ``range_errors`` alone misses the runs recorded before the harness learned to
    render an ``Error`` argument (``JSON.stringify(new RangeError(...))`` is
    ``{}``), so the marker line is what is matched.

    Args:
        result: The harness result.

    Returns:
        The rendered console arguments of each failure, in order.
    """
    out: list[str] = []
    for entry in result.get("page_log") or []:
        joined = " ".join(arg["head"] for arg in entry["args"])
        if "patch could not be applied" in joined:
            out.append(joined)
    return out


def verdict(result: dict[str, Any]) -> str:
    """Classify one run's outcome from its measurements.

    Args:
        result: The harness result.

    Returns:
        ``"intact"``, ``"TRUNCATED"``, or a reason the run did not conclude.
    """
    if result.get("boot_ms") is None:
        return "no-boot"
    samples = result.get("samples") or []
    if not samples:
        return "no-samples"
    if failed_patches(result):
        return f"TRUNCATED ({len(failed_patches(result))} failed patch)"
    last = samples[-1]["dom"]
    for field, expected in EXPECTED.items():
        if last.get(field) != expected:
            return f"unexpected {field}={last.get(field)} (expected {expected})"
    return "intact"


def main() -> None:
    """Print the run table and every path-failure line found."""
    root = Path(sys.argv[1])
    labels = sys.argv[2:]
    print(
        f"{'run':<6} {'port':<6} {'sw':<4} {'boot_ms':>8} {'precache':>9} "
        f"{'sw_reqs':>8} {'actions':>8} {'result'}"
    )
    for label in labels:
        result = load(root / f"{label}.json")
        if not result:
            print(f"{label:<6} (missing)")
            continue
        caches = (result.get("sw_at_boot") or {}).get("caches") or {}
        entries = sum(caches.values()) if caches else 0
        _, _, count = precache_window(root / f"req-{label}.log")
        samples = result.get("samples") or []
        actions = samples[-1]["dom"]["appbar_actions_children"] if samples else None
        print(
            f"{label:<6} {result['port']:<6} "
            f"{str((result.get('sw_at_boot') or {}).get('registered')):<4} "
            f"{result.get('boot_ms') or -1:>8} {entries:>9} {count:>8} "
            f"{str(actions):>8} {verdict(result)}"
        )

    for label in labels:
        result = load(root / f"{label}.json")
        errors = failed_patches(result)
        if not errors:
            continue
        print(f"\n===== {label}: {len(errors)} path failure line(s) =====")
        damage = result.get("damage_at_failure")
        if damage is not None:
            print(f"DOM measured at the failure: {json.dumps(damage['dom'])}")
        for entry in result.get("page_log") or []:
            joined = " ".join(arg["head"] for arg in entry["args"])
            if "out of range" in joined or "client tree at failure" in joined:
                print(f"--- console.{entry['level']}")
                for arg in entry["args"]:
                    print(arg["head"])


if __name__ == "__main__":
    main()
