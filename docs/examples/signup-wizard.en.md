# Multi-step Signup Wizard

🚀 Build a three-step registration form — Account, Profile, and Review — where
each step validates its own fields before letting the user proceed.

---

## What you will build

A signup wizard split across three screens:

| Step | Name    | Fields                                               |
|------|---------|------------------------------------------------------|
| 1    | Account | Email, password, password confirmation               |
| 2    | Profile | Display name, role (dropdown), bio                   |
| 3    | Review  | Read-only summary + terms-of-service acceptance      |

A `step` index in state decides which screen is visible. The **Next** button only
advances when every `FormField` on the current step passes its `Validator` chain.
The **Back** button always retreats without re-validating. After confirming on
step 3, a success message replaces the wizard.

---

## Why a wizard?

Long forms are intimidating. Breaking registration into smaller steps creates a
progressive experience: the user only fills in what is needed at that moment and
gets immediate feedback on errors before moving forward.

The pattern you will learn here — an index in state + `Form.validate()` as a
gate — is reusable in any multi-step flow.

---

## Full file

Save the file below as `examples/signup-wizard/app.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from tempest_core import App, Style, Widget
from tempest_core.style import Edge
from tempest_core.widgets import (
    Button,
    Column,
    Dropdown,
    Form,
    FormField,
    FormState,
    Input,
    Row,
    Text,
    TextArea,
    Validator,
)
from tempest_core.widgets.events import SelectEvent, TextChangeEvent

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

TOTAL_STEPS: int = 3

ROLE_OPTIONS: list[str] = [
    "Developer",
    "Designer",
    "Product Manager",
    "Data Scientist",
    "Other",
]


@dataclass
class WizardState:
    """Mutable state for the multi-step signup wizard."""

    step: int = 0
    email: str = ""
    password: str = ""
    confirm_password: str = ""
    display_name: str = ""
    role: str = ""
    bio: str = ""
    errors: dict[str, str] = field(default_factory=dict)
    submitted: bool = False
    accept_terms: bool = False


def make_state() -> WizardState:
    """Build the initial wizard state at step 0 with all fields blank."""
    return WizardState()


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def _require(message: str) -> Validator:
    def rule(value: Any) -> str | None:
        return message if not str(value).strip() else None
    return rule


def _email_format() -> Validator:
    _pattern: re.Pattern[str] = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    def rule(value: Any) -> str | None:
        return None if _pattern.match(str(value)) else "Enter a valid email address"

    return rule


def _min_length(length: int) -> Validator:
    def rule(value: Any) -> str | None:
        return (
            None
            if len(str(value)) >= length
            else f"Must be at least {length} characters"
        )
    return rule


def _has_digit() -> Validator:
    def rule(value: Any) -> str | None:
        return None if any(c.isdigit() for c in str(value)) else "Must contain a digit"
    return rule


def _has_upper() -> Validator:
    def rule(value: Any) -> str | None:
        return (
            None
            if any(c.isupper() for c in str(value))
            else "Must contain an uppercase letter"
        )
    return rule


def _passwords_match(get_password: Any) -> Validator:
    def rule(value: Any) -> str | None:
        return None if str(value) == str(get_password()) else "Passwords do not match"
    return rule


def _role_chosen() -> Validator:
    def rule(value: Any) -> str | None:
        return None if str(value).strip() else "Please select a role"
    return rule


def _max_length(length: int) -> Validator:
    def rule(value: Any) -> str | None:
        return (
            None
            if len(str(value)) <= length
            else f"Must be at most {length} characters"
        )
    return rule


def _terms_accepted() -> Validator:
    def rule(value: Any) -> str | None:
        v = str(value).lower()
        if v in ("true", "1", "yes"):
            return None
        return "You must accept the terms to continue"
    return rule


# ---------------------------------------------------------------------------
# Step indicator helper
# ---------------------------------------------------------------------------


def _step_indicator(current: int, total: int) -> Widget:
    """Render a simple text step indicator."""
    return Text(
        content=f"Step {current + 1} of {total}",
        key="step-indicator",
    )


# ---------------------------------------------------------------------------
# Main view
# ---------------------------------------------------------------------------


def view(app: App[WizardState]) -> Widget:
    """Render the multi-step signup wizard from the current state."""
    state: WizardState = app.state

    # Handlers for step 1
    def on_email_change(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "email", event.value))

    def on_password_change(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "password", event.value))

    def on_confirm_password_change(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "confirm_password", event.value))

    # Handlers for step 2
    def on_display_name_change(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "display_name", event.value))

    def on_role_select(event: SelectEvent) -> None:
        app.set_state(lambda s: setattr(s, "role", event.value))

    def on_bio_change(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "bio", event.value))

    # Handler for step 3
    def on_terms_change(event: TextChangeEvent) -> None:
        accepted: bool = event.value.strip().lower() == "true"
        app.set_state(lambda s: setattr(s, "accept_terms", accepted))

    # Assemble forms
    form1: Form = Form(
        key="form-step1",
        fields=[
            FormField(
                name="email",
                label="Email address",
                validators=[_require("Email is required"), _email_format()],
                error=state.errors.get("email", ""),
                child=Input(
                    key="input-email",
                    value=state.email,
                    placeholder="you@example.com",
                    on_change=on_email_change,
                ),
            ),
            FormField(
                name="password",
                label="Password",
                validators=[
                    _require("Password is required"),
                    _min_length(8),
                    _has_digit(),
                    _has_upper(),
                ],
                error=state.errors.get("password", ""),
                child=Input(
                    key="input-password",
                    value=state.password,
                    placeholder="Min 8 chars, 1 digit, 1 uppercase",
                    secure=True,
                    on_change=on_password_change,
                ),
            ),
            FormField(
                name="confirm_password",
                label="Confirm password",
                validators=[
                    _require("Please confirm your password"),
                    _passwords_match(lambda: state.password),
                ],
                error=state.errors.get("confirm_password", ""),
                child=Input(
                    key="input-confirm-password",
                    value=state.confirm_password,
                    placeholder="Repeat password",
                    secure=True,
                    on_change=on_confirm_password_change,
                ),
            ),
        ],
    )

    form2: Form = Form(
        key="form-step2",
        fields=[
            FormField(
                name="display_name",
                label="Display name",
                validators=[
                    _require("Display name is required"),
                    _min_length(2),
                    _max_length(50),
                ],
                error=state.errors.get("display_name", ""),
                child=Input(
                    key="input-display-name",
                    value=state.display_name,
                    placeholder="How others will see you",
                    max_length=50,
                    on_change=on_display_name_change,
                ),
            ),
            FormField(
                name="role",
                label="Role",
                validators=[_role_chosen()],
                error=state.errors.get("role", ""),
                child=Dropdown(
                    key="dropdown-role",
                    options=ROLE_OPTIONS,
                    value=state.role if state.role else None,
                    placeholder="Select your role…",
                    on_select=on_role_select,
                ),
            ),
            FormField(
                name="bio",
                label="Short bio (optional)",
                validators=[_max_length(200)],
                error=state.errors.get("bio", ""),
                child=TextArea(
                    key="textarea-bio",
                    value=state.bio,
                    placeholder="Tell us a little about yourself",
                    rows=3,
                    max_length=200,
                    on_change=on_bio_change,
                ),
            ),
        ],
    )

    form3: Form = Form(
        key="form-step3",
        fields=[
            FormField(
                name="accept_terms",
                label="Accept terms of service",
                validators=[_terms_accepted()],
                error=state.errors.get("accept_terms", ""),
                child=Input(
                    key="input-terms",
                    value="true" if state.accept_terms else "false",
                    placeholder="Type 'true' to accept",
                    on_change=on_terms_change,
                ),
            ),
        ],
    )

    # Navigation
    def go_back() -> None:
        def mutate(s: WizardState) -> None:
            s.step = max(0, s.step - 1)
            s.errors = {}
        app.set_state(mutate)

    def go_next() -> None:
        current: int = state.step
        if current == 0:
            values: dict[str, str] = {
                "email": state.email,
                "password": state.password,
                "confirm_password": state.confirm_password,
            }
            result: FormState = form1.validate(values)
        elif current == 1:
            values = {
                "display_name": state.display_name,
                "role": state.role,
                "bio": state.bio,
            }
            result = form2.validate(values)
        else:
            result = FormState(valid=True)

        def mutate(s: WizardState) -> None:
            s.errors = dict(result.errors)
            if result.valid:
                s.step = min(TOTAL_STEPS - 1, s.step + 1)

        app.set_state(mutate)

    def submit() -> None:
        result: FormState = form3.validate(
            {"accept_terms": "true" if state.accept_terms else "false"}
        )

        def mutate(s: WizardState) -> None:
            s.errors = dict(result.errors)
            s.submitted = result.valid

        app.set_state(mutate)

    # Build active step body
    if state.submitted:
        body: Widget = Column(
            key="success-body",
            style=Style(gap=8.0),
            children=[
                Text(content="Account created!", key="success-title"),
                Text(content=f"Welcome, {state.display_name}!", key="success-welcome"),
                Text(
                    content=f"A confirmation email is on its way to {state.email}.",
                    key="success-email",
                ),
            ],
        )
    elif state.step == 0:
        body = Column(
            key="step1-body",
            style=Style(gap=12.0),
            children=[
                Text(content="Step 1: Account credentials", key="step1-title"),
                form1,
                Row(
                    key="step1-nav",
                    style=Style(gap=8.0),
                    children=[
                        Button(key="btn-next-1", label="Next →", on_click=go_next),
                    ],
                ),
            ],
        )
    elif state.step == 1:
        body = Column(
            key="step2-body",
            style=Style(gap=12.0),
            children=[
                Text(content="Step 2: Your profile", key="step2-title"),
                form2,
                Row(
                    key="step2-nav",
                    style=Style(gap=8.0),
                    children=[
                        Button(key="btn-back-2", label="← Back", on_click=go_back),
                        Button(key="btn-next-2", label="Next →", on_click=go_next),
                    ],
                ),
            ],
        )
    else:
        body = Column(
            key="step3-body",
            style=Style(gap=12.0),
            children=[
                Text(content="Step 3: Review & submit", key="step3-title"),
                Text(content=f"Email: {state.email}", key="review-email"),
                Text(content=f"Name: {state.display_name}", key="review-name"),
                Text(content=f"Role: {state.role}", key="review-role"),
                form3,
                Row(
                    key="step3-nav",
                    style=Style(gap=8.0),
                    children=[
                        Button(key="btn-back-3", label="← Back", on_click=go_back),
                        Button(
                            key="btn-submit",
                            label="Create account",
                            on_click=submit,
                        ),
                    ],
                ),
            ],
        )

    return Column(
        key="wizard-root",
        style=Style(gap=16.0, padding=Edge.all(20)),
        children=[
            _step_indicator(state.step, TOTAL_STEPS),
            body,
        ],
    )
```

