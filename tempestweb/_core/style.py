"""Typed, web-like inline style model.

This module borrows the *vocabulary* of CSS (flexbox, box model, typography)
expressed as validated Pydantic objects, while deliberately dropping the CSS
*machine*: there are no selectors, no specificity and no implicit cascade.
Every style is explicit, validated and predictable.

The same ``Style`` object is later translated by two leaf renderers
(``Style -> Qt`` and ``Style -> Compose``); keeping it backend-agnostic here is
what allows the desktop simulator to stay honest against the device.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "FlexDirection",
    "FlexWrap",
    "JustifyContent",
    "AlignItems",
    "TextAlign",
    "FontWeight",
    "FontStyle",
    "TextDecoration",
    "TextOverflow",
    "GradientDirection",
    "Curve",
    "Position",
    "StackAlign",
    "Color",
    "Edge",
    "Border",
    "SideBorder",
    "Corners",
    "Shadow",
    "GradientStop",
    "Gradient",
    "Transition",
    "Style",
]


class FlexDirection(StrEnum):
    """Main-axis direction of a flex container (``flex-direction``)."""

    ROW = "row"
    COLUMN = "column"


class FlexWrap(StrEnum):
    """Whether a flex container wraps its children onto new lines (``flex-wrap``).

    ``NOWRAP`` keeps every child on a single line (the flex default), while
    ``WRAP`` lets children flow onto subsequent lines once the current one fills
    and ``WRAP_REVERSE`` does the same with the cross-axis order reversed. Only
    flow-capable containers (a :class:`~tempestroid.widgets.Wrap`) react to it;
    the Compose translator lowers it into the spec, while the Qt translator
    realizes wrapping imperatively in its flow-layout widget (see the conformance
    suite).
    """

    NOWRAP = "nowrap"
    WRAP = "wrap"
    WRAP_REVERSE = "wrap-reverse"


class JustifyContent(StrEnum):
    """Distribution of children along the main axis (``justify-content``)."""

    START = "start"
    END = "end"
    CENTER = "center"
    SPACE_BETWEEN = "space-between"
    SPACE_AROUND = "space-around"
    SPACE_EVENLY = "space-evenly"


class AlignItems(StrEnum):
    """Alignment of children along the cross axis (``align-items``)."""

    START = "start"
    END = "end"
    CENTER = "center"
    STRETCH = "stretch"


class TextAlign(StrEnum):
    """Horizontal text alignment (``text-align``)."""

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "justify"


class FontWeight(IntEnum):
    """Common font weights, matching the CSS numeric scale."""

    THIN = 100
    LIGHT = 300
    NORMAL = 400
    MEDIUM = 500
    SEMIBOLD = 600
    BOLD = 700
    BLACK = 900


class Curve(StrEnum):
    """Easing curve for an animated transition (CSS ``transition-timing-function``).

    Mirrors the common CSS/Flutter easing presets; the leaf renderer maps each
    onto its native curve (Compose ``Easing``; Qt ``QEasingCurve``). The core's
    own :func:`~tempestroid.animation._apply_curve` also approximates each so the
    simulator/test clock can interpolate without a renderer.
    """

    LINEAR = "linear"
    EASE_IN = "ease-in"
    EASE_OUT = "ease-out"
    EASE_IN_OUT = "ease-in-out"
    EASE = "ease"
    BOUNCE = "bounce"
    ELASTIC = "elastic"


class FontStyle(StrEnum):
    """Font slant (``font-style``)."""

    NORMAL = "normal"
    ITALIC = "italic"


class TextDecoration(StrEnum):
    """Text line decoration (``text-decoration``)."""

    NONE = "none"
    UNDERLINE = "underline"
    LINE_THROUGH = "line-through"


class TextOverflow(StrEnum):
    """How clipped text terminates (``text-overflow`` / Compose ``TextOverflow``)."""

    CLIP = "clip"
    ELLIPSIS = "ellipsis"


class GradientDirection(StrEnum):
    """Direction of a linear gradient's color progression."""

    TOP_BOTTOM = "top-bottom"
    BOTTOM_TOP = "bottom-top"
    LEFT_RIGHT = "left-right"
    RIGHT_LEFT = "right-left"


