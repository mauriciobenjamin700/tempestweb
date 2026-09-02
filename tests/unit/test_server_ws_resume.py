"""Mode B WebSocket session resume (#203).

Before this, the two transports of the same mode disagreed about what a reconnect
means. SSE reconnected and **resumed**; WebSocket reconnected onto a fresh
``AppSession``, so a 400 ms blip reset the user's state — a half-filled form, a
cart, the selected tab — and the client had no way to tell that from a first load.

What is asserted here is the behaviour, not the plumbing: after a drop and a
reconnect carrying the same id, *the counter is still 7*. Plus the three failure
modes the SSE path already paid for — an id is not an authorization, a takeover
must survive the old socket unwinding, and a session nobody comes back for cannot
pin state forever.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from tempest_core import App, Button, Column, Text, Widget
from tempestweb.server import create_app
from tempestweb.server.app import TempestWebServer


@dataclass
class CounterState:
    """Counter state for the test app."""

    value: int = 0


def make_state() -> CounterState:
    """Build a fresh counter state.

    Returns:
        A counter starting at zero.
    """
    return CounterState()


def view(app: App[CounterState]) -> Widget:
    """Render the counter: a label and a single increment button.

    Args:
        app: The app whose state is rendered.

    Returns:
        The counter tree.
    """

    def increment() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    return Column(
        children=[
            Text(content=f"Count: {app.state.value}", key="label"),
            Button(label="+", on_click=increment, key="inc"),
        ]
    )


def _label_content(node: dict) -> str | None:
    """Find the ``label`` node's ``content`` prop in a wire node tree.

    Args:
        node: A wire node.

    Returns:
        The label's content, or ``None`` when the subtree has no label.
    """
    if node.get("key") == "label":
        content = node["props"].get("content")
        return str(content) if content is not None else None
    for child in node.get("children", []):
        found = _label_content(child)
        if found is not None:
            return found
    return None


def _mounted_label(envelope: dict) -> str | None:
    """Read the label out of a full-tree ``patches`` envelope.

    Args:
        envelope: A ``patches`` envelope carrying a root replace.

    Returns:
        The label's content in the mounted scene.
    """
    assert envelope["kind"] == "patches"
    root = envelope["data"][0]
    assert root["path"] == []
    return _label_content(root["node"])


def _click(ws: object, times: int = 1) -> None:
    """Send ``times`` clicks on the increment button and drain the replies.

    Args:
        ws: The test client's WebSocket session.
        times: How many clicks to send.
    """
    for _ in range(times):
        ws.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})  # type: ignore[attr-defined]
        ws.receive_json()  # type: ignore[attr-defined]


def test_reconnect_with_the_same_id_keeps_the_state() -> None:
    """The counter is still 7 after the socket drops and comes back."""
    client = TestClient(create_app(make_state, view))
    with client:
        with client.websocket_connect("/ws?session=abc") as ws:
            assert _mounted_label(ws.receive_json()) == "Count: 0"
            _click(ws, times=7)

        with client.websocket_connect("/ws?session=abc") as ws:
            assert _mounted_label(ws.receive_json()) == "Count: 7"


def test_reconnect_resumes_as_a_full_scene_not_a_partial_patch() -> None:
    """The resumed client is handed the whole tree, because it holds none.

    Patches address the tree by index. Replaying them at a client that just
    loaded would apply to nothing, so the only correct repair is one root replace
    carrying the scene as it stands — the same choice the SSE path makes when a
    gap outruns its replay buffer.
    """
    client = TestClient(create_app(make_state, view))
    with client:
        with client.websocket_connect("/ws?session=scene") as ws:
            ws.receive_json()
            _click(ws, times=2)

        with client.websocket_connect("/ws?session=scene") as ws:
            resumed = ws.receive_json()
            assert resumed["kind"] == "patches"
            assert resumed["data"][0]["path"] == []
            assert _label_content(resumed["data"][0]["node"]) == "Count: 2"


def test_a_different_id_gets_a_fresh_session() -> None:
    """Resuming is opt-in per id: another id is another user, and starts at zero."""
    client = TestClient(create_app(make_state, view))
    with client:
        with client.websocket_connect("/ws?session=one") as ws:
            ws.receive_json()
            _click(ws, times=3)

        with client.websocket_connect("/ws?session=two") as ws:
            assert _mounted_label(ws.receive_json()) == "Count: 0"


def test_no_id_keeps_the_old_fresh_per_connection_behaviour() -> None:
    """A client that names no session still gets isolation, as it always did."""
    client = TestClient(create_app(make_state, view))
    with client:
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()
            _click(ws, times=4)

        with client.websocket_connect("/ws") as ws:
            assert _mounted_label(ws.receive_json()) == "Count: 0"


def test_two_ids_stay_isolated_while_both_are_live() -> None:
    """Resume must not weaken isolation: two sessions never see each other."""
    client = TestClient(create_app(make_state, view))
    with (
        client,
        client.websocket_connect("/ws?session=a") as ws_a,
        client.websocket_connect("/ws?session=b") as ws_b,
    ):
        ws_a.receive_json()
        ws_b.receive_json()
        _click(ws_a, times=5)
        _click(ws_b, times=1)

        ws_a.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
        assert "Count: 6" in str(ws_a.receive_json())


def test_resume_window_of_zero_restores_fresh_state_per_connection() -> None:
    """``ws_resume_seconds=0`` is the switch back to the old behaviour."""
    app = create_app(make_state, view, ws_resume_seconds=0)
    client = TestClient(app)
    with client:
        with client.websocket_connect("/ws?session=off") as ws:
            ws.receive_json()
            _click(ws, times=2)

        with client.websocket_connect("/ws?session=off") as ws:
            assert _mounted_label(ws.receive_json()) == "Count: 0"


@pytest.mark.asyncio
async def test_an_orphaned_session_expires_and_is_closed() -> None:
    """A session nobody comes back for is closed, not pinned forever.

    Driven against the server object rather than over a socket, because what is
    asserted is the timer: the record is gone and the session is unmounted.
    """
    server: TempestWebServer[CounterState] = TempestWebServer(
        make_state, view, ws_resume_seconds=0.05
    )
    session = server._new_session(_SilentTransport())
    server._ws_sessions["orphan"] = _record(server, session, owner="")

    await server._release_ws("orphan", session, generation=0)
    assert "orphan" in server._ws_sessions

    await asyncio.sleep(0.2)
    assert "orphan" not in server._ws_sessions
    assert session._closed is True


@pytest.mark.asyncio
async def test_a_superseded_socket_cannot_retire_the_resumed_session() -> None:
    """The takeover race: the old socket unwinding must not drop the new session.

    This is not hypothetical — it is the race the SSE path pays for with
    ``stream_token``, and it drops a session the client had just successfully
    reconnected to.
    """
    server: TempestWebServer[CounterState] = TempestWebServer(
        make_state, view, ws_resume_seconds=30
    )
    session = server._new_session(_SilentTransport())
    held = _record(server, session, owner="")
    server._ws_sessions["taken"] = held

    held.generation += 1
    await server._release_ws("taken", session, generation=0)

    assert "taken" in server._ws_sessions
    assert held.expiry is None, "the superseded socket armed an expiry it does not own"
    assert session._closed is False


def _record(
    server: TempestWebServer[CounterState],
    session: object,
    owner: str,
) -> object:
    """Build a ``_WSSession`` record without importing it at module scope.

    Args:
        server: The server the record belongs to (for its generic parameter).
        session: The app session to wrap.
        owner: The owner fingerprint.

    Returns:
        The record.
    """
    from tempestweb.server.app import _WSSession

    return _WSSession(session, owner)  # type: ignore[arg-type]


class _SilentTransport:
    """A transport that accepts everything and never yields an event."""

    async def send_patches(self, patches: list[dict]) -> None:
        """Discard a patch batch.

        Args:
            patches: The batch.
        """

    async def send_navigate(self, path: str) -> None:
        """Discard a navigate envelope.

        Args:
            path: The path.
        """

    async def send_theme(self, mode: str) -> None:
        """Discard a theme envelope.

        Args:
            mode: The resolved mode.
        """

    async def send_native_call(self, call_id: str, capability: str, args: dict) -> None:
        """Discard a native call.

        Args:
            call_id: The call id.
            capability: The capability name.
            args: The call arguments.
        """

    async def send_native_subscribe(
        self, sub_id: str, capability: str, args: dict
    ) -> None:
        """Discard a native subscribe.

        Args:
            sub_id: The subscription id.
            capability: The capability name.
            args: The subscribe arguments.
        """

    async def send_native_unsubscribe(self, sub_id: str) -> None:
        """Discard a native unsubscribe.

        Args:
            sub_id: The subscription id.
        """

    async def recv_event(self) -> dict:
        """Never yield an event.

        Returns:
            Never returns.
        """
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    def on_native_result(self, handler: object) -> None:
        """Ignore the native-result sink.

        Args:
            handler: The sink.
        """

    def on_native_event(self, handler: object) -> None:
        """Ignore the native-event sink.

        Args:
            handler: The sink.
        """

    async def close(self) -> None:
        """Close nothing."""


def _two_user_app() -> TestClient:
    """A host that authenticates two distinct principals.

    Returns:
        A test client over an app where ``alice`` and ``bob`` are both valid and
        distinguishable — which is what an ownership check needs to be tested at
        all.
    """
    from tempestweb.server.security import SecurityConfig

    def authenticate(credentials: object) -> bool:
        return getattr(credentials, "token", None) in {"alice", "bob"}

    app = create_app(
        make_state, view, security=SecurityConfig(authenticate=authenticate)
    )
    return TestClient(app)


def test_another_principal_cannot_claim_a_live_session() -> None:
    """A session id is not an authorization.

    The id travels in a URL, so anything that can read a URL — a log, a referrer,
    a shoulder — could otherwise attach to somebody's live session and read their
    screen. The same rule the SSE path states with its ``403``.
    """
    client = _two_user_app()
    with client:
        with client.websocket_connect("/ws?session=shared&token=alice") as ws:
            ws.receive_json()
            _click(ws, times=2)

        with (
            pytest.raises(Exception),  # noqa: B017 - the upgrade is refused, shape is client-specific
            client.websocket_connect("/ws?session=shared&token=bob") as ws,
        ):
            ws.receive_json()


def test_the_owner_still_resumes_their_own_session() -> None:
    """The ownership check must not lock the owner out of their own session."""
    client = _two_user_app()
    with client:
        with client.websocket_connect("/ws?session=mine&token=alice") as ws:
            ws.receive_json()
            _click(ws, times=2)

        with client.websocket_connect("/ws?session=mine&token=alice") as ws:
            assert _mounted_label(ws.receive_json()) == "Count: 2"
