"""Unit tests for the Mode A (WASM) runtime glue — pure Python, headless.

These cover the serialization (handler stripping, node/patch JSON shape) and the
event routing (key → handler resolution, sync/async, payload passing) without any
browser or Pyodide. The live ``pyodide.ffi`` path is documented in NOTES-T3.md.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest
from tempest_core import App, Button, Column, Row, Style, Text, Widget, build
from tempest_core.style import Edge

from tempestweb.runtime import WasmRuntime, serialize_node, serialize_patches
from tempestweb.transports import WasmTransport


@dataclass
class CounterState:
    """State for the counter test app."""

    value: int = 0


def counter_view(app: App[CounterState]) -> Widget:
    """Build the canonical counter tree with keyed, zero-arg handlers."""

    def increment() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    def decrement() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value - 1))

    return Column(
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Count: {app.state.value}", key="label"),
            Row(
                style=Style(gap=4.0),
                children=[
                    Button(label="-", on_click=decrement, key="dec"),
                    Button(label="+", on_click=increment, key="inc"),
                ],
            ),
        ],
    )


# --------------------------------------------------------------------------- #
# serialize_node                                                              #
# --------------------------------------------------------------------------- #


def test_serialize_node_shape() -> None:
    """A serialized node has exactly the contract keys and recurses children."""
    node = build(Column(children=[Text(content="hi", key="t")]))
    out = serialize_node(node)
    assert set(out) == {"type", "key", "props", "children"}
    assert out["type"] == "Column"
    assert out["children"][0]["type"] == "Text"
    assert out["children"][0]["key"] == "t"
    assert out["children"][0]["props"]["content"] == "hi"


def test_serialize_node_is_json_able() -> None:
    """A serialized tree round-trips through json with handlers present."""
    import json

    app: App[CounterState] = App(CounterState(), counter_view, lambda _patches: None)
    scene = app.start()
    out = serialize_node(scene.root)
    # Must not raise: every value (incl. nulled handlers, Style/Edge dicts) is
    # JSON-able.
    text = json.dumps(out)
    assert "Count: 0" in text


def test_serialize_node_strips_handlers_to_null() -> None:
    """A present handler serializes to null, not a function."""
    node = build(Button(label="+", on_click=lambda: None, key="b"))
    out = serialize_node(node)
    assert out["props"]["on_click"] is None
    assert out["props"]["label"] == "+"


def test_serialize_node_lowers_style_to_dict() -> None:
    """Style/Edge objects lower to plain dicts (Color rgba, Edge ltrb)."""
    node = build(Column(style=Style(gap=8.0, padding=Edge.all(16)), children=[]))
    out = serialize_node(node)
    style = out["props"]["style"]
    assert isinstance(style, dict)
    assert style["gap"] == 8.0
    assert style["padding"] == {
        "top": 16.0,
        "right": 16.0,
        "bottom": 16.0,
        "left": 16.0,
    }


# --------------------------------------------------------------------------- #
# serialize_patches                                                           #
# --------------------------------------------------------------------------- #


def test_serialize_patches_update_shape() -> None:
    """An Update patch keeps path/set_props/unset_props and is JSON-able."""
    from tempest_core import diff

    old = build(Text(content="Count: 0", key="label"))
    new = build(Text(content="Count: 1", key="label"))
    patches = serialize_patches(diff(old, new))
    assert len(patches) == 1
    patch = patches[0]
    assert patch["path"] == []
    assert patch["set_props"]["content"] == "Count: 1"


def test_serialize_patches_insert_node_is_sanitized() -> None:
    """An Insert patch's embedded node has its handlers nulled out."""
    from tempest_core import diff

    old = build(Column(children=[Text(content="a", key="a")]))
    new = build(
        Column(
            children=[
                Text(content="a", key="a"),
                Button(label="+", on_click=lambda: None, key="b"),
            ]
        )
    )
    patches = serialize_patches(diff(old, new))
    insert = next(p for p in patches if "index" in p and "node" in p)
    assert insert["node"]["props"]["on_click"] is None


def test_serialize_patches_set_props_strips_handlers() -> None:
    """A handler appearing in an Update's set_props is nulled out."""
    from tempest_core import diff

    old = build(Button(label="+", key="b"))
    new = build(Button(label="+", on_click=lambda: None, key="b"))
    patches = serialize_patches(diff(old, new))
    update = next(p for p in patches if "set_props" in p)
    assert update["set_props"]["on_click"] is None


