"""Ready-to-use, Material 3-styled form fields.

``TextField``/``EmailField``/``PasswordField`` are tempestweb-native: a labelled
column wrapping a plain :class:`~tempest_core.widgets.inputs.Input` with *no*
inline style, so the always-on MD3 base stylesheet (``client/theme.js``) renders
them as light, outlined fields consistent with the rest of a tempestweb UI. The
BR-specific fields (``PhoneField``/``CPFField``/``CNPJField``/``AddressField``)
are aliases over the core's masked inputs (:mod:`tempest_core.components.brforms`),
which keep their own masking logic.

    from tempestweb.components import EmailField, PasswordField, validate_email

Each field is *controlled*: pass the current ``value`` and an ``on_change`` that
stores the new string; pass ``error`` to show a validation message. They render
identically in both modes (the field is just core widgets).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import Field

from tempest_core import Column, Style, Text, Widget
from tempest_core.components.brforms import (
    AddressInput as AddressField,
)
from tempest_core.components.brforms import (
    CNPJInput as CNPJField,
)
from tempest_core.components.brforms import (
    CPFInput as CPFField,
)
from tempest_core.components.brforms import (
    PhoneInput as PhoneField,
)
from tempest_core.style import Color, Edge, FontWeight
from tempest_core.validators import (
    validate_cnpj,
    validate_cpf,
    validate_email,
    validate_phone,
)
from tempest_core.widgets import Component
from tempest_core.widgets.events import TextChangeEvent
from tempest_core.widgets.inputs import Input, KeyboardType

__all__ = [
    "AddressField",
    "CNPJField",
    "CPFField",
    "EmailField",
    "PasswordField",
    "PhoneField",
    "TextField",
    "validate_cnpj",
    "validate_cpf",
    "validate_email",
    "validate_phone",
]

# Shared text colors for a field's label and error line, tuned for the light
# Material 3 surface the base stylesheet renders against (client/theme.js).
_LABEL_COLOR: Color = Color.from_hex("#49454f")
_ERROR_COLOR: Color = Color.from_hex("#b3261e")


def _labelled_field(label: str, field: Widget, error: str, key: str) -> Widget:
    """Wrap an input in an optional label + optional error column.

    Args:
        label: The label text shown above the field (omitted when empty).
        field: The input widget to wrap.
        error: The validation message; the error line is hidden when empty.
        key: The reconciler key for the wrapping column.

    Returns:
        A :class:`~tempest_core.Column` of the optional label, the field and the
        optional error line.
    """
    children: list[Widget] = []
    if label:
        children.append(
            Text(
                content=label,
                style=Style(
                    font_size=13.0,
                    font_weight=FontWeight.MEDIUM,
                    color=_LABEL_COLOR,
                ),
                key="field-label",
            )
        )
    children.append(field)
    if error:
        children.append(
            Text(
                content=error,
                style=Style(font_size=12.0, color=_ERROR_COLOR),
                key="field-error",
            )
        )
    return Column(key=key, style=Style(gap=4.0), children=children)


class TextField(Component):
    """A generic labelled text field for arbitrary input (name, title, …).

    The general-purpose sibling of the BR-specific fields: a label, a controlled
    text :class:`~tempest_core.Input`, and an optional error message. Controlled —
    pass ``value`` and an ``on_change`` that stores the new string.

    Attributes:
        value: The current text value (controlled).
        label: The label shown above the field (omitted when empty).
        placeholder: The empty-field hint.
        error: The validation message; shown in red when non-empty.
        on_change: Called with the new string value on each edit.
    """

    value: str = Field(default="", description="The current text value (controlled).")
    label: str = Field(default="", description="The label shown above the field.")
    placeholder: str = Field(default="", description="The empty-field hint.")
    error: str = Field(default="", description="Validation message (shown when set).")
    on_change: Callable[[str], Any] = Field(
        description="Called with the new string value on each edit."
    )

    def render(self) -> Widget:
        """Lower the field into a labelled column wrapping a text Input.

        Returns:
            A :class:`~tempest_core.Column` with the optional label, the text
            input, and the optional error line.
        """
        on_change = self.on_change

        def _emit(event: TextChangeEvent) -> None:
            on_change(event.value)

        children: list[Widget] = []
        if self.label:
            children.append(Text(content=self.label, key="text-field-label"))
        children.append(
            Input(
                value=self.value,
                placeholder=self.placeholder,
                on_change=_emit,
                key="text-field-input",
            )
        )
        if self.error:
            children.append(
                Text(
                    content=self.error,
                    key="text-field-error",
                    style=Style(color=_ERROR_COLOR),
                )
            )
        return Column(
            key=self.key or "text-field",
            style=Style(gap=4.0, padding=Edge.symmetric(vertical=4.0)),
            children=children,
        )


class EmailField(Component):
    """A labelled e-mail field styled for the Material 3 light surface.

    The tempestweb-native e-mail field: a muted label, a controlled
    :class:`~tempest_core.widgets.inputs.Input` on the e-mail keyboard, and an
    optional error line. The input carries no inline style, so the always-on MD3
    base stylesheet (``client/theme.js``) renders it as a light, outlined field
    that matches the rest of a tempestweb UI — unlike the core's dark BR input.

    Validate with :func:`validate_email`.

    Attributes:
        value: The current e-mail value (controlled).
        label: The label shown above the field (omitted when empty).
        placeholder: The empty-field hint.
        error: The validation message; shown in red when non-empty.
        on_change: Called with the new string value on each edit.
    """

    value: str = Field(default="", description="The current e-mail value (controlled).")
    label: str = Field(default="E-mail", description="The label shown above the field.")
    placeholder: str = Field(
        default="you@example.com", description="The empty-field hint."
    )
    error: str = Field(default="", description="Validation message (shown when set).")
    on_change: Callable[[str], Any] = Field(
        description="Called with the new string value on each edit."
    )

    def render(self) -> Widget:
        """Lower the e-mail field into a labelled column wrapping an Input.

        Returns:
            A :class:`~tempest_core.Column` with the optional label, the e-mail
            input, and the optional error line.
        """
        on_change = self.on_change

        def _emit(event: TextChangeEvent) -> None:
            on_change(event.value)

        field = Input(
            value=self.value,
            placeholder=self.placeholder,
            keyboard=KeyboardType.EMAIL,
            on_change=_emit,
            key="email-field-input",
        )
        return _labelled_field(self.label, field, self.error, self.key or "email-field")


class PasswordField(Component):
    """A labelled, secure password field styled for the MD3 light surface.

    Like :class:`EmailField` but the input is ``secure`` (masked) and carries no
    inline style, so the MD3 base stylesheet renders a light, outlined field.

    Attributes:
        value: The current password value (controlled).
        label: The label shown above the field (omitted when empty).
        placeholder: The empty-field hint.
        error: The validation message; shown in red when non-empty.
        on_change: Called with the new string value on each edit.
    """

    value: str = Field(default="", description="The current password (controlled).")
    label: str = Field(default="Senha", description="The label shown above the field.")
    placeholder: str = Field(default="", description="The empty-field hint.")
    error: str = Field(default="", description="Validation message (shown when set).")
    on_change: Callable[[str], Any] = Field(
        description="Called with the new string value on each edit."
    )

    def render(self) -> Widget:
        """Lower the password field into a labelled column wrapping an Input.

        Returns:
            A :class:`~tempest_core.Column` with the optional label, the secure
            input, and the optional error line.
        """
        on_change = self.on_change

        def _emit(event: TextChangeEvent) -> None:
            on_change(event.value)

        field = Input(
            value=self.value,
            placeholder=self.placeholder,
            secure=True,
            on_change=_emit,
            key="password-field-input",
        )
        return _labelled_field(
            self.label, field, self.error, self.key or "password-field"
        )
