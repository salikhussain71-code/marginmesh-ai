# MarginMesh order analysis: ORD-2026-0001

> Findings are potential discrepancies that require human review. They are not confirmed financial losses and are not accounting, tax or legal advice.

Generated: 2026-11-22T09:16:45+00:00 | Tool version: 0.1.0

## Reconciliation summary

| Item | Amount |
|---|---:|
| Purchase order total (USD) | 60,661.39 |
| Invoice total (USD) | 60,895.80 |
| Net difference (invoice - PO) | 234.41 |
| Flagged: invoice above PO | 2,393.35 |
| Flagged: invoice below PO | 2,158.94 |

## Order margin

| Measure | Planned | Actual |
|---|---:|---:|
| Revenue (USD) | 108,006.87 | 108,006.87 |
| Cost | 88,565.63 | 90,553.15 |
| Margin | 19,441.24 | 17,453.72 |
| Margin % | 18.00% | 16.16% |

Margin erosion: **1,987.52 USD**.

Received: 106,386.77; shortfall vs revenue: 1,620.10; realised margin: 15,833.62.

### Cost variance by category

| Category | Planned | Actual | Variance | Variance % |
|---|---:|---:|---:|---:|
| materials | 60,661.39 | 60,895.80 | 234.41 | 0.39% |
| cutting_stitching | 18,198.42 | 18,926.36 | 727.94 | 4.00% |
| washing_finishing | 3,639.68 | 4,076.44 | 436.76 | 12.00% |
| packaging | 2,426.46 | 2,377.93 | -48.53 | -2.00% |
| freight | 3,033.07 | 3,670.01 | 636.94 | 21.00% |
| testing_compliance | 606.61 | 606.61 | 0.00 | 0.00% |

## Findings (11)

| ID | Severity | Kind | SKU | Expected | Actual | Difference | Status |
|---|---|---|---|---:|---:|---:|---|
| ORD-2026-0001-F001 | HIGH | PRICE_VARIANCE | FAB-JER-180 | 21,800.85 | 23,095.95 | 1,295.10 | needs_review |
| ORD-2026-0001-F002 | HIGH | QUANTITY_VARIANCE | FAB-FLC-280 | 18,970.04 | 19,940.54 | 970.50 | needs_review |
| ORD-2026-0001-F003 | HIGH | QUANTITY_VARIANCE | YRN-DYE-30S | 6,472.00 | 5,672.00 | -800.00 | needs_review |
| ORD-2026-0001-F004 | HIGH | COST_OVERRUN | - | 3,033.07 | 3,670.01 | 636.94 | needs_review |
| ORD-2026-0001-F005 | HIGH | COST_OVERRUN | - | 3,639.68 | 4,076.44 | 436.76 | needs_review |
| ORD-2026-0001-F006 | HIGH | UNORDERED_ON_INVOICE | TRM-DRW-CORD | 0.00 | 90.00 | 90.00 | needs_review |
| ORD-2026-0001-F007 | MEDIUM | SHORT_PAYMENT | - | 108,006.87 | 106,386.77 | -1,620.10 | needs_review |
| ORD-2026-0001-F008 | MEDIUM | MISSING_ON_INVOICE | TRM-BTN-18 | 1,358.94 | 0.00 | -1,358.94 | needs_review |
| ORD-2026-0001-F009 | MEDIUM | COST_OVERRUN | - | 18,198.42 | 18,926.36 | 727.94 | needs_review |
| ORD-2026-0001-F010 | MEDIUM | PRICE_VARIANCE | PKG-CTN-5P | 1,026.80 | 1,064.55 | 37.75 | needs_review |
| ORD-2026-0001-F011 | INFO | DUPLICATE_SKU_LINES | PKG-POL-01 | 618.00 | 618.00 | 0.00 | needs_review |

### Finding details and evidence

- **ORD-2026-0001-F001** (PRICE_VARIANCE): Invoice unit price 5.35 is above the purchase order price 5.05. Effect: (5.35 - 5.05) x 4317 = 1,295.10 USD.
  - Evidence: purchase_order.csv:row 2; supplier_invoice.csv:row 2
- **ORD-2026-0001-F002** (QUANTITY_VARIANCE): Invoice quantity 3082 vs ordered 2932 (more than ordered - check for over-shipment or over-billing). Effect at purchase-order price: (3082 - 2932) x 6.47 = 970.50 USD.
  - Evidence: purchase_order.csv:row 4; supplier_invoice.csv:row 4
- **ORD-2026-0001-F003** (QUANTITY_VARIANCE): Invoice quantity 1418 vs ordered 1618 (fewer than ordered - check for short shipment). Effect at purchase-order price: (1418 - 1618) x 4.00 = -800.00 USD.
  - Evidence: purchase_order.csv:row 5; supplier_invoice.csv:row 5
- **ORD-2026-0001-F004** (COST_OVERRUN): 'freight' actual cost 3,670.01 exceeds planned 3,033.07 by 636.94 (21.00%).
  - Evidence: costing_sheet.csv:row 6
- **ORD-2026-0001-F005** (COST_OVERRUN): 'washing_finishing' actual cost 4,076.44 exceeds planned 3,639.68 by 436.76 (12.00%).
  - Evidence: costing_sheet.csv:row 4
- **ORD-2026-0001-F006** (UNORDERED_ON_INVOICE): SKU TRM-DRW-CORD is billed (500 x 0.18 = 90.00) but is not on the purchase order.
  - Evidence: supplier_invoice.csv:row 12
- **ORD-2026-0001-F007** (SHORT_PAYMENT): Received 106,386.77 against order revenue 108,006.87: shortfall 1,620.10. Check buyer deductions, bank charges and agreed claims.
  - Evidence: order file: revenue / received
- **ORD-2026-0001-F008** (MISSING_ON_INVOICE): SKU TRM-BTN-18 is on the purchase order (1,358.94) but not on the invoice. This may be a partial shipment or a later invoice.
  - Evidence: purchase_order.csv:row 7
- **ORD-2026-0001-F009** (COST_OVERRUN): 'cutting_stitching' actual cost 18,926.36 exceeds planned 18,198.42 by 727.94 (4.00%).
  - Evidence: costing_sheet.csv:row 3
- **ORD-2026-0001-F010** (PRICE_VARIANCE): Invoice unit price 1.41 is above the purchase order price 1.36. Effect: (1.41 - 1.36) x 755 = 37.75 USD.
  - Evidence: purchase_order.csv:row 10; supplier_invoice.csv:row 10
- **ORD-2026-0001-F011** (DUPLICATE_SKU_LINES): SKU PKG-POL-01 appears on 2 invoice lines; they were combined (quantities summed, prices averaged by quantity). Check this is not a double-billing.
  - Evidence: supplier_invoice.csv:row 8; supplier_invoice.csv:row 9
