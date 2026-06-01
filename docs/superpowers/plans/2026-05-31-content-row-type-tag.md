# 审查树 content 行表格/图片类型标识 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在编辑器节点树的正文行上，为「表格」「图片」两类内容显示「图标+文字标签」，让用户无需展开即可分辨该行解析出的内容类型。

**Architecture:** 纯前端、零后端、零数据库迁移。新增纯函数 `contentKind(node)`（看 `node.body` 是否含 `<table>`/`<img>`），预计算进 `TreeRow.contentKind`，由展示组件 `NodeTreeRow.vue` 渲染 Element Plus 图标 + 标签。纯文字行与章节行不打标。

**Tech Stack:** Vue 3 `<script setup>` + TypeScript、Element Plus（`@element-plus/icons-vue` 已是依赖）、Vitest + @vue/test-utils。

参考 spec：`docs/superpowers/specs/2026-05-31-content-row-type-tag-design.md`

---

## File Structure

- 修改 `frontend/src/utils/nodeTree.ts` — 加 `ContentKind` 类型、`contentKind()` 纯函数、`TreeRow.contentKind` 字段、`visibleRows()` 填值。
- 修改 `frontend/src/components/editor/NodeTreeRow.vue` — 图标 import、常量映射、模板插入标签、样式。
- 修改 `frontend/tests/unit/utils/nodeTree.spec.ts` — `contentKind` 单测 + `visibleRows` 携带字段断言。
- 修改 `frontend/tests/unit/NodeTreeRow.spec.ts` — `treeRow` helper 补默认值 + 渲染断言。

所有命令在 `frontend/` 目录下执行。

---

### Task 1: `contentKind` 纯函数 + 类型

**Files:**
- Modify: `frontend/src/utils/nodeTree.ts`
- Test: `frontend/tests/unit/utils/nodeTree.spec.ts`

- [ ] **Step 1: 写失败测试**

在 `frontend/tests/unit/utils/nodeTree.spec.ts` 顶部 import 行追加 `contentKind`、`ContentKind`：

```ts
import { nodeTitle, hasChildren, visibleRows, descendantIds, subtreeIds, checkStates, indentLevel, arrowNav, contentKind } from '@/utils/nodeTree'
import type { TreeRow, ContentKind } from '@/utils/nodeTree'
```

在文件末尾追加：

```ts
describe('contentKind', () => {
  it('table body → table', () => {
    expect(contentKind(n({ body: '<table border="1"><tr><td>a</td></tr></table>' }))).toBe('table')
  })
  it('img body → image', () => {
    expect(contentKind(n({ body: '<p><img src="x.png"/></p>' }))).toBe('image')
  })
  it('table wins when both present', () => {
    expect(contentKind(n({ body: '<table><tr><td><img src="x.png"/></td></tr></table>' }))).toBe('table')
  })
  it('plain text → null', () => {
    expect(contentKind(n({ body: '<p>纯文字</p>' }))).toBe(null)
  })
  it('empty body → null', () => {
    expect(contentKind(n({ body: '' }))).toBe(null)
  })
  it('chapter row (heading_level set) → null even with table', () => {
    expect(contentKind(n({ heading_level: 1, body: '<table><tr><td>a</td></tr></table>' }))).toBe(null)
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npx vitest run tests/unit/utils/nodeTree.spec.ts -t contentKind`
Expected: FAIL（`contentKind is not a function` / 类型导出不存在）

- [ ] **Step 3: 实现**

在 `frontend/src/utils/nodeTree.ts` 的 `nodeTitle` 函数之后插入：

