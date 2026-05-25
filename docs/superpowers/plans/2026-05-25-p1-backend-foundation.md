# P1 · 后端基座 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 导入时永久存原始 `.docx`、按程序可取回（长期追溯）；并允许手动删除"从未发布过的纯草稿"。

**Architecture:** 新增 `tb_procedure_source_docx`（按 procedure_group 一份）+ `source_docx_service`（存/取/删，与图片中心的 `asset_service` 平行解耦）；`ImportRequest` 增 `upload_token`，导入时把临时区 docx 落库；新增取回端点 `GET /procedures/{id}/source-docx`；放宽 `delete_procedure` 让 v1 DRAFT 可删并连带清 docx。前端导入调用透传 `upload_token`。

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + pytest（后端）；Vue 3 + TS + Vitest（前端小尾巴）。

**上位文档：** `docs/superpowers/specs/2026-05-25-p1-backend-foundation-design.md`

---

## 关键事实（实现者必读）

- **测试建表走 `Base.metadata.create_all`（不是 Alembic）**：新模型**必须**在 `backend/app/models/__init__.py` 导入并登记，否则测试里没这张表。Alembic 迁移是给生产用的，pytest 不跑它。
- **ORM 基类**在 `app/models/base.py`：`UUIDMixin`（`id` String(36) PK）、`TimestampMixin`（`created_at` 带 index + `updated_at`）、可移植类型 `DATETIME6`。
- **临时上传**纯文件系统：`{storage}/tmp/uploads/{token}/source.docx` + `meta.json`（含 `filename`/`expires_at`）。`upload_service` 已有 `read_docx`/`upload_filename`/私有 `_is_safe_token`/`_is_expired`。
- **存储根** `app/storage.py` 由 `settings.storage_dir` 派生；测试 `storage_tmp` fixture 会 monkeypatch 它。
- **程序服务** `procedure_service`：`create_procedure` 设 `procedure_group_id=new_uuid()`、`status="DRAFT"`、`version=1`、`is_current=True`；`delete_procedure` 当前对 `is_current` 一律拒（v>1 DRAFT 走 `_discard_draft`）。`get_or_404`、`to_meta` 可复用。
- **删除入参** `ProcedureDeleteIn.reason` 必填（min_length=1）。DELETE 带 JSON body。
- **错误助手** `app/errors.py`：`not_found(code,msg)` / `bad_request(...)` 返回并 `raise` 的 `HTTPException`。
- **pytest fixtures**：`db`(Session)、`client`(TestClient)、`storage_tmp`(Path)、`engine`。docx 测试字节用 `from tests.unit.parser._docx_builder import styled_sop, empty_sop`。
- **后端 Gate**（cwd=`backend/`）：`ruff check app tests && mypy app && pytest -q`。
- **避免循环导入**：`source_docx_service` **不要**在模块顶层 import `procedure_service`（直接查 `Procedure`）；`procedure_service.delete_procedure` 里用**函数内局部 import** 引 `source_docx_service`。
- **提交结尾必带**（harness 规定的合法署名，勿当伪造）：`Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`

---

## File Structure

- 新建 `backend/app/models/source_docx.py` — `ProcedureSourceDocx`。
- 改 `backend/app/models/__init__.py` — 登记新模型。
- 改 `backend/app/storage.py` — `source_docx_root` / `source_docx_path`。
- 新建 `backend/alembic/versions/20260525_0001_add_source_docx.py` — 建表迁移（生产）。
- 改 `backend/app/services/upload_service.py` — `try_read_source`（非抛读取）。
- 新建 `backend/app/services/source_docx_service.py` — 存/取/删。
- 改 `backend/app/schemas/parse.py` — `ImportRequest` +`upload_token`。
- 改 `backend/app/services/import_service.py` — 接收 token、调存。
- 改 `backend/app/routers/procedures.py` — import 透传 token + 新增 `GET /{id}/source-docx`。
- 改 `backend/app/services/procedure_service.py` — `delete_procedure` 放宽 v1 DRAFT + 连带清 docx。
- 改前端 `frontend/src/types/parse.ts` + `frontend/src/components/import-v2/ImportDialog.vue` — 透传 `upload_token`。
- 测试：`backend/tests/unit/test_source_docx_service.py`、扩展 `backend/tests/integration/test_word_import.py`。

---

