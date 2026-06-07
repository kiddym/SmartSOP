# 工单执行态 UPLOAD/PHOTO/SIGNATURE 附件上传实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让执行人在工单执行态对 UPLOAD/PHOTO/SIGNATURE 步骤上传文件/选图/手写签名，落为该执行步骤的附件，必填步骤完成时硬校验附件存在。

**Architecture:** 复用通用 Attachment 多态基础设施——给 `WorkOrderStepResult` 加 SoftDeleteMixin（满足附件宿主要求）、注册 `work_order_step_result` 到 ENTITY_REGISTRY（复用 `/api/v1/attachments`，零新端点）、执行服务完成校验加附件存在分支、ExecutionView 暴露 attachment_count；前端 ExecutionTab 加三类控件（UPLOAD/PHOTO=el-upload，SIGNATURE=canvas 画板），SOP 编辑器给三类加"必填"开关。详见 `docs/superpowers/specs/2026-06-07-execution-attachments-design.md`。

**Tech Stack:** 后端 FastAPI + SQLAlchemy + Alembic（venv `backend/.venv`，当前 alembic 单 head `custom_field`）；前端 Vue3 + TS + Element Plus + vitest。

**全局门禁（每个 Task 提交前满足）：**
- 后端：`cd backend && .venv/bin/python -m pytest <相关测试> -q` 绿；改模型/迁移则 `.venv/bin/alembic heads` 单 head + 重放（`rm -f /tmp/ea.db && DATABASE_URL="sqlite:////tmp/ea.db" .venv/bin/alembic upgrade head && downgrade -1 && upgrade head && rm -f /tmp/ea.db`）；`.venv/bin/python -c "import app.main"`；`.venv/bin/ruff check app tests`；`.venv/bin/ruff format --check app`；`.venv/bin/mypy app`。
- 前端：`cd frontend && npx vue-tsc --noEmit`；`npx eslint <改动文件>`；`npx vitest run <相关 spec>`。
- 净室红线：全新原创，不复制第三方代码/命名。

---

## 文件结构（先锁定边界）

**后端 修改：**
- `app/models/work_order_step_result.py` — `WorkOrderStepResult` 加 SoftDeleteMixin
- `app/services/attachment_entities.py` — ENTITY_REGISTRY 注册 `work_order_step_result`
- `app/services/attachment_service.py` — 加 `count_active` / `count_active_by_entity_ids` 计数公开函数
- `app/services/work_order_execution_service.py` — 完成校验加附件分支；execution_view 填 attachment_count；list_step_results 加 is_active 过滤
- `app/schemas/work_order.py` — `StepResultRead` 加 `attachment_count`

**后端 新建：**
- `alembic/versions/20260607_0019_step_result_soft_delete.py`
- `tests/unit/test_step_result_attachments.py`（注册/计数/完成校验单测）
- `tests/integration/test_step_attachments_api.py`（端点 round-trip + 权限/租户）

**前端 修改：**
- `src/components/editor/StepFormFields.vue` — UPLOAD/PHOTO/SIGNATURE 加"必填(需上传)"开关
- `src/components/workorder/ExecutionTab.vue` — 三类控件 + 附件列表 + 只读
- `src/types/workOrder.ts` — StepResultRead 加 attachment_count

**前端 新建：**
- `src/components/workorder/SignaturePad.vue` — canvas 签名画板
- `tests/unit/ExecutionTabAttachments.spec.ts`、`tests/unit/SignaturePad.spec.ts`

> 复用既有 `src/api/attachments.ts` 的 `listEntityAttachments`/`uploadEntityAttachment`/`deleteAttachment`（已存在，无需新增）。

---

## Phase 1：宿主软删 + 迁移

### Task 1：WorkOrderStepResult 加 SoftDeleteMixin + 迁移 + 查询过滤

**Files:**
- Modify: `backend/app/models/work_order_step_result.py`
- Create: `backend/alembic/versions/20260607_0019_step_result_soft_delete.py`
- Modify: `backend/app/services/work_order_execution_service.py`（`list_step_results` 加 is_active 过滤）
- Test: `backend/tests/unit/test_step_result_attachments.py`（本 Task 起逐步追加）

- [ ] **Step 1: 写失败测试** `backend/tests/unit/test_step_result_attachments.py`

```python
"""执行态步骤附件：宿主软删 + 注册 + 计数 + 完成校验。"""

from app.models.work_order_step_result import WorkOrderStepResult


def test_step_result_has_soft_delete_columns():
    # SoftDeleteMixin 提供 is_active / deleted_at
    cols = set(WorkOrderStepResult.__table__.columns.keys())
    assert "is_active" in cols
    assert "deleted_at" in cols
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_step_result_attachments.py -q`
Expected: FAIL（is_active 不在列集合）

- [ ] **Step 3: 模型加 SoftDeleteMixin** `backend/app/models/work_order_step_result.py`

