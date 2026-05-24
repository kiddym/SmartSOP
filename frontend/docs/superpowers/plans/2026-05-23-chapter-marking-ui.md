# Chapter Marking UI Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Three coordinated UI improvements to the import wizard: Word document preview on the left of the chapter-marking step, hierarchical chapter numbering (1 / 1.1 / 1.1.1) in both tree views, and first-20-character rich-text snippets for content nodes in both tree views.

**Architecture:** `computeChapterNumbers` pure function added to `importTree.ts` traverses the tree and returns `Record<id, string>` (e.g. `{ "abc": "1.2" }`); `skip_numbering=true` nodes are excluded and do **not** consume a sequence position (plan A). `ImportTreeNode.vue` accepts an optional `numberMap` prop passed all the way down the recursive tree and a local `snippetOf` helper strips HTML for content node previews. `BlockMarkingStep.vue` is restructured: left panel renders the `.docx` file with `docx-preview`, right panel holds the toolbar + block list + collapsible tree preview. `ImportWizardView.vue` passes its existing `file` ref to `BlockMarkingStep` via a new optional prop.

**Tech Stack:** Vue 3, TypeScript, Element Plus, `docx-preview` (new npm dep), Vitest + jsdom (existing test setup)

---

## File Map

| File | Change |
|------|--------|
| `SmartSOP/frontend/package.json` | Add `docx-preview` dependency |
| `SmartSOP/frontend/src/utils/importTree.ts` | Export `computeChapterNumbers` |
| `SmartSOP/frontend/tests/unit/importTree.spec.ts` | Tests for `computeChapterNumbers` |
| `SmartSOP/frontend/src/components/import/ImportTreeNode.vue` | Add `numberMap` prop + `snippetOf` helper + snippet rendering |
| `SmartSOP/frontend/tests/unit/ImportTreeNode.spec.ts` | Tests for numberMap display + snippet |
| `SmartSOP/frontend/src/components/import/BlockMarkingStep.vue` | New layout + `file` prop + docx-preview + compute/pass `numberMap` |
| `SmartSOP/frontend/tests/unit/BlockMarkingStep.spec.ts` | Update stub set for new layout |
| `SmartSOP/frontend/src/components/import/TreeReviewStep.vue` | Compute + pass `numberMap` |
| `SmartSOP/frontend/src/views/procedures/ImportWizardView.vue` | Pass `:file="file"` to BlockMarkingStep |

---

## Task 1: Install `docx-preview`

**Files:**
- Modify: `SmartSOP/frontend/package.json`

- [ ] **Step 1: Install the package**

```bash
cd SmartSOP/frontend && npm install docx-preview
```

Expected output: `added 1 package` (or similar) with no errors.

- [ ] **Step 2: Verify the import resolves**

```bash
node -e "require('./node_modules/docx-preview/dist/docx-preview.umd.js'); console.log('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add SmartSOP/frontend/package.json SmartSOP/frontend/package-lock.json
git commit -m "chore: add docx-preview for Word document preview in import wizard"
```

---

## Task 2: Add `computeChapterNumbers` to `importTree.ts`

**Files:**
- Modify: `SmartSOP/frontend/src/utils/importTree.ts`
- Test: `SmartSOP/frontend/tests/unit/importTree.spec.ts`

- [ ] **Step 1: Write the failing tests**

Append to the existing `describe('importTree 纯函数')` block in `SmartSOP/frontend/tests/unit/importTree.spec.ts`:

```typescript
import {
  buildWizardTree,
  clearReview,
  computeChapterNumbers,  // add to existing import
  countReview,
  deleteNode,
  findNode,
  moveNode,
  toImportNodes,
  updateNode,
} from '@/utils/importTree'
```

Then add a new `describe` block at the bottom of the file:

