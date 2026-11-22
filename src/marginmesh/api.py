"""Optional local HTTP API (install with ``pip install -e ".[api]"``).

This is a local prototype: it has NO authentication and must not be exposed to the internet.
"""

import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from marginmesh import __version__
from marginmesh.analysis import OrderInfo, analyze_order
from marginmesh.ingest import IngestError, parse_costing, parse_line_items, to_decimal
from marginmesh.report import build_report

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_SUFFIXES = {".csv", ".xlsx"}

app = FastAPI(title="MarginMesh AI", version=__version__)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


async def _save(upload: UploadFile, directory: Path, stem: str) -> Path:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(422, f"{stem}: only .csv and .xlsx files are accepted")
    data = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"{stem}: file larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    path = directory / f"{stem}{suffix}"  # server-chosen name: never trust client filenames
    path.write_bytes(data)
    return path


@app.post("/v1/analyze")
async def analyze(
    order_id: str = Form(...),
    currency: str = Form("USD"),
    revenue: Optional[str] = Form(None),
    received: Optional[str] = Form(None),
    po: UploadFile = File(...),
    invoice: UploadFile = File(...),
    costing: Optional[UploadFile] = File(None),
) -> dict:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            po_path = await _save(po, directory, "purchase_order")
            inv_path = await _save(invoice, directory, "supplier_invoice")
            cost_path = await _save(costing, directory, "costing_sheet") if costing else None
            order = OrderInfo(
                order_id=order_id,
                currency=currency.upper(),
                revenue=None if not revenue else to_decimal(revenue, "revenue", "form"),
                received=None if not received else to_decimal(received, "received", "form"),
            )
            result = analyze_order(
                order,
                parse_line_items(po_path, order.currency),
                parse_line_items(inv_path, order.currency),
                parse_costing(cost_path) if cost_path else None,
            )
    except (IngestError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return build_report(result)
