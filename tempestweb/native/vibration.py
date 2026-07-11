"""Native vibration capability over the browser's Vibration Web API.

:func:`vibrate` sends a ``vibration.vibrate`` ``native_call``;
``client/native/vibration.js`` calls ``navigator.vibrate`` with either a single
duration in milliseconds or an on/off pattern. Vibration is a fire-and-forget
capability — the browser returns no meaningful value, so the result is unwrapped
and discarded.
"""

from __future__ import annotations

from tempestweb.native.dispatch import send_native_call

__all__ = ["vibrate"]


async def vibrate(pattern: int | list[int]) -> None:
    """Vibrate the device with a duration or an on/off pattern.

    Args:
        pattern: Either a single vibration duration in milliseconds, or a list of
            alternating vibrate/pause durations (``[on, off, on, ...]``).

    Raises:
        NativeError: If the browser has no vibration hardware or blocks the call
            (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call("vibration.vibrate", {"pattern": pattern})