```typescript
describe('computeChapterNumbers', () => {
  it('flat list: assigns sequential integers starting at 1', () => {
    const tree = buildWizardTree([
      pnode({ id: 'a', title: 'A' }),
      pnode({ id: 'b', title: 'B' }),
      pnode({ id: 'c', title: 'C' }),
    ])
    expect(computeChapterNumbers(tree)).toEqual({ a: '1', b: '2', c: '3' })
  })

  it('nested children get dotted prefix from parent', () => {
    const tree = buildWizardTree([
      pnode({
        id: 'a',
        title: 'A',
        children: [
          pnode({ id: 'a1', title: 'A1' }),
          pnode({ id: 'a2', title: 'A2' }),
        ],
      }),
      pnode({
        id: 'b',
        title: 'B',
        children: [
          pnode({
            id: 'b1',
            title: 'B1',
            children: [pnode({ id: 'b1a', title: 'B1A' })],
          }),
        ],
      }),
    ])
    const nums = computeChapterNumbers(tree)
    expect(nums.a).toBe('1')
    expect(nums.a1).toBe('1.1')
    expect(nums.a2).toBe('1.2')
    expect(nums.b).toBe('2')
    expect(nums.b1).toBe('2.1')
    expect(nums.b1a).toBe('2.1.1')
  })

  it('skip_numbering=true: excluded from map and does not consume sequence', () => {
    const tree = buildWizardTree([
      pnode({ id: 'a', title: 'A' }),
      pnode({ id: 's', title: 'Skip', skip_numbering: true }),
      pnode({ id: 'b', title: 'B' }),
    ])
    const nums = computeChapterNumbers(tree)
    expect(nums.a).toBe('1')
    expect('s' in nums).toBe(false)
    expect(nums.b).toBe('2') // sequence is 2, not 3
  })

  it('content nodes are not numbered', () => {
    const tree = buildWizardTree([
      pnode({
        id: 'a',
        title: 'A',
        children: [pnode({ id: 'c', title: 'Content', content_type: 'content' })],
      }),
    ])
    const nums = computeChapterNumbers(tree)
    expect(nums.a).toBe('1')
    expect('c' in nums).toBe(false)
  })

  it('empty tree returns empty object', () => {
    expect(computeChapterNumbers([])).toEqual({})
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd SmartSOP/frontend && npx vitest run tests/unit/importTree.spec.ts
```

Expected: FAIL with `computeChapterNumbers is not a function` (or similar import error).

- [ ] **Step 3: Implement `computeChapterNumbers` in `importTree.ts`**

Add the following at the bottom of `SmartSOP/frontend/src/utils/importTree.ts`, before the closing of the file:

```typescript
function _computeNumbers(nodes: WizardNode[], prefix: string): Record<string, string> {
  const result: Record<string, string> = {}
  let seq = 0
  for (const node of nodes) {
    if (node.content_type !== 'chapter') continue
    if (node.skip_numbering) {
      Object.assign(result, _computeNumbers(node.children, ''))
      continue
    }
    seq++
    const num = prefix ? `${prefix}.${seq}` : String(seq)
    result[node.id] = num
    Object.assign(result, _computeNumbers(node.children, num))
  }
  return result
}

export function computeChapterNumbers(nodes: WizardNode[]): Record<string, string> {
  return _computeNumbers(nodes, '')
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd SmartSOP/frontend && npx vitest run tests/unit/importTree.spec.ts
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add SmartSOP/frontend/src/utils/importTree.ts SmartSOP/frontend/tests/unit/importTree.spec.ts
git commit -m "feat: add computeChapterNumbers pure function with skip_numbering support"
```

---

## Task 3: Update `ImportTreeNode.vue` — number display + content snippet

**Files:**
- Modify: `SmartSOP/frontend/src/components/import/ImportTreeNode.vue`
- Test: `SmartSOP/frontend/tests/unit/ImportTreeNode.spec.ts`

- [ ] **Step 1: Write the failing tests**

Append to the existing `describe('ImportTreeNode')` block in `SmartSOP/frontend/tests/unit/ImportTreeNode.spec.ts`:

```typescript
  it('renders chapter number when numberMap contains node id', () => {
    const w = mount(ImportTreeNode, {
      props: { node: node({ id: 'a', title: '目的' }), depth: 0, selectedId: null, numberMap: { a: '1' } },
      global: { plugins: [ElementPlus] },
    })
    expect(w.find('.chapter-num').text()).toBe('1')
  })

  it('does not render number span when numberMap omitted', () => {
    const w = mount(ImportTreeNode, {
      props: { node: node({ id: 'a', title: '目的' }), depth: 0, selectedId: null },
      global: { plugins: [ElementPlus] },
    })
    expect(w.find('.chapter-num').exists()).toBe(false)
  })

  it('content node shows plain-text snippet from rich_content', () => {
    const w = mount(ImportTreeNode, {
      props: {
        node: node({
          id: 'x',
          content_type: 'content',
          rich_content: '<p>这是正文内容ABCDEFGHIJKLMNOPQ</p>',
        }),
        depth: 0,
        selectedId: null,
      },
      global: { plugins: [ElementPlus] },
    })
    const snippet = w.find('.snippet')
    expect(snippet.exists()).toBe(true)
    // 20-char plain text slice, HTML stripped
    expect(snippet.text()).toBe('这是正文内容ABCDEFGHIJKLMNO')
  })

  it('content node with empty rich_content shows no snippet', () => {
    const w = mount(ImportTreeNode, {
      props: { node: node({ id: 'x', content_type: 'content', rich_content: '' }), depth: 0, selectedId: null },
      global: { plugins: [ElementPlus] },
    })
    expect(w.find('.snippet').exists()).toBe(false)
  })
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd SmartSOP/frontend && npx vitest run tests/unit/ImportTreeNode.spec.ts
```

