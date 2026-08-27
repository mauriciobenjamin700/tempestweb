# Export CSV and XLSX (`tempestweb.export`)

!!! tip "What you'll learn"
    How to turn the rows already on your screen into a file the user downloads —
    CSV or XLSX — without writing an encoder by hand and without installing
    anything. 🚀

Your app shows a `DataTable`. The user wants an **"Export"** button. You already
have [`native.file.save`](native-reference.md), which hands bytes to the user —
but what **produces** those bytes?

Until now, you did. And hand-rolled encoders fail in the same places every time.

## The problem, in four lines

```python
# ❌ Don't do this
lines = ["id,name,city"]
for row in rows:
    lines.append(f"{row['id']},{row['name']},{row['city']}")
csv = "\n".join(lines).encode("utf-8")
```

It works right up to the first row of real data:

| The data | What breaks |
| --- | --- |
| `Recife, PE` | the comma becomes a separator: the row grows a column |
| `Ana "A" Silva` | the quotes break whoever parses the file |
| `João` | with no BOM, Excel opens it as `JoÃ£o` |
| `27/08/2026` in an XLSX | becomes the number `46265` — Excel has no date type |

`tempestweb.export` wraps exactly those four.

## Your first export

A complete program that runs:

```python
from tempestweb import native
from tempestweb.export import CSV_MIME_TYPE, Column, to_csv

COLUMNS = [
    Column("id", "ID"),
    Column("name", "Name"),
    Column("city", "City"),
]

ROWS = [
    {"id": 1, "name": 'Ana "A" Silva', "city": "Recife, PE"},
    {"id": 2, "name": "João", "city": "Olinda"},
]


async def export() -> None:
    """Generate the CSV and hand it to the user."""
    await native.file.save(
        "users.csv",
        to_csv(ROWS, COLUMNS),
        mime_type=CSV_MIME_TYPE,
    )
```

The file that comes out, byte for byte:

```text
﻿ID,Name,City
1,"Ana ""A"" Silva","Recife, PE"
2,João,Olinda
```

Notice what you did **not** write: the comma in `Recife, PE` went inside quotes,
the quotes around `"A"` were doubled, and the `﻿` up front is the BOM that
makes Excel read `João` correctly.

!!! info "This runs in all three modes"
    Generating bytes is pure Python — nothing here touches the browser. `to_csv`
    and `to_xlsx` behave identically in Mode A (WASM), Mode B (server) and Mode C
    (transpile). Only the delivery, `file.save`, is a native capability.

## `Column`: where it comes from, what it says, how it looks

A column carries three things:

```python
Column("created_at", "Created at", format=lambda v: v.strftime("%d/%m/%Y"))
#      ^ the field    ^ the header    ^ how the value becomes text (optional)
```

The field is read off the row **whether it is a dict or an object** — the same
column list serves the `dict` from your API and the `@dataclass` in your state:

```python
from dataclasses import dataclass

from tempestweb.export import Column, to_csv


@dataclass(frozen=True)
class User:
    """One row of the table."""

    id: int
    name: str


COLUMNS = [Column("id", "ID"), Column("name", "Name")]

print(to_csv([{"id": 1, "name": "Ana"}], COLUMNS, bom=False))
print(to_csv([User(1, "Ana")], COLUMNS, bom=False))
# b'ID,Name\r\n1,Ana\r\n' in both cases
```

!!! warning "A field that does not exist **raises**; it does not export blanks"
    `Column("nmae", "Name")` does not produce an empty column: it raises
    `ColumnFieldError`, naming the field that was missing and the ones that
    exist. A column of blanks is discovered by whoever opens the spreadsheet —
    much later, and much more expensively.

## Excel's separator in a non-English locale

!!! danger "Comma + Excel in pt-BR = everything in one column"
    Excel uses the **system list separator**. On a Windows configured in
    Portuguese that is `;` — and a comma-separated file opens with every column
    stacked into one. The BOM does not fix this: they are different problems.

    ```python
    to_csv(rows, COLUMNS, delimiter=";")   # opens correctly in a pt-BR Excel
    ```

    If the destination is another system (an importer, a script, a
    `pandas.read_csv`), keep the comma — the default, and what RFC 4180 says.

