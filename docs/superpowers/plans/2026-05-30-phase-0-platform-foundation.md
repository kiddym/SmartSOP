# Phase 0：平台基座 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Smart CMMS 建立多租户平台基座——租户(Company)、邮箱密码 JWT 认证、用户、权限点 RBAC、租户行级隔离、i18n 框架、品牌改名，并把现有 SOP 表纳入多租户体系。

**Architecture:** 在现有 SmartSOP FastAPI 仓库内扩展（方案 A）。租户隔离用 `company_id` 行级 + SQLAlchemy `do_orm_execute`/`before_flush` 事件钩子（注册在全局 `Session` 类上，应用与测试自动覆盖），租户上下文用 `contextvar` 承载。认证层抽象为可插拔 provider，本期只实现本地密码登录。RBAC 用字符串权限点 code registry + 角色持有 code 列表。

**关键事实（已核对真实代码库，务必遵守）：**
- **扁平布局**：`app/config.py`、`app/db.py`、`app/deps.py`、`app/errors.py`，模型在 `app/models/`，schema 在 `app/schemas/`，服务在 `app/services/`，路由在 `app/routers/`。新代码沿用，**不**新建 `app/core/`、`app/api/`。
- **主键为 UUID 字符串**（`UUIDMixin` → `String(36)`，`default=new_uuid`），表名 `tb_` 前缀。新表 `tb_company`/`tb_user`/`tb_role` 一致；`company_id` 外键为 `String(36)`。
- **路由统一 `/api/v1` 前缀**（如既有 `prefix="/api/v1/folders"`），在 `app/main.py` 直接 `app.include_router(...)`，无聚合 router。本期新增 `/api/v1/auth`、`/api/v1/users`、`/api/v1/roles`、`/api/v1/companies`。
- **Alembic 已配置**（`alembic.ini` + `alembic/env.py` 已接 `app.config.settings` 与 `app.models.base.Base`，含 11 历史迁移）。本期只需 `alembic revision --autogenerate` 生成增量迁移。
- **测试基础设施已存在**（`tests/conftest.py`：function 级 SQLite in-memory `engine`（每测试新建+drop）+ `db`/`client`/`factory` fixtures；pytest 配置在 `pyproject.toml`）。本期**复用**，仅追加 autouse 上下文清理。
- **错误助手**（`app/errors.py`）：有 `bad_request/not_found/conflict/...`，但**无** `unauthorized/forbidden` —— Task 12 需先补这两个。
- **`app/config.py`**：`settings = get_settings()`（lru_cache 单例），**无** `app_name` 字段 —— Task 1 新增。
- **`DATETIME6`**（可移植 datetime）来自 `app.models.base`。业务模型普遍叠 `UUIDMixin, TimestampMixin, SoftDeleteMixin`。
- **租户隔离的双层强度**：
  - 平台表 `tb_company/tb_user/tb_role`：`company_id` **NOT NULL**，完整作用域+盖章；只在 `get_current_user` 建立的请求上下文中访问。
  - SOP 业务表：加 **nullable** `company_id` 并参与作用域（有上下文时），但**不**改动现有无认证 SOP 端点/测试的行为（无上下文 → 不过滤、不盖章 → 行为不变）。**SOP 的认证强制与 NOT NULL 收紧明确推迟到 Phase 1**。此为有意的 Phase 0→1 边界，非遗漏。

**命令约定：** 后端命令假定已激活虚拟环境：`cd backend && source .venv/bin/activate`（环境无全局 `python`）。下文 `python -m pytest` / `alembic` 均在该 venv 内运行。

**Tech Stack:** FastAPI · SQLAlchemy 2.0 (sync) · Pydantic v2 / pydantic-settings · **新增** python-jose[cryptography] + passlib[bcrypt] + email-validator · Alembic（已配置）· MySQL/PyMySQL（生产）· SQLite in-memory（测试）· pytest · TestClient · Vue 3 + vue-i18n（前端）。

**净室合规：** 全新模型，依据领域理解编写，绝不复制 Atlas 源码/DDL/文案/品牌；产物不含 "Atlas" 字样。

---

## 文件结构（本期新建 / 改造）

**新建（后端）**
- `app/tenant.py` — 租户上下文 contextvar + set/get/reset/bypass
- `app/tenant_isolation.py` — `do_orm_execute` + `before_flush` 监听 + 注册到全局 `Session` 类
- `app/permissions.py` — 权限点常量 + registry + 内置角色默认集 + `effective_codes()`
- `app/security.py` — 密码哈希 + JWT 编解码
- `app/i18n.py` — locale 解析 + message catalog
- `app/models/company.py` · `app/models/role.py` · `app/models/user.py`
- `app/schemas/auth.py` · `app/schemas/user.py` · `app/schemas/role.py` · `app/schemas/company.py`
- `app/services/auth_service.py` · `app/services/user_service.py` · `app/services/role_service.py` · `app/services/company_service.py`
- `app/routers/auth.py` · `app/routers/users.py` · `app/routers/roles.py` · `app/routers/company.py`
- `tests/test_*.py`（各任务）
- `alembic/versions/<rev>_phase0_platform.py`（autogenerate 产物）

**改造（后端）**
- `app/config.py` — 新增 `app_name` + JWT/locale 配置
- `app/models/base.py` — 新增 `TenantScoped`/`TenantMixin`/`NullableTenantMixin`
- `app/db.py` — import `app.tenant_isolation` 触发注册；`get_db` 退出清理上下文
- `app/errors.py` — 新增 `unauthorized`/`forbidden`
- `app/deps.py` — 新增 `get_current_user` / `require_permission`
- `app/models/__init__.py` — 注册新模型
- 各 SOP 业务模型 — 叠加 `NullableTenantMixin`
- `app/main.py` — include 新路由；`title` 改 `Smart CMMS API`
- `tests/conftest.py` — autouse 清理上下文
- `requirements.txt` — 加 python-jose[cryptography]、passlib[bcrypt]、email-validator

**前端**
- `frontend/src/i18n/index.ts` · `frontend/src/i18n/locales/zh-CN.ts` · `frontend/src/main.ts` · `frontend/index.html` · 品牌字样替换

---

## Task 1: 依赖与配置（JWT 配置 + 品牌名）

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_config_jwt.py`

- [ ] **Step 1: 加运行时依赖**

Modify `backend/requirements.txt` — 在「数据库」段后追加：

```
# 认证 / 安全（Phase 0 平台基座）
python-jose[cryptography]>=3.3,<4.0
passlib[bcrypt]>=1.7,<2.0
email-validator>=2.1,<3.0
```

Run: `cd backend && pip install -r requirements.txt`
Expected: jose / passlib / email_validator 安装成功。

- [ ] **Step 2: 写失败测试**

Create `backend/tests/test_config_jwt.py`:

```python
from app.config import settings


def test_jwt_settings_present():
    assert settings.secret_key
    assert settings.algorithm == "HS256"
    assert settings.access_token_expire_minutes > 0
    assert settings.refresh_token_expire_days > 0


def test_locale_settings():
    assert settings.default_locale == "zh-CN"
    assert "zh-CN" in settings.supported_locales


def test_app_name_rebranded():
    assert settings.app_name == "Smart CMMS"
```

- [ ] **Step 3: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_config_jwt.py -v`
Expected: FAIL（`AttributeError: ... 'secret_key'`）

- [ ] **Step 4: 扩展配置**

Modify `backend/app/config.py` — 在 `Settings` 类内（如 CORS 段后）新增字段：

