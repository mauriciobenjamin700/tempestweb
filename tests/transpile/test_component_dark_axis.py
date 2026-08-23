"""The dark half of the component matrix says what it actually covers.

The matrix builds every component twice, light and dark, and that second half is
the guard for tempestweb#106 — a port that forgets to pass the theme down to a
child fails on that child's colour. Except for thirteen cases where the two halves
are **byte-identical**, and for two different reasons that a reader cannot tell
apart by looking:

* the component has no colour of its own (``Grid``, ``HStack``, ``VStack``,
  ``StyledContainer``, ``Drawer``) — identical is the truth about it;
* the component cannot be themed at all (:data:`LIGHT_ONLY_COMPONENTS`) — the
  twin is a light case wearing a dark name, and proves nothing about dark.

The second kind is where the #106 bug would hide if it came back: a component that
*can* take a theme, drops it on the floor, and lands in the identical set looking
like the harmless first kind. This test pins the split, so a newly-identical pair
is a failure with a name on it instead of one more entry in a list nobody reads.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.conformance._transpile_components import (
    LIGHT_ONLY_COMPONENTS,
    _cases,
)

FIXTURE: Path = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "transpile_component_samples.json"
)


def _samples() -> dict[str, Any]:
    """The committed component-parity matrix.

    Returns:
        The scenario → serialized IR node map.
    """
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_every_case_has_a_dark_twin() -> None:
    """No case is built light-only: the dark axis covers the whole matrix."""
    samples = _samples()
    missing = [name for name in _cases() if f"{name}__dark" not in samples]
    assert missing == [], f"cases with no dark twin: {missing}"


def test_a_themable_component_actually_changes_in_dark() -> None:
    """A component that takes a theme and shows colour must differ in dark.

    This is the #106 assertion at component level. A themable component whose dark
    twin is identical either has no colour at all — true for the layout ones, and
    they say so by resolving no colour field — or dropped the theme before its
    children, which is the bug.
    """
    samples = _samples()
    offenders: list[str] = []
    for name, widget in _cases().items():
        if type(widget).__name__ in LIGHT_ONLY_COMPONENTS:
            continue
        light, dark = samples[name], samples[f"{name}__dark"]
        if light != dark:
            continue
        if not _has_colour(light):
            continue
        offenders.append(f"{name} ({type(widget).__name__})")
    assert offenders == [], (
        "these components take a theme and paint colour, yet their dark twin is "
        "identical to the light one — the theme is being dropped before the "
        f"children: {offenders}"
    )


def test_the_light_only_list_names_every_identical_themable_case() -> None:
    """Every identical pair is explained: no colour, or listed as light-only.

    The list cannot rot in either direction. A component that gains theming stops
    being identical and has to leave the list (the generator asserts that too); one
    that stops being themable fails the generator until it is added here with the
    reason.
    """
    samples = _samples()
    unexplained: list[str] = []
    for name, widget in _cases().items():
        component = type(widget).__name__
        if samples[name] != samples[f"{name}__dark"]:
            assert component not in LIGHT_ONLY_COMPONENTS, (
                f"{name}: {component} is listed as light-only but its dark twin "
                "differs — the list is stale, drop it from LIGHT_ONLY_COMPONENTS"
            )
            continue
        if component in LIGHT_ONLY_COMPONENTS or not _has_colour(samples[name]):
            continue
        unexplained.append(f"{name} ({component})")
    assert unexplained == [], f"identical pairs with no stated reason: {unexplained}"


def _has_colour(node: dict[str, Any]) -> bool:
    """Whether a serialized tree resolves any colour anywhere.

    Args:
        node: A serialized IR node.

    Returns:
        ``True`` when the node or a descendant carries a non-null colour field.
    """
    style = (node.get("props") or {}).get("style") or {}
    if any(style.get(field) is not None for field in ("background", "color")):
        return True
    return any(_has_colour(child) for child in node.get("children") or [])
