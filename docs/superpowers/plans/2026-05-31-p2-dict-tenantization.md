# P2 动态字典三表租户化（NullableTenantMixin + 复合唯一 + 隔离/IDOR 验证）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 P1 落地的三张字典表（`tb_heading_style_rule` / `tb_numbering_profile` / `tb_heading_learning_event`）加挂主线既有的 `NullableTenantMixin`（得 `company_id`），唯一约束改复合 `(company_id, style_name)` / `(company_id, pattern_key)`，并以测试**验证** ORM 事件级隔离（`tenant_isolation.py` 的 `before_flush` 自动盖 `company_id`、`do_orm_execute` 自动给 SELECT 加 `company_id` 过滤）确实覆盖：投票聚合、注入查询、`get_or_404`（IDOR）。覆盖不到的路径显式补 `company_id` 过滤。

**Architecture:** 加挂 mixin 后隔离**几乎免费**——主线 ORM 事件已对所有 `TenantScoped` 子类生效。本 plan 核心不是写隔离逻辑，而是**用对抗性测试证明隔离真的生效**（两租户互不串、跨租户 id→404），并对 ORM 事件覆盖不到的查询（若有）补显式过滤。迁移须用 `batch_alter_table`（SQLite 改唯一约束须重建表）。

**Tech Stack:** SQLAlchemy 2.0（`with_loader_criteria` 自动注入）、Alembic batch、pytest（`tenant.set_current_company_id` 设上下文）。

**前置：** P1a–P1e 全部落地（三表 + service + 注入 + 钩子已在主线）。

---

## File Structure
- `backend/app/models/heading_rule.py`（modify：+`NullableTenantMixin`、复合唯一）
- `backend/app/models/numbering_profile.py`（modify：同上）
- `backend/app/models/heading_learning_event.py`（modify：+`NullableTenantMixin`、索引含 company_id）
- `backend/alembic/versions/20260531_0012_dict_tenantization.py`（author：三表 batch alter）
- `backend/tests/integration/test_dict_tenant_isolation.py`（author：隔离 + IDOR 对抗测试）
- 可能：`heading_rule_service.py` / `heading_learning_service.py`（仅当 Task5 验证发现 ORM 事件未覆盖时补显式过滤）

---

## Task 1: 三表模型加挂 NullableTenantMixin + 复合唯一

**Files:**
- Modify: `backend/app/models/heading_rule.py`、`numbering_profile.py`、`heading_learning_event.py`

- [ ] **Step 1: heading_rule.py**

import 改：`from app.models.base import Base, NullableTenantMixin, SoftDeleteMixin, TimestampMixin, UUIDMixin`
类声明改：

```python
class HeadingStyleRule(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, NullableTenantMixin):
```

`style_name` 去掉 `unique=True`：

```python
    style_name: Mapped[str] = mapped_column(String(255))
```

类体末尾加复合唯一：

```python
    from sqlalchemy import UniqueConstraint  # 移到文件顶部 import 区
    __table_args__ = (
        UniqueConstraint("company_id", "style_name", name="uq_heading_style_rule_company_style"),
    )
```

- [ ] **Step 2: numbering_profile.py**

同法加 `NullableTenantMixin`，`pattern_key` 去 `unique=True`，加：

```python
    __table_args__ = (
        UniqueConstraint("company_id", "pattern_key", name="uq_numbering_profile_company_pattern"),
    )
```

- [ ] **Step 3: heading_learning_event.py**

类声明加 `NullableTenantMixin`，并把既有复合索引扩为含 company_id（投票按租户分区的索引基础）：

```python
class HeadingLearningEvent(Base, NullableTenantMixin):
    ...
    __table_args__ = (
        Index(
            "ix_tb_heading_learning_event_company_style_proc",
            "company_id", "style_name", "procedure_id",
        ),
    )
```

- [ ] **Step 4: import 校验**

Run: `cd backend && python -c "import app.models; from app.models.heading_rule import HeadingStyleRule; print(hasattr(HeadingStyleRule, 'company_id'))"`
Expected: `True`。

- [ ] **Step 5: 提交**

```bash
git add backend/app/models/heading_rule.py backend/app/models/numbering_profile.py backend/app/models/heading_learning_event.py
git commit -m "feat(tenant): 字典三表加挂 NullableTenantMixin + 复合唯一 (P2 Task1)"
```

