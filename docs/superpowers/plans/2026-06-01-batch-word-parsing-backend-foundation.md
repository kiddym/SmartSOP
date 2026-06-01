# 批量解析 Word — Plan 1：后端地基 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 SmartSOP 能"批量上传 N 份 docx → 后台异步解析出结构 + 暂存 → 进入待审阅态"，纯后端、可用 pytest 端到端验证，不触碰正式程序库。

**Architecture:** 两阶段流水线的 parse-stage。新增 `BatchImportJob`/`BatchImportItem` 两表（挂 `NullableTenantMixin`，租户隔离交给现有 ORM 事件）。批次创建 API 把上传 token 的 docx **持久化到批次暂存目录**（不依赖 24h 临时 token）。现有 `app/tasks/scheduler.py` 的 `BlockingScheduler` 新增 `batch_parse_tick` + `batch_reaper_tick` 两个 interval job：以"短事务 + 租约 + `SKIP LOCKED`"领取 `queued` 项，**`bypass_tenant_scope()` 跨租户领取、per-item `set_current_company_id` 解析**，解析产出 `ParseResponse` 形态 JSON 存为暂存 blob，图片暂存到批次 media 目录（落库阶段才提升永久 asset，属 Plan 2），item 置 `review`。审阅交互、落库属 Plan 2/3。

**Tech Stack:** Python 3.12 / FastAPI（同步 def 路由）/ SQLAlchemy 2.x ORM / Alembic / APScheduler `BlockingScheduler` / pytest（SQLite in-memory）/ ruff 0.15 + mypy 1.20 严格门禁。

**前置依赖：** `phase-0-platform-foundation` 分支（多租户：`company_id` 行隔离 / `NullableTenantMixin` / `tenant.py` / `TenantContextMiddleware` / `deps.get_current_user`）已合并到工作分支。本计划的所有 `from app.models.base import NullableTenantMixin`、`from app import tenant`、`Depends(get_current_user)` 均依赖该前提。

**非目标（属 Plan 2/3，本计划不做）：** 审阅改判 API、dry-run、apply worker、落库、图片提升永久 asset、所有前端。

---

## 关键约定（贯穿全计划，先读）

- **暂存 blob 形态 = `ParseResponse` 的 JSON**（`app/schemas/parse.py:build_parse_response` 的产物 `.model_dump()`）。与现有 `POST /parse` 响应同构，Plan 3 前端零额外适配。
- **图片**：解析阶段把 `ParseResult.image_refs` 写入批次 media 目录（emf/wmf 归一 png），blob 内图片 URL 指向新端点 `GET /api/v1/batch-imports/{job}/items/{item}/media/{filename}`。**不**在本阶段提升永久 asset（避免依赖尚不存在的 `procedure_id`），落库时再提升（Plan 2）。
- **租户上下文铁律**（worker 无 HTTP 请求 → contextvar 为空 → 现有 ORM 事件 fail-closed）：
  - 领取作业：`with tenant.bypass_tenant_scope(): ...` 跨租户领取。
  - 解析单项：`token = tenant.set_current_company_id(item.company_id)` → 解析/写库 → `tenant.reset_current_company_id(token)`。
- **SQLite 测试限制**：`with_for_update(skip_locked=True)` 在 SQLite 是 no-op，并发"不双取"只能在 MySQL 集成验证。单测验证**逻辑路径**（领取后状态变 `parsing`、租约时间写入、reaper 回收过期项），并在计划末尾标注 MySQL 集成验证项。
- **逐项提交**：worker 每解析完一项独立 `commit()`（参照 `app/tasks/asset_gc.py`），单项失败 `rollback` + 标 `failed`，不拖垮整批。

---

## 文件结构

| 文件 | 责任 | 动作 |
|---|---|---|
| `backend/app/models/batch.py` | `BatchImportJob` / `BatchImportItem` ORM 模型 | 创建 |
| `backend/app/models/__init__.py` | 导出新模型（供 `Base.metadata` 注册、conftest import） | 修改 |
| `backend/alembic/versions/20260601_0002_add_batch_import.py` | 两表迁移 | 创建 |
| `backend/app/storage.py` | 批次暂存路径助手 | 修改（追加） |
| `backend/app/schemas/batch.py` | 批次 API 的请求/响应 schema | 创建 |
| `backend/app/services/batch_media_service.py` | 解析图写入批次 media + 占位改写 | 创建 |
| `backend/app/services/batch_import_service.py` | 批次创建 + 查询 + blob 读取 | 创建 |
| `backend/app/services/batch_parse_service.py` | 领取租约 + 解析单项 + 计数重算 + reaper | 创建 |
| `backend/app/tasks/batch_parse.py` | scheduler 调用入口（parse tick / reaper tick） | 创建 |
| `backend/app/tasks/scheduler.py` | 注册两个 interval job | 修改 |
| `backend/app/routers/batch_imports.py` | 批次 REST 端点 | 创建 |
| `backend/app/main.py` | `include_router(batch_imports.router)` | 修改 |
| `backend/tests/unit/models/test_batch_models.py` | 模型/默认值测试 | 创建 |
| `backend/tests/unit/services/test_batch_import_service.py` | 批次创建/查询测试 | 创建 |
| `backend/tests/unit/services/test_batch_parse_service.py` | 领取/解析/reaper 测试 | 创建 |
| `backend/tests/integration/test_batch_imports_api.py` | API 端到端测试 | 创建 |

---

## Task 1: 数据模型 `BatchImportJob` / `BatchImportItem`

**Files:**
- Create: `backend/app/models/batch.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/unit/models/test_batch_models.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/unit/models/test_batch_models.py`:

```python
"""BatchImportJob / BatchImportItem 模型默认值与关系测试。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.batch import BatchImportItem, BatchImportJob


def test_job_defaults(db: Session) -> None:
    job = BatchImportJob(folder_id="f1", parse_mode="smart")
    db.add(job)
    db.commit()
    assert job.id  # UUID 自动生成
    assert job.status == "parsing"
    assert job.counts == {}
    assert job.is_active is True
    assert job.created_at is not None


def test_item_defaults_and_relationship(db: Session) -> None:
    job = BatchImportJob(folder_id="f1")
    db.add(job)
    db.commit()
    item = BatchImportItem(job_id=job.id, filename="a.docx")
    db.add(item)
    db.commit()
    assert item.status == "queued"
    assert item.summary == {}
    assert item.review_revision == 1
    assert item.attempts == 0
    assert item.created_procedure_id is None
    assert item.job.id == job.id
    assert job.items[0].id == item.id
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/unit/models/test_batch_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.batch'`

