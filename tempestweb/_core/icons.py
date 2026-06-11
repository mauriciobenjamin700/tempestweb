"""A curated, dependency-free icon set (Lucide-style line icons).

The framework ships its own small, opinionated icon set so apps get crisp,
modern line icons without pulling in a runtime icon dependency on either
renderer. Each icon is normalized to a **single SVG path ``d`` string on a
24x24 viewBox**: stroke-based, no fill, intended to be stroked with width ~2,
round line cap and join, in ``currentColor``. Any circles, lines, rectangles or
polylines from the source geometry are expressed as path commands so each icon
is exactly one ``d`` string — both leaf renderers only ever build a single
path.

The geometry follows `Lucide <https://lucide.dev>`_ (ISC-licensed), so the
icons match the familiar modern line-icon look rather than ad-hoc shapes.

Public surface:
    - :data:`ICON_PATHS`: ``name -> d`` mapping for every curated icon.
    - :class:`Icons`: a :class:`~enum.StrEnum` of the curated names, so callers
      get ``Icons.EYE == "eye"`` with autocomplete.
    - :func:`icon_path`: resolve a name (an :class:`Icons` member or a raw
      ``str``) to its ``d`` string, or ``None`` when unknown.
    - :func:`icon_names`: the sorted list of available icon names.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from enum import StrEnum
from pathlib import Path

__all__ = [
    "ICON_PATHS",
    "Icons",
    "icon_path",
    "icon_names",
    "svg_to_path",
    "register_icon",
]

#: Custom icons registered at runtime (``register_icon``): name -> ``d`` string.
#: Consulted by :func:`icon_path` after the curated :data:`ICON_PATHS`, so an app
#: can use its own SVG glyphs through the same ``Icon`` / input-slot machinery.
_CUSTOM_PATHS: dict[str, str] = {}


#: Curated icon name -> normalized single-path ``d`` string (24x24 viewBox,
#: stroke-based, ``currentColor``). Geometry mirrors Lucide (ISC-licensed); every
#: shape is flattened into one path so a renderer builds a single stroked path.
ICON_PATHS: dict[str, str] = {
    "eye": (
        "M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 "
        ".696 10.75 10.75 0 0 1-19.876 0 M15 12 a3 3 0 1 1-6 0 3 3 0 0 1 6 0 Z"
    ),
    "eye-off": (
        "M10.733 5.076 a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 "
        "10.747 10.747 0 0 1-1.444 2.49 "
        "M14.084 14.158 a3 3 0 0 1-4.242-4.242 "
        "M17.479 17.499 a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 "
        "10.75 10.75 0 0 1 4.446-5.143 "
        "M2 2 l20 20"
    ),
    "lock": (
        "M5 11 a2 2 0 0 1 2-2 h10 a2 2 0 0 1 2 2 v8 a2 2 0 0 1-2 2 H7 a2 2 0 0 "
        "1-2-2 Z M7 11 V7 a5 5 0 0 1 10 0 v4"
    ),
    "unlock": (
        "M5 11 a2 2 0 0 1 2-2 h10 a2 2 0 0 1 2 2 v8 a2 2 0 0 1-2 2 H7 a2 2 0 0 "
        "1-2-2 Z M7 11 V7 a5 5 0 0 1 9.9-1"
    ),
    "search": ("M21 21 l-4.34-4.34 M11 19 a8 8 0 1 0 0-16 8 8 0 0 0 0 16 Z"),
    "x": "M18 6 6 18 M6 6 l12 12",
    "check": "M20 6 9 17 l-5-5",
    "chevron-down": "M6 9 l6 6 6-6",
    "chevron-up": "M18 15 l-6-6-6 6",
    "chevron-left": "M15 18 l-6-6 6-6",
    "chevron-right": "M9 18 l6-6-6-6",
    "arrow-left": "M19 12 H5 M12 19 l-7-7 7-7",
    "arrow-right": "M5 12 h14 M12 5 l7 7-7 7",
    "plus": "M5 12 h14 M12 5 v14",
    "minus": "M5 12 h14",
    "user": (
        "M19 21 v-2 a4 4 0 0 0-4-4 H9 a4 4 0 0 0-4 4 v2 "
        "M12 11 a4 4 0 1 0 0-8 4 4 0 0 0 0 8 Z"
    ),
    "mail": (
        "M22 7 l-8.991 5.727 a2 2 0 0 1-2.018 0 L2 7 "
        "M4 4 h16 c1.1 0 2 .9 2 2 v12 c0 1.1-.9 2-2 2 H4 c-1.1 0-2-.9-2-2 V6 "
        "c0-1.1.9-2 2-2 Z"
    ),
    "phone": (
        "M13.832 16.568 a1 1 0 0 0 1.213-.303 l.355-.465 "
        "A2 2 0 0 1 17 15 h3 a2 2 0 0 1 2 2 v3 a2 2 0 0 1-2 2 "
        "A18 18 0 0 1 2 4 a2 2 0 0 1 2-2 h3 a2 2 0 0 1 2 2 v3 "
        "a2 2 0 0 1-.8 1.6 l-.468.351 a1 1 0 0 0-.292 1.233 "
        "a14 14 0 0 0 6.06 6.0 Z"
    ),
    "calendar": (
        "M8 2 v4 M16 2 v4 "
        "M3 10 h18 "
        "M5 4 h14 a2 2 0 0 1 2 2 v14 a2 2 0 0 1-2 2 H5 a2 2 0 0 1-2-2 V6 "
        "a2 2 0 0 1 2-2 Z"
    ),
    "clock": ("M12 6 v6 l4 2 M12 2 a10 10 0 1 0 0 20 10 10 0 0 0 0-20 Z"),
    "trash": (
        "M3 6 h18 M19 6 v14 c0 1-1 2-2 2 H7 c-1 0-2-1-2-2 V6 "
        "M8 6 V4 c0-1 1-2 2-2 h4 c1 0 2 1 2 2 v2 "
        "M10 11 v6 M14 11 v6"
    ),
    "menu": "M4 12 h16 M4 6 h16 M4 18 h16",
    "home": ("M3 9 l9-7 9 7 v11 a2 2 0 0 1-2 2 H5 a2 2 0 0 1-2-2 z M9 22 V12 h6 v10"),
    "settings": (
        "M12.22 2 h-.44 a2 2 0 0 0-2 2 v.18 a2 2 0 0 1-1 1.73 l-.43.25 "
        "a2 2 0 0 1-2 0 l-.15-.08 a2 2 0 0 0-2.73.73 l-.22.38 "
        "a2 2 0 0 0 .73 2.73 l.15.1 a2 2 0 0 1 1 1.72 v.51 "
        "a2 2 0 0 1-1 1.74 l-.15.09 a2 2 0 0 0-.73 2.73 l.22.38 "
        "a2 2 0 0 0 2.73.73 l.15-.08 a2 2 0 0 1 2 0 l.43.25 "
        "a2 2 0 0 1 1 1.73 V20 a2 2 0 0 0 2 2 h.44 "
        "a2 2 0 0 0 2-2 v-.18 a2 2 0 0 1 1-1.73 l.43-.25 "
        "a2 2 0 0 1 2 0 l.15.08 a2 2 0 0 0 2.73-.73 l.22-.39 "
        "a2 2 0 0 0-.73-2.73 l-.15-.08 a2 2 0 0 1-1-1.74 v-.5 "
        "a2 2 0 0 1 1-1.74 l.15-.09 a2 2 0 0 0 .73-2.73 l-.22-.38 "
        "a2 2 0 0 0-2.73-.73 l-.15.08 a2 2 0 0 1-2 0 l-.43-.25 "
        "a2 2 0 0 1-1-1.73 V4 a2 2 0 0 0-2-2 Z "
        "M15 12 a3 3 0 1 1-6 0 3 3 0 0 1 6 0 Z"
    ),
    "star": (
        "M11.525 2.295 a.53.53 0 0 1 .95 0 l2.31 4.679 "
        "a2.123 2.123 0 0 0 1.595 1.16 l5.166.756 "
        "a.53.53 0 0 1 .294.904 l-3.736 3.638 "
        "a2.123 2.123 0 0 0-.611 1.878 l.882 5.14 "
        "a.53.53 0 0 1-.771.56 l-4.618-2.428 "
        "a2.122 2.122 0 0 0-1.973 0 L6.396 21.01 "
        "a.53.53 0 0 1-.77-.56 l.881-5.139 "
        "a2.122 2.122 0 0 0-.611-1.879 L2.16 9.795 "
        "a.53.53 0 0 1 .294-.906 l5.165-.755 "
        "a2.122 2.122 0 0 0 1.597-1.16 Z"
    ),
    "heart": (
        "M2 9.5 a5.5 5.5 0 0 1 9.591-3.676 .56.56 0 0 0 .818 0 "
        "A5.49 5.49 0 0 1 22 9.5 c0 2.29-1.5 4-3 5.5 l-5.492 5.313 "
        "a2 2 0 0 1-3.016 0 L5 14.5 c-1.5-1.5-3-3.2-3-5 Z"
    ),
    "bell": (
        "M10.268 21 a2 2 0 0 0 3.464 0 "
        "M3.262 15.326 A1 1 0 0 0 4 17 h16 a1 1 0 0 0 .74-1.673 "
        "C19.41 13.956 18 12.499 18 8 "
        "A6 6 0 0 0 6 8 c0 4.499-1.411 5.956-2.738 7.326 Z"
    ),
    "info": ("M12 16 v-4 M12 8 h.01 M12 2 a10 10 0 1 0 0 20 10 10 0 0 0 0-20 Z"),
}


class Icons(StrEnum):
    """The names of the curated built-in icons.

    A :class:`~enum.StrEnum` so each member doubles as its kebab-case string —
    ``Icons.EYE == "eye"`` — giving editor autocomplete while still being a
    plain ``str`` anywhere a name is accepted (e.g. ``Icon(name=Icons.SEARCH)``
    or ``Input(leading_icon=Icons.MAIL)``).

    Attributes:
        EYE: An open eye; toggle to reveal hidden content (e.g. a password).
        EYE_OFF: An eye with a slash; toggle to hide content (e.g. a password).
        LOCK: A closed padlock, denoting secured or locked state.
        UNLOCK: An open padlock, denoting unsecured or unlocked state.
        SEARCH: A magnifying glass, for search inputs and actions.
        X: A close cross, for dismissing dialogs, chips, or clearing input.
        CHECK: A checkmark, indicating success, confirmation, or selection.
        CHEVRON_DOWN: A downward chevron, for expanding or opening dropdowns.
        CHEVRON_UP: An upward chevron, for collapsing or closing dropdowns.
        CHEVRON_LEFT: A left-pointing chevron, for back or previous navigation.
        CHEVRON_RIGHT: A right-pointing chevron, for forward or next navigation.
        ARROW_LEFT: A left arrow, for back navigation or moving content left.
        ARROW_RIGHT: A right arrow, for forward navigation or moving content
            right.
        PLUS: A plus sign, for add, create, or increment actions.
        MINUS: A minus sign, for remove or decrement actions.
        USER: A person silhouette, for accounts, profiles, or authors.
        MAIL: An envelope, for email addresses, messages, or contact actions.
        PHONE: A telephone handset, for phone numbers or call actions.
        CALENDAR: A calendar grid, for dates, schedules, or date pickers.
        CLOCK: A clock face, for times, durations, or recent activity.
        TRASH: A trash can, for delete or discard actions.
        MENU: A three-line "hamburger", for opening a navigation menu.
        HOME: A house, for the home screen or landing page.
        SETTINGS: A gear, for settings, preferences, or configuration.
        STAR: A five-point star, for favorites, ratings, or bookmarks.
        HEART: A heart, for likes, favorites, or wishlist actions.
        BELL: A bell, for notifications or alerts.
        INFO: An "i" in a circle, for informational hints or details.
    """

    EYE = "eye"
    EYE_OFF = "eye-off"
    LOCK = "lock"
    UNLOCK = "unlock"
    SEARCH = "search"
    X = "x"
    CHECK = "check"
    CHEVRON_DOWN = "chevron-down"
    CHEVRON_UP = "chevron-up"
    CHEVRON_LEFT = "chevron-left"
    CHEVRON_RIGHT = "chevron-right"
    ARROW_LEFT = "arrow-left"
    ARROW_RIGHT = "arrow-right"
    PLUS = "plus"
    MINUS = "minus"
    USER = "user"
    MAIL = "mail"
    PHONE = "phone"
    CALENDAR = "calendar"
    CLOCK = "clock"
    TRASH = "trash"
    MENU = "menu"
    HOME = "home"
    SETTINGS = "settings"
    STAR = "star"
    HEART = "heart"
    BELL = "bell"
    INFO = "info"


def icon_path(name: str) -> str | None:
    """Resolve an icon name to its single-path ``d`` string.

    Args:
        name: An :class:`Icons` member or a raw icon name string. As
            :class:`Icons` is a :class:`~enum.StrEnum`, both forms are accepted
            transparently.

    Returns:
        The icon's ``d`` string — from the curated set, else a custom icon
        registered via :func:`register_icon` — or ``None`` when the name is
        unknown (the renderer then falls back to a platform icon / the name).
    """
    key = str(name)
    curated = ICON_PATHS.get(key)
    if curated is not None:
        return curated
    return _CUSTOM_PATHS.get(key)


def icon_names() -> list[str]:
    """Return the names of every available icon, sorted alphabetically.

    Includes both the curated set and any custom icons registered via
    :func:`register_icon`.

    Returns:
        A sorted list of available icon names (always a list, never raises).
    """
    return sorted({*ICON_PATHS, *_CUSTOM_PATHS})


# SVG element names appear namespaced (``{http://www.w3.org/2000/svg}path``);
# this strips the namespace so we can match on the local tag.
def _local_tag(tag: str) -> str:
    """Return an XML element's local name, dropping any ``{ns}`` prefix.

    Args:
        tag: The (possibly namespaced) element tag.

    Returns:
        The local tag name.
    """
    return tag.rsplit("}", 1)[-1]


def _shape_to_path(tag: str, attrib: dict[str, str]) -> str:
    """Convert a single SVG shape element into path ``d`` commands.

    Handles the element kinds the curated icons (and most line-icon SVGs) use:
    ``path`` (verbatim ``d``), ``circle``, ``ellipse``, ``line``, ``rect``
    (square corners), ``polyline`` and ``polygon``. Unknown elements yield an
    empty string and are skipped.

    Args:
        tag: The element's local tag name.
        attrib: The element's attributes.

    Returns:
        A ``d`` fragment for this shape, or ``""`` when unsupported.
    """

    def num(key: str, default: float = 0.0) -> float:
        try:
            return float(attrib.get(key, default))
        except ValueError:
            return default

    if tag == "path":
        return attrib.get("d", "").strip()
    if tag in ("circle", "ellipse"):
        cx, cy = num("cx"), num("cy")
        rx = num("r") if tag == "circle" else num("rx")
        ry = num("r") if tag == "circle" else num("ry")
        if rx <= 0 or ry <= 0:
            return ""
        # Two arcs trace the full ellipse, starting at the left-most point.
        return (
            f"M{cx - rx},{cy} a{rx},{ry} 0 1,0 {rx * 2},0 a{rx},{ry} 0 1,0 {-rx * 2},0"
        )
    if tag == "line":
        x1, y1, x2, y2 = num("x1"), num("y1"), num("x2"), num("y2")
        return f"M{x1},{y1} L{x2},{y2}"
    if tag == "rect":
        x, y, w, h = num("x"), num("y"), num("width"), num("height")
        if w <= 0 or h <= 0:
            return ""
        return f"M{x},{y} h{w} v{h} h{-w} Z"
    if tag in ("polyline", "polygon"):
        raw = attrib.get("points", "").strip()
        coords = [c for c in re.split(r"[\s,]+", raw) if c]
        if len(coords) < 4:
            return ""
        pairs = [f"{coords[i]},{coords[i + 1]}" for i in range(0, len(coords) - 1, 2)]
        d = "M" + " L".join(pairs)
        return d + " Z" if tag == "polygon" else d
    return ""


def svg_to_path(source: str | Path) -> str:
    """Convert an SVG image (file path or raw markup) into one ``d`` string.

    Extracts every drawable shape (``path``/``circle``/``ellipse``/``line``/
    ``rect``/``polyline``/``polygon``) and flattens them into a single
    space-joined ``d`` string in the same shape the renderers stroke — so a
    project SVG becomes a tempestroid icon. The SVG should already be on a 24x24
    viewBox (or a similar small grid) for the stroke width to look right.

    Args:
        source: A path to an ``.svg`` file, or a raw SVG markup string.

    Returns:
        The combined path ``d`` string.

    Raises:
        ValueError: When the source has no usable shapes, or the markup / file
            cannot be parsed as XML.
    """
    if isinstance(source, Path):
        markup = source.read_text(encoding="utf-8")
    elif "<" not in source:
        markup = Path(source).read_text(encoding="utf-8")
    else:
        markup = source
    try:
        root = ET.fromstring(markup)
    except ET.ParseError as exc:
        raise ValueError(f"could not parse SVG: {exc}") from exc

    fragments: list[str] = []
    for element in root.iter():
        fragment = _shape_to_path(_local_tag(element.tag), dict(element.attrib))
        if fragment:
            fragments.append(fragment)
    if not fragments:
        raise ValueError("SVG has no drawable shapes to convert into a path")
    return " ".join(fragments)


def register_icon(
    name: str, source: str | Path | None = None, *, path: str | None = None
) -> str:
    """Register a custom icon so it resolves like a curated one.

    Provide either a raw path ``d`` string (``path=``) or an ``source`` SVG
    (file path or markup) that is converted via :func:`svg_to_path`. After
    registering, ``Icon(name=…)`` / an input's ``leading_icon``/``trailing_icon``
    / :func:`icon_path` all resolve the name to this glyph. Re-registering the
    same name overwrites it.

    Args:
        name: The icon name to register (used as ``Icon(name=…)``).
        source: An SVG file path or markup to convert. Mutually exclusive with
            ``path``.
        path: A ready normalized ``d`` string to register verbatim.

    Returns:
        The registered ``d`` string.

    Raises:
        ValueError: If neither or both of ``source``/``path`` are given, if the
            name collides with a curated icon, or the SVG has no shapes.
    """
    if (source is None) == (path is None):
        raise ValueError("pass exactly one of source= or path=")
    if name in ICON_PATHS:
        raise ValueError(
            f"{name!r} is a curated icon name; choose a different custom name"
        )
    resolved = path if path is not None else svg_to_path(source)  # type: ignore[arg-type]
    _CUSTOM_PATHS[name] = resolved
    return resolved
