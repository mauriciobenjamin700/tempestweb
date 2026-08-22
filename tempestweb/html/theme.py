"""An app's theme, rendered as the CSS custom properties the client reads.

The base stylesheet paints every widget from ``--tw-*`` tokens on ``:root``
and its own docs say an app rebrands by overriding them. Nothing rendered
them: an app that built a palette with
:meth:`~tempest_core.Theme.from_seed` — 39 Material 3 roles, light and dark
— had no way to get those colours onto the page, and every tempestweb app
therefore shipped the baseline purple.

:func:`theme_css` is that missing half. It maps the roles the sheet
actually reads onto their variables and returns a CSS block to drop in the
document head, **before** the base sheet is installed at mount:

    from tempest_core import Theme, ThemeMode
    from tempest_core import Color
    from tempestweb.html import theme_css

    theme = Theme.from_seed(Color(r=39, g=58, b=79), mode=ThemeMode.SYSTEM)
    head = f"<style>{theme_css(theme)}</style>"

Dark mode comes free and comes honestly: a ``SYSTEM`` theme emits the light
scheme on ``:root`` and the dark one inside
``@media (prefers-color-scheme: dark)``, so the page follows the reader's
own setting rather than a preference the app guessed. A theme pinned to
``LIGHT`` or ``DARK`` emits that one scheme and no media query, because a
pinned theme that still flipped with the system would not be pinned.

Only the variables the sheet reads are emitted. Writing all 39 roles would
look thorough and would be worse: a variable nothing consumes is a promise
the next reader has to verify by grepping the stylesheet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tempest_core import ThemeMode

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
        str: A CSS block for the document head — ``:root`` declarations,
        plus a ``prefers-color-scheme: dark`` block when the theme follows
        the system.

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
    if theme.mode is ThemeMode.DARK:
        return f":root {{\n{_declarations(schemes.dark, '  ')}\n}}"
    light = f":root {{\n{_declarations(schemes.light, '  ')}\n}}"
    if theme.mode is ThemeMode.LIGHT:
        return light
    dark = _declarations(schemes.dark, "    ")
    return (
        f"{light}\n@media (prefers-color-scheme: dark) {{\n  :root {{\n{dark}\n  }}\n}}"
    )
