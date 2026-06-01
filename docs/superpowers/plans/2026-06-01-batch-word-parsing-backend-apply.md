# 批量解析 Word — Plan 2：后端落库与暂存改判 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让批量审阅的后端能力闭环——暂存改判（节点级 diff 写回 blob，乐观锁）、dry-run 影响摘要、批量应用（后台 apply worker 幂等落库 + 图片提升永久 asset）、retry/skip/undo。

**Architecture:** 两阶段流水线的 apply-stage。审阅改判 `PATCH .../review` 读-改-写暂存 blob（`review_revision` 乐观锁，409→E4）。应用 `POST .../apply` 把选中 `review` 项置 `applying` 入队；scheduler 新增 `batch_apply_tick` 以 Plan 1 同款"租约 + `SKIP LOCKED` + per-item 切租户上下文"领取并落库——从暂存 blob 重建节点树、把批次 media 图提升为永久 `ProcedureAsset`、复用 `create_procedure`/`node_numbering.recompute`/`asset_service.rebuild_references` 落库，`created_procedure_id` 作幂等键。

**Tech Stack:** 同 Plan 1（FastAPI 同步 / SQLAlchemy 2.x / APScheduler / pytest SQLite / ruff 0.15 + mypy 1.20）。

**前置依赖：** **Plan 1 已完成**（`BatchImportJob`/`BatchImportItem` 模型、暂存 blob、`batch_parse_service`、批次查询端点均已落地）；phase-0 多租户已合并。

**非目标（属 Plan 3）：** 所有前端。本计划只做后端 API + worker。

---

## 关键约定（先读）

- **落库不直接复用 `import_service.import_procedure`**：后者绑定 `upload_token` 的临时 media 与 `store_from_token`，而批量的图在批次 media 目录、docx 在批次暂存目录。本计划写独立的 `batch_apply_service`，**复用底层** `procedure_service.create_procedure` / `node_numbering.recompute` / `asset_service.find_or_create_asset` / `asset_service.rebuild_references`，自行编排。
- **图片提升**：apply 时扫描节点 body 里的批次 media URL（`/api/v1/batch-imports/{job}/items/{item}/media/{file}`），读文件 → `asset_service.find_or_create_asset` → 改写为 `asset_service.asset_url(procedure_id, asset_id)`。批次 media 在 Plan 1 解析阶段已做 emf/wmf→png 归一，这里字节可直接入库。
- **worker 无请求上下文**：构造系统 `RequestMeta(ip_address="-", user_agent="batch-apply-worker", request_id="batch")` 传给 `create_procedure`；租户铁律同 Plan 1（领取 `bypass_tenant_scope()`、解析单项 `set_current_company_id(item.company_id)`）。
- **`level_of_use` 固定 `"reference"`**（`ProcedureCreate` 必填无默认）：批量落库无法逐份指定用途，MVP 固定 reference，落库后用户可在程序编辑器改。**这是对 spec 的细化，已在本约定声明。**
- **无"编号冲突"**：`sequence_generator` 是 `FolderSequence` 自增计数器，每次给新号，批量落库**不会撞号**。故 dry-run 不含 spec §6.4 的"编号冲突→建新版本"，改为"新建 + 内容重复(content_hash)跳过"。**这是对 spec 的修正。**
- **幂等**：`apply_item` 落库前查 `created_procedure_id` 非空即返回（at-least-once 重试不重建、不烧号）。

---

## 文件结构

| 文件 | 责任 | 动作 |
|---|---|---|
| `backend/app/services/source_docx_service.py` | 增 `store_from_bytes`（从字节存源 docx，apply 用） | 修改（追加） |
| `backend/app/services/batch_apply_service.py` | 图片提升 + 节点树重建 + `apply_item` + 领取 applying + run_apply_once | 创建 |
| `backend/app/services/batch_review_service.py` | 暂存改判（读-改-写 blob + 乐观锁）+ dry-run preview + retry/skip/undo | 创建 |
| `backend/app/schemas/batch.py` | 增改判/preview/apply 的请求响应 schema | 修改（追加） |
| `backend/app/tasks/batch_parse.py` | 增 `run_apply()` 入口 | 修改（追加） |
| `backend/app/tasks/scheduler.py` | 注册 `batch_apply_tick` | 修改 |
| `backend/app/routers/batch_imports.py` | 增 review/apply-preview/apply/retry/skip/undo 端点 | 修改 |
| `backend/tests/unit/services/test_batch_review_service.py` | 改判/preview/retry/skip/undo 测试 | 创建 |
| `backend/tests/unit/services/test_batch_apply_service.py` | 落库/幂等/图片提升测试 | 创建 |
| `backend/tests/integration/test_batch_apply_api.py` | apply 端到端 | 创建 |

---

## Task 1: 落库 service `batch_apply_service`

**Files:**
- Modify: `backend/app/services/source_docx_service.py`
- Create: `backend/app/services/batch_apply_service.py`
- Test: `backend/tests/unit/services/test_batch_apply_service.py`

- [ ] **Step 1: 源 docx 从字节存储变体**

在 `backend/app/services/source_docx_service.py` 追加（复用现有 `import hashlib` / `storage` / `ProcedureSourceDocx`）:

```python
def store_from_bytes(
    db: Session, *, procedure_group_id: str, data: bytes, filename: str
) -> ProcedureSourceDocx | None:
    """从内存字节持久化源 docx（批量 apply 用，docx 已在批次暂存目录）。

    非法/超限 → None（降级，不阻断落库），与 store_from_token 一致。
    """
    if len(data) > settings.upload_max_size_mb * 1024 * 1024 or not is_docx_bytes(data):
        return None
    filename = filename[:_FILENAME_MAX]
    path = storage.source_docx_path(procedure_group_id)
    row = ProcedureSourceDocx(
        procedure_group_id=procedure_group_id,
        filename=filename,
        storage_path=str(path.relative_to(storage.storage_root())),
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
    )
    db.add(row)
    db.flush()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_bytes(data)
    except OSError:
        path.unlink(missing_ok=True)
        raise
    return row
```

- [ ] **Step 2: 写失败测试**

Create `backend/tests/unit/services/test_batch_apply_service.py`:

```python
"""批量落库：节点树重建 / 图片提升 / 幂等。"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app import storage, tenant
from app.models.batch import BatchImportItem, BatchImportJob
from app.models.procedure import Procedure
from app.services import batch_apply_service


def _seed_review_item(db: Session, *, folder_id: str, company_id: str = "co-1") -> BatchImportItem:
    tenant.set_current_company_id(company_id)
    job = BatchImportJob(folder_id=folder_id, parse_mode="smart",
                         counts={"total": 1, "parsed": 1, "review": 1, "applied": 0, "failed": 0})
    db.add(job)
    db.flush()
    item = BatchImportItem(
        job_id=job.id, filename="alpha.docx", status="review",
        docx_ref="batch/x/y/source.docx",
    )
    db.add(item)
    db.flush()
    # 写一份最小 blob（ParseResponse 形态）
    blob = {
        "metadata": {"total_chapters": 1, "image_count": 0, "table_count": 0,
                     "body_start_index": 0, "body_start_detected_by": "t",
                     "format": "docx", "parse_time_ms": 0},
        "chapters": [
            {"id": "n1", "title": "第一章", "level": 1, "order": 0, "parent_id": None,
             "content_type": "chapter", "rich_content": "", "skip_numbering": False,
             "confidence": 1.0, "confidence_tier": "high", "mark_status": "unmarked",
             "heading_source": "style", "children": [
                {"id": "n2", "title": "", "level": 2, "order": 0, "parent_id": "n1",
                 "content_type": "content", "rich_content": "<p>正文</p>", "skip_numbering": False,
                 "confidence": 1.0, "confidence_tier": "high", "mark_status": "unmarked",
                 "heading_source": None, "children": []},
             ]},
        ],
        "assets": [], "detected_patterns": [], "validation": None, "warnings": [],
        "review_required": 0, "parse_method": "smart",
    }
    path = storage.batch_blob_path(item.job_id, item.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob), encoding="utf-8")
    item.parse_blob_ref = str(path.relative_to(storage.storage_root()).as_posix())
    db.commit()
    return item


def test_apply_item_creates_procedure_with_nodes(db: Session, storage_tmp, factory) -> None:
    folder = factory.folder(name="目标", prefix="QC")
    factory.sequence(folder.id)
    item = _seed_review_item(db, folder_id=folder.id)

    batch_apply_service.apply_item(db, item)
    db.commit()

    fresh = db.get(BatchImportItem, item.id)
    assert fresh.status == "applied"
    assert fresh.created_procedure_id is not None
    proc = db.get(Procedure, fresh.created_procedure_id)
    assert proc is not None
    assert proc.code.startswith("QC-")
    assert proc.level_of_use == "reference"


def test_apply_item_is_idempotent(db: Session, storage_tmp, factory) -> None:
    folder = factory.folder(name="目标", prefix="QC")
    factory.sequence(folder.id)
    item = _seed_review_item(db, folder_id=folder.id)

    batch_apply_service.apply_item(db, item)
    db.commit()
    first_pid = db.get(BatchImportItem, item.id).created_procedure_id

    item.status = "applying"  # 模拟重试
    db.commit()
    batch_apply_service.apply_item(db, item)
    db.commit()
    assert db.get(BatchImportItem, item.id).created_procedure_id == first_pid
```

- [ ] **Step 3: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/test_batch_apply_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.batch_apply_service'`

- [ ] **Step 4: 写 service**

Create `backend/app/services/batch_apply_service.py`:

```python
"""批量落库 worker（apply-stage）：从暂存 blob 重建节点树并落定稿程序。

复用 procedure_service.create_procedure / node_numbering.recompute /
asset_service。图片从批次 media 提升为永久 asset。created_procedure_id 幂等。
"""

from __future__ import annotations

import html
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import storage, tenant
from app.deps import RequestMeta
from app.models.base import utcnow
from app.models.batch import BatchImportItem, BatchImportJob
from app.models.node import ProcedureNode
from app.schemas.procedure import ProcedureCreate
from app.services import (
    asset_service,
    batch_parse_service,
    node_numbering,
    procedure_service,
    source_docx_service,
)

logger = logging.getLogger(__name__)

_SYSTEM_META = RequestMeta(ip_address="-", user_agent="batch-apply-worker", request_id="batch")
_MEDIA_RE = re.compile(
    r"/api/v1/batch-imports/[0-9a-fA-F-]+/items/[0-9a-fA-F-]+/media/([^\"]+)"
)
_LEASE_TTL_SECONDS = 600


def _proc_name(filename: str) -> str:
    base = filename.rsplit(".", 1)[0].strip() or filename
    return base[:200]


def _chapter_body(title: str) -> str:
    return f"<p>{html.escape(title)}</p>"


def _promote_media(db: Session, procedure_id: str, body: str, *, job_id: str, item_id: str) -> str:
    """把 body 里的批次 media URL 提升为永久 asset，改写成 procedure asset URL。"""
    media_dir = storage.batch_media_dir(job_id, item_id)

    def repl(m: re.Match[str]) -> str:
        filename = m.group(1)
        path = media_dir / filename
        try:
            path.resolve().relative_to(media_dir.resolve())
        except ValueError:
            return m.group(0)
        if not path.exists():
            return m.group(0)  # 缺失降级，原样保留
        asset = asset_service.find_or_create_asset(
            db, path.read_bytes(), ext=Path(filename).suffix,
            source_meta={"source": "batch_import", "job_id": job_id},
        )
        return asset_service.asset_url(procedure_id, asset.id)

    return _MEDIA_RE.sub(repl, body)


def _build_nodes(
    db: Session, procedure_id: str, chapters: list[dict], *, job_id: str, item_id: str
) -> None:
    order = 0

    def walk(nodes: list[dict]) -> None:
        nonlocal order
        for n in nodes:
            order += 1
            if n.get("content_type") == "chapter":
                body = _chapter_body(n.get("title", ""))
                heading_level = n.get("level")
            else:
                body = _promote_media(
                    db, procedure_id, n.get("rich_content", ""), job_id=job_id, item_id=item_id
                )
                heading_level = None
            db.add(
                ProcedureNode(
                    procedure_id=procedure_id,
                    body=body,
                    sort_order=order * 1000,
                    heading_level=heading_level,
                    kind="node",
                    skip_numbering=bool(n.get("skip_numbering", False)),
                    input_schema={},
                    mark_status="unmarked",
                )
            )
            walk(n.get("children", []))

    walk(chapters)
    db.flush()


def apply_item(db: Session, item: BatchImportItem) -> None:
    """落库单项：进入租户上下文，幂等检查，建 procedure + 节点树 + 源 docx。"""
    token = tenant.set_current_company_id(item.company_id)
    try:
        if item.created_procedure_id is not None:  # 幂等
            item.status = "applied"
            batch_parse_service._recompute_counts(db, item.job_id)
            return
        job = db.get(BatchImportJob, item.job_id)
        if job is None:
            raise RuntimeError("批次不存在")

        blob_path = storage.batch_blob_path(item.job_id, item.id)
        blob = json.loads(blob_path.read_text(encoding="utf-8"))

        proc = procedure_service.create_procedure(
            db,
            ProcedureCreate(folder_id=job.folder_id, name=_proc_name(item.filename),
                            level_of_use="reference"),
            _SYSTEM_META,
        )
        _build_nodes(db, proc.id, blob.get("chapters", []), job_id=item.job_id, item_id=item.id)
        node_numbering.recompute(db, proc.id)
        asset_service.rebuild_references(db, proc.id)

        docx_path = storage.storage_root() / item.docx_ref
        if docx_path.exists():
            source_docx_service.store_from_bytes(
                db, procedure_group_id=proc.procedure_group_id,
                data=docx_path.read_bytes(), filename=item.filename,
            )

        item.created_procedure_id = proc.id
        item.status = "applied"
        item.leased_until = None
        item.error = None
        batch_parse_service._recompute_counts(db, item.job_id)
    finally:
        tenant.reset_current_company_id(token)


def claim_applying(
    db: Session, *, limit: int, now: datetime, lease_ttl_seconds: int = _LEASE_TTL_SECONDS
) -> list[BatchImportItem]:
    """领取 applying 项（调用方包 bypass_tenant_scope + commit）。"""
    rows = list(
        db.execute(
            select(BatchImportItem)
            .where(BatchImportItem.status == "applying", BatchImportItem.is_active.is_(True))
            .order_by(BatchImportItem.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).scalars()
    )
    for item in rows:
        item.leased_until = now + timedelta(seconds=lease_ttl_seconds)
        item.attempts += 1
    db.flush()
    return rows


def run_apply_once(db: Session, *, max_items: int = 4, now: datetime | None = None) -> dict:
    started = now or utcnow()
    with tenant.bypass_tenant_scope():
        items = claim_applying(db, limit=max_items, now=started)
        db.commit()
    applied = 0
    failed = 0
    for item in items:
        try:
            apply_item(db, item)
            db.commit()
            applied += 1
        except Exception as exc:
            db.rollback()
            fresh = db.get(BatchImportItem, item.id)
            if fresh is not None:
                batch_parse_service.mark_failed(db, fresh, f"落库失败：{exc}")
                db.commit()
            failed += 1
            logger.exception("batch apply 失败 item_id=%s", item.id)
    return {"claimed": len(items), "applied": applied, "failed": failed}
```

