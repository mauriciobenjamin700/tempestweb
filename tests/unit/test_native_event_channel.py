"""Tests for the native event channel (T-EV) — streaming capabilities.

Covers the Python side of the seam: the :class:`ProxyBridge` (Mode B) and
:class:`FFIBridge` (Mode A) ``subscribe``/``unsubscribe`` paths, the
:func:`native_events` async iterator, and the ``geolocation.watch`` facade built
on top of it.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

from tempestweb.native import (
    BrowserUnavailableError,
    FFIBridge,
    NativeError,
    ProxyBridge,
    geolocation,
    install_bridge,
    native_events,
    uninstall_bridge,
)


@pytest.fixture(autouse=True)
def _clean_bridge() -> Any:
    uninstall_bridge()
    yield
    uninstall_bridge()


# --------------------------------------------------------------------------- #
# ProxyBridge (Mode B)                                                        #
# --------------------------------------------------------------------------- #


async def test_proxy_bridge_subscribe_sends_frame_and_routes_events() -> None:
    sent: list[dict[str, Any]] = []
    bridge = ProxyBridge(sent.append)
    received: list[dict[str, Any]] = []

    sub_id = await bridge.subscribe(
        "geolocation.watch", {"high_accuracy": True}, received.append
    )

    assert sent[-1] == {
        "kind": "native_subscribe",
        "sub_id": sub_id,
        "capability": "geolocation.watch",
        "args": {"high_accuracy": True},
    }

    # An inbound native_event is delivered to the subscription's emit.
    assert bridge.deliver_event(sub_id, {"event": {"latitude": 1.0}}) is True
    assert received == [{"event": {"latitude": 1.0}}]

    # A terminal event drops the subscription; later delivery finds nothing.
    assert bridge.deliver_event(sub_id, {"done": True}) is True
    assert bridge.deliver_event(sub_id, {"event": {"latitude": 2.0}}) is False


async def test_proxy_bridge_unsubscribe_sends_frame() -> None:
    sent: list[dict[str, Any]] = []
    bridge = ProxyBridge(sent.append)
    sub_id = await bridge.subscribe("geolocation.watch", {}, lambda _p: None)

    await bridge.unsubscribe(sub_id)

    assert sent[-1] == {"kind": "native_unsubscribe", "sub_id": sub_id}


async def test_proxy_bridge_close_ends_subscriptions() -> None:
    bridge = ProxyBridge(lambda _f: None)
    received: list[dict[str, Any]] = []
    await bridge.subscribe("geolocation.watch", {}, received.append)

    bridge.close()

    assert received == [{"error": "transport_closed"}]


# --------------------------------------------------------------------------- #
# FFIBridge (Mode A)                                                          #
# --------------------------------------------------------------------------- #


async def test_ffi_bridge_subscribe_wires_emit_and_unsubscribe() -> None:
    captured: dict[str, Any] = {}

    async def fake_dispatch(_raw: str) -> str:
        return json.dumps({"ok": True, "value": {}})

    async def fake_subscribe(envelope_json: str, emit: Callable[[str], None]) -> str:
        captured["envelope"] = json.loads(envelope_json)
        captured["emit"] = emit
        return "js-token"

    async def fake_unsubscribe(sub_id: str) -> None:
        captured["unsubscribed"] = sub_id

    bridge = FFIBridge(fake_dispatch, fake_subscribe, fake_unsubscribe)
    received: list[dict[str, Any]] = []

    sub_id = await bridge.subscribe(
        "geolocation.watch", {"high_accuracy": False}, received.append
    )

    assert captured["envelope"]["capability"] == "geolocation.watch"
    assert captured["envelope"]["sub_id"] == sub_id
    assert captured["envelope"]["args"] == {"high_accuracy": False}

    # The browser calls emit with a JSON string; it reaches Python as a dict.
    captured["emit"](json.dumps({"event": {"latitude": 3.0}}))
    assert received == [{"event": {"latitude": 3.0}}]

    await bridge.unsubscribe(sub_id)
    assert captured["unsubscribed"] == sub_id


async def test_ffi_bridge_without_subscribe_callable_raises() -> None:
    async def fake_dispatch(_raw: str) -> str:
        return json.dumps({"ok": True, "value": {}})

    bridge = FFIBridge(fake_dispatch)

    with pytest.raises(BrowserUnavailableError):
        await bridge.subscribe("geolocation.watch", {}, lambda _p: None)


# --------------------------------------------------------------------------- #
# native_events iterator + geolocation.watch facade                          #
# --------------------------------------------------------------------------- #


class _ScriptedEventBridge:
    """A bridge whose subscription replays a canned script of payloads."""

    def __init__(self, script: list[dict[str, Any]]) -> None:
        self._script = script
        self.unsubscribed: list[str] = []

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "value": {}}

    async def subscribe(
        self,
        capability: str,
        args: dict[str, Any],
        emit: Callable[[dict[str, Any]], None],
    ) -> str:
        for payload in self._script:
            emit(payload)
        return "s1"

    async def unsubscribe(self, sub_id: str) -> None:
        self.unsubscribed.append(sub_id)


async def test_native_events_yields_until_done_then_unsubscribes() -> None:
    bridge = _ScriptedEventBridge(
        [
            {"event": {"n": 1}},
            {"event": {"n": 2}},
            {"done": True},
        ]
    )
    install_bridge(bridge)

    seen = [event async for event in native_events("geolocation.watch", {})]

    assert seen == [{"n": 1}, {"n": 2}]
    assert bridge.unsubscribed == ["s1"]


async def test_native_events_raises_on_error_payload() -> None:
    bridge = _ScriptedEventBridge([{"error": "permission_denied", "message": "no"}])
    install_bridge(bridge)

    with pytest.raises(NativeError) as exc:
        async for _event in native_events("geolocation.watch", {}):
            pass

    assert exc.value.code == "permission_denied"
    assert bridge.unsubscribed == ["s1"]


async def test_native_events_requires_a_streaming_bridge() -> None:
    class _CallOnly:
        async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
            return {"ok": True, "value": {}}

    install_bridge(_CallOnly())

    with pytest.raises(BrowserUnavailableError):
        async for _event in native_events("geolocation.watch", {}):
            pass


async def test_geolocation_watch_yields_positions() -> None:
    bridge = _ScriptedEventBridge(
        [
            {"event": {"latitude": 1.0, "longitude": 2.0, "accuracy": 5.0}},
            {"event": {"latitude": 1.5, "longitude": 2.5, "accuracy": 4.0}},
            {"done": True},
        ]
    )
    install_bridge(bridge)

    fixes = [pos async for pos in geolocation.watch()]

    assert [(p.latitude, p.longitude) for p in fixes] == [(1.0, 2.0), (1.5, 2.5)]
    assert fixes[0].accuracy == 5.0
