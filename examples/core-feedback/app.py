"""Core feedback — a tempestweb gallery of status/feedback components.

This example showcases the feedback widgets shipped by the core, all wired
into a single screen that runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

It demonstrates :class:`Alert` (info/success/warning/error variants), a
:class:`Banner`, a row of :class:`Badge` chips, a :class:`ProgressStepper`
driving a multi-step checkout flow, and an :class:`EmptyState`. A button
advances the stepper, updating the state in place.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.style import Edge
from tempestweb.components import (
    Alert,
    Badge,
    Banner,
    Card,
    EmptyState,
    ProgressStepper,
)

CHECKOUT_STEPS: list[str] = ["Cart", "Shipping", "Payment", "Done"]


@dataclass
class State:
    """State for the feedback gallery.

    Attributes:
        step: The zero-based index of the active checkout step.
    """

    step: int = 0
    steps: list[str] = field(default_factory=lambda: list(CHECKOUT_STEPS))


def make_state() -> State:
    """Build the initial state.

    Returns:
        A fresh :class:`State` positioned on the first checkout step.
    """
    return State()


def view(app: App[State]) -> Widget:
    """Render the feedback gallery from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def advance() -> None:
        """Move the stepper to the next step, clamped at the last one."""
        last: int = len(app.state.steps) - 1
        app.set_state(lambda s: setattr(s, "step", min(s.step + 1, last)))

    def reset() -> None:
        """Return the stepper to the first step."""
        app.set_state(lambda s: setattr(s, "step", 0))

    is_done: bool = app.state.step >= len(app.state.steps) - 1

    alerts: Card = Card(
        key="alerts-card",
        children=[
            Text(content="Alerts", key="alerts-title"),
            Alert(
                key="alert-info",
                title="Heads up",
                body="This is an informational alert.",
                color_scheme="info",
            ),
            Alert(
                key="alert-success",
                title="Saved",
                body="Your changes were saved successfully.",
                color_scheme="success",
            ),
            Alert(
                key="alert-warning",
                title="Check your input",
                body="Some fields look incomplete.",
                color_scheme="warning",
            ),
            Alert(
                key="alert-error",
                title="Payment failed",
                body="We could not charge your card.",
                color_scheme="error",
            ),
        ],
    )

    badges: Card = Card(
        key="badges-card",
        children=[
            Text(content="Badges", key="badges-title"),
            Row(
                key="badges-row",
                style=Style(gap=8.0),
                children=[
                    Badge(label="New", tone="success", key="badge-new"),
                    Badge(label="Beta", tone="info", key="badge-beta"),
                    Badge(label="Deprecated", tone="warning", key="badge-dep"),
                    Badge(label="3", tone="error", key="badge-count"),
                ],
            ),
        ],
    )

    stepper: Card = Card(
        key="stepper-card",
        children=[
            Text(content="Checkout progress", key="stepper-title"),
            ProgressStepper(
                key="checkout-stepper",
                steps=app.state.steps,
                current=app.state.step,
            ),
            Row(
                key="stepper-actions",
                style=Style(gap=8.0),
                children=[
                    Button(label="Next step", on_click=advance, key="next"),
                    Button(label="Reset", on_click=reset, key="reset"),
                ],
            ),
        ],
    )

    empty: Card = Card(
        key="empty-card",
        children=[
            EmptyState(
                key="empty-state",
                title="Your cart is empty",
                subtitle="Browse the catalog to add your first item.",
            ),
        ],
    )

    summary: Widget = (
        Alert(
            key="summary-alert",
            title="Order complete",
            body="Thanks! Your order is on its way.",
            color_scheme="success",
        )
        if is_done
        else Banner(
            key="summary-banner",
            message="Complete the steps above to place your order.",
            tone="info",
        )
    )

    return Column(
        key="root",
        style=Style(gap=16.0, padding=Edge.all(16)),
        children=[
            Text(content="Feedback & status gallery", key="heading"),
            Banner(
                key="top-banner",
                message="Scheduled maintenance tonight at 02:00 UTC.",
                tone="warning",
            ),
            summary,
            alerts,
            badges,
            stepper,
            empty,
        ],
    )
