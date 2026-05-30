# Phase 0：平台基座 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Smart CMMS 建立多租户平台基座——租户(Company)、邮箱密码 JWT 认证、用户、权限点 RBAC、租户行级隔离、i18n 框架、品牌改名，并把现有 SOP 表纳入多租户体系。

**Architecture:** 在现有 SmartSOP FastAPI 仓库内扩展（方案 A）。租户隔离用 `company_id` 行级 + SQLAlchemy `do_orm_execute`/`before_flush` 事件钩子自动作用域（读自动加 WHERE、写自动盖章），租户上下文用 `contextvar` 承载。认证层抽象为可插拔 `AuthProvider`，本期只实现本地密码 provider。RBAC 用字符串权限点 code registry + 角色持有 code 列表。沿用既有 flat 布局：模型在 `app/models/`、schema 在 `app/schemas/`、服务在 `app/services/`、路由在 `app/api/v1/`；横切隔离基础设施放 `app/db/` 与 `app/core/`。

**Tech Stack:** FastAPI 0.111 · SQLAlchemy 2.0 (sync) · Pydantic v2 / pydantic-settings · python-jose (JWT) · passlib[bcrypt] · Alembic 1.13 · MySQL/PyMySQL（生产）· SQLite in-memory（测试）· pytest 8.2 · httpx TestClient · Vue 3 + vue-i18n（前端）。

**净室合规：** 全新模型，依据领域理解编写，绝不复制 Atlas 源码/DDL/文案/品牌；产物不含 "Atlas" 字样。

---

## 文件结构（本期新建 / 改造）

**新建（后端）**
- `app/db/base.py` — 改造：新增 `TenantMixin`（与现有 `TimestampMixin` 并列）
- `app/core/tenant.py` — 租户上下文 contextvar + set/get/reset/bypass 辅助
- `app/db/tenant_isolation.py` — `do_orm_execute` + `before_flush` 事件监听 + `register_tenant_events()`
- `app/core/permissions.py` — 权限点 code 常量 + registry + 内置角色默认权限集 + `role_permission_codes()`
- `app/models/company.py` · `app/models/role.py` · `app/models/user.py`
- `app/schemas/auth.py` · `app/schemas/user.py` · `app/schemas/role.py` · `app/schemas/company.py`
- `app/services/auth_service.py` · `app/services/user_service.py` · `app/services/role_service.py` · `app/services/company_service.py`
- `app/api/v1/auth.py` · `app/api/v1/users.py` · `app/api/v1/roles.py` · `app/api/v1/company.py`
- `app/core/i18n.py` — locale 解析 + message catalog
- `alembic.ini` · `alembic/env.py` · `alembic/versions/0001_phase0_platform.py`
- `tests/conftest.py` + 各 `tests/test_*.py`
- `pytest.ini`

**改造（后端）**
- `app/core/security.py` — 重写 token 函数（带 claims、用 settings、加 decode/refresh）
- `app/core/config.py` — 新增 `default_locale`、`refresh_token_expire_days`、改 `app_name`
- `app/api/deps.py` — 新增 `get_current_user` / `require_permission`
- `app/db/session.py` — 注册租户事件
- `app/models/__init__.py` — 注册新模型
- `app/models/folder.py` · `app/models/procedure.py`（及其余 SOP 模型）— 加 `TenantMixin`
- `app/api/v1/sop_router.py` — include 新路由
- `app/main.py` — 标题改 Smart CMMS

**前端**
- `frontend/src/i18n/index.ts` · `frontend/src/i18n/locales/zh-CN.ts`
- 品牌改名（标题/壳/配置）

---

## Task 1: 测试基础设施（conftest + SQLite + TestClient）

仓库当前无 `tests/` 目录与 pytest 配置，先把它建起来，后续任务全部 TDD。

**Files:**
- Create: `backend/pytest.ini`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_smoke.py`

- [ ] **Step 1: 写 pytest 配置**

Create `backend/pytest.ini`:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -q
```

- [ ] **Step 2: 写 conftest（in-memory SQLite + 建表 + 覆盖 get_db）**

Create `backend/tests/__init__.py` (空文件).

Create `backend/tests/conftest.py`:

```python
"""Pytest fixtures: in-memory SQLite engine, session, TestClient."""
from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    # Import all models so metadata is fully populated, then create tables.
    import app.models  # noqa: F401
    from app.db.base import Base

    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture()
def db(engine) -> Generator[Session, None, None]:
    TestingSessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, future=True,
        expire_on_commit=False,
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(engine) -> Generator[TestClient, None, None]:
    from app.main import app
    from app.db.session import get_db

    TestingSessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, future=True,
        expire_on_commit=False,
    )

    def override_get_db() -> Generator[Session, None, None]:
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 3: 写冒烟测试**

Create `backend/tests/test_smoke.py`:

```python
def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
```

- [ ] **Step 4: 运行，确认通过**

Run: `cd backend && python -m pytest tests/test_smoke.py -v`
Expected: PASS（若 `/health` 路径不同，改成 `app/api/v1/health.py` 中的实际路径）。

- [ ] **Step 5: 提交**

```bash
cd backend && git add pytest.ini tests/
git commit -m "test: add pytest infra (sqlite in-memory, TestClient fixtures)"
```

---

## Task 2: 租户上下文 contextvar

**Files:**
- Create: `backend/app/core/tenant.py`
- Test: `backend/tests/test_tenant_context.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_tenant_context.py`:

```python
import pytest

from app.core import tenant


def test_default_is_none():
    assert tenant.get_current_company_id() is None
    assert tenant.is_bypassed() is False


def test_set_and_reset():
    token = tenant.set_current_company_id(7)
    assert tenant.get_current_company_id() == 7
    tenant.reset_current_company_id(token)
    assert tenant.get_current_company_id() is None


def test_bypass_context_manager():
    tenant.set_current_company_id(7)
    with tenant.bypass_tenant_scope():
        assert tenant.is_bypassed() is True
    assert tenant.is_bypassed() is False
    assert tenant.get_current_company_id() == 7
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_tenant_context.py -v`
Expected: FAIL（`ModuleNotFoundError: app.core.tenant`）

- [ ] **Step 3: 实现**

Create `backend/app/core/tenant.py`:

```python
"""Request-scoped tenant context backed by contextvars."""
from __future__ import annotations

import contextlib
from contextvars import ContextVar, Token

_company_id: ContextVar[int | None] = ContextVar("company_id", default=None)
_bypass: ContextVar[bool] = ContextVar("tenant_bypass", default=False)


def get_current_company_id() -> int | None:
    return _company_id.get()


def set_current_company_id(company_id: int | None) -> Token:
    return _company_id.set(company_id)


def reset_current_company_id(token: Token) -> None:
    _company_id.reset(token)


def is_bypassed() -> bool:
    return _bypass.get()


@contextlib.contextmanager
def bypass_tenant_scope():
    """Temporarily disable tenant scoping (e.g. platform-admin / migrations)."""
    token = _bypass.set(True)
    try:
        yield
    finally:
        _bypass.reset(token)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_tenant_context.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/core/tenant.py tests/test_tenant_context.py
git commit -m "feat(tenant): request-scoped tenant context via contextvars"
```

---

## Task 3: TenantMixin

**Files:**
- Modify: `backend/app/db/base.py`
- Test: `backend/tests/test_tenant_mixin.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_tenant_mixin.py`:

```python
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin


class _Sample(Base, TenantMixin):
    __tablename__ = "_sample_tenant_mixin"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50))


def test_mixin_adds_company_id_column():
    assert "company_id" in _Sample.__table__.columns
    col = _Sample.__table__.columns["company_id"]
    assert col.nullable is False
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_tenant_mixin.py -v`
Expected: FAIL（`ImportError: cannot import name 'TenantMixin'`）

- [ ] **Step 3: 实现（在 base.py 追加）**

Modify `backend/app/db/base.py` — 在文件末尾追加：

```python
from sqlalchemy import Integer, ForeignKey


class TenantMixin:
    """Adds a company_id column for row-level multi-tenant isolation."""

    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
```

> 注意：现有 `base.py` 顶部已 `from sqlalchemy import DateTime, func` 和 `from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column`。本步骤新增的 `Integer, ForeignKey` import 放文件末尾本段即可（Python 允许），或合并进顶部 import 行。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_tenant_mixin.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/db/base.py tests/test_tenant_mixin.py
git commit -m "feat(tenant): add TenantMixin (company_id FK column)"
```

---

## Task 4: Company 模型

**Files:**
- Create: `backend/app/models/company.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_company_model.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_company_model.py`:

