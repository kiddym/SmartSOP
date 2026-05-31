# P1c 自学习闭环（事件表+学习service+node钩子，单租户）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移植动态字典的隐式学习闭环（M3）：`tb_heading_learning_event`（append-only 信号）+ `heading_learning_service`（`observe_node_edit` 采信号 + `reaggregate` 投票聚合）+ `node_service` 钩子（改级/确认后采集并重聚合）。并补齐 M2 前置——`ProcedureNode.source_style_name` 持久化（学习归因的硬前提）。**单租户**（投票全局聚合，租户分区留 P2）。落地后：3 份文档对同一样式一致改级 → 自动生成 `learned active` 规则 → 注入解析（越用越准）。

**Architecture:** 事件模型 + 学习 service 与 parser 线一致、可 `git checkout`（事件模型用裸 `Base`，单租户）。**`node.py` / `import_service.py` / `node_service.py` / `schemas/node.py` 绝不 checkout**——它们在主线含租户(`NullableTenantMixin`)与 CMMS 改动，parser 线版本会反向丢失（如 node.py 删了 `NullableTenantMixin`、import_service 夹带无关 `level_of_use`）。这些按 diff **外科增量补**。两处 schema 变更合入一个新迁移，链在 P1b 的 `heading_style_rule` 之后。

**Tech Stack:** Python 3.11+、SQLAlchemy 2.0（`BigInteger().with_variant(Integer,"sqlite")`）、Alembic、pytest。

**前置：** P1a（归因字段在 ParsedNode/Out）、P1b（`tb_heading_style_rule` + service + 注入）已落地。

---

## File Structure

- `backend/app/models/node.py`（**surgical**）：ProcedureNode **保留** `NullableTenantMixin`，**增** `source_style_name`
- `backend/app/schemas/node.py`（surgical）：`NodeOut.source_style_name`
- `backend/app/schemas/<import schema>.py`（surgical）：`ImportNodeIn.source_style_name`
- `backend/app/services/import_service.py`（surgical）：建节点写 `source_style_name`（**不带 `level_of_use`**）
- `backend/app/services/node_service.py`（surgical）：`_learn_from_edit` + patch/batch 接线 + get_nodes 暴露
- `backend/app/models/heading_learning_event.py`（port）：事件模型
- `backend/app/models/__init__.py`（modify）：注册 `HeadingLearningEvent`
- `backend/app/services/heading_learning_service.py`（port）：`observe_node_edit` + `reaggregate` + `K_DOCS`/`MIN_AGREEMENT`
- `backend/alembic/versions/20260531_0010_heading_learning.py`（author）：加列 + 建事件表
- `backend/tests/unit/services/test_heading_learning_service.py`（port/author）

---

## Task 1: ProcedureNode 增 source_style_name（保留租户 mixin）+ 迁移

**Files:**
- Modify: `backend/app/models/node.py`
- Create: `backend/alembic/versions/20260531_0010_heading_learning.py`

- [ ] **Step 1: 在 node.py 增列（不动 mixin）**

在 `backend/app/models/node.py` 的 `ProcedureNode` 中，`mark_status` 之后、`revision` 之前，加：

```python
    # 来源样式名（解析归因，动态标题字典方案 M2）：样式标题记 Word 样式显示名，供编辑器
    # 「记住此样式」与 M3 学习闭环反查到底是哪个样式被改级（None=非样式标题/零样式编号标题）。
    source_style_name: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
```

**务必保留** `class ProcedureNode(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, NullableTenantMixin)` 的 `NullableTenantMixin`（勿照搬 parser 线删除版）。

- [ ] **Step 2: 新建迁移（加列 + 建事件表一并完成）**

`backend/alembic/versions/20260531_0010_heading_learning.py`：

