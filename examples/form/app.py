"""Sign-up form — exercises the form aggregation widgets.

Like :mod:`examples.counter.app`, this exact ``view`` runs unchanged in both
modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

It demonstrates the form layer of the core: a :class:`~tempestweb._core.widgets.Form`
aggregating two :class:`~tempestweb._core.widgets.FormField` wrappers, each
wrapping an :class:`~tempestweb._core.widgets.Input`, with typed
:data:`~tempestweb._core.widgets.Validator` rules that run purely in Python. The
form gates its :class:`~tempestweb._core.widgets.events.SubmitEvent` on
:meth:`Form.validate`, mirroring each error back onto its field.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tempestweb._core import App, Style, Widget
from tempestweb._core.style import Edge
from tempestweb._core.widgets import (
    Button,
    Column,
    Form,
    FormField,
    FormState,
    Input,
    Text,
    Validator,
)
from tempestweb._core.widgets.events import TextChangeEvent


@dataclass
class FormDataState:
    """State for the sign-up form app.

    Attributes:
        email: The current value of the email field.
        password: The current value of the password field.
        errors: The per-field validation errors from the last submit attempt.
        submitted: Whether a valid submit has happened.
    """

    email: str = ""
    password: str = ""
    errors: dict[str, str] = field(default_factory=dict)
    submitted: bool = False


def make_state() -> FormDataState:
    """Build the initial, empty form state.

    Returns:
        A fresh :class:`FormDataState`.
    """
    return FormDataState()


def _require(message: str) -> Validator:
    """Build a validator rejecting empty/blank values.

    Args:
        message: The error message shown when the value is blank.

    Returns:
        A validator returning ``message`` for a blank value, else ``None``.
    """

    def rule(value: Any) -> str | None:  # noqa: ANN401 — opaque field value
        return message if not str(value).strip() else None

    return rule


def _min_length(length: int, message: str) -> Validator:
    """Build a validator enforcing a minimum length.

    Args:
        length: The minimum acceptable number of characters.
        message: The error message shown when the value is too short.

    Returns:
        A validator returning ``message`` for a too-short value, else ``None``.
    """

    def rule(value: Any) -> str | None:  # noqa: ANN401 — opaque field value
        return message if len(str(value)) < length else None

    return rule


def view(app: App[FormDataState]) -> Widget:
    """Render the sign-up form from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def edit_email(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "email", event.value))

    def edit_password(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "password", event.value))

    form = Form(
        key="signup",
        fields=[
            FormField(
                name="email",
                label="Email",
                validators=[_require("Email is required")],
                error=app.state.errors.get("email", ""),
                child=Input(
                    value=app.state.email,
                    placeholder="you@example.com",
                    on_change=edit_email,
                    key="email-input",
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
                child=Input(
                    value=app.state.password,
                    placeholder="••••••••",
                    secure=True,
                    on_change=edit_password,
                    key="password-input",
                ),
            ),
        ],
    )

    def submit() -> None:
        result: FormState = form.validate(
            {"email": app.state.email, "password": app.state.password}
        )

        def mutate(s: FormDataState) -> None:
            s.errors = dict(result.errors)
            s.submitted = result.valid

        app.set_state(mutate)

    status = "Welcome!" if app.state.submitted else "Please sign up"
    return Column(
        style=Style(gap=12.0, padding=Edge.all(16)),
        children=[
            Text(content=status, key="status"),
            form,
            Button(label="Sign up", on_click=submit, key="submit"),
        ],
    )
