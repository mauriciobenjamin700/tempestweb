"""Tests for the streaming native capabilities (native event channel / T-EV).

Each streaming capability is an async generator built on
:func:`~tempestweb.native.native_events`. These tests install a scripted event
bridge that replays a canned list of ``{"event": ...}`` payloads terminated by
``{"done": True}``, consume the generator, and assert both the yielded
values/models and the dotted capability name + args that were requested.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from tempestweb.native import (
    battery,
    gamepad,
    idle,
    install_bridge,
    midi,
    network,
    orientation,
    sensors,
    speech,
    tabs,
    uninstall_bridge,
    visibility,
)


@pytest.fixture(autouse=True)
def _clean_bridge() -> Any:
    uninstall_bridge()
    yield
    uninstall_bridge()


class _ScriptedEventBridge:
    """A bridge whose ``subscribe`` replays a canned script and records the request.

    Attributes:
        requested: The ``(capability, args)`` pairs passed to :meth:`subscribe`.
        unsubscribed: The subscription ids passed to :meth:`unsubscribe`.
    """

    def __init__(self, script: list[dict[str, Any]]) -> None:
        """Initialize the bridge.

        Args:
            script: The payloads to replay through ``emit`` on every subscribe.
        """
        self._script = script
        self.requested: list[tuple[str, dict[str, Any]]] = []
        self.unsubscribed: list[str] = []

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Satisfy the single-shot half of the bridge protocol (unused here)."""
        return {"ok": True, "value": {}}

    async def subscribe(
        self,
        capability: str,
        args: dict[str, Any],
        emit: Callable[[dict[str, Any]], None],
    ) -> str:
        """Record the request and replay the scripted payloads through ``emit``."""
        self.requested.append((capability, args))
        for payload in self._script:
            emit(payload)
        return "s1"

    async def unsubscribe(self, sub_id: str) -> None:
        """Record that the subscription was closed."""
        self.unsubscribed.append(sub_id)


def _events(*values: Any) -> list[dict[str, Any]]:
    """Wrap raw event values into ``{"event": value}`` payloads plus a ``done``."""
    return [{"event": value} for value in values] + [{"done": True}]


async def test_battery_watch_yields_status_models() -> None:
    bridge = _ScriptedEventBridge(
        _events(
            {
                "level": 0.8,
                "charging": True,
                "charging_time": 1200.0,
                "discharging_time": 0.0,
            },
            {
                "level": 0.81,
                "charging": True,
                "charging_time": 1100.0,
                "discharging_time": 0.0,
            },
        )
    )
    install_bridge(bridge)

    seen = [status async for status in battery.watch()]

    assert [s.level for s in seen] == [0.8, 0.81]
    assert seen[0].charging is True
    assert seen[0].charging_time == 1200.0
    assert bridge.requested == [("battery.watch", {})]
    assert bridge.unsubscribed == ["s1"]


async def test_idle_watch_yields_state_and_passes_threshold() -> None:
    bridge = _ScriptedEventBridge(
        _events(
            {"user": "active", "screen": "unlocked"},
            {"user": "idle", "screen": "locked"},
        )
    )
    install_bridge(bridge)

    seen = [s async for s in idle.watch(threshold_seconds=120)]

    assert [(s.user, s.screen) for s in seen] == [
        ("active", "unlocked"),
        ("idle", "locked"),
    ]
    assert bridge.requested == [("idle.watch", {"threshold_seconds": 120})]
    assert bridge.unsubscribed == ["s1"]


async def test_sensors_orientation_yields_readings() -> None:
    bridge = _ScriptedEventBridge(
        _events(
            {"alpha": 10.0, "beta": 20.0, "gamma": None, "absolute": True},
        )
    )
    install_bridge(bridge)

    seen = [r async for r in sensors.orientation()]

    assert seen[0].alpha == 10.0
    assert seen[0].gamma is None
    assert seen[0].absolute is True
    assert bridge.requested == [("sensors.orientation", {})]
    assert bridge.unsubscribed == ["s1"]


async def test_sensors_motion_yields_readings() -> None:
    bridge = _ScriptedEventBridge(
        _events(
            {
                "acceleration": {"x": 0.1, "y": 0.2, "z": None},
                "rotation_rate": {"alpha": 1.0, "beta": None, "gamma": 2.0},
                "interval": 16.0,
            },
        )
    )
    install_bridge(bridge)

    seen = [m async for m in sensors.motion()]

    assert seen[0].acceleration == {"x": 0.1, "y": 0.2, "z": None}
    assert seen[0].rotation_rate == {"alpha": 1.0, "beta": None, "gamma": 2.0}
    assert seen[0].interval == 16.0
    assert bridge.requested == [("sensors.motion", {})]
    assert bridge.unsubscribed == ["s1"]


