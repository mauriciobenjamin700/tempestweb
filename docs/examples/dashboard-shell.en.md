# Dashboard App Shell

> 🚀 **What you'll build:** a complete dashboard shell with `Scaffold` + `AppBar` +
> `Sidebar` + `NavBar`, four swappable sections (Overview, Analytics, Users,
> Settings) and reactive state — all in plain typed Python, no manual CSS.

---

## Why this example matters

Most real web applications share the same shape: a top bar with a title and actions,
a side menu that organises sections, a bottom navigation bar for smaller screens, and
a central body area that swaps content without reloading the page.

Building that skeleton from scratch in traditional JavaScript involves routing, layout
CSS, state management and synchronisation between the sidebar and the bottom bar.
With tempestweb you describe all of it in typed Python — the framework handles the rest.

In this tutorial you'll learn to:

- Assemble the classic dashboard layout with `Scaffold`, `AppBar`, `Sidebar` and `NavBar`;
- Swap sections using a single `int` in state (`active_tab`);
- Display KPIs in a grid with `Grid` + `Card` + `Badge`;
- Build dismissible alerts with `Banner` and `Button`;
- Control sidebar visibility directly from a Settings section;
- Compose a user table with `Avatar`, `Badge` and `Divider`.

!!! note "Note"
    This example runs **without any changes** in both modes — WASM (Pyodide in the
    browser) and Server (FastAPI + WebSocket). The same Python `view()` serves both
    transports.

---

## Prerequisites

You should have already read the [core tutorial](../tutorial/index.md) and know what
`App`, `make_state` and `view` are. Install tempestweb if you haven't yet:

```bash
pip install tempestweb
tempestweb --version
```

---

## Project structure

```
examples/
└── dashboard-shell/
    └── app.py
```

```bash
mkdir -p examples/dashboard-shell
touch examples/dashboard-shell/app.py
```

---

## Step 1 — Imports and data model

All the code lives in a single file. We start with the imports and the two dataclasses
that define the application state.

```python
"""Dashboard shell — demonstrates Scaffold + AppBar + Sidebar + NavBar layout.

Selecting a :class:`NavBar` item swaps the body content via state. The sidebar
shows navigation shortcuts identical to the bottom bar so the layout works at
any screen width. Both modes run this exact ``view`` unchanged::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

The application never names a transport — that is the whole point.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from tempestweb._core import App, Style, Widget
from tempestweb._core.components import (
    AppBar,
    Avatar,
    Badge,
    Banner,
    Card,
    Divider,
    Grid,
    NavBar,
    Scaffold,
    Sidebar,
)
from tempestweb._core.components.base import (
    ACCENT,
    BACKGROUND,
    MUTED,
    ON_MUTED,
    ON_SURFACE,
    SURFACE,
)
from tempestweb._core.style import AlignItems, Color, Edge, FontWeight
from tempestweb._core.widgets import Button, Column, Container, Row, Text

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

_NAV_LABELS: list[str] = ["Overview", "Analytics", "Users", "Settings"]

_STAT_LABELS: list[str] = ["Revenue", "Sessions", "Signups", "Errors"]
_STAT_VALUES: list[str] = ["$128 400", "42 310", "1 870", "23"]
_STAT_TONES: list[str] = ["success", "info", "success", "error"]


@dataclass
class Alert:
    """A single dashboard alert entry.

    Attributes:
        message: The alert text.
        tone: The severity tone (info / success / warning / error).
        dismissed: Whether the user has dismissed this alert.
    """

    message: str
    tone: str
    dismissed: bool = False


@dataclass
class DashState:
    """Application state for the dashboard shell.

    Attributes:
        active_tab: Index of the currently selected navigation item.
        alerts: The list of active alerts shown on the Overview page.
        sidebar_open: Whether the collapsible sidebar is expanded.
    """

    active_tab: int = 0
    alerts: list[Alert] = field(
        default_factory=lambda: [
            Alert("Deploy #42 succeeded in production.", "success"),
            Alert("Queue depth above threshold — 1 200 jobs pending.", "warning"),
            Alert("Scheduled maintenance window in 3 hours.", "info"),
        ]
    )
    sidebar_open: bool = True


def make_state() -> DashState:
    """Build the initial dashboard state.

    Returns:
        A fresh :class:`DashState` landing on the Overview tab.
    """
    return DashState()
```

