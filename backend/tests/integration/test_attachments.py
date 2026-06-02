"""附件端点集成测试（api-specification §5.5）。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

PROC = "/api/v1/procedures"
FOLDER = "/api/v1/folders"


def _auth(client: TestClient) -> dict[str, str]:
    tok = client.post("/api/v1/auth/register", json={
        "company_name": "Acme", "email": "a@acme.com", "password": "secret123", "name": "A",
    }).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def _make_procedure(client: TestClient) -> str:
    leaf = client.post(FOLDER, json={"name": "叶子", "prefix": "QC"}).json()["id"]
    resp = client.post(
        PROC, json={"folder_id": leaf, "name": "启动 SOP", "level_of_use": "continuous"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_upload_list_and_detail(client: TestClient, storage_tmp: Path) -> None:
    pid = _make_procedure(client)
    resp = client.post(
        f"{PROC}/{pid}/attachments",
        files=[("files", ("报告.pdf", b"PDFDATA", "application/pdf"))],
        data={"description": "季度报告"},
    )
    assert resp.status_code == 201, resp.text
    att = resp.json()[0]
    assert att["file_name"] == "报告.pdf"
    assert att["description"] == "季度报告"
    assert att["procedure_id"] == att["entity_id"]

    listed = client.get(f"{PROC}/{pid}/attachments").json()
    assert [a["id"] for a in listed] == [att["id"]]

    detail = client.get(f"{PROC}/{pid}").json()
    assert [a["id"] for a in detail["attachments"]] == [att["id"]]


def test_download_forces_attachment(client: TestClient, storage_tmp: Path) -> None:
    pid = _make_procedure(client)
    att = client.post(
        f"{PROC}/{pid}/attachments",
        files=[("files", ("数据.bin", b"\x00\x01\x02", "application/octet-stream"))],
    ).json()[0]
    h = _auth(client)
    resp = client.get(f"/api/v1/attachments/{att['id']}/download", headers=h)
    assert resp.status_code == 200
    assert resp.content == b"\x00\x01\x02"
    assert resp.headers["content-disposition"].startswith("attachment")


def test_preview_whitelist_and_415(client: TestClient, storage_tmp: Path) -> None:
    pid = _make_procedure(client)
    png = client.post(
        f"{PROC}/{pid}/attachments",
        files=[("files", ("p.png", b"img", "image/png"))],
    ).json()[0]
    h = _auth(client)
    ok = client.get(f"/api/v1/attachments/{png['id']}/preview", headers=h)
    assert ok.status_code == 200
    assert ok.headers["content-disposition"] == "inline"

    txt = client.post(
        f"{PROC}/{pid}/attachments",
        files=[("files", ("n.txt", b"hi", "text/plain"))],
    ).json()[0]
    blocked = client.get(f"/api/v1/attachments/{txt['id']}/preview", headers=h)
    assert blocked.status_code == 415
    assert blocked.json()["detail"]["code"] == "ATTACHMENT_NOT_PREVIEWABLE"


def test_update_and_delete(client: TestClient, storage_tmp: Path) -> None:
    pid = _make_procedure(client)
    att = client.post(
        f"{PROC}/{pid}/attachments",
        files=[("files", ("a.txt", b"hi", "text/plain"))],
    ).json()[0]

    h = _auth(client)
    upd = client.put(f"/api/v1/attachments/{att['id']}", json={"description": "改了"}, headers=h)
    assert upd.status_code == 200
    assert upd.json()["description"] == "改了"

    dele = client.delete(f"/api/v1/attachments/{att['id']}", headers=h)
    assert dele.status_code == 204
    assert client.get(f"{PROC}/{pid}/attachments").json() == []


def test_upload_to_missing_procedure_404(client: TestClient, storage_tmp: Path) -> None:
    resp = client.post(
        f"{PROC}/ghost/attachments",
        files=[("files", ("a.txt", b"hi", "text/plain"))],
    )
    assert resp.status_code == 404


def test_upload_multiple_files_returns_list(client: TestClient, storage_tmp: Path) -> None:
    pid = _make_procedure(client)
    resp = client.post(
        f"{PROC}/{pid}/attachments",
        files=[
            ("files", ("a.pdf", b"AAA", "application/pdf")),
            ("files", ("b.png", b"BBB", "image/png")),
        ],
        data={"description": "批量"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert isinstance(body, list) and len(body) == 2
    assert {a["file_name"] for a in body} == {"a.pdf", "b.png"}
    assert all(a["entity_type"] == "procedure" and a["entity_id"] == pid for a in body)
    # 列表端点应见到这 2 个
    listed = client.get(f"{PROC}/{pid}/attachments").json()
    assert {a["file_name"] for a in listed} == {"a.pdf", "b.png"}