```ts
export type ContentKind = 'table' | 'image'

/** 正文行的内容类型标识；纯文字或章节标题行返回 null（不打标）。
 *  仅对正文行（heading_level === null）判定。表格优先于图片
 *  （表格单元格内可能内嵌图，整体语义仍是表格）。
 *  依据 body HTML 是否含 <table>/<img>，与后端序列化输出对应。 */
export function contentKind(node: Node): ContentKind | null {
  if (node.heading_level !== null) return null
  const body = node.body ?? ''
  if (/<table[\s>]/i.test(body)) return 'table'
  if (/<img[\s>]/i.test(body)) return 'image'
  return null
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npx vitest run tests/unit/utils/nodeTree.spec.ts -t contentKind`
Expected: PASS（6 个用例）

---

### Task 2: `TreeRow.contentKind` 字段 + `visibleRows` 填值

**Files:**
- Modify: `frontend/src/utils/nodeTree.ts`
- Test: `frontend/tests/unit/utils/nodeTree.spec.ts`

- [ ] **Step 1: 写失败测试**

在 `frontend/tests/unit/utils/nodeTree.spec.ts` 的 `describe('visibleRows', ...)` 内追加用例：

```ts
  it('row carries contentKind (table/image/null)', () => {
    const ns = [
      n({ id: 't', body: '<table><tr><td>x</td></tr></table>' }),
      n({ id: 'i', body: '<p><img src="x.png"/></p>' }),
      n({ id: 'p', body: '<p>文字</p>' }),
    ]
    const rows = visibleRows(ns, {}, { search: '', reviewOnly: false })
    expect(rows.map((r) => r.contentKind)).toEqual(['table', 'image', null])
  })
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npx vitest run tests/unit/utils/nodeTree.spec.ts -t "carries contentKind"`
Expected: FAIL（`rows[*].contentKind` 为 `undefined`，不等于期望数组）

- [ ] **Step 3: 实现**

在 `frontend/src/utils/nodeTree.ts` 的 `TreeRow` 接口加字段：

```ts
export interface TreeRow {
  node: Node
  title: string
  contentKind: ContentKind | null
  hasChildren: boolean
  expanded: boolean
}
```

在 `visibleRows()` 内 `rows.push(...)` 处补 `contentKind`：

```ts
    rows.push({
      node,
      title,
      contentKind: contentKind(node),
      hasChildren: parentIds.has(node.id),
      expanded: isExpanded(node.id),
    })
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npx vitest run tests/unit/utils/nodeTree.spec.ts`
Expected: PASS（含新用例与既有用例）

- [ ] **Step 5: typecheck（TreeRow 新增必填字段不破坏现有构造点）**

Run: `npx vue-tsc --noEmit`
Expected: 可能在 `NodeTreeRow.spec.ts` 的 `treeRow` helper 处报缺 `contentKind`——Task 3 修复；本步若仅该测试文件报错可继续。若 `src/` 下有报错须就地修复（`visibleRows` 是唯一构造 `TreeRow` 的生产代码点）。

---

### Task 3: `NodeTreeRow.vue` 渲染图标+标签

**Files:**
- Modify: `frontend/src/components/editor/NodeTreeRow.vue`
- Test: `frontend/tests/unit/NodeTreeRow.spec.ts`

- [ ] **Step 1: 写失败测试**

在 `frontend/tests/unit/NodeTreeRow.spec.ts` 中，先把 `treeRow` helper 的默认 `contentKind` 补上（避免类型缺字段）：

```ts
function treeRow(over: Partial<Node> = {}, row: Partial<TreeRow> = {}): TreeRow {
  const nd = node(over)
  return { node: nd, title: '章节', contentKind: null, hasChildren: false, expanded: true, ...row }
}
```

在 `describe('NodeTreeRow', ...)` 内追加用例：

```ts
  it('table content row renders 表格 tag', () => {
    const w = mountRow(treeRow({ heading_level: null }, { contentKind: 'table' }))
    expect(w.find('.ntr-type').exists()).toBe(true)
    expect(w.find('.ntr-type').text()).toContain('表格')
  })
  it('image content row renders 图片 tag', () => {
    const w = mountRow(treeRow({ heading_level: null }, { contentKind: 'image' }))
    expect(w.find('.ntr-type').text()).toContain('图片')
  })
  it('text/chapter row renders no type tag', () => {
    const w = mountRow(treeRow({}, { contentKind: null }))
    expect(w.find('.ntr-type').exists()).toBe(false)
  })
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npx vitest run tests/unit/NodeTreeRow.spec.ts -t "type tag"`
Expected: FAIL（`.ntr-type` 不存在）

