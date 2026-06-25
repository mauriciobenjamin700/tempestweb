"""Tests for wire-payload → typed-event coercion (runtime.events)."""

from __future__ import annotations

import importlib
import inspect
import pkgutil

import tempest_core
from tempest_core.widgets.base import Widget
from tempest_core.widgets.events import SwipeEvent, TextChangeEvent, ToggleEvent
from tempestweb.runtime import coerce_event
from tempestweb.runtime.events import _WIDGET_EVENT_TYPES
from tempestweb.runtime.serialize import EVENT_TYPE_TO_HANDLER_PROPS


def _widgets_with_schemas() -> dict[str, dict[str, type]]:
    """Collect every core widget class that declares event schemas.

    Returns:
        ``{widget_type: {handler_prop: EventClass}}`` over all importable core
        widget subclasses.
    """
    found: dict[str, dict[str, type]] = {}
    for module in pkgutil.walk_packages(tempest_core.__path__, "tempest_core."):
        try:
            imported = importlib.import_module(module.name)
        except Exception:  # noqa: BLE001 — optional submodules may not import bare
            continue
        for name in dir(imported):
            obj = getattr(imported, name)
            if (
                inspect.isclass(obj)
                and issubclass(obj, Widget)
                and getattr(obj, "event_schemas", None)
            ):
                found[obj.__name__] = dict(obj.event_schemas)
    return found


def test_coerce_gesture_swipe_payload() -> None:
    """A GestureDetector swipe payload becomes a typed SwipeEvent."""
    event = coerce_event(
        "GestureDetector", "swipe", {"direction": "right", "dx": 80, "dy": 4}
    )
    assert isinstance(event, SwipeEvent)
    assert event.direction == "right"
    assert event.dx == 80


def test_coerce_input_change_payload() -> None:
    """An Input change payload becomes a typed TextChangeEvent."""
    event = coerce_event("Input", "change", {"value": "hello"})
    assert isinstance(event, TextChangeEvent)
    assert event.value == "hello"


def test_coerce_input_live_typing_input_event() -> None:
    """The DOM ``input`` wire type (live typing) coerces like ``change``.

    Regression: the live ``input`` event aliases to ``on_change`` for routing, so
    it must also coerce to TextChangeEvent — otherwise a live-filtering handler
    receives the raw payload dict and ``event.value`` fails.
    """
    event = coerce_event("Input", "input", {"value": "admin"})
    assert isinstance(event, TextChangeEvent)
    assert event.value == "admin"


def test_coerce_checkbox_toggle_payload() -> None:
    """A Checkbox toggle payload becomes a typed ToggleEvent."""
    event = coerce_event("Checkbox", "toggle", {"checked": True})
    assert isinstance(event, ToggleEvent)
    assert event.checked is True


def test_coerce_checkbox_input_with_value_payload_falls_back() -> None:
    """A wire type aliased to on_change whose payload does not match falls back.

    A checkbox's DOM ``input`` carries a value, not ``checked``; it cannot validate
    as a ToggleEvent, so it degrades to the raw payload rather than crashing.
    """
    payload = {"value": "on"}
    assert coerce_event("Checkbox", "input", payload) is payload


def test_routing_and_coercion_maps_agree() -> None:
    """Every wire type that routes to a schema'd handler prop also coerces.

    Guards the two maps against drift: ``resolve_handler`` routes a wire event
    type to a handler prop via ``EVENT_TYPE_TO_HANDLER_PROPS``, and
    ``_WIDGET_EVENT_TYPES`` must carry the matching coercion entry for the same
    ``(widget, wire_type)`` — otherwise a routed handler silently receives the raw
    payload dict (the live-typing ``input`` bug).
    """
    schemas_by_widget = _widgets_with_schemas()
    gaps: list[tuple[str, str, str]] = []
    for wire_type, props in EVENT_TYPE_TO_HANDLER_PROPS.items():
        for prop in props:
            for widget_name, schema in schemas_by_widget.items():
                if prop not in schema:
                    continue
                coerced = _WIDGET_EVENT_TYPES.get(widget_name, {}).get(wire_type)
                if coerced is not schema[prop]:
                    gaps.append((widget_name, wire_type, prop))
    assert not gaps, f"routing/coercion drift for {gaps}"


def test_coerce_unknown_widget_returns_raw_payload() -> None:
    """A widget/event with no declared schema keeps the raw payload dict."""
    payload = {"anything": 1}
    assert coerce_event("Column", "click", payload) is payload


def test_coerce_none_node_type_returns_raw_payload() -> None:
    """An unknown node type (no key match) passes the payload through."""
    payload = {"x": 1.0}
    assert coerce_event(None, "tap", payload) is payload


def test_coerce_invalid_payload_falls_back_to_raw() -> None:
    """A payload that fails validation falls back to the raw dict, not a crash."""
    payload = {"direction": "sideways"}  # not a valid SwipeDirection
    assert coerce_event("GestureDetector", "swipe", payload) is payload