- [ ] **Step 3: 写模型**

Create `backend/app/models/batch.py`:

```python
"""批量导入作业与条目（批量解析 Word MVP — 后端地基）。

两阶段流水线的 parse-stage 状态载体：BatchImportJob 是一次批量上传，
BatchImportItem 是其中一份 docx。company_id 由 NullableTenantMixin 提供，
隔离交给全局 ORM 事件（app/tenant_isolation.py）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    DATETIME6,
    Base,
    NullableTenantMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDMixin,
)


class BatchImportJob(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, NullableTenantMixin):
    """一次批量导入（N 份 docx）。status 由 items 聚合冗余，便于列表与轮询。"""

    __tablename__ = "tb_batch_import_job"

    folder_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_folder.id", ondelete="RESTRICT"), index=True
    )
    parse_mode: Mapped[str] = mapped_column(String(20), default="smart", server_default="smart")
    # parsing | reviewing | completed | failed
    status: Mapped[str] = mapped_column(
        String(20), default="parsing", server_default="parsing", index=True
    )
    # {total, parsed, review, applied, failed} 冗余计数
    counts: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)

    items: Mapped[list[BatchImportItem]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class BatchImportItem(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, NullableTenantMixin):
    """批次内一份 docx 的解析/审阅/落库生命周期。"""

    __tablename__ = "tb_batch_import_item"

    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_batch_import_job.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(
        String(64), default="", server_default="", index=True
    )
    # queued | parsing | review | applying | applied | skipped | failed
    status: Mapped[str] = mapped_column(
        String(20), default="queued", server_default="queued", index=True
    )
    # {chapter_count, confidence_tier, warning_count}
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    parse_blob_ref: Mapped[str] = mapped_column(String(255), default="", server_default="")
    docx_ref: Mapped[str] = mapped_column(String(255), default="", server_default="")
    # 暂存改判乐观锁（Plan 2 PATCH review 用）
    review_revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    # 落库幂等键：非空即已落库
    created_procedure_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_procedure.id", ondelete="SET NULL"), nullable=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    leased_until: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)

    job: Mapped[BatchImportJob] = relationship(back_populates="items")
```

- [ ] **Step 4: 导出模型**

Modify `backend/app/models/__init__.py` — 在文件末尾的 import 区追加，并把两个名字加入 `__all__`：

```python
from app.models.batch import BatchImportItem, BatchImportJob  # noqa: E402
```

