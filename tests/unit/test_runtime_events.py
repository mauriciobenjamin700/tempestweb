"""Tests for wire-payload → typed-event coercion (runtime.events)."""

from __future__ import annotations

from tempest_core.widgets.events import SwipeEvent, TextChangeEvent

from tempestweb.runtime import coerce_event


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
