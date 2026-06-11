"""Mode B WebSocket transport — end-to-end through the FastAPI host.

Drives the real :func:`tempestweb.server.create_app` with a counter ``view`` over
the Starlette test client's WebSocket, asserting the full B1/B2 loop:

- connect = mount → the client receives the initial ``patches`` envelope;
- a ``click`` event flows up and the resulting ``Update`` patch flows back;
- two simultaneous connections keep fully independent state.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from tempestweb._core import App, Button, Column, Text, Widget
from tempestweb.server import create_app


@dataclass
class CounterState:
    """Counter state for the test app."""

    value: int = 0


def make_state() -> CounterState:
    """Build a fresh counter state."""
    return CounterState()


def view(app: App[CounterState]) -> Widget:
    """Render the counter: a label and a single increment button."""

    def increment() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    return Column(
        children=[
            Text(content=f"Count: {app.state.value}", key="label"),
            Button(label="+", on_click=increment, key="inc"),
        ]
    )


def _find_label_content(node: dict) -> str | None:
    """Find the ``label`` node's ``content`` prop in a wire node tree."""
    if node.get("key") == "label":
        return node["props"].get("content")
    for child in node.get("children", []):
        found = _find_label_content(child)
        if found is not None:
            return found
    return None


def _label_update(patches: list[dict]) -> dict:
    """Return the Update patch that sets the label ``content``.

    The reconciler may also re-emit the button's handler prop each tick (a fresh
    closure diffs as changed); this isolates the meaningful label patch.

    Args:
        patches: A ``patches`` envelope's ``data`` list.

    Returns:
        The first Update patch carrying a ``content`` in ``set_props``.
    """
    for patch in patches:
        if "content" in patch.get("set_props", {}):
            return patch
    raise AssertionError(f"no label content update in {patches}")


def test_ws_initial_patches_and_click_update() -> None:
    """Connect → receive initial mount → click → receive the Update patch."""
    client = TestClient(create_app(make_state, view))
    with client.websocket_connect("/ws") as ws:
        initial = ws.receive_json()
        assert initial["kind"] == "patches"
        root_patch = initial["data"][0]
        assert root_patch["path"] == []
        assert _find_label_content(root_patch["node"]) == "Count: 0"

        ws.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})

        update = ws.receive_json()
        assert update["kind"] == "patches"
        patch = _label_update(update["data"])
        assert patch["set_props"] == {"content": "Count: 1"}
        assert patch["path"] == [0]


def test_ws_two_connections_keep_independent_state() -> None:
    """Two connections each own their counter; one click never leaks across."""
    client = TestClient(create_app(make_state, view))
    with (
        client.websocket_connect("/ws") as ws_a,
        client.websocket_connect("/ws") as ws_b,
    ):
        ws_a.receive_json()
        ws_b.receive_json()

        ws_a.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
        ws_a.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
        update_a1 = ws_a.receive_json()
        update_a2 = ws_a.receive_json()
        assert _label_update(update_a1["data"])["set_props"] == {"content": "Count: 1"}
        assert _label_update(update_a2["data"])["set_props"] == {"content": "Count: 2"}

        # B was never clicked: its first click yields Count: 1, not 3.
        ws_b.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
        update_b = ws_b.receive_json()
        assert _label_update(update_b["data"])["set_props"] == {"content": "Count: 1"}


def test_ws_unknown_key_is_ignored() -> None:
    """A click on a non-existent key produces no patch and does not crash."""
    client = TestClient(create_app(make_state, view))
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_json({"kind": "event", "data": {"type": "click", "key": "ghost"}})
        # A real click after the ignored one still yields exactly Count: 1.
        ws.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
        update = ws.receive_json()
        assert _label_update(update["data"])["set_props"] == {"content": "Count: 1"}
