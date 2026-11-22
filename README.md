# MarginMesh AI: Order Recovery Engine

[![CI](https://github.com/salikhussain71-code/marginmesh-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/salikhussain71-code/marginmesh-ai/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)

Evidence-linked reconciliation and margin analysis for export orders. Give it a purchase order, a
supplier invoice and a costing sheet; it shows **where an order's expected profit differs from the
actual outcome**, with the formula and the source row behind every number.

Built for the textile and apparel export workflow. Early prototype (v0.1) that runs on
synthetic data only.

## Why this exists

Export manufacturers lose margin quietly: invoice prices drift from the PO, quantities differ,
unordered items appear, freight and finishing overrun, and buyers short-pay. Checking this by hand
across many orders is slow. MarginMesh automates the arithmetic and leaves the judgement to people.

## What it does

- Matches PO and invoice lines by SKU and splits every difference **exactly** into a price effect
  and a quantity effect (the two always sum to the invoice-minus-PO total).
- Flags unordered items, missing items, currency mismatches and duplicate invoice lines.
- Computes planned vs actual margin, margin erosion, cost overruns by category and payment shortfall.
- Writes JSON, Markdown, CSV and Excel reports; every finding cites `file:row`.

## What it deliberately does not do

- It does not call anything a "loss". Every finding is a *potential discrepancy* with status
  `needs_review`.
- No language model calculates any amount; all numbers come from tested `Decimal` arithmetic.
- No OCR / PDF reading, tax logic, amendments, credit notes or currency conversion yet (see roadmap).
- No real customer data is included or required.

## Quick start

```bash
git clone https://github.com/salikhussain71-code/marginmesh-ai.git
cd marginmesh-ai
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

marginmesh demo --out marginmesh-demo
```

Open `marginmesh-demo/reports/ORD-2026-0001_report.md` (or the `.xlsx`).

## Example output (synthetic order, seed 42)

```
Order ORD-2026-0001: 11 finding(s) need review
  PO total 60,661.39 | invoice total 60,895.80 | net 234.41 USD
  Margin: planned 18.00% -> actual 16.16% (erosion 1,987.52 USD)
```

| Severity | Kind | SKU | Expected | Actual | Difference |
|---|---|---|---:|---:|---:|
| HIGH | PRICE_VARIANCE | FAB-JER-180 | 21,800.85 | 23,095.95 | 1,295.10 |
| HIGH | QUANTITY_VARIANCE | FAB-FLC-280 | 18,970.04 | 19,940.54 | 970.50 |
| HIGH | QUANTITY_VARIANCE | YRN-DYE-30S | 6,472.00 | 5,672.00 | -800.00 |
| MEDIUM | MISSING_ON_INVOICE | TRM-BTN-18 | 1,358.94 | 0.00 | -1,358.94 |
| HIGH | UNORDERED_ON_INVOICE | TRM-DRW-CORD | 0.00 | 90.00 | 90.00 |

Example explanation: *Invoice unit price 5.35 is above the purchase order price 5.05.
Effect: (5.35 - 5.05) x 4317 = 1,295.10 USD.* Full output: `data/sample/expected_output/`.

## Using your own files

```bash
marginmesh analyze \
  --po purchase_order.xlsx --invoice supplier_invoice.csv --costing costing_sheet.csv \
  --order-id ORD-1001 --currency USD --revenue 108000 --received 106400 \
  --out reports --formats json,md,csv,xlsx
```

Input columns (case-insensitive, common aliases accepted):

| File | Required columns |
|---|---|
| Purchase order / invoice | `sku`, `quantity`, `unit_price` (optional: `description`, `currency`) |
| Costing sheet | `category`, `planned_cost`, `actual_cost` |

`--costing` needs `--revenue` (or an `--order-file` JSON). Exit code `2` means invalid input; the
message names the file and row.

## Optional local API

```bash
pip install -e ".[api]"
uvicorn marginmesh.api:app --host 127.0.0.1 --port 8000   # docs at /docs
```

`POST /v1/analyze` accepts multipart files. **No authentication: local use only.**

## Verification

```bash
pytest --cov=marginmesh
```

- 86 tests pass; 98% line coverage.
- Ground-truth test: for 25 CSV seeds and 5 XLSX seeds, the generator injects known
  discrepancies and the engine must find all of them with no extra reconciliation findings.
  This measures correctness on *synthetic* data only. It is not a claim about real-world accuracy.
- A 500-case randomised test proves `price effect + quantity effect = invoice total - PO total`.

## Project structure

```
src/marginmesh/   models, ingest, reconcile, margin, analysis, report, synthetic, cli, api
tests/            unit, property, end-to-end and API tests
data/sample/      synthetic order and expected output
docs/             methodology, architecture, roadmap, data policy, customer discovery guide
.github/          CI (Python 3.10-3.12, lint + tests)
```

## Documentation

[Methodology](docs/METHODOLOGY.md) | [Architecture](docs/ARCHITECTURE.md) |
[Roadmap](docs/ROADMAP.md) | [Data policy](docs/DATA_POLICY.md) |
[Customer discovery](docs/CUSTOMER_DISCOVERY.md) | [Security](SECURITY.md)

## Limitations

Single currency per comparison, SKU-level matching only, spreadsheet input only, no persistence,
no user accounts. Existing ERP and costing products already cover parts of this space; this
project explores a lightweight, spreadsheet-first, evidence-linked workflow and has not been
validated with real exporters.

## Author

Salik Hussain, BS Computer Science, Iqra University, Islamabad.
GitHub: [@salikhussain71-code](https://github.com/salikhussain71-code)

## License

MIT. See [LICENSE](LICENSE).