在 `__all__` 列表中加入 `"BatchImportJob"`, `"BatchImportItem"`（保持原有项不动）。

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/unit/models/test_batch_models.py -v`
Expected: PASS（2 passed）

- [ ] **Step 6: 门禁 + 提交**

```bash
cd backend && ruff check app/models/batch.py tests/unit/models/test_batch_models.py && ruff format app/models/batch.py && mypy app/models/batch.py
git add app/models/batch.py app/models/__init__.py tests/unit/models/test_batch_models.py
git commit -m "feat(batch): add BatchImportJob/BatchImportItem models"
```

---

## Task 2: Alembic 迁移

**Files:**
- Create: `backend/alembic/versions/20260601_0002_add_batch_import.py`

- [ ] **Step 1: 确定 down_revision（合并后的迁移头）**

phase-0 链头是 `20260531_0017_phase5b_email_storage`，step-type 链头是 `20260601_0001_add_node_step_type`，合并后会有单一 head。

Run: `cd backend && alembic heads`
Expected: 输出单一 head revision id。记下它作为下面的 `down_revision`。若输出**多个 head**（说明两链尚未线性化），先 `alembic merge heads -m "merge phase0 and step-type"` 生成合并迁移，再以其 id 作 `down_revision`。

- [ ] **Step 2: 写迁移**

Create `backend/alembic/versions/20260601_0002_add_batch_import.py`（把 `down_revision` 改成 Step 1 得到的真实 head id）:

```python
"""add tb_batch_import_job / tb_batch_import_item (batch word parsing — backend foundation)"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "add_batch_import"
down_revision: str | None = "REPLACE_WITH_ALEMBIC_HEADS_OUTPUT"  # 见 Step 1
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tb_batch_import_job",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=True),
        sa.Column("folder_id", sa.String(length=36), nullable=False),
        sa.Column("parse_mode", sa.String(length=20), nullable=False, server_default="smart"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="parsing"),
        sa.Column("counts", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"], ["tb_company.id"],
            name="fk_tb_batch_import_job_company_id", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["folder_id"], ["tb_folder.id"],
            name="fk_tb_batch_import_job_folder_id", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["tb_user.id"],
            name="fk_tb_batch_import_job_created_by", ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tb_batch_import_job"),
    )
    op.create_index("ix_tb_batch_import_job_company_id", "tb_batch_import_job", ["company_id"])
    op.create_index("ix_tb_batch_import_job_folder_id", "tb_batch_import_job", ["folder_id"])
    op.create_index("ix_tb_batch_import_job_status", "tb_batch_import_job", ["status"])
    op.create_index("ix_tb_batch_import_job_is_active", "tb_batch_import_job", ["is_active"])
    op.create_index("ix_tb_batch_import_job_created_at", "tb_batch_import_job", ["created_at"])

    op.create_table(
        "tb_batch_import_item",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=True),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("parse_blob_ref", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("docx_ref", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("review_revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_procedure_id", sa.String(length=36), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("leased_until", sa.DateTime(), nullable=True),
        sa.Column("error", sa.Text().with_variant(mysql.LONGTEXT(), "mysql"), nullable=True),
        sa.Column("reviewed_by", sa.String(length=36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"], ["tb_company.id"],
            name="fk_tb_batch_import_item_company_id", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["tb_batch_import_job.id"],
            name="fk_tb_batch_import_item_job_id", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_procedure_id"], ["tb_procedure.id"],
            name="fk_tb_batch_import_item_created_procedure_id", ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tb_batch_import_item"),
    )
    op.create_index("ix_tb_batch_import_item_company_id", "tb_batch_import_item", ["company_id"])
    op.create_index("ix_tb_batch_import_item_job_id", "tb_batch_import_item", ["job_id"])
    op.create_index("ix_tb_batch_import_item_content_hash", "tb_batch_import_item", ["content_hash"])
    op.create_index("ix_tb_batch_import_item_status", "tb_batch_import_item", ["status"])
    op.create_index("ix_tb_batch_import_item_is_active", "tb_batch_import_item", ["is_active"])
    op.create_index("ix_tb_batch_import_item_created_at", "tb_batch_import_item", ["created_at"])


def downgrade() -> None:
    op.drop_table("tb_batch_import_item")
    op.drop_table("tb_batch_import_job")
```

- [ ] **Step 3: 验证迁移可升降**

Run:
```bash
cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head
```
Expected: 无错误；`tb_batch_import_job` / `tb_batch_import_item` 创建→删除→重建成功。

- [ ] **Step 4: 提交**

```bash
cd backend && ruff check alembic/versions/20260601_0002_add_batch_import.py && ruff format alembic/versions/20260601_0002_add_batch_import.py
git add alembic/versions/20260601_0002_add_batch_import.py
git commit -m "feat(batch): migration for batch import tables"
```

---

## Task 3: 批次暂存路径助手

**Files:**
- Modify: `backend/app/storage.py`
- Test: 由 Task 4/5 的 service 测试间接覆盖（路径助手是纯函数，单独测试价值低；本任务只加函数 + 一个纯函数断言）。

- [ ] **Step 1: 写失败测试**

在 `backend/tests/unit/services/test_batch_import_service.py` 顶部先放一个路径助手断言（该文件 Task 4 会扩充）:

```python
"""批次暂存路径 + 创建/查询 service 测试。"""

from __future__ import annotations

from app import storage


def test_batch_paths_are_nested_under_storage_root(monkeypatch) -> None:
    import app.config as config_mod

    monkeypatch.setattr(config_mod.settings, "storage_dir", "/tmp/sop-test-store")
    docx = storage.batch_docx_path("job1", "item1")
    blob = storage.batch_blob_path("job1", "item1")
    media = storage.batch_media_dir("job1", "item1")
    assert docx.as_posix().endswith("batch/job1/item1/source.docx")
    assert blob.as_posix().endswith("batch/job1/item1/parse.json")
    assert media.as_posix().endswith("batch/job1/item1/media")
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/test_batch_import_service.py::test_batch_paths_are_nested_under_storage_root -v`
Expected: FAIL — `AttributeError: module 'app.storage' has no attribute 'batch_docx_path'`

- [ ] **Step 3: 追加路径助手**

在 `backend/app/storage.py` 末尾追加：

```python
def batch_root() -> Path:
    return storage_root() / "batch"


def batch_job_dir(job_id: str) -> Path:
    return batch_root() / job_id


def batch_item_dir(job_id: str, item_id: str) -> Path:
    return batch_job_dir(job_id) / item_id


def batch_docx_path(job_id: str, item_id: str) -> Path:
    return batch_item_dir(job_id, item_id) / "source.docx"


def batch_blob_path(job_id: str, item_id: str) -> Path:
    return batch_item_dir(job_id, item_id) / "parse.json"


def batch_media_dir(job_id: str, item_id: str) -> Path:
    return batch_item_dir(job_id, item_id) / "media"
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/unit/services/test_batch_import_service.py::test_batch_paths_are_nested_under_storage_root -v`
Expected: PASS

- [ ] **Step 5: 门禁 + 提交**

```bash
cd backend && ruff check app/storage.py && ruff format app/storage.py && mypy app/storage.py
git add app/storage.py tests/unit/services/test_batch_import_service.py
git commit -m "feat(batch): batch staging path helpers"
```

---

## Task 4: 批次创建 + 查询 service 与 schema

**Files:**
- Create: `backend/app/schemas/batch.py`
- Create: `backend/app/services/batch_import_service.py`
- Test: `backend/tests/unit/services/test_batch_import_service.py`（扩充）

- [ ] **Step 1: 写 schema**

Create `backend/app/schemas/batch.py`:

```python
"""批量导入 API schema（snake_case，对齐既有 API 约定）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BatchImportItemIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    upload_token: str = Field(min_length=1)


class BatchImportCreate(BaseModel):
    folder_id: str
    parse_mode: str = "smart"
    items: list[BatchImportItemIn] = Field(min_length=1)


class BatchImportJobOut(BaseModel):
    id: str
    folder_id: str
    parse_mode: str
    status: str
    counts: dict[str, int]
    created_at: datetime


class BatchImportItemOut(BaseModel):
    id: str
    job_id: str
    filename: str
    status: str
    content_hash: str
    summary: dict[str, Any]
    error: str | None
```

- [ ] **Step 2: 写失败测试**

在 `backend/tests/unit/services/test_batch_import_service.py` 追加（沿用 conftest 的 `db` / `storage_tmp` / `factory` fixture）:

```python
import io
import zipfile

import pytest
from sqlalchemy.orm import Session

from app import tenant
from app.schemas.batch import BatchImportCreate, BatchImportItemIn
from app.services import batch_import_service, upload_service


