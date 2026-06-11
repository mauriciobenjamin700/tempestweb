"""Native notifications capability over the browser's Notifications Web API.

The web sibling of :mod:`tempestroid.native.notifications`. :func:`notify` is
fire-and-forget (mirrors tempestroid's signature); the web adds an explicit
permission gate, so :func:`request_permission` is exposed as a request/response
call returning a typed :class:`NotificationPermission`.

``client/native.js`` drives ``Notification.requestPermission`` and the
``new Notification(title, { body })`` constructor.
"""

from __future__ import annotations

from enum import StrEnum

from tempestweb.native.dispatch import send_native, send_native_request

__all__ = ["NotificationPermission", "notify", "request_permission"]


class NotificationPermission(StrEnum):
    """The browser's notification permission state.

    Mirrors the Web ``NotificationPermission`` enum.

    Attributes:
        DEFAULT: The user has not yet chosen (notifications are not allowed yet).
        GRANTED: The user allowed notifications.
        DENIED: The user blocked notifications.
    """

    DEFAULT = "default"
    GRANTED = "granted"
    DENIED = "denied"


def notify(title: str, body: str = "") -> None:
    """Post a system notification.

    Fire-and-forget, matching tempestroid. The notification only appears if
    permission has been granted (see :func:`request_permission`); otherwise the
    browser silently drops it.

    Args:
        title: The notification title.
        body: The notification body text.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    send_native("notifications", "notify", {"title": title, "body": body})


async def request_permission() -> NotificationPermission:
    """Request permission to show notifications, awaiting the user's choice.

    Returns:
        The resulting :class:`NotificationPermission` after the prompt (or the
        existing state if the user already chose).

    Raises:
        NativeError: If the Notifications API is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    data = await send_native_request("notifications", "request_permission", {})
    return NotificationPermission(str(data.get("permission", "default")))
