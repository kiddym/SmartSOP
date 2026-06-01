# P0 — 步骤类型语义层（纯叠加，零迁移） Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给节点新增一个 `step_type` 语义标签（7 类：action/data/decision/wait/information/hold/link）+ 预留 `step_config` JSON，**与现有 15 型 `input_schema` 并存联动**，只驱动编写侧显示（详情面板下拉 + 树行色条）。零数据迁移、零行为破坏，作为后续执行态（P1~P3）的地基。

**Architecture:** 后端 `ProcedureNode` 加两列（均可空）→ schema/服务白名单放行 → 序列化回带。前端 `step_type` 加入 Node 类型；新增纯函数 `deriveStepType`（从 `input_schema.type` 派生显示默认，使旧数据无需写库即可显示）+ `STEP_TYPE_META`（标签/色）。`NodeDetailPanel` 在 `kind==='step'` 时多一个「步骤类型」下拉；`NodeTreeRow` 显示色条。Spec：`docs/superpowers/specs/2026-06-01-step-type-mobile-execution-design.md`（P0 行）。

**关于范围收敛（重要）：** Spec 的 P0 原列了「解析推断 + NCW 同页 PDF」。核查发现解析器目前只产出 chapter/content、**不产出 step**（[result.py](../../../backend/app/parser/result.py)），步骤化在编辑器标记阶段完成——故解析推断无落点，连同 NCW-PDF 一并移到 **P0b**（另立计划）。本 P0 仅做"模型 + 编写侧显示"这一最小垂直切片。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Alembic + pytest（后端）；Vue 3 + Pinia + vitest/jsdom + vue-tsc（前端）。无新依赖。

---

## File Structure

**后端**
- **Modify** `backend/app/models/node.py` — 加 `step_type` / `step_config` 两列。
- **Create** `backend/alembic/versions/20260601_0001_add_node_step_type.py` — add_column ×2（可空）。
- **Modify** `backend/app/schemas/node.py` — NodeOut / NodePatchIn / NodeCreateIn / NodeBatchItem 加字段。
- **Modify** `backend/app/services/node_service.py` — `_PATCHABLE` 加键；`_node_dict` 序列化回带；`create_node` 透传。
- **Modify** `backend/tests/unit/services/test_node_service.py` + `backend/tests/integration/test_nodes_api.py` — round-trip 测试。

**前端**
- **Modify** `frontend/src/types/node.ts` — `StepType` 联合 + Node/NodePatch/NodeCreate/NodeBatchItem 加字段。
- **Modify** `frontend/src/utils/editor.ts` — `STEP_TYPES` / `STEP_TYPE_META` / `deriveStepType` / `effectiveStepType`。
- **Modify** `frontend/src/store/nodeEditor.ts` — `setStepType`（走 batchUpdate，对齐 `setKind`）。
- **Modify** `frontend/src/components/editor/NodeDetailPanel.vue` — `kind==='step'` 时加「步骤类型」下拉。
- **Modify** `frontend/src/components/editor/NodeTreeRow.vue` — step 行显示 step_type 色条。
- **Modify** `frontend/tests/unit/editorUtils.spec.ts` + `NodeDetailPanel.spec.ts` + `NodeTreeRow.spec.ts`。

---

## Task 1: 后端模型 + 迁移

**Files:** `backend/app/models/node.py`, `backend/alembic/versions/20260601_0001_add_node_step_type.py`

- [ ] **Step 1: 加两列** — 在 [node.py](../../../backend/app/models/node.py) `revision` 字段前插入：
```python
    # 步骤语义类型（7 类，P0 叠加层；null=未标注，显示时由 input_schema.type 派生）。
    # action|data|decision|wait|information|hold|link；'notice'(NCW)留待 P4 归位。
    step_type: Mapped[str | None] = mapped_column(String(20), nullable=True, default=None)
    # 流程控制只读参数（decision 分支/wait 时长/hold 门控/link 目标）。P0 仅建列，编写 UI 在 P1。
    step_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
```
（`String` / `JSON` / `Any` 已在文件顶部导入，无需新增 import。）

