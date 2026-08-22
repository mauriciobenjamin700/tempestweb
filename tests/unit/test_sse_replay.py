"""SSE reconnect: every tick exactly once, in order, or a full resync.

A Mode B client's tree is only correct while it has applied every patch in
order — patches are index-relative. These tests pin the three ways the SSE leg
can break that chain, all of which used to be silent:

- a reconnect re-delivering ticks the client had already applied (the buffer and
  a separate outbound queue both held them);
- a second stream on one transport splitting the tick stream between the two;
- a gap the replay buffer has evicted, which must force a resync rather than a
  patch landing on a stale tree.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

import pytest

from tempest_core import App, Button, Column, Text, Widget
from tempestweb.runtime.session import AppSession
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


def _tick_id(frame: str) -> int:
    """Read the SSE ``id:`` field out of one event block."""
    for line in frame.splitlines():
        if line.startswith("id: "):
            return int(line[len("id: ") :])
    raise AssertionError(f"no id in frame {frame!r}")


def _envelope(frame: str) -> dict:
    """Read the SSE ``data:`` field out of one event block."""
    for line in frame.splitlines():
        if line.startswith("data: "):
            return json.loads(line[len("data: ") :])
    raise AssertionError(f"no data in frame {frame!r}")


async def _drain(stream, count: int, timeout: float = 1.0) -> list[str]:
    """Pull ``count`` frames off an SSE stream, skipping heartbeats."""
    frames: list[str] = []
    while len(frames) < count:
        frame = await asyncio.wait_for(stream.__anext__(), timeout)
        if "event: ping" not in frame:
            frames.append(frame)
    return frames


async def test_reconnect_delivers_each_missed_tick_once_in_order() -> None:
    """Ticks queued while no stream was open replay once, in id order."""
    transport = SSETransport(ping_interval=10.0)
    for index in range(1, 7):
        await transport.send_patches([{"path": [], "index": index}])

    stream = transport.stream(last_event_id=1)
    frames = await _drain(stream, 5)
    await stream.aclose()

    ids = [_tick_id(frame) for frame in frames]
    assert ids == [2, 3, 4, 5, 6]
    await transport.close()


async def test_a_new_stream_retires_the_previous_one() -> None:
    """Two streams never split the tick stream: the newer one takes over."""
    transport = SSETransport(ping_interval=0.05)
    await transport.send_patches([{"path": [], "index": 1}])

    old = transport.stream()
    await _drain(old, 1)
    new = transport.stream()
    await _drain(new, 1)

    await transport.send_patches([{"path": [], "index": 2}])
    live = await _drain(new, 1)
    assert _tick_id(live[0]) == 2

    # The retired stream ends instead of stealing envelopes from the live one.
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(old.__anext__(), 1.0)

    await new.aclose()
    await transport.close()


async def test_missed_since_reports_only_an_evicted_gap() -> None:
    """A gap the buffer still covers is not a gap; an evicted one is."""
    transport = SSETransport(ping_interval=10.0, replay_buffer=3)
    for index in range(1, 7):
        await transport.send_patches([{"path": [], "index": index}])

    assert transport.last_id == 6
    assert transport.missed_since(1) is True
    assert transport.missed_since(2) is True
    assert transport.missed_since(3) is False
    assert transport.missed_since(6) is False
    await transport.close()


async def test_resync_re_sends_the_whole_scene() -> None:
    """A ``resync`` event answers with one root replace carrying the live scene."""
    transport = SSETransport(ping_interval=10.0)
    session: AppSession[CounterState] = AppSession(make_state, view, transport)
    await session.start()
    await session.dispatch({"type": "click", "key": "inc"})
    await asyncio.sleep(0.01)

    before = transport.last_id
    await session.dispatch({"type": "resync", "key": ""})

    stream = transport.stream(last_event_id=before)
    frames = await _drain(stream, 1)
    await stream.aclose()

    patch = _envelope(frames[0])["data"][0]
    assert patch["path"] == []
    assert "node" in patch
    label = patch["node"]["children"][0]
    assert label["props"]["content"] == "Count: 1"

    await session.close()
