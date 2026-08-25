"""Ready-to-use, Material 3-styled form fields.

``TextField``/``EmailField``/``PasswordField`` are tempestweb-native: a labelled
column wrapping a plain :class:`~tempest_core.widgets.inputs.Input`. tempest-core
resolves the Input's outlined Material 3 style inline **against the theme the
field hands it**, so the fields look consistent with the rest of a tempestweb UI
without any per-field styling — and follow a dark app into dark. Pass
``theme=app.theme`` exactly as you would to a widget. The
BR-specific fields (``PhoneField``/``CPFField``/``CNPJField``/``AddressField``)
are aliases over the core's masked inputs (:mod:`tempest_core.components.brforms`),
which keep their own masking logic.

    from tempestweb.components import EmailField, PasswordField, validate_email

Each field is *controlled*: pass the current ``value`` and an ``on_change`` that
stores the new string; pass ``error`` to show a validation message. They render
identically in both modes (the field is just core widgets).

!!! note
    Until 0.101.0 these three declared no ``theme`` at all and built their ``Input``
    without one, so they were **light by construction**: an app in dark mode got a
    light field with no warning, and in the worst case a dark surface under dark
    text.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import Field

from tempest_core import (
    AddressInput as AddressField,
)
from tempest_core import (
    CNPJInput as CNPJField,
)
from tempest_core import (
    Color,
    ColorRole,
    Column,
    Component,
    Edge,
    FontWeight,
    Input,
    KeyboardType,
    Style,
    Text,
    TextChangeEvent,
    Theme,
    Widget,
    current_theme,
    validate_cnpj,
    validate_cpf,
    validate_email,
    validate_phone,
)
from tempest_core import (
    CPFInput as CPFField,
)
from tempest_core import (
    PhoneInput as PhoneField,
)

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


def _label_color(theme: Theme) -> Color:
    """The muted text colour a field's label paints with, for this theme.

    Resolved from the theme's colour scheme rather than frozen as a hex, which is
    what made these fields light-only: the label was tuned for the Material 3
    light surface and stayed that colour in a dark app.

    Args:
        theme: The theme the field was given.

    Returns:
        The scheme's ``on_surface_variant`` role.
    """
    return theme.scheme().role(ColorRole.ON_SURFACE_VARIANT)


def _error_color(theme: Theme) -> Color:
    """The colour a field's validation message paints with, for this theme.

    Args:
        theme: The theme the field was given.

    Returns:
        The scheme's ``error`` role.
    """
    return theme.scheme().role(ColorRole.ERROR)


def _labelled_field(
    label: str, field: Widget, error: str, key: str, theme: Theme
) -> Widget:
    """Wrap an input in an optional label + optional error column.

    Every child key is derived from ``key``. Keys are how the event router finds
    the handler that fired, so a literal key here would be shared by every field
    of this kind on the screen and edits would land on the wrong one.

    ``Text`` takes no theme of its own, so the label and error colours are
    resolved here and passed as inline style — which is why the theme has to
    travel this far down rather than stopping at the ``Input``.

    Args:
        label: The label text shown above the field (omitted when empty).
        field: The input widget to wrap.
        error: The validation message; the error line is hidden when empty.
        key: The reconciler key for the wrapping column, and the prefix its
            children's keys are derived from.
        theme: The theme whose scheme resolves the label and error colours.

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
                    color=_label_color(theme),
                ),
                key=f"{key}-label",
            )
        )
    children.append(field)
    if error:
        children.append(
            Text(
                content=error,
                style=Style(font_size=12.0, color=_error_color(theme)),
                key=f"{key}-error",
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
        error: The validation message; shown in the theme's error colour.
        on_change: Called with the new string value on each edit.
        theme: The theme the input, label and error line resolve against.
    """

    value: str = Field(default="", description="The current text value (controlled).")
    label: str = Field(default="", description="The label shown above the field.")
    placeholder: str = Field(default="", description="The empty-field hint.")
    error: str = Field(default="", description="Validation message (shown when set).")
    on_change: Callable[[str], Any] = Field(
        description="Called with the new string value on each edit."
    )
    theme: Theme = Field(
        default_factory=current_theme,
        description="The theme the field's input, label and error resolve against.",
    )

    def render(self) -> Widget:
        """Lower the field into a labelled column wrapping a text Input.

        The inner widgets' keys are derived from this component's ``key``. They
        used to be literals, so two fields on the same screen shared the key of
        the ``Input`` that actually emits the events and the router could not
        tell them apart — an edit applied to the wrong field, silently.

        Returns:
            A :class:`~tempest_core.Column` with the optional label, the text
            input, and the optional error line.
        """
        on_change = self.on_change

        def _emit(event: TextChangeEvent) -> None:
            """Unwrap the core's change event and hand the plain string over.

            The field's public ``on_change`` takes a ``str``, not an event, so
            the component absorbs the widget-level event shape. It closes over
            the callable captured above rather than over ``self``, so the
            handler does not keep the component instance alive.

            Args:
                event: The input's change event, carrying the new value.
            """
            on_change(event.value)

        base = self.key or "text-field"
        children: list[Widget] = []
        if self.label:
            children.append(Text(content=self.label, key=f"{base}-label"))
        children.append(
            Input(
                value=self.value,
                placeholder=self.placeholder,
                on_change=_emit,
                theme=self.theme,
                key=f"{base}-input",
            )
        )
        if self.error:
            children.append(
                Text(
                    content=self.error,
                    key=f"{base}-error",
                    style=Style(color=_error_color(self.theme)),
                )
            )
        return Column(
            key=base,
            style=Style(gap=4.0, padding=Edge.symmetric(vertical=4.0)),
            children=children,
        )


class EmailField(Component):
    """A labelled, Material 3 e-mail field that follows the theme it is given.

    The tempestweb-native e-mail field: a muted label, a controlled
    :class:`~tempest_core.widgets.inputs.Input` on the e-mail keyboard, and an
    optional error line. tempest-core resolves the Input's outlined Material 3
    style inline **against ``theme``**, so it matches the rest of a tempestweb UI
    in light and in dark alike.

    Validate with :func:`validate_email`.

    Attributes:
        value: The current e-mail value (controlled).
        label: The label shown above the field (omitted when empty).
        placeholder: The empty-field hint.
        error: The validation message; shown in the theme's error colour.
        on_change: Called with the new string value on each edit.
        theme: The theme the input, label and error line resolve against.
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
    theme: Theme = Field(
        default_factory=current_theme,
        description="The theme the field's input, label and error resolve against.",
    )

    def render(self) -> Widget:
        """Lower the e-mail field into a labelled column wrapping an Input.

        Returns:
            A :class:`~tempest_core.Column` with the optional label, the e-mail
            input, and the optional error line.
        """
        on_change = self.on_change

        def _emit(event: TextChangeEvent) -> None:
            """Unwrap the core's change event and hand the plain string over.

            The field's public ``on_change`` takes a ``str``, not an event, so
            the component absorbs the widget-level event shape. It closes over
            the callable captured above rather than over ``self``, so the
            handler does not keep the component instance alive.

            Args:
                event: The input's change event, carrying the new value.
            """
            on_change(event.value)

        base = self.key or "email-field"
        field = Input(
            value=self.value,
            placeholder=self.placeholder,
            keyboard=KeyboardType.EMAIL,
            on_change=_emit,
            theme=self.theme,
            key=f"{base}-input",
        )
        return _labelled_field(self.label, field, self.error, base, self.theme)


class PasswordField(Component):
    """A labelled, secure password field that follows the theme it is given.

    Like :class:`EmailField` but the input is ``secure`` (masked). It carries no
    inline style of its own: the core resolves the outlined Material 3 treatment
    from ``theme``, so the field is light in a light app and dark in a dark one.

    Attributes:
        value: The current password value (controlled).
        label: The label shown above the field (omitted when empty).
        placeholder: The empty-field hint.
        error: The validation message; shown in the theme's error colour.
        on_change: Called with the new string value on each edit.
        theme: The theme the input, label and error line resolve against.
    """

    value: str = Field(default="", description="The current password (controlled).")
    label: str = Field(default="Senha", description="The label shown above the field.")
    placeholder: str = Field(default="", description="The empty-field hint.")
    error: str = Field(default="", description="Validation message (shown when set).")
    on_change: Callable[[str], Any] = Field(
        description="Called with the new string value on each edit."
    )
    theme: Theme = Field(
        default_factory=current_theme,
        description="The theme the field's input, label and error resolve against.",
    )

    def render(self) -> Widget:
        """Lower the password field into a labelled column wrapping an Input.

        Returns:
            A :class:`~tempest_core.Column` with the optional label, the secure
            input, and the optional error line.
        """
        on_change = self.on_change

        def _emit(event: TextChangeEvent) -> None:
            """Unwrap the core's change event and hand the plain string over.

            The field's public ``on_change`` takes a ``str``, not an event, so
            the component absorbs the widget-level event shape. It closes over
            the callable captured above rather than over ``self``, so the
            handler does not keep the component instance alive.

            Args:
                event: The input's change event, carrying the new value.
            """
            on_change(event.value)

        base = self.key or "password-field"
        field = Input(
            value=self.value,
            placeholder=self.placeholder,
            secure=True,
            on_change=_emit,
            theme=self.theme,
            key=f"{base}-input",
        )
        return _labelled_field(self.label, field, self.error, base, self.theme)