```python
"""ProcedureNode.source_style_name (M2) + tb_heading_learning_event (M3，单租户)

Revision ID: heading_learning
Revises: heading_style_rule
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "heading_learning"
down_revision: str | Sequence[str] | None = "heading_style_rule"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # M2：节点来源样式名（nullable，SQLite 加列无需 batch）
    op.add_column(
        "tb_procedure_node",
        sa.Column("source_style_name", sa.String(length=255), nullable=True),
    )
    # M3：学习事件表（append-only；BIGINT/SQLite INTEGER 自增）
    op.create_table(
        "tb_heading_learning_event",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
                  nullable=False, autoincrement=True),
        sa.Column("procedure_id", sa.String(length=36), nullable=False),
        sa.Column("node_id", sa.String(length=36), nullable=False),
        sa.Column("style_name", sa.String(length=255), nullable=False),
        sa.Column("signal_type", sa.String(length=30), nullable=False),
        sa.Column("from_level", sa.Integer(), nullable=True),
        sa.Column("to_level", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tb_heading_learning_event_procedure_id",
                    "tb_heading_learning_event", ["procedure_id"])
    op.create_index("ix_tb_heading_learning_event_style_name",
                    "tb_heading_learning_event", ["style_name"])
    op.create_index("ix_tb_heading_learning_event_style_name_procedure_id",
                    "tb_heading_learning_event", ["style_name", "procedure_id"])


def downgrade() -> None:
    op.drop_table("tb_heading_learning_event")
    op.drop_column("tb_procedure_node", "source_style_name")
```

- [ ] **Step 3: 迁移双向跑通**

Run: `cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head`
Expected: 无错。

- [ ] **Step 4: 提交**

```bash
git add backend/app/models/node.py backend/alembic/versions/20260531_0010_heading_learning.py
git commit -m "feat(dict): ProcedureNode.source_style_name + 事件表迁移(单租户) (P1c Task1)"
```

---

## Task 2: M2 持久化接线（import 写入 + 读暴露）

**Files:**
- Modify: `backend/app/schemas/node.py`、import schema、`backend/app/services/import_service.py`、`backend/app/services/node_service.py`

- [ ] **Step 1: NodeOut 暴露**

`backend/app/schemas/node.py` 的 `NodeOut` 中 `mark_status` 后加：

```python
    source_style_name: str | None = None  # 来源样式名（动态字典「记住此样式」归因，M2）
```

- [ ] **Step 2: ImportNodeIn 增字段**

定位 import 节点输入 schema（`grep -rn "class ImportNodeIn" backend/app/schemas/`），在其中加：

```python
    source_style_name: str | None = None
```

- [ ] **Step 3: import_service 写入（仅此一行，勿带 level_of_use 等无关改动）**

`backend/app/services/import_service.py` 中创建 `ProcedureNode`（chapter 节点）处，`mark_status=...` 之后加：

```python
                        source_style_name=n.source_style_name,
```

> ⚠️ parser 线该文件还夹带了无关的 `level_of_use` 形参改动——**不要移植**，只加 `source_style_name` 这一行。

- [ ] **Step 4: node_service.get_nodes 暴露**

`backend/app/services/node_service.py` 的 `get_nodes` 返回 dict 中 `"mark_status": r.mark_status,` 后加：

```python
                "source_style_name": r.source_style_name,
```

- [ ] **Step 5: 回归既有节点/导入测试**

Run: `cd backend && python -m pytest tests/unit/services -k "import or node" tests/integration -k "node or import or procedure" -q`
Expected: PASS（新字段默认 None，向下兼容）。

- [ ] **Step 6: 提交**

```bash
git add backend/app/schemas/node.py backend/app/services/import_service.py backend/app/services/node_service.py backend/app/schemas/
git commit -m "feat(dict): source_style_name 持久化(import写入+读暴露,M2) (P1c Task2)"
```

---

## Task 3: 移植事件模型 + 注册

