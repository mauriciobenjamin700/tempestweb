"""Brazilian form-input components (labelled CPF/CNPJ/phone/e-mail and address).

Each component lowers to the primitive :class:`~tempestroid.widgets.Input` /
:class:`~tempestroid.widgets.MaskedInput` leaves wrapped in a labelled
``Column`` (optional label ``Text`` above, the input, an optional red error
``Text`` below) — the same idiom as ``FormField`` / ``SearchBar``. Because they
are :class:`~tempestroid.widgets.Component` subclasses, they work in both
renderers (Qt and Compose) with no renderer change.

Every component exposes a plain ``on_change`` callable that receives the new
*string* value (the child input's typed ``TextChangeEvent.value``), so callers
never touch the event object. Pair each masked/validated field with the matching
validator from :mod:`tempestroid.validators`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import Field

from tempestweb._core.components.base import BACKGROUND, ON_MUTED, ON_SURFACE, merge_style
from tempestweb._core.style import Color, Edge, FontWeight, Style
from tempestweb._core.validators import EMAIL_PATTERN
from tempestweb._core.widgets import (
    Column,
    Component,
    Input,
    KeyboardType,
    MaskedInput,
    Text,
    TextChangeEvent,
    Widget,
)

__all__ = [
    "EmailInput",
    "PasswordInput",
    "PhoneInput",
    "CPFInput",
    "CNPJInput",
    "AddressInput",
]

#: The error-text color shared by every labelled BR field.
_ERROR_COLOR: Color = Color.from_hex("#ef4444")


def _label_text(label: str, key: str) -> Widget:
    """Build the small label shown above a field.

    Args:
        label: The label text.
        key: The reconciler key.

    Returns:
        A muted, medium-weight :class:`~tempestroid.widgets.Text`.
    """
    return Text(
        content=label,
        style=Style(font_size=13.0, font_weight=FontWeight.MEDIUM, color=ON_MUTED),
        key=key,
    )


def _error_text(error: str, key: str) -> Widget:
    """Build the red error line shown under a field.

    Args:
        error: The validation message.
        key: The reconciler key.

    Returns:
        A red :class:`~tempestroid.widgets.Text` carrying the message.
    """
    return Text(
        content=error,
        style=Style(font_size=12.0, color=_ERROR_COLOR),
        key=key,
    )


def _labelled_field(
    label: str, field: Widget, error: str, key: str, style: Style | None
) -> Widget:
    """Wrap an input in an optional label + optional error column.

    Args:
        label: The label text (omitted when empty).
        field: The input widget to wrap.
        error: The validation message (the error line is hidden when empty).
        key: The reconciler key for the wrapping column.
        style: The caller-supplied style merged over the default column style.

    Returns:
        A :class:`~tempestroid.widgets.Column` of the label, the field and the
        error line.
    """
    children: list[Widget] = []
    if label:
        children.append(_label_text(label, "field-label"))
    children.append(field)
    if error:
        children.append(_error_text(error, "field-error"))
    default = Style(gap=4.0)
    return Column(key=key, style=merge_style(default, style), children=children)


def _on_value(handler: Callable[[str], Any]) -> Callable[[TextChangeEvent], None]:
    """Adapt a string handler to the input's typed ``on_change``.

    Args:
        handler: The component's ``on_change`` callable taking the new value.

    Returns:
        A handler taking a :class:`~tempestroid.widgets.TextChangeEvent` and
        forwarding its ``value`` to ``handler``.
    """

    def adapter(event: TextChangeEvent) -> None:
        handler(event.value)

    return adapter


def _field_style() -> Style:
    """Build the shared visual style for the inner input widget.

    Returns:
        A :class:`~tempestroid.style.Style` with padding, radius and on-surface
        text color.
    """
    return Style(
        padding=Edge.symmetric(vertical=10.0, horizontal=14.0),
        radius=8.0,
        background=BACKGROUND,
        color=ON_SURFACE,
    )


class EmailInput(Component):
    """A labelled e-mail field with the e-mail keyboard and a mail icon.

    Validate with :func:`tempestroid.validators.validate_email`.

    Attributes:
        value: The current text value (controlled).
        label: The label shown above the field (omitted when empty).
        placeholder: The empty-field hint.
        error: The validation message; shown in red when non-empty.
        on_change: Called with the new string value on each edit.
    """

    value: str = Field(default="", description="The current text value (controlled).")
    label: str = Field(
        default="E-mail", description="The label shown above the field."
    )
    placeholder: str = Field(default="", description="The empty-field hint.")
    error: str = Field(
        default="", description="The validation message; shown in red when non-empty."
    )
    on_change: Callable[[str], Any] = Field(
        description="Called with the new string value on each edit."
    )

    def render(self) -> Widget:
        """Lower the e-mail input into a labelled column.

        Returns:
            A labelled :class:`~tempestroid.widgets.Column` wrapping an
            e-mail-keyboard :class:`~tempestroid.widgets.Input`.
        """
        field = Input(
            value=self.value,
            placeholder=self.placeholder,
            keyboard=KeyboardType.EMAIL,
            pattern=EMAIL_PATTERN,
            leading_icon="mail",
            on_change=_on_value(self.on_change),
            style=_field_style(),
            key="email-field",
        )
        return _labelled_field(
            self.label, field, self.error, self.key or "email-input", self.style
        )


class PasswordInput(Component):
    """A labelled password field (secure, with the built-in eye toggle).

    Attributes:
        value: The current text value (controlled).
        label: The label shown above the field (omitted when empty).
        placeholder: The empty-field hint.
        error: The validation message; shown in red when non-empty.
        on_change: Called with the new string value on each edit.
    """

    value: str = Field(default="", description="The current text value (controlled).")
    label: str = Field(default="Senha", description="The label shown above the field.")
    placeholder: str = Field(default="Senha", description="The empty-field hint.")
    error: str = Field(
        default="", description="The validation message; shown in red when non-empty."
    )
    on_change: Callable[[str], Any] = Field(
        description="Called with the new string value on each edit."
    )

    def render(self) -> Widget:
        """Lower the password input into a labelled column.

        Returns:
            A labelled :class:`~tempestroid.widgets.Column` wrapping a secure
            :class:`~tempestroid.widgets.Input`.
        """
        field = Input(
            value=self.value,
            placeholder=self.placeholder,
            secure=True,
            leading_icon="lock",
            on_change=_on_value(self.on_change),
            style=_field_style(),
            key="password-field",
        )
        return _labelled_field(
            self.label, field, self.error, self.key or "password-input", self.style
        )


class PhoneInput(Component):
    """A labelled Brazilian phone field, masked ``(99) 99999-9999``.

    Validate with :func:`tempestroid.validators.validate_phone`.

    Attributes:
        value: The current text value (controlled).
        label: The label shown above the field (omitted when empty).
        placeholder: The empty-field hint.
        error: The validation message; shown in red when non-empty.
        on_change: Called with the new string value on each edit.
    """

    value: str = Field(default="", description="The current text value (controlled).")
    label: str = Field(
        default="Telefone", description="The label shown above the field."
    )
    placeholder: str = Field(default="", description="The empty-field hint.")
    error: str = Field(
        default="", description="The validation message; shown in red when non-empty."
    )
    on_change: Callable[[str], Any] = Field(
        description="Called with the new string value on each edit."
    )

    def render(self) -> Widget:
        """Lower the phone input into a labelled column.

        Returns:
            A labelled :class:`~tempestroid.widgets.Column` wrapping a masked
            :class:`~tempestroid.widgets.MaskedInput`.
        """
        field = MaskedInput(
            value=self.value,
            placeholder=self.placeholder,
            mask="(99) 99999-9999",
            keyboard=KeyboardType.PHONE,
            on_change=_on_value(self.on_change),
            style=_field_style(),
            key="phone-field",
        )
        return _labelled_field(
            self.label, field, self.error, self.key or "phone-input", self.style
        )


class CPFInput(Component):
    """A labelled CPF field, masked ``999.999.999-99``.

    Validate with :func:`tempestroid.validators.validate_cpf`.

    Attributes:
        value: The current text value (controlled).
        label: The label shown above the field (omitted when empty).
        placeholder: The empty-field hint.
        error: The validation message; shown in red when non-empty.
        on_change: Called with the new string value on each edit.
    """

    value: str = Field(default="", description="The current text value (controlled).")
    label: str = Field(default="CPF", description="The label shown above the field.")
    placeholder: str = Field(default="", description="The empty-field hint.")
    error: str = Field(
        default="", description="The validation message; shown in red when non-empty."
    )
    on_change: Callable[[str], Any] = Field(
        description="Called with the new string value on each edit."
    )

    def render(self) -> Widget:
        """Lower the CPF input into a labelled column.

        Returns:
            A labelled :class:`~tempestroid.widgets.Column` wrapping a masked
            :class:`~tempestroid.widgets.MaskedInput`.
        """
        field = MaskedInput(
            value=self.value,
            placeholder=self.placeholder,
            mask="999.999.999-99",
            keyboard=KeyboardType.NUMBER,
            on_change=_on_value(self.on_change),
            style=_field_style(),
            key="cpf-field",
        )
        return _labelled_field(
            self.label, field, self.error, self.key or "cpf-input", self.style
        )


class CNPJInput(Component):
    """A labelled CNPJ field, masked ``99.999.999/9999-99``.

    Validate with :func:`tempestroid.validators.validate_cnpj`.

    Attributes:
        value: The current text value (controlled).
        label: The label shown above the field (omitted when empty).
        placeholder: The empty-field hint.
        error: The validation message; shown in red when non-empty.
        on_change: Called with the new string value on each edit.
    """

    value: str = Field(default="", description="The current text value (controlled).")
    label: str = Field(default="CNPJ", description="The label shown above the field.")
    placeholder: str = Field(default="", description="The empty-field hint.")
    error: str = Field(
        default="", description="The validation message; shown in red when non-empty."
    )
    on_change: Callable[[str], Any] = Field(
        description="Called with the new string value on each edit."
    )

    def render(self) -> Widget:
        """Lower the CNPJ input into a labelled column.

        Returns:
            A labelled :class:`~tempestroid.widgets.Column` wrapping a masked
            :class:`~tempestroid.widgets.MaskedInput`.
        """
        field = MaskedInput(
            value=self.value,
            placeholder=self.placeholder,
            mask="99.999.999/9999-99",
            keyboard=KeyboardType.NUMBER,
            on_change=_on_value(self.on_change),
            style=_field_style(),
            key="cnpj-field",
        )
        return _labelled_field(
            self.label, field, self.error, self.key or "cnpj-input", self.style
        )


class AddressInput(Component):
    """A grouped Brazilian address block of labelled fields.

    Renders a labelled ``Column`` of CEP (masked ``99999-999``), street, number,
    complement, neighborhood, city and UF inputs. A single ``on_change`` handler
    is called as ``on_change(field_name, new_value)`` for whichever field
    changed, where ``field_name`` is one of ``"cep"``, ``"street"``, ``"number"``,
    ``"complement"``, ``"neighborhood"``, ``"city"`` or ``"state"``.

    Attributes:
        cep: The current postal code (CEP) value.
        street: The current street value.
        number: The current house/building number value.
        complement: The current address complement value.
        neighborhood: The current neighborhood value.
        city: The current city value.
        state: The current state (UF) value.
        label: The block heading (omitted when empty).
        on_change: Called as ``on_change(field_name, new_value)`` on each edit.
    """

    cep: str = Field(default="", description="The current postal code (CEP) value.")
    street: str = Field(default="", description="The current street value.")
    number: str = Field(
        default="", description="The current house/building number value."
    )
    complement: str = Field(
        default="", description="The current address complement value."
    )
    neighborhood: str = Field(
        default="", description="The current neighborhood value."
    )
    city: str = Field(default="", description="The current city value.")
    state: str = Field(default="", description="The current state (UF) value.")
    label: str = Field(
        default="Endereço", description="The block heading (omitted when empty)."
    )
    on_change: Callable[[str, str], Any] = Field(
        description="Called as ``on_change(field_name, new_value)`` on each edit."
    )

    def _field_handler(self, field_name: str) -> Callable[[TextChangeEvent], None]:
        """Build a typed handler that reports edits for one named field.

        Args:
            field_name: The address field this handler reports for.

        Returns:
            A handler forwarding ``(field_name, event.value)`` to ``on_change``.
        """

        def handler(event: TextChangeEvent) -> None:
            self.on_change(field_name, event.value)

        return handler

    def render(self) -> Widget:
        """Lower the address block into a labelled column of inputs.

        Returns:
            A :class:`~tempestroid.widgets.Column` of the heading and the
            address inputs.
        """
        children: list[Widget] = []
        if self.label:
            children.append(_label_text(self.label, "address-label"))
        children.append(
            MaskedInput(
                value=self.cep,
                placeholder="CEP",
                mask="99999-999",
                keyboard=KeyboardType.NUMBER,
                on_change=self._field_handler("cep"),
                style=_field_style(),
                key="address-cep",
            )
        )
        text_fields: list[tuple[str, str, str]] = [
            ("street", self.street, "Rua"),
            ("number", self.number, "Número"),
            ("complement", self.complement, "Complemento"),
            ("neighborhood", self.neighborhood, "Bairro"),
            ("city", self.city, "Cidade"),
            ("state", self.state, "UF"),
        ]
        for field_name, field_value, placeholder in text_fields:
            children.append(
                Input(
                    value=field_value,
                    placeholder=placeholder,
                    on_change=self._field_handler(field_name),
                    style=_field_style(),
                    key=f"address-{field_name}",
                )
            )
        default = Style(gap=8.0)
        return Column(
            key=self.key or "address-input",
            style=merge_style(default, self.style),
            children=children,
        )
