# E10 — Version Diff / Compare Viewer (MVP) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compare an older version of a procedure against the group's current version, showing a node-level diff (added/removed/modified/unchanged) with modified nodes' old vs new body side by side.

**Architecture:** Pure `versionDiff.ts` (LCS over a `code || title` signature) + a `VersionCompareDialog.vue` (fetches both trees, renders the diff) + a 「对比当前」 entry in `VersionListPanel.vue`, hosted in `ProcedureDetailView.vue`. Frontend-only. Spec: `docs/superpowers/specs/2026-05-29-editor-e10-version-diff-viewer-design.md`.

**Tech Stack:** Vue 3 `<script setup>`, Element Plus, vitest + @vue/test-utils, vue-tsc. No new dependency.

---

## File Structure

- **Create** `frontend/src/components/version/versionDiff.ts` — pure `nodeSignature` / `changedFields` / `diffVersions`.
- **Create** `frontend/tests/unit/versionDiff.spec.ts` — pure tests (flat dir, matching `pdfModel.spec.ts`).
- **Create** `frontend/src/components/version/VersionCompareDialog.vue` — the compare dialog.
- **Create** `frontend/tests/unit/VersionCompareDialog.spec.ts` — dialog tests.
- **Modify** `frontend/src/components/version/VersionListPanel.vue` — `compare` emit + 「对比当前」 button.
- **Modify** `frontend/tests/unit/VersionListPanel.spec.ts` — entry tests.
- **Modify** `frontend/src/views/procedures/ProcedureDetailView.vue` — host the dialog.

No backend change.

---

## Task 1: Pure `versionDiff.ts`

**Files:**
- Create: `frontend/src/components/version/versionDiff.ts`
- Test: `frontend/tests/unit/versionDiff.spec.ts`

- [ ] **Step 1: Write the failing test — CREATE `frontend/tests/unit/versionDiff.spec.ts`**

```ts
import { describe, it, expect } from 'vitest'
import { nodeSignature, changedFields, diffVersions } from '@/components/version/versionDiff'
import type { Node } from '@/types/node'

function n(over: Partial<Node>): Node {
  return {
    id: 'x', procedure_id: 'p', sort_order: 0, heading_level: null, kind: 'node',
    body: '', code: '', skip_numbering: false, input_schema: {}, attachment_marks: [],
    mark_status: 'unmarked', revision: 1, parent_id: null, depth: 0, ...over,
  }
}

describe('nodeSignature', () => {
  it('uses code when present, else first-line title', () => {
    expect(nodeSignature(n({ code: '3.1', body: '<p>职责</p>' }))).toBe('3.1')
    expect(nodeSignature(n({ code: '', body: '<p>正文内容</p>' }))).toBe('正文内容')
  })
})

describe('changedFields', () => {
  it('detects body / level / kind / form changes; none when identical', () => {
    expect(changedFields(n({ body: '<p>a</p>' }), n({ body: '<p>b</p>' }))).toEqual(['正文'])
    expect(changedFields(n({ heading_level: 1 }), n({ heading_level: 2 }))).toEqual(['层级'])
    expect(changedFields(n({ kind: 'node' }), n({ kind: 'step' }))).toContain('类型')
    expect(changedFields(n({ input_schema: { type: 'NOTE' } }), n({ input_schema: { type: 'CHECK' } }))).toContain('执行表单')
    expect(changedFields(n({ body: '<p>a</p>' }), n({ body: '<p>a</p>' }))).toEqual([])
  })
})

describe('diffVersions', () => {
  it('identical trees → all unchanged', () => {
    const t = [n({ code: '1', body: '<p>目的</p>' }), n({ code: '', body: '<p>正文</p>', sort_order: 1 })]
    const rows = diffVersions(t, t.map((x) => ({ ...x })))
    expect(rows.map((r) => r.status)).toEqual(['unchanged', 'unchanged'])
  })
  it('added node only in new', () => {
    const old = [n({ code: '1', body: '<p>A</p>' })]
    const neu = [n({ code: '1', body: '<p>A</p>' }), n({ code: '2', body: '<p>B</p>', sort_order: 1 })]
    const rows = diffVersions(old, neu)
    expect(rows.map((r) => r.status)).toEqual(['unchanged', 'added'])
    expect(rows[1].new?.code).toBe('2')
  })
  it('removed node only in old', () => {
    const old = [n({ code: '1', body: '<p>A</p>' }), n({ code: '2', body: '<p>B</p>', sort_order: 1 })]
    const neu = [n({ code: '1', body: '<p>A</p>' })]
    const rows = diffVersions(old, neu)
    expect(rows.map((r) => r.status)).toEqual(['unchanged', 'removed'])
    expect(rows[1].old?.code).toBe('2')
  })
  it('same signature, different body → modified with changedFields', () => {
    const old = [n({ code: '1', body: '<p>目的</p>' })]
    const neu = [n({ code: '1', body: '<p>目的（修订）多一句</p>' })]
    const rows = diffVersions(old, neu)
    expect(rows).toHaveLength(1)
    expect(rows[0].status).toBe('modified')
    expect(rows[0].changedFields).toEqual(['正文'])
  })
  it('duplicate-title content matched positionally', () => {
    const mk = () => [n({ code: '', body: '<p>未命名</p>' }), n({ code: '', body: '<p>未命名</p>', sort_order: 1 })]
    expect(diffVersions(mk(), mk()).map((r) => r.status)).toEqual(['unchanged', 'unchanged'])
  })
  it('empty old → all added; empty new → all removed', () => {
    expect(diffVersions([], [n({ code: '1' })]).map((r) => r.status)).toEqual(['added'])
    expect(diffVersions([n({ code: '1' })], []).map((r) => r.status)).toEqual(['removed'])
  })
})
```

