# Form — `Form` + `FormField` + typed validators 📝

**Modes: A/B** — uses form widgets and the Python event shape (`event.value`).

A sign-up form that **validates before submitting**: two fields (email and
password) aggregated by a `Form`, each wrapped in a `FormField` with validation
rules that run **purely in Python**. Errors are mirrored back onto each field. 🚀

!!! note "Why a form layer?"
    You could validate by hand in every handler, but the `Form` centralizes
    aggregation: a single `Form.validate(values)` runs all validators at once and
    returns a `FormState` with `valid` and a per-field `errors` dict.

---

## What this example shows

- **`Form`** aggregating two **`FormField`**s, each wrapping an `Input`.
- **Typed `Validator`s** — functions `value -> str | None` (an error message or
  `None`). The example defines `_require` and `_min_length`.
- **`Form.validate(values)`** returning a `FormState` (`valid`, `errors`).
- **Errors mirrored onto state** — each `FormField` gets its error back via
  `error=app.state.errors.get(name, "")`.

---

## Running ▶

```bash
tempestweb dev --mode wasm     --path examples/form   # Python in the browser (Pyodide)
tempestweb dev --mode server   --path examples/form   # Python on the server (FastAPI + WS)
```

---

## The code

```python
"""Sign-up form — exercises the form aggregation widgets."""

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
from tempest_core.widgets.events import TextChangeEvent


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
```

---

## Piece by piece

### Validators are functions

```python
def _require(message: str) -> Validator:
    def rule(value: Any) -> str | None:
        return message if not str(value).strip() else None
    return rule
```

A `Validator` is just a `value -> str | None` function: it returns the **error
message** when invalid, or `None` when ok. `_require` and `_min_length` are
factories that capture the message — the password field stacks both.

### The `Form` aggregates the fields

Each `FormField` declares a `name`, `label`, a list of `validators`, the current
`error` (from state), and the child widget (`child=Input(...)`). The `Form` just
gathers them — validation happens at submit time.

### Validate on submit

```python
def submit() -> None:
    result: FormState = form.validate(
        {"email": app.state.email, "password": app.state.password}
    )
    def mutate(s: FormDataState) -> None:
        s.errors = dict(result.errors)
        s.submitted = result.valid
    app.set_state(mutate)
```

`form.validate(values)` runs every validator and returns a `FormState`. We store
`result.errors` in state — and because each `FormField` reads
`error=...errors.get(name)`, the next render **mirrors the error** under the right
field.

!!! tip "One direction only"
    The flow is always: state → `view` → validation → `set_state` → new render. No
    widget holds hidden state; the source of truth is `FormDataState`.

---

## Recap

In this example you saw:

- ✅ **`Validator`s** as `value -> str | None` functions, built by factories
- ✅ A **`Form`** aggregating two **`FormField`**s with stacked validators
- ✅ **`Form.validate`** returning `FormState(valid, errors)`
- ✅ Errors **mirrored onto state** and rendered under each field
- ✅ The pattern running unchanged in **Modes A/B**

---

## Next steps

- 💡 The [Login form](login-form.md) adds `EmailInput`/`PasswordInput` and a `Banner`
- 💡 The [Signup wizard](signup-wizard.md) chains validation across multiple steps
- 💡 The [Brazilian registration](br-cadastro.md) uses real-time BR validators (CPF/CNPJ)
