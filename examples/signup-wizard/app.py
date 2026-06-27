"""Multi-step signup wizard — stepper with Form, FormField and Validator.

Demonstrates a real-world registration flow split across three steps:

- **Step 1 — Account**: email + password with strength validation.
- **Step 2 — Profile**: display name, role dropdown, and a bio textarea.
- **Step 3 — Review**: read-only summary; a final Submit gated on all prior steps
  being valid.

A ``step`` index in state drives which :class:`~tempest_core.widgets.Form` is
shown.  ``Next`` and ``Back`` buttons advance or retreat the stepper; ``Next`` only
advances when the current step's form validates cleanly. This pattern is transport-
agnostic — the same ``view`` runs unchanged under Mode A (Pyodide in the browser)
and Mode B (FastAPI + WebSocket)::

    tempestweb dev --mode wasm
    tempestweb dev --mode server
"""

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
    """Mutable state for the multi-step signup wizard.

    Attributes:
        step: The zero-based index of the currently displayed step (0–2).
        email: Email address entered in step 1.
        password: Password entered in step 1.
        confirm_password: Password confirmation entered in step 1.
        display_name: Display name entered in step 2.
        role: Selected role from the dropdown in step 2.
        bio: Short biography entered in step 2.
        errors: Per-field validation errors keyed by field name.
        submitted: Whether the final submit was successfully dispatched.
        accept_terms: Whether the user ticked the terms checkbox in step 3.
    """

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
    """Build the initial wizard state at step 0 with all fields blank.

    Returns:
        A fresh :class:`WizardState`.
    """
    return WizardState()


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def _require(message: str) -> Validator:
    """Build a validator that rejects blank values.

    Args:
        message: Error text shown when the value is blank or whitespace-only.

    Returns:
        A validator returning *message* for blank input, else ``None``.
    """

    def rule(value: Any) -> str | None:  # noqa: ANN401
        return message if not str(value).strip() else None

    return rule


def _email_format() -> Validator:
    """Build a validator enforcing a minimal RFC 5322-like email shape.

    Returns:
        A validator returning an error message for invalid emails, else ``None``.
    """
    _pattern: re.Pattern[str] = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    def rule(value: Any) -> str | None:  # noqa: ANN401
        return None if _pattern.match(str(value)) else "Enter a valid email address"

    return rule


def _min_length(length: int) -> Validator:
    """Build a validator enforcing a minimum character count.

    Args:
        length: The minimum number of characters required.

    Returns:
        A validator that fails when the value is shorter than *length*.
    """

    def rule(value: Any) -> str | None:  # noqa: ANN401
        return (
            None
            if len(str(value)) >= length
            else f"Must be at least {length} characters"
        )

    return rule


def _has_digit() -> Validator:
    """Build a validator requiring at least one digit.

    Returns:
        A validator that fails when the value contains no ASCII digit.
    """

    def rule(value: Any) -> str | None:  # noqa: ANN401
        return None if any(c.isdigit() for c in str(value)) else "Must contain a digit"

    return rule


def _has_upper() -> Validator:
    """Build a validator requiring at least one uppercase letter.

    Returns:
        A validator that fails when the value has no uppercase ASCII letter.
    """

    def rule(value: Any) -> str | None:  # noqa: ANN401
        return (
            None
            if any(c.isupper() for c in str(value))
            else "Must contain an uppercase letter"
        )

    return rule


def _passwords_match(get_password: Any) -> Validator:  # noqa: ANN401
    """Build a validator checking that the confirmation equals the primary password.

    Args:
        get_password: A zero-argument callable returning the current password string
            at validation time (avoids stale closure over a mutable value).

    Returns:
        A validator that fails when the confirmation does not match the password.
    """

    def rule(value: Any) -> str | None:  # noqa: ANN401
        return None if str(value) == str(get_password()) else "Passwords do not match"

    return rule


def _role_chosen() -> Validator:
    """Build a validator requiring a non-empty role selection.

    Returns:
        A validator that fails when the value is blank (no role chosen yet).
    """

    def rule(value: Any) -> str | None:  # noqa: ANN401
        return None if str(value).strip() else "Please select a role"

    return rule


def _max_length(length: int) -> Validator:
    """Build a validator capping the maximum character count.

    Args:
        length: The maximum number of characters permitted.

    Returns:
        A validator that fails when the value exceeds *length* characters.
    """

    def rule(value: Any) -> str | None:  # noqa: ANN401
        return (
            None
            if len(str(value)) <= length
            else f"Must be at most {length} characters"
        )

    return rule


