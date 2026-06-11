"""Overlay and feedback widgets: dialogs, sheets, toasts, menus, tooltips.

These widgets are pushed onto the app's floating overlay layer (the ``overlays``
of a :class:`~tempestroid.core.ir.Scene`) rather than nested in the screen tree.
The app's imperative overlay API (``show_dialog`` / ``show_sheet`` / ``toast`` /
``show_menu``) wraps these and manages their lifetime; a renderer realizes each
as the platform-native surface (Qt ``QDialog``/``QMenu``; Compose
``AlertDialog``/``ModalBottomSheet``/``DropdownMenu``).

A dismiss-bearing overlay (``Dialog``/``BottomSheet``/``Popover``) declares an
``on_dismiss`` handler validated against :class:`DismissEvent`; a selection
overlay (``Menu``/``ActionSheet``) declares ``on_select`` validated against
:class:`MenuSelectEvent`. :class:`MenuItem` is a frozen, JSON-serializable value
model (not a widget) so menu items cross the bridge as plain data.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from tempestweb._core.widgets.base import (
    DismissHandler,
    MenuSelectHandler,
    Widget,
)
from tempestweb._core.widgets.events import DismissEvent, Event, MenuSelectEvent

__all__ = [
    "Dialog",
    "BottomSheet",
    "Toast",
    "Tooltip",
    "Menu",
    "MenuItem",
    "Popover",
    "ActionSheet",
]


def _empty_children() -> list[Widget]:
    """Provide a fresh, typed empty child list for default factories.

    Returns:
        A new empty list of widgets.
    """
    return []


class MenuItem(BaseModel):
    """A single selectable entry in a :class:`Menu` or :class:`ActionSheet`.

    A frozen value model (not a widget): it carries only JSON-serializable data
    so it crosses the device bridge as a plain dict.

    Attributes:
        label: The display label.
        value: The stable value reported by :class:`MenuSelectEvent` on select.
        icon: Optional icon name to render alongside the label.
    """

    model_config = ConfigDict(frozen=True)

    label: str = Field(description="The display label.")
    value: str = Field(
        description="The stable value reported by :class:`MenuSelectEvent` on select."
    )
    icon: str | None = Field(
        default=None, description="Optional icon name to render alongside the label."
    )


def _empty_items() -> list[MenuItem]:
    """Provide a fresh, typed empty item list for default factories.

    Returns:
        A new empty list of menu items.
    """
    return []


class Dialog(Widget):
    """A modal dialog floated above the screen, optionally with a title.

    Attributes:
        title: Optional dialog title.
        children: The dialog body widgets.
        on_dismiss: Handler invoked when the user dismisses the dialog (barrier
            tap or system back), validated against :class:`DismissEvent`.
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"children"})
    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_dismiss": DismissEvent}

    title: str | None = Field(default=None, description="Optional dialog title.")
    children: list[Widget] = Field(
        description="The dialog body widgets.", default_factory=_empty_children
    )
    on_dismiss: DismissHandler | None = Field(
        default=None,
        description="Handler invoked when the user dismisses the dialog (barrier tap "
        "or system back), validated against :class:`DismissEvent`.",
    )

    def child_nodes(self) -> list[Widget]:
        """Return the dialog's body widgets.

        Returns:
            The ordered child widgets.
        """
        return self.children


class BottomSheet(Widget):
    """A sheet that slides up from the bottom edge of the screen.

    Attributes:
        children: The sheet body widgets.
        on_dismiss: Handler invoked when the user dismisses the sheet (barrier
            tap or swipe-down), validated against :class:`DismissEvent`.
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"children"})
    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_dismiss": DismissEvent}

    children: list[Widget] = Field(
        description="The sheet body widgets.", default_factory=_empty_children
    )
    on_dismiss: DismissHandler | None = Field(
        default=None,
        description="Handler invoked when the user dismisses the sheet (barrier tap or "
        "swipe-down), validated against :class:`DismissEvent`.",
    )

    def child_nodes(self) -> list[Widget]:
        """Return the sheet's body widgets.

        Returns:
            The ordered child widgets.
        """
        return self.children


class Toast(Widget):
    """A transient message that appears briefly then auto-dismisses.

    The app's :meth:`~tempestroid.core.state.App.toast` schedules the
    auto-dismiss on the loop; ``duration_s`` is also carried to the renderer so a
    device can mirror the timing for snappy visual feedback.

    Attributes:
        message: The text to display.
        duration_s: How long the toast stays visible, in seconds.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {}

    message: str = Field(description="The text to display.")
    duration_s: float = Field(
        default=2.5, description="How long the toast stays visible, in seconds."
    )


class Tooltip(Widget):
    """A small hint label shown next to an anchored child.

    Attributes:
        message: The hint text.
        child: Optional widget the tooltip annotates.
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"child"})
    event_schemas: ClassVar[dict[str, type[Event]]] = {}

    message: str = Field(description="The hint text.")
    child: Widget | None = Field(
        default=None, description="Optional widget the tooltip annotates."
    )

    def child_nodes(self) -> list[Widget]:
        """Return the annotated child, if any.

        Returns:
            A single-element list with the child, or an empty list.
        """
        return [self.child] if self.child is not None else []


class Menu(Widget):
    """A list of selectable items anchored to a widget.

    Attributes:
        items: The selectable entries.
        anchor: Optional ``key`` of the widget the menu anchors to.
        on_select: Handler invoked on item selection, validated against
            :class:`MenuSelectEvent`.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_select": MenuSelectEvent}

    items: list[MenuItem] = Field(
        description="The selectable entries.", default_factory=_empty_items
    )
    anchor: str | None = Field(
        default=None, description="Optional ``key`` of the widget the menu anchors to."
    )
    on_select: MenuSelectHandler | None = Field(
        default=None,
        description="Handler invoked on item selection, validated against "
        ":class:`MenuSelectEvent`.",
    )


class Popover(Widget):
    """A floating panel anchored near a widget, dismissible by tapping away.

    Attributes:
        child: Optional widget shown inside the popover.
        anchor: Optional ``key`` of the widget the popover anchors to.
        on_dismiss: Handler invoked on dismiss, validated against
            :class:`DismissEvent`.
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"child"})
    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_dismiss": DismissEvent}

    child: Widget | None = Field(
        default=None, description="Optional widget shown inside the popover."
    )
    anchor: str | None = Field(
        default=None,
        description="Optional ``key`` of the widget the popover anchors to.",
    )
    on_dismiss: DismissHandler | None = Field(
        default=None,
        description="Handler invoked on dismiss, validated against "
        ":class:`DismissEvent`.",
    )

    def child_nodes(self) -> list[Widget]:
        """Return the popover's child, if any.

        Returns:
            A single-element list with the child, or an empty list.
        """
        return [self.child] if self.child is not None else []


class ActionSheet(Widget):
    """A bottom-anchored list of actions, optionally titled.

    Attributes:
        title: Optional sheet title.
        items: The selectable actions.
        on_select: Handler invoked on action selection, validated against
            :class:`MenuSelectEvent`.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_select": MenuSelectEvent}

    title: str | None = Field(default=None, description="Optional sheet title.")
    items: list[MenuItem] = Field(
        description="The selectable actions.", default_factory=_empty_items
    )
    on_select: MenuSelectHandler | None = Field(
        default=None,
        description="Handler invoked on action selection, validated against "
        ":class:`MenuSelectEvent`.",
    )
