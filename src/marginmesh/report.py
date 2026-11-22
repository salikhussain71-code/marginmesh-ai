"""Render an AnalysisResult as JSON, Markdown, CSV or Excel."""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from marginmesh import __version__
from marginmesh.analysis import AnalysisResult
from marginmesh.models import money, plain_money

DISCLAIMER = (
    "Findings are potential discrepancies that require human review. They are not confirmed "
    "financial losses and are not accounting, tax or legal advice."
)
FORMATS = ("json", "md", "csv", "xlsx")
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value: object) -> object:
    """Neutralise spreadsheet formula injection in untrusted *text* values."""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def _pct(value: Decimal | None) -> str | None:
    return None if value is None else plain_money(value)


def build_report(result: AnalysisResult, generated_at: str | None = None) -> dict:
    """Build a JSON-serialisable report. All amounts are strings (no float rounding)."""
    stamp = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    order, rec, margin = result.order, result.reconciliation, result.margin
    report: dict = {
        "meta": {
            "tool": "marginmesh-ai",
            "version": __version__,
            "generated_at": stamp,
            "disclaimer": DISCLAIMER,
        },
        "order": {
            "order_id": order.order_id,
            "buyer": order.buyer,
            "currency": order.currency,
            "revenue": None if order.revenue is None else plain_money(order.revenue),
            "received": None if order.received is None else plain_money(order.received),
        },
        "reconciliation": {
            "currency": rec.currency,
            "purchase_order_total": plain_money(rec.po_total),
            "invoice_total": plain_money(rec.invoice_total),
            "net_difference": plain_money(rec.net_difference),
            "flagged_invoice_above_po": plain_money(rec.flagged_over_po),
            "flagged_invoice_below_po": plain_money(rec.flagged_under_po),
        },
        "margin": None,
        "summary": {
            "total_findings": len(result.findings),
            "by_severity": dict(Counter(f.severity.value for f in result.findings)),
            "by_kind": dict(Counter(f.kind.value for f in result.findings)),
        },
        "findings": [f.to_dict() for f in result.findings],
    }
    if margin is not None:
        report["margin"] = {
            "currency": margin.currency,
            "revenue": plain_money(margin.revenue),
            "planned_cost": plain_money(margin.planned_cost),
            "actual_cost": plain_money(margin.actual_cost),
            "planned_margin": plain_money(margin.planned_margin),
            "actual_margin": plain_money(margin.actual_margin),
            "planned_margin_pct": plain_money(margin.planned_margin_pct),
            "actual_margin_pct": plain_money(margin.actual_margin_pct),
            "margin_erosion": plain_money(margin.margin_erosion),
            "received": None if margin.received is None else plain_money(margin.received),
            "short_payment": _pct(margin.short_payment),
            "realised_margin": _pct(margin.realised_margin),
            "categories": [
                {
                    "category": c.category,
                    "planned": plain_money(c.planned),
                    "actual": plain_money(c.actual),
                    "variance": plain_money(c.variance),
                    "variance_pct": _pct(c.variance_pct),
                }
                for c in margin.categories
            ],
        }
    return report


def _fm(text: str | None) -> str:
    return "-" if text is None else f"{Decimal(text):,.2f}"


def _md(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def render_json(report: dict) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False) + "\n"


