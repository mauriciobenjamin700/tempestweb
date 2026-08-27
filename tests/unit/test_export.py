"""CSV and XLSX generation: the classic encoder mistakes, fixed by a test each.

The CSV cases are the three things a hand-rolled ``",".join(...)`` gets wrong —
a separator inside a field, a quote inside the text, the missing BOM — plus the
line break inside a quoted field, which is the fourth.

The XLSX cases open the workbook back up: unzip it, parse every part, resolve
the relationships, and assert the cell *types*. A file that merely looks like a
spreadsheet passes none of them — in particular ``test_date_cell_is_a_date``,
because a date written without its ``numFmt`` is a valid workbook that shows
``46265`` where the reader expects ``27/08/2026``.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from xml.etree import ElementTree

import pytest

from tempestweb.export import (
    BOM,
    CSV_MIME_TYPE,
    XLSX_MIME_TYPE,
    Column,
    ColumnFieldError,
    ExportError,
    SheetNameError,
    to_csv,
    to_xlsx,
)
from tempestweb.export.xlsx_writer import (
    EXCEL_EPOCH,
    STYLE_DATE,
    STYLE_DATETIME,
    STYLE_HEADER,
    _ref,
)

MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

COLUMNS = [Column("name", "Nome"), Column("city", "Cidade")]


@dataclass(frozen=True)
class Person:
    name: str
    city: str


def _parts(data: bytes) -> dict[str, bytes]:
    """Unzip a workbook into ``{part name: bytes}``."""
    with zipfile.ZipFile(BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def _sheet(data: bytes) -> ElementTree.Element:
    """Parse the single worksheet out of a workbook."""
    return ElementTree.fromstring(_parts(data)["xl/worksheets/sheet1.xml"])


def _cells(data: bytes) -> dict[str, ElementTree.Element]:
    """Map every cell reference in the worksheet to its ``<c>`` element."""
    sheet = _sheet(data)
    return {
        cell.attrib["r"]: cell
        for row in sheet.iter(f"{MAIN}row")
        for cell in row.iter(f"{MAIN}c")
    }


def _text_of(cell: ElementTree.Element) -> str | None:
    """Read an inline-string cell's text."""
    node = cell.find(f"{MAIN}is/{MAIN}t")
    return None if node is None else node.text


def _value_of(cell: ElementTree.Element) -> str | None:
    """Read a ``<v>`` cell's raw value."""
    node = cell.find(f"{MAIN}v")
    return None if node is None else node.text


# --------------------------------------------------------------------------
# CSV — the classic mistakes
# --------------------------------------------------------------------------


def test_separator_inside_a_field_is_quoted() -> None:
    rows = [{"name": "Ana", "city": "Recife, PE"}]
    assert to_csv(rows, COLUMNS, bom=False) == (b'Nome,Cidade\r\nAna,"Recife, PE"\r\n')


def test_quote_inside_the_text_is_doubled() -> None:
    rows = [{"name": 'Ana "A" Silva', "city": "Recife"}]
    assert to_csv(rows, COLUMNS, bom=False) == (
        b'Nome,Cidade\r\n"Ana ""A"" Silva",Recife\r\n'
    )


def test_line_break_inside_a_field_is_quoted_and_survives() -> None:
    rows = [{"name": "Ana\nSilva", "city": "Recife"}]
    data = to_csv(rows, COLUMNS, bom=False)
    assert data == b'Nome,Cidade\r\n"Ana\nSilva",Recife\r\n'
    assert data.count(b"\r\n") == 2


def test_bom_is_present_by_default_and_absent_on_request() -> None:
    rows = [{"name": "João", "city": "Recife"}]
    with_bom = to_csv(rows, COLUMNS)
    without = to_csv(rows, COLUMNS, bom=False)

    assert with_bom.startswith(b"\xef\xbb\xbf")
    assert not without.startswith(b"\xef\xbb\xbf")
    assert with_bom == BOM.encode("utf-8") + without
    assert "João".encode() in without