- [ ] **Step 2: 迁移脚本** — 新建 `backend/alembic/versions/20260601_0001_add_node_step_type.py`，`down_revision` 指向当前最新 `20260531_0004_add_numbering_profile`（实施时用 `alembic heads` 复核）：
```python
"""add step_type / step_config to tb_procedure_node (P0 additive)"""
from alembic import op
import sqlalchemy as sa

revision = "20260601_0001"
down_revision = "20260531_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tb_procedure_node", sa.Column("step_type", sa.String(length=20), nullable=True))
    op.add_column("tb_procedure_node", sa.Column("step_config", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("tb_procedure_node", "step_config")
    op.drop_column("tb_procedure_node", "step_type")
```
（`step_config` 列设 `nullable=True`：MySQL JSON 列不便给 server_default；应用层 `default=dict` 兜底，读出 null 视为 `{}`。）

- [ ] **Step 3: 升级并核对** — `cd backend && alembic upgrade head`；确认无报错、`tb_procedure_node` 多出两列。

---

## Task 2: 后端 schema + 服务放行

**Files:** `backend/app/schemas/node.py`, `backend/app/services/node_service.py`

- [ ] **Step 1: schema 加字段** — [schemas/node.py](../../../backend/app/schemas/node.py)：
  - `NodeOut` 加：`step_type: str | None = None` 与 `step_config: dict[str, Any] = Field(default_factory=dict)`（文件已导入 `Field`）。
  - `NodePatchIn` 加：`step_type: str | None = None` 与 `step_config: dict[str, Any] | None = None`。
  - `NodeCreateIn` 加：`step_type: str | None = None` 与 `step_config: dict[str, Any] = Field(default_factory=dict)`。
  - `NodeBatchItem` 加：`step_type: str | None = None`（批量改类型，对齐 `setStepType` 走 batch）。

- [ ] **Step 2: 服务白名单 + 序列化 + 透传** — [node_service.py](../../../backend/app/services/node_service.py)：
  - `_PATCHABLE`（line 109）加 `"step_type", "step_config"`。
  - `_node_dict`（line ~79-90 的 dict 字面量）加 `"step_type": r.step_type,` 与 `"step_config": r.step_config or {},`。
  - `create_node`（line 160 的 `ProcedureNode(...)`）加 `step_type=data.get("step_type"), step_config=data.get("step_config") or {},`。
  - **不动** `enforce_node_invariants`（P0 不加 step_type 约束，保持纯叠加；约束在 P1 随 step_config 编写一起加）。

- [ ] **Step 3: 后端测试** — 在 `test_node_service.py` 加：patch `{step_type:'decision'}` 后读出为 `decision`；create 带 `step_type` 回读一致；patch 非法键仍被拒（回归）。在 `test_nodes_api.py` 加：`PATCH /nodes/{id}` 传 `step_type` → 200 且 `NodeOut.step_type` 回带；旧节点（无 step_type）GET 返回 `null` + `step_config={}`。

- [ ] **Step 4: 跑后端门禁** — `cd backend && pytest tests/unit/services/test_node_service.py tests/integration/test_nodes_api.py` → 全绿。

- [ ] **Step 5: Commit**
```bash
git add backend/app/models/node.py backend/alembic/versions/20260601_0001_add_node_step_type.py backend/app/schemas/node.py backend/app/services/node_service.py backend/tests
git commit -m "feat(node): add step_type + step_config columns (additive, P0 Task 1-2)"
```

---

## Task 3: 前端类型 + 纯函数（TDD）

**Files:** `frontend/src/types/node.ts`, `frontend/src/utils/editor.ts`, `frontend/tests/unit/editorUtils.spec.ts`

