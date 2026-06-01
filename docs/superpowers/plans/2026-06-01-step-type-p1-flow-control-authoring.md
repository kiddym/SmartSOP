# P1 — 流程控制建模（编写侧） Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让作者能为 4 个流程控制类型编写其专属参数（写入 P0 已建的 `step_config` 列），并按 step_type 收窄/替换采集表单：
- **decision** 判断：分支选项 + 每项跳转目标（本程序内节点）。
- **wait** 等待：定时（时长）或条件（文本）。
- **hold** 暂停：门控开关 + 批准角色 + 是否需签字。
- **link** 跳转：目标节点 + 返回原位（本程序内；跨程序留 P3 工单上下文）。
- **data** 记录：把 15 型采集下拉**收窄**到数据控件；**information** 隐藏采集表单。

这是移动端执行（P2/P3）真正吃到收益的前提——把流程语义"写得出来"。**纯编写侧**，不含执行运行时。

**Architecture:** 新增 `StepConfigFields.vue`（按 step_type 渲染配置，类比现有 `StepFormFields.vue`），跳转/分支目标从 `store.nodes` 选取。`NodeDetailPanel` 按 `effectiveStepType` 决定显示采集表单（收窄）还是 `StepConfigFields`。校验用纯函数 `validateStepConfig`，在组件内空态提示 + 发布清单汇总。`store.setStepConfig` 经 `patchNode` 持久化（文本字段防抖）。

**前置依赖：** P0（`step_type`/`step_config` 列 + `effectiveStepType` + 下拉）已合并。建议 P0b 也已合并（推断让默认类型更准）。Spec：`docs/superpowers/specs/2026-06-01-step-type-mobile-execution-design.md`（P1 行 / §3.4 / §4.2-4.3）。

**Tech Stack:** Vue 3 + Element Plus + Pinia + vitest/jsdom + vue-tsc。无新依赖、无后端改动（`step_config` 不透明 JSON，P0 已放行）。

---

## File Structure

- **Modify** `frontend/src/types/node.ts` — `StepConfig` / `DecisionBranch` 接口。
- **Modify** `frontend/src/utils/editor.ts` — `validateStepConfig` + `nodeLabel` + `captureFormsFor`（按 step_type 过滤 15 型）。
- **Create** `frontend/src/components/editor/StepConfigFields.vue` — 按 step_type 的配置编辑器。
- **Modify** `frontend/src/store/nodeEditor.ts` — `setStepConfig`。
- **Modify** `frontend/src/components/editor/NodeDetailPanel.vue` — 按 step_type 切换采集表单/配置编辑器 + 收窄采集下拉。
- **Modify** `frontend/src/components/editor/PublishChecklistDialog.vue` — 汇总 `validateStepConfig` 告警。
- **Tests:** `editorUtils.spec.ts`、`StepConfigFields.spec.ts`(新)、`NodeDetailPanel.spec.ts`。

---

## Task 1: 类型 + 纯函数（TDD）

**Files:** `frontend/src/types/node.ts`, `frontend/src/utils/editor.ts`, `frontend/tests/unit/editorUtils.spec.ts`

- [ ] **Step 1: 类型** — [types/node.ts](../../../frontend/src/types/node.ts) 加：
```ts
export interface DecisionBranch { option: string; target_node_id: string | null }
export interface StepConfig {
  branches?: DecisionBranch[]                     // decision
  wait_mode?: 'timer' | 'condition'               // wait
  duration_sec?: number
  condition_text?: string
  gated?: boolean                                 // hold
  approver_role?: string
  require_signature?: boolean
  target_node_id?: string | null                  // link（本程序内）
  return_to_origin?: boolean
}
```
（`Node.step_config` 在 P0 已是 `Record<string, unknown>`；本期视图层按 `StepConfig` 收窄读取，无需改 P0 字段类型。）

