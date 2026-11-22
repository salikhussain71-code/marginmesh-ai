"""Orchestrates reconciliation and margin analysis for a single order."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from marginmesh.margin import OrderMargin, compute_order_margin, margin_findings
from marginmesh.models import (
    SEVERITY_RANK,
    CostLine,
    Finding,
    FindingKind,
    LineItem,
    Tolerance,
)
from marginmesh.reconcile import reconcile

_ORDER_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")
_RECON_KINDS = {
    FindingKind.PRICE_VARIANCE,
    FindingKind.QUANTITY_VARIANCE,
    FindingKind.UNORDERED_ON_INVOICE,
    FindingKind.MISSING_ON_INVOICE,
}


@dataclass(frozen=True)
class OrderInfo:
    order_id: str
    currency: str = "USD"
    buyer: str | None = None
    revenue: Decimal | None = None
    received: Decimal | None = None

    def __post_init__(self) -> None:
        if not _ORDER_ID.fullmatch(self.order_id):
            raise ValueError("order_id must be 1-64 characters: letters, digits, '.', '_' or '-'")
        if not re.fullmatch(r"[A-Z]{3}", self.currency):
            raise ValueError("currency must be a 3-letter uppercase code, e.g. USD")


@dataclass(frozen=True)
class ReconciliationSummary:
    currency: str
    po_total: Decimal
    invoice_total: Decimal
    net_difference: Decimal
    flagged_over_po: Decimal  # sum of positive flagged differences
    flagged_under_po: Decimal  # sum of negative flagged differences (as positive number)


@dataclass
class AnalysisResult:
    order: OrderInfo
    findings: list[Finding]
    reconciliation: ReconciliationSummary
    margin: OrderMargin | None


def _total(items: list[LineItem], currency: str) -> Decimal:
    return sum((i.total for i in items if i.currency == currency), Decimal(0))


def analyze_order(
    order: OrderInfo,
    po_items: list[LineItem],
    invoice_items: list[LineItem],
    cost_lines: list[CostLine] | None = None,
    tolerance: Tolerance | None = None,
) -> AnalysisResult:
    findings = reconcile(order.order_id, po_items, invoice_items, tolerance)

    margin: OrderMargin | None = None
    if cost_lines is not None:
        if order.revenue is None:
            raise ValueError("revenue is required when a costing sheet is provided")
        margin = compute_order_margin(
            order.order_id, order.currency, order.revenue, cost_lines, order.received
        )
        findings.extend(margin_findings(margin, tolerance))

    findings.sort(
        key=lambda f: (-SEVERITY_RANK[f.severity], -abs(f.difference), f.sku or "", f.kind.value)
    )
    for n, finding in enumerate(findings, start=1):
        finding.id = f"{order.order_id}-F{n:03d}"

    po_total = _total(po_items, order.currency)
    inv_total = _total(invoice_items, order.currency)
    flagged = [f for f in findings if f.kind in _RECON_KINDS and f.currency == order.currency]
    over = sum((f.difference for f in flagged if f.difference > 0), Decimal(0))
    under = sum((-f.difference for f in flagged if f.difference < 0), Decimal(0))
    summary = ReconciliationSummary(
        currency=order.currency,
        po_total=po_total,
        invoice_total=inv_total,
        net_difference=inv_total - po_total,
        flagged_over_po=over,
        flagged_under_po=under,
    )
    return AnalysisResult(order, findings, summary, margin)
