# P1d 编号体例 numbering_profile（表+service+router追加+注入，单租户）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移植编号体例（M4b）：`tb_numbering_profile` 表 + CRUD service + 把 `/numbering-profiles` 端点追加到 P1b 的 router + `parse_service` 接 `numbering_overrides` 注入。**单租户**。落地后：管理员配「`第X条`=L3 标题」「`N.N、`=正文压制」等体例，解析按本部署体例覆盖编号判定，无需改 `_classify_numbering_base` 主干。

**Architecture:** parser 侧 M4b（`classify_numbering(text, overrides)` 壳 + `DocStats.numbering_overrides` 穿线）**已由 P1a 带入**——P1d 只补 DB/service/API/注入。model/schema/service 与 parser 线一致、可 checkout；router 与 parse_service 是**在 P1b 的裁剪版上追加**（P1b 已注明追加点）。迁移新建、链在 P1c 的 `heading_learning` 之后。

**Tech Stack:** Python 3.11+、SQLAlchemy 2.0、Alembic、FastAPI、pytest。

**前置：** P1a（`numbering_overrides` parser 形参）、P1b（router + parse_service 裁剪版）已落地。

---

## File Structure

- `backend/app/models/numbering_profile.py`（port）+ `models/__init__.py`（register）
- `backend/app/schemas/numbering_profile.py`（port）
- `backend/app/services/numbering_profile_service.py`（port：CRUD + `active_numbering_overrides`）
- `backend/app/routers/heading_rules.py`（modify：追加 `/numbering-profiles` 4 端点）
- `backend/app/services/parse_service.py`（modify：注入 `numbering_overrides`）
- `backend/alembic/versions/20260531_0011_add_numbering_profile.py`（author）
- `backend/tests/unit/services/test_numbering_profile_service.py`（author）
- `backend/tests/integration/test_numbering_profiles_api.py`（author）

---

## Task 1: 移植 model + 注册 + 迁移

**Files:**
- Port: `backend/app/models/numbering_profile.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/20260531_0011_add_numbering_profile.py`

- [ ] **Step 1: 取 model**

```bash
git checkout origin/feat/dynamic-heading-dictionary -- backend/app/models/numbering_profile.py
```

- [ ] **Step 2: 注册**

`backend/app/models/__init__.py` 加：

```python
from app.models.numbering_profile import NumberingProfile
```

- [ ] **Step 3: 新建迁移**

`backend/alembic/versions/20260531_0011_add_numbering_profile.py`：

```python
"""add tb_numbering_profile (动态标题字典 M4b，单租户)

Revision ID: numbering_profile
Revises: heading_learning
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "numbering_profile"
down_revision: str | Sequence[str] | None = "heading_learning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tb_numbering_profile",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("pattern_key", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="heading"),
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
        sa.UniqueConstraint("pattern_key", name="uq_numbering_profile_pattern_key"),
    )


def downgrade() -> None:
    op.drop_table("tb_numbering_profile")
```

- [ ] **Step 4: 迁移双向跑通**

Run: `cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head`
Expected: 无错。

- [ ] **Step 5: 提交**

```bash
git add backend/app/models/numbering_profile.py backend/app/models/__init__.py backend/alembic/versions/20260531_0011_add_numbering_profile.py
git commit -m "feat(dict): tb_numbering_profile 模型+注册+迁移(单租户) (P1d Task1)"
```

---

## Task 2: 移植 schema + service + 单测

**Files:**
- Port: `backend/app/schemas/numbering_profile.py`、`backend/app/services/numbering_profile_service.py`
- Test: `backend/tests/unit/services/test_numbering_profile_service.py`

- [ ] **Step 1: 取 schema + service**

```bash
git checkout origin/feat/dynamic-heading-dictionary -- \
  backend/app/schemas/numbering_profile.py \
  backend/app/services/numbering_profile_service.py
```

- [ ] **Step 2: import 校验**

Run: `cd backend && python -c "from app.services import numbering_profile_service; print('ok')"`
Expected: `ok`。

- [ ] **Step 3: 写 service 单测**

`backend/tests/unit/services/test_numbering_profile_service.py`：

```python
"""numbering_profile_service 单测（P1d）。"""
from __future__ import annotations

import pytest

from app.errors import AppError  # 按 app/errors.py 实际基类调整
from app.schemas.numbering_profile import NumberingProfileCreate, NumberingProfileUpdate
from app.services import numbering_profile_service as svc


def test_create_and_active_overrides(db) -> None:
    p = svc.create(db, NumberingProfileCreate(pattern_key="第X条", kind="heading", level=3))
    db.flush()
    assert p.source == "manual" and p.status == "active"
    assert svc.active_numbering_overrides(db) == {"第X条": ("heading", 3)}


def test_bad_kind_rejected(db) -> None:
    with pytest.raises(AppError):
        svc.create(db, NumberingProfileCreate(pattern_key="X", kind="bogus", level=1))


def test_duplicate_pattern_conflicts(db) -> None:
    svc.create(db, NumberingProfileCreate(pattern_key="N.N、", kind="list", level=None))
    db.flush()
    with pytest.raises(AppError):
        svc.create(db, NumberingProfileCreate(pattern_key="N.N、", kind="heading", level=2))


def test_update_pins_manual_and_bumps_revision(db) -> None:
    p = svc.create(db, NumberingProfileCreate(pattern_key="N、", kind="weak_heading", level=1))
    db.flush()
    before = p.revision
    svc.update(db, p, NumberingProfileUpdate(kind="heading", level=2))
    assert p.kind == "heading" and p.level == 2 and p.source == "manual" and p.revision == before + 1
```