- [ ] **Step 1: 类型** — [types/node.ts](../../../frontend/src/types/node.ts)：
```ts
// 步骤语义类型（7 类，P0 叠加层，对齐后端 step_type）。
export type StepType =
  | 'action' | 'data' | 'decision' | 'wait' | 'information' | 'hold' | 'link'
export const STEP_TYPES: readonly StepType[] =
  ['action', 'data', 'decision', 'wait', 'information', 'hold', 'link']
```
并给 `Node` 加 `step_type: StepType | null`、`step_config: Record<string, unknown>`；给 `NodePatch` / `NodeCreate` 加可选 `step_type?: StepType | null`、`step_config?: Record<string, unknown>`；给 `NodeBatchItem` 加 `step_type?: StepType | null`。

- [ ] **Step 2: 先写失败测试** — append `frontend/tests/unit/editorUtils.spec.ts`：
```ts
import { deriveStepType, effectiveStepType, STEP_TYPE_META, STEP_TYPES } from '@/utils/editor'

describe('deriveStepType (从 15 型派生显示默认)', () => {
  it.each(['NUMBER','METER','CHECKBOX','RADIO','DATE','UPLOAD','PHOTO'] as const)('%s → data', (t) => {
    expect(deriveStepType(t)).toBe('data')
  })
  it('SIGNATURE → hold', () => expect(deriveStepType('SIGNATURE')).toBe('hold'))
  it.each(['NOTE','CAUTION','WARNING'] as const)('%s → information', (t) => {
    expect(deriveStepType(t)).toBe('information')
  })
  it.each(['COMMON','NONE','CHECK','YESNO'] as const)('%s → action', (t) => {
    expect(deriveStepType(t)).toBe('action')
  })
})

describe('effectiveStepType', () => {
  it('显式 step_type 优先', () => {
    expect(effectiveStepType('hold', 'NUMBER')).toBe('hold')
  })
  it('step_type 为空时回退派生', () => {
    expect(effectiveStepType(null, 'NUMBER')).toBe('data')
  })
})

describe('STEP_TYPE_META', () => {
  it('覆盖全部 7 类', () => {
    for (const t of STEP_TYPES) expect(STEP_TYPE_META[t]).toBeTruthy()
  })
})
```
Run `cd frontend && npm test -- tests/unit/editorUtils.spec.ts` → FAIL（未导出）。

- [ ] **Step 3: 实现** — append [utils/editor.ts](../../../frontend/src/utils/editor.ts)：
```ts
import type { FormType, StepType } from '@/types/node'

export interface StepTypeMeta { label: string; color: 'gray' | 'purple' | 'cyan' | 'blue' | 'orange' }
// 色对齐 spec §4.2（建立 §6.5.4 视觉-行为条件反射）。
export const STEP_TYPE_META: Record<StepType, StepTypeMeta> = {
  action:      { label: '执行', color: 'gray' },
  data:        { label: '记录', color: 'purple' },
  decision:    { label: '判断', color: 'cyan' },
  wait:        { label: '等待', color: 'blue' },
  information: { label: '信息', color: 'gray' },
  hold:        { label: '暂停', color: 'orange' },
  link:        { label: '跳转', color: 'blue' },
}

const _DATA_FORMS: readonly FormType[] = ['NUMBER','METER','CHECKBOX','RADIO','DATE','UPLOAD','PHOTO']
/** 旧数据无 step_type 时，从 input_schema.type 派生一个显示默认（不写库，§3.3 映射）。 */
export function deriveStepType(formType: FormType): StepType {
  if (_DATA_FORMS.includes(formType)) return 'data'
  if (formType === 'SIGNATURE') return 'hold'
  if (isAlertType(formType)) return 'information'
  return 'action'
}
/** 显式 step_type 优先，否则回退派生。 */
export function effectiveStepType(stepType: StepType | null | undefined, formType: FormType): StepType {
  return stepType ?? deriveStepType(formType)
}
```
Run 同上 → PASS。

- [ ] **Step 4: Commit**
```bash
git add frontend/src/types/node.ts frontend/src/utils/editor.ts frontend/tests/unit/editorUtils.spec.ts
git commit -m "feat(editor): StepType + STEP_TYPE_META + deriveStepType (P0 Task 3)"
```

---

## Task 4: store.setStepType + 详情面板下拉

