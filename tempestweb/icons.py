"""Material 3 + Lucide icons for tempestweb apps.

The renderer-agnostic core ships an :class:`~tempest_core.widgets.Icon` widget and
a curated **Lucide** set (:class:`~tempest_core.icons.Icons`). tempestweb adds a
second vendored set — **Material Symbols (Outlined)** — and a tiny façade so an
app picks an icon set in one obvious call:

    from tempestweb.icons import material_icon, lucide_icon, MaterialIcons, Icons

    material_icon(MaterialIcons.HOME)        # Material Symbols "home"
    lucide_icon(Icons.MAIL)                  # Lucide "mail"
    material_icon("settings", size=20.0)

Both sets are rendered client-side as inline SVG from vendored path data
(``client/icons/{lucide,material}.js``) — no icon font, no network, offline/PWA
safe. The set is encoded as a ``"set:"`` prefix on the :class:`Icon` name
(``"material:home"`` / ``"lucide:mail"``), which the client resolves; a bare name
stays Lucide for compatibility with the core's ``Icon`` and input icon slots.

Need a glyph that is not vendored? Ship its raw SVG path over the wire with
:func:`custom_icon` (no client-side registration required), or register it on
both sides (Python :func:`register_icon` + the client ``registerIcon``).
"""

from __future__ import annotations

from enum import StrEnum

from tempest_core.icons import (
    ICON_PATHS,
    Icons,
    icon_names,
    icon_path,
    register_icon,
)
from tempest_core.style import Style
from tempest_core.widgets import Icon

__all__ = [
    "ICON_PATHS",
    "Icon",
    "Icons",
    "MaterialIcons",
    "custom_icon",
    "icon_names",
    "icon_path",
    "lucide_icon",
    "material_icon",
    "register_icon",
]


class MaterialIcons(StrEnum):
    """Names of the vendored Material Symbols (Outlined) icons.

    A :class:`~enum.StrEnum`, so each member doubles as its snake_case string —
    ``MaterialIcons.HOME == "home"`` — giving editor autocomplete while staying a
    plain ``str`` anywhere a name is accepted (e.g. ``material_icon("home")``).
    Apps can still pass any other Material Symbols name as a raw string once it is
    vendored on the client.
    """

    ACCOUNT_CIRCLE = "account_circle"
    ADD = "add"
    ARROW_BACK = "arrow_back"
    ARROW_FORWARD = "arrow_forward"
    CALENDAR_MONTH = "calendar_month"
    CALL = "call"
    CHECK = "check"
    CHEVRON_LEFT = "chevron_left"
    CHEVRON_RIGHT = "chevron_right"
    CLOSE = "close"
    DELETE = "delete"
    DONE_ALL = "done_all"
    DOWNLOAD = "download"
    EDIT = "edit"
    ERROR = "error"
    FAVORITE = "favorite"
    HOME = "home"
    INFO = "info"
    KEYBOARD_ARROW_DOWN = "keyboard_arrow_down"
    KEYBOARD_ARROW_UP = "keyboard_arrow_up"
    LOCK = "lock"
    LOCK_OPEN = "lock_open"
    LOGIN = "login"
    LOGOUT = "logout"
    MAIL = "mail"
    MENU = "menu"
    MORE_VERT = "more_vert"
    NOTIFICATIONS = "notifications"
    PERSON = "person"
    REMOVE = "remove"
    SCHEDULE = "schedule"
    SEARCH = "search"
    SETTINGS = "settings"
    SHARE = "share"
    STAR = "star"
    VISIBILITY = "visibility"
    VISIBILITY_OFF = "visibility_off"
    WARNING = "warning"


def material_icon(
    name: str,
    *,
    size: float | None = None,
    key: str | None = None,
    style: Style | None = None,
) -> Icon:
    """Build an :class:`Icon` drawn from the Material Symbols (Outlined) set.

    Args:
        name: A Material Symbols name (e.g. ``"home"`` or :class:`MaterialIcons`).
        size: The icon's edge length in logical pixels, or ``None`` to scale with
            the surrounding font size.
        key: Optional reconciler key.
        style: Optional :class:`~tempest_core.style.Style`; its ``color`` tints the
            icon (it is drawn in ``currentColor``).

    Returns:
        An :class:`Icon` whose name is prefixed ``"material:"`` so the client
        resolves it against the Material set.
    """
    return Icon(name=f"material:{name}", size=size, key=key, style=style)


def lucide_icon(
    name: str,
    *,
    size: float | None = None,
    key: str | None = None,
    style: Style | None = None,
) -> Icon:
    """Build an :class:`Icon` drawn from the Lucide set (the default set).

    Args:
        name: A Lucide name (e.g. ``"mail"`` or :class:`~tempest_core.icons.Icons`).
        size: The icon's edge length in logical pixels, or ``None`` to scale with
            the surrounding font size.
        key: Optional reconciler key.
        style: Optional :class:`~tempest_core.style.Style`; its ``color`` tints the
            icon.

    Returns:
        An :class:`Icon` whose name is prefixed ``"lucide:"``.
    """
    return Icon(name=f"lucide:{name}", size=size, key=key, style=style)


def custom_icon(
    path: str,
    *,
    size: float | None = None,
    key: str | None = None,
    style: Style | None = None,
) -> Icon:
    """Build an :class:`Icon` from a raw SVG path, shipped over the wire.

    Use for a one-off glyph that is not vendored: the path ``d`` rides in the icon
    name (``"path:<d>"``) so the client needs no prior registration. The path is
    drawn stroked on a ``0 0 24 24`` grid in ``currentColor`` (the Lucide
    convention), so author it accordingly.

    Args:
        path: The SVG path ``d`` string (24x24 grid, stroke-based).
        size: The icon's edge length in logical pixels, or ``None`` to scale with
            the surrounding font size.
        key: Optional reconciler key.
        style: Optional :class:`~tempest_core.style.Style`.

    Returns:
        An :class:`Icon` whose name is prefixed ``"path:"``.
    """
    return Icon(name=f"path:{path}", size=size, key=key, style=style)