## XLSX: the date is the detail that matters

```python
from datetime import date

from tempestweb import native
from tempestweb.export import XLSX_MIME_TYPE, Column, to_xlsx

COLUMNS = [
    Column("name", "Name"),
    Column("created_at", "Created at"),
]

ROWS = [{"name": "Ana", "created_at": date(2026, 8, 27)}]


async def export() -> None:
    """Generate the workbook and hand it to the user."""
    await native.file.save(
        "users.xlsx",
        to_xlsx(ROWS, COLUMNS, sheet="Users"),
        mime_type=XLSX_MIME_TYPE,
    )
```

Open the file: the **Created at** column shows `27/08/2026`, and the cell is a
**real date** — it sorts, it filters by period, and you can do arithmetic on it.

??? info "Technical details — why this is hard"
    Excel has **no date type**. A date cell is a **number** — days since
    1899-12-30 — that looks like a date because of a *number format* stored
    separately, in `styles.xml`.

    Hand-rolled encoders get the number right and forget the format. The result
    is a valid workbook showing `46265` where the reader expected a date, and the
    bug only surfaces when somebody opens the file.

    That is why `tempestweb.export` ships a `styles.xml` with two `numFmt`
    entries (`dd/mm/yyyy` and `dd/mm/yyyy hh:mm`), and why the repo's test
    **opens the workbook back up** — unzips it, resolves the relationships, and
    asserts the cell is a date rather than a number that looks like one.

    The 1899-12-30 epoch, rather than 1900-01-01, absorbs Excel's deliberate bug
    of treating 1900 as a leap year — kept since Lotus 1-2-3.

The types the workbook understands without being asked:

| Python value | Excel cell |
| --- | --- |
| `str` | text |
| `int`, `float`, `Decimal` | number |
| `bool` | boolean (`TRUE`/`FALSE`), not the number 1 |
| `date` | date, formatted `dd/mm/yyyy` |
| `datetime` | date and time, formatted `dd/mm/yyyy hh:mm` |
| `None` | empty cell |

!!! note "Passing `format=` turns the cell into text"
    `Column("created_at", "Created at", format=lambda v: v.strftime("%d/%m/%Y"))`
    produces a **string**, and strings become text cells — which do not sort like
    dates. For XLSX, let the date through raw and let the number format do the
    work. `format=` is for CSV, or for when you actually want text.

## Sheet names Excel refuses

```python
to_xlsx(rows, COLUMNS, sheet="Sales/2026")   # SheetNameError
```

Excel caps sheet names at 31 characters and forbids `[ ] : * ? / \`, a leading or
trailing apostrophe, and the reserved name `History`. A workbook carrying an
invalid name opens as "unreadable content", with no hint about which part is at
fault — so `to_xlsx` refuses up front, naming the reason.

## Zero dependencies

An XLSX is a zip of XMLs, and the subset an export needs is small: one worksheet,
a header row, and cells typed as text, number, boolean and date. `zipfile` and
`xml.etree` from the standard library cover all of it.

!!! info "Why not `openpyxl`"
    That library's surface is enormous next to the handful of parts used here,
    and in a published package its bounds propagate to **every** tempestweb
    consumer. The project's rule is to implement before depending when the
    library's value is small relative to what it constrains — and this is that
    case.

## Recap

- `Column(field, header, format=...)` says where it comes from, what shows, and
  how.
- `to_csv(rows, columns)` returns **bytes** with the BOM on by default; use
  `delimiter=";"` when the destination is Excel in a non-English locale.
- `to_xlsx(rows, columns, sheet=...)` returns **bytes** of a real workbook, with
  dates that are dates.
- Both are pure Python: they run in all three modes and install nothing.
- Deliver with
  [`native.file.save(name, data, mime_type=...)`](native-reference.md).
- A missing field and an invalid sheet name **raise** — instead of exporting
  something silently wrong.
