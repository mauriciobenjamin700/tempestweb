"""HTML escaping helpers for the static SSR renderer.

The renderer (:mod:`tempestweb.html.renderer`) turns an IR tree into an HTML
string. Any text or attribute value that originates from application data must be
escaped before it is written into the markup, otherwise a value such as
``"<script>"`` would be interpreted as markup rather than shown literally (a
cross-site-scripting hole). These two helpers are the single choke point every
string passes through:

- :func:`escape_text` for element **text content** (``<`` / ``>`` / ``&``).
- :func:`escape_attr` for **attribute values**, which additionally escapes quotes
  so a value can never break out of its surrounding ``"..."``.

Both accept any object, coerce it with :func:`str`, and map ``None`` to the empty
string so callers never emit the literal text ``"None"``.
"""

from __future__ import annotations

import html

__all__: list[str] = [
    "escape_attr",
    "escape_text",
]


def escape_text(value: object) -> str:
    """Escape a value for use as HTML **text content**.

    Escapes ``&``, ``<`` and ``>`` (but not quotes — they are safe in text
    nodes). ``None`` becomes the empty string.

    Args:
        value: Any value to render as text; coerced with :func:`str`.

    Returns:
        The escaped text, or ``""`` when ``value`` is ``None``.
    """
    if value is None:
        return ""
    return html.escape(str(value), quote=False)


def escape_attr(value: object) -> str:
    """Escape a value for use as a double-quoted HTML **attribute value**.

    Escapes ``&``, ``<``, ``>`` and both quote characters, so the result can be
    safely placed inside ``attr="..."`` without breaking out of the attribute.
    ``None`` becomes the empty string.

    Args:
        value: Any value to render as an attribute value; coerced with
            :func:`str`.

    Returns:
        The escaped attribute value, or ``""`` when ``value`` is ``None``.
    """
    if value is None:
        return ""
    return html.escape(str(value), quote=True)
