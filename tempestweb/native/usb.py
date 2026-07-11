"""Native USB capability over the WebUSB API.

:func:`request` sends a ``usb.request`` ``native_call`` and gets back a device
carrying an opaque id plus identifying fields; ``client/native/usb.js`` calls
``navigator.usb.requestDevice`` with the supplied filters and stores the live
``USBDevice`` in a registry keyed by that id. The Python side never touches the
device — it only shuttles the id and metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tempestweb.native.dispatch import send_native_call

__all__ = ["UsbDevice", "is_supported", "request"]


@dataclass(frozen=True)
class UsbDevice:
    """A USB device granted through the WebUSB API.

    Attributes:
        id: The opaque device id; the client holds the live ``USBDevice`` in a
            registry keyed by this id.
        vendor_id: The USB vendor id.
        product_id: The USB product id.
        product_name: The device's product name, or ``""`` when unknown.
    """

    id: str
    vendor_id: int
    product_id: int
    product_name: str


async def is_supported() -> bool:
    """Report whether the WebUSB API is available.

    Returns:
        ``True`` if the browser exposes ``navigator.usb``.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("usb.is_supported", {})
    return bool(value.get("supported", False))


async def request(filters: list[dict[str, Any]] | None = None) -> UsbDevice:
    """Request a USB device through the browser chooser.

    Args:
        filters: The ``USBDeviceFilter`` dicts constraining the chooser; an empty
            list offers all devices.

    Returns:
        The granted :class:`UsbDevice`.

    Raises:
        NativeError: If the API is unavailable (``unavailable``) or the chooser is
            dismissed/refused (``permission_denied``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    filters = filters or []
    value = await send_native_call("usb.request", {"filters": filters})
    return UsbDevice(
        id=str(value.get("id", "")),
        vendor_id=int(value.get("vendor_id", 0)),
        product_id=int(value.get("product_id", 0)),
        product_name=str(value.get("product_name", "")),
    )
