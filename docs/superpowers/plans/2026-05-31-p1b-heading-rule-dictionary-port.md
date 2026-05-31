# P1b 样式字典 heading_rule（表+service+router+解析注入，单租户）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把动态标题字典的**样式规则**（M1）移植进主线：`tb_heading_style_rule` 表 + CRUD service + REST router + 解析注入（`parse_service` 读 active 规则→`style_overrides`→`parse_docx`）。**单租户**（`style_name` 全局唯一，租户维度留待 P2）。落地后：管理员建规则 → `/parse` 即按规则识别层级。

**Architecture:** model/schema/service 与 parser 线一致、可整文件 `git checkout` 自 `origin/feat/dynamic-heading-dictionary`（`$SRC`）取得（均用主线已有的 `Base/UUIDMixin/TimestampMixin/SoftDeleteMixin`）。router 与 `parse_service` 因分支版本**纠缠了编号体例（M4b）**，需写 **heading-only 裁剪版**——`numbering_overrides` 喂 `None`，P1d 再追加。Alembic 迁移**新建并链在主线 head `phase3b_vendor` 之后**（不能 checkout 分支迁移，revision 链不同）。

**Tech Stack:** Python 3.11+、SQLAlchemy 2.0 ORM、Alembic（字符串 slug revision）、FastAPI、pytest（`db`/`client` fixtures）。

**前置：** P1a 已落地（`parse_docx(..., style_overrides=, numbering_overrides=)` 签名就位）。

---

## File Structure

- `backend/app/models/heading_rule.py`（port）：`HeadingStyleRule`（单租户）
- `backend/app/models/__init__.py`（modify）：注册 `HeadingStyleRule`
- `backend/app/schemas/heading_rule.py`（port）：`HeadingRuleOut/Create/Update`
- `backend/app/services/heading_rule_service.py`（port）：CRUD + `active_style_overrides`
- `backend/app/routers/heading_rules.py`（**author 裁剪版**）：仅 `/heading-rules` CRUD
- `backend/app/main.py`（modify）：`include_router(heading_rules.router)`
- `backend/app/services/parse_service.py`（modify）：`parse(..., db=None)` + 注入 `style_overrides`
- `backend/app/routers/parse.py`（modify）：注入 `db`
- `backend/alembic/versions/20260531_0009_add_heading_style_rule.py`（**author 新迁移**）
- `backend/tests/unit/services/test_heading_rule_service.py`（author）
- `backend/tests/integration/test_heading_rules_api.py`（author）

---

## Task 1: 移植 model + 注册 + 新建迁移

**Files:**
- Port: `backend/app/models/heading_rule.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/20260531_0009_add_heading_style_rule.py`

- [ ] **Step 1: 取 model（单租户版，分支与本步一致）**

```bash
git checkout origin/feat/dynamic-heading-dictionary -- backend/app/models/heading_rule.py
```

- [ ] **Step 2: 在 models/__init__.py 注册**

在 `backend/app/models/__init__.py` 的 import 区（与其它 `from app.models.xxx import` 同段）加入：

```python
from app.models.heading_rule import HeadingStyleRule
```

并确保 `HeadingStyleRule` 出现在该文件的 `__all__`（若存在 `__all__` 列表）。

- [ ] **Step 3: 读取主线 head 的 revision 作 down_revision**

Run: `grep -nE "^revision" backend/alembic/versions/20260531_0008_phase3b_vendor.py`
Expected: `revision: str = "phase3b_vendor"` —— 即新迁移 `down_revision = "phase3b_vendor"`。

- [ ] **Step 4: 新建迁移文件**

`backend/alembic/versions/20260531_0009_add_heading_style_rule.py`：

