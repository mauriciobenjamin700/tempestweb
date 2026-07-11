"""Native eyedropper capability over the EyeDropper Web API.

:func:`open` sends an ``eyedropper.open`` ``native_call``; ``client/native/
eyedropper.js`` constructs an ``EyeDropper`` and calls ``open()`` so the user can
pick a color from anywhere on screen, returning its sRGB hex string.
"""

from __future__ import annotations

from tempestweb.native.dispatch import send_native_call

__all__ = ["open"]


async def open() -> str:
    """Let the user pick a screen color with the eyedropper.

    Returns:
        The picked color as an sRGB hex string (e.g. ``"#3366ff"``), or ``""`` if
        the picker is dismissed.

    Raises:
        NativeError: If the API is unavailable (``unavailable``) or the picker is
            aborted (``permission_denied``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("eyedropper.open", {})
    return str(value.get("srgb_hex", ""))