```python
from app.models.company import Company, CompanyStatus


def test_company_defaults(db):
    c = Company(name="Acme", slug="acme")
    db.add(c)
    db.commit()
    db.refresh(c)
    assert c.id is not None
    assert c.status == CompanyStatus.active
    assert c.locale == "zh-CN"
    assert c.is_platform_admin_org is False
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_company_model.py -v`
Expected: FAIL（`ModuleNotFoundError: app.models.company`）

- [ ] **Step 3: 实现**

Create `backend/app/models/company.py`:

```python
"""Company: the tenant root. Not a TenantMixin — its id IS the tenant id."""
from __future__ import annotations

import enum
from typing import Optional

from sqlalchemy import String, Boolean, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class CompanyStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"


class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[CompanyStatus] = mapped_column(
        SAEnum(CompanyStatus), nullable=False, default=CompanyStatus.active
    )
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="zh-CN")
    # Reserved for platform-operator org (Phase 0: always False, no UI).
    is_platform_admin_org: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    # Reserved placeholders for billing (Phase 6) — no logic attached.
    plan: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    subscription_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
```

- [ ] **Step 4: 注册到 models/__init__.py**

Modify `backend/app/models/__init__.py`：

```python
from app.models.company import Company
from app.models.role import Role
from app.models.user import User
from app.models.folder import Folder
from app.models.procedure import Procedure
from app.models.custom_field import CustomFieldDef
from app.models.attachment import Attachment
from app.models.audit import AuditLog

__all__ = [
    "Company", "Role", "User",
    "Folder", "Procedure", "CustomFieldDef", "Attachment", "AuditLog",
]
```

> 此时 `Role`、`User` 尚未创建，Task 5/6 会补上；若现在运行全量 import 会失败，故本步骤先只加 `Company`，待 Task 5/6 完成后再补 `Role`/`User` 行。**当前仅添加 `from app.models.company import Company` 与把 `"Company"` 加入 `__all__`。**

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_company_model.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
cd backend && git add app/models/company.py app/models/__init__.py tests/test_company_model.py
git commit -m "feat(company): add Company tenant-root model"
```

---

## Task 5: 权限点 registry

**Files:**
- Create: `backend/app/core/permissions.py`
- Test: `backend/tests/test_permissions.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_permissions.py`:

```python
from app.core import permissions as perms


def test_registry_contains_platform_codes():
    assert "user.create" in perms.ALL_PERMISSIONS
    assert "role.manage" in perms.ALL_PERMISSIONS
    assert "company.settings" in perms.ALL_PERMISSIONS


def test_builtin_roles_present():
    codes = {r["code"] for r in perms.BUILTIN_ROLES}
    assert codes == {"super_admin", "admin", "technician", "viewer"}


def test_super_admin_gets_all_permissions():
    sa = next(r for r in perms.BUILTIN_ROLES if r["code"] == "super_admin")
    assert set(sa["permissions"]) == set(perms.ALL_PERMISSIONS)


def test_viewer_only_view():
    viewer = next(r for r in perms.BUILTIN_ROLES if r["code"] == "viewer")
    assert all(c.endswith(".view") for c in viewer["permissions"])


def test_effective_codes_super_admin_is_wildcard():
    assert perms.effective_codes("super_admin", []) == set(perms.ALL_PERMISSIONS)


def test_effective_codes_regular_role():
    assert perms.effective_codes("admin", ["user.view"]) == {"user.view"}
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_permissions.py -v`
Expected: FAIL（`ModuleNotFoundError: app.core.permissions`）

- [ ] **Step 3: 实现**

Create `backend/app/core/permissions.py`:

```python
"""Permission-code registry + built-in role defaults.

Phase 0 declares only platform-layer permission codes. Later phases append
their module codes here; built-in role default sets get extended accordingly.
"""
from __future__ import annotations

# --- Platform permission codes (Phase 0) ---
USER_CREATE = "user.create"
USER_VIEW = "user.view"
USER_EDIT = "user.edit"
USER_DELETE = "user.delete"
ROLE_VIEW = "role.view"
ROLE_MANAGE = "role.manage"
COMPANY_SETTINGS = "company.settings"

ALL_PERMISSIONS: list[str] = [
    USER_CREATE, USER_VIEW, USER_EDIT, USER_DELETE,
    ROLE_VIEW, ROLE_MANAGE,
    COMPANY_SETTINGS,
]

# --- Built-in roles seeded into every new company ---
BUILTIN_ROLES: list[dict] = [
    {
        "code": "super_admin",
        "name": "超级管理员",
        "permissions": list(ALL_PERMISSIONS),  # wildcard, see effective_codes
    },
    {
        "code": "admin",
        "name": "管理员",
        "permissions": [
            USER_CREATE, USER_VIEW, USER_EDIT, USER_DELETE,
            ROLE_VIEW, ROLE_MANAGE, COMPANY_SETTINGS,
        ],
    },
    {
        "code": "technician",
        "name": "技术员",
        "permissions": [USER_VIEW, ROLE_VIEW],
    },
    {
        "code": "viewer",
        "name": "只读",
        "permissions": [c for c in ALL_PERMISSIONS if c.endswith(".view")],
    },
]


def effective_codes(role_code: str, stored_codes: list[str]) -> set[str]:
    """super_admin is an implicit wildcard over ALL_PERMISSIONS."""
    if role_code == "super_admin":
        return set(ALL_PERMISSIONS)
    return set(stored_codes)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_permissions.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/core/permissions.py tests/test_permissions.py
git commit -m "feat(rbac): permission-code registry + built-in role defaults"
```

---

## Task 6: Role 模型

**Files:**
- Create: `backend/app/models/role.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_role_model.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_role_model.py`:

```python
from app.models.company import Company
from app.models.role import Role


def test_role_persists_permissions(db):
    c = Company(name="Acme", slug="acme")
    db.add(c)
    db.commit()
    r = Role(company_id=c.id, code="admin", name="管理员",
             is_builtin=True, permissions=["user.view", "user.create"])
    db.add(r)
    db.commit()
    db.refresh(r)
    assert r.id is not None
    assert r.permissions == ["user.view", "user.create"]
    assert r.is_builtin is True
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_role_model.py -v`
Expected: FAIL（`ModuleNotFoundError: app.models.role`）

- [ ] **Step 3: 实现**

Create `backend/app/models/role.py`:

```python
"""Role: tenant-scoped role holding a list of permission codes."""
from __future__ import annotations

from sqlalchemy import String, Boolean, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, TenantMixin


class Role(Base, TimestampMixin, TenantMixin):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_role_company_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    permissions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
```

- [ ] **Step 4: 注册到 models/__init__.py**

在 `backend/app/models/__init__.py` 加 `from app.models.role import Role` 并把 `"Role"` 加入 `__all__`（Task 4 Step 4 已示意最终态）。

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_role_model.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
cd backend && git add app/models/role.py app/models/__init__.py tests/test_role_model.py
git commit -m "feat(rbac): add Role model (tenant-scoped, JSON permission codes)"
```

---

## Task 7: User 模型

**Files:**
- Create: `backend/app/models/user.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_user_model.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_user_model.py`:

```python
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.company import Company
from app.models.role import Role
from app.models.user import User, UserStatus


def _company(db, slug):
    c = Company(name=slug, slug=slug)
    db.add(c)
    db.commit()
    return c


def test_user_defaults(db):
    c = _company(db, "acme")
    r = Role(company_id=c.id, code="admin", name="管理员", permissions=[])
    db.add(r)
    db.commit()
    u = User(company_id=c.id, email="a@acme.com", password_hash="x",
             name="Alice", role_id=r.id)
    db.add(u)
    db.commit()
    db.refresh(u)
    assert u.status == UserStatus.active
    assert u.is_platform_admin is False
    assert u.locale == "zh-CN"


def test_email_unique_per_company(db):
    c = _company(db, "acme")
    db.add(User(company_id=c.id, email="dup@acme.com", password_hash="x", name="A"))
    db.commit()
    db.add(User(company_id=c.id, email="dup@acme.com", password_hash="y", name="B"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_same_email_allowed_across_companies(db):
    c1 = _company(db, "acme")
    c2 = _company(db, "globex")
    db.add(User(company_id=c1.id, email="same@x.com", password_hash="x", name="A"))
    db.add(User(company_id=c2.id, email="same@x.com", password_hash="y", name="B"))
    db.commit()  # no error
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_user_model.py -v`
Expected: FAIL（`ModuleNotFoundError: app.models.user`）

- [ ] **Step 3: 实现**

Create `backend/app/models/user.py`:

```python
"""User: tenant-scoped account. Email unique within a company."""
from __future__ import annotations

import enum
from typing import Optional
from datetime import datetime

from sqlalchemy import String, Boolean, Integer, ForeignKey, DateTime, Enum as SAEnum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, TenantMixin


class UserStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"


class User(Base, TimestampMixin, TenantMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("company_id", "email", name="uq_user_company_email"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        SAEnum(UserStatus), nullable=False, default=UserStatus.active
    )
    role_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("roles.id", ondelete="SET NULL"), nullable=True
    )
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="zh-CN")
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Reserved for platform-operator identity (Phase 0: always False).
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

- [ ] **Step 4: 注册到 models/__init__.py**

确保 `backend/app/models/__init__.py` 现在为 Task 4 Step 4 所示的最终态（含 `Company`/`Role`/`User`）。

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_user_model.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
cd backend && git add app/models/user.py app/models/__init__.py tests/test_user_model.py
git commit -m "feat(user): add User model (tenant-scoped, email unique per company)"
```

---

## Task 8: 租户隔离事件（自动作用域 + 自动盖章）

**Files:**
- Create: `backend/app/db/tenant_isolation.py`
- Modify: `backend/app/db/session.py`（注册事件）
- Modify: `backend/tests/conftest.py`（测试 session 也注册事件 + 提供 tenant 上下文 fixture）
- Test: `backend/tests/test_tenant_isolation.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_tenant_isolation.py`:

```python
from sqlalchemy import select

from app.core import tenant
from app.models.company import Company
from app.models.role import Role


def _mk_company(db, slug):
    c = Company(name=slug, slug=slug)
    db.add(c)
    db.commit()
    return c


def test_auto_stamp_company_id_on_insert(db):
    c = _mk_company(db, "acme")
    token = tenant.set_current_company_id(c.id)
    try:
        r = Role(code="x", name="X", permissions=[])  # no company_id given
        db.add(r)
        db.commit()
        db.refresh(r)
        assert r.company_id == c.id
    finally:
        tenant.reset_current_company_id(token)


def test_read_scoped_to_current_company(db):
    c1 = _mk_company(db, "acme")
    c2 = _mk_company(db, "globex")
    db.add(Role(company_id=c1.id, code="r1", name="R1", permissions=[]))
    db.add(Role(company_id=c2.id, code="r2", name="R2", permissions=[]))
    db.commit()

    token = tenant.set_current_company_id(c1.id)
    try:
        rows = db.execute(select(Role)).scalars().all()
        assert {r.code for r in rows} == {"r1"}
    finally:
        tenant.reset_current_company_id(token)


def test_no_context_no_scope(db):
    c1 = _mk_company(db, "acme")
    c2 = _mk_company(db, "globex")
    db.add(Role(company_id=c1.id, code="r1", name="R1", permissions=[]))
    db.add(Role(company_id=c2.id, code="r2", name="R2", permissions=[]))
    db.commit()
    # No tenant context => pre-auth style query sees all (login needs this).
    rows = db.execute(select(Role)).scalars().all()
    assert {r.code for r in rows} == {"r1", "r2"}
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_tenant_isolation.py -v`
Expected: FAIL（事件未注册 → 自动盖章/作用域不生效，断言失败或 IntegrityError）

- [ ] **Step 3: 实现事件模块**

Create `backend/app/db/tenant_isolation.py`:

```python
"""SQLAlchemy event listeners enforcing row-level tenant isolation.

- before_flush: stamp company_id on new TenantMixin objects from context.
- do_orm_execute: inject `WHERE company_id = :current` for TenantMixin entities.

Both are skipped when no tenant context is set (pre-auth flows like login) or
when tenant scope is explicitly bypassed (platform-admin / migrations).
"""
from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria

from app.core import tenant
from app.db.base import TenantMixin


def _before_flush(session: Session, flush_context, instances) -> None:
    if tenant.is_bypassed():
        return
    company_id = tenant.get_current_company_id()
    if company_id is None:
        return
    for obj in session.new:
        if isinstance(obj, TenantMixin) and getattr(obj, "company_id", None) is None:
            obj.company_id = company_id


def _do_orm_execute(execute_state) -> None:
    if not execute_state.is_select:
        return
    if tenant.is_bypassed():
        return
    company_id = tenant.get_current_company_id()
    if company_id is None:
        return
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            TenantMixin,
            lambda cls: cls.company_id == company_id,
            include_aliases=True,
        )
    )


def register_tenant_events(session_factory) -> None:
    """Idempotently attach listeners to a sessionmaker/Session class."""
    if not event.contains(session_factory, "before_flush", _before_flush):
        event.listen(session_factory, "before_flush", _before_flush)
    if not event.contains(session_factory, "do_orm_execute", _do_orm_execute):
        event.listen(session_factory, "do_orm_execute", _do_orm_execute)
```

- [ ] **Step 4: 在生产 session 工厂注册事件**

Modify `backend/app/db/session.py` — 在 `SessionLocal = sessionmaker(...)` 之后追加：

```python
from app.db.tenant_isolation import register_tenant_events

register_tenant_events(SessionLocal)
```

- [ ] **Step 5: 测试 session 也注册事件**

Modify `backend/tests/conftest.py` — 在 `db` fixture 与 `client` fixture 各自 `sessionmaker(...)` 之后，调用注册：

在 `db` fixture 内 `TestingSessionLocal = sessionmaker(...)` 之后加：
```python
    from app.db.tenant_isolation import register_tenant_events
    register_tenant_events(TestingSessionLocal)
```
在 `client` fixture 内 `TestingSessionLocal = sessionmaker(...)` 之后同样加上述两行。

- [ ] **Step 6: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_tenant_isolation.py -v`
Expected: PASS

- [ ] **Step 7: 回归全量**

Run: `cd backend && python -m pytest -v`
Expected: 全部 PASS（确认事件未破坏既有 model 测试）。

- [ ] **Step 8: 提交**

```bash
cd backend && git add app/db/tenant_isolation.py app/db/session.py tests/conftest.py tests/test_tenant_isolation.py
git commit -m "feat(tenant): auto-scope reads + auto-stamp writes via ORM events"
```

---

## Task 9: 安全/JWT 重写（带 claims，用 settings）

现有 `security.py` 用硬编码 key 且无 decode。重写为带 claims、用配置、可生成 access/refresh + decode。

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/core/security.py`
- Test: `backend/tests/test_security.py`

- [ ] **Step 1: 扩展配置**

Modify `backend/app/core/config.py` — 在 `Settings` 内：
- 把 `app_name: str = "SmartSOP"` 改为 `app_name: str = "Smart CMMS"`
- 新增字段：
```python
    refresh_token_expire_days: int = 14
    default_locale: str = "zh-CN"
    supported_locales: list[str] = ["zh-CN"]
```

- [ ] **Step 2: 写失败测试**

Create `backend/tests/test_security.py`:

```python
import pytest

from app.core import security


def test_hash_and_verify():
    h = security.hash_password("secret123")
    assert h != "secret123"
    assert security.verify_password("secret123", h) is True
    assert security.verify_password("wrong", h) is False


def test_access_token_roundtrip():
    token = security.create_access_token(user_id=5, company_id=9, role_code="admin")
    claims = security.decode_token(token)
    assert claims["sub"] == "5"
    assert claims["company_id"] == 9
    assert claims["role_code"] == "admin"
    assert claims["type"] == "access"


def test_refresh_token_type():
    token = security.create_refresh_token(user_id=5, company_id=9, role_code="admin")
    claims = security.decode_token(token)
    assert claims["type"] == "refresh"


def test_decode_invalid_raises():
    with pytest.raises(security.TokenError):
        security.decode_token("not-a-token")
```