def test_semicolon_delimiter_for_excel_pt_br() -> None:
    rows = [{"name": "Ana", "city": "Recife, PE"}]
    assert to_csv(rows, COLUMNS, bom=False, delimiter=";") == (
        b"Nome;Cidade\r\nAna;Recife, PE\r\n"
    )


def test_header_can_be_omitted() -> None:
    rows = [{"name": "Ana", "city": "Recife"}]
    assert to_csv(rows, COLUMNS, bom=False, header=False) == b"Ana,Recife\r\n"


def test_none_becomes_an_empty_field() -> None:
    rows = [{"name": None, "city": "Recife"}]
    assert to_csv(rows, COLUMNS, bom=False) == b"Nome,Cidade\r\n,Recife\r\n"


def test_dates_default_to_iso_and_format_overrides_it() -> None:
    rows = [{"created_at": date(2026, 8, 27)}]
    plain = [Column("created_at", "Criado em")]
    formatted = [
        Column("created_at", "Criado em", format=lambda v: v.strftime("%d/%m/%Y"))
    ]

    assert to_csv(rows, plain, bom=False) == b"Criado em\r\n2026-08-27\r\n"
    assert to_csv(rows, formatted, bom=False) == b"Criado em\r\n27/08/2026\r\n"


def test_decimal_keeps_its_scale_instead_of_going_exponential() -> None:
    rows = [{"total": Decimal("0.00000001")}]
    columns = [Column("total", "Total")]
    assert to_csv(rows, columns, bom=False) == b"Total\r\n0.00000001\r\n"


def test_empty_rows_still_produce_the_header() -> None:
    assert to_csv([], COLUMNS, bom=False) == b"Nome,Cidade\r\n"


def test_a_generator_of_rows_works() -> None:
    rows = ({"name": f"P{i}", "city": "Recife"} for i in range(2))
    assert to_csv(rows, COLUMNS, bom=False) == (
        b"Nome,Cidade\r\nP0,Recife\r\nP1,Recife\r\n"
    )


def test_csv_rejects_no_columns_and_a_multi_character_delimiter() -> None:
    with pytest.raises(ExportError, match="at least one column"):
        to_csv([], [])
    with pytest.raises(ExportError, match="exactly one character"):
        to_csv([], COLUMNS, delimiter="||")


# --------------------------------------------------------------------------
# Columns — a typo must not export a column of blanks
# --------------------------------------------------------------------------


def test_missing_mapping_key_raises_and_names_what_is_available() -> None:
    with pytest.raises(ColumnFieldError) as caught:
        to_csv([{"name": "Ana"}], [Column("nmae", "Nome")])
    assert "'nmae'" in str(caught.value)
    assert "name" in str(caught.value)


def test_missing_attribute_raises_and_names_the_type() -> None:
    with pytest.raises(ColumnFieldError) as caught:
        to_csv([Person("Ana", "Recife")], [Column("nmae", "Nome")])
    assert "Person" in str(caught.value)
    assert "name" in str(caught.value)


def test_objects_and_mappings_share_one_column_spec() -> None:
    expected = b"Nome,Cidade\r\nAna,Recife\r\n"
    assert to_csv([{"name": "Ana", "city": "Recife"}], COLUMNS, bom=False) == expected
    assert to_csv([Person("Ana", "Recife")], COLUMNS, bom=False) == expected


def test_a_none_value_is_not_a_missing_field() -> None:
    assert to_csv([{"name": None, "city": "R"}], COLUMNS, bom=False).endswith(b",R\r\n")


# --------------------------------------------------------------------------
# XLSX — opened back up, not just generated
# --------------------------------------------------------------------------


def test_workbook_is_a_zip_with_every_part_declared() -> None:
    data = to_xlsx([{"name": "Ana", "city": "Recife"}], COLUMNS)
    parts = _parts(data)

    assert data[:2] == b"PK"
    assert set(parts) == {
        "[Content_Types].xml",
        "_rels/.rels",
        "xl/workbook.xml",
        "xl/_rels/workbook.xml.rels",
        "xl/styles.xml",
        "xl/worksheets/sheet1.xml",
    }
    for name, payload in parts.items():
        try:
            ElementTree.fromstring(payload)
        except ElementTree.ParseError as exc:
            pytest.fail(f"{name} is not well-formed XML: {exc}")


