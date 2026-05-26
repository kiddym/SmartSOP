# 标记模式：章节级联勾选 + step↔content 批量切换 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在编辑器「标记模式」中加入章节 checkbox 级联选/反选其下全部后代（章节 + content + step），并让 step / content 行能被批量「标记为步骤」/「标记为内容」就地翻转 kind。

**Architecture:** 纯前端改动，无后端 schema 变更。新增一个纯函数 `buildCascadeSelection` 与 `buildSelection` 并列；TreeRow 渲染逻辑放宽 + 加 `indeterminate` prop；ChapterTreePanel 计算后代映射与半选集合，重写 `onCheck` 与 `applyBatch` 分发。所有变更走 vitest TDD。

**Tech Stack:** Vue 3 + Pinia + Element Plus + vitest + @vue/test-utils。

**Spec:** `docs/superpowers/specs/2026-05-26-mark-mode-cascade-selection-design.md`

**Test commands (frontend root: `frontend/`):**

- 全跑：`npm test`
- 单文件：`npm test -- tests/unit/utils/batchMark.spec.ts`
- 单用例：`npm test -- -t "用例名片段"`
- 类型检查：`npm run typecheck`
- Lint：`npm run lint`

---

## File Inventory

| 文件 | 动作 | 职责 |
| --- | --- | --- |
| `frontend/src/utils/batchMark.ts` | Modify | 现有 `buildSelection` 放开 step；新增 `buildCascadeSelection` |
| `frontend/tests/unit/utils/batchMark.spec.ts` | Modify | 调整两个旧用例的"跳过 step"断言；加 cascade 与 shift-包含-step 用例 |
| `frontend/src/types/node.ts` | Modify | `FlatRow.mark_status` 注释微调（line 185） |
| `frontend/src/components/editor/TreeRow.vue` | Modify | checkbox 改为 `v-if="markMode"`；加 `indeterminate` prop |
| `frontend/tests/unit/TreeRow.spec.ts` | Modify | 加 markMode 下三 kind 均渲染 checkbox + indeterminate 透传 |
| `frontend/src/components/editor/ChapterTreePanel.vue` | Modify | 后代映射 + 半选集合 + 级联 dispatch + applyBatch 按 kind 分发 |
| `frontend/tests/unit/ChapterTreePanel.spec.ts` | Modify | 加级联 / 半选 / applyBatch 分发 三组用例 |

---

## Task 1：放开 `buildSelection` 对 step 的过滤（TDD）

**Files:**
- Modify: `frontend/src/utils/batchMark.ts:42`（删除一行）
- Modify: `frontend/tests/unit/utils/batchMark.spec.ts`

### Step 1.1：写一个会失败的新测试

打开 `frontend/tests/unit/utils/batchMark.spec.ts`，在文件末尾 `describe('buildSelection', ...)` 块内（即第 75 行 `})` 之前）追加：

```ts
  it('shift 区间：同父范围现在包含 step（B 方案）', () => {
    // a(idx 1) → s1(idx 3) 之间含 b(idx 2)。三者同父 c1，全部入选。
    const r = buildSelection({ current: new Set(['a']), anchor: 'a', rows, rowId: 's1', shift: true })
    expect([...r.selection].sort()).toEqual(['a', 'b', 's1'])
    expect(r.warnings).toEqual([])
  })
```

### Step 1.2：验证测试失败

Run：
```
npm test -- tests/unit/utils/batchMark.spec.ts -t "同父范围现在包含 step"
```
Expected: 1 failing —`expected ['a','b'] to deeply equal ['a','b','s1']`（当前实现仍跳过 step）。

### Step 1.3：修改实现，去掉 step 跳过

编辑 `frontend/src/utils/batchMark.ts`，删除第 42 行整行：

```ts
        if (r.kind === 'step') continue
```

修改后该 for 循环看起来是：

```ts
      for (let i = lo; i <= hi; i++) {
        const r = rows[i]
        if (r.parent_id !== anchorParent) {
          crossed = true
          continue
        }
        sel.add(r.id)
      }
```

### Step 1.4：更新两个旧用例（用例名 + 断言）

编辑 `frontend/tests/unit/utils/batchMark.spec.ts`：

**a)** 把 `it('shift 区间：选同父章节/正文，跳过步骤', ...)` 的标题改成 `it('shift 区间：选同父章节/正文/步骤', ...)`（仅改标题，断言原本就只 `['a','b']`，行为不变）。

