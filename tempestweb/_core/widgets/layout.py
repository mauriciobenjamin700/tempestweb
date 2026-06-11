"""Layout + overlay widgets (Column, Row, Container, ScrollView, SafeArea, Stack)."""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from pydantic import Field

from tempestweb._core.widgets.base import PageChangeHandler, Widget
from tempestweb._core.widgets.events import Event, PageChangeEvent

__all__ = [
    "Column",
    "Row",
    "Container",
    "ScrollView",
    "SafeArea",
    "SafeAreaEdge",
    "Stack",
    "Wrap",
    "PageView",
    "AspectRatio",
    "KeyboardAvoidingView",
]


def _empty_children() -> list[Widget]:
    """Provide a fresh, typed empty child list for default factories.

    Returns:
        A new empty list of widgets.
    """
    return []


class SafeAreaEdge(StrEnum):
    """A screen edge a :class:`SafeArea` can inset against system intrusions."""

    TOP = "top"
    RIGHT = "right"
    BOTTOM = "bottom"
    LEFT = "left"


def _all_safe_area_edges() -> list[SafeAreaEdge]:
    """Provide the default edge set for a :class:`SafeArea` — every edge.

    Returns:
        A fresh list holding all four edges.
    """
    return [
        SafeAreaEdge.TOP,
        SafeAreaEdge.RIGHT,
        SafeAreaEdge.BOTTOM,
        SafeAreaEdge.LEFT,
    ]


class Column(Widget):
    """A vertical flex container (main axis = top-to-bottom).

    Attributes:
        children: The ordered child widgets.
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"children"})
    children: list[Widget] = Field(
        description="The ordered child widgets.", default_factory=_empty_children
    )

    def child_nodes(self) -> list[Widget]:
        """Return the column's children.

        Returns:
            The ordered child widgets.
        """
        return self.children


class Row(Widget):
    """A horizontal flex container (main axis = left-to-right).

    Attributes:
        children: The ordered child widgets.
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"children"})
    children: list[Widget] = Field(
        description="The ordered child widgets.", default_factory=_empty_children
    )

    def child_nodes(self) -> list[Widget]:
        """Return the row's children.

        Returns:
            The ordered child widgets.
        """
        return self.children


class Container(Widget):
    """A single-child box used for padding, background, borders and sizing.

    Attributes:
        child: The optional wrapped widget.
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"child"})
    child: Widget | None = Field(
        default=None, description="The optional wrapped widget."
    )

    def child_nodes(self) -> list[Widget]:
        """Return the wrapped child, if any.

        Returns:
            A one-element list with the child, or an empty list.
        """
        return [self.child] if self.child is not None else []


class ScrollView(Widget):
    """A scrollable container holding an overflowing list of children.

    Attributes:
        horizontal: When ``True``, children lay out and scroll left-to-right;
            otherwise they stack and scroll top-to-bottom.
        children: The ordered child widgets.
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"children"})
    horizontal: bool = Field(
        default=False,
        description="When ``True``, children lay out and scroll left-to-right; "
        "otherwise they stack and scroll top-to-bottom.",
    )
    children: list[Widget] = Field(
        description="The ordered child widgets.", default_factory=_empty_children
    )

    def child_nodes(self) -> list[Widget]:
        """Return the scroll view's children.

        Returns:
            The ordered child widgets.
        """
        return self.children


class SafeArea(Widget):
    """A single-child box that insets its child away from system intrusions.

    Mirrors React Native's ``SafeAreaView``: it pads the content so it does not
    sit under the status bar, the navigation bar, or a display cutout/notch. On
    the device renderer the inset is the *real* ``WindowInsets.safeDrawing``
    reported by the platform; the desktop simulator has no system bars, so it
    stands in with fixed approximate insets. The ``edges`` set selects which
    edges are protected — pass a subset (e.g. only ``SafeAreaEdge.TOP``) to leave
    the others flush.

    Attributes:
        child: The optional wrapped widget.
        edges: The edges to inset against (defaults to all four).
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"child"})
    child: Widget | None = Field(
        default=None, description="The optional wrapped widget."
    )
    edges: list[SafeAreaEdge] = Field(
        description="The edges to inset against (defaults to all four).",
        default_factory=_all_safe_area_edges,
    )

    def child_nodes(self) -> list[Widget]:
        """Return the wrapped child, if any.

        Returns:
            A one-element list with the child, or an empty list.
        """
        return [self.child] if self.child is not None else []


class Stack(Widget):
    """An overlapping container: children share one box, layered by z-order.

    Unlike ``Column``/``Row`` (which lay children out along an axis), a ``Stack``
    paints its children on top of one another in declaration order — the first
    child is the bottom layer, the last is on top. This is the framework's
    overlay primitive: a scrim, a modal card, a toast or a floating action button
    is just a later child of a ``Stack`` wrapping the page content.

    Non-positioned children are aligned within the box by the stack's
    :attr:`~tempestroid.style.Style.stack_align`. A child whose style sets
    ``position = ABSOLUTE`` is anchored instead by its
    ``top``/``right``/``bottom``/``left`` insets (Flutter ``Positioned`` / CSS
    ``position: absolute``); set both ``left`` and ``right`` (or ``top`` and
    ``bottom``) to stretch it across that axis — a full-bleed scrim is
    ``position = ABSOLUTE`` with all four insets at ``0``.

    Attributes:
        children: The ordered child widgets, bottom layer first.
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"children"})
    children: list[Widget] = Field(
        description="The ordered child widgets, bottom layer first.",
        default_factory=_empty_children,
    )

    def child_nodes(self) -> list[Widget]:
        """Return the stack's children in z-order (bottom layer first).

        Returns:
            The ordered child widgets.
        """
        return self.children


