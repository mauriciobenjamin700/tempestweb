"""Copy & share — exercises the clipboard and share native capabilities.

Like :mod:`examples.counter.app`, this exact ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

The demo presents a short text snippet alongside two action buttons:

* **Copy** — writes the snippet to the OS clipboard via
  ``native.clipboard.write``.  The action status is stored in state so the UI
  reflects whether the write succeeded, failed or is still pending.
* **Share** — opens the platform share sheet via ``native.share.share`` and
  renders the :class:`~tempestweb.native.share.ShareOutcome` back to the user:
  ``shared``, ``cancelled``, or ``unsupported`` (the API does not exist in
  the current browser).

Both capability callables are **injected into** :class:`ClipShareState` with
real defaults so that:

1. ``build(view(app))`` is green with **no bridge installed** — the initial
   mount only reads state; it never calls the capabilities.
2. Tests swap in a ``FakeBridge`` and drive the async handlers end-to-end,
   asserting real state transitions.

State machine
-------------
* ``Phase.IDLE``    — nothing has been attempted yet.
* ``Phase.BUSY``    — a capability call is in flight (spinner or disabled feedback).
* ``Phase.COPIED``  — clipboard write succeeded.
* ``Phase.SHARED``  — share sheet completed (outcome stored separately).
* ``Phase.ERROR``   — the capability raised :class:`~tempestweb.native.NativeError`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum

from tempestweb._core import App, Style, Widget
from tempestweb._core.style import Edge
from tempestweb._core.widgets import Button, Column, Row, Spinner, Text
from tempestweb.native import clipboard
from tempestweb.native.share import ShareOutcome, ShareResult
from tempestweb.native.share import share as _native_share

# ---------------------------------------------------------------------------
# Injected capability types
# ---------------------------------------------------------------------------

#: A coroutine that writes text to the clipboard. Injected for testability.
Copier = Callable[[str], Awaitable[None]]

#: A coroutine that opens the share sheet. Injected for testability.
Sharer = Callable[..., Awaitable[ShareResult]]

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

#: The snippet shown to the user and offered for copy / share.
SNIPPET: str = "tempestweb — write UIs in typed Python, run them everywhere."


class Phase(StrEnum):
    """Lifecycle phase of the clipboard-share interaction.

    Attributes:
        IDLE: Nothing has been attempted yet.
        BUSY: A capability call is in flight.
        COPIED: The clipboard write succeeded.
        SHARED: The share sheet completed.
        ERROR: The capability raised an error.
    """

    IDLE = "idle"
    BUSY = "busy"
    COPIED = "copied"
    SHARED = "shared"
    ERROR = "error"


@dataclass
class ClipShareState:
    """Application state for the clipboard-share demo.

    Attributes:
        phase: Current lifecycle phase.
        share_outcome: The :class:`~tempestweb.native.share.ShareOutcome` from
            the last share attempt, or ``None`` if no share has been tried.
        error: Human-readable error message shown when ``phase`` is ERROR.
        copy: Injected clipboard-write coroutine (real default is the native cap).
        share_fn: Injected share coroutine (real default is the native cap).
    """

    phase: Phase = Phase.IDLE
    share_outcome: ShareOutcome | None = None
    error: str = ""
    copy: Copier = field(default=clipboard.write)
    share_fn: Sharer = field(default=_native_share)


def make_state() -> ClipShareState:
    """Build the initial, idle clipboard-share state.

    Returns:
        A fresh :class:`ClipShareState`.
    """
    return ClipShareState()


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[ClipShareState]) -> Widget:
    """Render the clipboard-share UI from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    # ------------------------------------------------------------------
    # Async handlers
    # ------------------------------------------------------------------

    async def do_copy() -> None:
        """Copy the snippet to the OS clipboard.

        Transitions: IDLE/ERROR -> BUSY -> COPIED | ERROR.
        """
        app.set_state(lambda s: setattr(s, "phase", Phase.BUSY))
        try:
            await app.state.copy(SNIPPET)
        except Exception as exc:  # noqa: BLE001 — surface to UI
            msg = str(exc)

            def _on_copy_error(s: ClipShareState) -> None:
                s.phase = Phase.ERROR
                s.error = msg

            app.set_state(_on_copy_error)
            return

        app.set_state(lambda s: setattr(s, "phase", Phase.COPIED))

    async def do_share() -> None:
        """Open the OS share sheet.

        Transitions: IDLE/ERROR -> BUSY -> SHARED (outcome stored) | ERROR.
        """
        app.set_state(lambda s: setattr(s, "phase", Phase.BUSY))
        try:
            result: ShareResult = await app.state.share_fn(
                title="tempestweb",
                text=SNIPPET,
                url="https://github.com/tempest-framework/tempestweb",
            )
        except Exception as exc:  # noqa: BLE001 — surface to UI
            msg = str(exc)

            def _on_share_error(s: ClipShareState) -> None:
                s.phase = Phase.ERROR
                s.error = msg

            app.set_state(_on_share_error)
            return

        def _on_shared(s: ClipShareState) -> None:
            s.phase = Phase.SHARED
            s.share_outcome = result.outcome

        app.set_state(_on_shared)

    # ------------------------------------------------------------------
    # Status text — reflects the last action
    # ------------------------------------------------------------------

    phase = app.state.phase

    if phase is Phase.IDLE:
        status_text = "Choose an action below."
    elif phase is Phase.BUSY:
        status_text = "Working…"
    elif phase is Phase.COPIED:
        status_text = "Copied to clipboard!"
    elif phase is Phase.SHARED:
        outcome = app.state.share_outcome
        if outcome is ShareOutcome.SHARED:
            status_text = "Shared successfully."
        elif outcome is ShareOutcome.CANCELLED:
            status_text = "Share cancelled."
        else:
            # UNSUPPORTED — Web Share API missing in this browser
            status_text = "Sharing is not supported in this browser."
    else:
        # ERROR
        status_text = f"Error: {app.state.error}"

    # ------------------------------------------------------------------
    # Action buttons row
    # ------------------------------------------------------------------

    is_busy = phase is Phase.BUSY
    action_children: list[Widget] = []

    if is_busy:
        action_children.append(Spinner(key="spinner"))
    else:
        action_children.extend(
            [
                Button(
                    label="Copy",
                    on_click=do_copy,
                    key="copy-btn",
                ),
                Button(
                    label="Share",
                    on_click=do_share,
                    key="share-btn",
                ),
            ]
        )

    actions: Widget = Row(
        style=Style(gap=8.0),
        children=action_children,
        key="actions",
    )

    # ------------------------------------------------------------------
    # Assemble the full view
    # ------------------------------------------------------------------

    return Column(
        style=Style(gap=16.0, padding=Edge.all(20.0)),
        children=[
            Text(content="Copy & Share", style=Style(font_size=22.0), key="title"),
            Text(
                content=SNIPPET,
                style=Style(font_size=14.0),
                key="snippet",
            ),
            actions,
            Text(content=status_text, key="status"),
        ],
    )
