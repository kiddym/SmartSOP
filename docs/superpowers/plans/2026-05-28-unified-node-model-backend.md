# 统一节点模型后端基座(ProcedureNode)实现计划 — Plan A

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建 `ProcedureNode` 模型 + 树派生 + 节点 API(GET/PATCH/POST/DELETE/reorder/batch),作为统一节点模型的后端基座,与旧 chapter/step 表并存、零破坏。

**Architecture:** 纯增量。`tb_procedure_node` 单表用 `heading_level: int|null` 表达"章节 vs 正文",`kind: node|step` 表达"是否带表单"。父子关系由 `sort_order + heading_level` 一次 O(n) 栈扫**派生**,不存 `parent_id`。"章节↔内容转换"= 一次 `PATCH heading_level`。旧 `ProcedureChapter`/`ProcedureStep`/层级标定/标记模式本计划全部不动(留给 Plan B 切换下游后删除)。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy 2.0(`Mapped`/`mapped_column`)、Alembic、Pydantic v2、pytest + SQLite in-memory(conftest `Factory`)。运行测试用 `backend/.venv/bin/python -m pytest`(本机无 uv,见 memory `uv-missing-use-venv-python`)。

**Spec:** `docs/superpowers/specs/2026-05-28-unified-node-model-design.md`(§1 模型、§2 树派生、§3 转换语义、§4 API、§10 测试)。

---

## 范围说明

**本计划(Plan A)做** spec 的:§1 数据模型、§2 树派生、§3 转换语义、§4 API、§10.1 中与上述相关的后端测试。

**本计划不做**(留给 Plan B):parser 扁平化(§5)、import/seed 改写、下游适配(§7 PDF/sign-off/editor 读取)、前端(§6)、删除旧 chapter/step/layer/mark(§9)、重建 dev.db(§8)。

**为什么并存而非一次性重建:** spec §8 设想"一次性重建",但执行上分阶段更安全——删旧表会同时打断 PDF/sign-off/前端,那是 Plan B 的切换工作。Plan A 保持旧系统运行,新代码全部可独立测试。

---

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `backend/app/models/node.py` | `ProcedureNode` ORM 模型 | 创建 |
| `backend/app/models/__init__.py` | 导出 `ProcedureNode` | 修改 |
| `backend/app/services/_invariants.py` | 加 `enforce_node_invariants` | 修改 |
| `backend/app/services/node_tree.py` | `build_tree` 派生算法(纯函数) | 创建 |
| `backend/app/services/node_numbering.py` | 从派生树算 `code` | 创建 |
| `backend/app/services/node_service.py` | 节点 CRUD/patch/batch/reorder 业务逻辑 | 创建 |
| `backend/app/schemas/node_v2.py` | `NodeOut`/`NodePatchIn`/`NodeCreateIn`/`NodeBatchIn`/`NodeReorderIn` | 创建 |
| `backend/app/routers/nodes.py` | 节点路由 | 创建 |
| `backend/app/main.py` | 注册 `nodes.router` | 修改 |
| `backend/alembic/versions/20260528_0001_add_procedure_node.py` | 建 `tb_procedure_node` 表 | 创建 |
| `backend/tests/conftest.py` | `Factory.node()` 工厂方法 | 修改 |
| `backend/tests/unit/services/test_node_tree.py` | 树派生单测 | 创建 |
| `backend/tests/unit/services/test_node_numbering.py` | 编号单测 | 创建 |
| `backend/tests/unit/services/test_node_service.py` | 节点服务单测 | 创建 |
| `backend/tests/integration/test_nodes_api.py` | 节点 API 集成测试 | 创建 |

新建 `schemas/node_v2.py`(而非改 `schemas/node.py`):旧 schema 仍被旧 chapter/step 路由引用,Plan B 删旧路由时再合并。

---

## Group 1 — ProcedureNode 模型 + 不变量 + 迁移 + 测试工厂

### Task 1: ProcedureNode 模型

