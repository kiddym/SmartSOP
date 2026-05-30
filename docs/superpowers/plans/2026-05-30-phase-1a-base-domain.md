# Phase 1A 基础域（Location / Asset / Team）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Smart CMMS 维护域建立被维护对象基座——位置层级、资产（分类/层级/状态/停机/扫码标识）、团队，全部作为一等多租户实体，并提供通用每租户自增序列。

**Architecture:** 在 Phase 0 多租户基座上扩展（同仓库、扁平布局）。新实体用 `TenantMixin`（NOT NULL `company_id`），由 Phase 0 `TenantContextMiddleware` 按 bearer token 为整请求设租户上下文，行级隔离 fail-closed；`db.get()` 按主键取的路径用 `_ensure_same_tenant` 显式兜底。接口走 `require_permission` 权限点。软删沿用 `SoftDeleteMixin`。customId 用通用 `Sequence`（仿 `FolderSequence`，并供后续阶段复用）。

**关键事实（已核对真实代码库，务必遵守）：**
- **扁平布局**：模型 `app/models/`、schema `app/schemas/`、服务 `app/services/`、路由 `app/routers/`；`main.py` 直接 `app.include_router(...)`。
- **命名冲突**：`app/models/asset.py`（=SOP `ProcedureAsset`）与 `app/services/asset_service.py`（SOP）**已存在**。本期 CMMS 设备资产改用：模型 `app/models/maintenance_asset.py`（class `Asset`，表 `tb_asset`）、服务 `app/services/maintenance_asset_service.py`。路由 `app/routers/assets.py`、schema `app/schemas/asset.py` 当前不存在，可用。
- **主键 UUID 字符串**（`UUIDMixin`），表名 `tb_` 前缀。`company_id` 为 `String(36)`。
- **错误助手返回 HTTPException**（`app/errors.py`：`not_found/bad_request/conflict/...`），调用处 `raise not_found(...)`。
- **路由风格**（见 `app/routers/company.py`）：注入 `current_user: User = Depends(require_permission(permissions.X))` 与 `db: Session = Depends(get_db)`；service 的 create 显式收 `company_id=current_user.company_id`；按主键取对象用 `_ensure_same_tenant(obj, current_user.company_id)`。
- **软删约定**（见 `app/services/folder_service.py`）：list/get 用 `.where(X.is_active.is_(True))`；delete 设 `is_active=False, deleted_at=utcnow()`（`utcnow` 来自 `app.models.base`）。
- **模型注册**：`app/models/__init__.py` 按字母序 import + 加入 `__all__`；`conftest` 通过 `from app.models import ...` 触发全量 import → `Base.metadata.create_all` 在测试 SQLite 建表。**每个新模型都要在本文件登记**，否则测试 schema 不含该表。
- **Alembic 现 head 修订 id = `phase0_platform`**（`alembic/versions/`）。本期所有表都是**新建**（`create_table`），FK 在 SQLite 与 MySQL 的 `create_table` 内均可——**无需** Phase 0 那种 dialect 分支。
- **多租户隔离事件**已注册在全局 `Session` 类（`app/tenant_isolation.py`）：有上下文时自动作用域 SELECT、自动盖章 INSERT。新表继承 `TenantMixin` 即自动纳入。`conftest` 有 autouse 清理上下文。

**命令约定：** 后端命令在激活的虚拟环境内：`cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && <cmd>`。git 仓库在仓库根（`/Users/yuming/Desktop/smart CMMS/SmartSOP`），backend 内无嵌套仓库；提交用 `git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" add backend/<path>`。当前分支 `phase-0-platform-foundation`（Phase 1A 依赖未合并的 Phase 0，继续在此分支）。

**Tech Stack:** FastAPI · SQLAlchemy 2.0 (sync) · Pydantic v2 · Alembic · MySQL/PyMySQL（生产）· SQLite in-memory（测试）· pytest · TestClient。

**净室合规：** 全新模型，依据领域理解编写，绝不复制 Atlas 源码/DDL/文案/品牌；产物不含 "Atlas" 字样。

---

## 文件结构（本期新建 / 改造）

**新建（后端）**
- `app/models/sequence.py` — 通用每租户自增序列 `Sequence`（`tb_sequence`）
- `app/models/asset_status.py` — `AssetStatus` 枚举 + `UP_STATUSES`/`DOWN_STATUSES`
- `app/models/asset_category.py` — `AssetCategory`（`tb_asset_category`）
- `app/models/team.py` — `Team` + `TeamUser`（`tb_team` / `tb_team_user`）
- `app/models/location.py` — `Location` + `LocationUser` + `LocationTeam`
- `app/models/maintenance_asset.py` — `Asset` + `AssetUser` + `AssetTeam`（`tb_asset` / `tb_asset_user` / `tb_asset_team`）
- `app/models/asset_downtime.py` — `AssetDowntime`（`tb_asset_downtime`）
- `app/services/sequence_service.py` · `asset_category_service.py` · `team_service.py` · `location_service.py` · `maintenance_asset_service.py`
- `app/schemas/asset_category.py` · `team.py` · `location.py` · `asset.py`
- `app/routers/asset_categories.py` · `teams.py` · `locations.py` · `assets.py`
- `app/alembic/versions/<rev>_phase1a_base_domain.py`
- `tests/test_*.py`（各任务）

**改造（后端）**
- `app/permissions.py` — 新增 location/asset/asset_category/team 权限点 + 内置角色默认集
- `app/models/__init__.py` — 登记全部新模型
- `app/main.py` — include 新路由

---

## Task 1: 权限点扩展（location/asset/asset_category/team）

**Files:**
- Modify: `backend/app/permissions.py`
- Test: `backend/tests/test_permissions_phase1a.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_permissions_phase1a.py`:

```python
from app import permissions as perms


def test_phase1a_codes_registered():
    for code in [
        "location.view", "location.create", "location.edit", "location.delete",
        "asset.view", "asset.create", "asset.edit", "asset.delete",
        "asset_category.view", "asset_category.manage",
        "team.view", "team.manage",
    ]:
        assert code in perms.ALL_PERMISSIONS


def test_super_admin_wildcard_includes_new_codes():
    assert perms.effective_codes("super_admin", []) == set(perms.ALL_PERMISSIONS)


def test_admin_has_all_phase1a():
    admin = next(r for r in perms.BUILTIN_ROLES if r["code"] == "admin")
    for code in ["location.create", "asset.delete", "asset_category.manage", "team.manage"]:
        assert code in admin["permissions"]


def test_technician_can_edit_asset_not_delete():
    tech = next(r for r in perms.BUILTIN_ROLES if r["code"] == "technician")
    assert "asset.edit" in tech["permissions"]
    assert "asset.delete" not in tech["permissions"]
    assert "location.view" in tech["permissions"]


def test_viewer_only_view():
    viewer = next(r for r in perms.BUILTIN_ROLES if r["code"] == "viewer")
    assert all(c.endswith(".view") for c in viewer["permissions"])
    assert "asset.view" in viewer["permissions"]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_permissions_phase1a.py -v`
Expected: FAIL（`asset.view` 等不在 `ALL_PERMISSIONS`）。

- [ ] **Step 3: 实现**

Modify `backend/app/permissions.py` — 在现有平台权限点常量后、`ALL_PERMISSIONS` 定义前插入新常量；并扩展 `ALL_PERMISSIONS` 与内置角色。完整替换文件为：

```python
"""Permission-code registry + built-in role defaults.

Phase 0 declares platform-layer codes; Phase 1A adds maintenance base-domain
codes (location/asset/asset_category/team). Later phases append more here and
extend the built-in role default sets accordingly.
"""
from __future__ import annotations

# --- 平台层（Phase 0）---
USER_CREATE = "user.create"
USER_VIEW = "user.view"
USER_EDIT = "user.edit"
USER_DELETE = "user.delete"
ROLE_VIEW = "role.view"
ROLE_MANAGE = "role.manage"
COMPANY_SETTINGS = "company.settings"

# --- 维护基础域（Phase 1A）---
LOCATION_VIEW = "location.view"
LOCATION_CREATE = "location.create"
LOCATION_EDIT = "location.edit"
LOCATION_DELETE = "location.delete"
ASSET_VIEW = "asset.view"
ASSET_CREATE = "asset.create"
ASSET_EDIT = "asset.edit"
ASSET_DELETE = "asset.delete"
ASSET_CATEGORY_VIEW = "asset_category.view"
ASSET_CATEGORY_MANAGE = "asset_category.manage"
TEAM_VIEW = "team.view"
TEAM_MANAGE = "team.manage"

_PLATFORM = [
    USER_CREATE, USER_VIEW, USER_EDIT, USER_DELETE,
    ROLE_VIEW, ROLE_MANAGE, COMPANY_SETTINGS,
]
_BASE_DOMAIN = [
    LOCATION_VIEW, LOCATION_CREATE, LOCATION_EDIT, LOCATION_DELETE,
    ASSET_VIEW, ASSET_CREATE, ASSET_EDIT, ASSET_DELETE,
    ASSET_CATEGORY_VIEW, ASSET_CATEGORY_MANAGE,
    TEAM_VIEW, TEAM_MANAGE,
]

ALL_PERMISSIONS: list[str] = _PLATFORM + _BASE_DOMAIN

BUILTIN_ROLES: list[dict] = [
    {"code": "super_admin", "name": "超级管理员", "permissions": list(ALL_PERMISSIONS)},
    {"code": "admin", "name": "管理员", "permissions": list(ALL_PERMISSIONS)},
    {"code": "technician", "name": "技术员", "permissions": [
        USER_VIEW, ROLE_VIEW,
        LOCATION_VIEW, ASSET_VIEW, ASSET_EDIT, ASSET_CATEGORY_VIEW, TEAM_VIEW,
    ]},
    {"code": "viewer", "name": "只读", "permissions": [
        c for c in ALL_PERMISSIONS if c.endswith(".view")]},
]


def effective_codes(role_code: str, stored_codes: list[str]) -> set[str]:
    """super_admin is an implicit wildcard over ALL_PERMISSIONS."""
    if role_code == "super_admin":
        return set(ALL_PERMISSIONS)
    return set(stored_codes)
```

> 注意：原 admin 之前是平台权限子集，现改为 `list(ALL_PERMISSIONS)`（admin 拥有全部已注册权限点）。原 Phase 0 测试断言 admin 含平台点，仍成立。

- [ ] **Step 4: 运行确认通过**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_permissions_phase1a.py tests/test_permissions.py -v`
Expected: PASS（新测试 + 原 Phase 0 权限测试）。

- [ ] **Step 5: 提交**

```bash
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" add backend/app/permissions.py backend/tests/test_permissions_phase1a.py
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" commit -m "feat(rbac): phase1a permission codes (location/asset/category/team)"
```

---

## Task 2: 通用序列 Sequence（模型 + 取号服务）

**Files:**
- Create: `backend/app/models/sequence.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/services/sequence_service.py`
- Test: `backend/tests/test_sequence.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_sequence.py`:

```python
from app.models.company import Company
from app.services import sequence_service


