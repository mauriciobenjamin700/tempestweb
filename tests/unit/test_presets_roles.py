"""The drift guard between the preset roles and ``client/layouts.js``.

The feature is two halves in two languages: Python stamps ``data-tw-layout``
roles, CSS styles them. Nothing in either language notices when they stop
agreeing — a renamed role just silently loses its layout, in a way tests that
only build widget trees or only parse CSS would both call green. This module is
the seam that fails instead.
"""

from __future__ import annotations

import re
from pathlib import Path

from tempestweb.presets.roles import LAYOUT_ATTR, ROLES

SHEET = Path(__file__).resolve().parents[2] / "client" / "layouts.js"


def _styled_roles() -> set[str]:
    """Collect every role the stylesheet has a rule for.

    Returns:
        The role names appearing in ``[data-tw-layout="…"]`` selectors.
    """
    source = SHEET.read_text(encoding="utf-8")
    pattern = re.compile(rf'\[{re.escape(LAYOUT_ATTR)}="([a-z-]+)"\]')
    return set(pattern.findall(source))


def test_every_role_has_a_rule_in_the_sheet() -> None:
    """A role with no rule is a container that renders unstyled."""
    missing = sorted(ROLES - _styled_roles())
    assert not missing, f"roles with no rule in client/layouts.js: {missing}"


def test_the_sheet_styles_no_unknown_role() -> None:
    """A rule for a role nobody emits is dead CSS — usually a rename left behind."""
    extra = sorted(_styled_roles() - ROLES)
    assert not extra, f"client/layouts.js styles roles the presets never emit: {extra}"


def test_the_sheet_declares_the_responsive_behaviour_it_promises() -> None:
    """The breakpoints are the whole reason the sheet exists; assert they are there.

    Presets deliberately measure nothing at runtime, so if these media queries
    disappear the layout silently stops adapting instead of failing loudly.
    """
    source = SHEET.read_text(encoding="utf-8")
    assert "@media (max-width: 1023px)" in source, "sidebar collapse breakpoint"
    assert "@media (max-width: 639px)" in source, "phone breakpoint"
    assert "@media print" in source, "print rules"
    assert "@media (prefers-reduced-motion: reduce)" in source, "reduced motion"
