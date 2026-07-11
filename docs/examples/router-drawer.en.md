# Drawer Navigation & Routing 🗂️

> Build a documentation-style site with a slide-over side panel, 2-level route
> push/pop via `app.push` / `app.pop` / `app.reset`, and a tappable Breadcrumb
> trail.

---

## What we'll build

In this tutorial you'll create a fully navigable mini-documentation site in
plain Python.  It will have:

- A **`RouteDrawer`** — the side panel that slides over the main content.
- A **route stack** using `app.push`, `app.pop`, and `app.reset` to navigate
  between sections and articles.
- A **tappable `Breadcrumb`** that shows where the user is and lets them jump
  back to any point in the trail.
- A **dynamic `AppBar`** that swaps the hamburger icon for a "←" back arrow
  whenever there are pages to pop.

!!! note "Prerequisites"
    - Read [Getting Started](../tutorial/index.md) first to understand the
      `make_state → view → rebuild` cycle.
    - If you want to understand how patches reach the DOM, read
      [How Patches Work](../tutorial/patches.md).

---

## 1. Install and create files

```bash
pip install tempestweb
mkdir -p examples/router-drawer
touch examples/router-drawer/app.py
```

---

## 2. The content catalogue

Navigation needs data.  We declare three static dictionaries describing the
sections, the articles inside each section, and the body text for every page.

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from tempest_core import App, NavStack, Route, Style, Widget, build
from tempest_core.components import (
    AppBar,
    Breadcrumb,
    Card,
    Divider,
    ListTile,
    Scaffold,
)
from tempest_core.components.base import (
    ACCENT,
    BACKGROUND,
    MUTED,
    ON_MUTED,
    ON_SURFACE,
    SURFACE,
)
from tempest_core.style import AlignItems, Color, Edge, FontWeight
from tempest_core.widgets import (
    Button,
    Column,
    Container,
    RouteDrawer,
    Row,
    Text,
)

# Top-level sections available in the drawer
_SECTIONS: list[tuple[str, str]] = [
    ("Getting Started", "/getting-started"),
    ("Core Concepts", "/core-concepts"),
    ("Widgets", "/widgets"),
    ("Deployment", "/deployment"),
]

# Articles per section
_ARTICLES: dict[str, list[tuple[str, str]]] = {
    "/getting-started": [
        ("Installation", "/getting-started/installation"),
        ("Quick Start", "/getting-started/quickstart"),
        ("Project Layout", "/getting-started/layout"),
    ],
    "/core-concepts": [
        ("Widget Tree", "/core-concepts/widget-tree"),
        ("State & Rebuild", "/core-concepts/state"),
        ("Navigation Stack", "/core-concepts/navigation"),
    ],
    "/widgets": [
        ("Layout Widgets", "/widgets/layout"),
        ("Input Widgets", "/widgets/inputs"),
        ("Navigation Widgets", "/widgets/navigation"),
    ],
    "/deployment": [
        ("Mode A — WASM", "/deployment/wasm"),
        ("Mode B — Server", "/deployment/server"),
        ("Docker", "/deployment/docker"),
    ],
}

