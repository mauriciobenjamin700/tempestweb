# Charts dashboard — Canvas-backed charts 🚀

In this example you'll build a **mini analytics dashboard**: two charts (a bar
chart and a multi-series line chart) drawn on a `<canvas>`, a row of metric cards,
and a **Next week** button that rewrites the data. Everything is driven by typed
Python state — you don't write a single line of JavaScript.

---

## What you'll build

- 📊 A **BarChart** with the week's daily revenue.
- 📈 A **LineChart** with two series (visits and sign-ups).
- 🧮 A row of **MetricCard** / **StatCard** widgets with totals and percentage deltas.
- 🔁 A **Next week** button that advances the data window and repaints the charts.

!!! note "Note — deterministic data"
    The example keeps only a week index (`week: int`) in state. Every number —
    totals, deltas, series — is **derived** inside `view()` on each render. No
    redundant state, no drift.

---

## Prerequisites

```bash
pip install tempestweb
```

!!! tip "Tip"
    If you're not yet familiar with the state → view → patches cycle, read the
    [introductory tutorial](../tutorial/index.md) first.

---

## Step 1 — Domain data

We start with two weeks of synthetic figures. The dashboard shows one week at a
time; the button toggles between them.

```python
from __future__ import annotations

from dataclasses import dataclass, field

# Two weeks of synthetic daily figures.
WEEKLY_REVENUE: list[list[float]] = [
    [1200.0, 1500.0, 900.0, 1800.0, 2100.0, 2400.0, 1700.0],
    [1600.0, 1400.0, 2000.0, 2300.0, 1900.0, 2600.0, 2200.0],
]
WEEKLY_VISITS: list[list[float]] = [
    [320.0, 410.0, 280.0, 500.0, 640.0, 720.0, 480.0],
    [450.0, 390.0, 560.0, 680.0, 600.0, 810.0, 700.0],
]
WEEKLY_SIGNUPS: list[list[float]] = [
    [12.0, 18.0, 9.0, 22.0, 31.0, 40.0, 25.0],
    [20.0, 16.0, 28.0, 34.0, 30.0, 45.0, 38.0],
]
DAY_LABELS: list[str] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
```

The data lives as module constants — it is never copied into state.

---

## Step 2 — The state

The state is tiny: just the week index and the x-axis labels.

```python
@dataclass
class DashboardState:
    """State for the analytics dashboard.

    Attributes:
        week: Index of the currently displayed week (0 or 1).
        labels: The x-axis day labels shared by every chart.
    """

    week: int = 0
    labels: list[str] = field(default_factory=lambda: list(DAY_LABELS))


def make_state() -> DashboardState:
    """Build the initial dashboard state.

    Returns:
        A fresh :class:`DashboardState` showing the first week.
    """
    return DashboardState()
```

---

## Step 3 — Formatting helpers

Two small pure helpers keep `view` clean: one formats money, the other computes
the percentage delta between two totals.

```python
def _money(value: float) -> str:
    """Format a number as a compact USD string.

    Args:
        value: The raw monetary amount.

    Returns:
        The amount formatted with a dollar sign and thousands separators.
    """
    return f"${value:,.0f}"


def _delta_pct(current: float, previous: float) -> tuple[str, bool]:
    """Compute a percentage delta and its direction.

    Args:
        current: The current period's total.
        previous: The prior period's total to compare against.

    Returns:
        A tuple of the formatted percentage string and whether it went up.
    """
    if previous == 0.0:
        return "+0%", True
    change: float = (current - previous) / previous * 100.0
    return f"{change:+.1f}%", change >= 0.0
```

!!! tip "Tip — pure functions are testable"
    Since `_money` and `_delta_pct` never touch `app.state`, you can test them
    directly with `pytest`, no runtime required.

---

## Step 4 — Metric cards

`MetricCard` and `StatCard` take `label`, `value`, `delta`, `delta_up` and a
`color_scheme`. The `delta_up` flag controls the arrow color (green up, red down).

```python
from tempest_core import Row, Style
from tempestweb.components import MetricCard, StatCard

metrics: Row = Row(
    style=Style(gap=12.0),
    children=[
        MetricCard(
            key="m-revenue",
            label="Revenue",
            value=_money(revenue_total),
            delta=revenue_delta,
            delta_up=revenue_up,
            color_scheme="primary",
        ),
        MetricCard(
            key="m-visits",
            label="Visits",
            value=f"{visits_total:,.0f}",
            delta=visits_delta,
            delta_up=visits_up,
            color_scheme="secondary",
        ),
        StatCard(
            key="m-signups",
            label="Sign-ups",
            value=f"{signups_total:,.0f}",
            delta=signups_delta,
            delta_up=signups_up,
            color_scheme="tertiary",
        ),
    ],
)
```

