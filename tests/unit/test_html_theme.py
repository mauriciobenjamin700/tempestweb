"""Tests for ``theme_css`` — an app's palette as the tokens the client reads.

The gap it closes was documented and unimplemented: the base stylesheet
says an app rebrands by overriding ``--tw-*``, and nothing turned a
:class:`~tempest_core.Theme` into those variables. So every tempestweb app
shipped the Material baseline purple no matter what palette it built.

These pin the three things a consumer depends on: that every variable the
sheet reads is emitted, that the mode decides whether a dark block appears,
and that the values are the theme's own — not a copy that can drift.
"""

from __future__ import annotations

import re

import pytest

from tempest_core import Color, Theme, ThemeMode
from tempestweb.html import ROLE_BY_VARIABLE, theme_css

SEED: Color = Color(r=39, g=58, b=79)
"""A slate blue, dark enough that its scheme differs from the baseline."""


def _variables(css: str) -> set[str]:
    """Collect every custom property a CSS block declares.

    Args:
        css (str): The rendered block.

    Returns:
        set[str]: The property names.
    """
    return set(re.findall(r"--tw-[a-z-]+(?=:)", css))


class TestWhatItEmits:
    """The variables, and where the values come from."""

    def test_every_variable_the_sheet_reads_is_declared(self) -> None:
        css = theme_css(Theme.from_seed(SEED, mode=ThemeMode.LIGHT))

        assert _variables(css) == set(ROLE_BY_VARIABLE)

    def test_the_values_are_the_theme_own_roles(self) -> None:
        """A copied palette drifts; this reads the theme it was given."""
        theme = Theme.from_seed(SEED, mode=ThemeMode.LIGHT)
        primary = theme.tokens.schemes.light.primary

        css = theme_css(theme)

        assert f"--tw-primary: #{primary.r:02x}{primary.g:02x}{primary.b:02x};" in css

    def test_a_seeded_palette_is_not_the_baseline_purple(self) -> None:
        """The whole point: the app's colour reaches the page."""
        css = theme_css(Theme.from_seed(SEED, mode=ThemeMode.LIGHT))

        assert "#6750a4" not in css

    def test_a_translucent_role_keeps_its_alpha(self) -> None:
        """Dropping the alpha would paint an overlay as a solid."""
        theme = Theme.from_seed(SEED, mode=ThemeMode.LIGHT)
        faded = theme.tokens.schemes.light.model_copy(
            update={"outline": Color(r=0, g=0, b=0, a=0.5)},
        )
        schemes = theme.tokens.schemes.model_copy(update={"light": faded})
        tokens = theme.tokens.model_copy(update={"schemes": schemes})

        css = theme_css(theme.model_copy(update={"tokens": tokens}))

        assert "--tw-outline: #00000080;" in css


class TestHowTheModeDecidesDarkness:
    """A pinned theme stays pinned; a system theme follows the reader."""

    def test_system_emits_both_schemes(self) -> None:
        css = theme_css(Theme.from_seed(SEED, mode=ThemeMode.SYSTEM))

        assert ':root[data-tw-theme="dark"]' in css
        assert css.count("--tw-primary:") == 2

    @pytest.mark.parametrize("mode", [ThemeMode.LIGHT, ThemeMode.DARK])
    def test_a_pinned_theme_emits_one_scheme(self, mode: ThemeMode) -> None:
        css = theme_css(Theme.from_seed(SEED, mode=mode))

        assert css.count("--tw-primary:") == 1

    @pytest.mark.parametrize(
        "mode", [ThemeMode.LIGHT, ThemeMode.DARK, ThemeMode.SYSTEM]
    )
    def test_the_os_alone_never_flips_the_page(self, mode: ThemeMode) -> None:
        """No mode emits a media query, whatever the reader's OS says.

        The core resolves a ``SYSTEM`` theme as light for every widget — a widget
        never sees the OS — so a page that darkened from ``prefers-color-scheme``
        alone put a light tree on a dark background, and the inline half won.
        Measured before this was fixed: ``--tw-surface`` went to the dark value
        while every widget stayed light.
        """
        assert "prefers-color-scheme" not in theme_css(Theme.from_seed(SEED, mode=mode))

    def test_a_pinned_dark_theme_outranks_the_base_sheet_dark_block(self) -> None:
        """A pinned dark palette wins over the sheet's own dark tokens.

        The base sheet's dark block is ``:root[data-tw-theme="dark"]``. An app
        palette emitted on bare ``:root`` loses to it on specificity, so the app's
        rebrand silently reverted to the baseline the moment the page went dark —
        the base theme acting as a cage instead of a floor. Emitting the pinned
        scheme under both selectors ties the specificity, and the app's block is
        appended after the sheet, so the app wins.
        """
        css = theme_css(Theme.from_seed(SEED, mode=ThemeMode.DARK))

        assert css.startswith(':root, :root[data-tw-theme="dark"] {')

    def test_dark_and_light_are_not_the_same_scheme(self) -> None:
        """A dark block copied from the light one would be worse than none."""
        light = theme_css(Theme.from_seed(SEED, mode=ThemeMode.LIGHT))
        dark = theme_css(Theme.from_seed(SEED, mode=ThemeMode.DARK))

        assert light != dark