async def test_network_watch_yields_states() -> None:
    bridge = _ScriptedEventBridge(
        _events(
            {
                "online": True,
                "effective_type": "4g",
                "downlink": 10.0,
                "rtt": 50,
                "save_data": False,
            },
            {
                "online": False,
                "effective_type": "",
                "downlink": 0.0,
                "rtt": 0,
                "save_data": False,
            },
        )
    )
    install_bridge(bridge)

    seen = [n async for n in network.watch()]

    assert [n.online for n in seen] == [True, False]
    assert seen[0].effective_type == "4g"
    assert seen[0].rtt == 50
    assert bridge.requested == [("network.watch", {})]
    assert bridge.unsubscribed == ["s1"]


async def test_orientation_watch_yields_states() -> None:
    bridge = _ScriptedEventBridge(
        _events(
            {"type": "portrait-primary", "angle": 0},
            {"type": "landscape-primary", "angle": 90},
        )
    )
    install_bridge(bridge)

    seen = [o async for o in orientation.watch()]

    assert [(o.type, o.angle) for o in seen] == [
        ("portrait-primary", 0),
        ("landscape-primary", 90),
    ]
    assert bridge.requested == [("orientation.watch", {})]
    assert bridge.unsubscribed == ["s1"]


async def test_visibility_watch_yields_state_strings() -> None:
    bridge = _ScriptedEventBridge(
        _events(
            {"state": "hidden", "hidden": True},
            {"state": "visible", "hidden": False},
        )
    )
    install_bridge(bridge)

    seen = [v async for v in visibility.watch()]

    assert seen == ["hidden", "visible"]
    assert bridge.requested == [("visibility.watch", {})]
    assert bridge.unsubscribed == ["s1"]


async def test_speech_listen_yields_results_and_passes_args() -> None:
    bridge = _ScriptedEventBridge(
        _events(
            {"transcript": "hel", "is_final": False, "confidence": 0.4},
            {"transcript": "hello", "is_final": True, "confidence": 0.95},
        )
    )
    install_bridge(bridge)

    seen = [r async for r in speech.listen(lang="en-US", interim=True)]

    assert [(r.transcript, r.is_final) for r in seen] == [
        ("hel", False),
        ("hello", True),
    ]
    assert seen[1].confidence == 0.95
    assert bridge.requested == [("speech.listen", {"lang": "en-US", "interim": True})]
    assert bridge.unsubscribed == ["s1"]


async def test_tabs_receive_yields_messages_and_passes_channel() -> None:
    bridge = _ScriptedEventBridge(
        _events(
            {"message": {"kind": "hi", "n": 1}},
            {"message": "plain-string"},
        )
    )
    install_bridge(bridge)

    seen = [m async for m in tabs.receive("chat")]

    assert seen == [{"kind": "hi", "n": 1}, "plain-string"]
    assert bridge.requested == [("tabs.receive", {"channel": "chat"})]
    assert bridge.unsubscribed == ["s1"]


async def test_midi_messages_yields_message_models() -> None:
    bridge = _ScriptedEventBridge(
        _events(
            {"input_id": "in-1", "data": [144, 60, 127], "timestamp": 12.5},
        )
    )
    install_bridge(bridge)

    seen = [m async for m in midi.messages()]

    assert seen[0].input_id == "in-1"
    assert seen[0].data == [144, 60, 127]
    assert seen[0].timestamp == 12.5
    assert bridge.requested == [("midi.messages", {})]
    assert bridge.unsubscribed == ["s1"]


async def test_gamepad_watch_yields_snapshots() -> None:
    bridge = _ScriptedEventBridge(
        _events(
            {"gamepads": [{"id": "pad-0", "axes": [0.0, 0.0]}]},
            {"gamepads": []},
        )
    )
    install_bridge(bridge)

    seen = [g async for g in gamepad.watch()]

    assert seen == [[{"id": "pad-0", "axes": [0.0, 0.0]}], []]
    assert bridge.requested == [("gamepad.watch", {})]
    assert bridge.unsubscribed == ["s1"]