---

## Step 5 — The Canvas charts

`BarChart` takes `values` + `labels`. `LineChart` takes a list of `ChartSeries`,
each with its own `points`, a `label` and a `color_scheme`. Both draw on a
`<canvas>` — `width`/`height` set the bitmap size.

```python
from tempest_core import Card, Text
from tempestweb.components import BarChart, ChartSeries, LineChart

revenue_card: Card = Card(
    key="card-revenue",
    children=[
        Text(content="Daily revenue", key="title-revenue"),
        BarChart(
            key="chart-revenue",
            width=520.0,
            height=220.0,
            color_scheme="primary",
            values=revenue,
            labels=app.state.labels,
        ),
    ],
)

trends_card: Card = Card(
    key="card-trends",
    children=[
        Text(content="Engagement trends", key="title-trends"),
        LineChart(
            key="chart-trends",
            width=520.0,
            height=220.0,
            series=[
                ChartSeries(points=visits, label="Visits", color_scheme="primary"),
                ChartSeries(
                    points=signups,
                    label="Sign-ups",
                    color_scheme="tertiary",
                ),
            ],
        ),
    ],
)
```

!!! info "Info — the Canvas is just another tree node"
    The DOM renderer emits a `<canvas>` and re-runs the drawing whenever the
    `values`/`series` change. To you, the app author, the chart is just a widget
    like any other — no hand-written 2D-context juggling.

---

## Step 6 — The "Next week" handler

A single handler advances the data window, wrapping around with modulo:

```python
def next_week() -> None:
    app.set_state(lambda s: setattr(s, "week", (s.week + 1) % len(WEEKLY_REVENUE)))
```

Since everything is derived from `state.week`, changing that index repaints
**all** charts and cards at once.

---

## The complete app

