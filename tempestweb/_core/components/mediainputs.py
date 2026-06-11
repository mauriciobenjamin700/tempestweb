"""Media-picker components: image, document and circular profile-photo pickers.

Each lowers to the primitive :class:`~tempestroid.widgets.FilePicker` and
:class:`~tempestroid.widgets.Image` leaves, so they work in both renderers (Qt
and Compose) with no renderer change. Every component exposes a plain ``on_pick``
callable that receives the picked file's URI (the child picker's
:class:`~tempestroid.widgets.FileSelectEvent` ``uri``), so callers never touch
the event object.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import Field

from tempestweb._core.components.base import MUTED, ON_MUTED, merge_style
from tempestweb._core.style import AlignItems, FontWeight, Style
from tempestweb._core.widgets import (
    ClipPath,
    ClipShape,
    Column,
    Component,
    Container,
    FilePicker,
    FileSelectEvent,
    Icon,
    Image,
    ImageFit,
    Text,
    Widget,
)

__all__ = [
    "ImagePicker",
    "DocumentPicker",
    "ImagePicture",
]


def _on_uri(handler: Callable[[str], Any]) -> Callable[[FileSelectEvent], None]:
    """Adapt a URI handler to the picker's typed ``on_select``.

    Args:
        handler: The component's ``on_pick`` callable taking the picked URI.

    Returns:
        A handler taking a :class:`~tempestroid.widgets.FileSelectEvent` and
        forwarding its ``uri`` to ``handler``.
    """

    def adapter(event: FileSelectEvent) -> None:
        handler(event.uri)

    return adapter


class ImagePicker(Component):
    """A labelled image picker with an inline preview of the chosen image.

    Attributes:
        value: The picked image URI (``""`` until one is chosen).
        label: An optional heading shown above the picker (omitted when empty).
        on_pick: Called with the picked image URI on selection.
    """

    value: str = Field(
        default="", description="The picked image URI (empty until one is chosen)."
    )
    label: str = Field(
        default="", description="An optional heading shown above the picker."
    )
    on_pick: Callable[[str], Any] = Field(
        description="Called with the picked image URI on selection."
    )

    def render(self) -> Widget:
        """Lower the image picker into a labelled column.

        Returns:
            A :class:`~tempestroid.widgets.Column` of the optional label, an
            :class:`~tempestroid.widgets.Image` preview (when a URI is set) and a
            :class:`~tempestroid.widgets.FilePicker`.
        """
        children: list[Widget] = []
        if self.label:
            children.append(
                Text(
                    content=self.label,
                    style=Style(
                        font_size=13.0, font_weight=FontWeight.MEDIUM, color=ON_MUTED
                    ),
                    key="image-picker-label",
                )
            )
        if self.value:
            children.append(
                Image(
                    src=self.value,
                    fit=ImageFit.COVER,
                    style=Style(width=160.0, height=160.0, radius=8.0),
                    key="image-picker-preview",
                )
            )
        children.append(
            FilePicker(
                label="Choose image",
                value=self.value,
                on_select=_on_uri(self.on_pick),
                key="image-picker-button",
            )
        )
        default = Style(gap=8.0)
        return Column(
            key=self.key or "image-picker",
            style=merge_style(default, self.style),
            children=children,
        )


class DocumentPicker(Component):
    """A labelled document picker.

    Attributes:
        value: The picked document URI (``""`` until one is chosen).
        label: An optional heading shown above the picker (omitted when empty).
        on_pick: Called with the picked document URI on selection.
    """

    value: str = Field(
        default="",
        description="The picked document URI (empty until one is chosen).",
    )
    label: str = Field(
        default="", description="An optional heading shown above the picker."
    )
    on_pick: Callable[[str], Any] = Field(
        description="Called with the picked document URI on selection."
    )

    def render(self) -> Widget:
        """Lower the document picker into a labelled column.

        Returns:
            A :class:`~tempestroid.widgets.Column` of the optional label and a
            :class:`~tempestroid.widgets.FilePicker`.
        """
        children: list[Widget] = []
        if self.label:
            children.append(
                Text(
                    content=self.label,
                    style=Style(
                        font_size=13.0, font_weight=FontWeight.MEDIUM, color=ON_MUTED
                    ),
                    key="document-picker-label",
                )
            )
        children.append(
            FilePicker(
                label="Choose document",
                value=self.value,
                on_select=_on_uri(self.on_pick),
                key="document-picker-button",
            )
        )
        default = Style(gap=8.0)
        return Column(
            key=self.key or "document-picker",
            style=merge_style(default, self.style),
            children=children,
        )


class ImagePicture(Component):
    """A circular profile-photo picker: a round photo over a change affordance.

    Distinct from :class:`~tempestroid.components.Avatar` (which shows initials):
    this clips a chosen :class:`~tempestroid.widgets.Image` to a circle, falling
    back to a ``user`` :class:`~tempestroid.widgets.Icon` placeholder when no
    photo is set, and offers a :class:`~tempestroid.widgets.FilePicker` to change
    it.

    Attributes:
        src: The current photo URI (``""`` shows the placeholder).
        size: The circle's diameter in logical pixels.
        on_pick: Called with the picked photo URI on selection.
    """

    src: str = Field(
        default="",
        description="The current photo URI (empty shows the placeholder).",
    )
    size: float = Field(
        default=96.0, description="The circle's diameter in logical pixels."
    )
    on_pick: Callable[[str], Any] = Field(
        description="Called with the picked photo URI on selection."
    )

    def _photo(self) -> Widget:
        """Build the circular photo or its placeholder.

        Returns:
            A circle-clipped :class:`~tempestroid.widgets.Image` when ``src`` is
            set, otherwise a centered ``user`` icon in a round container.
        """
        circle = Style(width=self.size, height=self.size, radius=self.size / 2.0)
        if self.src:
            return ClipPath(
                shape=ClipShape.CIRCLE,
                child=Image(
                    src=self.src,
                    fit=ImageFit.COVER,
                    style=circle,
                    key="image-picture-img",
                ),
                style=circle,
                key="image-picture-clip",
            )
        return Container(
            style=Style(
                width=self.size,
                height=self.size,
                radius=self.size / 2.0,
                background=MUTED,
                align=AlignItems.CENTER,
            ),
            child=Icon(name="user", size=self.size / 2.0, key="image-picture-icon"),
            key="image-picture-placeholder",
        )

    def render(self) -> Widget:
        """Lower the profile-photo picker into a column.

        Returns:
            A centered :class:`~tempestroid.widgets.Column` of the circular photo
            and a "change" :class:`~tempestroid.widgets.FilePicker`.
        """
        default = Style(gap=8.0, align=AlignItems.CENTER)
        return Column(
            key=self.key or "image-picture",
            style=merge_style(default, self.style),
            children=[
                self._photo(),
                FilePicker(
                    label="Change",
                    value=self.src,
                    on_select=_on_uri(self.on_pick),
                    key="image-picture-button",
                ),
            ],
        )
