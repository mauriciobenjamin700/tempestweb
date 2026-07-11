"""Native clipboard capability over the browser's Clipboard Web API.

The web sibling of :mod:`tempestroid.native.clipboard`. Both operations are
request/response ``native_call`` round-trips because the browser Clipboard API is
async: :func:`write` (``navigator.clipboard.writeText``) and :func:`read`
(``navigator.clipboard.readText``). The plan-facing names are :func:`read` /
:func:`write`; :func:`get_text` / :func:`set_text` remain as tempestroid-style
aliases so application code is identical across platforms.

The Clipboard API requires a secure context and (for reads) transient user
activation — ``client/native/clipboard.js`` surfaces those as :class:`NativeError`
codes (``insecure_context``, ``permission_denied``).
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestweb.native.dispatch import send_native_call

__all__ = [
    "ClipboardImage",
    "get_text",
    "read",
    "read_image",
    "set_text",
    "write",
    "write_image",
]


@dataclass(frozen=True)
class ClipboardImage:
    """An image read from the system clipboard.

    Attributes:
        data_base64: The image bytes, base64-encoded (JSON-safe over the wire).
        mime_type: The image MIME type (e.g. ``"image/png"``).
    """

    data_base64: str
    mime_type: str


async def write(text: str) -> None:
    """Write text to the system clipboard.

    Args:
        text: The text to place on the clipboard.

    Raises:
        NativeError: If the write is blocked (``permission_denied``) or the page is
            not a secure context (``insecure_context``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call("clipboard.write", {"text": text})


async def read() -> str:
    """Read the current text from the system clipboard.

    Returns:
        The clipboard text, or ``""`` if the clipboard is empty or non-text.

    Raises:
        NativeError: If the read is blocked (``permission_denied``) or the page is
            not a secure context (``insecure_context``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("clipboard.read", {})
    return str(value.get("text", ""))


async def read_image() -> ClipboardImage:
    """Read an image from the system clipboard.

    Returns:
        The clipboard image as a :class:`ClipboardImage` carrying base64 bytes and
        its MIME type.

    Raises:
        NativeError: If the read is blocked (``permission_denied``), the page is
            not a secure context (``insecure_context``), or the clipboard holds no
            image (``not_found``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("clipboard.read_image", {})
    return ClipboardImage(
        data_base64=str(value.get("data_base64", "")),
        mime_type=str(value.get("mime_type", "")),
    )


async def write_image(data_base64: str, mime_type: str = "image/png") -> None:
    """Write an image to the system clipboard.

    Args:
        data_base64: The image bytes, base64-encoded.
        mime_type: The image MIME type (defaults to ``"image/png"``).

    Raises:
        NativeError: If the write is blocked (``permission_denied``) or the page is
            not a secure context (``insecure_context``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call(
        "clipboard.write_image",
        {"data_base64": data_base64, "mime_type": mime_type},
    )


#: Alias matching the tempestroid API ``await clipboard.set_text(...)``.
set_text = write
#: Alias matching the tempestroid API ``await clipboard.get_text()``.
get_text = read
