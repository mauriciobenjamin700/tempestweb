"""Mode B end-to-end — the counter example served over WebSocket.

This test suite proves that the *exact same* ``make_state``/``view`` from
``examples/counter/app.py`` works unchanged when mounted on a FastAPI server
(Mode B).  It mirrors :mod:`tests.unit.test_server_ws` but uses the real
counter module instead of a local re-definition, demonstrating the "one view,
both modes" property of tempestweb.

The Starlette :class:`~fastapi.testclient.TestClient` drives the WebSocket
transport in-process, so no network port is opened and the suite is fully
deterministic.

Tests
-----
- :func:`test_initial_mount_receives_counter_zero` — the very first envelope
  after connecting contains the initial label ``"Count: 0"``.
- :func:`test_click_increments_counter` — sending a ``click`` event on key
  ``"inc"`` yields an Update patch that sets the label to ``"Count: 1"``.
- :func:`test_multiple_clicks_accumulate` — two successive clicks bring the
  label to ``"Count: 2"`` (stateful accumulation, not reset).
- :func:`test_decrement_via_dec_button` — clicking ``"dec"`` after three
  increments rolls the counter back to ``"Count: 2"``.
- :func:`test_two_connections_independent_state` — two simultaneous WebSocket
  connections own their own state; clicks on one do not leak to the other.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from examples.counter.app import make_state, view
from tempestweb.server import create_app

# ---------------------------------------------------------------------------
# Helpers (no dependencies — pure dict traversal)
# ---------------------------------------------------------------------------


def _find_label_content(node: dict[str, Any]) -> str | None:
    """Recursively find the ``label`` node's ``content`` prop in a wire tree.

    Args:
        node: A wire-format IR node (``{type, key, props, children}``).

    Returns:
        The ``content`` string if found, otherwise ``None``.
    """
    if node.get("key") == "label":
        content: Any = node["props"].get("content")
        return str(content) if content is not None else None
    for child in node.get("children", []):
        found = _find_label_content(child)
        if found is not None:
            return found
    return None


def _label_update(patches: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the Update patch whose ``set_props`` contains ``content``.

    The reconciler may emit additional patches (e.g. re-serialised handler
    props) alongside the label update.  This isolates the one we care about.

    Args:
        patches: The ``data`` list from a ``patches`` envelope.

    Returns:
        The first Update patch that carries a ``content`` key in ``set_props``.

    Raises:
        AssertionError: If no such patch is present.
    """
    for patch in patches:
        if "content" in patch.get("set_props", {}):
            return patch
    raise AssertionError(f"no label content update in {patches}")


# ---------------------------------------------------------------------------
# Fixtures / app instance
# ---------------------------------------------------------------------------
# Each test creates its own TestClient so sessions do not bleed across tests.


def _client() -> TestClient:
    """Build a fresh TestClient wrapping a Mode B counter app.

    Returns:
        A configured :class:`~fastapi.testclient.TestClient`.
    """
    return TestClient(create_app(make_state, view, title="test-counter"))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_initial_mount_receives_counter_zero() -> None:
    """Connecting receives one ``patches`` envelope with the initial counter label."""
    with _client().websocket_connect("/ws") as ws:
        initial = ws.receive_json()

    assert initial["kind"] == "patches", f"unexpected kind: {initial['kind']}"
    root = initial["data"][0]
    assert root["path"] == [], "initial patch must target the root (empty path)"
    assert _find_label_content(root["node"]) == "Count: 0"


def test_click_increments_counter() -> None:
    """A single ``click`` on ``"inc"`` drives the counter from 0 → 1."""
    with _client().websocket_connect("/ws") as ws:
        ws.receive_json()  # discard initial mount

        ws.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})

        update = ws.receive_json()

    assert update["kind"] == "patches"
    patch = _label_update(update["data"])
    assert patch["set_props"] == {"content": "Count: 1"}
    # The path is non-empty because it is an Update, not a full Replace.
    assert patch["path"] != []


def test_multiple_clicks_accumulate() -> None:
    """Two successive increments accumulate: 0 → 1 → 2."""
    with _client().websocket_connect("/ws") as ws:
        ws.receive_json()  # discard initial mount

        ws.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
        first = ws.receive_json()

        ws.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
        second = ws.receive_json()

    assert _label_update(first["data"])["set_props"] == {"content": "Count: 1"}
    assert _label_update(second["data"])["set_props"] == {"content": "Count: 2"}


def test_decrement_via_dec_button() -> None:
    """Clicking ``"dec"`` after three increments rolls the counter back to 2."""
    with _client().websocket_connect("/ws") as ws:
        ws.receive_json()  # discard initial mount

        for _ in range(3):
            ws.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
            ws.receive_json()  # consume each update

        ws.send_json({"kind": "event", "data": {"type": "click", "key": "dec"}})
        update = ws.receive_json()

    assert _label_update(update["data"])["set_props"] == {"content": "Count: 2"}


def test_two_connections_independent_state() -> None:
    """Two simultaneous WebSocket connections own fully isolated state.

    Connection A is clicked twice; connection B is never clicked and then
    clicked once.  B must yield ``Count: 1``, not ``Count: 3``.
    """
    client = _client()
    with (
        client.websocket_connect("/ws") as ws_a,
        client.websocket_connect("/ws") as ws_b,
    ):
        ws_a.receive_json()
        ws_b.receive_json()

        # Drive A up to 2.
        ws_a.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
        ws_a.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
        update_a1 = ws_a.receive_json()
        update_a2 = ws_a.receive_json()
        assert _label_update(update_a1["data"])["set_props"] == {"content": "Count: 1"}
        assert _label_update(update_a2["data"])["set_props"] == {"content": "Count: 2"}

        # B was never touched: its first click must yield Count: 1, not Count: 3.
        ws_b.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
        update_b = ws_b.receive_json()
        assert _label_update(update_b["data"])["set_props"] == {"content": "Count: 1"}
