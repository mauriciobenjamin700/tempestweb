"""Explicit, core-driven animation framework.

This module holds the *driver* half of tempestroid's animation system, which
lives entirely in the renderer-agnostic core so the reconciler stays pure: an
:class:`AnimationController` advances a normalized ``value`` (0.0..1.0) on the
app's frame clock, a :class:`Tween` interpolates a typed value (``float``,
:class:`~tempestroid.style.Color`, :class:`~tempestroid.style.Edge` or a numeric
``tuple``) from that ``value``, and the user's ``view`` reads the interpolated
result to build a tree whose styles are already at their per-frame target.

Because the interpolation happens here — not in either leaf renderer — both the
Qt and Compose backends only ever see *final* props for the current frame, so
the divergence between "interpolate in the core" (Qt) and "drive the native
animation engine" (Compose) is confined to the leaf renderers (documented in the
conformance suite).

The :class:`AnimationController` is wired to an :class:`~tempestroid.core.state.App`
lazily — :meth:`AnimationController.forward`/:meth:`AnimationController.reverse`
bind the controller to whatever app registered it — so this module never imports
``App`` and there is no import cycle (the binding is duck-typed through a small
:class:`_AppClock` protocol).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Generic, Protocol, TypeVar, cast, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from tempestweb._core.style import Color, Curve, Edge

__all__ = ["Spring", "AnimationController", "Tween"]

T = TypeVar("T")


@runtime_checkable
class _AppClock(Protocol):
    """The slice of :class:`~tempestroid.core.state.App` an animation drives.

    Declared structurally so :class:`AnimationController` binds to an app via
    duck typing, keeping ``animation.py`` free of any ``App`` import (no cycle).
    """

    def register_animation(self, ctrl: AnimationController) -> None:
        """Register an active controller on the app's frame clock."""
        ...

    def unregister_animation(self, ctrl: AnimationController) -> None:
        """Remove a finished/stopped controller from the app's frame clock."""
        ...


class Spring(BaseModel):
    """A spring's physical parameters, used instead of a fixed duration.

    When a :class:`AnimationController` is given a :class:`Spring`, it advances
    its ``value`` by integrating a damped harmonic oscillator toward the target
    (1.0 on ``forward``, 0.0 on ``reverse``) rather than easing over a fixed
    ``duration_s``. Frozen so it can be compared/diffed by value.

    Attributes:
        stiffness: The spring constant ``k`` (higher snaps faster).
        damping: The damping coefficient ``c`` (higher settles with less bounce).
        mass: The attached mass ``m`` (higher is more sluggish).
    """

    model_config = ConfigDict(frozen=True)

    stiffness: float = Field(default=300.0, gt=0.0)
    damping: float = Field(default=30.0, ge=0.0)
    mass: float = Field(default=1.0, gt=0.0)


def _apply_curve(curve: Curve, t: float) -> float:
    """Map a linear progress ``t`` (0..1) through an easing curve.

    These are pure, dependency-free approximations of the named curves so the
    core can interpolate without a renderer. The leaf renderers may apply their
    own native curve to the *same* ``Curve`` value; the core's job is only to
    produce a smooth per-frame value for the simulator/test clock.

    Args:
        curve: The easing curve to apply.
        t: Linear progress, clamped to ``[0.0, 1.0]``.

    Returns:
        The eased progress, in ``[0.0, 1.0]`` for the monotone curves and
        possibly slightly outside for the overshoot curves (``ELASTIC``).
    """
    t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
    if curve is Curve.LINEAR:
        return t
    if curve is Curve.EASE_IN:
        return t * t
    if curve is Curve.EASE_OUT:
        return 1.0 - (1.0 - t) * (1.0 - t)
    if curve in (Curve.EASE_IN_OUT, Curve.EASE):
        # Smooth cubic ease-in-out (matches CSS ``ease``/``ease-in-out`` closely).
        if t < 0.5:
            return 4.0 * t * t * t
        f = 2.0 * t - 2.0
        return 1.0 + f * f * f / 2.0
    if curve is Curve.BOUNCE:
        return _bounce_out(t)
    if curve is Curve.ELASTIC:
        if t in (0.0, 1.0):
            return t
        c4 = (2.0 * math.pi) / 3.0
        return (
            -(2.0 ** (10.0 * t - 10.0)) * math.sin((t * 10.0 - 10.75) * c4)
        )
    return t


def _bounce_out(t: float) -> float:
    """Compute the ``ease-out`` bounce curve (decelerating with rebounds).

    Args:
        t: Linear progress, in ``[0.0, 1.0]``.

    Returns:
        The bounced progress, in ``[0.0, 1.0]``.
    """
    n1 = 7.5625
    d1 = 2.75
    if t < 1.0 / d1:
        return n1 * t * t
    if t < 2.0 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375