def _company(db, slug):
    c = Company(name=slug, slug=slug)
    db.add(c)
    db.commit()
    return c


def test_next_value_starts_at_one_and_increments(db):
    c = _company(db, "acme")
    assert sequence_service.next_value(db, "asset", c.id) == 1
    assert sequence_service.next_value(db, "asset", c.id) == 2
    assert sequence_service.next_value(db, "asset", c.id) == 3


def test_scopes_are_independent(db):
    c = _company(db, "acme")
    assert sequence_service.next_value(db, "asset", c.id) == 1
    assert sequence_service.next_value(db, "location", c.id) == 1
    assert sequence_service.next_value(db, "asset", c.id) == 2


def test_tenants_are_independent(db):
    c1 = _company(db, "acme"); c2 = _company(db, "globex")
    assert sequence_service.next_value(db, "asset", c1.id) == 1
    assert sequence_service.next_value(db, "asset", c1.id) == 2
    assert sequence_service.next_value(db, "asset", c2.id) == 1  # 独立计数


def test_format_custom_id():
    assert sequence_service.format_custom_id("A", 1) == "A000001"
    assert sequence_service.format_custom_id("L", 42) == "L000042"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_sequence.py -v`
Expected: FAIL（`ModuleNotFoundError: app.models.sequence`）。

- [ ] **Step 3: 实现模型**

Create `backend/app/models/sequence.py`:

```python
"""通用每租户自增序列（custom_id 生成）。

按 (company_id, scope) 维护一个计数器；scope 如 "asset"/"location"，
后续阶段（库存/采购/工单）可复用，仅新增 scope。
"""
from __future__ import annotations

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin


class Sequence(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_sequence"
    __table_args__ = (
        UniqueConstraint("company_id", "scope", name="uq_sequence_company_scope"),
    )

    scope: Mapped[str] = mapped_column(String(40), nullable=False)
    # 下一个待分配的编号（从 1 起）
    next_val: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
```

- [ ] **Step 4: 登记模型**

Modify `backend/app/models/__init__.py` — 加 import `from app.models.sequence import Sequence`（置于字母序合适位置，如 `settings` 后、`source_docx` 前不强求，按字母 `sequence` 在 `role` 与 `settings` 之间）并把 `"Sequence"` 加入 `__all__`。

- [ ] **Step 5: 实现服务**

Create `backend/app/services/sequence_service.py`:

```python
"""序列取号服务。

next_value 在事务内对 (company_id, scope) 行加锁后原子自增（MySQL 用
SELECT ... FOR UPDATE；SQLite 串行化连接天然原子）。调用方在同一事务内
取号 + 写业务行 + 提交。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sequence import Sequence


def next_value(db: Session, scope: str, company_id: str) -> int:
    """返回该租户该 scope 的下一个编号（从 1 起），并自增计数器。"""
    seq = db.execute(
        select(Sequence)
        .where(Sequence.company_id == company_id, Sequence.scope == scope)
        .with_for_update()
    ).scalar_one_or_none()
    if seq is None:
        seq = Sequence(scope=scope, next_val=1, company_id=company_id)
        db.add(seq)
        db.flush()
    value = seq.next_val
    seq.next_val = value + 1
    db.flush()
    return value


def format_custom_id(prefix: str, value: int, digits: int = 6) -> str:
    """A + 1 -> 'A000001'。"""
    return f"{prefix}{value:0{digits}d}"
```

> 说明：SQLite 测试不会真正并发，故 FOR UPDATE 在 SQLite 是 no-op；真正的并发安全由 MySQL 行锁保证，SQLite 单元测试仅覆盖顺序/隔离正确性（已知限制，非缺陷）。

- [ ] **Step 6: 运行确认通过**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_sequence.py -v`
Expected: PASS。

- [ ] **Step 7: 全量回归**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest -q`
Expected: 全部 PASS（新表加入 metadata 不影响既有）。

- [ ] **Step 8: 提交**

```bash
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" add backend/app/models/sequence.py backend/app/models/__init__.py backend/app/services/sequence_service.py backend/tests/test_sequence.py
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" commit -m "feat(sequence): per-tenant auto-increment sequence + custom_id format"
```

---

## Task 3: 资产分类 AssetCategory（模型 + schema + service + 路由）

建立最简单的实体垂直切片，确立本期 CRUD/隔离/RBAC 范式。

**Files:**
- Create: `backend/app/models/asset_category.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/schemas/asset_category.py`
- Create: `backend/app/services/asset_category_service.py`
- Create: `backend/app/routers/asset_categories.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_asset_categories_api.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_asset_categories_api.py`:

```python
def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email,
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_create_and_list_category(client):
    t = _admin(client)
    r = client.post("/api/v1/asset-categories", headers=_h(t), json={"name": "泵类"})
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "泵类"
    names = {c["name"] for c in client.get("/api/v1/asset-categories", headers=_h(t)).json()}
    assert names == {"泵类"}


def test_update_and_delete_category(client):
    t = _admin(client)
    cid = client.post("/api/v1/asset-categories", headers=_h(t), json={"name": "泵类"}).json()["id"]
    r = client.patch(f"/api/v1/asset-categories/{cid}", headers=_h(t), json={"name": "水泵"})
    assert r.status_code == 200
    assert r.json()["name"] == "水泵"
    assert client.delete(f"/api/v1/asset-categories/{cid}", headers=_h(t)).status_code == 204
    assert client.get("/api/v1/asset-categories", headers=_h(t)).json() == []


def test_requires_auth(client):
    assert client.get("/api/v1/asset-categories").status_code == 401


def test_cross_tenant_category_isolated(client):
    ta = _admin(client, "Acme", "a@acme.com")
    tb = _admin(client, "Globex", "b@globex.com")
    cid = client.post("/api/v1/asset-categories", headers=_h(tb), json={"name": "B类"}).json()["id"]
    assert client.get("/api/v1/asset-categories", headers=_h(ta)).json() == []
    assert client.patch(f"/api/v1/asset-categories/{cid}", headers=_h(ta),
                        json={"name": "x"}).status_code == 404
```

- [ ] **Step 2: 运行确认失败**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_asset_categories_api.py -v`
Expected: FAIL（404）。

- [ ] **Step 3: 实现模型 + 登记**

Create `backend/app/models/asset_category.py`:

```python
"""资产分类（每租户）。"""
from __future__ import annotations

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin


class AssetCategory(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_asset_category"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_asset_category_company_name"),
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
```

Modify `backend/app/models/__init__.py` — 加 `from app.models.asset_category import AssetCategory` 并把 `"AssetCategory"` 加入 `__all__`。

- [ ] **Step 4: 实现 schema**

Create `backend/app/schemas/asset_category.py`:

```python
"""资产分类 schema。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AssetCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class AssetCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)


class AssetCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
```

- [ ] **Step 5: 实现服务**

Create `backend/app/services/asset_category_service.py`:

```python
"""资产分类服务（租户作用域由 ORM 事件 + 显式 company_id 双重保证）。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset_category import AssetCategory
from app.models.base import utcnow
from app.schemas.asset_category import AssetCategoryCreate, AssetCategoryUpdate


def create_category(db: Session, payload: AssetCategoryCreate, company_id: str) -> AssetCategory:
    cat = AssetCategory(name=payload.name, company_id=company_id)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def list_categories(db: Session) -> list[AssetCategory]:
    return list(
        db.execute(
            select(AssetCategory).where(AssetCategory.is_active.is_(True))
        ).scalars().all()
    )


def get_category(db: Session, category_id: str) -> AssetCategory | None:
    cat = db.get(AssetCategory, category_id)
    if cat is None or not cat.is_active:
        return None
    return cat


def update_category(db: Session, cat: AssetCategory, payload: AssetCategoryUpdate) -> AssetCategory:
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return cat


def delete_category(db: Session, cat: AssetCategory) -> None:
    cat.is_active = False
    cat.deleted_at = utcnow()
    db.commit()
```

- [ ] **Step 6: 实现路由 + 挂载**

Create `backend/app/routers/asset_categories.py`:

```python
"""资产分类 API（/api/v1/asset-categories）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.asset_category import AssetCategory
from app.models.user import User
from app.schemas.asset_category import (
    AssetCategoryCreate, AssetCategoryRead, AssetCategoryUpdate,
)
from app.services import asset_category_service

router = APIRouter(prefix="/api/v1/asset-categories", tags=["asset-categories"])


def _ensure(cat: AssetCategory | None, company_id: str) -> AssetCategory:
    if cat is None or cat.company_id != company_id:
        raise not_found("ASSET_CATEGORY_NOT_FOUND", "资产分类不存在")
    return cat


@router.get("", response_model=list[AssetCategoryRead])
def list_categories(db: Session = Depends(get_db),
                    current_user: User = Depends(require_permission(permissions.ASSET_CATEGORY_VIEW))):
    return asset_category_service.list_categories(db)


@router.post("", response_model=AssetCategoryRead, status_code=201)
def create_category(payload: AssetCategoryCreate, db: Session = Depends(get_db),
                    current_user: User = Depends(require_permission(permissions.ASSET_CATEGORY_MANAGE))):
    return asset_category_service.create_category(db, payload, current_user.company_id)


@router.patch("/{category_id}", response_model=AssetCategoryRead)
def update_category(category_id: str, payload: AssetCategoryUpdate, db: Session = Depends(get_db),
                    current_user: User = Depends(require_permission(permissions.ASSET_CATEGORY_MANAGE))):
    cat = _ensure(asset_category_service.get_category(db, category_id), current_user.company_id)
    return asset_category_service.update_category(db, cat, payload)


@router.delete("/{category_id}", status_code=204)
def delete_category(category_id: str, db: Session = Depends(get_db),
                    current_user: User = Depends(require_permission(permissions.ASSET_CATEGORY_MANAGE))):
    cat = _ensure(asset_category_service.get_category(db, category_id), current_user.company_id)
    asset_category_service.delete_category(db, cat)
```

Modify `backend/app/main.py` — 在 router import 区加 `from app.routers import asset_categories`；在 include 区加 `app.include_router(asset_categories.router)`。

- [ ] **Step 7: 运行确认通过**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_asset_categories_api.py -v`
Expected: PASS。

- [ ] **Step 8: 提交**

```bash
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" add backend/app/models/asset_category.py backend/app/models/__init__.py backend/app/schemas/asset_category.py backend/app/services/asset_category_service.py backend/app/routers/asset_categories.py backend/app/main.py backend/tests/test_asset_categories_api.py
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" commit -m "feat(asset-category): AssetCategory CRUD (/api/v1/asset-categories)"
```

---

## Task 4: 团队 Team（模型 + 成员 + schema + service + 路由）

**Files:**
- Create: `backend/app/models/team.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/schemas/team.py`
- Create: `backend/app/services/team_service.py`
- Create: `backend/app/routers/teams.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_teams_api.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_teams_api.py`:

