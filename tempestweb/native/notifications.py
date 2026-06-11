"""Native notifications capability over the browser's Notifications Web API.

The web sibling of :mod:`tempestroid.native.notifications`. :func:`notify` posts a
local notification; the web adds an explicit permission gate, so
:func:`request_permission` returns a typed :class:`NotificationPermission`.

``client/native/notifications.js`` drives ``Notification.requestPermission`` and
the ``new Notification(title, { body })`` constructor.

WebPush subscriptions (P3) are out of this module's scope — they share the
``native_call`` envelope but live in ``tempestweb/pwa`` (Track T9).
"""

from __future__ import annotations

from enum import StrEnum

from tempestweb.native.dispatch import send_native_call

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


async def notify(title: str, body: str = "") -> None:
    """Post a local system notification.

    The notification only appears if permission has been granted (see
    :func:`request_permission`); otherwise the browser silently drops it.

    Args:
        title: The notification title.
        body: The notification body text.

    Raises:
        NativeError: If the Notifications API is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call("notifications.notify", {"title": title, "body": body})


async def request_permission() -> NotificationPermission:
    """Request permission to show notifications, awaiting the user's choice.

    Returns:
        The resulting :class:`NotificationPermission` after the prompt (or the
        existing state if the user already chose).

    Raises:
        NativeError: If the Notifications API is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("notifications.request_permission", {})
    return NotificationPermission(str(value.get("permission", "default")))
