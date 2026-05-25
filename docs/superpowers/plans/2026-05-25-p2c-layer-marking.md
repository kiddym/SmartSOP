# P2c · 批量层级标定（4 选项）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在编辑器加一个批量「层级标定」视图（一级/二级/三级/正文）：扁平文档序清单逐行选角色，应用时本地原地重排（保 id、置脏、可撤销、随正常保存，服务端重算 level）。步骤维持现有 mark-mode 不动。

**Architecture:** 纯逻辑 `layerMark.ts`（角色→`{parent_id,content_type,sort_order}` 走位，沿用 import 的 l1/l2/l3 算法）；store 加 `layerMode` + `toggleLayerMode`（与 markMode 互斥）+ `layerRows` getter + `applyLayerRoles`；新组件 `EditorLayerMarking.vue` 渲染扁平 `ImportMarkingRow` 清单 + 应用/取消；`ChapterTreePanel` 加入口切换 + 条件渲染；`ImportMarkingRow` 加 `disableContent` prop。纯前端。

**Tech Stack:** Vue 3 `<script setup>` + TS + Pinia + Vitest + Element Plus。

**Gate（cwd=`frontend/`）：** `npm run lint && npm run typecheck && npm run test && npm run build`

**上位文档：** `docs/superpowers/specs/2026-05-25-p2c-layer-marking-design.md`

---

## 关键事实（实现者必读）

- 角色算法已在 `frontend/src/utils/importTree.ts`（`buildTreeFromRoles`/`computeMarkIndents`/`defaultRoleOf`，l1/l2/l3 走位）。它输出**嵌套 WizardNode**；本计划另写**扁平 EditorChapter 更新**版 `layerMark.ts`（复用算法思路，不复用该函数）。
- `ImportMarkingRow.vue`（import-v2）：props `{ label: string; role: LayerRole; indent: number }`，emit `set(role)`，4 个 `el-radio-button`（一级/二级/三级/正文）。本计划加可选 `disableContent` 禁用"正文"。
- 批量保存只发 `parent_id`/`content_type`/`sort_order`（`ChapterUpsert`），**level 服务端重算**；不能跨表（章节↔步骤）。本地改 `EditorChapter` 字段 + `dirtyChapters.add(id)` 即随 `save()` 持久化。
- store（`frontend/src/store/procedureEditor.ts`）：`state` 有 `markMode: boolean`（加 `layerMode`）；getters 有 `chapterMap`、`levelMap`；actions 有 `pushUndo(tag?)`、`toggleMarkMode`（~725：`this.markMode = !this.markMode`）；`updateChapterFields` 用 `this.dirtyChapters.add(id)`。
- store 测试 `procedureEditorStore.spec.ts`：`seed()` 建 `chapters=[chap('a'),chap('b')]`；`chap(id,parent,sort)` 默认 `content_type:'chapter'`、`mark_status:'unmarked'`；`stp(id,chapterId,sort)` 建步骤；mock `@/api/*`。
- `ChapterTreePanel.vue`：toolbar `.tree-toolbar`；树渲染在 `.tree-scroll`（虚拟列表）。`@/utils/editor` 导出 `computeFallback(kind, html)`（content 摘要回退）。
- 提交结尾必带（harness 规定的合法署名，勿当伪造）：`Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`

---

## File Structure

- 新建 `frontend/src/utils/layerMark.ts` + `frontend/tests/unit/utils/layerMark.spec.ts`。
- 改 `frontend/src/store/procedureEditor.ts`（`layerMode`/`toggleLayerMode`/`layerRows`/`applyLayerRoles` + `toggleMarkMode` 互斥）+ `frontend/tests/unit/procedureEditorStore.spec.ts`。
- 改 `frontend/src/components/import-v2/ImportMarkingRow.vue`（`disableContent` prop）+ `frontend/tests/unit/ImportMarkingRow.spec.ts`。
- 新建 `frontend/src/components/editor/EditorLayerMarking.vue` + `frontend/tests/unit/EditorLayerMarking.spec.ts`。
- 改 `frontend/src/components/editor/ChapterTreePanel.vue`（入口切换 + 条件渲染）。

