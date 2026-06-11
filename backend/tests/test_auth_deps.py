import pytest
from fastapi import HTTPException, Request

from app import deps, security, tenant
from app.schemas.auth import RegisterRequest
from app.services import auth_service


def _request(method: str = "POST") -> Request:
    """构造一个最小 ASGI Request，供直接调用 get_current_user 的单元测试使用。"""
    return Request({"type": "http", "method": method, "headers": []})


def _register(db):
    return auth_service.register(
        db, RegisterRequest(company_name="Acme", email="a@acme.com", password="secret123", name="A")
    )


def test_get_current_user_sets_context(db):
    user = _register(db)
    token = security.create_access_token(
        user_id=user.id, company_id=user.company_id, role_code="super_admin"
    )
    try:
        loaded = deps.get_current_user(_request(), token=token, db=db)
        assert loaded.id == user.id
        assert tenant.get_current_company_id() == user.company_id
    finally:
        tenant.set_current_company_id(None)


def test_get_current_user_bad_token_401(db):
    with pytest.raises(HTTPException) as exc:
        deps.get_current_user(_request(), token="garbage", db=db)
    assert exc.value.status_code == 401


def test_require_permission_allows_super_admin(db):
    user = _register(db)
    tenant.set_current_company_id(user.company_id)
    try:
        checker = deps.require_permission("user.create")
        assert checker(current_user=user, db=db).id == user.id
    finally:
        tenant.set_current_company_id(None)


def test_require_permission_denies_viewer(db):
    from sqlalchemy import select

    from app.models.role import Role

    user = _register(db)
    tenant.set_current_company_id(user.company_id)
    try:
        viewer = db.execute(select(Role).where(Role.code == "viewer")).scalar_one()
        user.role_id = viewer.id
        db.commit()
        with pytest.raises(HTTPException) as exc:
            deps.require_permission("user.create")(current_user=user, db=db)
        assert exc.value.status_code == 403
    finally:
        tenant.set_current_company_id(None)
