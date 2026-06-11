"""Native clipboard capability over the browser's Clipboard Web API.

The web sibling of :mod:`tempestroid.native.clipboard`. :func:`set_text` is
fire-and-forget (``navigator.clipboard.writeText``); :func:`get_text` is
request/response (``navigator.clipboard.readText``). Naming mirrors tempestroid
so application code is identical across platforms.

The Clipboard API requires a secure context and (for reads) transient user
activation — ``client/native.js`` surfaces those as :class:`NativeError` codes
(``insecure_context``, ``permission_denied``).
"""

from __future__ import annotations

from tempestweb.native.dispatch import send_native, send_native_request

__all__ = ["get_text", "set_text"]


def set_text(text: str) -> None:
    """Write text to the system clipboard.

    Args:
        text: The text to place on the clipboard.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    send_native("clipboard", "set", {"text": text})


async def get_text() -> str:
    """Read the current text from the system clipboard.

    Returns:
        The clipboard text, or ``""`` if the clipboard is empty or non-text.

    Raises:
        NativeError: If the read is blocked (``permission_denied``) or the page
            is not a secure context (``insecure_context``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    data = await send_native_request("clipboard", "get", {})
    return str(data.get("text", ""))