class Wrap(Widget):
    """A flow-layout container: children wrap to the next line when a row fills.

    Unlike ``Row`` (which keeps every child on a single line), a ``Wrap`` flows
    its children left-to-right and breaks onto a new line once the current line
    is full — the natural primitive for chips, tags or any free-flowing set of
    pills. Wrapping is controlled by
    :attr:`~tempestroid.style.Style.flex_wrap`; a ``Wrap`` wraps by default even
    when the caller leaves the field unset, since wrapping is the widget's whole
    purpose. The Compose renderer lowers it to ``FlowRow``/``FlowColumn`` and the
    Qt renderer realizes the flow imperatively (see the conformance suite).

    Attributes:
        children: The ordered child widgets, flowed and wrapped in order.
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"children"})
    children: list[Widget] = Field(
        description="The ordered child widgets, flowed and wrapped in order.",
        default_factory=_empty_children,
    )

    def child_nodes(self) -> list[Widget]:
        """Return the wrap's children in flow order.

        Returns:
            The ordered child widgets.
        """
        return self.children


class PageView(Widget):
    """A paginated horizontal carousel: one full-width page visible at a time.

    Each child is a page; the user swipes (device) or uses prev/next controls
    (simulator) to move between them. The active page index lives in the
    application's own state — the app passes the current :attr:`page` and updates
    it from the :attr:`on_page_change` handler. To avoid a feedback loop, a
    handler should ignore a :class:`PageChangeEvent` whose ``page`` already
    matches the state. The Compose renderer lowers it to a ``HorizontalPager``;
    the Qt renderer uses a ``QStackedWidget`` with prev/next navigation.

    Attributes:
        children: The ordered page widgets.
        page: The active page index (0-based), driven by the application state.
        on_page_change: Handler invoked with a :class:`PageChangeEvent` when the
            active page changes.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {
        "on_page_change": PageChangeEvent
    }
    child_field_names: ClassVar[frozenset[str]] = frozenset({"children"})
    children: list[Widget] = Field(
        description="The ordered page widgets.", default_factory=_empty_children
    )
    page: int = Field(
        default=0,
        description="The active page index (0-based), driven by the application state.",
    )
    on_page_change: PageChangeHandler | None = Field(
        default=None,
        description="Handler invoked with a :class:`PageChangeEvent` when the active "
        "page changes.",
    )

    def child_nodes(self) -> list[Widget]:
        """Return the carousel's pages in order.

        Returns:
            The ordered child widgets.
        """
        return self.children


class AspectRatio(Widget):
    """A single-child box that constrains its child to a fixed width/height ratio.

    The ``ratio`` is ``width / height``: a value of ``1.0`` is square, ``16/9``
    is widescreen. The renderer derives the missing dimension from whichever one
    is bounded by the parent. This is the explicit-widget counterpart to
    :attr:`~tempestroid.style.Style.aspect_ratio` — use the widget when fixing
    the ratio is the box's only purpose; the two coexist. The Compose renderer
    lowers it to ``Modifier.aspectRatio`` and the Qt renderer derives the fixed
    dimension imperatively.

    Attributes:
        ratio: The ``width / height`` ratio to enforce (must be positive).
        child: The optional wrapped widget.
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"child"})
    ratio: float = Field(
        description="The ``width / height`` ratio to enforce (must be positive).",
        gt=0.0,
    )
    child: Widget | None = Field(
        default=None, description="The optional wrapped widget."
    )

    def child_nodes(self) -> list[Widget]:
        """Return the wrapped child, if any.

        Returns:
            A one-element list with the child, or an empty list.
        """
        return [self.child] if self.child is not None else []


class KeyboardAvoidingView(Widget):
    """A vertical container that recedes its content when the keyboard appears.

    Wraps its children and, while the on-screen keyboard is open, insets them so
    the focused input stays visible above it. On the device the Compose renderer
    lowers it to a ``Column`` with ``Modifier.imePadding()`` (driven by
    ``WindowInsets.ime``); the Qt simulator listens on
    ``QApplication.inputMethod().keyboardRectangleChanged`` and adjusts its
    content margins, behaving like a plain ``Column`` on desktop (no virtual
    keyboard). It declares no event contract — the keyboard inset is handled by
    the renderer, not surfaced to application handlers.

    Attributes:
        children: The ordered child widgets the view insets.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {}
    child_field_names: ClassVar[frozenset[str]] = frozenset({"children"})
    children: list[Widget] = Field(
        description="The ordered child widgets the view insets.",
        default_factory=_empty_children,
    )

    def child_nodes(self) -> list[Widget]:
        """Return the view's children.

        Returns:
            The ordered child widgets.
        """
        return self.children
