"""Regenerate the conformance golden fixtures from the real core.

Run as a module to (re)write the goldens whenever the wire format intentionally
changes::

    python -m tests.conformance._generate

The test suite (:mod:`.test_wire_contract`) asserts the committed fixtures equal
what this module produces *right now*, so a drift between the core and the
goldens fails CI until the goldens are regenerated and reviewed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.conformance._scenarios import build_all_fixtures

FIXTURES_DIR: Path = Path(__file__).resolve().parents[1] / "fixtures"
CONFORMANCE_FIXTURE: Path = FIXTURES_DIR / "conformance_scenarios.json"


def render_fixture_text() -> str:
    """Render the conformance golden payload as canonical JSON text.

    Returns:
        Pretty-printed, key-sorted JSON with a trailing newline, so the file is
        diff-stable and regeneration is idempotent.
    """
    payload: dict[str, Any] = build_all_fixtures()
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_fixture() -> Path:
    """Write the conformance golden fixture to disk.

    Returns:
        The path the fixture was written to.
    """
    CONFORMANCE_FIXTURE.write_text(render_fixture_text(), encoding="utf-8")
    return CONFORMANCE_FIXTURE


def main() -> None:
    """Regenerate the conformance fixture and print its path."""
    path = write_fixture()
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
