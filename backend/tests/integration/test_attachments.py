"""附件端点集成测试（api-specification §5.5）。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

PROC = "/api/v1/procedures"
FOLDER = "/api/v1/folders"


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
        files={"file": ("报告.pdf", b"PDFDATA", "application/pdf")},
        data={"description": "季度报告"},
    )
    assert resp.status_code == 201, resp.text
    att = resp.json()
    assert att["file_name"] == "报告.pdf"
    assert att["description"] == "季度报告"

    listed = client.get(f"{PROC}/{pid}/attachments").json()
    assert [a["id"] for a in listed] == [att["id"]]

    detail = client.get(f"{PROC}/{pid}").json()
    assert [a["id"] for a in detail["attachments"]] == [att["id"]]


def test_download_forces_attachment(client: TestClient, storage_tmp: Path) -> None:
    pid = _make_procedure(client)
    att = client.post(
        f"{PROC}/{pid}/attachments",
        files={"file": ("数据.bin", b"\x00\x01\x02", "application/octet-stream")},
    ).json()
    resp = client.get(f"/api/v1/attachments/{att['id']}/download")
    assert resp.status_code == 200
    assert resp.content == b"\x00\x01\x02"
    assert resp.headers["content-disposition"].startswith("attachment")


def test_preview_whitelist_and_415(client: TestClient, storage_tmp: Path) -> None:
    pid = _make_procedure(client)
    png = client.post(
        f"{PROC}/{pid}/attachments",
        files={"file": ("p.png", b"img", "image/png")},
    ).json()
    ok = client.get(f"/api/v1/attachments/{png['id']}/preview")
    assert ok.status_code == 200
    assert ok.headers["content-disposition"] == "inline"

    txt = client.post(
        f"{PROC}/{pid}/attachments",
        files={"file": ("n.txt", b"hi", "text/plain")},
    ).json()
    blocked = client.get(f"/api/v1/attachments/{txt['id']}/preview")
    assert blocked.status_code == 415
    assert blocked.json()["detail"]["code"] == "ATTACHMENT_NOT_PREVIEWABLE"


def test_update_and_delete(client: TestClient, storage_tmp: Path) -> None:
    pid = _make_procedure(client)
    att = client.post(
        f"{PROC}/{pid}/attachments",
        files={"file": ("a.txt", b"hi", "text/plain")},
    ).json()

    upd = client.put(f"/api/v1/attachments/{att['id']}", json={"description": "改了"})
    assert upd.status_code == 200
    assert upd.json()["description"] == "改了"

    dele = client.delete(f"/api/v1/attachments/{att['id']}")
    assert dele.status_code == 204
    assert client.get(f"{PROC}/{pid}/attachments").json() == []


def test_upload_to_missing_procedure_404(client: TestClient, storage_tmp: Path) -> None:
    resp = client.post(
        f"{PROC}/ghost/attachments",
        files={"file": ("a.txt", b"hi", "text/plain")},
    )
    assert resp.status_code == 404