- [ ] **Step 3: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_security.py -v`
Expected: FAIL（`create_access_token` 签名不符 / 无 `decode_token`/`TokenError`）

- [ ] **Step 4: 重写 security.py**

Replace entire `backend/app/core/security.py`:

```python
"""Security utilities: password hashing and JWT tokens."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenError(Exception):
    """Raised when a JWT cannot be decoded or is invalid."""


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _create_token(
    *, user_id: int, company_id: int, role_code: str | None,
    token_type: str, expires_delta: timedelta,
) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": str(user_id),
        "company_id": company_id,
        "role_code": role_code,
        "type": token_type,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(*, user_id: int, company_id: int, role_code: str | None) -> str:
    return _create_token(
        user_id=user_id, company_id=company_id, role_code=role_code,
        token_type="access",
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(*, user_id: int, company_id: int, role_code: str | None) -> str:
    return _create_token(
        user_id=user_id, company_id=company_id, role_code=role_code,
        token_type="refresh",
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise TokenError(str(exc)) from exc
```

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_security.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
cd backend && git add app/core/config.py app/core/security.py tests/test_security.py
git commit -m "feat(auth): JWT tokens with tenant/role claims + decode; brand=Smart CMMS"
```

---

## Task 10: Auth schemas

**Files:**
- Create: `backend/app/schemas/auth.py`
- Test: `backend/tests/test_auth_schemas.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_auth_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from app.schemas.auth import RegisterRequest, LoginRequest, TokenPair


def test_register_request_valid():
    r = RegisterRequest(company_name="Acme", email="a@acme.com",
                        password="secret123", name="Alice")
    assert r.email == "a@acme.com"


def test_register_rejects_short_password():
    with pytest.raises(ValidationError):
        RegisterRequest(company_name="Acme", email="a@acme.com",
                        password="x", name="Alice")


def test_login_request_optional_slug():
    l = LoginRequest(email="a@acme.com", password="secret123")
    assert l.company_slug is None


def test_token_pair_shape():
    t = TokenPair(access_token="a", refresh_token="r")
    assert t.token_type == "bearer"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_auth_schemas.py -v`
Expected: FAIL（`ModuleNotFoundError: app.schemas.auth`）

- [ ] **Step 3: 实现**

Create `backend/app/schemas/auth.py`:

```python
"""Auth request/response schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    company_slug: Optional[str] = None  # disambiguates when email spans tenants


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class CurrentUser(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    email: EmailStr
    name: str
    company_id: int
    role_code: Optional[str] = None
    permissions: list[str] = []
```

> `EmailStr` 需要 `email-validator`。若未安装，在 `backend/requirements.txt` 追加 `email-validator==2.1.1` 并 `pip install -r requirements.txt`（本步骤一并处理）。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_auth_schemas.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/schemas/auth.py tests/test_auth_schemas.py requirements.txt
git commit -m "feat(auth): auth request/response schemas"
```

---

## Task 11: Auth service（注册建租户 / 登录 / 刷新）

**Files:**
- Create: `backend/app/services/auth_service.py`
- Test: `backend/tests/test_auth_service.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_auth_service.py`:

```python
import pytest
from sqlalchemy import select

from app.services import auth_service
from app.schemas.auth import RegisterRequest, LoginRequest
from app.models.company import Company
from app.models.role import Role
from app.models.user import User


def _register(db, company="Acme", slug_email="a@acme.com"):
    return auth_service.register(
        db, RegisterRequest(company_name=company, email=slug_email,
                            password="secret123", name="Alice"))


def test_register_creates_company_user_and_4_roles(db):
    user = _register(db)
    assert user.id is not None
    company = db.get(Company, user.company_id)
    assert company is not None
    roles = db.execute(
        select(Role).where(Role.company_id == company.id)
    ).scalars().all()
    assert {r.code for r in roles} == {"super_admin", "admin", "technician", "viewer"}
    # registrant is super_admin
    sa = next(r for r in roles if r.code == "super_admin")
    assert user.role_id == sa.id


def test_register_duplicate_company_slug_raises(db):
    _register(db, company="Acme")
    with pytest.raises(auth_service.AuthError):
        _register(db, company="Acme", slug_email="b@acme.com")


def test_login_success_returns_user(db):
    _register(db)
    user = auth_service.authenticate(db, LoginRequest(email="a@acme.com",
                                                      password="secret123"))
    assert user.email == "a@acme.com"


def test_login_wrong_password_raises(db):
    _register(db)
    with pytest.raises(auth_service.AuthError):
        auth_service.authenticate(db, LoginRequest(email="a@acme.com",
                                                   password="nope"))


def test_login_ambiguous_email_requires_slug(db):
    auth_service.register(db, RegisterRequest(company_name="Acme",
        email="same@x.com", password="secret123", name="A"))
    auth_service.register(db, RegisterRequest(company_name="Globex",
        email="same@x.com", password="secret123", name="B"))
    with pytest.raises(auth_service.AuthError):
        auth_service.authenticate(db, LoginRequest(email="same@x.com",
                                                   password="secret123"))
    # with slug it works
    u = auth_service.authenticate(db, LoginRequest(email="same@x.com",
        password="secret123", company_slug="globex"))
    assert u.company_id is not None
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_auth_service.py -v`
Expected: FAIL（`ModuleNotFoundError: app.services.auth_service`）

- [ ] **Step 3: 实现**

Create `backend/app/services/auth_service.py`:

```python
"""Auth service: self-service registration (creates tenant), login.

Pre-auth flows run with NO tenant context, so cross-tenant lookups (login by
email) work. register() sets context to the new company before seeding rows so
the isolation events stamp them correctly.
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import tenant, security
from app.core.permissions import BUILTIN_ROLES
from app.models.company import Company
from app.models.role import Role
from app.models.user import User, UserStatus
from app.schemas.auth import RegisterRequest, LoginRequest


class AuthError(Exception):
    """Registration or authentication failure."""


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return s or "company"


def register(db: Session, payload: RegisterRequest) -> User:
    slug = _slugify(payload.company_name)
    with tenant.bypass_tenant_scope():
        exists = db.execute(select(Company).where(Company.slug == slug)).scalar_one_or_none()
    if exists is not None:
        raise AuthError(f"公司标识已存在: {slug}")

    company = Company(name=payload.company_name, slug=slug)
    db.add(company)
    db.flush()  # assign company.id

    token = tenant.set_current_company_id(company.id)
    try:
        roles_by_code: dict[str, Role] = {}
        for spec in BUILTIN_ROLES:
            role = Role(code=spec["code"], name=spec["name"],
                        is_builtin=True, permissions=list(spec["permissions"]))
            db.add(role)
            roles_by_code[spec["code"]] = role
        db.flush()

        user = User(
            email=payload.email,
            password_hash=security.hash_password(payload.password),
            name=payload.name,
            role_id=roles_by_code["super_admin"].id,
            status=UserStatus.active,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        tenant.reset_current_company_id(token)


def authenticate(db: Session, payload: LoginRequest) -> User:
    with tenant.bypass_tenant_scope():
        stmt = select(User).where(User.email == payload.email)
        candidates = db.execute(stmt).scalars().all()
        if payload.company_slug:
            company = db.execute(
                select(Company).where(Company.slug == payload.company_slug)
            ).scalar_one_or_none()
            if company is None:
                raise AuthError("公司不存在")
            candidates = [u for u in candidates if u.company_id == company.id]

    if not candidates:
        raise AuthError("邮箱或密码错误")
    if len(candidates) > 1:
        raise AuthError("该邮箱存在于多个公司，请提供公司标识")

    user = candidates[0]
    if user.status != UserStatus.active:
        raise AuthError("账号已禁用")
    if not security.verify_password(payload.password, user.password_hash):
        raise AuthError("邮箱或密码错误")
    return user
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_auth_service.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/services/auth_service.py tests/test_auth_service.py
git commit -m "feat(auth): registration (creates tenant + seeds roles) and login service"
```

---

## Task 12: Auth 依赖（get_current_user / require_permission）

**Files:**
- Modify: `backend/app/api/deps.py`
- Test: `backend/tests/test_auth_deps.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_auth_deps.py`:

```python
import pytest
from fastapi import HTTPException

from app.api import deps
from app.core import security, tenant
from app.services import auth_service
from app.schemas.auth import RegisterRequest


def _register(db):
    return auth_service.register(db, RegisterRequest(
        company_name="Acme", email="a@acme.com", password="secret123", name="A"))


def test_get_current_user_sets_context_and_loads(db):
    user = _register(db)
    token = security.create_access_token(
        user_id=user.id, company_id=user.company_id, role_code="super_admin")
    try:
        loaded = deps.get_current_user(token=token, db=db)
        assert loaded.id == user.id
        assert tenant.get_current_company_id() == user.company_id
    finally:
        tenant.set_current_company_id(None)


def test_get_current_user_bad_token_401(db):
    with pytest.raises(HTTPException) as exc:
        deps.get_current_user(token="garbage", db=db)
    assert exc.value.status_code == 401


def test_require_permission_allows_super_admin(db):
    user = _register(db)
    tenant.set_current_company_id(user.company_id)
    try:
        checker = deps.require_permission("user.create")
        # super_admin wildcard => returns user without raising
        assert checker(current_user=user, db=db).id == user.id
    finally:
        tenant.set_current_company_id(None)


def test_require_permission_denies_viewer(db):
    user = _register(db)
    # demote to viewer
    from app.models.role import Role
    from sqlalchemy import select
    tenant.set_current_company_id(user.company_id)
    try:
        viewer = db.execute(select(Role).where(Role.code == "viewer")).scalar_one()
        user.role_id = viewer.id
        db.commit()
        checker = deps.require_permission("user.create")
        with pytest.raises(HTTPException) as exc:
            checker(current_user=user, db=db)
        assert exc.value.status_code == 403
    finally:
        tenant.set_current_company_id(None)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_auth_deps.py -v`
Expected: FAIL（`AttributeError: module app.api.deps has no attribute get_current_user`）

- [ ] **Step 3: 实现**

Replace `backend/app/api/deps.py`:

```python
"""FastAPI dependency providers."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core import security, tenant
from app.core.permissions import effective_codes
from app.db.session import get_db
from app.models.role import Role
from app.models.user import User

__all__ = ["get_db", "get_current_user", "require_permission"]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="未认证")
    try:
        claims = security.decode_token(token)
    except security.TokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="无效的令牌")
    if claims.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="令牌类型错误")
    company_id = claims.get("company_id")
    user_id = int(claims["sub"])
    # Establish tenant scope BEFORE loading so the query is correctly scoped.
    tenant.set_current_company_id(company_id)
    user = db.get(User, user_id)
    if user is None or user.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="用户不存在")
    return user


def _user_permission_codes(db: Session, user: User) -> set[str]:
    role_code = None
    stored: list[str] = []
    if user.role_id is not None:
        role = db.get(Role, user.role_id)
        if role is not None:
            role_code = role.code
            stored = role.permissions or []
    return effective_codes(role_code or "", stored)


def require_permission(code: str):
    """Return a dependency that enforces the given permission code."""

    def checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if code not in _user_permission_codes(db, current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="权限不足")
        return current_user

    return checker
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_auth_deps.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/api/deps.py tests/test_auth_deps.py
git commit -m "feat(auth): get_current_user (sets tenant scope) + require_permission"
```

---

## Task 13: Auth 路由（register / login / refresh / me）

**Files:**
- Create: `backend/app/api/v1/auth.py`
- Modify: `backend/app/api/v1/sop_router.py`
- Test: `backend/tests/test_auth_api.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_auth_api.py`:

```python
def _register(client, company="Acme", email="a@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email,
        "password": "secret123", "name": "Alice"})


def test_register_returns_token_pair(client):
    r = _register(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_login_then_me(client):
    _register(client)
    r = client.post("/api/v1/auth/login", json={
        "email": "a@acme.com", "password": "secret123"})
    assert r.status_code == 200, r.text
    access = r.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["email"] == "a@acme.com"
    assert body["role_code"] == "super_admin"
    assert "user.create" in body["permissions"]


def test_login_bad_password_401(client):
    _register(client)
    r = client.post("/api/v1/auth/login", json={
        "email": "a@acme.com", "password": "wrong"})
    assert r.status_code == 401


def test_refresh_issues_new_access(client):
    reg = _register(client).json()
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": reg["refresh_token"]})
    assert r.status_code == 200, r.text
    assert r.json()["access_token"]


def test_me_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_auth_api.py -v`
Expected: FAIL（路由不存在 → 404）

- [ ] **Step 3: 实现路由**

Create `backend/app/api/v1/auth.py`:

```python
"""Auth API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.core import security
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import (
    RegisterRequest, LoginRequest, RefreshRequest, TokenPair, CurrentUser,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _role_code(db: Session, user: User) -> str | None:
    if user.role_id is None:
        return None
    role = db.get(Role, user.role_id)
    return role.code if role else None


def _token_pair(db: Session, user: User) -> TokenPair:
    role_code = _role_code(db, user)
    return TokenPair(
        access_token=security.create_access_token(
            user_id=user.id, company_id=user.company_id, role_code=role_code),
        refresh_token=security.create_refresh_token(
            user_id=user.id, company_id=user.company_id, role_code=role_code),
    )


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    try:
        user = auth_service.register(db, payload)
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return _token_pair(db, user)


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        user = auth_service.authenticate(db, payload)
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    return _token_pair(db, user)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        claims = security.decode_token(payload.refresh_token)
    except security.TokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的令牌")
    if claims.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌类型错误")
    from app.core import tenant
    tenant.set_current_company_id(claims.get("company_id"))
    user = db.get(User, int(claims["sub"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return _token_pair(db, user)


@router.get("/me", response_model=CurrentUser)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.api.deps import _user_permission_codes
    role_code = _role_code(db, current_user)
    return CurrentUser(
        id=current_user.id, email=current_user.email, name=current_user.name,
        company_id=current_user.company_id, role_code=role_code,
        permissions=sorted(_user_permission_codes(db, current_user)),
    )
```

- [ ] **Step 4: 挂载路由**

Modify `backend/app/api/v1/sop_router.py`：
```python
from app.api.v1 import auth, folders, procedures, custom_fields, attachments, audit
...
api_router.include_router(auth.router)
```
（把 `auth` 加到 import 行，并在其它 `include_router` 前后任意位置加 `api_router.include_router(auth.router)`。）

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_auth_api.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
cd backend && git add app/api/v1/auth.py app/api/v1/sop_router.py tests/test_auth_api.py
git commit -m "feat(auth): register/login/refresh/me endpoints"
```

---

## Task 14: 用户管理（schema + service + 路由）

含「管理员直接建号」（非邮件邀请）。

**Files:**
- Create: `backend/app/schemas/user.py`
- Create: `backend/app/services/user_service.py`
- Create: `backend/app/api/v1/users.py`
- Modify: `backend/app/api/v1/sop_router.py`
- Test: `backend/tests/test_users_api.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_users_api.py`:

```python
def _register_admin(client):
    r = client.post("/api/v1/auth/register", json={
        "company_name": "Acme", "email": "admin@acme.com",
        "password": "secret123", "name": "Admin"})
    return r.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_admin_creates_user(client):
    token = _register_admin(client)
    r = client.post("/api/v1/users", headers=_auth(token), json={
        "email": "bob@acme.com", "password": "secret123", "name": "Bob"})
    assert r.status_code == 201, r.text
    assert r.json()["email"] == "bob@acme.com"


def test_list_users_scoped_to_company(client):
    token = _register_admin(client)
    client.post("/api/v1/users", headers=_auth(token), json={
        "email": "bob@acme.com", "password": "secret123", "name": "Bob"})
    r = client.get("/api/v1/users", headers=_auth(token))
    assert r.status_code == 200
    emails = {u["email"] for u in r.json()}
    assert emails == {"admin@acme.com", "bob@acme.com"}


def test_cannot_create_user_without_auth(client):
    r = client.post("/api/v1/users", json={
        "email": "x@acme.com", "password": "secret123", "name": "X"})
    assert r.status_code == 401


def test_new_user_can_login(client):
    token = _register_admin(client)
    client.post("/api/v1/users", headers=_auth(token), json={
        "email": "bob@acme.com", "password": "secret123", "name": "Bob"})
    r = client.post("/api/v1/auth/login", json={
        "email": "bob@acme.com", "password": "secret123",
        "company_slug": "acme"})
    assert r.status_code == 200, r.text
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_users_api.py -v`
Expected: FAIL（404）

- [ ] **Step 3: 实现 schema**

Create `backend/app/schemas/user.py`:

```python
"""User management schemas."""
from __future__ import annotations

from typing import Optional
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.models.user import UserStatus


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    role_id: Optional[int] = None


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    role_id: Optional[int] = None
    status: Optional[UserStatus] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    name: str
    status: UserStatus
    role_id: Optional[int] = None
    locale: str
    last_login_at: Optional[datetime] = None
    created_at: datetime
```

- [ ] **Step 4: 实现 service**

Create `backend/app/services/user_service.py`:

```python
"""User management service (tenant-scoped via ORM events)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class UserServiceError(Exception):
    pass


def create_user(db: Session, payload: UserCreate) -> User:
    user = User(
        email=payload.email,
        password_hash=security.hash_password(payload.password),
        name=payload.name,
        role_id=payload.role_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session) -> list[User]:
    return list(db.execute(select(User)).scalars().all())


def get_user(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def update_user(db: Session, user_id: int, payload: UserUpdate) -> User | None:
    user = db.get(User, user_id)
    if user is None:
        return None
    data = payload.model_dump(exclude_unset=True)
    if "password" in data:
        user.password_hash = security.hash_password(data.pop("password"))
    for k, v in data.items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int) -> None:
    user = db.get(User, user_id)
    if user:
        db.delete(user)
        db.commit()
```

> `db.get(User, user_id)` 走主键直取，**不经过** `do_orm_execute` 作用域，因此跨租户 `get_user` 可能取到他租户对象。为防越权，service 取回后由调用方（路由）校验 `company_id`，见 Step 5 路由中的显式断言。

- [ ] **Step 5: 实现路由（含跨租户显式校验兜底）**

Create `backend/app/api/v1/users.py`:

```python
"""User management API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_permission
from app.core import permissions, tenant
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


def _ensure_same_tenant(obj: User | None) -> User:
    if obj is None or obj.company_id != tenant.get_current_company_id():
        raise HTTPException(status_code=404, detail="用户不存在")
    return obj


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db),
                _: User = Depends(require_permission(permissions.USER_CREATE))):
    return user_service.create_user(db, payload)


