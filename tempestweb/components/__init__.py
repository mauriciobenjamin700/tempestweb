"""tempestweb.components — ready-to-use fields, forms and Material 3 buttons.

Pre-built, validated building blocks so an app declares a field, a button or a
whole form in one line instead of wiring inputs, labels, errors and validators
by hand:

    from tempestweb.components import EmailField, PasswordField, LoginForm
    from tempestweb.components import filled_button, text_button

``EmailField``/``PasswordField`` and ``TextField`` are tempestweb-native, styled
for the Material 3 light surface the base stylesheet renders; the BR fields
(:class:`PhoneField`/:class:`CPFField`/:class:`CNPJField`/:class:`AddressField`)
wrap the core's masked inputs. The ``*_button`` helpers build the MD3 button
variants. Everything renders identically in Mode A (WASM) and Mode B (server).
"""

from __future__ import annotations

from tempestweb.components.buttons import (
    elevated_button,
    filled_button,
    outlined_button,
    text_button,
    tonal_button,
)
from tempestweb.components.fields import (
    AddressField,
    CNPJField,
    CPFField,
    EmailField,
    PasswordField,
    PhoneField,
    TextField,
    validate_cnpj,
    validate_cpf,
    validate_email,
    validate_phone,
)
from tempestweb.components.forms import LoginForm, SignupForm

__all__ = [
    "AddressField",
    "CNPJField",
    "CPFField",
    "EmailField",
    "LoginForm",
    "PasswordField",
    "SignupForm",
    "TextField",
    "PhoneField",
    "elevated_button",
    "filled_button",
    "outlined_button",
    "text_button",
    "tonal_button",
    "validate_cnpj",
    "validate_cpf",
    "validate_email",
    "validate_phone",
]