Expected: FAIL on the 4 new tests (`.chapter-num` not found, `.snippet` not found).

- [ ] **Step 3: Implement changes in `ImportTreeNode.vue`**

Replace the entire file with:

```vue
<script setup lang="ts">
import type { WizardNode } from '@/utils/importTree'

defineProps<{
  node: WizardNode
  depth: number
  selectedId: string | null
  readonly?: boolean
  numberMap?: Record<string, string>
}>()
const emit = defineEmits<{
  (e: 'select', id: string): void
  (e: 'delete', id: string): void
  (e: 'move', id: string, dir: -1 | 1): void
}>()

const TYPE_LABEL = { chapter: '章', content: '容' } as const

function snippetOf(html: string): string {
  const el = document.createElement('div')
  el.innerHTML = html
  return (el.textContent ?? '').trim().slice(0, 20)
}
</script>

<template>
  <div class="tnode">
    <div
      class="row"
      :class="{ selected: selectedId === node.id, review: node.mark_status === 'review' }"
      :style="{ paddingLeft: `${8 + depth * 18}px` }"
      @click="emit('select', node.id)"
    >
      <el-tag size="small" :type="node.content_type === 'chapter' ? 'primary' : 'info'" disable-transitions>
        {{ TYPE_LABEL[node.content_type] }}
      </el-tag>
      <span v-if="numberMap?.[node.id]" class="chapter-num">{{ numberMap[node.id] }}</span>
      <span class="title" :class="{ empty: !node.title && node.content_type === 'chapter' }">
        {{ node.content_type === 'chapter' ? (node.title || '（无标题）') : '' }}
      </span>
      <span v-if="node.content_type === 'content' && node.rich_content" class="snippet">
        {{ snippetOf(node.rich_content) }}
      </span>
      <el-tag v-if="node.mark_status === 'review'" size="small" type="warning" disable-transitions>
        待确认
      </el-tag>
      <el-tag v-if="node.skip_numbering" size="small" disable-transitions>不编号</el-tag>
      <span class="spacer" />
      <span v-if="!readonly" class="ops" @click.stop>
        <el-button text size="small" title="上移" @click="emit('move', node.id, -1)">↑</el-button>
        <el-button text size="small" title="下移" @click="emit('move', node.id, 1)">↓</el-button>
        <el-button text size="small" type="danger" title="删除（含子节点）" @click="emit('delete', node.id)">
          ✕
        </el-button>
      </span>
    </div>
    <ImportTreeNode
      v-for="child in node.children"
      :key="child.id"
      :node="child"
      :depth="depth + 1"
      :selected-id="selectedId"
      :readonly="readonly"
      :number-map="numberMap"
      @select="(id) => emit('select', id)"
      @delete="(id) => emit('delete', id)"
      @move="(id, dir) => emit('move', id, dir)"
    />
  </div>
</template>

<style scoped>
.row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  cursor: pointer;
  border-bottom: 1px solid var(--el-border-color-lighter, #f0f0f0);
}
.row:hover {
  background: #f5f7fa;
}
.row.selected {
  background: #ecf5ff;
}
.row.review {
  background: #fdf6ec;
}
.row.review.selected {
  background: #faecd8;
}
.chapter-num {
  font-size: 13px;
  font-weight: 600;
  color: #409eff;
  flex-shrink: 0;
}
.title {
  font-size: 13px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 320px;
}
.title.empty {
  color: #c0c4cc;
  font-style: italic;
}
.snippet {
  font-size: 12px;
  color: #909399;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 280px;
  font-style: italic;
}
.spacer {
  flex: 1;
}
.ops {
  display: flex;
  gap: 0;
  opacity: 0;
}
.row:hover .ops,
.row.selected .ops {
  opacity: 1;
}
</style>
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd SmartSOP/frontend && npx vitest run tests/unit/ImportTreeNode.spec.ts
```

