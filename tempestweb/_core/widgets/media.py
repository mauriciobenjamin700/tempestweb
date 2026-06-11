"""Media and graphics widgets.

Beyond the simple ``Image``/``Icon`` leaves, this module carries the richer
media surface: a retained-mode ``Canvas`` (a serializable list of draw
commands), video/web/SVG embedding, live camera and QR scanning, an embedded
map, and visual-effect wrappers (``Blur``/``BackdropFilter``/``ClipPath``).

The ``Canvas`` drawing API mirrors how ``Style`` lowers to a renderer-agnostic
spec: a :data:`DrawCommand` is a frozen, discriminated union of plain value
models whose every field is JSON-serializable (colors are ``[r, g, b, a]``
*lists*, never tuples or ``Color`` objects). The reconciler diffs the command
list by value through the existing prop diff, and the serializer lowers each
command via ``model_dump()`` — so the same list reaches both leaf renderers
unchanged.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from tempestweb._core.widgets.base import EventHandler, Widget
from tempestweb._core.widgets.events import Event, QrScanEvent

__all__ = [
    "ImageFit",
    "Image",
    "Icon",
    "MoveTo",
    "LineTo",
    "ArcTo",
    "Close",
    "FillCmd",
    "StrokeCmd",
    "DrawText",
    "DrawRect",
    "DrawOval",
    "DrawCommand",
    "Canvas",
    "VideoPlayer",
    "WebView",
    "Svg",
    "CameraPreview",
    "QrScanner",
    "MapView",
    "Blur",
    "BackdropFilter",
    "ClipShape",
    "ClipPath",
]


class ImageFit(StrEnum):
    """How an image scales to fill its box (CSS ``object-fit`` vocabulary)."""

    CONTAIN = "contain"
    COVER = "cover"
    FILL = "fill"
    NONE = "none"


class Image(Widget):
    """A bitmap image loaded from a URL or asset path.

    Attributes:
        src: The image source — an ``http(s)`` URL or a bundled asset path.
        fit: How the image scales within its box.
        alt: Alternative text shown if the image cannot be loaded.
    """

    src: str = Field(
        description="The image source — an ``http(s)`` URL or a bundled asset path."
    )
    fit: ImageFit = Field(
        default=ImageFit.CONTAIN, description="How the image scales within its box."
    )
    alt: str = Field(
        default="", description="Alternative text shown if the image cannot be loaded."
    )


class Icon(Widget):
    """A vector icon, drawn from the built-in curated set or a platform set.

    The ``name`` may be one of the framework's curated icon names — see
    :class:`tempestroid.icons.Icons` and :data:`tempestroid.icons.ICON_PATHS`
    (e.g. ``Icons.SEARCH`` / ``"search"``) — in which case the renderer strokes
    the built-in single-path geometry resolved via
    :func:`tempestroid.icons.icon_path`. Otherwise ``name`` is treated as an
    arbitrary platform icon identifier (e.g. a Material Icons name like
    ``"home"``); when neither resolves, the renderer falls back to showing the
    name. This keeps the field contract unchanged.

    Attributes:
        name: The icon identifier — a curated :class:`~tempestroid.icons.Icons`
            value (or its string) or an arbitrary platform icon name.
        size: The icon's edge length in logical pixels, or ``None`` for the
            renderer default.
    """

    name: str = Field(
        description='The icon identifier (e.g. a Material Icons name like ``"home"``).'
    )
    size: float | None = Field(
        default=None,
        description="The icon's edge length in logical pixels, or ``None`` for the "
        "renderer default.",
    )


class MoveTo(BaseModel):
    """Move the current point of the active path without drawing.

    Attributes:
        kind: The command discriminator (``"move_to"``).
        x: Target x coordinate, in logical pixels.
        y: Target y coordinate, in logical pixels.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["move_to"] = Field(
        default="move_to", description='The command discriminator (``"move_to"``).'
    )
    x: float = Field(description="Target x coordinate, in logical pixels.")
    y: float = Field(description="Target y coordinate, in logical pixels.")