---

## Task 1: 纯逻辑 `layerMark.ts`

**Files:** Create `frontend/src/utils/layerMark.ts`, `frontend/tests/unit/utils/layerMark.spec.ts`

- [ ] **Step 1: 写失败测试**

新建 `frontend/tests/unit/utils/layerMark.spec.ts`：
```ts
import { describe, it, expect } from 'vitest'
import {
  computeLayerIndents,
  computeLayerUpdates,
  defaultLayerRole,
  type LayerRole,
  type LayerRow,
} from '@/utils/layerMark'

function row(id: string, content_type: 'chapter' | 'content', level: number, hasStepChildren = false): LayerRow {
  return { id, content_type, level, hasStepChildren }
}

describe('layerMark', () => {
  it('defaultLayerRole：content→content；章节按 level 夹 1..3', () => {
    expect(defaultLayerRole('content', 2)).toBe('content')
    expect(defaultLayerRole('chapter', 1)).toBe('chapter_1')
    expect(defaultLayerRole('chapter', 5)).toBe('chapter_3')
  })

  it('computeLayerUpdates：一级/二级/三级嵌套 + 正文挂最近章节', () => {
    const rows = [row('a', 'chapter', 1), row('b', 'chapter', 1), row('c', 'content', 1)]
    const m = new Map<string, LayerRole>([
      ['a', 'chapter_1'], ['b', 'chapter_2'], ['c', 'content'],
    ])
    const u = computeLayerUpdates(rows, m)
    expect(u.get('a')).toEqual({ parent_id: null, content_type: 'chapter', sort_order: 0 })
    expect(u.get('b')).toEqual({ parent_id: 'a', content_type: 'chapter', sort_order: 0 })
    expect(u.get('c')).toEqual({ parent_id: 'b', content_type: 'content', sort_order: 0 })
  })

  it('不可达层级夹紧：二级无一级父→根', () => {
    const rows = [row('a', 'chapter', 1)]
    const u = computeLayerUpdates(rows, new Map([['a', 'chapter_2']]))
    expect(u.get('a')?.parent_id).toBeNull()
  })

  it('含步骤子节点的行标 content 仍保持章节', () => {
    const rows = [row('a', 'chapter', 1, true)]
    const u = computeLayerUpdates(rows, new Map([['a', 'content']]))
    expect(u.get('a')?.content_type).toBe('chapter')
  })

  it('computeLayerIndents：章节 = level-1，正文 = 当前标题层级', () => {
    const rows = [row('a', 'chapter', 1), row('b', 'content', 2)]
    const m = new Map<string, LayerRole>([['a', 'chapter_1'], ['b', 'content']])
    const ind = computeLayerIndents(rows, m)
    expect(ind.get('a')).toBe(0)
    expect(ind.get('b')).toBe(1)
  })
})
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `cd frontend && npx vitest run tests/unit/utils/layerMark.spec.ts`
Expected: FAIL（模块缺失）。

- [ ] **Step 3: 实现 `layerMark.ts`**

新建 `frontend/src/utils/layerMark.ts`：
```ts
export type LayerRole = 'chapter_1' | 'chapter_2' | 'chapter_3' | 'content'

/** 文档序里参与层级标定的章节/正文行（步骤不参与）。 */
export interface LayerRow {
  id: string
  content_type: 'chapter' | 'content'
  level: number // 当前层级（预填默认角色用）
  hasStepChildren: boolean // 含步骤子节点 → 不可降为正文
}

/** 应用层级后单个节点的目标归属。 */
export interface LayerUpdate {
  parent_id: string | null
  content_type: 'chapter' | 'content'
  sort_order: number
}