@router.get("", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db),
               _: User = Depends(require_permission(permissions.USER_VIEW))):
    return user_service.list_users(db)


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: Session = Depends(get_db),
             _: User = Depends(require_permission(permissions.USER_VIEW))):
    return _ensure_same_tenant(user_service.get_user(db, user_id))


@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db),
                _: User = Depends(require_permission(permissions.USER_EDIT))):
    _ensure_same_tenant(user_service.get_user(db, user_id))
    return user_service.update_user(db, user_id, payload)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db),
                _: User = Depends(require_permission(permissions.USER_DELETE))):
    _ensure_same_tenant(user_service.get_user(db, user_id))
    user_service.delete_user(db, user_id)
```

- [ ] **Step 6: 挂载路由**

Modify `backend/app/api/v1/sop_router.py`：import 行加 `users`，并加 `api_router.include_router(users.router)`。

- [ ] **Step 7: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_users_api.py -v`
Expected: PASS

- [ ] **Step 8: 提交**

```bash
cd backend && git add app/schemas/user.py app/services/user_service.py app/api/v1/users.py app/api/v1/sop_router.py tests/test_users_api.py
git commit -m "feat(users): admin user CRUD (create/list/get/update/delete)"
```

---

## Task 15: 角色管理（schema + service + 路由）