class LineTo(BaseModel):
    """Add a straight line from the current point to ``(x, y)``.

    Attributes:
        kind: The command discriminator (``"line_to"``).
        x: Target x coordinate, in logical pixels.
        y: Target y coordinate, in logical pixels.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["line_to"] = Field(
        default="line_to", description='The command discriminator (``"line_to"``).'
    )
    x: float = Field(description="Target x coordinate, in logical pixels.")
    y: float = Field(description="Target y coordinate, in logical pixels.")


class ArcTo(BaseModel):
    """Add an elliptical arc within the bounding box ``(x, y, width, height)``.

    Attributes:
        kind: The command discriminator (``"arc_to"``).
        x: Bounding box left, in logical pixels.
        y: Bounding box top, in logical pixels.
        width: Bounding box width, in logical pixels.
        height: Bounding box height, in logical pixels.
        start_angle: Start angle, in degrees.
        sweep_angle: Sweep angle, in degrees.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["arc_to"] = Field(
        default="arc_to", description='The command discriminator (``"arc_to"``).'
    )
    x: float = Field(description="Bounding box left, in logical pixels.")
    y: float = Field(description="Bounding box top, in logical pixels.")
    width: float = Field(description="Bounding box width, in logical pixels.")
    height: float = Field(description="Bounding box height, in logical pixels.")
    start_angle: float = Field(description="Start angle, in degrees.")
    sweep_angle: float = Field(description="Sweep angle, in degrees.")


class Close(BaseModel):
    """Close the active subpath back to its start point.

    Attributes:
        kind: The command discriminator (``"close"``).
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["close"] = Field(
        default="close", description='The command discriminator (``"close"``).'
    )


class FillCmd(BaseModel):
    """Fill the active path with a solid color and reset the path.

    Attributes:
        kind: The command discriminator (``"fill"``).
        color: The fill color as an ``[r, g, b, a]`` list of floats in ``[0, 1]``
            (a list, never a tuple, so the command is JSON-serializable directly).
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["fill"] = Field(
        default="fill", description='The command discriminator (``"fill"``).'
    )
    color: list[float] = Field(
        description="The fill color as an ``[r, g, b, a]`` list of floats in ``[0, "
        "1]`` (a list, never a tuple, so the command is JSON-serializable directly).",
    )


class StrokeCmd(BaseModel):
    """Stroke the active path with a solid color and reset the path.

    Attributes:
        kind: The command discriminator (``"stroke"``).
        color: The stroke color as an ``[r, g, b, a]`` list of floats in
            ``[0, 1]`` (a list, never a tuple).
        width: The stroke width, in logical pixels.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["stroke"] = Field(
        default="stroke", description='The command discriminator (``"stroke"``).'
    )
    color: list[float] = Field(
        description="The stroke color as an ``[r, g, b, a]`` list of floats in ``[0, "
        "1]`` (a list, never a tuple).",
    )
    width: float = Field(
        default=1.0, description="The stroke width, in logical pixels."
    )


class DrawText(BaseModel):
    """Draw a run of text at a baseline anchor.

    Attributes:
        kind: The command discriminator (``"draw_text"``).
        text: The text to draw.
        x: Baseline x coordinate, in logical pixels.
        y: Baseline y coordinate, in logical pixels.
        size: The font size, in logical pixels.
        color: The text color as an ``[r, g, b, a]`` list of floats in ``[0, 1]``
            (a list, never a tuple).
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["draw_text"] = Field(
        default="draw_text", description='The command discriminator (``"draw_text"``).'
    )
    text: str = Field(description="The text to draw.")
    x: float = Field(description="Baseline x coordinate, in logical pixels.")
    y: float = Field(description="Baseline y coordinate, in logical pixels.")
    size: float = Field(default=14.0, description="The font size, in logical pixels.")
    color: list[float] = Field(
        description="The text color as an ``[r, g, b, a]`` list of floats in ``[0, "
        "1]`` (a list, never a tuple).",
        default_factory=lambda: [0.0, 0.0, 0.0, 1.0],
    )