---

## Running the example

Open a terminal at the project root and choose a mode:

=== "Mode A — WASM (Pyodide)"

    ```bash
    tempestweb dev --mode wasm --path examples/signup-wizard
    ```

    Python runs directly in the browser via Pyodide. No backend server is required.

=== "Mode B — Server (FastAPI + WebSocket)"

    ```bash
    tempestweb dev --mode server --path examples/signup-wizard
    ```

    Python runs on the server; a thin JS client connects over WebSocket and applies
    patches to the DOM.

!!! note "Note — same `view` in both modes"
    The `view` function and all validation logic are **identical** in both modes.
    The only difference is where Python executes — in the browser or on the server.

---

## Understanding the code step by step

### 1. Wizard state

```python
@dataclass
class WizardState:
    step: int = 0
    email: str = ""
    password: str = ""
    confirm_password: str = ""
    display_name: str = ""
    role: str = ""
    bio: str = ""
    errors: dict[str, str] = field(default_factory=dict)
    submitted: bool = False
    accept_terms: bool = False
```

`step` is the zero-based index of the current step (0, 1, or 2). `errors` is a
dictionary that maps a field name to its error text. `submitted` becomes `True`
after the final form passes validation.

!!! tip "Tip — dataclass vs. dict"
    Using a `@dataclass` makes the state self-documenting and gives you IDE
    autocomplete. tempestweb accepts any mutable object, but dataclass is the
    recommended choice.

