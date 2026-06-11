"""Drawer navigation & routing — demonstrates RouteDrawer + Navigator + Breadcrumb.

This example shows how tempestweb's navigation primitives compose together:

* :class:`~tempestweb._core.widgets.RouteDrawer` — a slide-over side panel whose
  ``open`` flag lives in state and is toggled without naming a transport.
* :class:`~tempestweb._core.widgets.Navigator` — wraps the active screen; pushing /
  popping via ``app.push`` / ``app.pop`` replaces its ``child`` and the reconciler
  diffs the swap.
* :class:`~tempestweb._core.components.Breadcrumb` — renders the current route path
  as a tappable trail so users can jump back to any ancestor.

The app models a small documentation-style site with four top-level sections and a
two-level drill-down (section → article).  All navigation flows through
``app.push``/``app.pop``/``app.replace`` — the view reads ``app.nav.top`` to decide
which screen to build.  Both modes (WASM / server) run the same ``view`` unchanged.

Usage::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from tempestweb._core import App, NavStack, Route, Style, Widget, build
from tempestweb._core.components import (
    AppBar,
    Breadcrumb,
    Card,
    Divider,
    ListTile,
    Scaffold,
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
from tempestweb._core.widgets import (
    Button,
    Column,
    Container,
    RouteDrawer,
    Row,
    Text,
)

# ---------------------------------------------------------------------------
# Static content catalogue
# ---------------------------------------------------------------------------

#: Top-level sections available in the drawer.
_SECTIONS: list[tuple[str, str]] = [
    ("Getting Started", "/getting-started"),
    ("Core Concepts", "/core-concepts"),
    ("Widgets", "/widgets"),
    ("Deployment", "/deployment"),
]

#: Articles per section keyed by route name.
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

#: Body text snippets per article route.
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


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Public contract
# ---------------------------------------------------------------------------


def make_state() -> DrawerNavState:
    """Build the initial drawer-navigation state.

    Returns:
        A fresh :class:`DrawerNavState` with the drawer closed and the
        breadcrumb trail showing only the root crumb.
    """
    return DrawerNavState()


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------


def _article_body(route_name: str) -> Widget:
    """Render the content body for a leaf article page.

    Args:
        route_name: The current route name, used to look up the article text.

    Returns:
        A :class:`Card` containing the article content text.
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


def _section_body(
    route_name: str,
    app: App[DrawerNavState],
) -> Widget:
    """Render the index page for a top-level section showing its articles.

    Args:
        route_name: The section's route name (e.g. ``"/getting-started"``).
        app: The application handle for wiring navigation handlers.

    Returns:
        A :class:`Column` of tappable article tiles plus an intro paragraph.
    """
    articles = _ARTICLES.get(route_name, [])

    def make_nav_handler(title: str, article_route: str) -> Callable[[], None]:
        """Build a handler that navigates to *article_route*.

        Args:
            title: The human-readable article title, appended to the breadcrumb.
            article_route: The destination route name.

        Returns:
            A zero-argument callable that pushes the route and updates crumbs.
        """

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


def _home_body(app: App[DrawerNavState]) -> Widget:
    """Render the root home screen with section entry points.

    Args:
        app: The application handle for wiring navigation handlers.

    Returns:
        A :class:`Column` with cards for each top-level section.
    """

    def make_section_handler(label: str, route: str) -> Callable[[], None]:
        """Build a handler that navigates to *route*.

        Args:
            label: The human-readable section label for the breadcrumb.
            route: The destination route name.

        Returns:
            A zero-argument callable that pushes the route and records the crumb.
        """

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


def _screen_for_route(
    route: Route,
    app: App[DrawerNavState],
) -> Widget:
    """Return the content widget for the given route.

    A top-level route (e.g. ``"/getting-started"``) shows the section index;
    a two-segment route (e.g. ``"/getting-started/installation"``) shows the
    article body.  The root ``"/"`` shows the home screen.

    Args:
        route: The current top-of-stack route.
        app: The application handle.

    Returns:
        The content widget matching ``route.name``.
    """
    if route.name == "/":
        return _home_body(app)
    segments = [s for s in route.name.split("/") if s]
    if len(segments) == 1:
        return _section_body(route.name, app)
    return _article_body(route.name)


