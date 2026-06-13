"""Login form — demonstrates auth-oriented form validation with brform components.

The form uses :class:`~tempestweb._core.components.EmailInput` and
:class:`~tempestweb._core.components.PasswordInput` (the pre-built BR-form
components) together with :class:`~tempestweb._core.widgets.Form` /
:class:`~tempestweb._core.widgets.FormField` validators to gate submission on
both field validity and a fake credential check. The result flips an
``authenticated`` flag in state, rendering a success screen or a red error
banner for wrong credentials.

Run in either mode — the ``view`` function is transport-agnostic::

    tempestweb dev --mode wasm    # Python in the browser (Pyodide)
    tempestweb dev --mode server  # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from tempestweb._core.style import AlignItems, Color, Edge, FontWeight, TextAlign

from tempestweb._core import App, Style, Widget
from tempestweb._core.components import (
    Banner,
    Card,
    Divider,
    EmailInput,
    PasswordInput,
)
from tempestweb._core.widgets import (
    Button,
    Column,
    Form,
    FormField,
    FormState,
    Text,
    Validator,
)

# ---------------------------------------------------------------------------
# Fake credential store — real apps would call an async API instead.
# ---------------------------------------------------------------------------

_VALID_CREDENTIALS: dict[str, str] = {
    "admin@example.com": "secret1234",
    "user@example.com": "password99",
}

_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]{2,}")

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class LoginState:
    """All mutable state for the login screen.

    Attributes:
        email: The current value of the email field.
        password: The current value of the password field.
        errors: Per-field validation errors keyed by field name.
        auth_error: A top-level authentication error message (wrong credentials).
        authenticated: Whether the user has successfully authenticated.
        loading: Whether a credential check is in progress.
    """

    email: str = ""
    password: str = ""
    errors: dict[str, str] = field(default_factory=dict)
    auth_error: str = ""
    authenticated: bool = False
    loading: bool = False


def make_state() -> LoginState:
    """Build the initial, unauthenticated login state.

    Returns:
        A fresh :class:`LoginState` with all fields blank and no errors.
    """
    return LoginState()


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def _require(message: str) -> Validator:
    """Return a validator that rejects blank/whitespace-only values.

    Args:
        message: The error message returned when the value is blank.

    Returns:
        A :data:`~tempestweb._core.widgets.Validator` callable.
    """

    def rule(value: Any) -> str | None:  # noqa: ANN401
        return message if not str(value).strip() else None

    return rule


def _valid_email(message: str) -> Validator:
    """Return a validator that rejects strings that are not valid e-mail addresses.

    Args:
        message: The error message returned when the address is syntactically invalid.

    Returns:
        A :data:`~tempestweb._core.widgets.Validator` callable.
    """

    def rule(value: Any) -> str | None:  # noqa: ANN401
        text = str(value).strip()
        return None if _EMAIL_RE.fullmatch(text) else message

    return rule


def _min_length(length: int, message: str) -> Validator:
    """Return a validator that rejects values shorter than ``length`` characters.

    Args:
        length: The minimum character count (inclusive).
        message: The error message returned when the value is too short.

    Returns:
        A :data:`~tempestweb._core.widgets.Validator` callable.
    """

    def rule(value: Any) -> str | None:  # noqa: ANN401
        return message if len(str(value)) < length else None

    return rule


# ---------------------------------------------------------------------------
# Helpers for the two screens
# ---------------------------------------------------------------------------


def _success_screen() -> Widget:
    """Render the post-authentication success screen.

    Returns:
        A :class:`~tempestweb._core.widgets.Column` with a success card.
    """
    return Column(
        key="success-screen",
        style=Style(
            gap=20.0,
            padding=Edge.all(24.0),
            align=AlignItems.CENTER,
        ),
        children=[
            Text(
                content="Welcome back!",
                style=Style(
                    font_size=28.0,
                    font_weight=FontWeight.BOLD,
                    color=Color.from_hex("#16a34a"),
                    text_align=TextAlign.CENTER,
                ),
                key="welcome-heading",
            ),
            Card(
                key="success-card",
                children=[
                    Text(
                        content="You are now authenticated.",
                        style=Style(
                            font_size=15.0,
                            text_align=TextAlign.CENTER,
                        ),
                        key="success-body",
                    ),
                ],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# view
# ---------------------------------------------------------------------------


def view(app: App[LoginState]) -> Widget:
    """Render the login form from the current application state.

    Builds a :class:`~tempestweb._core.widgets.Form` that:

    * Validates the email field (required + syntactically valid).
    * Validates the password field (required + minimum 8 characters).
    * On a valid form, checks the credentials against a fake store and either
      sets :attr:`LoginState.authenticated` to ``True`` or writes an error
      banner message.
    * Shows a green success screen once authenticated.

    Args:
        app: The application handle providing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """
    if app.state.authenticated:
        return _success_screen()

    # ---- handlers ----------------------------------------------------------

    def on_email_change(value: str) -> None:
        """Update the email field and clear the auth error.

        Args:
            value: The new value typed by the user.
        """

        def _set(s: LoginState) -> None:
            s.email = value
            s.auth_error = ""

        app.set_state(_set)

    def on_password_change(value: str) -> None:
        """Update the password field and clear the auth error.

        Args:
            value: The new value typed by the user.
        """

        def _set(s: LoginState) -> None:
            s.password = value
            s.auth_error = ""

        app.set_state(_set)

    # ---- form --------------------------------------------------------------

    form = Form(
        key="login-form",
        fields=[
            FormField(
                name="email",
                label="E-mail",
                validators=[
                    _require("E-mail is required"),
                    _valid_email("Enter a valid e-mail address"),
                ],
                error=app.state.errors.get("email", ""),
                child=EmailInput(
                    value=app.state.email,
                    label="E-mail",
                    placeholder="you@example.com",
                    error=app.state.errors.get("email", ""),
                    on_change=on_email_change,
                    key="email-brfield",
                ),
            ),
            FormField(
                name="password",
                label="Password",
                validators=[
                    _require("Password is required"),
                    _min_length(8, "Password must be at least 8 characters"),
                ],
                error=app.state.errors.get("password", ""),
                child=PasswordInput(
                    value=app.state.password,
                    label="Password",
                    placeholder="Enter your password",
                    error=app.state.errors.get("password", ""),
                    on_change=on_password_change,
                    key="password-brfield",
                ),
            ),
        ],
    )

    # ---- submit handler ----------------------------------------------------

    def submit() -> None:
        """Validate fields and, if valid, check credentials.

        Runs the :class:`~tempestweb._core.widgets.Form` validators first. If
        the form is invalid the per-field errors are reflected into state so the
        components re-render with their red error messages. If the form is valid
        the credentials are checked against the fake store; a mismatch writes an
        ``auth_error`` banner rather than a field error.
        """
        result: FormState = form.validate(
            {"email": app.state.email, "password": app.state.password}
        )

        if not result.valid:

            def apply_errors(s: LoginState) -> None:
                s.errors = dict(result.errors)
                s.auth_error = ""

            app.set_state(apply_errors)
            return

        # Credential check (synchronous stub — real apps use async I/O).
        expected = _VALID_CREDENTIALS.get(app.state.email.strip())
        if expected is None or expected != app.state.password:

            def set_auth_error(s: LoginState) -> None:
                s.auth_error = "Invalid e-mail or password. Please try again."
                s.errors = {}

            app.set_state(set_auth_error)
            return

        def authenticate(s: LoginState) -> None:
            s.authenticated = True
            s.errors = {}
            s.auth_error = ""

        app.set_state(authenticate)

    # ---- tree --------------------------------------------------------------

    children: list[Widget] = []

    # Auth-level error banner (wrong credentials, shown above the form).
    if app.state.auth_error:
        children.append(
            Banner(
                message=app.state.auth_error,
                tone="error",
                key="auth-error-banner",
            )
        )

    children += [
        Text(
            content="Sign in to your account",
            style=Style(
                font_size=22.0,
                font_weight=FontWeight.BOLD,
                text_align=TextAlign.CENTER,
            ),
            key="login-heading",
        ),
        Divider(key="heading-divider"),
        form,
        Button(
            label="Sign in",
            on_click=submit,
            key="submit-btn",
        ),
    ]

    return Column(
        key="login-screen",
        style=Style(gap=16.0, padding=Edge.all(24.0)),
        children=children,
    )