# Body text for each page
_CONTENT: dict[str, str] = {
    "/getting-started": (
        "Welcome! This guide walks you through setting up tempestweb, "
        "writing your first app, and understanding the project layout."
    ),
    "/getting-started/installation": (
        "Install tempestweb with pip:\n\n"
        "    pip install tempestweb\n\n"
        "Python 3.11+ is required. Both WASM and server runtimes are included."
    ),
    "/getting-started/quickstart": (
        "Create app.py, define make_state() and view(), then run:\n\n"
        "    tempestweb dev --mode wasm"
    ),
    "/getting-started/layout": (
        "The canonical layout is a single app.py per example.\n"
        "Larger apps can split into multiple modules imported by app.py."
    ),
    "/core-concepts": (
        "Learn about the widget tree, state management and the navigation stack."
    ),
    "/core-concepts/widget-tree": (
        "The widget tree is a declarative, typed Pydantic model graph.\n"
        "The reconciler diffs two trees and emits minimal patches."
    ),
    "/core-concepts/state": (
        "State lives in a plain Python dataclass.\n"
        "Call app.set_state(lambda s: ...) to mutate it and schedule a rebuild."
    ),
    "/core-concepts/navigation": (
        "The NavStack is a list of Route objects.\n"
        "app.push(), app.pop() and app.replace() mutate it and schedule a rebuild."
    ),
    "/widgets": "Browse the full widget catalogue organised by category.",
    "/widgets/layout": (
        "Column, Row, Container, Stack, Wrap, ScrollView and Grid "
        "cover the full flex layout surface."
    ),
    "/widgets/inputs": (
        "Input, TextArea, Checkbox, Switch, Slider, Dropdown, DatePicker and "
        "more — all typed, all async-first."
    ),
    "/widgets/navigation": (
        "Navigator, RouteDrawer, TabView, TabBar — navigation host widgets "
        "that keep state in the declarative tree."
    ),
    "/deployment": "Choose between Mode A (WASM) and Mode B (server + WebSocket).",
    "/deployment/wasm": (
        "Mode A runs Python in the browser via Pyodide.\n"
        "No server needed — the entire app ships as static files."
    ),
    "/deployment/server": (
        "Mode B runs Python on the server and pushes patches over WebSocket.\n"
        "Great for I/O-heavy apps that need server-side resources."
    ),
    "/deployment/docker": (
        "A single Dockerfile covers Mode B.\n"
        "Set TEMPESTWEB_MODE=server and expose port 8000."
    ),
}
```

!!! tip "Static data is plain Python"
    Notice that `_SECTIONS`, `_ARTICLES`, and `_CONTENT` are ordinary
    dictionaries and lists.  tempestweb doesn't require any special data format
    — any Python structure works inside `view()`.

---

## 3. State

All app state fits in two fields:

```python
@dataclass
class DrawerNavState:
    """Application state for the drawer-navigation demo.

    Attributes:
        drawer_open: Whether the navigation drawer is currently expanded.
        history_labels: Human-readable crumb labels for the breadcrumb trail,
            parallel to ``app.nav.stack``.
    """

    drawer_open: bool = False
    history_labels: list[str] = field(default_factory=lambda: ["Home"])


def make_state() -> DrawerNavState:
    """Build the initial drawer-navigation state.

    Returns:
        A fresh DrawerNavState with the drawer closed and the
        breadcrumb trail showing only the root crumb.
    """
    return DrawerNavState()
```

- **`drawer_open`** — `True` while the side panel is visible.
- **`history_labels`** — a list of human-readable labels that mirrors
  `app.nav.stack`.  We keep labels separate because the stack stores route
  names (`"/getting-started"`), but the breadcrumb needs to show
  `"Getting Started"`.

!!! info "NavStack and State travel together"
    tempestweb maintains two parallel stacks: `app.nav.stack` (routes) and
    `state.history_labels` (readable labels).  Every `push` / `pop` / `reset`
    must be paired with a matching `app.set_state` call to keep them in sync.

---

## 4. Content helper functions

Before building the full `view`, let's create three functions that render the
right content based on the current route.

### 4.1 Article page (leaf)

```python
def _article_body(route_name: str) -> Widget:
    """Render the content body for a leaf article page.

    Args:
        route_name: The current route name, used to look up the article text.

    Returns:
        A Card containing the article content text.
    """
    content = _CONTENT.get(route_name, "Content coming soon.")
    return Column(
        key="article-body",
        style=Style(gap=16.0, padding=Edge.all(24.0), background=BACKGROUND),
        children=[
            Card(
                key="article-card",
                children=[
                    Text(
                        content=content,
                        key="article-text",
                        style=Style(
                            font_size=15.0,
                            color=ON_SURFACE,
                        ),
                    ),
                ],
            ),
        ],
    )
