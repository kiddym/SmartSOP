# C001/C002/C003 强确认 + 解析提示可见化 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **⚠️ 用户指令 #5：不做任何 git 提交。** 本计划所有「提交」步骤一律替换为「运行测试确认通过、改动留工作区」，由用户决定后续提交。每个 Task 末尾不 commit。

**Goal:** 把 C001/C002/C003 完整性失败从静默 warning 升级为 import 前的「阻断式强确认」，并把所有解析提示（含有意裁剪）持久化、在编辑器常驻提示区可见。

**Architecture:** 后端给 `ParseWarning` 加 `severity`（blocking/info，默认 info）作为 A/B/C 共用正交轴；C001/C002/C003 标 blocking，页眉页脚/首标题前丢弃靠默认 info。完整 warnings 快照随 import 落到新增的 `Procedure.import_notes` JSON 列。前端拆「直通」流为 `uploadAndParse` + `importParsed`，blocking warning 触发 `ParseConfirmDialog`，编辑器用 `ParseNoticeBar` 渲染 `import_notes`。

**Tech Stack:** 后端 FastAPI + SQLAlchemy + Pydantic + alembic，pytest；前端 Vue 3 + Pinia + Element Plus，vitest。

---

## 文件结构（创建 / 修改 + 职责）

**后端**
- 修改 `app/parser/validators/completeness.py` —— C003 阈值 95% → 100%。
- 修改 `app/parser/result.py` —— `ParseWarning` 加 `severity: str = "info"`。
- 修改 `app/parser/structurer.py` —— `_append_completeness_warnings` 三条 warning 传 `severity="blocking"`。
- 修改 `app/schemas/parse.py` —— `ParseWarningOut.severity`；`build_parse_response` 透传；`ImportRequest.import_notes`。
- 修改 `app/models/procedure.py` —— 新增 `import_notes` JSON 列。
- 创建 `alembic/versions/20260531_0016_procedure_import_notes.py` —— 加列迁移。
- 修改 `app/services/import_service.py` —— `import_procedure` 收 `import_notes` 并落库。
- 修改 `app/routers/procedures.py` —— import 端点传 `import_notes`。
- 修改 `app/schemas/procedure.py` —— `ProcedureMeta.import_notes`。
- 修改 `app/services/procedure_service.py` —— `_META_FIELDS` 加 `import_notes`。

**前端**
- 修改 `src/types/parse.ts` —— `ParseWarning.severity`、`ImportRequest.import_notes`。
- 修改 `src/types/procedure.ts` —— `ProcedureMeta.import_notes`。
- 修改 `src/api/parse.ts` —— 拆出 `uploadAndParse` / `importParsed`，删 `importFromWord`。
- 创建 `src/components/ParseConfirmDialog.vue` —— 阻断式强确认弹窗（纯展示 + confirm/cancel）。
- 修改 `src/components/CreateFromWordDialog.vue` —— 编排 parse→（blocking?）→确认→import。
- 创建 `src/components/editor/ParseNoticeBar.vue` —— 编辑器常驻解析提示区。
- 修改 `src/views/procedures/ProcedureEditorView.vue` —— 左栏挂 `ParseNoticeBar`。

**测试**
- `backend/tests/unit/parser/test_completeness.py`（改）
- `backend/tests/unit/parser/test_warning_severity.py`（建）
- `backend/tests/unit/services/test_import_service.py`（改）
- `backend/tests/integration/test_word_import.py`（改，补一条 detail 返回断言）
- `frontend/tests/unit/wordImport.spec.ts`（改：测 uploadAndParse + importParsed）
- `frontend/tests/unit/CreateFromWordDialog.spec.ts`（改：测 blocking 流）
- `frontend/tests/unit/ParseConfirmDialog.spec.ts`（建）
- `frontend/tests/unit/ParseNoticeBar.spec.ts`（建）

---

## Task 1: C003 阈值 95% → 100%

**Files:**
- Modify: `backend/app/parser/validators/completeness.py:29-43`
- Test: `backend/tests/unit/parser/test_completeness.py:65-92`

- [ ] **Step 1: 改失败测试（把 95% 边界测试改成 100% 语义）**

把 `test_completeness.py` 中 `test_c003_passes_at_exactly_95_percent` 与 `test_c003_fails_when_kept_below_95_percent` 两个函数整体替换为下面三个：

```python
def test_c003_passes_only_when_kept_equals_raw() -> None:
    """C003：100% 保留（kept == raw）→ pass。"""
    from app.parser.ir import NormalizedDoc
    blocks = [Block(kind="paragraph", source_index=i) for i in range(20)]
    nd = NormalizedDoc(blocks=blocks, raw_paragraph_count=20)
    ok, raw, kept = completeness.paragraph_count_match(nd)
    assert ok is True
    assert raw == 20 and kept == 20


def test_c003_fails_at_95_percent() -> None:
    """C003：19/20 = 95% 现在应当 fail（阈值已提至 100%）。"""
    from app.parser.ir import NormalizedDoc
    blocks = [Block(kind="paragraph", source_index=i) for i in range(19)]
    nd = NormalizedDoc(blocks=blocks, raw_paragraph_count=20)
    ok, raw, kept = completeness.paragraph_count_match(nd)
    assert ok is False  # 19/20 < 100%
    assert raw == 20 and kept == 19


def test_c003_fails_when_one_paragraph_dropped() -> None:
    """C003：丢 1 段（模拟 normalize 漏抽）→ fail。"""
    from app.parser.ir import NormalizedDoc
    blocks = [Block(kind="paragraph", source_index=i) for i in range(18)]
    nd = NormalizedDoc(blocks=blocks, raw_paragraph_count=20)
    ok, raw, kept = completeness.paragraph_count_match(nd)
    assert ok is False
    assert raw == 20 and kept == 18
```

