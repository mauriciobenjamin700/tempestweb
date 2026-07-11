"""Native background-sync capability over the Background Sync Web APIs.

:func:`register` sends a ``bgsync.register`` ``native_call`` and
:func:`register_periodic` a ``bgsync.register_periodic``;
``client/native/bgsync.js`` reaches the active service-worker registration and
calls ``registration.sync.register`` / ``registration.periodicSync.register``. The
service worker replays the tagged work when connectivity (or the periodic interval)
allows. Registration can be refused when the permission is denied or the API is
unavailable.
"""

from __future__ import annotations

from tempestweb.native.dispatch import send_native_call

__all__ = ["register", "register_periodic"]


async def register(tag: str) -> bool:
    """Register a one-off background sync under a tag.

    Args:
        tag: The sync tag the service worker listens for.

    Returns:
        ``True`` if the sync was registered.

    Raises:
        NativeError: If the API is unavailable (``unavailable``) or registration is
            refused (``permission_denied``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("bgsync.register", {"tag": tag})
    return bool(value.get("registered", False))


async def register_periodic(tag: str, min_interval_ms: int) -> bool:
    """Register a periodic background sync under a tag.

    Args:
        tag: The periodic-sync tag the service worker listens for.
        min_interval_ms: The minimum interval between syncs, in milliseconds.

    Returns:
        ``True`` if the periodic sync was registered.

    Raises:
        NativeError: If the API is unavailable (``unavailable``) or registration is
            refused (``permission_denied``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call(
        "bgsync.register_periodic",
        {"tag": tag, "min_interval_ms": min_interval_ms},
    )
    return bool(value.get("registered", False))
