"""SSE over the real FastAPI host, driven asynchronously.

The synchronous ``TestClient`` cannot exercise this leg: an open streaming
``GET`` blocks its thread, so the concurrent ``POST`` that drives the next tick
never runs (which is why the round-trip test in ``test_server_sse`` is skipped).
``httpx``'s ASGI transport cannot either — it buffers a response until the app
says the body is done, and this body never is. So these tests serve the app on a
real loopback port and speak HTTP to it, which covers the round-trip plus the
session-lifetime rules the id-in-a-URL design needs:

- an event POSTed for a session reaches it and its patch comes back down;
- a *different* principal presenting the same id is refused, rather than reading
  the session's rendered state and posting events into it;
- the owner reopening the stream takes the session over instead of racing the old
  response into tearing it down.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
import pytest
import uvicorn
from fastapi import FastAPI

from tempest_core import App, Button, Column, Text, Widget
from tempestweb.runtime.session import AppSession
from tempestweb.server import create_app
from tempestweb.server.app import TempestWebServer, _SSESession
from tempestweb.server.security import SecurityConfig
from tempestweb.transports.sse import SSETransport as _SSETransport


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


#: Auth that accepts every token, so a connection's *identity* (its bearer token)
#: is what distinguishes two principals, not whether it may connect at all.
ANY_TOKEN = SecurityConfig(authenticate=lambda credentials: True)


@asynccontextmanager
async def _client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """Serve ``app`` on an ephemeral loopback port; yield a client bound to it.

    A streaming SSE response has no end, so it can only be read by a client that
    is genuinely incremental — hence a real server rather than an in-process ASGI
    shim. WebSocket support is switched off: these tests only need the HTTP/SSE
    surface, and uvicorn's protocol autodetect imports ``websockets.legacy``,
    whose DeprecationWarning this suite turns into an error.

    Args:
        app: The FastAPI application to serve.

    Yields:
        An ``httpx.AsyncClient`` whose base URL points at the running server.
    """
    config = uvicorn.Config(
        app, host="127.0.0.1", port=0, log_level="warning", ws="none"
    )
    server = uvicorn.Server(config)
    serving = asyncio.ensure_future(server.serve())
    for _ in range(500):
        if server.started:
            break
        await asyncio.sleep(0.01)
    else:
        serving.cancel()
        raise AssertionError("uvicorn did not start")
    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{port}", timeout=5.0
        ) as client:
            yield client
    finally:
        server.should_exit = True
        await serving


async def _frames(lines: AsyncIterator[str]) -> AsyncIterator[tuple[int, dict]]:
    """Yield ``(id, envelope)`` for each non-ping SSE block on the stream."""
    block: list[str] = []
    async for raw in lines:
        if raw != "":
            block.append(raw)
            continue
        if not block:
            continue
        text = "\n".join(block)
        block = []
        if "event: ping" in text:
            continue
        event_id = 0
        data = "{}"
        for line in text.splitlines():
            if line.startswith("id: "):
                event_id = int(line[len("id: ") :])
            elif line.startswith("data: "):
                data = line[len("data: ") :]
        yield event_id, json.loads(data)


def _label_content(node: dict) -> str | None:
    """Find the ``label`` node's ``content`` prop in a wire node tree."""
    if node.get("key") == "label":
        content: str | None = node["props"].get("content")
        return content
    for child in node.get("children", []):
        found = _label_content(child)
        if found is not None:
            return found
    return None


def _label_update(envelope: dict) -> dict:
    """Pull the label ``content`` Update out of a ``patches`` envelope."""
    for patch in envelope["data"]:
        if "content" in patch.get("set_props", {}):
            props: dict = patch["set_props"]
            return props
    raise AssertionError(f"no label update in {envelope}")


async def _sessions_stay_up(client: httpx.AsyncClient, *, window: float = 1.5) -> int:
    """Poll ``/health`` for ``window`` seconds and report the live session count.

    Returns as soon as the count reaches zero, so a session torn down by the
    stream that a reconnect replaced is observed rather than waited out.

    Args:
        client: The client bound to the running server.
        window: How long to keep polling while the count stays positive.

    Returns:
        The last observed live session count.
    """
    live = -1
    deadline = asyncio.get_running_loop().time() + window
    while asyncio.get_running_loop().time() < deadline:
        live = int((await client.get("/health")).json()["sessions"])
        if live == 0:
            return live
        await asyncio.sleep(0.05)
    return live


async def test_mount_then_post_click_yields_update() -> None:
    """GET /sse mounts, POST /sse/{id} clicks, and the Update comes back down."""
    app = create_app(make_state, view)
    async with (
        _client(app) as client,
        client.stream("GET", "/sse?session=s1") as stream,
    ):
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        frames = _frames(stream.aiter_lines())

        mount_id, mount = await asyncio.wait_for(frames.__anext__(), 2.0)
        assert mount_id == 1
        assert _label_content(mount["data"][0]["node"]) == "Count: 0"

        post = await client.post(
            "/sse/s1",
            json={"kind": "event", "data": {"type": "click", "key": "inc"}},
        )
        assert post.status_code == 204

        update_id, update = await asyncio.wait_for(frames.__anext__(), 2.0)
        assert update_id == 2
        assert _label_update(update) == {"content": "Count: 1"}


