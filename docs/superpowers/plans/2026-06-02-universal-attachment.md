# 通用附件基础设施 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把程序专属附件原地泛化为多态通用附件基础设施，可挂任意业务实体（procedure/work_order/asset/request/location/part），现有 SOP 附件无损平移、行为不变、前端零改。

**Architecture:** 多态单表 `Attachment(entity_type, entity_id)`（无硬 FK）+ `ENTITY_REGISTRY`（entity_type → 宿主 model / view_perm / edit_perm / 钩子）。service 拆「泛型核心 + per-entity 钩子」：读路径全泛型；写路径泛型核心 + procedure 专属钩子（草稿态校验 + 审计）。procedure 别名端点保持无认证、host 查询走 bypass（容忍 SOP 裸奔 company_id 为 NULL）；RBAC 实体走租户作用域查询（跨租户 404 安全保证）。

**Tech Stack:** FastAPI + SQLAlchemy 2.0（Mapped/mapped_column）+ pytest（SQLite `create_all`，不依赖 alembic）+ alembic（生产迁移，末置）。门禁 ruff 0.15 / mypy 1.20，解释器 `backend/.venv/bin/python`。

**关键事实（已核实）：**
- 现有模型 `ProcedureAttachment`（`tb_procedure_attachment`），列 `procedure_id` FK→tb_procedure。引用点：`models/__init__.py`、`models/procedure.py`（relationship）、`services/attachment_service.py`、`services/version_flow_service.py:526`、`services/pdf/context.py:220`，及单元测试 `test_attachment_service.py` / `test_version_flow_service.py` / `pdf/test_engine.py` / `pdf/test_context.py`。
- 集成测试 `tests/integration/test_attachments.py` 是 API 级、不碰模型 → 不改即应保持绿（行为回归基准）。
- mixin：`NullableTenantMixin`（procedure/附件，company_id 可空）、`TenantMixin`（5 个 RBAC 实体，company_id NOT NULL）。租户字段 `company_id`。
- 宿主类名/表：`WorkOrder`(tb_work_order)、`Asset`(tb_asset, `models/maintenance_asset.py`)、`Request`(tb_request)、`Location`(tb_location)、`Part`(tb_part)、`Procedure`(tb_procedure)。
- 权限码：`work_order.view/edit`、`asset.view/edit`、`location.view/edit`、`part.view/edit`、`request.view`+**edit 用 `request.create`**（评审定）、procedure=None/None。
- 权限检查：`from app.deps import _user_permission_codes`（`_user_permission_codes(db, user) -> set[str]`，`perm in codes`）。
- errors：`bad_request(code,msg,field=None)` / `not_found(code,msg)` / `forbidden(code,msg)` / `app_error(status,code,msg)`。
- tenant：`tenant.set_current_company_id(id)` / `tenant.get_current_company_id()` / `tenant.is_bypassed()` / `tenant.bypass_tenant_scope()`（context manager）。`do_orm_execute` 在有上下文且非 bypass 时按 `company_id==X` 自动过滤 SELECT（会排除 company_id 为 NULL 的行）。
- 认证：注册 `POST /api/v1/auth/register {company_name,email,password,name}` → `access_token`，首用户 super_admin 全权限；`headers={"Authorization": f"Bearer {tok}"}`。
- storage：`storage.attachment_path(uid, ext)` / `storage.storage_root()` / `get_storage_backend().write/read/delete`（不动）。

