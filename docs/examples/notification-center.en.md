# Notification Center 🚀

Build a complete notification inbox with `Banner`, `Badge`, and `EmptyState` — and learn how to model **aggregate feedback states** using a phase machine in tempestweb.

---

## What you'll build

A notification center featuring:

- 🔔 **Header** with title, a red `Badge` showing the unread count, and a context-aware action button
- 📣 **Aggregate status Banner** that reflects the overall inbox alarm level in real time
- 📋 **Lazy list** (`LazyColumn`) with one `Banner` per notification — each with its own dismiss button
- 🔕 **Empty state** (`EmptyState`) when all notifications are cleared
- Three verified transitions: *dismiss one*, *dismiss all*, and *reset*

!!! note "Note — phase machine"
    The app uses a `StrEnum` called `Phase` with two values: `INBOX` (one or more notifications present) and `CLEAR` (everything dismissed). The `view` reads `app.state.phase` to decide which branch to render — no stray booleans, no deeply nested conditionals.

---

## Prerequisites

Make sure tempestweb is installed:

```bash
pip install tempestweb
```

Recommended reading (optional):

- [Basic tutorial](../tutorial/index.md) — first steps with `App`, `view`, and `set_state`
- [Managing state](../tutorial/state.md) — how `set_state` works
- [Execution modes](../tutorial/modes.md) — WASM vs. server

---

## Creating the project

Create the folder and app file:

```bash
mkdir -p examples/notification-center
touch examples/notification-center/app.py
```

---

## Step 1 — Domain model

Before the UI, we need to represent a notification. Each item has a unique identifier, a message, a **tone** (severity), and a `read` flag.

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4


#: Notification severity levels, mapped directly to Banner tones.
TONES: tuple[str, ...] = ("info", "success", "warning", "error")


@dataclass
class Notification:
    """A single notification entry.

    Attributes:
        id: Unique identifier used as a widget key.
        message: The human-readable message text.
        tone: One of ``"info"``, ``"success"``, ``"warning"`` or ``"error"``.
        read: Whether the notification has been seen by the user.
    """

    id: str
    message: str
    tone: str
    read: bool = False


def _seed() -> list[Notification]:
    """Return the initial set of seed notifications.

    Returns:
        A fresh list of four pre-built notifications covering every tone.
    """
    return [
        Notification(
            id=str(uuid4()),
            message="Your export has been queued and will be ready shortly.",
            tone="info",
        ),
        Notification(
            id=str(uuid4()),
            message="Payment processed — invoice #2048 is available.",
            tone="success",
        ),
        Notification(
            id=str(uuid4()),
            message="Your free-tier storage is 85 % full.  Consider upgrading.",
            tone="warning",
        ),
        Notification(
            id=str(uuid4()),
            message="Scheduled job 'nightly-backup' failed.  Check the logs.",
            tone="error",
        ),
    ]
```

!!! tip "Tip — `uuid4()` for widget keys"
    Each notification receives a random `id` at creation time. That `id` is used as the `key` on its corresponding `Banner` widget. This ensures the reconciler correctly identifies each row even when items are removed from the middle of the list.

---

## Step 2 — Phase and state

`Phase` is a simple `StrEnum`. The top-level state combines the current phase with the item list and exposes a computed `unread_count` property.

```python
class Phase(StrEnum):
    """Lifecycle phase of the notification center.

    Attributes:
        INBOX: One or more notifications are present.
        CLEAR: All notifications have been dismissed.
    """

    INBOX = "inbox"
    CLEAR = "clear"


@dataclass
class NotificationState:
    """Top-level state for the notification-center app.

    Attributes:
        phase: Current lifecycle phase (INBOX or CLEAR).
        items: Ordered list of active notifications.
    """

    phase: Phase = Phase.INBOX
    items: list[Notification] = field(default_factory=_seed)

    @property
    def unread_count(self) -> int:
        """Count notifications that have not yet been read.

        Returns:
            Number of items whose ``read`` flag is ``False``.
        """
        return sum(1 for n in self.items if not n.read)


def make_state() -> NotificationState:
    """Build the initial application state with seed notifications.

    Returns:
        A fresh :class:`NotificationState` pre-populated with four items so
        the first mount shows a non-empty notification list.
    """
    return NotificationState()