async def test_a_second_principal_cannot_attach_to_a_session() -> None:
    """Knowing the id is not enough: another principal is refused, not attached."""
    app = create_app(make_state, view, security=ANY_TOKEN)
    async with _client(app) as client:
        owner = {"Authorization": "Bearer owner-token"}
        intruder = {"Authorization": "Bearer intruder-token"}
        async with client.stream("GET", "/sse?session=shared", headers=owner) as stream:
            frames = _frames(stream.aiter_lines())
            await asyncio.wait_for(frames.__anext__(), 2.0)

            attach = await client.get("/sse?session=shared", headers=intruder)
            assert attach.status_code == 403

            injected = await client.post(
                "/sse/shared",
                headers=intruder,
                json={"kind": "event", "data": {"type": "click", "key": "inc"}},
            )
            assert injected.status_code == 403

            allowed = await client.post(
                "/sse/shared",
                headers=owner,
                json={"kind": "event", "data": {"type": "click", "key": "inc"}},
            )
            assert allowed.status_code == 204


async def test_owner_reconnect_takes_the_session_over(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reconnect keeps the state, and the stream it replaced cannot drop it.

    The race this pins is the ordinary one: the network drops, the client
    reconnects, and only *then* does the old response unwind on the server. Its
    cleanup used to tear down the session the client had just resumed.

    The heartbeat is shortened because an abandoned stream is only *noticed* when
    the response next tries to write — with the 15s default the teardown, and so
    the bug, would land long after the test finished.
    """
    from tempestweb.server import app as server_app
    from tempestweb.transports.sse import SSETransport

    def quick_ping(**kwargs: object) -> SSETransport:
        """Build a transport that heartbeats often enough to notice a drop."""
        return SSETransport(ping_interval=0.1)

    monkeypatch.setattr(server_app, "SSETransport", quick_ping)

    app = create_app(make_state, view, security=ANY_TOKEN)
    async with _client(app) as client:
        owner = {"Authorization": "Bearer owner-token"}
        dropped = client.stream("GET", "/sse?session=keep", headers=owner)
        first = await dropped.__aenter__()
        await asyncio.wait_for(_frames(first.aiter_lines()).__anext__(), 2.0)

        resumed = client.stream(
            "GET", "/sse?session=keep", headers={**owner, "Last-Event-ID": "1"}
        )
        second = await resumed.__aenter__()
        frames = _frames(second.aiter_lines())

        # Only now does the dropped connection finish unwinding on the server.
        await dropped.__aexit__(None, None, None)
        assert await _sessions_stay_up(client) == 1

        click = await client.post(
            "/sse/keep",
            headers=owner,
            json={"kind": "event", "data": {"type": "click", "key": "inc"}},
        )
        assert click.status_code == 204
        _, update = await asyncio.wait_for(frames.__anext__(), 2.0)
        assert _label_update(update) == {"content": "Count: 1"}
        await resumed.__aexit__(None, None, None)


async def test_a_gap_the_buffer_evicted_forces_a_full_resync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resuming past an evicted tick yields a root replace, not a stale patch."""
    from tempestweb.server import app as server_app
    from tempestweb.transports.sse import SSETransport

    def tiny_buffer(**kwargs: object) -> SSETransport:
        """Build a transport whose replay buffer holds a single envelope."""
        return SSETransport(replay_buffer=1)

    monkeypatch.setattr(server_app, "SSETransport", tiny_buffer)

    app = create_app(make_state, view, security=ANY_TOKEN)
    async with _client(app) as client:
        owner = {"Authorization": "Bearer owner-token"}
        live = client.stream("GET", "/sse?session=gap", headers=owner)
        first = await live.__aenter__()
        first_frames = _frames(first.aiter_lines())
        await asyncio.wait_for(first_frames.__anext__(), 2.0)
        for _ in range(3):
            await client.post(
                "/sse/gap",
                headers=owner,
                json={"kind": "event", "data": {"type": "click", "key": "inc"}},
            )
            await asyncio.wait_for(first_frames.__anext__(), 2.0)

        # The client resumes claiming tick 1, long since evicted from the buffer.
        resumed = client.stream(
            "GET", "/sse?session=gap", headers={**owner, "Last-Event-ID": "1"}
        )
        second = await resumed.__aenter__()
        frames = _frames(second.aiter_lines())
        _, repair = await asyncio.wait_for(frames.__anext__(), 2.0)
        patch = repair["data"][0]
        assert patch["path"] == []
        assert _label_content(patch["node"]) == "Count: 3"

        await live.__aexit__(None, None, None)
        await resumed.__aexit__(None, None, None)


async def test_a_retired_stream_cannot_release_the_session() -> None:
    """Cleanup from a stream a takeover retired leaves the session mounted.

    Over HTTP this is a race — whether the replaced response unwinds before or
    after the reconnect settles is up to the event loop — so the rule is pinned
    where it is decided: only the holder of the newest stream token may tear the
    session down.
    """
    server: TempestWebServer[CounterState] = TempestWebServer(make_state, view)
    transport = _SSETransport()
    entry = _SSESession(
        transport=transport,
        session=AppSession(make_state, view, transport),
        owner="fingerprint",
    )
    server._sse_sessions["s"] = entry
    server._live = 1
    entry.stream_token = 2  # a reconnect has taken the session over

    await server._release_sse("s", 1)  # the stream it replaced unwinds now
    assert "s" in server._sse_sessions
    assert server._live == 1

    await server._release_sse("s", 2)  # the stream that owns it ends
    assert "s" not in server._sse_sessions
    assert server._live == 0
