"""Native share capability over the browser's Web Share API (N2).

The pythonic mirror of the React SDK's ``share`` / ``isShareSupported``. Opens the
OS share sheet via ``navigator.share`` when available, and degrades gracefully
otherwise. Pairs with the ``share_target`` manifest field (P5).

``client/native/share.js`` calls ``navigator.share`` (a user gesture and a secure
context are required). When the API is missing it returns an ``unsupported``
outcome rather than throwing, so callers can fall back (e.g. to the clipboard).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from tempestweb.native.dispatch import send_native_call

__all__ = ["ShareOutcome", "ShareResult", "is_share_supported", "share"]


class ShareOutcome(StrEnum):
    """The outcome of a :func:`share` call.

    Attributes:
        SHARED: The OS share sheet completed (content was shared).
        CANCELLED: The user dismissed the share sheet.
        UNSUPPORTED: The Web Share API is unavailable in this browser.
    """

    SHARED = "shared"
    CANCELLED = "cancelled"
    UNSUPPORTED = "unsupported"


class ShareResult(BaseModel):
    """The typed result of a :func:`share` call.

    Attributes:
        outcome: The :class:`ShareOutcome`.
    """

    model_config = ConfigDict(frozen=True)

    outcome: ShareOutcome


async def is_share_supported() -> bool:
    """Report whether the Web Share API is available in the current browser.

    Returns:
        ``True`` if ``navigator.share`` exists (and the context permits sharing),
        ``False`` otherwise.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("share.is_supported", {})
    return bool(value.get("supported", False))


async def share(
    *,
    title: str = "",
    text: str = "",
    url: str = "",
    files: list[dict[str, str]] | None = None,
) -> ShareResult:
    """Open the OS share sheet, falling back gracefully when unsupported.

    Args:
        title: The share title.
        text: The share body text.
        url: A URL to share.
        files: Optional file descriptors (``{"name", "type", "data"}``); file
            sharing has uneven browser support and may downgrade to text/url.

    Returns:
        A :class:`ShareResult`. ``ShareOutcome.UNSUPPORTED`` and
        ``ShareOutcome.CANCELLED`` are normal, non-error outcomes — never raised.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call(
        "share.share",
        {"title": title, "text": text, "url": url, "files": files or []},
    )
    outcome = ShareOutcome(str(value.get("outcome", ShareOutcome.UNSUPPORTED.value)))
    return ShareResult(outcome=outcome)
