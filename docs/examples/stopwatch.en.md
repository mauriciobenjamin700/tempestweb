# Stopwatch — Timer with Lap Recording 🚀

Build a fully functional stopwatch with Start/Stop, Lap, and Reset buttons — and learn how to manage time-based state **deterministically** in tempestweb.

---

## What you'll build

A classic stopwatch featuring:

- ⏱ Large display showing `MM:SS.T`
- ▶ **Start/Stop** button that toggles in real time
- 🏁 **Lap** button to record split times
- 🔄 **Reset** button that clears everything
- 🔬 **Tick (+0.1 s)** button to advance the clock manually (great for testing)

!!! note "Note — deterministic time"
    Elapsed time is stored as an **integer count of tenths of a second** (`tenths: int`). This makes the widget tree completely deterministic — no `datetime.now()` or `time.time()` inside `view()`. In a deployed app the runtime calls `app.set_state` from an `asyncio.sleep(0.1)` loop; the `view` function itself never needs to change.

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
mkdir -p examples/stopwatch
touch examples/stopwatch/app.py
```

---

## Step 1 — Defining the state

Every tempestweb app starts with its **state**. Think first about what needs to be remembered between renders.

For a stopwatch, we need three things:

| Field | Type | Meaning |
|---|---|---|
| `running` | `bool` | Is it currently counting? |
| `tenths` | `int` | Accumulated tenths of a second |
| `laps` | `list[int]` | Recorded lap times |

```python
from __future__ import annotations

from dataclasses import dataclass, field


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
```

!!! tip "Tip — `field(default_factory=list)`"
    Never use `laps: list[int] = []` in a dataclass. Python would share the same list across all instances. `field(default_factory=list)` guarantees a fresh list for every instance.

---

## Step 2 — Formatting time

Before the UI, we need a helper that converts tenths of a second into something readable:

```python
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
```

Quick examples:

| `tenths` | Result |
|---|---|
| `0` | `00:00.0` |
| `7` | `00:00.7` |
| `137` | `00:13.7` |
| `3600` | `06:00.0` |

---

## Step 3 — Event handlers

Inside `view()`, we define the functions that respond to button clicks. Each one calls `app.set_state(mutator)` where the mutator receives the current state and modifies it in place:

```python
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
```

!!! info "Note — why is `tick` a button?"
    In production, `tick` would be driven by an `asyncio.sleep(0.1)` loop on the server (Mode B) or a `setInterval` in the Service Worker (Mode A). Exposing it as a button keeps the example completely **self-contained and testable** without a real timer running in the background.

---

## Step 4 — Building the widget tree

Now we assemble the UI. The stopwatch has three sections:

1. **Display** — large `monospace` number, green when running
2. **Controls** — four buttons in a `Row`
3. **Lap list** — only appears when laps have been recorded

```python
from tempestweb._core import App, Button, Column, Row, Style, Text, Widget
from tempestweb._core.style import (
    AlignItems,
    Color,
    Edge,
    FontWeight,
    JustifyContent,
    TextAlign,
)


def view(app: App[StopwatchState]) -> Widget:
    """Render the stopwatch UI from the current state."""
    state: StopwatchState = app.state

    # ... (handlers defined here — see Step 3)

    start_stop_label: str = "Stop" if state.running else "Start"
    main_display: str = _format_time(state.tenths)

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

    return Column(
        style=Style(
            gap=24.0,
            padding=Edge.all(24.0),
            align=AlignItems.CENTER,
        ),
        children=[
            Text(
                content="Stopwatch",
                key="title",
                style=Style(
                    font_size=22.0,
                    font_weight=FontWeight.BOLD,
                    text_align=TextAlign.CENTER,
                ),
            ),
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
```

!!! tip "Tip — conditional rendering with `*([] if ... else [...])`"
    Python doesn't have JSX, but the `*([widget] if condition else [])` pattern inside a `children` list works perfectly as conditional rendering. The lap list only appears in the DOM when `state.laps` is non-empty.

---

## The complete app

Here is the full file, ready to copy:

```python
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

from tempestweb._core import App, Button, Column, Row, Style, Text, Widget
from tempestweb._core.style import (
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

    The tree is a :class:`~tempestweb._core.widgets.Column` with three
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
```

---

## Running the example ▶

### Mode A — Python in the browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm examples/stopwatch/app.py
```

Python runs **inside the browser** via Pyodide. No server required.

### Mode B — Python on the server (FastAPI + WebSocket)

```bash
tempestweb dev --mode server examples/stopwatch/app.py
```

Python runs on the server; the browser receives JSON patches over WebSocket and applies them to the DOM.

!!! check "Verification"
    In either mode, you should see:
    
    1. Display showing `00:00.0`, centred
    2. Four buttons: **Start**, **Lap**, **Reset**, **Tick (+0.1 s)**
    3. Click **Start** → label changes to **Stop** and display turns green
    4. Click **Tick (+0.1 s)** repeatedly → display advances
    5. Click **Lap** → "Laps" section appears with the current time
    6. Click **Reset** → everything clears and the lap section disappears

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

All should pass green. The example was specifically designed to be `mypy --strict` clean — every variable and return type is explicitly annotated.

---

## How it works under the hood

### The update cycle

```
Button click
      │
      ▼
handler (e.g. start_stop)
      │
      ▼
app.set_state(mutator)
      │
      ▼
tempestweb applies mutator → new state
      │
      ▼
view(app) called again → new widget tree
      │
      ▼
reconciler computes diff (patches)
      │
      ▼
DOM updated (minimum changes)
```

### State vs. derived values

The `state` holds **only the minimum** necessary (`running`, `tenths`, `laps`). Everything else — `main_display`, `start_stop_label`, `lap_widgets` — is **derived** inside `view()` on each render. This is intentional: less state to manage, fewer bugs.

### Why `key` on every widget?

The reconciler uses `key` to identify widgets across renders. Without `key`, a growing lap list would cause the wrong nodes to be remounted. With `key=f"lap-{i}"`, each lap row stays stable in the DOM even as new ones are added.

---

## Recap

In this tutorial you learned:

- ✅ Model **deterministic time-based state** using integer tenths of a second
- ✅ Use `app.set_state(mutator)` with nested functions for complex mutations
- ✅ Write **conditional rendering** with `*([widget] if cond else [])`
- ✅ Use stable `key` on dynamic lists so the reconciler works correctly
- ✅ Separate **state** (minimum) from **derived values** (computed in `view`)
- ✅ Write a pure, testable formatting helper outside the UI

---

## Next steps

Try extending the example:

- 💡 Add a **best lap** indicator that highlights the fastest lap in blue
- 💡 Wire up a real timer with `asyncio.sleep(0.1)` in Mode B (see [Execution modes](../tutorial/modes.md))
- 💡 Explore the [Tutorial — the Counter](../tutorial/index.md) for the simplest `set_state` pattern
- 💡 Explore [Todo in the tutorial](../tutorial/state.md) for another dynamic list with `key`