```

!!! info "Note — `@property` vs. a state field"
    `unread_count` is a **derived property**, not a state field. It is recomputed on every call from the `items` list. This is intentional: keeping state minimal and computing what can be computed inside `view` (or in dataclass properties) prevents inconsistencies — you never forget to update a separate counter.

---

## Step 3 — Transition handlers

Inside `view()`, we define three handlers. Each one calls `app.set_state(mutator)` where the mutator receives the current state and modifies it in place:

```python
def dismiss_one(notification_id: str) -> None:
    """Remove a single notification and mark the inbox clear if empty.

    Args:
        notification_id: The ``id`` of the notification to remove.
    """

    def mutate(s: NotificationState) -> None:
        s.items = [n for n in s.items if n.id != notification_id]
        if not s.items:
            s.phase = Phase.CLEAR

    app.set_state(mutate)


def dismiss_all() -> None:
    """Remove every notification and switch to the CLEAR phase."""

    def mutate(s: NotificationState) -> None:
        s.items = []
        s.phase = Phase.CLEAR

    app.set_state(mutate)


def reset() -> None:
    """Restore the seed notifications and switch back to INBOX phase."""

    def mutate(s: NotificationState) -> None:
        s.items = _seed()
        s.phase = Phase.INBOX

    app.set_state(mutate)
```

!!! tip "Tip — automatic phase transition in `dismiss_one`"
    Notice that `dismiss_one` checks `if not s.items` after filtering the list. When the last item is dismissed, the phase switches to `CLEAR` automatically — no separate button or special "last item" handler is needed.

---

## Step 4 — Header with Badge

The header combines a `Text` with `grow=1.0` (takes the remaining space), a `Badge` with the unread count, and a conditional button that switches between "Dismiss all" and "Reset" depending on the phase:

```python
from tempestweb._core import App, Style, Widget
from tempestweb._core.components.feedback import Badge, Banner, EmptyState
from tempestweb._core.style import Edge
from tempestweb._core.widgets import Button, Column, LazyColumn, Row, Text


def view(app: App[NotificationState]) -> Widget:
    """Render the notification-center UI from the current state."""

    # ... (handlers defined here — see Step 3)

    unread = app.state.unread_count
    badge_label = str(unread) if unread > 0 else "0"

    header_children: list[Widget] = [
        Text(
            content="Notifications",
            style=Style(font_size=20.0, grow=1.0),
            key="nc-title",
        ),
        Badge(label=badge_label, tone="error", key="nc-badge"),
    ]

    if app.state.phase is Phase.INBOX:
        header_children.append(
            Button(label="Dismiss all", on_click=dismiss_all, key="nc-dismiss-all")
        )
    else:
        header_children.append(Button(label="Reset", on_click=reset, key="nc-reset"))

    header: Widget = Row(
        style=Style(gap=10.0, padding=Edge.symmetric(vertical=8.0, horizontal=0.0)),
        children=header_children,
        key="nc-header",
    )
```

!!! tip "Tip — `grow=1.0` on `Text`"
    `grow=1.0` makes the text widget stretch to fill all available space in the `Row`, pushing the `Badge` and the button to the right — the classic flexible header behavior, without any external CSS.

---

## Step 5 — Aggregate status Banner

A single `Banner` at the top of the page reflects the overall inbox state. Its `tone` and `message` are computed from the phase and the unread count:

```python
    if app.state.phase is Phase.CLEAR:
        status_tone = "success"
        status_message = "All caught up — your inbox is empty."
    elif unread > 0:
        status_tone = "warning"
        plural = "s" if unread != 1 else ""
        status_message = f"You have {unread} unread notification{plural}."
    else:
        status_tone = "info"
        status_message = "No new notifications."

    status_banner: Widget = Banner(
        message=status_message,
        tone=status_tone,
        key="nc-status-banner",
    )
