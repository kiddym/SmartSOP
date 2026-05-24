# 平铺逐段层级标定 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Word 导入弹窗的「层级标定」模式从「嵌套树 + 复选框 + 批量按钮」改为「按原文顺序的平铺清单 + 每行 `一级│二级│三级│正文` 分段选择器」，每行预选解析器现值，用户只点改错的行。

**Architecture:** 纯前端。新增 3 个纯函数（`flattenForMarking`/`buildTreeFromRoles`/`computeMarkIndents` + 小工具 `defaultRoleOf`）于 `importTree.ts`；标定期间以 `roleMap`（每段 id→级别）为唯一真相源、以进入时的 `markingBaseline` 快照为重建基准；离开标定模式（任何方式）统一 `buildTreeFromRoles` 重建嵌套树。删除已无调用方的 `applyLayerRole`/`applyLayerMarking` 与 `promoteNode`/`demoteNode`（平铺标定完整覆盖其能力）。

**Tech Stack:** Vue 3.4 `<script setup>` + TypeScript、Element Plus 2.7、Vitest 2 + @vue/test-utils 2、vue-tsc。

**关联 spec:** `docs/superpowers/specs/2026-05-24-flat-layer-marking-design.md`

**门禁（每个 Task 末尾 commit 前必须全绿，命令在 `frontend/` 下运行）:**
```bash
npm run lint && npm run typecheck && npm run test
```
最终任务额外跑 `npm run build`。

---

## 关键约定（实现前先读）

- **不保留子树连动**：旧 `applyLayerRole` 里"父降级、未选中的子自动跟降"在平铺模型下取消——每行独立、所见即所选。
- **`roleMap` 值类型** = `importTree.ts` 现有的 `export type LayerRole = 'chapter_1' | 'chapter_2' | 'chapter_3' | 'content'`（4 值，无 `ignored`）。
- **测试未全局注册 Element Plus**：纯文本断言（slot 文本）无需 EP；需要 `el-radio` 真正交互的测试要在该用例 `mount(..., { global: { plugins: [ElementPlus] } })`。
- **「已忽略」相关一律不动**（`ignored`/`extractIgnored`/`restoreFromIgnored`/`restoreIgnored`/`restoreAllIgnored`/底部忽略区）；本计划只移除标定模式里的「→忽略」批量按钮入口。
- **`ImportTreeRow.vue` 不改**（标定模式不再渲染它）。

---

## Task 1: 纯函数 `defaultRoleOf` + `flattenForMarking`

**Files:**
- Modify: `frontend/src/utils/importTree.ts`（在文件末尾、`applyLayerRole` 之后追加）
- Test: `frontend/tests/unit/importTree.spec.ts`（追加 describe 块）

- [ ] **Step 1: 写失败测试** — 在 `frontend/tests/unit/importTree.spec.ts` 顶部 import 增加 `defaultRoleOf, flattenForMarking` 与 `type LayerRole`，并在文件末尾追加：

```ts
import { defaultRoleOf, flattenForMarking } from '@/utils/importTree'
import type { LayerRole } from '@/utils/importTree'

describe('defaultRoleOf', () => {
  it('content→content；章节按深度（>3 夹紧 3）', () => {
    const c = buildWizardTree([pnode({ id: 'c', content_type: 'content' })])[0]
    const h = buildWizardTree([pnode({ id: 'h' })])[0]
    expect(defaultRoleOf(c, 1)).toBe('content')
    expect(defaultRoleOf(h, 1)).toBe('chapter_1')
    expect(defaultRoleOf(h, 2)).toBe('chapter_2')
    expect(defaultRoleOf(h, 5)).toBe('chapter_3')
  })
})

describe('flattenForMarking', () => {
  it('按文档前序拍平 + 默认级别映射 + 正文摘要', () => {
    const tree = buildWizardTree([
      pnode({ id: 'a', title: '目的', children: [
        pnode({ id: 'a1', title: '范围' }),
        pnode({ id: 'a2', content_type: 'content', rich_content: '<p>正文内容</p>' }),
      ] }),
      pnode({ id: 'b', title: '职责' }),
    ])
    const rows = flattenForMarking(tree)
    expect(rows.map((r) => r.id)).toEqual(['a', 'a1', 'a2', 'b'])
    expect(rows.map((r) => r.defaultRole)).toEqual(['chapter_1', 'chapter_2', 'content', 'chapter_1'])
    expect(rows[2].label).toBe('正文内容')
    expect(rows[0].label).toBe('目的')
  })

  it('深度>3 的章节默认夹紧为 chapter_3', () => {
    const tree = buildWizardTree([
      pnode({ id: 'a', children: [pnode({ id: 'b', children: [
        pnode({ id: 'c', children: [pnode({ id: 'd' })] }),
      ] })] }),
    ])
    expect(flattenForMarking(tree).find((r) => r.id === 'd')?.defaultRole).toBe('chapter_3')
  })

  it('空标题章节 label 回落（无标题）', () => {
    const tree = buildWizardTree([pnode({ id: 'a', title: '' })])
    expect(flattenForMarking(tree)[0].label).toBe('（无标题）')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run tests/unit/importTree.spec.ts`
Expected: FAIL，报 `defaultRoleOf`/`flattenForMarking` 不存在（import 解析失败）。

- [ ] **Step 3: 实现** — 在 `frontend/src/utils/importTree.ts` 末尾追加（`titleFromHtml` 已存在于本文件，`LayerRole` 类型已在本文件导出）：

```ts
// ---- 平铺逐段层级标定（import-v2 标定模式用） ---- //

export interface MarkRow {
  id: string
  label: string // 章节用 title；正文用去标签摘要
  defaultRole: LayerRole
}

// 节点 + 深度 → 解析器当前级别：content→content；章节按深度→chapter_1/2/3（夹紧 1..3）。
export function defaultRoleOf(node: WizardNode, depth: number): LayerRole {
  if (node.content_type === 'content') return 'content'
  const lv = Math.min(3, Math.max(1, depth))
  return `chapter_${lv}` as LayerRole
}

// 按文档前序遍历拍平为平铺标定行（顺序 = Word 原文顺序）。
export function flattenForMarking(nodes: WizardNode[]): MarkRow[] {
  const rows: MarkRow[] = []
  const walk = (list: WizardNode[], depth: number): void => {
    for (const n of list) {
      rows.push({
        id: n.id,
        label: n.content_type === 'content' ? titleFromHtml(n.rich_content) : n.title || '（无标题）',
        defaultRole: defaultRoleOf(n, depth),
      })
      walk(n.children, depth + 1)
    }
  }
  walk(nodes, 1)
  return rows
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run tests/unit/importTree.spec.ts`
Expected: PASS（含原有用例）。

