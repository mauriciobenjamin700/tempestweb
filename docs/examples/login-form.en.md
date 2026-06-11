# Login Form

Build a **complete authentication form** with three-layer validation, an error
banner, and a success screen — all in pure Python, no HTML or JavaScript. 🔐

By the end of this tutorial you'll have a working app that uses the
`EmailInput`, `PasswordInput`, `Form`, `FormField`, `Banner`, `Card`, `Divider`,
`Button`, `Column`, and `Text` components to deliver a professional login
experience, including inline field error messages and a red banner for wrong
credentials.

---

## The problem

Every authenticated system needs a login form. But a good form goes beyond looks:
it needs to **validate fields before submitting**, display **error messages next
to the field** that failed, block the submit while there are errors, and still
show a **top-level error** when the server rejects the credentials (individually
valid email + password, but the pair is wrong).

The challenge in Python is orchestrating that flow without coupling validation
logic to the render. tempestweb solves it with `Form` + `FormField` + `Validator`
— components that separate "what rule?" (validators) from "when to show the
error?" (state) and "how to render it?" (the child widgets).

!!! note "What you'll practice"
    - `EmailInput` and `PasswordInput` — pre-built form components with correct
      style and semantics.
    - `FormField` — wrapper that associates validators and error messages with
      a field.
    - `Form.validate()` — fires all validators at once and returns a `FormState`
      with `valid` and `errors`.
    - `Banner(tone="error")` — displays authentication-level errors above the
      form.
    - Screen switching by boolean flag in state (`authenticated`).

---

## Prerequisites

Make sure you have completed the [Installation](../installation.en.md) and read
the [Counter Tutorial](../tutorial/index.en.md). This example assumes you
already know `App`, `set_state`, `make_state`, and `view`.

If you want to understand how patches are propagated when the form switches
screens, also read [Patches on the wire](../tutorial/patches.en.md).

---

## The complete app

This is the exact code from
[`examples/login-form/app.py`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/login-form/app.py).
Copy it, run it, then read the section-by-section explanation below.

```python
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

from tempestweb._core import App, Style, Widget
from tempestweb._core.components import (
    Banner,
    Card,
    Divider,
    EmailInput,
    PasswordInput,
)
from tempestweb._core.style import AlignItems, Color, Edge, FontWeight, TextAlign
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
```

---

## Explaining it piece by piece

### 1. State: five fields, two responsibilities

```python
@dataclass
class LoginState:
    email: str = ""
    password: str = ""
    errors: dict[str, str] = field(default_factory=dict)
    auth_error: str = ""
    authenticated: bool = False
    loading: bool = False
```

The state has two separate "planes" of error:

- **`errors`** — per-field validation errors (`{"email": "...", "password": "..."}`),
  produced by the `Form` validators before any network request.
- **`auth_error`** — authentication-level error, produced when the credentials are
  individually valid but incorrect as a pair.

This separation matters: when submit fails at field validation, `auth_error` is
cleared; when it fails at the credential check, `errors` is cleared. The two
error types never coexist.

!!! tip "Tip"
    `field(default_factory=dict)` is the correct pattern for mutable fields in
    dataclasses. Without `default_factory`, all `LoginState` instances would share
    the same dictionary — a very common silent bug.

---

### 2. The three validators

The app defines three validator factory functions — each returns a `Validator`
(a `Callable[[Any], str | None]`):

```python
def _require(message: str) -> Validator:
    def rule(value: Any) -> str | None:
        return message if not str(value).strip() else None
    return rule


def _valid_email(message: str) -> Validator:
    def rule(value: Any) -> str | None:
        text = str(value).strip()
        return None if _EMAIL_RE.fullmatch(text) else message
    return rule


def _min_length(length: int, message: str) -> Validator:
    def rule(value: Any) -> str | None:
        return message if len(str(value)) < length else None
    return rule
```

Each validator returns `None` when the rule passes, or the error message string
when it fails. This contract is easy to test in isolation:

- `_require("Required")("")` → `"Required"`
- `_require("Required")("admin@example.com")` → `None`
- `_valid_email("Invalid email")("not-an-email")` → `"Invalid email"`
- `_min_length(8, "Min 8 chars")("abc")` → `"Min 8 chars"`

!!! info "Why factories and not fixed validators?"
    The factories (`_require(msg)`, `_min_length(n, msg)`) let you customize the
    message and the threshold without inheritance or global config. `FormField`
    accepts a plain list of callables.

---

### 3. `Form`, `FormField`, and the field components

```python
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
```

Notice the **dual role of `error`**:

- `FormField(error=...)` — used by the Form internally to track the field's error
  state in the IR tree.
- `EmailInput(error=...)` / `PasswordInput(error=...)` — used by the visual
  component to render the red text below the field.

Both read `app.state.errors.get("email", "")`, so they stay perfectly in sync.

!!! warning "Warning"
    `EmailInput` and `PasswordInput` are pre-built form components
    (`_core.components`), not basic widgets. They encapsulate the DOM's
    `type="email"` and `type="password"`, the password visibility toggle icon,
    and the standard error style. Use them instead of the raw `Input` whenever
    the context is authentication.

---

### 4. The field handlers

```python
def on_email_change(value: str) -> None:
    def _set(s: LoginState) -> None:
        s.email = value
        s.auth_error = ""

    app.set_state(_set)
```

Each handler does two things at once:

1. **Updates the field** with the newly typed value.
2. **Clears `auth_error`** — so if the user starts correcting the email after a
   failed login attempt, the red banner disappears immediately, giving feedback
   that the app registered the correction.

