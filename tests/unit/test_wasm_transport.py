"""Unit tests for the Mode A (WASM) transport — pure Python, headless.

Covers the in-process bridge contract: patch delivery through the sink, event
buffering through the queue, and clean teardown. No Pyodide is involved; the live
``pyodide.ffi`` wiring is documented in NOTES-T3.md.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from tempestweb.transports import PatchTransport, TransportClosedError, WasmTransport


def test_implements_patch_transport_protocol() -> None:
    """WasmTransport satisfies the runtime-checkable PatchTransport Protocol."""
    transport = WasmTransport(lambda _patches: None)
    assert isinstance(transport, PatchTransport)


@pytest.mark.asyncio
async def test_send_patches_calls_deliver() -> None:
    """A non-empty batch is passed verbatim to the deliver sink."""
    sent: list[list[dict[str, Any]]] = []
    transport = WasmTransport(sent.append)
    batch = [{"path": [0], "set_props": {"content": "x"}, "unset_props": []}]
    await transport.send_patches(batch)
    assert sent == [batch]


@pytest.mark.asyncio
async def test_send_empty_patches_is_noop() -> None:
    """An empty batch never touches the sink."""
    sent: list[Any] = []
    transport = WasmTransport(sent.append)
    await transport.send_patches([])
    assert sent == []


@pytest.mark.asyncio
async def test_push_event_then_recv_event() -> None:
    """An event pushed by the client is returned by recv_event in order."""
    transport = WasmTransport(lambda _patches: None)
    transport.push_event({"type": "click", "key": "a", "payload": {}})
    transport.push_event({"type": "click", "key": "b", "payload": {}})
    first = await transport.recv_event()
    second = await transport.recv_event()
    assert first["key"] == "a"
    assert second["key"] == "b"


@pytest.mark.asyncio
async def test_recv_event_blocks_until_pushed() -> None:
    """recv_event awaits until an event is pushed."""
    transport = WasmTransport(lambda _patches: None)
    task = asyncio.ensure_future(transport.recv_event())
    await asyncio.sleep(0)
    assert not task.done()
    transport.push_event({"type": "click", "key": "a", "payload": {}})
    event = await asyncio.wait_for(task, timeout=1.0)
    assert event["key"] == "a"


@pytest.mark.asyncio
async def test_close_unblocks_recv_event() -> None:
    """Closing a transport unblocks a pending recv_event with the closed error."""
    transport = WasmTransport(lambda _patches: None)
    task = asyncio.ensure_future(transport.recv_event())
    await asyncio.sleep(0)
    await transport.close()
    with pytest.raises(TransportClosedError):
        await asyncio.wait_for(task, timeout=1.0)


@pytest.mark.asyncio
async def test_operations_after_close_raise() -> None:
    """send/recv/push after close raise TransportClosedError."""
    transport = WasmTransport(lambda _patches: None)
    await transport.close()
    with pytest.raises(TransportClosedError):
        await transport.send_patches([{"path": [], "index": 0, "node": {}}])
    with pytest.raises(TransportClosedError):
        await transport.recv_event()
    with pytest.raises(TransportClosedError):
        transport.push_event({"type": "click", "key": "a", "payload": {}})


@pytest.mark.asyncio
async def test_close_is_idempotent() -> None:
    """Closing twice is a no-op."""
    transport = WasmTransport(lambda _patches: None)
    await transport.close()
    await transport.close()
    assert transport.closed
