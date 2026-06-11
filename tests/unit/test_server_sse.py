"""Mode B SSE transport (phase B5) — patches down EventSource, events up via POST.

SSE is unidirectional, so the duplex contract is split across two HTTP channels.
These tests drive the real :class:`~tempestweb.transports.sse.SSETransport` with
the same counter ``view`` used by the WebSocket suite, asserting the identical
patch stream plus the SSE-only concerns: ``id:`` framing, named ``ping``
heartbeats, and ``Last-Event-ID`` replay on reconnect. A separate test exercises
the FastAPI POST endpoint's routing and 404 behavior.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

from fastapi.testclient import TestClient

from tempestweb._core import App, Button, Column, Text, Widget
from tempestweb.runtime.session import AppSession
from tempestweb.server import create_app
from tempestweb.transports.sse import SSETransport


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


def _parse_frame(frame: str) -> tuple[int | None, dict]:
    """Parse one SSE event block into ``(id, json-data)``."""
    event_id: int | None = None
    data = "{}"
    for line in frame.splitlines():
        if line.startswith("id: "):
            event_id = int(line[len("id: ") :])
        elif line.startswith("data: "):
            data = line[len("data: ") :]
    return event_id, json.loads(data)


def _label_set_props(envelope: dict) -> dict:
    """Pull the label ``content`` Update out of a ``patches`` envelope."""
    for patch in envelope["data"]:
        if "content" in patch.get("set_props", {}):
            return patch["set_props"]
    raise AssertionError(f"no label update in {envelope}")


async def test_sse_initial_mount_click_update_and_ping() -> None:
    """Mount via the stream, click via feed_inbound, then see a ping heartbeat."""
    transport = SSETransport(ping_interval=0.05)
    session: AppSession[CounterState] = AppSession(make_state, view, transport)
    run_task = asyncio.ensure_future(session.run())
    await asyncio.sleep(0.01)

    stream = transport.stream()
    frame_id, env = _parse_frame(await asyncio.wait_for(stream.__anext__(), 1.0))
    assert frame_id == 1
    assert env["kind"] == "patches"
    assert env["data"][0]["path"] == []

    transport.feed_inbound({"kind": "event", "data": {"type": "click", "key": "inc"}})
    await asyncio.sleep(0.01)
    frame_id, env = _parse_frame(await asyncio.wait_for(stream.__anext__(), 1.0))
    assert frame_id == 2
    assert _label_set_props(env) == {"content": "Count: 1"}

    ping = await asyncio.wait_for(stream.__anext__(), 1.0)
    assert "event: ping" in ping

    await transport.close()
    await session.close()
    run_task.cancel()


async def test_sse_last_event_id_replay_on_reconnect() -> None:
    """A reconnect with Last-Event-ID replays only the ticks the client missed."""
    transport = SSETransport(ping_interval=10.0)
    session: AppSession[CounterState] = AppSession(make_state, view, transport)
    run_task = asyncio.ensure_future(session.run())
    await asyncio.sleep(0.01)

    # Drain the live stream: mount (id 1) + two clicks (ids 2, 3).
    stream = transport.stream()
    await asyncio.wait_for(stream.__anext__(), 1.0)  # id 1
    transport.feed_inbound({"kind": "event", "data": {"type": "click", "key": "inc"}})
    await asyncio.sleep(0.01)
    await asyncio.wait_for(stream.__anext__(), 1.0)  # id 2
    transport.feed_inbound({"kind": "event", "data": {"type": "click", "key": "inc"}})
    await asyncio.sleep(0.01)
    await asyncio.wait_for(stream.__anext__(), 1.0)  # id 3
    await stream.aclose()

    # Reconnect having seen id 1: replay must re-emit ids 2 and 3 only.
    replay = transport.stream(last_event_id=1)
    first_id, first_env = _parse_frame(await asyncio.wait_for(replay.__anext__(), 1.0))
    second_id, second_env = _parse_frame(
        await asyncio.wait_for(replay.__anext__(), 1.0)
    )
    assert first_id == 2
    assert _label_set_props(first_env) == {"content": "Count: 1"}
    assert second_id == 3
    assert _label_set_props(second_env) == {"content": "Count: 2"}
    await replay.aclose()

    await transport.close()
    await session.close()
    run_task.cancel()


async def test_sse_two_transports_keep_independent_state() -> None:
    """Two SSE sessions own separate counters; a click never crosses over."""
    t_a = SSETransport(ping_interval=10.0)
    t_b = SSETransport(ping_interval=10.0)
    s_a: AppSession[CounterState] = AppSession(make_state, view, t_a)
    s_b: AppSession[CounterState] = AppSession(make_state, view, t_b)
    run_a = asyncio.ensure_future(s_a.run())
    run_b = asyncio.ensure_future(s_b.run())
    await asyncio.sleep(0.01)

    stream_a = t_a.stream()
    stream_b = t_b.stream()
    await asyncio.wait_for(stream_a.__anext__(), 1.0)
    await asyncio.wait_for(stream_b.__anext__(), 1.0)

    t_a.feed_inbound({"kind": "event", "data": {"type": "click", "key": "inc"}})
    await asyncio.sleep(0.01)
    _, env_a = _parse_frame(await asyncio.wait_for(stream_a.__anext__(), 1.0))
    assert _label_set_props(env_a) == {"content": "Count: 1"}

    # B untouched so far: its first click is Count: 1, not Count: 2.
    t_b.feed_inbound({"kind": "event", "data": {"type": "click", "key": "inc"}})
    await asyncio.sleep(0.01)
    _, env_b = _parse_frame(await asyncio.wait_for(stream_b.__anext__(), 1.0))
    assert _label_set_props(env_b) == {"content": "Count: 1"}

    for stream in (stream_a, stream_b):
        await stream.aclose()
    await t_a.close()
    await t_b.close()
    await s_a.close()
    await s_b.close()
    run_a.cancel()
    run_b.cancel()


def test_sse_post_to_unknown_session_returns_404() -> None:
    """POSTing an event to a session id that was never opened returns 404."""
    client = TestClient(create_app(make_state, view))
    response = client.post(
        "/sse/never-opened",
        json={"kind": "event", "data": {"type": "click", "key": "inc"}},
    )
    assert response.status_code == 404