- [ ] **Step 2: Run to verify FAIL**

Run: `cd frontend && npm test -- tests/unit/versionDiff.spec.ts`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement — CREATE `frontend/src/components/version/versionDiff.ts`**

```ts
import type { Node } from '@/types/node'
import { nodeTitle } from '@/utils/nodeTree'

export type DiffStatus = 'unchanged' | 'modified' | 'added' | 'removed'
export interface DiffRow {
  status: DiffStatus
  old: Node | null
  new: Node | null
  changedFields: string[]
}

/** Match signature: stable heading numbering when present, else first-line text. */
export function nodeSignature(n: Node): string {
  return n.code.trim() || nodeTitle(n)
}

const FIELD_LABELS: { key: 'body' | 'heading_level' | 'kind' | 'skip_numbering'; label: string }[] = [
  { key: 'body', label: '正文' },
  { key: 'heading_level', label: '层级' },
  { key: 'kind', label: '类型' },
  { key: 'skip_numbering', label: '跳号' },
]

/** Persistent fields that differ between a matched pair (human labels). */
export function changedFields(a: Node, b: Node): string[] {
  const out: string[] = []
  for (const { key, label } of FIELD_LABELS) {
    if (a[key] !== b[key]) out.push(label)
  }
  if (JSON.stringify(a.input_schema) !== JSON.stringify(b.input_schema)) out.push('执行表单')
  if (JSON.stringify(a.attachment_marks) !== JSON.stringify(b.attachment_marks)) out.push('附件')
  return out
}

/** Pure node-level diff: LCS over signatures of two sort_order-ordered trees.
 *  Output in new-version order; removed rows interleaved at their old position. O(n·m). */
export function diffVersions(oldNodes: Node[], newNodes: Node[]): DiffRow[] {
  const a = oldNodes
  const b = newNodes
  const sa = a.map(nodeSignature)
  const sb = b.map(nodeSignature)
  const n = a.length
  const m = b.length
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0))
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = sa[i] === sb[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }
  const rows: DiffRow[] = []
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (sa[i] === sb[j]) {
      const fields = changedFields(a[i], b[j])
      rows.push({ status: fields.length ? 'modified' : 'unchanged', old: a[i], new: b[j], changedFields: fields })
      i++
      j++
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      rows.push({ status: 'removed', old: a[i], new: null, changedFields: [] })
      i++
    } else {
      rows.push({ status: 'added', old: null, new: b[j], changedFields: [] })
      j++
    }
  }
  while (i < n) {
    rows.push({ status: 'removed', old: a[i], new: null, changedFields: [] })
    i++
  }
  while (j < m) {
    rows.push({ status: 'added', old: null, new: b[j], changedFields: [] })
    j++
  }
  return rows
}
```

- [ ] **Step 4: Run to verify PASS**

