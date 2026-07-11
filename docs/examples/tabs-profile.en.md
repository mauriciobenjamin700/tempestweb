# Tabbed Profile

> 🚀 **What you'll build:** a profile screen with three sections — *Overview*, *Activity* and *Settings* — navigable via tabs, with Switch toggles that update preferences in real time.

---

## Why this example matters

Every real application needs to organise content into sections without overwhelming the user.
`TabView` solves exactly that: it presents a set of labels at the top and swaps the screen
body as the selected tab changes.

In this tutorial you will learn how to:

- Use `TabView` for section navigation;
- Respond to `RouteChangeEvent` to update the tab index in state;
- Use `Switch` with `ToggleEvent` for boolean controls (notifications, dark mode);
- Compose rich layouts with `Card`, `Avatar`, `ListTile` and `Divider`.

!!! note "Note"
    This example runs **without any modification** in both modes — WASM (Pyodide in the
    browser) and Server (FastAPI + WebSocket). The same Python `view()` serves both.

---

## Prerequisites

Install tempestweb and confirm the CLI is available:

```bash
pip install tempestweb
tempestweb --version
```

---

## Project structure

```
examples/
└── tabs-profile/
    └── app.py
```

Create the folder and file:

```bash
mkdir -p examples/tabs-profile
touch examples/tabs-profile/app.py
```

---

## Step 1 — Define the state

The state holds which tab is active and the two boolean preferences (notifications and
dark mode). A second dataclass models each entry in the activity list.

```python
from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Style, Widget
from tempest_core.components import (
    AppBar,
    Avatar,
    Card,
    Divider,
    ListTile,
    Scaffold,
)
from tempest_core.style import AlignItems, Edge, FontWeight
from tempest_core.widgets import (
    Column,
    Row,
    Switch,
    TabView,
    Text,
)
from tempest_core.widgets.events import RouteChangeEvent, ToggleEvent

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
```

!!! tip "Tip"
    `_TABS` is a simple list of strings. `TabView` uses these labels to render the tab
    buttons — no extra configuration needed.

**What just happened:**

- `_TABS` defines the three labels that `TabView` will display.
- `ProfileState.active_tab` is the single source of truth about which tab is visible.
- `make_state()` provides initial activity data so the *Activity* tab is already
  populated on the very first render.

---

## Step 2 — Build the Overview section

The first tab shows an avatar, a bio, and a stats card.

```python
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
```

!!! info "Info"
    The `Divider` inside the stats card is a simple horizontal visual separator —
    no required parameters beyond `key`.

**Highlights:**

- `Avatar(initials="AJ", size=72.0)` — the pre-built component renders a circle
  with the initials; no image URL handling needed.
- `Edge.all(16.0)` — applies uniform 16 px padding on all sides.
- `AlignItems.CENTER` — vertically aligns the avatar and the name block.
- The preferences summary at the bottom (`prefs-summary`) already reflects the Settings
  state even when you are on a different tab — because everything shares the same
  `ProfileState`.

---

## Step 3 — Build the Activity section

The second tab iterates over the activity entries and creates a `ListTile` for each,
separated by `Divider` widgets.

```python
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
```

!!! tip "Tip"
    Every widget needs a unique `key` within the same parent. Here we use
    `f"activity-{i}"` and `f"div-{i}"` to guarantee that in dynamic lists.
    The reconciler uses these keys to apply minimal patches to the DOM.

**Highlights:**

- `ListTile` accepts `leading` (a widget on the left), `title` and `subtitle`.
- The `if i < len(state.activity) - 1` guard avoids a trailing `Divider` after the last item.

---

## Step 4 — Build the Settings section with Switch

The third tab uses `Switch` for boolean controls. Each `Switch` receives a `ToggleEvent`
handler.

```python
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
```

!!! info "Info"
    `ListTile` also accepts `trailing` — a widget placed on the right. Using a `Switch`
    in that position is a classic settings-screen pattern.

---

## Step 5 — The `view` function and event handlers

This is where everything connects. The `view` function defines event handlers as inner
functions and decides which section to render based on `state.active_tab`.

```python
def view(app: App[ProfileState]) -> Widget:
    """Render the tabbed-profile UI from the current state.

    The active section is determined by ``app.state.active_tab``.  Tapping a
    tab fires a :class:`~tempest_core.widgets.events.RouteChangeEvent`;
    the handler reads ``event.params["index"]`` and writes it back via
    :meth:`~tempest_core.core.state.App.set_state`.

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
```

**What is happening:**

| Part | Responsibility |
|---|---|
| `on_tab_change` | Reads `event.params["index"]` and writes it to `active_tab` via `set_state` |
| `on_notifications_toggle` | Reads `event.checked` and flips `notifications_on` |
| `on_dark_toggle` | Reads `event.checked` and flips `dark_mode` |
| `if tab == 0 / 1 / else` | Selects which section builder to call |
| `TabView(active=..., child=body)` | Receives the active index and the already-built widget |

!!! warning "Warning"
    `TabView` does **not** manage state internally — it only renders the correct label
    as active and fires `on_change`. It is your `view`'s responsibility to persist the
    index in state and pass the correct `child`.

---

## Step 6 — Run the app

Run in **Mode A** (Python in the browser via Pyodide):

```bash
tempestweb dev --mode wasm examples/tabs-profile/app.py
```

Run in **Mode B** (Python on the server via FastAPI + WebSocket):

```bash
tempestweb dev --mode server examples/tabs-profile/app.py
```

Open `http://localhost:8000` in your browser. You should see:

- ✅ AppBar with the title "Profile";
- ✅ Three tabs: Overview, Activity, Settings;
- ✅ Clicking each tab swaps the content without reloading the page;
- ✅ In the Settings tab, both `Switch` controls respond to clicks and the summary in
  Overview reflects the new state.

---

## Recap

In this tutorial you built a complete profile screen with three sections and learned:

- 💡 **`TabView`** takes `tabs` (labels), `active` (index) and `on_change` (handler).
  You pass the already-built `child` — `TabView` does not decide which section to render.
- 💡 **`RouteChangeEvent`** carries the new index in `event.params["index"]`. Use
  `int(event.params.get("index", 0))` to convert it safely.
- 💡 **`ToggleEvent`** carries the new boolean in `event.checked` — ideal for `Switch`
  controls in settings screens.
- 💡 **`Card` + `ListTile` + `Avatar` + `Divider`** form a set of pre-built components
  for rich list layouts without any manual CSS.
- 💡 The same `app.py` runs in both modes — WASM and Server — without any modification.

---

## Next steps

- Read the [central tutorial](../tutorial/index.md) to understand the full tempestweb
  lifecycle.
- Add screen-to-screen navigation with the `router-push` example (coming soon).
- Explore tab transition animations with `AnimatedSwitcher`.
