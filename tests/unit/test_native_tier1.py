"""Unit tests for the Tier-1 native capability Python facades (Track N).

Each capability is driven through a scripted fake bridge that records the outgoing
``native_call`` envelopes and returns a canned result. The tests assert that every
Python awaitable dispatches the right dotted capability with the right args and
unwraps the result dict into the documented Python return shape.
"""

from __future__ import annotations

from typing import Any

import pytest

from tempestweb import native
from tempestweb.native import (
    ClipboardImage,
    NetworkState,
    OrientationState,
    StorageEstimate,
    install_bridge,
    uninstall_bridge,
)


class _ScriptedBridge:
    """Fake bridge returning canned values per capability, recording every call."""

    def __init__(self, responses: dict[str, dict[str, Any]]) -> None:
        """Initialize the bridge.

        Args:
            responses: Mapping of dotted capability name to the ``value`` payload
                the browser handler would return.
        """
        self.responses: dict[str, dict[str, Any]] = responses
        self.calls: list[dict[str, Any]] = []

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Record the envelope and return the canned success result.

        Args:
            envelope: The ``native_call`` envelope to dispatch.

        Returns:
            A success result envelope wrapping the scripted value.
        """
        self.calls.append(envelope)
        cap = envelope["capability"]
        return {"ok": True, "value": self.responses.get(cap, {})}


@pytest.fixture(autouse=True)
def _clean_bridge() -> Any:  # noqa: ANN401
    """Ensure each test starts and ends with no bridge installed."""
    uninstall_bridge()
    yield
    uninstall_bridge()


def _install(responses: dict[str, dict[str, Any]]) -> _ScriptedBridge:
    """Install a scripted bridge with the given canned responses.

    Args:
        responses: Mapping of capability name to its canned ``value`` payload.

    Returns:
        The installed bridge, so tests can inspect ``calls``.
    """
    bridge = _ScriptedBridge(responses)
    install_bridge(bridge)
    return bridge


async def test_vibration_vibrate_single_duration() -> None:
    bridge = _install({"vibration.vibrate": {}})
    result = await native.vibration.vibrate(200)
    assert result is None
    assert bridge.calls[0]["capability"] == "vibration.vibrate"
    assert bridge.calls[0]["args"] == {"pattern": 200}


async def test_vibration_vibrate_pattern() -> None:
    bridge = _install({"vibration.vibrate": {}})
    await native.vibration.vibrate([100, 30, 100])
    assert bridge.calls[0]["args"] == {"pattern": [100, 30, 100]}


async def test_badge_set_with_count() -> None:
    bridge = _install({"badge.set": {}})
    await native.badge.set_badge(5)
    assert bridge.calls[0]["capability"] == "badge.set"
    assert bridge.calls[0]["args"] == {"count": 5}


async def test_badge_set_generic_dot() -> None:
    bridge = _install({"badge.set": {}})
    await native.badge.set_badge()
    assert bridge.calls[0]["args"] == {"count": None}


async def test_badge_clear() -> None:
    bridge = _install({"badge.clear": {}})
    await native.badge.clear()
    assert bridge.calls[0]["capability"] == "badge.clear"
    assert bridge.calls[0]["args"] == {}


async def test_wakelock_request_returns_id() -> None:
    bridge = _install({"wakelock.request": {"id": "wl-1"}})
    lock_id = await native.wakelock.request()
    assert lock_id == "wl-1"
    assert bridge.calls[0]["capability"] == "wakelock.request"
    assert bridge.calls[0]["args"] == {}


async def test_wakelock_release() -> None:
    bridge = _install({"wakelock.release": {}})
    await native.wakelock.release("wl-1")
    assert bridge.calls[0]["capability"] == "wakelock.release"
    assert bridge.calls[0]["args"] == {"id": "wl-1"}


async def test_fullscreen_enter() -> None:
    bridge = _install({"fullscreen.enter": {"active": True}})
    assert await native.fullscreen.enter() is True
    assert bridge.calls[0]["capability"] == "fullscreen.enter"
    assert bridge.calls[0]["args"] == {}


async def test_fullscreen_exit() -> None:
    bridge = _install({"fullscreen.exit": {"active": False}})
    assert await native.fullscreen.exit() is False
    assert bridge.calls[0]["capability"] == "fullscreen.exit"


async def test_fullscreen_state() -> None:
    bridge = _install({"fullscreen.state": {"active": True}})
    assert await native.fullscreen.state() is True
    assert bridge.calls[0]["capability"] == "fullscreen.state"


async def test_visibility_state() -> None:
    bridge = _install({"visibility.state": {"state": "hidden", "hidden": True}})
    assert await native.visibility.state() == "hidden"
    assert bridge.calls[0]["capability"] == "visibility.state"
    assert bridge.calls[0]["args"] == {}


async def test_orientation_lock() -> None:
    bridge = _install({"orientation.lock": {"locked": True}})
    assert await native.orientation.lock("portrait") is True
    assert bridge.calls[0]["capability"] == "orientation.lock"
    assert bridge.calls[0]["args"] == {"kind": "portrait"}


async def test_orientation_unlock() -> None:
    bridge = _install({"orientation.unlock": {}})
    await native.orientation.unlock()
    assert bridge.calls[0]["capability"] == "orientation.unlock"
    assert bridge.calls[0]["args"] == {}


async def test_orientation_state() -> None:
    bridge = _install({"orientation.state": {"type": "landscape-primary", "angle": 90}})
    result = await native.orientation.state()
    assert result == OrientationState(type="landscape-primary", angle=90)
    assert bridge.calls[0]["capability"] == "orientation.state"


async def test_quota_estimate() -> None:
    bridge = _install({"quota.estimate": {"usage": 1024, "quota": 8192}})
    result = await native.quota.estimate()
    assert result == StorageEstimate(usage=1024, quota=8192)
    assert bridge.calls[0]["capability"] == "quota.estimate"
    assert bridge.calls[0]["args"] == {}


async def test_quota_persist() -> None:
    bridge = _install({"quota.persist": {"persisted": True}})
    assert await native.quota.persist() is True
    assert bridge.calls[0]["capability"] == "quota.persist"


async def test_quota_persisted() -> None:
    bridge = _install({"quota.persisted": {"persisted": False}})
    assert await native.quota.persisted() is False
    assert bridge.calls[0]["capability"] == "quota.persisted"


async def test_network_state() -> None:
    bridge = _install(
        {
            "network.state": {
                "online": True,
                "effective_type": "4g",
                "downlink": 10.5,
                "rtt": 50,
                "save_data": False,
            }
        }
    )
    result = await native.network.state()
    assert result == NetworkState(
        online=True,
        effective_type="4g",
        downlink=10.5,
        rtt=50,
        save_data=False,
    )
    assert bridge.calls[0]["capability"] == "network.state"
    assert bridge.calls[0]["args"] == {}


async def test_clipboard_read_image() -> None:
    bridge = _install(
        {"clipboard.read_image": {"data_base64": "aGk=", "mime_type": "image/png"}}
    )
    result = await native.clipboard.read_image()
    assert result == ClipboardImage(data_base64="aGk=", mime_type="image/png")
    assert bridge.calls[0]["capability"] == "clipboard.read_image"
    assert bridge.calls[0]["args"] == {}


async def test_clipboard_write_image_default_mime() -> None:
    bridge = _install({"clipboard.write_image": {}})
    await native.clipboard.write_image("aGk=")
    assert bridge.calls[0]["capability"] == "clipboard.write_image"
    assert bridge.calls[0]["args"] == {"data_base64": "aGk=", "mime_type": "image/png"}


async def test_clipboard_write_image_explicit_mime() -> None:
    bridge = _install({"clipboard.write_image": {}})
    await native.clipboard.write_image("aGk=", "image/jpeg")
    assert bridge.calls[0]["args"] == {
        "data_base64": "aGk=",
        "mime_type": "image/jpeg",
    }
