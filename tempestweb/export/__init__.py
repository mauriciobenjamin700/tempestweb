"""Generate CSV and XLSX bytes in Python, for ``native.file.save`` to deliver.

``native.file.save`` hands bytes to the user. Nothing produced those bytes: an
app showing a ``DataTable`` with an "Export CSV" button had to write the encoder
by hand, and hand-rolled encoders fail in the same four places every time — a
separator inside a field, a quote inside the text, the missing UTF-8 BOM that
makes Excel read ``João`` as ``JoÃ£o``, and an XLSX date written as a bare
number.

This is byte generation, so it needs **no browser**: it runs in Python, and the
``file.save`` that already exists delivers the result.

!!! warning "Modes A and B only"
    Mode C transpiles the app's own Python into JavaScript and serves a fixed set
    of modules — ``tempest_core``, ``tempestweb.components`` and
    ``tempestweb.native``. Importing this package from a Mode C app is refused at
    build time with a named error. A Mode C app exports by asking the server for
    the file.

Example:
    ```python
    from tempestweb import native
    from tempestweb.export import Column, to_csv, to_xlsx

    COLUMNS = [
        Column("id", "ID"),
        Column("name", "Nome"),
        Column("created_at", "Criado em"),
    ]


    async def export_csv(rows: list[dict[str, object]]) -> None:
        await native.file.save(
            "usuarios.csv",
            to_csv(rows, COLUMNS),
            mime_type="text/csv",
        )


    async def export_xlsx(rows: list[dict[str, object]]) -> None:
        await native.file.save(
            "usuarios.xlsx",
            to_xlsx(rows, COLUMNS, sheet="Usuários"),
            mime_type=XLSX_MIME_TYPE,
        )
    ```

Import everything from this package level rather than from submodules.
"""

from __future__ import annotations

from tempestweb.export.columns import Column, Formatter
from tempestweb.export.csv_writer import BOM, LINE_TERMINATOR, to_csv
from tempestweb.export.errors import ColumnFieldError, ExportError, SheetNameError
from tempestweb.export.xlsx_writer import to_xlsx

__all__ = [
    "Column",
    "Formatter",
    "to_csv",
    "to_xlsx",
    "BOM",
    "LINE_TERMINATOR",
    "CSV_MIME_TYPE",
    "XLSX_MIME_TYPE",
    "ExportError",
    "ColumnFieldError",
    "SheetNameError",
]

#: The MIME type to pass to :func:`tempestweb.native.file.save` for CSV.
CSV_MIME_TYPE = "text/csv"

#: The MIME type to pass to :func:`tempestweb.native.file.save` for XLSX. Long
#: enough that every caller would otherwise paste it, and a typo here makes the
#: browser download the workbook as an unnamed binary blob.
XLSX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