# --------------------------------------------------------------------------- #
# WasmRuntime.start + dispatch_event                                          #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_start_returns_serialized_root() -> None:
    """start() returns the JSON-able initial root node."""
    transport = WasmTransport(lambda _patches: None)
    runtime: WasmRuntime[CounterState] = WasmRuntime(
        CounterState(), counter_view, transport
    )
    root = runtime.start()
    assert root["type"] == "Column"
    assert root["children"][0]["props"]["content"] == "Count: 0"


@pytest.mark.asyncio
async def test_dispatch_event_invokes_zero_arg_handler() -> None:
    """A click on a keyed button runs its zero-arg handler and rebuilds."""
    sent: list[list[dict[str, Any]]] = []
    transport = WasmTransport(sent.append)
    runtime: WasmRuntime[CounterState] = WasmRuntime(
        CounterState(), counter_view, transport
    )
    runtime.start()

    await runtime.dispatch_event({"type": "click", "key": "inc", "payload": {}})
    # The handler called set_state, which schedules a coalesced rebuild on the
    # loop; let it run so the patch is produced and serialized.
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert runtime.app.state.value == 1
    assert sent, "a patch batch should have been delivered"
    update = sent[-1][0]
    assert update["set_props"]["content"] == "Count: 1"


@pytest.mark.asyncio
async def test_dispatch_event_unknown_key_is_ignored() -> None:
    """An event for an unknown key is a no-op (widget may have been removed)."""
    transport = WasmTransport(lambda _patches: None)
    runtime: WasmRuntime[CounterState] = WasmRuntime(
        CounterState(), counter_view, transport
    )
    runtime.start()
    # Must not raise.
    await runtime.dispatch_event({"type": "click", "key": "nope", "payload": {}})
    assert runtime.app.state.value == 0


@pytest.mark.asyncio
async def test_dispatch_event_unknown_type_is_ignored() -> None:
    """An event whose type has no matching on_<type> handler is ignored."""
    transport = WasmTransport(lambda _patches: None)
    runtime: WasmRuntime[CounterState] = WasmRuntime(
        CounterState(), counter_view, transport
    )
    runtime.start()
    await runtime.dispatch_event({"type": "input", "key": "inc", "payload": {}})
    assert runtime.app.state.value == 0


@pytest.mark.asyncio
async def test_dispatch_event_coerces_payload_to_typed_event() -> None:
    """An arg-accepting handler receives the typed event the widget declares.

    ``Button.on_click`` is schema'd as a ``TapEvent``, so the wire payload is
    validated into one (``event.x``) rather than handed over as a raw dict.
    """
    received: list[Any] = []

    def view(_app: App[None]) -> Widget:
        return Button(label="x", on_click=received.append, key="b")

    transport = WasmTransport(lambda _patches: None)
    runtime: WasmRuntime[None] = WasmRuntime(None, view, transport)
    runtime.start()
    await runtime.dispatch_event({"type": "click", "key": "b", "payload": {"x": 1.0}})
    assert len(received) == 1
    assert received[0].x == 1.0


@pytest.mark.asyncio
async def test_dispatch_event_awaits_async_handler() -> None:
    """An async handler is awaited before dispatch returns."""
    done: list[bool] = []

    async def handler() -> None:
        await asyncio.sleep(0)
        done.append(True)

    def view(_app: App[None]) -> Widget:
        return Button(label="x", on_click=handler, key="b")

    transport = WasmTransport(lambda _patches: None)
    runtime: WasmRuntime[None] = WasmRuntime(None, view, transport)
    runtime.start()
    await runtime.dispatch_event({"type": "click", "key": "b", "payload": {}})
    assert done == [True]


@pytest.mark.asyncio
async def test_run_dispatches_until_closed() -> None:
    """run() drains queued events and exits cleanly when the transport closes."""
    transport = WasmTransport(lambda _patches: None)
    runtime: WasmRuntime[CounterState] = WasmRuntime(
        CounterState(), counter_view, transport
    )
    runtime.start()
    task = asyncio.ensure_future(runtime.run())

    transport.push_event({"type": "click", "key": "inc", "payload": {}})
    transport.push_event({"type": "click", "key": "inc", "payload": {}})
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    await transport.close()
    await asyncio.wait_for(task, timeout=1.0)

    assert runtime.app.state.value == 2