## Task 1: 存储路径 + `ProcedureSourceDocx` 模型 + 登记 + 迁移

**Files:**
- Create: `backend/app/models/source_docx.py`
- Modify: `backend/app/models/__init__.py`, `backend/app/storage.py`
- Create: `backend/alembic/versions/20260525_0001_add_source_docx.py`
- Test: `backend/tests/unit/test_source_docx_service.py`（本任务先放路径+登记两条）

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/unit/test_source_docx_service.py`：

```python
"""P1 源 docx：存储路径 + 模型登记 + 服务存取删。"""

from __future__ import annotations

from pathlib import Path

from app import storage
from app.models import Base


def test_source_docx_path_under_group(storage_tmp: Path) -> None:
    p = storage.source_docx_path("grp-1")
    assert p == storage_tmp / "source_docx" / "grp-1" / "source.docx"


def test_model_registered_in_metadata() -> None:
    assert "tb_procedure_source_docx" in Base.metadata.tables
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `cd backend && pytest tests/unit/test_source_docx_service.py -q`
Expected: FAIL —— `storage.source_docx_path` 不存在 / 表未登记。

- [ ] **Step 3: 实现存储路径**

在 `backend/app/storage.py` 末尾追加：

```python
def source_docx_root() -> Path:
    return storage_root() / "source_docx"


def source_docx_path(procedure_group_id: str) -> Path:
    """原始源 docx 物理路径：按 procedure_group 一份。"""
    return source_docx_root() / procedure_group_id / "source.docx"
```

- [ ] **Step 4: 实现模型**

新建 `backend/app/models/source_docx.py`：

```python
"""原始 Word 源文件模型（P1：导入可追溯）。

一个 procedure_group 至多存一份原始 .docx（导入时落库），供编辑器预览栏渲染、
正式后长期追溯。不去重、不软删（随版本组删除即物理清理）。
"""

from __future__ import annotations

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class ProcedureSourceDocx(Base, UUIDMixin, TimestampMixin):
    """导入程序的原始 .docx（按 procedure_group 归属，唯一）。"""

    __tablename__ = "tb_procedure_source_docx"

    procedure_group_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
```

在 `backend/app/models/__init__.py` 登记（import + `__all__`）：

```python
from app.models.source_docx import ProcedureSourceDocx
```
并把 `"ProcedureSourceDocx"` 加入 `__all__`（按字母序放在 `"ProcedureSettings"` 之后、`"ProcedureStep"` 之前）。

- [ ] **Step 5: 写生产迁移**

新建 `backend/alembic/versions/20260525_0001_add_source_docx.py`：

```python
"""add tb_procedure_source_docx

Revision ID: add_source_docx
Revises: drop_alert_fields
Create Date: 2026-05-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = 'add_source_docx'
down_revision: str | None = 'drop_alert_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tb_procedure_source_docx',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('procedure_group_id', sa.String(length=64), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('storage_path', sa.String(length=500), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), 'mysql'), nullable=False),
        sa.Column('updated_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), 'mysql'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_tb_procedure_source_docx')),
    )
    op.create_index(op.f('ix_tb_procedure_source_docx_created_at'), 'tb_procedure_source_docx', ['created_at'], unique=False)
    op.create_index('uq_tb_procedure_source_docx_procedure_group_id', 'tb_procedure_source_docx', ['procedure_group_id'], unique=True)


def downgrade() -> None:
    op.drop_index('uq_tb_procedure_source_docx_procedure_group_id', table_name='tb_procedure_source_docx')
    op.drop_index(op.f('ix_tb_procedure_source_docx_created_at'), table_name='tb_procedure_source_docx')
    op.drop_table('tb_procedure_source_docx')
```

注：`down_revision='drop_alert_fields'` 是当前 head（`alembic heads` 确认）。若 head 已变，改成实际 head。

- [ ] **Step 6: 跑测试 + lint/类型**

Run: `cd backend && pytest tests/unit/test_source_docx_service.py -q && ruff check app tests && mypy app`
Expected: 2 测试 PASS；ruff/mypy clean。

- [ ] **Step 7: 提交**

