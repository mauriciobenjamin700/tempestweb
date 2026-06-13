"""Tests for the ready-to-use components (tempestweb.components)."""

from __future__ import annotations

from typing import Any

from tempest_core import Node, build
from tempestweb.components import (
    EmailField,
    LoginForm,
    PasswordField,
    SignupForm,
    TextField,
    elevated_button,
    filled_button,
    outlined_button,
    text_button,
    tonal_button,
    validate_email,
    validate_phone,
)


def _walk(node: Node) -> list[Node]:
    nodes = [node]
    for child in node.children:
        nodes.extend(_walk(child))
    return nodes


def _types(node: Node) -> set[str]:
    return {n.type for n in _walk(node)}


def test_email_field_builds_an_input() -> None:
    """EmailField renders into an Input the DOM client can mount."""
    node = build(EmailField(value="a@b.com", on_change=lambda _v: None))
    assert "Input" in _types(node)


def test_login_form_composes_fields_and_submit() -> None:
    """LoginForm lays out two inputs and a submit button."""
    captured: list[str] = []
    node = build(
        LoginForm(
            email="you@example.com",
            password="secret",
            on_email_change=captured.append,
            on_password_change=lambda _v: None,
            on_submit=lambda: captured.append("submit"),
            title="Sign in",
        )
    )
    types = _types(node)
    assert "Input" in types
    assert "Button" in types
    assert "Text" in types  # the title
    # Two text inputs (email + password) are present in the tree.
    inputs = [n for n in _walk(node) if n.type == "Input"]
    assert len(inputs) == 2


def test_login_form_submit_handler_fires() -> None:
    """The composed submit button carries the form's on_submit."""
    fired: list[str] = []
    form = LoginForm(
        email="",
        password="",
        on_email_change=lambda _v: None,
        on_password_change=lambda _v: None,
        on_submit=lambda: fired.append("go"),
    )
    submit = _find(build(form), key="login-submit")
    assert submit is not None
    handler = submit.props.get("on_click")
    assert callable(handler)
    handler()
    assert fired == ["go"]


def test_signup_form_has_three_inputs() -> None:
    """SignupForm lays out email + password + confirm-password and a submit."""
    node = build(
        SignupForm(
            email="",
            password="",
            confirm="",
            on_email_change=lambda _v: None,
            on_password_change=lambda _v: None,
            on_confirm_change=lambda _v: None,
            on_submit=lambda: None,
        )
    )
    inputs = [n for n in _walk(node) if n.type == "Input"]
    assert len(inputs) == 3
    # The two password fields are secure.
    secure = [n for n in inputs if n.props.get("secure") is True]
    assert len(secure) == 2
    assert _find(node, key="signup-submit") is not None


def test_validators_reexported() -> None:
    """Validators come through the components package unchanged."""
    assert validate_email("nope") is not None
    assert validate_email("you@example.com") is None
    assert validate_phone("(11) 99999-9999") is None


def _find(node: Node, key: str) -> Node | None:
    for candidate in _walk(node):
        if candidate.key == key:
            return candidate
    return None


def test_password_field_is_secure() -> None:
    """PasswordField lowers to a secure Input."""
    node = build(PasswordField(value="x", on_change=lambda _v: None))
    inputs: list[Any] = [n for n in _walk(node) if n.type == "Input"]
    assert inputs and inputs[0].props.get("secure") is True


def test_text_field_generic_labelled_input() -> None:
    """TextField renders a label, a text Input and (when set) an error line."""
    node = build(
        TextField(
            value="Ada", label="Name", error="required", on_change=lambda _v: None
        )
    )
    types = _types(node)
    assert "Input" in types
    labels = [n for n in _walk(node) if n.key == "text-field-label"]
    assert labels and labels[0].props.get("content") == "Name"
    inputs = [n for n in _walk(node) if n.type == "Input"]
    assert inputs[0].props.get("value") == "Ada"


def _bg_alpha(style: Any | None) -> float | None:
    """Read a Style's background alpha, or None when unset/not a solid color."""
    if style is None:
        return None
    background = getattr(style, "background", None)
    alpha = getattr(background, "a", None)
    return float(alpha) if alpha is not None else None


def test_light_fields_carry_no_dark_inline_background() -> None:
    """EmailField/PasswordField inputs are unstyled so the MD3 base sheet applies.

    Guards against regressing to the core's dark BR input: the inner Input must
    not ship an inline background, leaving it to the light base stylesheet.
    """
    for field in (
        EmailField(value="", on_change=lambda _v: None),
        PasswordField(value="", on_change=lambda _v: None),
    ):
        inputs = [n for n in _walk(build(field)) if n.type == "Input"]
        assert inputs
        assert inputs[0].props.get("style") is None


def test_filled_button_is_unstyled_for_the_base_sheet() -> None:
    """filled_button carries no inline style, so the base sheet styles it."""
    fired: list[str] = []
    node = build(filled_button("Save", lambda: fired.append("x"), key="save"))
    assert node.type == "Button"
    assert node.props.get("style") is None
    assert node.props.get("label") == "Save"
    handler = node.props.get("on_click")
    assert callable(handler)
    handler()
    assert fired == ["x"]


def test_tonal_button_sets_an_opaque_fill() -> None:
    """tonal_button paints a secondary-container fill (opaque background)."""
    node = build(tonal_button("More", lambda: None))
    assert _bg_alpha(node.props.get("style")) == 1.0


def test_elevated_button_carries_a_resting_shadow() -> None:
    """elevated_button ships an inline shadow for its resting elevation."""
    node = build(elevated_button("Open", lambda: None))
    style = node.props.get("style")
    assert style is not None and getattr(style, "shadow", None) is not None


def test_outlined_button_has_a_border_and_transparent_fill() -> None:
    """outlined_button draws a border over a transparent background."""
    node = build(outlined_button("Edit", lambda: None))
    style = node.props.get("style")
    assert style is not None
    assert getattr(style, "border", None) is not None
    assert _bg_alpha(style) == 0.0


def test_text_button_is_transparent_with_no_border() -> None:
    """text_button is a bare label: transparent fill, no border."""
    node = build(text_button("Cancel", lambda: None))
    style = node.props.get("style")
    assert style is not None
    assert _bg_alpha(style) == 0.0
    assert getattr(style, "border", None) is None