```python
def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email,
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _new_user(client, t, email):
    return client.post("/api/v1/users", headers=_h(t), json={
        "email": email, "password": "secret123", "name": email}).json()["id"]


def test_create_and_list_team(client):
    t = _admin(client)
    r = client.post("/api/v1/teams", headers=_h(t), json={"name": "电气班", "description": "电工组"})
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "电气班"
    assert r.json()["member_ids"] == []
    names = {x["name"] for x in client.get("/api/v1/teams", headers=_h(t)).json()}
    assert names == {"电气班"}


def test_set_members(client):
    t = _admin(client)
    u1 = _new_user(client, t, "u1@acme.com")
    u2 = _new_user(client, t, "u2@acme.com")
    tid = client.post("/api/v1/teams", headers=_h(t), json={"name": "电气班"}).json()["id"]
    r = client.put(f"/api/v1/teams/{tid}/members", headers=_h(t), json={"user_ids": [u1, u2]})
    assert r.status_code == 200, r.text
    assert set(r.json()["member_ids"]) == {u1, u2}
    # 重设为单人
    r = client.put(f"/api/v1/teams/{tid}/members", headers=_h(t), json={"user_ids": [u1]})
    assert set(r.json()["member_ids"]) == {u1}


def test_update_and_delete_team(client):
    t = _admin(client)
    tid = client.post("/api/v1/teams", headers=_h(t), json={"name": "电气班"}).json()["id"]
    assert client.patch(f"/api/v1/teams/{tid}", headers=_h(t),
                        json={"name": "电气一班"}).json()["name"] == "电气一班"
    assert client.delete(f"/api/v1/teams/{tid}", headers=_h(t)).status_code == 204
    assert client.get("/api/v1/teams", headers=_h(t)).json() == []


def test_requires_auth(client):
    assert client.get("/api/v1/teams").status_code == 401


def test_cross_tenant_team_isolated(client):
    ta = _admin(client, "Acme", "a@acme.com")
    tb = _admin(client, "Globex", "b@globex.com")
    tid = client.post("/api/v1/teams", headers=_h(tb), json={"name": "B班"}).json()["id"]
    assert client.get("/api/v1/teams", headers=_h(ta)).json() == []
    assert client.patch(f"/api/v1/teams/{tid}", headers=_h(ta), json={"name": "x"}).status_code == 404
```

- [ ] **Step 2: 运行确认失败**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_teams_api.py -v`
Expected: FAIL（404）。

- [ ] **Step 3: 实现模型 + 登记**

Create `backend/app/models/team.py`:

```python
"""团队及其成员（每租户）。成员关系用显式关联类，便于租户作用域。"""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin


class Team(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_team"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_team_company_name"),)

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")


class TeamUser(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """团队↔用户成员关系。"""

    __tablename__ = "tb_team_user"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_team_user"),)

    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_team.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="CASCADE"), index=True
    )
```

Modify `backend/app/models/__init__.py` — 加 `from app.models.team import Team, TeamUser` 并把 `"Team"`, `"TeamUser"` 加入 `__all__`。

- [ ] **Step 4: 实现 schema**

Create `backend/app/schemas/team.py`:

```python
"""团队 schema。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = ""


class TeamUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None


class TeamMembersSet(BaseModel):
    user_ids: list[str] = []


class TeamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str
    member_ids: list[str] = []
```

- [ ] **Step 5: 实现服务**

Create `backend/app/services/team_service.py`:

```python
"""团队服务（含成员设置）。"""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.team import Team, TeamUser
from app.schemas.team import TeamCreate, TeamUpdate


def _member_ids(db: Session, team_id: str) -> list[str]:
    return list(
        db.execute(select(TeamUser.user_id).where(TeamUser.team_id == team_id)).scalars().all()
    )


def to_read(db: Session, team: Team) -> dict:
    return {
        "id": team.id, "name": team.name, "description": team.description,
        "member_ids": _member_ids(db, team.id),
    }


def create_team(db: Session, payload: TeamCreate, company_id: str) -> Team:
    team = Team(name=payload.name, description=payload.description, company_id=company_id)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def list_teams(db: Session) -> list[Team]:
    return list(db.execute(select(Team).where(Team.is_active.is_(True))).scalars().all())


def get_team(db: Session, team_id: str) -> Team | None:
    team = db.get(Team, team_id)
    if team is None or not team.is_active:
        return None
    return team


def update_team(db: Session, team: Team, payload: TeamUpdate) -> Team:
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(team, k, v)
    db.commit()
    db.refresh(team)
    return team


def delete_team(db: Session, team: Team) -> None:
    team.is_active = False
    team.deleted_at = utcnow()
    db.commit()


def set_members(db: Session, team: Team, user_ids: list[str], company_id: str) -> Team:
    db.execute(delete(TeamUser).where(TeamUser.team_id == team.id))
    for uid in dict.fromkeys(user_ids):  # 去重保序
        db.add(TeamUser(team_id=team.id, user_id=uid, company_id=company_id))
    db.commit()
    db.refresh(team)
    return team
```

- [ ] **Step 6: 实现路由 + 挂载**

Create `backend/app/routers/teams.py`:

```python
"""团队 API（/api/v1/teams）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.team import Team
from app.models.user import User
from app.schemas.team import TeamCreate, TeamMembersSet, TeamRead, TeamUpdate
from app.services import team_service

router = APIRouter(prefix="/api/v1/teams", tags=["teams"])


def _ensure(team: Team | None, company_id: str) -> Team:
    if team is None or team.company_id != company_id:
        raise not_found("TEAM_NOT_FOUND", "团队不存在")
    return team


@router.get("", response_model=list[TeamRead])
def list_teams(db: Session = Depends(get_db),
               current_user: User = Depends(require_permission(permissions.TEAM_VIEW))):
    return [team_service.to_read(db, t) for t in team_service.list_teams(db)]


@router.post("", response_model=TeamRead, status_code=201)
def create_team(payload: TeamCreate, db: Session = Depends(get_db),
                current_user: User = Depends(require_permission(permissions.TEAM_MANAGE))):
    team = team_service.create_team(db, payload, current_user.company_id)
    return team_service.to_read(db, team)


@router.patch("/{team_id}", response_model=TeamRead)
def update_team(team_id: str, payload: TeamUpdate, db: Session = Depends(get_db),
                current_user: User = Depends(require_permission(permissions.TEAM_MANAGE))):
    team = _ensure(team_service.get_team(db, team_id), current_user.company_id)
    team = team_service.update_team(db, team, payload)
    return team_service.to_read(db, team)


@router.put("/{team_id}/members", response_model=TeamRead)
def set_members(team_id: str, payload: TeamMembersSet, db: Session = Depends(get_db),
                current_user: User = Depends(require_permission(permissions.TEAM_MANAGE))):
    team = _ensure(team_service.get_team(db, team_id), current_user.company_id)
    team = team_service.set_members(db, team, payload.user_ids, current_user.company_id)
    return team_service.to_read(db, team)


@router.delete("/{team_id}", status_code=204)
def delete_team(team_id: str, db: Session = Depends(get_db),
                current_user: User = Depends(require_permission(permissions.TEAM_MANAGE))):
    team = _ensure(team_service.get_team(db, team_id), current_user.company_id)
    team_service.delete_team(db, team)
```

Modify `backend/app/main.py` — 加 `from app.routers import teams`；加 `app.include_router(teams.router)`。

- [ ] **Step 7: 运行确认通过**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_teams_api.py -v`
Expected: PASS。

- [ ] **Step 8: 提交**

```bash
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" add backend/app/models/team.py backend/app/models/__init__.py backend/app/schemas/team.py backend/app/services/team_service.py backend/app/routers/teams.py backend/app/main.py backend/tests/test_teams_api.py
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" commit -m "feat(team): Team CRUD + members (/api/v1/teams)"
```

---

## Task 5: 位置 Location（树 + customId + 关联）

**Files:**
- Create: `backend/app/models/location.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/schemas/location.py`
- Create: `backend/app/services/location_service.py`
- Create: `backend/app/routers/locations.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_locations_api.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_locations_api.py`:

```python
def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email,
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_create_assigns_custom_id(client):
    t = _admin(client)
    a = client.post("/api/v1/locations", headers=_h(t), json={"name": "厂区A"}).json()
    b = client.post("/api/v1/locations", headers=_h(t), json={"name": "厂区B"}).json()
    assert a["custom_id"] == "L000001"
    assert b["custom_id"] == "L000002"


def test_tree_children_and_cycle_guard(client):
    t = _admin(client)
    root = client.post("/api/v1/locations", headers=_h(t), json={"name": "厂区"}).json()
    child = client.post("/api/v1/locations", headers=_h(t),
                        json={"name": "车间", "parent_id": root["id"]}).json()
    kids = client.get(f"/api/v1/locations/{root['id']}/children", headers=_h(t)).json()
    assert {k["id"] for k in kids} == {child["id"]}
    # 把 root 的父设为它自己的子 -> 成环，拒绝
    r = client.patch(f"/api/v1/locations/{root['id']}", headers=_h(t),
                     json={"parent_id": child["id"]})
    assert r.status_code == 400, r.text
    # 自指也拒绝
    assert client.patch(f"/api/v1/locations/{root['id']}", headers=_h(t),
                        json={"parent_id": root["id"]}).status_code == 400


def test_delete_with_children_rejected(client):
    t = _admin(client)
    root = client.post("/api/v1/locations", headers=_h(t), json={"name": "厂区"}).json()
    client.post("/api/v1/locations", headers=_h(t), json={"name": "车间", "parent_id": root["id"]})
    assert client.delete(f"/api/v1/locations/{root['id']}", headers=_h(t)).status_code == 400


def test_mini_and_relations(client):
    t = _admin(client)
    u = client.post("/api/v1/users", headers=_h(t),
                    json={"email": "w@acme.com", "password": "secret123", "name": "W"}).json()["id"]
    tid = client.post("/api/v1/teams", headers=_h(t), json={"name": "班组"}).json()["id"]
    loc = client.post("/api/v1/locations", headers=_h(t), json={
        "name": "厂区", "assigned_user_ids": [u], "team_ids": [tid]}).json()
    assert set(loc["assigned_user_ids"]) == {u}
    assert set(loc["team_ids"]) == {tid}
    mini = client.get("/api/v1/locations/mini", headers=_h(t)).json()
    assert mini[0]["custom_id"] == "L000001" and "name" in mini[0]


def test_requires_auth(client):
    assert client.get("/api/v1/locations").status_code == 401


def test_cross_tenant_location_isolated(client):
    ta = _admin(client, "Acme", "a@acme.com")
    tb = _admin(client, "Globex", "b@globex.com")
    lid = client.post("/api/v1/locations", headers=_h(tb), json={"name": "B区"}).json()["id"]
    assert client.get("/api/v1/locations", headers=_h(ta)).json() == []
    assert client.get(f"/api/v1/locations/{lid}", headers=_h(ta)).status_code == 404
```

- [ ] **Step 2: 运行确认失败**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_locations_api.py -v`
Expected: FAIL（404）。

- [ ] **Step 3: 实现模型 + 登记**

Create `backend/app/models/location.py`:

```python
"""位置（自引用树）及其负责人/团队关联（每租户）。"""
from __future__ import annotations

