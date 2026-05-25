# Procedure 级签字栏（signoff）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将逐步 `step.require_confirmation` 替换为程序级 `procedure.signoff_enabled`；开启后 PDF 在每个非警示型步骤末尾右对齐渲染手写签字栏。

**Architecture:** 受控文档属性（持久化、随版本快照传播、开关在编辑器草稿态）。PDF 沿用现有流式版式（方案 B），不改表格化。分两条 Alembic 迁移：先加 procedure 列（additive），再回填 + 删 step 列，保证每步提交可独立运行。

**Tech Stack:** 后端 FastAPI + SQLAlchemy + Alembic + pytest；前端 Vue 3 + Pinia + Element Plus + vitest；PDF 用 reportlab。

**参考 spec:** `docs/superpowers/specs/2026-05-25-procedure-signoff-design.md`

**测试命令速查:**
- 后端单测：`cd backend && .venv/bin/python -m pytest <path> -v`
- 后端全量：`cd backend && .venv/bin/python -m pytest -q`
- 迁移：`cd backend && .venv/bin/alembic upgrade head` / `.venv/bin/alembic history`
- 前端单测：`cd frontend && npx vitest run <path>`
- 前端类型：`cd frontend && npm run typecheck`

> **迁移链当前 head：`drop_expected_output`**（本计划新增两条接在其后）。
> **说明：spec 写的是单条迁移；本计划拆成两条（add / backfill+drop），净效果一致，但让 Task 1 纯 additive、Task 3 收尾，更利于增量提交与回滚。**

---

## Task 1: 后端 — Procedure 新增 `signoff_enabled`（additive）

纯新增字段：模型 + 迁移（仅加列）+ schema + 版本 fork 传播。完成后 `require_confirmation` 原封不动，测试全绿。

**Files:**
- Modify: `backend/app/models/procedure.py`
- Create: `backend/alembic/versions/20260525_0003_add_procedure_signoff.py`
- Modify: `backend/app/schemas/procedure.py`（ProcedureUpdate / ProcedureOut / ProcedureMeta）
- Modify: `backend/app/services/version_flow_service.py`（`_fork`）
- Test: `backend/tests/unit/services/test_version_flow_service.py`

- [ ] **Step 1: 写失败测试 — fork 传播 signoff_enabled**

在 `backend/tests/unit/services/test_version_flow_service.py` 末尾追加：

```python
def test_upgrade_propagates_signoff_enabled(db: Session, factory: Factory) -> None:
    folder = _leaf(factory)
    proc = _published(factory, folder, signoff_enabled=True)
    new = version_flow_service.upgrade_version(db, proc.id, META)
    assert new.signoff_enabled is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/services/test_version_flow_service.py::test_upgrade_propagates_signoff_enabled -v`
Expected: FAIL — `TypeError`（factory 不认 signoff_enabled）或 `AttributeError: signoff_enabled`。

- [ ] **Step 3: 模型加列**

`backend/app/models/procedure.py`，在 `archived_at` 行（line 53）后、relationships 之前加：

```python
    archived_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    # PDF 操作员签字栏总开关（程序级，受控文档属性）
    signoff_enabled: Mapped[bool] = mapped_column(default=False, server_default="0")
```

- [ ] **Step 4: 写迁移（仅加列）**

新建 `backend/alembic/versions/20260525_0003_add_procedure_signoff.py`：

```python
"""add signoff_enabled to procedure

Revision ID: add_procedure_signoff
Revises: drop_expected_output
Create Date: 2026-05-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'add_procedure_signoff'
down_revision: str | None = 'drop_expected_output'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('tb_procedure') as batch:
        batch.add_column(sa.Column('signoff_enabled', sa.Boolean(), server_default='0', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('tb_procedure') as batch:
        batch.drop_column('signoff_enabled')
```

- [ ] **Step 5: schema 加字段**

`backend/app/schemas/procedure.py`：

`ProcedureUpdate` 末尾（`version_update_notes` 后）加：
```python
    signoff_enabled: bool = Field(default=False)
```
`ProcedureOut` 字段列表加（任意位置，建议 `description` 后）：
```python
    signoff_enabled: bool
```
`ProcedureMeta` 字段列表加（建议 `version_update_notes` 后）：
```python
    signoff_enabled: bool
```

