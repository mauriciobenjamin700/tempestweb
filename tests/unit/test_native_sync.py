"""Tests for the ``native.sync`` capability (configurable read+write sync).

A fake bridge stands in for the browser controller: each capability call returns
a scripted ``native_result`` value. The Python side is the typed awaitable
surface over the ``sync.*`` dispatch.
"""

from __future__ import annotations

from typing import Any

import pytest

from tempestweb.native import (
    SyncState,
    SyncSummary,
    install_bridge,
    sync,
    uninstall_bridge,
)


class ScriptedBridge:
    """Fake :class:`NativeBridge` returning scripted ``native_result`` values."""

    def __init__(self, script: list[Any]) -> None:
        self.script: list[Any] = script
        self.calls: list[dict[str, Any]] = []

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(envelope)
        return {"ok": True, "value": self.script.pop(0)}


@pytest.fixture(autouse=True)
def _clean_bridge() -> Any:
    uninstall_bridge()
    yield
    uninstall_bridge()


async def test_configure_sends_the_source_config() -> None:
    bridge = ScriptedBridge([{"configured": True, "name": "notes"}])
    install_bridge(bridge)
    await sync.configure("notes", "/api/notes", "app-db", "notes", watermark_key="wm")
    args = bridge.calls[0]["args"]
    assert bridge.calls[0]["capability"] == "sync.configure"
    assert args["name"] == "notes"
    assert args["url"] == "/api/notes"
    assert args["database"] == "app-db"
    assert args["table"] == "notes"
    assert args["watermark_key"] == "wm"


async def test_now_returns_a_summary() -> None:
    bridge = ScriptedBridge(
        [{"sent": 2, "remaining": 1, "failed": 0, "conflicts": 0, "applied": 5}]
    )
    install_bridge(bridge)
    summary = await sync.now("notes")
    assert isinstance(summary, SyncSummary)
    assert summary.sent == 2
    assert summary.applied == 5
    assert summary.remaining == 1


async def test_status_returns_state() -> None:
    bridge = ScriptedBridge(
        [
            {
                "phase": "idle",
                "online": True,
                "pending": 3,
                "last_synced_at": 111,
                "last_summary": {"sent": 1, "remaining": 0, "applied": 2},
                "error": None,
            }
        ]
    )
    install_bridge(bridge)
    state = await sync.status("notes")
    assert isinstance(state, SyncState)
    assert state.pending == 3
    assert state.last_synced_at == 111
    assert state.last_summary is not None
    assert state.last_summary.applied == 2


def test_sync_is_a_mode_c_capability() -> None:
    from tempestweb.native import mode_c_capability_names, streaming_capability_names

    names = mode_c_capability_names()
    assert {"sync.configure", "sync.now", "sync.status"} <= names
    assert "sync.watch" in streaming_capability_names()