> 注：`apply_item` 复用 `batch_parse_service._recompute_counts` / `mark_failed`（Plan 1 已定义），保持单一计数逻辑。

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/unit/services/test_batch_apply_service.py -v`
Expected: PASS（2 passed）

- [ ] **Step 6: 门禁 + 提交**

```bash
cd backend && ruff check app/services/source_docx_service.py app/services/batch_apply_service.py tests/unit/services/test_batch_apply_service.py && ruff format app/services/source_docx_service.py app/services/batch_apply_service.py && mypy app/services/batch_apply_service.py app/services/source_docx_service.py
git add app/services/source_docx_service.py app/services/batch_apply_service.py tests/unit/services/test_batch_apply_service.py
git commit -m "feat(batch): apply worker service (idempotent landing + media promote)"
```

---

## Task 2: apply 入队 API + scheduler apply tick

**Files:**
- Modify: `backend/app/schemas/batch.py`
- Modify: `backend/app/services/batch_review_service.py`（本任务先建文件，含 enqueue_apply；改判/preview 在 Task 3/4）
- Modify: `backend/app/tasks/batch_parse.py`
- Modify: `backend/app/tasks/scheduler.py`
- Modify: `backend/app/routers/batch_imports.py`
- Test: `backend/tests/integration/test_batch_apply_api.py`

- [ ] **Step 1: 增 schema**

在 `backend/app/schemas/batch.py` 追加：

```python
class BatchApplyRequest(BaseModel):
    item_ids: list[str] | None = None  # None = 该批次全部 review 项
    high_confidence_only: bool = False


class BatchApplyResult(BaseModel):
    enqueued: int
```

- [ ] **Step 2: 写 enqueue service**

Create `backend/app/services/batch_review_service.py`（本任务先放 enqueue_apply，Task 3/4 追加其余）:

```python
"""批量审阅后端：应用入队 / dry-run / 暂存改判 / retry / skip / undo。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import bad_request
from app.models.batch import BatchImportItem
from app.services import batch_import_service


def enqueue_apply(
    db: Session, job_id: str, *, item_ids: list[str] | None, high_confidence_only: bool
) -> int:
    """把选中的 review 项置 applying 入队。返回入队数。"""
    batch_import_service.get_job(db, job_id)  # 404 / 租户隔离
    stmt = select(BatchImportItem).where(
        BatchImportItem.job_id == job_id,
        BatchImportItem.status == "review",
        BatchImportItem.is_active.is_(True),
    )
    if item_ids:
        stmt = stmt.where(BatchImportItem.id.in_(item_ids))
    items = list(db.execute(stmt).scalars())
    if high_confidence_only:
        items = [i for i in items if (i.summary or {}).get("confidence_tier") == "high"]
    if not items:
        raise bad_request("BATCH_NO_APPLICABLE_ITEMS", "没有可应用的待审阅条目")
    for item in items:
        item.status = "applying"
        item.leased_until = None
    db.flush()
    return len(items)
```

- [ ] **Step 3: 增 task 入口 + 注册 scheduler**

在 `backend/app/tasks/batch_parse.py` 追加：

```python
def run_apply(max_items: int = 4) -> dict:
    from app.services import batch_apply_service

    db = SessionLocal()
    try:
        return batch_apply_service.run_apply_once(db, max_items=max_items)
    finally:
        db.close()
```

在 `backend/app/tasks/scheduler.py` 的 `_run_batch_reaper` 之后追加回调，并在 `build_scheduler()` 注册：

```python
def _run_batch_apply() -> None:
    batch_parse.run_apply()
```

```python
    sched.add_job(
        _run_batch_apply,
        IntervalTrigger(seconds=5),
        id="batch_apply",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
```

- [ ] **Step 4: 增 apply 端点**

在 `backend/app/routers/batch_imports.py` 增 import 与端点：

```python
from app.schemas.batch import BatchApplyRequest, BatchApplyResult
from app.services import batch_review_service
```

```python
@router.post("/{job_id}/apply", response_model=BatchApplyResult)
def apply_batch(
    job_id: str,
    payload: BatchApplyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BatchApplyResult:
    n = batch_review_service.enqueue_apply(
        db, job_id, item_ids=payload.item_ids, high_confidence_only=payload.high_confidence_only
    )
    db.commit()
    return BatchApplyResult(enqueued=n)
```

- [ ] **Step 5: 写端到端测试**

Create `backend/tests/integration/test_batch_apply_api.py`:

```python
"""apply 端到端：建批次→解析→apply 入队→apply worker 落库→程序生成。"""

from __future__ import annotations

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app import storage, tenant
from app.deps import get_current_user
from app.main import app
from app.models.batch import BatchImportItem
from app.models.procedure import Procedure
from app.models.user import User
from app.services import batch_apply_service


@pytest.fixture
def auth_client(client: TestClient):
    fake = User(id="u-1", email="t@e.com", password_hash="x", company_id="co-1")
    app.dependency_overrides[get_current_user] = lambda: fake
    tenant.set_current_company_id("co-1")
    yield client
    app.dependency_overrides.pop(get_current_user, None)


def _seed_blob(item: BatchImportItem) -> None:
    blob = {
        "metadata": {"total_chapters": 1, "image_count": 0, "table_count": 0,
                     "body_start_index": 0, "body_start_detected_by": "t",
                     "format": "docx", "parse_time_ms": 0},
        "chapters": [{"id": "n1", "title": "章", "level": 1, "order": 0, "parent_id": None,
                      "content_type": "chapter", "rich_content": "", "skip_numbering": False,
                      "confidence": 1.0, "confidence_tier": "high", "mark_status": "unmarked",
                      "heading_source": "style", "children": []}],
        "assets": [], "detected_patterns": [], "validation": None, "warnings": [],
        "review_required": 0, "parse_method": "smart",
    }
    path = storage.batch_blob_path(item.job_id, item.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob), encoding="utf-8")
    item.parse_blob_ref = str(path.relative_to(storage.storage_root()).as_posix())


def test_apply_flow_creates_procedure(
    auth_client: TestClient, engine: Engine, storage_tmp, factory, db: Session
) -> None:
    folder = factory.folder(name="目标", prefix="QC")
    factory.sequence(folder.id)
    from app.models.batch import BatchImportJob

    tenant.set_current_company_id("co-1")
    job = BatchImportJob(folder_id=folder.id, parse_mode="smart",
                         counts={"total": 1, "parsed": 1, "review": 1, "applied": 0, "failed": 0})
    db.add(job)
    db.flush()
    item = BatchImportItem(job_id=job.id, filename="a.docx", status="review", docx_ref="x")
    db.add(item)
    db.flush()
    _seed_blob(item)
    db.commit()

    # 入队
    resp = auth_client.post(f"/api/v1/batch-imports/{job.id}/apply", json={"item_ids": [item.id]})
    assert resp.status_code == 200
    assert resp.json()["enqueued"] == 1

    # worker 落库
    with Session(engine, expire_on_commit=False) as worker_db:
        batch_apply_service.run_apply_once(worker_db, max_items=10)

    fresh = db.get(BatchImportItem, item.id)
    db.refresh(fresh)
    assert fresh.status == "applied"
    proc = db.get(Procedure, fresh.created_procedure_id)
    assert proc is not None and proc.code.startswith("QC-")
```

- [ ] **Step 6: 运行 + 门禁 + 提交**

Run: `cd backend && python -m pytest tests/integration/test_batch_apply_api.py -v`
Expected: PASS

```bash
cd backend && ruff check app/schemas/batch.py app/services/batch_review_service.py app/tasks/batch_parse.py app/tasks/scheduler.py app/routers/batch_imports.py tests/integration/test_batch_apply_api.py && ruff format app/schemas/batch.py app/services/batch_review_service.py && mypy app/services/batch_review_service.py app/tasks/batch_parse.py
git add app/schemas/batch.py app/services/batch_review_service.py app/tasks/batch_parse.py app/tasks/scheduler.py app/routers/batch_imports.py tests/integration/test_batch_apply_api.py
git commit -m "feat(batch): apply enqueue API + apply scheduler tick"
```

---

## Task 3: dry-run 影响摘要

**Files:**
- Modify: `backend/app/schemas/batch.py`
- Modify: `backend/app/services/batch_review_service.py`
- Modify: `backend/app/routers/batch_imports.py`
- Test: `backend/tests/unit/services/test_batch_review_service.py`

- [ ] **Step 1: 增 schema**

在 `backend/app/schemas/batch.py` 追加：

```python
class ApplyPreviewOut(BaseModel):
    to_create: int  # 将新建程序数
    duplicate_skip: int  # content_hash 命中已落库 → 跳过
    target_folder_id: str
```

- [ ] **Step 2: 写失败测试**

Create `backend/tests/unit/services/test_batch_review_service.py`:

```python
"""暂存改判 / dry-run / retry / skip / undo 测试。"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app import storage, tenant
from app.models.batch import BatchImportItem, BatchImportJob
from app.services import batch_review_service


