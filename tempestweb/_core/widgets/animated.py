"""Animation widgets: animated wrappers, list transitions, hero tags, shimmers.

These widgets are the declarative surface of the E3 animation framework. The
interpolation itself lives in the core (an
:class:`~tempestroid.animation.AnimationController` advances a normalized value
and a :class:`~tempestroid.animation.Tween` interpolates it), so the leaf
renderers only ever see *final* props for the current frame. The widgets here
carry the metadata each renderer needs to realize the motion:

* :class:`Animated` wraps one child whose style the ``view`` already interpolated
  per frame — the renderer just mounts the child (it never drives the motion).
* :class:`AnimatedList` is a flex container that animates its children in and out
  as they are inserted/removed (Qt: ``QPropertyAnimation`` on opacity + height;
  Compose: ``AnimatedVisibility``).
* :class:`Hero` tags a subtree as a shared element so a screen transition can
  interpolate its geometry between routes.
* :class:`Shimmer` overlays a moving gradient on a child as a loading placeholder;
  :class:`Skeleton` is the childless rectangular variant.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import Field

from tempestweb._core.style import Color, Curve, FlexDirection
from tempestweb._core.widgets.base import Widget
from tempestweb._core.widgets.events import Event

__all__ = [
    "Animated",
    "AnimatedList",
    "Hero",
    "Shimmer",
    "Skeleton",
]


def _empty_children() -> list[Widget]:
    """Provide a fresh, typed empty child list for default factories.

    Returns:
        A new empty list of widgets.
    """
    return []


def _shimmer_base() -> Color:
    """Provide the default shimmer base (resting) color.

    Returns:
        A light-grey color used as the shimmer's resting tone.
    """
    return Color(r=224, g=224, b=224)


def _shimmer_highlight() -> Color:
    """Provide the default shimmer highlight (sweep) color.

    Returns:
        A near-white color used as the shimmer's moving highlight.
    """
    return Color(r=245, g=245, b=245)


class Animated(Widget):
    """A wrapper whose child is rebuilt with interpolated style each frame.

    The interpolation happens in the core: the ``view`` reads the ``value`` of its
    :attr:`controller` (driven by the app frame clock), interpolates
    a :class:`~tempestroid.animation.Tween` with it, and folds the result into the
    child :class:`~tempestroid.style.Style`. So the renderer receives a child
    that is *already* at this frame target — it just mounts it normally. The
    :attr:`controller`, :attr:`style_begin` and :attr:`style_end` fields are kept
    on the node for introspection/device parity; they are not consumed by the Qt
    renderer's mount path (a documented Qt-vs-Compose divergence).

    Attributes:
        child: The wrapped widget (mounted with its per-frame interpolated style).
        controller: The :class:`~tempestroid.animation.AnimationController` driving
            the interpolation (typed ``Any`` to avoid an import cycle through the
            core animation module).
        style_begin: The style at ``value == 0.0`` (or ``None`` to use the child's
            own style as the start).
        style_end: The style at ``value == 1.0`` (or ``None``).
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"child"})
    event_schemas: ClassVar[dict[str, type[Event]]] = {}

    child: Widget = Field(
        description="The wrapped widget (mounted with its per-frame interpolated "
        "style).",
    )
    controller: Any = Field(
        default=None,
        description="The :class:`~tempestroid.animation.AnimationController` driving "
        "the interpolation (typed ``Any`` to avoid an import cycle through the core "
        "animation module).",
    )
    style_begin: Any = Field(
        default=None,
        description="The style at ``value == 0.0`` (or ``None`` to use the child's own "
        "style as the start).",
    )
    style_end: Any = Field(
        default=None, description="The style at ``value == 1.0`` (or ``None``)."
    )

    def child_nodes(self) -> list[Widget]:
        """Return the single wrapped child.

        Returns:
            A one-element list holding the child.
        """
        return [self.child]


