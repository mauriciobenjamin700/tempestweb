"""Native screen-orientation capability over the Screen Orientation Web API.

:func:`lock` / :func:`unlock` send the ``orientation.lock`` / ``orientation.unlock``
``native_call`` envelopes and :func:`state` reads the current orientation;
``client/native/orientation.js`` calls ``screen.orientation.lock`` /
``screen.orientation.unlock`` and reads ``screen.orientation.{type,angle}``. Locking
requires fullscreen on most browsers.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestweb.native.dispatch import send_native_call

__all__ = ["OrientationState", "lock", "state", "unlock"]


@dataclass(frozen=True)
class OrientationState:
    """The current screen orientation.

    Attributes:
        type: The orientation type (e.g. ``"portrait-primary"``,
            ``"landscape-primary"``).
        angle: The orientation angle in degrees (``0``, ``90``, ``180``, ``270``).
    """

    type: str
    angle: int


async def lock(kind: str) -> bool:
    """Lock the screen to a given orientation.

    Args:
        kind: The orientation to lock to (e.g. ``"portrait"``, ``"landscape"``,
            ``"portrait-primary"``).

    Returns:
        ``True`` if the lock was applied.

    Raises:
        NativeError: If the lock is refused (``permission_denied``) or unsupported
            (``unavailable``) — e.g. not in fullscreen.
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("orientation.lock", {"kind": kind})
    return bool(value.get("locked", False))


async def unlock() -> None:
    """Release any screen-orientation lock.

    Raises:
        NativeError: If the API is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call("orientation.unlock", {})


async def state() -> OrientationState:
    """Report the current screen orientation.

    Returns:
        The current :class:`OrientationState`.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("orientation.state", {})
    return OrientationState(
        type=str(value.get("type", "")),
        angle=int(value.get("angle", 0)),
    )
