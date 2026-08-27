"""`device.profile`: the coarse hardware facts, and the browser that says none.

Every field is optional because every source is Chromium-only except
`hardwareConcurrency`. The case worth pinning is the empty answer: a browser that
exposes nothing must produce a profile of `None`, not an exception, because that
is Safari and Firefox — the common case, not the edge.
"""

from __future__ import annotations

from typing import Any

import pytest

from tempestweb.native import device, install_bridge, uninstall_bridge


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


async def test_a_chromium_answer_is_read_whole() -> None:
    install_bridge(
        ScriptedBridge(
            [
                {
                    "memory_gb": 8,
                    "cores": 12,
                    "heap_used_mb": 50.0,
                    "heap_limit_mb": 4095.8,
                }
            ]
        )
    )

    profile = await device.profile()

    assert profile.memory_gb == 8.0
    assert profile.cores == 12
    assert profile.heap_used_mb == 50.0
    assert profile.heap_limit_mb == 4095.8


async def test_a_browser_that_exposes_nothing_gives_every_field_none() -> None:
    """Safari and Firefox. This is the common path, and it must not raise."""
    install_bridge(
        ScriptedBridge(
            [
                {
                    "memory_gb": None,
                    "cores": None,
                    "heap_used_mb": None,
                    "heap_limit_mb": None,
                }
            ]
        )
    )

    profile = await device.profile()

    assert profile.memory_gb is None
    assert profile.cores is None
    assert profile.heap_used_mb is None
    assert profile.heap_limit_mb is None


async def test_an_empty_answer_is_still_an_answer() -> None:
    install_bridge(ScriptedBridge([{}]))
    assert await device.profile() == device.DeviceProfile()


async def test_a_partial_answer_keeps_what_came() -> None:
    """`hardwareConcurrency` is the one with real reach; alone is normal."""
    install_bridge(ScriptedBridge([{"cores": 4}]))

    profile = await device.profile()

    assert profile.cores == 4
    assert profile.memory_gb is None


@pytest.mark.parametrize("value", [True, False, "muita", [], {}, None])
async def test_a_field_that_is_not_a_number_reads_as_unknown(value: Any) -> None:
    """`True` is an `int` in Python; 1 GB of RAM is not what the browser said."""
    install_bridge(ScriptedBridge([{"memory_gb": value, "cores": value}]))

    profile = await device.profile()

    assert profile.memory_gb is None
    assert profile.cores is None


async def test_cores_is_a_whole_number_even_when_the_browser_sends_a_float() -> None:
    install_bridge(ScriptedBridge([{"cores": 8.0}]))
    profile = await device.profile()

    assert profile.cores == 8
    assert isinstance(profile.cores, int)


async def test_the_profile_is_frozen_because_it_is_a_reading() -> None:
    from dataclasses import FrozenInstanceError

    install_bridge(ScriptedBridge([{"cores": 4}]))
    profile = await device.profile()

    with pytest.raises(FrozenInstanceError):
        profile.cores = 8  # type: ignore[misc]


def test_the_capability_is_in_the_contract_and_reaches_mode_c() -> None:
    from tempestweb.native import contract

    assert "device.profile" in {cap.name for cap in contract.CAPABILITIES}
    assert "device.profile" in {cap.name for cap in contract.MODE_C_CAPABILITIES}


def test_connection_and_quota_are_not_duplicated_here() -> None:
    """The narrowing that keeps one fact from having two names on the wire."""
    fields = set(device.DeviceProfile.__dataclass_fields__)

    assert fields == {"memory_gb", "cores", "heap_used_mb", "heap_limit_mb"}
    assert not fields & {"connection", "effective_type", "save_data", "cache_bytes"}