class DrawRect(BaseModel):
    """Add a rectangle to the active path.

    Attributes:
        kind: The command discriminator (``"draw_rect"``).
        x: Rectangle left, in logical pixels.
        y: Rectangle top, in logical pixels.
        width: Rectangle width, in logical pixels.
        height: Rectangle height, in logical pixels.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["draw_rect"] = Field(
        default="draw_rect", description='The command discriminator (``"draw_rect"``).'
    )
    x: float = Field(description="Rectangle left, in logical pixels.")
    y: float = Field(description="Rectangle top, in logical pixels.")
    width: float = Field(description="Rectangle width, in logical pixels.")
    height: float = Field(description="Rectangle height, in logical pixels.")


class DrawOval(BaseModel):
    """Add an ellipse (oval) to the active path.

    Attributes:
        kind: The command discriminator (``"draw_oval"``).
        x: Bounding box left, in logical pixels.
        y: Bounding box top, in logical pixels.
        width: Bounding box width, in logical pixels.
        height: Bounding box height, in logical pixels.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["draw_oval"] = Field(
        default="draw_oval", description='The command discriminator (``"draw_oval"``).'
    )
    x: float = Field(description="Bounding box left, in logical pixels.")
    y: float = Field(description="Bounding box top, in logical pixels.")
    width: float = Field(description="Bounding box width, in logical pixels.")
    height: float = Field(description="Bounding box height, in logical pixels.")


#: A single drawing instruction for :class:`Canvas`. A frozen, discriminated
#: union of plain value models whose every field is JSON-serializable, so a
#: command list lowers to the wire via ``model_dump()`` with no tuples or live
#: objects. Discriminated on the ``kind`` literal so Pydantic validates the right
#: member when a command crosses back as a dict.
DrawCommand = Annotated[
    MoveTo
    | LineTo
    | ArcTo
    | Close
    | FillCmd
    | StrokeCmd
    | DrawText
    | DrawRect
    | DrawOval,
    Field(discriminator="kind"),
]


def _empty_commands() -> list[DrawCommand]:
    """Return a fresh, empty draw-command list.

    A typed factory (rather than bare ``list``) so pyright strict infers the
    element type for :attr:`Canvas.commands`.

    Returns:
        A new empty list.
    """
    return []


def _empty_markers() -> list[dict[str, Any]]:
    """Return a fresh, empty marker list.

    A typed factory (rather than bare ``list``) so pyright strict infers the
    element type for :attr:`MapView.markers`.

    Returns:
        A new empty list.
    """
    return []


class Canvas(Widget):
    """A retained-mode drawing surface interpreting a list of draw commands.

    The command list is the IR: a serializable, value-diffable sequence of
    :data:`DrawCommand` that both leaf renderers replay (Qt via ``QPainter`` in a
    ``paintEvent``; Compose via ``drawIntoCanvas``). The reconciler diffs the list
    by value, so changing a command emits a single ``Update`` carrying the new
    list.

    Attributes:
        commands: The ordered draw commands to replay each paint.
        width: Optional fixed canvas width, in logical pixels.
        height: Optional fixed canvas height, in logical pixels.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {}
    commands: list[DrawCommand] = Field(
        description="The ordered draw commands to replay each paint.",
        default_factory=_empty_commands,
    )
    width: float | None = Field(
        default=None, description="Optional fixed canvas width, in logical pixels."
    )
    height: float | None = Field(
        default=None, description="Optional fixed canvas height, in logical pixels."
    )


class VideoPlayer(Widget):
    """An embedded video player.

    Attributes:
        src: The video source — an ``http(s)`` URL or a bundled asset path.
        autoplay: Whether playback starts automatically when mounted.
        loop: Whether playback restarts when it reaches the end.
        controls: Whether the platform transport controls are shown.
        muted: Whether the audio track starts muted.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {}
    src: str = Field(
        description="The video source — an ``http(s)`` URL or a bundled asset path."
    )
    autoplay: bool = Field(
        default=False, description="Whether playback starts automatically when mounted."
    )
    loop: bool = Field(
        default=False, description="Whether playback restarts when it reaches the end."
    )
    controls: bool = Field(
        default=True, description="Whether the platform transport controls are shown."
    )
    muted: bool = Field(
        default=False, description="Whether the audio track starts muted."
    )


