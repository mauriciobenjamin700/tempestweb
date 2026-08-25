"""An app's theme, rendered as the CSS custom properties the client reads.

The base stylesheet paints every widget from ``--tw-*`` tokens on ``:root``
and its own docs say an app rebrands by overriding them. Nothing rendered
them: an app that built a palette with
:meth:`~tempest_core.Theme.from_seed` — 39 Material 3 roles, light and dark
— had no way to get those colours onto the page, and every tempestweb app
therefore shipped the baseline purple.

:func:`theme_css` is that missing half. It maps the roles the sheet
actually reads onto their variables and returns a CSS block to drop in the
document head; the base sheet is inserted at the *top* of the head at
mount, so this block always follows it in cascade order:

    from tempest_core import Theme, ThemeMode
    from tempest_core import Color
    from tempestweb.html import theme_css

    theme = Theme.from_seed(Color(r=39, g=58, b=79), mode=ThemeMode.SYSTEM)
    head = f"<style>{theme_css(theme)}</style>"

Dark mode keys off :data:`THEME_MODE_ATTR` — the same attribute the base
sheet reads — and deliberately **not** ``prefers-color-scheme``. The core
resolves a ``SYSTEM`` theme as *light* for every widget, because a widget
never sees the OS, so darkening the page from the OS alone put a light tree
on a dark page: the two halves of dark mode disagreed, and the half with
inline precedence won. An app that wants to follow the reader's setting
reads ``app.media.platform_dark_mode`` in its ``view`` and calls
``set_theme``; then the resolved mode reaches the document as the attribute
and everything moves together.

So a ``SYSTEM`` theme emits the light scheme on ``:root`` and the dark one
under ``:root[data-tw-theme="dark"]``. A theme pinned to ``DARK`` emits its
dark scheme under **both**, so it paints before any attribute arrives *and*
still outranks the base sheet's own dark block once it does — that block is
``:root[data-tw-theme="dark"]`` too, and the base sheet is inserted at the
top of the head while this goes after it, so equal specificity resolves in
the app's favour. The base theme is a floor, not a cage.

Only the variables the sheet reads are emitted. Writing all 39 roles would
look thorough and would be worse: a variable nothing consumes is a promise
the next reader has to verify by grepping the stylesheet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tempest_core import ThemeMode

#: The attribute the renderer writes on ``<html>`` to pin the active theme mode.
#: Mirrors ``THEME_MODE_ATTR`` in ``client/theme.js``, which is what makes the
#: app's palette and the base sheet's token block key off the same switch.
THEME_MODE_ATTR: str = "data-tw-theme"

if TYPE_CHECKING:
    from tempest_core import Color, ColorScheme, Theme

__all__: list[str] = ["ROLE_BY_VARIABLE", "theme_css"]


ROLE_BY_VARIABLE: dict[str, str] = {
    "--tw-primary": "primary",
    "--tw-on-primary": "on_primary",
    "--tw-primary-container": "primary_container",
    "--tw-on-primary-container": "on_primary_container",
    "--tw-secondary-container": "secondary_container",
    "--tw-on-secondary-container": "on_secondary_container",
    "--tw-surface": "surface",
    "--tw-on-surface": "on_surface",
    "--tw-on-surface-variant": "on_surface_variant",
    "--tw-outline": "outline",
    "--tw-error": "error",
    "--tw-success": "success",
    "--tw-warning": "warning",
    "--tw-info": "info",
    "--tw-neutral": "on_surface_variant",
}
"""Which Material 3 role each variable the base sheet reads comes from.

``--tw-neutral`` has no role of its own: it tints the "nothing is claimed
here" state of an indicator, which is the same job ``on_surface_variant``
does for text.
"""


def _hex(color: Color) -> str:
    """Render a colour as the hex CSS understands.

    Args:
        color (Color): The role's colour.

    Returns:
        str: ``"#48647f"``, or ``"#48647fcc"`` when the colour is
        translucent — the alpha is part of the token and dropping it would
        paint an overlay as a solid.
    """
    body = f"#{color.r:02x}{color.g:02x}{color.b:02x}"
    if color.a >= 1.0:
        return body
    return f"{body}{round(color.a * 255):02x}"


def _declarations(scheme: ColorScheme, indent: str) -> str:
    """Render one scheme as the variable declarations the sheet reads.

    Args:
        scheme (ColorScheme): The resolved light or dark scheme.
        indent (str): Leading whitespace for each line.

    Returns:
        str: The declaration block, one variable per line.
    """
    return "\n".join(
        f"{indent}{variable}: {_hex(getattr(scheme, role))};"
        for variable, role in ROLE_BY_VARIABLE.items()
    )


def theme_css(theme: Theme) -> str:
    """Render a theme as the CSS custom properties the client reads.

    Args:
        theme (Theme): The app's theme, usually from
            :meth:`~tempest_core.Theme.from_seed`.

    Returns:
        str: A CSS block for the document head — ``:root`` declarations, plus a
        ``:root[data-tw-theme="dark"]`` block when the theme can go dark. Never a
        ``prefers-color-scheme`` query: see the module docstring for why the OS
        alone must not flip the page.

    Example:
        ```python
        from tempest_core import Theme, ThemeMode
        from tempest_core import Color
        from tempestweb.html import theme_css


        def head() -> str:
            \"\"\"Build the head markup that rebrands every widget.

    Returns:
                str: A style element carrying the app's palette.
            \"\"\"
            theme = Theme.from_seed(Color(r=39, g=58, b=79), mode=ThemeMode.SYSTEM)
            return f"<style>{theme_css(theme)}</style>"
        ```
    """
    schemes = theme.tokens.schemes
    dark_selector = f':root[{THEME_MODE_ATTR}="dark"]'
    dark = _declarations(schemes.dark, "  ")
    if theme.mode is ThemeMode.DARK:
        return f":root, {dark_selector} {{\n{dark}\n}}"
    light = f":root {{\n{_declarations(schemes.light, '  ')}\n}}"
    if theme.mode is ThemeMode.LIGHT:
        return light
    return f"{light}\n{dark_selector} {{\n{dark}\n}}"
