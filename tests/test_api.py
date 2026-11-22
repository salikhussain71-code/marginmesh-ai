import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("multipart")

from fastapi.testclient import TestClient  # noqa: E402

from marginmesh.api import app  # noqa: E402
from marginmesh.synthetic import generate_sample  # noqa: E402

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_analyze_endpoint(tmp_path):
    generate_sample(tmp_path, 5, ("csv",))
    files = {
        "po": ("anything.csv", (tmp_path / "purchase_order.csv").read_bytes()),
        "invoice": ("x.csv", (tmp_path / "supplier_invoice.csv").read_bytes()),
        "costing": ("y.csv", (tmp_path / "costing_sheet.csv").read_bytes()),
    }
    data = {"order_id": "API-1", "revenue": "108000.00", "received": "106000.00"}
    response = client.post("/v1/analyze", data=data, files=files)
    assert response.status_code == 200
    body = response.json()
    assert body["order"]["order_id"] == "API-1"
    assert body["summary"]["total_findings"] > 0


def test_rejects_wrong_extension_and_bad_content(tmp_path):
    files = {"po": ("a.exe", b"x"), "invoice": ("b.csv", b"sku,quantity\nA,1\n")}
    assert client.post("/v1/analyze", data={"order_id": "A"}, files=files).status_code == 422
    files = {"po": ("a.csv", b"sku,quantity\nA,1\n"), "invoice": ("b.csv", b"x")}
    assert client.post("/v1/analyze", data={"order_id": "A"}, files=files).status_code == 422


def test_rejects_path_like_order_id(tmp_path):
    generate_sample(tmp_path, 5, ("csv",))
    files = {
        "po": ("a.csv", (tmp_path / "purchase_order.csv").read_bytes()),
        "invoice": ("b.csv", (tmp_path / "supplier_invoice.csv").read_bytes()),
    }
    assert client.post("/v1/analyze", data={"order_id": "../x"}, files=files).status_code == 422
