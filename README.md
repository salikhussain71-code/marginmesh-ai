# MarginMesh AI: Order Recovery Engine

CI · Python · MIT License

Evidence-linked reconciliation and margin analysis for export orders. Give it a purchase order, a supplier invoice, and a costing sheet; it shows where an order's expected profit differs from the actual outcome, with the formula and the source row behind every number.

Built for the textile and apparel export workflow. MarginMesh AI is an early prototype (v0.1.0) that runs on synthetic data only.

## Why This Exists

Export manufacturers can lose margin through invoice price changes, quantity discrepancies, unexpected items, freight and finishing overruns, and payment shortfalls.

Checking these issues manually across multiple purchase orders, invoices, and costing sheets is time-consuming and error-prone.

MarginMesh AI automates reconciliation and financial calculations while keeping the evidence visible, so people can review discrepancies rather than blindly trust a number.

## What It Does

- Matches purchase order and invoice lines by SKU.
- Separates invoice differences into price effects and quantity effects.
- Ensures price effect + quantity effect equals the invoice-minus-PO difference.
- Flags unordered items, missing items, currency mismatches, and duplicate invoice lines.
- Calculates planned and actual margin.
- Identifies margin erosion, cost overruns by category, and payment shortfalls.
- Produces JSON, Markdown, CSV, and Excel reports.
- Links findings to their source file and row.
- Uses deterministic calculations instead of AI-generated financial amounts.

## What It Deliberately Does Not Do

- It does not automatically classify a discrepancy as a confirmed loss.
- Every finding is marked for review.
- No language model calculates financial amounts.
- No OCR or PDF extraction.
- No tax calculations.
- No purchase order amendments or credit note processing.
- No currency conversion.
- No real customer or company financial data is included.

## Key Design Principles

### Financial Precision

All monetary calculations use Python `Decimal` rather than binary floating-point arithmetic.

### Evidence-Linked Findings

Reconciliation findings retain references to the original file and row, making it possible to trace results back to their source.

### Transparent Calculations

Financial differences are broken down into explicit price and quantity effects rather than hidden behind a single unexplained number.

### Human Review

The tool identifies potential discrepancies. It does not make final accounting decisions or automatically declare financial losses.

### Deterministic Results

The same input records produce reproducible calculations and findings.

---

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/salikhussain71-code/marginmesh-ai.git
cd marginmesh-ai
```

### 2. Create a Virtual Environment

**Windows:**

```powershell
python -m venv .venv
.venv\Scripts\activate
```

**Linux / macOS:**

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -e ".[dev]"
```

### 4. Run the Demo

```bash
marginmesh demo --out marginmesh-demo
```

Generated reports will be available in:

```text
marginmesh-demo/
└── reports/
```

Open the generated Markdown report or Excel workbook to review the findings.

---

## Example Output

Synthetic order:

`ORD-2026-0001`

```text
Order ORD-2026-0001: 11 finding(s) need review

PO total       60,661.39
Invoice total  60,895.80
Net difference    234.41 USD

Margin:
Planned: 18.00%
Actual:  16.16%
Erosion:  1,987.52 USD
```

### Sample Findings

| Severity | Finding | SKU | Expected | Actual | Difference |
|---|---|---|---:|---:|---:|
| HIGH | PRICE_VARIANCE | FAB-JER-180 | 21,800.85 | 23,095.95 | 1,295.10 |
| HIGH | QUANTITY_VARIANCE | FAB-FLC-280 | 18,970.04 | 19,940.54 | 970.50 |
| HIGH | QUANTITY_VARIANCE | YRN-DYE-30S | 6,472.00 | 5,672.00 | -800.00 |
| MEDIUM | MISSING_ON_INVOICE | TRM-BTN-18 | 1,358.94 | 0.00 | -1,358.94 |
| HIGH | UNORDERED_ON_INVOICE | TRM-DRW-CORD | 0.00 | 90.00 | 90.00 |

All values above are from fictional sample records.

### Example Price Effect

If the invoice unit price is 5.35 while the purchase order unit price is 5.05, for a quantity of 4,317:

```text
(5.35 - 5.05) × 4,317 = 1,295.10 USD
```

The report provides the calculation and supporting evidence.

Full generated output:

```text
data/sample/expected_output/
```

---

## Verification and Testing

MarginMesh AI has been tested through automated tests, CI, and manual execution on a local Windows environment.

### Automated Tests

```bash
pytest
```

Observed result:

```text
86 passed
```

### Continuous Integration

The GitHub Actions CI workflow completed successfully.

CI checks include automated testing and linting across its configured Python versions.

### Local Environment Verification

| Environment | Result |
|---|---|
| Operating System | Windows 10 |
| Python | 3.14.3 |
| Installation | Successful |
| CLI demo | Successful |
| Automated tests | 86 passed |
| JSON report generation | Successful |
| Markdown report generation | Successful |
| CSV report generation | Successful |
| Excel report generation | Successful |

### Manual Input-Change Verification

A sample supplier invoice price was deliberately changed from `5.35` to `6.00` to verify that the application recalculates results from updated input data.

| Metric | Original | Modified |
|---|---:|---:|
| Invoice unit price | 5.35 | 6.00 |
| Invoice total | 60,895.80 | 63,701.85 |
| Net difference | 234.41 | 3,040.46 |

