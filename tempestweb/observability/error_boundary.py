"""O2 — Error boundary: catch render errors, show a fallback, report the crash.

A view's ``render`` can raise. Without a boundary one bad subtree takes the whole
app down. :class:`ErrorBoundary` is a core :class:`~tempest_core.Component`
that wraps a subtree: when the wrapped builder raises during render, the boundary
swallows the exception, renders a **fallback** widget in its place (so the rest
of the app keeps rendering), and invokes a **report** hook with the error — which
typically forwards to telemetry (O0).

This complements, rather than replaces, the core's state rollback: rollback
restores consistent state after a failed event; the boundary contains a failed
*render* so a single broken branch does not blank the screen.

Example:
    >>> from tempest_core import Text
    >>> reported: list[ErrorInfo] = []
    >>> def broken() -> Text:
    ...     raise ValueError("boom")
    >>> boundary = ErrorBoundary(child_builder=broken, on_error=reported.append)
    >>> rendered = boundary.render()  # does not raise
    >>> isinstance(rendered, Text)
    True
    >>> reported[0].error_type
    'ValueError'

The decorator form wraps a plain builder function so callers get a
boundary-protected widget without constructing the component by hand::

    @with_error_boundary(on_error=telemetry_report)
    def profile_card() -> Widget: ...
"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps

from pydantic import Field
from tempest_core import Column, Component, Text, Widget

from tempestweb.observability.telemetry import TelemetryProvider

__all__ = [
    "ErrorInfo",
    "ErrorReporter",
    "FallbackBuilder",
    "ChildBuilder",
    "ErrorBoundary",
    "default_fallback",
    "with_error_boundary",
    "telemetry_reporter",
]

#: A builder that produces the subtree the boundary protects. It is called during
#: render and may raise; the boundary contains any exception it throws.
ChildBuilder = Callable[[], Widget]

#: A builder that produces the fallback subtree shown when the child raises. It
#: receives the captured :class:`ErrorInfo` so it can show a tailored message.
FallbackBuilder = Callable[["ErrorInfo"], Widget]

#: A report hook invoked with the captured :class:`ErrorInfo` when a render fails.
ErrorReporter = Callable[["ErrorInfo"], None]


@dataclass(frozen=True)
class ErrorInfo:
    """A captured render failure, passed to the fallback and report hooks.

    Attributes:
        error: The exception instance that was raised during render.
        error_type: The exception class name (e.g. ``"ValueError"``).
        message: The exception's string message.
        stack: The formatted traceback, preserved for reporting rather than
            being swallowed.
    """

    error: BaseException
    error_type: str
    message: str
    stack: str

    @classmethod
    def from_exception(cls, error: BaseException) -> ErrorInfo:
        """Build an :class:`ErrorInfo` from a raised exception.

        Args:
            error: The exception caught during render.

        Returns:
            A populated :class:`ErrorInfo` capturing type, message and stack.
        """
        stack: str = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        return cls(
            error=error,
            error_type=type(error).__name__,
            message=str(error),
            stack=stack,
        )


def default_fallback(info: ErrorInfo) -> Widget:
    """Render a minimal, renderer-agnostic fallback for a failed subtree.

    Args:
        info: The captured render failure.

    Returns:
        A :class:`~tempest_core.Column` showing a generic apology and the
        error type (never the raw stack, which goes to the report hook).
    """
    return Column(
        children=[
            Text(content="Something went wrong."),
            Text(content=f"({info.error_type})"),
        ]
    )


class ErrorBoundary(Component):
    """A component that contains a render error in its wrapped subtree.

    On :meth:`render` it invokes ``child_builder``. If that returns a widget, the
    widget is rendered unchanged. If it raises, the boundary captures the error
    into an :class:`ErrorInfo`, calls ``on_error`` (if set) for reporting, and
    returns ``fallback_builder(info)`` instead — so the exception never escapes
    and the surrounding tree keeps rendering.
    """

    # Component is a Pydantic model; callable fields are stored as-is because the
    # core's Widget already sets ``arbitrary_types_allowed`` in its model_config.
    child_builder: ChildBuilder = Field(
        description="Builds the protected subtree; may raise during render."
    )
    fallback_builder: FallbackBuilder = Field(
        default=default_fallback,
        description="Builds the fallback subtree from the captured error.",
    )
    on_error: ErrorReporter | None = Field(
        default=None,
        description="Optional hook invoked with the captured error for reporting.",
    )

    def render(self) -> Widget:
        """Render the protected subtree, falling back on any render error.

        Returns:
            The child's widget on success, or the fallback widget on failure.
        """
        try:
            return self.child_builder()
        except Exception as exc:  # noqa: BLE001 - boundary intentionally broad
            info: ErrorInfo = ErrorInfo.from_exception(exc)
            if self.on_error is not None:
                self.on_error(info)
            return self.fallback_builder(info)


def with_error_boundary(
    *,
    fallback_builder: FallbackBuilder = default_fallback,
    on_error: ErrorReporter | None = None,
) -> Callable[[ChildBuilder], Callable[[], ErrorBoundary]]:
    """Decorate a widget builder so it returns a boundary-wrapped component.

    Args:
        fallback_builder: Builds the fallback subtree from the captured error.
        on_error: Optional report hook invoked on a render failure.

    Returns:
        A decorator that turns a ``() -> Widget`` builder into a ``() ->
        ErrorBoundary`` builder, wrapping the original so its render errors are
        contained.
    """

    def decorator(builder: ChildBuilder) -> Callable[[], ErrorBoundary]:
        """Wrap ``builder`` so calling it yields a protected :class:`ErrorBoundary`.

        Args:
            builder: The original widget builder to protect.

        Returns:
            A zero-argument callable producing an :class:`ErrorBoundary`.
        """

        @wraps(builder)
        def wrapped() -> ErrorBoundary:
            return ErrorBoundary(
                child_builder=builder,
                fallback_builder=fallback_builder,
                on_error=on_error,
            )

        return wrapped

    return decorator


def telemetry_reporter(
    provider: TelemetryProvider, *, event: str = "render_error"
) -> ErrorReporter:
    """Build a report hook that forwards captured errors to telemetry (O0).

    Args:
        provider: The telemetry provider that receives the error event.
        event: The telemetry event name to emit.

    Returns:
        An :data:`ErrorReporter` that tracks ``event`` with the error type,
        message and stack as properties.
    """

    def report(info: ErrorInfo) -> None:
        """Forward a captured render error to telemetry.

        Args:
            info: The captured render failure.

        Returns:
            None.
        """
        provider.track(
            event,
            {
                "error_type": info.error_type,
                "message": info.message,
                "stack": info.stack,
            },
        )

    return report
