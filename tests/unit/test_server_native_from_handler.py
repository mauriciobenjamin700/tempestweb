"""End-to-end native bridge wiring across both execution modes (integration).

These tests drive the **full** native chain that the unit tests of the bridges in
isolation never exercised — and which therefore let a real regression slip:
``tempestweb/native/bridges.py`` had ``ProxyBridge``/``FFIBridge`` fully
unit-tested, yet **neither was ever installed** by a runtime, so a real
``await native.<capability>()`` raised :class:`BrowserUnavailableError` at runtime
in both modes.

* **Mode B** asserts that mounting an :class:`AppSession` installs a
  :class:`ProxyBridge`, that a handler calling ``await native.<capability>()`` (the
  dispatch-module path, not the session's own ``native_call``) flows
  handler → ``send_native_call`` → bridge → ``transport.send_native_call`` and that
  feeding the matching ``native_result`` resolves the typed value (and that an
  ``ok: false`` result raises the typed :class:`NativeError`). It also asserts the
  bridge is uninstalled on :meth:`AppSession.close`, so no state leaks between
  sessions/tests.

* **Mode A** asserts that installing an :class:`FFIBridge` (as the WASM bootstrap
  does) makes the same ``await native.<capability>()`` resolve in-process through a
  fake dispatch.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import pytest
from tempest_core import App, Text, Widget

from tempestweb import native
from tempestweb.native import (
    BrowserUnavailableError,
    FFIBridge,
    NativeError,
    current_bridge,
    install_bridge,
    send_native_call,
    uninstall_bridge,
)
from tempestweb.runtime.session import AppSession
from tempestweb.transports.sse import SSETransport


@pytest.fixture(autouse=True)
def _clean_bridge() -> Any:
    """Guarantee no bridge leaks into or out of a test in this module."""
    uninstall_bridge()
    yield
    uninstall_bridge()


@dataclass
class EmptyState:
    """Trivial state; these tests only exercise the native chain."""


def make_state() -> EmptyState:
    """Build a fresh empty state."""
    return EmptyState()


def view(app: App[EmptyState]) -> Widget:
    """Render a static label (no interactivity needed here)."""
    return Text(content="native", key="label")


async def _read_native_call(stream: Any) -> dict[str, Any]:
    """Drain SSE frames until a ``native_call`` envelope is seen, return it.

    Args:
        stream: The SSE transport's async event stream.

    Returns:
        The parsed ``native_call`` envelope.
    """
    for _ in range(10):
        frame = await asyncio.wait_for(stream.__anext__(), 1.0)
        if "data: " not in frame:
            continue
        envelope = json.loads(frame.split("data: ", 1)[1])
        if envelope.get("kind") == "native_call":
            return envelope
    raise AssertionError("no native_call frame emitted")


async def test_mount_installs_proxy_bridge_and_handler_chain_resolves() -> None:
    """A handler's ``await native.*()`` proxies through the installed bridge.

    This is the test that would have caught the "bridge never installed" bug: it
    runs the dispatch-module ``send_native_call`` (the same path the public
    ``tempestweb.native`` capabilities use), not the session's own ``native_call``.
    """
    transport = SSETransport(ping_interval=10.0)
    session: AppSession[EmptyState] = AppSession(make_state, view, transport)
    await session.start()

    # Mounting installs this session's ProxyBridge process-wide.
    assert current_bridge() is session._bridge  # noqa: SLF001 — asserting wiring

    stream = transport.stream()
    await asyncio.wait_for(stream.__anext__(), 1.0)  # drain initial mount

    # Drive the FULL chain a handler would: dispatch-module send_native_call ->
    # current_bridge() -> ProxyBridge -> transport.send_native_call.
    call = asyncio.ensure_future(send_native_call("geolocation.get", {}))
    envelope = await _read_native_call(stream)
    assert envelope["capability"] == "geolocation.get"
    call_id = envelope["call_id"]

    transport.feed_inbound(
        {
            "kind": "native_result",
            "call_id": call_id,
            "ok": True,
            "value": {"latitude": -23.5, "longitude": -46.6},
        }
    )
    value = await asyncio.wait_for(call, 1.0)
    assert value == {"latitude": -23.5, "longitude": -46.6}

    await stream.aclose()
    await transport.close()
    await session.close()


async def test_handler_chain_propagates_typed_error() -> None:
    """An ``ok: false`` result raises the typed NativeError up the handler chain."""
    transport = SSETransport(ping_interval=10.0)
    session: AppSession[EmptyState] = AppSession(make_state, view, transport)
    await session.start()

    stream = transport.stream()
    await asyncio.wait_for(stream.__anext__(), 1.0)

    call = asyncio.ensure_future(native.clipboard.read())
    envelope = await _read_native_call(stream)
    assert envelope["capability"] == "clipboard.read"
    call_id = envelope["call_id"]

    transport.feed_inbound(
        {
            "kind": "native_result",
            "call_id": call_id,
            "ok": False,
            "error": "permission_denied",
            "message": "blocked",
        }
    )
    with pytest.raises(NativeError) as exc:
        await asyncio.wait_for(call, 1.0)
    assert exc.value.code == "permission_denied"

    await stream.aclose()
    await transport.close()
    await session.close()


async def test_close_uninstalls_the_bridge() -> None:
    """After ``close()`` the process-wide bridge is gone (no cross-session leak)."""
    transport = SSETransport(ping_interval=10.0)
    session: AppSession[EmptyState] = AppSession(make_state, view, transport)
    await session.start()
    assert current_bridge() is session._bridge  # noqa: SLF001 — asserting wiring

    await session.close()
    with pytest.raises(BrowserUnavailableError):
        current_bridge()


async def test_concurrent_sessions_isolate_their_bridges() -> None:
    """Two concurrent Mode-B sessions each see their **own** bridge.

    Regression guard for the context-local bridge: ``install_bridge`` used to be
    process-global, so the last session to ``start()`` clobbered every other
    session's ``await native.*`` path. Now each session runs in its own asyncio
    task (as the SSE/WS endpoints drive it), so each ``current_bridge()`` resolves
    to that session's bridge even while the other is concurrently mounted.
    """
    transport_a = SSETransport(ping_interval=10.0)
    session_a: AppSession[EmptyState] = AppSession(make_state, view, transport_a)
    transport_b = SSETransport(ping_interval=10.0)
    session_b: AppSession[EmptyState] = AppSession(make_state, view, transport_b)

    both_mounted = asyncio.Event()
    mounted = 0
    seen: dict[str, Any] = {}

    async def drive(session: AppSession[EmptyState], label: str) -> None:
        """Mount a session in its own task, then read the bridge once both are up."""
        nonlocal mounted
        await session.start()
        # Park until BOTH sessions have installed their bridge, so a process-wide
        # bridge would already have been overwritten by the second start().
        mounted += 1
        if mounted == 2:
            both_mounted.set()
        await asyncio.wait_for(both_mounted.wait(), 1.0)
        seen[label] = current_bridge()

    # gather wraps each coroutine in its own Task (own context copy) — exactly how
    # the server drives one task per connection.
    await asyncio.gather(drive(session_a, "a"), drive(session_b, "b"))

    assert seen["a"] is session_a._bridge  # noqa: SLF001 — asserting isolation
    assert seen["b"] is session_b._bridge  # noqa: SLF001 — asserting isolation
    assert seen["a"] is not seen["b"]

    await session_a.close()
    await session_b.close()


async def test_mode_a_ffi_bridge_install_resolves_in_process() -> None:
    """Installing an FFIBridge (as the WASM bootstrap does) wires the chain.

    Mirrors what ``wasm_main.bootstrap`` does when handed the in-process
    ``__tempestweb_native__`` dispatch: install ``FFIBridge(dispatch)`` so that a
    handler's ``await native.*()`` resolves in-process — no network hop.
    """
    seen: list[dict[str, Any]] = []

    async def fake_dispatch(envelope_json: str) -> str:
        """Stand in for the Pyodide-proxied window.__tempestweb_native__."""
        seen.append(json.loads(envelope_json))
        return json.dumps({"ok": True, "value": {"text": "clip"}})

    install_bridge(FFIBridge(fake_dispatch))

    # The dispatch-module path returns the unwrapped value dict; the capability
    # wrapper (native.clipboard.read) lowers it to a str — assert both legs.
    value = await send_native_call("clipboard.read", {})
    assert value == {"text": "clip"}
    text = await native.clipboard.read()
    assert text == "clip"
    assert seen[0]["kind"] == "native_call"
    assert seen[0]["capability"] == "clipboard.read"
