"""End-to-end transpile test for the canonical Mode C tour example.

`examples/transpile-tour/app.py` exercises the whole app-layer surface at once —
state + methods, navigation, i18n, theme + responsiveness, a validated form, and
an imperative animation. This locks that the example transpiles cleanly through
the real path and that its cross-cutting features route to the right JS modules,
so the "tour" the docs point users to never drifts from a working build.
"""

from __future__ import annotations

from pathlib import Path

from tempestweb.transpile import transpile_file

ROOT = Path(__file__).resolve().parents[2]
TOUR_SOURCE = ROOT / "examples" / "transpile-tour" / "app.py"


def test_tour_transpiles_and_routes_features() -> None:
    """The tour transpiles and each feature imports from its native module."""
    js = transpile_file(TOUR_SOURCE)
    # Every cross-cutting concern routes to the right native module.
    assert 'from "./i18n.js"' in js
    assert 'from "./nav.js"' in js
    assert 'from "./theme.js"' in js
    assert 'from "./animation.js"' in js
    assert 'from "./validators.js"' in js
    assert 'from "./widgets.js"' in js


def test_tour_hoists_block_assigned_names() -> None:
    """`body`/`width`, assigned inside `if`/`else`, hoist to a function-top let.

    A JS `const` inside the branch would trap them there, breaking the trailing
    `return Column(... body ...)`. Top-level-only names (e.g. `loc`) stay `const`.
    """
    js = transpile_file(TOUR_SOURCE)
    assert "let body, width;" in js
    assert "const loc = new Locale(" in js
    # The hoisted names are re-assigned (not re-declared) inside the branches.
    assert "    body = " in js
    assert "    width = " in js
