from decimal import Decimal

import pytest

from marginmesh.margin import compute_order_margin, margin_findings
from marginmesh.models import CostLine, FindingKind


def cl(cat, planned, actual):
    return CostLine(cat, Decimal(str(planned)), Decimal(str(actual)), "c.csv:row 2")


def test_docs_example_margin_erosion():
    # revenue 100,000; planned cost 70,000; actual 76,000 -> margin 30,000 -> 24,000
    m = compute_order_margin("O1", "USD", Decimal(100000), [cl("all", 70000, 76000)])
    assert m.planned_margin == Decimal(30000)
    assert m.actual_margin == Decimal(24000)
    assert m.margin_erosion == Decimal(6000)
    assert m.planned_margin_pct == Decimal(30)
    assert m.actual_margin_pct == Decimal(24)


def test_categories_are_grouped_case_insensitively():
    m = compute_order_margin(
        "O1", "USD", Decimal(1000), [cl("Fabric", 100, 120), cl(" fabric ", 50, 50)]
    )
    assert len(m.categories) == 1
    assert m.categories[0].planned == Decimal(150)
    assert m.categories[0].actual == Decimal(170)


def test_overrun_finding_respects_tolerance_and_ignores_underruns():
    m = compute_order_margin(
        "O1",
        "USD",
        Decimal(10000),
        [cl("a", 1000, 1015), cl("b", 1000, 1030), cl("c", 1000, 900)],
    )
    found = margin_findings(m)
    assert [f.kind for f in found] == [FindingKind.COST_OVERRUN]
    assert found[0].difference == Decimal(30)  # only 'b' exceeds 2%


def test_short_payment_finding():
    m = compute_order_margin("O1", "USD", Decimal(1000), [cl("a", 500, 500)], Decimal(985))
    assert m.short_payment == Decimal(15)
    assert m.realised_margin == Decimal(485)
    found = margin_findings(m)
    assert found[0].kind is FindingKind.SHORT_PAYMENT
    assert found[0].difference == Decimal(-15)


def test_no_short_payment_when_paid_in_full_or_more():
    m = compute_order_margin("O1", "USD", Decimal(1000), [cl("a", 500, 500)], Decimal(1000))
    assert margin_findings(m) == []


def test_invalid_revenue_or_received_rejected():
    with pytest.raises(ValueError):
        compute_order_margin("O1", "USD", Decimal(0), [cl("a", 1, 1)])
    with pytest.raises(ValueError):
        compute_order_margin("O1", "USD", Decimal(10), [cl("a", 1, 1)], Decimal(-1))
