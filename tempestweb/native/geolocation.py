"""Native geolocation capability over the browser's Geolocation Web API.

The web sibling of :mod:`tempestroid.native.geolocation`. :func:`get_position`
(aliased :func:`get`) sends a ``geolocation.get`` ``native_call``;
``client/native/geolocation.js`` calls ``navigator.geolocation.getCurrentPosition``
and replies with the fix.

Naming mirrors tempestroid (:class:`Position`, :func:`get_position`) so the same
application code reads identically on Android and on the web.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from pydantic import BaseModel, ConfigDict

from tempestweb.native.dispatch import native_events, send_native_call

__all__ = ["Position", "get", "get_position", "watch"]


class Position(BaseModel):
    """A geographic position fix returned by the browser.

    Mirrors ``GeolocationCoordinates``: ``accuracy`` is always present, while
    ``altitude`` is ``None`` when the device cannot report it.

    Attributes:
        latitude: Latitude in decimal degrees.
        longitude: Longitude in decimal degrees.
        accuracy: Horizontal accuracy radius in meters (``0.0`` if unknown).
        altitude: Altitude in meters above the WGS84 ellipsoid, or ``None``.
    """

    model_config = ConfigDict(frozen=True)

    latitude: float
    longitude: float
    accuracy: float = 0.0
    altitude: float | None = None


async def get_position(high_accuracy: bool = True) -> Position:
    """Request a single location fix from the browser.

    Args:
        high_accuracy: Set ``enableHighAccuracy`` (prefer GPS) when ``True``.

    Returns:
        The current :class:`Position`.

    Raises:
        NativeError: If the user denies permission (``permission_denied``), the
            page is not a secure context (``insecure_context``), or no fix is
            available (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("geolocation.get", {"high_accuracy": high_accuracy})
    return Position.model_validate(value)


async def watch(high_accuracy: bool = True) -> AsyncIterator[Position]:
    """Stream location fixes as the device moves (event channel / T-EV).

    Opens a ``navigator.geolocation.watchPosition`` subscription and yields a fresh
    :class:`Position` for every update until the ``async for`` loop is exited (which
    cancels the watch). Consume it with::

        async for pos in geolocation.watch():
            app.set_state(lambda s: setattr(s, "here", pos))

    Args:
        high_accuracy: Set ``enableHighAccuracy`` (prefer GPS) when ``True``.

    Yields:
        Each updated :class:`Position`.

    Raises:
        NativeError: If the user denies permission (``permission_denied``), the page
            is not a secure context (``insecure_context``), or the watch fails.
        BrowserUnavailableError: If no bridge is installed, or the installed bridge
            does not support the event channel.
    """
    args = {"high_accuracy": high_accuracy}
    async for value in native_events("geolocation.watch", args):
        yield Position.model_validate(value)


#: Alias matching the tempestroid/plan API ``await geolocation.get()``.
get = get_position