```

!!! info "Note — three states of the aggregate banner"
    | Situation | Tone | Message |
    |---|---|---|
    | Phase `CLEAR` | `success` ✅ | "All caught up — your inbox is empty." |
    | Unread items exist | `warning` ⚠️ | "You have N unread notification(s)." |
    | No unread, still `INBOX` | `info` ℹ️ | "No new notifications." |

---

## Step 6 — Lazy list vs. EmptyState

This is the heart of the app: when items exist, we render a `LazyColumn` with one `Banner` per notification; when there are none, we show an `EmptyState` with a restore button.

```python
    if app.state.phase is Phase.CLEAR or not app.state.items:
        restore_btn: Widget = Button(
            label="Restore notifications", on_click=reset, key="nc-restore"
        )
        inbox_body: Widget = EmptyState(
            glyph="🔕",
            title="Your inbox is empty",
            subtitle="All notifications have been dismissed.",
            action=restore_btn,
            key="nc-empty",
        )
    else:
        items_snapshot = list(app.state.items)

        def build_row(index: int) -> Widget:
            """Build one notification row inside the lazy list.

            Args:
                index: Position in the current items snapshot.

            Returns:
                A ``Banner`` with a dismiss button in its action slot.
            """
            n = items_snapshot[index]
            dismiss_btn: Widget = Button(
                label="✕",
                on_click=lambda _nid=n.id: dismiss_one(_nid),
                key=f"dismiss-{n.id}",
            )
            return Banner(
                message=n.message,
                tone=n.tone,
                action=dismiss_btn,
                key=f"notif-{n.id}",
            )

        inbox_body = LazyColumn(
            item_count=len(items_snapshot),
            item_builder=build_row,
            key="nc-list",
        )
```

!!! warning "Warning — snapshot the list before entering `build_row`"
    Notice `items_snapshot = list(app.state.items)`. The `build_row` callback is invoked *during* the render pass with fixed indices. If `app.state.items` could change between calls (in concurrent environments), reading the state directly could cause index-out-of-range bugs. The snapshot guarantees consistency across the entire build pass.

!!! tip "Tip — `lambda _nid=n.id: dismiss_one(_nid)` (default argument capture)"
    Python closes over *variables*, not *values*. Inside a loop, `lambda: dismiss_one(n.id)` would capture the *variable* `n`, which at the end of the loop points to the last item — every button would dismiss the same notification. The `_nid=n.id` pattern creates a **default argument** that captures the *current value* of `n.id` for each closure. Always use this for callbacks generated inside loops.

---

## Step 7 — Assembling the full page

With the header, the status banner, and the inbox body ready, we assemble the final tree in a `Column`:

```python
    return Column(
        style=Style(gap=12.0, padding=Edge.all(16.0)),
        children=[
            header,
            status_banner,
            inbox_body,
        ],
    )