from sqlalchemy import Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin


class Location(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_location"

    custom_id: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_location.id", ondelete="RESTRICT"), index=True
    )
    address: Mapped[str] = mapped_column(String(500), default="", server_default="")
    longitude: Mapped[float | None] = mapped_column(Float, default=None)
    latitude: Mapped[float | None] = mapped_column(Float, default=None)


class LocationUser(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_location_user"
    __table_args__ = (UniqueConstraint("location_id", "user_id", name="uq_location_user"),)

    location_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_location.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="CASCADE"), index=True
    )


class LocationTeam(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_location_team"
    __table_args__ = (UniqueConstraint("location_id", "team_id", name="uq_location_team"),)

    location_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_location.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_team.id", ondelete="CASCADE"), index=True
    )
```

Modify `backend/app/models/__init__.py` — 加 `from app.models.location import Location, LocationTeam, LocationUser` 并把 `"Location"`, `"LocationTeam"`, `"LocationUser"` 加入 `__all__`。

- [ ] **Step 4: 实现 schema**

Create `backend/app/schemas/location.py`:

```python
"""位置 schema。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    parent_id: str | None = None
    address: str = ""
    longitude: float | None = None
    latitude: float | None = None
    assigned_user_ids: list[str] = []
    team_ids: list[str] = []


class LocationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    parent_id: str | None = None
    address: str | None = None
    longitude: float | None = None
    latitude: float | None = None
    assigned_user_ids: list[str] | None = None
    team_ids: list[str] | None = None


class LocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    custom_id: str
    name: str
    description: str
    parent_id: str | None = None
    address: str
    longitude: float | None = None
    latitude: float | None = None
    assigned_user_ids: list[str] = []
    team_ids: list[str] = []


class LocationMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    custom_id: str
```

- [ ] **Step 5: 实现服务**

Create `backend/app/services/location_service.py`:

```python
"""位置服务：树（防环）、customId、负责人/团队关联。"""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.errors import bad_request
from app.models.base import utcnow
from app.models.location import Location, LocationTeam, LocationUser
from app.schemas.location import LocationCreate, LocationUpdate
from app.services import sequence_service


def _user_ids(db: Session, location_id: str) -> list[str]:
    return list(db.execute(
        select(LocationUser.user_id).where(LocationUser.location_id == location_id)
    ).scalars().all())


def _team_ids(db: Session, location_id: str) -> list[str]:
    return list(db.execute(
        select(LocationTeam.team_id).where(LocationTeam.location_id == location_id)
    ).scalars().all())


def to_read(db: Session, loc: Location) -> dict:
    return {
        "id": loc.id, "custom_id": loc.custom_id, "name": loc.name,
        "description": loc.description, "parent_id": loc.parent_id,
        "address": loc.address, "longitude": loc.longitude, "latitude": loc.latitude,
        "assigned_user_ids": _user_ids(db, loc.id), "team_ids": _team_ids(db, loc.id),
    }


def _descendant_ids(db: Session, location_id: str) -> set[str]:
    """收集 location_id 的所有后代 id（活跃）。"""
    out: set[str] = set()
    frontier = [location_id]
    while frontier:
        rows = db.execute(
            select(Location.id).where(
                Location.parent_id.in_(frontier), Location.is_active.is_(True)
            )
        ).scalars().all()
        rows = [r for r in rows if r not in out]
        out.update(rows)
        frontier = rows
    return out


def _validate_parent(db: Session, loc_id: str, parent_id: str | None) -> None:
    if parent_id is None:
        return
    if parent_id == loc_id:
        raise bad_request("LOCATION_CYCLE", "父位置不能是自身")
    if parent_id in _descendant_ids(db, loc_id):
        raise bad_request("LOCATION_CYCLE", "父位置不能是自身的后代")


def _sync_relations(db: Session, loc: Location, user_ids, team_ids, company_id: str) -> None:
    if user_ids is not None:
        db.execute(delete(LocationUser).where(LocationUser.location_id == loc.id))
        for uid in dict.fromkeys(user_ids):
            db.add(LocationUser(location_id=loc.id, user_id=uid, company_id=company_id))
    if team_ids is not None:
        db.execute(delete(LocationTeam).where(LocationTeam.location_id == loc.id))
        for tid in dict.fromkeys(team_ids):
            db.add(LocationTeam(location_id=loc.id, team_id=tid, company_id=company_id))


def create_location(db: Session, payload: LocationCreate, company_id: str) -> Location:
    seq = sequence_service.next_value(db, "location", company_id)
    loc = Location(
        custom_id=sequence_service.format_custom_id("L", seq),
        name=payload.name, description=payload.description, parent_id=payload.parent_id,
        address=payload.address, longitude=payload.longitude, latitude=payload.latitude,
        company_id=company_id,
    )
    db.add(loc)
    db.flush()
    _sync_relations(db, loc, payload.assigned_user_ids, payload.team_ids, company_id)
    db.commit()
    db.refresh(loc)
    return loc


def list_locations(db: Session, parent_id: str | None = None) -> list[Location]:
    stmt = select(Location).where(Location.is_active.is_(True))
    if parent_id is not None:
        stmt = stmt.where(Location.parent_id == parent_id)
    return list(db.execute(stmt).scalars().all())


def list_children(db: Session, location_id: str) -> list[Location]:
    return list(db.execute(
        select(Location).where(
            Location.parent_id == location_id, Location.is_active.is_(True)
        )
    ).scalars().all())


def get_location(db: Session, location_id: str) -> Location | None:
    loc = db.get(Location, location_id)
    if loc is None or not loc.is_active:
        return None
    return loc


def update_location(db: Session, loc: Location, payload: LocationUpdate, company_id: str) -> Location:
    data = payload.model_dump(exclude_unset=True)
    if "parent_id" in data:
        _validate_parent(db, loc.id, data["parent_id"])
    user_ids = data.pop("assigned_user_ids", None)
    team_ids = data.pop("team_ids", None)
    for k, v in data.items():
        setattr(loc, k, v)
    _sync_relations(db, loc, user_ids, team_ids, company_id)
    db.commit()
    db.refresh(loc)
    return loc


def delete_location(db: Session, loc: Location) -> None:
    if list_children(db, loc.id):
        raise bad_request("LOCATION_HAS_CHILDREN", "请先删除子位置")
    loc.is_active = False
    loc.deleted_at = utcnow()
    db.commit()
```

- [ ] **Step 6: 实现路由 + 挂载**

Create `backend/app/routers/locations.py`:

```python
"""位置 API（/api/v1/locations）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.location import Location
from app.models.user import User
from app.schemas.location import LocationCreate, LocationMini, LocationRead, LocationUpdate
from app.services import location_service

router = APIRouter(prefix="/api/v1/locations", tags=["locations"])


def _ensure(loc: Location | None, company_id: str) -> Location:
    if loc is None or loc.company_id != company_id:
        raise not_found("LOCATION_NOT_FOUND", "位置不存在")
    return loc


@router.get("", response_model=list[LocationRead])
def list_locations(parent_id: str | None = None, db: Session = Depends(get_db),
                   current_user: User = Depends(require_permission(permissions.LOCATION_VIEW))):
    return [location_service.to_read(db, x) for x in location_service.list_locations(db, parent_id)]


@router.get("/mini", response_model=list[LocationMini])
def list_mini(db: Session = Depends(get_db),
              current_user: User = Depends(require_permission(permissions.LOCATION_VIEW))):
    return location_service.list_locations(db)


@router.post("", response_model=LocationRead, status_code=201)
def create_location(payload: LocationCreate, db: Session = Depends(get_db),
                    current_user: User = Depends(require_permission(permissions.LOCATION_CREATE))):
    loc = location_service.create_location(db, payload, current_user.company_id)
    return location_service.to_read(db, loc)


@router.get("/{location_id}", response_model=LocationRead)
def get_location(location_id: str, db: Session = Depends(get_db),
                 current_user: User = Depends(require_permission(permissions.LOCATION_VIEW))):
    loc = _ensure(location_service.get_location(db, location_id), current_user.company_id)
    return location_service.to_read(db, loc)


@router.get("/{location_id}/children", response_model=list[LocationRead])
def list_children(location_id: str, db: Session = Depends(get_db),
                  current_user: User = Depends(require_permission(permissions.LOCATION_VIEW))):
    _ensure(location_service.get_location(db, location_id), current_user.company_id)
    return [location_service.to_read(db, x) for x in location_service.list_children(db, location_id)]


@router.patch("/{location_id}", response_model=LocationRead)
def update_location(location_id: str, payload: LocationUpdate, db: Session = Depends(get_db),
                    current_user: User = Depends(require_permission(permissions.LOCATION_EDIT))):
    loc = _ensure(location_service.get_location(db, location_id), current_user.company_id)
    loc = location_service.update_location(db, loc, payload, current_user.company_id)
    return location_service.to_read(db, loc)


@router.delete("/{location_id}", status_code=204)
def delete_location(location_id: str, db: Session = Depends(get_db),
                    current_user: User = Depends(require_permission(permissions.LOCATION_DELETE))):
    loc = _ensure(location_service.get_location(db, location_id), current_user.company_id)
    location_service.delete_location(db, loc)
```

Modify `backend/app/main.py` — 加 `from app.routers import locations`；加 `app.include_router(locations.router)`。

> 路由顺序注意：`/mini` 必须在 `/{location_id}` 之前声明（FastAPI 按声明序匹配），上面已满足。

- [ ] **Step 7: 运行确认通过**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_locations_api.py -v`
Expected: PASS。

- [ ] **Step 8: 提交**

```bash
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" add backend/app/models/location.py backend/app/models/__init__.py backend/app/schemas/location.py backend/app/services/location_service.py backend/app/routers/locations.py backend/app/main.py backend/tests/test_locations_api.py
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" commit -m "feat(location): Location tree + customId + relations (/api/v1/locations)"
```

---

## Task 6: 资产模型层（AssetStatus + Asset + 关联 + Downtime）

**Files:**
- Create: `backend/app/models/asset_status.py`
- Create: `backend/app/models/maintenance_asset.py`
- Create: `backend/app/models/asset_downtime.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_asset_model.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_asset_model.py`:

```python
from app.models.asset_status import AssetStatus, DOWN_STATUSES, UP_STATUSES
from app.models.company import Company
from app.models.maintenance_asset import Asset


def test_status_up_down_partition():
    all_values = set(AssetStatus)
    assert UP_STATUSES | DOWN_STATUSES == all_values
    assert UP_STATUSES & DOWN_STATUSES == set()
    assert AssetStatus.OPERATIONAL in UP_STATUSES
    assert AssetStatus.DOWN in DOWN_STATUSES
    assert AssetStatus.EMERGENCY_SHUTDOWN in DOWN_STATUSES


def test_asset_defaults(db):
    c = Company(name="Acme", slug="acme")
    db.add(c)
    db.commit()
    a = Asset(custom_id="A000001", name="泵1", company_id=c.id)
    db.add(a)
    db.commit()
    db.refresh(a)
    assert a.status == AssetStatus.OPERATIONAL
    assert a.id is not None and len(a.id) == 36
```

