"""Test for nfc.scan — the streaming NFC read capability (T-EV)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from tempestweb.native import install_bridge, nfc, uninstall_bridge


@pytest.fixture(autouse=True)
def _clean_bridge() -> Any:
    uninstall_bridge()
    yield
    uninstall_bridge()


class _ScriptedEventBridge:
    """A bridge whose subscription replays a canned script of payloads."""

    def __init__(self, script: list[dict[str, Any]]) -> None:
        self._script = script
        self.capability: str = ""

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "value": {}}

    async def subscribe(
        self,
        capability: str,
        args: dict[str, Any],
        emit: Callable[[dict[str, Any]], None],
    ) -> str:
        self.capability = capability
        for payload in self._script:
            emit(payload)
        return "s1"

    async def unsubscribe(self, sub_id: str) -> None:
        return None


async def test_nfc_scan_yields_ndef_messages() -> None:
    bridge = _ScriptedEventBridge(
        [
            {
                "event": {
                    "serial_number": "04:a2:b3",
                    "records": [
                        {"record_type": "text", "media_type": "", "data_base64": "aGk="}
                    ],
                }
            },
            {"done": True},
        ]
    )
    install_bridge(bridge)

    messages = [msg async for msg in nfc.scan()]

    assert bridge.capability == "nfc.scan"
    assert len(messages) == 1
    assert messages[0].serial_number == "04:a2:b3"
    assert messages[0].records[0]["record_type"] == "text"