!!! tip "Tip — semantic colour tokens"
    `ACCENT`, `BACKGROUND`, `SURFACE`, `MUTED`, `ON_SURFACE` and `ON_MUTED` are
    semantic colour constants defined in `tempestweb._core.components.base`. They
    follow the default theme colour scheme and let you build consistent UIs without
    hardcoding hex values.

**What just happened:**

- `_NAV_LABELS` lists the four sections — the same value will be reused in both the
  `Sidebar` and the `NavBar`, keeping them in sync.
- `Alert.dismissed` starts as `False`; when the user clicks "✕", state changes to
  `True` and the alert disappears on the next render.
- `DashState.sidebar_open` controls sidebar visibility — toggled by either the "☰"
  button in the `AppBar` or the button inside the Settings section.

---

## Step 2 — Overview section: KPIs and dismissible alerts

The Overview section has two blocks: a KPI grid and an alert list. We build a helper
component for each metric card, then assemble the section body.

```python
def _stat_card(label: str, value: str, tone: str) -> Widget:
    """Render a single KPI card.

    Args:
        label: The metric label shown above the value.
        value: The formatted metric value.
        tone: A tone string accepted by :class:`Badge` (``"success"`` /
            ``"error"`` / ``"info"``).

    Returns:
        A :class:`Card` with the label, value and a status badge.
    """
    return Card(
        key=f"stat-{label}",
        children=[
            Text(
                content=label,
                style=Style(font_size=13.0, color=ON_MUTED),
                key=f"stat-label-{label}",
            ),
            Text(
                content=value,
                style=Style(
                    font_size=28.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                ),
                key=f"stat-value-{label}",
            ),
            Badge(label=tone.upper(), tone=tone, key=f"stat-badge-{label}"),
        ],
    )


def _overview_body(app: App[DashState]) -> Widget:
    """Render the Overview section body.

    Shows a KPI stats grid and the dismissible alert list.

    Args:
        app: The application handle.

    Returns:
        A :class:`Column` with the stats grid and alert banners.
    """

    def dismiss(index: int) -> None:
        """Dismiss the alert at *index*."""

        def mutate(s: DashState) -> None:
            s.alerts[index].dismissed = True

        app.set_state(mutate)

    stats_grid = Grid(
        key="stats-grid",
        columns=2,
        gap=12.0,
        children=[
            _stat_card(lbl, val, tone)
            for lbl, val, tone in zip(
                _STAT_LABELS, _STAT_VALUES, _STAT_TONES, strict=False
            )
        ],
    )

    visible_alerts: list[Widget] = []
    for idx, alert in enumerate(app.state.alerts):
        if alert.dismissed:
            continue
        i = idx  # capture loop variable

        def _make_dismiss(bound_i: int) -> Widget:
            return Button(
                label="✕",
                on_click=lambda _i=bound_i: dismiss(_i),
                key=f"dismiss-{bound_i}",
                style=Style(
                    padding=Edge.symmetric(vertical=4.0, horizontal=8.0),
                    radius=6.0,
                    background=Color.from_hex("#ffffff22"),
                    color=ON_SURFACE,
                    font_size=12.0,
                ),
            )

        visible_alerts.append(
            Banner(
                message=alert.message,
                tone=alert.tone,
                action=_make_dismiss(i),
                key=f"alert-{i}",
            )
        )

    alerts_section: Widget = Column(
        key="alerts-col",
        style=Style(gap=8.0),
        children=visible_alerts
        if visible_alerts
        else [
            Text(
                content="No active alerts.",
                style=Style(color=ON_MUTED, font_size=14.0),
                key="no-alerts",
            )
        ],
    )

    return Column(
        key="overview-body",
        style=Style(gap=20.0, padding=Edge.all(20.0), background=BACKGROUND),
        children=[
            Text(
                content="Key Metrics",
                style=Style(
                    font_size=16.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                ),
                key="metrics-heading",
            ),
            stats_grid,
            Text(
                content="Alerts",
                style=Style(
                    font_size=16.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                ),
                key="alerts-heading",
            ),
            alerts_section,
        ],
    )
```

