"""Native page-visibility capability over the Page Visibility Web API.

:func:`state` sends a ``visibility.state`` ``native_call``;
``client/native/visibility.js`` reads ``document.visibilityState``. The plan-facing
return is the visibility string (``"visible"`` or ``"hidden"``); the client also
reports a redundant ``hidden`` boolean which the Python side ignores.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from tempestweb.native.dispatch import native_events, send_native_call

__all__ = ["state", "watch"]


async def state() -> str:
    """Report the current page-visibility state.

    Returns:
        The visibility state string: ``"visible"`` or ``"hidden"``.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("visibility.state", {})
    return str(value.get("state", "visible"))


async def watch() -> AsyncIterator[str]:
    """Stream page-visibility changes from the browser (event channel / T-EV).

    Yields the new visibility string (``"visible"`` or ``"hidden"``) every time the
    page is shown or hidden, until the ``async for`` loop is exited (which closes
    the subscription). Consume it with::

        async for vis in native.visibility.watch():
            app.set_state(lambda s: setattr(s, "visible", vis == "visible"))

    Yields:
        Each new visibility state string.

    Raises:
        NativeError: If the browser reports the subscription failed.
        BrowserUnavailableError: If no bridge is installed, or the installed bridge
            does not support the event channel.
    """
    async for value in native_events("visibility.watch", {}):
        yield str(value["state"])
