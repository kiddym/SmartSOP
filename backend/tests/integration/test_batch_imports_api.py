"""批次 API 端到端：建批次 → 后台解析 → 查询 review 态 + blob。"""

from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app import tenant
from app.deps import get_current_user
from app.main import app
from app.models.user import User
from app.services import batch_parse_service, upload_service


def _docx() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", "<document/>")
    return buf.getvalue()


@pytest.fixture
def auth_client(client: TestClient):
    fake = User(id="u-1", email="t@e.com", name="测试", password_hash="x", company_id="co-1")
    app.dependency_overrides[get_current_user] = lambda: fake
    tenant.set_current_company_id("co-1")
    yield client
    app.dependency_overrides.pop(get_current_user, None)


def test_create_then_parse_then_review(
    auth_client: TestClient, engine: Engine, storage_tmp, factory, monkeypatch
) -> None:
    folder = factory.folder(name="目标", prefix="QC")
    token = upload_service.save_upload(_docx(), "a.docx").upload_token

    resp = auth_client.post(
        "/api/v1/batch-imports",
        json={
            "folder_id": folder.id,
            "parse_mode": "smart",
            "items": [{"filename": "a.docx", "upload_token": token}],
        },
    )
    assert resp.status_code == 201
    job_id = resp.json()["id"]

    from app.parser.result import ParseMetadata, ParseResult

    monkeypatch.setattr(batch_parse_service, "_read_docx", lambda item: b"x")
    monkeypatch.setattr(
        batch_parse_service,
        "_parse",
        lambda data, mode: ParseResult(
            metadata=ParseMetadata(
                total_chapters=1,
                image_count=0,
                table_count=0,
                body_start_index=0,
                body_start_detected_by="t",
            ),
            chapters=[],
            parse_method="smart",
        ),
    )
    with Session(engine, expire_on_commit=False) as worker_db:
        batch_parse_service.run_parse_once(worker_db, max_items=10)

    items = auth_client.get(f"/api/v1/batch-imports/{job_id}/items").json()
    assert len(items) == 1
    assert items[0]["status"] == "review"
    assert items[0]["summary"]["chapter_count"] == 1

    item_id = items[0]["id"]
    blob = auth_client.get(f"/api/v1/batch-imports/{job_id}/items/{item_id}/parse-result").json()
    assert blob["parse_method"] == "smart"
    assert blob["metadata"]["total_chapters"] == 1
