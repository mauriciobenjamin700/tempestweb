"""Tests for the typed capability wrappers (audio, share, geo, clipboard, ...).

Each capability is driven through a fake FFI bridge that records the dispatched
``native_call`` envelope and returns a scripted ``native_result``. This verifies
the dotted capability name, the args shape, and the typed return value — with no
browser present.
"""

from __future__ import annotations

from typing import Any

import pytest

from tempestweb.native import (
    NativeError,
    NotificationPermission,
    Photo,
    PlayResult,
    Position,
    ShareOutcome,
    ShareResult,
    audio,
    camera,
    clipboard,
    geolocation,
    install_bridge,
    notifications,
    share,
    storage,
    uninstall_bridge,
)


class RecordingBridge:
    """Fake FFI bridge: records the last envelope, returns a fixed value."""

    def __init__(self, value: dict[str, Any], *, ok: bool = True) -> None:
        self.value: dict[str, Any] = value
        self.ok: bool = ok
        self.last: dict[str, Any] | None = None

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        self.last = envelope
        if not self.ok:
            return {"ok": False, "error": self.value.get("error", "failed")}
        return {"ok": True, "value": self.value}


@pytest.fixture(autouse=True)
def _clean_bridge() -> Any:
    uninstall_bridge()
    yield
    uninstall_bridge()


async def test_geolocation_get_returns_position() -> None:
    bridge = RecordingBridge({"latitude": -23.5, "longitude": -46.6, "accuracy": 10.0})
    install_bridge(bridge)
    pos = await geolocation.get(high_accuracy=False)
    assert isinstance(pos, Position)
    assert pos.latitude == -23.5
    assert pos.altitude is None
    assert bridge.last is not None
    assert bridge.last["capability"] == "geolocation.get"
    assert bridge.last["args"] == {"high_accuracy": False}


async def test_geolocation_permission_denied_raises() -> None:
    bridge = RecordingBridge({"error": "permission_denied"}, ok=False)
    install_bridge(bridge)
    with pytest.raises(NativeError) as exc:
        await geolocation.get()
    assert exc.value.code == "permission_denied"


async def test_clipboard_write_then_read() -> None:
    bridge = RecordingBridge({"text": "copied"})
    install_bridge(bridge)
    await clipboard.write("copied")
    assert bridge.last is not None
    assert bridge.last["capability"] == "clipboard.write"
    assert bridge.last["args"] == {"text": "copied"}
    text = await clipboard.read()
    assert text == "copied"
    assert bridge.last["capability"] == "clipboard.read"


async def test_storage_put_get_list_remove() -> None:
    bridge = RecordingBridge({"content": "v", "keys": ["a", "b"]})
    install_bridge(bridge)

    await storage.put("a", "v")
    assert bridge.last is not None
    assert bridge.last["capability"] == "storage.put"
    assert bridge.last["args"] == {"name": "a", "content": "v"}

    assert await storage.get("a") == "v"
    assert bridge.last["capability"] == "storage.get"

    keys = await storage.list_keys()
    assert keys == ["a", "b"]
    assert bridge.last["capability"] == "storage.list"

    await storage.remove("a")
    assert bridge.last["capability"] == "storage.remove"


async def test_storage_list_empty_returns_empty_list() -> None:
    bridge = RecordingBridge({})  # no "keys" key
    install_bridge(bridge)
    assert await storage.list_keys() == []


async def test_audio_play_returns_play_result() -> None:
    bridge = RecordingBridge({"played": True, "channel": "fx"})
    install_bridge(bridge)
    res = await audio.play("/audio/plim.wav", volume=0.4, channel="fx")
    assert isinstance(res, PlayResult)
    assert res.played is True
    assert res.blocked is False
    assert bridge.last is not None
    assert bridge.last["capability"] == "audio.play"
    assert bridge.last["args"]["volume"] == 0.4


async def test_audio_play_clamps_volume() -> None:
    bridge = RecordingBridge({"played": True})
    install_bridge(bridge)
    await audio.play("/x.wav", volume=5.0)
    assert bridge.last is not None
    assert bridge.last["args"]["volume"] == 1.0


async def test_audio_play_blocked_is_not_an_error() -> None:
    bridge = RecordingBridge({"played": False, "blocked": True})
    install_bridge(bridge)
    res = await audio.play("/x.wav")
    assert res.played is False
    assert res.blocked is True


async def test_audio_stop() -> None:
    bridge = RecordingBridge({})
    install_bridge(bridge)
    await audio.stop("fx")
    assert bridge.last is not None
    assert bridge.last["capability"] == "audio.stop"
    assert bridge.last["args"] == {"channel": "fx"}


async def test_share_supported_and_shared() -> None:
    bridge = RecordingBridge({"outcome": "shared"})
    install_bridge(bridge)
    res = await share(title="Hi", url="https://example.com")
    assert isinstance(res, ShareResult)
    assert res.outcome is ShareOutcome.SHARED
    assert bridge.last is not None
    assert bridge.last["capability"] == "share.share"
    assert bridge.last["args"]["files"] == []


async def test_share_unsupported_is_normal_outcome() -> None:
    bridge = RecordingBridge({"outcome": "unsupported"})
    install_bridge(bridge)
    res = await share(text="x")
    assert res.outcome is ShareOutcome.UNSUPPORTED


async def test_is_share_supported() -> None:
    install_bridge(RecordingBridge({"supported": True}))
    from tempestweb.native import is_share_supported

    assert await is_share_supported() is True


async def test_camera_capture_returns_photo_with_bytes() -> None:
    # base64 of b"\x01\x02\x03" is "AQID"
    bridge = RecordingBridge(
        {"mime_type": "image/png", "width": 4, "height": 4, "data_base64": "AQID"}
    )
    install_bridge(bridge)
    photo = await camera.capture(facing="user", quality=0.5)
    assert isinstance(photo, Photo)
    assert photo.mime_type == "image/png"
    assert photo.to_bytes() == b"\x01\x02\x03"
    assert bridge.last is not None
    assert bridge.last["capability"] == "camera.capture"
    assert bridge.last["args"] == {
        "facing": "user",
        "quality": 0.5,
        "mime_type": "image/jpeg",
    }


async def test_notifications_notify_and_permission() -> None:
    bridge = RecordingBridge({"permission": "granted"})
    install_bridge(bridge)
    await notifications.notify("Title", "Body")
    assert bridge.last is not None
    assert bridge.last["capability"] == "notifications.notify"

    perm = await notifications.request_permission()
    assert perm is NotificationPermission.GRANTED