- [ ] **Step 2: 先写失败测试** — append `editorUtils.spec.ts`：
```ts
import { validateStepConfig, captureFormsFor, nodeLabel } from '@/utils/editor'

describe('validateStepConfig (返回问题列表，空=通过)', () => {
  it('data 未选采集控件 → 报', () => {
    expect(validateStepConfig('data', {}, 'COMMON').length).toBeGreaterThan(0)
    expect(validateStepConfig('data', {}, 'NUMBER')).toEqual([])
  })
  it('decision 无分支 / 分支缺目标 → 报', () => {
    expect(validateStepConfig('decision', {}, 'COMMON').length).toBeGreaterThan(0)
    expect(validateStepConfig('decision', { branches: [{ option: 'A', target_node_id: null }] }, 'COMMON').length).toBeGreaterThan(0)
    expect(validateStepConfig('decision', { branches: [{ option: 'A', target_node_id: 'n1' }] }, 'COMMON')).toEqual([])
  })
  it('wait timer 缺时长 / condition 缺条件 → 报', () => {
    expect(validateStepConfig('wait', { wait_mode: 'timer' }, 'COMMON').length).toBeGreaterThan(0)
    expect(validateStepConfig('wait', { wait_mode: 'timer', duration_sec: 60 }, 'COMMON')).toEqual([])
    expect(validateStepConfig('wait', { wait_mode: 'condition' }, 'COMMON').length).toBeGreaterThan(0)
  })
  it('hold 门控缺批准角色 → 报', () => {
    expect(validateStepConfig('hold', { gated: true }, 'COMMON').length).toBeGreaterThan(0)
    expect(validateStepConfig('hold', { gated: true, approver_role: '值长' }, 'COMMON')).toEqual([])
  })
  it('link 缺目标 → 报', () => {
    expect(validateStepConfig('link', {}, 'COMMON').length).toBeGreaterThan(0)
    expect(validateStepConfig('link', { target_node_id: 'n2' }, 'COMMON')).toEqual([])
  })
  it('action/information 永远通过', () => {
    expect(validateStepConfig('action', {}, 'COMMON')).toEqual([])
    expect(validateStepConfig('information', {}, 'COMMON')).toEqual([])
  })
})

describe('captureFormsFor', () => {
  it('data → 仅数据控件', () => {
    expect(captureFormsFor('data')).toEqual(['NUMBER','METER','CHECKBOX','RADIO','DATE','UPLOAD','PHOTO'])
  })
  it('action → 完成确认子集', () => {
    expect(captureFormsFor('action')).toEqual(['COMMON','CHECK','YESNO','NONE'])
  })
})

describe('nodeLabel', () => {
  it('code + 去标签正文首段', () => {
    expect(nodeLabel({ code: '1.2', body: '<p>关闭阀门</p>' } as never)).toContain('关闭阀门')
  })
})
```
Run `cd frontend && npm test -- tests/unit/editorUtils.spec.ts` → FAIL。

- [ ] **Step 3: 实现** — append [utils/editor.ts](../../../frontend/src/utils/editor.ts)：
```ts
import type { Node, StepConfig, StepType } from '@/types/node'

const _DATA_CAPTURE: readonly FormType[] = ['NUMBER','METER','CHECKBOX','RADIO','DATE','UPLOAD','PHOTO']
const _ACTION_CAPTURE: readonly FormType[] = ['COMMON','CHECK','YESNO','NONE']
/** 某 step_type 下采集下拉允许的 15 型子集（§4.3 收窄）。非采集型返回 []（不显示采集表单）。 */
export function captureFormsFor(stepType: StepType): FormType[] {
  if (stepType === 'data') return [..._DATA_CAPTURE]
  if (stepType === 'action') return [..._ACTION_CAPTURE]
  return []
}

/** 节点选择器显示标签：code + 去标签正文首段（截断）。 */
export function nodeLabel(node: Pick<Node, 'code' | 'body'>): string {
  const text = (node.body ?? '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 30)
  return `${node.code ?? ''} ${text}`.trim() || '（无标题）'
}

/** step_config 完整性校验，返回问题文案列表（空=通过）。captureType=当前 input_schema.type。 */
export function validateStepConfig(stepType: StepType, cfg: StepConfig, captureType: FormType): string[] {
  const issues: string[] = []
  if (stepType === 'data' && (captureType === 'COMMON' || captureType === 'NONE')) {
    issues.push('记录步骤需选择一个采集控件')
  }
  if (stepType === 'decision') {
    const b = cfg.branches ?? []
    if (b.length === 0) issues.push('判断步骤至少需要一个分支')
    else if (b.some((x) => !x.target_node_id)) issues.push('存在未指定跳转目标的分支')
  }
  if (stepType === 'wait') {
    if (cfg.wait_mode === 'timer' && !cfg.duration_sec) issues.push('定时等待需填写时长')
    if (cfg.wait_mode === 'condition' && !cfg.condition_text?.trim()) issues.push('条件等待需填写条件')
  }
  if (stepType === 'hold' && cfg.gated && !cfg.approver_role?.trim()) {
    issues.push('门控暂停需指定批准角色')
  }
  if (stepType === 'link' && !cfg.target_node_id) issues.push('跳转步骤需指定目标')
  return issues
}
```
Run 同上 → PASS。

