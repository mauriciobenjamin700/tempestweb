"""Native storage-quota capability over the StorageManager Web API.

:func:`estimate` sends a ``quota.estimate`` ``native_call`` and :func:`persist` /
:func:`persisted` manage durable storage; ``client/native/quota.js`` calls
``navigator.storage.estimate`` / ``navigator.storage.persist`` /
``navigator.storage.persisted``. Persistent storage exempts the origin's data from
eviction under storage pressure.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestweb.native.dispatch import send_native_call

__all__ = ["StorageEstimate", "estimate", "persist", "persisted"]


@dataclass(frozen=True)
class StorageEstimate:
    """An estimate of the origin's storage usage and quota.

    Attributes:
        usage: Bytes currently used by the origin.
        quota: Total bytes available to the origin.
    """

    usage: int
    quota: int


async def estimate() -> StorageEstimate:
    """Estimate the origin's storage usage and quota.

    Returns:
        The current :class:`StorageEstimate`.

    Raises:
        NativeError: If the StorageManager API is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("quota.estimate", {})
    return StorageEstimate(
        usage=int(value.get("usage", 0)),
        quota=int(value.get("quota", 0)),
    )


async def persist() -> bool:
    """Request that the origin's storage be made persistent.

    Returns:
        ``True`` if storage is persistent after the request.

    Raises:
        NativeError: If the API is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("quota.persist", {})
    return bool(value.get("persisted", False))


async def persisted() -> bool:
    """Report whether the origin's storage is already persistent.

    Returns:
        ``True`` if storage is persistent.

    Raises:
        NativeError: If the API is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("quota.persisted", {})
    return bool(value.get("persisted", False))
