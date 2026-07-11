# Core app shell — layout and navigation 🚀

In this example you'll build the **classic application skeleton**: a top bar
(`AppBar`), a side navigation (`Sidebar` + `NavBar` + `ListTile`) and a content
region (`Card`) that swaps based on the selected item. Everything is a `Scaffold`
driven by typed Python state.

---

## What you'll build

- 🧱 A **Scaffold** with an `AppBar` at the top.
- 🧭 A **Sidebar** with a `NavBar` (selection) and `ListTile` rows (rich descriptors).
- 🗂️ A content **Card** that swaps its heading/body as you navigate.

---

## Prerequisites

```bash
pip install tempestweb
```

!!! tip "Tip"
    If you're not yet familiar with the state → view → patches cycle, read the
    [introductory tutorial](../tutorial/index.md).

---

## Step 1 — The navigation destination

Each destination is an immutable `NavItem` carrying everything shown in the
sidebar **and** in the content region.

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class NavItem:
    """A single navigation destination in the app shell.

    Attributes:
        label: The short label shown in the navigation bar.
        subtitle: A one-line description rendered beside the label.
        heading: The page heading shown in the content region.
        body: The page body text shown in the content region.
    """

    label: str
    subtitle: str
    heading: str
    body: str


NAV_ITEMS: list[NavItem] = [
    NavItem(
        label="Home",
        subtitle="Overview and quick stats",
        heading="Welcome home",
        body="This is the home page of the app shell. Pick a destination "
        "on the left to swap the content region.",
    ),
    NavItem(
        label="Reports",
        subtitle="Charts and exports",
        heading="Reports",
        body="The reports page would render charts and downloadable exports. "
        "Here it is a placeholder driven entirely by state.",
    ),
    NavItem(
        label="Settings",
        subtitle="Preferences and account",
        heading="Settings",
        body="The settings page would expose preferences and account "
        "controls. The shell layout stays identical across pages.",
    ),
]
```

---

## Step 2 — The state

The state keeps only the index of the active destination.

```python
@dataclass
class ShellState:
    """State for the app-shell example.

    Attributes:
        selected: Index into :data:`NAV_ITEMS` of the active destination.
        items: The available navigation destinations.
    """

    selected: int = 0
    items: list[NavItem] = field(default_factory=lambda: list(NAV_ITEMS))


def make_state() -> ShellState:
    """Build the initial state.

    Returns:
        A fresh :class:`ShellState` with the first destination selected.
    """
    return ShellState()
```

---

## Step 3 — The sidebar

The `Sidebar` groups a `NavBar` (which owns the selection via `on_select`) and a
list of `ListTile` rows (richer descriptors). The active tile gets
`color_scheme="primary"`.

```python
from tempest_core import App, Text, Widget
from tempestweb.components import ListTile, NavBar, Sidebar

def _build_sidebar(app: App[ShellState]) -> Sidebar:
    """Build the side navigation for the shell."""
    state: ShellState = app.state

    def select(index: int) -> None:
        app.set_state(lambda s: setattr(s, "selected", index))

    tiles: list[Widget] = [
        ListTile(
            key=f"tile-{i}",
            title=item.label,
            subtitle=item.subtitle,
            color_scheme="primary" if i == state.selected else None,
        )
        for i, item in enumerate(state.items)
    ]

    return Sidebar(
        key="sidebar",
        width=260.0,
        children=[
            Text(content="Navigation", key="nav-title"),
            NavBar(
                key="navbar",
                items=[item.label for item in state.items],
                active=state.selected,
                on_select=select,
            ),
            *tiles,
        ],
    )
```

!!! info "Info — `NavBar.on_select` receives the index"
    `NavBar` calls `on_select(index)` with the index of the clicked item. We store
    that index in `state.selected` and derive everything else from it.

---

## Step 4 — The content region

The content `Card` simply reads the active `NavItem` and renders its heading and
body.

```python
from tempest_core import Text
from tempestweb.components import Card

def _build_content(app: App[ShellState]) -> Card:
    """Build the content region for the active destination."""
    state: ShellState = app.state
    active: NavItem = state.items[state.selected]

    return Card(
        key="content",
        children=[
            Text(content=active.heading, key="content-heading"),
            Text(content=active.body, key="content-body"),
        ],
    )
```

---

## Step 5 — The Scaffold

The `Scaffold` ties it all together: `app_bar` on top and `body` with the sidebar
+ content.

```python
from tempest_core import Column, Style
from tempest_core.style import Edge
from tempestweb.components import AppBar, Scaffold

