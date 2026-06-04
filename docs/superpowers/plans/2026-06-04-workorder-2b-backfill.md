# 工单 2B 后端补全 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为工单后端补齐完成字段族、工单间 Relation、按备件反查、canBeEditedBy 对象级谓词四块 Atlas parity 缺口（纯后端）。

**Architecture:** 在既有 `WorkOrder` 上加 8 列；新建 `tb_work_order_relation` 自关联表（单有向记录、查询双向展开）；`transition()` 内补完成钩子（completed_by/is_compliant 快照/first_responded_at）；新增纯函数 `can_edit_work_order` 守卫 PATCH 字段编辑（不锁 reopen）；LIST 加 `part_id` 过滤。统一一个 alembic 迁移，全程 SQLite TDD。

**Tech Stack:** FastAPI + SQLAlchemy 2.0（Mapped/mapped_column）+ Alembic + Pydantic v2 + pytest。

**设计依据:** `docs/superpowers/specs/2026-06-04-workorder-2b-backfill-design.md`

---

## 全局约定（每任务适用）

- 每任务：写测试 → 跑红 → 实现 → `pytest` 绿 → `ruff check` + `ruff format` + `mypy` 净 → commit。
- 后端根目录 = `backend/`，命令均在 `backend/` 下执行（venv 已激活）。
- 跑单测：`pytest tests/<file>::<test> -v`；跑全量：`pytest -q`。
- 门禁：`ruff check app tests && ruff format --check app tests && mypy app`。
- 弱引用 user id 列沿用既有约定（`String(36)`，无 FK），与 `created_by_user_id` 一致。

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `app/models/work_order_status.py` | 加 `WorkOrderRelationType` 枚举 | Modify |
| `app/models/work_order.py` | WorkOrder 加 8 列 + `WorkOrderRelation` 模型 | Modify |
| `app/schemas/work_order.py` | WorkOrderRead 加字段 + Relation 读写 schema | Modify |
| `app/services/work_order_service.py` | transition 钩子 + `can_edit_work_order` + relation CRUD + LIST part_id | Modify |
| `app/routers/work_orders.py` | PATCH 守卫 + Relation 3 端点 + LIST part_id 参 + to_read viewer | Modify |
| `alembic/versions/20260604_0001_workorder_2b_backfill.py` | 8 列 + relation 表迁移 | Create |
| `tests/test_work_order_fields.py` | 字段族 + to_read 映射 | Create |
| `tests/test_work_order_transition_hooks.py` | 完成钩子 + 首响时间 | Create |
| `tests/test_work_order_can_edit.py` | can_edit 谓词 + PATCH 守卫 | Create |
| `tests/test_work_order_relations.py` | Relation service + API + 跨租户 | Create |
| `tests/test_work_order_part_lookup.py` | 按备件反查 + 跨租户隔离 | Create |
| `tests/unit/test_migration_workorder_2b.py` | 迁移 up/down 重放 | Create |

---

## Task 1: WorkOrder 加 8 列 + WorkOrderRead 映射

**Files:**
- Modify: `app/models/work_order.py`（WorkOrder 类）
- Modify: `app/schemas/work_order.py`（WorkOrderRead）
- Modify: `app/services/work_order_service.py:54-73`（to_read）
- Test: `tests/test_work_order_fields.py`

- [ ] **Step 1: 写失败测试** `tests/test_work_order_fields.py`

```python
from datetime import date

from app import tenant
from app.models.company import Company
from app.models.work_order import WorkOrder
from app.models.work_order_status import WorkOrderStatus
from app.services import work_order_service as svc


def _company(db):
    c = Company(name="Acme", slug="acme")
    db.add(c)
    db.commit()
    return c


def test_new_fields_default(db):
    c = _company(db)
    tenant.set_current_company_id(c.id)
    wo = WorkOrder(custom_id="WO000001", title="t", company_id=c.id)
    db.add(wo)
    db.commit()
    db.refresh(wo)
    assert wo.completed_by_user_id is None
    assert wo.feedback is None
    assert wo.urgent is False
    assert wo.estimated_duration is None
    assert wo.estimated_start_date is None
    assert wo.first_responded_at is None
    assert wo.archived is False
    assert wo.is_compliant is None


def test_to_read_includes_new_fields(db):
    c = _company(db)
    tenant.set_current_company_id(c.id)
    wo = WorkOrder(
        custom_id="WO000001",
        title="t",
        company_id=c.id,
        urgent=True,
        feedback="ok",
        estimated_duration=90,
        estimated_start_date=date(2026, 6, 10),
        archived=True,
    )
    db.add(wo)
    db.commit()
    data = svc.to_read(db, wo)
    assert data["urgent"] is True
    assert data["feedback"] == "ok"
    assert data["estimated_duration"] == 90
    assert data["estimated_start_date"] == date(2026, 6, 10)
    assert data["archived"] is True
    assert data["completed_by_user_id"] is None
    assert data["first_responded_at"] is None
    assert data["is_compliant"] is None
```

- [ ] **Step 2: 跑红** `pytest tests/test_work_order_fields.py -v` → FAIL（AttributeError: 无 urgent 等）。

