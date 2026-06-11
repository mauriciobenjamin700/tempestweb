"""tempestweb.components — ready-to-use fields and forms.

Pre-built, validated building blocks so an app declares a field or a whole form
in one line instead of wiring inputs, labels, errors and validators by hand:

    from tempestweb.components import EmailField, PasswordField, LoginForm

The fields are ergonomic aliases over the renderer-agnostic core's BR inputs
(:mod:`tempest_core.components.brforms`); the forms compose them. Everything
renders identically in Mode A (WASM) and Mode B (server).
"""

from __future__ import annotations

from tempestweb.components.fields import (
    AddressField,
    CNPJField,
    CPFField,
    EmailField,
    PasswordField,
    PhoneField,
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
    "PhoneField",
    "validate_cnpj",
    "validate_cpf",
    "validate_email",
    "validate_phone",
]