- [ ] **Step 2: 运行确认失败**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_asset_model.py -v`
Expected: FAIL（`ModuleNotFoundError: app.models.asset_status`）。

- [ ] **Step 3: 实现 AssetStatus**

Create `backend/app/models/asset_status.py`:

```python
"""资产状态枚举 + UP/DOWN 归类（供 Phase 4 可用率复用）。"""
from __future__ import annotations

import enum


class AssetStatus(str, enum.Enum):
    OPERATIONAL = "OPERATIONAL"
    STANDBY = "STANDBY"
    MODERNIZATION = "MODERNIZATION"
    INSPECTION_SCHEDULED = "INSPECTION_SCHEDULED"
    COMMISSIONING = "COMMISSIONING"
    EMERGENCY_SHUTDOWN = "EMERGENCY_SHUTDOWN"
    DOWN = "DOWN"


UP_STATUSES: set[AssetStatus] = {
    AssetStatus.OPERATIONAL,
    AssetStatus.STANDBY,
    AssetStatus.INSPECTION_SCHEDULED,
    AssetStatus.COMMISSIONING,
}
DOWN_STATUSES: set[AssetStatus] = {
    AssetStatus.MODERNIZATION,
    AssetStatus.EMERGENCY_SHUTDOWN,
    AssetStatus.DOWN,
}
```

- [ ] **Step 4: 实现 Asset + 关联**

Create `backend/app/models/maintenance_asset.py`:

```python
"""CMMS 设备资产（自引用树）+ 负责人/团队关联（每租户）。

注意：文件名为 maintenance_asset 以避开既有 app/models/asset.py（SOP
ProcedureAsset）。类名 Asset、表名 tb_asset。
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Enum as SAEnum, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.asset_status import AssetStatus
from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin


class Asset(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_asset"

    custom_id: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_asset.id", ondelete="RESTRICT"), index=True
    )
    location_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_location.id", ondelete="RESTRICT"), index=True
    )
    category_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_asset_category.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[AssetStatus] = mapped_column(
        SAEnum(AssetStatus), nullable=False, default=AssetStatus.OPERATIONAL
    )
    serial_number: Mapped[str] = mapped_column(String(200), default="", server_default="")
    model: Mapped[str] = mapped_column(String(200), default="", server_default="")
    manufacturer: Mapped[str] = mapped_column(String(200), default="", server_default="")
    power: Mapped[str] = mapped_column(String(100), default="", server_default="")
    warranty_expiration_date: Mapped[date | None] = mapped_column(Date, default=None)
    in_service_date: Mapped[date | None] = mapped_column(Date, default=None)
    acquisition_cost: Mapped[float | None] = mapped_column(Numeric(18, 2), default=None)
    barcode: Mapped[str | None] = mapped_column(String(120), default=None, index=True)
    nfc_id: Mapped[str | None] = mapped_column(String(120), default=None, index=True)
    primary_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="SET NULL"), index=True
    )


class AssetUser(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_asset_user"
    __table_args__ = (UniqueConstraint("asset_id", "user_id", name="uq_asset_user"),)

    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_asset.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="CASCADE"), index=True
    )


class AssetTeam(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_asset_team"
    __table_args__ = (UniqueConstraint("asset_id", "team_id", name="uq_asset_team"),)

    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_asset.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_team.id", ondelete="CASCADE"), index=True
    )
```

- [ ] **Step 5: 实现 AssetDowntime**

Create `backend/app/models/asset_downtime.py`:

```python
"""资产停机时段（手动登记；无树传播，Phase 4 再做）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import DATETIME6, Base, UUIDMixin, TimestampMixin, TenantMixin