def _job(db: Session, folder_id: str = "f1", company_id: str = "co-1") -> BatchImportJob:
    tenant.set_current_company_id(company_id)
    job = BatchImportJob(folder_id=folder_id,
                         counts={"total": 0, "parsed": 0, "review": 0, "applied": 0, "failed": 0})
    db.add(job)
    db.flush()
    return job


def _item(db: Session, job: BatchImportJob, *, status: str, content_hash: str = "",
          procedure_id: str | None = None) -> BatchImportItem:
    item = BatchImportItem(job_id=job.id, filename="a.docx", status=status,
                           content_hash=content_hash, created_procedure_id=procedure_id)
    db.add(item)
    db.flush()
    return item


def test_preview_counts_new_and_duplicates(db: Session) -> None:
    job = _job(db)
    _item(db, job, status="applied", content_hash="HASH1", procedure_id="p-existing")
    a = _item(db, job, status="review", content_hash="HASH2")
    b = _item(db, job, status="review", content_hash="HASH1")  # 与已 applied 重复
    db.commit()

    out = batch_review_service.preview_apply(db, job.id, item_ids=[a.id, b.id])
    assert out.to_create == 1
    assert out.duplicate_skip == 1
    assert out.target_folder_id == "f1"
```

- [ ] **Step 3: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/test_batch_review_service.py::test_preview_counts_new_and_duplicates -v`
Expected: FAIL — `AttributeError: module 'app.services.batch_review_service' has no attribute 'preview_apply'`

- [ ] **Step 4: 写 preview**

在 `backend/app/services/batch_review_service.py` 追加（顶部 import 增 `from app.schemas.batch import ApplyPreviewOut`）:

```python
def preview_apply(
    db: Session, job_id: str, *, item_ids: list[str] | None
) -> ApplyPreviewOut:
    """dry-run：统计新建数 + content_hash 命中已落库的重复跳过数。

    无"编号冲突"——FolderSequence 自增取号不撞号。
    """
    job = batch_import_service.get_job(db, job_id)
    stmt = select(BatchImportItem).where(
        BatchImportItem.job_id == job_id,
        BatchImportItem.status == "review",
        BatchImportItem.is_active.is_(True),
    )
    if item_ids:
        stmt = stmt.where(BatchImportItem.id.in_(item_ids))
    candidates = list(db.execute(stmt).scalars())

    applied_hashes = {
        h for (h,) in db.execute(
            select(BatchImportItem.content_hash).where(
                BatchImportItem.status == "applied",
                BatchImportItem.content_hash != "",
                BatchImportItem.is_active.is_(True),
            )
        )
    }
    duplicate = sum(1 for c in candidates if c.content_hash and c.content_hash in applied_hashes)
    return ApplyPreviewOut(
        to_create=len(candidates) - duplicate,
        duplicate_skip=duplicate,
        target_folder_id=job.folder_id,
    )
```

- [ ] **Step 5: 增端点**

在 `backend/app/routers/batch_imports.py` 增 import `ApplyPreviewOut`、`BatchApplyRequest`（已有），并加端点：

```python
from app.schemas.batch import ApplyPreviewOut


@router.post("/{job_id}/apply-preview", response_model=ApplyPreviewOut)
def apply_preview(
    job_id: str,
    payload: BatchApplyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApplyPreviewOut:
    return batch_review_service.preview_apply(db, job_id, item_ids=payload.item_ids)
```

- [ ] **Step 6: 运行 + 门禁 + 提交**

Run: `cd backend && python -m pytest tests/unit/services/test_batch_review_service.py -v`
Expected: PASS

```bash
cd backend && ruff check app/schemas/batch.py app/services/batch_review_service.py app/routers/batch_imports.py tests/unit/services/test_batch_review_service.py && ruff format app/services/batch_review_service.py && mypy app/services/batch_review_service.py
git add app/schemas/batch.py app/services/batch_review_service.py app/routers/batch_imports.py tests/unit/services/test_batch_review_service.py
git commit -m "feat(batch): dry-run apply-preview"
```

---

## Task 4: 暂存改判（节点级 diff，乐观锁）

**Files:**
- Modify: `backend/app/schemas/batch.py`
- Modify: `backend/app/services/batch_review_service.py`
- Modify: `backend/app/routers/batch_imports.py`
- Test: `backend/tests/unit/services/test_batch_review_service.py`（追加）

- [ ] **Step 1: 增 schema**

在 `backend/app/schemas/batch.py` 追加：

```python
from typing import Literal


class ReviewOp(BaseModel):
    node_id: str
    action: Literal["accept", "to_content", "to_chapter", "set_level"]
    level: int | None = None  # set_level 时必填


class ReviewPatchRequest(BaseModel):
    review_revision: int
    ops: list[ReviewOp] = Field(min_length=1)


class ReviewPatchResult(BaseModel):
    review_revision: int
```

- [ ] **Step 2: 写失败测试**

在 `backend/tests/unit/services/test_batch_review_service.py` 追加：

```python
import pytest

from app.errors import HTTPException
from app.schemas.batch import ReviewOp, ReviewPatchRequest


def _review_item_with_blob(db: Session, job: BatchImportJob) -> BatchImportItem:
    item = _item(db, job, status="review")
    blob = {
        "metadata": {}, "assets": [], "detected_patterns": [], "validation": None,
        "warnings": [], "review_required": 1, "parse_method": "smart",
        "chapters": [{"id": "n1", "title": "标题", "level": 2, "order": 0, "parent_id": None,
                      "content_type": "chapter", "rich_content": "", "skip_numbering": False,
                      "confidence": 0.5, "confidence_tier": "medium", "mark_status": "review",
                      "heading_source": "heuristic", "children": []}],
    }
    path = storage.batch_blob_path(item.job_id, item.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob), encoding="utf-8")
    item.parse_blob_ref = str(path.relative_to(storage.storage_root()).as_posix())
    db.commit()
    return item


def test_apply_review_ops_rewrites_blob_and_bumps_revision(db: Session, storage_tmp) -> None:
    job = _job(db)
    item = _review_item_with_blob(db, job)
    assert item.review_revision == 1

    result = batch_review_service.apply_review_ops(
        db, job.id, item.id,
        payload=ReviewPatchRequest(
            review_revision=1,
            ops=[ReviewOp(node_id="n1", action="to_content"),
                 ReviewOp(node_id="n1", action="accept")],
        ),
    )
    db.commit()
    assert result.review_revision == 2
    blob = batch_import_service.load_blob(db, job.id, item.id)
    assert blob["chapters"][0]["content_type"] == "content"
    assert blob["chapters"][0]["mark_status"] == "unmarked"


def test_apply_review_ops_conflict_raises_409(db: Session, storage_tmp) -> None:
    job = _job(db)
    item = _review_item_with_blob(db, job)
    with pytest.raises(HTTPException) as ei:
        batch_review_service.apply_review_ops(
            db, job.id, item.id,
            payload=ReviewPatchRequest(
                review_revision=99,  # 陈旧
                ops=[ReviewOp(node_id="n1", action="accept")],
            ),
        )
    assert ei.value.status_code == 409
```