def _minimal_docx_bytes() -> bytes:
    """构造一个最小可被 is_docx_bytes 接受的 docx（zip 含 [Content_Types].xml）。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", "<document/>")
    return buf.getvalue()


def _upload(filename: str = "a.docx") -> str:
    res = upload_service.save_upload(_minimal_docx_bytes(), filename)
    return res.upload_token


def test_create_batch_persists_docx_and_queues_items(
    db: Session, storage_tmp, factory
) -> None:
    folder = factory.folder(name="目标", prefix="QC")
    tenant.set_current_company_id("co-1")
    token = _upload("first.docx")

    job = batch_import_service.create_batch(
        db,
        payload=BatchImportCreate(
            folder_id=folder.id,
            parse_mode="smart",
            items=[BatchImportItemIn(filename="first.docx", upload_token=token)],
        ),
        created_by=None,
    )
    db.commit()

    assert job.status == "parsing"
    assert job.company_id == "co-1"  # ORM 事件自动 stamp
    items = batch_import_service.list_items(db, job.id)
    assert len(items) == 1
    assert items[0].status == "queued"
    assert items[0].content_hash  # sha256 已算
    # docx 已持久化到批次目录
    from app import storage

    assert storage.batch_docx_path(job.id, items[0].id).exists()


def test_create_batch_rejects_missing_folder(db: Session, storage_tmp) -> None:
    tenant.set_current_company_id("co-1")
    token = _upload()
    with pytest.raises(Exception) as ei:
        batch_import_service.create_batch(
            db,
            payload=BatchImportCreate(
                folder_id="nope",
                items=[BatchImportItemIn(filename="a.docx", upload_token=token)],
            ),
            created_by=None,
        )
    assert "FOLDER" in str(ei.value) or "404" in str(ei.value)
```

- [ ] **Step 3: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/test_batch_import_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.batch_import_service'`

- [ ] **Step 4: 写 service**

Create `backend/app/services/batch_import_service.py`:

```python
"""批次创建与查询（parse-stage 前半：建 job/items + 持久化 docx）。"""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import storage
from app.errors import bad_request, not_found
from app.models.batch import BatchImportItem, BatchImportJob
from app.models.folder import Folder
from app.schemas.batch import BatchImportCreate
from app.services import upload_service

_VALID_MODES = {"standard", "smart"}


def create_batch(
    db: Session, *, payload: BatchImportCreate, created_by: str | None
) -> BatchImportJob:
    """建 job + N×item，并把每份 token 的 docx 持久化到批次暂存目录。

    company_id 由全局 ORM before_flush 事件按当前租户上下文自动 stamp。
    """
    if payload.parse_mode not in _VALID_MODES:
        raise bad_request("PARSE_FAILED", f"未知解析模式：{payload.parse_mode}", field="parse_mode")

    folder = db.execute(
        select(Folder).where(Folder.id == payload.folder_id, Folder.is_active.is_(True))
    ).scalar_one_or_none()
    if folder is None:
        raise not_found("FOLDER_NOT_FOUND", "目标文件夹不存在", field="folder_id")

    job = BatchImportJob(
        folder_id=payload.folder_id,
        parse_mode=payload.parse_mode,
        status="parsing",
        counts={"total": len(payload.items), "parsed": 0, "review": 0, "applied": 0, "failed": 0},
        created_by=created_by,
    )
    db.add(job)
    db.flush()  # 取 job.id

    for spec in payload.items:
        read = upload_service.try_read_source(spec.upload_token)
        if read is None:
            raise bad_request(
                "UPLOAD_TOKEN_INVALID", f"上传凭证无效或已过期：{spec.filename}", field="upload_token"
            )
        data, _src_filename = read
        item = BatchImportItem(
            job_id=job.id,
            filename=spec.filename,
            content_hash=hashlib.sha256(data).hexdigest(),
            status="queued",
        )
        db.add(item)
        db.flush()  # 取 item.id 以定位暂存路径

        path = storage.batch_docx_path(job.id, item.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        item.docx_ref = str(path.relative_to(storage.storage_root()).as_posix())

    return job


def get_job(db: Session, job_id: str) -> BatchImportJob:
    job = db.execute(
        select(BatchImportJob).where(
            BatchImportJob.id == job_id, BatchImportJob.is_active.is_(True)
        )
    ).scalar_one_or_none()
    if job is None:
        raise not_found("BATCH_JOB_NOT_FOUND", "批次不存在")
    return job


def list_items(
    db: Session, job_id: str, *, status_filter: str | None = None
) -> list[BatchImportItem]:
    stmt = (
        select(BatchImportItem)
        .where(BatchImportItem.job_id == job_id, BatchImportItem.is_active.is_(True))
        .order_by(BatchImportItem.created_at)
    )
    if status_filter:
        stmt = stmt.where(BatchImportItem.status == status_filter)
    return list(db.execute(stmt).scalars())


def get_item(db: Session, job_id: str, item_id: str) -> BatchImportItem:
    item = db.execute(
        select(BatchImportItem).where(
            BatchImportItem.id == item_id,
            BatchImportItem.job_id == job_id,
            BatchImportItem.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if item is None:
        raise not_found("BATCH_ITEM_NOT_FOUND", "批次条目不存在")
    return item


def load_blob(db: Session, job_id: str, item_id: str) -> dict:
    """读暂存 ParseResponse JSON；未解析或文件缺失 → 404。"""
    item = get_item(db, job_id, item_id)
    if not item.parse_blob_ref:
        raise not_found("BATCH_BLOB_NOT_READY", "该条目尚未解析完成")
    path = storage.batch_blob_path(job_id, item_id)
    if not path.exists():
        raise not_found("BATCH_BLOB_NOT_FOUND", "解析结果已丢失")
    return json.loads(path.read_text(encoding="utf-8"))
```

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/unit/services/test_batch_import_service.py -v`
Expected: PASS（3 passed，含 Task 3 的路径测试）

- [ ] **Step 6: 门禁 + 提交**

```bash
cd backend && ruff check app/schemas/batch.py app/services/batch_import_service.py tests/unit/services/test_batch_import_service.py && ruff format app/schemas/batch.py app/services/batch_import_service.py && mypy app/schemas/batch.py app/services/batch_import_service.py
git add app/schemas/batch.py app/services/batch_import_service.py tests/unit/services/test_batch_import_service.py
git commit -m "feat(batch): batch create + query service"
```

---

## Task 5: 解析 worker service（领取 / 解析 / 计数 / reaper）

**Files:**
- Create: `backend/app/services/batch_media_service.py`
- Create: `backend/app/services/batch_parse_service.py`
- Test: `backend/tests/unit/services/test_batch_parse_service.py`

- [ ] **Step 1: 写图片暂存 helper**

Create `backend/app/services/batch_media_service.py`:

```python
"""解析图写入批次 media 目录 + 占位 URL 改写（审阅预览用，不提升永久 asset）。