**Files:**
- Port: `backend/app/models/heading_learning_event.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: 取模型（裸 Base，单租户版与分支一致）**

```bash
git checkout origin/feat/dynamic-heading-dictionary -- backend/app/models/heading_learning_event.py
```

- [ ] **Step 2: 注册**

`backend/app/models/__init__.py` 加：

```python
from app.models.heading_learning_event import HeadingLearningEvent
```

- [ ] **Step 3: import 校验**

Run: `cd backend && python -c "from app.models.heading_learning_event import HeadingLearningEvent; print('ok')"`
Expected: `ok`。

- [ ] **Step 4: 提交**

```bash
git add backend/app/models/heading_learning_event.py backend/app/models/__init__.py
git commit -m "feat(dict): 学习事件模型+注册(单租户) (P1c Task3)"
```

---

## Task 4: 移植学习 service

**Files:**
- Port: `backend/app/services/heading_learning_service.py`

- [ ] **Step 1: 取 service（分支版干净：依赖 node.source_style_name 已在 Task1 加）**

```bash
git checkout origin/feat/dynamic-heading-dictionary -- backend/app/services/heading_learning_service.py
```

- [ ] **Step 2: import 校验**

Run: `cd backend && python -c "from app.services import heading_learning_service as s; print(s.K_DOCS, s.MIN_AGREEMENT)"`
Expected: `3 0.8`。

- [ ] **Step 3: 提交**

```bash
git add backend/app/services/heading_learning_service.py
git commit -m "feat(dict): 学习service observe+reaggregate(投票护栏) (P1c Task4)"
```

---

## Task 5: node_service 学习钩子接线（surgical，按 diff）

**Files:**
- Modify: `backend/app/services/node_service.py`

- [ ] **Step 1: 加 import**

把 `from app.services import optimistic_lock` 与 `from app.services import node_numbering` 合并为：

```python
from app.services import heading_learning_service, node_numbering, optimistic_lock
```

- [ ] **Step 2: 加 `_learn_from_edit` 帮助器（放在 `_active_nodes` 之前）**

```python
def _learn_from_edit(
    db: Session, node: ProcedureNode, old_level: int | None, old_mark: str
) -> None:
    """采集样式标题校正信号并重聚合动态字典（M3 隐式学习；无来源样式名则 no-op）。"""
    style = heading_learning_service.observe_node_edit(
        db, node, old_level=old_level, old_mark=old_mark
    )
    if style:
        heading_learning_service.reaggregate(db, style)
```

- [ ] **Step 3: patch_node 接线**

在 `patch_node` 中，`enforce_node_invariants(...)` 之后、`for k, v in changes.items()` 之前加：

```python
    old_level, old_mark = node.heading_level, node.mark_status
```

并在 `node_numbering.recompute(db, node.procedure_id)` 之后加：

```python
    _learn_from_edit(db, node, old_level, old_mark)  # M3 隐式学习信号
```

- [ ] **Step 4: batch_update 接线**

在 `batch_update` 循环前加：

```python
    observed: list[tuple[ProcedureNode, int | None, str]] = []  # (node, old_level, old_mark) M3
```

在每个节点 `enforce_node_invariants(...)` 之后、`for k, v in changes.items()` 之前加：

```python
        observed.append((node, node.heading_level, node.mark_status))
```

在 `node_numbering.recompute(db, procedure_id)` 之后加：

```python
    for node, old_level, old_mark in observed:  # M3 隐式学习信号
        _learn_from_edit(db, node, old_level, old_mark)
```

- [ ] **Step 5: import 校验 + 既有节点测试回归**

Run: `cd backend && python -c "import app.services.node_service" && python -m pytest tests/unit/services -k node tests/integration -k node -q`
Expected: PASS（无来源样式名的既有节点 → `observe_node_edit` 返回 None → 钩子 no-op，零行为变化）。

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/node_service.py
git commit -m "feat(dict): node_service 改级/确认→学习钩子(无来源no-op) (P1c Task5)"
```

---

## Task 6: 移植学习 service 单测（含三道护栏）

**Files:**
- Port: `backend/tests/unit/services/test_heading_learning_service.py`

- [ ] **Step 1: 取分支单测**

```bash
git checkout origin/feat/dynamic-heading-dictionary -- backend/tests/unit/services/test_heading_learning_service.py
```

- [ ] **Step 2: 跑测试**

Run: `cd backend && python -m pytest tests/unit/services/test_heading_learning_service.py -v`
Expected: 全 PASS（8 项：达标激活 / 证据不足 candidate / 冲突 candidate / **归因粒度 23:1 不翻** / 手动优先 / 确认计票 / 无来源 no-op / 钩子接线）。
若个别用例引用了 parser 线特有夹具（如 `level_of_use`、租户删除版 node）→ 按主线 node 字段调整构造（主线 node 多 `NullableTenantMixin.company_id` 但 nullable，构造不受影响）。