- [ ] **Step 4: 跑测试**

Run: `cd backend && python -m pytest tests/unit/services/test_numbering_profile_service.py -v`
Expected: 全 PASS（4 passed）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/schemas/numbering_profile.py backend/app/services/numbering_profile_service.py backend/tests/unit/services/test_numbering_profile_service.py
git commit -m "feat(dict): numbering_profile schema+service+单测 (P1d Task2)"
```

---

## Task 3: router 追加 /numbering-profiles 端点

**Files:**
- Modify: `backend/app/routers/heading_rules.py`
- Test: `backend/tests/integration/test_numbering_profiles_api.py`

- [ ] **Step 1: 在 heading_rules.py 追加 import 与 4 端点**

在 import 区加：

```python
from app.schemas.numbering_profile import (
    NumberingProfileCreate,
    NumberingProfileOut,
    NumberingProfileUpdate,
)
from app.services import numbering_profile_service
```

在文件末尾追加：

```python
# --------------------------------------------------------------------------- #
# 编号体例（M4b）：/numbering-profiles
# --------------------------------------------------------------------------- #
@router.get("/numbering-profiles", response_model=list[NumberingProfileOut])
def list_numbering_profiles(db: Session = Depends(get_db)) -> list[NumberingProfileOut]:
    return [
        NumberingProfileOut.model_validate(p)
        for p in numbering_profile_service.list_profiles(db)
    ]


@router.post(
    "/numbering-profiles", response_model=NumberingProfileOut, status_code=status.HTTP_201_CREATED
)
def create_numbering_profile(
    payload: NumberingProfileCreate, db: Session = Depends(get_db)
) -> NumberingProfileOut:
    p = numbering_profile_service.create(db, payload)
    db.commit()
    db.refresh(p)
    return NumberingProfileOut.model_validate(p)


@router.put("/numbering-profiles/{profile_id}", response_model=NumberingProfileOut)
def update_numbering_profile(
    profile_id: str, payload: NumberingProfileUpdate, db: Session = Depends(get_db)
) -> NumberingProfileOut:
    p = numbering_profile_service.get_or_404(db, profile_id)
    numbering_profile_service.update(db, p, payload)
    db.commit()
    db.refresh(p)
    return NumberingProfileOut.model_validate(p)