class AnimatedList(Widget):
    """A flex container that animates items as they enter and leave.

    Lays its children along :attr:`direction` like a ``Column``/``Row``, but on a
    structural change (an ``Insert``/``Remove`` patch) the affected child is
    animated in/out rather than appearing/disappearing instantly. The Qt renderer
    realizes this with a ``QPropertyAnimation`` on the child's opacity and maximum
    height; the device renderer wraps each child in ``AnimatedVisibility`` (a
    documented divergence).

    Attributes:
        direction: The main-axis direction (column or row).
        children: The ordered child widgets.
        enter_duration_ms: Enter-animation duration in milliseconds.
        exit_duration_ms: Exit-animation duration in milliseconds.
        enter_curve: The easing curve applied to the enter animation.
        exit_curve: The easing curve applied to the exit animation.
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"children"})
    event_schemas: ClassVar[dict[str, type[Event]]] = {}

    direction: FlexDirection = Field(
        default=FlexDirection.COLUMN,
        description="The main-axis direction (column or row).",
    )
    children: list[Widget] = Field(
        description="The ordered child widgets.", default_factory=_empty_children
    )
    enter_duration_ms: int = Field(
        default=300, description="Enter-animation duration in milliseconds."
    )
    exit_duration_ms: int = Field(
        default=300, description="Exit-animation duration in milliseconds."
    )
    enter_curve: Curve = Field(
        default=Curve.EASE_OUT,
        description="The easing curve applied to the enter animation.",
    )
    exit_curve: Curve = Field(
        default=Curve.EASE_IN,
        description="The easing curve applied to the exit animation.",
    )

    def child_nodes(self) -> list[Widget]:
        """Return the list's children in order.

        Returns:
            The ordered child widgets.
        """
        return self.children


class Hero(Widget):
    """A shared-element transition tag wrapping a single child.

    When two screens of a :class:`~tempestroid.widgets.Navigator` each contain a
    ``Hero`` with the same :attr:`hero_tag`, the renderer interpolates the tagged
    subtree's geometry across the route transition (Qt: a ``QPropertyAnimation`` on
    geometry; Compose: ``SharedTransitionLayout`` + ``Modifier.sharedElement``).
    The tag must be unique within each screen.

    Attributes:
        hero_tag: The shared-element identity (must match across screens).
        child: The wrapped widget that participates in the transition.
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"child"})
    event_schemas: ClassVar[dict[str, type[Event]]] = {}

    hero_tag: str = Field(
        description="The shared-element identity (must match across screens)."
    )
    child: Widget = Field(
        description="The wrapped widget that participates in the transition."
    )

    def child_nodes(self) -> list[Widget]:
        """Return the single wrapped child.

        Returns:
            A one-element list holding the child.
        """
        return [self.child]


class Shimmer(Widget):
    """A loading placeholder that sweeps a gradient highlight over a child.

    Wraps a child (usually a skeleton layout) and animates a diagonal gradient
    band from :attr:`base_color` toward :attr:`highlight_color` and back in a loop,
    the classic "content is loading" shimmer. Qt drives the gradient with an
    internal ``QTimer`` repaint loop; the device renderer uses an
    ``InfiniteTransition`` + ``Brush.linearGradient`` (a documented divergence).

    Attributes:
        child: The wrapped widget the shimmer paints over.
        base_color: The resting tone of the gradient.
        highlight_color: The moving highlight tone.
        duration_ms: The duration of one full sweep, in milliseconds.
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"child"})
    event_schemas: ClassVar[dict[str, type[Event]]] = {}

    child: Widget = Field(description="The wrapped widget the shimmer paints over.")
    base_color: Color = Field(
        description="The resting tone of the gradient.", default_factory=_shimmer_base
    )
    highlight_color: Color = Field(
        description="The moving highlight tone.", default_factory=_shimmer_highlight
    )
    duration_ms: int = Field(
        default=1200, description="The duration of one full sweep, in milliseconds."
    )

    def child_nodes(self) -> list[Widget]:
        """Return the single wrapped child.

        Returns:
            A one-element list holding the child.
        """
        return [self.child]


class Skeleton(Widget):
    """A childless rectangular shimmer placeholder.

    The leaf variant of :class:`Shimmer`: a single rounded rectangle that sweeps a
    gradient highlight, used to stand in for a line of text or an avatar while the
    real content loads. Qt realizes it as a rounded ``QLabel`` with the same
    gradient repaint loop as :class:`Shimmer`.

    Attributes:
        width: The fixed width in logical pixels, or ``None`` to flex.
        height: The fixed height in logical pixels, or ``None`` to flex.
        radius: The corner radius in logical pixels.
        base_color: The resting tone of the gradient.
        highlight_color: The moving highlight tone.
        duration_ms: The duration of one full sweep, in milliseconds.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {}

    width: float | None = Field(
        default=None,
        description="The fixed width in logical pixels, or ``None`` to flex.",
    )
    height: float | None = Field(
        default=None,
        description="The fixed height in logical pixels, or ``None`` to flex.",
    )
    radius: float = Field(
        default=4.0, description="The corner radius in logical pixels."
    )
    base_color: Color = Field(
        description="The resting tone of the gradient.", default_factory=_shimmer_base
    )
    highlight_color: Color = Field(
        description="The moving highlight tone.", default_factory=_shimmer_highlight
    )
    duration_ms: int = Field(
        default=1200, description="The duration of one full sweep, in milliseconds."
    )
