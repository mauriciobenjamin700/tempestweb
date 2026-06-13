"""Tabbed profile — demonstrates Layout & navigation with TabView.

Three profile sections — Overview, Activity, Settings — are surfaced via a
:class:`~tempestweb._core.widgets.TabView`.  Switching tabs fires a
:class:`~tempestweb._core.widgets.events.RouteChangeEvent`; the index stored
in ``params["index"]`` is written back to state so the reconciler can diff
the active ``child`` to the correct section.

Each section is composed from :class:`~tempestweb._core.components.cards.Card`,
:class:`~tempestweb._core.components.cards.Avatar`,
:class:`~tempestweb._core.components.cards.ListTile`, and
:class:`~tempestweb._core.components.cards.Divider` to produce a rich,
non-trivial layout.  The Settings section lets the user toggle notifications
and toggle dark-mode preference, exercising
:class:`~tempestweb._core.widgets.inputs.Switch` and
:class:`~tempestweb._core.widgets.events.ToggleEvent`.

Run unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempestweb._core import App, Style, Widget
from tempestweb._core.components import (
    AppBar,
    Avatar,
    Card,
    Divider,
    ListTile,
    Scaffold,
)
from tempestweb._core.style import AlignItems, Edge, FontWeight
from tempestweb._core.widgets import (
    Column,
    Row,
    Switch,
    TabView,
    Text,
)
from tempestweb._core.widgets.events import RouteChangeEvent, ToggleEvent

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_TABS: list[str] = ["Overview", "Activity", "Settings"]


@dataclass
class ActivityEntry:
    """A single item in the user's recent-activity feed.

    Attributes:
        title: Short description of the activity.
        subtitle: Timestamp or context string.
    """

    title: str
    subtitle: str


@dataclass
class ProfileState:
    """All mutable state for the tabbed-profile screen.

    Attributes:
        active_tab: Index of the currently visible tab (0 = Overview, etc.).
        notifications_on: Whether push notifications are enabled.
        dark_mode: Whether the user has chosen dark-mode.
        activity: Ordered list of recent activity entries.
    """

    active_tab: int = 0
    notifications_on: bool = True
    dark_mode: bool = True
    activity: list[ActivityEntry] = field(default_factory=list)


def make_state() -> ProfileState:
    """Build the initial profile state with seed activity entries.

    Returns:
        A fresh :class:`ProfileState` ready for the first render.
    """
    return ProfileState(
        activity=[
            ActivityEntry("Joined the platform", "2 years ago"),
            ActivityEntry("Completed onboarding", "2 years ago"),
            ActivityEntry("Published first project", "18 months ago"),
            ActivityEntry("Reached 100 followers", "1 year ago"),
            ActivityEntry("Earned contributor badge", "6 months ago"),
        ]
    )


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _overview_section(state: ProfileState) -> Widget:
    """Render the Overview tab: avatar, bio card, and stats row.

    Args:
        state: The current application state.

    Returns:
        A ``Column`` composing the overview content.
    """
    notifications_label = "on" if state.notifications_on else "off"
    dark_label = "dark" if state.dark_mode else "light"
    return Column(
        key="overview",
        style=Style(gap=16.0, padding=Edge.all(16.0)),
        children=[
            Row(
                key="profile-header",
                style=Style(gap=16.0, align=AlignItems.CENTER),
                children=[
                    Avatar(initials="AJ", size=72.0, key="avatar-lg"),
                    Column(
                        key="name-block",
                        style=Style(gap=4.0),
                        children=[
                            Text(
                                content="Alex Johnson",
                                key="full-name",
                                style=Style(
                                    font_size=22.0,
                                    font_weight=FontWeight.BOLD,
                                ),
                            ),
                            Text(
                                content="@alexj · Senior Engineer",
                                key="handle",
                                style=Style(font_size=14.0),
                            ),
                        ],
                    ),
                ],
            ),
            Card(
                key="bio-card",
                children=[
                    Text(
                        content="Bio",
                        key="bio-heading",
                        style=Style(
                            font_size=16.0,
                            font_weight=FontWeight.BOLD,
                        ),
                    ),
                    Text(
                        content=(
                            "Building developer tools and open-source libraries. "
                            "Passionate about clean architecture and great UX."
                        ),
                        key="bio-body",
                        style=Style(font_size=14.0),
                    ),
                ],
            ),
            Card(
                key="stats-card",
                children=[
                    Text(
                        content="Quick stats",
                        key="stats-heading",
                        style=Style(
                            font_size=16.0,
                            font_weight=FontWeight.BOLD,
                        ),
                    ),
                    Divider(key="stats-divider"),
                    Row(
                        key="stats-row",
                        style=Style(gap=24.0),
                        children=[
                            Column(
                                key="stat-projects",
                                style=Style(gap=2.0, align=AlignItems.CENTER),
                                children=[
                                    Text(
                                        content="34",
                                        key="stat-projects-val",
                                        style=Style(
                                            font_size=20.0,
                                            font_weight=FontWeight.BOLD,
                                        ),
                                    ),
                                    Text(
                                        content="Projects",
                                        key="stat-projects-lbl",
                                        style=Style(font_size=12.0),
                                    ),
                                ],
                            ),
                            Column(
                                key="stat-followers",
                                style=Style(gap=2.0, align=AlignItems.CENTER),
                                children=[
                                    Text(
                                        content="1.2k",
                                        key="stat-followers-val",
                                        style=Style(
                                            font_size=20.0,
                                            font_weight=FontWeight.BOLD,
                                        ),
                                    ),
                                    Text(
                                        content="Followers",
                                        key="stat-followers-lbl",
                                        style=Style(font_size=12.0),
                                    ),
                                ],
                            ),
                            Column(
                                key="stat-stars",
                                style=Style(gap=2.0, align=AlignItems.CENTER),
                                children=[
                                    Text(
                                        content="892",
                                        key="stat-stars-val",
                                        style=Style(
                                            font_size=20.0,
                                            font_weight=FontWeight.BOLD,
                                        ),
                                    ),
                                    Text(
                                        content="Stars",
                                        key="stat-stars-lbl",
                                        style=Style(font_size=12.0),
                                    ),
                                ],
                            ),
                        ],
                    ),
                    Text(
                        content=(
                            f"Notifications: {notifications_label}"
                            f"  |  Theme: {dark_label}"
                        ),
                        key="prefs-summary",
                        style=Style(font_size=12.0),
                    ),
                ],
            ),
        ],
    )


def _activity_section(state: ProfileState) -> Widget:
    """Render the Activity tab: a card list of recent events.

    Args:
        state: The current application state.

    Returns:
        A ``Column`` of activity list tiles inside a ``Card``.
    """
    tiles: list[Widget] = []
    for i, entry in enumerate(state.activity):
        tiles.append(
            ListTile(
                key=f"activity-{i}",
                leading=Avatar(initials=entry.title[0], size=36.0, key=f"av-{i}"),
                title=entry.title,
                subtitle=entry.subtitle,
            )
        )
        if i < len(state.activity) - 1:
            tiles.append(Divider(key=f"div-{i}"))
    return Column(
        key="activity",
        style=Style(gap=16.0, padding=Edge.all(16.0)),
        children=[
            Text(
                content="Recent activity",
                key="activity-heading",
                style=Style(font_size=18.0, font_weight=FontWeight.BOLD),
            ),
            Card(key="activity-card", children=tiles),
        ],
    )


def _settings_section(
    state: ProfileState,
    on_notifications: RouteChangeEvent | None,
    toggle_notifications: ToggleEvent | None,
    toggle_dark: ToggleEvent | None,
    on_notifications_switch: object,
    on_dark_switch: object,
) -> Widget:
    """Render the Settings tab: notification and theme toggles inside cards.

    Args:
        state: The current application state.
        on_notifications: Unused placeholder kept for API symmetry.
        toggle_notifications: Unused placeholder kept for API symmetry.
        toggle_dark: Unused placeholder kept for API symmetry.
        on_notifications_switch: Zero-argument-accepting handler for the
            notifications ``Switch``.
        on_dark_switch: Zero-argument-accepting handler for the dark-mode
            ``Switch``.

    Returns:
        A ``Column`` of settings cards.
    """
    return Column(
        key="settings",
        style=Style(gap=16.0, padding=Edge.all(16.0)),
        children=[
            Text(
                content="Settings",
                key="settings-heading",
                style=Style(font_size=18.0, font_weight=FontWeight.BOLD),
            ),
            Card(
                key="notif-card",
                children=[
                    ListTile(
                        key="notif-tile",
                        title="Push notifications",
                        subtitle="Receive alerts for mentions and replies",
                        trailing=Switch(
                            checked=state.notifications_on,
                            on_change=on_notifications_switch,  # type: ignore[arg-type]
                            key="notif-switch",
                        ),
                    ),
                ],
            ),
            Card(
                key="theme-card",
                children=[
                    ListTile(
                        key="theme-tile",
                        title="Dark mode",
                        subtitle="Use a dark colour palette",
                        trailing=Switch(
                            checked=state.dark_mode,
                            on_change=on_dark_switch,  # type: ignore[arg-type]
                            key="theme-switch",
                        ),
                    ),
                ],
            ),
            Card(
                key="account-card",
                children=[
                    Text(
                        content="Account",
                        key="account-heading",
                        style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
                    ),
                    Divider(key="account-divider"),
                    ListTile(
                        key="email-tile",
                        leading=Avatar(initials="@", size=32.0, key="email-av"),
                        title="alex@example.com",
                        subtitle="Primary email address",
                    ),
                    ListTile(
                        key="joined-tile",
                        leading=Avatar(initials="J", size=32.0, key="joined-av"),
                        title="Joined",
                        subtitle="March 2022",
                    ),
                ],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# view
# ---------------------------------------------------------------------------


def view(app: App[ProfileState]) -> Widget:
    """Render the tabbed-profile UI from the current state.

    The active section is determined by ``app.state.active_tab``.  Tapping a
    tab fires a :class:`~tempestweb._core.widgets.events.RouteChangeEvent`;
    the handler reads ``event.params["index"]`` and writes it back via
    :meth:`~tempestweb._core.core.state.App.set_state`.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The full widget tree for the current state.
    """
    state: ProfileState = app.state

    # --- Tab-change handler -------------------------------------------------
    def on_tab_change(event: RouteChangeEvent) -> None:
        """Switch the active tab when the user taps a tab label.

        Args:
            event: The route-change event carrying the new tab index in
                ``params["index"]``.
        """
        index: int = int(event.params.get("index", 0))
        app.set_state(lambda s: setattr(s, "active_tab", index))

    # --- Toggle handlers (Settings tab) -------------------------------------
    def on_notifications_toggle(event: ToggleEvent) -> None:
        """Toggle push-notification preference.

        Args:
            event: The toggle event carrying the new ``checked`` state.
        """
        app.set_state(lambda s: setattr(s, "notifications_on", event.checked))

    def on_dark_toggle(event: ToggleEvent) -> None:
        """Toggle dark-mode preference.

        Args:
            event: The toggle event carrying the new ``checked`` state.
        """
        app.set_state(lambda s: setattr(s, "dark_mode", event.checked))

    # --- Build the active section -------------------------------------------
    tab: int = state.active_tab
    if tab == 0:
        body: Widget = _overview_section(state)
    elif tab == 1:
        body = _activity_section(state)
    else:
        body = _settings_section(
            state,
            on_notifications=None,
            toggle_notifications=None,
            toggle_dark=None,
            on_notifications_switch=on_notifications_toggle,
            on_dark_switch=on_dark_toggle,
        )

    return Scaffold(
        key="profile-scaffold",
        app_bar=AppBar(title="Profile", key="profile-appbar"),
        body=TabView(
            key="profile-tabs",
            tabs=_TABS,
            active=state.active_tab,
            on_change=on_tab_change,
            child=body,
        ),
    )
