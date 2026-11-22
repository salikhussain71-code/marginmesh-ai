from decimal import Decimal

import pytest
from openpyxl import Workbook

from marginmesh.ingest import IngestError, parse_costing, parse_line_items, read_table, to_decimal


def write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


def test_parses_csv_with_aliases_and_formatted_numbers(tmp_path):
    p = write(
        tmp_path / "po.csv",
        'Item Code,Qty,Price,CCY\nabc-1,"1,000",$5.30,usd\n\n',
    )
    items = parse_line_items(p)
    assert len(items) == 1
    assert items[0].sku == "ABC-1"
    assert items[0].quantity == Decimal("1000")
    assert items[0].unit_price == Decimal("5.30")
    assert items[0].currency == "USD"
    assert items[0].source == "po.csv:row 2"


def test_default_currency_applies_when_column_missing(tmp_path):
    p = write(tmp_path / "po.csv", "sku,quantity,unit_price\nA,1,2\n")
    assert parse_line_items(p, "PKR")[0].currency == "PKR"


def test_xlsx_roundtrip_uses_decimal_from_float(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.append(["sku", "quantity", "unit_price"])
    ws.append(["A", 10, 0.1])
    path = tmp_path / "x.xlsx"
    wb.save(path)
    item = parse_line_items(path)[0]
    assert item.unit_price == Decimal("0.1")
    assert item.total == Decimal("1.0")


@pytest.mark.parametrize(
    "body, message",
    [
        ("sku,quantity\nA,1\n", "missing required column"),
        ("sku,quantity,unit_price\nA,abc,1\n", "not a number"),
        ("sku,quantity,unit_price\nA,-1,1\n", "negative"),
        ("sku,quantity,unit_price\n,1,1\n", "'sku' is empty"),
        ("sku,quantity,unit_price\nA,NaN,1\n", "finite"),
        ("sku,quantity,unit_price\nA,1,1,\n", None),
        ("sku,quantity,unit_price,currency\nA,1,1,EURO\n", "invalid currency"),
        ("sku,sku,quantity,unit_price\nA,A,1,1\n", "duplicate column"),
        ("sku,quantity,unit_price\n", "no data rows"),
        ("", "empty"),
    ],
)
def test_invalid_inputs_raise_clear_errors(tmp_path, body, message):
    p = write(tmp_path / "bad.csv", body)
    if message is None:
        parse_line_items(p)  # trailing empty cell is tolerated
        return
    with pytest.raises(IngestError, match=message):
        parse_line_items(p)


def test_error_message_names_file_and_row(tmp_path):
    p = write(tmp_path / "inv.csv", "sku,quantity,unit_price\nA,1,1\nB,x,1\n")
    with pytest.raises(IngestError, match=r"inv\.csv:row 3"):
        parse_line_items(p)


def test_unsupported_missing_and_corrupt_files(tmp_path):
    with pytest.raises(IngestError, match="not found"):
        read_table(tmp_path / "nope.csv")
    txt = write(tmp_path / "a.txt", "x")
    with pytest.raises(IngestError, match="unsupported"):
        read_table(txt)
    bad = tmp_path / "bad.xlsx"
    bad.write_bytes(b"this is not a zip file")
    with pytest.raises(IngestError, match="cannot read Excel"):
        read_table(bad)


def test_parse_costing(tmp_path):
    p = write(tmp_path / "c.csv", "Category,Planned,Actual\nFabric,100,110\n")
    line = parse_costing(p)[0]
    assert (line.category, line.planned, line.actual) == ("Fabric", 100, 110)


def test_to_decimal_rejects_bool_and_blank():
    with pytest.raises(IngestError):
        to_decimal(True, "x", "w")
    with pytest.raises(IngestError):
        to_decimal("  ", "x", "w")
