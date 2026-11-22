import json

from marginmesh.cli import main
from marginmesh.synthetic import generate_sample


def test_generate_sample_and_analyze(tmp_path, capsys):
    sample = tmp_path / "s"
    assert main(["generate-sample", "--out", str(sample), "--seed", "3"]) == 0
    out = tmp_path / "out"
    code = main(
        [
            "analyze",
            "--po", str(sample / "purchase_order.csv"),
            "--invoice", str(sample / "supplier_invoice.xlsx"),
            "--costing", str(sample / "costing_sheet.csv"),
            "--order-file", str(sample / "order.json"),
            "--out", str(out),
            "--formats", "json,md",
        ]
    )  # fmt: skip
    assert code == 0
    assert "need review" in capsys.readouterr().out
    report = json.loads((out / "ORD-2026-0001_report.json").read_text())
    assert report["summary"]["total_findings"] > 0
    assert not (out / "ORD-2026-0001_report.xlsx").exists()


def test_demo_command(tmp_path):
    assert main(["demo", "--out", str(tmp_path / "d")]) == 0
    assert (tmp_path / "d" / "reports" / "ORD-2026-0001_report.md").exists()


def test_analyze_without_costing_does_not_need_revenue(tmp_path):
    generate_sample(tmp_path, 1, ("csv",))
    code = main(
        [
            "analyze", "--order-id", "X1",
            "--po", str(tmp_path / "purchase_order.csv"),
            "--invoice", str(tmp_path / "supplier_invoice.csv"),
            "--out", str(tmp_path / "o"), "--formats", "json",
        ]
    )  # fmt: skip
    assert code == 0


def test_bad_input_returns_exit_code_2_with_message(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text("sku,quantity\nA,1\n")
    code = main(["analyze", "--order-id", "X", "--po", str(bad), "--invoice", str(bad)])
    assert code == 2
    assert "missing required column" in capsys.readouterr().err


def test_costing_without_revenue_is_a_clean_error(tmp_path, capsys):
    generate_sample(tmp_path, 1, ("csv",))
    code = main(
        [
            "analyze", "--order-id", "X",
            "--po", str(tmp_path / "purchase_order.csv"),
            "--invoice", str(tmp_path / "supplier_invoice.csv"),
            "--costing", str(tmp_path / "costing_sheet.csv"),
        ]
    )  # fmt: skip
    assert code == 2
    assert "revenue" in capsys.readouterr().err


def test_path_traversal_order_id_rejected(tmp_path, capsys):
    generate_sample(tmp_path, 1, ("csv",))
    code = main(
        [
            "analyze", "--order-id", "../evil",
            "--po", str(tmp_path / "purchase_order.csv"),
            "--invoice", str(tmp_path / "supplier_invoice.csv"),
        ]
    )  # fmt: skip
    assert code == 2