/** 当前角色：content→content；章节按 level 夹到 chapter_1/2/3。 */
export function defaultLayerRole(contentType: 'chapter' | 'content', level: number): LayerRole {
  if (contentType === 'content') return 'content'
  const lv = Math.min(3, Math.max(1, level))
  return `chapter_${lv}` as LayerRole
}

function roleLevel(role: LayerRole): number {
  return role === 'chapter_3' ? 3 : role === 'chapter_2' ? 2 : 1
}

// 含步骤子节点的行即便被标 content 也保持章节（content 不能有步骤子，Q25）。
function effectiveRole(row: LayerRow, roleMap: Map<string, LayerRole>): LayerRole {
  const role = roleMap.get(row.id) ?? defaultLayerRole(row.content_type, row.level)
  if (role === 'content' && row.hasStepChildren) return defaultLayerRole('chapter', row.level)
  return role
}

/**
 * 由文档序行 + roleMap 算每个章节/正文节点的目标 {parent_id, content_type, sort_order}。
 * l1/l2/l3 走位：chapter_2 无一级父→根；chapter_3 无二级父→挂一级/根；正文挂最近章节、作叶子。
 */
export function computeLayerUpdates(
  rows: LayerRow[],
  roleMap: Map<string, LayerRole>,
): Map<string, LayerUpdate> {
  const out = new Map<string, LayerUpdate>()
  let l1: string | null = null
  let l2: string | null = null
  let l3: string | null = null
  const sortCounter = new Map<string | null, number>()
  const nextSort = (p: string | null): number => {
    const n = sortCounter.get(p) ?? 0
    sortCounter.set(p, n + 1)
    return n
  }
  for (const row of rows) {
    const role = effectiveRole(row, roleMap)
    if (role === 'content') {
      const parent = l3 ?? l2 ?? l1
      out.set(row.id, { parent_id: parent, content_type: 'content', sort_order: nextSort(parent) })
      continue
    }
    const level = roleLevel(role)
    let parent: string | null
    if (level >= 3 && l2) {
      parent = l2
      l3 = row.id
    } else if (level >= 2 && l1) {
      parent = l1
      l2 = row.id
      l3 = null
    } else {
      parent = null
      l1 = row.id
      l2 = null
      l3 = null
    }
    out.set(row.id, { parent_id: parent, content_type: 'chapter', sort_order: nextSort(parent) })
  }
  return out
}

