"""Text leaf widget."""

from __future__ import annotations

from pydantic import Field

from tempestweb._core.widgets.base import Widget

__all__ = ["Text"]


class Text(Widget):
    """A run of text.

    Attributes:
        content: The string to display.
    """

    content: str = Field(description="The string to display.")
