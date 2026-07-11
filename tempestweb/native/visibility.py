"""Native page-visibility capability over the Page Visibility Web API.

:func:`state` sends a ``visibility.state`` ``native_call``;
``client/native/visibility.js`` reads ``document.visibilityState``. The plan-facing
return is the visibility string (``"visible"`` or ``"hidden"``); the client also
reports a redundant ``hidden`` boolean which the Python side ignores.
"""

from __future__ import annotations

from tempestweb.native.dispatch import send_native_call

__all__ = ["state"]


async def state() -> str:
    """Report the current page-visibility state.

    Returns:
        The visibility state string: ``"visible"`` or ``"hidden"``.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("visibility.state", {})
    return str(value.get("state", "visible"))
