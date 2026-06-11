"""Gesture detection: wrap a child and report taps, drags, pinches and reorders.

``GestureDetector`` is the framework's base touch-gesture primitive. It is a
single-child container that renders its child untouched but watches the pointer
over it, turning press/drag/release sequences into typed events:

* ``on_tap`` / ``on_double_tap`` → :class:`~tempestroid.widgets.events.TapEvent`
* ``on_long_press`` → :class:`~tempestroid.widgets.events.LongPressEvent`
* ``on_swipe`` → :class:`~tempestroid.widgets.events.SwipeEvent` (carrying the
  dominant cardinal direction and total travel)

The advanced gesture widgets specialize that contract for richer interactions:

* :class:`PanHandler` — continuous drag + fling velocity
  (:class:`~tempestroid.widgets.events.PanEvent`).
* :class:`ScaleHandler` — pinch scale + rotation
  (:class:`~tempestroid.widgets.events.ScaleEvent`) and a double tap.
* :class:`DoubleTapHandler` — a double tap only.
* :class:`Draggable` / :class:`DragTarget` — drag-and-drop
  (:class:`~tempestroid.widgets.events.DragEvent`).
* :class:`Dismissible` — swipe-to-dismiss
  (:class:`~tempestroid.widgets.events.DismissEvent`).
* :class:`ReorderableList` — drag-to-reorder
  (:class:`~tempestroid.widgets.events.ReorderEvent`).
* :class:`InteractiveViewer` — pan + zoom
  (:class:`~tempestroid.widgets.events.ScaleEvent`).

Both leaf renderers realize the same contract: Qt via pointer event filters /
``QGraphicsView`` / ``QDrag``, Compose via ``Modifier.pointerInput``
(``detectTransformGestures`` / ``detectDragGesturesAfterLongPress``) /
``SwipeToDismissBox`` / ``graphicsLayer``. Gestures are best wrapped around
non-interactive content (a card, an image, a row of text); a child that consumes
the pointer itself (e.g. a ``Button``) keeps its own handling — a documented v1
limit.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from tempestweb._core.widgets.base import (
    DismissHandler,
    DragHandler,
    LongPressHandler,
    ReorderHandler,
    SwipeHandler,
    TapHandler,
    Widget,
)
from tempestweb._core.widgets.base import (
    PanHandler as PanHandler_T,
)
from tempestweb._core.widgets.base import (
    ScaleHandler as ScaleHandler_T,
)
from tempestweb._core.widgets.events import (
    DismissEvent,
    DragEvent,
    Event,
    LongPressEvent,
    PanEvent,
    ReorderEvent,
    ScaleEvent,
    SwipeDirection,
    SwipeEvent,
    TapEvent,
)


def _empty_children() -> list[Widget]:
    """Build an empty, correctly typed child list for a default factory.

    Returns:
        A fresh empty ``list[Widget]``.
    """
    return []


__all__ = [
    "GestureDetector",
    "PanHandler",
    "ScaleHandler",
    "DoubleTapHandler",
    "Draggable",
    "DragTarget",
    "Dismissible",
    "ReorderableList",
    "InteractiveViewer",
]


class GestureDetector(Widget):
    """A single-child container that reports touch gestures over its child.

    Attributes:
        child: The wrapped widget the gestures are detected over.
        on_tap: Optional handler for a single tap (receives a ``TapEvent``).
        on_double_tap: Optional handler for a double tap (receives a ``TapEvent``).
        on_long_press: Optional handler for a held press past the long-press
            threshold (receives a ``LongPressEvent``).
        on_swipe: Optional handler for a directional swipe (receives a
            ``SwipeEvent``).
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {
        "on_tap": TapEvent,
        "on_double_tap": TapEvent,
        "on_long_press": LongPressEvent,
        "on_swipe": SwipeEvent,
    }
    child_field_names: ClassVar[frozenset[str]] = frozenset({"child"})

    child: Widget | None = Field(
        default=None, description="The wrapped widget the gestures are detected over."
    )
    on_tap: TapHandler | None = Field(
        default=None,
        description="Optional handler for a single tap (receives a ``TapEvent``).",
    )
    on_double_tap: TapHandler | None = Field(
        default=None,
        description="Optional handler for a double tap (receives a ``TapEvent``).",
    )
    on_long_press: LongPressHandler | None = Field(
        default=None,
        description="Optional handler for a held press past the long-press threshold "
        "(receives a ``LongPressEvent``).",
    )
    on_swipe: SwipeHandler | None = Field(
        default=None,
        description="Optional handler for a directional swipe (receives a "
        "``SwipeEvent``).",
    )

    def child_nodes(self) -> list[Widget]:
        """Return the wrapped child, if any.

        Returns:
            A one-element list with the child, or an empty list.
        """
        return [self.child] if self.child is not None else []


