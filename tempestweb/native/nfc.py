"""Native NFC write capability over the Web NFC API.

:func:`write` sends an ``nfc.write`` ``native_call``; ``client/native/nfc.js``
constructs an ``NDEFReader`` and calls ``write`` with the supplied records. Scanning
is a continuous stream and is deferred to the event channel rather than exposed as a
one-shot awaitable here. The NDEF record shape is browser-defined, so records pass
through as ``dict[str, Any]``.
"""

from __future__ import annotations

from typing import Any

from tempestweb.native.dispatch import send_native_call

__all__ = ["is_supported", "write"]


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
