"""Native screen wake-lock capability over the Screen Wake Lock Web API.

:func:`request` sends a ``wakelock.request`` ``native_call`` and gets back an
opaque lock id; ``client/native/wakelock.js`` calls
``navigator.wakeLock.request("screen")`` and stores the returned sentinel in a
registry keyed by that id. :func:`release` sends ``wakelock.release`` with the id
so the client can release the matching sentinel. The Python side never touches the
sentinel — it only shuttles the id.
"""

from __future__ import annotations

from tempestweb.native.dispatch import send_native_call

__all__ = ["release", "request"]


async def request() -> str:
    """Request a screen wake lock, keeping the display awake.

    Returns:
        An opaque lock id to pass back to :func:`release`. The client holds the
        underlying wake-lock sentinel in a registry keyed by this id.

    Raises:
        NativeError: If the wake lock is refused (``permission_denied``) or the API
            is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("wakelock.request", {})
    return str(value.get("id", ""))


async def release(lock_id: str) -> None:
    """Release a previously requested screen wake lock.

    Args:
        lock_id: The opaque id returned by :func:`request`.

    Raises:
        NativeError: If the API is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call("wakelock.release", {"id": lock_id})