- [ ] **Step 3: 模型加列** —— 在 `app/models/work_order.py` 的 WorkOrder 类 `created_by_user_id`（行 64）之后追加：

```python
    # 完成归属与反馈（2B）
    completed_by_user_id: Mapped[str | None] = mapped_column(String(36), default=None)
    feedback: Mapped[str | None] = mapped_column(Text, default=None)
    # 紧急旗标（与 priority 正交）
    urgent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 估时（分钟）与预计开始日
    estimated_duration: Mapped[int | None] = mapped_column(Integer, default=None)
    estimated_start_date: Mapped[date | None] = mapped_column(Date, default=None)
    # 首次离开 OPEN 的时刻（MTTA 原料，只记一次）
    first_responded_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    # 归档维度（与 is_active 软删正交）
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 完成时自动判定的合规快照；未完成为 None
    is_compliant: Mapped[bool | None] = mapped_column(Boolean, default=None)
```

并把文件顶部导入补全 `Boolean` 与 `Integer`（行 11-17 的 sqlalchemy import 块）：

```python
from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
```

- [ ] **Step 4: schema 加字段** —— `app/schemas/work_order.py` WorkOrderRead（行 68 `created_by_user_id` 之后）追加：

```python
    completed_by_user_id: str | None = None
    feedback: str | None = None
    urgent: bool = False
    estimated_duration: int | None = None
    estimated_start_date: date | None = None
    first_responded_at: datetime | None = None
    archived: bool = False
    is_compliant: bool | None = None
```

- [ ] **Step 5: to_read 映射** —— `app/services/work_order_service.py` to_read（行 55-73 的 dict）在 `"created_by_user_id": wo.created_by_user_id,` 之后追加：

```python
        "completed_by_user_id": wo.completed_by_user_id,
        "feedback": wo.feedback,
        "urgent": wo.urgent,
        "estimated_duration": wo.estimated_duration,
        "estimated_start_date": wo.estimated_start_date,
        "first_responded_at": wo.first_responded_at,
        "archived": wo.archived,
        "is_compliant": wo.is_compliant,
```

- [ ] **Step 6: 跑绿** `pytest tests/test_work_order_fields.py -v` → PASS。门禁 `ruff check app tests && ruff format app tests && mypy app`。

- [ ] **Step 7: Commit**

```bash
git add app/models/work_order.py app/schemas/work_order.py app/services/work_order_service.py tests/test_work_order_fields.py
git commit -m "feat(wo-2b): add completion field family columns + read mapping"
```

---

## Task 2: transition 完成钩子 + 首响时间

**Files:**
- Modify: `app/services/work_order_service.py:231-264`（transition）
- Test: `tests/test_work_order_transition_hooks.py`

- [ ] **Step 1: 写失败测试** `tests/test_work_order_transition_hooks.py`

```python
from datetime import date, timedelta

from app import tenant
from app.models.company import Company
from app.models.work_order import WorkOrder
from app.models.work_order_status import WorkOrderStatus
from app.schemas.work_order import WorkOrderTransition
from app.services import work_order_service as svc


def _wo(db, **kw):
    c = Company(name="Acme", slug="acme")
    db.add(c)
    db.commit()
    tenant.set_current_company_id(c.id)
    wo = WorkOrder(custom_id="WO000001", title="t", company_id=c.id, **kw)
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return c, wo


def _to(db, wo, status, company_id, actor="u1"):
    return svc.transition(
        db, wo, WorkOrderTransition(to_status=status), company_id, actor_user_id=actor
    )


def test_complete_stamps_completed_by_and_compliant_on_time(db):
    c, wo = _wo(db, status=WorkOrderStatus.IN_PROGRESS, due_date=date.today() + timedelta(days=1))
    _to(db, wo, WorkOrderStatus.COMPLETE, c.id, actor="u9")
    assert wo.status == WorkOrderStatus.COMPLETE
    assert wo.completed_by_user_id == "u9"
    assert wo.completed_at is not None
    assert wo.is_compliant is True


def test_complete_overdue_is_not_compliant(db):
    c, wo = _wo(db, status=WorkOrderStatus.IN_PROGRESS, due_date=date.today() - timedelta(days=1))
    _to(db, wo, WorkOrderStatus.COMPLETE, c.id)
    assert wo.is_compliant is False


def test_complete_without_due_date_is_compliant(db):
    c, wo = _wo(db, status=WorkOrderStatus.IN_PROGRESS, due_date=None)
    _to(db, wo, WorkOrderStatus.COMPLETE, c.id)
    assert wo.is_compliant is True


def test_reopen_clears_completion(db):
    c, wo = _wo(db, status=WorkOrderStatus.IN_PROGRESS, due_date=None)
    _to(db, wo, WorkOrderStatus.COMPLETE, c.id, actor="u9")
    _to(db, wo, WorkOrderStatus.IN_PROGRESS, c.id, actor="u3")
    assert wo.completed_at is None
    assert wo.completed_by_user_id is None
    assert wo.is_compliant is None


def test_first_responded_at_set_once_on_leaving_open(db):
    c, wo = _wo(db, status=WorkOrderStatus.OPEN, due_date=None)
    _to(db, wo, WorkOrderStatus.IN_PROGRESS, c.id)
    first = wo.first_responded_at
    assert first is not None
    # 完成再重开，first_responded_at 不被覆盖
    _to(db, wo, WorkOrderStatus.COMPLETE, c.id)
    _to(db, wo, WorkOrderStatus.IN_PROGRESS, c.id)
    assert wo.first_responded_at == first
```

