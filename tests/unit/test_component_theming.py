"""The tempestweb-owned fields and forms follow the theme they are given.

Five components — ``TextField``, ``EmailField``, ``PasswordField``, ``LoginForm``
and ``SignupForm`` — declared no ``theme`` and passed none down, so they rendered
**light in a dark app**, in all three modes (tempestweb#158). It was never a
regression: it is how they always were, and their docstrings said so.

That matters more than a wrong shade, because the core resolves colour in Python
and inline style wins over the stylesheet: the worst case is the base sheet's dark
surface under this component's dark-on-light text, i.e. unreadable.

These pin the capability itself — the field declares a theme, and the colour it
resolves actually changes with it — next to the matrix in
``tests/fixtures/transpile_component_samples.json``, which pins that Mode C
reproduces the same tree.
"""

from __future__ import annotations

from typing import Any

import pytest

from tempest_core import (
    Color,
    ColorRole,
    Node,
    Theme,
    ThemeMode,
    Widget,
    build,
)
from tempestweb.components import (
    EmailField,
    LoginForm,
    PasswordField,
    SignupForm,
    TextField,
)

DARK: Theme = Theme(mode=ThemeMode.DARK)
LIGHT: Theme = Theme(mode=ThemeMode.LIGHT)


def _noop(_value: str) -> None:
    """Swallow a field's change event.

    Args:
        _value: The new value (ignored).
    """


def _submit() -> None:
    """Swallow a form's submit."""


def _samples(theme: Theme) -> dict[str, Widget]:
    """One instance of each themable tempestweb component, on ``theme``.

    Args:
        theme: The theme to build every sample against.

    Returns:
        A component name → instance map.
    """
    return {
        "TextField": TextField(
            label="Nome", error="obrigatório", on_change=_noop, theme=theme
        ),
        "EmailField": EmailField(error="inválido", on_change=_noop, theme=theme),
        "PasswordField": PasswordField(error="curta", on_change=_noop, theme=theme),
        "LoginForm": LoginForm(
            on_email_change=_noop,
            on_password_change=_noop,
            on_submit=_submit,
            theme=theme,
        ),
        "SignupForm": SignupForm(
            on_email_change=_noop,
            on_password_change=_noop,
            on_confirm_change=_noop,
            on_submit=_submit,
            theme=theme,
        ),
    }


def _colours(node: Node) -> list[Color]:
    """Every colour a built tree resolves, depth-first.

    Args:
        node: The root of a built IR tree.

    Returns:
        Each non-null ``background``/``color`` found on the tree.
    """
    found: list[Color] = []
    style: Any = (node.props or {}).get("style")
    for field in ("background", "color"):
        value = getattr(style, field, None) if style is not None else None
        if isinstance(value, Color):
            found.append(value)
    for child in node.children:
        found.extend(_colours(child))
    return found


COMPONENTS: tuple[str, ...] = (
    "TextField",
    "EmailField",
    "PasswordField",
    "LoginForm",
    "SignupForm",
)


@pytest.mark.parametrize("name", COMPONENTS)
def test_the_component_declares_a_theme(name: str) -> None:
    """A component with no ``theme`` field cannot be themed at all.

    Worth pinning separately because ``model_copy(update={"theme": ...})`` skips
    validation: without the field, injecting a theme silently attaches an
    attribute the render ignores, and the "dark" build comes out identical.
    """
    component = _samples(LIGHT)[name]
    assert "theme" in type(component).model_fields


@pytest.mark.parametrize("name", COMPONENTS)
def test_dark_resolves_different_colours_than_light(name: str) -> None:
    """The theme has to reach every coloured widget the component builds."""
    light = _colours(build(_samples(LIGHT)[name]))
    dark = _colours(build(_samples(DARK)[name]))

    assert light, f"{name} resolves no colour at all — the test proves nothing"
    assert len(light) == len(dark), f"{name} changed shape between themes"
    assert light != dark, (
        f"{name} resolves the same colours in dark as in light — the theme is "
        "being dropped before the children"
    )


@pytest.mark.parametrize("name", ("TextField", "EmailField", "PasswordField"))
def test_the_error_line_paints_the_theme_error_role(name: str) -> None:
    """The error colour was a frozen hex (``#b3261e``), tuned for light.

    Reading it from the scheme is what lets it darken with the app; a field whose
    error line kept the light red would be the one unreadable line on a dark
    surface.
    """
    for theme in (LIGHT, DARK):
        expected = theme.scheme().role(ColorRole.ERROR)
        tree = build(_samples(theme)[name])
        assert expected in _colours(tree), f"{name}: error role missing in {theme.mode}"


def test_a_form_hands_the_theme_to_its_submit_button() -> None:
    """The button is the form's only filled surface, so it is the loud one."""
    light_fills = _colours(build(_samples(LIGHT)["LoginForm"]))
    dark_fills = _colours(build(_samples(DARK)["LoginForm"]))
    light_primary = LIGHT.scheme().role(ColorRole.PRIMARY)
    dark_primary = DARK.scheme().role(ColorRole.PRIMARY)

    assert light_primary in light_fills
    assert dark_primary in dark_fills
    assert light_primary != dark_primary


@pytest.mark.parametrize("name", COMPONENTS)
def test_an_unthemed_component_still_builds(name: str) -> None:
    """``theme`` is optional: an app that never passes one keeps working.

    It falls back to ``current_theme()``, the same default every coloured core
    widget uses, so this is a capability added and not a new required argument.
    """
    samples = {
        "TextField": TextField(on_change=_noop),
        "EmailField": EmailField(on_change=_noop),
        "PasswordField": PasswordField(on_change=_noop),
        "LoginForm": LoginForm(
            on_email_change=_noop, on_password_change=_noop, on_submit=_submit
        ),
        "SignupForm": SignupForm(
            on_email_change=_noop,
            on_password_change=_noop,
            on_confirm_change=_noop,
            on_submit=_submit,
        ),
    }
    assert build(samples[name]) is not None