**Files:** `frontend/src/store/nodeEditor.ts`, `frontend/src/components/editor/NodeDetailPanel.vue`, `frontend/tests/unit/NodeDetailPanel.spec.ts`

- [ ] **Step 1: store 方法** — [nodeEditor.ts](../../../frontend/src/store/nodeEditor.ts) 在 `setKind`（line 166）后加，对齐其 batchUpdate + undo 模式：
```ts
    async setStepType(id: string, stepType: import('@/types/node').StepType | null): Promise<void> {
      if (!this.procedureId) return
      const prev = this.nodeMap.get(id)?.step_type ?? null
      this.nodes = await api.batchUpdateNodes(this.procedureId, { [id]: { step_type: stepType } })
      this._pushUndo(() => this.setStepType(id, prev))
    },
```

- [ ] **Step 2: 面板下拉** — [NodeDetailPanel.vue](../../../frontend/src/components/editor/NodeDetailPanel.vue)：
  - script 加 import：`import { STEP_TYPES, STEP_TYPE_META, effectiveStepType } from '@/utils/editor'`；`import type { StepType } from '@/types/node'`。
  - computed：`const effStepType = computed(() => effectiveStepType(node.value?.step_type ?? null, schema.value.type))`。
  - handler：`function onStepType(v: StepType): void { if (node.value) void store.setStepType(node.value.id, v) }`。
  - template：在「执行表单」折叠区（line 149 `el-collapse-item ... name="form"`）**顶部、类型下拉之前**插入：
```html
          <el-form-item label="步骤类型">
            <el-select :model-value="effStepType" :disabled="props.readonly" @change="onStepType">
              <el-option v-for="t in STEP_TYPES" :key="t" :value="t" :label="STEP_TYPE_META[t].label" />
            </el-select>
            <span class="step-type-hint">语义标签：决定移动端执行行为（P1 起生效）；当前仅用于标注与呈现。</span>
          </el-form-item>
```
  - 加 scoped 样式：`.step-type-hint { font-size: 12px; color: #909399; margin-top: 4px; display: block; }`。

- [ ] **Step 3: 面板测试** — `NodeDetailPanel.spec.ts` 加：step 节点渲染「步骤类型」下拉，默认值 = `effectiveStepType`（如 input_schema.type=NUMBER 的旧节点显示 data）；选中触发 `store.setStepType`；正文/章节节点不渲染该下拉。

- [ ] **Step 4: Commit**
```bash
git add frontend/src/store/nodeEditor.ts frontend/src/components/editor/NodeDetailPanel.vue frontend/tests/unit/NodeDetailPanel.spec.ts
git commit -m "feat(editor): step_type select in NodeDetailPanel + store.setStepType (P0 Task 4)"
```

---

## Task 5: 树行 step_type 色条

**Files:** `frontend/src/components/editor/NodeTreeRow.vue`, `frontend/tests/unit/NodeTreeRow.spec.ts`

- [ ] **Step 1: 计算 + 渲染** — [NodeTreeRow.vue](../../../frontend/src/components/editor/NodeTreeRow.vue)：
  - script 加：`import { STEP_TYPE_META, effectiveStepType } from '@/utils/editor'`；
    ```ts
    const stepType = computed(() =>
      n.value.kind === 'step'
        ? effectiveStepType(n.value.step_type ?? null, (n.value.input_schema as { type?: import('@/types/node').FormType })?.type ?? 'COMMON')
        : null,
    )
    ```
  - 把现有「步骤」标签（line 91 `.ntr-kind`）替换为带类型的小色条 chip：
```html
    <span
      v-if="stepType"
      class="ntr-steptype"
      :class="`stc-${STEP_TYPE_META[stepType].color}`"
      :title="`步骤类型：${STEP_TYPE_META[stepType].label}`"
    >{{ STEP_TYPE_META[stepType].label }}</span>
```
  - 加 scoped 样式（5 色，复用 Element 调色感）：
