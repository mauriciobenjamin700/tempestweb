"""Native notifications capability over the browser's Notifications Web API.

The web sibling of :mod:`tempestroid.native.notifications`. :func:`notify` posts a
local notification; the web adds an explicit permission gate, so
:func:`request_permission` returns a typed :class:`NotificationPermission`.

``client/native/notifications.js`` drives ``Notification.requestPermission`` and
the ``new Notification(title, { body })`` constructor.

WebPush subscriptions (P3) ride the **same** ``native_call`` envelope:
:func:`subscribe` / :func:`unsubscribe` ask the client to run the browser-side
``pushManager`` flow (via ``client/push/web-push-client.js``) and hand the raw
subscription back. The framework does not decide your endpoint schema — persist
the returned subscription server-side however you like. The server-side WebPush
*send* path lives in ``tempestweb/server/webpush.py`` (Track T9).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict

from tempestweb.native.dispatch import send_native_call

__all__ = [
    "NotificationPermission",
    "PushState",
    "notify",
    "push_state",
    "request_permission",
    "subscribe",
    "unsubscribe",
]


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


class PushState(BaseModel):
    """WebPush support and current permission, reported without prompting.

    Attributes:
        supported: Whether WebPush (service worker + PushManager + Notification)
            is available in this context.
        permission: The current notification permission
            (``"granted"``/``"denied"``/``"default"``/``"unsupported"``).
    """

    model_config = ConfigDict(frozen=True)

    supported: bool = False
    permission: str = "unsupported"


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


async def push_state() -> PushState:
    """Report WebPush support and current permission WITHOUT prompting.

    Use this to decide whether to show an "enable notifications" button before
    calling :func:`subscribe` (which must follow a user gesture).

    Returns:
        The :class:`PushState` (support flag + current permission).

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("notifications.push_state", {})
    return PushState.model_validate(value)


async def subscribe(vapid_public_key: str) -> dict[str, Any]:
    """Subscribe to WebPush, returning the raw browser subscription (P3).

    Asks the client to run the browser-side push flow (ensure permission, create
    or reuse the ``pushManager`` subscription) with the given VAPID public key, and
    hands the subscription JSON back. Persist it server-side however your app likes
    (the framework does not own the endpoint schema).

    Args:
        vapid_public_key: The base64url-encoded VAPID application server key.

    Returns:
        The push subscription as a JSON-able dict (``endpoint``, ``keys``, ...).

    Raises:
        NativeError: If push is unsupported, permission is denied, or no service
            worker registration is available.
        BrowserUnavailableError: If called with no native bridge installed.
    """
    return await send_native_call(
        "notifications.subscribe", {"vapid_public_key": vapid_public_key}
    )


async def unsubscribe() -> bool:
    """Cancel the current WebPush subscription, if any (P3).

    Asks the client to unsubscribe from ``pushManager``. Returns whether a
    subscription was actually cancelled (``False`` when none existed).

    Returns:
        ``True`` if a subscription was cancelled, ``False`` otherwise.

    Raises:
        NativeError: If the unsubscribe call fails in the browser.
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("notifications.unsubscribe", {})
    return bool(value.get("unsubscribed", False))