```python
    # 品牌
    app_name: str = "Smart CMMS"

    # 认证 / JWT
    secret_key: str = "dev-insecure-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14

    # i18n
    default_locale: str = "zh-CN"
    supported_locales: list[str] = Field(default_factory=lambda: ["zh-CN"])
```

> `Field` 已在 `config.py` 顶部 import。模块级 `settings = get_settings()` 保持不变；测试可用 `get_settings.cache_clear()` 重置（本步骤无需）。

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_config_jwt.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
cd backend && git add requirements.txt app/config.py tests/test_config_jwt.py
git commit -m "feat(config): app_name=Smart CMMS + JWT/locale settings; auth deps"
```

---

## Task 2: 租户上下文 contextvar

**Files:**
- Create: `backend/app/tenant.py`
- Test: `backend/tests/test_tenant_context.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_tenant_context.py`:

```python
from app import tenant


def test_default_is_none():
    assert tenant.get_current_company_id() is None
    assert tenant.is_bypassed() is False


def test_set_and_reset():
    token = tenant.set_current_company_id("c-1")
    assert tenant.get_current_company_id() == "c-1"
    tenant.reset_current_company_id(token)
    assert tenant.get_current_company_id() is None


def test_bypass_context_manager():
    tenant.set_current_company_id("c-1")
    with tenant.bypass_tenant_scope():
        assert tenant.is_bypassed() is True
    assert tenant.is_bypassed() is False
    assert tenant.get_current_company_id() == "c-1"
    tenant.set_current_company_id(None)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_tenant_context.py -v`
Expected: FAIL（`ModuleNotFoundError: app.tenant`）

- [ ] **Step 3: 实现**

Create `backend/app/tenant.py`:

```python
"""Request-scoped tenant context backed by contextvars.

Company ids are UUID strings (see UUIDMixin). None means "no tenant scope"
(pre-auth flows like login/register).
"""
from __future__ import annotations

import contextlib
from contextvars import ContextVar, Token

_company_id: ContextVar[str | None] = ContextVar("company_id", default=None)
_bypass: ContextVar[bool] = ContextVar("tenant_bypass", default=False)


def get_current_company_id() -> str | None:
    return _company_id.get()


def set_current_company_id(company_id: str | None) -> Token:
    return _company_id.set(company_id)


def reset_current_company_id(token: Token) -> None:
    _company_id.reset(token)


def is_bypassed() -> bool:
    return _bypass.get()


@contextlib.contextmanager
def bypass_tenant_scope():
    """Temporarily disable tenant scoping (platform-admin / pre-auth lookups)."""
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
cd backend && git add app/tenant.py tests/test_tenant_context.py
git commit -m "feat(tenant): request-scoped tenant context via contextvars"
```

---

## Task 3: 租户 Mixin（NOT NULL + nullable + 作用域标记）

**Files:**
- Modify: `backend/app/models/base.py`
- Test: `backend/tests/test_tenant_mixin.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_tenant_mixin.py`:

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScoped, TenantMixin, NullableTenantMixin, UUIDMixin


class _Strict(Base, UUIDMixin, TenantMixin):
    __tablename__ = "_strict_tenant"
    name: Mapped[str] = mapped_column(String(50))


class _Loose(Base, UUIDMixin, NullableTenantMixin):
    __tablename__ = "_loose_tenant"
    name: Mapped[str] = mapped_column(String(50))


def test_strict_not_null_and_scoped():
    assert issubclass(_Strict, TenantScoped)
    assert _Strict.__table__.columns["company_id"].nullable is False


def test_loose_nullable_and_scoped():
    assert issubclass(_Loose, TenantScoped)
    assert _Loose.__table__.columns["company_id"].nullable is True
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_tenant_mixin.py -v`
Expected: FAIL（`ImportError: cannot import name 'TenantScoped'`）

- [ ] **Step 3: 实现（在 base.py 追加）**

Modify `backend/app/models/base.py` — 顶部 import 行 `from sqlalchemy import Boolean, DateTime, MetaData, String, Text` 改为加入 `ForeignKey`：`from sqlalchemy import Boolean, DateTime, ForeignKey, MetaData, String, Text`。在文件末尾追加：

```python
class TenantScoped:
    """Marker base for any entity participating in tenant row-level scoping.

    The isolation events (do_orm_execute / before_flush) target this marker,
    so both NOT-NULL platform tables and nullable SOP tables are covered.
    """


class TenantMixin(TenantScoped):
    """Platform tables: company_id is required (NOT NULL)."""

    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_company.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )


class NullableTenantMixin(TenantScoped):
    """SOP tables (Phase 0): company_id nullable; enforcement deferred to Phase 1."""

    company_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_company.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_tenant_mixin.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/models/base.py tests/test_tenant_mixin.py
git commit -m "feat(tenant): TenantScoped marker + TenantMixin + NullableTenantMixin"
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
    assert c.id is not None and len(c.id) == 36
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
"""Company: the tenant root. Not tenant-scoped — its id IS the tenant id."""
from __future__ import annotations

import enum

from sqlalchemy import String, Boolean, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin


class CompanyStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"


class Company(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tb_company"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[CompanyStatus] = mapped_column(
        SAEnum(CompanyStatus), nullable=False, default=CompanyStatus.active
    )
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="zh-CN")
    # Reserved: platform-operator org (Phase 0: always False, no UI).
    is_platform_admin_org: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Reserved billing placeholders (Phase 6) — no logic attached.
    plan: Mapped[str | None] = mapped_column(String(32), nullable=True)
    subscription_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
```

- [ ] **Step 4: 注册模型**

Modify `backend/app/models/__init__.py` — 加 `from app.models.company import Company`，`"Company"` 入 `__all__`。

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_company_model.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
cd backend && git add app/models/company.py app/models/__init__.py tests/test_company_model.py
git commit -m "feat(company): add Company tenant-root model (tb_company)"
```

---

## Task 5: 权限点 registry

**Files:**
- Create: `backend/app/permissions.py`
- Test: `backend/tests/test_permissions.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_permissions.py`:

```python
from app import permissions as perms


def test_registry_contains_platform_codes():
    assert "user.create" in perms.ALL_PERMISSIONS
    assert "role.manage" in perms.ALL_PERMISSIONS
    assert "company.settings" in perms.ALL_PERMISSIONS


def test_builtin_roles_present():
    assert {r["code"] for r in perms.BUILTIN_ROLES} == {
        "super_admin", "admin", "technician", "viewer"}


def test_super_admin_gets_all():
    sa = next(r for r in perms.BUILTIN_ROLES if r["code"] == "super_admin")
    assert set(sa["permissions"]) == set(perms.ALL_PERMISSIONS)


def test_viewer_only_view():
    viewer = next(r for r in perms.BUILTIN_ROLES if r["code"] == "viewer")
    assert all(c.endswith(".view") for c in viewer["permissions"])


def test_effective_codes_super_admin_wildcard():
    assert perms.effective_codes("super_admin", []) == set(perms.ALL_PERMISSIONS)


def test_effective_codes_regular():
    assert perms.effective_codes("admin", ["user.view"]) == {"user.view"}
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_permissions.py -v`
Expected: FAIL（`ModuleNotFoundError: app.permissions`）

- [ ] **Step 3: 实现**

Create `backend/app/permissions.py`:

```python
"""Permission-code registry + built-in role defaults.

Phase 0 declares only platform-layer codes. Later phases append module codes
here; built-in role default sets get extended accordingly.
"""
from __future__ import annotations

