"""Locale and string translation context (phase E9).

A :class:`Locale` (language tag, region, layout direction) is **input context**
the ``view(app)`` reads — like :class:`~tempestroid.theme.Theme`, it is not a
node in the tree. The view picks the active language and reads ``locale.rtl`` to
build right-to-left layouts; the two ``Style`` translators mirror ``start``/
``end`` (padding, margin, text-align) when the renderer is told the layout is
RTL.

:func:`translate` (aliased :data:`t`) is a minimal, dependency-free lookup with
``str.format`` interpolation — enough for an app to localize strings without
pulling in a heavyweight i18n stack.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

__all__ = [
    "Locale",
    "translate",
    "t",
]


class Locale(BaseModel):
    """An immutable locale: language, optional region, and layout direction.

    Attributes:
        language: The BCP-47 language tag (e.g. ``"pt"``, ``"en"``, ``"ar"``).
        region: The optional region/country subtag (e.g. ``"BR"``, ``"US"``).
        rtl: Whether the locale lays out right-to-left (e.g. Arabic, Hebrew).

    Properties:
        tag: The locale as a BCP-47 tag (``language`` or ``language-REGION``).
    """

    model_config = ConfigDict(frozen=True)

    language: str = "pt"
    region: str | None = None
    rtl: bool = False

    @property
    def tag(self) -> str:
        """Render the locale as a BCP-47 tag (``language`` or ``language-REGION``).

        Returns:
            The composed tag, e.g. ``"pt-BR"`` or ``"pt"``.
        """
        return f"{self.language}-{self.region}" if self.region else self.language


def translate(
    key: str,
    locale: Locale,
    translations: dict[str, dict[str, str]],
    **kwargs: str,
) -> str:
    """Look up and interpolate a localized string.

    Resolution order, by the locale's language: a translation table keyed by
    language (``{"pt": {"hello": "Olá, {name}"}, "en": {...}}``) is searched for
    ``locale.language``; the matched string is then interpolated with ``kwargs``
    via :meth:`str.format`. When the language or key is missing, ``key`` itself is
    returned (still interpolated when possible) so a missing translation degrades
    to the developer-facing key rather than raising.

    Args:
        key: The translation key to resolve.
        locale: The active locale (its :attr:`Locale.language` selects the table).
        translations: A ``{language: {key: template}}`` mapping.
        **kwargs: Interpolation values applied to the resolved template.

    Returns:
        The interpolated, localized string (or the interpolated ``key`` on miss).
    """
    template = translations.get(locale.language, {}).get(key, key)
    if not kwargs:
        return template
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        # A template referencing a placeholder no value was supplied for must not
        # crash the view; fall back to the un-interpolated template.
        return template


#: Convenience alias so app code can write ``from tempestweb._core import t``.
t = translate
