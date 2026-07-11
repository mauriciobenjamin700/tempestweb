"""Native Bluetooth capability over the Web Bluetooth API.

:func:`request` sends a ``bluetooth.request`` ``native_call`` and gets back a
device carrying an opaque id; ``client/native/bluetooth.js`` calls
``navigator.bluetooth.requestDevice`` and stores the live ``BluetoothDevice`` in a
registry keyed by that id. :func:`read` / :func:`write` send ``bluetooth.read`` /
``bluetooth.write`` with the id so the client can talk to the matching GATT
characteristic. The Python side never touches the device — it only shuttles the id
and base64 bytes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tempestweb.native.dispatch import send_native_call

__all__ = ["BluetoothDevice", "is_supported", "read", "request", "write"]


@dataclass(frozen=True)
class BluetoothDevice:
    """A Bluetooth device paired through the Web Bluetooth API.

    Attributes:
        id: The opaque device id; the client holds the live ``BluetoothDevice`` in a
            registry keyed by this id.
        name: The device's advertised name, or ``""`` when unknown.
    """

    id: str
    name: str


async def is_supported() -> bool:
    """Report whether the Web Bluetooth API is available.

    Returns:
        ``True`` if the browser exposes ``navigator.bluetooth``.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("bluetooth.is_supported", {})
    return bool(value.get("supported", False))


async def request(
    filters: list[dict[str, Any]] | None = None,
    optional_services: list[str] | None = None,
) -> BluetoothDevice:
    """Request a Bluetooth device through the browser chooser.

    Args:
        filters: The ``BluetoothLEScanFilter`` dicts constraining the chooser; an
            empty list requests all devices (paired with ``acceptAllDevices``).
        optional_services: Extra GATT service UUIDs the app may access after
            pairing.

    Returns:
        The paired :class:`BluetoothDevice`.

    Raises:
        NativeError: If the API is unavailable (``unavailable``) or the chooser is
            dismissed/refused (``permission_denied``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    filters = filters or []
    optional_services = optional_services or []
    value = await send_native_call(
        "bluetooth.request",
        {"filters": filters, "optional_services": optional_services},
    )
    return BluetoothDevice(
        id=str(value.get("id", "")),
        name=str(value.get("name", "")),
    )


async def read(device_id: str, service: str, characteristic: str) -> str:
    """Read a GATT characteristic value from a paired device.

    Args:
        device_id: The opaque id from a :class:`BluetoothDevice` returned by
            :func:`request`.
        service: The GATT service UUID.
        characteristic: The GATT characteristic UUID to read.

    Returns:
        The characteristic value bytes, base64-encoded.

    Raises:
        NativeError: If the device id is unknown (``not_found``) or the API is
            unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call(
        "bluetooth.read",
        {"id": device_id, "service": service, "characteristic": characteristic},
    )
    return str(value.get("data_base64", ""))


async def write(
    device_id: str,
    service: str,
    characteristic: str,
    data_base64: str,
) -> None:
    """Write a value to a GATT characteristic on a paired device.

    Args:
        device_id: The opaque id from a :class:`BluetoothDevice` returned by
            :func:`request`.
        service: The GATT service UUID.
        characteristic: The GATT characteristic UUID to write.
        data_base64: The bytes to write, base64-encoded.

    Raises:
        NativeError: If the device id is unknown (``not_found``) or the API is
            unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call(
        "bluetooth.write",
        {
            "id": device_id,
            "service": service,
            "characteristic": characteristic,
            "data_base64": data_base64,
        },
    )
