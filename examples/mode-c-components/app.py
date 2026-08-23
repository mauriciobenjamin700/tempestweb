"""Mode C component gallery — every ported core component, in native JS.

One transpiled app exercising the components the transpile client ports: the
surfaces (``Surface``, ``Card``, ``Sidebar``, ``Drawer``), the bars (``Header``,
``AppBar``, ``NavBar``, ``Breadcrumb``, ``Footer``), the content rows
(``ListTile``, ``Avatar``, ``Tag``, ``Badge``), the feedback blocks (``Alert``,
``Banner``, ``EmptyState``, ``Stat``, ``ProgressStepper``) and the interactive
ones (``Rating``, ``Stepper``, ``SearchBar``). Build it with::

    tempestweb build --mode transpile examples/mode-c-components
    tempestweb dev   --mode transpile examples/mode-c-components   # livereload

Zero Python runs in the browser: the composition of each component is rewritten
in ``client/transpile/components.js`` and its style comes from a table generated
from the core, so the tree here is the tree Modes A and B build. The same
``view`` runs under those modes unchanged.

Every component instance carries an explicit ``key``: a component's default key
is its own name (two ``Card``s under one parent would both answer to ``card``),
and the reconciler addresses children by key.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import (
    Alert,
    App,
    Avatar,
    Badge,
    Banner,
    Breadcrumb,
    Burger,
    Button,
    Card,
    Column,
    ConfidenceBadge,
    Divider,
    Drawer,
    Edge,
    EmptyState,
    Footer,
    Grid,
    Header,
    ListTile,
    MetricCard,
    NavBar,
    ProgressStepper,
    Rating,
    Row,
    SearchBar,
    Sidebar,
    Stat,
    StatCard,
    Stepper,
    Style,
    StyledContainer,
    Surface,
    Tag,
    Text,
    Widget,
)

SECTIONS = ["Surfaces", "Content", "Feedback"]
STEPS = ["Cart", "Address", "Payment"]
FRUITS = ["apple", "avocado", "banana", "cherry"]


@dataclass
class GalleryState:
    """State for the component gallery."""

    section: int = 0
    drawer_open: bool = False
    rating: int = 3
    quantity: int = 1
    query: str = ""
    step: int = 0

    def bump_step(self) -> None:
        """Advance the progress stepper, wrapping back to the first step."""
        self.step = (self.step + 1) % 3


def make_state() -> GalleryState:
    """Build the initial gallery state."""
    return GalleryState()


def matches(query: str) -> list[str]:
    """Filter the demo list by a case-insensitive prefix.

    Args:
        query: The current search text.

    Returns:
        The matching fruit names, or every name when the query is empty.
    """
    if query == "":
        return FRUITS
    needle = query.lower()
    return [fruit for fruit in FRUITS if fruit.startswith(needle)]


def surfaces() -> Widget:
    """Render the surface section: Surface, StyledContainer, Grid, Card.

    Returns:
        A column of surface demos.
    """
    cells = [
        StatCard(label="Users", value="1.2k", delta="+8%", key="cell-users"),
        StatCard(
            label="Churn", value="0.4%", delta="-2%", delta_up=False, key="cell-churn"
        ),
    ]
    return Column(
        key="sec-surfaces",
        style=Style(gap=16.0),
        children=[
            Surface(
                key="bare-surface",
                child=StyledContainer(
                    key="bare-pad",
                    padding="lg",
                    child=Text(content="Surface + StyledContainer", key="bare-text"),
                ),
            ),
            Card(
                key="card-demo",
                children=[
                    Text(content="Card, elevated", key="card-title"),
                    Divider(key="card-rule"),
                    Text(content="with a divider under the title", key="card-body"),
                ],
            ),
            Grid(key="grid-demo", columns=2, gap="md", children=cells),
            MetricCard(
                key="metric-demo",
                label="Requests",
                value="98.1k",
                delta="+3%",
                trailing=ConfidenceBadge(
                    confidence=0.92, label="SLA", key="metric-sla"
                ),
            ),
        ],
    )


def content(app: App[GalleryState]) -> Widget:
    """Render the content section: ListTile, Avatar, Tag, Rating, Stepper, search.

    Args:
        app: The running app, for the state the section reads and writes.

    Returns:
        A column of content demos.
    """

    def on_rate(value: int) -> None:
        app.set_state(lambda s: setattr(s, "rating", value))

    def on_quantity(value: int) -> None:
        app.set_state(lambda s: setattr(s, "quantity", value))

    def on_query(event: object) -> None:
        value = event.payload["value"]
        app.set_state(lambda s: setattr(s, "query", value))

    def clear_query() -> None:
        app.set_state(lambda s: setattr(s, "query", ""))

    found = matches(app.state.query)
    rows: list[Widget] = []
    for index, fruit in enumerate(found):
        rows.append(
            ListTile(
                key="row-" + fruit,
                title=fruit,
                subtitle="in stock",
                leading=Avatar(initials=fruit[0:2], key="av-" + fruit),
                trailing=Badge(label=str(index + 1), tone="info", key="qty-" + fruit),
            )
        )
    listing: Widget = Column(key="rows", style=Style(gap=4.0), children=rows)
    if len(found) == 0:
        listing = EmptyState(
            key="no-rows",
            title="No fruit matches",
            subtitle="Clear the search to see them all",
            action=Button(label="Clear", on_click=clear_query, key="clear-empty"),
        )
    return Column(
        key="sec-content",
        style=Style(gap=16.0),
        children=[
            SearchBar(
                key="search",
                value=app.state.query,
                placeholder="Filter fruit",
                on_change=on_query,
                on_clear=clear_query,
            ),
            listing,
            Row(
                key="tags",
                style=Style(gap=8.0),
                children=[
                    Tag(label="fresh", key="tag-fresh"),
                    Tag(label="local", color_scheme="success", key="tag-local"),
                    Tag(label="organic", color_scheme="warning", key="tag-organic"),
                ],
            ),
            Rating(key="rating", value=app.state.rating, on_rate=on_rate),
            Row(
                key="quantity",
                style=Style(gap=12.0, align="center"),
                children=[
                    Text(content="Quantity", key="qty-label"),
                    Stepper(
                        key="qty",
                        value=app.state.quantity,
                        min_value=1,
                        max_value=9,
                        on_change=on_quantity,
                    ),
                ],
            ),
        ],
    )


def feedback(app: App[GalleryState]) -> Widget:
    """Render the feedback section: Alert, Banner, Stat, ProgressStepper.

    Args:
        app: The running app, for the state the section reads and writes.

    Returns:
        A column of feedback demos.
    """

    def advance() -> None:
        app.set_state(lambda s: s.bump_step())

    return Column(
        key="sec-feedback",
        style=Style(gap=16.0),
        children=[
            Banner(
                key="banner",
                message="Deploy finished",
                tone="success",
                action=Button(label="Logs", on_click=advance, key="banner-action"),
            ),
            Alert(
                key="alert",
                title="Token expires soon",
                body="Rotate it before Friday to avoid a failed build.",
                glyph="!",
                variant="left_accent",
                color_scheme="warning",
            ),
            Row(
                key="stats",
                style=Style(gap=24.0),
                children=[
                    Stat(label="Uptime", value="99.9%", key="stat-uptime"),
                    Stat(
                        label="Errors",
                        value="12",
                        delta="-40%",
                        delta_up=False,
                        key="stat-errors",
                    ),
                ],
            ),
            ProgressStepper(key="steps", steps=STEPS, current=app.state.step),
            Button(label="Next step", on_click=advance, key="next-step"),
        ],
    )


def view(app: App[GalleryState]) -> Widget:
    """Render the gallery: a bar, a lateral panel and the active section.

    Args:
        app: The running app.

    Returns:
        The gallery tree.
    """

    def select(index: int) -> None:
        app.set_state(lambda s: setattr(s, "section", index))

    def toggle_drawer() -> None:
        app.set_state(lambda s: setattr(s, "drawer_open", not s.drawer_open))

    section = app.state.section
    body = surfaces()
    if section == 1:
        body = content(app)
    if section == 2:
        body = feedback(app)
    panel = Column(
        key="panel-body",
        style=Style(gap=12.0),
        children=[
            Text(content="Shortcuts", key="panel-title"),
            Tag(label="docs", key="panel-docs"),
            Tag(label="issues", color_scheme="error", key="panel-issues"),
        ],
    )
    lateral: Widget = Sidebar(key="sidebar", children=[panel])
    if app.state.drawer_open:
        lateral = Drawer(key="drawer", open=True, children=[panel])
    return Column(
        key="gallery",
        style=Style(gap=0.0),
        children=[
            Header(
                key="header",
                title="Mode C components",
                subtitle="every ported core component, in native JS",
            ),
            Row(
                key="toolbar",
                style=Style(gap=12.0, padding=Edge.all(12.0), align="center"),
                children=[
                    Burger(key="burger", on_click=toggle_drawer),
                    Breadcrumb(
                        key="crumbs",
                        items=["gallery", SECTIONS[section]],
                        on_select=select,
                    ),
                ],
            ),
            NavBar(key="nav", items=SECTIONS, active=section, on_select=select),
            Row(
                key="main",
                style=Style(gap=16.0, padding=Edge.all(16.0)),
                children=[
                    lateral,
                    Column(key="content", style=Style(grow=1.0), children=[body]),
                ],
            ),
            Footer(
                key="footer",
                children=[Text(content="tempestweb · Mode C", key="footer-text")],
            ),
        ],
    )