return Scaffold(
    key="shell",
    app_bar=AppBar(title="Core App Shell", key="appbar"),
    body=Column(
        key="shell-body",
        style=Style(gap=16.0, padding=Edge.all(16)),
        children=[
            _build_sidebar(app),
            _build_content(app),
        ],
    ),
)
```

---

## The complete app

```python
"""Core App Shell — a layout/navigation scaffolding showcase.

This example demonstrates the core's structural components working together to
form a classic application shell: a top bar, a side navigation, and a content
region that swaps based on the selected navigation item.

Like every tempestweb example, this exact ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb run --mode server   # Python on the server (FastAPI + WebSocket)

The application never names a transport — that is the whole point.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Column, Style, Text, Widget
from tempest_core.style import Edge
from tempestweb.components import AppBar, Card, ListTile, NavBar, Scaffold, Sidebar


@dataclass(frozen=True)
class NavItem:
    """A single navigation destination in the app shell.

    Attributes:
        label: The short label shown in the navigation bar.
        subtitle: A one-line description rendered beside the label.
        heading: The page heading shown in the content region.
        body: The page body text shown in the content region.
    """

    label: str
    subtitle: str
    heading: str
    body: str


NAV_ITEMS: list[NavItem] = [
    NavItem(
        label="Home",
        subtitle="Overview and quick stats",
        heading="Welcome home",
        body="This is the home page of the app shell. Pick a destination "
        "on the left to swap the content region.",
    ),
    NavItem(
        label="Reports",
        subtitle="Charts and exports",
        heading="Reports",
        body="The reports page would render charts and downloadable exports. "
        "Here it is a placeholder driven entirely by state.",
    ),
    NavItem(
        label="Settings",
        subtitle="Preferences and account",
        heading="Settings",
        body="The settings page would expose preferences and account "
        "controls. The shell layout stays identical across pages.",
    ),
]


@dataclass
class ShellState:
    """State for the app-shell example.

    Attributes:
        selected: Index into :data:`NAV_ITEMS` of the active destination.
        items: The available navigation destinations.
    """

    selected: int = 0
    items: list[NavItem] = field(default_factory=lambda: list(NAV_ITEMS))


def make_state() -> ShellState:
    """Build the initial state.

    Returns:
        A fresh :class:`ShellState` with the first destination selected.
    """
    return ShellState()


def _build_sidebar(app: App[ShellState]) -> Sidebar:
    """Build the side navigation for the shell.

    The :class:`NavBar` owns selection (via ``on_select``) while the
    :class:`ListTile` rows give each destination a richer descriptor.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The configured :class:`Sidebar` widget.
    """
    state: ShellState = app.state

    def select(index: int) -> None:
        app.set_state(lambda s: setattr(s, "selected", index))

    tiles: list[Widget] = [
        ListTile(
            key=f"tile-{i}",
            title=item.label,
            subtitle=item.subtitle,
            color_scheme="primary" if i == state.selected else None,
        )
        for i, item in enumerate(state.items)
    ]

    return Sidebar(
        key="sidebar",
        width=260.0,
        children=[
            Text(content="Navigation", key="nav-title"),
            NavBar(
                key="navbar",
                items=[item.label for item in state.items],
                active=state.selected,
                on_select=select,
            ),
            *tiles,
        ],
    )


def _build_content(app: App[ShellState]) -> Card:
    """Build the content region for the active destination.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A :class:`Card` rendering the selected page's heading and body.
    """
    state: ShellState = app.state
    active: NavItem = state.items[state.selected]

    return Card(
        key="content",
        children=[
            Text(content=active.heading, key="content-heading"),
            Text(content=active.body, key="content-body"),
        ],
    )


def view(app: App[ShellState]) -> Widget:
    """Render the app shell from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """
    return Scaffold(
        key="shell",
        app_bar=AppBar(title="Core App Shell", key="appbar"),
        body=Column(
            key="shell-body",
            style=Style(gap=16.0, padding=Edge.all(16)),
            children=[
                _build_sidebar(app),
                _build_content(app),
            ],
        ),
    )
```

---

## Running the example ▶

=== "Mode A — WASM (Python in the browser)"

    ```bash
    tempestweb dev --mode wasm --path examples/core-app-shell
    ```

=== "Mode B — Server (FastAPI + WebSocket)"

    ```bash
    tempestweb run --mode server --path examples/core-app-shell
    ```

!!! check "Verification"
    You should see the "Core App Shell" top bar, a sidebar with Home / Reports /
    Settings, and a content card. Click **Reports** → the tile highlights and the
    card swaps its heading and body. ✅

---

## Recap

- ✅ Build an app shell with `Scaffold` (`app_bar` + `body`).
- ✅ Compose navigation with `Sidebar` + `NavBar` (`on_select`) + `ListTile`.
- ✅ Swap content by deriving the active `NavItem` from a single index in state.
- ✅ Highlight the active item with `color_scheme="primary"`.
- ✅ Run the same `app.py` in both modes without changing a line.

!!! tip "Next steps"
    - See the [Dashboard app shell](dashboard-shell.md) for a fuller layout.
    - Combine with [Drawer navigation & routing](router-drawer.md) for real routes.