落库阶段（Plan 2）才从这里提升为永久 ProcedureAsset。
"""

from __future__ import annotations

from app import storage
from app.parser.ir import ImageRef
from app.parser.result import ParsedNode, ParseResult
from app.parser.utils import images

_API_PREFIX = "/api/v1"


def _media_url(job_id: str, item_id: str, filename: str) -> str:
    return f"{_API_PREFIX}/batch-imports/{job_id}/items/{item_id}/media/{filename}"


def _safe_name(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in ("-", "_")) or "img"


def stage_media_and_rewrite(result: ParseResult, *, job_id: str, item_id: str) -> None:
    """把 result.image_refs 写入批次 media 目录，并就地改写 chapters 里的占位 URL。"""
    media = storage.batch_media_dir(job_id, item_id)
    media.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, str] = {}
    seen: set[str] = set()

    for ref in result.image_refs:
        if ref.rid in seen:
            continue
        seen.add(ref.rid)
        data, ext = ref.data, ref.ext.lower()
        if ext in images.VECTOR_EXTS:  # emf/wmf → png 以便浏览器预览
            png = images.convert_to_png(data, ext)
            if png is not None:
                data, ext = png, ".png"
        filename = f"{_safe_name(ref.rid)}{ext}"
        (media / filename).write_bytes(data)
        mapping[ref.placeholder] = _media_url(job_id, item_id, filename)

    _rewrite(result.chapters, mapping)


def _rewrite(nodes: list[ParsedNode], mapping: dict[str, str]) -> None:
    if not mapping:
        return
    for node in nodes:
        value = node.rich_content
        if value:
            for placeholder, url in mapping.items():
                value = value.replace(f'"{placeholder}"', f'"{url}"')
            node.rich_content = value
        _rewrite(node.children, mapping)
```

- [ ] **Step 2: 写失败测试**

Create `backend/tests/unit/services/test_batch_parse_service.py`:

```python
"""领取租约 / 解析单项 / reaper 测试（解析用 monkeypatch 桩，不依赖真实 docx）。"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app import tenant
from app.models.base import utcnow
from app.models.batch import BatchImportItem, BatchImportJob
from app.parser.result import ParseMetadata, ParseResult
from app.services import batch_parse_service


def _make_job_with_item(db: Session, company_id: str = "co-1") -> tuple[str, str]:
    tenant.set_current_company_id(company_id)
    job = BatchImportJob(folder_id="f1", counts={"total": 1, "parsed": 0, "review": 0, "applied": 0, "failed": 0})
    db.add(job)
    db.flush()
    item = BatchImportItem(job_id=job.id, filename="a.docx", status="queued", docx_ref="x")
    db.add(item)
    db.commit()
    tenant.set_current_company_id(None)
    return job.id, item.id


def _fake_parse_result() -> ParseResult:
    return ParseResult(
        metadata=ParseMetadata(
            total_chapters=2, image_count=0, table_count=0,
            body_start_index=0, body_start_detected_by="test",
        ),
        chapters=[],
        parse_method="smart",
        review_required=1,
    )


def test_claim_marks_parsing_and_sets_lease(db: Session) -> None:
    job_id, item_id = _make_job_with_item(db)
    now = utcnow()
    with tenant.bypass_tenant_scope():
        claimed = batch_parse_service.claim_queued(db, limit=10, now=now, lease_ttl_seconds=300)
        db.commit()
    assert [c.id for c in claimed] == [item_id]
    fresh = db.get(BatchImportItem, item_id)
    assert fresh.status == "parsing"
    assert fresh.leased_until is not None and fresh.leased_until > now
    assert fresh.attempts == 1


def test_parse_item_writes_blob_and_sets_review(db: Session, storage_tmp, monkeypatch) -> None:
    job_id, item_id = _make_job_with_item(db)
    # 桩掉真实解析与 docx 读取
    monkeypatch.setattr(batch_parse_service, "_read_docx", lambda item: b"fake")
    monkeypatch.setattr(
        batch_parse_service, "_parse", lambda data, mode: _fake_parse_result()
    )
    item = db.get(BatchImportItem, item_id)
    item.status = "parsing"
    db.commit()

    batch_parse_service.parse_item(db, item)
    db.commit()

    fresh = db.get(BatchImportItem, item_id)
    assert fresh.status == "review"
    assert fresh.summary["chapter_count"] == 2
    assert fresh.summary["confidence_tier"] in {"high", "medium", "low"}
    assert fresh.parse_blob_ref
    from app import storage

    assert storage.batch_blob_path(job_id, item_id).exists()


def test_reclaim_expired_resets_to_queued(db: Session) -> None:
    job_id, item_id = _make_job_with_item(db)
    item = db.get(BatchImportItem, item_id)
    item.status = "parsing"
    item.leased_until = utcnow() - timedelta(seconds=10)  # 已过期
    db.commit()
    n = batch_parse_service.reclaim_expired(db, now=utcnow())
    db.commit()
    assert n == 1
    assert db.get(BatchImportItem, item_id).status == "queued"
```

- [ ] **Step 3: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/test_batch_parse_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.batch_parse_service'`

- [ ] **Step 4: 写 worker service**

Create `backend/app/services/batch_parse_service.py`:

```python
"""解析 worker（parse-stage 后半）：领取租约 + 解析单项 + 计数重算 + reaper。

租户铁律：领取用 bypass_tenant_scope() 跨租户；解析单项前 set_current_company_id
进入该 item 的租户上下文。SKIP LOCKED 在 SQLite 上是 no-op（仅 MySQL 真并发安全）。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import storage, tenant
from app.config import settings
from app.models.base import utcnow
from app.models.batch import BatchImportItem, BatchImportJob
from app.parser import parse_docx
from app.parser.result import ParseResult
from app.schemas.parse import build_parse_response
from app.services import batch_media_service

logger = logging.getLogger(__name__)

_LEASE_TTL_SECONDS = 300


def claim_queued(
    db: Session, *, limit: int, now: datetime, lease_ttl_seconds: int = _LEASE_TTL_SECONDS
) -> list[BatchImportItem]:
    """短事务领取 queued 项：SKIP LOCKED 选行 → 置 parsing + 租约 + attempts++。

    调用方须包在 `with tenant.bypass_tenant_scope():` 内并在返回后 commit。
    """
    rows = list(
        db.execute(
            select(BatchImportItem)
            .where(BatchImportItem.status == "queued", BatchImportItem.is_active.is_(True))
            .order_by(BatchImportItem.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).scalars()
    )
    for item in rows:
        item.status = "parsing"
        item.leased_until = now + timedelta(seconds=lease_ttl_seconds)
        item.attempts += 1
    db.flush()
    return rows


def _read_docx(item: BatchImportItem) -> bytes:
    """从批次暂存目录读 docx 字节（按 docx_ref 相对路径）。"""
    path = storage.storage_root() / item.docx_ref
    return path.read_bytes()


def _parse(data: bytes, mode: str) -> ParseResult:
    return parse_docx(data, mode)


def parse_item(db: Session, item: BatchImportItem) -> None:
    """解析单项：进入租户上下文 → 解析 → 暂存图 + blob + summary → status=review。

    调用方在 try 内调用本函数；异常由调用方捕获并 mark_failed。
    """
    token = tenant.set_current_company_id(item.company_id)
    try:
        job = db.get(BatchImportJob, item.job_id)
        mode = job.parse_mode if job else "smart"
        data = _read_docx(item)
        result = _parse(data, mode)

        batch_media_service.stage_media_and_rewrite(result, job_id=item.job_id, item_id=item.id)
        response = build_parse_response(result, assets=[], parse_time_ms=0)

        blob_path = storage.batch_blob_path(item.job_id, item.id)
        blob_path.parent.mkdir(parents=True, exist_ok=True)
        blob_path.write_text(
            json.dumps(response.model_dump(), ensure_ascii=False), encoding="utf-8"
        )
        item.parse_blob_ref = str(
            blob_path.relative_to(storage.storage_root()).as_posix()
        )
        item.summary = {
            "chapter_count": result.metadata.total_chapters,
            "confidence_tier": _job_tier(result),
            "warning_count": len(result.warnings),
        }
        item.status = "review"
        item.leased_until = None
        item.error = None
        _recompute_counts(db, item.job_id)
    finally:
        tenant.reset_current_company_id(token)


def _job_tier(result: ParseResult) -> str:
    """批次项整体置信：任一章节 low→low，否则任一 medium→medium，否则 high。"""
    tiers = {n_tier for n_tier in _walk_tiers(result)}
    if "low" in tiers:
        return "low"
    if "medium" in tiers:
        return "medium"
    return "high"


def _walk_tiers(result: ParseResult) -> list[str]:
    out: list[str] = []

    def walk(nodes: list) -> None:
        for n in nodes:
            out.append(n.confidence_tier)
            walk(n.children)

    walk(result.chapters)
    return out


def mark_failed(db: Session, item: BatchImportItem, message: str) -> None:
    """标记解析失败（在该 item 的租户上下文执行计数重算）。"""
    token = tenant.set_current_company_id(item.company_id)
    try:
        item.status = "failed"
        item.error = message[:2000]
        item.leased_until = None
        _recompute_counts(db, item.job_id)
    finally:
        tenant.reset_current_company_id(token)


def _recompute_counts(db: Session, job_id: str) -> None:
    """按当前 items 状态重算 job.counts 与 job.status（须在 job 的租户上下文内）。"""
    items = list(
        db.execute(
            select(BatchImportItem).where(
                BatchImportItem.job_id == job_id, BatchImportItem.is_active.is_(True)
            )
        ).scalars()
    )
    counts = {"total": len(items), "parsed": 0, "review": 0, "applied": 0, "failed": 0}
    for it in items:
        if it.status == "review":
            counts["review"] += 1
            counts["parsed"] += 1
        elif it.status == "applied":
            counts["applied"] += 1
            counts["parsed"] += 1
        elif it.status == "failed":
            counts["failed"] += 1
    job = db.get(BatchImportJob, job_id)
    if job is not None:
        job.counts = counts
        done = counts["applied"] + counts["failed"] + counts["review"]
        if counts["failed"] == counts["total"]:
            job.status = "failed"
        elif counts["review"] > 0 or counts["applied"] > 0:
            job.status = "reviewing"
        if counts["applied"] + counts["failed"] == counts["total"] and counts["total"] > 0:
            job.status = "completed"
    db.flush()


def reclaim_expired(db: Session, *, now: datetime) -> int:
    """reaper：把租约过期的 parsing/applying 项重置回 queued（崩溃自愈）。"""
    with tenant.bypass_tenant_scope():
        rows = list(
            db.execute(
                select(BatchImportItem).where(
                    BatchImportItem.status.in_(["parsing", "applying"]),
                    BatchImportItem.leased_until.is_not(None),
                    BatchImportItem.leased_until < now,
                    BatchImportItem.is_active.is_(True),
                )
            ).scalars()
        )
        for item in rows:
            item.status = "queued" if item.status == "parsing" else "review"
            item.leased_until = None
        db.flush()
    return len(rows)


def run_parse_once(db: Session, *, max_items: int = 4, now: datetime | None = None) -> dict:
    """领取一批并逐项解析（逐项提交）。返回 {claimed, parsed, failed}。"""
    started = now or utcnow()
    with tenant.bypass_tenant_scope():
        items = claim_queued(db, limit=max_items, now=started)
        db.commit()
    parsed = 0
    failed = 0
    for item in items:
        try:
            parse_item(db, item)
            db.commit()
            parsed += 1
        except Exception as exc:  # 单项失败不拖垮整批
            db.rollback()
            fresh = db.get(BatchImportItem, item.id)
            if fresh is not None:
                mark_failed(db, fresh, f"解析失败：{exc}")
                db.commit()
            failed += 1
            logger.exception("batch parse 失败 item_id=%s", item.id)
    return {"claimed": len(items), "parsed": parsed, "failed": failed}
```

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/unit/services/test_batch_parse_service.py -v`
Expected: PASS（3 passed）

- [ ] **Step 6: 门禁 + 提交**

```bash
cd backend && ruff check app/services/batch_media_service.py app/services/batch_parse_service.py tests/unit/services/test_batch_parse_service.py && ruff format app/services/batch_media_service.py app/services/batch_parse_service.py && mypy app/services/batch_media_service.py app/services/batch_parse_service.py
git add app/services/batch_media_service.py app/services/batch_parse_service.py tests/unit/services/test_batch_parse_service.py
git commit -m "feat(batch): parse worker service (claim/parse/reaper)"
```

---

## Task 6: scheduler 注册 parse tick + reaper tick

**Files:**
- Create: `backend/app/tasks/batch_parse.py`
- Modify: `backend/app/tasks/scheduler.py`
- Test: `backend/tests/unit/services/test_batch_parse_service.py`（追加 task 入口烟测）

- [ ] **Step 1: 写 task 入口**

Create `backend/app/tasks/batch_parse.py`:

```python
"""批量解析后台任务入口（由 scheduler 周期调用）。

parse tick：领取并解析一批 queued 项。reaper tick：回收过期租约。
两者都自管 Session，逐项提交在 service 内完成。
CLI（手动跑一次）：python -m app.tasks.batch_parse --once
"""