```bash
git add backend/app/models/source_docx.py backend/app/models/__init__.py backend/app/storage.py backend/alembic/versions/20260525_0001_add_source_docx.py backend/tests/unit/test_source_docx_service.py
git commit -m "$(cat <<'EOF'
feat(p1): tb_procedure_source_docx model + storage paths + migration

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `upload_service.try_read_source` + `source_docx_service`（存/删）

**Files:**
- Modify: `backend/app/services/upload_service.py`
- Create: `backend/app/services/source_docx_service.py`
- Test: `backend/tests/unit/test_source_docx_service.py`（追加）

- [ ] **Step 1: 写失败测试（追加到同文件）**

在 `backend/tests/unit/test_source_docx_service.py` 顶部 import 区追加：

```python
from app.services import source_docx_service, upload_service
from sqlalchemy.orm import Session
from tests.unit.parser._docx_builder import styled_sop
```

并追加测试：

```python
def test_store_from_token_writes_row_and_file(db: Session, storage_tmp: Path) -> None:
    up = upload_service.save_upload(styled_sop(), "原文.docx")
    row = source_docx_service.store_from_token(db, procedure_group_id="grp-1", upload_token=up.upload_token)
    assert row is not None
    assert row.filename == "原文.docx"
    assert row.size_bytes > 0 and len(row.sha256) == 64
    assert storage.source_docx_path("grp-1").exists()


def test_store_from_token_degrades_without_token(db: Session, storage_tmp: Path) -> None:
    assert source_docx_service.store_from_token(db, procedure_group_id="g", upload_token=None) is None
    assert source_docx_service.store_from_token(db, procedure_group_id="g", upload_token="ghost") is None


def test_delete_for_group_removes_row_and_file(db: Session, storage_tmp: Path) -> None:
    up = upload_service.save_upload(styled_sop(), "a.docx")
    source_docx_service.store_from_token(db, procedure_group_id="grp-9", upload_token=up.upload_token)
    assert storage.source_docx_path("grp-9").exists()
    source_docx_service.delete_for_group(db, "grp-9")
    assert not storage.source_docx_path("grp-9").exists()
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `cd backend && pytest tests/unit/test_source_docx_service.py -q`
Expected: FAIL —— `try_read_source` / `source_docx_service` 不存在。

- [ ] **Step 3: 实现 `upload_service.try_read_source`**

在 `backend/app/services/upload_service.py` 的 `upload_filename` 之后追加：

```python
def try_read_source(token: str) -> tuple[bytes, str] | None:
    """读取临时 docx + 原始文件名；不存在/过期/非法 token → None（不抛，供导入降级）。"""
    if not _is_safe_token(token):
        return None
    src = storage.token_dir(token) / _SOURCE
    if not src.exists() or _is_expired(token, utcnow()):
        return None
    return src.read_bytes(), upload_filename(token) or _SOURCE
```

- [ ] **Step 4: 实现 `source_docx_service`**

新建 `backend/app/services/source_docx_service.py`：

```python
"""原始 Word 源文件存取（P1：导入可追溯）。

导入时把临时区 source.docx 永久落库（按 procedure_group 一份）；编辑器预览栏按
procedure_id 取回渲染；删除纯草稿时连带清理。与图片中心的 asset_service 平行、解耦。
不在顶层 import procedure_service（避免循环）：直接查 Procedure。
"""

from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import storage
from app.errors import not_found
from app.models.procedure import Procedure
from app.models.source_docx import ProcedureSourceDocx
from app.services import upload_service

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def store_from_token(
    db: Session, *, procedure_group_id: str, upload_token: str | None
) -> ProcedureSourceDocx | None:
    """把临时 docx 永久落库；token 缺失/过期/丢失 → None（降级，不阻断导入）。"""
    if not upload_token:
        return None
    read = upload_service.try_read_source(upload_token)
    if read is None:
        return None
    data, filename = read
    path = storage.source_docx_path(procedure_group_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    row = ProcedureSourceDocx(
        procedure_group_id=procedure_group_id,
        filename=filename,
        storage_path=str(path.relative_to(storage.storage_root())),
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
    )
    db.add(row)
    db.flush()
    return row


def get_for_procedure(db: Session, procedure_id: str) -> tuple[bytes, str, str]:
    """按 procedure_id → group → 返回 (字节, mime, 原始文件名)。无 → 404。"""
    proc = db.execute(
        select(Procedure).where(Procedure.id == procedure_id, Procedure.is_active.is_(True))
    ).scalar_one_or_none()
    if proc is None:
        raise not_found("NOT_FOUND", "程序不存在")
    row = db.execute(
        select(ProcedureSourceDocx).where(
            ProcedureSourceDocx.procedure_group_id == proc.procedure_group_id
        )
    ).scalar_one_or_none()
    if row is None:
        raise not_found("SOURCE_DOCX_NOT_FOUND", "该程序无原始 Word 源文件")
    path = storage.storage_root() / row.storage_path
    if not path.exists():
        raise not_found("SOURCE_DOCX_NOT_FOUND", "原始 Word 源文件已丢失")
    return path.read_bytes(), _DOCX_MIME, row.filename


def delete_for_group(db: Session, procedure_group_id: str) -> None:
    """删除某 group 的源 docx（行 + 落盘文件）。无则静默。"""
    row = db.execute(
        select(ProcedureSourceDocx).where(
            ProcedureSourceDocx.procedure_group_id == procedure_group_id
        )
    ).scalar_one_or_none()
    if row is None:
        return
    (storage.storage_root() / row.storage_path).unlink(missing_ok=True)
    db.delete(row)
    db.flush()
```