class PanHandler(Widget):
    """A single-child container that reports a continuous pan gesture.

    As the pointer drags over the child, the renderer reports per-frame deltas
    and, at release, the fling velocity, as a :class:`PanEvent`.

    Attributes:
        child: The wrapped widget the pan is detected over.
        on_pan: Optional handler for the pan gesture (receives a ``PanEvent``).
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_pan": PanEvent}
    child_field_names: ClassVar[frozenset[str]] = frozenset({"child"})

    child: Widget | None = Field(
        default=None, description="The wrapped widget the pan is detected over."
    )
    on_pan: PanHandler_T | None = Field(
        default=None,
        description="Optional handler for the pan gesture (receives a ``PanEvent``).",
    )

    def child_nodes(self) -> list[Widget]:
        """Return the wrapped child, if any.

        Returns:
            A one-element list with the child, or an empty list.
        """
        return [self.child] if self.child is not None else []


class ScaleHandler(Widget):
    """A single-child container that reports pinch scale/rotation and a double tap.

    Attributes:
        child: The wrapped widget the gestures are detected over.
        on_scale: Optional handler for a pinch (receives a ``ScaleEvent`` with the
            cumulative scale, focal point and rotation).
        on_double_tap: Optional handler for a double tap (receives a ``TapEvent``;
            a common pairing with pinch to reset the zoom).
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {
        "on_scale": ScaleEvent,
        "on_double_tap": TapEvent,
    }
    child_field_names: ClassVar[frozenset[str]] = frozenset({"child"})

    child: Widget | None = Field(
        default=None, description="The wrapped widget the gestures are detected over."
    )
    on_scale: ScaleHandler_T | None = Field(
        default=None,
        description="Optional handler for a pinch (receives a ``ScaleEvent`` with the "
        "cumulative scale, focal point and rotation).",
    )
    on_double_tap: TapHandler | None = Field(
        default=None,
        description="Optional handler for a double tap (receives a ``TapEvent``; a "
        "common pairing with pinch to reset the zoom).",
    )

    def child_nodes(self) -> list[Widget]:
        """Return the wrapped child, if any.

        Returns:
            A one-element list with the child, or an empty list.
        """
        return [self.child] if self.child is not None else []


class DoubleTapHandler(Widget):
    """A single-child container that reports a double tap.

    Attributes:
        child: The wrapped widget the double tap is detected over.
        on_double_tap: Optional handler for a double tap (receives a ``TapEvent``).
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_double_tap": TapEvent}
    child_field_names: ClassVar[frozenset[str]] = frozenset({"child"})

    child: Widget | None = Field(
        default=None, description="The wrapped widget the double tap is detected over."
    )
    on_double_tap: TapHandler | None = Field(
        default=None,
        description="Optional handler for a double tap (receives a ``TapEvent``).",
    )

    def child_nodes(self) -> list[Widget]:
        """Return the wrapped child, if any.

        Returns:
            A one-element list with the child, or an empty list.
        """
        return [self.child] if self.child is not None else []


class Draggable(Widget):
    """A child that can be picked up and dragged onto a :class:`DragTarget`.

    Attributes:
        child: The wrapped widget the user drags.
        drag_data: An opaque label carried to the drop target via the
            ``DragEvent.data`` field, so the target can identify what landed on
            it.
        on_drag: Optional handler fired when the drag finishes (receives a
            ``DragEvent`` with the carried data and the release position).
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_drag": DragEvent}
    child_field_names: ClassVar[frozenset[str]] = frozenset({"child"})

    child: Widget | None = Field(
        default=None, description="The wrapped widget the user drags."
    )
    drag_data: str = Field(
        default="",
        description="An opaque label carried to the drop target via the "
        "``DragEvent.data`` field, so the target can identify what landed on it.",
    )
    on_drag: DragHandler | None = Field(
        default=None,
        description="Optional handler fired when the drag finishes (receives a "
        "``DragEvent`` with the carried data and the release position).",
    )

    def child_nodes(self) -> list[Widget]:
        """Return the wrapped child, if any.

        Returns:
            A one-element list with the child, or an empty list.
        """
        return [self.child] if self.child is not None else []


