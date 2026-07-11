"""Native battery capability over the Battery Status Web API.

:func:`watch` opens a ``battery.watch`` subscription on the native event channel
(T-EV); ``client/native/battery.js`` reads ``navigator.getBattery()`` and emits a
fresh :class:`BatteryStatus` on every ``levelchange`` / ``chargingchange`` /
``chargingtimechange`` / ``dischargingtimechange`` event until the subscription is
closed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from pydantic import BaseModel, ConfigDict

from tempestweb.native.dispatch import native_events

__all__ = ["BatteryStatus", "watch"]


class BatteryStatus(BaseModel):
    """A snapshot of the device battery reported by the Battery Status API.

    Attributes:
        level: The charge level as a fraction from ``0.0`` (empty) to ``1.0`` (full).
        charging: Whether the battery is currently charging.
        charging_time: Seconds until the battery is fully charged (``0.0`` when
            already full, ``inf`` when unknown).
        discharging_time: Seconds until the battery is empty (``inf`` when unknown
            or while charging).
    """

    model_config = ConfigDict(frozen=True)

    level: float
    charging: bool
    charging_time: float
    discharging_time: float


async def watch() -> AsyncIterator[BatteryStatus]:
    """Stream battery-status updates from the browser (event channel / T-EV).

    Yields a fresh :class:`BatteryStatus` whenever the charge level or charging
    state changes, until the ``async for`` loop is exited (which closes the
    subscription). Consume it with::

        async for battery in native.battery.watch():
            app.set_state(lambda s: setattr(s, "battery", battery))

    Yields:
        Each updated :class:`BatteryStatus`.

    Raises:
        NativeError: If the browser reports the subscription failed (e.g.
            ``unavailable`` when the Battery Status API is missing).
        BrowserUnavailableError: If no bridge is installed, or the installed bridge
            does not support the event channel.
    """
    async for value in native_events("battery.watch", {}):
        yield BatteryStatus.model_validate(value)