class Position(StrEnum):
    """Stacking-flow positioning of a child inside a ``Stack`` (``position``).

    ``STATIC`` (the default) lets the child participate in the stack's normal
    overlap flow, aligned by the stack's :attr:`Style.stack_align`. ``ABSOLUTE``
    pulls the child out of that flow and anchors it by its insets
    (:attr:`Style.top`/:attr:`Style.right`/:attr:`Style.bottom`/:attr:`Style.left`),
    modelled on Flutter's ``Positioned`` / CSS ``position: absolute``.
    """

    STATIC = "static"
    ABSOLUTE = "absolute"


class StackAlign(StrEnum):
    """Two-axis alignment of a ``Stack``'s non-positioned children.

    Mirrors Compose ``Alignment`` / Flutter ``AlignmentDirectional`` constants:
    a vertical band (top/center/bottom) crossed with a horizontal band
    (start/center/end). Used only by ``Stack`` containers; ordinary flex
    containers keep using single-axis :class:`JustifyContent`/:class:`AlignItems`.
    """

    TOP_START = "top-start"
    TOP_CENTER = "top-center"
    TOP_END = "top-end"
    CENTER_START = "center-start"
    CENTER = "center"
    CENTER_END = "center-end"
    BOTTOM_START = "bottom-start"
    BOTTOM_CENTER = "bottom-center"
    BOTTOM_END = "bottom-end"


class Color(BaseModel):
    """An RGBA color.

    Construct it directly, from a hex string via :meth:`from_hex`, or by passing
    a hex string anywhere a ``Color`` is expected (a ``before`` validator coerces
    ``str`` into a ``Color``).

    Attributes:
        r: Red channel, 0-255.
        g: Green channel, 0-255.
        b: Blue channel, 0-255.
        a: Alpha channel, 0.0 (transparent) to 1.0 (opaque).

    Methods:
        from_hex: Build a color from a hex string (classmethod).
        rgba: Build a color from explicit channel values (classmethod).
        to_hex: Render the color as ``#RRGGBB`` (or ``#RRGGBBAA`` when translucent).
        to_rgba_string: Render the color as a CSS-style ``rgba(...)`` string.
    """

    model_config = ConfigDict(frozen=True)

    r: int = Field(ge=0, le=255)
    g: int = Field(ge=0, le=255)
    b: int = Field(ge=0, le=255)
    a: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="before")
    @classmethod
    def _coerce_str(cls, value: object) -> object:
        """Coerce a hex string into the channel mapping Pydantic expects.

        Args:
            value: Raw input — either a hex string or an already-shaped mapping.

        Returns:
            A ``dict`` of channels when given a string, otherwise ``value``
            unchanged.
        """
        if isinstance(value, str):
            r, g, b, a = cls._parse_hex(value)
            return {"r": r, "g": g, "b": b, "a": a}
        return value

    @staticmethod
    def _parse_hex(value: str) -> tuple[int, int, int, float]:
        """Parse a ``#RGB``/``#RRGGBB``/``#RRGGBBAA`` string into channels.

        Args:
            value: The hex string, with or without a leading ``#``.

        Returns:
            The ``(r, g, b, a)`` channels — RGB as 0-255 ints, alpha as 0.0-1.0.

        Raises:
            ValueError: If the string is not a valid hex color.
        """
        text = value.lstrip("#")
        if len(text) == 3:
            text = "".join(ch * 2 for ch in text)
        if len(text) not in (6, 8):
            raise ValueError(f"invalid hex color: {value!r}")
        try:
            r = int(text[0:2], 16)
            g = int(text[2:4], 16)
            b = int(text[4:6], 16)
            a = int(text[6:8], 16) / 255 if len(text) == 8 else 1.0
        except ValueError as exc:
            raise ValueError(f"invalid hex color: {value!r}") from exc
        return r, g, b, a

    @classmethod
    def from_hex(cls, value: str) -> Color:
        """Build a color from a hex string.

        Args:
            value: A ``#RGB``, ``#RRGGBB`` or ``#RRGGBBAA`` string.

        Returns:
            The parsed color.

        Raises:
            ValueError: If the string is not a valid hex color.
        """
        r, g, b, a = cls._parse_hex(value)
        return cls(r=r, g=g, b=b, a=a)

    @classmethod
    def rgba(cls, r: int, g: int, b: int, a: float = 1.0) -> Color:
        """Build a color from explicit channel values.

        Args:
            r: Red channel, 0-255.
            g: Green channel, 0-255.
            b: Blue channel, 0-255.
            a: Alpha channel, 0.0-1.0.

        Returns:
            The constructed color.
        """
        return cls(r=r, g=g, b=b, a=a)

    def to_hex(self) -> str:
        """Render the color as ``#RRGGBB`` (or ``#RRGGBBAA`` when translucent).

        Returns:
            The hex representation.
        """
        base = f"#{self.r:02x}{self.g:02x}{self.b:02x}"
        if self.a < 1.0:
            return f"{base}{round(self.a * 255):02x}"
        return base

    def to_rgba_string(self) -> str:
        """Render the color as a CSS-style ``rgba(...)`` string.

        Returns:
            The ``rgba(r, g, b, a)`` representation.
        """
        return f"rgba({self.r}, {self.g}, {self.b}, {self.a})"


