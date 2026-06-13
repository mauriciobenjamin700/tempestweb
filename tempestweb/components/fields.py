"""Ready-to-use form fields — ergonomic aliases over the core's BR inputs.

The renderer-agnostic core ships labelled, validated input components (email,
password, phone, CPF, CNPJ, address). tempestweb re-exports them under ``*Field``
names so an app imports one obvious thing per field:

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
    EmailInput as EmailField,
)
from tempest_core.components.brforms import (
    PasswordInput as PasswordField,
)
from tempest_core.components.brforms import (
    PhoneInput as PhoneField,
)
from tempest_core.style import Color, Edge
from tempest_core.validators import (
    validate_cnpj,
    validate_cpf,
    validate_email,
    validate_phone,
)
from tempest_core.widgets import Component
from tempest_core.widgets.events import TextChangeEvent
from tempest_core.widgets.inputs import Input

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
                    style=Style(color=Color.from_hex("#cc3333")),
                )
            )
        return Column(
            key=self.key or "text-field",
            style=Style(gap=4.0, padding=Edge.symmetric(vertical=4.0)),
            children=children,
        )
