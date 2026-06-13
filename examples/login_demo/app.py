"""Login demo — a complete login screen in a few lines (pre-built components).

Uses :class:`tempestweb.components.LoginForm`, which composes the email and
password fields with a submit button. The app only holds the field values in
state and validates on submit — no manual layout, labels or error wiring.

    tempestweb run --mode wasm     # Python in the browser (Pyodide)
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Column, Style, Text, Widget
from tempest_core.style import Edge
from tempestweb.components import LoginForm, validate_email


@dataclass
class LoginState:
    """State for the login demo."""

    email: str = ""
    password: str = ""
    email_error: str = ""
    status: str = ""


def make_state() -> LoginState:
    """Build the initial state.

    Returns:
        A fresh :class:`LoginState`.
    """
    return LoginState()


def view(app: App[LoginState]) -> Widget:
    """Render the login screen and a status line.

    Args:
        app: The application handle.

    Returns:
        The widget tree for the current state.
    """

    def set_email(value: str) -> None:
        app.set_state(lambda s: setattr(s, "email", value))

    def set_password(value: str) -> None:
        app.set_state(lambda s: setattr(s, "password", value))

    def submit() -> None:
        error = validate_email(app.state.email) or ""

        def commit(state: LoginState) -> None:
            state.email_error = error
            state.status = "" if error else f"Welcome, {state.email}!"

        app.set_state(commit)

    return Column(
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[
            LoginForm(
                email=app.state.email,
                password=app.state.password,
                on_email_change=set_email,
                on_password_change=set_password,
                on_submit=submit,
                email_error=app.state.email_error,
                title="Sign in",
            ),
            Text(content=app.state.status, key="status"),
        ],
    )