USER_CREATE = "user.create"
USER_VIEW = "user.view"
USER_EDIT = "user.edit"
USER_DELETE = "user.delete"
ROLE_VIEW = "role.view"
ROLE_MANAGE = "role.manage"
COMPANY_SETTINGS = "company.settings"

ALL_PERMISSIONS: list[str] = [
    USER_CREATE, USER_VIEW, USER_EDIT, USER_DELETE,
    ROLE_VIEW, ROLE_MANAGE, COMPANY_SETTINGS,
]

BUILTIN_ROLES: list[dict] = [
    {"code": "super_admin", "name": "超级管理员", "permissions": list(ALL_PERMISSIONS)},
    {"code": "admin", "name": "管理员", "permissions": [
        USER_CREATE, USER_VIEW, USER_EDIT, USER_DELETE,
        ROLE_VIEW, ROLE_MANAGE, COMPANY_SETTINGS]},
    {"code": "technician", "name": "技术员", "permissions": [USER_VIEW, ROLE_VIEW]},
    {"code": "viewer", "name": "只读", "permissions": [
        c for c in ALL_PERMISSIONS if c.endswith(".view")]},
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
cd backend && git add app/permissions.py tests/test_permissions.py
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

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin


class Role(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_role"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_role_company_code"),)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    permissions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
```

- [ ] **Step 4: 注册模型**

Modify `backend/app/models/__init__.py` — 加 `from app.models.role import Role`，`"Role"` 入 `__all__`。

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_role_model.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
cd backend && git add app/models/role.py app/models/__init__.py tests/test_role_model.py
git commit -m "feat(rbac): add Role model (tb_role, JSON permission codes)"
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
from app.models.user import User, UserStatus


def _company(db, slug):
    c = Company(name=slug, slug=slug)
    db.add(c)
    db.commit()
    return c


def test_user_defaults(db):
    c = _company(db, "acme")
    u = User(company_id=c.id, email="a@acme.com", password_hash="x", name="Alice")
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


def test_same_email_across_companies(db):
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
from datetime import datetime

from sqlalchemy import String, Boolean, ForeignKey, Enum as SAEnum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, DATETIME6


class UserStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"


class User(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_user"
    __table_args__ = (UniqueConstraint("company_id", "email", name="uq_user_company_email"),)

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        SAEnum(UserStatus), nullable=False, default=UserStatus.active
    )
    role_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_role.id", ondelete="SET NULL"), nullable=True
    )
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="zh-CN")
    last_login_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    # Reserved: platform-operator identity (Phase 0: always False).
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

- [ ] **Step 4: 注册模型**

Modify `backend/app/models/__init__.py` — 加 `from app.models.user import User`，`"User"` 入 `__all__`。

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_user_model.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
cd backend && git add app/models/user.py app/models/__init__.py tests/test_user_model.py
git commit -m "feat(user): add User model (tb_user, email unique per company)"
```

---

## Task 8: 租户隔离事件 + 全局注册 + 测试上下文清理

**Files:**
- Create: `backend/app/tenant_isolation.py`
- Modify: `backend/app/db.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_tenant_isolation.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_tenant_isolation.py`:

```python
from sqlalchemy import select

from app import tenant
from app.models.company import Company
from app.models.role import Role


def _mk(db, slug):
    c = Company(name=slug, slug=slug)
    db.add(c)
    db.commit()
    return c


def test_auto_stamp_on_insert(db):
    c = _mk(db, "acme")
    token = tenant.set_current_company_id(c.id)
    try:
        r = Role(code="x", name="X", permissions=[])  # no company_id
        db.add(r)
        db.commit()
        db.refresh(r)
        assert r.company_id == c.id
    finally:
        tenant.reset_current_company_id(token)


def test_read_scoped(db):
    c1 = _mk(db, "acme"); c2 = _mk(db, "globex")
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
    c1 = _mk(db, "acme"); c2 = _mk(db, "globex")
    db.add(Role(company_id=c1.id, code="r1", name="R1", permissions=[]))
    db.add(Role(company_id=c2.id, code="r2", name="R2", permissions=[]))
    db.commit()
    # autouse fixture clears context => no scope; login relies on this.
    rows = db.execute(select(Role)).scalars().all()
    assert {r.code for r in rows} == {"r1", "r2"}
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_tenant_isolation.py -v`
Expected: FAIL（事件未注册 → 自动盖章/作用域不生效）

- [ ] **Step 3: 实现事件模块（注册到全局 Session 类）**

Create `backend/app/tenant_isolation.py`:

```python
"""SQLAlchemy event listeners enforcing row-level tenant isolation.

Registered on the global Session class so every session (app + tests) is
covered. Skipped when no tenant context is set (pre-auth flows) or bypassed.
"""
from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria

from app import tenant
from app.models.base import TenantScoped


def _before_flush(session, flush_context, instances) -> None:
    if tenant.is_bypassed():
        return
    company_id = tenant.get_current_company_id()
    if company_id is None:
        return
    for obj in session.new:
        if isinstance(obj, TenantScoped) and getattr(obj, "company_id", None) is None:
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
            TenantScoped,
            lambda cls: cls.company_id == company_id,
            include_aliases=True,
        )
    )


def register_tenant_events() -> None:
    """Idempotently attach listeners to the global Session class."""
    if not event.contains(Session, "before_flush", _before_flush):
        event.listen(Session, "before_flush", _before_flush)
    if not event.contains(Session, "do_orm_execute", _do_orm_execute):
        event.listen(Session, "do_orm_execute", _do_orm_execute)


register_tenant_events()
```

- [ ] **Step 4: 在 app/db.py 触发注册 + 请求结束清理上下文**

Modify `backend/app/db.py`：
- 顶部 import 区追加：`import app.tenant_isolation  # noqa: F401  registers tenant events`
- 把 `get_db` 改为：

```python
def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：每请求一个 session，结束后关闭并清理租户上下文。"""
    from app import tenant
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        tenant.set_current_company_id(None)
```

> `import app.tenant_isolation` 会 import `app.models.base`（含 `TenantScoped`）—— 确保 Task 3 已完成。注册在全局 `Session` 类上，故 conftest 中基于 `Session(engine)` 的测试会话也自动生效。

- [ ] **Step 5: conftest 追加 autouse 上下文清理**

Modify `backend/tests/conftest.py` — 文件末尾追加：

```python
@pytest.fixture(autouse=True)
def _clear_tenant_context():
    """Each test starts/ends with no tenant scope (prevents leakage)."""
    from app import tenant
    tenant.set_current_company_id(None)
    yield
    tenant.set_current_company_id(None)
```

> 仅清理上下文、不强制租户：既保证测试间隔离，又不破坏「无上下文」语义。既有 SOP 测试不设上下文 → SOP 表 `company_id` 可空 → 不盖章、不过滤 → 行为不变。

- [ ] **Step 6: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_tenant_isolation.py -v`
Expected: PASS

- [ ] **Step 7: 全量回归（确认未破坏既有测试）**

Run: `cd backend && python -m pytest -q`
Expected: 全部 PASS。

- [ ] **Step 8: 提交**

```bash
cd backend && git add app/tenant_isolation.py app/db.py tests/conftest.py tests/test_tenant_isolation.py
git commit -m "feat(tenant): global ORM isolation events (auto-scope + auto-stamp)"
```

---

## Task 9: 安全/JWT（app/security.py）

**Files:**
- Create: `backend/app/security.py`
- Test: `backend/tests/test_security.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_security.py`:

```python
import pytest

from app import security


