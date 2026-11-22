"""Purchase-order vs supplier-invoice reconciliation.

For each SKU present on both documents the total difference is split exactly into:

    price effect    = (invoice_price - po_price) * invoice_qty
    quantity effect = (invoice_qty   - po_qty)   * po_price

    price effect + quantity effect == invoice_total - po_total   (exact identity)

Every result is a *potential* discrepancy that needs human review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from marginmesh.models import (
    Finding,
    FindingKind,
    LineItem,
    Severity,
    Tolerance,
    fmt_money,
    fmt_price,
    plain_number,
    severity_for_ratio,
)

_HUNDRED = Decimal(100)


@dataclass
class _Agg:
    sku: str
    description: str
    first_price: Decimal
    quantity: Decimal = Decimal(0)
    amount: Decimal = Decimal(0)
    lines: int = 0
    currencies: set[str] = field(default_factory=set)
    sources: list[str] = field(default_factory=list)

    @property
    def unit_price(self) -> Decimal:
        if self.lines == 1 or self.quantity == 0:
            return self.first_price
        return self.amount / self.quantity  # weighted average across duplicate lines

    @property
    def currency(self) -> str:
        return sorted(self.currencies)[0]


def _aggregate(items: list[LineItem]) -> dict[str, _Agg]:
    out: dict[str, _Agg] = {}
    for item in items:
        agg = out.get(item.sku)
        if agg is None:
            agg = out[item.sku] = _Agg(item.sku, item.description, item.unit_price)
        agg.quantity += item.quantity
        agg.amount += item.total
        agg.lines += 1
        agg.currencies.add(item.currency)
        agg.sources.append(item.source)
    return out


def _ratio(difference: Decimal, baseline: Decimal) -> Decimal:
    return Decimal(1) if baseline <= 0 else abs(difference) / baseline


def reconcile(
    order_id: str,
    po_items: list[LineItem],
    invoice_items: list[LineItem],
    tolerance: Tolerance | None = None,
) -> list[Finding]:
    """Compare a purchase order with a supplier invoice and return findings."""
    tol = tolerance or Tolerance()
    po = _aggregate(po_items)
    inv = _aggregate(invoice_items)
    findings: list[Finding] = []

    for sku in sorted(set(po) | set(inv)):
        p, i = po.get(sku), inv.get(sku)

        if i is not None and i.lines > 1:
            findings.append(
                Finding(
                    order_id=order_id,
                    kind=FindingKind.DUPLICATE_SKU_LINES,
                    severity=Severity.INFO,
                    sku=sku,
                    currency=i.currency,
                    expected=i.amount,
                    actual=i.amount,
                    difference=Decimal(0),
                    explanation=(
                        f"SKU {sku} appears on {i.lines} invoice lines; they were combined "
                        "(quantities summed, prices averaged by quantity). Check this is not a "
                        "double-billing."
                    ),
                    evidence=list(i.sources),
                )
            )

        if p is None and i is not None:
            findings.append(
                Finding(
                    order_id=order_id,
                    kind=FindingKind.UNORDERED_ON_INVOICE,
                    severity=Severity.HIGH,
                    sku=sku,
                    currency=i.currency,
                    expected=Decimal(0),
                    actual=i.amount,
                    difference=i.amount,
                    explanation=(
                        f"SKU {sku} is billed ({plain_number(i.quantity)} x "
                        f"{fmt_price(i.unit_price)} = {fmt_money(i.amount)}) but is not on "
                        "the purchase order."
                    ),
                    evidence=list(i.sources),
                )
            )
        elif i is None and p is not None:
            findings.append(
                Finding(
                    order_id=order_id,
                    kind=FindingKind.MISSING_ON_INVOICE,
                    severity=Severity.MEDIUM,
                    sku=sku,
                    currency=p.currency,
                    expected=p.amount,
                    actual=Decimal(0),
                    difference=-p.amount,
                    explanation=(
                        f"SKU {sku} is on the purchase order ({fmt_money(p.amount)}) but not on "
                        "the invoice. This may be a partial shipment or a later invoice."
                    ),
                    evidence=list(p.sources),
                )
            )
        elif p is not None and i is not None:
            findings.extend(_compare(order_id, p, i, tol))
    return findings


def _compare(order_id: str, p: _Agg, i: _Agg, tol: Tolerance) -> list[Finding]:
    evidence = [*p.sources, *i.sources]
    if len(p.currencies) != 1 or p.currencies != i.currencies:
        return [
            Finding(
                order_id=order_id,
                kind=FindingKind.CURRENCY_MISMATCH,
                severity=Severity.HIGH,
                sku=p.sku,
                currency=p.currency,
                expected=p.amount,
                actual=i.amount,
                difference=Decimal(0),
                explanation=(
                    f"SKU {p.sku}: purchase order currency {sorted(p.currencies)} differs from "
                    f"invoice currency {sorted(i.currencies)}. Amounts are not comparable; no "
                    "conversion was applied."
                ),
                evidence=evidence,
            )
        ]

    out: list[Finding] = []
    currency = p.currency

    price_diff = i.unit_price - p.unit_price
    price_threshold = max(tol.unit_price_abs, p.unit_price * tol.unit_price_pct / _HUNDRED)
    if abs(price_diff) > price_threshold:
        expected = p.unit_price * i.quantity
        effect = price_diff * i.quantity
        direction = "above" if price_diff > 0 else "below"
        out.append(
            Finding(
                order_id=order_id,
                kind=FindingKind.PRICE_VARIANCE,
                severity=severity_for_ratio(_ratio(effect, p.amount)),
                sku=p.sku,
                currency=currency,
                expected=expected,
                actual=expected + effect,
                difference=effect,
                explanation=(
                    f"Invoice unit price {fmt_price(i.unit_price)} is {direction} the purchase "
                    f"order price {fmt_price(p.unit_price)}. Effect: ({fmt_price(i.unit_price)} - "
                    f"{fmt_price(p.unit_price)}) x {plain_number(i.quantity)} = "
                    f"{fmt_money(effect)} {currency}."
                ),
                evidence=evidence,
            )
        )

    qty_diff = i.quantity - p.quantity
    qty_threshold = max(tol.quantity_abs, p.quantity * tol.quantity_pct / _HUNDRED)
    if abs(qty_diff) > qty_threshold:
        effect = qty_diff * p.unit_price
        if qty_diff > 0:
            note = "more than ordered - check for over-shipment or over-billing"
        else:
            note = "fewer than ordered - check for short shipment"
        out.append(
            Finding(
                order_id=order_id,
                kind=FindingKind.QUANTITY_VARIANCE,
                severity=severity_for_ratio(_ratio(effect, p.amount)),
                sku=p.sku,
                currency=currency,
                expected=p.amount,
                actual=p.amount + effect,
                difference=effect,
                explanation=(
                    f"Invoice quantity {plain_number(i.quantity)} vs ordered "
                    f"{plain_number(p.quantity)} ({note}). Effect at purchase-order price: "
                    f"({plain_number(i.quantity)} - {plain_number(p.quantity)}) x "
                    f"{fmt_price(p.unit_price)} = {fmt_money(effect)} {currency}."
                ),
                evidence=evidence,
            )
        )
    return out
