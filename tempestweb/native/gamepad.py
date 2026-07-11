"""Native gamepad capability over the Gamepad Web API.

:func:`state` sends a ``gamepad.state`` ``native_call``; ``client/native/
gamepad.js`` reads ``navigator.getGamepads()`` and returns a snapshot of each
connected gamepad's axes and buttons. The gamepad shape is browser-defined, so
snapshots pass through as ``dict[str, Any]`` rather than being modeled as
dataclasses.
"""

from __future__ import annotations

from typing import Any, cast

from tempestweb.native.dispatch import send_native_call

__all__ = ["state"]


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