```python
"""add tb_heading_style_rule (动态标题字典 M1，单租户)

Revision ID: heading_style_rule
Revises: phase3b_vendor
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "heading_style_rule"
down_revision: str | Sequence[str] | None = "phase3b_vendor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tb_heading_style_rule",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("style_name", sa.String(length=255), nullable=False),
        sa.Column("level", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("level_votes", sa.JSON(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("agreement", sa.Float(), nullable=False, server_default="0"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("style_name", name="uq_heading_style_rule_style_name"),
    )


def downgrade() -> None:
    op.drop_table("tb_heading_style_rule")
```

> 若主线迁移文件模板含额外样板（如 `Create Date`、`from typing import`），照抄 `20260531_0008` 的头部风格以保持一致。

- [ ] **Step 5: 迁移 upgrade/downgrade 双向跑通**

Run: `cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head`
Expected: 无错；`tb_heading_style_rule` 建表/删表/重建成功。

- [ ] **Step 6: 提交**

```bash
git add backend/app/models/heading_rule.py backend/app/models/__init__.py backend/alembic/versions/20260531_0009_add_heading_style_rule.py
git commit -m "feat(dict): tb_heading_style_rule 模型+注册+迁移(单租户) (P1b Task1)"
```

---

## Task 2: 移植 schema + service

**Files:**
- Port: `backend/app/schemas/heading_rule.py`、`backend/app/services/heading_rule_service.py`
- Test: `backend/tests/unit/services/test_heading_rule_service.py`（Task 创建）

- [ ] **Step 1: 取 schema + service（分支版本干净、无编号纠缠）**

```bash
git checkout origin/feat/dynamic-heading-dictionary -- \
  backend/app/schemas/heading_rule.py \
  backend/app/services/heading_rule_service.py
```

- [ ] **Step 2: import 校验**

Run: `cd backend && python -c "from app.services import heading_rule_service; from app.schemas.heading_rule import HeadingRuleCreate; print('ok')"`
Expected: 打印 `ok`。

- [ ] **Step 3: 写 service 单测**

`backend/tests/unit/services/test_heading_rule_service.py`：

```python
"""heading_rule_service 单测（P1b）。"""
from __future__ import annotations

import pytest

from app.errors import AppError  # 若主线错误基类名不同，按 app/errors.py 调整
from app.schemas.heading_rule import HeadingRuleCreate, HeadingRuleUpdate
from app.services import heading_rule_service as svc


def test_create_and_active_overrides(db) -> None:
    rule = svc.create(db, HeadingRuleCreate(style_name="章节标题", level=2))
    db.flush()
    assert rule.source == "manual" and rule.status == "active" and rule.level == 2
    assert svc.active_style_overrides(db) == {"章节标题": 2}


def test_level_zero_is_none_and_excluded_from_overrides(db) -> None:
    svc.create(db, HeadingRuleCreate(style_name="正文样式", level=0))
    db.flush()
    # level=0 归一为 None（"非标题"），不进 style_overrides
    assert "正文样式" not in svc.active_style_overrides(db)


def test_duplicate_name_conflicts(db) -> None:
    svc.create(db, HeadingRuleCreate(style_name="重复名", level=1))
    db.flush()
    with pytest.raises(AppError):
        svc.create(db, HeadingRuleCreate(style_name="重复名", level=2))


def test_update_pins_to_manual_and_bumps_revision(db) -> None:
    rule = svc.create(db, HeadingRuleCreate(style_name="改级样式", level=1))
    db.flush()
    before = rule.revision
    svc.update(db, rule, HeadingRuleUpdate(level=3))
    assert rule.level == 3 and rule.source == "manual" and rule.revision == before + 1


def test_soft_delete_excludes_from_list_and_overrides(db) -> None:
    rule = svc.create(db, HeadingRuleCreate(style_name="待删", level=1))
    db.flush()
    svc.delete(db, rule)
    db.flush()
    assert all(r.style_name != "待删" for r in svc.list_rules(db))
    assert "待删" not in svc.active_style_overrides(db)
```

> `AppError`/`conflict` 的具体类型按 `backend/app/errors.py` 实际定义调整（service 用 `conflict(...)`，断言其抛出的基类即可）。

