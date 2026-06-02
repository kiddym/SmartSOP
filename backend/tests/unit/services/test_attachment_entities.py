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