- [ ] **Step 2: 跑红** `pytest tests/test_work_order_transition_hooks.py -v` → FAIL。

- [ ] **Step 3: 实现钩子** —— 改 `app/services/work_order_service.py` transition（行 238-248），替换为：

```python
    src, dst = wo.status, payload.to_status
    if not can_transition(src, dst):
        raise bad_request("WORKORDER_BAD_TRANSITION", f"非法状态转移 {src.value}->{dst.value}")
    # 首次离开 OPEN：戳记首响时间（只记一次，重开不覆盖）
    if src == WorkOrderStatus.OPEN and wo.first_responded_at is None:
        wo.first_responded_at = utcnow()
    if dst == WorkOrderStatus.COMPLETE:
        from app.services import work_order_execution_service as exe

        exe.assert_completable(db, wo)
        wo.completed_at = utcnow()
        wo.completed_by_user_id = actor_user_id
        # 合规快照：无截止日视为合规；否则按完成日 <= 截止日
        wo.is_compliant = wo.due_date is None or wo.completed_at.date() <= wo.due_date
    if src == WorkOrderStatus.COMPLETE and dst == WorkOrderStatus.IN_PROGRESS:
        wo.completed_at = None
        wo.completed_by_user_id = None
        wo.is_compliant = None
    wo.status = dst
```

- [ ] **Step 4: 跑绿** `pytest tests/test_work_order_transition_hooks.py -v` → PASS。门禁同 Task 1。

- [ ] **Step 5: Commit**

```bash
git add app/services/work_order_service.py tests/test_work_order_transition_hooks.py
git commit -m "feat(wo-2b): transition hooks for completed_by/is_compliant/first_responded_at"
```

---

## Task 3: can_edit_work_order 谓词 + PATCH 守卫 + can_be_edited 响应

**Files:**
- Modify: `app/services/work_order_service.py`（新增 `can_edit_work_order` + to_read 加 viewer）
- Modify: `app/schemas/work_order.py`（WorkOrderRead 加 `can_be_edited`）
- Modify: `app/routers/work_orders.py`（PATCH 守卫 + 各处 to_read 传 viewer）
- Test: `tests/test_work_order_can_edit.py`

- [ ] **Step 1: 写失败测试** `tests/test_work_order_can_edit.py`

```python
from app import tenant
from app.models.company import Company
from app.models.role import Role
from app.models.user import User
from app.models.work_order import WorkOrder, WorkOrderAssignee
from app.models.work_order_status import WorkOrderStatus
from app.services import work_order_service as svc


def _setup(db, role_code, status=WorkOrderStatus.IN_PROGRESS, created_by="creator"):
    c = Company(name="Acme", slug="acme")
    db.add(c)
    db.commit()
    tenant.set_current_company_id(c.id)
    role = Role(code=role_code, name=role_code, company_id=c.id, permissions=[])
    db.add(role)
    db.commit()
    wo = WorkOrder(
        custom_id="WO000001",
        title="t",
        company_id=c.id,
        status=status,
        created_by_user_id=created_by,
    )
    db.add(wo)
    db.commit()
    return c, role, wo


def _user(db, uid, role_id, company_id):
    u = User(
        id=uid,
        email=f"{uid}@a.com",
        password_hash="x",
        name=uid,
        role_id=role_id,
        company_id=company_id,
    )
    db.add(u)
    db.commit()
    return u


def test_admin_can_edit_even_in_terminal(db):
    c, role, wo = _setup(db, "admin", status=WorkOrderStatus.COMPLETE, created_by="other")
    u = _user(db, "adm", role.id, c.id)
    assert svc.can_edit_work_order(db, u, wo) is True


def test_terminal_locks_non_admin(db):
    c, role, wo = _setup(db, "technician", status=WorkOrderStatus.COMPLETE, created_by="creator")
    u = _user(db, "creator", role.id, c.id)
    assert svc.can_edit_work_order(db, u, wo) is False


def test_creator_can_edit_non_terminal(db):
    c, role, wo = _setup(db, "technician", created_by="creator")
    u = _user(db, "creator", role.id, c.id)
    assert svc.can_edit_work_order(db, u, wo) is True


def test_assignee_can_edit(db):
    c, role, wo = _setup(db, "technician", created_by="other")
    u = _user(db, "asg", role.id, c.id)
    db.add(WorkOrderAssignee(work_order_id=wo.id, user_id="asg", company_id=c.id))
    db.commit()
    assert svc.can_edit_work_order(db, u, wo) is True


def test_unrelated_user_cannot_edit(db):
    c, role, wo = _setup(db, "technician", created_by="other")
    u = _user(db, "stranger", role.id, c.id)
    assert svc.can_edit_work_order(db, u, wo) is False


def test_patch_returns_403_when_predicate_false(client, monkeypatch):
    from app.services import work_order_service

    t = client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "a@a.com", "password": "secret123", "name": "A"},
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    wid = client.post("/api/v1/work-orders", headers=h, json={"title": "t"}).json()["id"]
    monkeypatch.setattr(work_order_service, "can_edit_work_order", lambda *a, **k: False)
    r = client.patch(f"/api/v1/work-orders/{wid}", headers=h, json={"title": "x"})
    assert r.status_code == 403, r.text


def test_read_exposes_can_be_edited(client):
    t = client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "a@a.com", "password": "secret123", "name": "A"},
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    wo = client.post("/api/v1/work-orders", headers=h, json={"title": "t"}).json()
    assert wo["can_be_edited"] is True
```