把 `test_c003_passes_when_kept_above_95_percent` 函数的 docstring 改为 `"""C003：100% 保留 → pass。"""`（其余 20/20 断言不变，仍正确）。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/parser/test_completeness.py -q`
Expected: `test_c003_fails_at_95_percent` FAIL（当前实现 19/20 仍 pass），其余通过。

- [ ] **Step 3: 最小实现——阈值改 100%**

`completeness.py` 第 40-43 行：

```python
    if raw == 0:
        return True, 0, kept
    ok = kept == raw
    return ok, raw, kept
```

并把该函数 docstring 第一行 `... 保留率 ≥ 95% pass。` 改为 `... 100% 保留（kept == raw）才 pass。`，去掉文中「≥ 95%」表述。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/unit/parser/test_completeness.py -q`
Expected: PASS（全绿）。

- [ ] **Step 5: 改动留工作区，不提交（用户指令 #5）**

---

## Task 2: ParseWarning.severity（A/B/C 共用地基）

**Files:**
- Modify: `backend/app/parser/result.py:61-64`
- Modify: `backend/app/parser/structurer.py:371-393`
- Modify: `backend/app/schemas/parse.py:89-92`（`ParseWarningOut`）、`:212`（`build_parse_response`）
- Test: `backend/tests/unit/parser/test_warning_severity.py`（新建）

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/unit/parser/test_warning_severity.py`：

```python
"""ParseWarning.severity：blocking/info 正交轴（A 项强确认地基）。"""

from __future__ import annotations

from app.parser.ir import Block, ImageRef, NormalizedDoc
from app.parser.result import ParseResult, ParseMetadata, ParseWarning
from app.parser.structurer import _append_completeness_warnings
from app.schemas.parse import build_parse_response


def test_parsewarning_defaults_to_info() -> None:
    """页眉页脚 / 首标题前丢弃等不传 severity 的 warning 默认 info。"""
    assert ParseWarning(stage="discarded_by_design", message="x").severity == "info"
    assert ParseWarning(stage="boundary", message="x").severity == "info"


def test_completeness_warnings_are_blocking() -> None:
    """C001 图片不匹配 → 追加的 warning severity == blocking。"""
    body_blocks = [
        Block(
            kind="paragraph",
            source_index=0,
            raw_image_count=2,
            images=[ImageRef(rid="a", part_name="word/media/x.png", data=b"x", ext=".png")],
        )
    ]
    nd = NormalizedDoc(blocks=body_blocks, raw_paragraph_count=1)
    warnings: list[ParseWarning] = []
    _append_completeness_warnings(body_blocks, nd, warnings)
    assert warnings, "图片不匹配应至少产出一条 warning"
    assert all(w.severity == "blocking" for w in warnings)


