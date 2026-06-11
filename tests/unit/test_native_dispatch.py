"""Tests for the native dispatch seam and the two execution-mode bridges.

These tests exercise the Mode-A (FFI) vs Mode-B (proxy) split with fake bridges —
no browser, no Pyodide, no FastAPI. They lock the wire shape against
``docs/contract.md`` (``native_call`` / ``native_result`` / ``call_id``).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from tempestweb.native import (
    BrowserUnavailableError,
    FFIBridge,
    NativeError,
    ProxyBridge,
    current_bridge,
    install_bridge,
    native_call,
    send_native_call,
    uninstall_bridge,
)


@pytest.fixture(autouse=True)
def _clean_bridge() -> Any:
    """Ensure no bridge leaks across tests."""
    uninstall_bridge()
    yield
    uninstall_bridge()


def test_native_call_envelope_matches_contract() -> None:
    envelope = native_call("geolocation.get", {"high_accuracy": True}, "c1")
    assert envelope == {
        "kind": "native_call",
        "call_id": "c1",
        "capability": "geolocation.get",
        "args": {"high_accuracy": True},
    }


def test_current_bridge_raises_off_platform() -> None:
    with pytest.raises(BrowserUnavailableError):
        current_bridge()


async def test_send_native_call_raises_without_bridge() -> None:
    with pytest.raises(BrowserUnavailableError):
        await send_native_call("clipboard.read", {})


async def test_ffi_bridge_resolves_value_in_process() -> None:
    seen: list[dict[str, Any]] = []

    async def dispatch(envelope_json: str) -> str:
        seen.append(json.loads(envelope_json))
        return json.dumps({"ok": True, "value": {"text": "hello"}})

    install_bridge(FFIBridge(dispatch))
    value = await send_native_call("clipboard.read", {})

    assert value == {"text": "hello"}
    assert seen[0]["kind"] == "native_call"
    assert seen[0]["capability"] == "clipboard.read"
    assert seen[0]["call_id"].startswith("c")


async def test_ffi_bridge_error_becomes_native_error() -> None:
    async def dispatch(_: str) -> str:
        return json.dumps(
            {"ok": False, "error": "permission_denied", "message": "blocked"}
        )

    install_bridge(FFIBridge(dispatch))
    with pytest.raises(NativeError) as exc:
        await send_native_call("clipboard.read", {})
    assert exc.value.code == "permission_denied"


async def test_proxy_bridge_round_trip_resolves_by_call_id() -> None:
    sent: list[dict[str, Any]] = []
    bridge = ProxyBridge(sent.append)
    install_bridge(bridge)

    async def driver() -> dict[str, Any]:
        return await send_native_call("geolocation.get", {"high_accuracy": True})

    task = asyncio.create_task(driver())
    await asyncio.sleep(0)  # let the call register its pending future

    assert len(sent) == 1
    frame = sent[0]
    assert frame["kind"] == "native_call"
    call_id = frame["call_id"]

    resolved = bridge.resolve(
        call_id, {"ok": True, "value": {"latitude": -23.5, "longitude": -46.6}}
    )
    assert resolved is True

    value = await task
    assert value == {"latitude": -23.5, "longitude": -46.6}


async def test_proxy_bridge_resolve_unknown_call_id_is_false() -> None:
    bridge = ProxyBridge(lambda _: None)
    assert bridge.resolve("nope", {"ok": True, "value": {}}) is False


async def test_proxy_bridge_close_cancels_in_flight() -> None:
    bridge = ProxyBridge(lambda _: None)
    install_bridge(bridge)

    task = asyncio.create_task(send_native_call("geolocation.get", {}))
    await asyncio.sleep(0)
    bridge.close()

    with pytest.raises(asyncio.CancelledError):
        await task


async def test_proxy_bridge_call_after_close_raises() -> None:
    bridge = ProxyBridge(lambda _: None)
    bridge.close()
    install_bridge(bridge)
    with pytest.raises(BrowserUnavailableError):
        await send_native_call("geolocation.get", {})
