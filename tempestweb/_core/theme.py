"""Theme and media-query context for the app (phase E9).

A :class:`Theme` (dark/light mode + a small Material-like color palette) and the
:class:`MediaQueryData` (viewport size, density, text-scale, platform dark mode,
orientation) are **input context** the ``view(app)`` reads when it builds the
tree — not nodes in the tree. They never break the "widget tree is the IR"
invariant: the reconciler still diffs a plain widget tree; the theme/media just
change *which* tree the view produces.

Both models are frozen so the runtime can hold them as immutable snapshots and
swap them wholesale (``App.set_theme`` / ``App._update_media``) rather than
mutating in place.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from tempestweb._core.style import Color

__all__ = [
    "ThemeMode",
    "Theme",
    "MediaQueryData",
]


class ThemeMode(StrEnum):
    """The active color-scheme mode of the application.

    ``SYSTEM`` defers to the platform's current setting (read from
    :attr:`MediaQueryData.platform_dark_mode`); ``LIGHT`` / ``DARK`` force the
    respective scheme regardless of the OS.
    """

    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


class Theme(BaseModel):
    """An immutable theme: the active mode plus a small color palette.

    The palette mirrors a subset of Material's color roles. Every color is
    optional: ``None`` lets the renderer fall back to its own default scheme.
    The ``view`` reads :attr:`mode` (resolving ``SYSTEM`` against the media
    query) to decide which colors to apply to the tree it builds.

    Attributes:
        mode: The active color-scheme mode.
        primary: The primary brand color.
        secondary: The secondary brand color.
        background: The screen background color.
        surface: The color of raised surfaces (cards, sheets).
        on_primary: The color of content drawn on ``primary``.
        on_background: The color of content drawn on ``background``.
        error: The color used to signal errors.

    Methods:
        is_dark: Resolve whether the theme renders dark, given the platform
            setting (resolves ``SYSTEM`` against the media query).
    """

    model_config = ConfigDict(frozen=True)

    mode: ThemeMode = ThemeMode.SYSTEM
    primary: Color | None = None
    secondary: Color | None = None
    background: Color | None = None
    surface: Color | None = None
    on_primary: Color | None = None
    on_background: Color | None = None
    error: Color | None = None

    def is_dark(self, *, platform_dark_mode: bool = False) -> bool:
        """Resolve whether the theme renders dark, given the platform setting.

        ``LIGHT`` / ``DARK`` are absolute; ``SYSTEM`` defers to the platform.

        Args:
            platform_dark_mode: The OS dark-mode flag (typically
                :attr:`MediaQueryData.platform_dark_mode`).

        Returns:
            ``True`` when the resolved scheme is dark.
        """
        if self.mode is ThemeMode.DARK:
            return True
        if self.mode is ThemeMode.LIGHT:
            return False
        return platform_dark_mode


class MediaQueryData(BaseModel):
    """An immutable snapshot of the viewport / environment context.

    Read by the ``view`` to build responsively (e.g. switch a column to a row
    above a width breakpoint, scale text by the user's accessibility setting).
    The renderer keeps it current via ``App._update_media`` on resize / config
    change; it is never serialized as tree data — it is context, not a node.

    Attributes:
        width: The viewport width in logical pixels.
        height: The viewport height in logical pixels.
        device_pixel_ratio: The display density (physical / logical pixels).
        text_scale_factor: The user's font-scale accessibility multiplier.
        platform_dark_mode: Whether the OS is currently in dark mode.
        orientation: ``"portrait"`` or ``"landscape"``.
    """

    model_config = ConfigDict(frozen=True)

    width: float = 0.0
    height: float = 0.0
    device_pixel_ratio: float = 1.0
    text_scale_factor: float = 1.0
    platform_dark_mode: bool = False
    orientation: str = "portrait"