- [ ] **Step 4: 跑测试**

Run: `cd backend && python -m pytest tests/unit/services/test_heading_rule_service.py -v`
Expected: 全 PASS（5 passed）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/schemas/heading_rule.py backend/app/services/heading_rule_service.py backend/tests/unit/services/test_heading_rule_service.py
git commit -m "feat(dict): heading_rule schema+service+单测 (P1b Task2)"
```

---

## Task 3: 裁剪版 router（仅 heading-rules）+ 挂载 + HTTP 测试

**Files:**
- Create: `backend/app/routers/heading_rules.py`（heading-only）
- Modify: `backend/app/main.py`
- Test: `backend/tests/integration/test_heading_rules_api.py`

- [ ] **Step 1: 写 heading-only router（不引入 numbering_profile，P1d 再加）**

`backend/app/routers/heading_rules.py`：

```python
"""动态标题字典-样式规则路由（M1）。

GET/POST/PUT/DELETE /api/v1/heading-rules。事务边界：service 只 flush，本路由 commit。
编号体例 /numbering-profiles 由 P1d 追加到本 router。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.schemas.heading_rule import HeadingRuleCreate, HeadingRuleOut, HeadingRuleUpdate
from app.services import heading_rule_service

router = APIRouter(prefix="/api/v1", tags=["heading-rules"])


@router.get("/heading-rules", response_model=list[HeadingRuleOut])
def list_heading_rules(db: Session = Depends(get_db)) -> list[HeadingRuleOut]:
    return [HeadingRuleOut.model_validate(r) for r in heading_rule_service.list_rules(db)]


@router.post("/heading-rules", response_model=HeadingRuleOut, status_code=status.HTTP_201_CREATED)
def create_heading_rule(payload: HeadingRuleCreate, db: Session = Depends(get_db)) -> HeadingRuleOut:
    rule = heading_rule_service.create(db, payload)
    db.commit()
    db.refresh(rule)
    return HeadingRuleOut.model_validate(rule)


@router.put("/heading-rules/{rule_id}", response_model=HeadingRuleOut)
def update_heading_rule(
    rule_id: str, payload: HeadingRuleUpdate, db: Session = Depends(get_db)
) -> HeadingRuleOut:
    rule = heading_rule_service.get_or_404(db, rule_id)
    heading_rule_service.update(db, rule, payload)
    db.commit()
    db.refresh(rule)
    return HeadingRuleOut.model_validate(rule)


@router.delete("/heading-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_heading_rule(rule_id: str, db: Session = Depends(get_db)) -> Response:
    rule = heading_rule_service.get_or_404(db, rule_id)
    heading_rule_service.delete(db, rule)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

> **get_db 一致性**：本 router 用 `from app.deps import get_db`，与主线其它 router 保持一致。`conftest.py` 覆盖的是 `app.db.get_db`——若 `app.deps.get_db` 不是同一函数对象，TestClient 的 DB 覆盖会失效。Step 4 HTTP 测试跑绿即证明一致；若 401/连真库，改为与主线既有 router 完全相同的 get_db 导入来源。

- [ ] **Step 2: main.py 挂载**

在 `backend/app/main.py` 的 router import 区加 `from app.routers import heading_rules`，并在 `app.include_router(parse.router)` 附近加：

```python
app.include_router(heading_rules.router)
```

- [ ] **Step 3: 写 HTTP CRUD 测试**

`backend/tests/integration/test_heading_rules_api.py`：

```python
"""heading-rules REST CRUD（P1b）。"""
from __future__ import annotations


def test_crud_flow(client) -> None:
    # 创建
    r = client.post("/api/v1/heading-rules", json={"style_name": "章节标题", "level": 2})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    assert r.json()["source"] == "manual" and r.json()["status"] == "active"

    # 列表
    r = client.get("/api/v1/heading-rules")
    assert r.status_code == 200
    assert any(x["style_name"] == "章节标题" for x in r.json())

    # 更新 level
    r = client.put(f"/api/v1/heading-rules/{rid}", json={"level": 3})
    assert r.status_code == 200 and r.json()["level"] == 3

    # 删除
    r = client.delete(f"/api/v1/heading-rules/{rid}")
    assert r.status_code == 204
    r = client.get("/api/v1/heading-rules")
    assert all(x["id"] != rid for x in r.json())


def test_duplicate_returns_409(client) -> None:
    client.post("/api/v1/heading-rules", json={"style_name": "重复", "level": 1})
    r = client.post("/api/v1/heading-rules", json={"style_name": "重复", "level": 2})
    assert r.status_code == 409, r.text
```

- [ ] **Step 4: 跑 HTTP 测试**

Run: `cd backend && python -m pytest tests/integration/test_heading_rules_api.py -v`
Expected: 全 PASS（2 passed）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/heading_rules.py backend/app/main.py backend/tests/integration/test_heading_rules_api.py
git commit -m "feat(dict): heading-rules router(裁剪版)+挂载+HTTP测试 (P1b Task3)"
```

---

## Task 4: parse_service 注入 active 样式规则

**Files:**
- Modify: `backend/app/services/parse_service.py`、`backend/app/routers/parse.py`

- [ ] **Step 1: parse_service 加 db 参数 + 注入 style_overrides（numbering 留 None）**

修改 `backend/app/services/parse_service.py`：

import 区加：

```python
from sqlalchemy.orm import Session

from app.services import heading_rule_service, upload_service  # 合并既有 upload_service import
```

`parse` 签名与注入：

```python
def parse(token: str, mode: str, *, db: Session | None = None) -> ParseResponse:
    if mode not in VALID_MODES:
        raise bad_request("PARSE_FAILED", f"未知解析模式：{mode}", field="parse_mode")
    data = upload_service.read_docx(token)

    # 动态标题字典：读 active 样式规则注入解析（M1）。编号体例(numbering_overrides)留待 P1d。
    style_overrides = heading_rule_service.active_style_overrides(db) if db is not None else {}

    start = time.monotonic()
    try:
        result = _run_with_timeout(data, mode, style_overrides)
    except FuturesTimeout as exc:
        ...  # 其余不变
```

`_run_with_timeout` 加形参并透传：

```python
def _run_with_timeout(
    data: bytes, mode: str, style_overrides: dict[str, int] | None = None
) -> ParseResult:
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(parse_docx, data, mode, style_overrides=style_overrides)
    try:
        return future.result(timeout=settings.parse_timeout_seconds)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
```

- [ ] **Step 2: parse 路由注入 db**

修改 `backend/app/routers/parse.py`：import `Depends`/`Session`/`get_db`，端点改：

```python
@router.post("/parse", response_model=ParseResponse)
def parse(payload: ParseRequest, db: Session = Depends(get_db)) -> ParseResponse:
    return parse_service.parse(payload.upload_token, payload.parse_mode, db=db)
```

- [ ] **Step 3: import + 既有 parse 测试回归**

Run: `cd backend && python -m pytest tests/unit/services/test_parse_service.py tests/unit/parser/test_pipeline.py -v`
Expected: PASS（db 默认 None → style_overrides={} → 行为与 P1a 后一致；若既有 test_parse_service 调用 `parse(token, mode)` 不传 db，仍因 db 默认 None 通过）。

- [ ] **Step 4: 提交**

```bash
git add backend/app/services/parse_service.py backend/app/routers/parse.py
git commit -m "feat(dict): parse_service 注入 active 样式规则(style_overrides) (P1b Task4)"
```

---

## Task 5: 注入生效集成测试（建规则 → active_style_overrides → parse_docx 应用）

**Files:**
- Test: `backend/tests/integration/test_heading_rules_api.py`（追加）

- [ ] **Step 1: 写注入测试（合成 docx + 样式覆盖改变层级）**

追加到 `backend/tests/integration/test_heading_rules_api.py`：

```python
from app.parser import parse_docx
from app.parser.eval.accuracy import level_distribution
from app.schemas.heading_rule import HeadingRuleCreate
from app.services import heading_rule_service
from tests.unit.parser._docx_builder import styled_sop


def test_active_overrides_feed_parse_docx(db) -> None:
    # 无规则：active_style_overrides 为空
    assert heading_rule_service.active_style_overrides(db) == {}
    # 建一条 active 规则
    heading_rule_service.create(db, HeadingRuleCreate(style_name="章节标题", level=2))
    db.flush()
    overrides = heading_rule_service.active_style_overrides(db)
    assert overrides == {"章节标题": 2}
    # 把 override 喂进 parse_docx：注入参数被解析链接受（不抛错、产出章节树）
    res = parse_docx(styled_sop(), "standard", style_overrides=overrides)
    assert level_distribution(res.chapters)  # 非空，注入链通
```

> 完整 HTTP `upload→建规则→/parse 按规则识别` 的端到端，复用既有 parse 集成测试的上传夹具即可（若 conftest 有 `upload_token` 类 fixture）；此处以"规则→overrides→parse_docx 接受"覆盖注入接缝，自包含不依赖上传夹具。

- [ ] **Step 2: 跑测试**

Run: `cd backend && python -m pytest tests/integration/test_heading_rules_api.py -v`
Expected: 全 PASS（3 passed）。

- [ ] **Step 3: 提交**

```bash
git add backend/tests/integration/test_heading_rules_api.py
git commit -m "test(dict): 样式规则注入解析生效集成测试 (P1b Task5)"
```

---

## Task 6: 全量回归 + golden 不变 + lint

**Files:** 无

- [ ] **Step 1: 解析回归 golden 必须不变（P1b 不改解析算法，只加注入通路；db=None 路径行为不变）**

Run: `cd backend && python -m pytest tests/regression -v`
Expected: PASS（golden 零漂移——`evaluate_corpus` 走 `parse_docx` 无 db 注入，与 P1a 后一致）。

- [ ] **Step 2: 后端相关套件**

Run: `cd backend && python -m pytest tests/unit/services tests/integration tests/unit/parser -q`
Expected: 全 PASS。

- [ ] **Step 3: ruff + （如配置）mypy**

Run: `cd backend && ruff check app/models/heading_rule.py app/schemas/heading_rule.py app/services/heading_rule_service.py app/routers/heading_rules.py app/services/parse_service.py app/routers/parse.py tests/unit/services/test_heading_rule_service.py tests/integration/test_heading_rules_api.py`
Expected: 无 error。

- [ ] **Step 4: 提交（如有修正）**

```bash
git add -A && git commit -m "chore(dict): ruff 修正 (P1b Task6)" || echo "无需提交"
```

---

## Self-Review 记录

- **Spec 覆盖**：实现 spec §1-A 的样式字典部分 + §4 解析优先级中"learned/manual 样式覆盖"的单租户形态。租户化在 P2、学习闭环在 P1c、编号体例在 P1d、前端在 P1e。
- **占位符**：无 TBD。`AppError`/get_db 来源两处为**明确的环境适配指引**（含判据：测试跑绿即证），非占位符。
- **类型一致**：`active_style_overrides(db) -> dict[str,int]`、`parse(token, mode, *, db=None)`、`_run_with_timeout(data, mode, style_overrides=None)` 跨 Task 一致；migration `revision="heading_style_rule"`/`down_revision="phase3b_vendor"` 与主线 slug 风格一致。
- **纠缠隔离**：router/parse_service 写 heading-only 裁剪版、`numbering_overrides` 不引入，明确标注 P1d 追加点——避免引用尚不存在的 `numbering_profile_service`。
- **零回归**：Task6 要求 golden 不变（注入仅在 db 非 None 的请求路径生效，`evaluate_corpus`/既有测试走无 db 路径）。
