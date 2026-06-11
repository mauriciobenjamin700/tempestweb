"""Mode B native capability proxy — the 4th boundary crossing (docs/contract.md).

In Mode B a ``native/`` capability is proxied by a round-trip: the server sends a
``native_call`` envelope, the client runs the Web API and POSTs back a
``native_result``. These tests drive the round-trip through the real
:class:`~tempestweb.transports.sse.SSETransport` and the session's
:meth:`~tempestweb.runtime.session.AppSession.native_call` awaitable, covering
both the success path and the typed-error path.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

import pytest
from tempest_core import App, Text, Widget

from tempestweb.runtime.session import AppSession, NativeCallError
from tempestweb.transports.sse import SSETransport


@dataclass
class EmptyState:
    """Trivial state; these tests only exercise the native-call channel."""


def make_state() -> EmptyState:
    """Build a fresh empty state."""
    return EmptyState()


def view(app: App[EmptyState]) -> Widget:
    """Render a static label (no interactivity needed here)."""
    return Text(content="native", key="label")


async def test_native_call_resolves_with_client_value() -> None:
    """native_call emits a native_call envelope and resolves on native_result."""
    transport = SSETransport(ping_interval=10.0)
    session: AppSession[EmptyState] = AppSession(make_state, view, transport)
    await session.start()

    stream = transport.stream()
    await asyncio.wait_for(stream.__anext__(), 1.0)  # drain the initial mount

    call = asyncio.ensure_future(session.native_call("geolocation.get", {}))
    frame = await asyncio.wait_for(stream.__anext__(), 1.0)
    envelope = json.loads(frame.split("data: ", 1)[1])
    assert envelope["kind"] == "native_call"
    assert envelope["capability"] == "geolocation.get"
    call_id = envelope["call_id"]

    transport.feed_inbound(
        {
            "kind": "native_result",
            "call_id": call_id,
            "ok": True,
            "value": {"lat": -23.5, "lon": -46.6},
        }
    )
    value = await asyncio.wait_for(call, 1.0)
    assert value == {"lat": -23.5, "lon": -46.6}

    await stream.aclose()
    await transport.close()
    await session.close()


async def test_native_call_failure_raises_typed_error() -> None:
    """A native_result with ok=false raises NativeCallError carrying the message."""
    transport = SSETransport(ping_interval=10.0)
    session: AppSession[EmptyState] = AppSession(make_state, view, transport)
    await session.start()

    stream = transport.stream()
    await asyncio.wait_for(stream.__anext__(), 1.0)

    call = asyncio.ensure_future(session.native_call("camera.capture", {}))
    frame = await asyncio.wait_for(stream.__anext__(), 1.0)
    envelope = json.loads(frame.split("data: ", 1)[1])
    call_id = envelope["call_id"]

    transport.feed_inbound(
        {
            "kind": "native_result",
            "call_id": call_id,
            "ok": False,
            "error": "PermissionDenied",
        }
    )
    with pytest.raises(NativeCallError, match="PermissionDenied"):
        await asyncio.wait_for(call, 1.0)

    await stream.aclose()
    await transport.close()
    await session.close()