class AnimationController:
    """Drives a normalized ``value`` on the app's frame clock.

    A controller is renderer-agnostic: it owns only its progress (``value``,
    0.0..1.0), the direction it is moving (``forward`` toward 1.0, ``reverse``
    toward 0.0), and how to advance — either an eased ramp over ``duration_s`` or
    a :class:`Spring` integration. The app's clock calls :meth:`_advance` once
    per frame with the elapsed ``dt`` and removes the controller when it reports
    completion.

    The controller binds to an app lazily: it stores no ``App`` reference until
    :meth:`forward`/:meth:`reverse` is called *after* the app has registered it
    (via :meth:`bind`), so a controller can be constructed in a ``view`` without
    a circular import.

    Attributes:
        value: The current progress, 0.0..1.0 — read by the ``view``.

    Methods:
        bind: Attach the controller to an app's frame clock.
        forward: Animate ``value`` toward 1.0 and (re)register on the app clock.
        reverse: Animate ``value`` toward 0.0 and (re)register on the app clock.
        stop: Halt the animation and unregister from the app clock.
    """

    def __init__(
        self,
        duration_s: float,
        curve: Curve = Curve.EASE_IN_OUT,
        spring: Spring | None = None,
        *,
        time_source: Callable[[], float] | None = None,
    ) -> None:
        """Initialize the controller.

        Args:
            duration_s: The ramp duration in seconds (ignored when ``spring`` is
                given). Must be positive for a fixed-duration ramp.
            curve: The easing curve applied to the linear ramp.
            spring: Optional spring parameters; when set, the controller
                integrates a damped oscillator instead of easing over a fixed
                duration.
            time_source: Optional injectable monotonic clock (seconds). Tests
                pass a deterministic source; in production the app supplies its
                own loop clock, so this is normally left unset.
        """
        self.duration_s: float = duration_s
        self.curve: Curve = curve
        self.spring: Spring | None = spring
        self.value: float = 0.0
        self._time_source: Callable[[], float] | None = time_source
        self._dir: int = 0
        self._elapsed: float = 0.0
        # Spring integration state (velocity), only used when ``spring`` is set.
        self._velocity: float = 0.0
        self._app: _AppClock | None = None

    def bind(self, app: _AppClock) -> None:
        """Attach the controller to an app's frame clock.

        Called by :meth:`~tempestroid.core.state.App.register_animation` so a
        later :meth:`stop` can unregister, and so :meth:`forward`/:meth:`reverse`
        can (re)register even if invoked after construction.

        Args:
            app: The app driving this controller's frames.
        """
        self._app = app

    def forward(self) -> None:
        """Animate ``value`` toward 1.0 and (re)register on the app clock."""
        self._dir = 1
        if self._app is not None:
            self._app.register_animation(self)

    def reverse(self) -> None:
        """Animate ``value`` toward 0.0 and (re)register on the app clock."""
        self._dir = -1
        if self._app is not None:
            self._app.register_animation(self)

    def stop(self) -> None:
        """Halt the animation and unregister from the app clock."""
        self._dir = 0
        self._velocity = 0.0
        if self._app is not None:
            self._app.unregister_animation(self)

    def _advance(self, dt: float) -> bool:
        """Advance the controller by ``dt`` seconds toward its target.

        Args:
            dt: Elapsed wall-clock time since the previous frame, in seconds.

        Returns:
            ``True`` when the controller has reached its target (0.0 on reverse,
            1.0 on forward) and should be unregistered; ``False`` otherwise.
        """
        if self._dir == 0:
            return True
        if dt < 0.0:
            dt = 0.0
        if self.spring is not None:
            return self._advance_spring(dt)
        return self._advance_ramp(dt)

    def _advance_ramp(self, dt: float) -> bool:
        """Advance an eased fixed-duration ramp.

        Args:
            dt: Elapsed time since the previous frame, in seconds.

        Returns:
            ``True`` when the ramp has reached its target end, else ``False``.
        """
        target = 1.0 if self._dir > 0 else 0.0
        if self.duration_s <= 0.0:
            self.value = target
            self._dir = 0
            return True
        self._elapsed += dt
        progress = self._elapsed / self.duration_s
        if progress >= 1.0:
            self.value = target
            self._elapsed = 0.0
            self._dir = 0
            return True
        eased = _apply_curve(self.curve, progress)
        # On reverse, walk the eased curve back from 1.0 toward 0.0.
        self.value = eased if self._dir > 0 else 1.0 - eased
        return False

    def _advance_spring(self, dt: float) -> bool:
        """Integrate the damped harmonic oscillator one frame toward the target.

        Args:
            dt: Elapsed time since the previous frame, in seconds.

        Returns:
            ``True`` when the spring has settled at its target, else ``False``.
        """
        spring = self.spring
        assert spring is not None  # narrowed by the caller
        target = 1.0 if self._dir > 0 else 0.0
        displacement = self.value - target
        force = -spring.stiffness * displacement - spring.damping * self._velocity
        acceleration = force / spring.mass
        self._velocity += acceleration * dt
        self.value += self._velocity * dt
        # Settle once both the displacement and the velocity are negligible.
        if abs(self.value - target) < 0.001 and abs(self._velocity) < 0.001:
            self.value = target
            self._velocity = 0.0
            self._dir = 0
            return True
        return False


