"""每公司 SOP 播种 + 跨租户隔离（借自动隔离事件，不经 SOP router）。"""

from __future__ import annotations

from sqlalchemy import select

from app import tenant
from app.models.folder import Folder
from app.schemas.auth import RegisterRequest
from app.services import auth_service

DEPRECATED = "废止"
ARCHIVED = "归档"


def _register(db, *, name, email):
    return auth_service.register(
        db, RegisterRequest(company_name=name, email=email, password="secret123", name="Admin")
    )


def _system_folders(db, company_id):
    token = tenant.set_current_company_id(company_id)
    try:
        return db.execute(select(Folder).where(Folder.system.is_(True))).scalars().all()
    finally:
        tenant.reset_current_company_id(token)


def _system_folder_names(db, company_id):
    return {f.name for f in _system_folders(db, company_id)}


def test_register_seeds_system_folders_per_company(db):
    user = _register(db, name="Acme", email="a@acme.com")
    names = _system_folder_names(db, user.company_id)
    assert {DEPRECATED, ARCHIVED} <= names


def test_seed_folders_are_tenant_isolated(db):
    a = _register(db, name="Acme", email="a@acme.com")
    b = _register(db, name="Beta", email="b@beta.com")
    # 各自只看到自家系统文件夹，看不到对方的（数量上互不叠加）
    a_rows = _system_folders(db, a.company_id)
    b_rows = _system_folders(db, b.company_id)
    assert all(f.company_id == a.company_id for f in a_rows)
    assert all(f.company_id == b.company_id for f in b_rows)
    assert {f.id for f in a_rows}.isdisjoint({f.id for f in b_rows})
