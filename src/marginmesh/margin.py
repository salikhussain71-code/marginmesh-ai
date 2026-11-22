"""Order margin: planned vs actual cost, margin erosion and payment shortfall."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from marginmesh.models import (
    CostLine,
    Finding,
    FindingKind,
    Tolerance,
    fmt_money,
    severity_for_ratio,
)

_HUNDRED = Decimal(100)


@dataclass(frozen=True)
class CategoryVariance:
    category: str
    planned: Decimal
    actual: Decimal
    sources: tuple[str, ...]

    @property
    def variance(self) -> Decimal:
        """Positive = cost overrun."""
        return self.actual - self.planned

    @property
    def variance_pct(self) -> Decimal | None:
        return None if self.planned == 0 else self.variance / self.planned * _HUNDRED


@dataclass
class OrderMargin:
    order_id: str
    currency: str
    revenue: Decimal
    planned_cost: Decimal
    actual_cost: Decimal
    categories: list[CategoryVariance] = field(default_factory=list)
    received: Decimal | None = None

    @property
    def planned_margin(self) -> Decimal:
        return self.revenue - self.planned_cost

    @property
    def actual_margin(self) -> Decimal:
        return self.revenue - self.actual_cost

    @property
    def planned_margin_pct(self) -> Decimal:
        return self.planned_margin / self.revenue * _HUNDRED

    @property
    def actual_margin_pct(self) -> Decimal:
        return self.actual_margin / self.revenue * _HUNDRED

    @property
    def margin_erosion(self) -> Decimal:
        """planned_margin - actual_margin (equals actual_cost - planned_cost)."""
        return self.planned_margin - self.actual_margin

    @property
    def short_payment(self) -> Decimal | None:
        """revenue - received. Positive means the buyer paid less than invoiced."""
        return None if self.received is None else self.revenue - self.received

    @property
    def realised_margin(self) -> Decimal | None:
        return None if self.received is None else self.received - self.actual_cost


def compute_order_margin(
    order_id: str,
    currency: str,
    revenue: Decimal,
    cost_lines: list[CostLine],
    received: Decimal | None = None,
) -> OrderMargin:
    if revenue <= 0:
        raise ValueError("revenue must be greater than zero")
    if received is not None and received < 0:
        raise ValueError("received must not be negative")
    grouped: dict[str, list[CostLine]] = {}
    labels: dict[str, str] = {}
    for line in cost_lines:
        key = line.category.strip().lower()
        grouped.setdefault(key, []).append(line)
        labels.setdefault(key, line.category.strip())
    categories = [
        CategoryVariance(
            labels[key],
            sum((c.planned for c in lines), Decimal(0)),
            sum((c.actual for c in lines), Decimal(0)),
            tuple(c.source for c in lines),
        )
        for key, lines in grouped.items()
    ]
    return OrderMargin(
        order_id=order_id,
        currency=currency,
        revenue=revenue,
        planned_cost=sum((c.planned for c in categories), Decimal(0)),
        actual_cost=sum((c.actual for c in categories), Decimal(0)),
        categories=categories,
        received=received,
    )


def margin_findings(margin: OrderMargin, tolerance: Tolerance | None = None) -> list[Finding]:
    tol = tolerance or Tolerance()
    findings: list[Finding] = []
    for cat in margin.categories:
        threshold = max(tol.cost_abs, cat.planned * tol.cost_pct / _HUNDRED)
        if cat.variance > threshold:
            ratio = Decimal(1) if cat.planned == 0 else cat.variance / cat.planned
            pct = "n/a" if cat.variance_pct is None else f"{cat.variance_pct:.2f}%"
            findings.append(
                Finding(
                    order_id=margin.order_id,
                    kind=FindingKind.COST_OVERRUN,
                    severity=severity_for_ratio(ratio),
                    sku=None,
                    currency=margin.currency,
                    expected=cat.planned,
                    actual=cat.actual,
                    difference=cat.variance,
                    explanation=(
                        f"'{cat.category}' actual cost {fmt_money(cat.actual)} exceeds planned "
                        f"{fmt_money(cat.planned)} by {fmt_money(cat.variance)} ({pct})."
                    ),
                    evidence=list(cat.sources),
                )
            )
    short = margin.short_payment
    if short is not None and short > tol.payment_abs:
        findings.append(
            Finding(
                order_id=margin.order_id,
                kind=FindingKind.SHORT_PAYMENT,
                severity=severity_for_ratio(short / margin.revenue),
                sku=None,
                currency=margin.currency,
                expected=margin.revenue,
                actual=margin.received if margin.received is not None else Decimal(0),
                difference=-short,
                explanation=(
                    f"Received {fmt_money(margin.received or Decimal(0))} against order revenue "
                    f"{fmt_money(margin.revenue)}: shortfall {fmt_money(short)}. Check buyer "
                    "deductions, bank charges and agreed claims."
                ),
                evidence=["order file: revenue / received"],
            )
        )
    return findings
