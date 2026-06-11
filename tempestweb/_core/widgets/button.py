"""Button leaf widget."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from tempestweb._core.widgets.base import EventHandler, Widget
from tempestweb._core.widgets.events import Event, TapEvent

__all__ = ["Button"]


class Button(Widget):
    """A tappable button.

    Attributes:
        label: The text shown on the button.
        on_click: Optional handler invoked on tap. May be sync or ``async``;
            the runtime schedules awaitables on the event loop.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_click": TapEvent}

    label: str = Field(description="The text shown on the button.")
    on_click: EventHandler | None = Field(
        default=None,
        description="Optional handler invoked on tap. May be sync or ``async``; the "
        "runtime schedules awaitables on the event loop.",
    )