把 import 行与类声明改为含 SoftDeleteMixin：

```python
from app.models.base import DATETIME6, Base, SoftDeleteMixin, TenantMixin, TimestampMixin, UUIDMixin


class WorkOrderStepResult(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_work_order_step_result"
```

（其余字段不动。）

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_step_result_attachments.py -q`
Expected: PASS

- [ ] **Step 5: 写迁移** `backend/alembic/versions/20260607_0019_step_result_soft_delete.py`

先 `cd backend && .venv/bin/alembic heads` 确认 head 仍是 `custom_field`（若不是，把 down_revision 改成真实 head）。

```python
"""work_order_step_result soft delete columns

Revision ID: step_result_soft_delete
Revises: custom_field
Create Date: 2026-06-07

手工撰写（MySQL 生产 + SQLite 开发/测试）。给 tb_work_order_step_result 加
is_active / deleted_at（SoftDeleteMixin），使其可作为通用 Attachment 宿主。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.base import DATETIME6

revision: str = "step_result_soft_delete"
down_revision: str | Sequence[str] | None = "custom_field"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tb_work_order_step_result") as batch_op:
        batch_op.add_column(
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.add_column(sa.Column("deleted_at", DATETIME6, nullable=True))
        batch_op.create_index(
            "ix_tb_work_order_step_result_is_active", ["is_active"]
        )


def downgrade() -> None:
    with op.batch_alter_table("tb_work_order_step_result") as batch_op:
        batch_op.drop_index("ix_tb_work_order_step_result_is_active")
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("is_active")
```

- [ ] **Step 6: 校验单 head + 重放**

Run:
```
cd backend && .venv/bin/alembic heads
rm -f /tmp/ea.db && DATABASE_URL="sqlite:////tmp/ea.db" .venv/bin/alembic upgrade head && DATABASE_URL="sqlite:////tmp/ea.db" .venv/bin/alembic downgrade -1 && DATABASE_URL="sqlite:////tmp/ea.db" .venv/bin/alembic upgrade head && rm -f /tmp/ea.db
```
Expected: 单 head `step_result_soft_delete`；重放无错。

- [ ] **Step 7: list_step_results 加 is_active 过滤** `backend/app/services/work_order_execution_service.py`

把 `list_step_results` 的查询加 `is_active` 条件：

```python
def list_step_results(db: Session, work_order_id: str) -> list[WorkOrderStepResult]:
    return list(
        db.execute(
            select(WorkOrderStepResult)
            .where(
                WorkOrderStepResult.work_order_id == work_order_id,
                WorkOrderStepResult.is_active.is_(True),
            )
            .order_by(WorkOrderStepResult.node_sort_order, WorkOrderStepResult.id)
        )
        .scalars()
        .all()
    )
```

- [ ] **Step 8: 跑执行回归 + 门禁 + 提交**

Run: `cd backend && .venv/bin/python -m pytest tests/ -k "execution or step_result or work_order" -q`
Expected: PASS（既有执行测试不破）
门禁：`.venv/bin/ruff check app tests && .venv/bin/ruff format app tests && .venv/bin/mypy app && .venv/bin/python -c "import app.main"`

```bash
git add backend/app/models/work_order_step_result.py backend/alembic/versions/20260607_0019_step_result_soft_delete.py backend/app/services/work_order_execution_service.py backend/tests/unit/test_step_result_attachments.py
git commit -m "$(cat <<'EOF'
feat(ea): WorkOrderStepResult 软删列 + 迁移（备执行态附件宿主）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 2：附件注册 + 计数

### Task 2：注册 work_order_step_result + attachment 计数公开函数

**Files:**
- Modify: `backend/app/services/attachment_entities.py`
- Modify: `backend/app/services/attachment_service.py`
- Test: `backend/tests/unit/test_step_result_attachments.py`（追加）

- [ ] **Step 1: 写失败测试**（追加到 `tests/unit/test_step_result_attachments.py`）

```python
def test_registry_has_step_result():
    from app import permissions
    from app.services.attachment_entities import ENTITY_REGISTRY

    spec = ENTITY_REGISTRY["work_order_step_result"]
    assert spec.model is WorkOrderStepResult
    assert spec.scoped is True
    # 上传/删除步骤附件 = 执行动作，写权限用 WORK_ORDER_EXECUTE
    assert spec.edit_perm == permissions.WORK_ORDER_EXECUTE
    assert spec.view_perm == permissions.WORK_ORDER_VIEW


def test_count_active_helpers(db):
    from app.models.attachment import Attachment
    from app.services import attachment_service

    db.add(Attachment(entity_type="work_order_step_result", entity_id="sr1",
                       file_name="a.png", mime_type="image/png", file_type="image",
                       storage_path="x/a.png", size_bytes=1, company_id="c1"))
    db.add(Attachment(entity_type="work_order_step_result", entity_id="sr1",
                       file_name="b.png", mime_type="image/png", file_type="image",
                       storage_path="x/b.png", size_bytes=1, company_id="c1"))
    db.commit()
    assert attachment_service.count_active(db, "work_order_step_result", "sr1") == 2
    assert attachment_service.count_active(db, "work_order_step_result", "sr2") == 0
    m = attachment_service.count_active_by_entity_ids(db, "work_order_step_result", ["sr1", "sr2"])
    assert m == {"sr1": 2}
```

> 注：`db` fixture 见既有 `tests/conftest.py`（提供 Session）。`Attachment` 构造参数以真实模型字段为准——先 `grep -n "Mapped" app/models/attachment.py` 核对 file_name/mime_type/file_type/storage_path/size_bytes/company_id 是否齐全并按需补必填字段。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_step_result_attachments.py -q`
Expected: FAIL（KeyError work_order_step_result / count_active 不存在）

- [ ] **Step 3: 注册 ENTITY_REGISTRY** `backend/app/services/attachment_entities.py`

import 加：`from app.models.work_order_step_result import WorkOrderStepResult`（按字母序/既有 import 风格）。在 ENTITY_REGISTRY 字典末尾（`request` 后）加：

```python
    "work_order_step_result": EntitySpec(
        # 步骤附件 = 执行动作：读=work_order.view，写=work_order.execute（与步骤完成同权，
        # 避免有执行权无编辑权的执行人被挡）。
        WorkOrderStepResult,
        permissions.WORK_ORDER_VIEW,
        permissions.WORK_ORDER_EXECUTE,
        scoped=True,
    ),
```

- [ ] **Step 4: 加计数公开函数** `backend/app/services/attachment_service.py`

确认文件顶部已 `from sqlalchemy import func`（无则加；既有已 import select）。在 `_active_rows` 附近加：

```python
def count_active(db: Session, entity_type: str, entity_id: str) -> int:
    """某宿主实体下 active 附件数（内部用，不做权限检查；调用方须已授权）。"""
    return int(
        db.execute(
            select(func.count())
            .select_from(Attachment)
            .where(
                Attachment.entity_type == entity_type,
                Attachment.entity_id == entity_id,
                Attachment.is_active.is_(True),
            )
        ).scalar_one()
    )


def count_active_by_entity_ids(
    db: Session, entity_type: str, entity_ids: list[str]
) -> dict[str, int]:
    """批量：entity_id → active 附件数（仅返回有附件的 id）。"""
    if not entity_ids:
        return {}
    rows = db.execute(
        select(Attachment.entity_id, func.count())
        .where(
            Attachment.entity_type == entity_type,
            Attachment.entity_id.in_(entity_ids),
            Attachment.is_active.is_(True),
        )
        .group_by(Attachment.entity_id)
    ).all()
    return {eid: int(n) for eid, n in rows}
```

- [ ] **Step 5: 跑测试 + 门禁 + 提交**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_step_result_attachments.py -q` → PASS
门禁：`.venv/bin/ruff check app tests && .venv/bin/ruff format app tests && .venv/bin/mypy app && .venv/bin/python -c "import app.main"`

```bash
git add backend/app/services/attachment_entities.py backend/app/services/attachment_service.py backend/tests/unit/test_step_result_attachments.py
git commit -m "$(cat <<'EOF'
feat(ea): 注册 work_order_step_result 附件实体 + active 附件计数函数

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 3：附件端点 round-trip + 权限/租户集成测试

**Files:**
- Test: `backend/tests/integration/test_step_attachments_api.py`

- [ ] **Step 1: 写集成测试** `backend/tests/integration/test_step_attachments_api.py`

复用既有 register 模式 + db 级造程序。**先确认**：`/api/v1/auth/register` 返回 access_token 且首注册用户为有 work_order.* 全权限的 admin；`exe.attach_procedure` 生成 step results。

```python
from sqlalchemy import select

from app import tenant
from app.models.node import ProcedureNode
from app.models.procedure import Procedure
from app.models.user import User
from app.schemas.work_order import WorkOrderCreate, WorkOrderTransition
from app.models.work_order_status import WorkOrderStatus
from app.services import work_order_execution_service as exe
from app.services import work_order_service as wos


def _admin(client, company="Acme", email="a@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email, "password": "secret123", "name": "A"}).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _company_id(db, email):
    with tenant.bypass_tenant_scope():
        return db.execute(select(User).where(User.email == email)).scalar_one().company_id


def _wo_with_step(db, company_id):
    """造 PUBLISHED 程序(1 step) + 工单挂接 → 返回 (work_order, step_result_id)。"""
    p = Procedure(procedure_group_id="g1", folder_id="f1", code="SOP-1", name="P", version=1,
                  level_of_use="reference", status="PUBLISHED", company_id=company_id)
    db.add(p)
    db.flush()
    step = ProcedureNode(procedure_id=p.id, sort_order=1, heading_level=None, kind="step",
                         body="上传图纸", code="S1",
                         input_schema={"type": "UPLOAD", "required": True}, company_id=company_id)
    db.add(step)
    db.commit()
    wo = wos.create_work_order(db, WorkOrderCreate(title="T"), company_id, actor_user_id=None)
    exe.attach_procedure(db, wo, p.id, company_id, actor_user_id=None)
    sr_id = exe.list_step_results(db, wo.id)[0].id
    return wo, sr_id


def test_upload_list_delete_step_attachment(client, db):
    h = _h(_admin(client))
    cid = _company_id(db, "a@acme.com")
    with tenant.bypass_tenant_scope():
        _wo, sr_id = _wo_with_step(db, cid)
    # 上传
    r = client.post("/api/v1/attachments", headers=h, files={"file": ("x.png", b"\x89PNG", "image/png")},
                    data={"entity_type": "work_order_step_result", "entity_id": sr_id})
    assert r.status_code == 201, r.text
    att_id = r.json()["id"]
    # 列出
    lst = client.get(f"/api/v1/attachments?entity_type=work_order_step_result&entity_id={sr_id}", headers=h).json()
    assert [a["id"] for a in lst] == [att_id]
    # 删除
    assert client.delete(f"/api/v1/attachments/{att_id}", headers=h).status_code == 204
    assert client.get(f"/api/v1/attachments?entity_type=work_order_step_result&entity_id={sr_id}", headers=h).json() == []


def test_step_attachment_tenant_isolated(client, db):
    hA = _h(_admin(client, "CoA", "a@a.com"))
    hB = _h(_admin(client, "CoB", "b@b.com"))
    cidA = _company_id(db, "a@a.com")
    with tenant.bypass_tenant_scope():
        _wo, sr_id = _wo_with_step(db, cidA)
    client.post("/api/v1/attachments", headers=hA, files={"file": ("x.png", b"\x89PNG", "image/png")},
                data={"entity_type": "work_order_step_result", "entity_id": sr_id})
    # B 公司无法看到 A 的步骤附件（宿主跨租户 → 解析失败 404/403）
    rb = client.get(f"/api/v1/attachments?entity_type=work_order_step_result&entity_id={sr_id}", headers=hB)
    assert rb.status_code in (403, 404) or rb.json() == []
```

> 注：`files=`/`data=` 是 TestClient 的 multipart 写法。若 `_wo_with_step` 里 `wos.create_work_order` / `exe.attach_procedure` 的真实签名与此不符，按真实签名调整（参考 `tests/test_work_order_execution_service.py` 的用法）。租户隔离断言放宽到"403/404 或空列表"以兼容 `list_for` 的实际越权表现——实现后据真实行为收紧为单一断言。

- [ ] **Step 2: 跑测试 + 门禁 + 提交**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_step_attachments_api.py -q` → PASS
门禁：`.venv/bin/ruff check app tests && .venv/bin/ruff format app tests && .venv/bin/mypy app`

```bash
git add backend/tests/integration/test_step_attachments_api.py
git commit -m "$(cat <<'EOF'
test(ea): 执行态步骤附件端点 round-trip + 租户隔离

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 3：完成校验 + attachment_count 读出

### Task 4：必填附件步骤完成硬校验 + ExecutionView 暴露 attachment_count

**Files:**
- Modify: `backend/app/services/work_order_execution_service.py`
- Modify: `backend/app/schemas/work_order.py`
- Test: `backend/tests/unit/test_step_result_attachments.py`（追加）

- [ ] **Step 1: 写失败测试**（追加）

```python
def test_required_upload_step_blocks_done_without_attachment(db):
    import pytest
    from fastapi import HTTPException
    from app.schemas.work_order import StepResultUpdate
    from app.services import work_order_execution_service as exe
    from app.services import work_order_service as wos
    from app.schemas.work_order import WorkOrderCreate, WorkOrderTransition
    from app.models.procedure import Procedure
    from app.models.node import ProcedureNode
    from app.models.company import Company

    c = Company(name="ea", slug="ea")
    db.add(c)
    db.commit()
    from app import tenant
    tenant.set_current_company_id(c.id)
    p = Procedure(procedure_group_id="g", folder_id="f", code="S", name="P", version=1,
                  level_of_use="reference", status="PUBLISHED", company_id=c.id)
    db.add(p)
    db.flush()
    db.add(ProcedureNode(procedure_id=p.id, sort_order=1, heading_level=None, kind="step",
                         body="传图", code="S1",
                         input_schema={"type": "UPLOAD", "required": True}, company_id=c.id))
    db.commit()
    wo = wos.create_work_order(db, WorkOrderCreate(title="T"), c.id, actor_user_id=None)
    exe.attach_procedure(db, wo, p.id, c.id, actor_user_id=None)
    wos.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.IN_PROGRESS), c.id, actor_user_id=None)
    sr = exe.list_step_results(db, wo.id)[0]
    # 无附件 → is_done=True 应 422
    with pytest.raises(HTTPException) as ei:
        exe.update_step(db, wo, sr, StepResultUpdate(is_done=True), c.id, actor_user_id=None)
    assert ei.value.status_code == 422
    # 加一个该步骤附件后可完成
    from app.models.attachment import Attachment
    db.add(Attachment(entity_type="work_order_step_result", entity_id=sr.id, file_name="a.png",
                      mime_type="image/png", file_type="image", storage_path="x/a.png",
                      size_bytes=1, company_id=c.id))
    db.commit()
    exe.update_step(db, wo, sr, StepResultUpdate(is_done=True), c.id, actor_user_id=None)
    assert sr.is_done is True
```

> 注：`transition` 把工单转 IN_PROGRESS（update_step 前置要求）。若 OPEN→IN_PROGRESS 非法或需中间态，参考 `tests/test_work_order_execution_service.py` 既有完成流程的转移序列照搬。`Company` 必填字段（name/slug）以真实模型为准。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_step_result_attachments.py -k required_upload -q`
Expected: FAIL（当前无附件也能完成）

- [ ] **Step 3: 完成校验加附件分支** `backend/app/services/work_order_execution_service.py`

顶部加 import：`from app.services import attachment_service`。加常量与辅助（放 `_required_fields` 附近）：

```python
ATTACHMENT_STEP_TYPES = frozenset({"UPLOAD", "PHOTO", "SIGNATURE"})


def _requires_attachment(db: Session, node_id: str) -> bool:
    node = db.get(ProcedureNode, node_id)
    if node is None:
        return False
    schema = node.input_schema or {}
    return str(schema.get("type", "")).upper() in ATTACHMENT_STEP_TYPES and bool(
        schema.get("required")
    )
```

在 `update_step` 的 `is_done` 为真分支内，**既有 `missing` 校验之后**、`sr.is_done = True` 之前加：

```python
            if _requires_attachment(db, sr.node_id):
                count = attachment_service.count_active(db, "work_order_step_result", sr.id)
                if count == 0:
                    raise bad_request(
                        "STEP_ATTACHMENT_REQUIRED", "本步骤需上传附件后才能完成"
                    )
```

- [ ] **Step 4: execution_view 填 attachment_count** 同文件 `execution_view`

在构造 `steps` 前批量取计数，并在每个 step dict 加字段：

```python
    sr_rows = list_step_results(db, wo.id)
    counts = attachment_service.count_active_by_entity_ids(
        db, "work_order_step_result", [r.id for r in sr_rows]
    )
    steps = []
    for sr in sr_rows:
        steps.append(
            {
                "id": sr.id,
                "node_id": sr.node_id,
                "node_code": sr.node_code,
                "node_sort_order": sr.node_sort_order,
                "input_schema": schema_by_id.get(sr.node_id, {}),
                "response": sr.response or {},
                "is_done": sr.is_done,
                "done_by_user_id": sr.done_by_user_id,
                "done_at": sr.done_at,
                "notes": sr.notes,
                "attachment_count": counts.get(sr.id, 0),
            }
        )
```

（删除原先 `for sr in list_step_results(db, wo.id):` 那行，改用上面的 `sr_rows`。）

- [ ] **Step 5: schema 加字段** `backend/app/schemas/work_order.py` 的 `StepResultRead` 加：

```python
    attachment_count: int = 0
```

- [ ] **Step 6: 跑测试 + 回归 + 门禁 + 提交**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_step_result_attachments.py tests/ -k "execution or step_result" -q` → PASS
门禁：`.venv/bin/ruff check app tests && .venv/bin/ruff format app tests && .venv/bin/mypy app && .venv/bin/python -c "import app.main"`

```bash
git add backend/app/services/work_order_execution_service.py backend/app/schemas/work_order.py backend/tests/unit/test_step_result_attachments.py
git commit -m "$(cat <<'EOF'
feat(ea): 必填附件步骤完成硬校验 + ExecutionView 暴露 attachment_count

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 4：前端编辑器开关 + UPLOAD/PHOTO 控件

### Task 5：SOP 编辑器给三类加"必填(需上传)"开关

**Files:**
- Modify: `frontend/src/components/editor/StepFormFields.vue`

- [ ] **Step 1: 加开关** 在 `StepFormFields.vue` 的 UPLOAD / SIGNATURE / PHOTO 三个 `<template v-else-if>` 块内各加一个必填开关（绑定 `required` 布尔，与后端 `_requires_attachment` 读 `schema.get("required")` truthy 对齐）：

UPLOAD 块（在 accept/max_count 后）加：
```html
      <el-form-item label="必填（需上传附件）">
        <el-switch :model-value="bool('required')" :disabled="readonly" @change="(v: string | number | boolean) => set('required', !!v)" />
      </el-form-item>
```
SIGNATURE 块（在 hint 后）、PHOTO 块（在 max_count 后）各加同一段 `el-form-item`（文案同上）。

> `bool()` / `set()` 辅助函数文件已有；`required` 作为布尔存入 input_schema，不与值类型步骤的 `required: list` 冲突（不同步骤类型）。

- [ ] **Step 2: gate + 提交**

Run: `cd frontend && npx vue-tsc --noEmit && npx eslint src/components/editor/StepFormFields.vue`
（若有该组件既有 spec：`npx vitest run <StepFormFields spec>` 不破。）

```bash
git add frontend/src/components/editor/StepFormFields.vue
git commit -m "$(cat <<'EOF'
feat(ea): SOP 编辑器 UPLOAD/PHOTO/SIGNATURE 加必填开关

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 6：ExecutionTab UPLOAD/PHOTO 控件 + 附件列表

**Files:**
- Modify: `frontend/src/components/workorder/ExecutionTab.vue`, `frontend/src/types/workOrder.ts`
- Test: `frontend/tests/unit/ExecutionTabAttachments.spec.ts`

- [ ] **Step 1: 类型加字段** `frontend/src/types/workOrder.ts` 的 `StepResultRead` 加：

```ts
  attachment_count: number
```

- [ ] **Step 2: 写失败测试** `frontend/tests/unit/ExecutionTabAttachments.spec.ts`

mock `@/api/workOrders`（getExecution 返回含一个 UPLOAD step 的 ExecutionView）、`@/api/attachments`（listEntityAttachments/uploadEntityAttachment/deleteAttachment）、`@/api/users`、`@/store/auth`（work_order.execute=true）。

```ts
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const woApi = vi.hoisted(() => ({ getExecution: vi.fn(), patchStepResult: vi.fn() }))
vi.mock('@/api/workOrders', () => woApi)
const attApi = vi.hoisted(() => ({
  listEntityAttachments: vi.fn(),
  uploadEntityAttachment: vi.fn(),
  deleteAttachment: vi.fn(),
  downloadAttachment: vi.fn(),
}))
vi.mock('@/api/attachments', () => attApi)
vi.mock('@/api/users', () => ({ listUsers: vi.fn().mockResolvedValue([]) }))
vi.mock('@/store/auth', () => ({ useAuthStore: () => ({ hasPermission: () => true }) }))

import ExecutionTab from '@/components/workorder/ExecutionTab.vue'

const EXEC = {
  procedure: { id: 'p', group_id: 'g', code: 'S', name: 'P', version: 1 },
  outline: [],
  steps: [{
    id: 'sr1', node_id: 'n1', node_code: 'S1', node_sort_order: 1,
    input_schema: { type: 'UPLOAD', required: true }, response: {},
    is_done: false, done_by_user_id: null, done_at: null, notes: '', attachment_count: 0,
  }],
}

beforeEach(() => {
  setActivePinia(createPinia())
  woApi.getExecution.mockReset().mockResolvedValue(EXEC)
  attApi.listEntityAttachments.mockReset().mockResolvedValue([])
  attApi.uploadEntityAttachment.mockReset().mockResolvedValue({ id: 'a1', file_name: 'x.png' })
  attApi.deleteAttachment.mockReset().mockResolvedValue(undefined)
})

describe('ExecutionTab attachments', () => {
  it('UPLOAD 步骤渲染上传控件并按 step 拉附件', async () => {
    const w = mount(ExecutionTab, { props: { workOrderId: 'wo1' }, global: { plugins: [ElementPlus] } })
    await flushPromises()
    expect(attApi.listEntityAttachments).toHaveBeenCalledWith('work_order_step_result', 'sr1')
    expect(w.find('.el-upload').exists()).toBe(true)
  })
})
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd frontend && npx vitest run tests/unit/ExecutionTabAttachments.spec.ts`
Expected: FAIL（无 el-upload / 未调 listEntityAttachments）

- [ ] **Step 4: ExecutionTab 加 UPLOAD/PHOTO 控件**

在 `ExecutionTab.vue` `<script setup>`：
- import：`import { listEntityAttachments, uploadEntityAttachment, deleteAttachment } from '@/api/attachments'`、`import type { AttachmentOut } from '@/types/attachment'`。
- 加附件类型判定与状态：
```ts
const ATTACHMENT_TYPES = new Set(['UPLOAD', 'PHOTO', 'SIGNATURE'])
function isAttachmentType(step: StepResultRead): boolean {
  return ATTACHMENT_TYPES.has(stepType(step))
}
// 按 step id 缓存附件列表
const stepAttachments = reactive<Record<string, AttachmentOut[]>>({})
async function loadStepAttachments(stepId: string): Promise<void> {
  stepAttachments[stepId] = await listEntityAttachments('work_order_step_result', stepId)
}
async function onUpload(stepId: string, file: File): Promise<void> {
  await uploadEntityAttachment('work_order_step_result', stepId, file)
  await loadStepAttachments(stepId)
}
async function onRemoveAttachment(stepId: string, attId: string): Promise<void> {
  await deleteAttachment(attId)
  await loadStepAttachments(stepId)
}
```
- 在加载 execution 后（getExecution 成功的回调里），对每个 `isAttachmentType` 的 step 调 `loadStepAttachments(step.id)`。

在 `<template>`：把 UPLOAD/PHOTO 步骤的兜底分支替换为上传控件（PHOTO 加 `accept="image/*"`）。用 `el-upload` 的 `:http-request` 自定义上传：
```html
<template v-else-if="stepType(step) === 'UPLOAD' || stepType(step) === 'PHOTO'">
  <el-upload
    v-if="canExecute"
    :show-file-list="false"
    :accept="stepType(step) === 'PHOTO' ? 'image/*' : undefined"
    :http-request="(opt) => onUpload(step.id, opt.file as File)"
  >
    <el-button size="small">上传文件</el-button>
  </el-upload>
  <ul class="att-list">
    <li v-for="a in stepAttachments[step.id] || []" :key="a.id">
      {{ a.file_name }}
      <el-button v-if="canExecute" link type="danger" size="small" @click="onRemoveAttachment(step.id, a.id)">删除</el-button>
    </li>
  </ul>
</template>
```
（`canExecute` 既有；只读态——`!canExecute`——只列附件不渲染上传/删除。`el-upload` 的 `:http-request` 类型参考既有用法；`opt.file` 取上传文件。）

- [ ] **Step 5: 跑测试 + gate + 提交**

Run: `cd frontend && npx vitest run tests/unit/ExecutionTabAttachments.spec.ts && npx vue-tsc --noEmit && npx eslint src/components/workorder/ExecutionTab.vue src/types/workOrder.ts tests/unit/ExecutionTabAttachments.spec.ts`

```bash
git add frontend/src/components/workorder/ExecutionTab.vue frontend/src/types/workOrder.ts frontend/tests/unit/ExecutionTabAttachments.spec.ts
git commit -m "$(cat <<'EOF'
feat(ea): 执行态 UPLOAD/PHOTO 步骤附件上传控件 + 列表

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 5：SIGNATURE 画板 + 接入 + 只读

### Task 7：SignaturePad 组件 + SIGNATURE 接入 + 收口

**Files:**
- Create: `frontend/src/components/workorder/SignaturePad.vue`, `frontend/tests/unit/SignaturePad.spec.ts`
- Modify: `frontend/src/components/workorder/ExecutionTab.vue`

- [ ] **Step 1: 写 SignaturePad 组件** `frontend/src/components/workorder/SignaturePad.vue`

canvas 手写：鼠标按下/移动/抬起画线；「清除」清空；「确认」`canvas.toBlob` 出 PNG → emit `confirm(file: File)`。

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'

const emit = defineEmits<{ (e: 'confirm', file: File): void }>()
const canvasRef = ref<HTMLCanvasElement | null>(null)
let drawing = false
let ctx: CanvasRenderingContext2D | null = null

onMounted(() => {
  const c = canvasRef.value
  if (!c) return
  ctx = c.getContext('2d')
  if (ctx) {
    ctx.lineWidth = 2
    ctx.lineCap = 'round'
    ctx.strokeStyle = '#222'
  }
})

function pos(e: MouseEvent): [number, number] {
  const r = canvasRef.value!.getBoundingClientRect()
  return [e.clientX - r.left, e.clientY - r.top]
}
function start(e: MouseEvent): void {
  if (!ctx) return
  drawing = true
  const [x, y] = pos(e)
  ctx.beginPath()
  ctx.moveTo(x, y)
}
function move(e: MouseEvent): void {
  if (!drawing || !ctx) return
  const [x, y] = pos(e)
  ctx.lineTo(x, y)
  ctx.stroke()
}
function stop(): void {
  drawing = false
}
function clear(): void {
  const c = canvasRef.value
  if (c && ctx) ctx.clearRect(0, 0, c.width, c.height)
}
function confirm(): void {
  const c = canvasRef.value
  if (!c) return
  c.toBlob((blob) => {
    if (blob) emit('confirm', new File([blob], 'signature.png', { type: 'image/png' }))
  }, 'image/png')
}
</script>

<template>
  <div class="sign-pad">
    <canvas
      ref="canvasRef"
      width="320"
      height="140"
      class="sign-canvas"
      @mousedown="start"
      @mousemove="move"
      @mouseup="stop"
      @mouseleave="stop"
    />
    <div class="sign-actions">
      <el-button size="small" @click="clear">清除</el-button>
      <el-button size="small" type="primary" @click="confirm">确认签名</el-button>
    </div>
  </div>
</template>

<style scoped>
.sign-canvas {
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  touch-action: none;
  background: #fff;
}
.sign-actions {
  margin-top: 6px;
  display: flex;
  gap: 8px;
}
</style>
```

- [ ] **Step 2: 写测试** `frontend/tests/unit/SignaturePad.spec.ts`

```ts
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import SignaturePad from '@/components/workorder/SignaturePad.vue'

beforeEach(() => {
  // jsdom 无 canvas.toBlob：打桩为产出一个 PNG Blob
  // @ts-expect-error 测试桩
  HTMLCanvasElement.prototype.getContext = () => ({
    lineWidth: 0, lineCap: '', strokeStyle: '',
    beginPath() {}, moveTo() {}, lineTo() {}, stroke() {}, clearRect() {},
  })
  // @ts-expect-error 测试桩
  HTMLCanvasElement.prototype.toBlob = function (cb: (b: Blob) => void) {
    cb(new Blob(['x'], { type: 'image/png' }))
  }
})

describe('SignaturePad', () => {
  it('确认签名 emit confirm 携带 PNG File', async () => {
    const w = mount(SignaturePad, { global: { plugins: [ElementPlus] } })
    const btn = w.findAll('.el-button').find((b) => b.text() === '确认签名')
    await btn!.trigger('click')
    const ev = w.emitted('confirm')
    expect(ev).toBeTruthy()
    const file = ev![0][0] as File
    expect(file.type).toBe('image/png')
    expect(file.name).toBe('signature.png')
  })
})
```

- [ ] **Step 3: 跑测试确认通过**

Run: `cd frontend && npx vitest run tests/unit/SignaturePad.spec.ts`
Expected: PASS

- [ ] **Step 4: ExecutionTab 接入 SIGNATURE**

`ExecutionTab.vue` import `SignaturePad`。在 template 加 SIGNATURE 分支（复用 Task 6 的 onUpload 与附件列表）：
```html
<template v-else-if="stepType(step) === 'SIGNATURE'">
  <SignaturePad v-if="canExecute" @confirm="(f) => onUpload(step.id, f)" />
  <ul class="att-list">
    <li v-for="a in stepAttachments[step.id] || []" :key="a.id">
      {{ a.file_name }}
      <el-button v-if="canExecute" link type="danger" size="small" @click="onRemoveAttachment(step.id, a.id)">删除</el-button>
    </li>
  </ul>
</template>
```
（SIGNATURE 已在 Task 6 的 `isAttachmentType`/`loadStepAttachments` 覆盖，故加载逻辑无需再改。）

- [ ] **Step 5: 跑测试 + gate + 提交**

Run: `cd frontend && npx vitest run tests/unit/SignaturePad.spec.ts tests/unit/ExecutionTabAttachments.spec.ts && npx vue-tsc --noEmit && npx eslint src/components/workorder/SignaturePad.vue src/components/workorder/ExecutionTab.vue tests/unit/SignaturePad.spec.ts`

```bash
git add frontend/src/components/workorder/SignaturePad.vue frontend/src/components/workorder/ExecutionTab.vue frontend/tests/unit/SignaturePad.spec.ts
git commit -m "$(cat <<'EOF'
feat(ea): SignaturePad 签名画板 + 执行态 SIGNATURE 步骤接入

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 8：全量收口

- [ ] **Step 1: 后端全量** `cd backend && .venv/bin/python -m pytest -q`（全绿）+ `.venv/bin/alembic heads`（单 head `step_result_soft_delete`）+ ruff/format/mypy 净。
- [ ] **Step 2: 前端全量** `cd frontend && npx vue-tsc --noEmit && npx eslint . && npx vitest run`（全绿）。
- [ ] **Step 3: 提交（若有收口修整）** `chore(ea): 全量门禁收口绿`。

---

## 自审备注（实现者注意）
- **附件写权限 = WORK_ORDER_EXECUTE**（非 EDIT）：与步骤完成同权，避免执行人被挡（spec §4.1 初稿写 EDIT，此处按执行语义修正）。
- **required 布尔 vs list 不冲突**：值类型步骤 `required` 是字段 key 列表（`_required_fields` 处理）；附件类型步骤 `required` 是布尔（`_requires_attachment` 处理）。两路径互不干扰，因同一步骤只有一种 type。
- **Attachment 构造必填字段**以真实模型为准（先 grep `app/models/attachment.py`）；测试桩里若缺字段按真实补。
- **测试 setup 签名**（create_work_order/attach_procedure/transition/Company）一律以 `tests/test_work_order_execution_service.py` 既有用法为准，不符即对齐。
- **只读态**：`canExecute=false`（无 work_order.execute 或工单非 IN_PROGRESS 语境）只列附件、不渲染上传/删除控件。