**全局约定：** 所有命令在 `backend/` 下用 `.venv/bin/python`。每 task 测试绿 + `ruff check app/` + `mypy app/` 才提交。commit message 结尾固定加：
`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `app/models/attachment.py` | 改 | `ProcedureAttachment`→`Attachment`：多态列 entity_type/entity_id、去 FK/relationship、新索引 |
| `app/models/__init__.py` | 改 | export `Attachment`（替 `ProcedureAttachment`） |
| `app/models/procedure.py` | 改 | 移除 `attachments` relationship + TYPE_CHECKING import |
| `app/services/pdf/context.py` | 改 | 查询改 `Attachment` + entity_type 过滤 |
| `app/services/version_flow_service.py` | 改 | 第 526 行 delete 改 `Attachment` + entity_type 过滤；copy 调用不变 |
| `app/services/attachment_entities.py` | 新增 | `EntitySpec`、`ENTITY_REGISTRY`、`resolve_and_authorize` |
| `app/services/attachment_hooks.py` | 新增 | procedure 的 write_guard + 审计钩子（隔离循环依赖） |
| `app/services/attachment_service.py` | 改 | 写路径加 entity_type/entity_id + 钩子；读/上限泛化；copy_for_version/孤儿清理泛化 |
| `app/schemas/attachment.py` | 改 | `AttachmentOut` 加 entity_type/entity_id + procedure_id 兼容别名 |
| `app/routers/attachments.py` | 改 | 新增 `/attachments` query/form 端点；procedure 别名保持无认证转 service |
| `app/tasks/cleanup_attachments.py` | 改 | 扩展宿主存在性孤儿化（bypass 跨租户） |
| `alembic/versions/<rev>_universal_attachment.py` | 新增（末置） | 原地泛化迁移 |
| 单元测试若干 | 改 | 模型构造点 `ProcedureAttachment(procedure_id=)`→`Attachment(entity_type,entity_id)` |
| `tests/unit/services/test_attachment_entities.py` | 新增 | registry/resolve 单测 |
| `tests/integration/test_universal_attachments.py` | 新增 | 通用流 + 多态校验 + 跨租户 |
| `tests/unit/tasks/test_cleanup_attachments_hosts.py` | 新增 | 宿主孤儿化清理 |

---

## Task 1: 模型泛化（Attachment 多态单表）

把 `ProcedureAttachment` 改名 `Attachment`，`procedure_id`→`entity_id` + 新增 `entity_type`，去 FK 与双向 relationship，更新所有引用点。本 task 末尾全量旧测试（除直接构造模型的单测已同步更新外）应绿——证明无行为回归。

**Files:**
- Modify: `app/models/attachment.py`
- Modify: `app/models/__init__.py:11,110`
- Modify: `app/models/procedure.py:21,67`
- Modify: `app/services/attachment_service.py`（仅改名 + 列名，不改逻辑）
- Modify: `app/services/version_flow_service.py:19,526`
- Modify: `app/services/pdf/context.py:18,220-225`
- Modify: `tests/unit/services/test_attachment_service.py`、`test_version_flow_service.py`、`pdf/test_engine.py`、`pdf/test_context.py`（模型构造点）
- Test: `tests/unit/models/test_attachment_model.py`（新增）

- [ ] **Step 1: 写失败测试（新模型多态字段持久化）**

Create `tests/unit/models/test_attachment_model.py`：

```python
"""通用 Attachment 多态模型单测。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attachment import Attachment


def test_attachment_persists_entity_type_and_id(db: Session) -> None:
    att = Attachment(
        entity_type="work_order",
        entity_id="wo-1",
        file_name="r.pdf",
        storage_path="a/b.pdf",
        mime_type="application/pdf",
        size_bytes=3,
        description="",
        sort_order=0,
    )
    db.add(att)
    db.commit()
    row = db.execute(
        select(Attachment).where(
            Attachment.entity_type == "work_order", Attachment.entity_id == "wo-1"
        )
    ).scalar_one()
    assert row.id == att.id
    assert row.entity_type == "work_order"
    assert row.entity_id == "wo-1"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/models/test_attachment_model.py -v`
Expected: FAIL — `ImportError: cannot import name 'Attachment'`

- [ ] **Step 3: 重写模型为多态 Attachment**

Replace `app/models/attachment.py` 全文：

```python
"""通用附件模型：多态挂任意业务实体（entity_type + entity_id，无硬 FK）。"""

from __future__ import annotations

from sqlalchemy import BigInteger, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    NullableTenantMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDMixin,
)


class Attachment(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, NullableTenantMixin):
    """通用附件（多态软关联宿主实体；procedure 经 entity_type='procedure' 平移）。"""

    __tablename__ = "tb_attachment"

    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(36))
    file_name: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    __table_args__ = (
        Index("ix_tb_attachment_entity", "entity_type", "entity_id"),
        Index("ix_tb_attachment_storage_path", "storage_path"),
    )
```

- [ ] **Step 4: 更新 models/__init__.py**

`app/models/__init__.py`：
- 第 11 行 `from app.models.attachment import ProcedureAttachment` → `from app.models.attachment import Attachment`
- `__all__` 第 110 行 `"ProcedureAttachment",` → `"Attachment",`

- [ ] **Step 5: 移除 Procedure.attachments relationship**

`app/models/procedure.py`：
- 删第 21 行 TYPE_CHECKING `from app.models.attachment import ProcedureAttachment`
- 删第 67 行 `attachments: Mapped[list[ProcedureAttachment]] = relationship(back_populates="procedure")`
- 若 `from __future__ import annotations` 下 `ProcedureAttachment` 名不再被引用，确保无残留 import。

- [ ] **Step 6: 更新 attachment_service.py 的类名与列名（逻辑不变）**

`app/services/attachment_service.py` 内全部 `ProcedureAttachment` → `Attachment`，并把 procedure 专属查询补 entity_type 过滤。逐处：
- import：`from app.models.attachment import ProcedureAttachment` → `from app.models.attachment import Attachment`
- `_active_rows`（第 70-80）：
```python
def _active_rows(db: Session, procedure_id: str) -> list[Attachment]:
    return list(
        db.execute(
            select(Attachment)
            .where(
                Attachment.entity_type == "procedure",
                Attachment.entity_id == procedure_id,
                Attachment.is_active.is_(True),
            )
            .order_by(Attachment.sort_order, Attachment.created_at)
        ).scalars()
    )
```
- `get_or_404`（第 104-112）：`select(Attachment).where(Attachment.id == attachment_id, Attachment.is_active.is_(True))`
- `upload` 内构造（第 165）：
```python
    att = Attachment(
        entity_type="procedure",
        entity_id=procedure_id,
        file_name=name,
        ...
    )
```
- `copy_for_version`（第 247）构造同样改 `Attachment(entity_type="procedure", entity_id=dst_procedure_id, ...)`
- `_active_ref_count` / `orphan_storage_paths` / `delete_orphan_path` 内 `ProcedureAttachment`→`Attachment`（这些按 storage_path 跨 entity_type 去重，**不加 entity_type 过滤**——物理文件 GC 是全局的）。
- 类型注解 `-> ProcedureAttachment` 全改 `-> Attachment`。

> 本 task 仅机械改名 + procedure 查询补 entity_type；钩子/泛化在 Task 3 做。

- [ ] **Step 7: 更新 version_flow_service.py**

`app/services/version_flow_service.py`：
- 第 19 行 import 改 `Attachment`
- 第 526 行：
```python
    db.execute(
        delete(Attachment).where(
            Attachment.entity_type == "procedure", Attachment.entity_id == proc.id
        )
    )
```

- [ ] **Step 8: 更新 pdf/context.py**

`app/services/pdf/context.py`：
- 第 18 行 import 改 `Attachment`
- 第 220-225 查询：
```python
        for a in db.execute(
            select(Attachment)
            .where(
                Attachment.entity_type == "procedure",
                Attachment.entity_id == proc_id,
                Attachment.is_active.is_(True),
            )
            .order_by(Attachment.sort_order, Attachment.created_at)
        ).scalars()
```

- [ ] **Step 9: 更新直接构造模型的单元测试**

把以下文件中的 `ProcedureAttachment(procedure_id=X, ...)` 改为 `Attachment(entity_type="procedure", entity_id=X, ...)`，import 同步：
- `tests/unit/services/test_attachment_service.py:14,204`
- `tests/unit/services/test_version_flow_service.py:63,66`
- `tests/unit/services/pdf/test_engine.py:7,63`
- `tests/unit/services/pdf/test_context.py:9,73`

例（test_version_flow_service.py:66 区域）：
```python
    from app.models.attachment import Attachment
    ...
        Attachment(
            entity_type="procedure",
            entity_id=<原 procedure_id 值>,
            file_name=...,
            ...
        )
```
（`test_attachment_service.py:204` 的 `select(ProcedureAttachment).where(ProcedureAttachment.id == att.id)` → `select(Attachment).where(Attachment.id == att.id)`。）

- [ ] **Step 10: 运行新模型测试 + 全量回归**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/models/test_attachment_model.py tests/unit/services/test_attachment_service.py tests/integration/test_attachments.py tests/unit/services/test_version_flow_service.py tests/unit/services/pdf/ -v`
Expected: 全 PASS（集成 test_attachments.py 未改即绿 = 行为无回归）

- [ ] **Step 11: 门禁 + 提交**

Run: `cd backend && .venv/bin/python -m pytest -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: all green

```bash
git add backend/app/models backend/app/services backend/tests
git commit -m "$(cat <<'EOF'
refactor(attachment): generalize ProcedureAttachment to polymorphic Attachment

改名 ProcedureAttachment→Attachment、procedure_id→entity_id+entity_type，
去 tb_procedure FK 与双向 relationship，更新 service/version_flow/pdf 引用与
直接构造模型的单测。逻辑不变，集成测试不改即绿（行为无回归）。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: entity_registry + resolve_and_authorize + procedure 钩子

新增 registry（实体 → 宿主 model / 权限 / scoped / 钩子）与解析授权函数，及 procedure 专属钩子模块。

**Files:**
- Create: `app/services/attachment_hooks.py`
- Create: `app/services/attachment_entities.py`
- Test: `tests/unit/services/test_attachment_entities.py`

- [ ] **Step 1: 写失败测试（resolve 的各分支）**

Create `tests/unit/services/test_attachment_entities.py`：

```python
"""entity registry + resolve_and_authorize 单测。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import tenant
from app.models.maintenance_asset import Asset
from app.models.user import User
from app.services import attachment_entities as ae