from __future__ import annotations

import argparse
import logging
import sys

from app.db import SessionLocal
from app.logging_config import configure_logging
from app.models.base import utcnow
from app.services import batch_parse_service

logger = logging.getLogger(__name__)


def run_parse(max_items: int = 4) -> dict:
    db = SessionLocal()
    try:
        return batch_parse_service.run_parse_once(db, max_items=max_items)
    finally:
        db.close()


def run_reaper() -> int:
    db = SessionLocal()
    try:
        n = batch_parse_service.reclaim_expired(db, now=utcnow())
        db.commit()
        return n
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="批量解析（一次性）")
    parser.add_argument("--once", action="store_true", help="执行一次解析 tick 后退出")
    parser.parse_args(argv)
    configure_logging()
    summary = run_parse()
    logger.info("batch_parse once: %s", summary)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
```

- [ ] **Step 2: 注册到 scheduler**

Modify `backend/app/tasks/scheduler.py`:

在 import 区把 `from app.tasks import asset_gc, cleanup_attachments, cleanup_uploads` 改为：

```python
from app.tasks import asset_gc, batch_parse, cleanup_attachments, cleanup_uploads
```

新增两个模块级回调（放在 `_run_cleanup_attachments` 之后）：

```python
def _run_batch_parse() -> None:
    batch_parse.run_parse()


def _run_batch_reaper() -> None:
    batch_parse.run_reaper()
