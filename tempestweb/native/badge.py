"""Native PWA app-icon badge capability over the Badging Web API.

:func:`set_badge` sends a ``badge.set`` ``native_call`` and :func:`clear` sends
``badge.clear``; ``client/native/badge.js`` calls ``navigator.setAppBadge`` /
``navigator.clearAppBadge`` on the installed app's icon. Setting a badge with no
count shows a generic dot; a count of ``0`` also clears the badge per the spec.
"""

from __future__ import annotations

from tempestweb.native.dispatch import send_native_call

__all__ = ["clear", "set_badge"]


async def set_badge(count: int | None = None) -> None:
    """Set the app-icon badge to a count, or to a generic dot.

    Args:
        count: The number to display on the badge. When ``None`` the browser shows
            a generic marker with no number; ``0`` clears the badge.

    Raises:
        NativeError: If the Badging API is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call("badge.set", {"count": count})


async def clear() -> None:
    """Clear the app-icon badge.

    Raises:
        NativeError: If the Badging API is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call("badge.clear", {})