/** 「所见即所选」缩进：章节 = level-1；正文 = 当前标题层级。 */
export function computeLayerIndents(
  rows: LayerRow[],
  roleMap: Map<string, LayerRole>,
): Map<string, number> {
  const map = new Map<string, number>()
  let headingLevel = 0
  for (const row of rows) {
    const role = effectiveRole(row, roleMap)
    if (role === 'content') {
      map.set(row.id, headingLevel)
    } else {
      const lv = roleLevel(role)
      map.set(row.id, lv - 1)
      headingLevel = lv
    }
  }
  return map
}
```

- [ ] **Step 4: 跑测试 + lint/type**

Run: `cd frontend && npx vitest run tests/unit/utils/layerMark.spec.ts && npm run lint && npm run typecheck`
Expected: 测试 PASS；lint/type clean。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/utils/layerMark.ts frontend/tests/unit/utils/layerMark.spec.ts
git commit -m "$(cat <<'EOF'
feat(p2c): layerMark util (role -> parent/type/sort + indents)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: store——`layerMode` + `layerRows` + `applyLayerRoles`

**Files:** Modify `frontend/src/store/procedureEditor.ts`, `frontend/tests/unit/procedureEditorStore.spec.ts`

- [ ] **Step 1: 写失败测试（追加 describe）**

```ts
describe('层级标定 (P2c)', () => {
  it('toggleLayerMode 与 markMode 互斥', () => {
    const s = seed()
    s.toggleMarkMode()
    expect(s.markMode).toBe(true)
    s.toggleLayerMode()
    expect(s.layerMode).toBe(true)
    expect(s.markMode).toBe(false)
  })

  it('layerRows：文档序含章节/正文、标 hasStepChildren', () => {
    const s = seed()
    s.chapters = [chap('a', null, 0), { ...chap('b', 'a', 0), content_type: 'content' }]
    s.steps = [stp('s1', 'a', 0)]
    const rows = s.layerRows
    expect(rows.map((r) => r.id)).toEqual(['a', 'b'])
    expect(rows.find((r) => r.id === 'a')?.hasStepChildren).toBe(true)
    expect(rows.find((r) => r.id === 'b')?.content_type).toBe('content')
  })

  it('applyLayerRoles 把 b 提为一级章节并置脏、退出模式', () => {
    const s = seed()
    s.chapters = [chap('a', null, 0), chap('b', 'a', 0)]
    s.layerMode = true
    s.applyLayerRoles(new Map([['a', 'chapter_1'], ['b', 'chapter_1']]))
    expect(s.chapterMap.get('b')?.parent_id).toBeNull()
    expect(s.dirtyChapters.has('b')).toBe(true)
    expect(s.layerMode).toBe(false)
  })
})
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts -t 层级标定`
Expected: FAIL（`layerMode`/`toggleLayerMode`/`layerRows`/`applyLayerRoles` 未定义）。

- [ ] **Step 3: 实现**

`frontend/src/store/procedureEditor.ts`：

1. import 区加：`import { computeLayerUpdates, type LayerRole, type LayerRow } from '@/utils/layerMark'`
2. `State` 接口加：`layerMode: boolean`
3. `state()` 加：`layerMode: false,`
4. getters 区加（用 `this` 访问其它 getter/state）：
```ts
    layerRows(): LayerRow[] {
      const levels = this.levelMap
      const hasStep = new Set(this.steps.map((s) => s.chapter_id))
      const byParent = new Map<string | null, EditorChapter[]>()
      for (const c of this.chapters) {
        const g = byParent.get(c.parent_id) ?? []
        g.push(c)
        byParent.set(c.parent_id, g)
      }
      const cmp = (a: EditorChapter, b: EditorChapter): number =>
        a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1
      const rows: LayerRow[] = []
      const walk = (parent: string | null): void => {
        for (const c of [...(byParent.get(parent) ?? [])].sort(cmp)) {
          rows.push({
            id: c.id,
            content_type: c.content_type,
            level: levels.get(c.id) ?? 1,
            hasStepChildren: hasStep.has(c.id),
          })
          walk(c.id)
        }
      }
      walk(null)
      return rows
    },
```
5. actions 区：把 `toggleMarkMode` 改为互斥，并加 layer 动作：
```ts
    toggleMarkMode(): void {
      this.markMode = !this.markMode
      if (this.markMode) this.layerMode = false
    },
    toggleLayerMode(): void {
      this.layerMode = !this.layerMode
      if (this.layerMode) this.markMode = false
    },
    applyLayerRoles(roleMap: Map<string, LayerRole>): void {
      const updates = computeLayerUpdates(this.layerRows, roleMap)
      this.pushUndo('layer')
      for (const [id, u] of updates) {
        const ch = this.chapterMap.get(id)
        if (!ch) continue
        ch.parent_id = u.parent_id
        ch.content_type = u.content_type
        ch.sort_order = u.sort_order
        this.dirtyChapters.add(id)
      }
      this.layerMode = false
    },
```
（`EditorChapter` 类型已在文件内 import。）

- [ ] **Step 4: 跑测试 + lint/type**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts && npm run lint && npm run typecheck`
Expected: 全绿（含 3 新测试，既有不回归）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/store/procedureEditor.ts frontend/tests/unit/procedureEditorStore.spec.ts
git commit -m "$(cat <<'EOF'
feat(p2c): store layerMode + layerRows + applyLayerRoles (in-place re-nest)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `ImportMarkingRow` 加 `disableContent`