**b)** 把 `it('shift 跨父：仅同父部分入选，跨父忽略并告警', ...)` 内的两处：
- 注释 `// d 跨父忽略、s1 步骤跳过` 改成 `// d 跨父忽略；s1 现在算同父入选（B 方案）`
- 断言 `expect([...r.selection].sort()).toEqual(['a', 'b'])` 改成 `expect([...r.selection].sort()).toEqual(['a', 'b', 's1'])`

### Step 1.5：跑完整 batchMark 文件

Run：
```
npm test -- tests/unit/utils/batchMark.spec.ts
```
Expected: 所有用例通过（含新加的 + 两个调整后的旧用例）。

### Step 1.6：Commit

```bash
git add frontend/src/utils/batchMark.ts frontend/tests/unit/utils/batchMark.spec.ts
git commit -m "feat(batchMark): shift 区间放开 step（B 方案 step↔content 批量切换准备）

- 删除 buildSelection 中对 step kind 的过滤
- 同父范围内现在包含 step
- 跨父规则不变；100 项上限不变

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2：新增 `buildCascadeSelection` 纯函数（TDD）

**Files:**
- Modify: `frontend/src/utils/batchMark.ts`（追加导出与函数）
- Modify: `frontend/tests/unit/utils/batchMark.spec.ts`（新 describe 块）

### Step 2.1：先写四个失败测试

在 `frontend/tests/unit/utils/batchMark.spec.ts` 文件末尾追加一个新 describe：

```ts
import { buildCascadeSelection } from '@/utils/batchMark'

describe('buildCascadeSelection', () => {
  it('select：空集合 + 章节级联 → rootId + 所有 descendantIds 入选；anchor=rootId', () => {
    const r = buildCascadeSelection({
      current: new Set(),
      anchor: null,
      rootId: 'c1',
      descendantIds: ['a', 'b', 's1'],
      action: 'select',
    })
    expect([...r.selection].sort()).toEqual(['a', 'b', 'c1', 's1'])
    expect(r.anchor).toBe('c1')
    expect(r.warnings).toEqual([])
  })

  it('deselect：含 root + descendants → 全部移除；anchor=rootId', () => {
    const r = buildCascadeSelection({
      current: new Set(['c1', 'a', 'b', 's1', 'other']),
      anchor: 'c1',
      rootId: 'c1',
      descendantIds: ['a', 'b', 's1'],
      action: 'deselect',
    })
    expect([...r.selection].sort()).toEqual(['other'])
    expect(r.anchor).toBe('c1')
  })

  it('select 部分命中：未在集合的后代被补齐', () => {
    const r = buildCascadeSelection({
      current: new Set(['a']),
      anchor: 'a',
      rootId: 'c1',
      descendantIds: ['a', 'b', 's1'],
      action: 'select',
    })
    expect([...r.selection].sort()).toEqual(['a', 'b', 'c1', 's1'])
  })

  it('超 100：截断到前 100 并告警；锚点若不在裁后集合则置 null', () => {
    const descendantIds = Array.from({ length: 150 }, (_, i) => `d${i}`)
    const r = buildCascadeSelection({
      current: new Set(),
      anchor: null,
      rootId: 'root',
      descendantIds,
      action: 'select',
    })
    expect(r.selection.size).toBe(MAX_BATCH_MARK)
    expect(r.warnings.some((w) => w.includes('最多标记'))).toBe(true)
    // 截断按"集合插入顺序"：rootId 先插，descendantIds 依序插。前 100 必含 root。
    expect(r.selection.has('root')).toBe(true)
    expect(r.anchor).toBe('root')
  })
})
```

### Step 2.2：验证四个测试都失败

Run：
```
npm test -- tests/unit/utils/batchMark.spec.ts -t "buildCascadeSelection"
```
Expected: 4 failing —导入会先报 `"buildCascadeSelection" is not exported`。

### Step 2.3：实现 `buildCascadeSelection`

编辑 `frontend/src/utils/batchMark.ts`，在文件末尾追加（保留现有 `buildSelection` 与 `MAX_BATCH_MARK`）：

```ts
/** 章节级联选择参数。
 * - rootId：被点击的章节 id（自身也会被加入/移除）。
 * - descendantIds：rootId 的全部后代 id（含 chapter / content / step；DFS 顺序由调用方决定）。
 * - action：select 加入；deselect 移除。半选/未选/全选的判定在调用方，这里只执行结果。
 * - 100 项上限沿用 buildSelection 的策略：按 Set 插入顺序保留前 100，告警；锚点若被截则 null。
 */