def _company_user(db: Session, company_id: str) -> User:
    """构造一个带 super_admin 角色的内存 user（权限校验走 _user_permission_codes）。"""
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
            status="active",
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
    # B 公司用户解析 A 的 asset → 404
    tenant.set_current_company_id("co-b")
    b = db.query(User).filter(User.company_id == "co-b").one()
    with pytest.raises(HTTPException) as ei:
        ae.resolve_and_authorize(db, b, "asset", asset_id, "read")
    assert ei.value.status_code == 404
    # A 自己解析 → 通过
    tenant.set_current_company_id("co-a")
    host = ae.resolve_and_authorize(db, a, "asset", asset_id, "read")
    assert host.id == asset_id


def test_write_permission_denied_403(db: Session) -> None:
    """无 asset.edit 的用户写 → 403。"""
    from app.models.role import Role

    user = _company_user(db, "co-1")
    tenant.set_current_company_id("co-1")
    db.add(Asset(custom_id="A1", name="泵"))
    db.commit()
    asset_id = db.query(Asset).one().id
    # 把角色权限改成只读
    with tenant.bypass_tenant_scope():
        role = db.get(Role, user.role_id)
        role.code = "viewer"
        role.permissions = ["asset.view"]
        db.commit()
    with pytest.raises(HTTPException) as ei:
        ae.resolve_and_authorize(db, user, "asset", asset_id, "write")
    assert ei.value.status_code == 403
    # 读仍可
    assert ae.resolve_and_authorize(db, user, "asset", asset_id, "read").id == asset_id
```

> 注：`_user_permission_codes` 经 `effective_codes(role.code, role.permissions)`，super_admin 含全权限、viewer 用 stored 列表。若 super_admin 由 code 推断全集，测试用 viewer 显式 permissions 验证 403/200 分支。

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/services/test_attachment_entities.py -v`
Expected: FAIL — `ModuleNotFoundError: app.services.attachment_entities`

- [ ] **Step 3: 写 procedure 钩子模块**

Create `app/services/attachment_hooks.py`：

```python
"""procedure 实体的附件写钩子（草稿态校验 + 审计），隔离 service↔procedure 耦合。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.errors import bad_request
from app.models.attachment import Attachment
from app.models.procedure import Procedure
from app.services import audit_service


def procedure_write_guard(host: Any) -> None:
    """仅当前草稿可写附件（Q228）：废止→PROCEDURE_DEPRECATED；非当前草稿→PROCEDURE_READONLY。"""
    proc: Procedure = host
    if proc.deprecated_at is not None:
        raise bad_request("PROCEDURE_DEPRECATED", "程序已被废止，请先恢复后再操作")
    if not (proc.is_current and proc.status == "DRAFT"):
        raise bad_request("PROCEDURE_READONLY", "仅当前版本的草稿可编辑附件")


def procedure_audit_upload(
    db: Session, host: Any, att: Attachment, *, meta: RequestMeta
) -> None:
    audit_service.log_procedure_action(
        db,
        target_id=att.id,
        procedure_group_id=host.procedure_group_id,
        action="upload",
        meta=meta,
        new_value={"file_name": att.file_name, "size_bytes": att.size_bytes},
    )


def procedure_audit_update(
    db: Session, host: Any, att: Attachment, *, meta: RequestMeta, old_value: dict, new_value: dict
) -> None:
    audit_service.log_procedure_action(
        db,
        target_id=att.id,
        procedure_group_id=host.procedure_group_id,
        action="update",
        meta=meta,
        old_value=old_value,
        new_value=new_value,
    )


def procedure_audit_delete(
    db: Session, host: Any, att: Attachment, *, meta: RequestMeta
) -> None:
    audit_service.log_procedure_action(
        db,
        target_id=att.id,
        procedure_group_id=host.procedure_group_id,
        action="delete",
        meta=meta,
        old_value={"file_name": att.file_name},
    )
```

- [ ] **Step 4: 写 registry + resolve_and_authorize**

Create `app/services/attachment_entities.py`：

```python
"""通用附件的实体注册表 + 解析授权（多态权限随 entity_type 动态）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import permissions, tenant
from app.deps import _user_permission_codes
from app.errors import bad_request, forbidden, not_found
from app.models.location import Location
from app.models.maintenance_asset import Asset
from app.models.part import Part
from app.models.procedure import Procedure
from app.models.request import Request
from app.models.user import User
from app.models.work_order import WorkOrder
from app.services import attachment_hooks as hooks


@dataclass(frozen=True)
class EntitySpec:
    model: type[Any]
    view_perm: str | None
    edit_perm: str | None
    scoped: bool  # True=租户作用域查询；False=bypass（procedure 容忍 company_id NULL）
    write_guard: Callable[[Any], None] | None = None


ENTITY_REGISTRY: dict[str, EntitySpec] = {
    "procedure": EntitySpec(
        Procedure, None, None, scoped=False, write_guard=hooks.procedure_write_guard
    ),
    "work_order": EntitySpec(
        WorkOrder, permissions.WORK_ORDER_VIEW, permissions.WORK_ORDER_EDIT, scoped=True
    ),
    "asset": EntitySpec(
        Asset, permissions.ASSET_VIEW, permissions.ASSET_EDIT, scoped=True
    ),
    "location": EntitySpec(
        Location, permissions.LOCATION_VIEW, permissions.LOCATION_EDIT, scoped=True
    ),
    "part": EntitySpec(
        Part, permissions.PART_VIEW, permissions.PART_EDIT, scoped=True
    ),
    "request": EntitySpec(
        # request 无 .edit 权限码，附件写沿用 request.create（评审定）
        Request, permissions.REQUEST_VIEW, permissions.REQUEST_CREATE, scoped=True
    ),
}


def get_spec(entity_type: str) -> EntitySpec:
    spec = ENTITY_REGISTRY.get(entity_type)
    if spec is None:
        raise bad_request("INVALID_ENTITY_TYPE", "不支持的附件实体类型", field="entity_type")
    return spec


def _lookup_host(db: Session, spec: EntitySpec, entity_id: str) -> Any:
    stmt = select(spec.model).where(
        spec.model.id == entity_id, spec.model.is_active.is_(True)
    )
    if spec.scoped:
        host = db.execute(stmt).scalar_one_or_none()
    else:
        # procedure：company_id 可空，绕开租户 SELECT 过滤
        with tenant.bypass_tenant_scope():
            host = db.execute(stmt).scalar_one_or_none()
    if host is None:
        raise not_found("NOT_FOUND", "目标对象不存在")
    return host


def resolve_and_authorize(
    db: Session, user: User | None, entity_type: str, entity_id: str, action: str
) -> Any:
    """校验 entity_type（未知→400）→查宿主（不存在/跨租户→404）→授权（不足→403）。返回宿主。"""
    spec = get_spec(entity_type)
    host = _lookup_host(db, spec, entity_id)
    perm = spec.view_perm if action == "read" else spec.edit_perm
    if perm is not None:
        if user is None or perm not in _user_permission_codes(db, user):
            raise forbidden("FORBIDDEN", "权限不足")
    return host
```

