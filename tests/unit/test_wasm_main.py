"""Unit tests for the Mode A in-browser entrypoint glue (headless, no Pyodide).

``bootstrap``/``WasmAppHandle`` compose the unit-tested runtime + transport and
add the JSON string boundary that crosses ``pyodide.ffi``. These tests exercise
that boundary with plain Python stand-ins for the JS callbacks; the live Pyodide
wiring is documented in NOTES-T3.md.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import pytest

from tempestweb._core import App, Button, Column, Row, Style, Text, Widget
from tempestweb._core.style import Edge
from tempestweb.runtime import WasmAppHandle, bootstrap


@dataclass
class CounterState:
    """State for the counter test app."""

    value: int = 0


def counter_view(app: App[CounterState]) -> Widget:
    """Build the canonical counter tree."""

    def increment() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    return Column(
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Count: {app.state.value}", key="label"),
            Row(children=[Button(label="+", on_click=increment, key="inc")]),
        ],
    )


@pytest.mark.asyncio
async def test_bootstrap_returns_handle_with_initial_node() -> None:
    """bootstrap() returns a handle whose initial node JSON is parseable."""
    handle: WasmAppHandle[CounterState] = bootstrap(
        CounterState(), counter_view, lambda _json: None
    )
    initial = json.loads(handle.initial_node_json())
    assert initial["type"] == "Column"
    assert initial["children"][0]["props"]["content"] == "Count: 0"
    await handle.close()


@pytest.mark.asyncio
async def test_push_event_json_drives_rebuild_and_delivers_patch_json() -> None:
    """A JSON event pushed in produces a JSON patch batch out via on_patches."""
    delivered: list[Any] = []

    handle: WasmAppHandle[CounterState] = bootstrap(
        CounterState(), counter_view, delivered.append
    )
    handle.push_event_json(json.dumps({"type": "click", "key": "inc", "payload": {}}))
    # Let the runtime's event loop drain the event and the coalesced rebuild run.
    for _ in range(4):
        await asyncio.sleep(0)

    assert delivered, "a patch batch should have crossed to JS"
    patches = json.loads(delivered[-1])
    assert patches[0]["set_props"]["content"] == "Count: 1"
    await handle.close()


@pytest.mark.asyncio
async def test_close_stops_the_event_loop() -> None:
    """close() tears down the transport and cancels the runtime task."""
    handle: WasmAppHandle[CounterState] = bootstrap(
        CounterState(), counter_view, lambda _json: None
    )
    await handle.close()
    # A second close must not raise (transport close is idempotent).
    await handle.close()


@pytest.mark.asyncio
async def test_bootstrap_installs_ffi_bridge_when_dispatch_given() -> None:
    """Passing a dispatch installs an FFIBridge so native calls resolve in-process.

    This is the Mode A leg of the "bridge never installed" regression: without the
    install, ``await native.<capability>()`` raised BrowserUnavailableError in the
    browser. The fake dispatch stands in for the Pyodide proxy of
    ``window.__tempestweb_native__``.
    """
    from tempestweb.native import (
        BrowserUnavailableError,
        current_bridge,
        send_native_call,
        uninstall_bridge,
    )

    uninstall_bridge()
    seen: list[dict[str, Any]] = []

    async def dispatch(envelope: dict[str, Any]) -> dict[str, Any]:
        seen.append(envelope)
        return {"ok": True, "value": {"text": "hi"}}

    handle: WasmAppHandle[CounterState] = bootstrap(
        CounterState(), counter_view, lambda _json: None, dispatch
    )
    try:
        value = await send_native_call("clipboard.read", {})
        assert value == {"text": "hi"}
        assert seen[0]["capability"] == "clipboard.read"
    finally:
        # close() must uninstall the bridge so no state leaks across apps/tests.
        await handle.close()
    with pytest.raises(BrowserUnavailableError):
        current_bridge()


@pytest.mark.asyncio
async def test_bootstrap_without_dispatch_installs_no_bridge() -> None:
    """Omitting dispatch leaves the process bridge-free (apps with no native use)."""
    from tempestweb.native import (
        BrowserUnavailableError,
        current_bridge,
        uninstall_bridge,
    )

    uninstall_bridge()
    handle: WasmAppHandle[CounterState] = bootstrap(
        CounterState(), counter_view, lambda _json: None
    )
    try:
        with pytest.raises(BrowserUnavailableError):
            current_bridge()
    finally:
        await handle.close()