export interface CascadeParams {
  current: ReadonlySet<string>
  anchor: string | null
  rootId: string
  descendantIds: readonly string[]
  action: 'select' | 'deselect'
}

export function buildCascadeSelection(p: CascadeParams): SelectionUpdate {
  const { current, rootId, descendantIds, action } = p
  const sel = new Set(current)
  const warnings: string[] = []

  if (action === 'select') {
    sel.add(rootId)
    for (const id of descendantIds) sel.add(id)
  } else {
    sel.delete(rootId)
    for (const id of descendantIds) sel.delete(id)
  }

  let nextAnchor: string | null = rootId
  if (sel.size > MAX_BATCH_MARK) {
    const trimmed = new Set([...sel].slice(0, MAX_BATCH_MARK))
    if (!trimmed.has(nextAnchor)) nextAnchor = null
    warnings.push(`单次最多标记 ${MAX_BATCH_MARK} 项，已保留前 ${MAX_BATCH_MARK} 项`)
    return { selection: trimmed, anchor: nextAnchor, warnings }
  }
  return { selection: sel, anchor: nextAnchor, warnings }
}
```

### Step 2.4：跑完整 batchMark 测试

Run：
```
npm test -- tests/unit/utils/batchMark.spec.ts
```
Expected: 全部通过（含 Task 1 与 Task 2 新增）。

### Step 2.5：Commit

```bash
git add frontend/src/utils/batchMark.ts frontend/tests/unit/utils/batchMark.spec.ts
git commit -m "feat(batchMark): 新增 buildCascadeSelection（章节级联选/反选）

- 纯函数，调用方传 rootId + descendantIds + action
- 100 项上限沿用 buildSelection：按插入序截断 + 告警
- 锚点恒移到 rootId；被截断时置 null

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3：微调 `FlatRow.mark_status` 注释

**Files:**
- Modify: `frontend/src/types/node.ts:185`

### Step 3.1：改一行注释

编辑 `frontend/src/types/node.ts`，line 185：

把
```ts
  mark_status: MarkStatus // step 恒 'unmarked'（不参与标记模式）
```
改成
```ts
  mark_status: MarkStatus // step 上恒 'unmarked'（后端无此列）；step 行本身可参与标记模式
```

### Step 3.2：typecheck

Run：
```
cd frontend && npm run typecheck
```
Expected: 0 errors。

### Step 3.3：Commit

```bash
git add frontend/src/types/node.ts
git commit -m "docs(types): 更新 FlatRow.mark_status 注释（step 现在参与标记模式）

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4：TreeRow 放开 checkbox + 加 `indeterminate` prop（TDD）

**Files:**
- Modify: `frontend/src/components/editor/TreeRow.vue`
- Modify: `frontend/tests/unit/TreeRow.spec.ts`

### Step 4.1：先写两个失败测试

编辑 `frontend/tests/unit/TreeRow.spec.ts`，在 `describe('TreeRow', () => {` 块内末尾（即第 109 行 `})` 之前）追加：

```ts
  it('markMode 下三种 kind 都渲染 checkbox', () => {
    for (const kind of ['chapter', 'content', 'step'] as const) {
      const w = mountRow(row({ id: kind, kind, code: '1.1' }), { markMode: true })
      expect(w.findComponent({ name: 'ElCheckbox' }).exists()).toBe(true)
    }
  })

  it('markMode chapter checkbox 透传 indeterminate prop', () => {
    const w = mountRow(row({ id: 'c1', kind: 'chapter' }), { markMode: true, indeterminate: true })
    const cb = w.findComponent({ name: 'ElCheckbox' })
    expect(cb.props('indeterminate')).toBe(true)
  })
```

### Step 4.2：验证测试失败

Run：
```
npm test -- tests/unit/TreeRow.spec.ts -t "markMode"
```
Expected: 
- 第一个失败：content / step 不渲染 checkbox。
- 第二个失败：`indeterminate` 不是 props 的一部分，或被默认 false 覆盖。

### Step 4.3：改 TreeRow 接口与模板

编辑 `frontend/src/components/editor/TreeRow.vue`：

**a)** 在 `interface Props {...}` 末尾加一行（紧跟 `dropHint`，line 16）：

```ts
  indeterminate?: boolean