- [ ] **Step 5: 运行测试通过**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/services/test_attachment_entities.py -v`
Expected: PASS（若 `_company_user` 的 Company/Role/User 字段名与实际不符，按模型实际必填字段微调——参考 `app/models/company.py`/`role.py`/`user.py`）

- [ ] **Step 6: 门禁 + 提交**

Run: `cd backend && .venv/bin/python -m pytest -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`

```bash
git add backend/app/services/attachment_entities.py backend/app/services/attachment_hooks.py backend/tests/unit/services/test_attachment_entities.py
git commit -m "$(cat <<'EOF'
feat(attachment): entity registry + resolve_and_authorize + procedure hooks

ENTITY_REGISTRY 映射 6 实体（procedure None/None + bypass，5 RBAC 实体租户
作用域）；resolve 校验 400/404/403；procedure 钩子保留草稿态校验与审计。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: service 写路径泛化（钩子串联）

把 service 的 upload/update/delete 改为「resolve+authorize → write_guard 钩子 → 泛型核心 → 审计钩子」，新增泛型 read 函数；procedure 经钩子保留全部行为。`copy_for_version`/孤儿清理保持（Task 1 已改名）。

**Files:**
- Modify: `app/services/attachment_service.py`
- Test: `tests/unit/services/test_attachment_service_generic.py`（新增）

- [ ] **Step 1: 写失败测试（通用实体 service 流 + procedure 钩子仍生效）**

Create `tests/unit/services/test_attachment_service_generic.py`：

```python
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

    with tenant.bypass_tenant_scope():
        db.add(Company(id=company_id, name="C", slug=f"c-{company_id}"))
        role = Role(company_id=company_id, code="super_admin", name="管理员", permissions=[])
        db.add(role)
        db.flush()
        u = User(
            company_id=company_id, email=f"u@{company_id}.com", name="U",
            password_hash="x", role_id=role.id, status="active",
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
    """非草稿 procedure 上传附件 → PROCEDURE_READONLY（钩子保留）。"""
    folder = factory.folder(prefix="QC")
    proc = factory.procedure(folder_id=folder.id, status="RELEASED", is_current=True)
    with pytest.raises(HTTPException) as ei:
        svc.upload_for(
            db, None, "procedure", proc.id, b"x", "a.txt",
            content_type="text/plain", description="", meta=META,
        )
    assert ei.value.detail["code"] == "PROCEDURE_READONLY"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/services/test_attachment_service_generic.py -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'upload_for'`

- [ ] **Step 3: 在 attachment_service.py 增泛型函数 + 钩子串联**

在 `app/services/attachment_service.py`：
1. 顶部 import 增：
```python
from app.models.user import User
from app.services import attachment_entities as entities
from app.services import attachment_hooks as hooks
```
2. 把 `_active_rows(db, procedure_id)` 改为按 (entity_type, entity_id)：
```python
def _active_rows(db: Session, entity_type: str, entity_id: str) -> list[Attachment]:
    return list(
        db.execute(
            select(Attachment)
            .where(
                Attachment.entity_type == entity_type,
                Attachment.entity_id == entity_id,
                Attachment.is_active.is_(True),
            )
            .order_by(Attachment.sort_order, Attachment.created_at)
        ).scalars()
    )
```
3. 既有 procedure 专用包装改为转调（保持 `rows_for`/`list_attachments`/`upload`/`update`/`delete` 旧签名给 procedure 别名与 version_flow 用）：
```python
def rows_for(db: Session, procedure_id: str) -> list[Attachment]:
    return _active_rows(db, "procedure", procedure_id)


def list_attachments(db: Session, procedure_id: str) -> list[Attachment]:
    return list_for(db, None, "procedure", procedure_id)
```
4. 新增泛型函数：
```python
def list_for(
    db: Session, user: User | None, entity_type: str, entity_id: str
) -> list[Attachment]:
    entities.resolve_and_authorize(db, user, entity_type, entity_id, "read")
    return _active_rows(db, entity_type, entity_id)


def download_for(db: Session, user: User | None, attachment_id: str) -> tuple[bytes, str, str]:
    att = get_or_404(db, attachment_id)
    entities.resolve_and_authorize(db, user, att.entity_type, att.entity_id, "read")
    return _bytes_or_404(att), att.mime_type, att.file_name


def preview_for(db: Session, user: User | None, attachment_id: str) -> tuple[bytes, str]:
    att = get_or_404(db, attachment_id)
    entities.resolve_and_authorize(db, user, att.entity_type, att.entity_id, "read")
    if att.mime_type not in PREVIEW_WHITELIST:
        raise app_error(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "ATTACHMENT_NOT_PREVIEWABLE",
            "该类型不支持在线预览",
        )
    return _bytes_or_404(att), att.mime_type


def upload_for(
    db: Session,
    user: User | None,
    entity_type: str,
    entity_id: str,
    data: bytes,
    file_name: str,
    *,
    content_type: str | None,
    description: str,
    meta: RequestMeta,
) -> Attachment:
    spec = entities.get_spec(entity_type)
    host = entities.resolve_and_authorize(db, user, entity_type, entity_id, "write")
    if spec.write_guard is not None:
        spec.write_guard(host)

    size = len(data)
    if size > MAX_FILE_BYTES:
        raise bad_request("ATTACHMENT_LIMIT_EXCEEDED", "单文件超过 50MB 上限", field="file")
    existing = _active_rows(db, entity_type, entity_id)
    if len(existing) + 1 > MAX_COUNT:
        raise bad_request("ATTACHMENT_LIMIT_EXCEEDED", "附件数量超过 30 个上限", field="file")
    if sum(a.size_bytes for a in existing) + size > MAX_TOTAL_BYTES:
        raise bad_request("ATTACHMENT_LIMIT_EXCEEDED", "附件总大小超过 200MB 上限", field="file")

    name = file_name.strip() or "未命名"
    uid = new_uuid()
    path = storage.attachment_path(uid, Path(name).suffix)
    rel = path.relative_to(storage.storage_root()).as_posix()
    get_storage_backend().write(rel, data)

    att = Attachment(
        entity_type=entity_type,
        entity_id=entity_id,
        file_name=name,
        storage_path=rel,
        mime_type=_resolve_mime(name, content_type),
        size_bytes=size,
        description=description.strip(),
        sort_order=len(existing),
    )
    db.add(att)
    db.flush()
    if entity_type == "procedure":
        hooks.procedure_audit_upload(db, host, att, meta=meta)
    return att


def update_for(
    db: Session,
    user: User | None,
    attachment_id: str,
    *,
    description: str | None,
    sort_order: int | None,
    meta: RequestMeta,
) -> Attachment:
    att = get_or_404(db, attachment_id)
    spec = entities.get_spec(att.entity_type)
    host = entities.resolve_and_authorize(db, user, att.entity_type, att.entity_id, "write")
    if spec.write_guard is not None:
        spec.write_guard(host)

    before = {"description": att.description, "sort_order": att.sort_order}
    if description is not None:
        att.description = description.strip()
    if sort_order is not None:
        att.sort_order = sort_order
    db.flush()
    after = {"description": att.description, "sort_order": att.sort_order}
    if att.entity_type == "procedure":
        old_value, new_value = audit_service.compute_diff(before, after)
        if new_value:
            hooks.procedure_audit_update(
                db, host, att, meta=meta, old_value=old_value, new_value=new_value
            )
    return att


def delete_for(
    db: Session, user: User | None, attachment_id: str, *, meta: RequestMeta
) -> None:
    att = get_or_404(db, attachment_id)
    spec = entities.get_spec(att.entity_type)
    host = entities.resolve_and_authorize(db, user, att.entity_type, att.entity_id, "write")
    if spec.write_guard is not None:
        spec.write_guard(host)

    att.is_active = False
    att.deleted_at = utcnow()
    db.flush()
    if att.entity_type == "procedure":
        hooks.procedure_audit_delete(db, host, att, meta=meta)
```
5. 删除旧的 procedure 专属 `upload`/`update`/`delete`/`download`/`preview` 函数体（被 `*_for` 取代）。**保留** `copy_for_version`、`orphan_storage_paths`、`delete_orphan_path`、`get_or_404`、`_bytes_or_404`、`_resolve_mime`、`rows_for`、`list_attachments`。删除已无引用的 `_get_proc`/`_assert_editable`（逻辑迁入 hooks/entities）。

