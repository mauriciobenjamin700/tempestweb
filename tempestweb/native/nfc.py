"""Native NFC capabilities over the Web NFC API.

:func:`write` sends an ``nfc.write`` ``native_call``; ``client/native/nfc.js``
constructs an ``NDEFReader`` and calls ``write`` with the supplied records.
:func:`scan` is a **streaming** capability over the event channel (T-EV): it yields
one :class:`NdefMessage` per tag read until the ``async for`` loop is exited. The
NDEF record shape is browser-defined, so records pass through as ``dict[str, Any]``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, ConfigDict

from tempestweb.native.dispatch import native_events, send_native_call

__all__ = ["NdefMessage", "is_supported", "scan", "write"]


class NdefMessage(BaseModel):
    """One NDEF message read from a nearby tag.

    Attributes:
        serial_number: The tag's serial number, or ``""`` when unavailable.
        records: The decoded NDEF records (browser-defined shape).
    """

    model_config = ConfigDict(frozen=True)

    serial_number: str = ""
    records: list[dict[str, Any]] = []


async def is_supported() -> bool:
    """Report whether the Web NFC API is available.

    Returns:
        ``True`` if the browser exposes ``NDEFReader``.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("nfc.is_supported", {})
    return bool(value.get("supported", False))


async def write(records: list[dict[str, Any]]) -> None:
    """Write NDEF records to a nearby NFC tag.

    Args:
        records: The ``NDEFRecordInit`` dicts to write to the tag.

    Raises:
        NativeError: If the API is unavailable (``unavailable``) or the write is
            refused/aborted (``permission_denied``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call("nfc.write", {"records": records})


async def scan() -> AsyncIterator[NdefMessage]:
    """Stream NDEF messages as tags are read (event channel / T-EV).

    Opens an ``NDEFReader.scan()`` subscription and yields a fresh
    :class:`NdefMessage` for every tag read until the ``async for`` loop is exited
    (which aborts the scan). Consume it with::

        async for msg in nfc.scan():
            app.set_state(lambda s: setattr(s, "last_tag", msg.serial_number))

    Yields:
        Each :class:`NdefMessage` read from a nearby tag.

    Raises:
        NativeError: If the API is unavailable (``unavailable``) or the scan is
            refused/aborted (``permission_denied``).
        BrowserUnavailableError: If no bridge is installed, or the installed bridge
            does not support the event channel.
    """
    async for value in native_events("nfc.scan", {}):
        yield NdefMessage.model_validate(value)
