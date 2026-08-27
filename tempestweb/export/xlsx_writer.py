"""XLSX generation from the standard library — no dependency, no drift.

An ``.xlsx`` file is a ZIP of XML parts, and the subset an export needs is
small: one worksheet, a header row, and cells typed as text, number, boolean or
date. :mod:`zipfile` and :mod:`xml.etree.ElementTree` cover all of it, which is
why this ships instead of pulling ``openpyxl`` — that library's surface is
enormous next to the handful of parts used here, and in a published package its
bounds would propagate to every consumer.

The part worth reading is :func:`_cell`. Excel has no date type: a date cell is
a **number** — days since 1899-12-30 — displayed through a number format, and a
cell missing that format shows ``46265`` instead of ``27/08/2026``. Hand-rolled
writers get the number right and forget the format, which is why this module
carries a ``styles.xml`` with two ``numFmt`` entries and why the tests open the
workbook back up and assert the cell is a date, not a number that looks like one.

Example:
    >>> from datetime import date
    >>> rows = [{"id": 1, "created_at": date(2026, 8, 27)}]
    >>> columns = [Column("id", "ID"), Column("created_at", "Criado em")]
    >>> to_xlsx(rows, columns, sheet="Usuarios")[:2]
    b'PK'

The output is :class:`bytes`, ready for
:func:`tempestweb.native.file.save` — this module never touches the browser.
"""

from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from decimal import Decimal
from xml.etree import ElementTree

from tempestweb.export.columns import Column
from tempestweb.export.errors import ExportError, SheetNameError

__all__ = ["to_xlsx"]

#: Excel's day zero. The two-day offset from 1900-01-01 absorbs Excel's
#: deliberate 1900-02-29 bug, kept for Lotus 1-2-3 compatibility.
EXCEL_EPOCH = date(1899, 12, 30)

#: The earliest date the serial can represent. Below it Excel stores text.
EXCEL_MIN_DATE = date(1900, 1, 1)

#: Style indices declared by :data:`_STYLES`, in ``cellXfs`` order.
STYLE_DEFAULT = 0
STYLE_DATE = 1
STYLE_DATETIME = 2
STYLE_HEADER = 3

#: Excel caps sheet names at 31 characters.
SHEET_NAME_MAX = 31

#: Characters Excel refuses inside a sheet name.
SHEET_NAME_FORBIDDEN = frozenset("[]:*?/\\")

#: Characters XML 1.0 cannot carry at all — not even escaped. A NUL smuggled in
#: from a database column makes the whole workbook unopenable, so they are
#: dropped rather than encoded.
ILLEGAL_XML = re.compile(
    "[^\u0009\u000a\u000d\u0020-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]"
)

#: A fixed ZIP timestamp, so the same rows always produce the same bytes. Golden
#: tests and content hashing both depend on it.
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_OPC_NS = "http://schemas.openxmlformats.org/package/2006"
_RELS_TYPE = "application/vnd.openxmlformats-package.relationships+xml"
_SML_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml"

_CONTENT_TYPES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="{_OPC_NS}/content-types">
<Default Extension="rels" ContentType="{_RELS_TYPE}"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="{_SML_TYPE}.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="{_SML_TYPE}.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="{_SML_TYPE}.styles+xml"/>
</Types>"""

_ROOT_RELS = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{_OPC_NS}/relationships">
<Relationship Id="rId1" Type="{_REL_NS}/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

_WORKBOOK_RELS = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{_OPC_NS}/relationships">
<Relationship Id="rId1" Type="{_REL_NS}/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="{_REL_NS}/styles" Target="styles.xml"/>
</Relationships>"""

_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="2">
<numFmt numFmtId="164" formatCode="dd/mm/yyyy"/>
<numFmt numFmtId="165" formatCode="dd/mm/yyyy\\ hh:mm"/>
</numFmts>
<fonts count="2">
<font><sz val="11"/><name val="Calibri"/></font>
<font><b/><sz val="11"/><name val="Calibri"/></font>
</fonts>
<fills count="2">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
</fills>
<borders count="1">
<border><left/><right/><top/><bottom/><diagonal/></border>
</borders>
<cellStyleXfs count="1">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
</cellStyleXfs>
<cellXfs count="4">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""