def test_every_relationship_target_resolves_to_a_real_part() -> None:
    data = to_xlsx([{"name": "Ana", "city": "Recife"}], COLUMNS)
    parts = _parts(data)
    namespace = "{http://schemas.openxmlformats.org/package/2006/relationships}"

    for source, base in (("_rels/.rels", ""), ("xl/_rels/workbook.xml.rels", "xl/")):
        root = ElementTree.fromstring(parts[source])
        targets = [
            base + element.attrib["Target"]
            for element in root.iter(f"{namespace}Relationship")
        ]
        assert targets, f"{source} declares no relationship"
        for target in targets:
            assert target in parts, f"{source} points at missing part {target}"


def test_every_override_in_content_types_names_a_real_part() -> None:
    data = to_xlsx([{"name": "Ana", "city": "Recife"}], COLUMNS)
    parts = _parts(data)
    namespace = "{http://schemas.openxmlformats.org/package/2006/content-types}"
    root = ElementTree.fromstring(parts["[Content_Types].xml"])

    for element in root.iter(f"{namespace}Override"):
        assert element.attrib["PartName"].lstrip("/") in parts


def test_header_row_is_written_in_the_bold_style() -> None:
    data = to_xlsx([{"name": "Ana", "city": "Recife"}], COLUMNS)
    cells = _cells(data)

    assert _text_of(cells["A1"]) == "Nome"
    assert _text_of(cells["B1"]) == "Cidade"
    assert cells["A1"].attrib["s"] == str(STYLE_HEADER)


def test_date_cell_is_a_date() -> None:
    """The whole point: serial number *and* the number format that displays it.

    Without the ``s`` attribute the cell is a valid number cell showing 46265;
    without the ``numFmt`` behind that style it is the same thing wearing a
    different index. Both are asserted here.
    """
    data = to_xlsx(
        [{"created_at": date(2026, 8, 27)}], [Column("created_at", "Criado em")]
    )
    cell = _cells(data)["A2"]

    assert "t" not in cell.attrib, "a date cell is a number cell, not a string"
    assert cell.attrib["s"] == str(STYLE_DATE)
    assert _value_of(cell) == str((date(2026, 8, 27) - EXCEL_EPOCH).days)

    styles = ElementTree.fromstring(_parts(data)["xl/styles.xml"])
    cell_xfs = styles.find(f"{MAIN}cellXfs")
    assert cell_xfs is not None, "styles.xml declares no cellXfs"
    formats = list(cell_xfs)
    number_format_id = formats[STYLE_DATE].attrib["numFmtId"]
    codes = {
        element.attrib["numFmtId"]: element.attrib["formatCode"]
        for element in styles.iter(f"{MAIN}numFmt")
    }

    assert formats, "styles.xml declares no cell format"
    assert number_format_id in codes
    assert codes[number_format_id] == "dd/mm/yyyy"


def test_datetime_cell_carries_the_time_of_day_in_the_fraction() -> None:
    data = to_xlsx([{"at": datetime(2026, 8, 27, 12, 0, 0)}], [Column("at", "Quando")])
    cell = _cells(data)["A2"]
    whole = (date(2026, 8, 27) - EXCEL_EPOCH).days

    assert cell.attrib["s"] == str(STYLE_DATETIME)
    assert float(_value_of(cell) or "0") == pytest.approx(whole + 0.5)


def test_a_date_before_1900_is_refused_instead_of_silently_wrong() -> None:
    with pytest.raises(ExportError, match="1900-01-01"):
        to_xlsx([{"d": date(1899, 12, 31)}], [Column("d", "Data")])


def test_booleans_stay_booleans_and_do_not_become_the_number_one() -> None:
    data = to_xlsx(
        [{"active": True, "banned": False}],
        [
            Column("active", "Ativo"),
            Column("banned", "Banido"),
        ],
    )
    cells = _cells(data)

    assert cells["A2"].attrib["t"] == "b"
    assert _value_of(cells["A2"]) == "1"
    assert _value_of(cells["B2"]) == "0"


