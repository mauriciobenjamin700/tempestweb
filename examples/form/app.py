"""Sign-up form — exercises the form aggregation widgets.

Like :mod:`examples.counter.app`, this exact ``view`` runs unchanged in both
modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

It demonstrates the form layer of the core: a :class:`~tempest_core.widgets.Form`
aggregating :class:`~tempest_core.widgets.FormField` wrappers, each wrapping an
input, with typed :data:`~tempest_core.widgets.Validator` rules that run purely
in Python. The form gates its
:class:`~tempest_core.widgets.events.SubmitEvent` on :meth:`Form.validate`,
mirroring each error back onto its field.

It also shows the two per-field handlers, which is what keeps a form from only
telling the truth at the end:

* ``on_validate`` runs that field's validators when the reader leaves it, so a
  bad email is reported before six more fields are filled in. The client reports
  the *occasion* (this field, this value) — the validators are Python callables
  and never cross the wire.
* ``on_complete`` on the :class:`~tempest_core.widgets.inputs.PinInput` fires the
  moment the invite code is full, with no button to press.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tempest_core import App, Style, Widget
from tempest_core.style import Edge
from tempest_core.widgets import (
    Button,
    Column,
    Form,
    FormField,
    FormState,
    Input,
    Text,
    Validator,
)
from tempest_core.widgets.events import SubmitEvent, TextChangeEvent, ValidationEvent
from tempest_core.widgets.inputs import PinInput

#: Digits in the invite code, and what makes the field report completion.
CODE_LENGTH = 4


@dataclass
class FormDataState:
    """State for the sign-up form app.

    Attributes:
        email: The current value of the email field.
        password: The current value of the password field.
        code: The invite code typed so far.
        errors: The per-field validation errors, from a submit or from leaving a
            field.
        submitted: Whether a valid submit has happened.
        code_done: Whether the invite code has been filled in completely.
    """

    email: str = ""
    password: str = ""
    code: str = ""
    errors: dict[str, str] = field(default_factory=dict)
    submitted: bool = False
    code_done: bool = False


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

    def edit_code(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "code", event.value))

    rules: dict[str, list[Validator]] = {
        "email": [_require("Email is required")],
        "password": [
            _require("Password is required"),
            _min_length(8, "Password must be at least 8 characters"),
        ],
    }

    def validate_field(event: ValidationEvent) -> None:
        """Run one field's rules when the reader leaves it.

        Args:
            event: The validation request, carrying the field name and its
                current value.
        """
        message = ""
        for rule in rules.get(event.field, []):
            failed = rule(event.value)
            if failed is not None:
                message = failed
                break

        def mutate(s: FormDataState) -> None:
            errors = dict(s.errors)
            if message:
                errors[event.field] = message
            else:
                errors.pop(event.field, None)
            s.errors = errors

        app.set_state(mutate)

    def code_completed(event: SubmitEvent) -> None:
        """Accept the invite code as soon as its last digit lands.

        Args:
            event: The completion event, carrying the finished code.
        """
        app.set_state(lambda s: setattr(s, "code_done", True))

    form = Form(
        key="signup",
        fields=[
            FormField(
                key="field-email",
                name="email",
                label="Email",
                validators=rules["email"],
                error=app.state.errors.get("email", ""),
                on_validate=validate_field,
                child=Input(
                    value=app.state.email,
                    placeholder="you@example.com",
                    on_change=edit_email,
                    key="email-input",
                ),
            ),
            FormField(
                key="field-password",
                name="password",
                label="Password",
                validators=rules["password"],
                error=app.state.errors.get("password", ""),
                on_validate=validate_field,
                child=Input(
                    value=app.state.password,
                    placeholder="••••••••",
                    secure=True,
                    on_change=edit_password,
                    key="password-input",
                ),
            ),
            FormField(
                key="field-code",
                name="code",
                label="Invite code",
                child=PinInput(
                    key="code-input",
                    length=CODE_LENGTH,
                    value=app.state.code,
                    on_change=edit_code,
                    on_complete=code_completed,
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
    code_status = (
        "Invite code accepted" if app.state.code_done else "Invite code pending"
    )
    return Column(
        style=Style(gap=12.0, padding=Edge.all(16)),
        children=[
            Text(content=status, key="status"),
            Text(content=code_status, key="code-status"),
            form,
            Button(label="Sign up", on_click=submit, key="submit"),
        ],
    )