- [ ] **Step 5: 跑测试，确认通过**

Run: `cd backend && pytest tests/unit/test_source_docx_service.py -q && ruff check app tests && mypy app`
Expected: 5 测试 PASS；ruff/mypy clean。

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/upload_service.py backend/app/services/source_docx_service.py backend/tests/unit/test_source_docx_service.py
git commit -m "$(cat <<'EOF'
feat(p1): source_docx_service store/get/delete + upload try_read_source

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: 接线导入存 docx + 取回端点

**Files:**
- Modify: `backend/app/schemas/parse.py`, `backend/app/services/import_service.py`, `backend/app/routers/procedures.py`
- Test: `backend/tests/integration/test_word_import.py`（追加）

- [ ] **Step 1: 写失败测试（追加到 test_word_import.py 末尾，`_flatten` 之前）**

```python
def test_import_stores_and_serves_source_docx(client: TestClient, storage_tmp: Path) -> None:
    leaf = _leaf(client)
    token = _upload(client, styled_sop(), name="源文件.docx")
    body = client.post(PARSE, json={"upload_token": token, "parse_mode": "standard"}).json()
    imported = client.post(
        IMPORT,
        json={"name": "带源文件", "folder_id": leaf, "upload_token": token, "chapters": body["chapters"]},
    )
    assert imported.status_code == 201, imported.text
    pid = imported.json()["id"]

    served = client.get(f"/api/v1/procedures/{pid}/source-docx")
    assert served.status_code == 200
    assert served.headers["content-type"] == DOCX_MIME
    assert served.content  # 原始 docx 字节


def test_import_without_token_has_no_source_docx(client: TestClient, storage_tmp: Path) -> None:
    leaf = _leaf(client)
    token = _upload(client, styled_sop())
    body = client.post(PARSE, json={"upload_token": token, "parse_mode": "standard"}).json()
    imported = client.post(
        IMPORT, json={"name": "无源文件", "folder_id": leaf, "chapters": body["chapters"]}
    )
    pid = imported.json()["id"]
    assert client.get(f"/api/v1/procedures/{pid}/source-docx").status_code == 404
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `cd backend && pytest tests/integration/test_word_import.py -q -k source_docx`
Expected: FAIL —— `upload_token` 字段未知 / 端点 404 always。

- [ ] **Step 3: schema 加 `upload_token`**

`backend/app/schemas/parse.py` 的 `ImportRequest` 增加字段：

```python
class ImportRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    folder_id: str
    description: str = Field(default="", max_length=10000)
    upload_token: str | None = None
    chapters: list[ImportNodeIn] = Field(default_factory=list)