```

最终 Props 形如：
```ts
interface Props {
  row: FlatRow
  selected: boolean
  markMode: boolean
  selectedForMark: boolean
  addState: AddButtonState
  editable: boolean
  canMoveUp: boolean
  canMoveDown: boolean
  dropHint: '' | 'before' | 'after' | 'inside' | 'invalid'
  indeterminate?: boolean
}
```

**b)** 把 template 中 line 81-86 的 `el-checkbox` 块改成：

```html
    <el-checkbox
      v-if="markMode"
      :model-value="selectedForMark"
      :indeterminate="row.kind === 'chapter' ? !!indeterminate : false"
      class="tr-check"
      @click.stop="emit('check', ($event as MouseEvent).shiftKey)"
    />
```

要点：
- `v-if` 由 `markMode && row.kind === 'chapter'` 改为 `markMode`。
- 叶子行强制 `indeterminate=false`，避免误传。

### Step 4.4：跑 TreeRow 全部测试

Run：
```
npm test -- tests/unit/TreeRow.spec.ts
```
Expected: 全部通过（含两个新加 + 原有 9 个）。

### Step 4.5：Commit

```bash
git add frontend/src/components/editor/TreeRow.vue frontend/tests/unit/TreeRow.spec.ts
git commit -m "feat(editor): TreeRow markMode 下三种 kind 都渲染 checkbox + 加 indeterminate prop

- v-if 从 chapter-only 放开到所有 kind
- 新增可选 indeterminate prop；叶子行强制为 false
- 仅放渲染；级联接线在 ChapterTreePanel

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5：ChapterTreePanel 计算后代映射 + 半选集合，传 `indeterminate`（TDD）

**Files:**
- Modify: `frontend/src/components/editor/ChapterTreePanel.vue`
- Modify: `frontend/tests/unit/ChapterTreePanel.spec.ts`

### Step 5.1：先写一个失败测试

编辑 `frontend/tests/unit/ChapterTreePanel.spec.ts`，在第二个 `describe(...)` 块（line 178 起）之后追加新 describe：

```ts
describe('ChapterTreePanel · 标记模式级联', () => {
  it('部分子节点入选时，章节 checkbox 为 indeterminate', async () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '章一', null, 0)]
    store.steps = [
      { id: 's1', chapter_id: 'c1', kind: 'step', title: '步一', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 0 },
      { id: 's2', chapter_id: 'c1', kind: 'step', title: '步二', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 1 },
      { id: 's3', chapter_id: 'c1', kind: 'step', title: '步三', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 2 },
    ]
    store.expanded = { c1: true }
    store.markMode = true

    const w = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    const rows = w.findAllComponents({ name: 'TreeRow' })
    const stepRow = rows.find((r) => r.props('row').id === 's1')!

    // 勾选 1/3 子节点
    stepRow.vm.$emit('check', false)
    await w.vm.$nextTick()

    const chapterRow = rows.find((r) => r.props('row').id === 'c1')!
    expect(chapterRow.props('indeterminate')).toBe(true)
  })
})
```

### Step 5.2：验证失败

Run：
```
npm test -- tests/unit/ChapterTreePanel.spec.ts -t "indeterminate"
```
Expected: `indeterminate` 是 undefined 或 false（panel 尚未传该 prop）。

### Step 5.3：在 ChapterTreePanel.vue 加后代映射 + 半选集合 + 传 prop

编辑 `frontend/src/components/editor/ChapterTreePanel.vue`：

**a)** 在 `<script setup>` 块顶部 `import` 一行处补 `buildCascadeSelection`（line 10）：

```ts
import { buildSelection, buildCascadeSelection } from '@/utils/batchMark'
```

**b)** 在 `// ---- 标记模式批量选择 ---- //`（line 220）之前，插入后代映射与半选集合两个 computed：

```ts
// ---- 标记模式：后代映射（DFS 全子树，忽略折叠/过滤） ---- //
// 每个 chapter id → 其全部后代 id（含 chapter / content / step）。
// rebuild 触发：chapters / steps 形状变。
const descendantsByChapter = computed<Map<string, string[]>>(() => {
  const childChapters = new Map<string | null, string[]>()
  for (const c of store.chapters) {
    const g = childChapters.get(c.parent_id) ?? []
    g.push(c.id)
    childChapters.set(c.parent_id, g)
  }
  const childSteps = new Map<string | null, string[]>()
  for (const s of store.steps) {
    const g = childSteps.get(s.chapter_id) ?? []
    g.push(s.id)
    childSteps.set(s.chapter_id, g)
  }
  const out = new Map<string, string[]>()
  const dfs = (id: string): string[] => {
    const acc: string[] = []
    for (const cid of childChapters.get(id) ?? []) {
      acc.push(cid, ...dfs(cid))
    }
    for (const sid of childSteps.get(id) ?? []) {
      acc.push(sid)
    }
    return acc
  }
  for (const c of store.chapters) out.set(c.id, dfs(c.id))
  return out
})

// 半选集合：descendant 命中数 ∈ (0, total) 的 chapter id。chapter 自身是否在 selection 不影响半选判定。
const indeterminateSet = computed<Set<string>>(() => {
  const out = new Set<string>()
  for (const [chId, desc] of descendantsByChapter.value) {
    if (desc.length === 0) continue
    let hit = 0
    for (const id of desc) if (markSel.value.has(id)) hit++
    if (hit > 0 && hit < desc.length) out.add(chId)
  }
  return out
})
```