**Files:**
- Create: `backend/app/models/node.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: 写模型**

Create `backend/app/models/node.py`:

```python
"""统一节点模型(tb_procedure_node)。

单表表达章节/正文/步骤三态:
- heading_level: int|null —— null=正文;1/2/3…=章节层级
- kind: 'node'|'step'    —— 'node'=无表单(章节或正文);'step'=带 input_schema 表单
父子关系不存,由 sort_order+heading_level 派生(见 services/node_tree.py)。
与旧 tb_procedure_chapter/tb_procedure_step 并存,Plan B 切换下游后删旧表。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import LONGTEXT, Base, SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.procedure import Procedure


class ProcedureNode(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """统一节点(章节 / 正文 / 步骤同表)。"""

    __tablename__ = "tb_procedure_node"

    procedure_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_procedure.id", ondelete="RESTRICT")
    )
    # 全局有序(per procedure 的扁平位置),不再 per-parent。
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # null=正文;>=1=章节层级(跳级允许,见 spec §3.4)。
    heading_level: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    # 'node'=无表单(章节或正文);'step'=带表单。
    kind: Mapped[str] = mapped_column(String(20), default="node", server_default="node")
    # rich HTML。heading 的"标题"= body 第一个块级元素文本(派生,见 spec §2.3)。
    body: Mapped[str] = mapped_column(LONGTEXT, default="", server_default="")
    code: Mapped[str] = mapped_column(String(50), default="", server_default="")
    skip_numbering: Mapped[bool] = mapped_column(default=False, server_default="0")
    # 仅 kind='step' 非空。
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    attachment_marks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    # 解析存疑标记(parser 产出):'unmarked' | 'review'。
    mark_status: Mapped[str] = mapped_column(
        String(20), default="unmarked", server_default="unmarked"
    )
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    procedure: Mapped[Procedure] = relationship()

    __table_args__ = (
        Index("ix_tb_procedure_node_procedure_id_sort_order", "procedure_id", "sort_order"),
        Index("ix_tb_procedure_node_mark_status", "mark_status"),
    )
```

- [ ] **Step 2: 导出模型**

In `backend/app/models/__init__.py`, find where `ProcedureStep` is imported/exported and add `ProcedureNode` alongside it. The file imports models and lists them in `__all__`. Add the import line:

```python
from app.models.node import ProcedureNode
```

and add `"ProcedureNode"` to the `__all__` list (keep alphabetical/existing order consistent with neighbours like `"ProcedureChapter"`, `"ProcedureStep"`).

- [ ] **Step 3: 验证模型可建表**

Run: `backend/.venv/bin/python -c "from app.models import ProcedureNode; from app.models.base import Base; from sqlalchemy import create_engine; e=create_engine('sqlite://'); Base.metadata.create_all(e); print('tb_procedure_node' in Base.metadata.tables)"`
Expected: `True`

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/node.py backend/app/models/__init__.py
git commit -m "feat(model): add ProcedureNode unified node table"
```

---

### Task 2: 节点不变量

**Files:**
- Modify: `backend/app/services/_invariants.py`
- Test: `backend/tests/unit/services/test_node_service.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/unit/services/test_node_service.py`:

```python
"""ProcedureNode 服务与不变量单测。"""

from __future__ import annotations

import pytest

from app.errors import APIError
from app.services._invariants import enforce_node_invariants


def test_node_kind_with_input_schema_rejected() -> None:
    with pytest.raises(APIError):
        enforce_node_invariants(
            kind="node", heading_level=None, input_schema={"type": "COMMON"}, attachment_marks=[]
        )


def test_step_kind_with_heading_level_rejected() -> None:
    with pytest.raises(APIError):
        enforce_node_invariants(
            kind="step", heading_level=2, input_schema={"type": "COMMON"}, attachment_marks=[]
        )


def test_heading_level_zero_rejected() -> None:
    with pytest.raises(APIError):
        enforce_node_invariants(
            kind="node", heading_level=0, input_schema={}, attachment_marks=[]
        )


def test_valid_heading_node_ok() -> None:
    enforce_node_invariants(kind="node", heading_level=2, input_schema={}, attachment_marks=[])


def test_valid_content_node_ok() -> None:
    enforce_node_invariants(kind="node", heading_level=None, input_schema={}, attachment_marks=[])


def test_valid_step_ok() -> None:
    enforce_node_invariants(
        kind="step", heading_level=None, input_schema={"type": "COMMON"}, attachment_marks=[]
    )
```

Note: confirm the exception type. Check `backend/app/errors.py` — if `unprocessable()` raises `HTTPException` rather than a custom `APIError`, replace `APIError` in the test with `fastapi.HTTPException`. Run `grep -n "def unprocessable" backend/app/errors.py` and use the actual raised type. The existing `_invariants.py` raises whatever `unprocessable()` returns.

- [ ] **Step 2: 运行确认失败**

Run: `backend/.venv/bin/python -m pytest backend/tests/unit/services/test_node_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'enforce_node_invariants'`

- [ ] **Step 3: 实现不变量**

Append to `backend/app/services/_invariants.py`:

```python
def enforce_node_invariants(
    kind: str,
    heading_level: int | None,
    input_schema: dict[str, Any] | None,
    attachment_marks: list[Any] | None,
) -> None:
    """ProcedureNode 写入硬约束(spec §1.3)——违反时 raise 422。

    1. kind='node' → input_schema 与 attachment_marks 必须为空(章节/正文不带表单)。
    2. kind='step' → heading_level 必须为 None(步骤是叶子表单,不能是标题)。
    3. heading_level 若非 None,必须是 >=1 的整数。
    """
    if heading_level is not None and (not isinstance(heading_level, int) or heading_level < 1):
        raise unprocessable(
            "NODE_INVARIANT",
            f"heading_level 必须是 >=1 的整数或 None(got {heading_level!r})",
            field="heading_level",
        )
    if kind == "step":
        if heading_level is not None:
            raise unprocessable(
                "NODE_INVARIANT",
                "kind='step' 不能带 heading_level(步骤不能是标题)",
                field="heading_level",
            )
        return
    # kind='node':无结构化字段
    schema_empty = input_schema is None or input_schema == {}
    marks_empty = attachment_marks is None or attachment_marks in ([], ())
    if not schema_empty:
        raise unprocessable(
            "NODE_INVARIANT",
            f"kind='node' 不应携带 input_schema(got {input_schema!r})",
            field="input_schema",
        )
    if not marks_empty:
        raise unprocessable(
            "NODE_INVARIANT",
            f"kind='node' 不应携带 attachment_marks(got {attachment_marks!r})",
            field="attachment_marks",
        )
```

- [ ] **Step 4: 运行确认通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/unit/services/test_node_service.py -v`
Expected: PASS(6 个)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/_invariants.py backend/tests/unit/services/test_node_service.py
git commit -m "feat(invariants): add enforce_node_invariants for ProcedureNode"
```

---

### Task 3: Alembic 迁移建表

**Files:**
- Create: `backend/alembic/versions/20260528_0001_add_procedure_node.py`

- [ ] **Step 1: 查当前 head revision**

Run: `cd backend && .venv/bin/python -m alembic heads`
Expected: 打印一个 revision id(记下,作 down_revision)。若多 head 需先确认。本计划假设 head 为 `content_block_as_step`;若不同,用实际输出替换下一步的 `down_revision`。

- [ ] **Step 2: 写迁移**

Create `backend/alembic/versions/20260528_0001_add_procedure_node.py`:

```python
"""add tb_procedure_node (unified node model, Plan A)