class DragTarget(Widget):
    """A child that accepts a dropped :class:`Draggable`.

    Attributes:
        child: The wrapped widget that acts as the drop region.
        on_drop: Optional handler fired when a draggable is released over this
            target (receives a ``DragEvent`` carrying the dropped item's data).
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_drop": DragEvent}
    child_field_names: ClassVar[frozenset[str]] = frozenset({"child"})

    child: Widget | None = Field(
        default=None, description="The wrapped widget that acts as the drop region."
    )
    on_drop: DragHandler | None = Field(
        default=None,
        description="Optional handler fired when a draggable is released over this "
        "target (receives a ``DragEvent`` carrying the dropped item's data).",
    )

    def child_nodes(self) -> list[Widget]:
        """Return the wrapped child, if any.

        Returns:
            A one-element list with the child, or an empty list.
        """
        return [self.child] if self.child is not None else []


class Dismissible(Widget):
    """A child that can be swiped away to dismiss it (swipe-to-delete).

    Attributes:
        child: The wrapped widget the dismiss gesture is detected over.
        direction: The swipe direction that triggers the dismiss (defaults to
            :attr:`~tempestroid.widgets.events.SwipeDirection.LEFT`).
        on_dismiss: Optional handler fired once the swipe passes the dismiss
            threshold (receives a ``DismissEvent``; reuses the overlay-dismiss
            event type).
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_dismiss": DismissEvent}
    child_field_names: ClassVar[frozenset[str]] = frozenset({"child"})

    child: Widget | None = Field(
        default=None,
        description="The wrapped widget the dismiss gesture is detected over.",
    )
    direction: SwipeDirection = Field(
        default=SwipeDirection.LEFT,
        description="The swipe direction that triggers the dismiss (defaults to "
        ":attr:`~tempestroid.widgets.events.SwipeDirection.LEFT`).",
    )
    on_dismiss: DismissHandler | None = Field(
        default=None,
        description="Optional handler fired once the swipe passes the dismiss "
        "threshold (receives a ``DismissEvent``; reuses the overlay-dismiss event "
        "type).",
    )

    def child_nodes(self) -> list[Widget]:
        """Return the wrapped child, if any.

        Returns:
            A one-element list with the child, or an empty list.
        """
        return [self.child] if self.child is not None else []


class ReorderableList(Widget):
    """A vertical list whose items can be dragged into a new order.

    The handler typically mutates its backing list
    (``items.insert(to_index, items.pop(from_index))``) and re-renders; a keyed
    child list then diffs to a ``Reorder`` patch (the A2 mechanism), so no new
    patch kind is needed.

    Attributes:
        children: The ordered list items. Prefer stable ``key``s so the keyed
            diff emits a ``Reorder`` rather than positional updates.
        on_reorder: Optional handler fired when an item is dragged to a new slot
            (receives a ``ReorderEvent`` with the source and destination index).
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_reorder": ReorderEvent}
    child_field_names: ClassVar[frozenset[str]] = frozenset({"children"})

    children: list[Widget] = Field(
        description="The ordered list items. Prefer stable ``key``s so the keyed diff "
        "emits a ``Reorder`` rather than positional updates.",
        default_factory=_empty_children,
    )
    on_reorder: ReorderHandler | None = Field(
        default=None,
        description="Optional handler fired when an item is dragged to a new slot "
        "(receives a ``ReorderEvent`` with the source and destination index).",
    )

    def child_nodes(self) -> list[Widget]:
        """Return the list items in order.

        Returns:
            The ordered child widgets (empty when the list has no items).
        """
        return list(self.children)


class InteractiveViewer(Widget):
    """A single-child container the user can pan and zoom (pinch + drag).

    Attributes:
        child: The wrapped widget that is panned and zoomed.
        min_scale: The minimum allowed zoom factor.
        max_scale: The maximum allowed zoom factor.
        on_interaction: Optional handler fired as the view transforms (receives a
            ``ScaleEvent`` with the current scale, focal point and rotation).
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_interaction": ScaleEvent}
    child_field_names: ClassVar[frozenset[str]] = frozenset({"child"})

    child: Widget | None = Field(
        default=None, description="The wrapped widget that is panned and zoomed."
    )
    min_scale: float = Field(
        default=0.5, description="The minimum allowed zoom factor."
    )
    max_scale: float = Field(
        default=4.0, description="The maximum allowed zoom factor."
    )
    on_interaction: ScaleHandler_T | None = Field(
        default=None,
        description="Optional handler fired as the view transforms (receives a "
        "``ScaleEvent`` with the current scale, focal point and rotation).",
    )

    def child_nodes(self) -> list[Widget]:
        """Return the wrapped child, if any.

        Returns:
            A one-element list with the child, or an empty list.
        """
        return [self.child] if self.child is not None else []
