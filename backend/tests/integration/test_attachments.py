"""附件端点集成测试（api-specification §5.5）。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import tenant
from app.models.attachment import Attachment

pytestmark = pytest.mark.usefixtures("_sop_auth")

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


def test_uploaded_attachment_derives_company_from_host_not_ambient(
    client: TestClient, db: Session, storage_tmp: Path, _sop_auth: str
) -> None:
    """附件 company_id 须显式取自宿主，而非依赖 ambient tenant 上下文。

    procedure 宿主解析走 bypass。即便 ambient 上下文是另一家公司，附件归属也应随
    宿主（_sop_auth 公司）——验证 upload_for 显式落宿主 company_id 而非靠自动盖值。
    """
    from app.deps import RequestMeta
    from app.models.company import Company
    from app.services import attachment_service

    pid = _make_procedure(client)  # 宿主 procedure 属 _sop_auth 公司
    with tenant.bypass_tenant_scope():
        other = Company(name="OtherCo", slug="other-co")
        db.add(other)
        db.commit()

    meta = RequestMeta(ip_address="", user_agent="", request_id="-")
    token = tenant.set_current_company_id(other.id)  # ambient = 另一家公司
    try:
        att = attachment_service.upload_for(
            db,
            None,
            "procedure",
            pid,
            b"PDFDATA",
            "报告.pdf",
            content_type="application/pdf",
            description="",
            meta=meta,
        )
        db.flush()
        att_id = att.id
    finally:
        tenant.reset_current_company_id(token)
    with tenant.bypass_tenant_scope():
        row = db.execute(select(Attachment).where(Attachment.id == att_id)).scalar_one()
    assert row.company_id == _sop_auth  # 随宿主，而非 ambient(other)


def test_download_forces_attachment(client: TestClient, storage_tmp: Path) -> None:
    pid = _make_procedure(client)
    att = client.post(
        f"{PROC}/{pid}/attachments",
        files=[("files", ("数据.bin", b"\x00\x01\x02", "application/octet-stream"))],
    ).json()[0]
    resp = client.get(f"/api/v1/attachments/{att['id']}/download")
    assert resp.status_code == 200
    assert resp.content == b"\x00\x01\x02"
    assert resp.headers["content-disposition"].startswith("attachment")


def test_preview_whitelist_and_415(client: TestClient, storage_tmp: Path) -> None:
    pid = _make_procedure(client)
    png = client.post(
        f"{PROC}/{pid}/attachments",
        files=[("files", ("p.png", b"img", "image/png"))],
    ).json()[0]
    ok = client.get(f"/api/v1/attachments/{png['id']}/preview")
    assert ok.status_code == 200
    assert ok.headers["content-disposition"] == "inline"

    txt = client.post(
        f"{PROC}/{pid}/attachments",
        files=[("files", ("n.txt", b"hi", "text/plain"))],
    ).json()[0]
    blocked = client.get(f"/api/v1/attachments/{txt['id']}/preview")
    assert blocked.status_code == 415
    assert blocked.json()["detail"]["code"] == "ATTACHMENT_NOT_PREVIEWABLE"


def test_update_and_delete(client: TestClient, storage_tmp: Path) -> None:
    pid = _make_procedure(client)
    att = client.post(
        f"{PROC}/{pid}/attachments",
        files=[("files", ("a.txt", b"hi", "text/plain"))],
    ).json()[0]

    upd = client.put(f"/api/v1/attachments/{att['id']}", json={"description": "改了"})
    assert upd.status_code == 200
    assert upd.json()["description"] == "改了"

    dele = client.delete(f"/api/v1/attachments/{att['id']}")
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