**c)** 在 template 的 `<TreeRow ...>`（line 353-376）的 props 列表中，紧跟 `:selected-for-mark="markSel.has(row.id)"`（line 359）之后加一行：

```html
          :indeterminate="indeterminateSet.has(row.id)"
```

### Step 5.4：跑 panel 测试

Run：
```
npm test -- tests/unit/ChapterTreePanel.spec.ts
```
Expected: 全部通过（含新加 indeterminate 用例）。

### Step 5.5：typecheck + lint

Run：
```
cd frontend && npm run typecheck && npm run lint
```
Expected: 0 errors / 0 warnings。

### Step 5.6：Commit

```bash
git add frontend/src/components/editor/ChapterTreePanel.vue frontend/tests/unit/ChapterTreePanel.spec.ts
git commit -m "feat(editor): ChapterTreePanel 加后代映射 + 半选集合，传 indeterminate 到 TreeRow

- descendantsByChapter：DFS 全子树（chapter + content + step），忽略折叠/过滤
- indeterminateSet：部分命中（命中 ∈ (0, total)）的 chapter id
- TreeRow 接 :indeterminate 后，半选时章节 checkbox 渲染半选态

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6：ChapterTreePanel `onCheck` 分发——章节非 shift 走级联（TDD）

**Files:**
- Modify: `frontend/src/components/editor/ChapterTreePanel.vue`
- Modify: `frontend/tests/unit/ChapterTreePanel.spec.ts`

### Step 6.1：写三个失败测试

在 `describe('ChapterTreePanel · 标记模式级联', ...)` 块内追加：

```ts
  it('章节 checkbox 未选 → 点击级联选 root + 全部后代', async () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '章一', null, 0), chapter('c1a', '子章', 'c1', 0)]
    store.steps = [
      { id: 's1', chapter_id: 'c1', kind: 'step', title: '步一', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 0 },
    ]
    store.expanded = { c1: true, c1a: true }
    store.markMode = true

    const w = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    const rows = w.findAllComponents({ name: 'TreeRow' })
    const chapterRow = rows.find((r) => r.props('row').id === 'c1')!

    chapterRow.vm.$emit('check', false)
    await w.vm.$nextTick()
    // root c1 + 子章 c1a + 步 s1 全入选
    expect(chapterRow.props('selectedForMark')).toBe(true)
    const subRow = rows.find((r) => r.props('row').id === 'c1a')!
    const stepRow = rows.find((r) => r.props('row').id === 's1')!
    expect(subRow.props('selectedForMark')).toBe(true)
    expect(stepRow.props('selectedForMark')).toBe(true)
  })

  it('章节 checkbox 已全选 → 点击级联取消 root + 全部后代', async () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '章一', null, 0)]
    store.steps = [
      { id: 's1', chapter_id: 'c1', kind: 'step', title: '步一', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 0 },
    ]
    store.expanded = { c1: true }
    store.markMode = true

    const w = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    const rows = w.findAllComponents({ name: 'TreeRow' })
    const chapterRow = rows.find((r) => r.props('row').id === 'c1')!

    // 先级联选中
    chapterRow.vm.$emit('check', false)
    await w.vm.$nextTick()
    // 再点击 → 全部取消
    chapterRow.vm.$emit('check', false)
    await w.vm.$nextTick()

    expect(chapterRow.props('selectedForMark')).toBe(false)
    const stepRow = rows.find((r) => r.props('row').id === 's1')!
    expect(stepRow.props('selectedForMark')).toBe(false)
  })

  it('章节 indeterminate → 点击 = 级联选所有剩余', async () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '章一', null, 0)]
    store.steps = [
      { id: 's1', chapter_id: 'c1', kind: 'step', title: '一', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 0 },
      { id: 's2', chapter_id: 'c1', kind: 'step', title: '二', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 1 },
      { id: 's3', chapter_id: 'c1', kind: 'step', title: '三', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 2 },
    ]
    store.expanded = { c1: true }
    store.markMode = true

    const w = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    const rows = w.findAllComponents({ name: 'TreeRow' })
    const s1 = rows.find((r) => r.props('row').id === 's1')!
    s1.vm.$emit('check', false)
    await w.vm.$nextTick()
    const chapterRow = rows.find((r) => r.props('row').id === 'c1')!
    expect(chapterRow.props('indeterminate')).toBe(true)

    // 点 indeterminate 章节 → 选所有剩余
    chapterRow.vm.$emit('check', false)
    await w.vm.$nextTick()
    expect(chapterRow.props('selectedForMark')).toBe(true)
    expect(chapterRow.props('indeterminate')).toBe(false)
    for (const sid of ['s1', 's2', 's3']) {
      expect(rows.find((r) => r.props('row').id === sid)!.props('selectedForMark')).toBe(true)
    }
  })