Run: `cd frontend && npm test -- tests/unit/versionDiff.spec.ts` → expect all PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/version/versionDiff.ts frontend/tests/unit/versionDiff.spec.ts
git commit -m "feat(version): pure versionDiff (LCS node diff over code||title signature) (E10 Task 1)"
```

---

## Task 2: `VersionCompareDialog.vue`

**Files:**
- Create: `frontend/src/components/version/VersionCompareDialog.vue`
- Test: `frontend/tests/unit/VersionCompareDialog.spec.ts`

- [ ] **Step 1: Write the failing test — CREATE `frontend/tests/unit/VersionCompareDialog.spec.ts`**

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import type { Node } from '@/types/node'

const { listNodes } = vi.hoisted(() => ({ listNodes: vi.fn() }))
vi.mock('@/api/nodes', () => ({ listNodes }))

import VersionCompareDialog from '@/components/version/VersionCompareDialog.vue'

function n(over: Partial<Node>): Node {
  return {
    id: over.id ?? 'x', procedure_id: 'p', sort_order: 0, heading_level: null, kind: 'node',
    body: '', code: '', skip_numbering: false, input_schema: {}, attachment_marks: [],
    mark_status: 'unmarked', revision: 1, parent_id: null, depth: 0, ...over,
  }
}

let wrapper: ReturnType<typeof mount> | null = null

async function mountDialog(oldNodes: Node[], newNodes: Node[]) {
  listNodes.mockImplementation((procId: string) => Promise.resolve(procId === 'old' ? oldNodes : newNodes))
  wrapper = mount(VersionCompareDialog, {
    props: { modelValue: false, oldId: 'old', newId: 'new', oldVersion: 2, newVersion: 4 },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
  await wrapper.setProps({ modelValue: true }) // false→true triggers the open watcher
  await flushPromises()
  return wrapper
}

describe('VersionCompareDialog', () => {
  beforeEach(() => listNodes.mockReset())
  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
  })

  it('fetches both trees on open and renders title + a changed row', async () => {
    await mountDialog(
      [n({ id: 'o1', code: '1', body: '<p>目的</p>' })],
      [n({ id: 'n1', code: '1', body: '<p>目的（改）</p>' }), n({ id: 'n2', code: '2', body: '<p>新章节</p>', sort_order: 1 })],
    )
    expect(listNodes).toHaveBeenCalledWith('old')
    expect(listNodes).toHaveBeenCalledWith('new')
    expect(document.body.textContent).toContain('版本对比')
    expect(document.body.textContent).toContain('v2 → v4')
    expect(document.body.textContent).toContain('新章节') // the added node's title
  })

  it('只看变更 (default on) hides unchanged rows', async () => {
    await mountDialog(
      [n({ id: 'o1', code: '1', body: '<p>不变标题XYZ</p>' }), n({ id: 'o2', code: '2', body: '<p>旧</p>', sort_order: 1 })],
      [n({ id: 'n1', code: '1', body: '<p>不变标题XYZ</p>' }), n({ id: 'n2', code: '2', body: '<p>新内容</p>', sort_order: 1 })],
    )
    // code '1' node identical → unchanged → hidden by default; code '2' modified → shown
    expect(document.body.textContent).not.toContain('不变标题XYZ')
    expect(document.body.textContent).toContain('新内容')
  })
})
```

- [ ] **Step 2: Run to verify FAIL**

Run: `cd frontend && npm test -- tests/unit/VersionCompareDialog.spec.ts` → FAIL (component missing).

- [ ] **Step 3: Implement — CREATE `frontend/src/components/version/VersionCompareDialog.vue`**