Expected: all tests PASS including the 4 new ones.

- [ ] **Step 5: Commit**

```bash
git add SmartSOP/frontend/src/components/import/ImportTreeNode.vue SmartSOP/frontend/tests/unit/ImportTreeNode.spec.ts
git commit -m "feat: show chapter numbers and content snippets in tree nodes"
```

---

## Task 4: Wire `numberMap` into `BlockMarkingStep.vue`

**Files:**
- Modify: `SmartSOP/frontend/src/components/import/BlockMarkingStep.vue`

- [ ] **Step 1: Update the `<script setup>` imports and computed**

In `BlockMarkingStep.vue`, add `computeChapterNumbers` to the import from `@/utils/importTree`:

```typescript
import {
  applyBatchMark,
  rebuildTreeFromMarks,
  validateMarkedBlocks,
  type MarkRole,
  type MarkedImportBlock,
} from '@/utils/importBlocks'
import { computeChapterNumbers, type WizardNode } from '@/utils/importTree'
```

Add a computed for `numberMap` right after the existing `preview` computed:

```typescript
const numberMap = computed(() => computeChapterNumbers(preview.value as WizardNode[]))
```

- [ ] **Step 2: Pass `numberMap` to `ImportTreeNode` in the template**

Find the `ImportTreeNode` usage in the preview pane and add `:number-map="numberMap"`:

```html
<ImportTreeNode
  v-for="node in preview"
  :key="node.id"
  :node="node"
  :depth="0"
  :selected-id="null"
  :readonly="true"
  :number-map="numberMap"
/>
```

- [ ] **Step 3: Run existing tests to verify nothing broke**

```bash
cd SmartSOP/frontend && npx vitest run tests/unit/BlockMarkingStep.spec.ts
```

Expected: all existing tests PASS.

- [ ] **Step 4: Commit**

```bash
git add SmartSOP/frontend/src/components/import/BlockMarkingStep.vue
git commit -m "feat: show chapter numbers in BlockMarkingStep tree preview"
```

---

## Task 5: Wire `numberMap` into `TreeReviewStep.vue`

**Files:**
- Modify: `SmartSOP/frontend/src/components/import/TreeReviewStep.vue`

- [ ] **Step 1: Add import and computed in `<script setup>`**

Add `computeChapterNumbers` to the existing import:

```typescript
import {
  cloneTree,
  computeChapterNumbers,
  countReview,
  deleteNode,
  findNode,
  moveNode,
  updateNode,
  type WizardNode,
} from '@/utils/importTree'
```

Add the computed right after `reviewCount`:

```typescript
const numberMap = computed(() => computeChapterNumbers(props.modelValue))
```

- [ ] **Step 2: Pass `numberMap` to each `ImportTreeNode` in the template**

Find the `v-for` loop over `modelValue` and add `:number-map`:

```html
<ImportTreeNode
  v-for="node in modelValue"
  :key="node.id"
  :node="node"
  :depth="0"
  :selected-id="selectedId"
  :number-map="numberMap"
  @select="(id) => (selectedId = id)"
  @delete="onDelete"
  @move="onMove"
/>
```

- [ ] **Step 3: Run full test suite**

```bash
cd SmartSOP/frontend && npx vitest run
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add SmartSOP/frontend/src/components/import/TreeReviewStep.vue
git commit -m "feat: show chapter numbers in TreeReviewStep tree"
```

---

## Task 6: Pass `file` prop from `ImportWizardView` to `BlockMarkingStep`

**Files:**
- Modify: `SmartSOP/frontend/src/views/procedures/ImportWizardView.vue`
- Modify: `SmartSOP/frontend/src/components/import/BlockMarkingStep.vue`

- [ ] **Step 1: Add optional `file` prop to `BlockMarkingStep`**

At the top of `BlockMarkingStep.vue`'s `<script setup>`, update the `defineProps`:

```typescript
const props = defineProps<{
  modelValue: MarkedImportBlock[]
  file?: File | null
}>()
```

- [ ] **Step 2: Pass `:file="file"` in `ImportWizardView.vue`**