- [ ] **Step 4: Commit**
```bash
git add frontend/src/types/node.ts frontend/src/utils/editor.ts frontend/tests/unit/editorUtils.spec.ts
git commit -m "feat(editor): StepConfig types + validateStepConfig + captureFormsFor (P1 Task 1)"
```

---

## Task 2: `StepConfigFields.vue` 配置编辑器（TDD）

**Files:** `frontend/src/components/editor/StepConfigFields.vue`(新), `frontend/tests/unit/StepConfigFields.spec.ts`(新)

**Props/Emits：** `props: { stepType: StepType; config: StepConfig; nodes: {id,label}[]; readonly?: boolean }`；`emit('update:config', next)`。纯展示+派发，无 store 依赖（便于单测），持久化由父组件防抖。

- [ ] **Step 1: 先写失败测试** — `StepConfigFields.spec.ts`（`mount` + ElementPlus 插件，参考 `StepFormFields` 测试约定）：
  - `stepType='decision'`：渲染分支列表；点「+分支」emit 的 config.branches 长度 +1；每行有选项输入 + 目标 select（options = nodes）。
  - `stepType='wait'`：mode 切换显示时长 / 条件控件。
  - `stepType='hold'`：门控开关 + 批准角色输入 + 需签字开关。
  - `stepType='link'`：目标 select + 返回原位开关。
  - `stepType='action'|'information'`：渲染空（无配置）。
  Run `cd frontend && npm test -- tests/unit/StepConfigFields.spec.ts` → FAIL。

- [ ] **Step 2: 实现组件** — 结构按 step_type v-if 分支（沿用 `StepFormFields` 的 `set(key,value)=>emit('update:config',{...config,[key]:value})` 模式）：
```vue
<script setup lang="ts">
import { computed } from 'vue'
import type { StepType, StepConfig, DecisionBranch } from '@/types/node'
const props = defineProps<{ stepType: StepType; config: StepConfig; nodes: { id: string; label: string }[]; readonly?: boolean }>()
const emit = defineEmits<{ (e: 'update:config', v: StepConfig): void }>()
function set<K extends keyof StepConfig>(k: K, v: StepConfig[K]): void { emit('update:config', { ...props.config, [k]: v }) }
const branches = computed<DecisionBranch[]>(() => props.config.branches ?? [])
function setBranch(i: number, patch: Partial<DecisionBranch>): void {
  set('branches', branches.value.map((b, idx) => (idx === i ? { ...b, ...patch } : b)))
}
function addBranch(): void { set('branches', [...branches.value, { option: '', target_node_id: null }]) }
function removeBranch(i: number): void { set('branches', branches.value.filter((_, idx) => idx !== i)) }
</script>

<template>
  <div class="step-config">
    <!-- decision -->
    <template v-if="stepType === 'decision'">
      <div v-for="(b, i) in branches" :key="i" class="branch-row">
        <el-input :model-value="b.option" placeholder="选项（如：是/否、合格/不合格）" :disabled="readonly" @input="(v: string) => setBranch(i, { option: v })" />
        <el-select :model-value="b.target_node_id" placeholder="跳转到…" :disabled="readonly" @change="(v: string) => setBranch(i, { target_node_id: v })">
          <el-option v-for="n in nodes" :key="n.id" :value="n.id" :label="n.label" />
        </el-select>
        <el-button v-if="!readonly" size="small" text @click="removeBranch(i)">✕</el-button>
      </div>
      <el-button v-if="!readonly" size="small" @click="addBranch">+ 添加分支</el-button>
    </template>

    <!-- wait -->
    <template v-else-if="stepType === 'wait'">
      <el-radio-group :model-value="config.wait_mode ?? 'timer'" :disabled="readonly" @change="(v: string) => set('wait_mode', v as 'timer' | 'condition')">
        <el-radio value="timer">定时</el-radio>
        <el-radio value="condition">条件</el-radio>
      </el-radio-group>
      <el-input-number v-if="(config.wait_mode ?? 'timer') === 'timer'" :model-value="config.duration_sec" :min="1" :disabled="readonly" placeholder="时长(秒)" @change="(v: number) => set('duration_sec', v)" />
      <el-input v-else type="textarea" :model-value="config.condition_text" :disabled="readonly" placeholder="等待条件描述" @input="(v: string) => set('condition_text', v)" />
    </template>

    <!-- hold -->
    <template v-else-if="stepType === 'hold'">
      <el-switch :model-value="config.gated ?? false" :disabled="readonly" @change="(v: boolean) => set('gated', !!v)" /> <span>门控（批准前禁止继续）</span>
      <el-input :model-value="config.approver_role" placeholder="批准角色（如：值长）" :disabled="readonly" @input="(v: string) => set('approver_role', v)" />
      <el-switch :model-value="config.require_signature ?? false" :disabled="readonly" @change="(v: boolean) => set('require_signature', !!v)" /> <span>需电子签字</span>
    </template>

    <!-- link -->
    <template v-else-if="stepType === 'link'">
      <el-select :model-value="config.target_node_id" placeholder="跳转目标节点" :disabled="readonly" @change="(v: string) => set('target_node_id', v)">
        <el-option v-for="n in nodes" :key="n.id" :value="n.id" :label="n.label" />
      </el-select>
      <el-switch :model-value="config.return_to_origin ?? true" :disabled="readonly" @change="(v: boolean) => set('return_to_origin', !!v)" /> <span>看完返回原位</span>
    </template>
  </div>
</template>
```
（action / information 无分支 → 渲染空 `.step-config`。CSS：`.branch-row { display:flex; gap:6px; align-items:center; margin-bottom:6px }`。）
Run 同上 → PASS。