**Files:** Modify `frontend/src/components/import-v2/ImportMarkingRow.vue`, `frontend/tests/unit/ImportMarkingRow.spec.ts`

- [ ] **Step 1: 写失败测试（追加）**

在 `frontend/tests/unit/ImportMarkingRow.spec.ts` 追加（沿用其既有 import/mount 模式；该 spec 已有为 `el-radio` 注册 ElementPlus 的范式，照搬其挂载方式）：
```ts
describe('ImportMarkingRow disableContent', () => {
  it('disableContent=true 时「正文」单选被禁用', () => {
    const w = mount(ImportMarkingRow, {
      props: { label: 'X', role: 'chapter_1', indent: 0, disableContent: true },
      global: { plugins: [ElementPlus] },
    })
    const contentInput = w.find('input[value="content"]')
    expect(contentInput.attributes('disabled')).toBeDefined()
  })
  it('默认不禁用', () => {
    const w = mount(ImportMarkingRow, {
      props: { label: 'X', role: 'chapter_1', indent: 0 },
      global: { plugins: [ElementPlus] },
    })
    expect(w.find('input[value="content"]').attributes('disabled')).toBeUndefined()
  })
})
```
（若该 spec 顶部尚未 `import ElementPlus from 'element-plus'`，加上；其它既有用例不动。）

- [ ] **Step 2: 跑测试，确认失败**

Run: `cd frontend && npx vitest run tests/unit/ImportMarkingRow.spec.ts -t disableContent`
Expected: FAIL（content 未禁用）。

- [ ] **Step 3: 实现**

`frontend/src/components/import-v2/ImportMarkingRow.vue`：
1. `defineProps` 加可选 `disableContent?: boolean`：
```ts
defineProps<{
  label: string
  role: LayerRole
  indent: number
  disableContent?: boolean
}>()
```
2. 4 个 `el-radio-button` 的循环里，给 content 项加 `:disabled`：
```html
      <el-radio-button v-for="o in OPTIONS" :key="o.value" :value="o.value" :disabled="o.value === 'content' && disableContent">{{ o.text }}</el-radio-button>
```

- [ ] **Step 4: 跑测试 + lint/type**

Run: `cd frontend && npx vitest run tests/unit/ImportMarkingRow.spec.ts && npm run lint && npm run typecheck`
Expected: 全绿（既有 import-v2 用例不回归——`disableContent` 可选，默认行为不变）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/import-v2/ImportMarkingRow.vue frontend/tests/unit/ImportMarkingRow.spec.ts
git commit -m "$(cat <<'EOF'
feat(p2c): ImportMarkingRow optional disableContent prop

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `EditorLayerMarking.vue` + 接入树面板

**Files:** Create `frontend/src/components/editor/EditorLayerMarking.vue`, `frontend/tests/unit/EditorLayerMarking.spec.ts`; Modify `frontend/src/components/editor/ChapterTreePanel.vue`

- [ ] **Step 1: 写失败测试**