Find the `BlockMarkingStep` usage (line ~315):

```html
<BlockMarkingStep v-show="step === 3" v-model="markedBlocks" :file="file" />
```

- [ ] **Step 3: Run tests**

```bash
cd SmartSOP/frontend && npx vitest run tests/unit/BlockMarkingStep.spec.ts
```

Expected: PASS (file prop is optional, existing test doesn't pass it, no rendering triggered).

- [ ] **Step 4: Commit**

```bash
git add SmartSOP/frontend/src/components/import/BlockMarkingStep.vue SmartSOP/frontend/src/views/procedures/ImportWizardView.vue
git commit -m "feat: thread file prop from wizard down to BlockMarkingStep for docx preview"
```

---

## Task 7: Implement Word preview layout in `BlockMarkingStep.vue`

**Files:**
- Modify: `SmartSOP/frontend/src/components/import/BlockMarkingStep.vue`
- Modify: `SmartSOP/frontend/tests/unit/BlockMarkingStep.spec.ts`

- [ ] **Step 1: Add imports and refs to `<script setup>`**

Add at the top of the script section:

```typescript
import { computed, ref, watchEffect } from 'vue'
import { renderAsync } from 'docx-preview'
```

Add after the existing reactive state:

```typescript
const docxRef = ref<HTMLDivElement | null>(null)
const renderError = ref(false)

watchEffect(async () => {
  const el = docxRef.value
  const file = props.file
  if (!el || !file) return
  renderError.value = false
  el.innerHTML = ''
  try {
    await renderAsync(file, el, undefined, { className: 'docx-render', ignoreWidth: true })
  } catch {
    renderError.value = true
  }
})
```

- [ ] **Step 2: Replace the template**

Replace the entire `<template>` section with:

```html
<template>
  <div class="marking-step">
    <div class="panes">
      <!-- Left: Word document preview -->
      <div class="docx-pane">
        <div class="pane-title">Word 原文预览</div>
        <div v-if="!props.file" class="docx-empty">
          <el-empty description="未加载文档" />
        </div>
        <div v-else-if="renderError" class="docx-empty">
          <el-empty description="预览加载失败" />
        </div>
        <div ref="docxRef" class="docx-container" />
      </div>

      <!-- Right: toolbar + block list + tree preview -->
      <div class="right-pane">
        <div class="toolbar">
          <span class="hint">已选 {{ selectedCount }} 项</span>
          <span class="spacer" />
          <el-button size="small" @click="mark('chapter_1')">一级章节</el-button>
          <el-button size="small" @click="mark('chapter_2')">二级章节</el-button>
          <el-button size="small" @click="mark('chapter_3')">三级章节</el-button>
          <el-button size="small" @click="mark('content')">正文</el-button>
          <el-button size="small" @click="mark('ignored')">忽略</el-button>
        </div>

        <el-alert
          v-if="issues.some((i) => i.level === 'error')"
          class="banner"
          type="error"
          :closable="false"
          show-icon
          title="存在层级错误，请修正后再继续导入。"
        />
        <el-alert
          v-else-if="issues.some((i) => i.level === 'warning')"
          class="banner"
          type="warning"
          :closable="false"
          show-icon
          title="存在章节前正文，确认不需要导入时可标为忽略。"
        />

        <div class="blocks">
          <div
            v-for="block in modelValue"
            :key="block.id"
            class="block-row"
            :class="{ ignored: block.assigned_role === 'ignored' }"
          >
            <el-checkbox
              :model-value="checked(block.id)"
              @update:model-value="(v: boolean) => setChecked(block.id, v)"
            />
            <el-tag size="small" disable-transitions>{{ roleText(block.assigned_role) }}</el-tag>
            <span class="block-text">{{ block.display_text || '（空块）' }}</span>
            <el-tag v-if="block.has_word_numbering" size="small" type="info" disable-transitions>Word编号</el-tag>
            <el-tag v-if="block.mark_status === 'review'" size="small" type="warning" disable-transitions>待确认</el-tag>
            <span v-if="issueFor(block.id)" class="issue">{{ issueFor(block.id) }}</span>
          </div>
        </div>

        <div class="tree-section">
          <div class="section-title">导入后树预览</div>
          <div class="tree-container">
            <template v-if="preview.length">
              <ImportTreeNode
                v-for="node in preview"
                :key="node.id"
                :node="node"
                :depth="0"
                :selected-id="null"
                :readonly="true"
                :number-map="numberMap"
              />
            </template>
            <el-empty v-else description="暂无章节树" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 3: Replace the `<style>` section**

Replace the entire `<style scoped>` section with:

```css
<style scoped>
.marking-step {
  padding: 8px 0;
}
.panes {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  height: 560px;
}
.docx-pane {
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 4px;
  overflow: auto;
  display: flex;
  flex-direction: column;
}
.pane-title,
.section-title {
  padding: 8px 10px;
  font-size: 13px;
  font-weight: 600;
  border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
  background: #fff;
  flex-shrink: 0;
}
.docx-container {
  flex: 1;
  padding: 0 8px 8px;
}
.docx-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
/* scope docx-preview rendered styles */
:deep(.docx-render) {
  font-size: 13px;
}
:deep(.docx-render img) {
  max-width: 100%;
}
.right-pane {
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow: hidden;
  min-height: 0;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.hint {
  color: #606266;
  font-size: 13px;
}
.spacer {
  flex: 1;
}
.banner {
  flex-shrink: 0;
}
.blocks {
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 4px;
  overflow: auto;
  flex: 1;
  min-height: 0;
}
.block-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  padding: 6px 8px;
  border-bottom: 1px solid var(--el-border-color-lighter, #f0f0f0);
}
.block-row.ignored {
  color: #909399;
  background: #fafafa;
}
.block-text {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}
.issue {
  color: #f56c6c;
  font-size: 12px;
}
.tree-section {
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 4px;
  overflow: auto;
  max-height: 200px;
  flex-shrink: 0;
}
.tree-container {
  padding: 4px 0;
}
</style>
```

- [ ] **Step 4: Update `BlockMarkingStep.spec.ts` to add the `ImportTreeNode` stub**

The test uses `global.stubs` to stub Element Plus components. Add `ImportTreeNode` to the stubs so the recursive component doesn't cause issues in jsdom:

```typescript
global: {
  stubs: {
    ImportTreeNode: { template: '<div class="stub-tree" />' },  // add this line
    'el-button': { template: '<button @click="$emit(`click`)"><slot /></button>' },
    'el-checkbox': {
      props: ['modelValue'],
      emits: ['update:modelValue'],
      template: '<input type="checkbox" :checked="modelValue" @change="$emit(`update:modelValue`, !modelValue)" />',
    },
    'el-tag': { template: '<span><slot /></span>' },
    'el-alert': { template: '<div />' },
    'el-empty': { template: '<div />' },
  },
},
```

- [ ] **Step 5: Run tests**

```bash
cd SmartSOP/frontend && npx vitest run tests/unit/BlockMarkingStep.spec.ts
```

Expected: all tests PASS.

- [ ] **Step 6: Run full test suite**

```bash
cd SmartSOP/frontend && npx vitest run
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add SmartSOP/frontend/src/components/import/BlockMarkingStep.vue SmartSOP/frontend/tests/unit/BlockMarkingStep.spec.ts
git commit -m "feat: Word document preview in chapter marking step with new two-panel layout"
```

---

## Self-Review

### Spec Coverage
| Requirement | Covered by |
|-------------|-----------|
| Word preview on left of BlockMarkingStep | Task 7 |
| Block list + tree combined on right | Task 7 |
| Hierarchical numbering 1 / 1.1 / 1.1.1 | Task 2 (pure fn), Task 3 (render), Task 4 (BlockMarking), Task 5 (TreeReview) |
| skip_numbering nodes excluded + don't consume sequence (plan A) | Task 2 |
| Numbering in BlockMarkingStep (step 4) | Task 4 |
| Numbering in TreeReviewStep (step 5) | Task 5 |
| Content node snippet (first 20 chars, both steps) | Task 3 (render + prop), Tasks 4+5 use same ImportTreeNode |
| File prop threaded through wizard | Task 6 |

### Placeholder Scan
No TBDs or incomplete steps found.

### Type Consistency
- `computeChapterNumbers` takes `WizardNode[]`, returns `Record<string, string>` — used consistently across Tasks 2, 4, 5
- `numberMap` prop on `ImportTreeNode` is `Record<string, string> | undefined` — matches all usage sites
- `file` prop on `BlockMarkingStep` is `File | null | undefined` — matches `file.value` type in wizard (`ref<File | null>`)
- `renderAsync` import from `docx-preview` — standard named export from that package