class Edge(BaseModel):
    """Per-side spacing in logical pixels (used for padding and margin).

    Attributes:
        top: Spacing on the top side.
        right: Spacing on the right side.
        bottom: Spacing on the bottom side.
        left: Spacing on the left side.

    Methods:
        all: Build an edge with the same spacing on every side (classmethod).
        symmetric: Build an edge with mirrored vertical/horizontal spacing
            (classmethod).
    """

    model_config = ConfigDict(frozen=True)

    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    left: float = 0.0

    @classmethod
    def all(cls, value: float) -> Edge:
        """Build an edge with the same spacing on every side.

        Args:
            value: Spacing applied to all four sides.

        Returns:
            The constructed edge.
        """
        return cls(top=value, right=value, bottom=value, left=value)

    @classmethod
    def symmetric(cls, *, vertical: float = 0.0, horizontal: float = 0.0) -> Edge:
        """Build an edge with mirrored vertical and horizontal spacing.

        Args:
            vertical: Spacing for the top and bottom sides.
            horizontal: Spacing for the left and right sides.

        Returns:
            The constructed edge.
        """
        return cls(top=vertical, bottom=vertical, left=horizontal, right=horizontal)


class Border(BaseModel):
    """A uniform border (``border-width`` + ``border-color``)."""

    model_config = ConfigDict(frozen=True)

    width: float = 0.0
    color: Color | None = None


class SideBorder(BaseModel):
    """A per-side border (``border-top``/``border-right``/…).

    Each side is an independent :class:`Border`, or ``None`` to leave that side
    unset. Use it in :attr:`Style.border` instead of a uniform :class:`Border`
    when sides differ (e.g. only a bottom divider).
    """

    model_config = ConfigDict(frozen=True)

    top: Border | None = None
    right: Border | None = None
    bottom: Border | None = None
    left: Border | None = None


class Corners(BaseModel):
    """Per-corner border radii in logical pixels (``border-*-radius``).

    Use it in :attr:`Style.radius` instead of a single float when corners differ
    (e.g. a sheet rounded only on top).
    """

    model_config = ConfigDict(frozen=True)

    top_left: float = 0.0
    top_right: float = 0.0
    bottom_right: float = 0.0
    bottom_left: float = 0.0


class Shadow(BaseModel):
    """A drop shadow (``box-shadow``) / Material elevation.

    Compose maps it to elevation; Qt approximates it with a
    ``QGraphicsDropShadowEffect``. Frozen so the reconciler can diff it by value.

    Attributes:
        color: The shadow color (renderer default when ``None``).
        blur: The blur radius in logical pixels.
        offset_x: Horizontal offset in logical pixels.
        offset_y: Vertical offset in logical pixels.
    """

    model_config = ConfigDict(frozen=True)

    color: Color | None = None
    blur: float = Field(default=0.0, ge=0.0)
    offset_x: float = 0.0
    offset_y: float = 0.0


class GradientStop(BaseModel):
    """One color stop of a :class:`Gradient`.

    Attributes:
        color: The stop's color.
        position: The stop's position along the gradient, 0.0-1.0.
    """

    model_config = ConfigDict(frozen=True)

    color: Color
    position: float = Field(ge=0.0, le=1.0)


class Gradient(BaseModel):
    """A linear color gradient usable wherever a background color is.

    Attributes:
        stops: The ordered color stops (at least two for a visible gradient).
        direction: The direction the colors progress in.
    """

    model_config = ConfigDict(frozen=True)

    stops: list[GradientStop] = Field(min_length=1)
    direction: GradientDirection = GradientDirection.TOP_BOTTOM


