"""Native geolocation capability over the browser's Geolocation Web API.

The web sibling of :mod:`tempestroid.native.geolocation`. :func:`get_position`
(aliased :func:`get`) sends a ``geolocation.get`` ``native_call``;
``client/native/geolocation.js`` calls ``navigator.geolocation.getCurrentPosition``
and replies with the fix.

Naming mirrors tempestroid (:class:`Position`, :func:`get_position`) so the same
application code reads identically on Android and on the web.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from tempestweb.native.dispatch import send_native_call

__all__ = ["Position", "get", "get_position"]


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


#: Alias matching the tempestroid/plan API ``await geolocation.get()``.
get = get_position