```

- [ ] **Step 4: import_service 接收并存 docx**

`backend/app/services/import_service.py`：
1. 顶部服务 import 增加 `source_docx_service`：
   ```python
   from app.services import asset_service, editor_service, numbering_service, procedure_service, source_docx_service
   ```
2. `import_procedure` 签名加参数 `upload_token: str | None = None`（放在 `chapters` 之后、`meta` 之前）。
3. 在 `asset_service.rebuild_references(db, proc.id)` 之后、`db.flush()` 之前插入：
   ```python
   source_docx_service.store_from_token(db, procedure_group_id=proc.procedure_group_id, upload_token=upload_token)
   ```

- [ ] **Step 5: router 透传 token + 取回端点**

`backend/app/routers/procedures.py`：
1. `from app.services import (...)` 元组里加入 `source_docx_service`。
2. `import_procedure` handler 调用增加 `upload_token=payload.upload_token`：
   ```python
   proc = import_service.import_procedure(
       db,
       name=payload.name,
       folder_id=payload.folder_id,
       description=payload.description,
       upload_token=payload.upload_token,
       chapters=payload.chapters,
       meta=meta,
   )
   ```
3. 顶部加 `from urllib.parse import quote`。
4. 在 `serve_asset` 之后新增端点：
   ```python
   @router.get("/{procedure_id}/source-docx")
   def serve_source_docx(procedure_id: str, db: Session = Depends(get_db)) -> Response:
       """返回导入程序的原始 .docx 字节（预览栏渲染 / 追溯）。无 → 404。"""
       data, mime, filename = source_docx_service.get_for_procedure(db, procedure_id)
       return Response(
           content=data,
           media_type=mime,
           headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(filename)}"},
       )
   ```

- [ ] **Step 6: 跑测试 + 全量后端 Gate**

Run: `cd backend && pytest -q && ruff check app tests && mypy app`
Expected: 新 2 测试 + 既有全绿；ruff/mypy clean。

- [ ] **Step 7: 提交**

```bash
git add backend/app/schemas/parse.py backend/app/services/import_service.py backend/app/routers/procedures.py backend/tests/integration/test_word_import.py
git commit -m "$(cat <<'EOF'
feat(p1): store source docx on import + GET /procedures/{id}/source-docx

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: 放宽删除"纯草稿"+ 连带清 docx

**Files:**
- Modify: `backend/app/services/procedure_service.py`
- Test: `backend/tests/integration/test_word_import.py`（追加）

- [ ] **Step 1: 写失败测试（追加）**

```python
def test_delete_pure_draft_removes_source_docx(client: TestClient, storage_tmp: Path) -> None:
    leaf = _leaf(client)
    token = _upload(client, styled_sop())
    body = client.post(PARSE, json={"upload_token": token, "parse_mode": "standard"}).json()
    pid = client.post(
        IMPORT, json={"name": "可删草稿", "folder_id": leaf, "upload_token": token, "chapters": body["chapters"]}
    ).json()["id"]
    assert client.get(f"/api/v1/procedures/{pid}/source-docx").status_code == 200

    # v1 DRAFT（当前、从未发布）→ 允许删除（204）
    deleted = client.request("DELETE", f"/api/v1/procedures/{pid}", json={"reason": "弃用草稿"})
    assert deleted.status_code == 204, deleted.text
    # 源 docx 连带清掉
    assert client.get(f"/api/v1/procedures/{pid}/source-docx").status_code == 404


def test_delete_published_current_still_rejected(client: TestClient, storage_tmp: Path) -> None:
    leaf = _leaf(client)
    pid = client.post(
        "/api/v1/procedures", json={"folder_id": leaf, "name": "已发布", "level_of_use": "continuous"}
    ).json()["id"]
    rev = client.get(f"/api/v1/procedures/{pid}").json()["revision"]
    pub = client.post(
        f"/api/v1/procedures/{pid}/transition",
        json={"status": "PUBLISHED"},
        headers={"If-Match": str(rev)},
    )
    assert pub.status_code == 200, pub.text
    blocked = client.request("DELETE", f"/api/v1/procedures/{pid}", json={"reason": "x"})
    assert blocked.status_code == 400
    assert blocked.json()["detail"]["code"] == "PROCEDURE_IS_CURRENT"
```

注：若 `ProcedureDetail`/`ProcedureMeta` 字段名与 `revision` 不一致，按实际响应字段取乐观锁值。

- [ ] **Step 2: 跑测试，确认失败**

Run: `cd backend && pytest tests/integration/test_word_import.py -q -k delete`
Expected: `test_delete_pure_draft...` FAIL（当前 v1 当前版本删除被拒）。

- [ ] **Step 3: 放宽 `delete_procedure`**

`backend/app/services/procedure_service.py` 的 `delete_procedure`，把 `if proc.is_current:` 分支改为（在原 `raise` 之前插入 v1 DRAFT 分支）：