- [ ] **Step 2: 跑红** `pytest tests/test_work_order_can_edit.py -v` → FAIL。

- [ ] **Step 3: 实现谓词** —— `app/services/work_order_service.py` 顶部 import 区加：

```python
from app.models.role import Role
from app.models.user import User
```

在 `to_read` 之前新增函数：

```python
def can_edit_work_order(db: Session, user: User, wo: WorkOrder) -> bool:
    """对象级可编辑谓词：角色 → 终态锁 → 归属。仅用于 PATCH 字段编辑，不锁 reopen。"""
    role = db.get(Role, user.role_id) if user.role_id else None
    if role is not None and role.code in {"super_admin", "admin"}:
        return True
    if wo.status in {WorkOrderStatus.COMPLETE, WorkOrderStatus.CANCELED}:
        return False
    if user.id == wo.created_by_user_id:
        return True
    if user.id == wo.primary_user_id:
        return True
    return user.id in set(assignee_ids(db, wo.id))
```

- [ ] **Step 4: to_read 加 viewer** —— 改 `to_read` 签名与末尾：

```python
def to_read(db: Session, wo: WorkOrder, viewer: User | None = None) -> dict[str, object]:
    return {
        # ... 既有全部键不变 ...
        "team_ids": team_ids(db, wo.id),
        "can_be_edited": can_edit_work_order(db, viewer, wo) if viewer is not None else False,
    }
```

（把 `"can_be_edited"` 作为 dict 最后一项加入，其余键保持原样。）

- [ ] **Step 5: schema 加字段** —— `app/schemas/work_order.py` WorkOrderRead 末尾（Task 1 追加的字段之后）加：

```python
    can_be_edited: bool = False
```

- [ ] **Step 6: 路由守卫 + 传 viewer** —— `app/routers/work_orders.py`：
  1. import 区加 `from app.errors import forbidden`（与现有 `from app.errors import not_found` 合并为一行 `from app.errors import forbidden, not_found`）。
  2. PATCH `update_work_order`（行 102-104）改为：

```python
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    if not svc.can_edit_work_order(db, current_user, wo):
        raise forbidden("WORKORDER_NOT_EDITABLE", "无权编辑该工单")
    wo = svc.update_work_order(db, wo, payload, current_user.company_id)
    return svc.to_read(db, wo, viewer=current_user)
```

  3. 其余所有 `return svc.to_read(db, wo)` 调用点（list/create/get/assignees/teams/transition/attach/detach）统一改为 `svc.to_read(db, wo, viewer=current_user)`；list 端点的列表推导改为 `[svc.to_read(db, w, viewer=current_user) for w in rows]`。

- [ ] **Step 7: 跑绿** `pytest tests/test_work_order_can_edit.py -v` → PASS。回归 `pytest tests/test_work_orders_api.py -v`。门禁同上。

- [ ] **Step 8: Commit**

```bash
git add app/services/work_order_service.py app/schemas/work_order.py app/routers/work_orders.py tests/test_work_order_can_edit.py
git commit -m "feat(wo-2b): can_edit_work_order predicate + PATCH guard + can_be_edited"
```

---

## Task 4: WorkOrderRelation 模型 + service + API

**Files:**
- Modify: `app/models/work_order_status.py`（加 WorkOrderRelationType）
- Modify: `app/models/work_order.py`（加 WorkOrderRelation 模型）
- Modify: `app/schemas/work_order.py`（Relation 读写 schema）
- Modify: `app/services/work_order_service.py`（relation CRUD + 双向展开）
- Modify: `app/routers/work_orders.py`（3 端点）
- Test: `tests/test_work_order_relations.py`

- [ ] **Step 1: 写失败测试** `tests/test_work_order_relations.py`

