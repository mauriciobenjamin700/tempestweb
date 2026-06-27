"""Stopwatch — demonstrates time & timer state management in tempestweb.

A classic stopwatch with start/stop/reset controls and a lap-time recorder.
The elapsed time is stored as accumulated integer tenths-of-a-second so the
widget tree is fully deterministic — no wall-clock access is needed inside
``view``.  A "Tick (+0.1 s)" button advances the clock by one tenth of a
second, making the example self-contained and easily testable without a real
timer source.  In a deployed app the runtime would wire up a recurring
``app.set_state`` call from a ``setTimeout`` / ``asyncio.sleep`` loop; the
widget tree itself never changes.

Both modes work unchanged::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.style import (
    AlignItems,
    Color,
    Edge,
    FontWeight,
    JustifyContent,
    TextAlign,
)

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class StopwatchState:
    """Mutable state for the stopwatch application.

    Attributes:
        running: Whether the stopwatch is currently ticking.
        tenths: Total elapsed time in tenths of a second (0.1 s per unit).
        laps: Recorded lap times, each expressed as tenths of a second.
    """

    running: bool = False
    tenths: int = 0
    laps: list[int] = field(default_factory=list)


def make_state() -> StopwatchState:
    """Build the initial stopwatch state.

    Returns:
        A fresh :class:`StopwatchState` with the clock at zero.
    """
    return StopwatchState()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_time(tenths: int) -> str:
    """Format a tenths-of-a-second count as ``MM:SS.T``.

    Args:
        tenths: Elapsed time expressed in tenths of a second.

    Returns:
        A human-readable string of the form ``MM:SS.T``, e.g. ``01:23.7``.
    """
    total_seconds: int = tenths // 10
    t_digit: int = tenths % 10
    minutes: int = total_seconds // 60
    seconds: int = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}.{t_digit}"


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[StopwatchState]) -> Widget:
    """Render the stopwatch UI from the current state.

    The tree is a :class:`~tempest_core.widgets.Column` with three
    sections:

    1. **Display** — a large monospaced readout showing ``MM:SS.T``.
    2. **Controls** — Start/Stop, Lap, Reset and Tick buttons.
    3. **Lap list** — a scrollable column of recorded lap times.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """
    state: StopwatchState = app.state

    # -- Handlers --

    def start_stop() -> None:
        """Toggle the running flag on/off."""
        app.set_state(lambda s: setattr(s, "running", not s.running))

    def record_lap() -> None:
        """Append the current elapsed time to the lap list."""

        def _mutate(s: StopwatchState) -> None:
            s.laps.append(s.tenths)

        app.set_state(_mutate)

    def reset() -> None:
        """Stop the clock and clear all state."""

        def _mutate(s: StopwatchState) -> None:
            s.running = False
            s.tenths = 0
            s.laps = []

        app.set_state(_mutate)

    def tick() -> None:
        """Advance the clock by one tenth of a second (0.1 s).

        In a real deployment the runtime drives this from a timer; here it is
        exposed as a button so the example stays framework-agnostic and fully
        testable without async scheduling.  The handler is a no-op when the
        stopwatch is not running, matching the behaviour of a real timer that
        would simply not fire.
        """

        def _mutate(s: StopwatchState) -> None:
            if s.running:
                s.tenths += 1

        app.set_state(_mutate)

    # -- Derived display values --

    start_stop_label: str = "Stop" if state.running else "Start"
    main_display: str = _format_time(state.tenths)

    # -- Lap rows --

    lap_widgets: list[Widget] = [
        Row(
            key=f"lap-{i}",
            style=Style(
                justify=JustifyContent.SPACE_BETWEEN,
                padding=Edge.symmetric(vertical=4.0, horizontal=8.0),
                border=None,
            ),
            children=[
                Text(
                    content=f"Lap {i + 1}",
                    key=f"lap-label-{i}",
                    style=Style(
                        color=Color(r=100, g=100, b=100),
                        font_size=14.0,
                    ),
                ),
                Text(
                    content=_format_time(t),
                    key=f"lap-time-{i}",
                    style=Style(font_size=14.0, font_weight=FontWeight.MEDIUM),
                ),
            ],
        )
        for i, t in enumerate(state.laps)
    ]

    # -- Full tree --

    return Column(
        style=Style(
            gap=24.0,
            padding=Edge.all(24.0),
            align=AlignItems.CENTER,
        ),
        children=[
            # Title
            Text(
                content="Stopwatch",
                key="title",
                style=Style(
                    font_size=22.0,
                    font_weight=FontWeight.BOLD,
                    text_align=TextAlign.CENTER,
                ),
            ),
            # Main time display
            Text(
                content=main_display,
                key="display",
                style=Style(
                    font_size=56.0,
                    font_weight=FontWeight.BOLD,
                    font_family="monospace",
                    text_align=TextAlign.CENTER,
                    color=(
                        Color(r=34, g=139, b=34)
                        if state.running
                        else Color(r=30, g=30, b=30)
                    ),
                    letter_spacing=2.0,
                ),
            ),
            # Control buttons
            Row(
                key="controls",
                style=Style(
                    gap=12.0,
                    justify=JustifyContent.CENTER,
                    align=AlignItems.CENTER,
                ),
                children=[
                    Button(
                        label=start_stop_label,
                        on_click=start_stop,
                        key="start-stop",
                    ),
                    Button(
                        label="Lap",
                        on_click=record_lap,
                        key="lap",
                    ),
                    Button(
                        label="Reset",
                        on_click=reset,
                        key="reset",
                    ),
                ],
            ),
            # Tick button (testing / demo handle)
            Row(
                key="tick-row",
                style=Style(justify=JustifyContent.CENTER),
                children=[
                    Button(
                        label="Tick (+0.1 s)",
                        on_click=tick,
                        key="tick",
                    ),
                ],
            ),
            # Lap list (only rendered when there are recorded laps)
            *(
                [
                    Column(
                        key="lap-list",
                        style=Style(
                            gap=4.0,
                            padding=Edge.all(8.0),
                        ),
                        children=[
                            Text(
                                content="Laps",
                                key="laps-header",
                                style=Style(
                                    font_size=16.0,
                                    font_weight=FontWeight.SEMIBOLD,
                                ),
                            ),
                            *lap_widgets,
                        ],
                    )
                ]
                if state.laps
                else []
            ),
        ],
    )
