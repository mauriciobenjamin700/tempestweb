"""Virtualized list widgets and pull-to-refresh.

These are the framework's *virtual* container primitives: instead of declaring a
materialized list of children, they declare an ``item_count`` plus an
``item_builder(index) -> Widget`` factory. Only the currently visible window of
items is ever materialized into the IR — the renderer reports the scroll
``offset`` via :class:`~tempestroid.widgets.events.ScrollEvent`, the application
recomputes the visible ``[start, end]`` window and rebuilds, and the keyed diff
(item key = ``str(index)``) turns a window slide into a minimal
remove/reorder/insert patch sequence.

Because ``item_builder`` is a Python callable that materializes a widget on the
*same* thread as ``build``, it never crosses the native boundary. The serializer
drops it (see ``bridge/serializer.py``); the device receives ``item_count`` plus
the materialized window children and renders natively (Compose ``LazyColumn``).

These widgets declare **no static children** (``child_field_names`` is empty), but
they are **not leaves**: ``child_nodes()`` materializes the current visible window
on the fly. The window is ``window`` when set (the application slides it in
response to a :class:`~tempestroid.widgets.events.ScrollEvent` via
:meth:`~tempestroid.core.state.App.slide_window`), otherwise the initial default
``[0, min(window_size, item_count)]``. Each materialized item is keyed by its
**absolute index** (``str(index)``), so a window slide reduces — through the
shared reconciler's keyed diff (A2) — to a minimal remove/reorder/insert sequence.

This is what makes the *first* mount non-empty: ``build`` calls ``child_nodes``,
which materializes ``window_size`` items immediately, so the device renders
content on the initial mount without waiting for a scroll event. Virtualization is
preserved: only the window is ever built, never all ``item_count`` items.

Because ``item_builder`` is a Python callable that materializes a widget on the
*same* thread as ``build``, it never crosses the native boundary. The serializer
drops it (see ``bridge/serializer.py``); the device receives ``item_count`` plus
the materialized window children and renders natively (Compose ``LazyColumn``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, ClassVar, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema

from tempestweb._core.widgets.base import (
    EndReachedHandler,
    RefreshHandler,
    ScrollHandler,
    Widget,
)
from tempestweb._core.widgets.events import (
    EndReachedEvent,
    Event,
    RefreshEvent,
    ScrollEvent,
)

__all__ = [
    "DEFAULT_WINDOW_SIZE",
    "SectionHeader",
    "LazyColumn",
    "LazyRow",
    "LazyGrid",
    "SectionList",
    "RefreshControl",
]

#: The default number of items materialized into the initial visible window when
#: a list does not declare an explicit :attr:`window`. Keeps the first mount cheap
#: (the device renders this many items, not ``item_count``) while still showing
#: content immediately.
DEFAULT_WINDOW_SIZE: int = 20

_BUILDER_SCHEMA: dict[str, str] = {
    "type": "string",
    "title": "ItemBuilder",
    "description": "python-side widget factory; not serialized over the boundary",
}


def _resolve_window(
    window: tuple[int, int] | None,
    window_size: int,
    item_count: int,
) -> tuple[int, int]:
    """Resolve the visible ``[start, end)`` window, clamped to ``item_count``.

    When ``window`` is set (the application slid it on a scroll event) it is used
    verbatim after clamping; otherwise the default initial window
    ``[0, min(window_size, item_count)]`` materializes — this is what gives the
    first mount content.

    Args:
        window: The explicit window override, or ``None`` for the initial default.
        window_size: The initial window size when no override is set.
        item_count: The total number of items (the window is clamped to it).

    Returns:
        A clamped, non-empty-where-possible ``(start, end)`` pair with
        ``0 <= start <= end <= item_count``.
    """
    if window is None:
        start, end = 0, min(window_size, item_count)
    else:
        start, end = window
    start = max(0, min(start, item_count))
    end = max(start, min(end, item_count))
    return start, end


def _materialize_items(
    item_builder: Callable[[int], Widget],
    start: int,
    end: int,
    key_prefix: str = "",
) -> list[Widget]:
    """Materialize the window ``[start, end)`` into keyed item widgets.

    Each item is keyed by its absolute index (optionally prefixed for sections),
    so the reconciler's keyed diff turns a window slide into a minimal
    remove/reorder/insert sequence.

    Args:
        item_builder: The factory building the item widget at an absolute index.
        start: The first visible index (inclusive).
        end: The one-past-last visible index (exclusive).
        key_prefix: An optional key namespace (used by :class:`SectionList` to
            keep section-local item keys globally unique).

    Returns:
        The materialized, keyed item widgets in window order.
    """
    return [
        item_builder(index).model_copy(update={"key": f"{key_prefix}{index}"})
        for index in range(start, end)
    ]


#: An ``item_builder(index) -> Widget`` factory. Like an event handler, it is a
#: live Python callable that never crosses the native boundary, so it carries a
#: ``WithJsonSchema`` placeholder for introspection (a bare ``Callable`` has no
#: JSON-schema representation) and is dropped by the serializer.
ItemBuilder: TypeAlias = Annotated[
    Callable[[int], Widget],
    WithJsonSchema(_BUILDER_SCHEMA),
]

#: A ``header_builder() -> Widget`` factory for a :class:`SectionHeader`. Same
#: contract as :data:`ItemBuilder` but zero-argument.
HeaderBuilder: TypeAlias = Annotated[
    Callable[[], Widget],
    WithJsonSchema(_BUILDER_SCHEMA),
]


def _empty_sections() -> list[SectionHeader]:
    """Provide a fresh, typed empty section list for the default factory.

    Returns:
        A new empty list of section headers.
    """
    return []


class SectionHeader(BaseModel):
    """One section of a :class:`SectionList`: a header plus virtualized items.

    A section is *not* a widget — it is a frozen value object describing how to
    build a section's sticky header and its items. The ``header_builder`` and
    ``item_builder`` callables are Python factories that live only on the Python
    side; they never cross the native boundary (the serializer drops them).

    Attributes:
        title: A stable label for the section (used as a key and for the header).
        item_count: The number of items in this section.
        item_builder: Factory building the item widget at a section-local index.
        header_builder: Factory building this section's sticky header widget.
        window_size: The number of items materialized into this section's initial
            window when :attr:`window` is unset.
        window: The current visible ``[start, end)`` window for this section, or
            ``None`` to use the initial default. The application slides it on a
            scroll event by replacing the (frozen) section via ``model_copy``.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    title: str = Field(
        description="A stable label for the section (used as a key and for the header)."
    )
    item_count: int = Field(description="The number of items in this section.")
    item_builder: ItemBuilder = Field(
        description="Factory building the item widget at a section-local index."
    )
    header_builder: HeaderBuilder = Field(
        description="Factory building this section's sticky header widget."
    )
    window_size: int = Field(
        default=DEFAULT_WINDOW_SIZE,
        description="The number of items materialized into this section's initial "
        "window when :attr:`window` is unset.",
    )
    window: tuple[int, int] | None = Field(
        default=None,
        description="The current visible ``[start, end)`` window for this section, or "
        "``None`` to use the initial default. The application slides it on a scroll "
        "event by replacing the (frozen) section via ``model_copy``.",
    )

    def materialize(self) -> list[Widget]:
        """Materialize this section's header plus its visible item window.

        The header is keyed ``"sec:<title>:header"`` and each item
        ``"sec:<title>:<index>"`` so every materialized child of a
        :class:`SectionList` carries a globally unique key for the keyed diff.

        Returns:
            The header widget followed by the section's windowed items.
        """
        header = self.header_builder().model_copy(
            update={"key": f"sec:{self.title}:header"}
        )
        start, end = _resolve_window(self.window, self.window_size, self.item_count)
        items = _materialize_items(
            self.item_builder, start, end, key_prefix=f"sec:{self.title}:"
        )
        return [header, *items]