```python
from app.models.company import Company


def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "A"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _wo(client, h, title):
    return client.post("/api/v1/work-orders", headers=h, json={"title": title}).json()["id"]


def test_create_and_list_symmetric(client):
    t = _admin(client)
    h = _h(t)
    a, b = _wo(client, h, "A"), _wo(client, h, "B")
    r = client.post(
        f"/api/v1/work-orders/{a}/relations",
        headers=h,
        json={"target_work_order_id": b, "relation_type": "RELATED"},
    )
    assert r.status_code == 201, r.text
    # 从 a 看
    la = client.get(f"/api/v1/work-orders/{a}/relations", headers=h).json()
    assert len(la) == 1
    assert la[0]["relation_type"] == "RELATED"
    assert la[0]["direction"] == "symmetric"
    assert la[0]["related_work_order_id"] == b
    # 从 b 看（双向展开）
    lb = client.get(f"/api/v1/work-orders/{b}/relations", headers=h).json()
    assert len(lb) == 1
    assert lb[0]["related_work_order_id"] == a
    assert lb[0]["direction"] == "symmetric"


def test_directed_blocks_direction(client):
    t = _admin(client)
    h = _h(t)
    a, b = _wo(client, h, "A"), _wo(client, h, "B")
    client.post(
        f"/api/v1/work-orders/{a}/relations",
        headers=h,
        json={"target_work_order_id": b, "relation_type": "BLOCKS"},
    )
    la = client.get(f"/api/v1/work-orders/{a}/relations", headers=h).json()
    assert la[0]["direction"] == "outgoing"
    lb = client.get(f"/api/v1/work-orders/{b}/relations", headers=h).json()
    assert lb[0]["direction"] == "incoming"


def test_self_relation_rejected(client):
    t = _admin(client)
    h = _h(t)
    a = _wo(client, h, "A")
    r = client.post(
        f"/api/v1/work-orders/{a}/relations",
        headers=h,
        json={"target_work_order_id": a, "relation_type": "RELATED"},
    )
    assert r.status_code == 400


def test_duplicate_rejected(client):
    t = _admin(client)
    h = _h(t)
    a, b = _wo(client, h, "A"), _wo(client, h, "B")
    body = {"target_work_order_id": b, "relation_type": "RELATED"}
    client.post(f"/api/v1/work-orders/{a}/relations", headers=h, json=body)
    r = client.post(f"/api/v1/work-orders/{a}/relations", headers=h, json=body)
    assert r.status_code == 409


def test_cross_tenant_target_404(client):
    ta = _admin(client, "Acme", "a@a.com")
    tb = _admin(client, "Beta", "b@b.com")
    a = _wo(client, _h(ta), "A")
    b_other = _wo(client, _h(tb), "B")
    r = client.post(
        f"/api/v1/work-orders/{a}/relations",
        headers=_h(ta),
        json={"target_work_order_id": b_other, "relation_type": "RELATED"},
    )
    assert r.status_code == 404


def test_delete_relation(client):
    t = _admin(client)
    h = _h(t)
    a, b = _wo(client, h, "A"), _wo(client, h, "B")
    rid = client.post(
        f"/api/v1/work-orders/{a}/relations",
        headers=h,
        json={"target_work_order_id": b, "relation_type": "RELATED"},
    ).json()["id"]
    d = client.delete(f"/api/v1/work-orders/{a}/relations/{rid}", headers=h)
    assert d.status_code == 204
    assert client.get(f"/api/v1/work-orders/{a}/relations", headers=h).json() == []
```

- [ ] **Step 2: 跑红** `pytest tests/test_work_order_relations.py -v` → FAIL。

- [ ] **Step 3: 枚举** —— `app/models/work_order_status.py` 末尾加：

```python
class WorkOrderRelationType(enum.StrEnum):
    DUPLICATE = "DUPLICATE"
    RELATED = "RELATED"
    SPLIT = "SPLIT"
    BLOCKS = "BLOCKS"


SYMMETRIC_RELATION_TYPES: frozenset[WorkOrderRelationType] = frozenset(
    {WorkOrderRelationType.DUPLICATE, WorkOrderRelationType.RELATED}
)
```

- [ ] **Step 4: 模型** —— `app/models/work_order.py`：import 区加 `from app.models.work_order_status import WorkOrderPriority, WorkOrderRelationType, WorkOrderStatus`（在现有 import 上扩充 `WorkOrderRelationType`），文件末尾加：

```python
class WorkOrderRelation(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_work_order_relation"
    __table_args__ = (
        UniqueConstraint(
            "source_work_order_id",
            "target_work_order_id",
            "relation_type",
            name="uq_work_order_relation",
        ),
    )

    source_work_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_work_order.id", ondelete="CASCADE"), index=True
    )
    target_work_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_work_order.id", ondelete="CASCADE"), index=True
    )
    relation_type: Mapped[WorkOrderRelationType] = mapped_column(
        SAEnum(WorkOrderRelationType), nullable=False
    )
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), default=None)
```

- [ ] **Step 5: schema** —— `app/schemas/work_order.py`：import 加 `WorkOrderRelationType`（行 10），新增：

```python
class WorkOrderRelationCreate(BaseModel):
    target_work_order_id: str
    relation_type: WorkOrderRelationType


class WorkOrderRelationRead(BaseModel):
    id: str
    relation_type: WorkOrderRelationType
    direction: str  # "symmetric" | "outgoing" | "incoming"
    related_work_order_id: str
    related_custom_id: str | None = None
    related_title: str | None = None
    related_status: WorkOrderStatus | None = None
```

- [ ] **Step 6: service** —— `app/services/work_order_service.py`：import 加 `WorkOrderRelation` 与枚举：

```python
from app.models.work_order import WorkOrder, WorkOrderAssignee, WorkOrderRelation, WorkOrderTeam
from app.models.work_order_status import (
    SYMMETRIC_RELATION_TYPES,
    WorkOrderRelationType,
    WorkOrderStatus,
    can_transition,
)
```

新增函数：

