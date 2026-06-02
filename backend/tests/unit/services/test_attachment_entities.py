"""entity registry + resolve_and_authorize 单测。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import tenant
from app.models.maintenance_asset import Asset
from app.models.user import User, UserStatus
from app.services import attachment_entities as ae


def _company_user(db: Session, company_id: str) -> User:
    """构造一个带 super_admin 角色的 user。"""
    from app.models.company import Company
    from app.models.role import Role

    with tenant.bypass_tenant_scope():
        db.add(Company(id=company_id, name="C", slug=f"c-{company_id}"))
        role = Role(company_id=company_id, code="super_admin", name="管理员", permissions=[])
        db.add(role)
        db.flush()
        user = User(
            company_id=company_id,
            email=f"u@{company_id}.com",
            name="U",
            password_hash="x",
            role_id=role.id,
            status=UserStatus.active,
        )
        db.add(user)
        db.commit()
    return user


def test_unknown_entity_type_400(db: Session) -> None:
    user = _company_user(db, "co-1")
    tenant.set_current_company_id("co-1")
    with pytest.raises(HTTPException) as ei:
        ae.resolve_and_authorize(db, user, "ghost_type", "x", "read")
    assert ei.value.status_code == 400


def test_missing_host_404(db: Session) -> None:
    user = _company_user(db, "co-1")
    tenant.set_current_company_id("co-1")
    with pytest.raises(HTTPException) as ei:
        ae.resolve_and_authorize(db, user, "asset", "ghost", "read")
    assert ei.value.status_code == 404


def test_cross_tenant_host_404(db: Session) -> None:
    a = _company_user(db, "co-a")
    _company_user(db, "co-b")
    tenant.set_current_company_id("co-a")
    db.add(Asset(custom_id="A1", name="泵"))
    db.commit()
    asset_id = db.query(Asset).one().id
    tenant.set_current_company_id("co-b")
    b = db.query(User).filter(User.company_id == "co-b").one()
    with pytest.raises(HTTPException) as ei:
        ae.resolve_and_authorize(db, b, "asset", asset_id, "read")
    assert ei.value.status_code == 404
    tenant.set_current_company_id("co-a")
    host = ae.resolve_and_authorize(db, a, "asset", asset_id, "read")
    assert host.id == asset_id


def test_write_permission_denied_403(db: Session) -> None:
    from app.models.role import Role

    user = _company_user(db, "co-1")
    tenant.set_current_company_id("co-1")
    db.add(Asset(custom_id="A1", name="泵"))
    db.commit()
    asset_id = db.query(Asset).one().id
    with tenant.bypass_tenant_scope():
        role = db.get(Role, user.role_id)
        role.code = "viewer"
        role.permissions = ["asset.view"]
        db.commit()
    with pytest.raises(HTTPException) as ei:
        ae.resolve_and_authorize(db, user, "asset", asset_id, "write")
    assert ei.value.status_code == 403
    assert ae.resolve_and_authorize(db, user, "asset", asset_id, "read").id == asset_id


def test_procedure_resolve_bypasses_tenant_and_skips_rbac(db: Session, factory) -> None:
    """procedure：company_id 为 NULL，即使设了租户上下文也能 bypass 查到；perms None，user=None 不抛 403。"""
    folder = factory.folder(prefix="QC")
    proc = factory.procedure(folder_id=folder.id, status="DRAFT", is_current=True)
    tenant.set_current_company_id("co-x")  # 与 proc.company_id(None) 不一致
    host = ae.resolve_and_authorize(db, None, "procedure", proc.id, "read")
    assert host.id == proc.id
    # write 且当前草稿 → write_guard 通过
    assert ae.resolve_and_authorize(db, None, "procedure", proc.id, "write").id == proc.id


def test_procedure_write_guard_blocks_non_draft(db: Session, factory) -> None:
    """非当前草稿 procedure 的 write 解析触发 write_guard → PROCEDURE_READONLY(400)。"""
    folder = factory.folder(prefix="QC")
    proc = factory.procedure(folder_id=folder.id, status="PUBLISHED", is_current=True)
    with pytest.raises(HTTPException) as ei:
        ae.resolve_and_authorize(db, None, "procedure", proc.id, "write")
    assert ei.value.status_code == 400
    assert ei.value.detail["code"] == "PROCEDURE_READONLY"