def render_markdown(report: dict) -> str:
    o, rec, m = report["order"], report["reconciliation"], report["margin"]
    cur = o["currency"]
    lines = [
        f"# MarginMesh order analysis: {_md(o['order_id'])}",
        "",
        f"> {report['meta']['disclaimer']}",
        "",
        f"Generated: {report['meta']['generated_at']} | Tool version: {report['meta']['version']}",
        "",
        "## Reconciliation summary",
        "",
        "| Item | Amount |",
        "|---|---:|",
        f"| Purchase order total ({cur}) | {_fm(rec['purchase_order_total'])} |",
        f"| Invoice total ({cur}) | {_fm(rec['invoice_total'])} |",
        f"| Net difference (invoice - PO) | {_fm(rec['net_difference'])} |",
        f"| Flagged: invoice above PO | {_fm(rec['flagged_invoice_above_po'])} |",
        f"| Flagged: invoice below PO | {_fm(rec['flagged_invoice_below_po'])} |",
        "",
    ]
    if m:
        lines += [
            "## Order margin",
            "",
            "| Measure | Planned | Actual |",
            "|---|---:|---:|",
            f"| Revenue ({cur}) | {_fm(m['revenue'])} | {_fm(m['revenue'])} |",
            f"| Cost | {_fm(m['planned_cost'])} | {_fm(m['actual_cost'])} |",
            f"| Margin | {_fm(m['planned_margin'])} | {_fm(m['actual_margin'])} |",
            f"| Margin % | {m['planned_margin_pct']}% | {m['actual_margin_pct']}% |",
            "",
            f"Margin erosion: **{_fm(m['margin_erosion'])} {cur}**.",
        ]
        if m["received"] is not None:
            lines += [
                "",
                f"Received: {_fm(m['received'])}; shortfall vs revenue: "
                f"{_fm(m['short_payment'])}; realised margin: {_fm(m['realised_margin'])}.",
            ]
        lines += [
            "",
            "### Cost variance by category",
            "",
            "| Category | Planned | Actual | Variance | Variance % |",
            "|---|---:|---:|---:|---:|",
        ]
        for c in m["categories"]:
            pct = "-" if c["variance_pct"] is None else f"{c['variance_pct']}%"
            lines.append(
                f"| {_md(c['category'])} | {_fm(c['planned'])} | {_fm(c['actual'])} | "
                f"{_fm(c['variance'])} | {pct} |"
            )
        lines.append("")
    lines += [f"## Findings ({report['summary']['total_findings']})", ""]
    if not report["findings"]:
        lines.append("No discrepancies above tolerance were found.")
    else:
        lines += [
            "| ID | Severity | Kind | SKU | Expected | Actual | Difference | Status |",
            "|---|---|---|---|---:|---:|---:|---|",
        ]
        for f in report["findings"]:
            lines.append(
                f"| {_md(f['id'])} | {f['severity']} | {f['kind']} | {_md(f['sku'] or '-')} | "
                f"{_fm(f['expected'])} | {_fm(f['actual'])} | {_fm(f['difference'])} | "
                f"{f['status']} |"
            )
        lines += ["", "### Finding details and evidence", ""]
        for f in report["findings"]:
            lines.append(f"- **{_md(f['id'])}** ({f['kind']}): {_md(f['explanation'])}")
            lines.append(f"  - Evidence: {_md('; '.join(f['evidence']))}")
    lines.append("")
    return "\n".join(lines)


_CSV_COLUMNS = [
    "id", "order_id", "kind", "severity", "sku", "currency", "expected", "actual",
    "difference", "difference_pct", "status", "explanation", "evidence",
]  # fmt: skip


def render_csv(report: dict) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_CSV_COLUMNS)
    for f in report["findings"]:
        row = dict(f)
        row["evidence"] = "; ".join(f["evidence"])
        writer.writerow(
            [
                safe_cell(row[c]) if c in {"sku", "explanation", "evidence"} else row[c]
                for c in _CSV_COLUMNS
            ]
        )
    return buffer.getvalue()


