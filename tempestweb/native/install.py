"""Native PWA install-prompt capability (P0).

Exposes the browser's soft install flow to Python: whether the app is installable
(a ``beforeinstallprompt`` was captured) or already installed, and a call to fire
the stashed prompt after a real user gesture. ``client/native/install.js`` wraps
the tested ``client/pwa/install-prompt.js`` controller.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from tempestweb.native.dispatch import send_native_call

__all__ = ["InstallState", "prompt", "state"]


class InstallState(BaseModel):
    """The current PWA install state.

    Attributes:
        can_install: A deferred prompt is available to fire.
        installed: The app reports as installed (standalone / appinstalled).
        method: How the user can install here — ``"native"`` (a prompt is
            available), ``"ios"`` (manual Share → Add to Home) or ``"manual"``
            (e.g. Firefox desktop). Lets the view show a native button vs. a
            platform tutorial.
    """

    model_config = ConfigDict(frozen=True)

    can_install: bool = False
    installed: bool = False
    method: str = "manual"


async def state() -> InstallState:
    """Report whether the app is installable and/or already installed.

    Returns:
        The current :class:`InstallState`.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("install.state", {})
    return InstallState.model_validate(value)


async def prompt() -> str:
    """Fire the stashed native install prompt after a user gesture.

    Returns:
        The outcome: ``"accepted"``, ``"dismissed"``, or ``"unavailable"`` (no
        prompt was captured, or it was already used).

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("install.prompt", {})
    outcome = value.get("outcome", "unavailable")
    return str(outcome)
