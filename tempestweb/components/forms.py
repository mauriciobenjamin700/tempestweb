"""Ready-to-use composite forms built from the core's fields.

These compose the labelled fields into a complete, laid-out form so an app wires
one component instead of assembling inputs, labels, errors and a submit button by
hand. They are *controlled*: the app holds the field values in its state and
passes them in with ``on_*_change`` handlers; the form only lays out and dispatches.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import Field
from tempest_core import Button, Column, Style, Text, Widget
from tempest_core.style import Edge
from tempest_core.widgets import Component

from tempestweb.components.fields import EmailField, PasswordField

__all__ = ["LoginForm", "SignupForm"]


class LoginForm(Component):
    """A complete email + password login form with a submit button.

    The app keeps ``email``/``password`` in its state and updates them via the
    ``on_*_change`` handlers; ``on_submit`` fires when the button is pressed (the
    app reads the current values from its state and performs the login). Pass
    ``email_error``/``password_error`` to surface validation messages.

    Example:
        ```python
        def set_email(v: str) -> None:
            app.set_state(lambda s: setattr(s, "email", v))

        LoginForm(
            email=app.state.email,
            password=app.state.password,
            on_email_change=set_email,
            on_password_change=set_password,
            on_submit=do_login,
            email_error=app.state.email_error,
        )
        ```

    Attributes:
        email: The current e-mail value (controlled).
        password: The current password value (controlled).
        on_email_change: Called with the new e-mail string on each edit.
        on_password_change: Called with the new password string on each edit.
        on_submit: Called when the submit button is pressed.
        email_error: Validation message under the e-mail field (shown when set).
        password_error: Validation message under the password field.
        title: Optional heading shown above the fields.
        submit_label: The submit button label.
    """

    email: str = Field(default="", description="The current e-mail value.")
    password: str = Field(default="", description="The current password value.")
    on_email_change: Callable[[str], Any] = Field(
        description="Called with the new e-mail string on each edit."
    )
    on_password_change: Callable[[str], Any] = Field(
        description="Called with the new password string on each edit."
    )
    on_submit: Callable[[], Any] = Field(
        description="Called when the submit button is pressed."
    )
    email_error: str = Field(default="", description="E-mail validation message.")
    password_error: str = Field(default="", description="Password validation message.")
    title: str = Field(default="", description="Optional heading above the fields.")
    submit_label: str = Field(default="Entrar", description="Submit button label.")

    def render(self) -> Widget:
        """Lay out the title, fields and submit button in a column.

        Returns:
            A :class:`~tempest_core.Column` containing the optional title, the
            e-mail and password fields, and the submit button.
        """
        children: list[Widget] = []
        if self.title:
            children.append(Text(content=self.title, key="login-title"))
        children.extend(
            [
                EmailField(
                    value=self.email,
                    on_change=self.on_email_change,
                    error=self.email_error,
                    key="login-email",
                ),
                PasswordField(
                    value=self.password,
                    on_change=self.on_password_change,
                    error=self.password_error,
                    key="login-password",
                ),
                Button(
                    label=self.submit_label,
                    on_click=self.on_submit,
                    key="login-submit",
                ),
            ]
        )
        return Column(
            key=self.key or "login-form",
            style=Style(gap=12.0, padding=Edge.all(16)),
            children=children,
        )


class SignupForm(Component):
    """An email + password + confirm-password sign-up form with a submit button.

    Like :class:`LoginForm` it is controlled: the app holds the three values in
    state and updates them via the ``on_*_change`` handlers. ``on_submit`` fires
    when the button is pressed; surface validation via the ``*_error`` fields
    (e.g. set ``confirm_error`` when the passwords differ).

    Attributes:
        email: The current e-mail value (controlled).
        password: The current password value (controlled).
        confirm: The current confirm-password value (controlled).
        on_email_change: Called with the new e-mail string on each edit.
        on_password_change: Called with the new password string on each edit.
        on_confirm_change: Called with the new confirm-password string on each edit.
        on_submit: Called when the submit button is pressed.
        email_error: Validation message under the e-mail field.
        password_error: Validation message under the password field.
        confirm_error: Validation message under the confirm-password field.
        title: Optional heading shown above the fields.
        submit_label: The submit button label.
    """

    email: str = Field(default="", description="The current e-mail value.")
    password: str = Field(default="", description="The current password value.")
    confirm: str = Field(default="", description="The current confirm value.")
    on_email_change: Callable[[str], Any] = Field(
        description="Called with the new e-mail string on each edit."
    )
    on_password_change: Callable[[str], Any] = Field(
        description="Called with the new password string on each edit."
    )
    on_confirm_change: Callable[[str], Any] = Field(
        description="Called with the new confirm-password string on each edit."
    )
    on_submit: Callable[[], Any] = Field(
        description="Called when the submit button is pressed."
    )
    email_error: str = Field(default="", description="E-mail validation message.")
    password_error: str = Field(default="", description="Password validation message.")
    confirm_error: str = Field(default="", description="Confirm validation message.")
    title: str = Field(default="", description="Optional heading above the fields.")
    submit_label: str = Field(default="Cadastrar", description="Submit button label.")

    def render(self) -> Widget:
        """Lay out the title, fields and submit button in a column.

        Returns:
            A :class:`~tempest_core.Column` with the optional title, the e-mail,
            password and confirm-password fields, and the submit button.
        """
        children: list[Widget] = []
        if self.title:
            children.append(Text(content=self.title, key="signup-title"))
        children.extend(
            [
                EmailField(
                    value=self.email,
                    on_change=self.on_email_change,
                    error=self.email_error,
                    key="signup-email",
                ),
                PasswordField(
                    value=self.password,
                    on_change=self.on_password_change,
                    error=self.password_error,
                    key="signup-password",
                ),
                PasswordField(
                    value=self.confirm,
                    on_change=self.on_confirm_change,
                    error=self.confirm_error,
                    label="Confirmar senha",
                    key="signup-confirm",
                ),
                Button(
                    label=self.submit_label,
                    on_click=self.on_submit,
                    key="signup-submit",
                ),
            ]
        )
        return Column(
            key=self.key or "signup-form",
            style=Style(gap=12.0, padding=Edge.all(16)),
            children=children,
        )
