"""Regenerate the Mode C routes_from_path parity fixture from the real core.

Run as a module to (re)write the golden::

    python -m tests.conformance._transpile_routes

`client/transpile/nav.js` `routesFromPath` is a port of
`tempest_core.navigation.routes_from_path`. This fixture pins, per path, the
route-name stack the core produces, so a JS test asserts the port matches.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tempest_core import routes_from_path

FIXTURES_DIR: Path = Path(__file__).resolve().parents[1] / "fixtures"
ROUTES_FIXTURE: Path = FIXTURES_DIR / "transpile_route_cases.json"

_PATHS: tuple[str, ...] = (
    "/",
    "/about",
    "/a/b/c",
    "/users/123",
    "/search?q=abc&page=2",
    "/user/123?tab=info",
    "",
)


def build_cases() -> list[dict[str, Any]]:
    """Build ``{path, names}`` cases (the route-name stack) from the core."""
    cases: list[dict[str, Any]] = []
    for path in _PATHS:
        names = [route.name for route in routes_from_path(path)]
        cases.append({"path": path, "names": names})
    return cases


def render_fixture_text() -> str:
    """Render the routes parity fixture as canonical JSON text."""
    return json.dumps(build_cases(), indent=2, ensure_ascii=False) + "\n"


def write_fixture() -> Path:
    """Write the routes parity fixture to disk and return its path."""
    ROUTES_FIXTURE.write_text(render_fixture_text(), encoding="utf-8")
    return ROUTES_FIXTURE


def main() -> None:
    """Regenerate the routes parity fixture and print its path."""
    print(f"wrote {write_fixture()}")


if __name__ == "__main__":
    main()
