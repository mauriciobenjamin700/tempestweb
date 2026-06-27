# Ready-made components

You **don't** have to build a login form field by field. tempestweb ships
ready-made, validated, good-looking-by-default components — you write the minimum,
the component does the rest. 🚀

Everything comes from one obvious place:

```python
from tempestweb.components import EmailField, PasswordField, LoginForm, validate_email
```

## Ready-made fields

Each field is **controlled**: pass the current `value` and an `on_change` that
stores the new text; pass `error` to show a validation message.

```python
from tempest_core import App, Column, Widget
from tempestweb.components import EmailField


def view(app: App[State]) -> Widget:
    def set_email(value: str) -> None:
        app.set_state(lambda s: setattr(s, "email", value))

    return Column(
        children=[
            EmailField(
                value=app.state.email,
                on_change=set_email,
                error=app.state.email_error,  # "" when valid
                key="email",
            ),
        ],
    )
```

The available fields:

| Field | For | Validator |
|---|---|---|
| `EmailField` | E-mail (e-mail keyboard, icon) | `validate_email` |
| `PasswordField` | Password (secure field) | — |
| `PhoneField` | Masked BR phone `(99) 99999-9999` | `validate_phone` |
| `CPFField` | Masked CPF | `validate_cpf` |
| `CNPJField` | Masked CNPJ | `validate_cnpj` |
| `AddressField` | Address | — |

!!! tip "Validators return `None` when OK"
    `validate_email("you@example.com")` returns `None`; an invalid value returns
    the error message (a string). Store that string in the field's `error`:

    ```python
    error = validate_email(app.state.email) or ""
    ```

## A complete login form

`LoginForm` composes email + password + a submit button in **one call**. You only
keep the values in state; the form handles layout, labels and errors.

```python
from dataclasses import dataclass

from tempest_core import App, Column, Text, Widget
from tempestweb.components import LoginForm, validate_email


@dataclass
class LoginState:
    email: str = ""
    password: str = ""
    email_error: str = ""
    status: str = ""


def make_state() -> LoginState:
    return LoginState()


def view(app: App[LoginState]) -> Widget:
    def set_email(value: str) -> None:
        app.set_state(lambda s: setattr(s, "email", value))

    def set_password(value: str) -> None:
        app.set_state(lambda s: setattr(s, "password", value))

    def submit() -> None:
        error = validate_email(app.state.email) or ""

        def commit(s: LoginState) -> None:
            s.email_error = error
            s.status = "" if error else f"Welcome, {s.email}!"

        app.set_state(commit)

    return Column(
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
```

That's it. This is the `examples/login_demo` example — it runs the same in both
modes:

```bash
tempestweb run --mode wasm     # Python in the browser (Pyodide)
tempestweb run --mode server   # Python on the server (FastAPI + WebSocket)
```

!!! info "Why controlled?"
    State lives in the `App` (one source of truth), so the form keeps no hidden
    state. You always know what's in the fields — and can pre-fill, clear or
    validate them from outside whenever you want.

## Sign up

`SignupForm` follows the same idea with email + password + confirm-password. Show
the confirm error when the passwords differ:

```python
from tempestweb.components import SignupForm

SignupForm(
    email=app.state.email,
    password=app.state.password,
    confirm=app.state.confirm,
    on_email_change=set_email,
    on_password_change=set_password,
    on_confirm_change=set_confirm,
    on_submit=do_signup,
    confirm_error="" if app.state.password == app.state.confirm else "Passwords do not match",
    title="Create account",
)
```

## The full tempest-core library

Beyond the native helpers above, **the entire tempest-core Material 3 component
library** is re-exported from `tempestweb.components` — the same obvious place.
In total, `tempestweb.components` exposes **67 components** (+ 10 helpers): layout
scaffolds, app bars, navigation, `Card`, `ListTile`, inputs, feedback
(`Alert`/`Banner`/`Badge`), tables (`Table`/`DataTable`) and **charts**
(`BarChart`/`LineChart`).

```python
from tempestweb.components import Card, DataTable, BarChart, ChartSeries

BarChart(series=[ChartSeries(points=[3.0, 7.0, 2.0, 9.0, 5.0], label="sales")])
```

!!! info "Charts draw via Canvas — in both modes"
    `BarChart`/`LineChart` (and detection overlays) lower to a `Canvas` widget with
    a draw-command list. The web client executes those commands onto a real
    `<canvas>` — axes, gridlines, bars and lines actually draw, no charting library,
    **identical in Mode A and Mode B**. The value models that drive the components
    (`ChartSeries`, `TableRow`/`TableCell`, `DetectionBox`) come along.

## Recap

- Import from `tempestweb.components` — fields, forms **and** the full core library
  in one place.
- Fields are **controlled**: `value` + `on_change` (+ optional `error`).
- `LoginForm` is a whole form in one call; you just wire it to your state.
- Validators (`validate_email`, `validate_phone`, …) return `None` when OK.
- The core components (incl. `BarChart`/`LineChart` via `Canvas`) render the same
  in Mode A (WASM) and Mode B (server).
