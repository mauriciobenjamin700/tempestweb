"""A field names its control, and a component carries the name it is given.

Two defects, one page. First: every ``Component`` declares ``semantics`` — it
comes from the base — and until 0.113.0 not one of the five tempestweb-owned
components read it. Measured over ``tempestweb.components.__all__`` before the
fix: **59 of 63 dropped the name**, and the four that kept it kept it because the
*core* forwards it.

Second, and worse: a field's caption is a sibling ``Text``, not a
``<label for=…>``, so nothing associated it with the ``Input``. The control was
named by whatever its ``placeholder`` happened to say. Measured with axe over the
components' own IR:

| Case | Before | Why |
| --- | --- | --- |
| ``password_field_default`` | ``label`` (critical) | caption "Senha", no placeholder |
| ``email_field_default`` | clean | the default placeholder named it by accident |
| ``login_form_default`` | ``label`` (critical) | its password field |
| ``signup_form_default`` | ``label`` (critical) | its two password fields |

So the rule these pin is one line: **the field always names its control** — from
``semantics`` when the app passes one, from the visible caption otherwise. The
wrapper announces nothing, because ``aria-label`` on a role-less ``<div>`` is a
prohibited attribute and names an element no reader stops at.

The Mode C half is pinned by the parity matrix in
``tests/fixtures/transpile_component_samples.json`` (the ``*_named_*`` cases), and
the DOM half — that the attribute lands on the ``<input>``, and that axe agrees —
by ``tests/client/field-name.test.js``.
"""

from __future__ import annotations

from typing import Any

import pytest

import tempestweb.components as components
from tempest_core import Component, Node, Semantics, Widget, build
from tempestweb.components import (
    EmailField,
    LoginForm,
    PasswordField,
    SignupForm,
    TextField,
)

NAME: str = "Quantidade contratada"
"""The name the app asks for, distinctive enough to find in a tree."""

CAPTION: str = "Qtd."
"""A visible caption, which is the fallback name."""

#: The components in ``tempestweb.components`` this repo owns. Everything else in
#: that namespace is a re-export from ``tempest-core``, where 54 of them still drop
#: the ``semantics`` they are handed — measured here, reported upstream, and not
#: fixable from this repo: a component forwards its own ``semantics`` inside its
#: own ``render``.
OWNED: frozenset[str] = frozenset(
    {"TextField", "EmailField", "PasswordField", "LoginForm", "SignupForm"},
)

FIELDS: tuple[Any, ...] = (TextField, EmailField, PasswordField)
"""The three field components, which name their own control."""


def _noop(_value: str) -> None:
    """Swallow a field's change event.

    Args:
        _value: The new value (ignored).
    """


def _submit() -> None:
    """Swallow a form's submit."""


def _owned_samples(semantics: Semantics | None) -> dict[str, Widget]:
    """One instance of each tempestweb-owned component, named or not.

    Args:
        semantics: What the app asks the component to announce.

    Returns:
        A component name → instance map.
    """
    return {
        "TextField": TextField(label="", on_change=_noop, semantics=semantics),
        "EmailField": EmailField(label="", on_change=_noop, semantics=semantics),
        "PasswordField": PasswordField(label="", on_change=_noop, semantics=semantics),
        "LoginForm": LoginForm(
            on_email_change=_noop,
            on_password_change=_noop,
            on_submit=_submit,
            semantics=semantics,
        ),
        "SignupForm": SignupForm(
            on_email_change=_noop,
            on_password_change=_noop,
            on_confirm_change=_noop,
            on_submit=_submit,
            semantics=semantics,
        ),
    }


def _labelled(node: Node, label: str) -> list[Node]:
    """Collect every node in a built tree announcing one label.

    Args:
        node: The root of a built IR tree.
        label: The accessible name to look for.

    Returns:
        The matching nodes, in tree order.
    """
    found: list[Node] = []
    semantics = node.props.get("semantics")
    if semantics is not None and getattr(semantics, "label", None) == label:
        found.append(node)
    for child in node.children:
        found.extend(_labelled(child, label))
    return found


def test_owned_components_carry_the_name_they_are_given() -> None:
    """Each of the five puts the app's name on exactly one node."""
    for name, widget in _owned_samples(Semantics(label=NAME)).items():
        named = _labelled(build(widget), NAME)
        assert len(named) == 1, (
            f"{name}: {len(named)} nodes announce the app's name — a component "
            "that drops it leaves the control anonymous, and two names on one "
            "control is worse than one"
        )


@pytest.mark.parametrize("factory", FIELDS)
def test_a_field_names_its_control_and_not_its_wrapper(factory: Any) -> None:  # noqa: ANN401 — the field classes share no protocol
    """The name sits on the ``Input``, whether it came from the app or the caption.

    Args:
        factory: The field component under test.
    """
    for widget, expected in (
        (
            factory(
                label="", key="q", on_change=_noop, semantics=Semantics(label=NAME)
            ),
            NAME,
        ),
        (factory(label=CAPTION, key="q", on_change=_noop), CAPTION),
    ):
        named = _labelled(build(widget), expected)
        assert [(node.type, node.key) for node in named] == [("Input", "q-input")], (
            "the name has to sit on the control a screen reader stops at; a "
            "role-less wrapper div names nothing (axe: label, critical, plus "
            "aria-prohibited-attr)"
        )


@pytest.mark.parametrize("factory", FIELDS)
def test_the_app_name_wins_over_the_caption(factory: Any) -> None:  # noqa: ANN401 — the field classes share no protocol
    """With both, the app's ``semantics`` is what the control announces.

    Args:
        factory: The field component under test.
    """
    tree = build(
        factory(
            label=CAPTION,
            key="q",
            on_change=_noop,
            semantics=Semantics(label=NAME, hint="unidades contratadas"),
        ),
    )
    assert [node.key for node in _labelled(tree, NAME)] == ["q-input"]
    assert _labelled(tree, CAPTION) == []


@pytest.mark.parametrize("factory", FIELDS)
def test_a_caption_less_unnamed_field_invents_no_name(factory: Any) -> None:  # noqa: ANN401 — the field classes share no protocol
    """No caption and no ``semantics`` means no name — the app's call to fix.

    Args:
        factory: The field component under test.
    """
    tree = build(factory(label="", key="q", on_change=_noop))
    control = tree.children[0]
    assert control.key == "q-input"
    assert control.props.get("semantics") is None


def test_the_owned_list_is_the_whole_owned_surface() -> None:
    """:data:`OWNED` names every component this repo defines, and no other.

    A component added here without a ``semantics`` decision would otherwise join
    the 54 core re-exports that still drop it and never be looked at again.
    """
    defined: set[str] = set()
    for name in components.__all__:
        exported = getattr(components, name)
        if not isinstance(exported, type) or not issubclass(exported, Component):
            continue
        if exported.__module__.startswith("tempestweb."):
            defined.add(name)
    assert defined == OWNED