class Transition(BaseModel):
    """An implicit animation applied when a style's properties change.

    Modelled on CSS ``transition`` / Flutter's implicitly-animated widgets: when
    a node is rebuilt with a different ``Style``, the renderer tweens the changed
    visual properties over ``duration_ms`` using ``curve`` rather than snapping.
    Frozen so the reconciler can diff it by value.

    Attributes:
        duration_ms: Animation duration in milliseconds (must be positive).
        curve: The easing curve to apply.
        delay_ms: Delay before the animation starts, in milliseconds.
    """

    model_config = ConfigDict(frozen=True)

    duration_ms: int = Field(gt=0)
    curve: Curve = Curve.EASE_IN_OUT
    delay_ms: int = Field(default=0, ge=0)


class Style(BaseModel):
    """An inline, typed style object.

    Every field is optional: ``None`` means "unset", letting the leaf renderer
    fall back to its own default. Styles are frozen; combine them with
    :meth:`merge` to layer overrides without mutation.

    Methods:
        merge: Layer another style on top of this one (returns a new ``Style``).
    """

    model_config = ConfigDict(frozen=True)

    # Flexbox layout.
    direction: FlexDirection | None = None
    justify: JustifyContent | None = None
    align: AlignItems | None = None
    align_self: AlignItems | None = None
    grow: float | None = None
    gap: float | None = None
    flex_wrap: FlexWrap | None = None

    # Box model.
    padding: Edge | None = None
    margin: Edge | None = None
    border: Border | SideBorder | None = None
    radius: float | Corners | None = None

    # Paint.
    background: Color | Gradient | None = None
    color: Color | None = None
    opacity: float | None = Field(default=None, ge=0.0, le=1.0)
    shadow: Shadow | None = None

    # Typography.
    font_family: str | None = None
    font_size: float | None = None
    font_weight: FontWeight | None = None
    font_style: FontStyle | None = None
    text_align: TextAlign | None = None
    text_decoration: TextDecoration | None = None
    letter_spacing: float | None = None
    line_height: float | None = None
    max_lines: int | None = Field(default=None, gt=0)
    text_overflow: TextOverflow | None = None
    #: Multiplier applied to ``font_size`` (``1.0`` is neutral). The Qt
    #: translator scales the emitted ``font-size``; the Compose translator emits
    #: it as ``textScale`` for the device's ``LocalDensity`` to apply.
    text_scale: float | None = Field(default=None, gt=0.0)
    #: Path to a custom font asset relative to the app bundle (e.g.
    #: ``"fonts/Roboto.ttf"``). Both renderers load it (Qt ``QFontDatabase``,
    #: Compose ``FontFamily``) and apply it as the node's font family.
    font_asset: str | None = None

    # Dimensions (logical pixels).
    width: float | None = None
    height: float | None = None
    min_width: float | None = None
    max_width: float | None = None
    min_height: float | None = None
    max_height: float | None = None
    aspect_ratio: float | None = Field(default=None, gt=0.0)

    # Stacking / overlay. ``stack_align`` lives on a ``Stack`` and aligns its
    # non-positioned children; ``position`` + the four insets live on a *child*
    # of a Stack and anchor it absolutely (CSS ``position`` / Flutter
    # ``Positioned``). The leaf renderers realize these imperatively (Qt geometry,
    # Compose ``Box`` alignment/offset), so the pure ``Style → Qt`` translator does
    # not react to them — see the conformance suite.
    stack_align: StackAlign | None = None
    position: Position | None = None
    top: float | None = None
    right: float | None = None
    bottom: float | None = None
    left: float | None = None

    # Animation. Implicitly tween changed visual props on rebuild (Compose maps
    # this to ``animate*AsState``; Qt animation is renderer-imperative, so the
    # ``Style → Qt`` translator does not react to it — see the conformance suite).
    transition: Transition | None = None

    def merge(self, other: Style) -> Style:
        """Layer another style on top of this one.

        Fields explicitly set on ``other`` (i.e. not ``None``) win; everything
        else is inherited from ``self``.

        Args:
            other: The overriding style.

        Returns:
            A new, merged style.
        """
        overrides = other.model_dump(exclude_none=True)
        return self.model_copy(update=overrides)
