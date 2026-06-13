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