class AssetDowntime(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_asset_downtime"

    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_asset.id", ondelete="RESTRICT"), index=True
    )
    started_at: Mapped[datetime] = mapped_column(DATETIME6, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    reason: Mapped[str] = mapped_column(Text, default="", server_default="")
    downtime_type: Mapped[str] = mapped_column(
        String(20), default="manual", server_default="manual"
    )
```

- [ ] **Step 6: 登记模型**

Modify `backend/app/models/__init__.py` — 加：
```python
from app.models.asset_downtime import AssetDowntime
from app.models.maintenance_asset import Asset, AssetTeam, AssetUser
```
并把 `"Asset"`, `"AssetDowntime"`, `"AssetTeam"`, `"AssetUser"` 加入 `__all__`。（`asset_status` 无表，不需登记。）

- [ ] **Step 7: 运行确认通过**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_asset_model.py -v`
Expected: PASS。

- [ ] **Step 8: 全量回归 + 提交**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest -q`
Expected: 全部 PASS。

```bash
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" add backend/app/models/asset_status.py backend/app/models/maintenance_asset.py backend/app/models/asset_downtime.py backend/app/models/__init__.py backend/tests/test_asset_model.py
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" commit -m "feat(asset): Asset/AssetStatus/AssetDowntime models + associations"
```

---

## Task 7: 资产服务 + schema（CRUD / 树 / customId / barcode / 过滤 / 关联）

**Files:**
- Create: `backend/app/schemas/asset.py`
- Create: `backend/app/services/maintenance_asset_service.py`
- Test: `backend/tests/test_asset_service.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_asset_service.py`:

```python
import pytest
from fastapi import HTTPException

from app import tenant
from app.models.company import Company
from app.schemas.asset import AssetCreate, AssetUpdate
from app.services import maintenance_asset_service as svc


def _company(db, slug):
    c = Company(name=slug, slug=slug)
    db.add(c)
    db.commit()
    return c


def _ctx(db, company_id):
    tenant.set_current_company_id(company_id)


def test_create_assigns_custom_id_and_defaults(db):
    c = _company(db, "acme")
    _ctx(db, c.id)
    a = svc.create_asset(db, AssetCreate(name="泵1"), c.id)
    b = svc.create_asset(db, AssetCreate(name="泵2"), c.id)
    assert a.custom_id == "A000001"
    assert b.custom_id == "A000002"


def test_barcode_unique_within_tenant(db):
    c = _company(db, "acme")
    _ctx(db, c.id)
    svc.create_asset(db, AssetCreate(name="泵1", barcode="BC-1"), c.id)
    with pytest.raises(HTTPException) as exc:
        svc.create_asset(db, AssetCreate(name="泵2", barcode="BC-1"), c.id)
    assert exc.value.status_code == 409


def test_same_barcode_across_tenants_ok(db):
    c1 = _company(db, "acme"); c2 = _company(db, "globex")
    _ctx(db, c1.id)
    svc.create_asset(db, AssetCreate(name="泵", barcode="BC-1"), c1.id)
    _ctx(db, c2.id)
    svc.create_asset(db, AssetCreate(name="泵", barcode="BC-1"), c2.id)  # 不报错


def test_get_by_barcode_and_nfc(db):
    c = _company(db, "acme")
    _ctx(db, c.id)
    a = svc.create_asset(db, AssetCreate(name="泵", barcode="BC-9", nfc_id="NFC-9"), c.id)
    assert svc.get_by_barcode(db, "BC-9").id == a.id
    assert svc.get_by_nfc(db, "NFC-9").id == a.id
    assert svc.get_by_barcode(db, "nope") is None


def test_cycle_guard(db):
    c = _company(db, "acme")
    _ctx(db, c.id)
    root = svc.create_asset(db, AssetCreate(name="根"), c.id)
    child = svc.create_asset(db, AssetCreate(name="子", parent_id=root.id), c.id)
    with pytest.raises(HTTPException) as exc:
        svc.update_asset(db, root, AssetUpdate(parent_id=child.id), c.id)
    assert exc.value.status_code == 400


def test_relations_and_filters(db):
    from app.models.user import User
    c = _company(db, "acme")
    _ctx(db, c.id)
    u = User(company_id=c.id, email="w@a.com", password_hash="x", name="W")
    db.add(u); db.commit()
    a = svc.create_asset(db, AssetCreate(name="泵", assigned_user_ids=[u.id]), c.id)
    assert svc.assigned_user_ids(db, a.id) == [u.id]
    # 过滤
    rows = svc.list_assets(db, status="OPERATIONAL")
    assert any(x.id == a.id for x in rows)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_asset_service.py -v`
Expected: FAIL（`ModuleNotFoundError`）。

- [ ] **Step 3: 实现 schema**

Create `backend/app/schemas/asset.py`:

```python
"""资产 schema。"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.asset_status import AssetStatus


class AssetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    parent_id: str | None = None
    location_id: str | None = None
    category_id: str | None = None
    status: AssetStatus = AssetStatus.OPERATIONAL
    serial_number: str = ""
    model: str = ""
    manufacturer: str = ""
    power: str = ""
    warranty_expiration_date: date | None = None
    in_service_date: date | None = None
    acquisition_cost: Decimal | None = None
    barcode: str | None = None
    nfc_id: str | None = None
    primary_user_id: str | None = None
    assigned_user_ids: list[str] = []
    team_ids: list[str] = []


class AssetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    parent_id: str | None = None
    location_id: str | None = None
    category_id: str | None = None
    status: AssetStatus | None = None
    serial_number: str | None = None
    model: str | None = None
    manufacturer: str | None = None
    power: str | None = None
    warranty_expiration_date: date | None = None
    in_service_date: date | None = None
    acquisition_cost: Decimal | None = None
    barcode: str | None = None
    nfc_id: str | None = None
    primary_user_id: str | None = None
    assigned_user_ids: list[str] | None = None
    team_ids: list[str] | None = None


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    custom_id: str
    name: str
    description: str
    parent_id: str | None = None
    location_id: str | None = None
    category_id: str | None = None
    status: AssetStatus
    serial_number: str
    model: str
    manufacturer: str
    power: str
    warranty_expiration_date: date | None = None
    in_service_date: date | None = None
    acquisition_cost: Decimal | None = None
    barcode: str | None = None
    nfc_id: str | None = None
    primary_user_id: str | None = None
    assigned_user_ids: list[str] = []
    team_ids: list[str] = []


class AssetMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    custom_id: str


class DowntimeCreate(BaseModel):
    started_at: datetime
    ended_at: datetime | None = None
    reason: str = ""
    downtime_type: str = "manual"


class DowntimeClose(BaseModel):
    ended_at: datetime


class DowntimeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    asset_id: str
    started_at: datetime
    ended_at: datetime | None = None
    reason: str
    downtime_type: str
```

- [ ] **Step 4: 实现服务**

Create `backend/app/services/maintenance_asset_service.py`:

```python
"""CMMS 资产服务：CRUD、树（防环）、customId、barcode/nfc 唯一与查询、关联、停机。"""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.errors import bad_request, conflict
from app.models.asset_downtime import AssetDowntime
from app.models.base import utcnow
from app.models.maintenance_asset import Asset, AssetTeam, AssetUser
from app.schemas.asset import AssetCreate, AssetUpdate, DowntimeCreate, DowntimeClose
from app.services import sequence_service


def assigned_user_ids(db: Session, asset_id: str) -> list[str]:
    return list(db.execute(
        select(AssetUser.user_id).where(AssetUser.asset_id == asset_id)
    ).scalars().all())


def team_ids(db: Session, asset_id: str) -> list[str]:
    return list(db.execute(
        select(AssetTeam.team_id).where(AssetTeam.asset_id == asset_id)
    ).scalars().all())


def to_read(db: Session, a: Asset) -> dict:
    return {
        "id": a.id, "custom_id": a.custom_id, "name": a.name, "description": a.description,
        "parent_id": a.parent_id, "location_id": a.location_id, "category_id": a.category_id,
        "status": a.status, "serial_number": a.serial_number, "model": a.model,
        "manufacturer": a.manufacturer, "power": a.power,
        "warranty_expiration_date": a.warranty_expiration_date,
        "in_service_date": a.in_service_date, "acquisition_cost": a.acquisition_cost,
        "barcode": a.barcode, "nfc_id": a.nfc_id, "primary_user_id": a.primary_user_id,
        "assigned_user_ids": assigned_user_ids(db, a.id), "team_ids": team_ids(db, a.id),
    }


def _check_code_unique(db: Session, field, value: str | None, exclude_id: str | None) -> None:
    """barcode / nfc_id 在当前租户内（read-scope 已限定）唯一。value 为空跳过。"""
    if not value:
        return
    stmt = select(Asset.id).where(field == value, Asset.is_active.is_(True))
    if exclude_id is not None:
        stmt = stmt.where(Asset.id != exclude_id)
    if db.execute(stmt).first() is not None:
        label = "条码" if field is Asset.barcode else "NFC 标识"
        raise conflict("ASSET_CODE_TAKEN", f"{label}已被占用")


def _descendant_ids(db: Session, asset_id: str) -> set[str]:
    out: set[str] = set()
    frontier = [asset_id]
    while frontier:
        rows = db.execute(
            select(Asset.id).where(Asset.parent_id.in_(frontier), Asset.is_active.is_(True))
        ).scalars().all()
        rows = [r for r in rows if r not in out]
        out.update(rows)
        frontier = rows
    return out


def _validate_parent(db: Session, asset_id: str, parent_id: str | None) -> None:
    if parent_id is None:
        return
    if parent_id == asset_id:
        raise bad_request("ASSET_CYCLE", "父资产不能是自身")
    if parent_id in _descendant_ids(db, asset_id):
        raise bad_request("ASSET_CYCLE", "父资产不能是自身的后代")


def _sync_relations(db: Session, a: Asset, user_ids, team_ids_, company_id: str) -> None:
    if user_ids is not None:
        db.execute(delete(AssetUser).where(AssetUser.asset_id == a.id))
        for uid in dict.fromkeys(user_ids):
            db.add(AssetUser(asset_id=a.id, user_id=uid, company_id=company_id))
    if team_ids_ is not None:
        db.execute(delete(AssetTeam).where(AssetTeam.asset_id == a.id))
        for tid in dict.fromkeys(team_ids_):
            db.add(AssetTeam(asset_id=a.id, team_id=tid, company_id=company_id))


def create_asset(db: Session, payload: AssetCreate, company_id: str) -> Asset:
    _check_code_unique(db, Asset.barcode, payload.barcode, None)
    _check_code_unique(db, Asset.nfc_id, payload.nfc_id, None)
    seq = sequence_service.next_value(db, "asset", company_id)
    data = payload.model_dump(exclude={"assigned_user_ids", "team_ids"})
    a = Asset(custom_id=sequence_service.format_custom_id("A", seq), company_id=company_id, **data)
    db.add(a)
    db.flush()
    _sync_relations(db, a, payload.assigned_user_ids, payload.team_ids, company_id)
    db.commit()
    db.refresh(a)
    return a


def list_assets(db: Session, *, location_id: str | None = None, category_id: str | None = None,
                status: str | None = None, parent_id: str | None = None) -> list[Asset]:
    stmt = select(Asset).where(Asset.is_active.is_(True))
    if location_id is not None:
        stmt = stmt.where(Asset.location_id == location_id)
    if category_id is not None:
        stmt = stmt.where(Asset.category_id == category_id)
    if status is not None:
        stmt = stmt.where(Asset.status == status)
    if parent_id is not None:
        stmt = stmt.where(Asset.parent_id == parent_id)
    return list(db.execute(stmt).scalars().all())


def list_children(db: Session, asset_id: str) -> list[Asset]:
    return list(db.execute(
        select(Asset).where(Asset.parent_id == asset_id, Asset.is_active.is_(True))
    ).scalars().all())


def get_asset(db: Session, asset_id: str) -> Asset | None:
    a = db.get(Asset, asset_id)
    if a is None or not a.is_active:
        return None
    return a


def get_by_barcode(db: Session, code: str) -> Asset | None:
    return db.execute(
        select(Asset).where(Asset.barcode == code, Asset.is_active.is_(True))
    ).scalar_one_or_none()


def get_by_nfc(db: Session, nfc: str) -> Asset | None:
    return db.execute(
        select(Asset).where(Asset.nfc_id == nfc, Asset.is_active.is_(True))
    ).scalar_one_or_none()


def update_asset(db: Session, a: Asset, payload: AssetUpdate, company_id: str) -> Asset:
    data = payload.model_dump(exclude_unset=True)
    if "parent_id" in data:
        _validate_parent(db, a.id, data["parent_id"])
    if "barcode" in data:
        _check_code_unique(db, Asset.barcode, data["barcode"], a.id)
    if "nfc_id" in data:
        _check_code_unique(db, Asset.nfc_id, data["nfc_id"], a.id)
    user_ids = data.pop("assigned_user_ids", None)
    team_ids_ = data.pop("team_ids", None)
    for k, v in data.items():
        setattr(a, k, v)
    _sync_relations(db, a, user_ids, team_ids_, company_id)
    db.commit()
    db.refresh(a)
    return a


def delete_asset(db: Session, a: Asset) -> None:
    if list_children(db, a.id):
        raise bad_request("ASSET_HAS_CHILDREN", "请先删除子资产")
    a.is_active = False
    a.deleted_at = utcnow()
    db.commit()


# --- 停机 ---

def add_downtime(db: Session, asset_id: str, payload: DowntimeCreate, company_id: str) -> AssetDowntime:
    dt = AssetDowntime(
        asset_id=asset_id, started_at=payload.started_at, ended_at=payload.ended_at,
        reason=payload.reason, downtime_type=payload.downtime_type, company_id=company_id,
    )
    db.add(dt)
    db.commit()
    db.refresh(dt)
    return dt


def list_downtimes(db: Session, asset_id: str) -> list[AssetDowntime]:
    return list(db.execute(
        select(AssetDowntime).where(AssetDowntime.asset_id == asset_id)
        .order_by(AssetDowntime.started_at)
    ).scalars().all())


def get_downtime(db: Session, downtime_id: str) -> AssetDowntime | None:
    return db.get(AssetDowntime, downtime_id)


def close_downtime(db: Session, dt: AssetDowntime, payload: DowntimeClose) -> AssetDowntime:
    dt.ended_at = payload.ended_at
    db.commit()
    db.refresh(dt)
    return dt
```

- [ ] **Step 5: 运行确认通过**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_asset_service.py -v`
Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" add backend/app/schemas/asset.py backend/app/services/maintenance_asset_service.py backend/tests/test_asset_service.py
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" commit -m "feat(asset): asset service (CRUD/tree/customId/barcode/relations/downtime) + schemas"
```

---

## Task 8: 资产路由 + 停机端点（/api/v1/assets）

**Files:**
- Create: `backend/app/routers/assets.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_assets_api.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_assets_api.py`:

```python
def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email,
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_create_list_custom_id(client):
    t = _admin(client)
    a = client.post("/api/v1/assets", headers=_h(t), json={"name": "泵1"}).json()
    assert a["custom_id"] == "A000001"
    assert a["status"] == "OPERATIONAL"
    names = {x["name"] for x in client.get("/api/v1/assets", headers=_h(t)).json()}
    assert names == {"泵1"}


def test_by_barcode_and_nfc(client):
    t = _admin(client)
    client.post("/api/v1/assets", headers=_h(t), json={"name": "泵", "barcode": "BC1", "nfc_id": "N1"})
    assert client.get("/api/v1/assets/by-barcode/BC1", headers=_h(t)).json()["name"] == "泵"
    assert client.get("/api/v1/assets/by-nfc/N1", headers=_h(t)).json()["name"] == "泵"
    assert client.get("/api/v1/assets/by-barcode/nope", headers=_h(t)).status_code == 404


def test_barcode_conflict_409(client):
    t = _admin(client)
    client.post("/api/v1/assets", headers=_h(t), json={"name": "泵1", "barcode": "DUP"})
    r = client.post("/api/v1/assets", headers=_h(t), json={"name": "泵2", "barcode": "DUP"})
    assert r.status_code == 409, r.text


def test_filter_by_status_and_children(client):
    t = _admin(client)
    root = client.post("/api/v1/assets", headers=_h(t), json={"name": "根"}).json()
    client.post("/api/v1/assets", headers=_h(t), json={"name": "子", "parent_id": root["id"]})
    kids = client.get(f"/api/v1/assets/{root['id']}/children", headers=_h(t)).json()
    assert {k["name"] for k in kids} == {"子"}
    down = client.get("/api/v1/assets?status=DOWN", headers=_h(t)).json()
    assert down == []


def test_downtime_register_and_close(client):
    t = _admin(client)
    aid = client.post("/api/v1/assets", headers=_h(t), json={"name": "泵"}).json()["id"]
    r = client.post(f"/api/v1/assets/{aid}/downtimes", headers=_h(t),
                    json={"started_at": "2026-05-30T08:00:00", "reason": "故障"})
    assert r.status_code == 201, r.text
    did = r.json()["id"]
    assert r.json()["ended_at"] is None
    r2 = client.patch(f"/api/v1/assets/{aid}/downtimes/{did}", headers=_h(t),
                      json={"ended_at": "2026-05-30T10:00:00"})
    assert r2.status_code == 200
    assert r2.json()["ended_at"].startswith("2026-05-30T10:00:00")
    lst = client.get(f"/api/v1/assets/{aid}/downtimes", headers=_h(t)).json()
    assert len(lst) == 1


def test_technician_can_edit_not_delete(client):
    admin = _admin(client)
    # 建一个 technician 用户
    client.post("/api/v1/users", headers=_h(admin), json={
        "email": "tech@acme.com", "password": "secret123", "name": "T"})
    # 取 technician 角色 id 并改派
    roles = client.get("/api/v1/roles", headers=_h(admin)).json()
    tech_role = next(r for r in roles if r["code"] == "technician")["id"]
    uid = [u for u in client.get("/api/v1/users", headers=_h(admin)).json()
           if u["email"] == "tech@acme.com"][0]["id"]
    client.patch(f"/api/v1/users/{uid}", headers=_h(admin), json={"role_id": tech_role})
    tech = client.post("/api/v1/auth/login", json={
        "email": "tech@acme.com", "password": "secret123", "company_slug": "acme"}).json()["access_token"]
    aid = client.post("/api/v1/assets", headers=_h(admin), json={"name": "泵"}).json()["id"]
    assert client.patch(f"/api/v1/assets/{aid}", headers=_h(tech),
                        json={"status": "DOWN"}).status_code == 200
    assert client.delete(f"/api/v1/assets/{aid}", headers=_h(tech)).status_code == 403


def test_requires_auth(client):
    assert client.get("/api/v1/assets").status_code == 401
```

- [ ] **Step 2: 运行确认失败**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_assets_api.py -v`
Expected: FAIL（404）。

- [ ] **Step 3: 实现路由 + 挂载**

Create `backend/app/routers/assets.py`:

```python
"""CMMS 资产 API（/api/v1/assets）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.asset_downtime import AssetDowntime
from app.models.maintenance_asset import Asset
from app.models.user import User
from app.schemas.asset import (
    AssetCreate, AssetMini, AssetRead, AssetUpdate,
    DowntimeClose, DowntimeCreate, DowntimeRead,
)
from app.services import maintenance_asset_service as svc

router = APIRouter(prefix="/api/v1/assets", tags=["assets"])


def _ensure(a: Asset | None, company_id: str) -> Asset:
    if a is None or a.company_id != company_id:
        raise not_found("ASSET_NOT_FOUND", "资产不存在")
    return a


def _ensure_dt(dt: AssetDowntime | None, asset_id: str, company_id: str) -> AssetDowntime:
    if dt is None or dt.asset_id != asset_id or dt.company_id != company_id:
        raise not_found("DOWNTIME_NOT_FOUND", "停机记录不存在")
    return dt


@router.get("", response_model=list[AssetRead])
def list_assets(location_id: str | None = None, category_id: str | None = None,
                status: str | None = None, parent_id: str | None = None,
                db: Session = Depends(get_db),
                current_user: User = Depends(require_permission(permissions.ASSET_VIEW))):
    rows = svc.list_assets(db, location_id=location_id, category_id=category_id,
                           status=status, parent_id=parent_id)
    return [svc.to_read(db, a) for a in rows]


@router.get("/mini", response_model=list[AssetMini])
def list_mini(db: Session = Depends(get_db),
              current_user: User = Depends(require_permission(permissions.ASSET_VIEW))):
    return svc.list_assets(db)


@router.get("/by-barcode/{code}", response_model=AssetRead)
def get_by_barcode(code: str, db: Session = Depends(get_db),
                   current_user: User = Depends(require_permission(permissions.ASSET_VIEW))):
    a = svc.get_by_barcode(db, code)
    if a is None:
        raise not_found("ASSET_NOT_FOUND", "资产不存在")
    return svc.to_read(db, a)


@router.get("/by-nfc/{nfc}", response_model=AssetRead)
def get_by_nfc(nfc: str, db: Session = Depends(get_db),
               current_user: User = Depends(require_permission(permissions.ASSET_VIEW))):
    a = svc.get_by_nfc(db, nfc)
    if a is None:
        raise not_found("ASSET_NOT_FOUND", "资产不存在")
    return svc.to_read(db, a)


@router.post("", response_model=AssetRead, status_code=201)
def create_asset(payload: AssetCreate, db: Session = Depends(get_db),
                 current_user: User = Depends(require_permission(permissions.ASSET_CREATE))):
    a = svc.create_asset(db, payload, current_user.company_id)
    return svc.to_read(db, a)


@router.get("/{asset_id}", response_model=AssetRead)
def get_asset(asset_id: str, db: Session = Depends(get_db),
              current_user: User = Depends(require_permission(permissions.ASSET_VIEW))):
    a = _ensure(svc.get_asset(db, asset_id), current_user.company_id)
    return svc.to_read(db, a)


@router.get("/{asset_id}/children", response_model=list[AssetRead])
def list_children(asset_id: str, db: Session = Depends(get_db),
                  current_user: User = Depends(require_permission(permissions.ASSET_VIEW))):
    _ensure(svc.get_asset(db, asset_id), current_user.company_id)
    return [svc.to_read(db, a) for a in svc.list_children(db, asset_id)]


@router.patch("/{asset_id}", response_model=AssetRead)
def update_asset(asset_id: str, payload: AssetUpdate, db: Session = Depends(get_db),
                 current_user: User = Depends(require_permission(permissions.ASSET_EDIT))):
    a = _ensure(svc.get_asset(db, asset_id), current_user.company_id)
    a = svc.update_asset(db, a, payload, current_user.company_id)
    return svc.to_read(db, a)


@router.delete("/{asset_id}", status_code=204)
def delete_asset(asset_id: str, db: Session = Depends(get_db),
                 current_user: User = Depends(require_permission(permissions.ASSET_DELETE))):
    a = _ensure(svc.get_asset(db, asset_id), current_user.company_id)
    svc.delete_asset(db, a)


@router.post("/{asset_id}/downtimes", response_model=DowntimeRead, status_code=201)
def add_downtime(asset_id: str, payload: DowntimeCreate, db: Session = Depends(get_db),
                 current_user: User = Depends(require_permission(permissions.ASSET_EDIT))):
    _ensure(svc.get_asset(db, asset_id), current_user.company_id)
    return svc.add_downtime(db, asset_id, payload, current_user.company_id)


@router.get("/{asset_id}/downtimes", response_model=list[DowntimeRead])
def list_downtimes(asset_id: str, db: Session = Depends(get_db),
                   current_user: User = Depends(require_permission(permissions.ASSET_VIEW))):
    _ensure(svc.get_asset(db, asset_id), current_user.company_id)
    return svc.list_downtimes(db, asset_id)


@router.patch("/{asset_id}/downtimes/{downtime_id}", response_model=DowntimeRead)
def close_downtime(asset_id: str, downtime_id: str, payload: DowntimeClose,
                   db: Session = Depends(get_db),
                   current_user: User = Depends(require_permission(permissions.ASSET_EDIT))):
    _ensure(svc.get_asset(db, asset_id), current_user.company_id)
    dt = _ensure_dt(svc.get_downtime(db, downtime_id), asset_id, current_user.company_id)
    return svc.close_downtime(db, dt, payload)
```

Modify `backend/app/main.py` — 加 `from app.routers import assets`；加 `app.include_router(assets.router)`。

> 路由顺序：`/mini`、`/by-barcode/{code}`、`/by-nfc/{nfc}` 都在 `/{asset_id}` 之前声明（上面已满足），避免被参数路由吞掉。

- [ ] **Step 4: 运行确认通过**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_assets_api.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" add backend/app/routers/assets.py backend/app/main.py backend/tests/test_assets_api.py
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" commit -m "feat(asset): asset + downtime API (/api/v1/assets)"
```

---

## Task 9: Alembic 迁移 + 重建 dev.db

本期所有表均为新建（`create_table`），FK 在 SQLite 与 MySQL 均可，**无需** dialect 分支。

**Files:**
- Create: `backend/alembic/versions/20260530_0002_phase1a_base_domain.py`

- [ ] **Step 1: 确认模型已入 metadata**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -c "import app.models; from app.models.base import Base; print(sorted(t for t in Base.metadata.tables if t in ('tb_sequence','tb_asset_category','tb_team','tb_team_user','tb_location','tb_location_user','tb_location_team','tb_asset','tb_asset_user','tb_asset_team','tb_asset_downtime')))"`
Expected: 全部 11 张表名都打印出来。

- [ ] **Step 2: 写迁移**

Create `backend/alembic/versions/20260530_0002_phase1a_base_domain.py`:

```python
"""phase1a base domain: sequence, asset_category, team(+members),
location(+relations), asset(+relations), asset_downtime

Revision ID: phase1a_base_domain
Revises: phase0_platform
Create Date: 2026-05-30

Hand-authored (MySQL prod + SQLite dev/test). All new tables -> create_table
works on both dialects, no dialect branching needed.
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import DATETIME6

revision: str = "phase1a_base_domain"
down_revision: str | Sequence[str] | None = "phase0_platform"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts() -> list[sa.Column]:
    return [
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
    ]


def _soft() -> list[sa.Column]:
    return [
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", DATETIME6, nullable=True),
    ]


def _company_fk() -> sa.Column:
    return sa.Column(
        "company_id", sa.String(36),
        sa.ForeignKey("tb_company.id", ondelete="CASCADE"), nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "tb_sequence",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("scope", sa.String(40), nullable=False),
        sa.Column("next_val", sa.Integer(), nullable=False),
        *_ts(),
        sa.UniqueConstraint("company_id", "scope", name="uq_sequence_company_scope"),
    )
    op.create_index("ix_tb_sequence_company_id", "tb_sequence", ["company_id"])

    op.create_table(
        "tb_asset_category",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("name", sa.String(128), nullable=False),
        *_ts(), *_soft(),
        sa.UniqueConstraint("company_id", "name", name="uq_asset_category_company_name"),
    )
    op.create_index("ix_tb_asset_category_company_id", "tb_asset_category", ["company_id"])
    op.create_index("ix_tb_asset_category_is_active", "tb_asset_category", ["is_active"])

    op.create_table(
        "tb_team",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        *_ts(), *_soft(),
        sa.UniqueConstraint("company_id", "name", name="uq_team_company_name"),
    )
    op.create_index("ix_tb_team_company_id", "tb_team", ["company_id"])
    op.create_index("ix_tb_team_is_active", "tb_team", ["is_active"])

    op.create_table(
        "tb_team_user",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("team_id", sa.String(36),
                  sa.ForeignKey("tb_team.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("tb_user.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("team_id", "user_id", name="uq_team_user"),
    )
    op.create_index("ix_tb_team_user_company_id", "tb_team_user", ["company_id"])
    op.create_index("ix_tb_team_user_team_id", "tb_team_user", ["team_id"])
    op.create_index("ix_tb_team_user_user_id", "tb_team_user", ["user_id"])

    op.create_table(
        "tb_location",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("custom_id", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("parent_id", sa.String(36),
                  sa.ForeignKey("tb_location.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("address", sa.String(500), nullable=False, server_default=""),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        *_ts(), *_soft(),
    )
    op.create_index("ix_tb_location_company_id", "tb_location", ["company_id"])
    op.create_index("ix_tb_location_parent_id", "tb_location", ["parent_id"])
    op.create_index("ix_tb_location_is_active", "tb_location", ["is_active"])

    op.create_table(
        "tb_location_user",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("location_id", sa.String(36),
                  sa.ForeignKey("tb_location.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("tb_user.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("location_id", "user_id", name="uq_location_user"),
    )
    op.create_index("ix_tb_location_user_company_id", "tb_location_user", ["company_id"])
    op.create_index("ix_tb_location_user_location_id", "tb_location_user", ["location_id"])
    op.create_index("ix_tb_location_user_user_id", "tb_location_user", ["user_id"])

    op.create_table(
        "tb_location_team",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("location_id", sa.String(36),
                  sa.ForeignKey("tb_location.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.String(36),
                  sa.ForeignKey("tb_team.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("location_id", "team_id", name="uq_location_team"),
    )
    op.create_index("ix_tb_location_team_company_id", "tb_location_team", ["company_id"])
    op.create_index("ix_tb_location_team_location_id", "tb_location_team", ["location_id"])
    op.create_index("ix_tb_location_team_team_id", "tb_location_team", ["team_id"])

    op.create_table(
        "tb_asset",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("custom_id", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("parent_id", sa.String(36),
                  sa.ForeignKey("tb_asset.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("location_id", sa.String(36),
                  sa.ForeignKey("tb_location.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("category_id", sa.String(36),
                  sa.ForeignKey("tb_asset_category.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status",
                  sa.Enum("OPERATIONAL", "STANDBY", "MODERNIZATION", "INSPECTION_SCHEDULED",
                          "COMMISSIONING", "EMERGENCY_SHUTDOWN", "DOWN", name="assetstatus"),
                  nullable=False),
        sa.Column("serial_number", sa.String(200), nullable=False, server_default=""),
        sa.Column("model", sa.String(200), nullable=False, server_default=""),
        sa.Column("manufacturer", sa.String(200), nullable=False, server_default=""),
        sa.Column("power", sa.String(100), nullable=False, server_default=""),
        sa.Column("warranty_expiration_date", sa.Date(), nullable=True),
        sa.Column("in_service_date", sa.Date(), nullable=True),
        sa.Column("acquisition_cost", sa.Numeric(18, 2), nullable=True),
        sa.Column("barcode", sa.String(120), nullable=True),
        sa.Column("nfc_id", sa.String(120), nullable=True),
        sa.Column("primary_user_id", sa.String(36),
                  sa.ForeignKey("tb_user.id", ondelete="SET NULL"), nullable=True),
        *_ts(), *_soft(),
    )
    op.create_index("ix_tb_asset_company_id", "tb_asset", ["company_id"])
    op.create_index("ix_tb_asset_parent_id", "tb_asset", ["parent_id"])
    op.create_index("ix_tb_asset_location_id", "tb_asset", ["location_id"])
    op.create_index("ix_tb_asset_category_id", "tb_asset", ["category_id"])
    op.create_index("ix_tb_asset_barcode", "tb_asset", ["barcode"])
    op.create_index("ix_tb_asset_nfc_id", "tb_asset", ["nfc_id"])
    op.create_index("ix_tb_asset_primary_user_id", "tb_asset", ["primary_user_id"])
    op.create_index("ix_tb_asset_is_active", "tb_asset", ["is_active"])

    op.create_table(
        "tb_asset_user",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("asset_id", sa.String(36),
                  sa.ForeignKey("tb_asset.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("tb_user.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("asset_id", "user_id", name="uq_asset_user"),
    )
    op.create_index("ix_tb_asset_user_company_id", "tb_asset_user", ["company_id"])
    op.create_index("ix_tb_asset_user_asset_id", "tb_asset_user", ["asset_id"])
    op.create_index("ix_tb_asset_user_user_id", "tb_asset_user", ["user_id"])

    op.create_table(
        "tb_asset_team",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("asset_id", sa.String(36),
                  sa.ForeignKey("tb_asset.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.String(36),
                  sa.ForeignKey("tb_team.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("asset_id", "team_id", name="uq_asset_team"),
    )
    op.create_index("ix_tb_asset_team_company_id", "tb_asset_team", ["company_id"])
    op.create_index("ix_tb_asset_team_asset_id", "tb_asset_team", ["asset_id"])
    op.create_index("ix_tb_asset_team_team_id", "tb_asset_team", ["team_id"])

    op.create_table(
        "tb_asset_downtime",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("asset_id", sa.String(36),
                  sa.ForeignKey("tb_asset.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("started_at", DATETIME6, nullable=False),
        sa.Column("ended_at", DATETIME6, nullable=True),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("downtime_type", sa.String(20), nullable=False, server_default="manual"),
        *_ts(),
    )
    op.create_index("ix_tb_asset_downtime_company_id", "tb_asset_downtime", ["company_id"])
    op.create_index("ix_tb_asset_downtime_asset_id", "tb_asset_downtime", ["asset_id"])


def downgrade() -> None:
    for tbl in (
        "tb_asset_downtime", "tb_asset_team", "tb_asset_user", "tb_asset",
        "tb_location_team", "tb_location_user", "tb_location",
        "tb_team_user", "tb_team", "tb_asset_category", "tb_sequence",
    ):
        op.drop_table(tbl)
```

- [ ] **Step 3: 单 head + 全链 upgrade（SQLite）**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -c "from alembic.config import Config;from alembic.script import ScriptDirectory;print(ScriptDirectory.from_config(Config('alembic.ini')).get_heads())"`
Expected: `('phase1a_base_domain',)`（单 head）。

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && rm -f /tmp/p1a.db && DATABASE_URL="sqlite:////tmp/p1a.db" alembic upgrade head`
Expected: 无错误，升到 `phase1a_base_domain`。

- [ ] **Step 4: downgrade -1 / upgrade head 往返**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && DATABASE_URL="sqlite:////tmp/p1a.db" alembic downgrade -1 && DATABASE_URL="sqlite:////tmp/p1a.db" alembic upgrade head`
Expected: 均成功（downgrade 回到 `phase0_platform`，再升回 `phase1a_base_domain`）。

- [ ] **Step 5: 重建 dev.db**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && rm -f dev.db && alembic upgrade head`
Expected: dev.db 重建，含全部 1A 表。
Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -c "import sqlite3;c=sqlite3.connect('dev.db');t=set(r[0] for r in c.execute('SELECT name FROM sqlite_master WHERE type=\"table\"'));print('phase1a_ok', all(x in t for x in ('tb_sequence','tb_asset','tb_location','tb_team','tb_asset_downtime')));print('ver', c.execute('SELECT version_num FROM alembic_version').fetchone()[0])"`
Expected: `phase1a_ok True` 且 `ver phase1a_base_domain`。

- [ ] **Step 6: 提交**

```bash
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" add backend/alembic/versions/20260530_0002_phase1a_base_domain.py
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" commit -m "build(db): Alembic migration for Phase 1A base domain tables"
```

---

## Task 10: 跨租户隔离端到端验收 + 全量回归

**Files:**
- Test: `backend/tests/test_phase1a_cross_tenant_e2e.py`

- [ ] **Step 1: 写测试**

Create `backend/tests/test_phase1a_cross_tenant_e2e.py`:

```python
def _register(client, company, email):
    r = client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email, "password": "secret123", "name": "Admin"})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_assets_isolated(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    client.post("/api/v1/assets", headers=_h(ta), json={"name": "A泵"})
    bid = client.post("/api/v1/assets", headers=_h(tb), json={"name": "B泵"}).json()["id"]
    a_names = {x["name"] for x in client.get("/api/v1/assets", headers=_h(ta)).json()}
    assert a_names == {"A泵"}
    assert client.get(f"/api/v1/assets/{bid}", headers=_h(ta)).status_code == 404
    assert client.patch(f"/api/v1/assets/{bid}", headers=_h(ta),
                        json={"name": "hacked"}).status_code == 404
    assert client.delete(f"/api/v1/assets/{bid}", headers=_h(ta)).status_code == 404


def test_locations_isolated(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    bid = client.post("/api/v1/locations", headers=_h(tb), json={"name": "B区"}).json()["id"]
    assert client.get("/api/v1/locations", headers=_h(ta)).json() == []
    assert client.get(f"/api/v1/locations/{bid}", headers=_h(ta)).status_code == 404


def test_teams_and_categories_isolated(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    btid = client.post("/api/v1/teams", headers=_h(tb), json={"name": "B班"}).json()["id"]
    bcid = client.post("/api/v1/asset-categories", headers=_h(tb), json={"name": "B类"}).json()["id"]
    assert client.get("/api/v1/teams", headers=_h(ta)).json() == []
    assert client.get("/api/v1/asset-categories", headers=_h(ta)).json() == []
    assert client.patch(f"/api/v1/teams/{btid}", headers=_h(ta), json={"name": "x"}).status_code == 404
    assert client.patch(f"/api/v1/asset-categories/{bcid}", headers=_h(ta),
                        json={"name": "x"}).status_code == 404


def test_custom_id_per_tenant_independent(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    a1 = client.post("/api/v1/assets", headers=_h(ta), json={"name": "x"}).json()["custom_id"]
    b1 = client.post("/api/v1/assets", headers=_h(tb), json={"name": "y"}).json()["custom_id"]
    assert a1 == "A000001" and b1 == "A000001"  # 两租户各自从 1 起


def test_cross_tenant_downtime_404(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    bid = client.post("/api/v1/assets", headers=_h(tb), json={"name": "B泵"}).json()["id"]
    assert client.post(f"/api/v1/assets/{bid}/downtimes", headers=_h(ta),
                       json={"started_at": "2026-05-30T08:00:00"}).status_code == 404
```

- [ ] **Step 2: 运行确认通过**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_phase1a_cross_tenant_e2e.py -v`
Expected: PASS。若任何跨租户访问未被拦截，回到 Task 5/7/8 检查 `_ensure*` 与作用域。

- [ ] **Step 3: 全量回归**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest -q`
Expected: 全部 PASS（Phase 0 + SOP + Phase 1A）。

- [ ] **Step 4: 提交**

```bash
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" add backend/tests/test_phase1a_cross_tenant_e2e.py
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" commit -m "test(phase1a): cross-tenant isolation e2e acceptance"
```

---

## 验收清单（对照 spec §1.1 范围）

- [ ] 通用每租户自增序列 Sequence（Task 2）
- [ ] AssetCategory CRUD（Task 3）
- [ ] Team CRUD + 成员（Task 4）
- [ ] Location 树 + customId(L%06d) + assignedTo/teams + mini/children（Task 5）
- [ ] AssetStatus 7 值 + UP/DOWN 归类（Task 6）
- [ ] Asset CRUD + 树 + customId(A%06d) + barcode/nfc 唯一与查询 + 过滤 + primaryUser/assignedTo/teams（Task 6/7/8）
- [ ] AssetDowntime 登记/闭合/列表（Task 6/7/8）
- [ ] RBAC 权限点 + 内置角色默认（Task 1；technician 可 asset.edit 不可 asset.delete 由 Task 8 验证）
- [ ] Alembic 迁移（Task 9，SQLite up/down/up + 重建 dev.db）
- [ ] 跨租户隔离端到端（Task 10）
- [ ] 明确不做项保持未做：停机树传播、折旧、平面图、vendors/customers/parts/files 关联、前端 UI

## 净室合规复核（实现完成后）

- [ ] 全部模型/代码原创，未参照 Atlas DDL/源码。
- [ ] 代码与产物中无 "Atlas" 字样、商标、文案、资源。
- [ ] 资产/位置树、状态机、停机记录、序列号为通用工程/领域模式，非受版权保护的具体表达。
