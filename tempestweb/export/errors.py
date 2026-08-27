"""Errors raised while generating an export.

Every one of them is a developer mistake, not a user-facing condition: a column
naming a field the rows do not have, a sheet name Excel refuses to open, a date
the format cannot represent. They fail loudly for the same reason
:class:`~tempestweb.native.http.RetryOptions` forbids unknown keys — a silent
empty column is discovered by whoever opens the spreadsheet, which is much later
and much more expensive.
"""

from __future__ import annotations

__all__ = [
    "ExportError",
    "ColumnFieldError",
    "SheetNameError",
]


class ExportError(ValueError):
    """Base class for every export failure."""


class ColumnFieldError(ExportError):
    """A :class:`~tempestweb.export.Column` names a field the row does not have.

    Raised instead of writing an empty cell: a typo in ``Column("nmae", "Nome")``
    would otherwise export a full column of blanks, and nothing in the pipeline
    would say so.
    """


class SheetNameError(ExportError):
    r"""The sheet name is one Excel refuses to open.

    Excel caps sheet names at 31 characters and rejects ``[ ] : * ? / \\``, a
    leading or trailing apostrophe, an empty name, and the reserved name
    ``History``. A workbook carrying an invalid name opens as "unreadable
    content", with no hint about which part is at fault.
    """
