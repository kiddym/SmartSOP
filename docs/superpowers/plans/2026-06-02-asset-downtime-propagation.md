# 资产补全 ③ 停机树传播 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 资产停机持久级联（向下为主）+ 状态驱动的自动停机触发：资产状态跨越 UP↔DOWN 边界时自动登记/关闭停机记录，并向后代级联与反转。

**Architecture:** 所有副作用由 `update_asset` 检测 `status` 跃迁后调用公共函数 `apply_status_transition` 触发。`AssetDowntime` 加 `source_asset_id`/`prior_status` 两列承载级联溯源与还原。复用既有 `_descendant_ids`（BFS 收全部 active 后代）。不变量：自动/级联管理下，资产 DOWN ⟺ 至少一条 open 停机记录。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Pydantic v2 + Alembic + pytest（SQLite in-memory）。解释器 `backend/.venv/bin/python`；门禁 `ruff check app/` + `mypy app/`。

**全局约定（每任务适用）：**
- 工作目录 `backend/`；命令前缀 `.venv/bin/`。
- 每任务：写失败测试 → 跑红 → 最小实现 → 跑绿 → ruff + mypy 绿 → commit。
- commit message 结尾附：`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- 净室原创、仅中文。
- **文件边界（硬约束）**：本轮**绝不修改** `app/services/analytics/**` 或 `app/routers/analytics.py`（并行的分析补全 agent 正占用）。
- 多租户：`AssetDowntime` 已挂 TenantMixin；`_descendant_ids`/查询经 ORM 自动 company scope。

---

## File Structure

| 文件 | 责任 | 任务 |
|---|---|---|
| `app/models/asset_downtime.py` | 加 source_asset_id / prior_status 两列 | T1 |
| `app/schemas/asset.py` | DowntimeRead 暴露 source_asset_id | T1 |
| `app/services/maintenance_asset_service.py` | apply_status_transition + 自动触发 + 级联/反转 + update_asset 接线 | T2,T3 |
| `tests/test_asset_downtime_auto.py` | 自动触发测试 | T2 |
| `tests/test_asset_downtime_cascade.py` | 级联/反转/边界/跨租户测试 | T3,T4 |
| `alembic/versions/20260602_0005_asset_downtime_propagation.py` | 加两列迁移 | T5 |
| `tests/unit/test_migration_asset_downtime.py` | 迁移单测 | T5 |

测试 harness（复制到各新测试文件顶部，与 test_assets_api.py 一致）：
```python
def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}
```

API 速查：建资产 `POST /api/v1/assets {name, parent_id?}`（status 默认 OPERATIONAL）；改状态 `PATCH /api/v1/assets/{id} {status:"DOWN"}`；停机 `POST /api/v1/assets/{id}/downtimes {started_at,...}`、`GET /api/v1/assets/{id}/downtimes`。

---

## Task 1: 模型加列 + DowntimeRead 暴露

**Files:**
- Modify: `app/models/asset_downtime.py`
- Modify: `app/schemas/asset.py`
- Test: `tests/test_asset_downtime_model.py`

- [ ] **Step 1: 写失败测试**

`tests/test_asset_downtime_model.py`：
```python
"""AssetDowntime 新列 source_asset_id / prior_status 存在且可读写。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.models.asset_downtime import AssetDowntime
from app.models.company import Company


def test_new_columns_roundtrip(db):
    co = Company(name="Acme", slug="acme")
    db.add(co)
    db.flush()
    dt = AssetDowntime(
        asset_id="a1", started_at=datetime.utcnow(), downtime_type="cascade",
        source_asset_id="parent-1", prior_status="STANDBY", company_id=co.id,
    )
    db.add(dt)
    db.commit()
    row = db.execute(select(AssetDowntime)).scalar_one()
    assert row.source_asset_id == "parent-1"
    assert row.prior_status == "STANDBY"
```
> 核对 Company 构造必填（name/slug）；若不同按 `app/models/company.py` 调整。

- [ ] **Step 2: 跑红**

Run: `.venv/bin/python -m pytest tests/test_asset_downtime_model.py -q`
Expected: FAIL（无 source_asset_id 属性）。

- [ ] **Step 3: 模型加列**

`app/models/asset_downtime.py`，在 `downtime_type` 列后加：
```python
    source_asset_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("tb_asset.id", ondelete="SET NULL"),
        default=None,
        index=True,
    )
    prior_status: Mapped[str | None] = mapped_column(String(20), default=None)
```
（`ForeignKey`/`String` 已在该文件 import。）

- [ ] **Step 4: schema 暴露**

`app/schemas/asset.py` 的 `DowntimeRead` 加字段：
```python
    source_asset_id: str | None = None
```

- [ ] **Step 5: 跑绿 + 门禁**

Run: `.venv/bin/python -m pytest tests/test_asset_downtime_model.py tests/test_assets_api.py -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: PASS（确认未破坏既有停机测试）。

- [ ] **Step 6: commit**

```bash
git add -A && git commit -m "feat(asset): AssetDowntime source_asset_id + prior_status columns

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: 自动停机触发（状态跃迁）

**Files:**
- Modify: `app/services/maintenance_asset_service.py`
- Test: `tests/test_asset_downtime_auto.py`

- [ ] **Step 1: 写失败测试**

`tests/test_asset_downtime_auto.py`（含 harness）：
```python
"""状态跃迁自动停机：UP->DOWN 建 open auto；DOWN->UP 关闭；同向不触发。"""

from __future__ import annotations


def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _downtimes(client, t, aid):
    return client.get(f"/api/v1/assets/{aid}/downtimes", headers=_h(t)).json()


def test_up_to_down_creates_open_auto(client):
    t = _admin(client)
    aid = client.post("/api/v1/assets", headers=_h(t), json={"name": "泵"}).json()["id"]
    client.patch(f"/api/v1/assets/{aid}", headers=_h(t), json={"status": "DOWN"})
    rows = _downtimes(client, t, aid)
    assert len(rows) == 1
    assert rows[0]["downtime_type"] == "auto"
    assert rows[0]["ended_at"] is None
    assert rows[0]["source_asset_id"] is None


def test_down_to_up_closes_auto(client):
    t = _admin(client)
    aid = client.post("/api/v1/assets", headers=_h(t), json={"name": "泵"}).json()["id"]
    client.patch(f"/api/v1/assets/{aid}", headers=_h(t), json={"status": "DOWN"})
    client.patch(f"/api/v1/assets/{aid}", headers=_h(t), json={"status": "OPERATIONAL"})
    rows = _downtimes(client, t, aid)
    assert len(rows) == 1
    assert rows[0]["ended_at"] is not None


def test_up_to_up_no_trigger(client):
    t = _admin(client)
    aid = client.post("/api/v1/assets", headers=_h(t), json={"name": "泵"}).json()["id"]
    # OPERATIONAL -> STANDBY 均属 UP，不应建停机
    client.patch(f"/api/v1/assets/{aid}", headers=_h(t), json={"status": "STANDBY"})
    assert _downtimes(client, t, aid) == []
```

- [ ] **Step 2: 跑红**

Run: `.venv/bin/python -m pytest tests/test_asset_downtime_auto.py -q`
Expected: FAIL（状态变更无副作用）。

- [ ] **Step 3: 实现**

`app/services/maintenance_asset_service.py`：
顶部 import 加：
```python
from app.models.asset_status import AssetStatus, DOWN_STATUSES
```
（ruff isort 字母序：`AssetStatus` 在 `DOWN_STATUSES` 前。）
加函数（放在 `# --- 停机 ---` 区前或后）：
```python
def _open_downtimes_for(db: Session, asset_id: str) -> list[AssetDowntime]:
    return list(
        db.execute(
            select(AssetDowntime).where(
                AssetDowntime.asset_id == asset_id, AssetDowntime.ended_at.is_(None)
            )
        )
        .scalars()
        .all()
    )


def _go_down(db: Session, asset: Asset, company_id: str) -> None:
    now = utcnow()
    db.add(
        AssetDowntime(
            asset_id=asset.id, downtime_type="auto", source_asset_id=None,
            started_at=now, company_id=company_id,
        )
    )
    # 向下级联（T3 填充；T2 先留空体以便自动触发测试通过）


def _recover(db: Session, asset: Asset, company_id: str) -> None:
    now = utcnow()
    for dt in _open_downtimes_for(db, asset.id):
        if dt.source_asset_id is None and dt.downtime_type == "auto":
            dt.ended_at = now
    # 级联反转（T3 填充）


def apply_status_transition(
    db: Session, asset: Asset, old_status: AssetStatus, new_status: AssetStatus, company_id: str
) -> None:
    was_down = old_status in DOWN_STATUSES
    now_down = new_status in DOWN_STATUSES
    if not was_down and now_down:
        _go_down(db, asset, company_id)
    elif was_down and not now_down:
        _recover(db, asset, company_id)
    # UP->UP / DOWN->DOWN：无副作用
```
`update_asset`：捕获 old_status 并在 setattr 后调用。改为：
```python
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
    old_status = a.status
    for k, v in data.items():
        setattr(a, k, v)
    if "status" in data:
        apply_status_transition(db, a, old_status, a.status, company_id)
    _sync_relations(db, a, user_ids, team_ids_, company_id)
    db.commit()
    db.refresh(a)
    return a
```

- [ ] **Step 4: 跑绿 + 门禁**

Run: `.venv/bin/python -m pytest tests/test_asset_downtime_auto.py tests/test_assets_api.py tests/test_asset_service.py -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: PASS。

- [ ] **Step 5: commit**

```bash
git add -A && git commit -m "feat(asset): auto downtime on status UP<->DOWN transition

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 向下级联 + 反转

**Files:**
- Modify: `app/services/maintenance_asset_service.py`
- Test: `tests/test_asset_downtime_cascade.py`

- [ ] **Step 1: 写失败测试**

`tests/test_asset_downtime_cascade.py`（含 harness）：
```python
"""向下级联与反转：父 DOWN -> 后代 DOWN + cascade 记录；父恢复 -> 后代还原。"""

from __future__ import annotations


def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _mk(client, t, name, parent=None):
    body = {"name": name}
    if parent:
        body["parent_id"] = parent
    return client.post("/api/v1/assets", headers=_h(t), json=body).json()["id"]


def _status(client, t, aid):
    return client.get(f"/api/v1/assets/{aid}", headers=_h(t)).json()["status"]


def _downtimes(client, t, aid):
    return client.get(f"/api/v1/assets/{aid}/downtimes", headers=_h(t)).json()


def test_cascade_down_and_recover(client):
    t = _admin(client)
    a = _mk(client, t, "A")
    b = _mk(client, t, "B", a)
    c = _mk(client, t, "C", b)  # A->B->C 三层
    # 把 C 原状态设为 STANDBY 以验 prior 还原
    client.patch(f"/api/v1/assets/{c}", headers=_h(t), json={"status": "STANDBY"})

    client.patch(f"/api/v1/assets/{a}", headers=_h(t), json={"status": "DOWN"})
    assert _status(client, t, b) == "DOWN"
    assert _status(client, t, c) == "DOWN"
    # B、C 各有一条 source=A 的 open cascade
    for child in (b, c):
        rows = _downtimes(client, t, child)
        assert any(r["downtime_type"] == "cascade" and r["source_asset_id"] == a
                   and r["ended_at"] is None for r in rows)

    client.patch(f"/api/v1/assets/{a}", headers=_h(t), json={"status": "OPERATIONAL"})
    assert _status(client, t, b) == "OPERATIONAL"   # prior=OPERATIONAL 还原
    assert _status(client, t, c) == "STANDBY"        # prior=STANDBY 还原
    # cascade 记录均已闭合
    for child in (b, c):
        assert all(r["ended_at"] is not None for r in _downtimes(client, t, child)
                   if r["downtime_type"] == "cascade")


def test_recover_keeps_independently_down_descendant(client):
    t = _admin(client)
    a = _mk(client, t, "A")
    b = _mk(client, t, "B", a)
    # B 先独立手动 open 停机（解耦：不改状态），再让父级联
    client.post(f"/api/v1/assets/{b}/downtimes", headers=_h(t),
                json={"started_at": "2026-05-01T00:00:00"})
    client.patch(f"/api/v1/assets/{a}", headers=_h(t), json={"status": "DOWN"})
    assert _status(client, t, b) == "DOWN"
    # 父恢复，但 B 仍有独立 open 手动停机 -> 维持 DOWN
    client.patch(f"/api/v1/assets/{a}", headers=_h(t), json={"status": "OPERATIONAL"})
    assert _status(client, t, b) == "DOWN"


def test_manual_downtime_decoupled(client):
    t = _admin(client)
    aid = _mk(client, t, "孤立")
    client.post(f"/api/v1/assets/{aid}/downtimes", headers=_h(t),
                json={"started_at": "2026-05-01T00:00:00"})
    assert _status(client, t, aid) == "OPERATIONAL"  # 手动停机不改状态
```

- [ ] **Step 2: 跑红**

Run: `.venv/bin/python -m pytest tests/test_asset_downtime_cascade.py -q`
Expected: FAIL（级联未实现：后代状态未变）。

- [ ] **Step 3: 实现 — 填充 `_go_down` 级联体**

`_go_down` 在建自身 auto 记录后追加：
```python
    for did in _descendant_ids(db, asset.id):
        d = db.get(Asset, did)
        if d is None or not d.is_active:
            continue
        if d.status in DOWN_STATUSES:
            db.add(
                AssetDowntime(
                    asset_id=d.id, downtime_type="cascade", source_asset_id=asset.id,
                    prior_status=None, started_at=now, company_id=company_id,
                )
            )
        else:
            prior = d.status.value
            d.status = AssetStatus.DOWN
            db.add(
                AssetDowntime(
                    asset_id=d.id, downtime_type="cascade", source_asset_id=asset.id,
                    prior_status=prior, started_at=now, company_id=company_id,
                )
            )
```

- [ ] **Step 4: 实现 — 填充 `_recover` 反转体**

`_recover` 在关闭自身 auto 后追加：
```python
    cascade_rows = list(
        db.execute(
            select(AssetDowntime).where(
                AssetDowntime.source_asset_id == asset.id, AssetDowntime.ended_at.is_(None)
            )
        )
        .scalars()
        .all()
    )
    affected: dict[str, str | None] = {}
    for dt in cascade_rows:
        dt.ended_at = now
        # 取每个后代首个非空 prior_status
        if dt.asset_id not in affected or (
            affected[dt.asset_id] is None and dt.prior_status is not None
        ):
            affected[dt.asset_id] = dt.prior_status
    db.flush()  # 让 ended_at 对随后的 open 复查可见
    for did, prior in affected.items():
        d = db.get(Asset, did)
        if d is None or not d.is_active:
            continue
        if _open_downtimes_for(db, did):
            continue  # 仍有独立 open 停机 -> 维持 DOWN
        d.status = AssetStatus(prior) if prior is not None else AssetStatus.OPERATIONAL
```

- [ ] **Step 5: 跑绿 + 门禁**

Run: `.venv/bin/python -m pytest tests/test_asset_downtime_cascade.py tests/test_asset_downtime_auto.py tests/test_assets_api.py -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: PASS。

- [ ] **Step 6: commit**

```bash
git add -A && git commit -m "feat(asset): downtime down-cascade to descendants + recovery reversal

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: 跨租户对抗 + 边界回归

**Files:**
- Modify: `tests/test_asset_downtime_cascade.py`（追加）
- Test: 同上

- [ ] **Step 1: 写失败/守护测试**

追加到 `tests/test_asset_downtime_cascade.py`：
```python
def test_cross_tenant_cascade_isolation(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    # 两租户各建 父->子
    a_parent = _mk(client, ta, "A父")
    a_child = _mk(client, ta, "A子", a_parent)
    b_parent = _mk(client, tb, "B父")
    b_child = _mk(client, tb, "B子", b_parent)
    # A 父停机
    client.patch(f"/api/v1/assets/{a_parent}", headers=_h(ta), json={"status": "DOWN"})
    # B 侧完全不受影响
    assert _status(client, tb, b_child) == "OPERATIONAL"
    assert _downtimes(client, tb, b_child) == []
    # A 子被级联
    assert _status(client, ta, a_child) == "DOWN"


def test_down_internal_switch_no_extra_record(client):
    t = _admin(client)
    aid = _mk(client, t, "泵")
    client.patch(f"/api/v1/assets/{aid}", headers=_h(t), json={"status": "DOWN"})
    n1 = len(_downtimes(client, t, aid))
    # DOWN -> EMERGENCY_SHUTDOWN 仍属 DOWN 类，不应再建记录
    client.patch(f"/api/v1/assets/{aid}", headers=_h(t), json={"status": "EMERGENCY_SHUTDOWN"})
    assert len(_downtimes(client, t, aid)) == n1
```

- [ ] **Step 2: 跑（应直接 PASS，作为守护）**

Run: `.venv/bin/python -m pytest tests/test_asset_downtime_cascade.py -q`
Expected: PASS（T3 实现已满足；若失败说明跃迁边界/租户 scope 有漏，修复实现）。

> 若 `test_down_internal_switch_no_extra_record` 失败，复查 `apply_status_transition` 的 DOWN→DOWN 分支确为 no-op。若跨租户测试失败，复查 `_descendant_ids` 是否经 ORM 自动 scope（应仅返回当前 company 后代）。

- [ ] **Step 3: 门禁 + commit**

Run: `.venv/bin/ruff check app/ && .venv/bin/mypy app/`
```bash
git add -A && git commit -m "test(asset): cross-tenant isolation + down-internal-switch guards

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: 迁移 + 单测 + 零漂移

**Files:**
- Create: `alembic/versions/20260602_0005_asset_downtime_propagation.py`
- Test: `tests/unit/test_migration_asset_downtime.py`

- [ ] **Step 1: 写失败测试**

`tests/unit/test_migration_asset_downtime.py`：
```python
"""迁移 asset_downtime_propagation：链路 + up/down 可重放（SQLite）。"""

import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def _mod():
    return importlib.import_module("alembic.versions.20260602_0005_asset_downtime_propagation")


def test_migration_revision_chain():
    m = _mod()
    assert m.revision == "asset_downtime_propagation"
    assert m.down_revision == "workorder_labor_cost"


def test_upgrade_then_downgrade_sqlite():
    eng = create_engine("sqlite://")
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE tb_asset (id VARCHAR(36) PRIMARY KEY)")
        conn.exec_driver_sql(
            "CREATE TABLE tb_asset_downtime (id VARCHAR(36) PRIMARY KEY, asset_id VARCHAR(36))"
        )
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            _mod().upgrade()
            cols = {c["name"] for c in inspect(conn).get_columns("tb_asset_downtime")}
            assert {"source_asset_id", "prior_status"} <= cols
            _mod().downgrade()
            cols2 = {c["name"] for c in inspect(conn).get_columns("tb_asset_downtime")}
            assert "source_asset_id" not in cols2 and "prior_status" not in cols2
```

- [ ] **Step 2: 跑红**

Run: `.venv/bin/python -m pytest tests/unit/test_migration_asset_downtime.py -q`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 迁移（batch 模式，SQLite 安全）**

`alembic/versions/20260602_0005_asset_downtime_propagation.py`：
```python
"""asset downtime propagation: tb_asset_downtime + source_asset_id + prior_status

Revision ID: asset_downtime_propagation
Revises: workorder_labor_cost
Create Date: 2026-06-02

Hand-authored (MySQL prod + SQLite dev/test)。给 tb_asset_downtime 加级联溯源两列。
全新列、无数据平移。

合并协调：本迁移与分析补全 analytics_backfill 都以 workorder_labor_cost 为 down_revision
（各自分支）。两分支合入 main 时，后合入者须把本 down_revision 改指向先合入者的 revision，
形成单一线性链（迁移单测只验 DDL，不依赖链顺序）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "asset_downtime_propagation"
down_revision: str | Sequence[str] | None = "workorder_labor_cost"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tb_asset_downtime") as batch:
        batch.add_column(sa.Column("source_asset_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("prior_status", sa.String(length=20), nullable=True))
        batch.create_index(
            batch.f("ix_tb_asset_downtime_source_asset_id"), ["source_asset_id"], unique=False
        )
        batch.create_foreign_key(
            batch.f("fk_tb_asset_downtime_source_asset_id"),
            "tb_asset",
            ["source_asset_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("tb_asset_downtime") as batch:
        batch.drop_constraint(
            batch.f("fk_tb_asset_downtime_source_asset_id"), type_="foreignkey"
        )
        batch.drop_index(batch.f("ix_tb_asset_downtime_source_asset_id"))
        batch.drop_column("prior_status")
        batch.drop_column("source_asset_id")
```
> batch 模式对 SQLite 安全（重建表实现 ALTER），对 MySQL 退化为直接 ALTER。若 SQLite 下 `drop_constraint` 仍报错（命名 FK 在重建表时已随表重建），可在 downgrade 省略 drop_constraint 仅 drop_column（实现者按单测结果调整；MySQL upgrade 的 FK 必须保留）。

- [ ] **Step 4: 跑绿**

Run: `.venv/bin/python -m pytest tests/unit/test_migration_asset_downtime.py -q`
Expected: PASS。

- [ ] **Step 5: 模型 vs 迁移对账 + 零漂移**

核对 `source_asset_id`（String36, nullable, index, FK SET NULL）与 `prior_status`（String20 nullable）同 `AssetDowntime` 模型。然后：
```bash
.venv/bin/alembic upgrade head && .venv/bin/alembic check
```
Expected: tb_asset_downtime 两新列零漂移（若 `alembic check` 报漂移仅应是既有 tb_procedure_* 历史问题，grep 确认新列不在漂移行）。若本地全链受既有 initial_schema 阻塞无法 upgrade head，以单测 DDL 为准（已于 docstring 声明），沿用 2A T6 做法。

- [ ] **Step 6: 全量回归 + 门禁**

Run: `.venv/bin/python -m pytest -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: 全 PASS / All checks passed。

- [ ] **Step 7: commit**

```bash
git add -A && git commit -m "feat(asset): migration for downtime source_asset_id + prior_status

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 收尾

完成 T1–T5 后派发最终 code review（subagent-driven 末步），再用 `superpowers:finishing-a-development-branch`。

**自查清单：**
- 无 `app/services/analytics/**` 或 `app/routers/analytics.py` 改动（文件边界硬约束）。
- 不变量：自动/级联下资产 DOWN ⟺ ≥1 条 open 停机记录。
- 手动停机解耦（不改 status、不级联）守住。
- 无 assert 控制生产流程（仅测试/mypy 缩窄）。
- 跨租户级联隔离已测。
- 迁移 down_revision 合并协调点已在 docstring 标注。
