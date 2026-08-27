"""The column spec shared by every export format.

A :class:`Column` carries the three things a spreadsheet column needs and
nothing else: where the value comes from, what the header says, and how the
value is turned into something a cell can hold.

Example:
    >>> from datetime import date
    >>> rows = [{"id": 1, "name": "Ana", "created_at": date(2026, 8, 27)}]
    >>> columns = [
    ...     Column("id", "ID"),
    ...     Column("name", "Nome"),
    ...     Column("created_at", "Criado em"),
    ... ]
    >>> [column.value_of(rows[0]) for column in columns]
    [1, 'Ana', datetime.date(2026, 8, 27)]

Rows may be mappings or plain objects — a ``dict`` from an API, a dataclass, an
ORM row. The lookup tries the mapping key first and falls back to the attribute,
so the same column spec works across both without the caller adapting anything.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from tempestweb.export.errors import ColumnFieldError

__all__ = [
    "Column",
    "Formatter",
]

#: Turns a raw field value into what the cell should hold. Returning a ``str``
#: opts that column out of the format-aware cell typing in
#: :func:`~tempestweb.export.to_xlsx` — the value becomes text.
Formatter = Callable[[object], object]


@dataclass(frozen=True)
class Column:
    """One column of an export.

    Attributes:
        field: The mapping key (or attribute name) the value is read from.
        header: The text written in the header row.
        format: An optional callable turning the raw value into the cell value.
            Use it for presentation — ``lambda v: v.strftime("%d/%m/%Y")`` — and
            note that returning a string makes the XLSX cell a text cell.
    """

    field: str
    header: str
    format: Formatter | None = None

    def value_of(self, row: object) -> object:
        """Read this column's value out of one row.

        Args:
            row: The row to read, either a mapping or an object with attributes.

        Returns:
            The raw value, or the result of :attr:`format` when one is set.

        Raises:
            ColumnFieldError: If the row has neither the key nor the attribute.
        """
        raw = _read_field(row, self.field)
        return self.format(raw) if self.format is not None else raw


def _read_field(row: object, field: str) -> object:
    """Read one field off a row, whether it is a mapping or an object.

    Args:
        row: The row to read from.
        field: The mapping key or attribute name.

    Returns:
        The value stored under ``field``.

    Raises:
        ColumnFieldError: If the row carries neither the key nor the attribute.
            The message lists what the row does have, because the mistake is
            almost always a typo or a renamed field.
    """
    if isinstance(row, Mapping):
        if field in row:
            return row[field]
        available = ", ".join(sorted(str(key) for key in row)) or "<empty mapping>"
        raise ColumnFieldError(f"row has no key {field!r}; available keys: {available}")
    try:
        return getattr(row, field)
    except AttributeError as exc:
        available = ", ".join(
            sorted(name for name in dir(row) if not name.startswith("_"))
        )
        raise ColumnFieldError(
            f"row of type {type(row).__name__} has no attribute {field!r}; "
            f"available attributes: {available or '<none>'}"
        ) from exc