---

## Task 2: 迁移（batch alter，三表加 company_id + 改唯一）

**Files:**
- Create: `backend/alembic/versions/20260531_0012_dict_tenantization.py`

- [ ] **Step 1: 新建迁移**

```python
"""dict 三表租户化：+company_id + 复合唯一（SQLite batch 重建）

Revision ID: dict_tenantization
Revises: numbering_profile
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "dict_tenantization"
down_revision: str | Sequence[str] | None = "numbering_profile"
branch_labels = None
depends_on = None

_COMPANY_FK = sa.ForeignKey("tb_company.id", ondelete="CASCADE")


def _add_company(table: str, *, old_unique: str | None, new_unique: tuple[str, str] | None,
                 new_uq_name: str | None) -> None:
    with op.batch_alter_table(table, recreate="always") as b:
        b.add_column(sa.Column("company_id", sa.String(length=36), nullable=True))
        b.create_index(f"ix_{table}_company_id", ["company_id"])
        if old_unique:
            b.drop_constraint(old_unique, type_="unique")
        if new_unique and new_uq_name:
            b.create_unique_constraint(new_uq_name, list(new_unique))
        b.create_foreign_key(f"fk_{table}_company", "tb_company", ["company_id"], ["id"],
                             ondelete="CASCADE")


def upgrade() -> None:
    _add_company("tb_heading_style_rule",
                 old_unique="uq_heading_style_rule_style_name",
                 new_unique=("company_id", "style_name"),
                 new_uq_name="uq_heading_style_rule_company_style")
    _add_company("tb_numbering_profile",
                 old_unique="uq_numbering_profile_pattern_key",
                 new_unique=("company_id", "pattern_key"),
                 new_uq_name="uq_numbering_profile_company_pattern")
    # 事件表无唯一约束，仅加列 + 复合索引
    with op.batch_alter_table("tb_heading_learning_event", recreate="always") as b:
        b.add_column(sa.Column("company_id", sa.String(length=36), nullable=True))
        b.create_index("ix_tb_heading_learning_event_company_style_proc",
                       ["company_id", "style_name", "procedure_id"])
        b.create_foreign_key("fk_tb_heading_learning_event_company", "tb_company",
                             ["company_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    with op.batch_alter_table("tb_heading_learning_event", recreate="always") as b:
        b.drop_column("company_id")
    with op.batch_alter_table("tb_numbering_profile", recreate="always") as b:
        b.drop_constraint("uq_numbering_profile_company_pattern", type_="unique")
        b.create_unique_constraint("uq_numbering_profile_pattern_key", ["pattern_key"])
        b.drop_column("company_id")
    with op.batch_alter_table("tb_heading_style_rule", recreate="always") as b:
        b.drop_constraint("uq_heading_style_rule_company_style", type_="unique")
        b.create_unique_constraint("uq_heading_style_rule_style_name", ["style_name"])
        b.drop_column("company_id")
```

> `recreate="always"` 让 SQLite 走重建表路径（改约束必需）；MySQL 上 batch 亦兼容。`old_unique` 约束名须与 P1b/P1d 迁移里建的名字一致。

- [ ] **Step 2: 双向跑通**

Run: `cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head`
Expected: 无错；三表均有 `company_id` 列与新复合唯一。

- [ ] **Step 3: 提交**

```bash
git add backend/alembic/versions/20260531_0012_dict_tenantization.py
git commit -m "feat(tenant): 字典三表 company_id + 复合唯一迁移(batch) (P2 Task2)"
```

---

## Task 3: 验证两租户隔离（同名样式互不投票/覆盖）

**Files:**
- Create: `backend/tests/integration/test_dict_tenant_isolation.py`

- [ ] **Step 1: 写隔离测试（显式设租户上下文）**

