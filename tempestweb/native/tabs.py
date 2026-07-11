"""Native cross-tab capability over the BroadcastChannel and Web Locks Web APIs.

:func:`broadcast` sends a ``tabs.broadcast`` ``native_call`` and :func:`lock` /
:func:`unlock` manage named locks; ``client/native/tabs.js`` posts on a
``BroadcastChannel`` and drives ``navigator.locks``. Receiving broadcasts is a
continuous stream and is deferred to the event channel rather than a
request/response call. A lock held across the ``lock`` / ``unlock`` pair is kept
alive by the client on a registry keyed by its name.
"""

from __future__ import annotations

from tempestweb.native.dispatch import send_native_call

__all__ = ["broadcast", "lock", "unlock"]


async def broadcast(channel: str, message: object) -> None:
    """Post a message to all tabs listening on a broadcast channel.

    Args:
        channel: The broadcast channel name.
        message: The JSON-able message to post to other tabs.

    Raises:
        NativeError: If the API is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call(
        "tabs.broadcast",
        {"channel": channel, "message": message},
    )


async def lock(name: str, mode: str = "exclusive") -> bool:
    """Acquire a named cross-tab lock.

    Args:
        name: The lock name.
        mode: The lock mode, ``"exclusive"`` or ``"shared"``.

    Returns:
        ``True`` if the lock was acquired.

    Raises:
        NativeError: If the API is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("tabs.lock", {"name": name, "mode": mode})
    return bool(value.get("acquired", False))


async def unlock(name: str) -> None:
    """Release a previously acquired named cross-tab lock.

    Args:
        name: The lock name passed to :func:`lock`.

    Raises:
        NativeError: If the API is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call("tabs.unlock", {"name": name})