```css
.ntr-steptype { flex: none; font-size: 11px; line-height: 1; padding: 1px 5px; border-radius: 3px; border: 1px solid transparent; }
.stc-gray   { color: #606266; background: #f4f4f5; border-color: #e0e0e3; }
.stc-purple { color: #6b4ea8; background: #f3effa; border-color: #ddd0ef; }
.stc-cyan   { color: #1c8b9e; background: #e8f7f9; border-color: #c2e8ee; }
.stc-blue   { color: #4d6bb5; background: #eef2fb; border-color: #c9d6f0; }
.stc-orange { color: #b8772f; background: #fdf2e6; border-color: #f3d8b4; }
```
  （移除旧 `.ntr-kind` 规则与那行模板；`levelLabel` 里的 `·步骤` 后缀保留或删除均可，建议保留供 chip 下拉语境。）

- [ ] **Step 2: 行测试** — `NodeTreeRow.spec.ts` 加：kind='step' 且 input_schema.type=NUMBER（无 step_type）→ 渲染「记录」chip 且含 `stc-purple`；kind='step' 且 step_type='hold' → 「暂停」+ `stc-orange`；非 step 节点不渲染 chip。

- [ ] **Step 3: 前端门禁** — `cd frontend && npm run typecheck`（vue-tsc 无错）；`npm test`（0 失败）；`npm run build`。

- [ ] **Step 4: Commit**
```bash
git add frontend/src/components/editor/NodeTreeRow.vue frontend/tests/unit/NodeTreeRow.spec.ts
git commit -m "feat(editor): step_type color chip in NodeTreeRow (P0 Task 5)"
```

---

## Orchestrator browser smoke (NOT a subagent task — after Task 5, before merge)

启动 worktree 开发服务（参考 `running-smartsop-dev`）：后端 8000 + 前端 5173。打开一份含步骤的程序：
1. 选一个旧的「记录型」步骤（input_schema.type=NUMBER）→ 详情面板「步骤类型」下拉**自动显示「记录」**（派生默认，未写库）；树行显示紫色「记录」chip。
2. 把它改成「暂停」→ 树行 chip 变橙「暂停」，刷新后保持（已写库）。
3. 新建步骤 → 步骤类型默认显示「执行」（COMMON 派生）。
4. 章节 / 正文节点：不出现「步骤类型」下拉、不出现色条。
5. PDF 预览、版本、解析导入等既有流程不受影响（step_type 仅叠加）。
6. 撤销（Ctrl+Z）能回退步骤类型变更。

---

## Self-Review

**Spec 覆盖（P0 行）：**
- step_type 7 类语义标签，与 15 型并存 → Task 1-4。✓
- 零迁移：旧数据 step_type=null，显示靠 `deriveStepType` 派生（§3.3 映射），不写库 → Task 3。✓
- 色条/标签建立视觉条件反射（§6.5.4）→ Task 5。✓
- step_config 仅建列、不做编写 UI（留 P1）→ Task 1/2。✓
- 解析推断 + NCW-PDF 明确移出 P0（解析器不产 step）→ Goal 范围收敛说明。✓

**非目标（不碰）：** enforce_node_invariants 约束、流程控制编写 UI、执行记录表、工单挂载、NCW 归位、采集下拉收窄——全部留待 P1+。

**类型一致性：** `StepType` 后端 `str|None` ↔ 前端联合；`deriveStepType(formType: FormType): StepType`、`effectiveStepType(StepType|null, FormType): StepType` 在 Task 3 定义，Task 4/5 使用；store `setStepType` 走 `batchUpdateNodes`（NodeBatchItem 已含 step_type）+ undo，与 `setKind` 同构。

**Placeholder scan:** 无——模型/迁移/schema/服务/纯函数/下拉/色条均给出完整代码；测试给出断言要点（按现有 spec 文件风格补具体用例）。

**风险：** ① MySQL JSON 列 ALTER 加列在大表上可能锁表——P0 表数据量小，可忽略；② `_node_dict` 若遗漏新键则前端读不到 step_config——Task 2 Step 2 已覆盖并由 Task 2 Step 3 集成测试兜底。
