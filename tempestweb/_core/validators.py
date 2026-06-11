"""Pure, dependency-free field validators for Brazilian forms.

Each validator matches the ``Form`` validator shape
``Callable[[Any], str | None]``: it returns a PT-BR error message string when the
value is invalid, or ``None`` when the value is valid. Mask / formatting
characters (dots, dashes, slashes, parentheses, spaces) are stripped before
validation, so a masked value such as ``"123.456.789-09"`` validates the same as
its bare digits.

Plug a validator into a :class:`~tempestroid.widgets.FormField`::

    FormField(
        name="cpf",
        validators=[validate_cpf],
        child=CPFInput(value=state.cpf, on_change=...),
    )
"""

from __future__ import annotations

import re
from typing import Any

__all__ = [
    "EMAIL_PATTERN",
    "validate_cpf",
    "validate_cnpj",
    "validate_email",
    "validate_phone",
]

#: A pragmatic email regular expression: a local part, an ``@`` and a dotted
#: domain with a 2+ letter top-level segment. Suitable for both
#: :func:`validate_email` and an ``Input`` / ``EmailInput`` ``pattern``.
EMAIL_PATTERN: str = r"[^@\s]+@[^@\s]+\.[^@\s]{2,}"

_DIGITS_RE = re.compile(r"\D")
_EMAIL_RE = re.compile(rf"^{EMAIL_PATTERN}$")


def _only_digits(value: Any) -> str:  # noqa: ANN401 — an opaque field value
    """Strip every non-digit character from a value's string form.

    Args:
        value: The raw value (any type; coerced via ``str``).

    Returns:
        The value's digits, in order, with all other characters removed.
    """
    return _DIGITS_RE.sub("", str(value))


def _all_same(digits: str) -> bool:
    """Report whether every character of ``digits`` is identical.

    All-same-digit documents (``"00000000000"``, ``"11111111111"``) pass the
    check-digit maths but are never issued, so both CPF and CNPJ validators
    reject them.

    Args:
        digits: A string of digits.

    Returns:
        ``True`` when the string is non-empty and all characters are equal.
    """
    return bool(digits) and digits == digits[0] * len(digits)


def validate_cpf(value: Any) -> str | None:  # noqa: ANN401 — an opaque field value
    """Validate a Brazilian CPF number.

    Strips mask characters, then checks for exactly 11 digits, rejects
    all-same-digit sequences, and verifies the two mod-11 check digits.

    Pairs with :class:`~tempestroid.components.CPFInput`.

    Args:
        value: The raw CPF (e.g. ``"529.982.247-25"`` or ``"52998224725"``).

    Returns:
        A PT-BR error message when the CPF is invalid, or ``None`` when valid.
    """
    digits = _only_digits(value)
    if len(digits) != 11:
        return "CPF deve ter 11 dígitos"
    if _all_same(digits):
        return "CPF inválido"
    numbers = [int(char) for char in digits]
    for position in (9, 10):
        weighted = sum(
            numbers[index] * ((position + 1) - index) for index in range(position)
        )
        remainder = (weighted * 10) % 11
        check = 0 if remainder == 10 else remainder
        if check != numbers[position]:
            return "CPF inválido"
    return None


def validate_cnpj(value: Any) -> str | None:  # noqa: ANN401 — an opaque field value
    """Validate a Brazilian CNPJ number.

    Strips mask characters, then checks for exactly 14 digits, rejects
    all-same-digit sequences, and verifies the two check digits using the
    standard CNPJ weights (``5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2``).

    Pairs with :class:`~tempestroid.components.CNPJInput`.

    Args:
        value: The raw CNPJ (e.g. ``"11.222.333/0001-81"`` or
            ``"11222333000181"``).

    Returns:
        A PT-BR error message when the CNPJ is invalid, or ``None`` when valid.
    """
    digits = _only_digits(value)
    if len(digits) != 14:
        return "CNPJ deve ter 14 dígitos"
    if _all_same(digits):
        return "CNPJ inválido"
    numbers = [int(char) for char in digits]
    first_weights = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    second_weights = [6, *first_weights]
    for weights, position in ((first_weights, 12), (second_weights, 13)):
        weighted = sum(
            numbers[index] * weights[index] for index in range(position)
        )
        remainder = weighted % 11
        check = 0 if remainder < 2 else 11 - remainder
        if check != numbers[position]:
            return "CNPJ inválido"
    return None


def validate_email(value: Any) -> str | None:  # noqa: ANN401 — an opaque field value
    """Validate an email address with a pragmatic regular expression.

    Pairs with :class:`~tempestroid.components.EmailInput`.

    Args:
        value: The raw email address.

    Returns:
        A PT-BR error message when the address is invalid, or ``None`` when
        valid.
    """
    text = str(value).strip()
    if not _EMAIL_RE.match(text):
        return "E-mail inválido"
    return None


def validate_phone(value: Any) -> str | None:  # noqa: ANN401 — an opaque field value
    """Validate a Brazilian phone number.

    Strips non-digits, then requires 10 digits (landline: DDD + 8-digit number)
    or 11 digits (mobile: DDD + leading ``9`` + 8-digit number).

    Pairs with :class:`~tempestroid.components.PhoneInput`.

    Args:
        value: The raw phone (e.g. ``"(11) 98765-4321"`` or ``"11987654321"``).

    Returns:
        A PT-BR error message when the number is invalid, or ``None`` when valid.
    """
    digits = _only_digits(value)
    if len(digits) not in (10, 11):
        return "Telefone inválido"
    return None
