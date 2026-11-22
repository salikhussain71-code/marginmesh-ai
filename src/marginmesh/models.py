"""Core data models.

All money and quantities are ``Decimal``. Floats are never used for financial values.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

CENT = Decimal("0.01")
_HUNDRED = Decimal(100)


def money(value: Decimal) -> Decimal:
    """Round to 2 decimal places using half-up rounding."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def plain_money(value: Decimal) -> str:
    """Money as a plain string without exponent or separators, e.g. ``-300.00``."""
    return format(money(value), "f")


def plain_number(value: Decimal) -> str:
    """Quantity as a plain string, e.g. ``1000`` or ``2.5``."""
    return format(value.normalize(), "f")


def fmt_money(value: Decimal) -> str:
    """Human-readable money with thousands separators."""
    return f"{money(value):,.2f}"


def fmt_price(value: Decimal) -> str:
    """Unit price with 2 to 4 decimals (``5.30``, ``0.0625``)."""
    text = f"{value:.4f}".rstrip("0")
    whole, _, frac = text.partition(".")
    return f"{whole}.{frac.ljust(2, '0')}"


class FindingKind(str, Enum):
    PRICE_VARIANCE = "PRICE_VARIANCE"
    QUANTITY_VARIANCE = "QUANTITY_VARIANCE"
    MISSING_ON_INVOICE = "MISSING_ON_INVOICE"
    UNORDERED_ON_INVOICE = "UNORDERED_ON_INVOICE"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    DUPLICATE_SKU_LINES = "DUPLICATE_SKU_LINES"
    COST_OVERRUN = "COST_OVERRUN"
    SHORT_PAYMENT = "SHORT_PAYMENT"


class Severity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


SEVERITY_RANK = {Severity.INFO: 0, Severity.LOW: 1, Severity.MEDIUM: 2, Severity.HIGH: 3}


class ReviewStatus(str, Enum):
    """Every finding starts as NEEDS_REVIEW. Only a human may change it."""

    NEEDS_REVIEW = "needs_review"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"


def severity_for_ratio(ratio: Decimal) -> Severity:
    """Map |difference| / baseline to a severity band (>=5% HIGH, >=1% MEDIUM)."""
    if ratio >= Decimal("0.05"):
        return Severity.HIGH
    if ratio >= Decimal("0.01"):
        return Severity.MEDIUM
    return Severity.LOW


@dataclass(frozen=True)
class Tolerance:
    """Thresholds below which a difference is not reported."""

    unit_price_abs: Decimal = Decimal("0.005")
    unit_price_pct: Decimal = Decimal("0")
    quantity_abs: Decimal = Decimal("0")
    quantity_pct: Decimal = Decimal("0")
    cost_abs: Decimal = Decimal("1.00")
    cost_pct: Decimal = Decimal("2")
    payment_abs: Decimal = Decimal("0.005")


@dataclass(frozen=True)
class LineItem:
    sku: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    currency: str
    source: str  # e.g. "purchase_order.csv:row 4"

    @property
    def total(self) -> Decimal:
        return self.quantity * self.unit_price


@dataclass(frozen=True)
class CostLine:
    category: str
    planned: Decimal
    actual: Decimal
    source: str


@dataclass
class Finding:
    order_id: str
    kind: FindingKind
    severity: Severity
    currency: str
    expected: Decimal
    actual: Decimal
    difference: Decimal  # always actual - expected
    explanation: str
    evidence: list[str]
    sku: str | None = None
    id: str = ""
    status: ReviewStatus = ReviewStatus.NEEDS_REVIEW

    @property
    def difference_pct(self) -> Decimal | None:
        if self.expected == 0:
            return None
        return self.difference / self.expected * _HUNDRED

    def to_dict(self) -> dict[str, object]:
        pct = self.difference_pct
        return {
            "id": self.id,
            "order_id": self.order_id,
            "kind": self.kind.value,
            "severity": self.severity.value,
            "sku": self.sku,
            "currency": self.currency,
            "expected": plain_money(self.expected),
            "actual": plain_money(self.actual),
            "difference": plain_money(self.difference),
            "difference_pct": None if pct is None else plain_money(pct),
            "evidence": list(self.evidence),
            "explanation": self.explanation,
            "status": self.status.value,
        }
