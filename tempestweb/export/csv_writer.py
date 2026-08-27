r"""CSV generation, with the three mistakes hand-rolled encoders always make.

Writing CSV looks like ``",".join(...)`` right up to the first row that contains
a comma, a quote or a line break. This module delegates the quoting to the
standard library's :mod:`csv`, which gets all three right, and adds the fourth
thing nobody remembers: the UTF-8 BOM, without which Excel reads ``João`` as
``JoÃ£o``.

Example:
    >>> rows = [{"name": 'Ana "A" Silva', "city": "Recife, PE"}]
    >>> columns = [Column("name", "Nome"), Column("city", "Cidade")]
    >>> to_csv(rows, columns, bom=False)
    b'Nome,Cidade\r\n"Ana ""A"" Silva","Recife, PE"\r\n'

The output is :class:`bytes`, ready for
:func:`tempestweb.native.file.save` — this module never touches the browser.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from decimal import Decimal

from tempestweb.export.columns import Column
from tempestweb.export.errors import ExportError

__all__ = ["to_csv"]

#: Excel expects CRLF, including inside a quoted field. LF-only files open fine
#: in every other tool and break line breaks inside cells in Excel.
LINE_TERMINATOR = "\r\n"

#: The UTF-8 byte order mark. Excel needs it to detect the encoding; every other
#: consumer treats it as invisible whitespace at the start of the file.
BOM = "﻿"


def to_csv(
    rows: Iterable[object],
    columns: Sequence[Column],
    *,
    bom: bool = True,
    delimiter: str = ",",
    header: bool = True,
) -> bytes:
    """Render rows as CSV bytes.

    Args:
        rows: The rows to write, in order. Consumed once, so a generator works.
        columns: The columns to write, in order.
        bom: Whether to prefix the UTF-8 byte order mark. On by default because
            the common destination is Excel, which misreads accented text
            without it.
        delimiter: The field separator. Excel in a pt-BR locale expects ``";"``
            and puts a comma-separated file into a single column — see the
            warning in the recipe.
        header: Whether to write the header row.

    Returns:
        The encoded file, UTF-8, ready to hand to
        :func:`tempestweb.native.file.save`.

    Raises:
        ExportError: If ``columns`` is empty or ``delimiter`` is not exactly one
            character.
        ColumnFieldError: If a column names a field a row does not have.
    """
    if not columns:
        raise ExportError("to_csv needs at least one column")
    if len(delimiter) != 1:
        raise ExportError(f"delimiter must be exactly one character, got {delimiter!r}")

    buffer = io.StringIO(newline="")
    writer = csv.writer(
        buffer,
        delimiter=delimiter,
        quoting=csv.QUOTE_MINIMAL,
        lineterminator=LINE_TERMINATOR,
    )
    if header:
        writer.writerow([column.header for column in columns])
    for row in rows:
        writer.writerow([_as_text(column.value_of(row)) for column in columns])

    return ((BOM if bom else "") + buffer.getvalue()).encode("utf-8")


def _as_text(value: object) -> str:
    """Render one cell value as CSV text.

    Dates use ISO 8601 because it is the only unambiguous default; a column that
    wants ``dd/mm/yyyy`` says so with :attr:`Column.format`.

    Args:
        value: The value to render.

    Returns:
        The text written to the field, empty for ``None``.
    """
    if value is None:
        return ""
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)