!!! tip "Tip"
    This on-the-fly `auth_error` clearing is a UX detail that makes a big
    difference: the user doesn't keep staring at an error message that no longer
    applies to what they're typing.

---

### 5. The submit handler: three-layer validation

```python
def submit() -> None:
    result: FormState = form.validate(
        {"email": app.state.email, "password": app.state.password}
    )

    if not result.valid:
        def apply_errors(s: LoginState) -> None:
            s.errors = dict(result.errors)
            s.auth_error = ""
        app.set_state(apply_errors)
        return

    # Credential check
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
```

Submit goes through three sequential layers:

| Layer | What it checks | Where the error appears |
|-------|---------------|------------------------|
| **1. Required** | Empty field | Inline in `EmailInput` / `PasswordInput` |
| **2. Format** | Valid email / password ≥ 8 chars | Inline in the field |
| **3. Credentials** | Email + password pair in the "database" | `Banner(tone="error")` above the form |

Only when all three layers pass is the state updated to `authenticated = True`
and the success screen rendered.

!!! note "Note"
    `form.validate({"email": ..., "password": ...})` runs the validators of
    **all** `FormField` instances at once and returns a `FormState` with:
    - `result.valid` — `True` if every field passed.
    - `result.errors` — dictionary `{field_name: error_message}` for the fields
      that failed.

---

### 6. The authentication error banner

```python
children: list[Widget] = []

if app.state.auth_error:
    children.append(
        Banner(
            message=app.state.auth_error,
            tone="error",
            key="auth-error-banner",
        )
    )
```

The `Banner` only enters the tree when there is an `auth_error`. When the field is
empty (initial state or after the user starts typing again), the banner simply
does not exist in the IR — no `visible=False`, no zero opacity. The reconciler
detects the node's addition/removal and emits the correct patches.

!!! info "Why `tone=\"error\"` and not a direct color?"
    `Banner` abstracts the semantic meaning of the alert. `tone="error"` maps to
    red in the default theme, but the theme can be customized without touching
    any `app.py`. Available tones: `"info"`, `"success"`, `"warning"`, `"error"`.

---

### 7. The success screen as a full tree swap

```python
def view(app: App[LoginState]) -> Widget:
    if app.state.authenticated:
        return _success_screen()
    ...
```

When `authenticated` becomes `True`, `view` returns a **completely different
tree** — it doesn't hide fields or stack layers. The reconciler compares the
previous tree (form) with the new one (success screen) and emits only the minimum
patches needed for the transition.

```python
def _success_screen() -> Widget:
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
```

`Card` is a container component with a shadow and rounded border — useful for
grouping related content visually. Here it acts as a "welcome card" on the
success screen.

!!! check "Screen switching without a router"
    In this simple app, "navigation" is just a boolean flag in state. For apps
    with multiple screens, use the tempestweb navigation system — see
    [Navigation](../tutorial/index.en.md).

---

## Running the app 🚀

Save the file as `examples/login-form/app.py` and pick a mode:

=== "WASM mode (Python in the browser)"

    ```bash
    tempestweb dev --mode wasm examples/login-form/app.py
    ```

    Pyodide loads the full Python runtime in the browser. All validators and
    handlers run locally in the tab — no WebSocket, no server.

=== "Server mode (FastAPI + WebSocket)"

    ```bash
    tempestweb dev --mode server examples/login-form/app.py
    ```

    A FastAPI server starts locally. The JS client sends typing events and
    receives reconciler patches via WebSocket.

!!! check "Same code, two modes"
    The `app.py` doesn't reference either `wasm` or `server` anywhere. The
    transport layer is completely encapsulated inside tempestweb — you choose
    only at run time.

Open the browser at `http://localhost:8000`. Try these scenarios:

1. **Submit empty** → inline errors on both fields.
2. **Invalid email** → inline error only on the email field.
3. **Password shorter than 8 characters** → inline error only on the password field.
4. **Wrong credentials** (`test@example.com` / `anything`) → red banner above the
   form.
5. **Correct credentials** (`admin@example.com` / `secret1234`) → green success
   screen. ✅

---

## Recap

In this example you learned:

- ✅ **`EmailInput` and `PasswordInput`** — pre-built components with semantics,
  style, and an integrated `error` prop.
- ✅ **`Form` + `FormField` + `Validator`** — the triad that separates validation
  rules from rendering and from state.
- ✅ **Two error planes** — `errors` (per-field, validators) and `auth_error`
  (authentication level, business logic).
- ✅ **`form.validate()`** — runs all validators at once and returns
  `FormState.valid` + `FormState.errors`.
- ✅ **`Banner(tone="error")`** — semantic error above the form, present in the
  tree only when needed.
- ✅ **Tree swap via boolean flag** — `authenticated = True` makes `view` return
  a completely different tree, without conditional visibility.
- ✅ **On-the-fly error clearing** — field handlers clear `auth_error` while
  typing, avoiding stale messages.

---

## Next steps

- Read the [Counter Tutorial](../tutorial/index.en.md) if you haven't yet — it
  explains `set_state` and the rebuild cycle in more depth.
- See the [Temperature Converter](./temperature-converter.md) example to dive
  deeper into two-way binding with controlled fields.
- Explore the [Stopwatch](./stopwatch.md) example to see how state evolves in
  response to timer events.
- Check [Patches on the wire](../tutorial/patches.en.md) to understand which
  operations the reconciler emits during the form → success screen transition.