class WebView(Widget):
    """An embedded web view rendering a remote page.

    Attributes:
        url: The page URL to load.
        javascript_enabled: Whether JavaScript execution is allowed.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {}
    url: str = Field(description="The page URL to load.")
    javascript_enabled: bool = Field(
        default=True, description="Whether JavaScript execution is allowed."
    )


class Svg(Widget):
    """A scalable vector graphic loaded from a URL or asset path.

    Attributes:
        src: The SVG source — an ``http(s)`` URL or a bundled asset path.
        fit: How the vector scales within its box.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {}
    src: str = Field(
        description="The SVG source — an ``http(s)`` URL or a bundled asset path."
    )
    fit: ImageFit = Field(
        default=ImageFit.CONTAIN, description="How the vector scales within its box."
    )


class CameraPreview(Widget):
    """A live camera preview surface.

    Attributes:
        facing: Which camera to use (``"front"`` or ``"back"``).
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {}
    facing: str = Field(
        default="back", description='Which camera to use (``"front"`` or ``"back"``).'
    )


class QrScanner(Widget):
    """A live camera surface that scans QR/barcodes and reports each result.

    Attributes:
        on_scan: Handler invoked with a :class:`QrScanEvent` for each decoded
            code (the typed event is the widget's contract; the device wires the
            scanner directly to this handler's token).
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_scan": QrScanEvent}
    on_scan: EventHandler | None = Field(
        default=None,
        description="Handler invoked with a :class:`QrScanEvent` for each decoded code "
        "(the typed event is the widget's contract; the device wires the scanner "
        "directly to this handler's token).",
    )


class MapView(Widget):
    """An embedded map centered on a coordinate, with optional markers.

    Attributes:
        latitude: The map center latitude, in degrees.
        longitude: The map center longitude, in degrees.
        zoom: The map zoom level.
        markers: Plain JSON-serializable marker descriptors (each a dict, e.g.
            ``{"lat": ..., "lng": ..., "title": ...}``); the list crosses the
            boundary as-is.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {}
    latitude: float = Field(
        default=0.0, description="The map center latitude, in degrees."
    )
    longitude: float = Field(
        default=0.0, description="The map center longitude, in degrees."
    )
    zoom: float = Field(default=12.0, description="The map zoom level.")
    markers: list[dict[str, Any]] = Field(
        description="Plain JSON-serializable marker descriptors (each a dict, e.g. "
        '``{"lat": ..., "lng": ..., "title": ...}``); the list crosses the boundary '
        "as-is.",
        default_factory=_empty_markers,
    )


class Blur(Widget):
    """A wrapper that blurs its child.

    Attributes:
        radius: The blur radius, in logical pixels.
        child: The optional wrapped widget.
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"child"})
    event_schemas: ClassVar[dict[str, type[Event]]] = {}
    radius: float = Field(
        default=8.0, description="The blur radius, in logical pixels."
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


class BackdropFilter(Widget):
    """A wrapper that blurs the layers behind its child (semantic alias of Blur).

    Attributes:
        radius: The blur radius, in logical pixels.
        child: The optional wrapped widget.
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"child"})
    event_schemas: ClassVar[dict[str, type[Event]]] = {}
    radius: float = Field(
        default=8.0, description="The blur radius, in logical pixels."
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


class ClipShape(StrEnum):
    """The predefined shapes a :class:`ClipPath` can clip its child to."""

    CIRCLE = "circle"
    ROUNDED_RECT = "rounded_rect"
    OVAL = "oval"


class ClipPath(Widget):
    """A wrapper that clips its child to a predefined shape.

    Attributes:
        shape: The clipping shape.
        radius: The corner radius for ``ROUNDED_RECT``, in logical pixels.
        child: The optional wrapped widget.
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"child"})
    event_schemas: ClassVar[dict[str, type[Event]]] = {}
    shape: ClipShape = Field(
        default=ClipShape.ROUNDED_RECT, description="The clipping shape."
    )
    radius: float = Field(
        default=8.0,
        description="The corner radius for ``ROUNDED_RECT``, in logical pixels.",
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