> ⚠️ 循环 import 风险：`attachment_entities` import `app.deps`，`app.deps` 不 import service，OK。`attachment_service` import `attachment_entities` + `attachment_hooks`，二者不 import service，OK。

- [ ] **Step 4: 运行新测试 + 既有附件单测**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/services/test_attachment_service_generic.py tests/unit/services/test_attachment_service.py -v`
Expected: PASS（既有 `test_attachment_service.py` 调用旧 `upload`/`update`/`delete`？若是，需把这些调用切到 `*_for("procedure",...)`——见 Step 5）

- [ ] **Step 5: 适配既有 procedure service 单测的调用面**

`tests/unit/services/test_attachment_service.py` 若调用已删除的 `svc.upload(db, proc_id, ...)`，逐处改 `svc.upload_for(db, None, "procedure", proc_id, ...)`（update/delete/download/preview 同理 `*_for`）。行为与断言不变（procedure perms None，user 传 None）。

Run: `cd backend && .venv/bin/python -m pytest tests/unit/services/test_attachment_service.py -v`
Expected: PASS

- [ ] **Step 6: 门禁 + 提交**

Run: `cd backend && .venv/bin/python -m pytest -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`

```bash
git add backend/app/services/attachment_service.py backend/tests/unit/services/
git commit -m "$(cat <<'EOF'
feat(attachment): generic service write path with per-entity hooks

upload/update/delete_for + list/download/preview_for：resolve+authorize →
write_guard 钩子 → 泛型核心 → procedure 审计钩子。procedure 草稿态/审计经钩子
完整保留；上限对所有实体统一适用。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: 端点 + schema + procedure 别名

新增 `/attachments` query/form 端点（`Depends(get_current_user)` + 动态 RBAC）；procedure 别名端点保持**无认证**转 `*_for("procedure",...)`。schema 增 entity_type/entity_id + procedure_id 兼容别名。

**Files:**
- Modify: `app/schemas/attachment.py`
- Modify: `app/routers/attachments.py`
- Test: `tests/integration/test_universal_attachments.py`（新增）

- [ ] **Step 1: 写失败集成测试（通用流 + 多态校验 + 跨租户）**

Create `tests/integration/test_universal_attachments.py`：

```python
"""通用附件端点集成测试（多态 + RBAC + 跨租户）。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

ATT = "/api/v1/attachments"


def _register(client: TestClient, company: str, email: str) -> str:
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "A"},
    ).json()["access_token"]


def _make_asset(client: TestClient, db: Session, token: str) -> str:
    """用 token 的 company 上下文建一个 asset，返回 id。"""
    from app import tenant
    from app.models.maintenance_asset import Asset
    from app.models.user import User
    from app import security

    company_id = security.decode_token(token)["company_id"]
    tenant.set_current_company_id(company_id)
    db.add(Asset(custom_id="A1", name="泵"))
    db.commit()
    aid = db.query(Asset).filter(Asset.company_id == company_id).one().id
    tenant.set_current_company_id(None)
    return aid


def test_generic_flow_on_asset(client: TestClient, db: Session, storage_tmp: Path) -> None:
    tok = _register(client, "Acme", "a@acme.com")
    h = {"Authorization": f"Bearer {tok}"}
    aid = _make_asset(client, db, tok)

    up = client.post(
        ATT, headers=h,
        data={"entity_type": "asset", "entity_id": aid, "description": "手册"},
        files={"file": ("手册.pdf", b"PDF", "application/pdf")},
    )
    assert up.status_code == 201, up.text
    att = up.json()
    assert att["entity_type"] == "asset" and att["entity_id"] == aid

    listed = client.get(ATT, headers=h, params={"entity_type": "asset", "entity_id": aid})
    assert [a["id"] for a in listed.json()] == [att["id"]]

    dl = client.get(f"{ATT}/{att['id']}/download", headers=h)
    assert dl.status_code == 200 and dl.content == b"PDF"

    upd = client.put(f"{ATT}/{att['id']}", headers=h, json={"description": "改"})
    assert upd.status_code == 200 and upd.json()["description"] == "改"

    dele = client.delete(f"{ATT}/{att['id']}", headers=h)
    assert dele.status_code == 204
    assert client.get(ATT, headers=h, params={"entity_type": "asset", "entity_id": aid}).json() == []


def test_unknown_entity_type_400(client: TestClient, db: Session, storage_tmp: Path) -> None:
    h = {"Authorization": f"Bearer {_register(client, 'Acme', 'a@acme.com')}"}
    r = client.post(
        ATT, headers=h,
        data={"entity_type": "ghost", "entity_id": "x"},
        files={"file": ("a.txt", b"x", "text/plain")},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "INVALID_ENTITY_TYPE"


def test_missing_host_404(client: TestClient, db: Session, storage_tmp: Path) -> None:
    h = {"Authorization": f"Bearer {_register(client, 'Acme', 'a@acme.com')}"}
    r = client.get(ATT, headers=h, params={"entity_type": "asset", "entity_id": "ghost"})
    assert r.status_code == 404


def test_cross_tenant_attachment_not_leaked(
    client: TestClient, db: Session, storage_tmp: Path
) -> None:
    tokA = _register(client, "CoA", "a@a.com")
    tokB = _register(client, "CoB", "b@b.com")
    hA = {"Authorization": f"Bearer {tokA}"}
    hB = {"Authorization": f"Bearer {tokB}"}
    aid = _make_asset(client, db, tokA)
    att = client.post(
        ATT, headers=hA,
        data={"entity_type": "asset", "entity_id": aid},
        files={"file": ("s.pdf", b"S", "application/pdf")},
    ).json()
    # B 列 A 的 asset 附件 → 404（宿主对 B 不可见）
    assert client.get(ATT, headers=hB, params={"entity_type": "asset", "entity_id": aid}).status_code == 404
    # B 直接下载 A 的附件 id → 404
    assert client.get(f"{ATT}/{att['id']}/download", headers=hB).status_code == 404


def test_unprivileged_write_403(client: TestClient, db: Session, storage_tmp: Path) -> None:
    """无 asset.edit 的成员上传 → 403。"""
    from app import tenant
    from app.models.user import User
    from app.services import invitation_service
    from sqlalchemy import select

    tok = _register(client, "Acme", "admin@acme.com")
    aid = _make_asset(client, db, tok)
    with tenant.bypass_tenant_scope():
        admin = db.execute(select(User).where(User.email == "admin@acme.com")).scalar_one()
    # 邀请一个无权限角色成员（role_id=None → 默认最小权限，无 asset.edit）
    _inv, raw = invitation_service.invite(
        db, company_id=admin.company_id, email="m@acme.com", role_id=None, invited_by=admin.id
    )
    db.commit()
    mtok = client.post(
        "/api/v1/auth/accept-invite",
        json={"token": raw, "name": "M", "password": "memberpw1"},
    ).json()["access_token"]
    hm = {"Authorization": f"Bearer {mtok}"}
    r = client.post(
        ATT, headers=hm,
        data={"entity_type": "asset", "entity_id": aid},
        files={"file": ("a.txt", b"x", "text/plain")},
    )
    assert r.status_code == 403
```

