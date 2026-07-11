"""Native pointer-lock capability over the Pointer Lock Web API.

:func:`request` sends a ``pointerlock.request`` ``native_call`` and :func:`exit` a
``pointerlock.exit``; ``client/native/pointerlock.js`` calls
``element.requestPointerLock`` / ``document.exitPointerLock`` to hide and capture the
mouse cursor (as games and 3D viewers do).
"""

from __future__ import annotations

from tempestweb.native.dispatch import send_native_call

__all__ = ["exit", "request"]


async def request(selector: str = "") -> None:
    """Lock the pointer to an element, hiding and capturing the cursor.

    Args:
        selector: The CSS selector of the element to lock the pointer to; the
            document body is used when empty.

    Raises:
        NativeError: If the API is unavailable (``unavailable``), the element is not
            found (``not_found``), or the lock is refused (``permission_denied``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call("pointerlock.request", {"selector": selector})


async def exit() -> None:
    """Release the pointer lock, restoring the cursor.

    Raises:
        NativeError: If the API is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call("pointerlock.exit", {})