def _terms_accepted() -> Validator:
    """Build a validator requiring the terms checkbox to be ticked.

    Interprets falsy strings (``"false"``, ``""``, ``"False"``) as not accepted.

    Returns:
        A validator that fails when the value is falsy.
    """

    def rule(value: Any) -> str | None:  # noqa: ANN401
        v = str(value).lower()
        if v in ("true", "1", "yes"):
            return None
        return "You must accept the terms to continue"

    return rule


# ---------------------------------------------------------------------------
# Step indicator helper
# ---------------------------------------------------------------------------


def _step_indicator(current: int, total: int) -> Widget:
    """Render a simple text step indicator.

    Args:
        current: Zero-based index of the current step.
        total: Total number of steps in the wizard.

    Returns:
        A :class:`~tempest_core.widgets.Text` widget showing ``Step N of M``.
    """
    return Text(
        content=f"Step {current + 1} of {total}",
        key="step-indicator",
    )


# ---------------------------------------------------------------------------
# Main view
# ---------------------------------------------------------------------------


def view(app: App[WizardState]) -> Widget:
    """Render the multi-step signup wizard from the current state.

    Three steps — Account, Profile, Review — are gated behind a ``step`` index.
    ``Next`` validates the current step's form and only advances when every field
    passes. ``Back`` always retreats without re-validating. On step 3 a ``Submit``
    button dispatches the final action and shows a success message.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current wizard state.
    """
    state: WizardState = app.state

    # ------------------------------------------------------------------
    # Handlers for step 1
    # ------------------------------------------------------------------

    def on_email_change(event: TextChangeEvent) -> None:
        """Update the email field in state.

        Args:
            event: The text-change event carrying the new value.
        """
        app.set_state(lambda s: setattr(s, "email", event.value))

    def on_password_change(event: TextChangeEvent) -> None:
        """Update the password field in state.

        Args:
            event: The text-change event carrying the new value.
        """
        app.set_state(lambda s: setattr(s, "password", event.value))

    def on_confirm_password_change(event: TextChangeEvent) -> None:
        """Update the password-confirmation field in state.

        Args:
            event: The text-change event carrying the new value.
        """
        app.set_state(lambda s: setattr(s, "confirm_password", event.value))

    # ------------------------------------------------------------------
    # Handlers for step 2
    # ------------------------------------------------------------------

    def on_display_name_change(event: TextChangeEvent) -> None:
        """Update the display-name field in state.

        Args:
            event: The text-change event carrying the new value.
        """
        app.set_state(lambda s: setattr(s, "display_name", event.value))

    def on_role_select(event: SelectEvent) -> None:
        """Update the selected role in state.

        Args:
            event: The select event carrying the chosen option value.
        """
        app.set_state(lambda s: setattr(s, "role", event.value))

    def on_bio_change(event: TextChangeEvent) -> None:
        """Update the bio field in state.

        Args:
            event: The text-change event carrying the new value.
        """
        app.set_state(lambda s: setattr(s, "bio", event.value))

    # ------------------------------------------------------------------
    # Handler for step 3
    # ------------------------------------------------------------------

    def on_terms_change(event: TextChangeEvent) -> None:
        """Toggle terms acceptance based on the typed value.

        Args:
            event: The text-change event; interprets ``"true"`` as accepted.
        """
        accepted: bool = event.value.strip().lower() == "true"
        app.set_state(lambda s: setattr(s, "accept_terms", accepted))

    # ------------------------------------------------------------------
    # Assemble forms with live handlers attached to their child inputs
    # ------------------------------------------------------------------

    form1: Form = Form(
        key="form-step1",
        fields=[
            FormField(
                name="email",
                label="Email address",
                validators=[
                    _require("Email is required"),
                    _email_format(),
                ],
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

    # ------------------------------------------------------------------
    # Navigation actions
    # ------------------------------------------------------------------

    def go_back() -> None:
        """Retreat one step, clearing any validation errors for that step."""

        def mutate(s: WizardState) -> None:
            s.step = max(0, s.step - 1)
            s.errors = {}

        app.set_state(mutate)

    def go_next() -> None:
        """Validate the current step and advance only when every field passes."""
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
        """Validate the final step and mark the wizard as submitted when valid."""
        result: FormState = form3.validate(
            {"accept_terms": "true" if state.accept_terms else "false"}
        )

        def mutate(s: WizardState) -> None:
            s.errors = dict(result.errors)
            s.submitted = result.valid

        app.set_state(mutate)

    # ------------------------------------------------------------------
    # Build the active step body
    # ------------------------------------------------------------------

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
                        Button(
                            key="btn-next-1",
                            label="Next →",
                            on_click=go_next,
                        ),
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
                Text(
                    content=f"Email: {state.email}",
                    key="review-email",
                ),
                Text(
                    content=f"Name: {state.display_name}",
                    key="review-name",
                ),
                Text(
                    content=f"Role: {state.role}",
                    key="review-role",
                ),
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
