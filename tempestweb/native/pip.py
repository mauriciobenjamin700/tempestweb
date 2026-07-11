"""Native Picture-in-Picture capability over the Picture-in-Picture Web API.

:func:`request` sends a ``pip.request`` ``native_call`` and :func:`exit` a
``pip.exit``; ``client/native/pip.js`` calls ``video.requestPictureInPicture`` /
``document.exitPictureInPicture`` on the selected ``<video>`` element. Both return
whether a Picture-in-Picture window is active afterward.
"""

from __future__ import annotations

from tempestweb.native.dispatch import send_native_call

__all__ = ["exit", "request"]


async def request(selector: str = "video") -> bool:
    """Open a Picture-in-Picture window for a video element.

    Args:
        selector: The CSS selector of the ``<video>`` element (defaults to
            ``"video"``, the first video on the page).

    Returns:
        ``True`` if a Picture-in-Picture window is active after the request.

    Raises:
        NativeError: If the API is unavailable (``unavailable``), the element is not
            found (``not_found``), or the request is refused (``permission_denied``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("pip.request", {"selector": selector})
    return bool(value.get("active", False))


async def exit() -> bool:
    """Close the active Picture-in-Picture window.

    Returns:
        ``True`` if a Picture-in-Picture window is still active afterward (normally
        ``False``).

    Raises:
        NativeError: If the API is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("pip.exit", {})
    return bool(value.get("active", False))
