"""End-to-end accuracy check against injected, known discrepancies."""

import json
from decimal import Decimal

import pytest

from marginmesh.analysis import OrderInfo, analyze_order
from marginmesh.ingest import parse_costing, parse_line_items
from marginmesh.models import FindingKind
from marginmesh.synthetic import generate_sample

RECON = {
    FindingKind.PRICE_VARIANCE.value,
    FindingKind.QUANTITY_VARIANCE.value,
    FindingKind.MISSING_ON_INVOICE.value,
    FindingKind.UNORDERED_ON_INVOICE.value,
    FindingKind.DUPLICATE_SKU_LINES.value,
}


def run(folder, ext="csv"):
    spec = json.loads((folder / "order.json").read_text())
    order = OrderInfo(
        spec["order_id"], spec["currency"], spec["buyer"],
        Decimal(spec["revenue"]), Decimal(spec["received"]),
    )  # fmt: skip
    return analyze_order(
        order,
        parse_line_items(folder / f"purchase_order.{ext}"),
        parse_line_items(folder / f"supplier_invoice.{ext}"),
        parse_costing(folder / f"costing_sheet.{ext}"),
    )


CASES = [(seed, "csv") for seed in range(1, 26)] + [(seed, "xlsx") for seed in range(1, 6)]


@pytest.mark.parametrize(("seed", "ext"), CASES)
def test_every_injected_discrepancy_is_found_and_nothing_else(tmp_path, seed, ext):
    truth = generate_sample(tmp_path, seed)
    result = run(tmp_path, ext)

    found = sorted({(f.sku, f.kind.value) for f in result.findings if f.kind.value in RECON})
    expected = sorted((e["sku"], e["kind"]) for e in truth["reconciliation"])
    assert found == expected  # 100% recall, 0 false positives on the synthetic set

    overruns = {
        f.explanation.split("'")[1] for f in result.findings if f.kind is FindingKind.COST_OVERRUN
    }
    assert set(truth["cost_overruns"]) <= overruns
    assert overruns <= set(truth["cost_overruns"]) | {"materials"}
    assert any(f.kind is FindingKind.SHORT_PAYMENT for f in result.findings)


def test_generation_is_deterministic(tmp_path):
    generate_sample(tmp_path / "a", 7, ("csv",))
    generate_sample(tmp_path / "b", 7, ("csv",))
    for name in ["purchase_order.csv", "supplier_invoice.csv", "costing_sheet.csv", "order.json"]:
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_different_seeds_differ(tmp_path):
    generate_sample(tmp_path / "a", 1, ("csv",))
    generate_sample(tmp_path / "b", 2, ("csv",))
    assert (tmp_path / "a/purchase_order.csv").read_bytes() != (
        tmp_path / "b/purchase_order.csv"
    ).read_bytes()