> 若 `role_id=None` 成员默认含 asset.edit（取决于 `effective_codes` 默认），改用显式只读角色（参考 `test_company_settings_api.py` 的成员构造），保证无 asset.edit。

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_universal_attachments.py -v`
Expected: FAIL（端点未定义 → 404/422）

- [ ] **Step 3: 更新 schema**

Replace `app/schemas/attachment.py`：

```python
"""附件 schema（通用多态 + procedure 兼容别名）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field


class AttachmentOut(BaseModel):
    """附件元数据（通用 list/upload 响应）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_type: str
    entity_id: str
    file_name: str
    mime_type: str
    size_bytes: int
    description: str
    sort_order: int
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def procedure_id(self) -> str:
        """兼容别名：前端 SOP 仍读 procedure_id（= entity_id）。"""
        return self.entity_id


class AttachmentUpdate(BaseModel):
    """修改附件元数据（仅 description / sort_order）。"""

    description: str | None = Field(default=None, max_length=2000)
    sort_order: int | None = Field(default=None, ge=0)
```

- [ ] **Step 4: 重写 router**

Replace `app/routers/attachments.py`：

```python
"""附件路由：通用 /attachments（认证 + 动态 RBAC）+ procedure 别名（无认证，兼容）。"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.deps import RequestMeta, get_current_user, get_db, get_request_meta
from app.models.user import User
from app.schemas.attachment import AttachmentOut, AttachmentUpdate
from app.services import attachment_service

router = APIRouter(prefix="/api/v1", tags=["attachments"])


def _content_disposition(disposition: str, file_name: str) -> str:
    ascii_fallback = file_name.encode("ascii", "ignore").decode() or "download"
    return f"{disposition}; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(file_name)}"


# --------------------------------------------------------------------------- #
# 通用 /attachments（认证 + 动态 RBAC）
# --------------------------------------------------------------------------- #
@router.get("/attachments", response_model=list[AttachmentOut])
def list_attachments_generic(
    entity_type: str = Query(...),
    entity_id: str = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AttachmentOut]:
    rows = attachment_service.list_for(db, user, entity_type, entity_id)
    return [AttachmentOut.model_validate(r) for r in rows]


@router.post(
    "/attachments", response_model=AttachmentOut, status_code=status.HTTP_201_CREATED
)
async def upload_attachment_generic(
    entity_type: str = Form(...),
    entity_id: str = Form(...),
    file: UploadFile = File(...),
    description: str = Form(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    meta: RequestMeta = Depends(get_request_meta),
) -> AttachmentOut:
    data = await file.read()
    att = attachment_service.upload_for(
        db, user, entity_type, entity_id, data, file.filename or "",
        content_type=file.content_type, description=description, meta=meta,
    )
    db.commit()
    return AttachmentOut.model_validate(att)


@router.get("/attachments/{attachment_id}/download")
def download_attachment(
    attachment_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    data, mime, file_name = attachment_service.download_for(db, user, attachment_id)
    return Response(
        content=data, media_type=mime,
        headers={"Content-Disposition": _content_disposition("attachment", file_name)},
    )


@router.get("/attachments/{attachment_id}/preview")
def preview_attachment(
    attachment_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    data, mime = attachment_service.preview_for(db, user, attachment_id)
    return Response(content=data, media_type=mime, headers={"Content-Disposition": "inline"})


@router.put("/attachments/{attachment_id}", response_model=AttachmentOut)
def update_attachment(
    attachment_id: str,
    payload: AttachmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    meta: RequestMeta = Depends(get_request_meta),
) -> AttachmentOut:
    att = attachment_service.update_for(
        db, user, attachment_id,
        description=payload.description, sort_order=payload.sort_order, meta=meta,
    )
    db.commit()
    return AttachmentOut.model_validate(att)


@router.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(
    attachment_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    attachment_service.delete_for(db, user, attachment_id, meta=meta)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- #
# procedure 兼容别名（无认证，行为同既有；前端 SOP 零改）
# --------------------------------------------------------------------------- #
@router.get("/procedures/{procedure_id}/attachments", response_model=list[AttachmentOut])
def list_procedure_attachments(
    procedure_id: str, db: Session = Depends(get_db)
) -> list[AttachmentOut]:
    rows = attachment_service.list_for(db, None, "procedure", procedure_id)
    return [AttachmentOut.model_validate(r) for r in rows]


@router.post(
    "/procedures/{procedure_id}/attachments",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_procedure_attachment(
    procedure_id: str,
    file: UploadFile = File(...),
    description: str = Form(default=""),
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> AttachmentOut:
    data = await file.read()
    att = attachment_service.upload_for(
        db, None, "procedure", procedure_id, data, file.filename or "",
        content_type=file.content_type, description=description, meta=meta,
    )
    db.commit()
    return AttachmentOut.model_validate(att)
```

> 注意：download/preview/PUT/DELETE 现在**全部需认证**。既有 `test_attachments.py` 的 download/preview/update/delete 调用**无 token** → 会变 401。**这是行为变更**，需处理——见 Step 5。

- [ ] **Step 5: 处理既有 procedure 集成测试的认证变更**

既有 `tests/integration/test_attachments.py` 对 `/attachments/{id}/download|preview` 和 PUT/DELETE 无 token。两种合规做法，**采用 (A)**：
- **(A) 为 procedure 附件的单资源操作保留无认证别名**：新增 procedure 专属单资源端点（无认证）`GET /procedures/{pid}/attachments/{aid}/download|preview`、`PUT/DELETE /procedures/{pid}/attachments/{aid}`，转 `*_for(db, None, ...)`；保持既有 `/attachments/{id}/*` 为通用认证端点。**但前端 SOP 现用的是 `/attachments/{id}/*`**——故改既有测试不可避免。

**结论（评审已认可"泛型核心+钩子"，此处取最小破坏）**：既有 `test_attachments.py` 改为带 token（首注册 super_admin），证明 procedure 经通用认证端点同样工作；procedure 列表/上传别名保持无认证（前端 SOP 真正依赖处）。即：
- `test_attachments.py` 顶部加 `_token`/headers helper，给 download/preview/PUT/DELETE 调用补 `headers=h`。list/upload 别名调用可保持无 token（别名无认证）。

更新 `tests/integration/test_attachments.py`：每个 test 开头
```python
def _h(client):
    tok = client.post("/api/v1/auth/register", json={
        "company_name": "Acme", "email": "a@acme.com", "password": "secret123", "name": "A"
    }).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}
```
并把 `client.get(f"/api/v1/attachments/{id}/download")` 等改为带 `headers=_h(client)`（同一 test 内复用一个 h）。

> ⚠️ procedure 经通用端点 download 时会带租户上下文，但 `resolve_and_authorize("procedure")` 走 `scoped=False`+bypass，且 perms None → 任意已认证用户可读 procedure 附件，保持裸奔语义。新建 procedure 在测试中 company_id 为 NULL，bypass 查询可命中。✔

- [ ] **Step 6: 运行通用 + 既有集成测试**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_universal_attachments.py tests/integration/test_attachments.py -v`
Expected: PASS

- [ ] **Step 7: 门禁 + 提交**

Run: `cd backend && .venv/bin/python -m pytest -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`

```bash
git add backend/app/routers/attachments.py backend/app/schemas/attachment.py backend/tests/integration/
git commit -m "$(cat <<'EOF'
feat(attachment): /attachments endpoints (auth + dynamic RBAC) + procedure alias

通用 query/form 端点动态 RBAC；procedure list/upload 别名保持无认证；
AttachmentOut 增 entity_type/entity_id + procedure_id 兼容别名。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: 删宿主清理（孤儿化扩展）

扩展 cleanup task：扫各 entity_type 的 active 附件，宿主不存在 → 软删该附件（后续既有 storage GC 物理删除）。bypass 跨租户。

**Files:**
- Modify: `app/services/attachment_service.py`（新增 `soft_delete_orphaned_by_host`）
- Modify: `app/tasks/cleanup_attachments.py`（run 内先孤儿化再 GC）
- Test: `tests/unit/tasks/test_cleanup_attachments_hosts.py`（新增）

- [ ] **Step 1: 写失败测试（宿主删 → 附件软删）**

Create `tests/unit/tasks/test_cleanup_attachments_hosts.py`：

```python
"""宿主不存在 → 附件孤儿化软删。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app import tenant
from app.models.attachment import Attachment
from app.models.maintenance_asset import Asset
from app.services import attachment_service as svc