def test_build_parse_response_transports_severity() -> None:
    """build_parse_response 把 severity 透传到 ParseWarningOut。"""
    result = ParseResult(
        metadata=ParseMetadata(
            total_chapters=1, image_count=0, table_count=0,
            body_start_index=0, body_start_detected_by="x",
        ),
        chapters=[],
        parse_method="smart",
        warnings=[
            ParseWarning(stage="completeness", message="缺图", severity="blocking"),
            ParseWarning(stage="discarded_by_design", message="忽略页眉"),
        ],
    )
    resp = build_parse_response(result, assets=[], parse_time_ms=1)
    assert [w.severity for w in resp.warnings] == ["blocking", "info"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/parser/test_warning_severity.py -q`
Expected: FAIL（`ParseWarning` 无 `severity` 字段 → TypeError / AttributeError）。

- [ ] **Step 3: 加 severity 字段**

`result.py` 把 `ParseWarning` 改为：

```python
@dataclass
class ParseWarning:
    stage: str  # boundary | completeness | image | structure | discarded_by_design
    message: str
    severity: str = "info"  # "blocking"（内容可能静默丢失，需强确认）| "info"（有意裁剪/已知丢弃）
```

- [ ] **Step 4: structurer 给 C001/C002/C003 标 blocking**

`structurer.py` 的 `_append_completeness_warnings` 内三条 `ParseWarning(...)` 各加 `severity="blocking"`。改后：

```python
    img_ok, raw, ext = completeness.image_count_match(body_blocks)
    if not img_ok:
        warnings.append(
            ParseWarning(
                stage="completeness", message=f"图片可能遗漏：原始 {raw} / 解析 {ext}",
                severity="blocking",
            )
        )
    tbl_ok, traw, tser = completeness.table_count_match(body_blocks)
    if not tbl_ok:
        warnings.append(
            ParseWarning(
                stage="completeness", message=f"表格可能遗漏：原始 {traw} / 解析 {tser}",
                severity="blocking",
            )
        )
    p_ok, p_raw, p_kept = completeness.paragraph_count_match(nd)
    if not p_ok:
        warnings.append(
            ParseWarning(
                stage="completeness",
                message=f"段落可能遗漏：原始 {p_raw} / 解析 {p_kept}（保留 {p_kept/p_raw:.1%}）",
                severity="blocking",
            )
        )
```

> 注：`_append_discarded_warning`（页眉页脚）与首标题前丢弃 warning（`structurer.py:157-164`）不改——靠 `ParseWarning` 默认 `severity="info"` 即为软提示。

- [ ] **Step 5: schema 加 severity 并透传**

`schemas/parse.py` 的 `ParseWarningOut`：

```python
class ParseWarningOut(BaseModel):
    stage: str
    message: str
    severity: str = "info"
```

`build_parse_response` 末尾 warnings 行改为：

```python
        warnings=[
            ParseWarningOut(stage=w.stage, message=w.message, severity=w.severity)
            for w in result.warnings
        ],
```

- [ ] **Step 6: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/unit/parser/test_warning_severity.py tests/unit/parser/test_structurer.py -q`
Expected: PASS。

- [ ] **Step 7: 改动留工作区，不提交**

---

## Task 3: Procedure.import_notes 列 + 迁移

**Files:**
- Modify: `backend/app/models/procedure.py:47`（custom_values 之后）
- Create: `backend/alembic/versions/20260531_0016_procedure_import_notes.py`
- Test: `backend/tests/unit/services/test_import_service.py`（本 Task 仅加模型默认值断言）

- [ ] **Step 1: 写失败测试**

在 `test_import_service.py` 末尾追加：

```python
def test_import_notes_defaults_to_empty_list(db: Session, factory: Factory, storage_tmp) -> None:
    proc = import_service.import_procedure(
        db, name="P", folder_id=_leaf(factory), description="",
        chapters=[ImportNodeIn(title="引言", content_type="chapter")],
        meta=META,
    )
    assert proc.import_notes == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/services/test_import_service.py::test_import_notes_defaults_to_empty_list -q`
Expected: FAIL（`Procedure` 无 `import_notes` 属性 / 列）。

- [ ] **Step 3: 加模型列**

`app/models/procedure.py` 在 `custom_values` 行（`:47`）之后加：

```python
    # 导入时刻的解析 warnings 快照（A 项）：[{stage, message, severity}]。
    # blocking=已放行的潜在丢失；info=有意裁剪/已知丢弃。编辑器常驻提示区据此渲染。
    import_notes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
```

（`Any` 与 `JSON` 已在文件顶部 import，无需新增 import。）

- [ ] **Step 4: 写迁移文件**

新建 `backend/alembic/versions/20260531_0016_procedure_import_notes.py`：

```python
"""add import_notes to procedure

Revision ID: procedure_import_notes
Revises: phase5a_notification
Create Date: 2026-05-31

A 项：导入时刻解析 warnings 快照（强确认 + 编辑器常驻提示区）。
Hand-authored（MySQL prod + SQLite dev/test）。
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "procedure_import_notes"
down_revision: str | None = "phase5a_notification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tb_procedure") as batch:
        batch.add_column(
            sa.Column("import_notes", sa.JSON(), nullable=False, server_default="[]")
        )


def downgrade() -> None:
    with op.batch_alter_table("tb_procedure") as batch:
        batch.drop_column("import_notes")
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/unit/services/test_import_service.py::test_import_notes_defaults_to_empty_list -q`
Expected: PASS（测试用 `Base.metadata.create_all`，自动含新列）。

- [ ] **Step 6: 改动留工作区，不提交**

---

## Task 4: import 落库 import_notes + detail 端点暴露

**Files:**
- Modify: `backend/app/schemas/parse.py:118-138`（`ImportRequest`）
- Modify: `backend/app/services/import_service.py:20`（import）、`:34-57`（签名 + 落库）
- Modify: `backend/app/routers/procedures.py:127-135`（import 端点调用）
- Modify: `backend/app/schemas/procedure.py:200`（`ProcedureMeta`）
- Modify: `backend/app/services/procedure_service.py:81-106`（`_META_FIELDS`）
- Test: `backend/tests/unit/services/test_import_service.py`、`backend/tests/integration/test_word_import.py`

- [ ] **Step 1: 写失败测试（service 持久化）**

在 `test_import_service.py` 追加：

```python
def test_import_persists_import_notes(db: Session, factory: Factory, storage_tmp) -> None:
    from app.schemas.parse import ParseWarningOut
    proc = import_service.import_procedure(
        db, name="P", folder_id=_leaf(factory), description="",
        chapters=[ImportNodeIn(title="引言", content_type="chapter")],
        import_notes=[
            ParseWarningOut(stage="completeness", message="缺图 1/0", severity="blocking"),
            ParseWarningOut(stage="discarded_by_design", message="忽略页眉", severity="info"),
        ],
        meta=META,
    )
    assert [n["severity"] for n in proc.import_notes] == ["blocking", "info"]
    assert proc.import_notes[0]["message"] == "缺图 1/0"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/services/test_import_service.py::test_import_persists_import_notes -q`
Expected: FAIL（`import_procedure` 不接受 `import_notes` 关键字）。

- [ ] **Step 3: ImportRequest 加字段**

`schemas/parse.py` 的 `ImportRequest` 末尾加：

```python
    import_notes: list[ParseWarningOut] = Field(default_factory=list)
```

- [ ] **Step 4: import_service 收并落库**

`import_service.py` 顶部 import 改为：

```python
from app.schemas.parse import ImportNodeIn, ParseWarningOut
```

`import_procedure` 签名加参数（放在 `upload_token` 之后、`meta` 之前）：

```python
def import_procedure(
    db: Session,
    *,
    name: str,
    folder_id: str,
    description: str,
    chapters: list[ImportNodeIn],
    upload_token: str | None = None,
    import_notes: list[ParseWarningOut] | None = None,
    meta: RequestMeta,
) -> Procedure:
```

在 `proc = procedure_service.create_procedure(...)` 之后、`seq = 0` 之前加：

```python
    if import_notes:
        proc.import_notes = [n.model_dump() for n in import_notes]
```

- [ ] **Step 5: 路由传参**

`routers/procedures.py` import 端点的 `import_service.import_procedure(...)` 调用加一行 `import_notes=payload.import_notes,`（放在 `upload_token=payload.upload_token,` 之后）：

```python
    proc = import_service.import_procedure(
        db,
        name=payload.name,
        folder_id=payload.folder_id,
        description=payload.description,
        chapters=payload.chapters,
        upload_token=payload.upload_token,
        import_notes=payload.import_notes,
        meta=meta,
    )
```

- [ ] **Step 6: ProcedureMeta 暴露 + _META_FIELDS**

`schemas/procedure.py` 的 `ProcedureMeta` 在 `version_change_log` 行之后加：

```python
    import_notes: list[dict[str, Any]] = Field(default_factory=list)
```

（确认文件顶部已 import `Field`、`Any`；`ProcedureMeta` 已有 `version_change_log: list[dict[str, Any]]`，故二者均在。）

`procedure_service.py` 的 `_META_FIELDS` 元组在 `"version_change_log",` 之后加一行 `"import_notes",`。

- [ ] **Step 7: 集成测试断言 detail 返回 import_notes**

`test_word_import.py` 里找到现有「import 后 GET /procedures/{id} 取 detail」的测试（或新增）。新增一条：

```python
def test_import_notes_surface_in_detail(client, ...fixtures...) -> None:
    # 用一个会触发 completeness blocking 的 fixture 走 upload→parse→import，
    # 或直接构造 ImportRequest.import_notes 调 POST /procedures/import，
    # 然后 GET /procedures/{id} 断言 body["procedure"]["import_notes"] 非空且含 severity。
    ...
```

> 实现者注：`test_word_import.py` 现有的 client/fixture 形态以该文件已有用例为准（沿用同款 `client`、上传 fixture、解析→导入断言链）。本条最小目标 = 导入带 `import_notes` 后，`GET /procedures/{id}` 响应 `procedure.import_notes` 字段存在且元素含 `severity`。

- [ ] **Step 8: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/unit/services/test_import_service.py tests/integration/test_word_import.py -q`
Expected: PASS。

- [ ] **Step 9: 后端全量回归**

Run: `cd backend && .venv/bin/pytest -q`
Expected: PASS（确认 C003 阈值收紧、severity、新列无回归）。

- [ ] **Step 10: 改动留工作区，不提交**

---

## Task 5: 前端类型 + 拆 parse.ts 流

**Files:**
- Modify: `frontend/src/types/parse.ts:75-78`（`ParseWarning`）、`:113-119`（`ImportRequest`）
- Modify: `frontend/src/types/procedure.ts:28-54`（`ProcedureMeta`）
- Modify: `frontend/src/api/parse.ts:51-74`（删 `importFromWord`，加 `uploadAndParse` / `importParsed`）
- Test: `frontend/tests/unit/wordImport.spec.ts`（整文件替换）

- [ ] **Step 1: 写失败测试（替换 wordImport.spec.ts 全文）**

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'

const post = vi.hoisted(() => vi.fn())
vi.mock('@/api/http', () => ({ http: { post, get: vi.fn() } }))

import { uploadAndParse, importParsed } from '@/api/parse'
import type { ParseWarning } from '@/types/parse'

beforeEach(() => {
  post.mockReset()
  post.mockImplementation((url: string) => {
    if (url === '/uploads') return Promise.resolve({ data: { upload_token: 'tok', filename: 'a.docx' } })
    if (url === '/parse') return Promise.resolve({ data: { chapters: [{ id: 'c', title: 'X' }], warnings: [] } })
    if (url === '/procedures/import') return Promise.resolve({ data: { id: 'p1', code: 'QC-1' } })
    return Promise.reject(new Error('unexpected ' + url))
  })
})

describe('uploadAndParse', () => {
  it('upload→parse，返回 token 与 parsed', async () => {
    const file = new File(['x'], 'a.docx')
    const { uploadToken, parsed } = await uploadAndParse(file)
    expect(uploadToken).toBe('tok')
    expect(parsed.chapters).toHaveLength(1)
    expect(post.mock.calls.map((c) => c[0])).toEqual(['/uploads', '/parse'])
  })
})

describe('importParsed', () => {
  it('调 /procedures/import，回传 chapters 与 import_notes', async () => {
    const notes: ParseWarning[] = [{ stage: 'completeness', message: '缺图', severity: 'blocking' }]
    const proc = await importParsed({
      uploadToken: 'tok',
      folderId: 'f1',
      name: '我的程序',
      chapters: [{ id: 'c' }] as never,
      importNotes: notes,
    })
    expect(proc.id).toBe('p1')
    const body = post.mock.calls.find((c) => c[0] === '/procedures/import')![1]
    expect(body).toMatchObject({ name: '我的程序', folder_id: 'f1', upload_token: 'tok' })
    expect(body.import_notes).toEqual(notes)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run tests/unit/wordImport.spec.ts`
Expected: FAIL（`uploadAndParse` / `importParsed` 未导出）。

- [ ] **Step 3: 改类型**

`src/types/parse.ts` 的 `ParseWarning`：

```typescript
export interface ParseWarning {
  stage: string // boundary | completeness | image | structure | discarded_by_design
  message: string
  severity: 'blocking' | 'info'
}
```

`src/types/parse.ts` 的 `ImportRequest` 加字段：

```typescript
export interface ImportRequest {
  name: string
  folder_id: string
  description?: string
  upload_token?: string
  chapters: ImportNode[]
  import_notes?: ParseWarning[]
}
```

`src/types/procedure.ts` 顶部加 import 并在 `ProcedureMeta` 末尾加字段：

```typescript
import type { ParseWarning } from '@/types/parse'
// ... ProcedureMeta 内 created_at/updated_at 之后：
  import_notes: ParseWarning[]
```

- [ ] **Step 4: 拆 parse.ts**

`src/api/parse.ts` 把 `importFromWord`（第 53-74 行整段）替换为：

```typescript
// 上传 + 解析（不落库）。triage 在调用方按 warnings.severity 决定是否强确认。
export const uploadAndParse = async (
  file: File,
  onStage?: (stage: ImportStage, uploadPct?: number) => void,
): Promise<{ uploadToken: string; parsed: ParseResponse }> => {
  onStage?.('uploading', 0)
  const up = await uploadDocx(file, (e) => {
    if (e.total) onStage?.('uploading', Math.round((e.loaded / e.total) * 100))
  })
  onStage?.('parsing')
  const parsed = await parseDocx(up.upload_token, 'smart')
  return { uploadToken: up.upload_token, parsed }
}

// 用审查后的 chapters + 全量 warnings 快照落库创建草稿。
export const importParsed = async (
  args: {
    uploadToken: string
    folderId: string
    name: string
    chapters: ParseResponse['chapters']
    importNotes: ParseResponse['warnings']
  },
  onStage?: (stage: ImportStage) => void,
): Promise<ProcedureMeta> => {
  onStage?.('creating')
  return importProcedure({
    name: args.name,
    folder_id: args.folderId,
    upload_token: args.uploadToken,
    chapters: args.chapters,
    import_notes: args.importNotes,
  })
}
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd frontend && npx vitest run tests/unit/wordImport.spec.ts`
Expected: PASS。

- [ ] **Step 6: 改动留工作区，不提交**

---

## Task 6: ParseConfirmDialog.vue（阻断式强确认弹窗）

**Files:**
- Create: `frontend/src/components/ParseConfirmDialog.vue`
- Test: `frontend/tests/unit/ParseConfirmDialog.spec.ts`（新建）

- [ ] **Step 1: 写失败测试**

新建 `frontend/tests/unit/ParseConfirmDialog.spec.ts`：

```typescript
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ParseConfirmDialog from '@/components/ParseConfirmDialog.vue'
import type { ParseWarning } from '@/types/parse'

const WARNINGS: ParseWarning[] = [
  { stage: 'completeness', message: '图片可能遗漏：原始 3 / 解析 1', severity: 'blocking' },
  { stage: 'completeness', message: '表格可能遗漏：原始 2 / 解析 1', severity: 'blocking' },
]

function mountDialog() {
  return mount(ParseConfirmDialog, {
    props: { modelValue: true, warnings: WARNINGS },
    global: { plugins: [ElementPlus], stubs: { teleport: true } },
    attachTo: document.body,
  })
}

describe('ParseConfirmDialog', () => {
  it('标题含问题条数，列出每条 message', () => {
    const w = mountDialog()
    expect(w.text()).toContain('2 项')
    expect(w.text()).toContain('图片可能遗漏：原始 3 / 解析 1')
    expect(w.text()).toContain('表格可能遗漏：原始 2 / 解析 1')
  })

  it('点「仍要继续导入」emit confirm', async () => {
    const w = mountDialog()
    const btn = w.findAll('button').find((b) => b.text().includes('仍要继续'))
    await btn?.trigger('click')
    expect(w.emitted('confirm')).toBeTruthy()
  })

  it('点「取消导入」emit cancel', async () => {
    const w = mountDialog()
    const btn = w.findAll('button').find((b) => b.text().includes('取消导入'))
    await btn?.trigger('click')
    expect(w.emitted('cancel')).toBeTruthy()
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run tests/unit/ParseConfirmDialog.spec.ts`
Expected: FAIL（组件不存在）。

- [ ] **Step 3: 写组件**

新建 `frontend/src/components/ParseConfirmDialog.vue`：

```vue
<script setup lang="ts">
import { computed } from 'vue'
import type { ParseWarning } from '@/types/parse'

const props = defineProps<{ modelValue: boolean; warnings: ParseWarning[] }>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'confirm'): void
  (e: 'cancel'): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})
const count = computed(() => props.warnings.length)
</script>

<template>
  <el-dialog v-model="visible" :title="`检测到 ${count} 项内容可能未提取`" width="480px">
    <p class="lead">以下内容可能未能成功解析、导入后将缺失。是否仍要继续导入？</p>
    <ul class="warn-list">
      <li v-for="(w, i) in warnings" :key="i">{{ w.message }}</li>
    </ul>
    <template #footer>
      <el-button @click="emit('cancel')">取消导入</el-button>
      <el-button type="warning" @click="emit('confirm')">仍要继续导入</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.lead { color: #606266; font-size: 13px; margin: 0 0 8px; }
.warn-list { margin: 0; padding-left: 18px; color: var(--el-color-danger, #f56c6c); font-size: 13px; }
.warn-list li { margin: 2px 0; }
</style>
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run tests/unit/ParseConfirmDialog.spec.ts`
Expected: PASS。

- [ ] **Step 5: 改动留工作区，不提交**

---

## Task 7: CreateFromWordDialog 编排强确认流

**Files:**
- Modify: `frontend/src/components/CreateFromWordDialog.vue`（script + template）
- Test: `frontend/tests/unit/CreateFromWordDialog.spec.ts`（改写 mock 与用例）

- [ ] **Step 1: 改写测试**

`CreateFromWordDialog.spec.ts` 顶部 mock 从 `importFromWord` 改为 `uploadAndParse` / `importParsed`：

```typescript
const { uploadAndParse } = vi.hoisted(() => ({ uploadAndParse: vi.fn() }))
const { importParsed } = vi.hoisted(() => ({ importParsed: vi.fn() }))
const { fetchFolderTree } = vi.hoisted(() => ({ fetchFolderTree: vi.fn() }))
vi.mock('@/api/parse', () => ({ uploadAndParse, importParsed }))
vi.mock('@/api/folders', () => ({ fetchFolderTree }))
```

`beforeEach` 改为 reset 这两个 mock（`fetchFolderTree` 同前）。把原「提交成功」「提交失败」两用例替换为下面四个（其余文件夹/文件名用例不变，但凡用 `importFromWord` 的断言改成 `importParsed`）：

```typescript
const PARSED_CLEAN = { uploadToken: 'tok', parsed: { chapters: [{ id: 'c' }], warnings: [] } }
const PARSED_BLOCKING = {
  uploadToken: 'tok',
  parsed: {
    chapters: [{ id: 'c' }],
    warnings: [{ stage: 'completeness', message: '图片可能遗漏：原始 3 / 解析 1', severity: 'blocking' }],
  },
}

it('干净文档（无 blocking）：直接 import、不弹强确认、关闭对话框', async () => {
  uploadAndParse.mockResolvedValue(PARSED_CLEAN)
  importParsed.mockResolvedValue({ id: 'p9', code: 'QC-009' })
  const wrapper = await open()
  await pickFile(wrapper, '记录控制.docx')
  await setFolder(wrapper, 'f1')
  await clickSubmit(wrapper)
  await flushPromises()
  expect(importParsed).toHaveBeenCalledTimes(1)
  expect(wrapper.emitted('imported')?.[0]).toEqual(['p9'])
})

it('有 blocking：弹强确认且未直接 import', async () => {
  uploadAndParse.mockResolvedValue(PARSED_BLOCKING)
  importParsed.mockResolvedValue({ id: 'p9', code: 'QC-009' })
  const wrapper = await open()
  await pickFile(wrapper, '脏文档.docx')
  await setFolder(wrapper, 'f1')
  await clickSubmit(wrapper)
  await flushPromises()
  expect(importParsed).not.toHaveBeenCalled()
  expect(wrapper.findComponent({ name: 'ParseConfirmDialog' }).props('modelValue')).toBe(true)
})

it('blocking 后确认继续：调 importParsed 并回传全量 warnings', async () => {
  uploadAndParse.mockResolvedValue(PARSED_BLOCKING)
  importParsed.mockResolvedValue({ id: 'p9', code: 'QC-009' })
  const wrapper = await open()
  await pickFile(wrapper, '脏文档.docx')
  await setFolder(wrapper, 'f1')
  await clickSubmit(wrapper)
  await flushPromises()
  wrapper.findComponent({ name: 'ParseConfirmDialog' }).vm.$emit('confirm')
  await flushPromises()
  expect(importParsed).toHaveBeenCalledTimes(1)
  expect(importParsed.mock.calls[0][0].importNotes).toEqual(PARSED_BLOCKING.parsed.warnings)
  expect(wrapper.emitted('imported')?.[0]).toEqual(['p9'])
})

it('blocking 后取消：不 import、对话框保持打开', async () => {
  uploadAndParse.mockResolvedValue(PARSED_BLOCKING)
  const wrapper = await open()
  await pickFile(wrapper, '脏文档.docx')
  await setFolder(wrapper, 'f1')
  await clickSubmit(wrapper)
  await flushPromises()
  wrapper.findComponent({ name: 'ParseConfirmDialog' }).vm.$emit('cancel')
  await flushPromises()
  expect(importParsed).not.toHaveBeenCalled()
  expect(wrapper.emitted('imported')).toBeUndefined()
})
```

> stubs 里加 `ParseConfirmDialog: false` 不需要——用真实组件即可（`findComponent({ name: 'ParseConfirmDialog' })` 依赖组件 `name`，见 Step 3 给组件加 `defineOptions({ name: 'ParseConfirmDialog' })`）。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run tests/unit/CreateFromWordDialog.spec.ts`
Expected: FAIL（`uploadAndParse`/`importParsed` 编排尚未实现）。

- [ ] **Step 3: 改 ParseConfirmDialog 加 name（供测试 findComponent）**

`ParseConfirmDialog.vue` 的 `<script setup>` 顶部加：

```typescript
defineOptions({ name: 'ParseConfirmDialog' })
```

- [ ] **Step 4: 改 CreateFromWordDialog**

`<script setup>` 顶部 import 改为：

```typescript
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchFolderTree } from '@/api/folders'
import { uploadAndParse, importParsed, type ImportStage } from '@/api/parse'
import type { FolderTreeNode } from '@/types/folder'
import type { ParseResponse, ParseWarning } from '@/types/parse'
import ParseConfirmDialog from '@/components/ParseConfirmDialog.vue'
```

在 `const errorMsg = ref('')` 之后加状态：

```typescript
const parsed = ref<ParseResponse | null>(null)
const uploadToken = ref('')
const confirmVisible = ref(false)
const blockingWarnings = ref<ParseWarning[]>([])
```

把 `submit()` 整段替换为：

```typescript
async function submit(): Promise<void> {
  if (!file.value) { ElMessage.warning('请选择 .docx 文件'); return }
  if (!form.folder_id) { ElMessage.warning('请选择目标文件夹'); return }
  if (!form.name.trim()) { ElMessage.warning('请输入程序名称'); return }
  errorMsg.value = ''
  try {
    const r = await uploadAndParse(file.value, (s, pct) => {
      stage.value = s
      if (pct !== undefined) uploadPct.value = pct
    })
    parsed.value = r.parsed
    uploadToken.value = r.uploadToken
    const blocking = r.parsed.warnings.filter((w) => w.severity === 'blocking')
    if (blocking.length) {
      blockingWarnings.value = blocking
      confirmVisible.value = true
      stage.value = ''
      uploadPct.value = 0
      return // 等用户在 ParseConfirmDialog 里决定
    }
    await doImport()
  } catch (e) {
    errorMsg.value = errorMessage(e)
    stage.value = ''
    uploadPct.value = 0
  }
}