# ---------------------------------------------------------------------------
# Drawer panel
# ---------------------------------------------------------------------------


def _drawer_panel(app: App[DrawerNavState]) -> Widget:
    """Build the drawer side panel with section navigation links.

    Tapping a section link closes the drawer, resets the navigation stack to
    that section, and updates the breadcrumb labels.

    Args:
        app: The application handle.

    Returns:
        A :class:`Column` acting as the drawer panel content.
    """

    def make_drawer_nav(label: str, route: str) -> Callable[[], None]:
        """Build a drawer navigation handler for *route*.

        Args:
            label: The section label shown in the drawer and the breadcrumb.
            route: The destination route name.

        Returns:
            A zero-argument callable that resets the stack, updates crumbs,
            and closes the drawer.
        """

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


# ---------------------------------------------------------------------------
# Root view
# ---------------------------------------------------------------------------


def view(app: App[DrawerNavState]) -> Widget:
    """Render the full drawer-navigation app from the current state.

    The layout is: an ``AppBar`` on top, a ``Breadcrumb`` trail below it, then
    a ``RouteDrawer`` whose main content is a ``Navigator`` holding the current
    screen.  Tapping the burger icon toggles the drawer.  Tapping a breadcrumb
    crumb pops the stack back to that depth.

    Args:
        app: The application handle exposing ``state``, ``nav``, and the
            navigation mutators.

    Returns:
        The widget tree for the current state.
    """
    current_route = app.nav.top
    stack_depth = len(app.nav.stack)

    # ----- handlers -----

    def toggle_drawer() -> None:
        """Toggle the navigation drawer open or closed."""
        app.set_state(lambda s: setattr(s, "drawer_open", not s.drawer_open))

    def on_drawer_change() -> None:
        """Close the drawer when the renderer signals it should close."""
        app.set_state(lambda s: setattr(s, "drawer_open", False))

    def make_crumb_handler(crumb_index: int) -> Callable[[], None]:
        """Build a breadcrumb handler that pops back to *crumb_index*.

        Args:
            crumb_index: The depth in the nav stack to pop back to
                (``0`` = root, ``1`` = first level, etc.).

        Returns:
            A zero-argument callable that resets the stack to ``crumb_index + 1``
            routes and trims the breadcrumb labels to match.
        """

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

    # ----- breadcrumb -----

    crumb_labels = list(app.state.history_labels)
    breadcrumb = Breadcrumb(
        key="main-breadcrumb",
        items=crumb_labels,
        separator="›",
        on_select=lambda idx: make_crumb_handler(idx)(),
    )

    # ----- appbar -----

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

    # Leading widget: back button on sub-pages, burger on root.
    leading_widget: Widget = back_button if back_button is not None else burger

    # Always show depth indicator badge in the trailing area.
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

    # ----- breadcrumb sub-bar -----

    breadcrumb_bar = Container(
        key="breadcrumb-bar",
        style=Style(
            padding=Edge.symmetric(vertical=8.0, horizontal=16.0),
            background=SURFACE,
        ),
        child=breadcrumb,
    )

    # ----- screen content via Navigator -----

    screen_content = _screen_for_route(current_route, app)

    navigator_widget = Container(
        key="navigator-host",
        style=Style(grow=1.0, background=BACKGROUND),
        child=screen_content,
    )

    # ----- drawer -----

    drawer_panel = _drawer_panel(app)

    route_drawer = RouteDrawer(
        key="main-drawer",
        child=navigator_widget,
        drawer=drawer_panel,
        open=app.state.drawer_open,
        on_change=on_drawer_change,
    )

    # ----- full scaffold -----

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


# ---------------------------------------------------------------------------
# Smoke-test guard (not run by the contract verifier but useful locally)
# ---------------------------------------------------------------------------

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