---

### 2. Composable validators

Each field receives a list of `Validator`s. A `Validator` is simply a function
`(Any) -> str | None` — it returns an error string or `None` when everything is
fine.

```python
def _min_length(length: int) -> Validator:
    def rule(value: Any) -> str | None:
        return (
            None
            if len(str(value)) >= length
            else f"Must be at least {length} characters"
        )
    return rule
```

You can chain as many as you need on the same `FormField`:

```python
FormField(
    name="password",
    label="Password",
    validators=[
        _require("Password is required"),
        _min_length(8),
        _has_digit(),
        _has_upper(),
    ],
    ...
)
```

`Form` runs the validators in order and stops at the first error for each field.

!!! tip "Tip — validators with closures"
    `_passwords_match` accepts a `get_password` callable instead of a static
    value. This avoids a stale closure over a mutable variable: it always reads
    the current password when invoked.

    ```python
    _passwords_match(lambda: state.password)
    ```

---

### 3. Building forms inside `view`

All three `Form` objects are built inside `view` on every render. This ensures
that event handlers and state values are always fresh:

```python
form1: Form = Form(
    key="form-step1",
    fields=[
        FormField(
            name="email",
            label="Email address",
            validators=[_require("Email is required"), _email_format()],
            error=state.errors.get("email", ""),
            child=Input(
                key="input-email",
                value=state.email,
                placeholder="you@example.com",
                on_change=on_email_change,
            ),
        ),
        ...
    ],
)
```