- [ ] **Step 3: Commit**
```bash
git add frontend/src/components/editor/StepConfigFields.vue frontend/tests/unit/StepConfigFields.spec.ts
git commit -m "feat(editor): StepConfigFields per step_type config editor (P1 Task 2)"
```

---

## Task 3: store.setStepConfig + 面板集成 + 采集下拉收窄

**Files:** `frontend/src/store/nodeEditor.ts`, `frontend/src/components/editor/NodeDetailPanel.vue`, `frontend/tests/unit/NodeDetailPanel.spec.ts`

- [ ] **Step 1: store 方法** — [nodeEditor.ts](../../../frontend/src/store/nodeEditor.ts) 仿 `updateForm`（line 295）加（`patchNode` 单字段 + 替换节点 + undo）：
```ts
    async setStepConfig(id: string, config: import('@/types/node').StepConfig): Promise<void> {
      const node = this.nodeMap.get(id)
      if (!node) return
      const prev = (node.step_config ?? {}) as import('@/types/node').StepConfig
      const updated = await api.patchNode(id, { step_config: config }, node.revision)
      this.nodes = this.nodes.map((n) => (n.id === id ? updated : n))
      this._pushUndo(() => this.setStepConfig(id, prev))
    },
```

- [ ] **Step 2: 面板集成** — [NodeDetailPanel.vue](../../../frontend/src/components/editor/NodeDetailPanel.vue)：
  - import：`StepConfigFields`、`{ captureFormsFor, nodeLabel }`、`type { StepConfig }`。
  - computed：
    ```ts
    const captureOptions = computed(() => captureFormsFor(effStepType.value)) // effStepType 来自 P0
    const showCapture = computed(() => captureOptions.value.length > 0)        // data/action
    const showStepConfig = computed(() => ['decision','wait','hold','link'].includes(effStepType.value))
    const stepConfig = computed<StepConfig>(() => (node.value?.step_config ?? {}) as StepConfig)
    const pickerNodes = computed(() => store.nodes
      .filter((n) => n.id !== node.value?.id)
      .map((n) => ({ id: n.id, label: nodeLabel(n) })))
    ```
  - handler（文本字段防抖持久化）：
    ```ts
    const pushConfig = useDebounceFn((c: StepConfig) => { if (node.value) void store.setStepConfig(node.value.id, c) }, 500)
    function onConfig(c: StepConfig): void { pushConfig(c) }
    ```
  - 模板「执行表单」折叠区（line 149-166）改造：
    - 「类型」下拉的 `v-for="t in FORM_TYPES"` 改为 `v-for="t in captureOptions"`，并整段包 `v-if="showCapture"`（information 时整个采集块隐藏）。
    - 现有 `config-preview`（StepFormFields + FormFieldPreview）也包在 `v-if="showCapture"` 内。
    - 新增：`<StepConfigFields v-if="showStepConfig" :step-type="effStepType" :config="stepConfig" :nodes="pickerNodes" :readonly="props.readonly" @update:config="onConfig" />`。
  - 切换 step_type 时若新类型不再用采集表单（如 data→decision），保留 input_schema 不动（无副作用）；若 data 的采集型不在 `captureOptions`（历史脏数据）则下拉显示空，作者重选——不自动改写。

