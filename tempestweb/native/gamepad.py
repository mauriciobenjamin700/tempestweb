"""Native gamepad capability over the Gamepad Web API.

:func:`state` sends a ``gamepad.state`` ``native_call``; ``client/native/
gamepad.js`` reads ``navigator.getGamepads()`` and returns a snapshot of each
connected gamepad's axes and buttons. The gamepad shape is browser-defined, so
snapshots pass through as ``dict[str, Any]`` rather than being modeled as
dataclasses.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, cast

from tempestweb.native.dispatch import native_events, send_native_call

__all__ = ["state", "watch"]


async def state() -> list[dict[str, Any]]:
    """Snapshot the currently connected gamepads.

    Returns:
        A list of gamepad snapshots (axes, buttons, id, …) as JSON-able dicts; an
        empty list when no gamepad is connected.

    Raises:
        NativeError: If the API is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("gamepad.state", {})
    return cast("list[dict[str, Any]]", value.get("gamepads", []))


async def watch() -> AsyncIterator[list[dict[str, Any]]]:
    """Stream gamepad snapshots from the browser (event channel / T-EV).

    Yields a fresh list of gamepad snapshots on every animation-frame poll (or on
    connect/disconnect) until the ``async for`` loop is exited (which closes the
    subscription). Consume it with::

        async for gamepads in native.gamepad.watch():
            app.set_state(lambda s: setattr(s, "gamepads", gamepads))

    Yields:
        Each snapshot: a list of connected gamepads as JSON-able dicts (empty when
        none are connected).

    Raises:
        NativeError: If the browser reports the subscription failed.
        BrowserUnavailableError: If no bridge is installed, or the installed bridge
            does not support the event channel.
    """
    async for value in native_events("gamepad.watch", {}):
        yield cast("list[dict[str, Any]]", value["gamepads"])
