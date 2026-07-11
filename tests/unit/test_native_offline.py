"""Tests for the ``native.offline`` capability (durable mutation queue).

A fake bridge stands in for the browser queue: each capability call returns a
scripted ``native_result`` value. No IndexedDB, no browser — the Python side is
the typed awaitable surface over the ``offline.*`` dispatch.
"""

from __future__ import annotations

from typing import Any

import pytest

from tempestweb.native import (
    Mutation,
    ReplayResult,
    install_bridge,
    offline,
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


async def test_enqueue_returns_a_mutation() -> None:
    bridge = ScriptedBridge(
        [
            {
                "id": "row-1",
                "owner": "default",
                "idempotency_key": "k-1",
                "method": "POST",
                "url": "/api/todos",
                "attempts": 0,
                "status": "pending",
            }
        ]
    )
    install_bridge(bridge)
    row = await offline.enqueue("POST", "/api/todos", {"title": "x"})
    assert isinstance(row, Mutation)
    assert row.method == "POST"
    assert row.status == "pending"
    assert row.idempotency_key == "k-1"
    # The dispatched envelope carries the capability + args.
    assert bridge.calls[0]["capability"] == "offline.enqueue"
    assert bridge.calls[0]["args"]["url"] == "/api/todos"


async def test_pending_returns_a_list_of_mutations() -> None:
    bridge = ScriptedBridge(
        [
            {
                "mutations": [
                    {
                        "id": "a",
                        "owner": "default",
                        "idempotency_key": "k",
                        "method": "POST",
                        "url": "/a",
                        "attempts": 0,
                        "status": "pending",
                    }
                ]
            }
        ]
    )
    install_bridge(bridge)
    rows = await offline.pending()
    assert len(rows) == 1
    assert rows[0].url == "/a"


async def test_size_and_replay() -> None:
    bridge = ScriptedBridge([{"size": 3}, {"sent": 2, "remaining": 1}])
    install_bridge(bridge)
    assert await offline.size() == 3
    result = await offline.replay()
    assert isinstance(result, ReplayResult)
    assert result.sent == 2
    assert result.remaining == 1


def test_offline_is_a_mode_c_capability() -> None:
    from tempestweb.native import mode_c_capability_names

    names = mode_c_capability_names()
    offline_caps = {
        "offline.enqueue",
        "offline.pending",
        "offline.replay",
        "offline.size",
    }
    assert offline_caps <= names