def test_soft_delete_when_host_missing(db: Session) -> None:
    tenant.set_current_company_id("co-1")
    db.add(Asset(custom_id="A1", name="泵"))
    db.commit()
    aid = db.query(Asset).one().id
    db.add(Attachment(
        entity_type="asset", entity_id=aid, file_name="a.pdf",
        storage_path="x/a.pdf", mime_type="application/pdf", size_bytes=1,
    ))
    # 一个宿主已不存在的孤儿附件
    db.add(Attachment(
        entity_type="asset", entity_id="ghost", file_name="b.pdf",
        storage_path="x/b.pdf", mime_type="application/pdf", size_bytes=1,
    ))
    db.commit()
    tenant.set_current_company_id(None)

    n = svc.soft_delete_orphaned_by_host(db)
    db.commit()
    assert n == 1
    with tenant.bypass_tenant_scope():
        alive = {a.entity_id for a in db.query(Attachment).filter(Attachment.is_active.is_(True))}
    assert alive == {aid}
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/tasks/test_cleanup_attachments_hosts.py -v`
Expected: FAIL — `AttributeError: ... 'soft_delete_orphaned_by_host'`

- [ ] **Step 3: 实现孤儿化函数**

在 `app/services/attachment_service.py` 增（import `attachment_entities as entities` 已在 Task 3 加）：

```python
def soft_delete_orphaned_by_host(db: Session) -> int:
    """扫各 entity_type 的 active 附件，宿主不存在 → 软删附件。返回软删条数。bypass 跨租户。"""
    soft_deleted = 0
    with tenant.bypass_tenant_scope():
        rows = list(
            db.execute(select(Attachment).where(Attachment.is_active.is_(True))).scalars()
        )
        # 按 (entity_type, entity_id) 去重存在性查询
        existing: dict[tuple[str, str], bool] = {}
        for att in rows:
            spec = entities.ENTITY_REGISTRY.get(att.entity_type)
            if spec is None:
                continue
            key = (att.entity_type, att.entity_id)
            if key not in existing:
                host = db.execute(
                    select(spec.model.id).where(
                        spec.model.id == att.entity_id, spec.model.is_active.is_(True)
                    )
                ).scalar_one_or_none()
                existing[key] = host is not None
            if not existing[key]:
                att.is_active = False
                att.deleted_at = utcnow()
                soft_deleted += 1
        db.flush()
    return soft_deleted
```

- [ ] **Step 4: task run 内接入（孤儿化 → GC）**

`app/tasks/cleanup_attachments.py` 的 `run` 在取 orphan paths 前先孤儿化：

```python
    started = now or utcnow()
    retention = retention_days if retention_days is not None else settings.attachment_retention_days
    orphaned = attachment_service.soft_delete_orphaned_by_host(db)
    if commit and orphaned:
        db.commit()
    paths = attachment_service.orphan_storage_paths(db, retention_days=retention, now=started)
```
并在 summary 加 `"orphaned": orphaned`：
```python
    summary = {"scanned": len(paths), "deleted": deleted, "errors": errors, "orphaned": orphaned}
```

- [ ] **Step 5: 运行新测试 + 既有清理测试**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/tasks/test_cleanup_attachments_hosts.py tests/unit/services/test_attachment_service.py -k "orphan or cleanup or clean" -v`
并跑既有 cleanup task 测试（若存在 `tests/unit/tasks/test_cleanup_attachments*.py`）。
Expected: PASS（既有 summary 断言若严格等于 dict，需同步加 `orphaned` 键）

- [ ] **Step 6: 门禁 + 提交**

Run: `cd backend && .venv/bin/python -m pytest -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`

