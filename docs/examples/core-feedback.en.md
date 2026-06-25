# Feedback & status — alerts, banners and progress 🚀

In this example you'll build a **gallery of the core's feedback components**:
`Alert` (info/success/warning/error), `Banner`, `Badge`, `ProgressStepper` and
`EmptyState` — all on a single state-driven screen. **Next step** and **Reset**
buttons advance a multi-step checkout flow.

---

## What you'll build

- 🚨 Four **Alert** widgets (info, success, warning, error) via `color_scheme`.
- 📢 A maintenance **Banner** plus one that changes with the progress.
- 🏷️ A row of **Badge** chips with distinct tones.
- 🪜 A **ProgressStepper** driving a checkout (`steps` + `current`).
- 📭 An illustrative **EmptyState**.

---

## Prerequisites

```bash
pip install tempestweb
```

!!! tip "Tip"
    If you're not yet familiar with the state → view → patches cycle, read the
    [introductory tutorial](../tutorial/index.md).

---

## Step 1 — The state

The state keeps only the index of the current checkout step, plus the step list.

```python
from __future__ import annotations

from dataclasses import dataclass, field

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
```

---

## Step 2 — The handlers

`advance` moves to the next step with `min(...)` so it never overshoots the last;
`reset` returns to the start.

```python
def advance() -> None:
    """Move the stepper to the next step, clamped at the last one."""
    last: int = len(app.state.steps) - 1
    app.set_state(lambda s: setattr(s, "step", min(s.step + 1, last)))

def reset() -> None:
    """Return the stepper to the first step."""
    app.set_state(lambda s: setattr(s, "step", 0))
```

---

## Step 3 — The alerts

`Alert` takes `title`, `body` and a `color_scheme` that picks the visual variant:
`"info"`, `"success"`, `"warning"` or `"error"`.

```python
from tempest_core import Text
from tempestweb.components import Alert, Card

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
```

---

## Step 4 — Badges and the stepper

`Badge` takes `label` + `tone`. The `ProgressStepper` takes the `steps` list and
the `current` index — it draws itself from the state.

```python
from tempest_core import Button, Row, Style, Text
from tempestweb.components import Badge, Card, ProgressStepper

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
```

---

## Step 5 — EmptyState and the conditional summary

The `EmptyState` shows a friendly placeholder. The summary switches between an
`Alert` (when the checkout completes) and a `Banner` (while in progress).

```python
from tempestweb.components import Alert, Banner, Card, EmptyState

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
```

!!! info "Info — `Banner` uses `message`/`tone`, `Alert` uses `title`/`body`/`color_scheme`"
    They are two distinct components: `Banner` is a one-line strip
    (`message` + `tone`), while `Alert` is a block with a title and body
    (`title` + `body` + `color_scheme`).

---

## The complete app

```python
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
```

---

## Running the example ▶

=== "Mode A — WASM (Python in the browser)"

    ```bash
    tempestweb dev --mode wasm examples/core-feedback/app.py
    ```

=== "Mode B — Server (FastAPI + WebSocket)"

    ```bash
    tempestweb dev --mode server examples/core-feedback/app.py
    ```

!!! check "Verification"
    You should see four colored alerts, banners, badges and the checkout stepper.
    Click **Next step** a few times → the stepper advances; once it reaches
    "Done", the summary becomes a success alert. Click **Reset** → it returns to
    the start. ✅

---

## Recap

- ✅ Use `Alert` with `color_scheme` for the four variants (info/success/warning/error).
- ✅ Distinguish `Banner` (`message`/`tone`) from `Alert` (`title`/`body`/`color_scheme`).
- ✅ Show compact status with `Badge` (`label`/`tone`).
- ✅ Drive a `ProgressStepper` with `steps` + `current` derived from state.
- ✅ Swap the summary conditionally based on progress.
- ✅ Run the same `app.py` in both modes without changing a line.

!!! tip "Next steps"
    - See the [Notification center](notification-center.md) for dynamic feedback.
    - Combine with the [Signup wizard](signup-wizard.md) for a real multi-step flow.
