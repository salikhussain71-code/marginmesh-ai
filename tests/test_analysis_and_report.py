import csv
import io
import json
from decimal import Decimal

import pytest
from openpyxl import load_workbook

from marginmesh.analysis import OrderInfo, analyze_order
from marginmesh.models import CostLine
from marginmesh.report import (
    DISCLAIMER,
    build_report,
    render_csv,
    render_markdown,
    safe_cell,
    write_reports,
)


def build(make_item, sku="A"):
    order = OrderInfo("ORD-1", "USD", "Buyer", Decimal(1000), Decimal(980))
    costs = [CostLine("materials", Decimal(500), Decimal(560), "c:row 2")]
    return analyze_order(order, [make_item(sku, 100, "5")], [make_item(sku, 100, "5.30")], costs)


def test_order_id_validation():
    for bad in ["", "../etc", "a b", "x" * 65, "a/b"]:
        with pytest.raises(ValueError):
            OrderInfo(bad)
    with pytest.raises(ValueError):
        OrderInfo("ok", currency="usd")


def test_analysis_orders_findings_and_assigns_stable_ids(make_item):
    result = build(make_item)
    ids = [f.id for f in result.findings]
    assert ids == [f"ORD-1-F{n:03d}" for n in range(1, len(ids) + 1)]
    sev = [f.severity.value for f in result.findings]
    assert sev == sorted(sev, key=["INFO", "LOW", "MEDIUM", "HIGH"].index, reverse=True)
    assert result.reconciliation.po_total == Decimal(500)
    assert result.reconciliation.invoice_total == Decimal(530)
    assert result.reconciliation.flagged_over_po == Decimal(30)


def test_costing_without_revenue_is_rejected(make_item):
    with pytest.raises(ValueError, match="revenue"):
        analyze_order(
            OrderInfo("O"),
            [make_item("A", 1, 1)],
            [make_item("A", 1, 1)],
            [CostLine("x", Decimal(1), Decimal(1), "c")],
        )


def test_json_report_is_valid_and_amounts_are_strings(make_item):
    report = build_report(build(make_item), generated_at="2026-01-01T00:00:00+00:00")
    parsed = json.loads(json.dumps(report))
    assert parsed["meta"]["disclaimer"] == DISCLAIMER
    assert parsed["findings"][0]["difference"].replace(".", "").replace("-", "").isdigit()
    assert parsed["margin"]["margin_erosion"] == "60.00"


def test_markdown_contains_disclaimer_and_evidence(make_item):
    md = render_markdown(build_report(build(make_item)))
    assert "potential discrepancies" in md
    assert "Evidence:" in md
    assert "Margin erosion" in md


def test_report_without_costing_has_no_margin_section(make_item):
    result = analyze_order(OrderInfo("O"), [make_item("A", 1, 1)], [make_item("A", 1, 1)])
    report = build_report(result)
    assert report["margin"] is None
    assert "No discrepancies above tolerance" in render_markdown(report)


def test_csv_and_xlsx_neutralise_formula_injection(make_item):
    evil = '=HYPERLINK("http://x")'
    result = analyze_order(OrderInfo("O"), [make_item("A", 1, 1)], [make_item(evil, 1, 1)])
    report = build_report(result)
    rows = list(csv.DictReader(io.StringIO(render_csv(report))))
    assert rows[0]["sku"].startswith("'")
    assert safe_cell("+1") == "'+1"
    assert safe_cell("normal") == "normal"


def test_write_reports_creates_all_formats(make_item, tmp_path):
    paths = write_reports(build(make_item), tmp_path, generated_at="2026-01-01T00:00:00+00:00")
    names = sorted(p.name for p in paths)
    assert names == [
        "ORD-1_report.json",
        "ORD-1_report.md",
        "ORD-1_report.xlsx",
        "ORD-1_report_findings.csv",
    ]
    wb = load_workbook(tmp_path / "ORD-1_report.xlsx")
    assert wb.sheetnames == ["Summary", "Findings", "Cost variance"]
    with pytest.raises(ValueError, match="unknown format"):
        write_reports(build(make_item), tmp_path, ("pdf",))