```

Simple, declarative, and easy to read. The entire `view` function stays under 150 lines.

---

## The complete app

Here is the full file, ready to copy:

```python
"""Notification center — exercises Banner, Badge and EmptyState feedback components.

Like :mod:`examples.counter.app`, this exact ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

This demo shows how to compose ``Banner``, ``Badge`` and ``EmptyState`` to model a
real-world notification inbox.  The panel header carries a red ``Badge`` with the
unread count.  Each notification row is an inline ``Banner`` (info / success /
warning / error tones) with a dismiss ``Button`` in its ``action`` slot.  Dismissing
all items clears the list and reveals an ``EmptyState`` telling the user their inbox
is clean.  A persistent ``Banner`` at the top surface the aggregate alarm level
(warning when any unread item exists, success once everything is dismissed).

State machine
-------------
* ``Phase.INBOX``  — one or more notifications are present.
* ``Phase.CLEAR``  — all notifications have been dismissed.

Transitions
-----------
* *dismiss one* → removes one notification; if the list empties, moves to CLEAR.
* *dismiss all* → removes every notification at once; moves to CLEAR.
* *reset*        → restores the seed notifications; moves back to INBOX.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4

from tempestweb._core import App, Style, Widget
from tempestweb._core.components.feedback import Badge, Banner, EmptyState
from tempestweb._core.style import Edge
from tempestweb._core.widgets import Button, Column, LazyColumn, Row, Text

# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

#: Notification severity levels, mapped directly to Banner tones.
TONES: tuple[str, ...] = ("info", "success", "warning", "error")


@dataclass
class Notification:
    """A single notification entry.

    Attributes:
        id: Unique identifier used as a widget key.
        message: The human-readable message text.
        tone: One of ``"info"``, ``"success"``, ``"warning"`` or ``"error"``.
        read: Whether the notification has been seen by the user.
    """

    id: str
    message: str
    tone: str
    read: bool = False


def _seed() -> list[Notification]:
    """Return the initial set of seed notifications.

    Returns:
        A fresh list of four pre-built notifications covering every tone.
    """
    return [
        Notification(
            id=str(uuid4()),
            message="Your export has been queued and will be ready shortly.",
            tone="info",
        ),
        Notification(
            id=str(uuid4()),
            message="Payment processed — invoice #2048 is available.",
            tone="success",
        ),
        Notification(
            id=str(uuid4()),
            message="Your free-tier storage is 85 % full.  Consider upgrading.",
            tone="warning",
        ),
        Notification(
            id=str(uuid4()),
            message="Scheduled job 'nightly-backup' failed.  Check the logs.",
            tone="error",
        ),
    ]


class Phase(StrEnum):
    """Lifecycle phase of the notification center.

    Attributes:
        INBOX: One or more notifications are present.
        CLEAR: All notifications have been dismissed.
    """

    INBOX = "inbox"
    CLEAR = "clear"


# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------


@dataclass
class NotificationState:
    """Top-level state for the notification-center app.

    Attributes:
        phase: Current lifecycle phase (INBOX or CLEAR).
        items: Ordered list of active notifications.
    """

    phase: Phase = Phase.INBOX
    items: list[Notification] = field(default_factory=_seed)

    @property
    def unread_count(self) -> int:
        """Count notifications that have not yet been read.

        Returns:
            Number of items whose ``read`` flag is ``False``.
        """
        return sum(1 for n in self.items if not n.read)


def make_state() -> NotificationState:
    """Build the initial application state with seed notifications.

    Returns:
        A fresh :class:`NotificationState` pre-populated with four items so
        the first mount shows a non-empty notification list.
    """
    return NotificationState()


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[NotificationState]) -> Widget:
    """Render the notification-center UI from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def dismiss_one(notification_id: str) -> None:
        """Remove a single notification and mark the inbox clear if empty.

        Args:
            notification_id: The ``id`` of the notification to remove.
        """

        def mutate(s: NotificationState) -> None:
            s.items = [n for n in s.items if n.id != notification_id]
            if not s.items:
                s.phase = Phase.CLEAR

        app.set_state(mutate)

    def dismiss_all() -> None:
        """Remove every notification and switch to the CLEAR phase."""

        def mutate(s: NotificationState) -> None:
            s.items = []
            s.phase = Phase.CLEAR

        app.set_state(mutate)

    def reset() -> None:
        """Restore the seed notifications and switch back to INBOX phase."""

        def mutate(s: NotificationState) -> None:
            s.items = _seed()
            s.phase = Phase.INBOX

        app.set_state(mutate)

    # ------------------------------------------------------------------
    # Header row: title + unread badge + action buttons
    # ------------------------------------------------------------------

    unread = app.state.unread_count
    badge_label = str(unread) if unread > 0 else "0"

    header_children: list[Widget] = [
        Text(
            content="Notifications",
            style=Style(font_size=20.0, grow=1.0),
            key="nc-title",
        ),
        Badge(label=badge_label, tone="error", key="nc-badge"),
    ]

    if app.state.phase is Phase.INBOX:
        header_children.append(
            Button(label="Dismiss all", on_click=dismiss_all, key="nc-dismiss-all")
        )
    else:
        header_children.append(Button(label="Reset", on_click=reset, key="nc-reset"))

    header: Widget = Row(
        style=Style(gap=10.0, padding=Edge.symmetric(vertical=8.0, horizontal=0.0)),
        children=header_children,
        key="nc-header",
    )

    # ------------------------------------------------------------------
    # Status banner (aggregate state feedback)
    # ------------------------------------------------------------------

    if app.state.phase is Phase.CLEAR:
        status_tone = "success"
        status_message = "All caught up — your inbox is empty."
    elif unread > 0:
        status_tone = "warning"
        plural = "s" if unread != 1 else ""
        status_message = f"You have {unread} unread notification{plural}."
    else:
        status_tone = "info"
        status_message = "No new notifications."

    status_banner: Widget = Banner(
        message=status_message,
        tone=status_tone,
        key="nc-status-banner",
    )

    # ------------------------------------------------------------------
    # Notification list or empty state
    # ------------------------------------------------------------------

    if app.state.phase is Phase.CLEAR or not app.state.items:
        restore_btn: Widget = Button(
            label="Restore notifications", on_click=reset, key="nc-restore"
        )
        inbox_body: Widget = EmptyState(
            glyph="🔕",
            title="Your inbox is empty",
            subtitle="All notifications have been dismissed.",
            action=restore_btn,
            key="nc-empty",
        )
    else:
        items_snapshot = list(app.state.items)

        def build_row(index: int) -> Widget:
            """Build one notification row inside the lazy list.

            Args:
                index: Position in the current items snapshot.

            Returns:
                A ``Banner`` with a dismiss button in its action slot.
            """
            n = items_snapshot[index]
            dismiss_btn: Widget = Button(
                label="✕",
                on_click=lambda _nid=n.id: dismiss_one(_nid),
                key=f"dismiss-{n.id}",
            )
            return Banner(
                message=n.message,
                tone=n.tone,
                action=dismiss_btn,
                key=f"notif-{n.id}",
            )

        inbox_body = LazyColumn(
            item_count=len(items_snapshot),
            item_builder=build_row,
            key="nc-list",
        )

    # ------------------------------------------------------------------
    # Assemble the full page
    # ------------------------------------------------------------------

    return Column(
        style=Style(gap=12.0, padding=Edge.all(16.0)),
        children=[
            header,
            status_banner,
            inbox_body,
        ],
    )