- [ ] **Step 3: 面板测试** — `NodeDetailPanel.spec.ts` 加：
  - effStepType='data' → 采集下拉只含 7 个数据控件；显示 StepFormFields。
  - effStepType='decision' → 不显示采集下拉；显示 StepConfigFields（含分支）。
  - effStepType='information' → 采集块与 StepConfigFields 都不显示。
  - StepConfigFields emit update:config → 防抖后调用 `store.setStepConfig`（可用 fake timers 断言）。

- [ ] **Step 4: 前端门禁** — `npm run typecheck` / `npm test` / `npm run build`。

- [ ] **Step 5: Commit**
```bash
git add frontend/src/store/nodeEditor.ts frontend/src/components/editor/NodeDetailPanel.vue frontend/tests/unit/NodeDetailPanel.spec.ts
git commit -m "feat(editor): wire StepConfigFields + narrow capture dropdown by step_type (P1 Task 3)"
```

---

## Task 4: 发布清单汇总 step_config 校验

**Files:** `frontend/src/components/editor/PublishChecklistDialog.vue`, 对应单测

- [ ] **Step 1: 汇总告警** — 读 `PublishChecklistDialog.vue` 现有校验项结构，对每个 `kind==='step'` 节点调用 `validateStepConfig(effectiveStepType(...), node.step_config, node.input_schema.type)`，把非空问题汇总为一条「流程配置不完整」清单项（列出节点 code + 问题），与现有项同级展示。**非阻断**（warning 级，对齐既有清单交互）。

- [ ] **Step 2: 测试** — 给 dialog 测试加：含一个无分支的 decision 步骤时，清单出现该告警并列出其 code；全部完整时不出现。

- [ ] **Step 3: 门禁 + Commit**
```bash
git add frontend/src/components/editor/PublishChecklistDialog.vue frontend/tests
git commit -m "feat(editor): surface step_config completeness in publish checklist (P1 Task 4)"
```

---

## Orchestrator browser smoke (after Task 4, before merge)

1. 步骤设为 **判断** → 出现分支编辑；加两个分支并各选一个跳转目标节点；刷新后保持。
2. 步骤设为 **等待** → 选定时填 30 秒 / 选条件填文本，切换正确。
3. 步骤设为 **暂停** → 开门控、填批准角色「值长」、开需签字。
4. 步骤设为 **跳转** → 选目标节点、开返回原位。
5. 步骤设为 **记录** → 采集下拉只剩 7 个数据控件（无 WARNING/COMMON）；**信息** → 采集与配置区都消失，仅富文本。
6. 打开发布清单：留一个无分支的判断步骤 → 清单提示「流程配置不完整」并指出该步 code；补全后告警消失。
7. 既有编辑/PDF/版本流程无回归；Ctrl+Z 能回退配置变更。

---

## Self-Review

**Spec 覆盖（P1 行 / §3.4 / §4.2-4.3）：** decision 分支+目标、wait 定时/条件、hold 门控/角色/签字、link 目标/返回 → Task 2 ✓；data 采集下拉收窄、information 隐藏 → Task 3 ✓；分支非空等完整性校验 → Task 1 + Task 4 ✓。
**非目标（留后期）：** 跨程序 link（target_procedure_id，需工单上下文，P3）；执行运行时行为（门控拦截/倒计时/自动跳转，P2）；后端硬约束 enforce_node_invariants（本期校验走前端发布清单，非阻断，避免破坏编辑中途保存）；NCW 归位（P4）。
**类型一致性：** `StepConfig`/`DecisionBranch`（Task1）贯穿组件 props、store `setStepConfig`、`validateStepConfig`；`captureFormsFor(StepType):FormType[]`、`nodeLabel(Pick<Node,...>):string`、`validateStepConfig(StepType,StepConfig,FormType):string[]` 在 Task1 定义、后续任务引用；`effectiveStepType`/`STEP_TYPES` 复用 P0。
**Placeholder scan:** 组件/纯函数/store 方法给出完整代码；面板集成与发布清单按现有文件结构描述接入点（实施时读对应文件就近插入）。
**风险：** ① `store.nodes` 可能很大 → 目标 select 用 Element `filterable` 即可，无需虚拟化（本期规模可控）；② 防抖持久化与乐观锁 `revision`：`setStepConfig` 每次读 `nodeMap` 最新 revision，连续编辑由防抖合并为最后一次写，降低 409 概率；若仍 409，复用既有 E4 冲突恢复路径。