def write_xlsx(report: dict, path: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    header_fill = PatternFill("solid", fgColor="1F3A5F")
    header_font = Font(bold=True, color="FFFFFF")

    def style_header(ws, row: int, ncols: int) -> None:
        for col in range(1, ncols + 1):
            cell = ws.cell(row=row, column=col)
            cell.fill, cell.font = header_fill, header_font

    ws = wb.active
    ws.title = "Summary"
    o, rec, m = report["order"], report["reconciliation"], report["margin"]
    rows: list[tuple[str, object]] = [
        ("Order", safe_cell(o["order_id"])),
        ("Currency", o["currency"]),
        ("Generated at", report["meta"]["generated_at"]),
        ("PO total", Decimal(rec["purchase_order_total"])),
        ("Invoice total", Decimal(rec["invoice_total"])),
        ("Net difference", Decimal(rec["net_difference"])),
        ("Flagged: invoice above PO", Decimal(rec["flagged_invoice_above_po"])),
        ("Flagged: invoice below PO", Decimal(rec["flagged_invoice_below_po"])),
        ("Findings", report["summary"]["total_findings"]),
    ]
    if m:
        rows += [
            ("Revenue", Decimal(m["revenue"])),
            ("Planned margin", Decimal(m["planned_margin"])),
            ("Actual margin", Decimal(m["actual_margin"])),
            ("Margin erosion", Decimal(m["margin_erosion"])),
        ]
    rows.append(("Disclaimer", report["meta"]["disclaimer"]))
    for r, (k, v) in enumerate(rows, start=1):
        ws.cell(row=r, column=1, value=k).font = Font(bold=True)
        cell = ws.cell(row=r, column=2, value=v)
        if isinstance(v, Decimal):
            cell.number_format = "#,##0.00"
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 60
    ws.cell(row=len(rows), column=2).alignment = Alignment(wrap_text=True)

    fs = wb.create_sheet("Findings")
    fs.append(_CSV_COLUMNS)
    style_header(fs, 1, len(_CSV_COLUMNS))
    for f in report["findings"]:
        fs.append(
            [
                safe_cell(f["id"]),
                safe_cell(f["order_id"]),
                f["kind"],
                f["severity"],
                safe_cell(f["sku"]),
                f["currency"],
                Decimal(f["expected"]),
                Decimal(f["actual"]),
                Decimal(f["difference"]),
                None if f["difference_pct"] is None else Decimal(f["difference_pct"]),
                f["status"],
                safe_cell(f["explanation"]),
                safe_cell("; ".join(f["evidence"])),
            ]
        )
    for row in fs.iter_rows(min_row=2, min_col=7, max_col=10):
        for cell in row:
            cell.number_format = "#,##0.00"
    widths = {"A": 16, "B": 16, "C": 22, "D": 10, "E": 16, "F": 9, "G": 14, "H": 14}
    widths.update({"I": 14, "J": 10, "K": 14, "L": 70, "M": 50})
    for col, width in widths.items():
        fs.column_dimensions[col].width = width
    fs.freeze_panes = "A2"

    if m:
        cs = wb.create_sheet("Cost variance")
        cs.append(["category", "planned", "actual", "variance", "variance_pct"])
        style_header(cs, 1, 5)
        for c in m["categories"]:
            cs.append(
                [
                    safe_cell(c["category"]),
                    Decimal(c["planned"]),
                    Decimal(c["actual"]),
                    Decimal(c["variance"]),
                    None if c["variance_pct"] is None else Decimal(c["variance_pct"]),
                ]
            )
        for row in cs.iter_rows(min_row=2, min_col=2, max_col=5):
            for cell in row:
                cell.number_format = "#,##0.00"
        cs.column_dimensions["A"].width = 34
    wb.save(path)


def write_reports(
    result: AnalysisResult,
    out_dir: str | Path,
    formats: tuple[str, ...] = FORMATS,
    generated_at: str | None = None,
) -> list[Path]:
    unknown = [f for f in formats if f not in FORMATS]
    if unknown:
        raise ValueError(f"unknown format(s): {', '.join(unknown)}; choose from {FORMATS}")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = build_report(result, generated_at)
    stem = f"{result.order.order_id}_report"
    written: list[Path] = []
    for fmt in formats:
        path = out / (f"{stem}_findings.csv" if fmt == "csv" else f"{stem}.{fmt}")
        if fmt == "json":
            path.write_text(render_json(report), encoding="utf-8")
        elif fmt == "md":
            path.write_text(render_markdown(report), encoding="utf-8")
        elif fmt == "csv":
            path.write_text(render_csv(report), encoding="utf-8", newline="")
        else:
            write_xlsx(report, path)
        written.append(path)
    return written


__all__ = [
    "DISCLAIMER", "FORMATS", "build_report", "money", "render_csv", "render_json",
    "render_markdown", "safe_cell", "write_reports", "write_xlsx",
]  # fmt: skip