```

---

## Running the example ▶

### Mode A — Python in the browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm examples/notification-center/app.py
```

Python runs **inside the browser** via Pyodide. No server needed.

### Mode B — Python on the server (FastAPI + WebSocket)

```bash
tempestweb dev --mode server examples/notification-center/app.py
```

Python runs on the server; the browser receives JSON patches over the WebSocket and applies them to the DOM.

!!! check "Verification"
    In either mode, you should see:

    1. Header with **"Notifications"**, a red badge **"4"**, and **"Dismiss all"** button
    2. Warning banner: *"You have 4 unread notifications."*
    3. Four colored `Banner` items (blue / green / yellow / red) each with a **"✕"** button
    4. Click **"✕"** on any notification → it disappears; the badge updates
    5. Click **"✕"** on the last one → `EmptyState` appears; banner turns green *"All caught up"*
    6. Click **"Restore notifications"** → the list comes back; badge resets to **"4"**
    7. Click **"Dismiss all"** → direct transition to `EmptyState`

---

## Automated verification ✅

Run all four checks before committing:

```bash
# Lint
ruff check .

# Formatting
ruff format --check .

# Types
mypy --strict tempestweb

# Tests
pytest -q
```

All should pass green. The example was designed to be `mypy --strict` clean — every variable, parameter, and return value is explicitly annotated.

---

## How it works under the hood

### The update cycle

```
Click "✕" (dismiss_one)
      │
      ▼
app.set_state(mutate)
      │  filters the list, switches Phase if empty
      ▼
tempestweb applies the mutator → new state
      │
      ▼
view(app) called again → new widget tree
      │
      ▼
reconciler computes diff (patches)
      │
      ▼
DOM updated — only the removed Banner + Badge + status Banner
```

### LazyColumn vs. Column for lists

| | `Column` | `LazyColumn` |
|---|---|---|
| When to use | Short, static lists | Long or dynamic lists |
| How children are built | Ready `children` list | `item_builder(index)` callback |
| Build cost | All children at tree construction | Only visible children |

For a real inbox with hundreds of notifications, `LazyColumn` is the right choice.

### Why `key=f"notif-{n.id}"` and not `key=f"notif-{index}"`?

If you used `key=f"notif-{index}"`, dismissing the item at index 1 would make the former index-2 item become "index 1" — the reconciler would interpret that as an *update* to the existing node, not a *removal*. With `key=f"notif-{n.id}"`, each notification has a stable identity based on its `id`, and the reconciler handles the removal correctly.

---

## Recap

In this tutorial you learned:

- ✅ Model **UI feedback states** with a `StrEnum` phase machine (`Phase`)
- ✅ Use `Badge` to display notification counters with a color tone
- ✅ Use `Banner` at both the item level and the page-wide aggregate level
- ✅ Use `EmptyState` for the "empty inbox" state with a restore action
- ✅ Use `LazyColumn` with `item_builder` for efficient dynamic lists
- ✅ Capture values in closures with the `lambda _nid=n.id: ...` pattern
- ✅ Snapshot the list before entering `item_builder` for render consistency

---

## Next steps

Try extending the example:

- 💡 Add a `timestamp` field to `Notification` and show relative time ("2 min ago") in each Banner
- 💡 Implement "mark as read" (sets `read=True`) without removing the item — watch the `Badge` count decrease
- 💡 Filter notifications by `tone` with a tab selector (see the [Tabs Profile](./tabs-profile.en.md) example)
- 💡 Explore [Stopwatch](./stopwatch.en.md) for another phase-machine state pattern
- 💡 Read about [feedback components](../tutorial/index.md) to discover `Snackbar` and `ProgressBar`