async function doImport(): Promise<void> {
  if (!parsed.value) return
  try {
    stage.value = 'creating'
    const proc = await importParsed({
      uploadToken: uploadToken.value,
      folderId: form.folder_id,
      name: form.name.trim(),
      chapters: parsed.value.chapters,
      importNotes: parsed.value.warnings,
    })
    ElMessage.success(`已创建 ${proc.code}`)
    visible.value = false
    emit('imported', proc.id)
  } catch (e) {
    errorMsg.value = errorMessage(e)
  } finally {
    stage.value = ''
    uploadPct.value = 0
  }
}

function onConfirmContinue(): void {
  confirmVisible.value = false
  void doImport()
}
function onCancelImport(): void {
  confirmVisible.value = false
  stage.value = ''
  uploadPct.value = 0
}
```

template 里 `</el-dialog>` 之前（footer 之后、根 el-dialog 内或紧随其后均可，放根 el-dialog 之后更清晰）插入：

```html
  <ParseConfirmDialog
    v-model="confirmVisible"
    :warnings="blockingWarnings"
    @confirm="onConfirmContinue"
    @cancel="onCancelImport"
  />
```

> 放置：把它放在最外层（与 `<el-dialog>` 同级，用一个根 `<template>`/`<div>` 包裹，或直接置于主 `el-dialog` 标签之后同级）。若当前单根限制，用 `<template>` 包两者。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd frontend && npx vitest run tests/unit/CreateFromWordDialog.spec.ts`
Expected: PASS。