def test_numbers_are_number_cells_and_none_is_an_empty_cell() -> None:
    data = to_xlsx(
        [{"n": 42, "f": 1.5, "d": Decimal("3.25"), "z": None}],
        [
            Column("n", "Inteiro"),
            Column("f", "Float"),
            Column("d", "Decimal"),
            Column("z", "Vazio"),
        ],
    )
    cells = _cells(data)

    assert "t" not in cells["A2"].attrib
    assert _value_of(cells["A2"]) == "42"
    assert _value_of(cells["B2"]) == "1.5"
    assert _value_of(cells["C2"]) == "3.25"
    assert len(cells["D2"]) == 0


def test_xml_special_characters_are_escaped_not_broken() -> None:
    data = to_xlsx(
        [{"name": 'A & B <tag> "quoted"', "city": "R"}],
        COLUMNS,
    )
    assert _text_of(_cells(data)["A2"]) == 'A & B <tag> "quoted"'


def test_a_nul_byte_is_dropped_so_the_workbook_still_opens() -> None:
    data = to_xlsx([{"name": "Ana\x00Silva", "city": "R"}], COLUMNS)
    assert _text_of(_cells(data)["A2"]) == "AnaSilva"


def test_leading_whitespace_is_preserved_explicitly() -> None:
    data = to_xlsx([{"name": "  Ana", "city": "R"}], COLUMNS)
    cell = _cells(data)["A2"]
    node = cell.find(f"{MAIN}is/{MAIN}t")

    assert node is not None
    assert node.text == "  Ana"
    assert node.attrib.get("{http://www.w3.org/XML/1998/namespace}space") == "preserve"


def test_sheet_name_reaches_the_workbook_part() -> None:
    data = to_xlsx([{"name": "Ana", "city": "R"}], COLUMNS, sheet="Usuários")
    workbook = ElementTree.fromstring(_parts(data)["xl/workbook.xml"])
    sheet = workbook.find(f"{MAIN}sheets/{MAIN}sheet")

    assert sheet is not None
    assert sheet.attrib["name"] == "Usuários"


@pytest.mark.parametrize(
    "name",
    ["", "a" * 32, "Vendas/2026", "Vendas[2026]", "Um:Dois", "'Ana", "Ana'", "History"],
)
def test_sheet_names_excel_refuses_are_refused_here(name: str) -> None:
    with pytest.raises(SheetNameError):
        to_xlsx([{"name": "Ana", "city": "R"}], COLUMNS, sheet=name)


def test_xlsx_rejects_no_columns() -> None:
    with pytest.raises(ExportError, match="at least one column"):
        to_xlsx([], [])


def test_the_same_rows_always_produce_the_same_bytes() -> None:
    rows = [{"name": "Ana", "city": "Recife"}]
    assert to_xlsx(rows, COLUMNS) == to_xlsx(list(rows), COLUMNS)


def test_more_than_26_columns_keep_addressing_cells_correctly() -> None:
    columns = [Column(f"c{i}", f"H{i}") for i in range(28)]
    row = {f"c{i}": i for i in range(28)}
    cells = _cells(to_xlsx([row], columns))

    assert _text_of(cells["Z1"]) == "H25"
    assert _text_of(cells["AA1"]) == "H26"
    assert _value_of(cells["AB2"]) == "27"


@pytest.mark.parametrize(
    ("index", "expected"),
    [(0, "A1"), (25, "Z1"), (26, "AA1"), (51, "AZ1"), (52, "BA1"), (701, "ZZ1")],
)
def test_column_references_follow_the_spreadsheet_alphabet(
    index: int, expected: str
) -> None:
    assert _ref(index, 1) == expected


def test_mime_types_are_the_ones_file_save_expects() -> None:
    assert CSV_MIME_TYPE == "text/csv"
    assert XLSX_MIME_TYPE.endswith("spreadsheetml.sheet")