```python
def create_relation(
    db: Session,
    wo: WorkOrder,
    target_id: str,
    relation_type: WorkOrderRelationType,
    company_id: str,
    actor_user_id: str | None,
) -> WorkOrderRelation:
    if target_id == wo.id:
        raise bad_request("WORKORDER_RELATION_SELF", "不能关联自身")
    target = get_work_order(db, target_id)
    if target is None or target.company_id != company_id:
        raise not_found("WORKORDER_NOT_FOUND", "目标工单不存在")
    dup = db.execute(
        select(WorkOrderRelation).where(
            WorkOrderRelation.source_work_order_id == wo.id,
            WorkOrderRelation.target_work_order_id == target_id,
            WorkOrderRelation.relation_type == relation_type,
        )
    ).scalar_one_or_none()
    if dup is not None:
        raise conflict("WORKORDER_RELATION_DUPLICATE", "关联已存在")
    rel = WorkOrderRelation(
        source_work_order_id=wo.id,
        target_work_order_id=target_id,
        relation_type=relation_type,
        created_by_user_id=actor_user_id,
        company_id=company_id,
    )
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return rel


def list_relations(db: Session, wo: WorkOrder) -> list[dict[str, object]]:
    rels = db.execute(
        select(WorkOrderRelation).where(
            (WorkOrderRelation.source_work_order_id == wo.id)
            | (WorkOrderRelation.target_work_order_id == wo.id)
        )
    ).scalars().all()
    out: list[dict[str, object]] = []
    for r in rels:
        is_source = r.source_work_order_id == wo.id
        other_id = r.target_work_order_id if is_source else r.source_work_order_id
        if r.relation_type in SYMMETRIC_RELATION_TYPES:
            direction = "symmetric"
        else:
            direction = "outgoing" if is_source else "incoming"
        other = db.get(WorkOrder, other_id)
        out.append(
            {
                "id": r.id,
                "relation_type": r.relation_type,
                "direction": direction,
                "related_work_order_id": other_id,
                "related_custom_id": other.custom_id if other else None,
                "related_title": other.title if other else None,
                "related_status": other.status if other else None,
            }
        )
    return out


def delete_relation(db: Session, wo: WorkOrder, relation_id: str, company_id: str) -> None:
    rel = db.get(WorkOrderRelation, relation_id)
    if (
        rel is None
        or rel.company_id != company_id
        or wo.id not in {rel.source_work_order_id, rel.target_work_order_id}
    ):
        raise not_found("WORKORDER_RELATION_NOT_FOUND", "关联不存在")
    db.delete(rel)
    db.commit()
```

import 区补 `conflict`：`from app.errors import bad_request, conflict, not_found`。

- [ ] **Step 7: 路由** —— `app/routers/work_orders.py`：schema import 加 `WorkOrderRelationCreate, WorkOrderRelationRead`，新增端点（放在 activities 端点前）：

```python
@router.get("/{work_order_id}/relations", response_model=list[WorkOrderRelationRead])
def list_relations(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_VIEW)),
) -> list[dict[str, object]]:
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    return svc.list_relations(db, wo)


@router.post("/{work_order_id}/relations", response_model=WorkOrderRelationRead, status_code=201)
def create_relation(
    work_order_id: str,
    payload: WorkOrderRelationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> dict[str, object]:
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    rel = svc.create_relation(
        db,
        wo,
        payload.target_work_order_id,
        payload.relation_type,
        current_user.company_id,
        actor_user_id=current_user.id,
    )
    # 复用双向展开以返回带 direction 的视图
    for item in svc.list_relations(db, wo):
        if item["id"] == rel.id:
            return item
    raise not_found("WORKORDER_RELATION_NOT_FOUND", "关联不存在")


@router.delete(
    "/{work_order_id}/relations/{relation_id}", status_code=204, response_model=None
)
def delete_relation(
    work_order_id: str,
    relation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> None:
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    svc.delete_relation(db, wo, relation_id, current_user.company_id)
```

- [ ] **Step 8: 跑绿** `pytest tests/test_work_order_relations.py -v` → PASS。门禁同上。

- [ ] **Step 9: Commit**

```bash
git add app/models/work_order_status.py app/models/work_order.py app/schemas/work_order.py app/services/work_order_service.py app/routers/work_orders.py tests/test_work_order_relations.py
git commit -m "feat(wo-2b): WorkOrderRelation model + bidirectional CRUD API"
```

---

## Task 5: 按备件反查工单（LIST part_id 过滤）

**Files:**
- Modify: `app/services/work_order_service.py:179-208`（list_work_orders）
- Modify: `app/routers/work_orders.py:48-68`（LIST 端点）
- Test: `tests/test_work_order_part_lookup.py`

- [ ] **Step 1: 写失败测试** `tests/test_work_order_part_lookup.py`

