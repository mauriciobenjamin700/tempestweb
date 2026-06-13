"""PWA install + WebPush demo — exercises notification permission + subscription.

Like :mod:`examples.counter.app`, this exact ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

This example demonstrates the PWA/WebPush flow:

1. The user presses **Enable notifications** — the app calls
   :func:`~tempestweb.native.notifications.request_permission` and stores the
   resulting :class:`~tempestweb.native.notifications.NotificationPermission`.
2. If permission is *granted*, the button changes to **Subscribe to push** —
   pressing it calls :func:`~tempestweb.native.notifications.subscribe` with the
   injected VAPID public key and stores the raw subscription dict returned by the
   browser.
3. The current status (idle / requesting / subscribing / subscribed / denied) is
   rendered in a :class:`~tempestweb._core.widgets.Text` feedback label so the user
   always sees what happened.

State machine
-------------
* ``Phase.IDLE``         — initial; the user has not interacted yet.
* ``Phase.REQUESTING``   — :func:`request_permission` is in flight.
* ``Phase.DENIED``       — the user blocked notifications.
* ``Phase.GRANTED``      — permission granted; subscription not yet requested.
* ``Phase.SUBSCRIBING``  — :func:`subscribe` is in flight.
* ``Phase.SUBSCRIBED``   — fully subscribed; ``subscription`` dict is populated.
* ``Phase.ERROR``        — unexpected error; ``error`` field has the message.

Dependency injection
--------------------
Both async callables (``request_permission`` and ``subscribe``) are injected
into ``State`` so :func:`build` is deterministic with *no bridge installed*.
The initial mount only reads ``app.state`` — the callables are never invoked
until the user presses a button.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from tempestweb._core import App, Style, Widget
from tempestweb._core.style import Edge
from tempestweb._core.widgets import Button, Column, Row, Spinner, Text
from tempestweb.native import notifications
from tempestweb.native.notifications import NotificationPermission

#: Default VAPID public key used when none is injected (placeholder only;
#: a real app replaces this with its own server key).
DEMO_VAPID_KEY: str = (
    "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuB"
    "kr3qBUYIHBQFLXYp5Nksh8U"
)

# ---------------------------------------------------------------------------
# Injected callable types
# ---------------------------------------------------------------------------

#: Signature of the injected permission-request coroutine.
PermissionRequester = Callable[[], Awaitable[NotificationPermission]]

#: Signature of the injected subscribe coroutine.
Subscriber = Callable[[str], Awaitable[dict[str, Any]]]


# ---------------------------------------------------------------------------
# Phase
# ---------------------------------------------------------------------------


class Phase(StrEnum):
    """Lifecycle phases of the PWA WebPush consent flow.

    Attributes:
        IDLE: No user action yet.
        REQUESTING: Awaiting the browser permission prompt.
        DENIED: The user denied notification permission.
        GRANTED: Permission granted; WebPush subscription not yet requested.
        SUBSCRIBING: Awaiting the browser push subscription creation.
        SUBSCRIBED: Fully subscribed; ``subscription`` dict is available.
        ERROR: An unexpected error occurred.
    """

    IDLE = "idle"
    REQUESTING = "requesting"
    DENIED = "denied"
    GRANTED = "granted"
    SUBSCRIBING = "subscribing"
    SUBSCRIBED = "subscribed"
    ERROR = "error"


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class State:
    """Top-level state for the PWA WebPush demo app.

    Attributes:
        phase: Current lifecycle phase.
        subscription: The raw push subscription dict once subscribed.
        error: Human-readable error message, populated in ``Phase.ERROR``.
        vapid_key: VAPID public key passed to :func:`subscribe`.
        request_permission: Injected coroutine for the permission request.
        subscribe: Injected coroutine for the push subscription.
    """

    phase: Phase = Phase.IDLE
    subscription: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    vapid_key: str = DEMO_VAPID_KEY
    request_permission: PermissionRequester = notifications.request_permission
    subscribe: Subscriber = notifications.subscribe


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_state() -> State:
    """Build the initial idle state with real capability defaults.

    Returns:
        A fresh :class:`State` in the ``IDLE`` phase.
    """
    return State()


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[State]) -> Widget:
    """Render the PWA/WebPush consent UI from the current state.

    The view is a single :class:`~tempestweb._core.widgets.Column` containing:

    * A title.
    * A status feedback text that reflects the current phase.
    * A primary action button (changes label and handler per phase).
    * A subscription details section once fully subscribed.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    # ------------------------------------------------------------------
    # Async handlers
    # ------------------------------------------------------------------

    async def handle_request_permission() -> None:
        """Ask the browser for notification permission and update state."""
        app.set_state(lambda s: setattr(s, "phase", Phase.REQUESTING))
        try:
            perm = await app.state.request_permission()
        except Exception as exc:  # noqa: BLE001 — surface error to the UI
            message = str(exc)

            def on_error(s: State) -> None:
                s.phase = Phase.ERROR
                s.error = message

            app.set_state(on_error)
            return

        if perm is NotificationPermission.GRANTED:
            app.set_state(lambda s: setattr(s, "phase", Phase.GRANTED))
        elif perm is NotificationPermission.DENIED:
            app.set_state(lambda s: setattr(s, "phase", Phase.DENIED))
        else:
            # DEFAULT — the user dismissed the prompt; stay at IDLE
            app.set_state(lambda s: setattr(s, "phase", Phase.IDLE))

    async def handle_subscribe() -> None:
        """Subscribe to WebPush using the stored VAPID key and update state."""
        app.set_state(lambda s: setattr(s, "phase", Phase.SUBSCRIBING))
        try:
            sub = await app.state.subscribe(app.state.vapid_key)
        except Exception as exc:  # noqa: BLE001 — surface error to the UI
            message = str(exc)

            def on_error(s: State) -> None:
                s.phase = Phase.ERROR
                s.error = message

            app.set_state(on_error)
            return

        def on_subscribed(s: State) -> None:
            s.phase = Phase.SUBSCRIBED
            s.subscription = sub

        app.set_state(on_subscribed)

    def handle_reset() -> None:
        """Reset state back to IDLE."""

        def reset(s: State) -> None:
            s.phase = Phase.IDLE
            s.subscription = {}
            s.error = ""

        app.set_state(reset)

    # ------------------------------------------------------------------
    # Status label
    # ------------------------------------------------------------------

    phase = app.state.phase

    status_messages: dict[Phase, str] = {
        Phase.IDLE: "Notifications are not yet enabled.",
        Phase.REQUESTING: "Waiting for browser permission…",
        Phase.DENIED: (
            "Permission denied. You can re-enable notifications"
            " in your browser settings."
        ),
        Phase.GRANTED: (
            "Permission granted. You can now subscribe to push notifications."
        ),
        Phase.SUBSCRIBING: "Creating push subscription…",
        Phase.SUBSCRIBED: "Successfully subscribed to push notifications!",
        Phase.ERROR: f"Error: {app.state.error}",
    }

    status_text: Widget = Text(
        content=status_messages[phase],
        key="status-text",
    )

    # ------------------------------------------------------------------
    # Primary action button
    # ------------------------------------------------------------------

    children: list[Widget] = [
        Text(
            content="PWA WebPush Demo",
            style=Style(font_size=22.0),
            key="title",
        ),
        Text(
            content="Enable browser push notifications to receive real-time updates.",
            style=Style(font_size=14.0),
            key="subtitle",
        ),
        status_text,
    ]

    if phase is Phase.REQUESTING or phase is Phase.SUBSCRIBING:
        children.append(
            Row(
                style=Style(gap=8.0),
                children=[
                    Spinner(key="loading-spinner"),
                    Text(
                        content=(
                            "Requesting permission…"
                            if phase is Phase.REQUESTING
                            else "Subscribing…"
                        ),
                        key="loading-label",
                    ),
                ],
                key="loading-row",
            )
        )
    elif phase is Phase.IDLE or phase is Phase.DENIED:
        children.append(
            Button(
                label="Enable notifications",
                on_click=handle_request_permission,
                key="btn-enable",
            )
        )
        if phase is Phase.DENIED:
            children.append(
                Button(
                    label="Try again",
                    on_click=handle_request_permission,
                    key="btn-retry",
                )
            )
    elif phase is Phase.GRANTED:
        children.append(
            Button(
                label="Subscribe to push",
                on_click=handle_subscribe,
                key="btn-subscribe",
            )
        )
    elif phase is Phase.SUBSCRIBED:
        endpoint = app.state.subscription.get("endpoint", "")
        children.append(
            Column(
                style=Style(gap=4.0, padding=Edge.all(12.0)),
                children=[
                    Text(content="Subscription endpoint:", key="sub-label"),
                    Text(
                        content=endpoint[:64] + "…" if len(endpoint) > 64 else endpoint,
                        key="sub-endpoint",
                    ),
                ],
                key="sub-details",
            )
        )
        children.append(
            Button(
                label="Reset",
                on_click=handle_reset,
                key="btn-reset",
            )
        )
    elif phase is Phase.ERROR:
        children.append(
            Button(
                label="Try again",
                on_click=handle_reset,
                key="btn-error-reset",
            )
        )

    return Column(
        style=Style(gap=16.0, padding=Edge.all(24.0)),
        children=children,
    )
