"""Command-line interface: ``marginmesh analyze | generate-sample | demo``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from marginmesh import __version__
from marginmesh.analysis import OrderInfo, analyze_order
from marginmesh.ingest import IngestError, parse_costing, parse_line_items, to_decimal
from marginmesh.models import Tolerance, fmt_money
from marginmesh.report import FORMATS, write_reports
from marginmesh.synthetic import generate_sample


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="marginmesh",
        description="Reconcile export-order documents and analyse order margin.",
    )
    parser.add_argument("--version", action="version", version=f"marginmesh {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    a = sub.add_parser("analyze", help="analyse one order")
    a.add_argument("--po", required=True, help="purchase order (.csv/.xlsx)")
    a.add_argument("--invoice", required=True, help="supplier invoice (.csv/.xlsx)")
    a.add_argument("--costing", help="costing sheet (.csv/.xlsx); enables margin analysis")
    a.add_argument("--order-file", help="order.json with order_id, currency, revenue, received")
    a.add_argument("--order-id")
    a.add_argument("--currency")
    a.add_argument("--buyer")
    a.add_argument("--revenue", help="order revenue (required with --costing)")
    a.add_argument("--received", help="amount actually received from the buyer")
    a.add_argument("--out", default="marginmesh-output", help="output directory")
    a.add_argument("--formats", default=",".join(FORMATS), help="comma list of json,md,csv,xlsx")

    g = sub.add_parser("generate-sample", help="write synthetic sample data")
    g.add_argument("--out", default="data/sample")
    g.add_argument("--seed", type=int, default=42)

    d = sub.add_parser("demo", help="generate synthetic data and analyse it")
    d.add_argument("--out", default="marginmesh-demo")
    d.add_argument("--seed", type=int, default=42)
    return parser


def _order_from_args(args: argparse.Namespace) -> OrderInfo:
    data: dict = {}
    if args.order_file:
        try:
            data = json.loads(Path(args.order_file).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IngestError(f"cannot read order file: {exc}") from exc
        if not isinstance(data, dict):
            raise IngestError("order file must contain a JSON object")

    def pick(flag: object, key: str) -> object:
        return flag if flag is not None else data.get(key)

    order_id = pick(args.order_id, "order_id")
    if not order_id:
        raise IngestError("order id is required (--order-id or order.json)")
    revenue = pick(args.revenue, "revenue")
    received = pick(args.received, "received")
    return OrderInfo(
        order_id=str(order_id),
        currency=str(pick(args.currency, "currency") or "USD").upper(),
        buyer=pick(args.buyer, "buyer") or None,  # type: ignore[arg-type]
        revenue=None if revenue is None else to_decimal(revenue, "revenue", "order"),
        received=None if received is None else to_decimal(received, "received", "order"),
    )


def _run_analysis(args: argparse.Namespace) -> int:
    formats = tuple(f.strip() for f in args.formats.split(",") if f.strip())
    order = _order_from_args(args)
    po = parse_line_items(args.po, order.currency)
    invoice = parse_line_items(args.invoice, order.currency)
    costing = parse_costing(args.costing) if args.costing else None
    result = analyze_order(order, po, invoice, costing, Tolerance())
    written = write_reports(result, args.out, formats)

    rec = result.reconciliation
    print(f"Order {order.order_id}: {len(result.findings)} finding(s) need review")
    print(
        f"  PO total {fmt_money(rec.po_total)} | invoice total {fmt_money(rec.invoice_total)} "
        f"| net {fmt_money(rec.net_difference)} {rec.currency}"
    )
    if result.margin:
        m = result.margin
        print(
            f"  Margin: planned {m.planned_margin_pct:.2f}% -> actual {m.actual_margin_pct:.2f}% "
            f"(erosion {fmt_money(m.margin_erosion)} {m.currency})"
        )
    for path in written:
        print(f"  wrote {path}")
    print("  Reminder: findings are potential discrepancies, not confirmed losses.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "generate-sample":
            truth = generate_sample(args.out, args.seed)
            print(f"Wrote synthetic sample (seed {truth['seed']}) to {args.out}")
            return 0
        if args.command == "demo":
            sample = Path(args.out) / "sample"
            generate_sample(sample, args.seed)
            args = argparse.Namespace(
                po=str(sample / "purchase_order.csv"),
                invoice=str(sample / "supplier_invoice.csv"),
                costing=str(sample / "costing_sheet.csv"),
                order_file=str(sample / "order.json"),
                order_id=None,
                currency=None,
                buyer=None,
                revenue=None,
                received=None,
                out=str(Path(args.out) / "reports"),
                formats=",".join(FORMATS),
            )
        return _run_analysis(args)
    except (IngestError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
