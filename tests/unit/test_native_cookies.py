"""Tests for the typed `cookies` native capability wrapper.

Driven through a fake FFI bridge that records the dispatched ``native_call``
envelope and returns a scripted ``native_result`` — no browser present. Verifies
the dotted capability name, the args shape, and the typed return value.
"""

from __future__ import annotations

from typing import Any

import pytest

from tempestweb.native import cookies, install_bridge, uninstall_bridge


class RecordingBridge:
    """Fake FFI bridge: records the last envelope, returns a fixed value."""

    def __init__(self, value: Any, *, ok: bool = True) -> None:
        self.value: Any = value
        self.ok: bool = ok
        self.last: dict[str, Any] | None = None

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        self.last = envelope
        if not self.ok:
            return {"ok": False, "error": "failed"}
        return {"ok": True, "value": self.value}


@pytest.fixture(autouse=True)
def _clean_bridge() -> Any:
    uninstall_bridge()
    yield
    uninstall_bridge()


async def test_cookies_get_returns_value() -> None:
    bridge = RecordingBridge({"value": "abc"})
    install_bridge(bridge)
    result = await cookies.get("sid")
    assert result == "abc"
    assert bridge.last is not None
    assert bridge.last["capability"] == "cookies.get"
    assert bridge.last["args"] == {"name": "sid"}


async def test_cookies_get_absent_is_none() -> None:
    install_bridge(RecordingBridge({"value": None}))
    assert await cookies.get("nope") is None


async def test_cookies_set_sends_full_args() -> None:
    bridge = RecordingBridge(None)
    install_bridge(bridge)
    await cookies.set(
        "t", "v", max_age=60, path="/app", same_site="Strict", secure=True
    )
    assert bridge.last is not None
    assert bridge.last["capability"] == "cookies.set"
    assert bridge.last["args"] == {
        "name": "t",
        "value": "v",
        "max_age": 60,
        "path": "/app",
        "same_site": "Strict",
        "secure": True,
    }


async def test_cookies_remove_sends_name_and_path() -> None:
    bridge = RecordingBridge(None)
    install_bridge(bridge)
    await cookies.remove("t", path="/app")
    assert bridge.last is not None
    assert bridge.last["capability"] == "cookies.remove"
    assert bridge.last["args"] == {"name": "t", "path": "/app"}


async def test_cookies_all_returns_map() -> None:
    install_bridge(RecordingBridge({"a": "1", "b": "2"}))
    assert await cookies.all_cookies() == {"a": "1", "b": "2"}
