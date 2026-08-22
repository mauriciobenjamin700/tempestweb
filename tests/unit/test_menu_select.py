"""A menu selection reaches its ``on_select`` handler with the typed event.

``Menu``/``ActionSheet`` carry their choices in an ``items`` prop, so the client
draws them as renderer-owned buttons and reports a click as a ``select`` event
against the *menu's* key. This pins the server half: the event resolves to
``on_select`` and coerces into the ``MenuSelectEvent`` the widget declares.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi.testclient import TestClient

from tempest_core import App, Column, Text, Widget, build_scene
from tempest_core.widgets import ActionSheet, Menu, MenuItem
from tempest_core.widgets.events import MenuSelectEvent
from tempestweb.runtime.events import coerce_event
from tempestweb.runtime.serialize import find_node_type, resolve_handler
from tempestweb.server import create_app


@dataclass
class MenuState:
    """Values selected so far."""

    picked: list[str] = field(default_factory=list)


def make_state() -> MenuState:
    """Build a fresh state."""
    return MenuState()


def view(app: App[MenuState]) -> Widget:
    """Render a menu of two actions plus a label of what was picked."""

    def on_select(event: MenuSelectEvent) -> None:
        app.set_state(lambda s: s.picked.append(event.value))

    return Column(
        children=[
            Text(content=f"picked: {','.join(app.state.picked)}", key="picked"),
            Menu(
                key="row-menu",
                items=[
                    MenuItem(label="Copy", value="copy"),
                    MenuItem(label="Paste", value="paste"),
                ],
                on_select=on_select,
            ),
        ]
    )


def test_select_resolves_to_on_select() -> None:
    """A ``select`` event finds the menu's handler."""
    scene = build_scene(
        Menu(
            key="m",
            items=[MenuItem(label="Copy", value="copy")],
            on_select=lambda event: None,
        ),
        [],
    )
    assert resolve_handler(scene, "m", "select") is not None


def test_a_selection_coerces_to_a_menu_select_event() -> None:
    """The wire payload becomes the typed event the widget declares."""
    scene = build_scene(
        ActionSheet(
            key="sheet",
            title="Share via",
            items=[MenuItem(label="Email", value="email")],
            on_select=lambda event: None,
        ),
        [],
    )
    event = coerce_event(
        find_node_type(scene, "sheet"),
        "select",
        {"value": "email", "label": "Email"},
    )
    assert isinstance(event, MenuSelectEvent)
    assert event.value == "email"
    assert event.label == "Email"


def test_a_selection_drives_the_app_over_the_wire() -> None:
    """End to end: the client's ``select`` envelope updates the app's state."""
    with (
        TestClient(create_app(make_state, view)) as client,
        client.websocket_connect("/ws") as ws,
    ):
        ws.receive_json()
        ws.send_json(
            {
                "kind": "event",
                "data": {
                    "type": "select",
                    "key": "row-menu",
                    "payload": {"value": "paste", "label": "Paste"},
                },
            }
        )
        update = ws.receive_json()
        contents = [
            patch["set_props"]["content"]
            for patch in update["data"]
            if "content" in patch.get("set_props", {})
        ]
        assert contents == ["picked: paste"]