```python
"""动态字典多租户隔离 + IDOR 对抗测试（P2）。

依赖主线 tenant_isolation ORM 事件：before_flush 自动盖 company_id、
do_orm_execute 自动给 SELECT 加 company_id 过滤。本测试证明隔离真生效。
"""
from __future__ import annotations

import pytest

from app import tenant
from app.models.company import Company
from app.schemas.heading_rule import HeadingRuleCreate
from app.services import heading_rule_service as svc


@pytest.fixture
def two_companies(db):
    a = Company(name="A公司")
    b = Company(name="B公司")
    db.add_all([a, b]); db.flush()
    return a.id, b.id


def test_same_style_name_isolated_per_tenant(db, two_companies) -> None:
    a, b = two_companies
    # A 公司：章节标题=1
    tenant.set_current_company_id(a)
    svc.create(db, HeadingRuleCreate(style_name="章节标题", level=1)); db.flush()
    assert svc.active_style_overrides(db) == {"章节标题": 1}
    # B 公司：同名 章节标题=2（复合唯一允许共存）
    tenant.set_current_company_id(b)
    svc.create(db, HeadingRuleCreate(style_name="章节标题", level=2)); db.flush()
    assert svc.active_style_overrides(db) == {"章节标题": 2}  # 只见 B 的
    # 回到 A：仍是 1，未被 B 污染
    tenant.set_current_company_id(a)
    assert svc.active_style_overrides(db) == {"章节标题": 1}
    assert len(svc.list_rules(db)) == 1  # A 只见自己一条


def test_cross_tenant_get_returns_404(db, two_companies) -> None:
    a, b = two_companies
    tenant.set_current_company_id(a)
    rule = svc.create(db, HeadingRuleCreate(style_name="A私有", level=1)); db.flush()
    rid = rule.id
    # B 公司拿 A 的 id → get_or_404 应找不到（do_orm_execute 过滤掉）
    tenant.set_current_company_id(b)
    from app.errors import AppError  # 按实际基类调整
    with pytest.raises(AppError):
        svc.get_or_404(db, rid)
```

- [ ] **Step 2: 跑测试**

Run: `cd backend && python -m pytest tests/integration/test_dict_tenant_isolation.py -v`
Expected: 全 PASS。
**若 `test_cross_tenant_get_returns_404` 失败**（`db.get()` 绕过 `do_orm_execute`）→ 进入 Task 5 补显式过滤。
**若 `active_style_overrides` 串租户**（聚合 SELECT 未被自动过滤）→ 同样进 Task 5。

- [ ] **Step 3: 提交**

```bash
git add backend/tests/integration/test_dict_tenant_isolation.py
git commit -m "test(tenant): 字典两租户隔离 + IDOR 对抗测试 (P2 Task3)"
```

---

## Task 4: 验证投票聚合按租户分区

**Files:**
- Modify: `backend/tests/integration/test_dict_tenant_isolation.py`（追加）

- [ ] **Step 1: 写"A 公司纠偏不污染 B 公司规则"测试**

```python
from app.models.node import ProcedureNode
from app.services import heading_learning_service as learn


def _styled_node(db, pid, level, company_id, style="章节标题"):
    tenant.set_current_company_id(company_id)
    n = ProcedureNode(procedure_id=pid, kind="chapter", heading_level=level,
                      title="x", body="", mark_status="unmarked", source_style_name=style)
    db.add(n); db.flush()
    return n


def test_reaggregate_partitioned_by_tenant(db, two_companies) -> None:
    a, b = two_companies
    # A 公司 3 文档一致把「章节标题」改 L2 → A 规则应 active L2
    for i in range(3):
        node = _styled_node(db, f"a-{i}", 2, a)
        learn.observe_node_edit(db, node, old_level=1, old_mark="unmarked")
    tenant.set_current_company_id(a)
    rule_a = learn.reaggregate(db, "章节标题")
    assert rule_a.status == "active" and rule_a.level == 2
    # B 公司：无任何事件 → reaggregate 不应受 A 的事件影响
    tenant.set_current_company_id(b)
    rule_b = learn.reaggregate(db, "章节标题")
    # B 无证据 → 无规则或非 active（绝不继承 A 的 L2）
    assert rule_b is None or rule_b.status != "active" or rule_b.level != 2
```

- [ ] **Step 2: 跑**

Run: `cd backend && python -m pytest tests/integration/test_dict_tenant_isolation.py::test_reaggregate_partitioned_by_tenant -v`
Expected: PASS。**若失败**（reaggregate 的 `select(HeadingLearningEvent...)` / `select(ProcedureNode...)` 未按租户过滤）→ Task 5。

