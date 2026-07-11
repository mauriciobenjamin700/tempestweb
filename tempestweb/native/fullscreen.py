"""Native fullscreen capability over the browser's Fullscreen Web API.

:func:`enter` / :func:`exit` send the ``fullscreen.enter`` / ``fullscreen.exit``
``native_call`` envelopes, and :func:`state` reads the current mode;
``client/native/fullscreen.js`` calls ``Element.requestFullscreen`` /
``document.exitFullscreen`` and reads ``document.fullscreenElement``. Each returns
whether fullscreen is active afterwards.
"""

from __future__ import annotations

from tempestweb.native.dispatch import send_native_call

__all__ = ["enter", "exit", "state"]


async def enter() -> bool:
    """Enter fullscreen mode.

    Returns:
        ``True`` if the document is in fullscreen after the call.

    Raises:
        NativeError: If the request is refused (``permission_denied``) or the API
            is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("fullscreen.enter", {})
    return bool(value.get("active", False))


async def exit() -> bool:
    """Exit fullscreen mode.

    Returns:
        ``True`` if the document is still in fullscreen after the call
        (i.e. ``False`` on success).

    Raises:
        NativeError: If the API is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("fullscreen.exit", {})
    return bool(value.get("active", False))


async def state() -> bool:
    """Report whether the document is currently in fullscreen.

    Returns:
        ``True`` if a fullscreen element is active.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("fullscreen.state", {})
    return bool(value.get("active", False))