- [ ] **Step 3: 提交**

```bash
git add backend/tests/unit/services/test_heading_learning_service.py
git commit -m "test(dict): 学习闭环单测(三道护栏) (P1c Task6)"
```

---

## Task 7: 端到端"越用越准" + 全量回归 + lint

**Files:**
- Test: `backend/tests/integration/test_heading_rules_api.py`（追加）

- [ ] **Step 1: 写"3 文档一致改级→自动 active→注入"集成测试**

追加到 `backend/tests/integration/test_heading_rules_api.py`：

```python
from app.models.node import ProcedureNode
from app.services import heading_learning_service


def _styled_node(db, pid: str, level: int, style="章节标题") -> ProcedureNode:
    n = ProcedureNode(
        procedure_id=pid, kind="chapter", heading_level=level,
        title="x", body="", mark_status="unmarked", source_style_name=style,
    )
    db.add(n); db.flush()
    return n


def test_three_docs_consistent_relevel_activates_rule(db) -> None:
    # 3 份文档各有一个「章节标题」节点，用户一致把它改为 L2
    for i in range(3):
        pid = f"proc-{i}"
        node = _styled_node(db, pid, level=1)
        node.heading_level = 2  # 用户改级
        heading_learning_service.observe_node_edit(db, node, old_level=1, old_mark="unmarked")
    rule = heading_learning_service.reaggregate(db, "章节标题")
    assert rule is not None and rule.source == "learned"
    assert rule.status == "active" and rule.level == 2  # ≥3 文档一致 → 自动生效
    # 生效规则进入解析注入
    from app.services import heading_rule_service
    assert heading_rule_service.active_style_overrides(db).get("章节标题") == 2
```

> `ProcedureNode` 构造字段以主线 `models/node.py` 实际必填项为准（若有额外 NOT NULL 列需补默认值）。`company_id` 为 nullable，可不填（autouse `_clear_tenant_context` 使 company_id=None，ORM 隔离短路）。

- [ ] **Step 2: 跑该测试**

Run: `cd backend && python -m pytest tests/integration/test_heading_rules_api.py -v`
Expected: 全 PASS。

- [ ] **Step 3: 全量回归 + golden 不变**

Run: `cd backend && python -m pytest tests/regression tests/unit/services tests/integration tests/unit/parser -q`
Expected: 全 PASS；golden 零漂移（学习只影响"有规则后的请求路径"，`evaluate_corpus` 无 db、无规则）。

- [ ] **Step 4: ruff**

Run: `cd backend && ruff check app/services/heading_learning_service.py app/services/node_service.py app/models/heading_learning_event.py app/models/node.py app/services/import_service.py tests/unit/services/test_heading_learning_service.py`
Expected: 无 error。

- [ ] **Step 5: 提交（如有修正）**

```bash
git add -A && git commit -m "chore(dict): ruff 修正 (P1c Task7)" || echo "无需提交"
```

---

## Self-Review 记录

- **Spec 覆盖**：实现 spec §1-A 学习闭环 + §3.3 三道护栏（投票阈值 K_DOCS=3/MIN_AGREEMENT=0.8、归因粒度 23:1、手动优先）的单租户形态。租户分区在 P2。
- **占位符**：无 TBD。Task2 Step2 的"grep 定位 ImportNodeIn"与 Task6/7 的"按主线 node 必填项调整构造"是**明确的定位/适配指引**（含命令），非占位符。
- **类型一致**：`observe_node_edit(db, node, *, old_level, old_mark) -> str|None`、`reaggregate(db, style_name) -> HeadingStyleRule|None`、`_learn_from_edit(db, node, old_level, old_mark)` 跨 service/node_service 一致；migration `revision="heading_learning"`/`down="heading_style_rule"` 链正确。
- **不反向丢失主线**：node.py 保留 `NullableTenantMixin`、import_service 排除无关 `level_of_use`——明确标注，全程 surgical 不 checkout 这些主线文件。
- **零行为变化保证**：无来源样式名节点 → 钩子 no-op；golden 不变。
