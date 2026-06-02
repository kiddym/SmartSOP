"""泛化后 service：通用实体流 + procedure 草稿态钩子。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import tenant
from app.deps import RequestMeta
from app.models.maintenance_asset import Asset
from app.models.user import User
from app.services import attachment_service as svc

META = RequestMeta(ip_address="1.1.1.1", user_agent="t", request_id="r1")


def _super_user(db: Session, company_id: str) -> User:
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import UserStatus

    with tenant.bypass_tenant_scope():
        db.add(Company(id=company_id, name="C", slug=f"c-{company_id}"))
        role = Role(company_id=company_id, code="super_admin", name="管理员", permissions=[])
        db.add(role)
        db.flush()
        u = User(
            company_id=company_id, email=f"u@{company_id}.com", name="U",
            password_hash="x", role_id=role.id, status=UserStatus.active,
        )
        db.add(u)
        db.commit()
    return u


def test_generic_upload_list_download_update_delete(db: Session, storage_tmp) -> None:
    user = _super_user(db, "co-1")
    tenant.set_current_company_id("co-1")
    db.add(Asset(custom_id="A1", name="泵"))
    db.commit()
    aid = db.query(Asset).one().id

    att = svc.upload_for(
        db, user, "asset", aid, b"DATA", "手册.pdf",
        content_type="application/pdf", description="说明", meta=META,
    )
    db.commit()
    assert att.entity_type == "asset" and att.entity_id == aid

    rows = svc.list_for(db, user, "asset", aid)
    assert [r.id for r in rows] == [att.id]

    data, mime, name = svc.download_for(db, user, att.id)
    assert data == b"DATA" and name == "手册.pdf"

    svc.update_for(db, user, att.id, description="改", sort_order=2, meta=META)
    db.commit()
    assert svc.get_or_404(db, att.id).description == "改"

    svc.delete_for(db, user, att.id, meta=META)
    db.commit()
    assert svc.list_for(db, user, "asset", aid) == []


def test_procedure_write_guard_still_enforced(db: Session, storage_tmp, factory) -> None:
    """非草稿 procedure 上传附件 → PROCEDURE_READONLY（write_guard 经 resolve 触发）。"""
    folder = factory.folder(prefix="QC")
    proc = factory.procedure(folder_id=folder.id, status="PUBLISHED", is_current=True)
    with pytest.raises(HTTPException) as ei:
        svc.upload_for(
            db, None, "procedure", proc.id, b"x", "a.txt",
            content_type="text/plain", description="", meta=META,
        )
    assert ei.value.detail["code"] == "PROCEDURE_READONLY"