!!! info "Info — `Grid` vs `Row`"
    `Grid(columns=2, gap=12.0)` distributes its children into two equal-width columns
    with 12 px spacing. Use `Grid` when you have an even number of items and want
    symmetric columns; use `Row` when you need fine-grained `grow` control per cell.

!!! warning "Warning — loop variable capture"
    In Python, closures capture the *variable*, not the *value*. That is why the loop
    assigns `i = idx` and the helper function `_make_dismiss(bound_i)` takes the index
    as an argument. Without this, every dismiss button would close the last alert.

**Highlights:**

| Widget | Purpose here |
|---|---|
| `Grid(columns=2)` | Two-column KPI grid |
| `Badge(tone="success")` | Colour-coded status indicator |
| `Banner(message=..., tone=..., action=...)` | Alert strip with an inline action widget |
| `Button(label="✕", on_click=...)` | Dismiss button for each alert |

---

## Step 3 — Analytics section: traffic table

The Analytics section renders a `Card` containing period / sessions / change rows
separated by `Divider`.

```python
def _analytics_body() -> Widget:
    """Render the Analytics section placeholder.

    Returns:
        A :class:`Column` describing the Analytics page content.
    """
    rows: list[Widget] = []
    periods: list[tuple[str, str, str]] = [
        ("This week", "8 340", "+12 %"),
        ("Last week", "7 450", "+5 %"),
        ("This month", "32 100", "+9 %"),
        ("Last month", "29 500", "+3 %"),
    ]
    for period, sessions, change in periods:
        rows.append(
            Row(
                key=f"row-{period}",
                style=Style(
                    gap=12.0,
                    align=AlignItems.CENTER,
                    padding=Edge.symmetric(vertical=10.0, horizontal=4.0),
                ),
                children=[
                    Text(
                        content=period,
                        style=Style(grow=1.0, color=ON_SURFACE, font_size=14.0),
                        key=f"period-{period}",
                    ),
                    Text(
                        content=sessions,
                        style=Style(
                            color=ON_SURFACE,
                            font_size=14.0,
                            font_weight=FontWeight.BOLD,
                        ),
                        key=f"sessions-{period}",
                    ),
                    Text(
                        content=change,
                        style=Style(
                            color=Color.from_hex("#16a34a"),
                            font_size=13.0,
                        ),
                        key=f"change-{period}",
                    ),
                ],
            )
        )
        rows.append(Divider(key=f"div-{period}"))

    return Column(
        key="analytics-body",
        style=Style(gap=16.0, padding=Edge.all(20.0), background=BACKGROUND),
        children=[
            Text(
                content="Traffic by Period",
                style=Style(
                    font_size=16.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                ),
                key="analytics-heading",
            ),
            Card(key="analytics-card", children=rows),
        ],
    )
```

!!! tip "Tip — `Style(grow=1.0)`"
    `grow=1.0` on the period `Text` makes that cell absorb all available space in the
    row, pushing the sessions and change values to the right — equivalent to
    `flex: 1` in CSS.

---

## Step 4 — Users section: table with avatars and role badges

```python
def _users_body() -> Widget:
    """Render the Users section with a sample user table.

    Returns:
        A :class:`Column` showing a list of sample users.
    """
    users: list[tuple[str, str, str]] = [
        ("Alice Martin", "alice@example.com", "Admin"),
        ("Bob Chen", "bob@example.com", "Editor"),
        ("Clara Neves", "clara@example.com", "Viewer"),
        ("David Park", "david@example.com", "Editor"),
        ("Eva Rossi", "eva@example.com", "Viewer"),
    ]

    header = Row(
        key="users-header",
        style=Style(
            gap=8.0,
            padding=Edge.symmetric(vertical=10.0, horizontal=12.0),
            background=MUTED,
        ),
        children=[
            Text(
                content="Name",
                style=Style(
                    grow=2.0,
                    font_size=13.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_MUTED,
                ),
                key="h-name",
            ),
            Text(
                content="Email",
                style=Style(
                    grow=3.0,
                    font_size=13.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_MUTED,
                ),
                key="h-email",
            ),
            Text(
                content="Role",
                style=Style(
                    grow=1.0,
                    font_size=13.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_MUTED,
                ),
                key="h-role",
            ),
        ],
    )

    user_rows: list[Widget] = [header]
    for name, email, role in users:
        user_rows.append(
            Row(
                key=f"user-{name}",
                style=Style(
                    gap=8.0,
                    align=AlignItems.CENTER,
                    padding=Edge.symmetric(vertical=10.0, horizontal=12.0),
                ),
                children=[
                    Text(
                        content=name,
                        style=Style(grow=2.0, font_size=14.0, color=ON_SURFACE),
                        key=f"name-{name}",
                    ),
                    Text(
                        content=email,
                        style=Style(grow=3.0, font_size=14.0, color=ON_MUTED),
                        key=f"email-{name}",
                    ),
                    Badge(label=role, tone="info", key=f"role-{name}"),
                ],
            )
        )
        user_rows.append(Divider(key=f"udiv-{name}"))

    return Column(
        key="users-body",
        style=Style(gap=16.0, padding=Edge.all(20.0), background=BACKGROUND),
        children=[
            Text(
                content="Team Members",
                style=Style(
                    font_size=16.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                ),
                key="users-heading",
            ),
            Card(key="users-card", children=user_rows),
        ],
    )
```

