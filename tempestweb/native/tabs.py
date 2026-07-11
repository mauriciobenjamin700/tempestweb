"""Native cross-tab capability over the BroadcastChannel and Web Locks Web APIs.

:func:`broadcast` sends a ``tabs.broadcast`` ``native_call`` and :func:`lock` /
:func:`unlock` manage named locks; ``client/native/tabs.js`` posts on a
``BroadcastChannel`` and drives ``navigator.locks``. Receiving broadcasts is a
continuous stream and is deferred to the event channel rather than a
request/response call. A lock held across the ``lock`` / ``unlock`` pair is kept
alive by the client on a registry keyed by its name.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from tempestweb.native.dispatch import native_events, send_native_call

__all__ = ["broadcast", "lock", "receive", "unlock"]


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


async def receive(channel: str) -> AsyncIterator[Any]:
    """Stream messages broadcast by other tabs (event channel / T-EV).

    Opens a ``BroadcastChannel`` subscription and yields each message posted by
    another tab (via :func:`broadcast`) until the ``async for`` loop is exited
    (which closes the channel). Consume it with::

        async for message in native.tabs.receive("chat"):
            app.set_state(lambda s: s.messages.append(message))

    Args:
        channel: The broadcast channel name to listen on.

    Yields:
        Each JSON-able message posted by another tab.

    Raises:
        NativeError: If the browser reports the subscription failed (e.g.
            ``unavailable``).
        BrowserUnavailableError: If no bridge is installed, or the installed bridge
            does not support the event channel.
    """
    args = {"channel": channel}
    async for value in native_events("tabs.receive", args):
        yield value["message"]