```python
from app import tenant
from app.models.part_consumption import PartConsumption
from app.services import work_order_service as svc


def _admin(client, company="Acme", email="a@a.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "A"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _company_id(db, slug):
    from app.models.company import Company

    return db.execute(Company.__table__.select().where(Company.slug == slug)).first().id


def test_list_filtered_by_part(client, db):
    t = _admin(client)
    h = _h(t)
    cid = _company_id(db, "acme")
    a = client.post("/api/v1/work-orders", headers=h, json={"title": "A"}).json()["id"]
    client.post("/api/v1/work-orders", headers=h, json={"title": "B"})
    # a 消耗了 part p1
    tenant.set_current_company_id(cid)
    db.add(
        PartConsumption(
            part_id="p1", work_order_id=a, quantity=1, unit_cost=1, company_id=cid
        )
    )
    db.commit()
    rows = client.get("/api/v1/work-orders?part_id=p1", headers=h).json()
    assert {r["title"] for r in rows} == {"A"}


def test_list_part_filter_tenant_isolated(client, db):
    ta = _admin(client, "Acme", "a@a.com")
    tb = _admin(client, "Beta", "b@b.com")
    cid_a = _company_id(db, "acme")
    a = client.post("/api/v1/work-orders", headers=_h(ta), json={"title": "A"}).json()["id"]
    tenant.set_current_company_id(cid_a)
    db.add(
        PartConsumption(
            part_id="p1", work_order_id=a, quantity=1, unit_cost=1, company_id=cid_a
        )
    )
    db.commit()
    # Beta 用同样 part_id 查不到 Acme 的工单
    rows = client.get("/api/v1/work-orders?part_id=p1", headers=_h(tb)).json()
    assert rows == []
```

- [ ] **Step 2: 跑红** `pytest tests/test_work_order_part_lookup.py -v` → FAIL（未知参数 part_id 被忽略 → A、B 都返回，断言失败）。

- [ ] **Step 3: service** —— `app/services/work_order_service.py` list_work_orders 加参数与过滤：import 加 `from app.models.part_consumption import PartConsumption`；签名加 `part_id: str | None = None`；在 `if assignee_id is not None:` 块后加：

```python
    if part_id is not None:
        sub = select(PartConsumption.work_order_id).where(PartConsumption.part_id == part_id)
        stmt = stmt.where(WorkOrder.id.in_(sub))
```

> 租户隔离：`get_db` 已注入租户上下文，PartConsumption/WorkOrder 查询自动按 company 过滤（与既有 list 一致）。

- [ ] **Step 4: 路由** —— `app/routers/work_orders.py` LIST 端点签名加 `part_id: str | None = None`，并传入 `svc.list_work_orders(..., part_id=part_id)`。

- [ ] **Step 5: 跑绿** `pytest tests/test_work_order_part_lookup.py -v` → PASS。门禁同上。

- [ ] **Step 6: Commit**

```bash
git add app/services/work_order_service.py app/routers/work_orders.py tests/test_work_order_part_lookup.py
git commit -m "feat(wo-2b): list work orders filtered by consumed part_id"
```

---

## Task 6: Alembic 迁移（8 列 + relation 表）

**Files:**
- Create: `alembic/versions/20260604_0001_workorder_2b_backfill.py`
- Test: `tests/unit/test_migration_workorder_2b.py`

> 范式参照 `tests/unit/test_migration_inventory_backfill.py`：用 `importlib.import_module` 加载数字开头的迁移模块（不能用 `import` 语句），手建父表后以 `MigrationContext`/`Operations.context` 跑 `upgrade()`→断言→`downgrade()`→断言镜像。

- [ ] **Step 1: 写失败测试** `tests/unit/test_migration_workorder_2b.py`

```python
"""迁移 workorder_2b_backfill：链路 + up/down 可重放（SQLite）。"""

import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def _mod():
    return importlib.import_module("alembic.versions.20260604_0001_workorder_2b_backfill")


def test_revision_chain():
    m = _mod()
    assert m.revision == "workorder_2b_backfill"
    assert m.down_revision == "inventory_backfill"


def test_upgrade_downgrade_sqlite():
    eng = create_engine("sqlite://")
    new_cols = {
        "completed_by_user_id",
        "feedback",
        "urgent",
        "estimated_duration",
        "estimated_start_date",
        "first_responded_at",
        "archived",
        "is_compliant",
    }
    with eng.begin() as conn:
        for tbl in ("tb_company", "tb_work_order"):
            conn.exec_driver_sql(f"CREATE TABLE {tbl} (id VARCHAR(36) PRIMARY KEY)")
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            _mod().upgrade()
            tables = set(inspect(conn).get_table_names())
            assert "tb_work_order_relation" in tables
            cols = {c["name"] for c in inspect(conn).get_columns("tb_work_order")}
            assert new_cols <= cols
            _mod().downgrade()
            tables2 = set(inspect(conn).get_table_names())
            assert "tb_work_order_relation" not in tables2
            cols2 = {c["name"] for c in inspect(conn).get_columns("tb_work_order")}
            assert new_cols.isdisjoint(cols2)
    eng.dispose()
```

- [ ] **Step 2: 跑红** `pytest tests/unit/test_migration_workorder_2b.py -v` → FAIL（ModuleNotFoundError：迁移文件尚未创建）。

- [ ] **Step 3: 写迁移** `alembic/versions/20260604_0001_workorder_2b_backfill.py`