- [ ] **Step 6: 改动留工作区，不提交**

---

## Task 8: ParseNoticeBar.vue + 编辑器挂载

**Files:**
- Create: `frontend/src/components/editor/ParseNoticeBar.vue`
- Modify: `frontend/src/views/procedures/ProcedureEditorView.vue:207`（左栏）
- Test: `frontend/tests/unit/ParseNoticeBar.spec.ts`（新建）

- [ ] **Step 1: 写失败测试**

新建 `frontend/tests/unit/ParseNoticeBar.spec.ts`：

```typescript
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ParseNoticeBar from '@/components/editor/ParseNoticeBar.vue'
import type { ParseWarning } from '@/types/parse'

const NOTES: ParseWarning[] = [
  { stage: 'completeness', message: '图片可能遗漏：原始 3 / 解析 1', severity: 'blocking' },
  { stage: 'discarded_by_design', message: '已忽略 1 处页眉/页脚', severity: 'info' },
]

function mountBar(notes: ParseWarning[]) {
  return mount(ParseNoticeBar, {
    props: { notes },
    global: { plugins: [ElementPlus] },
  })
}

describe('ParseNoticeBar', () => {
  it('空数组不渲染', () => {
    const w = mountBar([])
    expect(w.text()).toBe('')
  })

  it('渲染条数、blocking 标已放行、info 普通', () => {
    const w = mountBar(NOTES)
    expect(w.text()).toContain('解析提示 2 条')
    expect(w.text()).toContain('已知缺失（已放行）')
    expect(w.text()).toContain('图片可能遗漏：原始 3 / 解析 1')
    expect(w.text()).toContain('已忽略 1 处页眉/页脚')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run tests/unit/ParseNoticeBar.spec.ts`
