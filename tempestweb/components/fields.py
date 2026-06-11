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
from tempest_core.validators import (
    validate_cnpj,
    validate_cpf,
    validate_email,
    validate_phone,
)

__all__ = [
    "AddressField",
    "CNPJField",
    "CPFField",
    "EmailField",
    "PasswordField",
    "PhoneField",
    "validate_cnpj",
    "validate_cpf",
    "validate_email",
    "validate_phone",
]