- [ ] **Step 3: 提交**

```bash
git add backend/tests/integration/test_dict_tenant_isolation.py
git commit -m "test(tenant): 投票聚合按租户分区验证 (P2 Task4)"
```

---

## Task 5: 补洞（仅当 Task3/4 暴露 ORM 事件未覆盖的查询）

**Files:**
- Modify（按需）: `backend/app/services/heading_rule_service.py`、`numbering_profile_service.py`、`heading_learning_service.py`

- [ ] **Step 1: 若 IDOR（db.get）未被覆盖 → get_or_404 改显式归属**

把 `db.get(HeadingStyleRule, rule_id)` 改为带 company 过滤的 query：

```python
from app import tenant

def get_or_404(db: Session, rule_id: str) -> HeadingStyleRule:
    q = select(HeadingStyleRule).where(
        HeadingStyleRule.id == rule_id, HeadingStyleRule.is_active.is_(True)
    )
    cid = tenant.get_current_company_id()
    if cid is not None:
        q = q.where(HeadingStyleRule.company_id == cid)
    rule = db.scalars(q).first()
    if rule is None:
        raise not_found("HEADING_RULE_NOT_FOUND", "样式规则不存在", field="id")
    return rule
```

`numbering_profile_service.get_or_404` 同法。

- [ ] **Step 2: 若聚合/注入未被覆盖 → 显式加 company_id 过滤**

在 `reaggregate` 的 `select(HeadingLearningEvent.procedure_id...)`、`select(ProcedureNode.heading_level...)`、`active_style_overrides`/`active_numbering_overrides` 的 select 上，按 `tenant.get_current_company_id()` 非 None 时追加 `.where(Model.company_id == cid)`。

- [ ] **Step 3: 重跑 Task3/4 全绿**

Run: `cd backend && python -m pytest tests/integration/test_dict_tenant_isolation.py -v`
Expected: 全 PASS。

- [ ] **Step 4: 提交（仅当本 Task 有改动）**

```bash
git add -A && git commit -m "fix(tenant): 补 ORM 事件未覆盖的字典查询显式 company 过滤 (P2 Task5)" || echo "ORM 事件已全覆盖，无需补洞"
```

---

## Task 6: 全量回归 + golden 不变 + lint

- [ ] **Step 1: 解析 golden 不变（评估在无租户上下文跑，company_id=None → 隔离短路）**

Run: `cd backend && python -m pytest tests/regression -v`
Expected: PASS。

- [ ] **Step 2: 全量后端 + 既有租户隔离用例不退化**

Run: `cd backend && python -m pytest -q`
Expected: 全 PASS（含主线既有 CMMS/SOP 租户测试）。

- [ ] **Step 3: ruff + 迁移幂等复查**

Run: `cd backend && ruff check app/models tests/integration/test_dict_tenant_isolation.py && alembic downgrade base && alembic upgrade head`
Expected: 无 error；全链迁移可从空库重建。

- [ ] **Step 4: 提交（如有修正）**

```bash
git add -A && git commit -m "chore(tenant): ruff + 迁移复查 (P2 Task6)" || echo "无需提交"
```

---

## Self-Review 记录
- **Spec 覆盖**：实现 spec §4.1（三表挂 mixin + 复合唯一）、§5（投票分区/IDOR 验证与补洞）、§3.5（SQLite batch 重建）。
- **占位符**：无 TBD。Task5 是**条件补洞**（仅当 Task3/4 测试暴露 ORM 事件覆盖缺口才执行，含完整替换代码），是 spec §5/§9 明确标注的"必须验证、证伪则补"——非占位符。
- **类型一致**：三表 `company_id` 经 `NullableTenantMixin`；migration `revision="dict_tenantization"`/`down="numbering_profile"` 链正确；约束名与 P1b/P1d 一致。
- **对抗性验证优先**：核心交付是"证明隔离生效"的测试（两租户互不串 + 跨租户 404 + 投票分区），而非假设 ORM 事件必然覆盖——符合 spec §9"do_orm_execute 覆盖面是唯一可能失效点，需最先验证"。
- **零回归**：golden 不变（评估无租户上下文）；全量后端不退化。
