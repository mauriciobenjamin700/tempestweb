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

from tempestweb._core.components.feedback import Badge, Banner, EmptyState
from tempestweb._core.style import Edge

from tempestweb._core import App, Style, Widget
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