```

### Step 6.2：验证失败

Run：
```
npm test -- tests/unit/ChapterTreePanel.spec.ts -t "标记模式级联"
```
Expected: 三个新用例失败（当前 onCheck 走 buildSelection 单选切换，不级联）。

### Step 6.3：改 `onCheck` 加级联分发

编辑 `frontend/src/components/editor/ChapterTreePanel.vue`，把 line 232-243 的 `onCheck` 函数整体替换为：

```ts
function onCheck(row: FlatRow, shift: boolean): void {
  // 章节 + 非 shift：级联。action 由当前状态判定——checked → deselect；其它（unchecked / indeterminate）→ select。
  if (row.kind === 'chapter' && !shift) {
    const desc = descendantsByChapter.value.get(row.id) ?? []
    const isChecked = markSel.value.has(row.id) && !indeterminateSet.value.has(row.id)
    const action: 'select' | 'deselect' = isChecked ? 'deselect' : 'select'
    const res = buildCascadeSelection({
      current: markSel.value,
      anchor: lastChecked.value,
      rootId: row.id,
      descendantIds: desc,
      action,
    })
    markSel.value = res.selection
    lastChecked.value = res.anchor
    for (const w of res.warnings) ElMessage.warning(w)
    return
  }
  // 其它情况（叶子 / shift）：走原 buildSelection
  const res = buildSelection({
    current: markSel.value,
    anchor: lastChecked.value,
    rows: visibleRows.value,
    rowId: row.id,
    shift,
  })
  markSel.value = res.selection
  lastChecked.value = res.anchor
  for (const w of res.warnings) ElMessage.warning(w)
}
```

### Step 6.4：跑 panel 全部测试

Run：
```
npm test -- tests/unit/ChapterTreePanel.spec.ts
```
Expected: 全部通过。

### Step 6.5：typecheck + lint

Run：
```
cd frontend && npm run typecheck && npm run lint
```
Expected: 0 errors / 0 warnings。

### Step 6.6：Commit

```bash
git add frontend/src/components/editor/ChapterTreePanel.vue frontend/tests/unit/ChapterTreePanel.spec.ts
git commit -m "feat(editor): 章节 checkbox 级联选/反选所有后代

- 章节 + 非 shift 走 buildCascadeSelection
- 当前态 checked → deselect；unchecked / indeterminate → select
- 叶子行 + shift 走原 buildSelection 路径
- 100 项上限告警沿用

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7：`applyBatch` 按 kind 分发（chapter→setMark / step↔content→setStepKind）（TDD）

**Files:**
- Modify: `frontend/src/components/editor/ChapterTreePanel.vue`
- Modify: `frontend/tests/unit/ChapterTreePanel.spec.ts`

### Step 7.1：写两个失败测试

在 `describe('ChapterTreePanel · 标记模式级联', ...)` 块内追加：