- [ ] **Step 6: fork 传播**

`backend/app/services/version_flow_service.py` 的 `_fork()` 内 `Procedure(...)` 构造，在 `custom_values=dict(source.custom_values),` 后加：

```python
        custom_values=dict(source.custom_values),
        signoff_enabled=source.signoff_enabled,
```

- [ ] **Step 7: 跑测试 + 迁移确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/services/test_version_flow_service.py -v`
Expected: PASS（含新用例）。
Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: 全绿。
Run: `cd backend && .venv/bin/alembic upgrade head && .venv/bin/alembic current`
Expected: `add_procedure_signoff (head)`。

- [ ] **Step 8: 提交**

```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
git add backend/app/models/procedure.py backend/alembic/versions/20260525_0003_add_procedure_signoff.py backend/app/schemas/procedure.py backend/app/services/version_flow_service.py backend/tests/unit/services/test_version_flow_service.py
git commit -m "feat(procedure): add signoff_enabled field (additive)"
```

---

## Task 2: 后端 — PDF 按程序级开关渲染签字栏

把渲染从逐步 `require_confirmation` 切到程序级 `signoff_enabled`，右对齐，排除警示型。`require_confirmation` 列此时仍在但 PDF 不再读它（下一 Task 删）。

**Files:**
- Modify: `backend/app/services/pdf/context.py`（`ProcedureData` + `load_render_data`）
- Modify: `backend/app/services/pdf/styles.py`（新增 `step_signoff`）
- Modify: `backend/app/services/pdf/sections.py`（`_render_step`）
- Test: `backend/tests/unit/services/pdf/test_sections.py`

- [ ] **Step 1: 写失败测试 — 签字栏由程序级开关 + 类型决定**

`backend/tests/unit/services/pdf/test_sections.py`：把 `_proc` 的 base dict 加上 `signoff_enabled=False`（在 `folder_full_path` 后）：

```python
        folder_full_path="根/质检",
        signoff_enabled=False,
```

找到现有的 require_confirmation 渲染测试（约 line 130-143，断言"已确认完成"那条），整体替换为下面三个用例：

```python
def test_signoff_renders_for_non_alert_when_enabled() -> None:
    step = _step(input_schema={"type": "CHECK"})
    out: list = []
    sections._render_step(step, _data(_proc(signoff_enabled=True)), out)
    assert any("签字" in _text(f) for f in out)


def test_signoff_absent_when_disabled() -> None:
    step = _step(input_schema={"type": "CHECK"})
    out: list = []
    sections._render_step(step, _data(_proc(signoff_enabled=False)), out)
    assert not any("签字" in _text(f) for f in out)


def test_signoff_absent_for_alert_type_even_when_enabled() -> None:
    step = _step(input_schema={"type": "WARNING"}, content="<p>危险</p>")
    out: list = []
    sections._render_step(step, _data(_proc(signoff_enabled=True)), out)
    assert not any("签字" in _text(f) for f in out)
```

> 注：`_step` 此时仍带 `require_confirmation`（Task 3 删），不影响本测试。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/services/pdf/test_sections.py -v`
Expected: FAIL — `_proc()` 不认 `signoff_enabled`（ProcedureData 还没该字段）。

- [ ] **Step 3: ProcedureData 加字段 + 装配**

`backend/app/services/pdf/context.py`：
`ProcedureData` dataclass 末尾（`folder_full_path: str` 后）加：
```python
    folder_full_path: str
    signoff_enabled: bool
```
`load_render_data` 内 `ProcedureData(...)` 构造（`folder_full_path=folder_path,` 后）加：
```python
        folder_full_path=folder_path,
        signoff_enabled=proc.signoff_enabled,
    )
```

- [ ] **Step 4: 新增右对齐样式**

`backend/app/services/pdf/styles.py`，在 `add("step_mark", ...)`（line 87）后加：

```python
    add("step_mark", fontName=song, fontSize=11, textColor=Color(0.25, 0.25, 0.25))
    # 操作员签字栏：右对齐（程序级 signoff，§6.3）
    add("step_signoff", fontName=song, fontSize=12, alignment=TA_RIGHT, spaceBefore=4)
```