The application reflected the modified invoice price in the generated reconciliation report.

The sample file was subsequently restored to its original value of `5.35`.

This verification demonstrates that the application responds to the modified synthetic input. It does not establish accuracy on real-world exporter records.

### Reproducibility

A randomized test suite verifies that price effect and quantity effect sum to the total invoice-versus-purchase-order difference across randomized cases.

The project also includes synthetic ground-truth tests designed to verify discrepancy detection against deliberately injected discrepancies.

These results are limited to the generated test data and defined test conditions.

---

## Using Your Own Files

Example:

```bash
marginmesh analyze \
  --po purchase_order.xlsx \
  --invoice supplier_invoice.csv \
  --costing costing_sheet.csv \
  --order-id ORD-1001 \
  --currency USD \
  --revenue 108000 \
  --received 106400 \
  --out reports \
  --formats json,md,csv,xlsx
```

### Supported Input Files

| File | Required columns | Optional columns |
|---|---|---|
| Purchase order | `sku`, `quantity`, `unit_price` | `description`, `currency` |
| Supplier invoice | `sku`, `quantity`, `unit_price` | `description`, `currency` |
| Costing sheet | `category`, `planned_cost`, `actual_cost` | Depends on supported schema |

Column aliases are supported and matching is case-insensitive.

The `--costing` option requires `--revenue` or a supported order JSON file.

Invalid inputs return exit code `2`, with an error identifying the relevant file and row where available.

---

## Financial Calculations

### Gross Profit

```text
Gross Profit = Revenue - Total Costs
```

### Gross Margin

```text
Gross Margin (%) = (Gross Profit / Revenue) × 100
```

Zero revenue is handled safely.

### Price Effect

The price effect isolates the financial difference caused by a change in unit price.

### Quantity Effect

The quantity effect isolates the financial difference caused by a change in ordered and invoiced quantities.

Price and quantity effects are designed to reconcile to the total invoice-minus-purchase-order difference.

All financial arithmetic uses `Decimal`.

---

## Optional Local API

Install the API dependencies:

```bash
pip install -e ".[api]"
```

Run the local API:

```bash
uvicorn marginmesh.api:app --host 127.0.0.1 --port 8000
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

The API exposes:

```text
POST /v1/analyze
```

It accepts multipart file uploads for local analysis.

**Security note:** The prototype API has no authentication. It is intended for local use only and should not be exposed publicly.

---

## Project Structure

```text
marginmesh-ai/
│
├── .github/
│   └── workflows/
│       └── CI
│
├── data/
│   └── sample/
│
├── docs/
│
├── src/
│   └── marginmesh/
│
├── tests/
│
├── CHANGELOG.md
├── CONTRIBUTING.md
├── Dockerfile
├── LICENSE
├── Makefile
├── README.md
├── SECURITY.md
├── pyproject.toml
├── requirements.txt
└── requirements-dev.txt
```

The source package separates models, ingestion, validation, reconciliation, calculations, reporting, synthetic data generation, CLI functionality, and API functionality.

---

## Limitations

MarginMesh AI is an early-stage prototype.

Current limitations include:

- Single-currency comparisons.
- SKU-level matching.
- Spreadsheet-based input.
- No database persistence.
- No user accounts or access management.
- No OCR or PDF extraction.
- No real-world exporter validation.
- No automated accounting or ERP integration.

Existing ERP, accounting, and costing systems already provide many related features.

MarginMesh explores a lightweight, spreadsheet-first reconciliation workflow with evidence-linked findings. Its effectiveness and usefulness have not yet been validated with real textile exporters.

---

## Roadmap

Potential future directions:

- Real-world workflow validation with textile exporters.
- More flexible SKU and line-item matching.
- Purchase order amendments and credit notes.
- Additional discrepancy rules.
- Improved evidence and audit trails.
- Document extraction from PDFs.
- Multi-currency support with explicit exchange-rate evidence.
- Optional integrations with existing ERP and accounting workflows.
- More comprehensive test cases using anonymized, permission-based records.

Future features will be prioritized based on workflow feedback rather than assumptions.

---

## Documentation

Additional project documentation is available in `docs/`:

- Methodology
- Architecture
- Roadmap
- Data policy
- Customer discovery
- Security

---

## Data Policy

The repository uses synthetic sample data.

Do not upload confidential invoices, supplier information, bank details, customer identities, or commercially sensitive financial information.

Any real-world testing should use properly authorized and anonymized records.

---

## Author

**Salik Hussain**

BS Computer Science student at Iqra University, Islamabad, Pakistan.

Areas of technical interest:

- Python Software Development
- Artificial Intelligence
- Machine Learning
- Natural Language Processing
- Data Engineering
- Research-oriented software development

GitHub:

https://github.com/salikhussain71-code

Project:

https://github.com/salikhussain71-code/marginmesh-ai

---

## License

This project is licensed under the MIT License.

See [LICENSE](LICENSE) for details.

---

**MarginMesh AI v0.1.0**

An experimental, evidence-linked reconciliation engine focused on transparent calculations, reproducibility, and human-reviewed financial findings.
