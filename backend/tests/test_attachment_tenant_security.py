"""附件跨租户越权回归（审计 #1 匿名别名 / #2 跨租户下载）。"""
from __future__ import annotations

import io
import uuid

import pytest
from fastapi import HTTPException

from app import tenant
from app.models.attachment import Attachment
from app.models.procedure import Procedure
from app.models.user import User
from app.services import attachment_entities as entities


def _proc(db, company_id: str) -> Procedure:
    with tenant.bypass_tenant_scope():
        proc = Procedure(
            procedure_group_id=str(uuid.uuid4()),
            folder_id=str(uuid.uuid4()),
            code="QC-00001",
            name="P",
            level_of_use="reference",
            version=1,
            status="DRAFT",
            is_current=True,
            company_id=company_id,
        )
        db.add(proc)
        db.commit()
    return proc


def _user(company_id: str) -> User:
    return User(email="x@x.com", name="X", password_hash="x", company_id=company_id)


def test_resolve_rejects_cross_tenant_procedure(db):
    proc = _proc(db, "company-B")
    with pytest.raises(HTTPException) as ei:
        entities.resolve_and_authorize(db, _user("company-A"), "procedure", proc.id, "read")
    assert ei.value.status_code == 404


def test_resolve_allows_same_tenant_procedure(db):
    proc = _proc(db, "company-B")
    host = entities.resolve_and_authorize(db, _user("company-B"), "procedure", proc.id, "read")
    assert host.id == proc.id


def test_anonymous_procedure_attachment_upload_401(client):
    pid = "00000000-0000-0000-0000-000000000000"
    r = client.post(
        f"/api/v1/procedures/{pid}/attachments",
        files={"files": ("a.txt", io.BytesIO(b"hi"), "text/plain")},
    )
    assert r.status_code == 401


def test_anonymous_procedure_attachment_list_401(client):
    pid = "00000000-0000-0000-0000-000000000000"
    r = client.get(f"/api/v1/procedures/{pid}/attachments")
    assert r.status_code == 401


def _register(client, company, email):
    r = client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_cross_tenant_attachment_download_404(client, db):
    """审计 #2 端到端：A 公司认证用户用 B 公司附件 id 下载 → 404（而非泄漏字节）。"""
    token_a = _register(client, "Acme", "a@acme.com")
    with tenant.bypass_tenant_scope():
        proc = Procedure(
            procedure_group_id=str(uuid.uuid4()),
            folder_id=str(uuid.uuid4()),
            code="QC-00002",
            name="B-proc",
            level_of_use="reference",
            version=1,
            status="DRAFT",
            is_current=True,
            company_id="company-B",
        )
        db.add(proc)
        db.flush()
        att = Attachment(
            company_id="company-B",
            entity_type="procedure",
            entity_id=proc.id,
            file_name="secret.bin",
            storage_path="company-B/secret.bin",
            mime_type="application/octet-stream",
            file_type="OTHER",
            size_bytes=3,
        )
        db.add(att)
        db.commit()
        att_id = att.id
    r = client.get(f"/api/v1/attachments/{att_id}/download", headers=_h(token_a))
    assert r.status_code == 404
