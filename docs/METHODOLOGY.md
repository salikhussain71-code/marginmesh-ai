# Methodology

All financial values are `decimal.Decimal`. Floats are never used for money or quantities.
Rounding to 2 decimals (half-up) happens only when a value is displayed or exported.

## 1. Reconciliation (purchase order vs supplier invoice)

Lines are matched by SKU (trimmed, upper-cased). Duplicate lines for the same SKU on one document
are combined: quantities and amounts are summed, and the unit price is the quantity-weighted
average.

For a SKU present on both documents:

```
price effect    = (invoice_price - po_price) * invoice_qty
quantity effect = (invoice_qty   - po_qty)   * po_price

price effect + quantity effect = invoice_total - po_total      (exact identity)
```

This identity is verified by a 500-case randomised test (`tests/test_reconcile.py`).

Worked example: PO 1,000 x 5.00; invoice 1,000 x 5.30. Price effect = (5.30 - 5.00) x 1,000 =
**300.00** = 6% of the PO line.

| Situation | Finding kind | Severity |
|---|---|---|
| Invoice price differs beyond tolerance | `PRICE_VARIANCE` | by size (see below) |
| Invoice quantity differs beyond tolerance | `QUANTITY_VARIANCE` | by size |
| SKU billed but not ordered | `UNORDERED_ON_INVOICE` | HIGH |
| SKU ordered but not billed | `MISSING_ON_INVOICE` | MEDIUM |
| Different currencies on the two documents | `CURRENCY_MISMATCH` | HIGH (no conversion applied) |
| Same SKU on several invoice lines | `DUPLICATE_SKU_LINES` | INFO |

Severity by size = |difference| / PO line total: >= 5% HIGH, >= 1% MEDIUM, otherwise LOW.

## 2. Order margin

```
planned_margin = revenue - planned_cost        actual_margin = revenue - actual_cost
margin_erosion = planned_margin - actual_margin  (= actual_cost - planned_cost)
short_payment  = revenue - received              realised_margin = received - actual_cost
```

A category is reported as `COST_OVERRUN` when `actual - planned > max(cost_abs, planned * cost_pct)`
(defaults: 1.00 and 2%). Under-runs are shown in the table but never reported as findings.
`SHORT_PAYMENT` is reported when `received` is below `revenue` by more than 0.005.

## 3. Tolerances

Defaults live in `marginmesh.models.Tolerance`: unit price 0.005 absolute, quantity 0, cost
overrun 1.00 / 2%, payment 0.005.

## 4. What the tool does not claim

- A finding is a **potential discrepancy**. Every finding starts as `needs_review`.
- No finding is a confirmed loss and none is "recoverable money" until a person verifies it
  against contracts, amendments, taxes, freight terms and agreed buyer claims.
- No currency conversion, tax logic, approved amendments or credit notes (v0.1).
- Findings are only as good as the input documents. There is no OCR or PDF extraction yet.