!!! info "Info — column proportions with `grow`"
    The header and each user row use `grow=2.0` for the name, `grow=3.0` for the
    email and `grow=1.0` for the role. This keeps columns visually aligned across all
    rows without any fixed widths.

---

## Step 5 — Settings section: interactive sidebar toggle

The Settings section demonstrates something special: it changes the **layout structure**
itself by opening or closing the sidebar — using the same `set_state` that swaps tabs.

```python
def _settings_body(app: App[DashState]) -> Widget:
    """Render the Settings section.

    Includes a sidebar-toggle control so the layout itself is interactive.

    Args:
        app: The application handle.

    Returns:
        A :class:`Column` with the settings controls.
    """

    def toggle_sidebar() -> None:
        """Toggle the sidebar open/closed."""
        app.set_state(lambda s: setattr(s, "sidebar_open", not s.sidebar_open))

    sidebar_label = "Hide Sidebar" if app.state.sidebar_open else "Show Sidebar"

    return Column(
        key="settings-body",
        style=Style(gap=20.0, padding=Edge.all(20.0), background=BACKGROUND),
        children=[
            Text(
                content="App Settings",
                style=Style(
                    font_size=16.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                ),
                key="settings-heading",
            ),
            Card(
                key="settings-card",
                children=[
                    Text(
                        content="Layout",
                        style=Style(
                            font_size=14.0,
                            font_weight=FontWeight.BOLD,
                            color=ON_SURFACE,
                        ),
                        key="layout-label",
                    ),
                    Divider(key="settings-div"),
                    Row(
                        key="sidebar-toggle-row",
                        style=Style(
                            gap=12.0,
                            align=AlignItems.CENTER,
                            padding=Edge.symmetric(vertical=8.0, horizontal=0.0),
                        ),
                        children=[
                            Text(
                                content="Sidebar",
                                style=Style(grow=1.0, color=ON_SURFACE, font_size=14.0),
                                key="sidebar-label-text",
                            ),
                            Button(
                                label=sidebar_label,
                                on_click=toggle_sidebar,
                                key="sidebar-toggle-btn",
                                style=Style(
                                    padding=Edge.symmetric(
                                        vertical=8.0, horizontal=16.0
                                    ),
                                    radius=8.0,
                                    background=ACCENT,
                                    color=ON_SURFACE,
                                    font_size=14.0,
                                ),
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
```

!!! tip "Tip — dynamic label"
    `sidebar_label` is computed *before* building the widget tree: `"Hide Sidebar"` if
    the sidebar is open, `"Show Sidebar"` if it is closed. The button always shows the
    correct text for the current state without any conditional logic inside the widget.

---

## Step 6 — Sidebar navigation

The sidebar has its own list of navigation buttons, synchronised with `active_tab`.
The active button receives a visual highlight via `background=ACCENT`.