The `error` field passes the current error message (from `state.errors`) to the
`FormField`, which renders it below the input.

---

### 4. The `go_next` gate

This is the heart of the wizard. `go_next` calls `form.validate(values)`, which
returns a `FormState` with `valid: bool` and `errors: dict[str, str]`:

```python
def go_next() -> None:
    current: int = state.step
    if current == 0:
        values: dict[str, str] = {
            "email": state.email,
            "password": state.password,
            "confirm_password": state.confirm_password,
        }
        result: FormState = form1.validate(values)
    elif current == 1:
        values = {
            "display_name": state.display_name,
            "role": state.role,
            "bio": state.bio,
        }
        result = form2.validate(values)
    else:
        result = FormState(valid=True)

    def mutate(s: WizardState) -> None:
        s.errors = dict(result.errors)
        if result.valid:
            s.step = min(TOTAL_STEPS - 1, s.step + 1)

    app.set_state(mutate)
```

If `result.valid` is `False`, only the errors are written to state — the step
does **not** advance. The reconciler re-renders with the errors visible below
each field.

!!! warning "Warning — validate before advancing"
    Never increment `step` directly without calling `validate()`. The error state
    would be stale and invalid fields would go unnoticed.

---

### 5. Navigation by state index

The `if/elif/else` block chooses which body to render:

```python
elif state.step == 0:
    body = Column(
        key="step1-body",
        ...
        children=[
            Text(content="Step 1: Account credentials", key="step1-title"),
            form1,
            Row(
                key="step1-nav",
                style=Style(gap=8.0),
                children=[
                    Button(key="btn-next-1", label="Next →", on_click=go_next),
                ],
            ),
        ],
    )
```

!!! info "Info — stable keys"
    Every widget needs a unique and **stable** `key` across renders. This lets the
    reconciler apply minimal patches to the DOM instead of recreating the entire
    tree.

---

### 6. The progress indicator

```python
def _step_indicator(current: int, total: int) -> Widget:
    return Text(
        content=f"Step {current + 1} of {total}",
        key="step-indicator",
    )
```

Always rendered at the root, above the body, it tells the user where they are in
the flow.

---

### 7. Success screen

When `state.submitted` is `True`, the wizard is replaced by a confirmation
message:

```python
if state.submitted:
    body = Column(
        key="success-body",
        style=Style(gap=8.0),
        children=[
            Text(content="Account created!", key="success-title"),
            Text(content=f"Welcome, {state.display_name}!", key="success-welcome"),
            Text(
                content=f"A confirmation email is on its way to {state.email}.",
                key="success-email",
            ),
        ],
    )
```

---

## Full data flow

```
User types → on_*_change → app.set_state → re-render
User clicks "Next" → go_next → form.validate → set_state(errors + step)
User clicks "Back" → go_back → set_state(step-1, errors={})
User clicks "Create account" → submit → form3.validate → set_state(submitted=True)
```

---

## Verifying code quality

Before committing, run the four checks:

```bash
ruff check examples/signup-wizard/app.py
ruff format --check examples/signup-wizard/app.py
mypy examples/signup-wizard/app.py
pytest -q
```

✅ All four pass with no errors.

---

## Recap

In this tutorial you learned how to:

- Manage an active step with a `step` index in state.
- Build reusable `Validator`s as higher-order functions.
- Chain multiple validators on a single `FormField`.
- Use `Form.validate()` as a gate before advancing the step.
- Propagate errors from `FormState` back into app state.
- Replace the wizard with a success screen after submission.

---

## Next steps

- 💡 See the full state tutorial at [../tutorial/index.md](../tutorial/index.md).
- 🔗 Explore the [profile tabs](tabs-profile.en.md) example for another
  index-based navigation pattern.
- 🔗 See the [temperature converter](temperature-converter.en.md) example for a
  simpler introduction to the state → view → event cycle.
