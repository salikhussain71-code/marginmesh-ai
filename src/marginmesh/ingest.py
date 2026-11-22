"""Read CSV / XLSX documents into validated, source-tagged records."""

from __future__ import annotations

import csv
import re
import zipfile
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from marginmesh.models import CostLine, LineItem

MAX_ROWS = 100_000
SUPPORTED_SUFFIXES = {".csv", ".xlsx", ".xlsm"}

LINE_ALIASES = {
    "sku": {"sku", "item", "item_code", "item_no", "article", "code", "style"},
    "description": {"description", "desc", "item_description", "details"},
    "quantity": {"quantity", "qty", "units", "pcs"},
    "unit_price": {"unit_price", "price", "rate", "unit_cost", "price_per_unit"},
    "currency": {"currency", "ccy", "curr"},
}
COST_ALIASES = {
    "category": {"category", "cost_category", "cost_head", "head", "cost_item"},
    "planned": {"planned_cost", "planned", "budget", "estimated", "estimate", "standard_cost"},
    "actual": {"actual_cost", "actual"},
}


class IngestError(ValueError):
    """Raised when an input document is missing, malformed or invalid."""


def _norm_header(value: object) -> str:
    return re.sub(r"[\s\-./]+", "_", str(value).strip().lower()).strip("_")


def _is_blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _table_from_iter(
    numbered_rows: Iterable[tuple[int, Iterable[Any]]], name: str
) -> tuple[list[str], list[tuple[int, dict[str, Any]]]]:
    headers: list[str] | None = None
    rows: list[tuple[int, dict[str, Any]]] = []
    for number, cells in numbered_rows:
        cells = list(cells)
        if all(_is_blank(c) for c in cells):
            continue
        if headers is None:
            headers = [_norm_header(c) if not _is_blank(c) else "" for c in cells]
            named = [h for h in headers if h]
            if len(named) != len(set(named)):
                raise IngestError(f"{name}: duplicate column names in header row")
            continue
        if len(rows) >= MAX_ROWS:
            raise IngestError(f"{name}: more than {MAX_ROWS} rows")
        record = {h: cells[i] if i < len(cells) else None for i, h in enumerate(headers) if h}
        rows.append((number, record))
    if headers is None:
        raise IngestError(f"{name}: file is empty")
    return [h for h in headers if h], rows


def read_table(path: str | Path) -> tuple[list[str], list[tuple[int, dict[str, Any]]]]:
    """Return (headers, [(row_number, record)]) for a CSV or XLSX file."""
    p = Path(path)
    if not p.is_file():
        raise IngestError(f"File not found: {p}")
    suffix = p.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise IngestError(f"{p.name}: unsupported file type '{suffix}' (use .csv or .xlsx)")
    if suffix == ".csv":
        try:
            with p.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.reader(handle)
                numbered = [(reader.line_num, row) for row in reader]
        except (UnicodeDecodeError, csv.Error) as exc:
            raise IngestError(f"{p.name}: cannot read CSV ({exc})") from exc
        return _table_from_iter(numbered, p.name)

    from openpyxl import load_workbook

    try:
        workbook = load_workbook(p, read_only=True, data_only=True)
    except (zipfile.BadZipFile, KeyError, OSError, ValueError) as exc:
        raise IngestError(f"{p.name}: cannot read Excel file ({exc})") from exc
    try:
        sheet = workbook.worksheets[0]
        numbered = list(enumerate(sheet.iter_rows(values_only=True), start=1))
    finally:
        workbook.close()
    return _table_from_iter(numbered, p.name)


def to_decimal(value: object, label: str, where: str) -> Decimal:
    """Parse a number strictly. Accepts '1,200.50' and '$5.30'; rejects NaN/inf/text."""
    if _is_blank(value) or isinstance(value, bool):
        raise IngestError(f"{where}: '{label}' is missing or not a number")
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, (int, float)):
        number = Decimal(str(value))
    else:
        text = str(value).strip().replace(",", "").replace("$", "").replace(" ", "")
        try:
            number = Decimal(text)
        except InvalidOperation as exc:
            raise IngestError(f"{where}: '{label}' is not a number: {value!r}") from exc
    if not number.is_finite():
        raise IngestError(f"{where}: '{label}' is not a finite number")
    return number


def _resolve(headers: list[str], aliases: dict[str, set[str]], required: list[str], name: str):
    mapping: dict[str, str] = {}
    for canonical, names in aliases.items():
        for header in headers:
            if header in names:
                mapping[canonical] = header
                break
    missing = [c for c in required if c not in mapping]
    if missing:
        raise IngestError(
            f"{name}: missing required column(s): {', '.join(missing)}. "
            f"Found columns: {', '.join(headers) or 'none'}"
        )
    return mapping


def parse_line_items(path: str | Path, default_currency: str = "USD") -> list[LineItem]:
    """Parse a purchase order or supplier invoice into line items."""
    p = Path(path)
    headers, rows = read_table(p)
    cols = _resolve(headers, LINE_ALIASES, ["sku", "quantity", "unit_price"], p.name)
    items: list[LineItem] = []
    for number, record in rows:
        where = f"{p.name}:row {number}"
        sku = "" if _is_blank(record[cols["sku"]]) else str(record[cols["sku"]]).strip().upper()
        if not sku:
            raise IngestError(f"{where}: 'sku' is empty")
        quantity = to_decimal(record[cols["quantity"]], "quantity", where)
        price = to_decimal(record[cols["unit_price"]], "unit_price", where)
        if quantity < 0 or price < 0:
            raise IngestError(f"{where}: negative quantity or price (credit notes not supported)")
        currency = default_currency
        if "currency" in cols and not _is_blank(record[cols["currency"]]):
            currency = str(record[cols["currency"]]).strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise IngestError(f"{where}: invalid currency code {currency!r}")
        description = ""
        if "description" in cols and not _is_blank(record[cols["description"]]):
            description = str(record[cols["description"]]).strip()
        items.append(LineItem(sku, description, quantity, price, currency, where))
    if not items:
        raise IngestError(f"{p.name}: no data rows found")
    return items


def parse_costing(path: str | Path) -> list[CostLine]:
    """Parse a costing sheet (category, planned_cost, actual_cost)."""
    p = Path(path)
    headers, rows = read_table(p)
    cols = _resolve(headers, COST_ALIASES, ["category", "planned", "actual"], p.name)
    lines: list[CostLine] = []
    for number, record in rows:
        where = f"{p.name}:row {number}"
        if _is_blank(record[cols["category"]]):
            raise IngestError(f"{where}: 'category' is empty")
        planned = to_decimal(record[cols["planned"]], "planned_cost", where)
        actual = to_decimal(record[cols["actual"]], "actual_cost", where)
        if planned < 0 or actual < 0:
            raise IngestError(f"{where}: negative cost")
        lines.append(CostLine(str(record[cols["category"]]).strip(), planned, actual, where))
    if not lines:
        raise IngestError(f"{p.name}: no data rows found")
    return lines
