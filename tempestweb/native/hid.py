"""Native HID capability over the WebHID API.

:func:`request` sends a ``hid.request`` ``native_call``; ``client/native/hid.js``
calls ``navigator.hid.requestDevice`` with the supplied filters and returns the
granted devices. The device shape is browser-defined, so devices pass through as
``dict[str, Any]`` rather than being modeled as dataclasses.
"""

from __future__ import annotations

from typing import Any, cast

from tempestweb.native.dispatch import send_native_call

__all__ = ["is_supported", "request"]


async def is_supported() -> bool:
    """Report whether the WebHID API is available.

    Returns:
        ``True`` if the browser exposes ``navigator.hid``.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("hid.is_supported", {})
    return bool(value.get("supported", False))


async def request(filters: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Request access to HID devices through the browser chooser.

    Args:
        filters: The ``HIDDeviceFilter`` dicts constraining the chooser; an empty
            list offers all devices.

    Returns:
        The granted devices as JSON-able dicts (an empty list when the chooser is
        dismissed).

    Raises:
        NativeError: If the API is unavailable (``unavailable``) or the chooser is
            refused (``permission_denied``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    filters = filters or []
    value = await send_native_call("hid.request", {"filters": filters})
    return cast("list[dict[str, Any]]", value.get("devices", []))
