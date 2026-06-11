"""Base widget node and event-handler typing.

A widget tree *is* the intermediate representation (IR): a declarative, typed,
serializable tree of Pydantic models. The reconciler (phase A2) diffs two such
trees and emits patches; the leaf renderers apply those patches. Everything a
renderer needs to walk the tree lives here, so the rest of the system can stay
backend-agnostic.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, ClassVar, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema

from tempestweb._core.style import Style
from tempestweb._core.widgets.events import (
    DateChangeEvent,
    DismissEvent,
    DragEvent,
    EndReachedEvent,
    Event,
    FileSelectEvent,
    LongPressEvent,
    MenuSelectEvent,
    PageChangeEvent,
    PanEvent,
    RangeChangeEvent,
    RefreshEvent,
    ReorderEvent,
    RouteChangeEvent,
    ScaleEvent,
    ScrollEvent,
    SelectEvent,
    SlideEvent,
    SubmitEvent,
    SwipeEvent,
    TapEvent,
    TextChangeEvent,
    TimeChangeEvent,
    ToggleEvent,
    ValidationEvent,
)

__all__ = [
    "Semantics",
    "EventHandler",
    "TextChangeHandler",
    "ToggleHandler",
    "SlideHandler",
    "DateChangeHandler",
    "FileSelectHandler",
    "TapHandler",
    "LongPressHandler",
    "SwipeHandler",
    "RouteChangeHandler",
    "ScrollHandler",
    "RefreshHandler",
    "EndReachedHandler",
    "DismissHandler",
    "MenuSelectHandler",
    "PanHandler",
    "ScaleHandler",
    "DragHandler",
    "ReorderHandler",
    "SelectHandler",
    "TimeChangeHandler",
    "RangeChangeHandler",
    "SubmitHandler",
    "ValidationHandler",
    "PageChangeHandler",
    "Widget",
    "Component",
    "handler_accepts_event",
]

_POSITIONAL_KINDS = (
    inspect.Parameter.POSITIONAL_ONLY,
    inspect.Parameter.POSITIONAL_OR_KEYWORD,
    inspect.Parameter.VAR_POSITIONAL,
)


def handler_accepts_event(handler: Callable[..., Any]) -> bool:
    """Whether ``handler`` accepts a positional event argument.

    Value-bearing widgets pass the validated typed event to their handler, but
    only when the handler is declared to accept one — a zero-argument handler is
    called bare. Both the device bridge registry and the Qt renderer use this to
    agree on the calling convention.

    Args:
        handler: The handler callable to inspect.

    Returns:
        ``True`` if the handler can take one positional argument, ``False`` if it
        must be called with none (or its signature cannot be inspected).
    """
    try:
        params = inspect.signature(handler).parameters
    except (ValueError, TypeError):
        return False
    return any(p.kind in _POSITIONAL_KINDS for p in params.values())


_RawHandler: TypeAlias = Callable[[], Any] | Callable[[], Awaitable[Any]]

#: A zero-argument event callback. Async-first: handlers may be plain functions
#: or coroutine functions, and the runtime schedules awaitables on the loop. The
#: ``WithJsonSchema`` annotation lets introspection emit a schema for widgets
#: that carry handlers (a raw ``Callable`` has no JSON-schema representation).
EventHandler: TypeAlias = Annotated[
    _RawHandler,
    WithJsonSchema(
        {
            "type": "string",
            "title": "EventHandler",
            "description": "client-side handler; not serialized over the boundary",
        }
    ),
]

_HANDLER_SCHEMA: dict[str, str] = {
    "type": "string",
    "title": "EventHandler",
    "description": "client-side handler; not serialized over the boundary",
}

#: A value-carrying event callback: receives the validated typed event (so the
#: handler can read e.g. ``event.value``) or, for convenience, may be declared
#: zero-argument when the value is not needed. The runtime passes the event only
#: when the handler accepts a positional argument (see the bridge registry and
#: the Qt renderer); both call sites agree on this contract.
TextChangeHandler: TypeAlias = Annotated[
    Callable[[TextChangeEvent], Any]
    | Callable[[TextChangeEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
ToggleHandler: TypeAlias = Annotated[
    Callable[[ToggleEvent], Any]
    | Callable[[ToggleEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
SlideHandler: TypeAlias = Annotated[
    Callable[[SlideEvent], Any] | Callable[[SlideEvent], Awaitable[Any]] | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
DateChangeHandler: TypeAlias = Annotated[
    Callable[[DateChangeEvent], Any]
    | Callable[[DateChangeEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
FileSelectHandler: TypeAlias = Annotated[
    Callable[[FileSelectEvent], Any]
    | Callable[[FileSelectEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
TapHandler: TypeAlias = Annotated[
    Callable[[TapEvent], Any] | Callable[[TapEvent], Awaitable[Any]] | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
LongPressHandler: TypeAlias = Annotated[
    Callable[[LongPressEvent], Any]
    | Callable[[LongPressEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
SwipeHandler: TypeAlias = Annotated[
    Callable[[SwipeEvent], Any] | Callable[[SwipeEvent], Awaitable[Any]] | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
RouteChangeHandler: TypeAlias = Annotated[
    Callable[[RouteChangeEvent], Any]
    | Callable[[RouteChangeEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
ScrollHandler: TypeAlias = Annotated[
    Callable[[ScrollEvent], Any]
    | Callable[[ScrollEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
RefreshHandler: TypeAlias = Annotated[
    Callable[[RefreshEvent], Any]
    | Callable[[RefreshEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
EndReachedHandler: TypeAlias = Annotated[
    Callable[[EndReachedEvent], Any]
    | Callable[[EndReachedEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
DismissHandler: TypeAlias = Annotated[
    Callable[[DismissEvent], Any]
    | Callable[[DismissEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
MenuSelectHandler: TypeAlias = Annotated[
    Callable[[MenuSelectEvent], Any]
    | Callable[[MenuSelectEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
PanHandler: TypeAlias = Annotated[
    Callable[[PanEvent], Any] | Callable[[PanEvent], Awaitable[Any]] | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
ScaleHandler: TypeAlias = Annotated[
    Callable[[ScaleEvent], Any] | Callable[[ScaleEvent], Awaitable[Any]] | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
DragHandler: TypeAlias = Annotated[
    Callable[[DragEvent], Any] | Callable[[DragEvent], Awaitable[Any]] | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
ReorderHandler: TypeAlias = Annotated[
    Callable[[ReorderEvent], Any]
    | Callable[[ReorderEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
SelectHandler: TypeAlias = Annotated[
    Callable[[SelectEvent], Any]
    | Callable[[SelectEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
TimeChangeHandler: TypeAlias = Annotated[
    Callable[[TimeChangeEvent], Any]
    | Callable[[TimeChangeEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
RangeChangeHandler: TypeAlias = Annotated[
    Callable[[RangeChangeEvent], Any]
    | Callable[[RangeChangeEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
SubmitHandler: TypeAlias = Annotated[
    Callable[[SubmitEvent], Any]
    | Callable[[SubmitEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
ValidationHandler: TypeAlias = Annotated[
    Callable[[ValidationEvent], Any]
    | Callable[[ValidationEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
PageChangeHandler: TypeAlias = Annotated[
    Callable[[PageChangeEvent], Any]
    | Callable[[PageChangeEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]


class Semantics(BaseModel):
    """Accessibility metadata propagated to both renderers.

    Attached to any :class:`Widget` via :attr:`Widget.semantics`; the leaf
    renderers map it to the platform's accessibility surface (Qt ``QAccessible``
    name/description; Compose ``Modifier.semantics { contentDescription; role }``)
    so screen readers (TalkBack, Qt AT) can describe the node. Frozen so the
    reconciler diffs it by value.

    Attributes:
        label: The accessible label (``contentDescription`` / accessible name).
        role: The accessible role hint (e.g. ``"button"``, ``"image"``,
            ``"heading"``); the renderer maps it to its native role enum.
        hint: An accessibility hint / tooltip describing what the node does.
    """

    model_config = ConfigDict(frozen=True)

    label: str | None = Field(
        default=None,
        description="The accessible label (``contentDescription`` / accessible name).",
    )
    role: str | None = Field(
        default=None,
        description='The accessible role hint (e.g. ``"button"``, ``"image"``, '
        '``"heading"``); the renderer maps it to its native role enum.',
    )
    hint: str | None = Field(
        default=None,
        description="An accessibility hint / tooltip describing what the node does.",
    )


class Widget(BaseModel):
    """Base class for every node in the declarative UI tree.

    Attributes:
        key: Optional stable identity used by the reconciler to match nodes
            across rebuilds (analogous to a React ``key``).
        style: Optional inline style for this node.
        semantics: Optional accessibility metadata for this node, propagated to
            both renderers and to :func:`~tempestroid.introspect`.
        focusable: Whether this node accepts focus. ``None`` keeps the widget's
            natural focusability (e.g. a button is focusable, a label is not).
        focus_order: The node's explicit focus/tab order; ``None`` uses the
            natural traversal order.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    #: Names of fields that hold child widgets. Layout widgets override this so
    #: the reconciler can split "children" from renderable props generically,
    #: without inspecting concrete field types. Leaf widgets keep it empty.
    child_field_names: ClassVar[frozenset[str]] = frozenset()

    #: Maps a handler prop name to the event type its payload is validated into
    #: at the boundary. Used by introspection to publish each widget's event
    #: contract. Widgets that emit events override this.
    event_schemas: ClassVar[dict[str, type[Event]]] = {}

    key: str | None = None
    style: Style | None = None
    semantics: Semantics | None = None
    focusable: bool | None = None
    focus_order: int | None = None

    @property
    def widget_type(self) -> str:
        """The node's type tag, used by renderers and diffing.

        Returns:
            The concrete class name (e.g. ``"Text"``, ``"Column"``).
        """
        return type(self).__name__

    def child_nodes(self) -> list[Widget]:
        """Return this node's children in order.

        Leaf widgets return an empty list. Container/layout widgets override
        this to expose their children, giving the reconciler a uniform way to
        walk any tree regardless of how children are stored.

        Returns:
            The ordered child widgets (empty for leaf nodes).
        """
        return []


class Component(Widget):
    """A composite widget that lowers to a primitive widget tree.

    A component is *not* part of the serialized IR. The reconciler expands it via
    :meth:`render` into primitive widgets (``Text`` / ``Row`` / ``Column`` /
    ``Container`` / inputs / …) **before** diffing, so neither leaf renderer (Qt
    or Compose) ever sees a component — only the tree it produces. This keeps
    higher-level, reusable building blocks (app bars, scaffolds, navigation bars)
    fully renderer-agnostic and device-ready: they work anywhere a primitive
    works, with zero renderer changes.

    Subclasses declare their inputs as Pydantic fields and implement
    :meth:`render`; they may read ``self.style`` / ``self.key`` and fold them into
    the returned tree. ``render`` runs on the same thread as ``build`` (desktop
    *and* device), so it may close over plain Python callables (e.g. a navigation
    item's ``on_select``) and wire them into the primitives it emits.
    """

    def render(self) -> Widget:
        """Lower this component into a primitive widget tree.

        Returns:
            The widget tree this component expands to (may itself contain further
            components, which are expanded recursively).

        Raises:
            NotImplementedError: If a subclass does not implement it.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement render()")