新建 `frontend/tests/unit/EditorLayerMarking.spec.ts`：
```ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/http', () => ({ http: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }))

import EditorLayerMarking from '@/components/editor/EditorLayerMarking.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'

const stubs = {
  ImportMarkingRow: {
    props: ['label', 'role', 'indent', 'disableContent'],
    emits: ['set'],
    template: '<div class="stub-mr" :data-role="role" :data-label="label" />',
  },
}

function setup() {
  const store = useProcedureEditorStore()
  store.chapters = [
    { id: 'a', parent_id: null, content_type: 'chapter', title: '甲', rich_content: '', skip_numbering: false, mark_status: 'unmarked', sort_order: 0 },
    { id: 'b', parent_id: 'a', content_type: 'chapter', title: '乙', rich_content: '', skip_numbering: false, mark_status: 'unmarked', sort_order: 0 },
  ]
  store.steps = []
  store.layerMode = true
  return mount(EditorLayerMarking, { global: { stubs } })
}

describe('EditorLayerMarking', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('渲染文档序的层级行并预填角色', () => {
    const w = setup()
    const rows = w.findAll('.stub-mr')
    expect(rows.map((r) => r.attributes('data-label'))).toEqual(['甲', '乙'])
    expect(rows[0].attributes('data-role')).toBe('chapter_1')
    expect(rows[1].attributes('data-role')).toBe('chapter_2')
  })

  it('点「应用层级」调 store.applyLayerRoles', async () => {
    const w = setup()
    const store = useProcedureEditorStore()
    const spy = vi.spyOn(store, 'applyLayerRoles').mockImplementation(() => {})
    const btn = w.findAll('button').find((b) => b.text().includes('应用'))
    await btn!.trigger('click')
    expect(spy).toHaveBeenCalledOnce()
  })
})
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `cd frontend && npx vitest run tests/unit/EditorLayerMarking.spec.ts`
Expected: FAIL（组件缺失）。

- [ ] **Step 3: 实现 `EditorLayerMarking.vue`**

新建 `frontend/src/components/editor/EditorLayerMarking.vue`：
```vue
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ImportMarkingRow from '@/components/import-v2/ImportMarkingRow.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import { computeLayerIndents, defaultLayerRole, type LayerRole } from '@/utils/layerMark'
import { computeFallback } from '@/utils/editor'

const store = useProcedureEditorStore()
const roleMap = ref<Map<string, LayerRole>>(new Map())

function seed(): void {
  const m = new Map<string, LayerRole>()
  for (const r of store.layerRows) m.set(r.id, defaultLayerRole(r.content_type, r.level))
  roleMap.value = m
}
watch(() => store.layerMode, (on) => { if (on) seed() }, { immediate: true })

const indents = computed(() => computeLayerIndents(store.layerRows, roleMap.value))

interface RenderRow { id: string; label: string; role: LayerRole; indent: number; disableContent: boolean }
const rows = computed<RenderRow[]>(() =>
  store.layerRows.map((r) => {
    const ch = store.chapterMap.get(r.id)
    const label =
      r.content_type === 'content'
        ? computeFallback('content', ch?.rich_content ?? '')
        : ch?.title.trim() || '（无标题）'
    return {
      id: r.id,
      label,
      role: roleMap.value.get(r.id) ?? defaultLayerRole(r.content_type, r.level),
      indent: indents.value.get(r.id) ?? 0,
      disableContent: r.hasStepChildren,
    }
  }),
)

function onSet(id: string, role: LayerRole): void {
  roleMap.value = new Map(roleMap.value).set(id, role)
}
function apply(): void {
  store.applyLayerRoles(roleMap.value)
}
function cancel(): void {
  store.toggleLayerMode()
}
</script>

<template>
  <div class="layer-marking">
    <div class="lm-bar">
      <span class="lm-hint">逐行设定层级，应用后原地重排</span>
      <span class="lm-spacer" />
      <el-button size="small" @click="cancel">取消</el-button>
      <el-button size="small" type="primary" @click="apply">应用层级</el-button>
    </div>
    <div class="lm-list">
      <ImportMarkingRow
        v-for="r in rows"
        :key="r.id"
        :label="r.label"
        :role="r.role"
        :indent="r.indent"
        :disable-content="r.disableContent"
        @set="(role: LayerRole) => onSet(r.id, role)"
      />
      <el-empty v-if="!rows.length" description="暂无可标定的章节/内容" :image-size="48" />
    </div>
  </div>
</template>