def test_hash_and_verify():
    h = security.hash_password("secret123")
    assert h != "secret123"
    assert security.verify_password("secret123", h) is True
    assert security.verify_password("wrong", h) is False


def test_access_token_roundtrip():
    token = security.create_access_token(user_id="u-5", company_id="c-9", role_code="admin")
    claims = security.decode_token(token)
    assert claims["sub"] == "u-5"
    assert claims["company_id"] == "c-9"
    assert claims["role_code"] == "admin"
    assert claims["type"] == "access"


def test_refresh_token_type():
    token = security.create_refresh_token(user_id="u-5", company_id="c-9", role_code="admin")
    assert security.decode_token(token)["type"] == "refresh"


def test_decode_invalid_raises():
    with pytest.raises(security.TokenError):
        security.decode_token("not-a-token")
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_security.py -v`
Expected: FAIL（`ModuleNotFoundError: app.security`）

- [ ] **Step 3: 实现**

Create `backend/app/security.py`:

```python
"""Security utilities: password hashing and JWT tokens."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenError(Exception):
    """Raised when a JWT cannot be decoded or is invalid."""


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _create_token(*, user_id: str, company_id: str, role_code: str | None,
                  token_type: str, expires_delta: timedelta) -> str:
    payload = {
        "sub": user_id,
        "company_id": company_id,
        "role_code": role_code,
        "type": token_type,
        "exp": datetime.now(timezone.utc) + expires_delta,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(*, user_id: str, company_id: str, role_code: str | None) -> str:
    return _create_token(user_id=user_id, company_id=company_id, role_code=role_code,
                         token_type="access",
                         expires_delta=timedelta(minutes=settings.access_token_expire_minutes))


def create_refresh_token(*, user_id: str, company_id: str, role_code: str | None) -> str:
    return _create_token(user_id=user_id, company_id=company_id, role_code=role_code,
                         token_type="refresh",
                         expires_delta=timedelta(days=settings.refresh_token_expire_days))


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise TokenError(str(exc)) from exc
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_security.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/security.py tests/test_security.py
git commit -m "feat(auth): password hashing + JWT tokens with tenant/role claims"
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


def test_register_valid():
    r = RegisterRequest(company_name="Acme", email="a@acme.com",
                        password="secret123", name="Alice")
    assert r.email == "a@acme.com"


def test_register_rejects_short_password():
    with pytest.raises(ValidationError):
        RegisterRequest(company_name="Acme", email="a@acme.com", password="x", name="Alice")


def test_login_optional_slug():
    assert LoginRequest(email="a@acme.com", password="secret123").company_slug is None


def test_token_pair_default_type():
    assert TokenPair(access_token="a", refresh_token="r").token_type == "bearer"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_auth_schemas.py -v`
Expected: FAIL（`ModuleNotFoundError: app.schemas.auth`）

- [ ] **Step 3: 实现**

Create `backend/app/schemas/auth.py`:

```python
"""Auth request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    company_slug: str | None = None  # disambiguates email across tenants


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class CurrentUser(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    email: EmailStr
    name: str
    company_id: str
    role_code: str | None = None
    permissions: list[str] = []
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_auth_schemas.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/schemas/auth.py tests/test_auth_schemas.py
git commit -m "feat(auth): auth request/response schemas"
```

---

## Task 11: Auth service（注册建租户 / 登录）

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


def _register(db, company="Acme", email="a@acme.com"):
    return auth_service.register(db, RegisterRequest(
        company_name=company, email=email, password="secret123", name="Alice"))


def test_register_creates_company_and_4_roles(db):
    user = _register(db)
    company = db.get(Company, user.company_id)
    assert company is not None
    from app import tenant
    token = tenant.set_current_company_id(company.id)
    try:
        roles = db.execute(select(Role)).scalars().all()
    finally:
        tenant.reset_current_company_id(token)
    assert {r.code for r in roles} == {"super_admin", "admin", "technician", "viewer"}
    sa = next(r for r in roles if r.code == "super_admin")
    assert user.role_id == sa.id


def test_register_duplicate_slug_raises(db):
    _register(db, company="Acme")
    with pytest.raises(auth_service.AuthError):
        _register(db, company="Acme", email="b@acme.com")


def test_login_success(db):
    _register(db)
    user = auth_service.authenticate(db, LoginRequest(email="a@acme.com", password="secret123"))
    assert user.email == "a@acme.com"


def test_login_wrong_password(db):
    _register(db)
    with pytest.raises(auth_service.AuthError):
        auth_service.authenticate(db, LoginRequest(email="a@acme.com", password="nope"))


def test_login_ambiguous_email_requires_slug(db):
    auth_service.register(db, RegisterRequest(company_name="Acme",
        email="same@x.com", password="secret123", name="A"))
    auth_service.register(db, RegisterRequest(company_name="Globex",
        email="same@x.com", password="secret123", name="B"))
    with pytest.raises(auth_service.AuthError):
        auth_service.authenticate(db, LoginRequest(email="same@x.com", password="secret123"))
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
"""Auth service: self-service registration (creates tenant) + login.

Pre-auth flows run with no tenant context, so cross-tenant lookups work.
register() sets context to the new company before seeding roles/user so the
isolation events stamp them correctly.
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import tenant, security
from app.permissions import BUILTIN_ROLES
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
        if db.execute(select(Company).where(Company.slug == slug)).scalar_one_or_none():
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
        candidates = db.execute(
            select(User).where(User.email == payload.email)
        ).scalars().all()
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

## Task 12: errors 补充 + Auth 依赖（get_current_user / require_permission）

**Files:**
- Modify: `backend/app/errors.py`
- Modify: `backend/app/deps.py`
- Test: `backend/tests/test_auth_deps.py`

- [ ] **Step 1: 补 errors 助手**

Modify `backend/app/errors.py` — 追加（`status` 已 import）：

```python
def unauthorized(code: str, message: str, field: str | None = None) -> HTTPException:
    return app_error(status.HTTP_401_UNAUTHORIZED, code, message, field)


def forbidden(code: str, message: str, field: str | None = None) -> HTTPException:
    return app_error(status.HTTP_403_FORBIDDEN, code, message, field)
```

- [ ] **Step 2: 写失败测试**

Create `backend/tests/test_auth_deps.py`:

```python
import pytest
from fastapi import HTTPException

from app import deps, security, tenant
from app.services import auth_service
from app.schemas.auth import RegisterRequest


def _register(db):
    return auth_service.register(db, RegisterRequest(
        company_name="Acme", email="a@acme.com", password="secret123", name="A"))


def test_get_current_user_sets_context(db):
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
```

- [ ] **Step 3: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_auth_deps.py -v`
Expected: FAIL（`AttributeError: module app.deps has no attribute get_current_user`）

- [ ] **Step 4: 实现（在 deps.py 追加）**

Modify `backend/app/deps.py` — 顶部已 `from app.db import get_db`。追加 import 与函数（保留既有 `RequestMeta`/`get_request_meta`/`__all__`）：

```python
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app import security, tenant
from app.errors import unauthorized, forbidden
from app.permissions import effective_codes
from app.models.role import Role
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise unauthorized("UNAUTHENTICATED", "未认证")
    try:
        claims = security.decode_token(token)
    except security.TokenError:
        raise unauthorized("INVALID_TOKEN", "无效的令牌")
    if claims.get("type") != "access":
        raise unauthorized("INVALID_TOKEN", "令牌类型错误")
    company_id = claims.get("company_id")
    user_id = claims.get("sub")
    tenant.set_current_company_id(company_id)  # scope before loading
    user = db.get(User, user_id)
    if user is None or user.company_id != company_id:
        raise unauthorized("USER_NOT_FOUND", "用户不存在")
    return user


def _user_permission_codes(db: Session, user: User) -> set[str]:
    role_code, stored = "", []
    if user.role_id is not None:
        role = db.get(Role, user.role_id)
        if role is not None:
            role_code, stored = role.code, (role.permissions or [])
    return effective_codes(role_code, stored)


def require_permission(code: str):
    """Return a dependency enforcing the given permission code."""
    def checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if code not in _user_permission_codes(db, current_user):
            raise forbidden("FORBIDDEN", "权限不足")
        return current_user
    return checker
```

> 把 `get_current_user`/`require_permission` 也加入 `__all__`。

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_auth_deps.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
cd backend && git add app/errors.py app/deps.py tests/test_auth_deps.py
git commit -m "feat(auth): unauthorized/forbidden helpers + get_current_user + require_permission"
```

---

## Task 13: Auth 路由（/api/v1/auth）

**Files:**
- Create: `backend/app/routers/auth.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_auth_api.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_auth_api.py`:

```python
def _register(client, company="Acme", email="a@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email, "password": "secret123", "name": "Alice"})


def test_register_returns_tokens(client):
    r = _register(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_login_then_me(client):
    _register(client)
    r = client.post("/api/v1/auth/login", json={"email": "a@acme.com", "password": "secret123"})
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
    r = client.post("/api/v1/auth/login", json={"email": "a@acme.com", "password": "wrong"})
    assert r.status_code == 401


def test_refresh(client):
    reg = _register(client).json()
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": reg["refresh_token"]})
    assert r.status_code == 200, r.text
    assert r.json()["access_token"]


def test_me_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_auth_api.py -v`
Expected: FAIL（404）

- [ ] **Step 3: 实现路由**

Create `backend/app/routers/auth.py`:

```python
"""Auth API (/api/v1/auth)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import security, tenant
from app.deps import get_db, get_current_user, _user_permission_codes
from app.errors import conflict, unauthorized
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import (
    RegisterRequest, LoginRequest, RefreshRequest, TokenPair, CurrentUser,
)
from app.services import auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _role_code(db: Session, user: User) -> str | None:
    if user.role_id is None:
        return None
    role = db.get(Role, user.role_id)
    return role.code if role else None


def _tokens(db: Session, user: User) -> TokenPair:
    rc = _role_code(db, user)
    return TokenPair(
        access_token=security.create_access_token(
            user_id=user.id, company_id=user.company_id, role_code=rc),
        refresh_token=security.create_refresh_token(
            user_id=user.id, company_id=user.company_id, role_code=rc),
    )


@router.post("/register", response_model=TokenPair, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    try:
        user = auth_service.register(db, payload)
    except auth_service.AuthError as exc:
        raise conflict("COMPANY_EXISTS", str(exc))
    return _tokens(db, user)


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        user = auth_service.authenticate(db, payload)
    except auth_service.AuthError as exc:
        raise unauthorized("LOGIN_FAILED", str(exc))
    return _tokens(db, user)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        claims = security.decode_token(payload.refresh_token)
    except security.TokenError:
        raise unauthorized("INVALID_TOKEN", "无效的令牌")
    if claims.get("type") != "refresh":
        raise unauthorized("INVALID_TOKEN", "令牌类型错误")
    tenant.set_current_company_id(claims.get("company_id"))
    user = db.get(User, claims.get("sub"))
    if user is None:
        raise unauthorized("USER_NOT_FOUND", "用户不存在")
    return _tokens(db, user)


@router.get("/me", response_model=CurrentUser)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return CurrentUser(
        id=current_user.id, email=current_user.email, name=current_user.name,
        company_id=current_user.company_id, role_code=_role_code(db, current_user),
        permissions=sorted(_user_permission_codes(db, current_user)),
    )
```

- [ ] **Step 4: 挂载路由 + 改标题**

Modify `backend/app/main.py`：
- 在 `from app.routers import (...)` 之后另起一行 `from app.routers import auth`。
- 在 `app.include_router(...)` 区加 `app.include_router(auth.router)`。
- `app = FastAPI(title="Smart SOP API", ...)` 的 `title` 改为 `"Smart CMMS API"`；可顺手把 lifespan 内日志字符串 `"Smart SOP API ..."` 改为 `"Smart CMMS API ..."`（可选）。

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_auth_api.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
cd backend && git add app/routers/auth.py app/main.py tests/test_auth_api.py
git commit -m "feat(auth): /api/v1/auth register/login/refresh/me; title=Smart CMMS API"
```

---

## Task 14: 用户管理 API（/api/v1/users）

含「管理员直接建号」（非邮件邀请）。

**Files:**
- Create: `backend/app/schemas/user.py`
- Create: `backend/app/services/user_service.py`
- Create: `backend/app/routers/users.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_users_api.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_users_api.py`:

```python
def _admin(client):
    return client.post("/api/v1/auth/register", json={
        "company_name": "Acme", "email": "admin@acme.com",
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_admin_creates_user(client):
    t = _admin(client)
    r = client.post("/api/v1/users", headers=_h(t), json={
        "email": "bob@acme.com", "password": "secret123", "name": "Bob"})
    assert r.status_code == 201, r.text
    assert r.json()["email"] == "bob@acme.com"


def test_list_users_scoped(client):
    t = _admin(client)
    client.post("/api/v1/users", headers=_h(t), json={
        "email": "bob@acme.com", "password": "secret123", "name": "Bob"})
    emails = {u["email"] for u in client.get("/api/v1/users", headers=_h(t)).json()}
    assert emails == {"admin@acme.com", "bob@acme.com"}


def test_create_requires_auth(client):
    r = client.post("/api/v1/users", json={
        "email": "x@acme.com", "password": "secret123", "name": "X"})
    assert r.status_code == 401


def test_new_user_can_login(client):
    t = _admin(client)
    client.post("/api/v1/users", headers=_h(t), json={
        "email": "bob@acme.com", "password": "secret123", "name": "Bob"})
    r = client.post("/api/v1/auth/login", json={
        "email": "bob@acme.com", "password": "secret123", "company_slug": "acme"})
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

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.models.user import UserStatus


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    role_id: str | None = None


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    role_id: str | None = None
    status: UserStatus | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: EmailStr
    name: str
    status: UserStatus
    role_id: str | None = None
    locale: str
    last_login_at: datetime | None = None
    created_at: datetime
```

- [ ] **Step 4: 实现 service**

Create `backend/app/services/user_service.py`:

```python
"""User management service (tenant-scoped via ORM events)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import security
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


def create_user(db: Session, payload: UserCreate) -> User:
    user = User(email=payload.email,
                password_hash=security.hash_password(payload.password),
                name=payload.name, role_id=payload.role_id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session) -> list[User]:
    return list(db.execute(select(User)).scalars().all())


def get_user(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def update_user(db: Session, user_id: str, payload: UserUpdate) -> User | None:
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


def delete_user(db: Session, user_id: str) -> None:
    user = db.get(User, user_id)
    if user:
        db.delete(user)
        db.commit()
```

> `db.get()` 走主键直取，**不经过** `do_orm_execute` 作用域 → 可能取到他租户对象。路由层用 `_ensure_same_tenant` 显式校验兜底（Step 5）。

- [ ] **Step 5: 实现路由（含跨租户显式校验）**

Create `backend/app/routers/users.py`:

```python
"""User management API (/api/v1/users)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import permissions, tenant
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _ensure_same_tenant(obj: User | None) -> User:
    if obj is None or obj.company_id != tenant.get_current_company_id():
        raise not_found("USER_NOT_FOUND", "用户不存在")
    return obj


@router.post("", response_model=UserRead, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db),
                _: User = Depends(require_permission(permissions.USER_CREATE))):
    return user_service.create_user(db, payload)


@router.get("", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db),
               _: User = Depends(require_permission(permissions.USER_VIEW))):
    return user_service.list_users(db)


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: str, db: Session = Depends(get_db),
             _: User = Depends(require_permission(permissions.USER_VIEW))):
    return _ensure_same_tenant(user_service.get_user(db, user_id))


@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: str, payload: UserUpdate, db: Session = Depends(get_db),
                _: User = Depends(require_permission(permissions.USER_EDIT))):
    _ensure_same_tenant(user_service.get_user(db, user_id))
    return user_service.update_user(db, user_id, payload)


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: str, db: Session = Depends(get_db),
                _: User = Depends(require_permission(permissions.USER_DELETE))):
    _ensure_same_tenant(user_service.get_user(db, user_id))
    user_service.delete_user(db, user_id)
```

- [ ] **Step 6: 挂载路由**

Modify `backend/app/main.py`：加 `from app.routers import users`；加 `app.include_router(users.router)`。

- [ ] **Step 7: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_users_api.py -v`
Expected: PASS

- [ ] **Step 8: 提交**

```bash
cd backend && git add app/schemas/user.py app/services/user_service.py app/routers/users.py app/main.py tests/test_users_api.py
git commit -m "feat(users): admin user CRUD (/api/v1/users)"
```

---

## Task 15: 角色管理 API（/api/v1/roles）

**Files:**
- Create: `backend/app/schemas/role.py`
- Create: `backend/app/services/role_service.py`
- Create: `backend/app/routers/roles.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_roles_api.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_roles_api.py`:

```python
def _admin(client):
    return client.post("/api/v1/auth/register", json={
        "company_name": "Acme", "email": "admin@acme.com",
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_list_seeded_roles(client):
    t = _admin(client)
    codes = {x["code"] for x in client.get("/api/v1/roles", headers=_h(t)).json()}
    assert codes == {"super_admin", "admin", "technician", "viewer"}


def test_create_custom_role(client):
    t = _admin(client)
    r = client.post("/api/v1/roles", headers=_h(t), json={
        "code": "planner", "name": "计划员", "permissions": ["user.view"]})
    assert r.status_code == 201, r.text
    assert r.json()["permissions"] == ["user.view"]


def test_reject_unknown_permission(client):
    t = _admin(client)
    r = client.post("/api/v1/roles", headers=_h(t), json={
        "code": "x", "name": "X", "permissions": ["does.not.exist"]})
    assert r.status_code == 422


def test_update_role(client):
    t = _admin(client)
    rid = client.post("/api/v1/roles", headers=_h(t), json={
        "code": "planner", "name": "计划员", "permissions": ["user.view"]}).json()["id"]
    r = client.patch(f"/api/v1/roles/{rid}", headers=_h(t),
                     json={"permissions": ["user.view", "user.create"]})
    assert r.status_code == 200
    assert set(r.json()["permissions"]) == {"user.view", "user.create"}


def test_cannot_delete_builtin(client):
    t = _admin(client)
    rid = [x for x in client.get("/api/v1/roles", headers=_h(t)).json()
           if x["code"] == "admin"][0]["id"]
    assert client.delete(f"/api/v1/roles/{rid}", headers=_h(t)).status_code == 400
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_roles_api.py -v`
Expected: FAIL（404）

- [ ] **Step 3: 实现 schema（含权限点校验）**

Create `backend/app/schemas/role.py`:

```python
"""Role management schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.permissions import ALL_PERMISSIONS


def _validate(codes: list[str]) -> list[str]:
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
    def _check(cls, v): return _validate(v)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    permissions: list[str] | None = None

    @field_validator("permissions")
    @classmethod
    def _check(cls, v): return None if v is None else _validate(v)


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
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


def create_role(db: Session, payload: RoleCreate) -> Role:
    role = Role(code=payload.code, name=payload.name,
                is_builtin=False, permissions=payload.permissions)
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def list_roles(db: Session) -> list[Role]:
    return list(db.execute(select(Role)).scalars().all())


def get_role(db: Session, role_id: str) -> Role | None:
    return db.get(Role, role_id)


def update_role(db: Session, role_id: str, payload: RoleUpdate) -> Role | None:
    role = db.get(Role, role_id)
    if role is None:
        return None
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(role, k, v)
    db.commit()
    db.refresh(role)
    return role


def delete_role(db: Session, role_id: str) -> None:
    role = db.get(Role, role_id)
    if role:
        db.delete(role)
        db.commit()
```

- [ ] **Step 5: 实现路由**

Create `backend/app/routers/roles.py`:

```python
"""Role management API (/api/v1/roles)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import permissions, tenant
from app.deps import get_db, require_permission
from app.errors import not_found, bad_request
from app.models.role import Role
from app.models.user import User
from app.schemas.role import RoleCreate, RoleRead, RoleUpdate
from app.services import role_service

router = APIRouter(prefix="/api/v1/roles", tags=["roles"])


def _ensure_same_tenant(role: Role | None) -> Role:
    if role is None or role.company_id != tenant.get_current_company_id():
        raise not_found("ROLE_NOT_FOUND", "角色不存在")
    return role


@router.get("", response_model=list[RoleRead])
def list_roles(db: Session = Depends(get_db),
               _: User = Depends(require_permission(permissions.ROLE_VIEW))):
    return role_service.list_roles(db)


@router.post("", response_model=RoleRead, status_code=201)
def create_role(payload: RoleCreate, db: Session = Depends(get_db),
                _: User = Depends(require_permission(permissions.ROLE_MANAGE))):
    return role_service.create_role(db, payload)


@router.patch("/{role_id}", response_model=RoleRead)
def update_role(role_id: str, payload: RoleUpdate, db: Session = Depends(get_db),
                _: User = Depends(require_permission(permissions.ROLE_MANAGE))):
    _ensure_same_tenant(role_service.get_role(db, role_id))
    return role_service.update_role(db, role_id, payload)


@router.delete("/{role_id}", status_code=204)
def delete_role(role_id: str, db: Session = Depends(get_db),
                _: User = Depends(require_permission(permissions.ROLE_MANAGE))):
    role = _ensure_same_tenant(role_service.get_role(db, role_id))
    if role.is_builtin:
        raise bad_request("ROLE_BUILTIN", "内置角色不可删除")
    role_service.delete_role(db, role_id)
```

- [ ] **Step 6: 挂载路由**

Modify `backend/app/main.py`：加 `from app.routers import roles`；加 `app.include_router(roles.router)`。

- [ ] **Step 7: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_roles_api.py -v`
Expected: PASS

- [ ] **Step 8: 提交**

```bash
cd backend && git add app/schemas/role.py app/services/role_service.py app/routers/roles.py app/main.py tests/test_roles_api.py
git commit -m "feat(rbac): role management API (/api/v1/roles, builtin guard)"
```

---

## Task 16: 租户设置 API（/api/v1/companies/me）

**Files:**
- Create: `backend/app/schemas/company.py`
- Create: `backend/app/services/company_service.py`
- Create: `backend/app/routers/company.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_company_api.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_company_api.py`:

```python
def _admin(client):
    return client.post("/api/v1/auth/register", json={
        "company_name": "Acme", "email": "admin@acme.com",
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_get_company_me(client):
    t = _admin(client)
    r = client.get("/api/v1/companies/me", headers=_h(t))
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Acme"
    assert r.json()["locale"] == "zh-CN"


def test_update_company(client):
    t = _admin(client)
    r = client.patch("/api/v1/companies/me", headers=_h(t), json={"name": "Acme Inc"})
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

from pydantic import BaseModel, Field, ConfigDict

from app.models.company import CompanyStatus


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    slug: str
    status: CompanyStatus
    locale: str


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    locale: str | None = Field(default=None, max_length=16)
```

- [ ] **Step 4: 实现 service**

Create `backend/app/services/company_service.py`:

```python
"""Company settings service."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.company import Company
from app.schemas.company import CompanyUpdate


def get_company(db: Session, company_id: str) -> Company | None:
    return db.get(Company, company_id)


def update_company(db: Session, company_id: str, payload: CompanyUpdate) -> Company | None:
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

Create `backend/app/routers/company.py`:

```python
"""Company (tenant) settings API (/api/v1/companies)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, get_current_user, require_permission
from app.errors import not_found
from app.models.user import User
from app.schemas.company import CompanyRead, CompanyUpdate
from app.services import company_service

router = APIRouter(prefix="/api/v1/companies", tags=["companies"])


@router.get("/me", response_model=CompanyRead)
def get_my_company(current_user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    company = company_service.get_company(db, current_user.company_id)
    if company is None:
        raise not_found("COMPANY_NOT_FOUND", "公司不存在")
    return company


@router.patch("/me", response_model=CompanyRead)
def update_my_company(
    payload: CompanyUpdate,
    current_user: User = Depends(require_permission(permissions.COMPANY_SETTINGS)),
    db: Session = Depends(get_db),
):
    company = company_service.update_company(db, current_user.company_id, payload)
    if company is None:
        raise not_found("COMPANY_NOT_FOUND", "公司不存在")
    return company
```

- [ ] **Step 6: 挂载路由**

Modify `backend/app/main.py`：加 `from app.routers import company`；加 `app.include_router(company.router)`。

- [ ] **Step 7: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_company_api.py -v`
Expected: PASS

- [ ] **Step 8: 提交**

```bash
cd backend && git add app/schemas/company.py app/services/company_service.py app/routers/company.py app/main.py tests/test_company_api.py
git commit -m "feat(company): tenant settings API (/api/v1/companies/me)"
```

---

## Task 17: 现有 SOP 表接入多租户（nullable 桥接）

给 SOP 业务模型加 `NullableTenantMixin`，结构上拥有 `company_id` 并参与作用域（有上下文时），同时**不**改动现有无认证 SOP 端点/测试的行为。

**Files:**
- Modify: 各 SOP 业务模型文件（见 Step 1 清单）
- Test: `backend/tests/test_sop_tenant.py`

- [ ] **Step 1: 确认 SOP 模型清单**

Run: `cd backend && grep -rnE "^class .*\(Base" app/models/*.py`
对每个**业务**模型（非 Company/Role/User）加 `NullableTenantMixin`。已知清单：`Folder`、`FolderSequence`（folder.py）；`Procedure`（procedure.py）；`ProcedureNode`（node.py）；`ProcedureField`（field.py）；`ProcedureSettings`（settings.py）；`ProcedureSourceDocx`（source_docx.py）；`ProcedureAttachment`（attachment.py）；`ProcedureAsset`/`ProcedureAssetReference`（asset.py）；`FolderAuditLog`/`ProcedureAuditLog`（audit.py）。

- [ ] **Step 2: 写失败测试**

Create `backend/tests/test_sop_tenant.py`:

```python
from app.models.base import TenantScoped
from app.models.folder import Folder
from app.models.procedure import Procedure


def test_sop_models_tenant_scoped():
    assert issubclass(Folder, TenantScoped)
    assert issubclass(Procedure, TenantScoped)
    assert "company_id" in Folder.__table__.columns
    assert Folder.__table__.columns["company_id"].nullable is True


def test_folder_auto_stamped_and_scoped(db):
    from sqlalchemy import select
    from app import tenant
    from app.models.company import Company

    c1 = Company(name="c1", slug="c1"); c2 = Company(name="c2", slug="c2")
    db.add_all([c1, c2]); db.commit()

    t = tenant.set_current_company_id(c1.id)
    try:
        f = Folder(name="只属于c1", full_path="只属于c1")
        db.add(f); db.commit()
        assert f.company_id == c1.id
    finally:
        tenant.reset_current_company_id(t)

    t = tenant.set_current_company_id(c2.id)
    try:
        rows = db.execute(select(Folder)).scalars().all()
        assert rows == []  # c2 sees none of c1's folders
    finally:
        tenant.reset_current_company_id(t)
```

- [ ] **Step 3: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_sop_tenant.py -v`
Expected: FAIL（`Folder` 还不是 `TenantScoped` 子类）

- [ ] **Step 4: 给每个 SOP 业务模型加 NullableTenantMixin**

对 Step 1 清单的每个文件：
- import 行：把 `from app.models.base import ...` 追加 `NullableTenantMixin`。
- 类定义：在基类元组末尾追加 `NullableTenantMixin`。例如 folder.py：
  - `from app.models.base import DATETIME6, Base, NullableTenantMixin, SoftDeleteMixin, TimestampMixin, UUIDMixin`
  - `class Folder(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, NullableTenantMixin):`
  - `class FolderSequence(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, NullableTenantMixin):`
- 其余文件（procedure / node / field / settings / source_docx / attachment / asset / audit）同理（保持各自原有 mixin，仅在末尾追加 `NullableTenantMixin`）。

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_sop_tenant.py -v`
Expected: PASS

- [ ] **Step 6: 全量回归（确认既有 SOP 测试不受影响）**

Run: `cd backend && python -m pytest -q`
Expected: 全部 PASS。既有 SOP 测试不设上下文 → `company_id` 保持 NULL（列可空）→ 不盖章、不过滤 → 行为不变。

- [ ] **Step 7: 提交**

```bash
cd backend && git add app/models/ tests/test_sop_tenant.py
git commit -m "feat(tenant): SOP models gain nullable company_id (Phase 1 enforces)"
```

> **已知限制（Phase 0→1 边界，非遗漏）：** 现有 SOP 的跨版本唯一性守卫（`tb_procedure`/`tb_folder` 的 MySQL 生成列 partial-unique，见初始迁移）仍是**全局**唯一，未按租户隔离；SOP 端点仍无认证。两者将在 Phase 1（SOP 被工单在认证上下文中消费）随之收紧为租户级。Phase 0 单租户启动不受影响。

---

## Task 18: Alembic 增量迁移

Alembic 已配置（`env.py` 已接 `app.models.base.Base` 与 `settings.database_url`，并有 `_GENERATED_ONLY_OBJECTS` 忽略名单与 `compare_type=True`）。本期只需对新模型 + SOP 的 `company_id` 列生成增量迁移。

**Files:**
- Create: `backend/alembic/versions/<rev>_phase0_platform.py`（autogenerate 产物）

- [ ] **Step 1: 确认新模型已被 metadata 收录**

Run: `cd backend && python -c "import app.models; from app.models.base import Base; print(sorted(t for t in Base.metadata.tables if t in ('tb_company','tb_role','tb_user')))"`
Expected: `['tb_company', 'tb_role', 'tb_user']`

- [ ] **Step 2: 升级到当前最新历史迁移**

确保本地 MySQL 按 `settings.database_url`（默认 `mysql+pymysql://root:root@localhost:3306/smart_sop`）可连且库存在。

Run: `cd backend && alembic upgrade head`
Expected: 升到当前最新（如 `20260529_0001`），无错误。

- [ ] **Step 3: autogenerate 生成迁移**

Run: `cd backend && alembic revision --autogenerate -m "phase0 platform company user role + sop company_id"`
检查产物：含 `create_table('tb_company')`、`create_table('tb_role')`（带 `uq_role_company_code`）、`create_table('tb_user')`（带 `uq_user_company_email`），以及各 SOP 表 `add_column(company_id)` + 外键/索引。删除任何对历史生成列/索引（`_GENERATED_ONLY_OBJECTS` 内）的误报变更。文件名按既有约定可改为 `<日期>_0001_phase0_platform.py`。

- [ ] **Step 4: 应用并回滚自检**

Run: `cd backend && alembic upgrade head`
Expected: 新表与列创建成功。

Run: `cd backend && alembic downgrade -1 && alembic upgrade head`
Expected: 均成功。

- [ ] **Step 5: 提交**

```bash
cd backend && git add alembic/versions/
git commit -m "build(db): Alembic migration for platform tables + SOP company_id"
```

---

## Task 19: i18n 后端

**Files:**
- Create: `backend/app/i18n.py`
- Test: `backend/tests/test_i18n.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_i18n.py`:

```python
from app import i18n


def test_translate_known_zh():
    assert i18n.translate("auth.invalid_credentials", "zh-CN") == "邮箱或密码错误"


def test_translate_unknown_returns_key():
    assert i18n.translate("nope.nope", "zh-CN") == "nope.nope"


def test_resolve_locale_priority():
    assert i18n.resolve_locale(user_locale="zh-CN", accept_language="en") == "zh-CN"
    assert i18n.resolve_locale(user_locale=None, accept_language="zh-CN,en;q=0.9") == "zh-CN"
    assert i18n.resolve_locale(user_locale=None, accept_language="fr") == "zh-CN"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_i18n.py -v`
Expected: FAIL（`ModuleNotFoundError: app.i18n`）

- [ ] **Step 3: 实现**

Create `backend/app/i18n.py`:

```python
"""Minimal i18n: locale resolution + message catalog (Phase 0 ships zh-CN)."""
from __future__ import annotations

from app.config import settings

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
cd backend && git add app/i18n.py tests/test_i18n.py
git commit -m "feat(i18n): backend locale resolution + zh-CN catalog"
```

---

## Task 20: 前端 i18n 框架 + 品牌改名

**Files:**
- Create: `frontend/src/i18n/index.ts` · `frontend/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/src/main.ts` · `frontend/index.html` · `frontend/package.json`

- [ ] **Step 1: 探查前端结构**

Run: `cd frontend && ls src && sed -n '1,40p' src/main.ts && cat index.html && grep -n "vue-i18n" package.json`
记录入口写法、当前标题、是否已装 vue-i18n。

- [ ] **Step 2: 安装 vue-i18n**

Run: `cd frontend && npm install vue-i18n@9`
Expected: `package.json` dependencies 出现 `vue-i18n`。

- [ ] **Step 3: 中文语言包**

Create `frontend/src/i18n/locales/zh-CN.ts`:

```typescript
export default {
  app: { name: 'Smart CMMS' },
  auth: { login: '登录', register: '注册', email: '邮箱', password: '密码', companyName: '公司名称' },
  common: { save: '保存', cancel: '取消', delete: '删除' },
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

Modify `frontend/src/main.ts` — 引入并在 app 实例上 `use(i18n)`：
```typescript
import i18n from './i18n'
```
在 `createApp(App)...` 链中插入 `.use(i18n)`（置于 `.mount('#app')` 之前；按实际写法适配）。

- [ ] **Step 6: 品牌改名**

- `frontend/index.html`：`<title>` 改为 `Smart CMMS`。
- Run: `cd frontend && grep -rn "SmartSOP\|Smart SOP" src index.html`，把**用户可见**展示名替换为 `Smart CMMS`（或改用 `$t('app.name')`）；不改内部变量/包标识。

- [ ] **Step 7: 构建自检**

Run: `cd frontend && npm run build`
Expected: 构建成功（无类型/编译错误）。

- [ ] **Step 8: 提交**

```bash
cd frontend && git add src/i18n package.json package-lock.json index.html src/main.ts
git commit -m "feat(i18n,brand): vue-i18n scaffold (zh-CN) + rebrand to Smart CMMS"
```

---

## Task 21: 跨租户隔离端到端验收

Phase 0 最高优先级验收：通过完整 API 路径验证「A 租户绝对读不到/改不到 B 租户数据」。

**Files:**
- Test: `backend/tests/test_cross_tenant_e2e.py`

- [ ] **Step 1: 写测试**

Create `backend/tests/test_cross_tenant_e2e.py`:

```python
def _register(client, company, email):
    r = client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email, "password": "secret123", "name": "Admin"})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_users_list_isolated(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    client.post("/api/v1/users", headers=_h(ta),
                json={"email": "u1@acme.com", "password": "secret123", "name": "U1"})
    client.post("/api/v1/users", headers=_h(tb),
                json={"email": "u2@globex.com", "password": "secret123", "name": "U2"})
    a = {u["email"] for u in client.get("/api/v1/users", headers=_h(ta)).json()}
    b = {u["email"] for u in client.get("/api/v1/users", headers=_h(tb)).json()}
    assert "u1@acme.com" in a and "u2@globex.com" not in a
    assert "u2@globex.com" in b and "u1@acme.com" not in b


def test_cross_tenant_user_fetch_404(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    bob = client.post("/api/v1/users", headers=_h(tb),
        json={"email": "bob@globex.com", "password": "secret123", "name": "Bob"}).json()["id"]
    assert client.get(f"/api/v1/users/{bob}", headers=_h(ta)).status_code == 404


def test_cross_tenant_role_update_404(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    rid = [x for x in client.get("/api/v1/roles", headers=_h(tb)).json()
           if x["code"] == "viewer"][0]["id"]
    assert client.patch(f"/api/v1/roles/{rid}", headers=_h(ta),
                        json={"name": "hacked"}).status_code == 404


def test_company_me_isolated(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    assert client.get("/api/v1/companies/me", headers=_h(ta)).json()["slug"] == "acme"
    assert client.get("/api/v1/companies/me", headers=_h(tb)).json()["slug"] == "globex"
```

- [ ] **Step 2: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_cross_tenant_e2e.py -v`
Expected: PASS（若任何跨租户访问未被拦截，回到 Task 8/14/15 修复作用域或显式校验）。

- [ ] **Step 3: 全量回归**

Run: `cd backend && python -m pytest -q`
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
- [ ] 品牌改名 Smart CMMS（Task 1 app_name + Task 13 title + Task 20 前端）
- [ ] 现有 SOP 表接入多租户（nullable 桥接）（Task 17）
- [ ] Alembic 迁移（Task 18）
- [ ] 跨租户隔离端到端验收（Task 21）
- [ ] 明确不做项保持未做：邮件邀请、找回密码、运营后台 UI、团队、SSO、计费（仅预留字段/抽象）

---

## 净室合规复核（实现完成后）

- [ ] 全部模型/代码原创，未参照 Atlas DDL/源码。
- [ ] 代码与产物中无 "Atlas" 字样、商标、文案、资源。
- [ ] 多租户/RBAC 为通用工程模式，非受版权保护的具体表达。
