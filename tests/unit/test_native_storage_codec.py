"""`storage.configure`: what the app asked for, and what will actually run.

The behaviour worth pinning is the **fallback**. A browser without
`CompressionStream` (Safari below 16.4) must not make `configure` raise: an app
that turned the codec on has to keep working there, with the store on plain
strings. So `supported` reports the truth and `active` reports what happened,
and neither of them is an exception.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from tempestweb.native import install_bridge, storage, uninstall_bridge
from tempestweb.native.storage import CODEC_DEFLATE, CODEC_JSON


class ScriptedBridge:
    """A fake bridge answering with scripted ``native_result`` values."""

    def __init__(self, script: list[Any]) -> None:
        self.script: list[Any] = script
        self.calls: list[dict[str, Any]] = []

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(envelope)
        outcome = self.script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return {"ok": True, "value": outcome}


@pytest.fixture(autouse=True)
def _clean_bridge() -> Any:
    uninstall_bridge()
    yield
    uninstall_bridge()


async def test_the_default_is_json_and_the_call_says_so() -> None:
    bridge = ScriptedBridge(
        [{"requested": CODEC_JSON, "active": CODEC_JSON, "supported": True}]
    )
    install_bridge(bridge)

    result = await storage.configure()

    assert bridge.calls[0]["args"] == {"codec": CODEC_JSON}
    assert (result.requested, result.active, result.supported) == (
        CODEC_JSON,
        CODEC_JSON,
        True,
    )


async def test_deflate_is_asked_for_by_name() -> None:
    bridge = ScriptedBridge(
        [{"requested": CODEC_DEFLATE, "active": CODEC_DEFLATE, "supported": True}]
    )
    install_bridge(bridge)

    result = await storage.configure(codec=CODEC_DEFLATE)

    assert bridge.calls[0]["args"] == {"codec": CODEC_DEFLATE}
    assert result.active == CODEC_DEFLATE
    assert result.supported


async def test_a_browser_without_compression_stream_falls_back_and_reports() -> None:
    """Safari below 16.4. This must not raise, or the app dies on that device."""
    bridge = ScriptedBridge(
        [{"requested": CODEC_DEFLATE, "active": CODEC_JSON, "supported": False}]
    )
    install_bridge(bridge)

    result = await storage.configure(codec=CODEC_DEFLATE)

    assert result.requested == CODEC_DEFLATE
    assert result.active == CODEC_JSON
    assert not result.supported


async def test_a_truncated_answer_defaults_to_the_safe_codec() -> None:
    bridge = ScriptedBridge([{}])
    install_bridge(bridge)

    result = await storage.configure(codec=CODEC_DEFLATE)

    assert result.requested == CODEC_DEFLATE
    assert result.active == CODEC_JSON
    assert not result.supported


async def test_the_result_is_frozen_because_it_is_an_answer_not_a_setting() -> None:
    bridge = ScriptedBridge(
        [{"requested": CODEC_JSON, "active": CODEC_JSON, "supported": True}]
    )
    install_bridge(bridge)
    result = await storage.configure()

    with pytest.raises(FrozenInstanceError):
        result.active = CODEC_DEFLATE  # type: ignore[misc]


def test_the_capability_is_in_the_contract_and_reaches_mode_c() -> None:
    from tempestweb.native import contract

    names = {cap.name for cap in contract.CAPABILITIES}
    mode_c = {cap.name for cap in contract.MODE_C_CAPABILITIES}

    assert "storage.configure" in names
    assert "storage.configure" in mode_c
