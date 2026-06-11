"""Navigation host widgets: Navigator, TabView, TabBar and RouteDrawer.

These widgets are the IR surface for navigation *in the tree*. The
:class:`~tempestroid.navigation.NavStack` (owned by :class:`~tempestroid.App`)
decides *which* route is on top; these widgets are how the ``view`` lowers that
into a renderable subtree so the reconciler can diff a route change into patches
(an :class:`~tempestroid.core.ir.Update` or :class:`~tempestroid.core.ir.Replace`
on the host node — no new patch kind).

Like every other widget they are renderer-agnostic Pydantic nodes: they carry
**props** (``transition``/``active``/``open``/``depth``/``tabs``) and **child
slots** (declared via ``child_field_names``), and nothing platform-specific. The
Qt leaf renderer maps them to ``QStackedWidget`` + ``QPropertyAnimation`` (slide/
fade), a tab strip and a sliding drawer panel; the Compose renderer mirrors the
same ``node.type``/props with ``AnimatedContent``/``TabRow``/``ModalDrawer``.
The four node-type names and their props are **frozen** here so both renderers
agree by value.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from tempestweb._core.widgets.base import RouteChangeHandler, Widget
from tempestweb._core.widgets.events import Event, RouteChangeEvent

__all__ = [
    "Navigator",
    "TabView",
    "TabBar",
    "RouteDrawer",
]


class Navigator(Widget):
    """A navigation-stack host that renders the screen on top of the stack.

    The ``view`` builds ``child`` from ``app.nav.top`` and wraps it in a
    ``Navigator``; pushing/popping a route rebuilds with a different ``child``,
    which the reconciler diffs (an ``Update`` when the screen's subtree is
    compatible, a ``Replace`` otherwise). The ``transition`` prop is a renderer
    hint for how to animate the swap, and ``depth`` (the stack length) lets the
    renderer tell a push (deeper) from a pop (shallower) to pick the slide
    direction.

    Attributes:
        child: The screen currently on top of the stack.
        transition: Animation hint for a screen swap (``"slide"``, ``"fade"`` or
            ``"none"``). Defaults to ``"slide"``.
        depth: The current navigation stack depth. The renderer compares it
            against the previous depth to slide forward (push) or back (pop).
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"child"})

    child: Widget = Field(description="The screen currently on top of the stack.")
    transition: str = Field(
        default="slide",
        description='Animation hint for a screen swap (``"slide"``, ``"fade"`` or '
        '``"none"``). Defaults to ``"slide"``.',
    )
    depth: int = Field(
        default=0,
        description="The current navigation stack depth. The renderer compares it "
        "against the previous depth to slide forward (push) or back (pop).",
    )

    def child_nodes(self) -> list[Widget]:
        """Return the top screen as this navigator's single child.

        Returns:
            A one-element list with the top screen.
        """
        return [self.child]


class TabBar(Widget):
    """A standalone tab strip: one selectable label per tab.

    Emits a typed :class:`~tempestroid.widgets.RouteChangeEvent` when a tab is
    tapped, with the tapped index in ``params["index"]``. Use it on its own to
    drive navigation, or let :class:`TabView` own one implicitly.

    Attributes:
        tabs: The ordered tab labels (paired by index across Qt/Compose).
        active: The index of the currently selected tab.
        on_change: Optional handler invoked with a ``RouteChangeEvent`` on a tap.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_change": RouteChangeEvent}

    tabs: list[str] = Field(
        description="The ordered tab labels (paired by index across Qt/Compose)."
    )
    active: int = Field(
        default=0, description="The index of the currently selected tab."
    )
    on_change: RouteChangeHandler | None = Field(
        default=None,
        description="Optional handler invoked with a ``RouteChangeEvent`` on a tap.",
    )


class TabView(Widget):
    """A tabbed host: a tab strip plus the active tab's content.

    The ``view`` builds ``child`` for the active tab (typically from
    ``app.nav``/``active``); tapping a tab fires ``on_change`` with a
    ``RouteChangeEvent`` carrying ``params["index"]`` so the handler can switch
    the active tab and rebuild a new ``child``.

    Attributes:
        tabs: The ordered tab labels.
        active: The index of the currently selected tab.
        child: The content widget for the active tab.
        on_change: Optional handler invoked with a ``RouteChangeEvent`` on a tap.
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"child"})
    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_change": RouteChangeEvent}

    tabs: list[str] = Field(description="The ordered tab labels.")
    active: int = Field(
        default=0, description="The index of the currently selected tab."
    )
    child: Widget = Field(description="The content widget for the active tab.")
    on_change: RouteChangeHandler | None = Field(
        default=None,
        description="Optional handler invoked with a ``RouteChangeEvent`` on a tap.",
    )

    def child_nodes(self) -> list[Widget]:
        """Return the active tab's content as the single child.

        Returns:
            A one-element list with the active tab's content.
        """
        return [self.child]


class RouteDrawer(Widget):
    """A drawer-as-route host: main content with a slide-over side panel.

    When ``open`` is ``True`` the renderer slides the ``drawer`` panel over the
    ``child`` content; toggling it fires ``on_change`` so a handler can flip the
    open flag and rebuild. Modelling the drawer as a widget (rather than a
    transient overlay) keeps its open/closed state in the declarative tree, so it
    survives rebuilds and diffs like any other prop.

    Attributes:
        child: The main content shown under the drawer.
        drawer: The panel that slides over the content when open.
        open: Whether the drawer panel is currently shown.
        on_change: Optional handler invoked with a ``RouteChangeEvent`` when the
            drawer toggles.
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"child", "drawer"})
    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_change": RouteChangeEvent}

    child: Widget = Field(description="The main content shown under the drawer.")
    drawer: Widget = Field(
        description="The panel that slides over the content when open."
    )
    open: bool = Field(
        default=False, description="Whether the drawer panel is currently shown."
    )
    on_change: RouteChangeHandler | None = Field(
        default=None,
        description="Optional handler invoked with a ``RouteChangeEvent`` when the "
        "drawer toggles.",
    )

    def child_nodes(self) -> list[Widget]:
        """Return the content and the drawer panel, in that order.

        Returns:
            A two-element list: ``[child, drawer]``.
        """
        return [self.child, self.drawer]