（`TA_RIGHT` 已在文件顶部 import，无需新增。）

- [ ] **Step 5: 改 `_render_step`**

`backend/app/services/pdf/sections.py`，把"确认行"分支（`if st.require_confirmation:` 那段）替换为：

```python
    # 签字栏：程序级开关开启 且 非警示型（右对齐手写签字，§6.3 顺序 6）
    if data.procedure.signoff_enabled and ftype not in ("NOTE", "CAUTION", "WARNING"):
        out.append(
            Paragraph(
                "签字: __________   日期: __________",
                s("step_signoff"),
            )
        )
```

- [ ] **Step 6: 跑测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/services/pdf/test_sections.py -v`
Expected: PASS。
Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: 全绿（若 `test_context.py` 因 ProcedureData 新字段失败，见 Task 3 Step 处理；如本步即红，在 test_context 的 ProcedureData 构造/断言补 `signoff_enabled`）。

- [ ] **Step 7: 提交**

```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
git add backend/app/services/pdf/context.py backend/app/services/pdf/styles.py backend/app/services/pdf/sections.py backend/tests/unit/services/pdf/test_sections.py
git commit -m "feat(pdf): render signoff line per procedure-level toggle"
```

---

## Task 3: 后端 — 移除 `require_confirmation`

迁移回填意图到程序级再删列；清理 model / node schema / service / pdf StepData / 版本拷贝。

**Files:**
- Create: `backend/alembic/versions/20260525_0004_drop_step_require_confirmation.py`
- Modify: `backend/app/models/step.py`
- Modify: `backend/app/schemas/node.py`（StepCreate/Update/Upsert/Out）
- Modify: `backend/app/services/step_service.py`、`backend/app/services/editor_service.py`
- Modify: `backend/app/services/version_flow_service.py`（`_STEP_COPY`）
- Modify: `backend/app/services/pdf/context.py`（`StepData` + `_to_step`）
- Test: `backend/tests/unit/services/pdf/test_sections.py`、`backend/tests/unit/services/pdf/test_context.py`

- [ ] **Step 1: 写迁移（回填 + 删列）**

新建 `backend/alembic/versions/20260525_0004_drop_step_require_confirmation.py`：

```python
"""backfill signoff_enabled then drop step.require_confirmation

Revision ID: drop_step_require_confirmation
Revises: add_procedure_signoff
Create Date: 2026-05-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'drop_step_require_confirmation'
down_revision: str | None = 'add_procedure_signoff'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 保留意图到程序级：任一步骤勾过 → 该 procedure.signoff_enabled = 1
    op.get_bind().execute(sa.text(
        "UPDATE tb_procedure SET signoff_enabled = 1 WHERE id IN "
        "(SELECT DISTINCT procedure_id FROM tb_procedure_step WHERE require_confirmation = 1)"
    ))
    with op.batch_alter_table('tb_procedure_step') as batch:
        batch.drop_column('require_confirmation')


def downgrade() -> None:
    with op.batch_alter_table('tb_procedure_step') as batch:
        batch.add_column(sa.Column('require_confirmation', sa.Boolean(), nullable=False, server_default='0'))
```

- [ ] **Step 2: 删模型列**

`backend/app/models/step.py`：删除
```python
    require_confirmation: Mapped[bool] = mapped_column(default=False, server_default="0")
```

- [ ] **Step 3: 删 node schema 字段**

`backend/app/schemas/node.py`：从 `StepCreate` / `StepUpdate` / `StepUpsert` 删
```python
    require_confirmation: bool = False
```
从 `StepOut` 删
```python
    require_confirmation: bool
```

- [ ] **Step 4: 删 service 赋值**

`backend/app/services/step_service.py`：删 create 的 `require_confirmation=data.require_confirmation,` 与 update 的 `st.require_confirmation = data.require_confirmation`。
`backend/app/services/editor_service.py`：删 `st_node.require_confirmation = su.require_confirmation`。

- [ ] **Step 5: 删版本拷贝字段**

`backend/app/services/version_flow_service.py`：`_STEP_COPY` 元组删 `"require_confirmation",`。

- [ ] **Step 6: 删 pdf StepData 字段**

`backend/app/services/pdf/context.py`：`StepData` dataclass 删 `require_confirmation: bool`；`_to_step` 删 `require_confirmation=s.require_confirmation,`。

- [ ] **Step 7: 清测试中的残留构造**

`backend/tests/unit/services/pdf/test_sections.py`：`_step` 的 base dict 删 `require_confirmation=False,`。
`backend/tests/unit/services/pdf/test_context.py`：若有 StepData/断言引用 `require_confirmation`，删除（运行后按报错定位）。

- [ ] **Step 8: 跑全量 + 迁移**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: 全绿。若有文件仍引用 `require_confirmation`，`grep -rn "require_confirmation" backend/app backend/tests` 应为空。
Run: `cd backend && .venv/bin/alembic upgrade head && .venv/bin/alembic current`
Expected: `drop_step_require_confirmation (head)`。

- [ ] **Step 9: 提交**

```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
git add backend/alembic/versions/20260525_0004_drop_step_require_confirmation.py backend/app/models/step.py backend/app/schemas/node.py backend/app/services/step_service.py backend/app/services/editor_service.py backend/app/services/version_flow_service.py backend/app/services/pdf/context.py backend/tests/unit/services/pdf/test_sections.py backend/tests/unit/services/pdf/test_context.py
git commit -m "refactor(step): drop require_confirmation (migrated to procedure signoff)"
```

---

## Task 4: 前端 — 类型与 store

types 删 step 字段、加 procedure 字段；store 同步。

**Files:**
- Modify: `frontend/src/types/node.ts`
- Modify: `frontend/src/types/procedure.ts`
- Modify: `frontend/src/store/procedureEditor.ts`
- Test: `frontend/tests/unit/procedureEditorStore.spec.ts`

- [ ] **Step 1: 写失败测试 — buildPayload 含 signoff_enabled**

`frontend/tests/unit/procedureEditorStore.spec.ts`，在 `describe('buildPayload', ...)`（line 195）内加：

```typescript
  it('includes signoff_enabled in payload', () => {
    // 复用本 describe('buildPayload') 已有的 store 初始化（procedure 已加载）
    const s = useProcedureEditorStore()
    s.procedure!.signoff_enabled = true
    const payload = s.buildPayload()
    expect(payload.signoff_enabled).toBe(true)
  })
```

> 现有 `describe('buildPayload')`（line 195）的用例已先把 store 初始化到带 procedure 的状态再调 `s.buildPayload()`；本用例复用该初始化，仅覆写 `signoff_enabled`。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts`
Expected: FAIL — `payload.signoff_enabled` 为 undefined / 类型错误。

- [ ] **Step 3: types/node.ts 删 require_confirmation**

`frontend/src/types/node.ts`：从 `StepOut`、`StepUpsert`、`EditorStep` 删 `require_confirmation: boolean`（含 EditorStep）；从 `FlatRow` 删 `require_confirmation: boolean // 仅 step`。

- [ ] **Step 4: types/procedure.ts 加 signoff_enabled**

`frontend/src/types/procedure.ts`：`ProcedureMeta`（line 29）加
```typescript
  signoff_enabled: boolean
```
`ProcedureUpdate`（line 99）加同字段（`ProcedureSaveIn extends ProcedureUpdate` 自动继承）。

- [ ] **Step 5: store 清理 + 透传**

`frontend/src/store/procedureEditor.ts`：
- `emptyStep` 删 `require_confirmation: false,`；
- `ingestStep` 删 `require_confirmation: s.require_confirmation,`；
- 扁平行 walk 内 chapter 行删 `require_confirmation: false,`、step 行删 `require_confirmation: st.require_confirmation,`（两处）；
- `buildPayload` 程序级返回（`version_update_notes: p.version_update_notes,` 附近）加 `signoff_enabled: p.signoff_enabled,`；删 step payload 里的 `require_confirmation: s.require_confirmation,`。

- [ ] **Step 6: 跑测试 + 类型**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts`
Expected: PASS。
Run: `cd frontend && npm run typecheck`
Expected: 报错集中在尚未改的 UI / 预览 / 其它 spec（Task 5/6 处理）。store 与 types 自身应无错。

- [ ] **Step 7: 提交**

```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
git add frontend/src/types/node.ts frontend/src/types/procedure.ts frontend/src/store/procedureEditor.ts frontend/tests/unit/procedureEditorStore.spec.ts
git commit -m "feat(editor): signoff_enabled in types and store"
```

---

## Task 5: 前端 — 编辑器 UI

加程序级开关、删步骤复选框、删树 ⚠ 图标。

**Files:**
- Modify: `frontend/src/components/editor/ProcedureDetailsPanel.vue`
- Modify: `frontend/src/components/editor/StepDetailPanel.vue`
- Modify: `frontend/src/components/editor/TreeRow.vue`
- Test: `frontend/tests/unit/editorNumbering.spec.ts`、`frontend/tests/unit/utils/treeDnd.spec.ts`（删 fixture 残留）

- [ ] **Step 1: ProcedureDetailsPanel 加开关**

`frontend/src/components/editor/ProcedureDetailsPanel.vue`，在"版本更新说明" `el-form-item`（line 81-83）后、自定义字段 `<template>` 前加：

```vue
        <el-form-item label="PDF 签字栏">
          <el-switch
            :model-value="p.signoff_enabled"
            :disabled="ro"
            @change="(v: string | number | boolean) => store.setMetaField('signoff_enabled', !!v)"
          />
        </el-form-item>
```

- [ ] **Step 2: StepDetailPanel 删复选框**

`frontend/src/components/editor/StepDetailPanel.vue`：删除"需要操作员确认"那段 `el-checkbox`（`:model-value="step.require_confirmation"` 整块）。

- [ ] **Step 3: TreeRow 删 ⚠**

`frontend/src/components/editor/TreeRow.vue`：删除
```vue
    <span v-if="row.require_confirmation" class="tr-flag" title="需操作员确认">⚠</span>
```
若 `.tr-flag` 样式仅此处使用，一并删除其 CSS 规则。

- [ ] **Step 4: 清 fixture 残留**

`frontend/tests/unit/editorNumbering.spec.ts`、`frontend/tests/unit/utils/treeDnd.spec.ts`：删 EditorStep fixture 里的 `require_confirmation: false,`（typecheck/测试会指出位置）。

- [ ] **Step 5: 跑测试 + 类型**

Run: `cd frontend && npx vitest run tests/unit/editorNumbering.spec.ts tests/unit/utils/treeDnd.spec.ts`
Expected: PASS。
Run: `cd frontend && npm run typecheck`
Expected: 仅剩预览相关（Task 6）报错。

- [ ] **Step 6: 提交**

```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
git add frontend/src/components/editor/ProcedureDetailsPanel.vue frontend/src/components/editor/StepDetailPanel.vue frontend/src/components/editor/TreeRow.vue frontend/tests/unit/editorNumbering.spec.ts frontend/tests/unit/utils/treeDnd.spec.ts
git commit -m "feat(editor): procedure signoff toggle, drop per-step confirmation UI"
```

---

## Task 6: 前端 — PDF 预览

预览改为读程序级开关 + 类型，签字行右对齐静态、去掉可勾选。

**Files:**
- Modify: `frontend/src/components/PdfPreview/pdfModel.ts`（`PreviewModel` + `buildModel`）
- Modify: `frontend/src/components/PdfPreview/PdfPreviewDialog.vue`
- Test: `frontend/tests/unit/pdfModel.spec.ts`

- [ ] **Step 1: 写失败测试 — buildModel 暴露 signoffEnabled**

`frontend/tests/unit/pdfModel.spec.ts`：先删 `step()` helper（line 21）里的 `require_confirmation: false,`。在文件内（buildModel 相关 describe，或新增 describe）加：

```typescript
  it('exposes signoffEnabled from procedure', () => {
    const d = detail()
    d.procedure.signoff_enabled = true
    const model = buildModel(d, layout)
    expect(model.signoffEnabled).toBe(true)
  })
```

> 本 spec 文件已有 `function detail(): ProcedureDetail`（约 line 26）及 buildModel 用例使用的 `layout` fixture——直接复用，仅给 `d.procedure` 覆写 `signoff_enabled`。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run tests/unit/pdfModel.spec.ts`
Expected: FAIL — `model.signoffEnabled` undefined / 类型错误。

- [ ] **Step 3: PreviewModel 加字段 + buildModel 装配**

`frontend/src/components/PdfPreview/pdfModel.ts`：
`PreviewModel` interface（line 56）加：
```typescript
  signoffEnabled: boolean
```
`buildModel`（line 281）返回对象加：
```typescript
    signoffEnabled: detail.procedure.signoff_enabled,
```

- [ ] **Step 4: PdfPreviewDialog 改签字块**

`frontend/src/components/PdfPreview/PdfPreviewDialog.vue`，把签字块（line 244-252）替换为右对齐静态行：

```vue
              <p
                v-if="model.signoffEnabled && !isAlertType(b.step.input_schema.type)"
                class="signoff"
              >
                签字: __________ 日期: __________
              </p>
```

并在 `<style>` 里把 `.signoff` 设为右对齐（找到现有 `.signoff` 规则，加 `text-align: right;`；若有 `.signoff .box` / `.signoff.checked` 等勾选相关样式，删除）。`checked` / `toggle` 若不再被其它元素使用，可一并清理（hold-point / signature-bar / 封面签名区若仍用 toggle 则保留）。

- [ ] **Step 5: 跑测试 + 类型 + 全量前端**

Run: `cd frontend && npx vitest run tests/unit/pdfModel.spec.ts`
Expected: PASS。
Run: `cd frontend && npm run typecheck`
Expected: 无错。
Run: `cd frontend && npx vitest run`
Expected: 全绿。
确认无残留：`grep -rn "require_confirmation" frontend/src frontend/tests` → 空。

- [ ] **Step 6: 提交**

```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
git add frontend/src/components/PdfPreview/pdfModel.ts frontend/src/components/PdfPreview/PdfPreviewDialog.vue frontend/tests/unit/pdfModel.spec.ts
git commit -m "feat(preview): signoff line driven by procedure toggle"
```

---

## Task 7: 文档同步

**Files:**
- Modify: `docs/data-model.md`、`docs/pdf-rendering.md`、`docs/editor-behavior.md`、`docs/api-specification.md`

- [ ] **Step 1: data-model.md**

step 表删 `require_confirmation` 行（沿用删除线约定）；procedure 表（§3.3）加
`| \`signoff_enabled\` | BOOLEAN | NOT NULL DEFAULT FALSE | PDF 操作员签字栏总开关（程序级）|`。

- [ ] **Step 2: pdf-rendering.md**

§6.3 顺序 6"确认行"改为"签字栏：程序级 `signoff_enabled` 开启且非警示型 → 步末右对齐 `签字: __ 日期: __`"；§6.7 signoff 预览交互去掉逐步确认框的可勾选描述（保留 hold-point / signature-bar / 封面）。

- [ ] **Step 3: editor-behavior.md**

去掉 `⚠ = require_confirmation` 图标说明与"切换 require_confirmation"行为行；程序详情面板加"PDF 签字栏"开关条目。

- [ ] **Step 4: api-specification.md**

step 示例 payload 删 `require_confirmation`（已删则跳过）；procedure 示例/字段加 `signoff_enabled`。

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
git add docs/data-model.md docs/pdf-rendering.md docs/editor-behavior.md docs/api-specification.md
git commit -m "docs: procedure signoff replaces per-step require_confirmation"
```

---

## 收尾验证（全部 Task 后）

- [ ] 后端全量：`cd backend && .venv/bin/python -m pytest -q` 全绿
- [ ] 前端全量：`cd frontend && npx vitest run` 全绿 + `npm run typecheck` 无错
- [ ] 迁移：`cd backend && .venv/bin/alembic upgrade head` → `drop_step_require_confirmation (head)`
- [ ] 残留扫描：`grep -rn "require_confirmation" backend/app backend/tests frontend/src frontend/tests` 为空
- [ ] 手动冒烟（可选）：编辑器开/关"PDF 签字栏" → 预览/下载 PDF，非警示型步骤右侧出现签字行、警示型不出
