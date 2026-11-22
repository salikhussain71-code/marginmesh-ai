import random
from decimal import Decimal

from marginmesh.models import FindingKind, Severity, Tolerance
from marginmesh.reconcile import reconcile


def kinds(findings):
    return sorted((f.sku, f.kind.value) for f in findings)


def test_docs_example_price_variance_300_and_6_percent(make_item):
    # PO: 1,000 units at 5.00; invoice: 1,000 units at 5.30 -> 300.00 (6%)
    f = reconcile("O1", [make_item("A", 1000, "5.00")], [make_item("A", 1000, "5.30")])
    assert len(f) == 1
    assert f[0].kind is FindingKind.PRICE_VARIANCE
    assert f[0].expected == Decimal("5000")
    assert f[0].actual == Decimal("5300")
    assert f[0].difference == Decimal("300")
    assert f[0].difference_pct == Decimal("6")
    assert f[0].severity is Severity.HIGH
    assert f[0].status.value == "needs_review"
    assert "po" not in f[0].evidence  # evidence are file:row references
    assert len(f[0].evidence) == 2


def test_identical_documents_produce_no_findings(make_item):
    items = [make_item("A", 10, "1.50"), make_item("B", 5, "2.00")]
    assert reconcile("O1", items, list(items)) == []


def test_missing_and_unordered(make_item):
    f = reconcile(
        "O1",
        [make_item("A", 10, "2"), make_item("B", 1, "1")],
        [make_item("A", 10, "2"), make_item("C", 3, "4")],
    )
    assert kinds(f) == [("B", "MISSING_ON_INVOICE"), ("C", "UNORDERED_ON_INVOICE")]
    missing = next(x for x in f if x.sku == "B")
    unordered = next(x for x in f if x.sku == "C")
    assert missing.difference == Decimal("-1")
    assert unordered.difference == Decimal("12")


def test_quantity_shortage_is_negative(make_item):
    f = reconcile("O1", [make_item("A", 100, "2")], [make_item("A", 90, "2")])
    assert f[0].kind is FindingKind.QUANTITY_VARIANCE
    assert f[0].difference == Decimal("-20")


def test_currency_mismatch_is_not_converted(make_item):
    f = reconcile("O1", [make_item("A", 1, "5", "USD")], [make_item("A", 1, "5", "EUR")])
    assert [x.kind for x in f] == [FindingKind.CURRENCY_MISMATCH]
    assert f[0].difference == 0


def test_duplicate_invoice_lines_are_combined_and_noted(make_item):
    f = reconcile(
        "O1",
        [make_item("A", 100, "2")],
        [make_item("A", 40, "2", source="i:row 2"), make_item("A", 60, "2", source="i:row 3")],
    )
    assert [x.kind for x in f] == [FindingKind.DUPLICATE_SKU_LINES]
    assert f[0].severity is Severity.INFO
    assert f[0].evidence == ["i:row 2", "i:row 3"]


def test_tolerance_suppresses_small_differences(make_item):
    po, inv = [make_item("A", 100, "10.00")], [make_item("A", 100, "10.04")]
    assert reconcile("O1", po, inv, Tolerance(unit_price_abs=Decimal("0.05"))) == []
    assert reconcile("O1", po, inv, Tolerance(unit_price_pct=Decimal("1"))) == []
    assert len(reconcile("O1", po, inv, Tolerance(unit_price_abs=Decimal("0.01")))) == 1


def test_price_and_quantity_effects_sum_exactly_to_total_difference(make_item):
    """Property test: price effect + quantity effect == invoice total - PO total."""
    rng = random.Random(2026)
    zero = Tolerance(Decimal(0), Decimal(0), Decimal(0), Decimal(0))
    checked = 0
    for _ in range(500):
        pq, pp = rng.randint(1, 5000), Decimal(rng.randint(1, 99999)) / 100
        iq, ip = rng.randint(1, 5000), Decimal(rng.randint(1, 99999)) / 100
        found = reconcile("O1", [make_item("A", pq, pp)], [make_item("A", iq, ip)], zero)
        total = sum((f.difference for f in found), Decimal(0))
        assert total == Decimal(iq) * ip - Decimal(pq) * pp
        checked += 1
    assert checked == 500


def test_price_effect_uses_invoice_quantity_and_quantity_effect_uses_po_price(make_item):
    f = reconcile("O1", [make_item("A", 100, "2")], [make_item("A", 110, "3")])
    by_kind = {x.kind: x for x in f}
    assert by_kind[FindingKind.PRICE_VARIANCE].difference == Decimal("110")  # (3-2)*110
    assert by_kind[FindingKind.QUANTITY_VARIANCE].difference == Decimal("20")  # (110-100)*2