新增 tb_procedure_node 表,与 tb_procedure_chapter/tb_procedure_step 并存。
不搬数据(开发数据可重建);旧表删除在 Plan B。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "add_procedure_node"
down_revision: str | None = "content_block_as_step"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tb_procedure_node",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("procedure_id", sa.String(length=36), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("heading_level", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="node"),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("code", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("skip_numbering", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("input_schema", sa.JSON(), nullable=False),
        sa.Column("attachment_marks", sa.JSON(), nullable=False),
        sa.Column("mark_status", sa.String(length=20), nullable=False, server_default="unmarked"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["procedure_id"], ["tb_procedure.id"],
            name="fk_tb_procedure_node_procedure_id", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tb_procedure_node"),
    )
    op.create_index(
        "ix_tb_procedure_node_procedure_id_sort_order",
        "tb_procedure_node", ["procedure_id", "sort_order"],
    )
    op.create_index(
        "ix_tb_procedure_node_mark_status", "tb_procedure_node", ["mark_status"]
    )
    op.create_index("ix_tb_procedure_node_is_active", "tb_procedure_node", ["is_active"])
    op.create_index("ix_tb_procedure_node_created_at", "tb_procedure_node", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_tb_procedure_node_created_at", table_name="tb_procedure_node")
    op.drop_index("ix_tb_procedure_node_is_active", table_name="tb_procedure_node")
    op.drop_index("ix_tb_procedure_node_mark_status", table_name="tb_procedure_node")
    op.drop_index(
        "ix_tb_procedure_node_procedure_id_sort_order", table_name="tb_procedure_node"
    )
    op.drop_table("tb_procedure_node")
```

- [ ] **Step 3: 验证迁移可升降级**

Run: `cd backend && .venv/bin/python -m alembic upgrade head && .venv/bin/python -m alembic downgrade -1 && .venv/bin/python -m alembic upgrade head`
Expected: 无报错;`alembic current` 显示 `add_procedure_node`。

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/20260528_0001_add_procedure_node.py
git commit -m "feat(migration): create tb_procedure_node table"
```

---

### Task 4: 测试工厂 Factory.node()

**Files:**
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: 加工厂方法**

In `backend/tests/conftest.py`, add `ProcedureNode` to the `from app.models import (...)` block (line ~23-31), then add this method to the `Factory` class (after the `step` method, before `settings`):

```python
    def node(
        self,
        procedure_id: str,
        body: str = "",
        sort_order: int = 0,
        heading_level: int | None = None,
        kind: str = "node",
        skip_numbering: bool = False,
        input_schema: dict[str, object] | None = None,
        mark_status: str = "unmarked",
    ) -> "ProcedureNode":
        node = ProcedureNode(
            procedure_id=procedure_id,
            body=body,
            sort_order=sort_order,
            heading_level=heading_level,
            kind=kind,
            skip_numbering=skip_numbering,
            input_schema=input_schema if input_schema is not None else {},
            mark_status=mark_status,
        )
        self.db.add(node)
        self.db.commit()
        return node
```

- [ ] **Step 2: 验证工厂可用**

Run: `backend/.venv/bin/python -m pytest backend/tests/unit/services/test_node_service.py -v` (existing tests still pass; factory import doesn't break collection)
Expected: PASS(6 个,无 collection error)

- [ ] **Step 3: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test(factory): add Factory.node() for ProcedureNode"
```

---

## Group 2 — 树派生算法

### Task 5: build_tree 派生(纯函数)

**Files:**
- Create: `backend/app/services/node_tree.py`
- Test: `backend/tests/unit/services/test_node_tree.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/unit/services/test_node_tree.py`:

```python
"""node_tree.build_tree 派生算法单测(spec §2.2)。"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.node_tree import build_tree


@dataclass
class Row:
    id: str
    heading_level: int | None


def _flat(rows: list[tuple[str, int | None]]) -> list[Row]:
    return [Row(id=i, heading_level=lvl) for i, lvl in rows]


def _by_id(tree_nodes):
    out = {}
    def walk(nodes):
        for n in nodes:
            out[n.id] = n
            walk(n.children)
    walk(tree_nodes)
    return out


def test_simple_nesting() -> None:
    rows = _flat([("a", 1), ("b", 2), ("x", None), ("y", None)])
    roots = build_tree(rows)
    nodes = _by_id(roots)
    assert [r.id for r in roots] == ["a"]
    assert nodes["a"].parent_id is None and nodes["a"].depth == 0
    assert nodes["b"].parent_id == "a" and nodes["b"].depth == 1
    assert nodes["x"].parent_id == "b" and nodes["y"].parent_id == "b"


def test_content_before_any_heading_is_root() -> None:
    rows = _flat([("x", None), ("a", 1)])
    nodes = _by_id(build_tree(rows))
    assert nodes["x"].parent_id is None
    assert nodes["a"].parent_id is None


def test_skip_level_l1_to_l3() -> None:
    rows = _flat([("a", 1), ("c", 3)])
    nodes = _by_id(build_tree(rows))
    assert nodes["c"].parent_id == "a" and nodes["c"].depth == 1


def test_demote_reparents_following_content() -> None:
    # a(L1) > [b(L2 demoted->null), x, y], c(L2)
    rows = _flat([("a", 1), ("b", None), ("x", None), ("y", None), ("c", 2)])
    nodes = _by_id(build_tree(rows))
    assert nodes["b"].parent_id == "a"
    assert nodes["x"].parent_id == "a"
    assert nodes["y"].parent_id == "a"
    assert nodes["c"].parent_id == "a"


def test_promote_captures_following_content() -> None:
    # a(L2) > x(L3 promoted), y, z  then b(L2)
    rows = _flat([("a", 2), ("x", 3), ("y", None), ("z", None), ("b", 2)])
    nodes = _by_id(build_tree(rows))
    assert nodes["x"].parent_id == "a"
    assert nodes["y"].parent_id == "x"
    assert nodes["z"].parent_id == "x"
    assert nodes["b"].parent_id is None  # b pops a(L2), no L1 above -> root


def test_sibling_l2s_share_l1_parent() -> None:
    rows = _flat([("a", 1), ("b", 2), ("c", 2)])
    nodes = _by_id(build_tree(rows))
    assert nodes["b"].parent_id == "a"
    assert nodes["c"].parent_id == "a"
```

- [ ] **Step 2: 运行确认失败**

Run: `backend/.venv/bin/python -m pytest backend/tests/unit/services/test_node_tree.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.node_tree'`

- [ ] **Step 3: 实现**

Create `backend/app/services/node_tree.py`:

```python
"""节点树派生(spec §2.2)。

父子关系不存,由 sort_order(输入已排序)+ heading_level 一次 O(n) 栈扫算出。
- heading(level!=None):弹栈直到栈顶 level < 本节点 level,栈顶为 parent,入栈。
- 正文/step(level=None):挂当前栈顶 heading,栈空则挂根。
跳级(L1→L3)被算法天然吸收(L3 挂 L1)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class NodeLike(Protocol):
    id: str
    heading_level: int | None


@dataclass
class TreeNode:
    id: str
    heading_level: int | None
    parent_id: str | None
    depth: int
    children: list["TreeNode"] = field(default_factory=list)


def build_tree(rows: list[NodeLike]) -> list[TreeNode]:
    """rows 必须已按 sort_order 升序。返回派生根节点列表。"""
    roots: list[TreeNode] = []
    stack: list[TreeNode] = []  # 当前祖先链(全是 heading)
    by_id: dict[str, TreeNode] = {}

    for row in rows:
        lvl = row.heading_level
        if lvl is None:
            parent = stack[-1] if stack else None
        else:
            while stack and (stack[-1].heading_level or 0) >= lvl:
                stack.pop()
            parent = stack[-1] if stack else None

        tn = TreeNode(
            id=row.id,
            heading_level=lvl,
            parent_id=parent.id if parent else None,
            depth=(parent.depth + 1) if parent else 0,
        )
        by_id[tn.id] = tn
        if parent is None:
            roots.append(tn)
        else:
            parent.children.append(tn)
        if lvl is not None:
            stack.append(tn)

    return roots
```

- [ ] **Step 4: 运行确认通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/unit/services/test_node_tree.py -v`
Expected: PASS(6 个)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/node_tree.py backend/tests/unit/services/test_node_tree.py
git commit -m "feat(node_tree): derive parent/depth from sort_order + heading_level"
```

---

## Group 3 — 编号

### Task 6: node_numbering 从派生树算 code

**Files:**
- Create: `backend/app/services/node_numbering.py`
- Test: `backend/tests/unit/services/test_node_numbering.py`

编号规则(沿用 `numbering_service` 语义,改用派生树):heading(`heading_level!=None`,非 skip)按层级连续编号 `1` / `1.1` / `1.1.1`;`kind='step'`(非 skip)在父 heading 下连续编号;`heading_level=None` 的 `kind='node'`(正文)永远 `code=''` 不占位;`skip_numbering` 节点 `code=''` 且其子树静默。

- [ ] **Step 1: 写失败测试**

Create `backend/tests/unit/services/test_node_numbering.py`:

```python
"""node_numbering.compute_codes 单测。"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.node_numbering import compute_codes


@dataclass
class Row:
    id: str
    heading_level: int | None
    kind: str = "node"
    skip_numbering: bool = False


def _rows(specs: list[tuple]) -> list[Row]:
    return [Row(*s) for s in specs]


def test_headings_hierarchical() -> None:
    rows = _rows([("a", 1), ("b", 2), ("c", 2), ("d", 1)])
    codes = compute_codes(rows)
    assert codes == {"a": "1", "b": "1.1", "c": "1.2", "d": "2"}


def test_content_never_numbered() -> None:
    rows = _rows([("a", 1), ("x", None, "node")])
    codes = compute_codes(rows)
    assert codes["a"] == "1"
    assert codes["x"] == ""


def test_step_numbered_under_heading() -> None:
    rows = _rows([("a", 1), ("s1", None, "step"), ("s2", None, "step")])
    codes = compute_codes(rows)
    assert codes["s1"] == "1.1"
    assert codes["s2"] == "1.2"


def test_skip_numbering_silences_subtree() -> None:
    rows = _rows([("a", 1, "node", True), ("b", 2), ("c", 1)])
    codes = compute_codes(rows)
    assert codes["a"] == ""
    assert codes["b"] == ""   # 父 skip → 子静默
    assert codes["c"] == "1"  # skip 不占位,c 仍是 1


def test_root_step_no_prefix() -> None:
    rows = _rows([("s", None, "step")])
    codes = compute_codes(rows)
    assert codes["s"] == "1"
```

- [ ] **Step 2: 运行确认失败**

Run: `backend/.venv/bin/python -m pytest backend/tests/unit/services/test_node_numbering.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.node_numbering'`

- [ ] **Step 3: 实现**

Create `backend/app/services/node_numbering.py`:

```python
"""节点编号引擎(从派生树算 code,沿用 numbering_service 语义)。

- heading(heading_level!=None,非 skip):按层级连续编号(1 / 1.1 / 1.1.1)。
- kind='step'(非 skip):在父 heading 下连续编号(父 code + '.' + seq;无父 → seq)。
- 正文(kind='node' 且 heading_level=None):code='' 不占位。
- skip_numbering:自身 code='' 且整个子树静默,且不占序号位。
纯函数 compute_codes(rows)->{id: code};recompute(db, proc_id) 落库。
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.node import ProcedureNode
from app.services.node_tree import TreeNode, build_tree


class NumRow(Protocol):
    id: str
    heading_level: int | None
    kind: str
    skip_numbering: bool


def compute_codes(rows: list[NumRow]) -> dict[str, str]:
    """rows 已按 sort_order 升序。返回 {node_id: code}。"""
    meta = {r.id: r for r in rows}
    roots = build_tree(rows)  # type: ignore[arg-type]
    codes: dict[str, str] = {}

    def walk_children(siblings: list[TreeNode], parent_code: str, silent: bool) -> None:
        # heading 与 step 各自连续编号;两者在同一父下分别计数(沿用旧引擎双计数器)。
        heading_seq = 0
        step_seq = 0
        for tn in siblings:
            r = meta[tn.id]
            node_silent = silent or r.skip_numbering
            if tn.heading_level is not None:
                # heading
                if node_silent:
                    codes[tn.id] = ""
                    walk_children(tn.children, "", True)
                    continue
                heading_seq += 1
                code = f"{parent_code}.{heading_seq}" if parent_code else str(heading_seq)
                codes[tn.id] = code
                walk_children(tn.children, code, False)
            elif r.kind == "step":
                if node_silent:
                    codes[tn.id] = ""
                    continue
                step_seq += 1
                codes[tn.id] = f"{parent_code}.{step_seq}" if parent_code else str(step_seq)
            else:
                # 正文 node:永远不编号
                codes[tn.id] = ""

    walk_children(roots, "", False)
    return codes


def recompute(db: Session, procedure_id: str) -> None:
    """重算指定程序所有 active 节点的 code 并落库(只 flush,不 commit)。"""
    rows = list(
        db.execute(
            select(ProcedureNode)
            .where(
                ProcedureNode.procedure_id == procedure_id,
                ProcedureNode.is_active.is_(True),
            )
            .order_by(ProcedureNode.sort_order, ProcedureNode.id)
        ).scalars()
    )
    codes = compute_codes(rows)  # type: ignore[arg-type]
    for r in rows:
        r.code = codes.get(r.id, "")
    db.flush()
```

注:`TreeNode` 在 `compute_codes` 内部函数注解 `siblings: list[TreeNode]` 中使用;`build_tree`/`select`/`Session`/`ProcedureNode` 均被用到,无未用 import。

- [ ] **Step 4: 运行确认通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/unit/services/test_node_numbering.py -v`
Expected: PASS(5 个)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/node_numbering.py backend/tests/unit/services/test_node_numbering.py
git commit -m "feat(node_numbering): compute codes from derived tree"
```

---

## Group 4 — 节点服务(转换/CRUD/批量/重排)

### Task 7: node_service 读取(get_nodes 含派生)

**Files:**
- Create: `backend/app/services/node_service.py`
- Test: `backend/tests/unit/services/test_node_service.py`(追加)

- [ ] **Step 1: 写失败测试**

Append to `backend/tests/unit/services/test_node_service.py`:

```python
from app.services import node_numbering, node_service


def _proc(factory):
    folder = factory.folder()
    return factory.procedure(folder_id=folder.id)


def test_get_nodes_returns_sorted_with_derived(factory, db) -> None:
    proc = _proc(factory)
    factory.node(proc.id, body="<p>A</p>", sort_order=10, heading_level=1)
    factory.node(proc.id, body="<p>x</p>", sort_order=20, heading_level=None)
    node_numbering.recompute(db, proc.id)
    rows = node_service.get_nodes(db, proc.id)
    assert [r["body"] for r in rows] == ["<p>A</p>", "<p>x</p>"]
    assert rows[0]["parent_id"] is None and rows[0]["depth"] == 0 and rows[0]["code"] == "1"
    assert rows[1]["parent_id"] == rows[0]["id"] and rows[1]["depth"] == 1
```

- [ ] **Step 2: 运行确认失败**

Run: `backend/.venv/bin/python -m pytest backend/tests/unit/services/test_node_service.py::test_get_nodes_returns_sorted_with_derived -v`
Expected: FAIL — `ImportError`/`AttributeError: module 'app.services.node_service' has no attribute 'get_nodes'`

- [ ] **Step 3: 实现**

Create `backend/app/services/node_service.py`:

```python
"""统一节点服务(spec §3/§4)。

"转换"= 改 heading_level/kind 一次写。父子关系派生(node_tree),不存。
所有写函数只 flush 不 commit(router 提交);写 ProcedureNode 前过 enforce_node_invariants。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import bad_request, not_found
from app.models.base import utcnow
from app.models.node import ProcedureNode
from app.services import node_numbering
from app.services._invariants import enforce_node_invariants
from app.services.node_tree import build_tree

_SORT_GAP = 1000


def _active_nodes(db: Session, procedure_id: str) -> list[ProcedureNode]:
    return list(
        db.execute(
            select(ProcedureNode)
            .where(
                ProcedureNode.procedure_id == procedure_id,
                ProcedureNode.is_active.is_(True),
            )
            .order_by(ProcedureNode.sort_order, ProcedureNode.id)
        ).scalars()
    )


def _get_node(db: Session, node_id: str) -> ProcedureNode:
    node = db.execute(
        select(ProcedureNode).where(
            ProcedureNode.id == node_id, ProcedureNode.is_active.is_(True)
        )
    ).scalar_one_or_none()
    if node is None:
        raise not_found("NOT_FOUND", "节点不存在")
    return node


def get_nodes(db: Session, procedure_id: str) -> list[dict[str, Any]]:
    """返回扁平 list,每项含派生 parent_id/depth + 持久字段。"""
    rows = _active_nodes(db, procedure_id)
    derived = {tn.id: tn for tn in _walk(build_tree(rows))}
    out: list[dict[str, Any]] = []
    for r in rows:
        tn = derived[r.id]
        out.append(
            {
                "id": r.id,
                "procedure_id": r.procedure_id,
                "sort_order": r.sort_order,
                "heading_level": r.heading_level,
                "kind": r.kind,
                "body": r.body,
                "code": r.code,
                "skip_numbering": r.skip_numbering,
                "input_schema": r.input_schema,
                "attachment_marks": r.attachment_marks,
                "mark_status": r.mark_status,
                "revision": r.revision,
                "parent_id": tn.parent_id,
                "depth": tn.depth,
            }
        )
    return out


def _walk(roots: list) -> list:
    out: list = []

    def rec(nodes: list) -> None:
        for n in nodes:
            out.append(n)
            rec(n.children)

    rec(roots)
    return out
```

- [ ] **Step 4: 运行确认通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/unit/services/test_node_service.py -v`
Expected: PASS(全部,含新 1 个)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/node_service.py backend/tests/unit/services/test_node_service.py
git commit -m "feat(node_service): get_nodes with derived parent/depth"
```

---

### Task 8: patch_node(转换 = 改 heading_level/kind/body)

**Files:**
- Modify: `backend/app/services/node_service.py`
- Test: `backend/tests/unit/services/test_node_service.py`(追加)

- [ ] **Step 1: 写失败测试**

Append to `backend/tests/unit/services/test_node_service.py`:

```python
def test_patch_promote_content_to_heading(factory, db) -> None:
    proc = _proc(factory)
    n = factory.node(proc.id, body="<p>3.1 质量部</p>", sort_order=10, heading_level=None)
    updated = node_service.patch_node(db, n.id, {"heading_level": 2}, expected_revision=1)
    assert updated.heading_level == 2
    assert updated.body == "<p>3.1 质量部</p>"  # body 原地不动
    assert updated.revision == 2


def test_patch_demote_heading_to_content(factory, db) -> None:
    proc = _proc(factory)
    n = factory.node(proc.id, body="<p>A</p>", sort_order=10, heading_level=2)
    updated = node_service.patch_node(db, n.id, {"heading_level": None}, expected_revision=1)
    assert updated.heading_level is None
    assert updated.body == "<p>A</p>"


def test_patch_roundtrip_strict(factory, db) -> None:
    proc = _proc(factory)
    n = factory.node(proc.id, body="<p>3.1 X</p>", sort_order=10, heading_level=None)
    node_service.patch_node(db, n.id, {"heading_level": 2}, expected_revision=1)
    back = node_service.patch_node(db, n.id, {"heading_level": None}, expected_revision=2)
    assert back.heading_level is None and back.body == "<p>3.1 X</p>"


def test_patch_step_with_heading_level_rejected(factory, db) -> None:
    import pytest
    proc = _proc(factory)
    n = factory.node(proc.id, body="", sort_order=10, kind="step", heading_level=None,
                     input_schema={"type": "COMMON"})
    with pytest.raises(Exception):
        node_service.patch_node(db, n.id, {"heading_level": 2}, expected_revision=1)


def test_patch_revision_conflict(factory, db) -> None:
    import pytest
    proc = _proc(factory)
    n = factory.node(proc.id, body="<p>A</p>", sort_order=10, heading_level=None)
    with pytest.raises(Exception):
        node_service.patch_node(db, n.id, {"heading_level": 2}, expected_revision=99)
```

- [ ] **Step 2: 运行确认失败**

Run: `backend/.venv/bin/python -m pytest backend/tests/unit/services/test_node_service.py -k patch -v`
Expected: FAIL — `AttributeError: ... has no attribute 'patch_node'`

- [ ] **Step 3: 实现**

Append to `backend/app/services/node_service.py`:

```python
from app.services import optimistic_lock

_PATCHABLE = {"heading_level", "kind", "body", "input_schema", "attachment_marks", "skip_numbering"}


def patch_node(
    db: Session, node_id: str, changes: dict[str, Any], *, expected_revision: int
) -> ProcedureNode:
    """单字段更新(spec §3.1)。changes 只允许 _PATCHABLE 的键。"""
    node = _get_node(db, node_id)
    optimistic_lock.verify_revision(node.revision, expected_revision)

    unknown = set(changes) - _PATCHABLE
    if unknown:
        raise bad_request("BAD_FIELD", f"不可更新字段:{sorted(unknown)}")

    new_kind = changes.get("kind", node.kind)
    new_level = changes["heading_level"] if "heading_level" in changes else node.heading_level
    new_schema = changes.get("input_schema", node.input_schema)
    new_marks = changes.get("attachment_marks", node.attachment_marks)
    enforce_node_invariants(new_kind, new_level, new_schema, new_marks)

    for k, v in changes.items():
        setattr(node, k, v)
    optimistic_lock.bump(node)
    db.flush()
    node_numbering.recompute(db, node.procedure_id)
    return node
```

注:`optimistic_lock.verify_revision(current, expected)` 在不符时 raise 409;`bump` 自增 `revision`。`changes` 含 `heading_level: None` 时,`"heading_level" in changes` 为 True,正确写入 None。

- [ ] **Step 4: 运行确认通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/unit/services/test_node_service.py -k patch -v`
Expected: PASS(5 个)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/node_service.py backend/tests/unit/services/test_node_service.py
git commit -m "feat(node_service): patch_node — conversion via heading_level/kind"
```

---

### Task 9: create_node / delete_node

**Files:**
- Modify: `backend/app/services/node_service.py`
- Test: `backend/tests/unit/services/test_node_service.py`(追加)

- [ ] **Step 1: 写失败测试**

Append to `backend/tests/unit/services/test_node_service.py`:

```python
def test_create_node_appends_to_end(factory, db) -> None:
    proc = _proc(factory)
    factory.node(proc.id, body="<p>A</p>", sort_order=10, heading_level=1)
    created = node_service.create_node(
        db, proc.id, {"body": "<p>new</p>", "heading_level": None, "kind": "node"}
    )
    rows = node_service.get_nodes(db, proc.id)
    assert rows[-1]["id"] == created.id
    assert created.sort_order > 10


def test_delete_node_soft_deletes(factory, db) -> None:
    proc = _proc(factory)
    n = factory.node(proc.id, body="<p>A</p>", sort_order=10, heading_level=1)
    node_service.delete_node(db, n.id)
    assert n.is_active is False and n.deleted_at is not None
    assert node_service.get_nodes(db, proc.id) == []
```

- [ ] **Step 2: 运行确认失败**

Run: `backend/.venv/bin/python -m pytest backend/tests/unit/services/test_node_service.py -k "create_node or delete_node" -v`
Expected: FAIL — `AttributeError: ... 'create_node'`

- [ ] **Step 3: 实现**

Append to `backend/app/services/node_service.py`:

```python
def create_node(db: Session, procedure_id: str, data: dict[str, Any]) -> ProcedureNode:
    """新建节点,默认追加到末尾(sort_order = 当前 max + _SORT_GAP)。
    data 可含 sort_order 显式指定位置。"""
    kind = data.get("kind", "node")
    heading_level = data.get("heading_level")
    input_schema = data.get("input_schema", {})
    attachment_marks = data.get("attachment_marks", [])
    enforce_node_invariants(kind, heading_level, input_schema, attachment_marks)

    if "sort_order" in data and data["sort_order"] is not None:
        sort_order = data["sort_order"]
    else:
        existing = _active_nodes(db, procedure_id)
        sort_order = (existing[-1].sort_order + _SORT_GAP) if existing else _SORT_GAP

    node = ProcedureNode(
        procedure_id=procedure_id,
        body=data.get("body", ""),
        heading_level=heading_level,
        kind=kind,
        input_schema=input_schema,
        attachment_marks=attachment_marks,
        skip_numbering=data.get("skip_numbering", False),
        mark_status=data.get("mark_status", "unmarked"),
        sort_order=sort_order,
    )
    db.add(node)
    db.flush()
    node_numbering.recompute(db, procedure_id)
    return node


def delete_node(db: Session, node_id: str) -> None:
    """软删单节点。子节点不随删(派生关系,删后自动重派生)。"""
    node = _get_node(db, node_id)
    node.is_active = False
    node.deleted_at = utcnow()
    db.flush()
    node_numbering.recompute(db, node.procedure_id)
```

- [ ] **Step 4: 运行确认通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/unit/services/test_node_service.py -k "create_node or delete_node" -v`
Expected: PASS(2 个)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/node_service.py backend/tests/unit/services/test_node_service.py
git commit -m "feat(node_service): create_node / delete_node"
```

---

### Task 10: batch_update(多选批量改 heading_level/kind)

**Files:**
- Modify: `backend/app/services/node_service.py`
- Test: `backend/tests/unit/services/test_node_service.py`(追加)

- [ ] **Step 1: 写失败测试**

Append to `backend/tests/unit/services/test_node_service.py`:

```python
def test_batch_update_sets_level_on_many(factory, db) -> None:
    proc = _proc(factory)
    a = factory.node(proc.id, body="<p>a</p>", sort_order=10, heading_level=None)
    b = factory.node(proc.id, body="<p>b</p>", sort_order=20, heading_level=None)
    c = factory.node(proc.id, body="<p>c</p>", sort_order=30, heading_level=None)
    node_service.batch_update(db, proc.id, {a.id: {"heading_level": 3}, b.id: {"heading_level": 3}})
    assert a.heading_level == 3 and b.heading_level == 3 and c.heading_level is None


def test_batch_update_mark_as_step_clears_review(factory, db) -> None:
    proc = _proc(factory)
    a = factory.node(proc.id, body="", sort_order=10, heading_level=1, mark_status="review")
    node_service.batch_update(
        db, proc.id, {a.id: {"kind": "step", "heading_level": None, "input_schema": {"type": "COMMON"}}}
    )
    assert a.kind == "step" and a.heading_level is None and a.mark_status == "unmarked"
```

注:`batch_update` 内对每个被改节点,若其 `mark_status=='review'` 则改后清回 `'unmarked'`(spec §6.4 确认动作)。

- [ ] **Step 2: 运行确认失败**

Run: `backend/.venv/bin/python -m pytest backend/tests/unit/services/test_node_service.py -k batch_update -v`
Expected: FAIL — `AttributeError: ... 'batch_update'`

- [ ] **Step 3: 实现**

Append to `backend/app/services/node_service.py`:

```python
def batch_update(
    db: Session, procedure_id: str, updates: dict[str, dict[str, Any]]
) -> list[ProcedureNode]:
    """批量改 heading_level/kind 等(多选浮动条 / 取代旧 apply_marks)。
    改动后若节点 mark_status=='review' 则清回 'unmarked'(确认动作,spec §6.4)。
    单事务,任一不变量违反则整体抛错(router 不 commit → 回滚)。"""
    changed: list[ProcedureNode] = []
    for node_id, changes in updates.items():
        node = _get_node(db, node_id)
        if node.procedure_id != procedure_id:
            raise bad_request("BAD_NODE", f"节点 {node_id} 不属于本程序")
        unknown = set(changes) - _PATCHABLE
        if unknown:
            raise bad_request("BAD_FIELD", f"不可更新字段:{sorted(unknown)}")
        new_kind = changes.get("kind", node.kind)
        new_level = changes["heading_level"] if "heading_level" in changes else node.heading_level
        new_schema = changes.get("input_schema", node.input_schema)
        new_marks = changes.get("attachment_marks", node.attachment_marks)
        enforce_node_invariants(new_kind, new_level, new_schema, new_marks)
        for k, v in changes.items():
            setattr(node, k, v)
        if node.mark_status == "review":
            node.mark_status = "unmarked"
        optimistic_lock.bump(node)
        changed.append(node)
    db.flush()
    node_numbering.recompute(db, procedure_id)
    return changed
```

- [ ] **Step 4: 运行确认通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/unit/services/test_node_service.py -k batch_update -v`
Expected: PASS(2 个)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/node_service.py backend/tests/unit/services/test_node_service.py
git commit -m "feat(node_service): batch_update + clear review on confirm"
```

---

### Task 11: reorder(批量写 sort_order)

**Files:**
- Modify: `backend/app/services/node_service.py`
- Test: `backend/tests/unit/services/test_node_service.py`(追加)

- [ ] **Step 1: 写失败测试**

Append to `backend/tests/unit/services/test_node_service.py`:

```python
def test_reorder_rewrites_sort_order(factory, db) -> None:
    proc = _proc(factory)
    a = factory.node(proc.id, body="<p>a</p>", sort_order=10, heading_level=1)
    b = factory.node(proc.id, body="<p>b</p>", sort_order=20, heading_level=1)
    # 把 b 排到 a 前面
    node_service.reorder(db, proc.id, [b.id, a.id])
    rows = node_service.get_nodes(db, proc.id)
    assert [r["id"] for r in rows] == [b.id, a.id]


def test_reorder_rejects_unknown_node(factory, db) -> None:
    import pytest
    proc = _proc(factory)
    a = factory.node(proc.id, body="<p>a</p>", sort_order=10, heading_level=1)
    with pytest.raises(Exception):
        node_service.reorder(db, proc.id, [a.id, "ghost-id"])
```

- [ ] **Step 2: 运行确认失败**

Run: `backend/.venv/bin/python -m pytest backend/tests/unit/services/test_node_service.py -k reorder -v`
Expected: FAIL — `AttributeError: ... 'reorder'`

- [ ] **Step 3: 实现**

Append to `backend/app/services/node_service.py`:

```python
def reorder(db: Session, procedure_id: str, ordered_ids: list[str]) -> None:
    """按 ordered_ids 给本程序所有 active 节点重写 sort_order(gap 序)。
    ordered_ids 必须恰好是本程序当前所有 active 节点 id 的一个排列。"""
    rows = _active_nodes(db, procedure_id)
    existing = {r.id for r in rows}
    if set(ordered_ids) != existing or len(ordered_ids) != len(existing):
        raise bad_request(
            "BAD_REORDER", "reorder 的 id 列表必须恰好是本程序全部 active 节点的排列"
        )
    by_id = {r.id: r for r in rows}
    for i, nid in enumerate(ordered_ids):
        by_id[nid].sort_order = (i + 1) * _SORT_GAP
    db.flush()
    node_numbering.recompute(db, procedure_id)
```

注:Plan A 的 reorder 取"全量排列"以保持简单与可验证(前端拖拽子树时算出整列新顺序传入)。Plan B 接前端拖拽时若需"区间移动"可在此基础上加便捷端点。

- [ ] **Step 4: 运行确认通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/unit/services/test_node_service.py -k reorder -v`
Expected: PASS(2 个)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/node_service.py backend/tests/unit/services/test_node_service.py
git commit -m "feat(node_service): reorder by full permutation"
```

---

## Group 5 — Schema + Router

### Task 12: 节点 schema

**Files:**
- Create: `backend/app/schemas/node_v2.py`

- [ ] **Step 1: 写 schema**

Create `backend/app/schemas/node_v2.py`:

```python
"""统一节点 API schema(spec §4)。独立于旧 schemas/node.py;Plan B 合并。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NodeOut(BaseModel):
    """节点输出(GET 平铺 + 派生 parent_id/depth)。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    procedure_id: str
    sort_order: int
    heading_level: int | None
    kind: str
    body: str
    code: str
    skip_numbering: bool
    input_schema: dict[str, Any]
    attachment_marks: list[dict[str, Any]]
    mark_status: str
    revision: int
    parent_id: str | None
    depth: int


class NodePatchIn(BaseModel):
    """单节点 patch。仅传需要改的字段;heading_level 显式传 null 表示降为正文。"""

    model_config = ConfigDict(extra="forbid")

    heading_level: int | None = Field(default=None)
    kind: str | None = None
    body: str | None = None
    input_schema: dict[str, Any] | None = None
    attachment_marks: list[dict[str, Any]] | None = None
    skip_numbering: bool | None = None
    # 标记"本次 patch 是否要改 heading_level"(因 None 既是合法值又是默认值)。
    set_heading_level: bool = False


class NodeCreateIn(BaseModel):
    body: str = ""
    heading_level: int | None = None
    kind: str = "node"
    input_schema: dict[str, Any] = Field(default_factory=dict)
    attachment_marks: list[dict[str, Any]] = Field(default_factory=list)
    skip_numbering: bool = False
    sort_order: int | None = None


class NodeBatchItem(BaseModel):
    heading_level: int | None = None
    set_heading_level: bool = False
    kind: str | None = None
    input_schema: dict[str, Any] | None = None
    skip_numbering: bool | None = None


class NodeBatchIn(BaseModel):
    updates: dict[str, NodeBatchItem]


class NodeReorderIn(BaseModel):
    ordered_ids: list[str]
```

注:`heading_level` 的"是否要改"用伴随布尔 `set_heading_level` 表达,因为 `None` 同时是合法目标值与字段默认值,无法只靠 `None` 区分"降为正文"与"不改"。router 据此把 `heading_level` 放进/不放进 `changes` dict。

- [ ] **Step 2: 验证 schema 可导入**

Run: `backend/.venv/bin/python -c "from app.schemas.node_v2 import NodeOut, NodePatchIn, NodeCreateIn, NodeBatchIn, NodeReorderIn; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/node_v2.py
git commit -m "feat(schema): node_v2 schemas for unified node API"
```

---

### Task 13: 节点路由

**Files:**
- Create: `backend/app/routers/nodes.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/integration/test_nodes_api.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/integration/test_nodes_api.py`:

```python
"""节点 API 集成测试。

`factory` 与 `client` fixture 共用同一个 in-memory engine(conftest:StaticPool),
故 factory 落库的数据对 client 请求可见。沿用仓库既有 integration 测试的 fixture 用法。
"""

from __future__ import annotations

from tests.conftest import Factory


def _proc(factory: Factory):
    folder = factory.folder()
    return factory.procedure(folder_id=folder.id)


def test_get_nodes_endpoint(client, factory: Factory) -> None:
    proc = _proc(factory)
    factory.node(proc.id, body="<p>A</p>", sort_order=10, heading_level=1)
    resp = client.get(f"/api/v1/procedures/{proc.id}/nodes")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1 and data[0]["heading_level"] == 1 and data[0]["parent_id"] is None


def test_patch_promote_endpoint(client, factory: Factory) -> None:
    proc = _proc(factory)
    n = factory.node(proc.id, body="<p>3.1 X</p>", sort_order=10, heading_level=None)
    resp = client.patch(
        f"/api/v1/nodes/{n.id}",
        json={"heading_level": 2, "set_heading_level": True},
        headers={"If-Match": "1"},
    )
    assert resp.status_code == 200
    assert resp.json()["heading_level"] == 2


def test_patch_requires_if_match(client, factory: Factory) -> None:
    proc = _proc(factory)
    n = factory.node(proc.id, body="<p>A</p>", sort_order=10, heading_level=None)
    resp = client.patch(
        f"/api/v1/nodes/{n.id}", json={"heading_level": 2, "set_heading_level": True}
    )
    assert resp.status_code == 412


def test_batch_endpoint(client, factory: Factory) -> None:
    proc = _proc(factory)
    a = factory.node(proc.id, body="<p>a</p>", sort_order=10, heading_level=None)
    b = factory.node(proc.id, body="<p>b</p>", sort_order=20, heading_level=None)
    resp = client.patch(
        f"/api/v1/procedures/{proc.id}/nodes:batch",
        json={"updates": {
            a.id: {"heading_level": 3, "set_heading_level": True},
            b.id: {"heading_level": 3, "set_heading_level": True},
        }},
    )
    assert resp.status_code == 200
```

注:`If-Match` 头由 router 内 `optimistic_lock.ensure_if_match` 解析;缺失 → 412(`precondition_failed`)。`factory`+`client` 同引擎共享数据是 conftest 的设计意图(两者都 `Depends(engine)`),无需手开 Session。若 `factory` fixture 在 integration 测试里行为异常,核对仓库现有 `backend/tests/integration/` 用例的播种写法并对齐。

- [ ] **Step 2: 运行确认失败**

Run: `backend/.venv/bin/python -m pytest backend/tests/integration/test_nodes_api.py -v`
Expected: FAIL — 404(路由不存在)

- [ ] **Step 3: 实现路由**

Create `backend/app/routers/nodes.py`:

```python
"""统一节点路由(spec §4)。Router 提交事务。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.schemas.node_v2 import (
    NodeBatchIn,
    NodeCreateIn,
    NodeOut,
    NodePatchIn,
    NodeReorderIn,
)
from app.services import node_service, optimistic_lock

router = APIRouter(tags=["nodes"])


def _changes_from_patch(payload: NodePatchIn) -> dict:
    changes: dict = {}
    if payload.set_heading_level:
        changes["heading_level"] = payload.heading_level
    if payload.kind is not None:
        changes["kind"] = payload.kind
    if payload.body is not None:
        changes["body"] = payload.body
    if payload.input_schema is not None:
        changes["input_schema"] = payload.input_schema
    if payload.attachment_marks is not None:
        changes["attachment_marks"] = payload.attachment_marks
    if payload.skip_numbering is not None:
        changes["skip_numbering"] = payload.skip_numbering
    return changes


@router.get("/api/v1/procedures/{procedure_id}/nodes", response_model=list[NodeOut])
def list_nodes(procedure_id: str, db: Session = Depends(get_db)) -> list[NodeOut]:
    return [NodeOut(**r) for r in node_service.get_nodes(db, procedure_id)]


@router.patch("/api/v1/nodes/{node_id}", response_model=NodeOut)
def patch_node(
    node_id: str,
    payload: NodePatchIn,
    db: Session = Depends(get_db),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> NodeOut:
    expected = optimistic_lock.ensure_if_match(if_match)
    node_service.patch_node(
        db, node_id, _changes_from_patch(payload), expected_revision=expected
    )
    db.commit()
    return NodeOut(**_one(db, node_id))


@router.post(
    "/api/v1/procedures/{procedure_id}/nodes",
    response_model=NodeOut,
    status_code=status.HTTP_201_CREATED,
)
def create_node(
    procedure_id: str, payload: NodeCreateIn, db: Session = Depends(get_db)
) -> NodeOut:
    created = node_service.create_node(db, procedure_id, payload.model_dump())
    db.commit()
    return NodeOut(**_one(db, created.id))


@router.delete("/api/v1/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_node(node_id: str, db: Session = Depends(get_db)) -> Response:
    node_service.delete_node(db, node_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/api/v1/procedures/{procedure_id}/nodes:batch", response_model=list[NodeOut])
def batch_update(
    procedure_id: str, payload: NodeBatchIn, db: Session = Depends(get_db)
) -> list[NodeOut]:
    updates: dict[str, dict] = {}
    for nid, item in payload.updates.items():
        changes: dict = {}
        if item.set_heading_level:
            changes["heading_level"] = item.heading_level
        if item.kind is not None:
            changes["kind"] = item.kind
        if item.input_schema is not None:
            changes["input_schema"] = item.input_schema
        if item.skip_numbering is not None:
            changes["skip_numbering"] = item.skip_numbering
        updates[nid] = changes
    node_service.batch_update(db, procedure_id, updates)
    db.commit()
    return [NodeOut(**r) for r in node_service.get_nodes(db, procedure_id)]


@router.post("/api/v1/procedures/{procedure_id}/nodes/reorder", status_code=status.HTTP_204_NO_CONTENT)
def reorder(
    procedure_id: str, payload: NodeReorderIn, db: Session = Depends(get_db)
) -> Response:
    node_service.reorder(db, procedure_id, payload.ordered_ids)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _one(db: Session, node_id: str) -> dict:
    node = node_service._get_node(db, node_id)
    rows = node_service.get_nodes(db, node.procedure_id)
    for r in rows:
        if r["id"] == node_id:
            return r
    raise RuntimeError("node disappeared after write")
```

- [ ] **Step 4: 注册路由**

In `backend/app/main.py`, find where other routers are included (e.g. `app.include_router(chapters.router)`). Add the import next to the other router imports:

```python
from app.routers import nodes
```

and register it next to the others:

```python
app.include_router(nodes.router)
```

- [ ] **Step 5: 运行确认通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/integration/test_nodes_api.py -v`
Expected: PASS(4 个)。若 `test_patch_requires_if_match` 不是 412,核对 `optimistic_lock.ensure_if_match` 的 precondition_failed 状态码(应为 412)。

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/nodes.py backend/app/main.py backend/tests/integration/test_nodes_api.py
git commit -m "feat(api): node router — GET/PATCH/POST/DELETE/batch/reorder"
```

---

### Task 14: 全量回归 + mypy

**Files:** 无新增

- [ ] **Step 1: 跑全部后端测试**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: 全绿(新增 node 测试通过,旧 chapter/step/layer/mark 测试**不受影响**仍通过——因为本计划纯增量)。

- [ ] **Step 2: 类型检查(若仓库用 mypy)**

Run: `cd backend && .venv/bin/python -m mypy app/services/node_service.py app/services/node_tree.py app/services/node_numbering.py app/routers/nodes.py app/models/node.py 2>&1 | tail -20`
Expected: 无 error(若仓库 mypy 配置严格,修正 `# type: ignore` 注释处的真实类型)。

- [ ] **Step 3: Commit(若有修正)**

```bash
git add -A
git commit -m "chore: type/lint fixes for node foundation"
```

---

## 完成标准(Plan A)

1. `tb_procedure_node` 表存在,迁移可升降级。
2. `build_tree` 正确派生父子(含跳级、降级上提、升级接管、根级正文)。
3. `PATCH /nodes/{id}` 改 `heading_level` 即"转换",body 不动,严格 round-trip;`kind='step'` 设 heading_level 被拒;revision 冲突 409;缺 If-Match 412。
4. `GET /procedures/{id}/nodes` 返回扁平 list + 派生 parent_id/depth + code。
5. `:batch` 批量改级 + review 清除;`reorder` 全排列重写 sort_order。
6. 旧 chapter/step/layer/mark 代码与测试**全部未动**,全测仍绿。

## 交接给 Plan B 的接口事实(写 Plan B 时据此对齐)

- 节点 GET 形状:`NodeOut`(见 Task 12),前端 `NodeTreePanel` 据 `parent_id`/`depth` 渲染或自行 `build_tree`。
- 转换入口:`PATCH /nodes/{id}` body `{heading_level, set_heading_level, kind, body, ...}` + `If-Match: <revision>`。
- 批量:`PATCH /procedures/{id}/nodes:batch`。
- Plan B 任务:parser 扁平化 + import/seed 写 ProcedureNode、前端两面板、PDF/sign-off/editor 读取切到 ProcedureNode、删 ProcedureChapter/ProcedureStep/layer/mark + 重建 dev.db。