注：测试需 `from app.services import batch_import_service`（文件顶部补 import）；`HTTPException` 从 `fastapi` 导入（`from fastapi import HTTPException`）。

- [ ] **Step 3: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/test_batch_review_service.py -k review_ops -v`
Expected: FAIL — `AttributeError: ... has no attribute 'apply_review_ops'`

- [ ] **Step 4: 写改判 service**

在 `backend/app/services/batch_review_service.py` 追加（顶部 import 增 `json`、`storage`、`conflict`、`not_found`、`ReviewPatchRequest`、`ReviewPatchResult`）:

```python
def apply_review_ops(
    db: Session, job_id: str, item_id: str, *, payload: ReviewPatchRequest
) -> ReviewPatchResult:
    """读-改-写暂存 blob 的节点判定，review_revision 乐观锁（冲突 409）。"""
    item = batch_import_service.get_item(db, job_id, item_id)
    if item.review_revision != payload.review_revision:
        raise conflict("VERSION_CONFLICT", "该条目已被修改，请刷新后重试")
    if not item.parse_blob_ref:
        raise not_found("BATCH_BLOB_NOT_READY", "该条目尚未解析完成")

    path = storage.batch_blob_path(job_id, item_id)
    blob = json.loads(path.read_text(encoding="utf-8"))
    index = _index_nodes(blob.get("chapters", []))

    for op in payload.ops:
        node = index.get(op.node_id)
        if node is None:
            raise not_found("BATCH_NODE_NOT_FOUND", f"节点不存在：{op.node_id}")
        if op.action == "to_content":
            node["content_type"] = "content"
        elif op.action == "to_chapter":
            node["content_type"] = "chapter"
        elif op.action == "set_level":
            if op.level is None:
                raise bad_request("VALIDATION_FAILED", "set_level 需指定 level", field="level")
            node["level"] = op.level
        elif op.action == "accept":
            node["mark_status"] = "unmarked"

    path.write_text(json.dumps(blob, ensure_ascii=False), encoding="utf-8")
    item.review_revision += 1
    db.flush()
    return ReviewPatchResult(review_revision=item.review_revision)


def _index_nodes(chapters: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}

    def walk(nodes: list[dict]) -> None:
        for n in nodes:
            out[n["id"]] = n
            walk(n.get("children", []))

    walk(chapters)
    return out