<style scoped>
.layer-marking { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.lm-bar {
  display: flex; align-items: center; gap: 8px; padding: 8px;
  border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
}
.lm-hint { font-size: 12px; color: #909399; }
.lm-spacer { flex: 1; }
.lm-list { flex: 1; overflow-y: auto; }
</style>
```

- [ ] **Step 4: 跑组件测试，确认通过**

Run: `cd frontend && npx vitest run tests/unit/EditorLayerMarking.spec.ts`
Expected: 2 测试 PASS。

- [ ] **Step 5: 接入 `ChapterTreePanel`**

`frontend/src/components/editor/ChapterTreePanel.vue`：
1. import 区加：`import EditorLayerMarking from './EditorLayerMarking.vue'`
2. toolbar `.tree-toolbar` 内（`store.editable && !store.markMode` 时显示一个入口按钮；放在搜索/计数之后）：
```html
      <div v-if="store.editable" class="layer-entry">
        <el-button size="small" :type="store.layerMode ? 'primary' : ''" @click="store.toggleLayerMode()">
          {{ store.layerMode ? '退出层级标定' : '层级标定' }}
        </el-button>
      </div>
```
3. 主体条件渲染：把现有 `<div v-bind="containerProps" class="tree-scroll"> … </div>`（树/虚拟列表整块）包成 `v-else`，前面加层级视图：
```html
    <EditorLayerMarking v-if="store.layerMode" />
    <div v-else v-bind="containerProps" class="tree-scroll">
      … 原有内容不变 …
    </div>
```
4. 样式追加：`.layer-entry { display: flex; }`

- [ ] **Step 6: 前端全量 Gate**

Run: `cd frontend && npm run lint && npm run typecheck && npm run test && npm run build`
Expected: 全绿（含本任务新测试，既有不回归）。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/components/editor/EditorLayerMarking.vue frontend/tests/unit/EditorLayerMarking.spec.ts frontend/src/components/editor/ChapterTreePanel.vue
git commit -m "$(cat <<'EOF'
feat(p2c): EditorLayerMarking bulk view wired into the tree panel

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## 收尾

- 最终 Gate：`cd frontend && npm run lint && npm run typecheck && npm run test && npm run build`。
- 可选手动冒烟：进编辑器 → 点「层级标定」→ 扁平清单逐行改一级/二级/三级/正文（含步骤子节点的行"正文"禁用）→「应用层级」→ 树原地重排（保 id）→ Ctrl+Z 可撤销 → 保存生效；步骤标记仍走原有 mark-mode。
- 用 superpowers:finishing-a-development-branch 收束。

## Self-Review 记录

- **Spec 覆盖**：D1 4 选项层级模式（T2 layerMode + T4 视图/入口）；D2 应用=本地原地重排+置脏+pushUndo（T2 applyLayerRoles）；D3 纯逻辑 layerMark（T1）；D4 步骤随行 + 含步骤子禁用正文（T1 effectiveRole + T3 disableContent + T4 disableContent 传参）；D5 步骤 mark-mode 不动（仅 toggleMarkMode 加互斥，未改其语义）。
- **占位符**：无；每步含完整代码与命令。
- **类型/契约一致**：`LayerRole`/`LayerRow`/`computeLayerUpdates`/`computeLayerIndents`（T1 定义；T2 用 computeLayerUpdates；T4 用 computeLayerIndents/defaultLayerRole）；`layerRows`/`applyLayerRoles`/`toggleLayerMode`（T2 定义；T4 用）；`disableContent`（T3 定义；T4 传）。
- **不破坏既有**：`disableContent` 可选默认不变；`toggleMarkMode` 仅加互斥；批量保存只发 parent_id/content_type/sort_order（level 服务端重算）；应用走本地置脏 + 正常保存（可撤销）。
- **测试环境**：layerMark/store 纯逻辑直测；EditorLayerMarking stub 掉 ImportMarkingRow；ImportMarkingRow 测试用 ElementPlus 插件 + `input[value="content"]` 查 disabled（沿用该 spec 既有范式）。
