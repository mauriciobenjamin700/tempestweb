"""Native serial-port capability over the Web Serial API.

:func:`request` sends a ``serial.request`` ``native_call`` and gets back an opaque
port id; ``client/native/serial.js`` calls ``navigator.serial.requestPort`` with the
supplied filters and stores the live ``SerialPort`` in a registry keyed by that id.
Reading and writing are continuous streams and are deferred to the event channel
rather than exposed as one-shot awaitables here.
"""

from __future__ import annotations

from typing import Any

from tempestweb.native.dispatch import send_native_call

__all__ = ["is_supported", "request"]


async def is_supported() -> bool:
    """Report whether the Web Serial API is available.

    Returns:
        ``True`` if the browser exposes ``navigator.serial``.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("serial.is_supported", {})
    return bool(value.get("supported", False))


async def request(filters: list[dict[str, Any]] | None = None) -> str:
    """Request a serial port through the browser chooser.

    Args:
        filters: The ``SerialPortFilter`` dicts constraining the chooser; an empty
            list offers all ports.

    Returns:
        An opaque port id to pass to future serial operations. The client holds the
        live ``SerialPort`` in a registry keyed by this id.

    Raises:
        NativeError: If the API is unavailable (``unavailable``) or the chooser is
            dismissed/refused (``permission_denied``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    filters = filters or []
    value = await send_native_call("serial.request", {"filters": filters})
    return str(value.get("id", ""))