class LazyColumn(Widget):
    """A vertically virtualized list (Compose ``LazyColumn``).

    Declares an ``item_count`` and an ``item_builder`` instead of materialized
    children. Only the visible window is built into the IR. Emits
    :class:`~tempestroid.widgets.events.ScrollEvent` as it scrolls,
    :class:`~tempestroid.widgets.events.RefreshEvent` on pull-to-refresh, and
    :class:`~tempestroid.widgets.events.EndReachedEvent` when scrolling past
    ``end_reached_threshold``.

    Attributes:
        item_count: The total number of items in the list.
        item_builder: Factory building the item widget at a given index. Lives
            only on the Python side; never serialized over the boundary.
        window_size: The number of items materialized into the initial window
            when :attr:`window` is unset (so the first mount has content).
        window: The current visible ``[start, end)`` window, or ``None`` to use
            the initial default. The application slides this on a scroll event.
        end_reached_threshold: The fraction ``0..1`` of total scroll at which
            :attr:`on_end_reached` fires.
        refreshing: Whether the pull-to-refresh spinner is active.
        on_scroll: Optional handler for scroll events.
        on_refresh: Optional handler for pull-to-refresh.
        on_end_reached: Optional handler fired near the end of the list.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {
        "on_scroll": ScrollEvent,
        "on_refresh": RefreshEvent,
        "on_end_reached": EndReachedEvent,
    }

    child_field_names: ClassVar[frozenset[str]] = frozenset()

    item_count: int = Field(description="The total number of items in the list.")
    item_builder: ItemBuilder = Field(
        description="Factory building the item widget at a given index. Lives only on "
        "the Python side; never serialized over the boundary.",
    )
    window_size: int = Field(
        default=DEFAULT_WINDOW_SIZE,
        description="The number of items materialized into the initial window when "
        ":attr:`window` is unset (so the first mount has content).",
    )
    window: tuple[int, int] | None = Field(
        default=None,
        description="The current visible ``[start, end)`` window, or ``None`` to use "
        "the initial default. The application slides this on a scroll event.",
    )
    end_reached_threshold: float = Field(
        default=0.8,
        description="The fraction ``0..1`` of total scroll at which "
        ":attr:`on_end_reached` fires.",
    )
    refreshing: bool = Field(
        default=False, description="Whether the pull-to-refresh spinner is active."
    )
    on_scroll: ScrollHandler | None = Field(
        default=None, description="Optional handler for scroll events."
    )
    on_refresh: RefreshHandler | None = Field(
        default=None, description="Optional handler for pull-to-refresh."
    )
    on_end_reached: EndReachedHandler | None = Field(
        default=None, description="Optional handler fired near the end of the list."
    )

    def child_nodes(self) -> list[Widget]:
        """Materialize the current visible window into keyed item widgets.

        Returns:
            The items in the resolved window, each keyed by absolute index.
        """
        start, end = _resolve_window(self.window, self.window_size, self.item_count)
        return _materialize_items(self.item_builder, start, end)


class LazyRow(Widget):
    """A horizontally virtualized list (Compose ``LazyRow``).

    The horizontal analogue of :class:`LazyColumn`: identical contract, items
    laid out and scrolled left-to-right.

    Attributes:
        item_count: The total number of items in the list.
        item_builder: Factory building the item widget at a given index. Lives
            only on the Python side; never serialized over the boundary.
        window_size: The number of items materialized into the initial window
            when :attr:`window` is unset (so the first mount has content).
        window: The current visible ``[start, end)`` window, or ``None`` to use
            the initial default. The application slides this on a scroll event.
        end_reached_threshold: The fraction ``0..1`` of total scroll at which
            :attr:`on_end_reached` fires.
        refreshing: Whether the pull-to-refresh spinner is active.
        on_scroll: Optional handler for scroll events.
        on_refresh: Optional handler for pull-to-refresh.
        on_end_reached: Optional handler fired near the end of the list.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {
        "on_scroll": ScrollEvent,
        "on_refresh": RefreshEvent,
        "on_end_reached": EndReachedEvent,
    }

    child_field_names: ClassVar[frozenset[str]] = frozenset()

    item_count: int = Field(description="The total number of items in the list.")
    item_builder: ItemBuilder = Field(
        description="Factory building the item widget at a given index. Lives only on "
        "the Python side; never serialized over the boundary.",
    )
    window_size: int = Field(
        default=DEFAULT_WINDOW_SIZE,
        description="The number of items materialized into the initial window when "
        ":attr:`window` is unset (so the first mount has content).",
    )
    window: tuple[int, int] | None = Field(
        default=None,
        description="The current visible ``[start, end)`` window, or ``None`` to use "
        "the initial default. The application slides this on a scroll event.",
    )
    end_reached_threshold: float = Field(
        default=0.8,
        description="The fraction ``0..1`` of total scroll at which "
        ":attr:`on_end_reached` fires.",
    )
    refreshing: bool = Field(
        default=False, description="Whether the pull-to-refresh spinner is active."
    )
    on_scroll: ScrollHandler | None = Field(
        default=None, description="Optional handler for scroll events."
    )
    on_refresh: RefreshHandler | None = Field(
        default=None, description="Optional handler for pull-to-refresh."
    )
    on_end_reached: EndReachedHandler | None = Field(
        default=None, description="Optional handler fired near the end of the list."
    )

    def child_nodes(self) -> list[Widget]:
        """Materialize the current visible window into keyed item widgets.

        Returns:
            The items in the resolved window, each keyed by absolute index.
        """
        start, end = _resolve_window(self.window, self.window_size, self.item_count)
        return _materialize_items(self.item_builder, start, end)


