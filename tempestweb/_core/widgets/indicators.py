"""Progress indicator leaf widgets: ``ProgressBar`` and ``Spinner``.

Non-interactive feedback widgets (no events). A :class:`ProgressBar` shows
either a determinate fraction or an indeterminate (looping) bar; a
:class:`Spinner` is a circular activity indicator.
"""

from __future__ import annotations

from pydantic import Field

from tempestweb._core.widgets.base import Widget

__all__ = ["ProgressBar", "Spinner"]


class ProgressBar(Widget):
    """A horizontal progress bar.

    Attributes:
        value: The completed fraction in ``[0.0, 1.0]`` (ignored when
            ``indeterminate`` is set).
        indeterminate: When ``True``, render a looping bar with no fixed value
            (work of unknown duration).
    """

    value: float = Field(
        description="The completed fraction in ``[0.0, 1.0]`` (ignored when "
        "``indeterminate`` is set).",
        default=0.0,
        ge=0.0,
        le=1.0,
    )
    indeterminate: bool = Field(
        default=False,
        description="When ``True``, render a looping bar with no fixed value (work of "
        "unknown duration).",
    )


class Spinner(Widget):
    """A circular activity indicator (always indeterminate).

    Attributes:
        size: The indicator's diameter in logical pixels, or ``None`` for the
            renderer default.
    """

    size: float | None = Field(
        default=None,
        description="The indicator's diameter in logical pixels, or ``None`` for the "
        "renderer default.",
    )