```vue
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { listNodes } from '@/api/nodes'
import { nodeTitle } from '@/utils/nodeTree'
import { diffVersions, type DiffRow } from './versionDiff'

const props = defineProps<{
  modelValue: boolean
  oldId: string
  newId: string
  oldVersion: number
  newVersion: number
}>()
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>()
const visible = computed({ get: () => props.modelValue, set: (v) => emit('update:modelValue', v) })

const loading = ref(false)
const rows = ref<DiffRow[]>([])
const onlyChanges = ref(true)
const expanded = ref<Set<number>>(new Set())

watch(visible, async (open) => {
  if (!open) return
  loading.value = true
  expanded.value = new Set()
  try {
    const [oldNodes, newNodes] = await Promise.all([listNodes(props.oldId), listNodes(props.newId)])
    rows.value = diffVersions(oldNodes, newNodes)
  } catch {
    visible.value = false // 拦截器已提示
  } finally {
    loading.value = false
  }
})

const visibleRows = computed(() =>
  onlyChanges.value ? rows.value.filter((r) => r.status !== 'unchanged') : rows.value,
)
const summary = computed(() => ({
  added: rows.value.filter((r) => r.status === 'added').length,
  removed: rows.value.filter((r) => r.status === 'removed').length,
  modified: rows.value.filter((r) => r.status === 'modified').length,
}))
const GLYPH: Record<DiffRow['status'], string> = { unchanged: '=', modified: '~', added: '+', removed: '−' }

function code(r: DiffRow): string {
  return (r.new ?? r.old)?.code ?? ''
}
function title(r: DiffRow): string {
  const x = r.new ?? r.old
  return x ? nodeTitle(x) : ''
}
function toggle(i: number): void {
  const next = new Set(expanded.value)
  if (next.has(i)) next.delete(i)
  else next.add(i)
  expanded.value = next
}
</script>

<template>
  <el-dialog v-model="visible" fullscreen :show-close="false" append-to-body class="vc-dialog">
    <template #header>
      <div class="vc-toolbar">
        <span class="vc-title">版本对比 · v{{ oldVersion }} → v{{ newVersion }}</span>
        <span class="vc-summary">
          <span class="add">+{{ summary.added }}</span>
          <span class="del">−{{ summary.removed }}</span>
          <span class="mod">~{{ summary.modified }}</span>
        </span>
        <span class="vc-spacer" />
        <el-switch v-model="onlyChanges" active-text="只看变更" />
        <el-button @click="visible = false">关闭</el-button>
      </div>
    </template>

    <div v-loading="loading" class="vc-body">
      <div v-for="(r, i) in visibleRows" :key="`${i}-${(r.new ?? r.old)?.id}`" class="vc-row" :class="`is-${r.status}`">
        <div class="vc-line" :class="{ clickable: r.status !== 'unchanged' }" @click="r.status !== 'unchanged' && toggle(i)">
          <span class="vc-glyph">{{ GLYPH[r.status] }}</span>
          <span class="vc-code">{{ code(r) }}</span>
          <span class="vc-rowtitle">{{ title(r) }}</span>
          <el-tag v-for="f in r.changedFields" :key="f" size="small" type="warning" disable-transitions>{{ f }}</el-tag>
        </div>
        <div v-if="expanded.has(i)" class="vc-bodies">
          <template v-if="r.status === 'modified'">
            <div class="vc-col">
              <div class="vc-coltag">旧 v{{ oldVersion }}</div>
              <!-- eslint-disable-next-line vue/no-v-html -->
              <div class="vc-html" v-html="r.old?.body"></div>
            </div>
            <div class="vc-col">
              <div class="vc-coltag">新 v{{ newVersion }}</div>
              <!-- eslint-disable-next-line vue/no-v-html -->
              <div class="vc-html" v-html="r.new?.body"></div>
            </div>
          </template>
          <div v-else-if="r.status === 'added'" class="vc-col">
            <div class="vc-coltag">新增</div>
            <!-- eslint-disable-next-line vue/no-v-html -->
            <div class="vc-html" v-html="r.new?.body"></div>
          </div>
          <div v-else-if="r.status === 'removed'" class="vc-col">
            <div class="vc-coltag">删除</div>
            <!-- eslint-disable-next-line vue/no-v-html -->
            <div class="vc-html" v-html="r.old?.body"></div>
          </div>
        </div>
      </div>
      <el-empty v-if="!loading && !visibleRows.length" description="两个版本内容一致" />
    </div>
  </el-dialog>
</template>

<style scoped>
.vc-toolbar { display: flex; align-items: center; gap: 12px; width: 100%; }
.vc-title { font-weight: 600; }
.vc-summary { display: inline-flex; gap: 8px; font-size: 13px; }
.vc-summary .add { color: var(--el-color-success, #67c23a); }
.vc-summary .del { color: var(--el-color-danger, #f56c6c); }
.vc-summary .mod { color: var(--el-color-warning, #e6a23c); }
.vc-spacer { flex: 1; }
.vc-body { height: calc(100vh - 90px); overflow: auto; }
.vc-row { border-bottom: 1px solid var(--el-border-color-lighter, #f0f0f0); }
.vc-line { display: flex; align-items: center; gap: 10px; padding: 6px 8px; }
.vc-line.clickable { cursor: pointer; }
.vc-glyph { width: 16px; text-align: center; font-weight: bold; }
.vc-code { min-width: 48px; color: #909399; }
.vc-rowtitle { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.is-added { background: #f0f9eb; }
.is-removed { background: #fef0f0; }
.is-modified { background: #fdf6ec; }
.vc-bodies { display: flex; gap: 16px; padding: 8px 8px 12px 42px; }
.vc-col { flex: 1; min-width: 0; }
.vc-coltag { font-size: 12px; color: #909399; margin-bottom: 4px; }
.vc-html { border: 1px solid var(--el-border-color-lighter, #ebeef5); border-radius: 4px; padding: 8px; background: #fff; overflow-x: auto; }
</style>
```
(The `v-html` renders the node body HTML — body is trusted app-wide, same as `PdfPreviewDialog`. The eslint-disable comments keep lint quiet if `vue/no-v-html` is enabled; remove them if the repo's `PdfPreviewDialog` renders body without them.)

- [ ] **Step 4: Run to verify PASS**

Run: `cd frontend && npm test -- tests/unit/VersionCompareDialog.spec.ts` → expect both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/version/VersionCompareDialog.vue frontend/tests/unit/VersionCompareDialog.spec.ts
git commit -m "feat(version): VersionCompareDialog renders the node diff (E10 Task 2)"
```

---

## Task 3: 「对比当前」 entry in `VersionListPanel.vue`

**Files:**
- Modify: `frontend/src/components/version/VersionListPanel.vue`
- Test: `frontend/tests/unit/VersionListPanel.spec.ts`

- [ ] **Step 1: Write the failing tests — append to `frontend/tests/unit/VersionListPanel.spec.ts`**

```ts
  it('非当前行显示「对比当前」并派发 compare（older→current）', async () => {
    const w = await mountPanel([
      item({ id: 'v3', version: 3, status: 'PUBLISHED', is_current: true }),
      item({ id: 'v2', version: 2, status: 'ARCHIVED' }),
    ], 'v3')
    const btn = w.findAll('button').find((b) => b.text().includes('对比当前'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    expect(w.emitted('compare')?.[0]).toEqual([{ oldId: 'v2', oldVersion: 2, newId: 'v3', newVersion: 3 }])
  })

  it('当前行不显示「对比当前」', async () => {
    const w = await mountPanel([item({ id: 'v3', version: 3, status: 'PUBLISHED', is_current: true })], 'v3')
    expect(w.findAll('button').some((b) => b.text().includes('对比当前'))).toBe(false)
  })
```

- [ ] **Step 2: Run to verify FAIL**

Run: `cd frontend && npm test -- tests/unit/VersionListPanel.spec.ts` → the 2 new tests fail; existing pass.

- [ ] **Step 3: Implement in `frontend/src/components/version/VersionListPanel.vue`**

(a) Add `compare` to `defineEmits` (the block currently has `view` + `rollback`):
```ts
const emit = defineEmits<{
  (e: 'view', id: string): void
  (e: 'rollback', targetVersion: number, currentId: string): void
  (e: 'compare', payload: { oldId: string; oldVersion: number; newId: string; newVersion: number }): void
}>()
```
(b) Add a `current` computed near `currentPublished` (~line 20):
```ts
const current = computed(() => items.value.find((i) => i.is_current))
```
(c) Add an `emitCompare` helper (after `toggleNotes`, ~line 40) — typed so vue-tsc is happy:
```ts
function emitCompare(v: VersionListItem): void {
  if (!current.value) return
  emit('compare', { oldId: v.id, oldVersion: v.version, newId: current.value.id, newVersion: current.value.version })
}
```
(`VersionListItem` is already imported.)
(d) In the row `.line`, add the button — place it right after the 「查看」 button (the `v-if="v.id !== viewingId"` one):
```html
        <el-button
          v-if="!v.is_current && current"
          text
          size="small"
          @click="emitCompare(v)"
        >
          对比当前
        </el-button>
```

- [ ] **Step 4: Run to verify PASS**

Run: `cd frontend && npm test -- tests/unit/VersionListPanel.spec.ts` → all PASS (existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/version/VersionListPanel.vue frontend/tests/unit/VersionListPanel.spec.ts
git commit -m "feat(version): 对比当前 entry on VersionListPanel rows (E10 Task 3)"
```

---

## Task 4: Host the dialog in `ProcedureDetailView.vue`

**Files:**
- Modify: `frontend/src/views/procedures/ProcedureDetailView.vue`

No new unit test (the view mounts heavily; the change is additive wiring). Verified by vue-tsc + full suite.

- [ ] **Step 1: Import the dialog**

After the existing `import PdfPreviewDialog from '@/components/PdfPreview/PdfPreviewDialog.vue'` (~line 10), add:
```ts
import VersionCompareDialog from '@/components/version/VersionCompareDialog.vue'
```

- [ ] **Step 2: Add state**

Near the other refs (e.g. after `const previewVisible = ref(false)`, ~line 39):
```ts
const compareVisible = ref(false)
const comparePair = ref<{ oldId: string; oldVersion: number; newId: string; newVersion: number } | null>(null)
```

- [ ] **Step 3: Wire `@compare` on `VersionListPanel`**

The panel is rendered (~lines 452-458) with `@view` + `@rollback`. Add a `@compare` handler:
```html
      <VersionListPanel
        ref="panelRef"
        :group-id="meta.procedure_group_id"
        :viewing-id="meta.id"
        @view="(vid) => router.push(`/procedures/${vid}`)"
        @rollback="onRollback"
        @compare="(p) => { comparePair = p; compareVisible = true }"
      />
```

- [ ] **Step 4: Render the dialog**

After the existing `<PdfPreviewDialog v-model="previewVisible" :procedure-id="id" />` (~line 516), add:
```html
      <VersionCompareDialog
        v-if="comparePair"
        v-model="compareVisible"
        :old-id="comparePair.oldId"
        :new-id="comparePair.newId"
        :old-version="comparePair.oldVersion"
        :new-version="comparePair.newVersion"
      />
```

- [ ] **Step 5: Type check + full suite**

Run: `cd frontend && npm run typecheck` → vue-tsc no errors.
Run: `cd frontend && npm test` → 0 failures (the new versionDiff + VersionCompareDialog + VersionListPanel tests + everything else).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/procedures/ProcedureDetailView.vue
git commit -m "feat(version): host VersionCompareDialog in ProcedureDetailView (E10 Task 4)"
```

---

## Orchestrator browser smoke (NOT a subagent task — after Task 4, before merge; best-effort)

Needs a group with ≥2 versions; dev data is mostly single-version drafts. If practical: launch the worktree dev servers (bootstrap backend), open a procedure's **detail** page (`/procedures/{id}` — the read-only detail view, not `/edit`), use the version actions to **upgrade** it (creates v2, archiving v1), then on the v1 row click 「对比当前」 and confirm the dialog shows the diff (try editing a node in the v2 draft first to produce a `modified` row). If staging proves impractical, rely on the pure `versionDiff` tests + the jsdom dialog test and note it (consistent with prior best-effort calls).

---

## Self-Review

**Spec coverage:**
- Pure `nodeSignature`/`changedFields`/`diffVersions` (LCS over `code||title`) → Task 1. ✓
- `VersionCompareDialog` fetches both trees, unified rows with `= ~ + −`, summary, 只看变更 filter, modified→old|new body side-by-side (`v-html`) → Task 2. ✓
- 「对比当前」 on non-current rows → emits `{oldId,oldVersion,newId,newVersion}` (older vs current) → Task 3. ✓
- Hosted in `ProcedureDetailView` (the actual `VersionListPanel` host) → Task 4. ✓
- Accepted caveat (title edit → add/remove) is inherent to the signature; no task fights it. ✓
- Non-goals (char highlighting, arbitrary-two, move detection, backend) → untouched. ✓

**Placeholder scan:** none — full code for the module, the component, and every wiring edit.

**Type consistency:** `DiffRow`/`DiffStatus` defined in Task 1, imported in Task 2. `diffVersions(Node[], Node[]): DiffRow[]`. The `compare` emit payload shape `{oldId,oldVersion,newId,newVersion}` is identical across VersionListPanel emit (Task 3), the `comparePair` ref + dialog props (Task 4), and the dialog's `defineProps` (Task 2). `listNodes(id): Promise<Node[]>` matches the `Promise.all` use. Node factory in both test files includes all required `Node` fields.