Expected: FAIL（组件不存在）。

- [ ] **Step 3: 写组件**

新建 `frontend/src/components/editor/ParseNoticeBar.vue`：

```vue
<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ParseWarning } from '@/types/parse'

const props = defineProps<{ notes: ParseWarning[] }>()
const expanded = ref(false)
const total = computed(() => props.notes.length)
const blocking = computed(() => props.notes.filter((n) => n.severity === 'blocking'))
const info = computed(() => props.notes.filter((n) => n.severity !== 'blocking'))
</script>

<template>
  <div v-if="total" class="parse-notice">
    <button class="pn-head" type="button" @click="expanded = !expanded">
      <span class="pn-icon">ⓘ</span>
      解析提示 {{ total }} 条
      <span class="pn-toggle">{{ expanded ? '收起' : '展开' }}</span>
    </button>
    <ul v-show="expanded" class="pn-list">
      <li v-for="(w, i) in blocking" :key="'b' + i" class="pn-blocking">
        已知缺失（已放行）：{{ w.message }}
      </li>
      <li v-for="(w, i) in info" :key="'i' + i" class="pn-info">{{ w.message }}</li>
    </ul>
  </div>
</template>

<style scoped>
.parse-notice { border: 1px solid #f5dab1; background: #fdf6ec; border-radius: 4px; margin: 0 0 8px; }
.pn-head { display: flex; align-items: center; gap: 6px; width: 100%; border: 0; background: none;
  padding: 6px 10px; font-size: 12px; color: #b88230; cursor: pointer; }
.pn-toggle { margin-left: auto; color: #909399; }
.pn-list { margin: 0; padding: 0 12px 8px 28px; font-size: 12px; }
.pn-list li { margin: 2px 0; }
.pn-blocking { color: var(--el-color-danger, #f56c6c); }
.pn-info { color: #606266; }
</style>
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run tests/unit/ParseNoticeBar.spec.ts`
Expected: PASS。

