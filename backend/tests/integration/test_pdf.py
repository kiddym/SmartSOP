"""PDF 端点集成测试（api-specification §5.2 / pdf-rendering §13 / §59）。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.usefixtures("_sop_auth")

PROC = "/api/v1/procedures"
FOLDER = "/api/v1/folders"


def _make_procedure(client: TestClient) -> str:
    leaf = client.post(FOLDER, json={"name": "质检", "prefix": "QC"}).json()["id"]
    resp = client.post(
        PROC, json={"folder_id": leaf, "name": "启动 SOP", "level_of_use": "continuous"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_pdf_download_returns_pdf(client: TestClient) -> None:
    pid = _make_procedure(client)
    resp = client.get(f"{PROC}/{pid}/pdf-download")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF-")
    cd = resp.headers["content-disposition"]
    assert "QC-00001_Rev1.pdf" in cd


def test_pdf_download_debug_returns_layout(client: TestClient) -> None:
    pid = _make_procedure(client)
    resp = client.get(f"{PROC}/{pid}/pdf-download", params={"debug": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert "total_pages" in body
    assert body["debug"] is not None


def test_pdf_layout_shape(client: TestClient) -> None:
    pid = _make_procedure(client)
    resp = client.get(f"{PROC}/{pid}/pdf-layout")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_pages"] >= 4
    assert "cover" in body["sections"]
    assert "toc" in body["sections"]
    assert len(body["page_labels"]) == body["total_pages"]
    assert body["page_labels"][0] == ""  # 封面无页码


def test_pdf_layout_matches_download_debug(client: TestClient) -> None:
    """pdf-layout 与 pdf-download 同引擎，页码一致（§59.3）。"""
    pid = _make_procedure(client)
    layout = client.get(f"{PROC}/{pid}/pdf-layout").json()
    dbg = client.get(f"{PROC}/{pid}/pdf-download", params={"debug": 1}).json()
    assert layout["total_pages"] == dbg["total_pages"]
    assert layout["page_labels"] == dbg["page_labels"]


def test_pdf_not_found(client: TestClient) -> None:
    resp = client.get(f"{PROC}/no-such-id/pdf-layout")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "PROCEDURE_NOT_FOUND"


def test_pdf_download_not_found(client: TestClient) -> None:
    resp = client.get(f"{PROC}/no-such-id/pdf-download")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "PROCEDURE_NOT_FOUND"
