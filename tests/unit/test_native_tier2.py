"""Unit tests for the Tier-2 native capability Python facades (Track N).

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
    FileHandle,
    Recording,
    Voice,
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


# --- speech ----------------------------------------------------------------


async def test_speech_speak_defaults() -> None:
    bridge = _install({"speech.speak": {}})
    result = await native.speech.speak("hello")
    assert result is None
    assert bridge.calls[0]["capability"] == "speech.speak"
    assert bridge.calls[0]["args"] == {
        "text": "hello",
        "lang": "",
        "rate": 1.0,
        "pitch": 1.0,
        "volume": 1.0,
    }


async def test_speech_speak_explicit() -> None:
    bridge = _install({"speech.speak": {}})
    await native.speech.speak("oi", lang="pt-BR", rate=1.5, pitch=0.8, volume=0.5)
    assert bridge.calls[0]["args"] == {
        "text": "oi",
        "lang": "pt-BR",
        "rate": 1.5,
        "pitch": 0.8,
        "volume": 0.5,
    }


async def test_speech_cancel() -> None:
    bridge = _install({"speech.cancel": {}})
    await native.speech.cancel()
    assert bridge.calls[0]["capability"] == "speech.cancel"
    assert bridge.calls[0]["args"] == {}


async def test_speech_voices() -> None:
    bridge = _install(
        {
            "speech.voices": {
                "voices": [
                    {"name": "Alice", "lang": "en-US", "default": True},
                    {"name": "Bruno", "lang": "pt-BR", "default": False},
                ]
            }
        }
    )
    result = await native.speech.voices()
    assert result == [
        Voice(name="Alice", lang="en-US", default=True),
        Voice(name="Bruno", lang="pt-BR", default=False),
    ]
    assert bridge.calls[0]["capability"] == "speech.voices"
    assert bridge.calls[0]["args"] == {}


async def test_speech_voices_empty() -> None:
    _install({"speech.voices": {}})
    assert await native.speech.voices() == []


# --- recorder --------------------------------------------------------------


async def test_recorder_start_defaults() -> None:
    bridge = _install({"recorder.start": {"id": "rec-1"}})
    rec_id = await native.recorder.start()
    assert rec_id == "rec-1"
    assert bridge.calls[0]["capability"] == "recorder.start"
    assert bridge.calls[0]["args"] == {"source": "microphone", "mime_type": ""}


async def test_recorder_start_screen() -> None:
    bridge = _install({"recorder.start": {"id": "rec-2"}})
    await native.recorder.start("screen", "video/webm")
    assert bridge.calls[0]["args"] == {"source": "screen", "mime_type": "video/webm"}


async def test_recorder_stop() -> None:
    bridge = _install(
        {
            "recorder.stop": {
                "data_base64": "aGk=",
                "mime_type": "audio/webm",
                "size": 3,
            }
        }
    )
    result = await native.recorder.stop("rec-1")
    assert result == Recording(data_base64="aGk=", mime_type="audio/webm", size=3)
    assert bridge.calls[0]["capability"] == "recorder.stop"
    assert bridge.calls[0]["args"] == {"id": "rec-1"}


# --- filesystem ------------------------------------------------------------


async def test_filesystem_open_file_defaults() -> None:
    bridge = _install(
        {
            "filesystem.open_file": {
                "files": [
                    {
                        "id": "fh-1",
                        "name": "a.txt",
                        "mime_type": "text/plain",
                        "data_base64": "aGk=",
                    }
                ]
            }
        }
    )
    result = await native.filesystem.open_file()
    assert result == [
        FileHandle(id="fh-1", name="a.txt", mime_type="text/plain", data_base64="aGk=")
    ]
    assert bridge.calls[0]["capability"] == "filesystem.open_file"
    assert bridge.calls[0]["args"] == {"accept": "", "multiple": False}


async def test_filesystem_open_file_explicit() -> None:
    bridge = _install({"filesystem.open_file": {}})
    result = await native.filesystem.open_file("image/*", multiple=True)
    assert result == []
    assert bridge.calls[0]["args"] == {"accept": "image/*", "multiple": True}


async def test_filesystem_write_file() -> None:
    bridge = _install({"filesystem.write_file": {"written": True}})
    result = await native.filesystem.write_file("fh-1", "aGk=")
    assert result is None
    assert bridge.calls[0]["capability"] == "filesystem.write_file"
    assert bridge.calls[0]["args"] == {"id": "fh-1", "data_base64": "aGk="}


async def test_filesystem_save_file_defaults() -> None:
    bridge = _install({"filesystem.save_file": {"id": "fh-9", "name": "out.bin"}})
    result = await native.filesystem.save_file("out.bin", "aGk=")
    assert result == FileHandle(
        id="fh-9",
        name="out.bin",
        mime_type="application/octet-stream",
        data_base64="",
    )
    assert bridge.calls[0]["capability"] == "filesystem.save_file"
    assert bridge.calls[0]["args"] == {
        "filename": "out.bin",
        "data_base64": "aGk=",
        "mime_type": "application/octet-stream",
    }


async def test_filesystem_save_file_explicit_mime() -> None:
    bridge = _install({"filesystem.save_file": {"id": "fh-9", "name": "out.png"}})
    result = await native.filesystem.save_file("out.png", "aGk=", "image/png")
    assert result.mime_type == "image/png"
    assert result.data_base64 == ""
    assert bridge.calls[0]["args"]["mime_type"] == "image/png"


# --- bgsync ----------------------------------------------------------------


async def test_bgsync_register() -> None:
    bridge = _install({"bgsync.register": {"registered": True}})
    assert await native.bgsync.register("outbox") is True
    assert bridge.calls[0]["capability"] == "bgsync.register"
    assert bridge.calls[0]["args"] == {"tag": "outbox"}


async def test_bgsync_register_periodic() -> None:
    bridge = _install({"bgsync.register_periodic": {"registered": False}})
    assert await native.bgsync.register_periodic("news", 3600000) is False
    assert bridge.calls[0]["capability"] == "bgsync.register_periodic"
    assert bridge.calls[0]["args"] == {"tag": "news", "min_interval_ms": 3600000}


# --- tabs ------------------------------------------------------------------


async def test_tabs_broadcast() -> None:
    bridge = _install({"tabs.broadcast": {}})
    result = await native.tabs.broadcast("room", {"hello": "world"})
    assert result is None
    assert bridge.calls[0]["capability"] == "tabs.broadcast"
    assert bridge.calls[0]["args"] == {
        "channel": "room",
        "message": {"hello": "world"},
    }


async def test_tabs_lock_defaults() -> None:
    bridge = _install({"tabs.lock": {"acquired": True}})
    assert await native.tabs.lock("job") is True
    assert bridge.calls[0]["capability"] == "tabs.lock"
    assert bridge.calls[0]["args"] == {"name": "job", "mode": "exclusive"}


async def test_tabs_lock_shared() -> None:
    bridge = _install({"tabs.lock": {"acquired": False}})
    assert await native.tabs.lock("job", "shared") is False
    assert bridge.calls[0]["args"] == {"name": "job", "mode": "shared"}


async def test_tabs_unlock() -> None:
    bridge = _install({"tabs.unlock": {}})
    await native.tabs.unlock("job")
    assert bridge.calls[0]["capability"] == "tabs.unlock"
    assert bridge.calls[0]["args"] == {"name": "job"}


# --- webauthn --------------------------------------------------------------


async def test_webauthn_create() -> None:
    bridge = _install({"webauthn.create": {"credential": {"id": "cred-1"}}})
    options: dict[str, Any] = {"challenge": "Y2g="}
    result = await native.webauthn.create(options)
    assert result == {"id": "cred-1"}
    assert bridge.calls[0]["capability"] == "webauthn.create"
    assert bridge.calls[0]["args"] == {"options": options}


async def test_webauthn_get() -> None:
    bridge = _install({"webauthn.get": {"credential": {"id": "cred-2"}}})
    options: dict[str, Any] = {"challenge": "Y2g="}
    result = await native.webauthn.get(options)
    assert result == {"id": "cred-2"}
    assert bridge.calls[0]["capability"] == "webauthn.get"
    assert bridge.calls[0]["args"] == {"options": options}


async def test_webauthn_get_empty_credential() -> None:
    _install({"webauthn.get": {}})
    assert await native.webauthn.get({}) == {}


async def test_webauthn_get_otp() -> None:
    bridge = _install({"webauthn.get_otp": {"code": "123456"}})
    assert await native.webauthn.get_otp() == "123456"
    assert bridge.calls[0]["capability"] == "webauthn.get_otp"
    assert bridge.calls[0]["args"] == {}