```bash
git add backend/app/services/attachment_service.py backend/app/tasks/cleanup_attachments.py backend/tests
git commit -m "$(cat <<'EOF'
feat(attachment): orphan attachments by missing host in cleanup task

soft_delete_orphaned_by_host 扫各 entity_type，宿主不存在则软删附件（bypass
跨租户，去重存在性查询）；既有 storage GC 物理删除逻辑不变。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: alembic 迁移（原地泛化，末置）

把生产库 `tb_procedure_attachment` 原地泛化为 `tb_attachment`，现有 procedure 附件无损平移。SQLite 测试用 `create_all` 不依赖本迁移；本迁移单独验 up/down/up + 与模型零漂移 + MySQL 实测。

**Files:**
- Create: `alembic/versions/<rev>_universal_attachment.py`
- Test: 手动 alembic 验证（命令见下）

- [ ] **Step 1: 确认迁移链头**

Run: `cd backend && .venv/bin/python -m alembic heads`
Expected: 单一 head = `platform_account_config`（若非，用实际 head 作 down_revision）

- [ ] **Step 2: 写迁移**

Create `alembic/versions/<rev>_universal_attachment.py`（`<rev>` 取生成的 revision id；用 `op.batch_alter_table` 兼容 SQLite/MySQL）：

```python
"""universal attachment: generalize tb_procedure_attachment -> tb_attachment

Revision ID: universal_attachment
Revises: platform_account_config
Create Date: 2026-06-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "universal_attachment"
down_revision = "platform_account_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("tb_procedure_attachment", "tb_attachment")
    with op.batch_alter_table("tb_attachment", schema=None) as batch:
        batch.add_column(
            sa.Column(
                "entity_type", sa.String(length=32), nullable=False, server_default="procedure"
            )
        )
        batch.add_column(sa.Column("entity_id", sa.String(length=36), nullable=True))
    op.execute("UPDATE tb_attachment SET entity_id = procedure_id")
    with op.batch_alter_table("tb_attachment", schema=None) as batch:
        batch.alter_column("entity_id", existing_type=sa.String(length=36), nullable=False)
        # drop 旧 FK + 旧列 + 旧索引（batch 重建表，自动丢弃对 tb_procedure 的 FK）
        batch.drop_index("ix_tb_procedure_attachment_procedure_id")
        batch.drop_index("ix_tb_procedure_attachment_storage_path")
        batch.drop_column("procedure_id")
        batch.create_index("ix_tb_attachment_entity", ["entity_type", "entity_id"])
        batch.create_index("ix_tb_attachment_storage_path", ["storage_path"])
        # 去掉 server_default（应用层负责写入 entity_type）
        batch.alter_column("entity_type", existing_type=sa.String(length=32), server_default=None)


def downgrade() -> None:
    # 非 procedure 行无法回填 procedure_id（FK→tb_procedure），删除之（评审定：丢弃）
    op.execute("DELETE FROM tb_attachment WHERE entity_type <> 'procedure'")
    with op.batch_alter_table("tb_attachment", schema=None) as batch:
        batch.add_column(sa.Column("procedure_id", sa.String(length=36), nullable=True))
    op.execute("UPDATE tb_attachment SET procedure_id = entity_id")
    with op.batch_alter_table("tb_attachment", schema=None) as batch:
        batch.alter_column("procedure_id", existing_type=sa.String(length=36), nullable=False)
        batch.drop_index("ix_tb_attachment_entity")
        batch.drop_index("ix_tb_attachment_storage_path")
        batch.drop_column("entity_id")
        batch.drop_column("entity_type")
        batch.create_index("ix_tb_procedure_attachment_procedure_id", ["procedure_id"])
        batch.create_index("ix_tb_procedure_attachment_storage_path", ["storage_path"])
        batch.create_foreign_key(
            "fk_tb_procedure_attachment_procedure_id",
            "tb_procedure", ["procedure_id"], ["id"], ondelete="RESTRICT",
        )
    op.rename_table("tb_attachment", "tb_procedure_attachment")
```

- [ ] **Step 3: 验 up / down / up（SQLite dev 库或临时库）**

Run（在临时 sqlite 或 dev 库）：
```bash
cd backend
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m alembic downgrade -1
.venv/bin/python -m alembic upgrade head
```
Expected: 三步均无错误。

- [ ] **Step 4: 验模型零漂移（autogenerate 空 diff）**

Run: `cd backend && .venv/bin/python -m alembic revision --autogenerate -m _drift_check`
Expected: 生成的迁移 `upgrade()` 体为空（仅 pass）。**确认后删除该探针文件**，不提交。
> 若有 diff（如索引名/列类型不一致），按 diff 修迁移或模型直至空。

- [ ] **Step 5: MySQL 实测（生产方言）**

按 `batch-word-parsing-mvp` 记忆的"集成项手动验证"惯例，在本地 MySQL 跑 up/down/up + 一条 procedure 附件平移校验：
```sql
SELECT entity_type, entity_id FROM tb_attachment LIMIT 5;  -- entity_type='procedure', entity_id=原 procedure_id
```
Expected: rename + 列变更在 MySQL 成功；现有 procedure 附件 entity_type='procedure'、entity_id 正确。
> 若 MySQL 不可用，在报告中明确标注"MySQL 实测待手动验证"（同 ① 惯例）。

- [ ] **Step 6: 全量收口 + 提交**

Run: `cd backend && .venv/bin/python -m pytest -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: all green

```bash
git add backend/alembic/versions/
git commit -m "$(cat <<'EOF'
feat(attachment): alembic migration generalizing tb_procedure_attachment

原地泛化 tb_procedure_attachment→tb_attachment：rename + entity_type/entity_id
+ drop tb_procedure FK + 重建索引；现有 procedure 附件无损平移。up/down/up 与
模型零漂移验证通过。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review（plan 对照 spec）

**Spec coverage：**
- §4.1 多态模型 → Task 1 ✔
- §4.2 迁移 → Task 6 ✔
- §5 registry + resolve_and_authorize（400/404/403、procedure None、scoped）→ Task 2 ✔
- §6.1 端点 → Task 4 ✔
- §6.2 procedure 别名 + procedure_id 兼容 → Task 4（schema computed_field + 无认证别名）✔
- §6.3 写路径钩子 → Task 3 ✔
- §2.3 泛型核心 + 钩子（editability/audit/copy/limits/preview）→ Task 1（copy/limits/preview 保留）+ Task 3（钩子）✔
- §7 孤儿清理扩展 → Task 5 ✔
- §8 错误处理 → Task 2/3/4 测试覆盖 ✔
- §9 测试策略（通用流/多态校验/兼容不破/跨租户/孤儿/迁移）→ Task 1-6 测试 ✔
- §12 决策项：request.create（Task 2 registry）✔、钩子架构 ✔、非 procedure MVP 无审计（Task 3 仅 procedure 审计）✔、downgrade 丢弃非 procedure（Task 6 DELETE）✔、上限统一（Task 3）✔

**Placeholder 扫描：** 无 TODO/TBD；每步含完整代码或精确命令。两处显式标注"按实际微调"（Task 2 `_company_user` 字段、Task 4 成员权限角色）——因依赖未逐字读取的 Company/Role/User/effective_codes 细节，留给执行 subagent 按真实模型对齐，非逻辑占位。

**Type consistency：** `Attachment`(entity_type/entity_id) 全 task 一致；service 函数名 `list_for/download_for/preview_for/upload_for/update_for/delete_for` + 保留 `rows_for/list_attachments/copy_for_version/get_or_404/orphan_storage_paths/delete_orphan_path` 一致；`resolve_and_authorize(db,user,entity_type,entity_id,action)`、`EntitySpec(model,view_perm,edit_perm,scoped,write_guard)`、`get_spec`、`soft_delete_orphaned_by_host` 跨 task 引用一致。

**执行风险提示（给执行者）：**
1. Task 4 Step 5 是行为变更点（单资源端点改需认证）——既有 `test_attachments.py` 须补 token；这是评审认可的最小破坏，执行时确认前端 SOP 仅依赖 list/upload（保持无认证别名）。
2. Task 2/3/4 的 user/role/company 构造须对齐真实模型必填字段与 `effective_codes` 默认权限，首次跑测可能需按报错微调 helper。
3. Task 6 MySQL 实测若环境缺失，按 ① 惯例报告标注待验。