```ts
  it('applyBatch(content) 混合选择：chapter→setMark / step→setStepKind / content 跳过', async () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '章一', null, 0), chapter('c2', '章二', null, 1)]
    store.steps = [
      { id: 's1', chapter_id: 'c1', kind: 'step', title: '步', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 0 },
      { id: 'ct1', chapter_id: 'c2', kind: 'content', title: '', content: '', input_schema: {} as never, attachment_marks: [], skip_numbering: false, sort_order: 0 },
    ]
    store.expanded = { c1: true, c2: true }
    store.markMode = true
    vi.spyOn(store, 'ensureSaved').mockResolvedValue({})
    const setMarkSpy = vi.spyOn(store, 'setMark').mockResolvedValue()
    const setStepKindSpy = vi.spyOn(store, 'setStepKind')

    const w = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    const rows = w.findAllComponents({ name: 'TreeRow' })
    // 手动构造混合选择（避免依赖 cascade 的展开/折叠细节）
    rows.find((r) => r.props('row').id === 'c1')!.vm.$emit('check', false)  // c1 cascade → c1+s1
    rows.find((r) => r.props('row').id === 'ct1')!.vm.$emit('check', false) // ct1 单选
    await w.vm.$nextTick()

    // 触发"标记为内容"
    const markBar = w.find('.mark-bar')
    const contentBtn = markBar.findAll('button').find((b) => b.text().includes('标记为内容'))!
    await contentBtn.trigger('click')
    await w.vm.$nextTick()
    await new Promise((r) => setTimeout(r, 0)) // 让 await ensureSaved 的 microtask 结算

    // c1 → setMark(c1, 'content')；ct1（已是 content）跳过；s1 → setStepKind(s1, 'content')
    expect(setMarkSpy).toHaveBeenCalledWith('c1', 'content')
    expect(setStepKindSpy).toHaveBeenCalledWith('s1', 'content')
    expect(setStepKindSpy).not.toHaveBeenCalledWith('ct1', expect.anything())
  })

  it('applyBatch(step) 对已是 step 的行跳过', async () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '章一', null, 0)]
    store.steps = [
      { id: 's1', chapter_id: 'c1', kind: 'step', title: '步', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 0 },
    ]
    store.expanded = { c1: true }
    store.markMode = true
    vi.spyOn(store, 'ensureSaved').mockResolvedValue({})
    const setStepKindSpy = vi.spyOn(store, 'setStepKind')

    const w = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    const rows = w.findAllComponents({ name: 'TreeRow' })
    rows.find((r) => r.props('row').id === 's1')!.vm.$emit('check', false)
    await w.vm.$nextTick()

    const markBar = w.find('.mark-bar')
    const stepBtn = markBar.findAll('button').find((b) => b.text().includes('标记为步骤'))!
    await stepBtn.trigger('click')
    await w.vm.$nextTick()
    await new Promise((r) => setTimeout(r, 0))

    expect(setStepKindSpy).not.toHaveBeenCalled()
  })
```

### Step 7.2：验证失败

Run：
```
npm test -- tests/unit/ChapterTreePanel.spec.ts -t "applyBatch"
```
Expected: 失败。当前 `applyBatch` 把所有 ids 都丢给 `setMark`，但 step/content 不在 `chapterMap` 中，所以 `setMark` 直接 return 一个 `undefined` —— `setStepKindSpy` 永远不会被调到。

### Step 7.3：重写 `applyBatch`

编辑 `frontend/src/components/editor/ChapterTreePanel.vue`，把 line 244-251 的 `applyBatch` 函数整体替换为：

```ts
async function applyBatch(status: 'step' | 'content'): Promise<void> {
  const ids = [...markSel.value]
  // 先保存待存改动并拿到 temp→real id 映射；再按行 kind 分发。
  const map = await store.ensureSaved()
  let inplace = 0
  for (const id of ids) {
    const real = map[id] ?? id
    const ch = store.chapterMap.get(real)
    if (ch) {
      await store.setMark(real, status)
      continue
    }
    const st = store.stepMap.get(real)
    if (st && st.kind !== status) {
      store.setStepKind(real, status)
      inplace++
    }
    // 已是目标 kind 的 step/content：跳过
  }
  ElMessage.success(`已标记 ${ids.length} 项${inplace ? `（${inplace} 项就地转换）` : ''}`)
  markSel.value = new Set()
}
```

### Step 7.4：跑 panel 全部测试

Run：
```
npm test -- tests/unit/ChapterTreePanel.spec.ts
```
Expected: 全部通过。

### Step 7.5：跑全套前端测试

Run：
```
cd frontend && npm test
```
Expected: 全部通过（含所有现有 spec 无回归）。

### Step 7.6：typecheck + lint

Run：
```
cd frontend && npm run typecheck && npm run lint
```
Expected: 0 errors / 0 warnings。

### Step 7.7：Commit