**Files:**
- Create: `backend/app/schemas/role.py`
- Create: `backend/app/services/role_service.py`
- Create: `backend/app/api/v1/roles.py`
- Modify: `backend/app/api/v1/sop_router.py`
- Test: `backend/tests/test_roles_api.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_roles_api.py`:

```python
def _admin_token(client):
    r = client.post("/api/v1/auth/register", json={
        "company_name": "Acme", "email": "admin@acme.com",
        "password": "secret123", "name": "Admin"})
    return r.json()["access_token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_list_seeded_roles(client):
    t = _admin_token(client)
    r = client.get("/api/v1/roles", headers=_auth(t))
    assert r.status_code == 200
    codes = {x["code"] for x in r.json()}
    assert codes == {"super_admin", "admin", "technician", "viewer"}


def test_create_custom_role(client):
    t = _admin_token(client)
    r = client.post("/api/v1/roles", headers=_auth(t), json={
        "code": "planner", "name": "计划员", "permissions": ["user.view"]})
    assert r.status_code == 201, r.text
    assert r.json()["permissions"] == ["user.view"]


def test_create_role_rejects_unknown_permission(client):
    t = _admin_token(client)
    r = client.post("/api/v1/roles", headers=_auth(t), json={
        "code": "x", "name": "X", "permissions": ["does.not.exist"]})
    assert r.status_code == 422


def test_update_role_permissions(client):
    t = _admin_token(client)
    rid = client.post("/api/v1/roles", headers=_auth(t), json={
        "code": "planner", "name": "计划员", "permissions": ["user.view"]}).json()["id"]
    r = client.patch(f"/api/v1/roles/{rid}", headers=_auth(t),
                     json={"permissions": ["user.view", "user.create"]})
    assert r.status_code == 200
    assert set(r.json()["permissions"]) == {"user.view", "user.create"}


def test_cannot_delete_builtin_role(client):
    t = _admin_token(client)
    rid = [x for x in client.get("/api/v1/roles", headers=_auth(t)).json()
           if x["code"] == "admin"][0]["id"]
    r = client.delete(f"/api/v1/roles/{rid}", headers=_auth(t))
    assert r.status_code == 400
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_roles_api.py -v`
Expected: FAIL（404）

- [ ] **Step 3: 实现 schema（含权限点校验）**

Create `backend/app/schemas/role.py`:

```python
"""Role management schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.core.permissions import ALL_PERMISSIONS


def _validate_codes(codes: list[str]) -> list[str]:
    unknown = [c for c in codes if c not in ALL_PERMISSIONS]
    if unknown:
        raise ValueError(f"未知权限点: {unknown}")
    return codes


class RoleCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    permissions: list[str] = []

    @field_validator("permissions")
    @classmethod
    def check_perms(cls, v: list[str]) -> list[str]:
        return _validate_codes(v)


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    permissions: Optional[list[str]] = None

    @field_validator("permissions")
    @classmethod
    def check_perms(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else _validate_codes(v)


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    is_builtin: bool
    permissions: list[str]
```

- [ ] **Step 4: 实现 service**

Create `backend/app/services/role_service.py`:

```python
"""Role management service (tenant-scoped via ORM events)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.role import Role
from app.schemas.role import RoleCreate, RoleUpdate


class RoleServiceError(Exception):
    pass


def create_role(db: Session, payload: RoleCreate) -> Role:
    role = Role(code=payload.code, name=payload.name,
                is_builtin=False, permissions=payload.permissions)
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def list_roles(db: Session) -> list[Role]:
    return list(db.execute(select(Role)).scalars().all())


def get_role(db: Session, role_id: int) -> Role | None:
    return db.get(Role, role_id)


def update_role(db: Session, role_id: int, payload: RoleUpdate) -> Role | None:
    role = db.get(Role, role_id)
    if role is None:
        return None
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(role, k, v)
    db.commit()
    db.refresh(role)
    return role


def delete_role(db: Session, role_id: int) -> None:
    role = db.get(Role, role_id)
    if role:
        db.delete(role)
        db.commit()
```

- [ ] **Step 5: 实现路由**

Create `backend/app/api/v1/roles.py`:

```python
"""Role management API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.core import permissions, tenant
from app.models.role import Role
from app.models.user import User
from app.schemas.role import RoleCreate, RoleRead, RoleUpdate
from app.services import role_service

router = APIRouter(prefix="/roles", tags=["roles"])


def _ensure_same_tenant(role: Role | None) -> Role:
    if role is None or role.company_id != tenant.get_current_company_id():
        raise HTTPException(status_code=404, detail="角色不存在")
    return role


@router.get("", response_model=list[RoleRead])
def list_roles(db: Session = Depends(get_db),
               _: User = Depends(require_permission(permissions.ROLE_VIEW))):
    return role_service.list_roles(db)


@router.post("", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
def create_role(payload: RoleCreate, db: Session = Depends(get_db),
                _: User = Depends(require_permission(permissions.ROLE_MANAGE))):
    return role_service.create_role(db, payload)


@router.patch("/{role_id}", response_model=RoleRead)
def update_role(role_id: int, payload: RoleUpdate, db: Session = Depends(get_db),
                _: User = Depends(require_permission(permissions.ROLE_MANAGE))):
    _ensure_same_tenant(role_service.get_role(db, role_id))
    return role_service.update_role(db, role_id, payload)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(role_id: int, db: Session = Depends(get_db),
                _: User = Depends(require_permission(permissions.ROLE_MANAGE))):
    role = _ensure_same_tenant(role_service.get_role(db, role_id))
    if role.is_builtin:
        raise HTTPException(status_code=400, detail="内置角色不可删除")
    role_service.delete_role(db, role_id)
```

- [ ] **Step 6: 挂载路由**

Modify `backend/app/api/v1/sop_router.py`：import 加 `roles`，加 `api_router.include_router(roles.router)`。

