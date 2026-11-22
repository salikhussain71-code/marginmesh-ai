# Architecture

```
 CSV / XLSX files                       order.json / CLI flags
 (PO, invoice, costing)                 (order id, revenue, received)
        |                                         |
        v                                         v
  ingest.py  ----- validated LineItem / CostLine -----> analysis.py
  (strict parsing, row-level source tags)               (orchestrates)
                                                          |        |
                                              reconcile.py        margin.py
                                              (PO vs invoice)     (cost, margin, payment)
                                                          \        /
                                                           Findings (+ evidence)
                                                                |
                                                           report.py
                                         JSON | Markdown | CSV | Excel
                                                                |
                                          cli.py  /  api.py (optional FastAPI)
```

| Module | Responsibility |
|---|---|
| `models.py` | Dataclasses, enums, tolerances, money formatting. Decimal only. |
| `ingest.py` | Read CSV/XLSX, normalise headers, validate every value, tag rows with `file:row`. |
| `reconcile.py` | Deterministic PO-vs-invoice comparison and exact variance split. |
| `margin.py` | Planned vs actual cost, margin erosion, payment shortfall. |
| `analysis.py` | Combine results, sort, assign stable finding IDs. |
| `report.py` | Render reports; neutralise spreadsheet formula injection. |
| `synthetic.py` | Deterministic fictional data with injected ground truth. |
| `cli.py` / `api.py` | Interfaces. The API is a local prototype without authentication. |

## Design rules

1. Calculations are plain, tested Python. No language model decides an amount.
2. Every finding carries evidence (file and row) and a human-readable formula.
3. Nothing is called a loss; every finding is `needs_review`.
4. Untrusted input is validated at the boundary (types, sizes, extensions, order id allow-list).

## Where AI fits later

Document extraction (OCR / PDF tables) and natural-language explanations are planned as layers
**in front of** and **after** this engine. They would produce candidate line items that a person
confirms; the engine would still calculate every number. See `ROADMAP.md`.