```bash
git add frontend/src/components/editor/ChapterTreePanel.vue frontend/tests/unit/ChapterTreePanel.spec.ts
git commit -m "feat(editor): applyBatch 按 kind 分发；step↔content 就地翻转

- chapter → setMark（沿用现状，apply-marks 时落库）
- step / content + 目标 kind 不同 → setStepKind 立即翻转
- 同目标 kind 的 step/content：跳过
- toast 文案显示 N 项 + 就地转换计数

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8：手工冒烟验证（无 commit）

**目的**：在跑过的单元测试之外，手验一遍交互（用 superpowers:verification-before-completion 提到的"evidence before assertions"）。

### Step 8.1：启动开发环境

Run：
```
cd frontend && npm run dev
```

在浏览器打开编辑器视图，加载一份至少含：
- 1 个章节包含 ≥ 2 个子章节
- 至少 1 个子章节含 ≥ 2 个 step

### Step 8.2：交互核对清单（逐条勾选）

- [ ] 进入"标记模式"。chapter / content / step 三种行都出现 checkbox。
- [ ] 点击章节 checkbox → 该章节 + 所有后代（chapter / content / step）全选中。
- [ ] 再次点击同一章节 checkbox → 全部取消。
- [ ] 单选一个 step → 该 step 父章节 checkbox 显示半选（indeterminate 灰色横线）。
- [ ] 点击半选章节 → 全选 root + 剩余后代。
- [ ] 选 1 chapter + 1 step + 1 content，点"标记为内容"。toast 显示 `已标记 3 项（1 项就地转换）`（或类似计数）。
- [ ] step 行图标即时变成 content 图标（📄）。
- [ ] 选 1 个已经是 step 的行，点"标记为步骤" → toast `已标记 1 项`（无"就地转换"）。
- [ ] 退出标记模式 → 选择集合清空。
- [ ] 选 > 100 项的章节级联 → 出现告警 `单次最多标记 100 项，已保留前 100 项`。

### Step 8.3：未通过任意一条则停下

如果有任何一条不符合预期：
- 不要 commit。
- 把现象（截图或文字）与对应任务编号反馈，回到上一个 task 排查。

---

## Self-Review

### 1. Spec coverage

| Spec 章节 | 任务覆盖 |
| --- | --- |
| §2.1 Checkbox 渲染（v-if 放开） | Task 4 |
| §2.2 章节级联点击规则（unchecked / indeterminate / checked） | Task 6（三条用例直接对应） |
| §2.3 叶子行只切换自身 | Task 6（onCheck 非 chapter 走 buildSelection） |
| §2.4 Shift-range 包含 step | Task 1 |
| §2.5 级联范围 = 全子树忽略 filter/collapse | Task 5（descendantsByChapter 从 store 派生而非 visibleRows） |
| §2.6 100 项上限 | Task 2（cascade）+ Task 1（shift，已存在） |
| §2.7 退出模式清空 | 现有 watch（Task 0 不需要） |
| §3.1 应用按钮按 kind 分发 + toast | Task 7 |
| §3.2 step↔content 立即翻转（B1） | Task 7 |
| §3.3 应用标记 / 清除标记 行为不变 | 现有，无任务 |
| §4.1 batchMark.ts 改动 | Task 1, 2 |
| §4.2 TreeRow.vue 改动 | Task 4 |
| §4.3 ChapterTreePanel.vue 改动 | Task 5, 6, 7 |
| §4.4 store 无新方法 | 默认满足（无任务） |
| §4.5 node.ts 注释 | Task 3 |
| §5 测试 | Task 1, 2, 4, 5, 6, 7 各有 TDD step |

无缺失。

### 2. Placeholder scan

- 无 TBD / TODO / "implement later"。
- 所有 code step 都给了完整代码块。
- 测试用例文本是可直接粘贴的。
- 命令均给了 expected output 关键词。

### 3. Type consistency

- `CascadeParams` / `SelectionUpdate` / `MAX_BATCH_MARK` 命名前后一致（Task 2）。
- `buildCascadeSelection` 在 batchMark.ts 中定义、在 ChapterTreePanel.vue 中按同名导入（Task 6.3）。
- `indeterminate?: boolean` prop 在 TreeRow.vue 与 ChapterTreePanel.vue 的传参两侧匹配（Task 4, 5）。
- `descendantsByChapter` / `indeterminateSet` 命名在 Task 5 定义、Task 6 引用，一致。
- `applyBatch(status: 'step' | 'content')` 签名不变（Task 7 仅改函数体），调用方 template 处不动。

无矛盾。