```python
"""work order 2B backfill: WorkOrder 加 8 列 + tb_work_order_relation

Revision ID: workorder_2b_backfill
Revises: inventory_backfill
Create Date: 2026-06-04

手工撰写（MySQL 生产 + SQLite 开发/测试）。
- tb_work_order 加 8 列（batch_alter_table，SQLite 表重建安全）：
  completed_by_user_id / feedback / urgent / estimated_duration /
  estimated_start_date / first_responded_at / archived / is_compliant；
- 新建 tb_work_order_relation（UUID+Timestamp+Tenant，单有向记录）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.base import DATETIME6

revision: str = "workorder_2b_backfill"
down_revision: str | Sequence[str] | None = "inventory_backfill"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tb_work_order") as batch_op:
        batch_op.add_column(sa.Column("completed_by_user_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("feedback", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("urgent", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch_op.add_column(sa.Column("estimated_duration", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("estimated_start_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("first_responded_at", DATETIME6, nullable=True))
        batch_op.add_column(
            sa.Column("archived", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch_op.add_column(sa.Column("is_compliant", sa.Boolean(), nullable=True))

    op.create_table(
        "tb_work_order_relation",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("tb_company.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_work_order_id",
            sa.String(length=36),
            sa.ForeignKey("tb_work_order.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_work_order_id",
            sa.String(length=36),
            sa.ForeignKey("tb_work_order.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "relation_type",
            sa.Enum("DUPLICATE", "RELATED", "SPLIT", "BLOCKS", name="workorderrelationtype"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.UniqueConstraint(
            "source_work_order_id",
            "target_work_order_id",
            "relation_type",
            name="uq_work_order_relation",
        ),
    )
    op.create_index(
        "ix_tb_work_order_relation_company_id", "tb_work_order_relation", ["company_id"]
    )
    op.create_index(
        "ix_tb_work_order_relation_source_work_order_id",
        "tb_work_order_relation",
        ["source_work_order_id"],
    )
    op.create_index(
        "ix_tb_work_order_relation_target_work_order_id",
        "tb_work_order_relation",
        ["target_work_order_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tb_work_order_relation_target_work_order_id", table_name="tb_work_order_relation"
    )
    op.drop_index(
        "ix_tb_work_order_relation_source_work_order_id", table_name="tb_work_order_relation"
    )
    op.drop_index("ix_tb_work_order_relation_company_id", table_name="tb_work_order_relation")
    op.drop_table("tb_work_order_relation")

    with op.batch_alter_table("tb_work_order") as batch_op:
        batch_op.drop_column("is_compliant")
        batch_op.drop_column("archived")
        batch_op.drop_column("first_responded_at")
        batch_op.drop_column("estimated_start_date")
        batch_op.drop_column("estimated_duration")
        batch_op.drop_column("urgent")
        batch_op.drop_column("feedback")
        batch_op.drop_column("completed_by_user_id")
```

- [ ] **Step 4: 跑绿** `pytest tests/unit/test_migration_workorder_2b.py -v` → PASS。门禁同上。

- [ ] **Step 5: 校验迁移链单 head** `alembic heads`（应仅 `workorder_2b_backfill` 一个 head）。

- [ ] **Step 6: Commit**

```bash
git add alembic/versions/20260604_0001_workorder_2b_backfill.py tests/unit/test_migration_workorder_2b.py
git commit -m "feat(wo-2b): alembic migration for 8 columns + relation table"
```

---

## Task 7: 全量门禁收尾

- [ ] **Step 1: 全量回归** `pytest -q`（应全绿，新增测试计入；既有工单 API 测试不回归）。
- [ ] **Step 2: 门禁** `ruff check app tests && ruff format --check app tests && mypy app` → 全净。
- [ ] **Step 3: 迁移链单 head 复核** `alembic heads` → 单 head `workorder_2b_backfill`。
- [ ] **Step 4: Commit（如有格式化改动）**

```bash
git add -A
git commit -m "chore(wo-2b): gate green + format wrap-up"
```

---

## Self-Review（写完即查，发现即修）

**Spec 覆盖核对：**
- 8 字段族 → Task 1 + Task 6 ✓
- transition 钩子（completed_by/is_compliant 快照/first_responded_at/reopen 清空）→ Task 2 ✓
- canBeEditedBy 谓词（角色+终态+归属，仅锁 PATCH）+ can_be_edited 响应 → Task 3 ✓
- WorkOrderRelation（单有向+双向展开，自指/重复/跨租户校验，3 端点）→ Task 4 ✓
- 按备件反查（LIST part_id，租户隔离）→ Task 5 ✓
- 迁移（8 列+relation 表，up/down 可重放）→ Task 6 ✓
- 跨租户对抗（relation target 404 / part 过滤隔离 / can_edit 不泄漏）→ Task 4/5 + Task 3 service 单测 ✓

**类型一致性：** `can_edit_work_order(db, user, wo)` 三参在 service 定义、router 调用、to_read 调用一致；`to_read(db, wo, viewer=None)` 新签名所有 router 调用点已统一传 `viewer=current_user`；`list_relations` 返回 dict 列表，`WorkOrderRelationRead` 字段名（direction/related_work_order_id/related_custom_id/related_title/related_status）与 service 组装键逐一对应。

**占位扫描：** 无 TBD/TODO；每个 code step 均含完整代码。Task 6 测试已对齐仓库既有迁移测试范式（`tests/unit/test_migration_inventory_backfill.py`：importlib 加载 + MigrationContext/Operations.context 跑 up/down）。
