"""Native idle-detection capability over the Idle Detection Web API.

:func:`watch` opens an ``idle.watch`` subscription on the native event channel
(T-EV); ``client/native/idle.js`` drives an ``IdleDetector`` and emits a fresh
:class:`IdleState` whenever the user or screen idle state changes, until the
subscription is closed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from pydantic import BaseModel, ConfigDict

from tempestweb.native.dispatch import native_events

__all__ = ["IdleState", "watch"]


class IdleState(BaseModel):
    """A snapshot of the user's idle state reported by the Idle Detection API.

    Attributes:
        user: The user idle state, ``"active"`` or ``"idle"``.
        screen: The screen state, ``"locked"`` or ``"unlocked"``.
    """

    model_config = ConfigDict(frozen=True)

    user: str
    screen: str


async def watch(threshold_seconds: int = 60) -> AsyncIterator[IdleState]:
    """Stream idle-state changes from the browser (event channel / T-EV).

    Yields a fresh :class:`IdleState` whenever the user's activity or the screen
    lock state changes, until the ``async for`` loop is exited (which closes the
    subscription). Consume it with::

        async for idle in native.idle.watch(threshold_seconds=120):
            app.set_state(lambda s: setattr(s, "idle", idle))

    Args:
        threshold_seconds: How long (in seconds) the user must be inactive before
            being reported as idle. Must be at least 60 per the Web API.

    Yields:
        Each updated :class:`IdleState`.

    Raises:
        NativeError: If the browser reports the subscription failed (e.g.
            ``permission_denied`` or ``unavailable``).
        BrowserUnavailableError: If no bridge is installed, or the installed bridge
            does not support the event channel.
    """
    args = {"threshold_seconds": threshold_seconds}
    async for value in native_events("idle.watch", args):
        yield IdleState.model_validate(value)