```

在 `build_scheduler()` 的 `return sched` 之前追加两个 job：

```python
    sched.add_job(
        _run_batch_parse,
        IntervalTrigger(seconds=5),
        id="batch_parse",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    sched.add_job(
        _run_batch_reaper,
        IntervalTrigger(seconds=60),
        id="batch_reaper",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
```

- [ ] **Step 3: 写烟测**

在 `backend/tests/unit/services/test_batch_parse_service.py` 追加：

```python
def test_scheduler_registers_batch_jobs() -> None:
    from app.tasks.scheduler import build_scheduler

    sched = build_scheduler()
    ids = {j.id for j in sched.get_jobs()}
    assert "batch_parse" in ids
    assert "batch_reaper" in ids
    sched.shutdown(wait=False)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/unit/services/test_batch_parse_service.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 门禁 + 提交**

```bash
cd backend && ruff check app/tasks/batch_parse.py app/tasks/scheduler.py && ruff format app/tasks/batch_parse.py app/tasks/scheduler.py && mypy app/tasks/batch_parse.py app/tasks/scheduler.py
git add app/tasks/batch_parse.py app/tasks/scheduler.py tests/unit/services/test_batch_parse_service.py
git commit -m "feat(batch): register parse + reaper scheduler ticks"
```

---

## Task 7: 批次 REST 端点

**Files:**
- Create: `backend/app/routers/batch_imports.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/integration/test_batch_imports_api.py`

- [ ] **Step 1: 写 router**

Create `backend/app/routers/batch_imports.py`:

```python
"""批量导入路由（parse-stage：创建 + 查询 + 暂存 blob/media 读取）。

审阅改判 / dry-run / apply 属 Plan 2。所有端点经 get_current_user 进入请求
租户上下文，行级隔离自动生效。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app import storage
from app.db import get_db
from app.deps import get_current_user
from app.errors import not_found
from app.models.user import User
from app.parser.utils import images
from app.schemas.batch import BatchImportCreate, BatchImportItemOut, BatchImportJobOut
from app.services import batch_import_service

router = APIRouter(prefix="/api/v1/batch-imports", tags=["batch-imports"])


def _job_out(job: Any) -> BatchImportJobOut:
    return BatchImportJobOut(
        id=job.id,
        folder_id=job.folder_id,
        parse_mode=job.parse_mode,
        status=job.status,
        counts=job.counts or {},
        created_at=job.created_at,
    )


def _item_out(item: Any) -> BatchImportItemOut:
    return BatchImportItemOut(
        id=item.id,
        job_id=item.job_id,
        filename=item.filename,
        status=item.status,
        content_hash=item.content_hash,
        summary=item.summary or {},
        error=item.error,
    )


@router.post("", response_model=BatchImportJobOut, status_code=201)
def create_batch(
    payload: BatchImportCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BatchImportJobOut:
    job = batch_import_service.create_batch(db, payload=payload, created_by=user.id)
    db.commit()
    return _job_out(job)


@router.get("/{job_id}", response_model=BatchImportJobOut)
def get_batch(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BatchImportJobOut:
    return _job_out(batch_import_service.get_job(db, job_id))


@router.get("/{job_id}/items", response_model=list[BatchImportItemOut])
def list_items(
    job_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[BatchImportItemOut]:
    batch_import_service.get_job(db, job_id)  # 404 if absent / cross-tenant
    items = batch_import_service.list_items(db, job_id, status_filter=status_filter)
    return [_item_out(i) for i in items]


@router.get("/{job_id}/items/{item_id}/parse-result")
def get_parse_result(
    job_id: str,
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return batch_import_service.load_blob(db, job_id, item_id)


@router.get("/{job_id}/items/{item_id}/media/{filename}")
def serve_media(
    job_id: str,
    item_id: str,
    filename: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    batch_import_service.get_item(db, job_id, item_id)  # 404 / 租户隔离
    media_dir = storage.batch_media_dir(job_id, item_id)
    target = media_dir / filename
    try:
        target.resolve().relative_to(media_dir.resolve())
    except ValueError:
        raise not_found("NOT_FOUND", "图片不存在") from None
    if not target.exists():
        raise not_found("NOT_FOUND", "图片不存在")
    return Response(content=target.read_bytes(), media_type=images.mime_for_ext(target.suffix))
```

- [ ] **Step 2: 注册 router**

Modify `backend/app/main.py`:

在 `from app.routers import (...)` 列表中加入 `batch_imports,`（按字母序放在 `audit_logs,` 之后、`auth,` 之前的位置即可，保持其余不动），并在 `app.include_router(...)` 区追加：

```python
app.include_router(batch_imports.router)
```

- [ ] **Step 3: 写 API 端到端测试**

Create `backend/tests/integration/test_batch_imports_api.py`:

```python
"""批次 API 端到端：建批次 → 后台解析 → 查询 review 态 + blob。

认证：覆盖 get_current_user 依赖直接注入测试用户，并设置租户上下文。
"""

from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app import tenant
from app.deps import get_current_user
from app.main import app
from app.models.batch import BatchImportItem
from app.models.user import User
from app.services import batch_parse_service, upload_service


def _docx() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
    return buf.getvalue()


@pytest.fixture
def auth_client(client: TestClient) -> TestClient:
    fake = User(id="u-1", email="t@e.com", password_hash="x", company_id="co-1")
    app.dependency_overrides[get_current_user] = lambda: fake
    tenant.set_current_company_id("co-1")
    yield client
    app.dependency_overrides.pop(get_current_user, None)


def test_create_then_parse_then_review(
    auth_client: TestClient, engine: Engine, storage_tmp, factory, monkeypatch
) -> None:
    folder = factory.folder(name="目标", prefix="QC")
    token = upload_service.save_upload(_docx(), "a.docx").upload_token

    # 1) 建批次
    resp = auth_client.post(
        "/api/v1/batch-imports",
        json={"folder_id": folder.id, "parse_mode": "smart",
              "items": [{"filename": "a.docx", "upload_token": token}]},
    )
    assert resp.status_code == 201
    job_id = resp.json()["id"]

    # 2) 桩解析，跑一次后台 tick
    from app.parser.result import ParseMetadata, ParseResult

    monkeypatch.setattr(batch_parse_service, "_read_docx", lambda item: b"x")
    monkeypatch.setattr(
        batch_parse_service, "_parse",
        lambda data, mode: ParseResult(
            metadata=ParseMetadata(total_chapters=1, image_count=0, table_count=0,
                                   body_start_index=0, body_start_detected_by="t"),
            chapters=[], parse_method="smart"),
    )
    with Session(engine, expire_on_commit=False) as worker_db:
        batch_parse_service.run_parse_once(worker_db, max_items=10)

    # 3) 查询 items → review
    items = auth_client.get(f"/api/v1/batch-imports/{job_id}/items").json()
    assert len(items) == 1
    assert items[0]["status"] == "review"
    assert items[0]["summary"]["chapter_count"] == 1

    # 4) 拉 blob
    item_id = items[0]["id"]
    blob = auth_client.get(
        f"/api/v1/batch-imports/{job_id}/items/{item_id}/parse-result"
    ).json()
    assert blob["parse_method"] == "smart"
    assert blob["metadata"]["total_chapters"] == 1
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/integration/test_batch_imports_api.py -v`
Expected: PASS（1 passed）

> 注：测试里 worker 用**独立 Session**（`Session(engine, ...)`）模拟后台进程，验证"web 请求建批次 → 后台进程解析 → web 请求读到 review"的跨会话链路。

- [ ] **Step 5: 全量回归 + 门禁 + 提交**

```bash
cd backend && python -m pytest -q && ruff check app/routers/batch_imports.py app/main.py tests/integration/test_batch_imports_api.py && ruff format app/routers/batch_imports.py && mypy app/routers/batch_imports.py
git add app/routers/batch_imports.py app/main.py tests/integration/test_batch_imports_api.py
git commit -m "feat(batch): batch import REST endpoints (create/query/blob/media)"
```

---

## 集成验证清单（需真实 MySQL，非 SQLite 单测覆盖）

这些在 SQLite 上无法验证，执行计划完成后须在 MySQL 环境手动确认（记录结果，勿静默跳过）：

- [ ] **租约不双取**：两个 worker 进程并发跑 `run_parse_once`，同一 `queued` 项只被一个领取（`SKIP LOCKED` 真实生效）。
- [ ] **租户隔离**：A 租户的 `GET /batch-imports/{job}` 在 B 租户 token 下返回 404（ORM 事件 fail-closed）。
- [ ] **worker bypass 不泄漏**：worker `bypass_tenant_scope()` 领取跨租户项，但 `parse_item` 内 `set_current_company_id` 后任何 ORM select 只见该租户数据。
- [ ] **崩溃自愈**：人为 kill 解析中的 worker，`batch_reaper_tick` 在租约过期后把 `parsing` 项重置回 `queued` 并被重新领取。

---

## Self-Review（计划作者已核对）

- **Spec 覆盖**：本计划覆盖 spec §3 流程 ①②、§4 数据模型、§5.1/5.2/5.3/5.5/5.6 后台执行（领取/解析/租户上下文/失败重试/reaper）、§7 的创建与查询端点。§5.4 落库 worker、§6 审阅台、§7 的 apply/review/dry-run 端点、§8 落库相关不变量属 Plan 2/3，已在"非目标"标明。
- **占位扫描**：唯一需运行时确定的是迁移 `down_revision`（两条迁移链合并后的 head），已在 Task 2 Step 1 给出 `alembic heads` 确定方法与 `alembic merge` 兜底——这是真实的链合并依赖，非模糊占位。
- **类型一致性**：`claim_queued` / `parse_item` / `mark_failed` / `_recompute_counts` / `reclaim_expired` / `run_parse_once` 跨 Task 5/6 签名一致；`_read_docx` / `_parse` 是 `parse_item` 内部依赖，测试用 `monkeypatch.setattr` 桩同名函数；blob 形态统一为 `build_parse_response(...).model_dump()`；状态字符串（`queued`/`parsing`/`review`/`failed`）全计划一致。
- **依赖前提**：所有多租户引用（`NullableTenantMixin` / `tenant.bypass_tenant_scope` / `tenant.set_current_company_id` / `get_current_user`）均来自 phase-0，已在 Header 标注前置依赖。