```python
"""Charts dashboard — a tempestweb example showcasing Canvas-backed charts.

This small analytics dashboard renders two charts (a bar chart and a multi-series
line chart) plus a row of metric cards, all driven entirely by typed Python state.
Like every tempestweb example, the same ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

A "Next week" button mutates the state to advance the data window, demonstrating
that the charts re-render reactively from the same source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.style import Edge
from tempestweb.components import (
    BarChart,
    Card,
    ChartSeries,
    LineChart,
    MetricCard,
    StatCard,
)

# Two weeks of synthetic daily figures. The dashboard shows one week at a time and
# the "Next week" button toggles between them.
WEEKLY_REVENUE: list[list[float]] = [
    [1200.0, 1500.0, 900.0, 1800.0, 2100.0, 2400.0, 1700.0],
    [1600.0, 1400.0, 2000.0, 2300.0, 1900.0, 2600.0, 2200.0],
]
WEEKLY_VISITS: list[list[float]] = [
    [320.0, 410.0, 280.0, 500.0, 640.0, 720.0, 480.0],
    [450.0, 390.0, 560.0, 680.0, 600.0, 810.0, 700.0],
]
WEEKLY_SIGNUPS: list[list[float]] = [
    [12.0, 18.0, 9.0, 22.0, 31.0, 40.0, 25.0],
    [20.0, 16.0, 28.0, 34.0, 30.0, 45.0, 38.0],
]
DAY_LABELS: list[str] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass
class DashboardState:
    """State for the analytics dashboard.

    Attributes:
        week: Index of the currently displayed week (0 or 1).
        labels: The x-axis day labels shared by every chart.
    """

    week: int = 0
    labels: list[str] = field(default_factory=lambda: list(DAY_LABELS))


def make_state() -> DashboardState:
    """Build the initial dashboard state.

    Returns:
        A fresh :class:`DashboardState` showing the first week.
    """
    return DashboardState()


def _money(value: float) -> str:
    """Format a number as a compact USD string.

    Args:
        value: The raw monetary amount.

    Returns:
        The amount formatted with a dollar sign and thousands separators.
    """
    return f"${value:,.0f}"


def _delta_pct(current: float, previous: float) -> tuple[str, bool]:
    """Compute a percentage delta and its direction.

    Args:
        current: The current period's total.
        previous: The prior period's total to compare against.

    Returns:
        A tuple of the formatted percentage string and whether it went up.
    """
    if previous == 0.0:
        return "+0%", True
    change: float = (current - previous) / previous * 100.0
    return f"{change:+.1f}%", change >= 0.0


def view(app: App[DashboardState]) -> Widget:
    """Render the dashboard UI from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def next_week() -> None:
        app.set_state(lambda s: setattr(s, "week", (s.week + 1) % len(WEEKLY_REVENUE)))

    week: int = app.state.week
    prev: int = (week - 1) % len(WEEKLY_REVENUE)

    revenue: list[float] = WEEKLY_REVENUE[week]
    visits: list[float] = WEEKLY_VISITS[week]
    signups: list[float] = WEEKLY_SIGNUPS[week]

    revenue_total: float = sum(revenue)
    visits_total: float = sum(visits)
    signups_total: float = sum(signups)

    revenue_delta, revenue_up = _delta_pct(revenue_total, sum(WEEKLY_REVENUE[prev]))
    visits_delta, visits_up = _delta_pct(visits_total, sum(WEEKLY_VISITS[prev]))
    signups_delta, signups_up = _delta_pct(signups_total, sum(WEEKLY_SIGNUPS[prev]))

    metrics: Row = Row(
        style=Style(gap=12.0),
        children=[
            MetricCard(
                key="m-revenue",
                label="Revenue",
                value=_money(revenue_total),
                delta=revenue_delta,
                delta_up=revenue_up,
                color_scheme="primary",
            ),
            MetricCard(
                key="m-visits",
                label="Visits",
                value=f"{visits_total:,.0f}",
                delta=visits_delta,
                delta_up=visits_up,
                color_scheme="secondary",
            ),
            StatCard(
                key="m-signups",
                label="Sign-ups",
                value=f"{signups_total:,.0f}",
                delta=signups_delta,
                delta_up=signups_up,
                color_scheme="tertiary",
            ),
        ],
    )

    revenue_card: Card = Card(
        key="card-revenue",
        children=[
            Text(content="Daily revenue", key="title-revenue"),
            BarChart(
                key="chart-revenue",
                width=520.0,
                height=220.0,
                color_scheme="primary",
                values=revenue,
                labels=app.state.labels,
            ),
        ],
    )

    trends_card: Card = Card(
        key="card-trends",
        children=[
            Text(content="Engagement trends", key="title-trends"),
            LineChart(
                key="chart-trends",
                width=520.0,
                height=220.0,
                series=[
                    ChartSeries(points=visits, label="Visits", color_scheme="primary"),
                    ChartSeries(
                        points=signups,
                        label="Sign-ups",
                        color_scheme="tertiary",
                    ),
                ],
            ),
        ],
    )

    return Column(
        style=Style(gap=16.0, padding=Edge.all(24)),
        children=[
            Row(
                style=Style(gap=12.0),
                children=[
                    Text(content=f"Analytics — Week {week + 1}", key="heading"),
                    Button(label="Next week", on_click=next_week, key="next-week"),
                ],
            ),
            metrics,
            Row(
                style=Style(gap=16.0),
                children=[revenue_card, trends_card],
            ),
        ],
    )
```

---

## Running the example ▶

=== "Mode A — WASM (Python in the browser)"

    ```bash
    tempestweb dev --mode wasm examples/charts-dashboard/app.py
    ```

    Pyodide loads Python in the browser; the `<canvas>` is drawn locally.

=== "Mode B — Server (FastAPI + WebSocket)"

    ```bash
    tempestweb dev --mode server examples/charts-dashboard/app.py
    ```

    Python runs on the server; the client receives JSON patches and repaints the canvas.

!!! check "Verification"
    You should see two charts and three metric cards. Click **Next week** → the
    title changes to "Week 2", the bars and lines rearrange, and the deltas
    recompute. ✅

---

## Recap

- ✅ Keep **only the minimum** in state (`week`) and derive the rest in `view`.
- ✅ Render Canvas charts with `BarChart` and `LineChart` + `ChartSeries`.
- ✅ Show metrics with `MetricCard` / `StatCard` (`delta` + `delta_up`).
- ✅ Repaint everything with a single state mutation.
- ✅ Run the same `app.py` in both modes without changing a line.

!!! tip "Next steps"
    - Add a range selector (day/week/month) with `SegmentedControl`.
    - See the [Dashboard app shell](dashboard-shell.md) for a full layout.