```python
def _sidebar_nav(app: App[DashState]) -> Widget:
    """Build the sidebar navigation links.

    Each link button changes the active tab; the active one is highlighted.

    Args:
        app: The application handle.

    Returns:
        A :class:`Column` of navigation buttons plus a user footer.
    """

    def make_nav_handler(index: int) -> Callable[[], None]:
        """Create a tab-selection handler for *index*.

        Args:
            index: The tab index to activate.

        Returns:
            A zero-argument callable that sets the active tab.
        """

        def handler() -> None:
            app.set_state(lambda s: setattr(s, "active_tab", index))

        return handler

    nav_buttons: list[Widget] = []
    for idx, label in enumerate(_NAV_LABELS):
        active = idx == app.state.active_tab
        nav_buttons.append(
            Button(
                label=label,
                on_click=make_nav_handler(idx),
                key=f"sidenav-{idx}",
                style=Style(
                    padding=Edge.symmetric(vertical=10.0, horizontal=12.0),
                    radius=8.0,
                    background=ACCENT if active else Color.from_hex("#00000000"),
                    color=ON_SURFACE if active else ON_MUTED,
                    font_size=14.0,
                    font_weight=FontWeight.BOLD if active else FontWeight.NORMAL,
                ),
            )
        )

    return Column(
        key="sidebar-nav-col",
        style=Style(gap=4.0, background=SURFACE),
        children=[
            Container(
                key="brand",
                style=Style(
                    padding=Edge.symmetric(vertical=16.0, horizontal=12.0),
                ),
                child=Text(
                    content="◈ Dashboard",
                    style=Style(
                        font_size=18.0,
                        font_weight=FontWeight.BOLD,
                        color=ON_SURFACE,
                    ),
                    key="brand-text",
                ),
            ),
            Divider(key="brand-div"),
            *nav_buttons,
            Container(
                key="sidebar-spacer",
                style=Style(grow=1.0),
            ),
            Divider(key="user-div"),
            Row(
                key="user-row",
                style=Style(
                    gap=10.0,
                    align=AlignItems.CENTER,
                    padding=Edge.all(12.0),
                ),
                children=[
                    Avatar(initials="MB", size=36.0, key="user-avatar"),
                    Column(
                        key="user-info",
                        style=Style(gap=2.0),
                        children=[
                            Text(
                                content="Mauricio B.",
                                style=Style(
                                    font_size=13.0,
                                    font_weight=FontWeight.BOLD,
                                    color=ON_SURFACE,
                                ),
                                key="user-name",
                            ),
                            Text(
                                content="Admin",
                                style=Style(font_size=11.0, color=ON_MUTED),
                                key="user-role",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
```

!!! info "Info — `Container` as a spacer"
    `Container(style=Style(grow=1.0))` with no children pushes the user footer to the
    bottom of the sidebar — equivalent to `margin-top: auto` in CSS flexbox.

**Sidebar highlights:**

- `make_nav_handler(index)` uses the factory pattern to correctly capture the index
  on each loop iteration.
- `Color.from_hex("#00000000")` is fully transparent — inactive buttons show no
  background.
- The footer displays `Avatar` + name + user role.

---

## Step 7 — The `view` function: assembling everything

With all pieces ready, `view` assembles the complete layout.

```python
def _body_for_tab(tab: int, app: App[DashState]) -> Widget:
    """Return the body widget matching the active tab index.

    Args:
        tab: The currently selected tab index.
        app: The application handle passed to tab bodies that need state.

    Returns:
        The section body widget for ``tab``.
    """
    if tab == 0:
        return _overview_body(app)
    if tab == 1:
        return _analytics_body()
    if tab == 2:
        return _users_body()
    return _settings_body(app)


def view(app: App[DashState]) -> Widget:
    """Render the full dashboard shell from the current state.

    The layout is: AppBar on top, then a ``Row`` containing an optional
    ``Sidebar`` on the left and the active section body filling the rest.
    A ``NavBar`` at the bottom mirrors the sidebar for compact viewports.
    Selecting a nav item in either bar updates ``active_tab`` via
    ``app.set_state``, which triggers a re-render swapping the body.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def on_nav_select(index: int) -> None:
        """Handle bottom NavBar item selection.

        Args:
            index: The selected item index.
        """
        app.set_state(lambda s: setattr(s, "active_tab", index))

    appbar = AppBar(
        key="main-appbar",
        title=f"Dashboard — {_NAV_LABELS[app.state.active_tab]}",
        leading=Button(
            label="☰",
            on_click=lambda: app.set_state(
                lambda s: setattr(s, "sidebar_open", not s.sidebar_open)
            ),
            key="menu-btn",
            style=Style(
                padding=Edge.all(8.0),
                radius=6.0,
                background=MUTED,
                color=ON_SURFACE,
                font_size=16.0,
            ),
        ),
        actions=[
            Avatar(initials="MB", size=32.0, key="appbar-avatar"),
        ],
    )

    sidebar = Sidebar(
        key="main-sidebar",
        width=220.0,
        children=[_sidebar_nav(app)],
    )

    section_body = _body_for_tab(app.state.active_tab, app)

    main_row_children: list[Widget] = []
    if app.state.sidebar_open:
        main_row_children.append(sidebar)
    main_row_children.append(
        Container(
            key="content-area",
            style=Style(grow=1.0, background=BACKGROUND),
            child=section_body,
        )
    )

    main_row = Row(
        key="main-row",
        style=Style(grow=1.0, align=AlignItems.START),
        children=main_row_children,
    )

    bottom_nav = NavBar(
        key="bottom-nav",
        items=_NAV_LABELS,
        active=app.state.active_tab,
        on_select=on_nav_select,
    )

    return Scaffold(
        key="dashboard-scaffold",
        app_bar=appbar,
        body=main_row,
        bottom_bar=bottom_nav,
    )
```

