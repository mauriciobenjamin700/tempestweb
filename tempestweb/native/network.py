"""Native network-information capability over the Network Information Web API.

:func:`state` sends a ``network.state`` ``native_call``;
``client/native/network.js`` reads ``navigator.onLine`` and ``navigator.connection``
(``effectiveType``, ``downlink``, ``rtt``, ``saveData``). The connection fields are
only populated on browsers that support the API — they fall back to neutral
defaults otherwise.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from tempestweb.native.dispatch import native_events, send_native_call

__all__ = ["NetworkState", "state", "watch"]


@dataclass(frozen=True)
class NetworkState:
    """A snapshot of the browser's network conditions.

    Attributes:
        online: Whether the browser reports itself as online.
        effective_type: The effective connection type (``"slow-2g"``, ``"2g"``,
            ``"3g"``, ``"4g"``), or ``""`` when unknown.
        downlink: Estimated downlink bandwidth in megabits per second.
        rtt: Estimated round-trip time in milliseconds.
        save_data: Whether the user has requested reduced data usage.
    """

    online: bool
    effective_type: str
    downlink: float
    rtt: int
    save_data: bool


async def state() -> NetworkState:
    """Report the current network conditions.

    Returns:
        The current :class:`NetworkState`.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("network.state", {})
    return NetworkState(
        online=bool(value.get("online", False)),
        effective_type=str(value.get("effective_type", "")),
        downlink=float(value.get("downlink", 0.0)),
        rtt=int(value.get("rtt", 0)),
        save_data=bool(value.get("save_data", False)),
    )


async def watch() -> AsyncIterator[NetworkState]:
    """Stream network-condition changes from the browser (event channel / T-EV).

    Yields a fresh :class:`NetworkState` whenever the browser goes online/offline
    or its connection properties change, until the ``async for`` loop is exited
    (which closes the subscription). Consume it with::

        async for net in native.network.watch():
            app.set_state(lambda s: setattr(s, "network", net))

    Yields:
        Each updated :class:`NetworkState`.

    Raises:
        NativeError: If the browser reports the subscription failed.
        BrowserUnavailableError: If no bridge is installed, or the installed bridge
            does not support the event channel.
    """
    async for value in native_events("network.watch", {}):
        yield NetworkState(
            online=bool(value.get("online", False)),
            effective_type=str(value.get("effective_type", "")),
            downlink=float(value.get("downlink", 0.0)),
            rtt=int(value.get("rtt", 0)),
            save_data=bool(value.get("save_data", False)),
        )