- [ ] **Step 3: 实现 — script 常量**

在 `NodeTreeRow.vue` 的 `<script setup>` 内，`import type { TreeRow }` 之后加：

```ts
import { Grid, Picture } from '@element-plus/icons-vue'

const TYPE_ICON = { table: Grid, image: Picture } as const
const TYPE_LABEL = { table: '表格', image: '图片' } as const
```

- [ ] **Step 4: 实现 — 模板插入**

在模板里 `<span class="ntr-code">{{ n.code }}</span>` 与 `<span class="ntr-title">...` 之间插入：

```vue
    <span v-if="row.contentKind" class="ntr-type" :class="`ntr-type--${row.contentKind}`">
      <el-icon><component :is="TYPE_ICON[row.contentKind]" /></el-icon>
      {{ TYPE_LABEL[row.contentKind] }}
    </span>
```

- [ ] **Step 5: 实现 — 样式**

在 `<style scoped>` 内 `.ntr-review { ... }` 之后加：

```css
.ntr-type { flex: none; display: inline-flex; align-items: center; gap: 2px; font-size: 11px; line-height: 1; padding: 1px 4px; border-radius: 3px; color: #5c6b7a; background: #eef1f4; border: 1px solid #dde3e9; }
.ntr-type .el-icon { font-size: 12px; }
```

- [ ] **Step 6: 运行测试确认通过**

Run: `npx vitest run tests/unit/NodeTreeRow.spec.ts`
Expected: PASS（新增 3 用例 + 既有用例全绿）

- [ ] **Step 7: typecheck + lint**

Run: `npx vue-tsc --noEmit && npx eslint src/components/editor/NodeTreeRow.vue src/utils/nodeTree.ts`
Expected: 无错误、无警告

---

### Task 4: 全量回归

**Files:** 无新增

- [ ] **Step 1: 跑全部前端单测**

Run: `npx vitest run`
Expected: 全绿（含 `nodeTree.spec.ts`、`NodeTreeRow.spec.ts`、`nodeTreeDnd.spec.ts` 等）

- [ ] **Step 2: 构建校验（typecheck + build）**

Run: `npm run build`
Expected: `vue-tsc --noEmit` 通过 + vite build 成功

---

## Self-Review

**Spec coverage:**
- spec §3.1 `contentKind` 函数 → Task 1 ✓
- spec §3.2 `TreeRow.contentKind` + `visibleRows` → Task 2 ✓
- spec §3.3 渲染（图标 import + 常量 + 模板）→ Task 3 Step 3/4 ✓
- spec §3.4 样式 → Task 3 Step 5 ✓
- spec §5 边界（空 body、章节行、表格+图片并存）→ Task 1 测试覆盖 ✓
- spec §6 测试（单测 + 组件测）→ Task 1/2/3 ✓
- spec §2 非目标（纯文字不打标、零后端）→ `contentKind` 纯文字返 null、改动仅 2 个 src 文件 ✓

**Placeholder scan:** 无 TBD/TODO；每个代码步含完整代码与精确命令。

**Type consistency:** `ContentKind = 'table' | 'image'`；`contentKind(): ContentKind | null` 一致；`TYPE_ICON`/`TYPE_LABEL` 键为 `table`/`image`，与类型一致；`TreeRow.contentKind: ContentKind | null` 在 Task 2 定义、Task 3 helper 与模板一致引用。

**注**：本计划不做任何 git 提交，所有改动只留在工作区（working tree），由用户自行决定后续提交。