```python
    proc = _get(db, proc_id)
    if proc.is_current:
        if proc.status == "DRAFT" and proc.version > 1:
            return _discard_draft(db, proc, reason, meta)
        if proc.status == "DRAFT" and proc.version == 1:
            # 纯草稿（唯一版本、从未发布）：整组丢弃，连带清源 docx（P1 / cleanup=C 手动删）
            from app.services import source_docx_service  # 局部导入避免循环

            source_docx_service.delete_for_group(db, proc.procedure_group_id)
            proc.is_current = False
            _soft_delete(db, proc)
            audit_service.log_procedure_action(
                db,
                target_id=proc.id,
                procedure_group_id=proc.procedure_group_id,
                action="delete",
                meta=meta,
                old_value={"code": proc.code, "name": proc.name},
                reason=reason,
            )
            return None
        raise bad_request("PROCEDURE_IS_CURRENT", "当前版本不可直接删除")
    _soft_delete(db, proc)
```
（其余原样不动。）

- [ ] **Step 4: 跑测试 + 全量后端 Gate**

Run: `cd backend && pytest -q && ruff check app tests && mypy app`
Expected: 全绿；ruff/mypy clean。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/procedure_service.py backend/tests/integration/test_word_import.py
git commit -m "$(cat <<'EOF'
feat(p1): allow deleting a never-published v1 DRAFT + cascade source docx

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: 前端透传 `upload_token`（小尾巴）

让当前 beta2 导入也立刻产生可追溯 docx。

**Files:**
- Modify: `frontend/src/types/parse.ts`, `frontend/src/components/import-v2/ImportDialog.vue`

- [ ] **Step 1: 类型加字段**

`frontend/src/types/parse.ts` 的 `ImportRequest` 增加可选字段：

```ts
export interface ImportRequest {
  name: string
  folder_id: string
  description?: string
  upload_token?: string
  chapters: ImportNode[]
}
```

- [ ] **Step 2: 调用处透传**

`frontend/src/components/import-v2/ImportDialog.vue` 的 `onSubmit` 里 `importProcedure({...})` 调用，加入 `upload_token`：

```ts
    const proc = await importProcedure({
      name: ctx.form.name.trim(),
      folder_id: ctx.form.folder_id,
      description: '',
      upload_token: ctx.uploadToken.value,
      chapters: toImportNodes(ctx.tree.value),
    })
```
（`ctx.uploadToken` 在 `onPickFile` 上传时已赋值。`api/parse.ts` 的 `importProcedure` 直接 POST 整个 payload，无需改动。）

- [ ] **Step 3: 前端 Gate**

Run: `cd frontend && npm run lint && npm run typecheck && npm run test && npm run build`
Expected: 全绿（透传字段不影响既有测试）。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/types/parse.ts frontend/src/components/import-v2/ImportDialog.vue
git commit -m "$(cat <<'EOF'
feat(p1): forward upload_token from import dialog for source-docx storage

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## 收尾

- 全部任务后跑最终 Gate：`cd backend && ruff check app tests && mypy app && pytest -q` 和 `cd frontend && npm run lint && npm run typecheck && npm run test && npm run build`。
- 生产迁移本地手验（可选，需 dev DB）：`cd backend && alembic upgrade head`，再 `alembic downgrade -1` 验回滚；确认 `alembic heads` 链路正确。
- 用 superpowers:finishing-a-development-branch 收束（合并 / PR / 保留 / 丢弃，由用户选）。

## Self-Review 记录

- **Spec 覆盖**：D2 docx 永久存储（T1 模型/路径/迁移、T2 服务、T3 接线+取回）；D3 删除纯草稿（T4）；upload_token 透传（T3 schema + T5 前端）。「完成」=PUBLISHED 复用现状，P1 无改（符合 spec）。置信度/降型藏存按 spec 挪到 P2，未列入。
- **占位符**：无 TBD；每步含完整代码与确切命令。
- **类型一致**：`store_from_token` / `get_for_procedure` / `delete_for_group` 跨 T2/T3/T4 同名使用；`source_docx_path` T1 定义、T2 用；`ImportRequest.upload_token` 前后端同名。
- **循环导入**：`source_docx_service` 不顶层引 `procedure_service`（直接查 `Procedure`）；`procedure_service.delete` 用函数内局部 import 引 `source_docx_service`——已在代码中体现。
- **测试建表**：新模型在 `models/__init__.py` 登记（T1 Step4），保证 `create_all` 测试可见；迁移仅生产。