- [ ] **Step 5: 编辑器左栏挂载**

`ProcedureEditorView.vue` `<script setup>` 加 import（与其它 editor 组件 import 同处）：

```typescript
import ParseNoticeBar from '@/components/editor/ParseNoticeBar.vue'
```

template 左栏（约 `:207`）改为：

```html
        <div class="left">
          <ParseNoticeBar :notes="store.procedure?.import_notes ?? []" />
          <NodeTreePanel :readonly="!store.editable" />
        </div>
```

（`store` = `useProcedureEditorStore()`，`store.procedure` 为 `ProcedureMeta | null`，含 `import_notes`。）

- [ ] **Step 6: 前端全量回归**

Run: `cd frontend && npx vitest run`
Expected: PASS（确认拆流、新组件、类型改动无回归；尤其 `ProcedureEditorView.switch.spec.ts` 等编辑器用例）。

- [ ] **Step 7: 改动留工作区，不提交**

---

## 自查（spec 覆盖 / 占位 / 类型一致）

**Spec 覆盖：**
- §3.1 ParseWarning.severity → Task 2 ✓
- §3.2 Procedure.import_notes + 迁移 → Task 3 ✓
- §4 C003 100%（Task 1）/ severity 分流（Task 2）/ import 落库（Task 4）/ detail 暴露（Task 4）✓
- §5 拆流（Task 5）/ ParseConfirmDialog（Task 6）/ 编排（Task 7）/ ParseNoticeBar（Task 8）/ 类型（Task 5）✓
- §5「持久化全部 warnings、blocking 标已放行」→ Task 7 回传 `parsed.warnings` 全量 + Task 8 blocking 标「已知缺失（已放行）」✓
- §7 测试计划 → 各 Task 的 TDD 测试覆盖；后端全量（Task 4 Step 9）+ 前端全量（Task 8 Step 6）✓

**占位扫描：** Task 4 Step 7 的集成测试留了「沿用该文件已有 client/fixture 形态」的弹性说明——这是因 `test_word_import.py` 现有夹具形态需实现者就地对齐，最小断言已给死（`procedure.import_notes` 存在且含 `severity`）。其余步骤均为完整代码。

**类型一致：** `uploadAndParse` 返回 `{ uploadToken, parsed }`；`importParsed` 入参 `{ uploadToken, folderId, name, chapters, importNotes }`——Task 5 定义、Task 7 调用一致。`ParseWarning.severity: 'blocking' | 'info'` 前后端一致。`import_notes`（后端 snake_case 列/字段）↔ 前端 `import_notes`（`ProcedureMeta`）一致。`ParseConfirmDialog` 的 `name`（Task 6 Step3 加）↔ Task 7 `findComponent({ name: 'ParseConfirmDialog' })` 一致。
