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

from tempestweb._core.components.base import (
    ACCENT,
    BACKGROUND,
    MUTED,
    ON_MUTED,
    ON_SURFACE,
    SURFACE,
)
from tempestweb._core.style import AlignItems, Color, Edge, FontWeight

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


# ---------------------------------------------------------------------------
# Public contract
# ---------------------------------------------------------------------------


def make_state() -> DashState:
    """Build the initial dashboard state.

    Returns:
        A fresh :class:`DashState` landing on the Overview tab.
    """
    return DashState()


# ---------------------------------------------------------------------------
# Per-section body builders
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Section dispatcher
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Sidebar nav items
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Root view
# ---------------------------------------------------------------------------


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