class Tween(BaseModel, Generic[T]):
    """A linear interpolator between two typed endpoints.

    Supports ``float``, :class:`~tempestroid.style.Color` (per-channel),
    :class:`~tempestroid.style.Edge` (per-side) and numeric ``tuple`` endpoints.
    The ``view`` reads :meth:`at` with an :class:`AnimationController`'s ``value``
    to get the per-frame interpolated value, which it then feeds into a
    :class:`~tempestroid.style.Style` — so the interpolation stays in the core.

    Type Args:
        T: The endpoint type being interpolated.

    Attributes:
        begin: The value at ``t == 0.0``.
        end: The value at ``t == 1.0``.

    Methods:
        at: Interpolate between ``begin`` and ``end`` at fraction ``t``.
    """

    model_config = ConfigDict(frozen=True)

    begin: T
    end: T

    def at(self, t: float) -> T:
        """Interpolate between :attr:`begin` and :attr:`end` at fraction ``t``.

        Args:
            t: The interpolation fraction, typically an
                :class:`AnimationController`'s ``value`` (0.0..1.0). Values
                outside ``[0, 1]`` extrapolate linearly.

        Returns:
            The interpolated value, of the same type as the endpoints.

        Raises:
            TypeError: If the endpoint type is not a supported interpolatable
                type.
        """
        begin: object = self.begin
        end: object = self.end
        if isinstance(begin, bool) or isinstance(end, bool):
            raise TypeError("Tween does not interpolate bool endpoints")
        if isinstance(begin, (int, float)) and isinstance(end, (int, float)):
            return _lerp_float(float(begin), float(end), t)  # type: ignore[return-value]
        if isinstance(begin, Color) and isinstance(end, Color):
            return _lerp_color(begin, end, t)  # type: ignore[return-value]
        if isinstance(begin, Edge) and isinstance(end, Edge):
            return _lerp_edge(begin, end, t)  # type: ignore[return-value]
        if isinstance(begin, tuple) and isinstance(end, tuple):
            a = cast("tuple[float, ...]", begin)
            b = cast("tuple[float, ...]", end)
            return _lerp_tuple(a, b, t)  # type: ignore[return-value]
        type_name: str = type(cast("object", begin)).__name__
        raise TypeError(
            f"Tween cannot interpolate endpoints of type {type_name}"
        )


def _lerp_float(a: float, b: float, t: float) -> float:
    """Linearly interpolate two floats.

    Args:
        a: The value at ``t == 0.0``.
        b: The value at ``t == 1.0``.
        t: The interpolation fraction.

    Returns:
        ``a + (b - a) * t``.
    """
    return a + (b - a) * t


def _lerp_color(a: Color, b: Color, t: float) -> Color:
    """Interpolate two colors per channel (r, g, b rounded; alpha as float).

    Args:
        a: The color at ``t == 0.0``.
        b: The color at ``t == 1.0``.
        t: The interpolation fraction.

    Returns:
        The interpolated color.
    """
    return Color(
        r=round(_lerp_float(a.r, b.r, t)),
        g=round(_lerp_float(a.g, b.g, t)),
        b=round(_lerp_float(a.b, b.b, t)),
        a=_lerp_float(a.a, b.a, t),
    )


def _lerp_edge(a: Edge, b: Edge, t: float) -> Edge:
    """Interpolate two edges per side.

    Args:
        a: The edge at ``t == 0.0``.
        b: The edge at ``t == 1.0``.
        t: The interpolation fraction.

    Returns:
        The interpolated edge.
    """
    return Edge(
        top=_lerp_float(a.top, b.top, t),
        right=_lerp_float(a.right, b.right, t),
        bottom=_lerp_float(a.bottom, b.bottom, t),
        left=_lerp_float(a.left, b.left, t),
    )


def _lerp_tuple(
    a: tuple[float, ...], b: tuple[float, ...], t: float
) -> tuple[float, ...]:
    """Interpolate two equal-length numeric tuples element-wise.

    Args:
        a: The tuple at ``t == 0.0``.
        b: The tuple at ``t == 1.0``.
        t: The interpolation fraction.

    Returns:
        The interpolated tuple.

    Raises:
        ValueError: If the tuples differ in length.
    """
    if len(a) != len(b):
        raise ValueError("Tween tuple endpoints must have the same length")
    return tuple(_lerp_float(x, y, t) for x, y in zip(a, b, strict=True))
