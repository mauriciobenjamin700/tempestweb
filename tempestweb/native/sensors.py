"""Native motion-sensor capabilities over the Device Orientation / Motion Web APIs.

:func:`orientation` opens a ``sensors.orientation`` subscription and :func:`motion`
a ``sensors.motion`` subscription on the native event channel (T-EV);
``client/native/sensors.js`` listens on the ``deviceorientation`` and
``devicemotion`` window events and emits a fresh reading for every sample until the
subscription is closed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from pydantic import BaseModel, ConfigDict

from tempestweb.native.dispatch import native_events

__all__ = ["DeviceOrientation", "Motion", "motion", "orientation"]


class DeviceOrientation(BaseModel):
    """A device-orientation reading from the Device Orientation API.

    Attributes:
        alpha: Rotation around the z-axis in degrees (0-360), or ``None`` when
            unavailable.
        beta: Front-to-back tilt in degrees (-180-180), or ``None``.
        gamma: Left-to-right tilt in degrees (-90-90), or ``None``.
        absolute: Whether the reading is relative to Earth's coordinate frame.
    """

    model_config = ConfigDict(frozen=True)

    alpha: float | None
    beta: float | None
    gamma: float | None
    absolute: bool


class Motion(BaseModel):
    """A device-motion reading from the Device Motion API.

    Attributes:
        acceleration: Acceleration on ``x``/``y``/``z`` axes in m/s^2; each value is
            ``None`` when the axis cannot be reported.
        rotation_rate: Rotation rate around ``alpha``/``beta``/``gamma`` axes in
            degrees per second; each value is ``None`` when unavailable.
        interval: The sampling interval in milliseconds between readings.
    """

    model_config = ConfigDict(frozen=True)

    acceleration: dict[str, float | None]
    rotation_rate: dict[str, float | None]
    interval: float


async def orientation() -> AsyncIterator[DeviceOrientation]:
    """Stream device-orientation readings from the browser (event channel / T-EV).

    Yields a fresh :class:`DeviceOrientation` for every ``deviceorientation``
    sample until the ``async for`` loop is exited (which closes the subscription).

    Yields:
        Each :class:`DeviceOrientation` reading.

    Raises:
        NativeError: If the browser reports the subscription failed (e.g.
            ``permission_denied`` or ``unavailable``).
        BrowserUnavailableError: If no bridge is installed, or the installed bridge
            does not support the event channel.
    """
    async for value in native_events("sensors.orientation", {}):
        yield DeviceOrientation.model_validate(value)


async def motion() -> AsyncIterator[Motion]:
    """Stream device-motion readings from the browser (event channel / T-EV).

    Yields a fresh :class:`Motion` for every ``devicemotion`` sample until the
    ``async for`` loop is exited (which closes the subscription).

    Yields:
        Each :class:`Motion` reading.

    Raises:
        NativeError: If the browser reports the subscription failed (e.g.
            ``permission_denied`` or ``unavailable``).
        BrowserUnavailableError: If no bridge is installed, or the installed bridge
            does not support the event channel.
    """
    async for value in native_events("sensors.motion", {}):
        yield Motion.model_validate(value)