def to_xlsx(
    rows: Iterable[object],
    columns: Sequence[Column],
    *,
    sheet: str = "Planilha1",
    header: bool = True,
) -> bytes:
    """Render rows as a single-worksheet XLSX workbook.

    Args:
        rows: The rows to write, in order. Consumed once, so a generator works.
        columns: The columns to write, in order.
        sheet: The worksheet name shown on the tab.
        header: Whether to write the header row, in bold.

    Returns:
        The workbook bytes, ready to hand to
        :func:`tempestweb.native.file.save` with the
        ``application/vnd.openxmlformats-officedocument.spreadsheetml.sheet``
        MIME type.

    Raises:
        ExportError: If ``columns`` is empty, or a date falls before
            :data:`EXCEL_MIN_DATE`, which the serial cannot represent.
        SheetNameError: If ``sheet`` is one Excel refuses to open.
        ColumnFieldError: If a column names a field a row does not have.
    """
    if not columns:
        raise ExportError("to_xlsx needs at least one column")
    _check_sheet_name(sheet)

    parts = (
        ("[Content_Types].xml", _CONTENT_TYPES),
        ("_rels/.rels", _ROOT_RELS),
        ("xl/workbook.xml", _workbook_xml(sheet)),
        ("xl/_rels/workbook.xml.rels", _WORKBOOK_RELS),
        ("xl/styles.xml", _STYLES),
        ("xl/worksheets/sheet1.xml", _sheet_xml(rows, columns, header=header)),
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in parts:
            info = zipfile.ZipInfo(name, date_time=ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, payload)
    return buffer.getvalue()


def _check_sheet_name(sheet: str) -> None:
    r"""Reject a sheet name Excel would refuse to open.

    Args:
        sheet: The proposed worksheet name.

    Raises:
        SheetNameError: If the name is empty, longer than 31 characters,
            contains ``[ ] : * ? / \``, starts or ends with an apostrophe, or is
            the reserved name ``History``.
    """
    if not sheet:
        raise SheetNameError("sheet name cannot be empty")
    if len(sheet) > SHEET_NAME_MAX:
        raise SheetNameError(
            f"sheet name is {len(sheet)} characters; Excel caps it at "
            f"{SHEET_NAME_MAX}: {sheet!r}"
        )
    forbidden = sorted(set(sheet) & SHEET_NAME_FORBIDDEN)
    if forbidden:
        raise SheetNameError(
            f"sheet name {sheet!r} contains characters Excel forbids: "
            + " ".join(forbidden)
        )
    if sheet.startswith("'") or sheet.endswith("'"):
        raise SheetNameError(
            f"sheet name {sheet!r} cannot start or end with an apostrophe"
        )
    if sheet.lower() == "history":
        raise SheetNameError(
            "'History' is reserved by Excel and cannot be a sheet name"
        )


def _workbook_xml(sheet: str) -> str:
    """Render the workbook part naming the single worksheet.

    Args:
        sheet: The worksheet name, already validated.

    Returns:
        The ``xl/workbook.xml`` payload.
    """
    root = ElementTree.Element("workbook", {"xmlns": _MAIN_NS, "xmlns:r": _REL_NS})
    sheets = ElementTree.SubElement(root, "sheets")
    ElementTree.SubElement(
        sheets, "sheet", {"name": _clean(sheet), "sheetId": "1", "r:id": "rId1"}
    )
    return _serialize(root)


def _sheet_xml(
    rows: Iterable[object],
    columns: Sequence[Column],
    *,
    header: bool,
) -> str:
    """Render the worksheet part.

    Args:
        rows: The rows to write.
        columns: The columns to write.
        header: Whether the first row is the bold header.

    Returns:
        The ``xl/worksheets/sheet1.xml`` payload.

    Raises:
        ExportError: If a date falls before :data:`EXCEL_MIN_DATE`.
        ColumnFieldError: If a column names a field a row does not have.
    """
    root = ElementTree.Element("worksheet", {"xmlns": _MAIN_NS})
    data = ElementTree.SubElement(root, "sheetData")

    number = 1
    if header:
        element = ElementTree.SubElement(data, "row", {"r": "1"})
        for index, column in enumerate(columns):
            _text_cell(element, _ref(index, 1), column.header, STYLE_HEADER)
        number = 2

    for row in rows:
        element = ElementTree.SubElement(data, "row", {"r": str(number)})
        for index, column in enumerate(columns):
            _cell(element, _ref(index, number), column.value_of(row))
        number += 1

    return _serialize(root)


def _cell(row: ElementTree.Element, ref: str, value: object) -> None:
    """Append one typed cell to a row.

    ``bool`` is checked before ``int`` on purpose: in Python ``True`` *is* an
    ``int``, and writing it as the number 1 loses the boolean rendering Excel
    gives a real ``t="b"`` cell.

    Args:
        row: The ``<row>`` element to append to.
        ref: The cell reference, such as ``"B7"``.
        value: The value to store.

    Raises:
        ExportError: If ``value`` is a date before :data:`EXCEL_MIN_DATE`.
    """
    if value is None:
        ElementTree.SubElement(row, "c", {"r": ref})
        return
    if isinstance(value, bool):
        cell = ElementTree.SubElement(row, "c", {"r": ref, "t": "b"})
        ElementTree.SubElement(cell, "v").text = "1" if value else "0"
        return
    if isinstance(value, datetime):
        _serial_cell(row, ref, value, STYLE_DATETIME)
        return
    if isinstance(value, date):
        _serial_cell(row, ref, value, STYLE_DATE)
        return
    if isinstance(value, int | float | Decimal):
        cell = ElementTree.SubElement(row, "c", {"r": ref})
        ElementTree.SubElement(cell, "v").text = _number(value)
        return
    _text_cell(row, ref, str(value), STYLE_DEFAULT)


def _serial_cell(
    row: ElementTree.Element,
    ref: str,
    value: date,
    style: int,
) -> None:
    """Append a date cell: a serial number wearing a date number format.

    Args:
        row: The ``<row>`` element to append to.
        ref: The cell reference.
        value: The date or datetime to store.
        style: :data:`STYLE_DATE` or :data:`STYLE_DATETIME`.

    Raises:
        ExportError: If the date precedes :data:`EXCEL_MIN_DATE`.
    """
    cell = ElementTree.SubElement(row, "c", {"r": ref, "s": str(style)})
    ElementTree.SubElement(cell, "v").text = _number(_excel_serial(value))


def _text_cell(row: ElementTree.Element, ref: str, text: str, style: int) -> None:
    """Append an inline-string cell.

    Inline strings keep the workbook to six parts: the alternative, a shared
    string table, buys deduplication this module has no use for.

    Args:
        row: The ``<row>`` element to append to.
        ref: The cell reference.
        text: The text to store.
        style: The ``cellXfs`` index to apply.
    """
    attributes = {"r": ref, "t": "inlineStr"}
    if style != STYLE_DEFAULT:
        attributes["s"] = str(style)
    cell = ElementTree.SubElement(row, "c", attributes)
    string = ElementTree.SubElement(cell, "is")
    node = ElementTree.SubElement(string, "t")
    cleaned = _clean(text)
    if cleaned != cleaned.strip():
        node.set("xml:space", "preserve")
    node.text = cleaned


def _excel_serial(value: date) -> float:
    """Convert a date or datetime to Excel's serial number.

    Args:
        value: The date or datetime to convert.

    Returns:
        Days since :data:`EXCEL_EPOCH`, with the time of day as the fraction.

    Raises:
        ExportError: If the date precedes :data:`EXCEL_MIN_DATE`, which the
            serial cannot represent — Excel stores such dates as text, and
            silently writing a negative serial produces a cell showing
            ``########``.
    """
    day = value.date() if isinstance(value, datetime) else value
    if day < EXCEL_MIN_DATE:
        raise ExportError(
            f"{day.isoformat()} precedes {EXCEL_MIN_DATE.isoformat()}, which the "
            "XLSX date serial cannot represent; format the column to text with "
            "Column(..., format=...) to export it"
        )
    serial = float((day - EXCEL_EPOCH).days)
    if isinstance(value, datetime):
        seconds = (
            value.hour * 3600
            + value.minute * 60
            + value.second
            + value.microsecond / 1_000_000
        )
        serial += seconds / 86_400
    return serial


def _number(value: int | float | Decimal) -> str:
    """Render a number the way the XLSX schema expects.

    Args:
        value: The number to render.

    Returns:
        A decimal string with no exponent and no trailing ``.0``.
    """
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    return str(value)


def _ref(column_index: int, row_number: int) -> str:
    """Build an A1-style cell reference.

    Args:
        column_index: The zero-based column index.
        row_number: The one-based row number.

    Returns:
        The reference, such as ``"AA3"``.
    """
    letters = ""
    remaining = column_index + 1
    while remaining:
        remaining, offset = divmod(remaining - 1, 26)
        letters = chr(ord("A") + offset) + letters
    return f"{letters}{row_number}"


def _clean(text: str) -> str:
    """Drop the characters XML 1.0 cannot carry.

    Args:
        text: The text to sanitize.

    Returns:
        The text with illegal control characters removed.
    """
    return ILLEGAL_XML.sub("", text)


def _serialize(root: ElementTree.Element) -> str:
    """Serialize a part, XML declaration included.

    Args:
        root: The part's root element.

    Returns:
        The complete XML document.
    """
    body = ElementTree.tostring(root, encoding="unicode")
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n{body}'