class LazyGrid(Widget):
    """A virtualized grid (Compose ``LazyVerticalGrid``).

    Lays virtualized items out in a fixed number of ``columns``, scrolling
    vertically. Has no pull-to-refresh (use a wrapping :class:`RefreshControl`).

    Attributes:
        item_count: The total number of items in the grid.
        item_builder: Factory building the item widget at a given index. Lives
            only on the Python side; never serialized over the boundary.
        columns: The number of grid columns.
        window_size: The number of items materialized into the initial window
            when :attr:`window` is unset (so the first mount has content).
        window: The current visible ``[start, end)`` window, or ``None`` to use
            the initial default. The application slides this on a scroll event.
        end_reached_threshold: The fraction ``0..1`` of total scroll at which
            :attr:`on_end_reached` fires.
        on_scroll: Optional handler for scroll events.
        on_end_reached: Optional handler fired near the end of the grid.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {
        "on_scroll": ScrollEvent,
        "on_end_reached": EndReachedEvent,
    }

    child_field_names: ClassVar[frozenset[str]] = frozenset()

    item_count: int = Field(description="The total number of items in the grid.")
    item_builder: ItemBuilder = Field(
        description="Factory building the item widget at a given index. Lives only on "
        "the Python side; never serialized over the boundary.",
    )
    columns: int = Field(default=2, description="The number of grid columns.")
    window_size: int = Field(
        default=DEFAULT_WINDOW_SIZE,
        description="The number of items materialized into the initial window when "
        ":attr:`window` is unset (so the first mount has content).",
    )
    window: tuple[int, int] | None = Field(
        default=None,
        description="The current visible ``[start, end)`` window, or ``None`` to use "
        "the initial default. The application slides this on a scroll event.",
    )
    end_reached_threshold: float = Field(
        default=0.8,
        description="The fraction ``0..1`` of total scroll at which "
        ":attr:`on_end_reached` fires.",
    )
    on_scroll: ScrollHandler | None = Field(
        default=None, description="Optional handler for scroll events."
    )
    on_end_reached: EndReachedHandler | None = Field(
        default=None, description="Optional handler fired near the end of the grid."
    )

    def child_nodes(self) -> list[Widget]:
        """Materialize the current visible window into keyed item widgets.

        Returns:
            The items in the resolved window, each keyed by absolute index.
        """
        start, end = _resolve_window(self.window, self.window_size, self.item_count)
        return _materialize_items(self.item_builder, start, end)


class SectionList(Widget):
    """A sectioned virtualized list with sticky section headers.

    Each :class:`SectionHeader` declares a header plus its own virtualized
    items. The renderer renders the headers sticky (Compose ``stickyHeader``;
    the Qt simulator pins a label above the scroll area).

    Attributes:
        sections: The ordered sections to render.
        end_reached_threshold: The fraction ``0..1`` of total scroll at which
            :attr:`on_end_reached` fires.
        on_scroll: Optional handler for scroll events.
        on_end_reached: Optional handler fired near the end of the list.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {
        "on_scroll": ScrollEvent,
        "on_end_reached": EndReachedEvent,
    }

    child_field_names: ClassVar[frozenset[str]] = frozenset()

    sections: list[SectionHeader] = Field(
        description="The ordered sections to render.", default_factory=_empty_sections
    )
    end_reached_threshold: float = Field(
        default=0.8,
        description="The fraction ``0..1`` of total scroll at which "
        ":attr:`on_end_reached` fires.",
    )
    on_scroll: ScrollHandler | None = Field(
        default=None, description="Optional handler for scroll events."
    )
    on_end_reached: EndReachedHandler | None = Field(
        default=None, description="Optional handler fired near the end of the list."
    )

    def child_nodes(self) -> list[Widget]:
        """Materialize each section's header and visible item window in order.

        Returns:
            The flattened header + windowed items of every section, keyed for the
            reconciler's keyed diff.
        """
        children: list[Widget] = []
        for section in self.sections:
            children.extend(section.materialize())
        return children


class RefreshControl(Widget):
    """A standalone pull-to-refresh wrapper (Compose ``PullToRefreshBox``).

    Wraps content with a pull-to-refresh gesture, decoupled from a virtualized
    list — use it around any scrollable content. The content is supplied by the
    renderer (the widget itself carries only the refresh contract); see the
    renderer's ``RefreshControl`` case for how content is wired.

    Attributes:
        refreshing: Whether the pull-to-refresh spinner is active.
        on_refresh: Optional handler for pull-to-refresh.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {
        "on_refresh": RefreshEvent,
    }

    child_field_names: ClassVar[frozenset[str]] = frozenset()

    refreshing: bool = Field(
        default=False, description="Whether the pull-to-refresh spinner is active."
    )
    on_refresh: RefreshHandler | None = Field(
        default=None, description="Optional handler for pull-to-refresh."
    )
