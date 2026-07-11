"""Offline queue — durable writes that survive being offline (native.offline).

The same ``view`` runs unchanged in both interactive modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

A tiny "activity log": typing a note and pressing **Queue** appends a mutation to
the durable offline queue (`native.offline.enqueue`) instead of hitting the
network directly — so it works with no connectivity. The pending count comes from
`native.offline.size`, and **Replay** drains the queue in FIFO order
(`native.offline.replay`), which the runtime also does automatically when
connectivity returns. The server dedups on the idempotency key, so a replay never
double-applies.

The initial mount only reads state, so ``build(view(app))`` is green with no
native bridge installed; the async handlers call the capability, and the test
drives them through a scripted bridge.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Style, Widget
from tempest_core.style import Edge
from tempest_core.widgets import Button, Column, Input, Row, Text
from tempest_core.widgets.events import TextChangeEvent
from tempestweb import native


@dataclass
class QueueState:
    """State for the offline-queue demo.

    Attributes:
        draft: The text currently typed into the input.
        queued: The number of pending mutations (from the last refresh).
        status: A short human-readable status line.
    """

    draft: str = ""
    queued: int = 0
    status: str = ""
    log: list[str] = field(default_factory=list)


def make_state() -> QueueState:
    """Build the initial state.

    Returns:
        A fresh :class:`QueueState`.
    """
    return QueueState()


def view(app: App[QueueState]) -> Widget:
    """Render the input, the pending count, and the replay control.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def on_draft(event: TextChangeEvent) -> None:
        value = event.value
        app.set_state(lambda s: setattr(s, "draft", value))

    async def queue_note() -> None:
        text = app.state.draft
        await native.offline.enqueue("POST", "/api/log", {"text": text})
        size = await native.offline.size()

        def _update(s: QueueState) -> None:
            s.queued = size
            s.draft = ""
            s.log = [*s.log, text]
            s.status = f"queued: {text}"

        app.set_state(_update)

    async def replay() -> None:
        result = await native.offline.replay()

        def _update(s: QueueState) -> None:
            s.queued = result.remaining
            s.status = f"replayed {result.sent}, {result.remaining} left"

        app.set_state(_update)

    return Column(
        style=Style(gap=10.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Pending: {app.state.queued}", key="pending"),
            Row(
                style=Style(gap=6.0),
                children=[
                    Input(
                        value=app.state.draft,
                        placeholder="a note to sync",
                        on_change=on_draft,
                        key="draft",
                    ),
                    Button(label="Queue", on_click=queue_note, key="queue"),
                    Button(label="Replay", on_click=replay, key="replay"),
                ],
            ),
            Text(content=app.state.status, key="status"),
            Column(
                style=Style(gap=2.0),
                children=[
                    Text(content=f"• {entry}", key=f"log-{i}")
                    for i, entry in enumerate(app.state.log)
                ],
            ),
        ],
    )