**What is happening in `view`:**

| Piece | Responsibility |
|---|---|
| `AppBar(title=..., leading=..., actions=[...])` | Top bar with dynamic title, menu button and avatar |
| `Sidebar(width=220.0, children=[...])` | 220 px side panel with navigation |
| `if app.state.sidebar_open` | Includes or omits the sidebar in the `Row` children list |
| `Container(style=Style(grow=1.0))` | Content area that expands to fill the remaining space |
| `NavBar(items=..., active=..., on_select=...)` | Bottom bar that mirrors sidebar navigation |
| `Scaffold(app_bar=..., body=..., bottom_bar=...)` | Root structure that positions AppBar, body and bottom bar |

!!! warning "Warning — sidebar ↔ NavBar synchronisation"
    Both the `Sidebar` and the `NavBar` call
    `set_state(lambda s: setattr(s, "active_tab", index))`. Because state is the
    single source of truth, both are automatically kept in sync. Never duplicate the
    active index — one `int` governs the entire layout.

---

## Step 8 — Run the app

Run in **Mode A** (Python in the browser via Pyodide/WASM):

```bash
tempestweb dev --mode wasm examples/dashboard-shell/app.py
```

Run in **Mode B** (Python on the server via FastAPI + WebSocket):

```bash
tempestweb dev --mode server examples/dashboard-shell/app.py
```

Open `http://localhost:8000` in your browser. You should see:

- ✅ `AppBar` with the title "Dashboard — Overview" and a "☰" button on the left;
- ✅ 220 px `Sidebar` with four navigation links and a user footer;
- ✅ 2×2 grid of KPI cards (Revenue, Sessions, Signups, Errors);
- ✅ Three dismissible alerts — clicking "✕" removes each one individually;
- ✅ Clicking "Analytics" in the sidebar or the bottom bar swaps the body;
- ✅ The Settings section lets you hide/show the sidebar in real time;
- ✅ The `AppBar` title updates to reflect the active section.

---

## Recap

In this tutorial you built a complete dashboard shell and learned:

- 💡 **`Scaffold`** is the root widget that organises `app_bar`, `body` and
  `bottom_bar` into the standard screen layout.
- 💡 **`Sidebar` + `NavBar`** are two entry points for the same navigation — both
  write to `active_tab` and stay synchronised automatically.
- 💡 **`Grid(columns=2)`** distributes KPIs into two balanced columns.
- 💡 **`Banner(tone=..., action=...)`** builds dismissible alerts with an embedded
  action widget — just pass a `Button` as `action`.
- 💡 **`Badge(tone=...)`** is the simplest visual block for status or role
  indicators.
- 💡 **Sidebar visibility** is just a `bool` in state — including or omitting the
  widget from the `Row` children list is all it takes to show or hide it.
- 💡 The same `app.py` runs unchanged in both modes — WASM and Server.

---

## Next steps

- Read the [core tutorial](../tutorial/index.md) to understand the full tempestweb
  lifecycle.
- Explore tab-based navigation in the [Tabbed Profile](tabs-profile.md) example.
- See how to build filterable, paginated data tables in the
  [Data Table](data-table.md) example.