- [ ] **Step 5: 门禁 + commit**

```bash
cd frontend && npm run lint && npm run typecheck && npm run test
git add frontend/src/utils/importTree.ts frontend/tests/unit/importTree.spec.ts
git commit -m "feat(import): add defaultRoleOf + flattenForMarking pure utils

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: 纯函数 `buildTreeFromRoles`

**Files:**
- Modify: `frontend/src/utils/importTree.ts`（末尾继续追加）
- Test: `frontend/tests/unit/importTree.spec.ts`（追加 describe 块）

- [ ] **Step 1: 写失败测试** — 顶部 import 增补 `buildTreeFromRoles`（与 `computeLevelMap`，若未引入），文件末尾追加：

```ts
import { buildTreeFromRoles } from '@/utils/importTree'
// computeLevelMap 已在其它 describe 用到则复用其 import

function rmap(obj: Record<string, LayerRole>): Map<string, LayerRole> {
  return new Map(Object.entries(obj) as [string, LayerRole][])
}

describe('buildTreeFromRoles', () => {
  it('默认级别 round-trip：结构不变', () => {
    const tree = buildWizardTree([
      pnode({ id: 'a', children: [pnode({ id: 'a1', content_type: 'content', rich_content: '<p>x</p>' })] }),
      pnode({ id: 'b' }),
    ])
    const m = new Map(flattenForMarking(tree).map((r) => [r.id, r.defaultRole]))
    const out = buildTreeFromRoles(tree, m)
    expect(out.map((n) => n.id)).toEqual(['a', 'b'])
    expect(out[0].children.map((n) => n.id)).toEqual(['a1'])
    expect(out[0].children[0].content_type).toBe('content')
  })

  it('正文挂到最近最深章节；开头即正文落根', () => {
    const tree = buildWizardTree([
      pnode({ id: 'a' }),
      pnode({ id: 'x', content_type: 'content', rich_content: '<p>x</p>' }),
    ])
    const out = buildTreeFromRoles(tree, rmap({ a: 'chapter_1', x: 'content' }))
    expect(out.map((n) => n.id)).toEqual(['a'])
    expect(out[0].children.map((n) => n.id)).toEqual(['x'])

    const tree2 = buildWizardTree([pnode({ id: 'x', content_type: 'content', rich_content: '<p>x</p>' })])
    const out2 = buildTreeFromRoles(tree2, rmap({ x: 'content' }))
    expect(out2.map((n) => n.id)).toEqual(['x'])
    expect(out2[0].content_type).toBe('content')
  })

  it('层级跳跃夹紧：chapter_2 无一级父→根级；chapter_3 无二级父→退挂一级', () => {
    const tree = buildWizardTree([pnode({ id: 'a' }), pnode({ id: 'b' })])
    const out = buildTreeFromRoles(tree, rmap({ a: 'chapter_2', b: 'chapter_3' }))
    expect(out.map((n) => n.id)).toEqual(['a'])
    expect(out[0].children.map((n) => n.id)).toEqual(['b'])
    expect(computeLevelMap(out).get('a')).toBe(1)
    expect(computeLevelMap(out).get('b')).toBe(2)
  })

  it('顺序无关：map 写入顺序不影响结果', () => {
    const tree = buildWizardTree([pnode({ id: 'A' }), pnode({ id: 'B' }), pnode({ id: 'C' })])
    const out1 = buildTreeFromRoles(tree, new Map<string, LayerRole>([['A', 'chapter_1'], ['B', 'chapter_2'], ['C', 'chapter_2']]))
    const out2 = buildTreeFromRoles(tree, new Map<string, LayerRole>([['C', 'chapter_2'], ['A', 'chapter_1'], ['B', 'chapter_2']]))
    expect(out2).toEqual(out1)
    expect(out1[0].children.map((n) => n.id)).toEqual(['B', 'C'])
  })

  it('内容升级为章节：文本作标题、清空正文、参与编号', () => {
    const tree = buildWizardTree([
      pnode({ id: 'a' }),
      pnode({ id: 'x', content_type: 'content', title: '', rich_content: '<p>操作步骤</p>' }),
    ])
    const x = buildTreeFromRoles(tree, rmap({ a: 'chapter_1', x: 'chapter_2' }))[0].children[0]
    expect(x.id).toBe('x')
    expect(x.content_type).toBe('chapter')
    expect(x.title).toBe('操作步骤')
    expect(x.rich_content).toBe('')
    expect(x.skip_numbering).toBe(false)
  })

  it('章节降级为正文：标题回填正文、skip_numbering=true', () => {
    const tree = buildWizardTree([pnode({ id: 'a', title: '操作' })])
    const out = buildTreeFromRoles(tree, rmap({ a: 'content' }))
    expect(out[0].content_type).toBe('content')
    expect(out[0].rich_content).toContain('操作')
    expect(out[0].skip_numbering).toBe(true)
  })

  it('全部设为正文：均落根且为 content', () => {
    const tree = buildWizardTree([pnode({ id: 'a' }), pnode({ id: 'b' })])
    const out = buildTreeFromRoles(tree, rmap({ a: 'content', b: 'content' }))
    expect(out.map((n) => n.id)).toEqual(['a', 'b'])
    expect(out.every((n) => n.content_type === 'content')).toBe(true)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run tests/unit/importTree.spec.ts`
Expected: FAIL，`buildTreeFromRoles` 不存在。

- [ ] **Step 3: 实现** — 在 `frontend/src/utils/importTree.ts` 末尾追加（承接 `applyLayerRole` 的重建算法，但每段显式取级别、不做子树连动）：

```ts
// 用「每段 id → 目标级别」映射表从基准树按文档序重建嵌套树。
// 每段都有显式级别（缺失回落 defaultRoleOf）；章节挂最近可达父、正文挂最深章节；
// 不可达层级夹紧（chapter_2 无一级父→根级；chapter_3 无二级父→退挂一级）；内容↔章节互转保数据。
export function buildTreeFromRoles(
  nodes: WizardNode[],
  roleMap: Map<string, LayerRole>,
): WizardNode[] {
  interface Flat { node: WizardNode; role: LayerRole }
  const flat: Flat[] = []
  const walk = (list: WizardNode[], depth: number): void => {
    for (const n of list) {
      flat.push({ node: n, role: roleMap.get(n.id) ?? defaultRoleOf(n, depth) })
      walk(n.children, depth + 1)
    }
  }
  walk(nodes, 1)

  const roots: WizardNode[] = []
  let l1: WizardNode | null = null
  let l2: WizardNode | null = null
  let l3: WizardNode | null = null

  for (const { node, role } of flat) {
    const asChapter = role !== 'content'
    const level = role === 'chapter_3' ? 3 : role === 'chapter_2' ? 2 : 1
    const fromContent = asChapter && node.content_type === 'content'
    const toContentNode = !asChapter && node.content_type === 'chapter'
    const fresh: WizardNode = {
      ...node,
      content_type: asChapter ? 'chapter' : 'content',
      title: fromContent ? node.title.trim() || titleFromHtml(node.rich_content) : node.title,
      rich_content: asChapter
        ? ''
        : toContentNode
          ? node.rich_content || (node.title.trim() ? `<p>${node.title.trim()}</p>` : '')
          : node.rich_content,
      skip_numbering: asChapter ? (fromContent ? false : node.skip_numbering) : true,
      children: [],
    }

    if (!asChapter) {
      const parent = l3 ?? l2 ?? l1
      if (parent) parent.children.push(fresh)
      else roots.push(fresh)
      continue
    }

    if (level >= 3 && l2) {
      l2.children.push(fresh)
      l3 = fresh
    } else if (level >= 2 && l1) {
      l1.children.push(fresh)
      l2 = fresh
      l3 = null
    } else {
      roots.push(fresh)
      l1 = fresh
      l2 = null
      l3 = null
    }
  }

  return roots
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run tests/unit/importTree.spec.ts`
Expected: PASS。

- [ ] **Step 5: 门禁 + commit**

```bash
cd frontend && npm run lint && npm run typecheck && npm run test
git add frontend/src/utils/importTree.ts frontend/tests/unit/importTree.spec.ts
git commit -m "feat(import): add buildTreeFromRoles pure rebuild util

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 纯函数 `computeMarkIndents`

**Files:**
- Modify: `frontend/src/utils/importTree.ts`（末尾继续追加）
- Test: `frontend/tests/unit/importTree.spec.ts`（追加 describe 块）

- [ ] **Step 1: 写失败测试** — 顶部 import 增补 `computeMarkIndents`，文件末尾追加：

```ts
import { computeMarkIndents } from '@/utils/importTree'

describe('computeMarkIndents', () => {
  it('章节缩进=level-1；正文比当前标题深一级', () => {
    const rows = [
      { id: 'a', label: 'A', defaultRole: 'chapter_1' as LayerRole },
      { id: 'b', label: 'B', defaultRole: 'chapter_2' as LayerRole },
      { id: 'x', label: 'X', defaultRole: 'content' as LayerRole },
      { id: 'c', label: 'C', defaultRole: 'chapter_1' as LayerRole },
    ]
    const m = computeMarkIndents(rows, new Map(rows.map((r) => [r.id, r.defaultRole])))
    expect(m.get('a')).toBe(0)
    expect(m.get('b')).toBe(1)
    expect(m.get('x')).toBe(2)
    expect(m.get('c')).toBe(0)
  })

  it('开头即正文（无标题）缩进 0', () => {
    const m = computeMarkIndents(
      [{ id: 'x', label: 'X', defaultRole: 'content' as LayerRole }],
      new Map([['x', 'content' as LayerRole]]),
    )
    expect(m.get('x')).toBe(0)
  })

  it('roleMap 覆盖默认：b 改正文后挂在一级标题 a 下（缩进 1）', () => {
    const rows = [
      { id: 'a', label: 'A', defaultRole: 'chapter_1' as LayerRole },
      { id: 'b', label: 'B', defaultRole: 'chapter_2' as LayerRole },
    ]
    const m = computeMarkIndents(rows, new Map<string, LayerRole>([['a', 'chapter_1'], ['b', 'content']]))
    expect(m.get('b')).toBe(1)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run tests/unit/importTree.spec.ts`
Expected: FAIL，`computeMarkIndents` 不存在。

- [ ] **Step 3: 实现** — 在 `frontend/src/utils/importTree.ts` 末尾追加：

```ts
// 平铺清单的「所见即所选」缩进：章节缩进 = 字面 level-1；正文 = 当前标题 level（深一级）。
export function computeMarkIndents(
  rows: MarkRow[],
  roleMap: Map<string, LayerRole>,
): Map<string, number> {
  const map = new Map<string, number>()
  let headingLevel = 0
  for (const row of rows) {
    const role = roleMap.get(row.id) ?? row.defaultRole
    if (role === 'content') {
      map.set(row.id, headingLevel)
    } else {
      const lv = role === 'chapter_3' ? 3 : role === 'chapter_2' ? 2 : 1
      map.set(row.id, lv - 1)
      headingLevel = lv
    }
  }
  return map
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run tests/unit/importTree.spec.ts`
Expected: PASS。

- [ ] **Step 5: 门禁 + commit**

```bash
cd frontend && npm run lint && npm run typecheck && npm run test
git add frontend/src/utils/importTree.ts frontend/tests/unit/importTree.spec.ts
git commit -m "feat(import): add computeMarkIndents pure util

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: 新组件 `ImportMarkingRow.vue`

平铺清单的单行：左侧 `el-radio-group` 分段选择器（一级/二级/三级/正文）+ 缩进 + 文本。尚未被任何处引用（下一任务接入）。

**Files:**
- Create: `frontend/src/components/import-v2/ImportMarkingRow.vue`
- Test: `frontend/tests/unit/ImportMarkingRow.spec.ts`

- [ ] **Step 1: 写失败测试** — 创建 `frontend/tests/unit/ImportMarkingRow.spec.ts`：

```ts
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ElementPlus from 'element-plus'
import ImportMarkingRow from '@/components/import-v2/ImportMarkingRow.vue'

const base = { label: '目的', role: 'chapter_1' as const, indent: 0 }

describe('ImportMarkingRow', () => {
  it('渲染四个级别选项 + 文本', () => {
    const w = mount(ImportMarkingRow, { props: base })
    const t = w.text()
    expect(t).toContain('一级')
    expect(t).toContain('二级')
    expect(t).toContain('三级')
    expect(t).toContain('正文')
    expect(t).toContain('目的')
  })

  it('点击某级别 → emit set（需真实 Element Plus）', async () => {
    const w = mount(ImportMarkingRow, { props: base, global: { plugins: [ElementPlus] } })
    const inners = w.findAll('.el-radio-button__inner')
    expect(inners.length).toBe(4)
    await inners[3].trigger('click') // 正文
    expect(w.emitted('set')?.[0]).toEqual(['content'])
  })

  it('缩进随 indent 变化（indent*16+8 px）', () => {
    const w = mount(ImportMarkingRow, { props: { ...base, indent: 2 } })
    expect((w.find('.mr').element as HTMLElement).style.paddingLeft).toBe('40px')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run tests/unit/ImportMarkingRow.spec.ts`
Expected: FAIL，组件文件不存在。

- [ ] **Step 3: 实现** — 创建 `frontend/src/components/import-v2/ImportMarkingRow.vue`：

```vue
<script setup lang="ts">
import type { LayerRole } from '@/utils/importTree'

defineProps<{
  label: string
  role: LayerRole
  indent: number
}>()
const emit = defineEmits<{ (e: 'set', role: LayerRole): void }>()

const OPTIONS: { value: LayerRole; text: string }[] = [
  { value: 'chapter_1', text: '一级' },
  { value: 'chapter_2', text: '二级' },
  { value: 'chapter_3', text: '三级' },
  { value: 'content', text: '正文' },
]

function onChange(v: string | number | boolean): void {
  emit('set', v as LayerRole)
}
</script>

<template>
  <div class="mr" :style="{ paddingLeft: `${indent * 16 + 8}px` }">
    <el-radio-group :model-value="role" size="small" class="mr-roles" @change="onChange">
      <el-radio-button v-for="o in OPTIONS" :key="o.value" :value="o.value">{{ o.text }}</el-radio-button>
    </el-radio-group>
    <span class="mr-title">{{ label }}</span>
  </div>
</template>

<style scoped>
.mr {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  padding: 4px 8px;
  border-bottom: 1px solid var(--el-border-color-lighter, #f0f0f0);
  font-size: 13px;
}
.mr:hover { background: #f5f7fa; }
.mr-roles { flex: none; }
.mr-title {
  flex: 0 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #303133;
}
</style>
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run tests/unit/ImportMarkingRow.spec.ts`
Expected: PASS（3 个用例）。若 `.el-radio-button__inner` 点击未触发 emit，改用 `await w.find('input[value="content"]').setValue(true)` 后再断言。

- [ ] **Step 5: 门禁 + commit**

```bash
cd frontend && npm run lint && npm run typecheck && npm run test
git add frontend/src/components/import-v2/ImportMarkingRow.vue frontend/tests/unit/ImportMarkingRow.spec.ts
git commit -m "feat(import): add ImportMarkingRow segmented level selector

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: 接入平铺标定 + 移除旧批量/提升降级（协同改动，单次提交）

本任务多文件互相依赖（接口变更），中间态可能不通过 typecheck；以**任务末尾的完整门禁**为准。建议按以下顺序改完再统一跑门禁。

**Files:**
- Modify: `frontend/src/composables/useImportDialog.ts`（整文件替换）
- Modify: `frontend/src/components/import-v2/ImportTreePanel.vue`（整文件替换）
- Modify: `frontend/src/components/import-v2/ImportDialog.vue`（删 Tab 键处理）
- Modify: `frontend/src/utils/importTree.ts`（删 `applyLayerRole`/`clampLevel`/`promoteNode`/`demoteNode`）
- Delete: `frontend/tests/unit/applyLayerRole.spec.ts`
- Modify: `frontend/tests/unit/importTreeOps.spec.ts`（删 promote/demote 用例与 import）
- Modify: `frontend/tests/unit/useImportDialog.spec.ts`（删 applyLayerMarking 用例、改 restoreIgnored、加新用例）
- Modify: `frontend/tests/unit/ImportTreePanel.spec.ts`（改写 layer-marking 工具条断言）

- [ ] **Step 1: 整文件替换 `frontend/src/composables/useImportDialog.ts`**

```ts
import { computed, reactive, ref } from 'vue'
import type { ParseResponse } from '@/types/parse'
import type { ContentType, MarkStatus } from '@/types/node'
import {
  addChildNode,
  addSiblingNode,
  buildTreeFromRoles,
  buildWizardTree,
  cloneTree,
  computeChapterNumbers,
  computeLevelMap,
  computeMarkIndents,
  countReview,
  deleteNode,
  findNode,
  flattenForMarking,
  moveNode,
  restoreFromIgnored,
  setMarkStatus,
  updateNode,
  type LayerRole,
  type MarkRow,
  type WizardNode,
} from '@/utils/importTree'

export type ImportDialogMode = 'normal' | 'layer-marking' | 'step-annotation'

export function useImportDialog() {
  // ---- 文件 / 解析 ---- //
  const file = ref<File | null>(null)
  const uploadToken = ref('')
  const filename = ref('')
  const parseResult = ref<ParseResponse | null>(null)

  // ---- 树状态 ---- //
  const tree = ref<WizardNode[]>([])
  const ignored = ref<WizardNode[]>([])
  const selectedId = ref<string | null>(null)

  // ---- 模式 / 标记选择 ---- //
  const mode = ref<ImportDialogMode>('normal')
  const markSelection = ref<Set<string>>(new Set())

  // ---- 层级标定（平铺逐段） ---- //
  const roleMap = ref<Map<string, LayerRole>>(new Map())
  const markingBaseline = ref<WizardNode[] | null>(null)

  // ---- 表单 ---- //
  const form = reactive({ name: '', folder_id: '' })

  // ---- 派生 ---- //
  const selected = computed(() => (selectedId.value ? findNode(tree.value, selectedId.value) : null))
  const levelMap = computed(() => computeLevelMap(tree.value))
  const numberMap = computed(() => computeChapterNumbers(tree.value))
  const reviewCount = computed(() => countReview(tree.value))
  const markRows = computed<MarkRow[]>(() =>
    markingBaseline.value ? flattenForMarking(markingBaseline.value) : [],
  )
  const markIndents = computed(() => computeMarkIndents(markRows.value, roleMap.value))

  // ---- 模式切换 ---- //
  // 离开层级标定（任何方式：完成 / 再点按钮 / Esc / 切到步骤标注）统一以 baseline 为基准重建，
  // 改动总会保留；没有"丢弃"路径，整体反悔用「↺ 重置」。
  function applyAndClearMarking(): void {
    if (markingBaseline.value) {
      tree.value = buildTreeFromRoles(markingBaseline.value, roleMap.value)
    }
    roleMap.value = new Map()
    markingBaseline.value = null
  }

  function exitMode(): void {
    if (mode.value === 'layer-marking') applyAndClearMarking()
    mode.value = 'normal'
    markSelection.value = new Set()
  }

  function enterLayerMarking(): void {
    markingBaseline.value = cloneTree(tree.value)
    const m = new Map<string, LayerRole>()
    for (const r of flattenForMarking(markingBaseline.value)) m.set(r.id, r.defaultRole)
    roleMap.value = m
    mode.value = 'layer-marking'
    markSelection.value = new Set()
  }

  function toggleLayerMarking(): void {
    if (mode.value === 'layer-marking') exitMode()
    else enterLayerMarking()
  }

  function toggleStepAnnotation(): void {
    if (mode.value === 'step-annotation') {
      exitMode()
    } else {
      exitMode() // 若正处于层级标定，先统一生效再切换
      mode.value = 'step-annotation'
      markSelection.value = new Set()
    }
  }

  function setRole(id: string, role: LayerRole): void {
    const next = new Map(roleMap.value)
    next.set(id, role)
    roleMap.value = next
  }

  function toggleMarkSelection(id: string): void {
    const next = new Set(markSelection.value)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    markSelection.value = next
  }

  function clearMarkSelection(): void {
    markSelection.value = new Set()
  }

  // ---- 装载 / 树编辑 ---- //
  function loadParseResult(res: ParseResponse): void {
    parseResult.value = res
    tree.value = buildWizardTree(res.chapters)
    ignored.value = []
    selectedId.value = null
    if (!form.name) {
      form.name = filename.value.replace(/\.docx$/i, '').trim()
    }
  }

  function selectNode(id: string | null): void {
    selectedId.value = id
  }

  function moveSelected(dir: -1 | 1): void {
    if (!selectedId.value) return
    tree.value = moveNode(tree.value, selectedId.value, dir)
  }

  function deleteSelected(): void {
    if (!selectedId.value) return
    tree.value = deleteNode(tree.value, selectedId.value)
    selectedId.value = null
  }

  function addChild(parentId: string | null, type: ContentType): void {
    tree.value = addChildNode(tree.value, parentId, type)
  }

  function addSibling(siblingId: string, type: ContentType): void {
    tree.value = addSiblingNode(tree.value, siblingId, type)
  }

  function updateSelectedFields(patch: { title?: string; skip_numbering?: boolean; mark_status?: MarkStatus }): void {
    if (!selectedId.value) return
    tree.value = updateNode(tree.value, selectedId.value, patch)
  }

  // ---- 步骤标注动作 ---- //
  function applyStepAnnotation(role: 'step' | 'content'): void {
    const ids = [...markSelection.value]
    if (ids.length === 0) return
    tree.value = setMarkStatus(tree.value, ids, role)
    exitMode()
  }

  function clearStepAnnotation(): void {
    const ids = [...markSelection.value]
    if (ids.length === 0) return
    tree.value = setMarkStatus(tree.value, ids, 'unmarked')
    exitMode()
  }

  // ---- 忽略项恢复（保留：删除走普通模式永久删除，恢复机制不变） ---- //
  function restoreIgnored(id: string): void {
    const idx = ignored.value.findIndex((n) => n.id === id)
    if (idx === -1) return
    const node = ignored.value[idx]
    ignored.value = ignored.value.filter((_, i) => i !== idx)
    tree.value = restoreFromIgnored(tree.value, [node])
  }

  function restoreAllIgnored(): void {
    if (ignored.value.length === 0) return
    tree.value = restoreFromIgnored(tree.value, ignored.value)
    ignored.value = []
  }

  // ---- 接受 review ---- //
  function acceptReview(id: string): void {
    tree.value = updateNode(tree.value, id, { mark_status: 'unmarked' })
  }

  return {
    // state
    file, uploadToken, filename, parseResult,
    tree, ignored, selectedId, mode, markSelection, form,
    roleMap, markingBaseline,
    // derived
    selected, levelMap, numberMap, reviewCount, markRows, markIndents,
    // mode
    toggleLayerMarking, toggleStepAnnotation, exitMode,
    toggleMarkSelection, clearMarkSelection, setRole,
    // tree actions
    loadParseResult, selectNode, moveSelected, deleteSelected,
    addChild, addSibling, updateSelectedFields,
    // step annotation
    applyStepAnnotation, clearStepAnnotation,
    // ignored
    restoreIgnored, restoreAllIgnored,
    // review
    acceptReview,
  }
}
```

- [ ] **Step 2: 整文件替换 `frontend/src/components/import-v2/ImportTreePanel.vue`**

```vue
<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import ImportTreeRow from './ImportTreeRow.vue'
import ImportMarkingRow from './ImportMarkingRow.vue'
import type { useImportDialog } from '@/composables/useImportDialog'

const props = defineProps<{ ctx: ReturnType<typeof useImportDialog> }>()

const search = ref('')

// 把树压平成可渲染的 FlatRow（含 depth 与可上下移标志）
interface FlatRow {
  node: typeof props.ctx.tree.value[0]
  depth: number
  canMoveUp: boolean
  canMoveDown: boolean
}

function flatten(nodes: typeof props.ctx.tree.value, depth = 0): FlatRow[] {
  const rows: FlatRow[] = []
  nodes.forEach((n, i) => {
    rows.push({
      node: n,
      depth,
      canMoveUp: i > 0,
      canMoveDown: i < nodes.length - 1,
    })
    rows.push(...flatten(n.children, depth + 1))
  })
  return rows
}

const allRows = computed(() => flatten(props.ctx.tree.value))
const visibleRows = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return allRows.value
  return allRows.value.filter((r) =>
    `${r.node.title} ${r.node.rich_content}`.toLowerCase().includes(q),
  )
})

// 平铺标定清单（按搜索过滤；行顺序恒为原文顺序）
const visibleMarkRows = computed(() => {
  const q = search.value.trim().toLowerCase()
  const rows = props.ctx.markRows.value
  if (!q) return rows
  return rows.filter((r) => r.label.toLowerCase().includes(q))
})

function checked(id: string): boolean {
  return props.ctx.markSelection.value.has(id)
}

function levelOf(id: string): string {
  const L = ['', '一级章节', '二级章节', '三级章节']
  const lv = props.ctx.levelMap.value.get(id) ?? 0
  return L[Math.min(lv, 3)] || ''
}

function onMove(id: string, dir: -1 | 1): void {
  props.ctx.selectNode(id)
  props.ctx.moveSelected(dir)
}

async function onRemove(id: string): Promise<void> {
  try {
    await ElMessageBox.confirm('删除该节点及其全部子节点？', '删除确认', { type: 'warning' })
    props.ctx.selectNode(id)
    props.ctx.deleteSelected()
  } catch { /* user cancelled */ }
}

async function onReset(): Promise<void> {
  try {
    await ElMessageBox.confirm('放弃当前所有调整，恢复为初始解析结果？', '重置确认', { type: 'warning' })
    if (props.ctx.parseResult.value) props.ctx.loadParseResult(props.ctx.parseResult.value)
  } catch { /* cancel */ }
}

async function onApplyStepAnnotation(): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `将 ${props.ctx.markSelection.value.size} 个节点标注为「步骤」？提交导入时会一并转换。`,
      '应用标注',
      { type: 'warning' },
    )
    props.ctx.applyStepAnnotation('step')
  } catch { /* cancel */ }
}
</script>

<template>
  <div class="tree-panel">
    <!-- Row① 固定工具栏 -->
    <div class="tb-row">
      <el-input v-model="search" size="small" placeholder="搜索章节 / 步骤..." clearable class="search" />
      <span class="spacer" />
      <el-button
        size="small"
        :type="ctx.mode.value === 'layer-marking' ? 'primary' : ''"
        @click="ctx.toggleLayerMarking"
      >🏷 层级标定</el-button>
      <el-button
        size="small"
        :type="ctx.mode.value === 'step-annotation' ? 'warning' : ''"
        @click="ctx.toggleStepAnnotation"
      >⚑ 步骤标注</el-button>
      <el-button size="small" @click="onReset">↺ 重置</el-button>
    </div>

    <!-- Row② 动态条 -->
    <div class="tb-row tb-row-dynamic">
      <template v-if="ctx.mode.value === 'normal'">
        <template v-if="!ctx.selected.value">
          <span class="ctx-label">根级：</span>
          <el-button size="small" @click="ctx.addChild(null, 'chapter')">+章节</el-button>
          <el-button size="small" @click="ctx.addChild(null, 'content')">+内容</el-button>
        </template>
        <template v-else>
          <span class="ctx-label">「{{ levelOf(ctx.selected.value.id) }} · {{ ctx.selected.value.title || '（无标题）' }}」：</span>
          <el-button size="small" @click="ctx.addChild(ctx.selectedId.value!, 'chapter')">+子章节</el-button>
          <el-button size="small" @click="ctx.addChild(ctx.selectedId.value!, 'content')">+内容</el-button>
        </template>
      </template>

      <template v-else-if="ctx.mode.value === 'layer-marking'">
        <span class="ctx-label">逐段选择级别（只需改解析错的行）：</span>
        <span class="spacer" />
        <el-button size="small" type="primary" @click="ctx.exitMode">完成</el-button>
      </template>

      <template v-else>
        <el-button size="small" @click="ctx.exitMode">← 退出</el-button>
        <span class="ctx-label">已选 {{ ctx.markSelection.value.size }} 项：</span>
        <el-button size="small" type="warning" :disabled="!ctx.markSelection.value.size" @click="onApplyStepAnnotation">→ 步骤</el-button>
        <el-button size="small" :disabled="!ctx.markSelection.value.size" @click="ctx.applyStepAnnotation('content')">→ 内容</el-button>
        <el-button size="small" :disabled="!ctx.markSelection.value.size" @click="ctx.clearStepAnnotation">清除标注</el-button>
      </template>
    </div>

    <!-- 树体 / 平铺标定清单 -->
    <div class="tree-scroll">
      <template v-if="ctx.mode.value === 'layer-marking'">
        <ImportMarkingRow
          v-for="row in visibleMarkRows"
          :key="row.id"
          :label="row.label"
          :role="ctx.roleMap.value.get(row.id) ?? row.defaultRole"
          :indent="ctx.markIndents.value.get(row.id) ?? 0"
          @set="(r) => ctx.setRole(row.id, r)"
        />
        <el-empty v-if="!visibleMarkRows.length" description="无可标定内容" :image-size="60" />
      </template>
      <template v-else>
        <ImportTreeRow
          v-for="row in visibleRows"
          :key="row.node.id"
          :node="row.node"
          :depth="row.depth"
          :level="ctx.levelMap.value.get(row.node.id) ?? 1"
          :number="ctx.numberMap.value[row.node.id] ?? ''"
          :selected="ctx.selectedId.value === row.node.id"
          :mode="ctx.mode.value"
          :checked="checked(row.node.id)"
          :can-move-up="row.canMoveUp"
          :can-move-down="row.canMoveDown"
          @select="ctx.mode.value === 'normal' ? ctx.selectNode(row.node.id) : ctx.toggleMarkSelection(row.node.id)"
          @check="() => ctx.toggleMarkSelection(row.node.id)"
          @move="(dir) => onMove(row.node.id, dir)"
          @remove="onRemove(row.node.id)"
        />
        <el-empty v-if="!visibleRows.length" description="树为空" :image-size="60" />
      </template>
    </div>

    <!-- 底部忽略区（保留：仅展示/恢复，已无新增入口） -->
    <div v-if="ctx.ignored.value.length" class="ignored-bar">
      <el-collapse>
        <el-collapse-item :title="`已忽略 (${ctx.ignored.value.length} 项)`" name="ig">
          <div v-for="n in ctx.ignored.value" :key="n.id" class="ignored-row">
            <el-tag size="small" type="info" disable-transitions>忽略</el-tag>
            <span class="ig-text">{{ n.title || '(无标题)' }}</span>
            <span class="spacer" />
            <el-button size="small" text @click="ctx.restoreIgnored(n.id)">恢复</el-button>
          </div>
          <div class="ignored-footer">
            <el-button size="small" @click="ctx.restoreAllIgnored">全部恢复</el-button>
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>
  </div>
</template>

<style scoped>
.tree-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  border-right: 1px solid var(--el-border-color-lighter, #ebeef5);
}
.tb-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px;
  min-height: 44px;
  border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
}
.tb-row-dynamic { background: #fafbfc; }
.search { max-width: 240px; }
.spacer { flex: 1; }
.ctx-label { font-size: 12px; color: #606266; margin-right: 4px; }
.tree-scroll { flex: 1; overflow-y: auto; }
.ignored-bar { border-top: 1px solid var(--el-border-color-lighter, #ebeef5); background: #fafafa; }
.ignored-row { display: flex; align-items: center; gap: 8px; padding: 4px 12px; font-size: 13px; color: #606266; }
.ig-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 360px; }
.ignored-footer { padding: 6px 12px; text-align: right; }
</style>
```

- [ ] **Step 3: 删 `ImportDialog.vue` 的 Tab 键处理** — 在 `frontend/src/components/import-v2/ImportDialog.vue` 把这段：

```ts
  if (ev.key === 'Delete' && ctx.selectedId.value) {
    ctx.deleteSelected()
    ev.preventDefault()
    return
  }
  if (ev.key === 'Tab' && ctx.selectedId.value) {
    if (ev.shiftKey) ctx.promoteSelected()
    else ctx.demoteSelected()
    ev.preventDefault()
  }
}
```

改为（删除整个 Tab 分支）：

```ts
  if (ev.key === 'Delete' && ctx.selectedId.value) {
    ctx.deleteSelected()
    ev.preventDefault()
  }
}
```

- [ ] **Step 4: 删 `importTree.ts` 中已无调用方的函数** — 在 `frontend/src/utils/importTree.ts`：
  - 删除 `promoteNode`（含其上注释 `// 提升节点：...`，约原 199–236 行）。
  - 删除 `demoteNode`（含其上注释 `// 降级节点：...`，约原 238–252 行）。
  - 删除 `const clampLevel = ...`（约原 314 行）。
  - 删除 `applyLayerRole` 函数及其上方的大段注释（约原 316–409 行）。
  - **保留** `export type LayerRole = ...`（约原 312 行）、`findParent`、`titleFromHtml`、`extractIgnored`、`restoreFromIgnored`，以及 Task 1–3 追加的新函数。

- [ ] **Step 5: 删测试文件 `applyLayerRole.spec.ts`**

```bash
git rm frontend/tests/unit/applyLayerRole.spec.ts
```

- [ ] **Step 6: 改 `importTreeOps.spec.ts`** — 删 import 里的 `demoteNode,` 与 `promoteNode,` 两行；删除这 5 个 `it(...)` 用例：
  - `it('promoteNode 把子节点提升到父的同级（紧跟父之后）', ...)`
  - `it('promoteNode 根节点 no-op', ...)`
  - `it('demoteNode 把节点降为前一个同级的最后一个子', ...)`
  - `it('demoteNode 同级首位 no-op（无前一个同级）', ...)`
  - `it('demoteNode 根级首位 no-op', ...)`

  其余用例（findParent / computeLevelMap / addChildNode / addSiblingNode / setMarkStatus / extractIgnored / restoreFromIgnored）全部保留。

- [ ] **Step 7: 改 `useImportDialog.spec.ts`**
  - 删除这 5 个 applyLayerMarking 用例：`'applyLayerMarking 把 markSelection 内节点设为目标层级'`、`'applyLayerMarking 多选标二级：与点选顺序无关，都挂到首章节下'`、`'applyLayerMarking 前驱为正文时不把章节嵌进正文'`、`'applyLayerMarking →正文 把节点类型改 content'`、`'applyLayerMarking →忽略 把节点移到 ignored'`。
  - 把 `'restoreIgnored 把单个忽略项恢复到根末尾'` 用例整体替换为（不再依赖已删除的 applyLayerMarking）：

```ts
  it('restoreIgnored 把单个忽略项恢复到根末尾', () => {
    const d = useImportDialog()
    d.loadParseResult(mkParse([pnode({ id: 'a' })]))
    // 直接预置一个忽略项（标定模式不再提供忽略入口）
    d.ignored.value = [{
      id: 'z', title: 'Z', content_type: 'chapter', rich_content: '',
      skip_numbering: false, mark_status: 'unmarked', confidence_tier: 'high', children: [],
    }]
    d.restoreIgnored('z')
    expect(d.tree.value.map((n) => n.id)).toEqual(['a', 'z'])
    expect(d.ignored.value).toHaveLength(0)
  })
```

  - 在 `describe('useImportDialog 装载与编辑', ...)` 内追加三个新用例：

```ts
  it('层级标定：setRole 改级别，离开模式时统一生效', () => {
    const d = useImportDialog()
    d.loadParseResult(mkParse([pnode({ id: 'a' }), pnode({ id: 'b' })]))
    d.toggleLayerMarking()
    expect(d.mode.value).toBe('layer-marking')
    expect(d.roleMap.value.get('b')).toBe('chapter_1') // 预填默认
    d.setRole('b', 'chapter_2')
    d.toggleLayerMarking() // 离开 → 生效
    expect(d.mode.value).toBe('normal')
    expect(d.levelMap.value.get('b')).toBe(2)
    expect(d.tree.value.find((n) => n.id === 'a')?.children.map((n) => n.id)).toEqual(['b'])
  })

  it('层级标定：切到步骤标注也会生效改动', () => {
    const d = useImportDialog()
    d.loadParseResult(mkParse([pnode({ id: 'a' })]))
    d.toggleLayerMarking()
    d.setRole('a', 'content')
    d.toggleStepAnnotation() // 切走 → 应已生效
    expect(d.tree.value[0].content_type).toBe('content')
  })

  it('markRows 预填解析级别；markIndents 按字面级别给缩进', () => {
    const d = useImportDialog()
    d.loadParseResult(mkParse([
      pnode({ id: 'a', children: [pnode({ id: 'a1', content_type: 'content', rich_content: '<p>x</p>' })] }),
    ]))
    d.toggleLayerMarking()
    expect(d.markRows.value.map((r) => r.id)).toEqual(['a', 'a1'])
    expect(d.roleMap.value.get('a')).toBe('chapter_1')
    expect(d.roleMap.value.get('a1')).toBe('content')
    expect(d.markIndents.value.get('a')).toBe(0)
    expect(d.markIndents.value.get('a1')).toBe(1)
  })
```

- [ ] **Step 8: 改 `ImportTreePanel.spec.ts`** — 把 `it('layer-marking 模式：Row② 显示批量按钮', ...)` 整体替换为：

```ts
  it('layer-marking 模式：Row② 显示「完成」，不再有批量/忽略按钮', () => {
    const ctx = useImportDialog()
    ctx.toggleLayerMarking()
    const w = mount(ImportTreePanel, { props: { ctx } })
    expect(w.text()).toContain('完成')
    expect(w.text()).not.toContain('→一级')
    expect(w.text()).not.toContain('→忽略')
  })

  it('layer-marking 模式：加载树后每段渲染级别选择器', () => {
    const ctx = useImportDialog()
    ctx.loadParseResult({
      metadata: { total_chapters: 1, image_count: 0, table_count: 0, body_start_index: 0,
        body_start_detected_by: '', format: 'docx', parse_time_ms: 0 },
      chapters: [{
        id: 'a', title: '目的', level: 1, order: 0, parent_id: null, content_type: 'chapter',
        rich_content: '', skip_numbering: false, confidence: 1, confidence_tier: 'high',
        mark_status: 'unmarked', heading_source: null, children: [],
      }],
      import_blocks: [], assets: [], detected_patterns: [], validation: null,
      warnings: [], review_required: 0, parse_method: 'smart',
    })
    ctx.toggleLayerMarking()
    const w = mount(ImportTreePanel, { props: { ctx } })
    const t = w.text()
    expect(t).toContain('一级')
    expect(t).toContain('正文')
    expect(t).toContain('目的')
  })
```

  > 说明：第二个用例用文本断言（slot 文本无需注册 Element Plus）；若 `ParseResponse` 字段与 `@/types/parse` 不符，照该类型补齐。

- [ ] **Step 9: 跑完整门禁**

Run:
```bash
cd frontend && npm run lint && npm run typecheck && npm run test && npm run build
```
Expected: 全部成功，0 失败。常见需修：删函数后残留的未用 import（lint 会报）、`ParseResponse` 字段不匹配（按类型补齐）。

- [ ] **Step 10: commit**

```bash
git add -A
git commit -m "feat(import): flat per-row layer marking; drop batch & promote/demote

Replace layer-marking nested-tree + checkbox + batch buttons with a flat
document-order list of ImportMarkingRow segmented selectors. roleMap +
markingBaseline drive a single rebuild on leaving the mode (any exit
applies; reset to undo all). Remove applyLayerRole/applyLayerMarking and
promoteNode/demoteNode (Tab shortcut) — fully covered by per-row marking.
Keep the ignored bar/restore untouched.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: 手动冒烟验证

- [ ] **Step 1: 起前端**

Run: `cd frontend && npm run dev`，浏览器开 `http://localhost:5173`。

- [ ] **Step 2: 走查导入流程**
  1. 打开「从 Word 导入」，上传一个标题层级解析不准的 .docx。
  2. 点「🏷 层级标定」→ 中栏变为**平铺清单**：每段一行、原文顺序、左侧 `一级│二级│三级│正文` 分段按钮已**预选解析现值**。
  3. 改几行错的级别 → 缩进随所选**实时变化、行不跳动**。
  4. 点「完成」回到嵌套树 → 结构按所选重建（层级跳跃被夹紧）。
  5. 重新进标定、改几行、按 **Esc** 或再点「层级标定」或切「步骤标注」→ 改动**都保留**（无丢弃）。
  6. 普通模式下选中节点：动态条**没有「提升/降级」**；Tab/Shift+Tab 不再改层级。
  7. 「↺ 重置」可整体回到初始解析。

- [ ] **Step 3:** 如有问题回到对应 Task 修复并补测试；无问题则完成。

---

## Self-Review（写计划后自检，已核对）

- **Spec 覆盖**：平铺清单(Task5)、分段选择器(Task4)、预填默认(Task1/composable)、所见即所选缩进(Task3)、离开统一生效+baseline(composable)、层级跳跃夹紧(Task2)、删提升/降级(Task5)、删忽略按钮+保留恢复(Task5)、内容↔章节互转(Task2)、测试(各 Task) —— 均有对应任务。
- **占位符**：无 TBD/TODO；每个改代码的步骤均含完整代码或精确增删指令。
- **类型一致**：`LayerRole`(4 值，importTree 导出)、`MarkRow`、`roleMap: Map<string,LayerRole>`、`markingBaseline`、`buildTreeFromRoles(nodes, roleMap)`、`flattenForMarking`、`computeMarkIndents`、`defaultRoleOf(node, depth)`、`setRole(id, role)` 在 util/composable/组件/测试间一致。
- **绿色提交边界**：Task1–4 各自独立全绿；Task5 为接口变更协同改动，以末尾完整门禁为准。
