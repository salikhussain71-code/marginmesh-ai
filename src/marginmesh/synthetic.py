"""Deterministic synthetic export-order data with known, injected discrepancies.

Everything produced here is fictional. It exists so the tool can be demonstrated and tested
without any real company's confidential records.
"""

from __future__ import annotations

import csv
import json
import random
from decimal import Decimal
from pathlib import Path

from marginmesh.models import money

# sku, description, base quantity, base unit price (USD)
CATALOGUE = [
    ("FAB-JER-180", "Combed cotton jersey 180 gsm (kg)", 4200, "5.20"),
    ("FAB-RIB-1X1", "Cotton rib 1x1 (kg)", 650, "5.85"),
    ("FAB-FLC-280", "Brushed fleece 280 gsm (kg)", 2800, "6.40"),
    ("YRN-DYE-30S", "Dyed cotton yarn 30s (kg)", 1500, "4.10"),
    ("TRM-ZIP-05", "Metal zipper 5 inch (pcs)", 12000, "0.42"),
    ("TRM-BTN-18", "Corozo button 18L (pcs)", 24000, "0.06"),
    ("TRM-LBL-WVN", "Woven main label (pcs)", 12000, "0.09"),
    ("PKG-POL-01", "Polybag with sticker (pcs)", 12000, "0.05"),
    ("PKG-CTN-5P", "Export carton 5-ply (pcs)", 800, "1.35"),
    ("THR-POL-40", "Polyester sewing thread cone (pcs)", 900, "1.10"),
]
UNORDERED = ("TRM-DRW-CORD", "Drawcord, flat (pcs)", 500, "0.18")

# (category, planned share of materials cost, actual multiplier vs planned)
OVERHEAD = [
    ("cutting_stitching", "0.30", "1.04"),
    ("washing_finishing", "0.06", "1.12"),
    ("packaging", "0.04", "0.98"),
    ("freight", "0.05", "1.21"),
    ("testing_compliance", "0.01", "1.00"),
]
ORDER_ID = "ORD-2026-0001"


def _d(text: str | int) -> Decimal:
    return Decimal(str(text))


def _write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def _write_xlsx(path: Path, header: list[str], rows: list[list[object]]) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(header)
    for row in rows:
        ws.append([_d(v) if isinstance(v, Decimal) else v for v in row])
    wb.save(path)


def generate_sample(
    out_dir: str | Path, seed: int = 42, formats: tuple[str, ...] = ("csv", "xlsx")
) -> dict:
    """Write a synthetic order and return the ground truth that was injected."""
    rng = random.Random(seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    po_rows: list[list[object]] = []
    po: dict[str, tuple[Decimal, Decimal]] = {}
    for sku, desc, qty, price in CATALOGUE:
        q = _d(max(1, round(qty * rng.uniform(0.9, 1.1))))
        p = money(_d(price) * _d(str(round(rng.uniform(0.97, 1.03), 4))))
        p = max(p, Decimal("0.04"))
        po[sku] = (q, p)
        po_rows.append([sku, desc, q, p, "USD"])

    inv_rows: list[list[object]] = []
    expected: list[dict[str, str]] = []
    for sku, desc, _, _ in CATALOGUE:
        q, p = po[sku]
        iq, ip = q, p
        if sku == "FAB-JER-180":
            ip = money(p * Decimal("1.06"))
            expected.append({"sku": sku, "kind": "PRICE_VARIANCE"})
        elif sku == "PKG-CTN-5P":
            ip = money(p * Decimal("1.04"))
            expected.append({"sku": sku, "kind": "PRICE_VARIANCE"})
        elif sku == "FAB-FLC-280":
            iq = q + 150
            expected.append({"sku": sku, "kind": "QUANTITY_VARIANCE"})
        elif sku == "YRN-DYE-30S":
            iq = q - 200
            expected.append({"sku": sku, "kind": "QUANTITY_VARIANCE"})
        elif sku == "TRM-BTN-18":
            expected.append({"sku": sku, "kind": "MISSING_ON_INVOICE"})
            continue
        elif sku == "PKG-POL-01":
            first = q // 2
            inv_rows.append([sku, desc, first, ip, "USD"])
            inv_rows.append([sku, desc, q - first, ip, "USD"])
            expected.append({"sku": sku, "kind": "DUPLICATE_SKU_LINES"})
            continue
        inv_rows.append([sku, desc, iq, ip, "USD"])
    usku, udesc, uqty, uprice = UNORDERED
    inv_rows.append([usku, udesc, _d(uqty), _d(uprice), "USD"])
    expected.append({"sku": usku, "kind": "UNORDERED_ON_INVOICE"})

    materials_planned = sum((r[2] * r[3] for r in po_rows), Decimal(0))  # type: ignore[operator]
    materials_actual = sum((r[2] * r[3] for r in inv_rows), Decimal(0))  # type: ignore[operator]
    cost_rows: list[list[object]] = [
        ["materials", money(materials_planned), money(materials_actual)]
    ]
    for category, share, mult in OVERHEAD:
        planned = money(materials_planned * _d(share))
        cost_rows.append([category, planned, money(planned * _d(mult))])
    total_planned = sum((r[1] for r in cost_rows), Decimal(0))  # type: ignore[arg-type]
    revenue = money(total_planned / Decimal("0.82"))  # planned margin of 18%
    received = money(revenue * Decimal("0.985"))  # 1.5% buyer deduction

    line_header = ["sku", "description", "quantity", "unit_price", "currency"]
    cost_header = ["category", "planned_cost", "actual_cost"]
    for fmt in formats:
        writer = _write_csv if fmt == "csv" else _write_xlsx
        writer(out / f"purchase_order.{fmt}", line_header, po_rows)
        writer(out / f"supplier_invoice.{fmt}", line_header, inv_rows)
        writer(out / f"costing_sheet.{fmt}", cost_header, cost_rows)

    order = {
        "order_id": ORDER_ID,
        "buyer": "Synthetic Buyer Ltd (fictional)",
        "currency": "USD",
        "revenue": str(revenue),
        "received": str(received),
    }
    (out / "order.json").write_text(json.dumps(order, indent=2) + "\n", encoding="utf-8")
    truth = {
        "seed": seed,
        "reconciliation": sorted(expected, key=lambda e: (e["sku"], e["kind"])),
        "cost_overruns": ["cutting_stitching", "freight", "washing_finishing"],
        "short_payment": True,
        "note": "Synthetic, fictional data. The 'materials' overrun depends on the injected rows.",
    }
    truth_text = json.dumps(truth, indent=2) + "\n"
    (out / "expected_findings.json").write_text(truth_text, encoding="utf-8")
    return truth