- [ ] **Step 7: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_roles_api.py -v`
Expected: PASS

- [ ] **Step 8: 提交**

```bash
cd backend && git add app/schemas/role.py app/services/role_service.py app/api/v1/roles.py app/api/v1/sop_router.py tests/test_roles_api.py
git commit -m "feat(rbac): role management API (list/create/update/delete, builtin guard)"
```

---

## Task 16: 租户设置（company/me）

**Files:**
- Create: `backend/app/schemas/company.py`
- Create: `backend/app/services/company_service.py`
- Create: `backend/app/api/v1/company.py`
- Modify: `backend/app/api/v1/sop_router.py`
- Test: `backend/tests/test_company_api.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_company_api.py`:

```python
def _admin_token(client):
    return client.post("/api/v1/auth/register", json={
        "company_name": "Acme", "email": "admin@acme.com",
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_get_company_me(client):
    t = _admin_token(client)
    r = client.get("/api/v1/companies/me", headers=_auth(t))
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Acme"
    assert r.json()["locale"] == "zh-CN"


def test_update_company_settings(client):
    t = _admin_token(client)
    r = client.patch("/api/v1/companies/me", headers=_auth(t),
                     json={"name": "Acme Inc", "locale": "zh-CN"})
    assert r.status_code == 200
    assert r.json()["name"] == "Acme Inc"


def test_company_me_requires_auth(client):
    assert client.get("/api/v1/companies/me").status_code == 401
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_company_api.py -v`
Expected: FAIL（404）

- [ ] **Step 3: 实现 schema**

Create `backend/app/schemas/company.py`:

```python
"""Company (tenant) settings schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from app.models.company import CompanyStatus


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    status: CompanyStatus
    locale: str


class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    locale: Optional[str] = Field(default=None, max_length=16)
```

- [ ] **Step 4: 实现 service**

Create `backend/app/services/company_service.py`:

```python
"""Company settings service."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.company import Company
from app.schemas.company import CompanyUpdate


def get_company(db: Session, company_id: int) -> Company | None:
    return db.get(Company, company_id)


def update_company(db: Session, company_id: int, payload: CompanyUpdate) -> Company | None:
    company = db.get(Company, company_id)
    if company is None:
        return None
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(company, k, v)
    db.commit()
    db.refresh(company)
    return company
```

- [ ] **Step 5: 实现路由**

Create `backend/app/api/v1/company.py`:

```python
"""Company (tenant) settings API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_permission
from app.core import permissions
from app.models.user import User
from app.schemas.company import CompanyRead, CompanyUpdate
from app.services import company_service

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/me", response_model=CompanyRead)
def get_my_company(current_user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    company = company_service.get_company(db, current_user.company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="公司不存在")
    return company


@router.patch("/me", response_model=CompanyRead)
def update_my_company(payload: CompanyUpdate,
                      current_user: User = Depends(require_permission(permissions.COMPANY_SETTINGS)),
                      db: Session = Depends(get_db)):
    company = company_service.update_company(db, current_user.company_id, payload)
    if company is None:
        raise HTTPException(status_code=404, detail="公司不存在")
    return company
```

- [ ] **Step 6: 挂载路由**

Modify `backend/app/api/v1/sop_router.py`：import 加 `company`，加 `api_router.include_router(company.router)`。

- [ ] **Step 7: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_company_api.py -v`
Expected: PASS

- [ ] **Step 8: 提交**

```bash
cd backend && git add app/schemas/company.py app/services/company_service.py app/api/v1/company.py app/api/v1/sop_router.py tests/test_company_api.py
git commit -m "feat(company): tenant settings API (GET/PATCH /companies/me)"
```

---

## Task 17: 现有 SOP 表接入多租户

为 SOP 系列模型加 `TenantMixin`。先确认完整模型清单，再逐一加。

**Files:**
- Modify: `backend/app/models/folder.py`、`backend/app/models/procedure.py`（及 procedure.py 中其余 SOP 子模型，如 Section/Step/ProcedureVersion）、`backend/app/models/custom_field.py`、`backend/app/models/attachment.py`、`backend/app/models/audit.py`
- Test: `backend/tests/test_sop_tenant.py`

- [ ] **Step 1: 确认 SOP 模型清单**

Run: `cd backend && grep -rn "__tablename__" app/models/`
记录所有业务表类名（Folder/Procedure/ProcedureVersion/Section/Step/CustomFieldDef/Attachment/AuditLog 等）。**Company/Role/User 已是租户体系自身，跳过。** 对每个**业务**表执行 Step 2 的改造。

- [ ] **Step 2: 写失败测试**

Create `backend/tests/test_sop_tenant.py`:

```python
from app.db.base import TenantMixin
from app.models.folder import Folder
from app.models.procedure import Procedure


def test_sop_models_are_tenant_scoped():
    assert issubclass(Folder, TenantMixin)
    assert issubclass(Procedure, TenantMixin)
    assert "company_id" in Folder.__table__.columns
    assert "company_id" in Procedure.__table__.columns


def test_folder_auto_stamped_and_scoped(db):
    from app.core import tenant
    from app.models.company import Company

    c1 = Company(name="c1", slug="c1"); c2 = Company(name="c2", slug="c2")
    db.add_all([c1, c2]); db.commit()

    t = tenant.set_current_company_id(c1.id)
    try:
        f = Folder(name="只属于c1")
        db.add(f); db.commit()
        assert f.company_id == c1.id
    finally:
        tenant.reset_current_company_id(t)

    t = tenant.set_current_company_id(c2.id)
    try:
        from sqlalchemy import select
        rows = db.execute(select(Folder)).scalars().all()
        assert rows == []  # c2 sees none of c1's folders
    finally:
        tenant.reset_current_company_id(t)
```

- [ ] **Step 3: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_sop_tenant.py -v`
Expected: FAIL（`Folder` 还不是 `TenantMixin` 子类）

- [ ] **Step 4: 给每个 SOP 业务模型加 TenantMixin**

对 `folder.py`：
- import 行改为 `from app.db.base import Base, TimestampMixin, TenantMixin`
- 类定义改为 `class Folder(Base, TimestampMixin, TenantMixin):`

对 `procedure.py` 中**每个**业务模型类（Procedure 及其子模型）做同样两处改动：import 追加 `TenantMixin`，类基类追加 `TenantMixin`。

对 `custom_field.py`、`attachment.py`、`audit.py` 中的业务模型类做同样改动。

> 注意 `Procedure.code` 当前是全局 `unique=True`（见 procedure.py L24）。多租户下应改为按租户唯一：把该列的 `unique=True` 去掉，并在类加 `__table_args__ = (UniqueConstraint("company_id", "code", name="uq_procedure_company_code"),)`（import `from sqlalchemy import UniqueConstraint`）。

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_sop_tenant.py -v`
Expected: PASS

- [ ] **Step 6: 回归全量**

Run: `cd backend && python -m pytest -v`
Expected: 全部 PASS。若既有 SOP 测试因 `company_id` NOT NULL 失败，说明那些测试在无租户上下文下建对象——本期 SOP 走 API 时均带上下文；如确有遗留单元测试，给其建对象处加 `company_id` 或包在 `tenant.set_current_company_id(...)` 中。

- [ ] **Step 7: 提交**

```bash
cd backend && git add app/models/ tests/test_sop_tenant.py
git commit -m "feat(tenant): bring existing SOP models under multi-tenant isolation"
```

---

## Task 18: Alembic 初始化 + 首版迁移

仓库当前无 `alembic.ini` 与可用 `env.py`。建立 Alembic 并生成覆盖全部表的首版迁移。

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/0001_phase0_platform.py`（autogenerate 产物）

- [ ] **Step 1: 初始化 Alembic 脚手架**

Run: `cd backend && alembic init -t generic alembic_tmp`
然后把生成的 `alembic_tmp/env.py`、`script.py.mako` 移入既有 `alembic/`，并把 `alembic.ini` 留在 `backend/`，删除 `alembic_tmp/`：

```bash
cd backend
mv alembic_tmp/env.py alembic/env.py
mv alembic_tmp/script.py.mako alembic/script.py.mako
rm -rf alembic_tmp
```

- [ ] **Step 2: 配置 alembic.ini 的 script_location 与 URL 来源**

编辑 `backend/alembic.ini`：
- `script_location = alembic`
- 移除/留空 `sqlalchemy.url`（改由 env.py 从 settings 读取）。

- [ ] **Step 3: 配置 env.py 接 Base.metadata 与 settings.database_url**

Replace `backend/alembic/env.py` 的相关部分，使其：

```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

from app.core.config import settings
import app.models  # noqa: F401  ensure all models imported
from app.db.base import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=settings.database_url, target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: 生成首版迁移**

确保本地有可连的 MySQL（按 `settings.database_url`，默认 `mysql+pymysql://root:root@localhost:3306/smartsop`，库需先存在）。

Run: `cd backend && alembic revision --autogenerate -m "phase0 platform"`
将产物重命名为 `alembic/versions/0001_phase0_platform.py`（或保留生成名）。

检查产物包含：`companies`、`roles`、`users` 建表，以及各 SOP 表的 `company_id` 列与 `procedures` 的复合唯一约束。

- [ ] **Step 5: 应用迁移确认可用**

Run: `cd backend && alembic upgrade head`
Expected: 无错误；MySQL 中出现上述表。

Run（回滚自检）: `cd backend && alembic downgrade -1 && alembic upgrade head`
Expected: 均成功。

- [ ] **Step 6: 提交**

```bash
cd backend && git add alembic.ini alembic/env.py alembic/script.py.mako alembic/versions/
git commit -m "build(db): set up Alembic + initial Phase 0 platform migration"
```

---

## Task 19: i18n 后端（locale 解析 + message catalog）

**Files:**
- Create: `backend/app/core/i18n.py`
- Test: `backend/tests/test_i18n.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_i18n.py`:

```python
from app.core import i18n


def test_translate_known_key_zh():
    assert i18n.translate("auth.invalid_credentials", "zh-CN") == "邮箱或密码错误"


def test_translate_unknown_key_returns_key():
    assert i18n.translate("nope.nope", "zh-CN") == "nope.nope"


def test_resolve_locale_priority():
    # user locale wins
    assert i18n.resolve_locale(user_locale="zh-CN", accept_language="en") == "zh-CN"
    # falls back to accept-language if supported
    assert i18n.resolve_locale(user_locale=None, accept_language="zh-CN,en;q=0.9") == "zh-CN"
    # falls back to default when nothing supported
    assert i18n.resolve_locale(user_locale=None, accept_language="fr") == "zh-CN"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_i18n.py -v`
Expected: FAIL（`ModuleNotFoundError: app.core.i18n`）

- [ ] **Step 3: 实现**

Create `backend/app/core/i18n.py`:

```python
"""Minimal i18n: locale resolution + message catalog.

Phase 0 ships zh-CN only; architecture allows adding locales by extending
CATALOG and settings.supported_locales.
"""
from __future__ import annotations

from app.core.config import settings

CATALOG: dict[str, dict[str, str]] = {
    "zh-CN": {
        "auth.invalid_credentials": "邮箱或密码错误",
        "auth.account_disabled": "账号已禁用",
        "auth.email_ambiguous": "该邮箱存在于多个公司，请提供公司标识",
        "auth.company_slug_exists": "公司标识已存在",
        "common.not_found": "资源不存在",
        "common.forbidden": "权限不足",
    },
}


def translate(key: str, locale: str | None = None) -> str:
    loc = locale if locale in CATALOG else settings.default_locale
    return CATALOG.get(loc, {}).get(key, key)


def resolve_locale(user_locale: str | None, accept_language: str | None) -> str:
    if user_locale and user_locale in settings.supported_locales:
        return user_locale
    if accept_language:
        for part in accept_language.split(","):
            code = part.split(";")[0].strip()
            if code in settings.supported_locales:
                return code
    return settings.default_locale
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_i18n.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/core/i18n.py tests/test_i18n.py
git commit -m "feat(i18n): backend locale resolution + zh-CN message catalog"
```

---

## Task 20: 前端 i18n 框架 + 品牌改名

**Files:**
- Create: `frontend/src/i18n/index.ts`
- Create: `frontend/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/src/main.ts`（注册 i18n）
- Modify: `frontend/index.html`（标题）+ 品牌展示位
- Modify: `frontend/package.json`（加 `vue-i18n` 依赖、改 name/展示名）

- [ ] **Step 1: 探查前端结构**

Run: `cd frontend && ls src && cat package.json | head -30 && cat index.html`
记录入口（`src/main.ts`）、是否已装 `vue-i18n`、当前标题与品牌出现位置。

- [ ] **Step 2: 安装 vue-i18n**

Run: `cd frontend && npm install vue-i18n@9`
Expected: `package.json` dependencies 出现 `vue-i18n`。

- [ ] **Step 3: 中文语言包**

Create `frontend/src/i18n/locales/zh-CN.ts`:

```typescript
export default {
  app: { name: 'Smart CMMS' },
  auth: {
    login: '登录',
    register: '注册',
    email: '邮箱',
    password: '密码',
    companyName: '公司名称',
  },
  common: {
    save: '保存',
    cancel: '取消',
    delete: '删除',
  },
}
```

- [ ] **Step 4: i18n 实例**

Create `frontend/src/i18n/index.ts`:

```typescript
import { createI18n } from 'vue-i18n'
import zhCN from './locales/zh-CN'

export const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  fallbackLocale: 'zh-CN',
  messages: { 'zh-CN': zhCN },
})

export default i18n
```

- [ ] **Step 5: 注册到应用**

Modify `frontend/src/main.ts` — 在 `createApp(App)` 链上加 `.use(i18n)`：

```typescript
import i18n from './i18n'
// ...
app.use(i18n)
```
（按实际 main.ts 的写法插入；若是 `createApp(App).use(...).mount('#app')` 链式，则插入 `.use(i18n)`。）

- [ ] **Step 6: 品牌改名**

- `frontend/index.html`：`<title>` 改为 `Smart CMMS`。
- 全局搜索前端中展示用的 "SmartSOP" 字样（`cd frontend && grep -rn "SmartSOP" src index.html`），把**用户可见**的展示名替换为 `Smart CMMS`（或改用 `$t('app.name')`）。不改内部变量/包名以免无谓变更。
- `frontend/package.json` 的展示性 `name` 字段可改为 `smart-cmms`（可选）。

- [ ] **Step 7: 构建自检**

Run: `cd frontend && npm run build`
Expected: 构建成功（类型/编译无错误）。

- [ ] **Step 8: 提交**

```bash
cd frontend && git add src/i18n package.json index.html src/main.ts
# 以及被替换品牌字样的文件
git commit -m "feat(i18n,brand): vue-i18n scaffold (zh-CN) + rebrand to Smart CMMS"
```

---

## Task 21: 跨租户隔离集成测试（端到端验收）

通过完整 API 路径验证「A 租户绝对读不到/改不到 B 租户数据」。这是 Phase 0 最高优先级验收。

**Files:**
- Test: `backend/tests/test_cross_tenant_e2e.py`

- [ ] **Step 1: 写测试**

Create `backend/tests/test_cross_tenant_e2e.py`:

```python
def _register(client, company, email):
    r = client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email,
        "password": "secret123", "name": "Admin"})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_users_list_isolated(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    client.post("/api/v1/users", headers=_auth(ta),
                json={"email": "u1@acme.com", "password": "secret123", "name": "U1"})
    client.post("/api/v1/users", headers=_auth(tb),
                json={"email": "u2@globex.com", "password": "secret123", "name": "U2"})

    a_emails = {u["email"] for u in client.get("/api/v1/users", headers=_auth(ta)).json()}
    b_emails = {u["email"] for u in client.get("/api/v1/users", headers=_auth(tb)).json()}
    assert "u1@acme.com" in a_emails and "u2@globex.com" not in a_emails
    assert "u2@globex.com" in b_emails and "u1@acme.com" not in b_emails


def test_cross_tenant_user_fetch_404(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    bob_id = client.post("/api/v1/users", headers=_auth(tb),
        json={"email": "bob@globex.com", "password": "secret123", "name": "Bob"}).json()["id"]
    # Acme admin tries to read Globex user by id
    r = client.get(f"/api/v1/users/{bob_id}", headers=_auth(ta))
    assert r.status_code == 404


def test_cross_tenant_role_update_404(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    b_role_id = [x for x in client.get("/api/v1/roles", headers=_auth(tb)).json()
                 if x["code"] == "viewer"][0]["id"]
    r = client.patch(f"/api/v1/roles/{b_role_id}", headers=_auth(ta),
                     json={"name": "hacked"})
    assert r.status_code == 404


def test_company_me_isolated(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    assert client.get("/api/v1/companies/me", headers=_auth(ta)).json()["slug"] == "acme"
    assert client.get("/api/v1/companies/me", headers=_auth(tb)).json()["slug"] == "globex"
```

- [ ] **Step 2: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_cross_tenant_e2e.py -v`
Expected: PASS（若任何跨租户访问未被拦截，回到 Task 8/14/15 修复作用域或显式校验）。

- [ ] **Step 3: 全量回归**

Run: `cd backend && python -m pytest -v`
Expected: 全部 PASS。

- [ ] **Step 4: 提交**

```bash
cd backend && git add tests/test_cross_tenant_e2e.py
git commit -m "test(tenant): end-to-end cross-tenant isolation acceptance"
```

---

## 验收清单（对照 spec §3 范围）

- [ ] Company 模型 + 自助注册建租户（Task 4, 11, 13）
- [ ] 邮箱密码登录 + JWT access/refresh（Task 9, 11, 13）
- [ ] 用户管理含管理员直接建号（Task 14）
- [ ] 权限点 RBAC + 内置 4 角色播种（Task 5, 6, 11, 15）
- [ ] 租户设置 GET/PATCH /companies/me（Task 16）
- [ ] 租户隔离：自动作用域 + 自动盖章 + 显式兜底（Task 2, 3, 8, 14, 15）
- [ ] i18n 框架（后端 catalog + 前端 vue-i18n，仅中文）（Task 19, 20）
- [ ] 品牌改名 Smart CMMS（Task 9 标题 + Task 20 前端）
- [ ] 现有 SOP 表接入多租户（Task 17）
- [ ] Alembic 迁移（Task 18）
- [ ] 跨租户隔离端到端验收（Task 21）
- [ ] 明确不做项保持未做：邮件邀请、找回密码、运营后台 UI、团队、SSO、计费（仅预留字段/抽象）

---

## 净室合规复核（实现完成后）

- [ ] 全部模型/代码为原创，未参照 Atlas DDL/源码。
- [ ] 代码与产物中无 "Atlas" 字样、商标、文案、资源。
- [ ] 多租户/RBAC 实现为通用工程模式，非受版权保护的具体表达。