@router.delete("/numbering-profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_numbering_profile(profile_id: str, db: Session = Depends(get_db)) -> Response:
    p = numbering_profile_service.get_or_404(db, profile_id)
    numbering_profile_service.delete(db, p)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 2: 写 HTTP 测试**

`backend/tests/integration/test_numbering_profiles_api.py`：

```python
"""numbering-profiles REST CRUD（P1d）。"""
from __future__ import annotations


def test_crud_flow(client) -> None:
    r = client.post("/api/v1/numbering-profiles",
                    json={"pattern_key": "第X条", "kind": "heading", "level": 3})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    r = client.get("/api/v1/numbering-profiles")
    assert any(x["pattern_key"] == "第X条" for x in r.json())

    r = client.put(f"/api/v1/numbering-profiles/{pid}", json={"level": 2})
    assert r.status_code == 200 and r.json()["level"] == 2

    r = client.delete(f"/api/v1/numbering-profiles/{pid}")
    assert r.status_code == 204


def test_bad_kind_returns_409(client) -> None:
    r = client.post("/api/v1/numbering-profiles",
                    json={"pattern_key": "X", "kind": "bogus", "level": 1})
    assert r.status_code == 409, r.text
```

- [ ] **Step 3: 跑测试**

Run: `cd backend && python -m pytest tests/integration/test_numbering_profiles_api.py -v`
Expected: 全 PASS（2 passed）。

- [ ] **Step 4: 提交**

```bash
git add backend/app/routers/heading_rules.py backend/tests/integration/test_numbering_profiles_api.py
git commit -m "feat(dict): /numbering-profiles 端点追加+HTTP测试 (P1d Task3)"
```

---

## Task 4: parse_service 注入 numbering_overrides

**Files:**
- Modify: `backend/app/services/parse_service.py`

- [ ] **Step 1: 注入编号体例（补齐 P1b 留的 numbering 空位）**

`backend/app/services/parse_service.py`：

import 区把 `from app.services import heading_rule_service, upload_service` 改为：

```python
from app.services import heading_rule_service, numbering_profile_service, upload_service
```

`parse` 内在 `style_overrides = ...` 之后加：

```python
    numbering_overrides = (
        numbering_profile_service.active_numbering_overrides(db) if db is not None else {}
    )
```

把 `result = _run_with_timeout(data, mode, style_overrides)` 改为：

```python
        result = _run_with_timeout(data, mode, style_overrides, numbering_overrides)
```

`_run_with_timeout` 签名与透传：

```python
def _run_with_timeout(
    data: bytes,
    mode: str,
    style_overrides: dict[str, int] | None = None,
    numbering_overrides: dict[str, tuple[str, int | None]] | None = None,
) -> ParseResult:
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        parse_docx, data, mode,
        style_overrides=style_overrides, numbering_overrides=numbering_overrides,
    )
    try:
        return future.result(timeout=settings.parse_timeout_seconds)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
```

- [ ] **Step 2: 既有 parse 测试回归**

Run: `cd backend && python -m pytest tests/unit/services/test_parse_service.py -v`
Expected: PASS（db=None → numbering_overrides={} → 行为不变）。

- [ ] **Step 3: 提交**

```bash
git add backend/app/services/parse_service.py
git commit -m "feat(dict): parse_service 注入 numbering_overrides (P1d Task4)"
```

---

## Task 5: 注入生效集成测试（升级 / 压制）

**Files:**
- Test: `backend/tests/integration/test_numbering_profiles_api.py`（追加）

- [ ] **Step 1: 写 overrides 喂 parse_docx 的端到端**

追加：

```python
from app.parser import classify_numbering  # 若导出路径不同，从 app.parser.heading_detector 导入
from app.schemas.numbering_profile import NumberingProfileCreate
from app.services import numbering_profile_service


def test_override_upgrades_numbering_kind(db) -> None:
    # 默认「第X条」可能非 heading；配 profile 覆盖为 heading L3
    numbering_profile_service.create(
        db, NumberingProfileCreate(pattern_key="第X条", kind="heading", level=3)
    )
    db.flush()
    overrides = numbering_profile_service.active_numbering_overrides(db)
    assert overrides["第X条"] == ("heading", 3)
    # classify_numbering 命中 profile → 返回覆盖后的 kind/level
    m = classify_numbering("第三条 适用范围", overrides)
    assert m is not None and m.kind == "heading" and m.level == 3
```

> `classify_numbering` 的 `pattern_key` 生成规则见 `heading_detector.py`；若 `第X条` 实际 pattern_key 字面不同（如带空格），按该文件实际产出的 key 配置 profile（可先 `print(classify_numbering("第三条 x", {}))` 查 pattern_key）。

- [ ] **Step 2: 跑测试**

Run: `cd backend && python -m pytest tests/integration/test_numbering_profiles_api.py -v`
Expected: 全 PASS。

- [ ] **Step 3: 提交**

```bash
git add backend/tests/integration/test_numbering_profiles_api.py
git commit -m "test(dict): 编号体例注入解析生效集成测试 (P1d Task5)"
```

---

## Task 6: 全量回归 + golden 不变 + lint

**Files:** 无

- [ ] **Step 1: 解析回归 golden 必须不变（注入仅请求路径生效，evaluate_corpus 无 db/无 profile）**

Run: `cd backend && python -m pytest tests/regression -v`
Expected: PASS（零漂移）。

- [ ] **Step 2: 后端相关套件**

Run: `cd backend && python -m pytest tests/unit/services tests/integration tests/unit/parser -q`
Expected: 全 PASS。

- [ ] **Step 3: ruff**

Run: `cd backend && ruff check app/models/numbering_profile.py app/schemas/numbering_profile.py app/services/numbering_profile_service.py app/routers/heading_rules.py app/services/parse_service.py tests/unit/services/test_numbering_profile_service.py tests/integration/test_numbering_profiles_api.py`
Expected: 无 error。

- [ ] **Step 4: 提交（如有修正）**

```bash
git add -A && git commit -m "chore(dict): ruff 修正 (P1d Task6)" || echo "无需提交"
```

---

## Self-Review 记录

- **Spec 覆盖**：实现 spec §1-A 编号体例 + §4 解析优先级中编号覆盖的单租户形态。parser 侧接缝由 P1a 提供；租户分区在 P2。
- **占位符**：无 TBD。Task5 的 "pattern_key 字面以 heading_detector 实际产出为准（含查看命令）" 是明确适配指引。
- **类型一致**：`active_numbering_overrides(db) -> dict[str, tuple[str, int|None]]` 与 `_run_with_timeout(..., numbering_overrides)` 及 P1a 的 `classify_numbering(text, overrides)` 一致；migration `revision="numbering_profile"`/`down="heading_learning"` 链正确。
- **追加而非覆盖**：router/parse_service 在 P1b 裁剪版上追加，不重写。
- **零回归**：golden 不变（Task6）。