```

### 4.2 Section index

```python
def _section_body(
    route_name: str,
    app: App[DrawerNavState],
) -> Widget:
    """Render the index page for a top-level section showing its articles.

    Args:
        route_name: The section's route name (e.g. "/getting-started").
        app: The application handle for wiring navigation handlers.

    Returns:
        A Column of tappable article tiles plus an intro paragraph.
    """
    articles = _ARTICLES.get(route_name, [])

    def make_nav_handler(title: str, article_route: str) -> Callable[[], None]:
        """Build a handler that navigates to article_route."""

        def handler() -> None:
            """Navigate to the article and append its crumb."""
            app.push(Route(name=article_route))
            app.set_state(lambda s: s.history_labels.append(title))

        return handler

    tiles: list[Widget] = []
    for title, article_route in articles:
        tiles.append(
            ListTile(
                key=f"tile-{article_route}",
                title=title,
                subtitle="Tap to read",
                trailing=Button(
                    label="→",
                    on_click=make_nav_handler(title, article_route),
                    key=f"tile-btn-{article_route}",
                    style=Style(
                        padding=Edge.symmetric(vertical=6.0, horizontal=12.0),
                        radius=6.0,
                        background=ACCENT,
                        color=ON_SURFACE,
                        font_size=13.0,
                    ),
                ),
            )
        )
        tiles.append(Divider(key=f"div-{article_route}"))

    intro = _CONTENT.get(route_name, "")

    return Column(
        key="section-body",
        style=Style(gap=16.0, padding=Edge.all(24.0), background=BACKGROUND),
        children=[
            Text(
                content=intro,
                key="section-intro",
                style=Style(font_size=15.0, color=ON_MUTED),
            ),
            Card(key="articles-card", children=tiles)
            if tiles
            else Container(key="no-tiles"),
        ],
    )
```

!!! tip "Closures for handlers inside loops"
    The inner `make_nav_handler` function captures `title` and `article_route`
    in a closure.  This pattern is essential inside loops: without it all
    lambdas would capture the variables from the **last** loop iteration — a
    classic Python gotcha.

### 4.3 Home screen

```python
def _home_body(app: App[DrawerNavState]) -> Widget:
    """Render the root home screen with section entry points.

    Args:
        app: The application handle for wiring navigation handlers.

    Returns:
        A Column with cards for each top-level section.
    """

    def make_section_handler(label: str, route: str) -> Callable[[], None]:
        """Build a handler that navigates to route."""

        def handler() -> None:
            """Navigate to the section and record its breadcrumb label."""
            app.push(Route(name=route))
            app.set_state(lambda s: s.history_labels.append(label))

        return handler

    section_cards: list[Widget] = []
    for label, route in _SECTIONS:
        section_cards.append(
            Card(
                key=f"section-card-{route}",
                children=[
                    Row(
                        key=f"section-row-{route}",
                        style=Style(
                            gap=12.0,
                            align=AlignItems.CENTER,
                        ),
                        children=[
                            Column(
                                key=f"section-info-{route}",
                                style=Style(gap=4.0, grow=1.0),
                                children=[
                                    Text(
                                        content=label,
                                        key=f"section-title-{route}",
                                        style=Style(
                                            font_size=16.0,
                                            font_weight=FontWeight.BOLD,
                                            color=ON_SURFACE,
                                        ),
                                    ),
                                    Text(
                                        content=(
                                            f"{len(_ARTICLES.get(route, []))} articles"
                                        ),
                                        key=f"section-count-{route}",
                                        style=Style(
                                            font_size=13.0,
                                            color=ON_MUTED,
                                        ),
                                    ),
                                ],
                            ),
                            Button(
                                label="→",
                                on_click=make_section_handler(label, route),
                                key=f"section-btn-{route}",
                                style=Style(
                                    padding=Edge.symmetric(
                                        vertical=8.0, horizontal=16.0
                                    ),
                                    radius=8.0,
                                    background=ACCENT,
                                    color=ON_SURFACE,
                                    font_size=16.0,
                                ),
                            ),
                        ],
                    ),
                ],
            )
        )

    return Column(
        key="home-body",
        style=Style(gap=16.0, padding=Edge.all(24.0), background=BACKGROUND),
        children=[
            Text(
                content="Browse the documentation by section or open the drawer.",
                key="home-intro",
                style=Style(font_size=15.0, color=ON_MUTED),
            ),
            *section_cards,
        ],
    )
