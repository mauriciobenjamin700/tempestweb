"""Drag and drop routes to a widget's ``on_drag`` / ``on_drop`` handler.

The core declares both handlers (and the ``DragEvent`` they receive), the client
now captures the HTML5 drag events — but nothing joined the two: the wire event
types ``drag`` and ``drop`` were absent from the routing table, so a dropped card
resolved to no handler and was silently ignored.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi.testclient import TestClient

from tempest_core import App, Column, Text, Widget, build_scene
from tempest_core.widgets import Draggable, DragTarget
from tempest_core.widgets.events import DragEvent
from tempestweb.runtime.events import coerce_event
from tempestweb.runtime.serialize import find_node_type, resolve_handler
from tempestweb.server import create_app


@dataclass
class BoardState:
    """Cards currently in the drop column."""

    dropped: list[str] = field(default_factory=list)


def make_state() -> BoardState:
    """Build a fresh board state."""
    return BoardState()


def view(app: App[BoardState]) -> Widget:
    """Render one draggable card and one drop target."""

    def on_drop(event: DragEvent) -> None:
        app.set_state(lambda s: s.dropped.append(event.data))

    return Column(
        children=[
            Draggable(
                key="drag-c1",
                drag_data="c1:Backlog",
                child=Text(content="a card", key="card-c1"),
            ),
            DragTarget(
                key="drop-Done",
                on_drop=on_drop,
                child=Text(content=f"dropped: {len(app.state.dropped)}", key="count"),
            ),
        ]
    )


def test_drag_and_drop_resolve_to_their_handlers() -> None:
    """``drag`` reaches ``on_drag`` and ``drop`` reaches ``on_drop``."""
    scene = build_scene(
        Column(
            children=[
                Draggable(
                    key="d1",
                    drag_data="c1:Backlog",
                    on_drag=lambda event: None,
                    child=Text(content="card", key="t1"),
                ),
                DragTarget(
                    key="t-done",
                    on_drop=lambda event: None,
                    child=Text(content="Done", key="t2"),
                ),
            ]
        ),
        [],
    )
    assert resolve_handler(scene, "d1", "drag") is not None
    assert resolve_handler(scene, "t-done", "drop") is not None


def test_a_drop_payload_coerces_to_a_drag_event() -> None:
    """The wire payload becomes the typed ``DragEvent`` the handler declares."""
    scene = build_scene(
        DragTarget(
            key="t-done",
            on_drop=lambda event: None,
            child=Text(content="Done", key="t2"),
        ),
        [],
    )
    event = coerce_event(
        find_node_type(scene, "t-done"),
        "drop",
        {"data": "c1:Backlog", "x": 10.0, "y": 20.0},
    )
    assert isinstance(event, DragEvent)
    assert event.data == "c1:Backlog"
    assert event.x == 10.0


def test_a_dropped_card_reaches_the_app_over_the_wire() -> None:
    """End to end: the client's ``drop`` envelope drives the app's state."""
    with (
        TestClient(create_app(make_state, view)) as client,
        client.websocket_connect("/ws") as ws,
    ):
        ws.receive_json()
        ws.send_json(
            {
                "kind": "event",
                "data": {
                    "type": "drop",
                    "key": "drop-Done",
                    "payload": {"data": "c1:Backlog", "x": 1.0, "y": 2.0},
                },
            }
        )
        update = ws.receive_json()
        assert update["kind"] == "patches"
        contents = [
            patch["set_props"]["content"]
            for patch in update["data"]
            if "content" in patch.get("set_props", {})
        ]
        assert contents == ["dropped: 1"]