```

- [ ] **Step 5: 增端点**

在 `backend/app/routers/batch_imports.py` 增 import `ReviewPatchRequest, ReviewPatchResult`，加端点：

```python
@router.patch("/{job_id}/items/{item_id}/review", response_model=ReviewPatchResult)
def patch_review(
    job_id: str,
    item_id: str,
    payload: ReviewPatchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReviewPatchResult:
    result = batch_review_service.apply_review_ops(db, job_id, item_id, payload=payload)
    db.commit()
    return result
```

- [ ] **Step 6: 运行 + 门禁 + 提交**

Run: `cd backend && python -m pytest tests/unit/services/test_batch_review_service.py -v`
Expected: PASS（全部）

```bash
cd backend && ruff check app/schemas/batch.py app/services/batch_review_service.py app/routers/batch_imports.py tests/unit/services/test_batch_review_service.py && ruff format app/services/batch_review_service.py && mypy app/services/batch_review_service.py
git add app/schemas/batch.py app/services/batch_review_service.py app/routers/batch_imports.py tests/unit/services/test_batch_review_service.py
git commit -m "feat(batch): staged review re-judge with optimistic lock"
```

---

## Task 5: retry / skip / undo

**Files:**
- Modify: `backend/app/services/batch_review_service.py`
- Modify: `backend/app/routers/batch_imports.py`
- Test: `backend/tests/unit/services/test_batch_review_service.py`（追加）

- [ ] **Step 1: 写失败测试**

在 `backend/tests/unit/services/test_batch_review_service.py` 追加：

```python
from app.models.procedure import Procedure


def test_retry_failed_back_to_queued(db: Session) -> None:
    job = _job(db)
    item = _item(db, job, status="failed")
    item.error = "boom"
    db.commit()
    batch_review_service.retry_item(db, job.id, item.id)
    db.commit()
    fresh = db.get(BatchImportItem, item.id)
    assert fresh.status == "queued"
    assert fresh.error is None


def test_skip_marks_skipped(db: Session) -> None:
    job = _job(db)
    item = _item(db, job, status="review")
    db.commit()
    batch_review_service.skip_item(db, job.id, item.id)
    db.commit()
    assert db.get(BatchImportItem, item.id).status == "skipped"


def test_undo_soft_deletes_procedure_and_reverts(db: Session, factory) -> None:
    job = _job(db)
    proc = factory.procedure(folder_id="f1", code="QC-00001")
    item = _item(db, job, status="applied", procedure_id=proc.id)
    db.commit()
    batch_review_service.undo_item(db, job.id, item.id)
    db.commit()
    fresh = db.get(BatchImportItem, item.id)
    assert fresh.status == "review"
    assert fresh.created_procedure_id is None
    assert db.get(Procedure, proc.id).is_active is False
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/test_batch_review_service.py -k "retry or skip or undo" -v`
Expected: FAIL — `AttributeError: ... has no attribute 'retry_item'`

- [ ] **Step 3: 写 service**

在 `backend/app/services/batch_review_service.py` 追加（import 增 `from app.models.procedure import Procedure`、`from app.models.base import utcnow`、`from app.services import batch_parse_service`）:

```python
def retry_item(db: Session, job_id: str, item_id: str) -> None:
    """失败项重排队（重新被 parse worker 领取）。"""
    item = batch_import_service.get_item(db, job_id, item_id)
    if item.status != "failed":
        raise bad_request("BATCH_ITEM_NOT_FAILED", "仅失败条目可重试")
    item.status = "queued"
    item.error = None
    item.leased_until = None
    db.flush()


def skip_item(db: Session, job_id: str, item_id: str) -> None:
    """跳过该条目（不落库）。"""
    item = batch_import_service.get_item(db, job_id, item_id)
    if item.status not in ("review", "failed"):
        raise bad_request("BATCH_ITEM_NOT_SKIPPABLE", "仅待审阅/失败条目可跳过")
    item.status = "skipped"
    batch_parse_service._recompute_counts(db, item.job_id)
    db.flush()


def undo_item(db: Session, job_id: str, item_id: str) -> None:
    """撤销已落库（软删刚建程序，条目回 review）。

    MVP 直接软删 Procedure；接审计/版本流的完整废止留作演进。
    """
    item = batch_import_service.get_item(db, job_id, item_id)
    if item.status != "applied" or item.created_procedure_id is None:
        raise bad_request("BATCH_ITEM_NOT_APPLIED", "仅已应用条目可撤销")
    proc = db.get(Procedure, item.created_procedure_id)
    if proc is not None:
        proc.is_active = False
        proc.deleted_at = utcnow()
    item.created_procedure_id = None
    item.status = "review"
    batch_parse_service._recompute_counts(db, item.job_id)
    db.flush()
```

- [ ] **Step 4: 增端点**

在 `backend/app/routers/batch_imports.py` 追加三个端点：

```python
@router.post("/{job_id}/items/{item_id}/retry", status_code=204)
def retry_item(
    job_id: str, item_id: str,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> Response:
    batch_review_service.retry_item(db, job_id, item_id)
    db.commit()
    return Response(status_code=204)


@router.post("/{job_id}/items/{item_id}/skip", status_code=204)
def skip_item(
    job_id: str, item_id: str,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> Response:
    batch_review_service.skip_item(db, job_id, item_id)
    db.commit()
    return Response(status_code=204)


@router.post("/{job_id}/items/{item_id}/undo", status_code=204)
def undo_item(
    job_id: str, item_id: str,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> Response:
    batch_review_service.undo_item(db, job_id, item_id)
    db.commit()
    return Response(status_code=204)
```

- [ ] **Step 5: 运行 + 全量回归 + 门禁 + 提交**

```bash
cd backend && python -m pytest -q && ruff check app/services/batch_review_service.py app/routers/batch_imports.py tests/unit/services/test_batch_review_service.py && ruff format app/services/batch_review_service.py app/routers/batch_imports.py && mypy app/services/batch_review_service.py app/routers/batch_imports.py
git add app/services/batch_review_service.py app/routers/batch_imports.py tests/unit/services/test_batch_review_service.py
git commit -m "feat(batch): retry/skip/undo endpoints"
```

---

## 集成验证清单（需真实 MySQL）

- [ ] **apply 不双取 / 不重复落库**：两 worker 并发 `run_apply_once`，同一 `applying` 项只落一次（`SKIP LOCKED` + `created_procedure_id` 幂等）。
- [ ] **图片提升**：含图 docx 批量解析→apply 后，程序 body 的图 URL 指向 `/procedures/{pid}/assets/{aid}`，`ProcedureAsset` 与 `ProcedureAssetReference` 正确建立。
- [ ] **租户隔离**：A 租户 `apply` B 租户的 job 返回 404；apply worker per-item 切上下文后取号/建程序落到正确租户。
- [ ] **undo 时序**：apply 完成后 undo，程序软删、条目回 review，可再次 apply（取新号）。

---

## Self-Review（计划作者已核对）

- **Spec 覆盖**：覆盖 spec §5.4（apply worker）、§6.3（节点级 diff 改判→`PATCH review`）、§6.4（dry-run→`apply-preview`）、§6.5（软撤销→`undo`）、§7（apply/apply-preview/review/retry/skip/undo 端点）、§8.1（落库取号幂等、改判 409、内容重复跳过）、§8.2 不变量 1/2/3/4。
- **占位扫描**：无 TBD/TODO。两处对 spec 的主动偏离（`level_of_use` 固定 reference、取消"编号冲突"分支）已在"关键约定"显式声明理由，非占位。
- **类型一致性**：`apply_item` / `claim_applying` / `run_apply_once` / `enqueue_apply` / `preview_apply` / `apply_review_ops` / `retry_item` / `skip_item` / `undo_item` 跨 Task 签名一致；复用 Plan 1 的 `batch_parse_service._recompute_counts` / `mark_failed`；blob 形态仍是 `ParseResponse` JSON；状态机字符串与 Plan 1 一致（`review`→`applying`→`applied`，`failed`→`queued`，`review`→`skipped`）。
- **依赖前提**：Plan 1 的模型/暂存/计数函数、phase-0 的 `create_procedure`/`RequestMeta`/租户 API 均已具备。