```

### 4.4 Route dispatcher

```python
def _screen_for_route(
    route: Route,
    app: App[DrawerNavState],
) -> Widget:
    """Return the content widget for the given route.

    Args:
        route: The current top-of-stack route.
        app: The application handle.

    Returns:
        The content widget matching route.name.
    """
    if route.name == "/":
        return _home_body(app)
    segments = [s for s in route.name.split("/") if s]
    if len(segments) == 1:
        return _section_body(route.name, app)
    return _article_body(route.name)
```

The logic is straightforward:

| `route.name`                    | Segments | Renders             |
| ------------------------------- | -------- | ------------------- |
| `"/"`                           | 0        | Home screen         |
| `"/getting-started"`            | 1        | Section index       |
| `"/getting-started/quickstart"` | 2        | Article body        |

---

## 5. The drawer panel

The drawer lists all sections.  Tapping one calls `app.reset()` to replace the
entire route stack at once, then closes the drawer.

```python
def _drawer_panel(app: App[DrawerNavState]) -> Widget:
    """Build the drawer side panel with section navigation links.

    Args:
        app: The application handle.

    Returns:
        A Column acting as the drawer panel content.
    """

    def make_drawer_nav(label: str, route: str) -> Callable[[], None]:
        """Build a drawer navigation handler for route."""

        def handler() -> None:
            """Navigate to section and close drawer."""
            app.reset([Route(name="/"), Route(name=route)])

            def _update(s: DrawerNavState) -> None:
                s.history_labels[:] = ["Home", label]
                s.drawer_open = False

            app.set_state(_update)

        return handler

    nav_items: list[Widget] = []
    current_route = app.nav.top.name
    for label, route in _SECTIONS:
        active = current_route == route or current_route.startswith(route + "/")
        nav_items.append(
            Button(
                label=label,
                on_click=make_drawer_nav(label, route),
                key=f"drawer-nav-{route}",
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

    def go_home() -> None:
        """Reset to the root route and close the drawer."""
        app.reset([Route(name="/")])

        def _reset_home(s: DrawerNavState) -> None:
            s.history_labels[:] = ["Home"]
            s.drawer_open = False

        app.set_state(_reset_home)

    return Column(
        key="drawer-panel",
        style=Style(
            width=260.0,
            padding=Edge.all(16.0),
            gap=8.0,
            background=SURFACE,
        ),
        children=[
            Text(
                content="tempestweb",
                key="drawer-brand",
                style=Style(
                    font_size=18.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                ),
            ),
            Text(
                content="Documentation",
                key="drawer-subtitle",
                style=Style(font_size=12.0, color=ON_MUTED),
            ),
            Divider(key="drawer-div-top"),
            Button(
                label="Home",
                on_click=go_home,
                key="drawer-home-btn",
                style=Style(
                    padding=Edge.symmetric(vertical=10.0, horizontal=12.0),
                    radius=8.0,
                    background=Color.from_hex("#00000000"),
                    color=ON_MUTED,
                    font_size=14.0,
                ),
            ),
            Divider(key="drawer-div-sections"),
            *nav_items,
        ],
    )
```

!!! info "Why `app.reset()` instead of `app.push()`?"
    `app.push` **stacks** a new route on top of the existing ones.  If the user
    has navigated to `"/getting-started/installation"` and then taps
    **Deployment** in the drawer, we don't want to accumulate routes — we want
    to replace everything.  `app.reset([Route("/"), Route("/deployment")])`
    replaces the entire stack at once, and the reconciler emits a single patch.

---

## 6. The main `view`

Now we assemble everything.  `view` is the function tempestweb calls on every
rebuild.

```python
def view(app: App[DrawerNavState]) -> Widget:
    """Render the full drawer-navigation app from the current state.

    Args:
        app: The application handle exposing state, nav, and the
            navigation mutators.

    Returns:
        The widget tree for the current state.
    """
    current_route = app.nav.top
    stack_depth = len(app.nav.stack)

    # --- handlers ---

    def toggle_drawer() -> None:
        """Toggle the navigation drawer open or closed."""
        app.set_state(lambda s: setattr(s, "drawer_open", not s.drawer_open))

    def on_drawer_change() -> None:
        """Close the drawer when the renderer signals it should close."""
        app.set_state(lambda s: setattr(s, "drawer_open", False))

    def make_crumb_handler(crumb_index: int) -> Callable[[], None]:
        """Build a breadcrumb handler that pops back to crumb_index."""

        def handler() -> None:
            """Pop the nav stack back to crumb_index and trim the crumb labels."""
            new_stack = list(app.nav.stack[: crumb_index + 1])
            app.reset(new_stack)
            app.set_state(
                lambda s: s.history_labels.__setitem__(
                    slice(None), s.history_labels[: crumb_index + 1]
                )
            )

        return handler

    # --- breadcrumb ---

    crumb_labels = list(app.state.history_labels)
    breadcrumb = Breadcrumb(
        key="main-breadcrumb",
        items=crumb_labels,
        separator="›",
        on_select=lambda idx: make_crumb_handler(idx)(),
    )

    # --- appbar ---

    back_button: Widget | None = None
    if app.nav.can_pop:

        def go_back() -> None:
            """Pop the current route and trim the breadcrumb."""
            app.pop()

            def _trim(s: DrawerNavState) -> None:
                if len(s.history_labels) > 1:
                    s.history_labels.pop()

            app.set_state(_trim)

        back_button = Button(
            label="←",
            on_click=go_back,
            key="back-btn",
            style=Style(
                padding=Edge.all(8.0),
                radius=6.0,
                background=MUTED,
                color=ON_SURFACE,
                font_size=16.0,
            ),
        )

    burger = Button(
        label="☰",
        on_click=toggle_drawer,
        key="burger-btn",
        style=Style(
            padding=Edge.all(8.0),
            radius=6.0,
            background=MUTED,
            color=ON_SURFACE,
            font_size=16.0,
        ),
    )

    leading_widget: Widget = back_button if back_button is not None else burger

    depth_text = Text(
        content=f"depth: {stack_depth}",
        key="depth-badge",
        style=Style(
            font_size=12.0,
            color=ON_MUTED,
            padding=Edge.symmetric(vertical=4.0, horizontal=8.0),
            radius=6.0,
            background=MUTED,
        ),
    )

    appbar = AppBar(
        key="main-appbar",
        title=crumb_labels[-1] if crumb_labels else "Home",
        leading=leading_widget,
        actions=[depth_text],
    )

    # --- breadcrumb sub-bar ---

    breadcrumb_bar = Container(
        key="breadcrumb-bar",
        style=Style(
            padding=Edge.symmetric(vertical=8.0, horizontal=16.0),
            background=SURFACE,
        ),
        child=breadcrumb,
    )

    # --- screen content via dispatcher ---

    screen_content = _screen_for_route(current_route, app)

    navigator_widget = Container(
        key="navigator-host",
        style=Style(grow=1.0, background=BACKGROUND),
        child=screen_content,
    )

    # --- drawer ---

    drawer_panel = _drawer_panel(app)

    route_drawer = RouteDrawer(
        key="main-drawer",
        child=navigator_widget,
        drawer=drawer_panel,
        open=app.state.drawer_open,
        on_change=on_drawer_change,
    )

    # --- full scaffold ---

    top_area = Column(
        key="top-area",
        style=Style(gap=0.0),
        children=[appbar, breadcrumb_bar],
    )

    return Scaffold(
        key="root-scaffold",
        app_bar=top_area,
        body=route_drawer,
    )
```

Let's unpack the key points:

### 6.1 `app.nav.can_pop` — hamburger or back arrow

```python
leading_widget: Widget = back_button if back_button is not None else burger
```

When `app.nav.can_pop` is `True` (there is more than one route in the stack),
we show `"←"` to go back.  Otherwise we show `"☰"` to open the drawer.  The
reconciler swaps them with a single `replace` patch.

### 6.2 `Breadcrumb` with `on_select`

```python
breadcrumb = Breadcrumb(
    key="main-breadcrumb",
    items=crumb_labels,
    separator="›",
    on_select=lambda idx: make_crumb_handler(idx)(),
)
```

`on_select` receives the index of the tapped item.  `make_crumb_handler(idx)`
calls `app.reset` with only the first `idx + 1` elements of the stack,
effectively popping multiple levels at once.

### 6.3 `RouteDrawer` with `open` and `on_change`

```python
route_drawer = RouteDrawer(
    key="main-drawer",
    child=navigator_widget,
    drawer=drawer_panel,
    open=app.state.drawer_open,
    on_change=on_drawer_change,
)
```

`open` is driven by state — never by the drawer itself.  `on_change` is called
by the renderer when the user closes the drawer by clicking outside it, and
syncs the state back.

---

## 7. Smoke-test guard

```python
if __name__ == "__main__":
    _app: App[DrawerNavState] = App(
        state=make_state(),
        view=view,
        apply_patches=lambda p: None,
        nav=NavStack(),
    )
    _node = build(view(_app))
    assert _node.type and _node.children, "smoke-test failed"
    print("smoke-test OK", _node.type, len(_node.children))
```

Run `python examples/router-drawer/app.py` to verify that the widget tree
builds without errors before launching in the browser.

---

## 8. Run the app 🚀

**Mode A — Python in the browser (Pyodide):**

```bash
tempestweb dev --mode wasm --path examples/router-drawer
```

**Mode B — Python on the server (FastAPI + WebSocket):**

```bash
tempestweb run --mode server --path examples/router-drawer
```

Open `http://localhost:8000` and:

1. ✅ Tap any section card — the route changes and the breadcrumb grows.
2. ✅ Tap `"→"` on an article tile — you navigate one level deeper.
3. ✅ Tap any breadcrumb crumb — the stack rewinds to that point.
4. ✅ Open the drawer (`"☰"`) and choose a different section — the stack is
   replaced entirely.

!!! check "Verify the four checks"
    Before committing, run:

    ```bash
    ruff check . && ruff format --check .
    mypy tempestweb
    pytest -q
    ```

    All four checks must pass green ✅.

---

## Recap

In this tutorial you learned:

- **`RouteDrawer`** — a side panel controlled by `open` (a state flag) and
  closed via `on_change`.
- **`app.push(Route(...))`** — pushes a route onto the stack and schedules a
  rebuild.
- **`app.pop()`** — undoes the last push; `app.nav.can_pop` tells you whether
  this is possible.
- **`app.reset([...])`** — replaces the entire stack at once, ideal for drawer
  navigation.
- **`Breadcrumb`** with `on_select` — lets users jump back to any depth without
  calling `pop` manually multiple times.
- **Closures for handlers inside loops** — the `make_xxx_handler(arg)` pattern
  to capture loop variables correctly.

---

## Next steps

- See [Dashboard Shell](dashboard-shell.en.md) for a more elaborate layout with
  `NavBar` and multiple panels.
- Explore [Tabs & Profile](tabs-profile.en.md) for tab-based navigation instead
  of a drawer.
- Read [Execution Modes](../tutorial/modes.en.md) to understand the differences
  between Mode A and Mode B in production.
