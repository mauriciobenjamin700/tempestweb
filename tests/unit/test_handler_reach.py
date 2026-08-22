"""Which widget handlers the client can actually reach (issue #77, item 1).

A widget declares a handler prop; the client decides whether any gesture ever
produces the wire event that resolves to it. When it does not, the handler is
**inert**: registered, documented, never called. The audit that found them wrote
the roster into an issue table by hand, with the emitted set as a literal:

    emitted = {"click","input","change","submit","tap","swipe","long_press",
               "scroll","navigate","resync","drag","drop","select","dismiss"}

That was true the day it was written. It aged in silence — `end_reached` and
`refresh` shipped, and the table went on listing `on_end_reached` and
`on_refresh` as missing, so the next reader either re-does finished work or
distrusts the whole table.

So the emitted set is **derived from the client**, not restated here, and the
inert roster is pinned. Wiring a handler fails this test until the roster is
updated — which is the moment to update the issue too.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import tempest_core.widgets as widgets
from tempest_core.widgets.base import Widget
from tempestweb.runtime.serialize import EVENT_TYPE_TO_HANDLER_PROPS

ROOT = Path(__file__).resolve().parents[2]
CLIENT = ROOT / "client"

#: A wire event type in a JS object literal, e.g. `type: "end_reached"`.
_TYPE_LITERAL = re.compile(r'type:\s*"([a-z][a-z_]*)"')

#: The `EVENT_TYPES` map, whose values are wire types written as `key: "value"`
#: rather than under a `type:` key.
_EVENT_TYPES_BLOCK = re.compile(
    r"EVENT_TYPES\s*=\s*Object\.freeze\(\{(.*?)\}\)", re.DOTALL
)
_MAP_VALUE = re.compile(r':\s*"([a-z][a-z_]*)"')

#: The service worker speaks to the page, not to the runtime: its `type:` keys
#: ("module", "window") are not wire events.
_NOT_EVENT_SURFACES = ("sw",)

#: Handlers no gesture reaches yet, as `(prop, widget)`. Shrinking this is the
#: work; every removal is a handler that started firing.
INERT: frozenset[tuple[str, str]] = frozenset(
    {
        ("on_complete", "PinInput"),
        ("on_double_tap", "DoubleTapHandler"),
        ("on_double_tap", "GestureDetector"),
        ("on_double_tap", "ScaleHandler"),
        ("on_double_tap", "ScaleHandlerWidget"),
        ("on_frame", "CameraPreview"),
        ("on_interaction", "InteractiveViewer"),
        ("on_page_change", "PageView"),
        ("on_pan", "PanHandler"),
        ("on_pan", "PanHandlerWidget"),
        ("on_reorder", "ReorderableList"),
        ("on_scale", "ScaleHandler"),
        ("on_scale", "ScaleHandlerWidget"),
        ("on_scan", "QrScanner"),
        ("on_validate", "FormField"),
    }
)


def _client_sources() -> list[Path]:
    """Return every client module that can emit a wire event.

    Returns:
        list[Path]: The JS sources, service worker excluded, in a stable order.
    """
    return [
        path
        for path in sorted(CLIENT.rglob("*.js"))
        if not any(
            part in _NOT_EVENT_SURFACES for part in path.relative_to(CLIENT).parts
        )
    ]


def emitted_types() -> set[str]:
    """Return every wire event type the client is able to send.

    Reads the sources rather than restating them, so a new event type counts the
    moment it is written and no list has to be remembered.

    Returns:
        set[str]: The wire event types found in the client.
    """
    found: set[str] = set()
    for path in _client_sources():
        source = path.read_text()
        found.update(_TYPE_LITERAL.findall(source))
        for block in _EVENT_TYPES_BLOCK.findall(source):
            found.update(_MAP_VALUE.findall(block))
    return found


def reachable_props(emitted: set[str]) -> set[str]:
    """Return every handler prop an emitted event can resolve to.

    Args:
        emitted (set[str]): The wire types the client can send.

    Returns:
        set[str]: The handler prop names those types reach, including the
        ``on_<type>`` fallback :func:`resolve_handler` applies.
    """
    routed = {
        prop
        for wire, props in EVENT_TYPE_TO_HANDLER_PROPS.items()
        if wire in emitted
        for prop in props
    }
    return routed | {f"on_{wire}" for wire in emitted}


def declared_handlers() -> set[tuple[str, str]]:
    """Return every ``(handler prop, widget name)`` the core declares.

    Returns:
        set[tuple[str, str]]: One entry per handler prop per widget.
    """
    pairs: set[tuple[str, str]] = set()
    for name in dir(widgets):
        obj = getattr(widgets, name)
        if not inspect.isclass(obj) or not issubclass(obj, Widget):
            continue
        fields = getattr(obj, "model_fields", None)
        if fields is None:
            continue
        pairs.update((field, name) for field in fields if field.startswith("on_"))
    return pairs


def test_the_client_emits_the_types_the_runtimes_intercept() -> None:
    """The reserved types are only reserved if something sends them."""
    emitted = emitted_types()

    for reserved in ("scroll", "navigate", "resync", "media"):
        assert reserved in emitted, reserved


def test_end_reached_and_refresh_are_wired() -> None:
    """Pins the two rows of the issue table that shipped.

    Kept as its own test so the reason they left the roster stays readable, and
    so a regression in ``lists.js`` names itself instead of showing up as a
    diff in a set.
    """
    emitted = emitted_types()

    assert "end_reached" in emitted
    assert "refresh" in emitted


def test_the_inert_roster_is_exactly_what_is_pinned() -> None:
    """The roster tracks the client, so it cannot rot the way the table did."""
    reachable = reachable_props(emitted_types())
    inert = {pair for pair in declared_handlers() if pair[0] not in reachable}

    started_firing = INERT - inert
    newly_inert = inert - INERT
    assert inert == INERT, (
        "the inert roster moved.\n"
        f"  started firing (drop from INERT, update #77): {sorted(started_firing)}\n"
        f"  newly inert (declared with no gesture): {sorted(newly_inert)}"
    )
