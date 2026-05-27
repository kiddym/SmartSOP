# Layer-Mode Tree Overlay 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把「层级标定」(layer marking) 模式从独立替换视图改造为 TreeRow 叠加层——与「标记模式」(mark mode) 的渲染模型对齐——同时把「叶子(step/content) → 章节(chapter)」的提升能力作为角色选项纳入层级标定。

**Architecture:** TreeRow 新增 `:layer-mode` prop，在层级标定状态下隐藏 `.tr-actions`、改渲染 4 项角色选择器（chapter 行与 leaf 行选项集不同）。ChapterTreePanel 在 layer 模式下持有 `roleMap`，把 `computeLayerIndents` 算出的实时缩进通过 `:indent-override` 喂给 TreeRow（保留现有「应用前看到新形」的 live preview UX）。`store.applyLayerRoles` 重写为 async：先调 `validateLayerQ25` 做 dry-run 校验，把冲突回传 UI；用户确认无冲突再按文档序分发「叶子→章节」(`convertStepToChapter` API) + 「章节重排」+ 「章节→content」三类操作。content 块的提升受后端 `CONTENT_BLOCK_NOT_CONVERTIBLE` 限制，Phase 1 UI 上 chapter_X 选项 disabled + tooltip；放宽 content 后端规则作为 Phase 2 单独评估。

**Tech Stack:** Vue 3 + TypeScript + Pinia + Element Plus + Vitest + Chrome DevTools MCP

---

## File Structure

**Touch list:**

- Modify: `frontend/src/utils/layerMark.ts` — 扩展 `LayerRole` 与 `LayerRow`；扩展 `defaultLayerRole/effectiveRole/computeLayerUpdates/computeLayerIndents` 处理叶子行；新增 `validateLayerQ25`
- Modify: `frontend/src/store/procedureEditor.ts` — `layerRows` 改输出 chapter+leaf；`applyLayerRoles` 改为 async，分发三类操作并把 Q25 冲突返回调用方
- Modify: `frontend/src/components/editor/TreeRow.vue` — 加 `:layer-mode` + `:layer-role` + `:indent-override` props；layer 模式下渲染 role picker 并隐藏 action buttons；emit `layer-role`
- Modify: `frontend/src/components/editor/ChapterTreePanel.vue` — 删 `<EditorLayerMarking>` 分支；在 layer 模式下维护 `roleMap`、传 `indent-override`、显示 Q25 冲突 banner、调 `applyLayerRoles`
- Delete: `frontend/src/components/editor/EditorLayerMarking.vue`
- Delete (after pre-flight 确认无其它消费者): `frontend/src/components/shared/ImportMarkingRow.vue` + `frontend/tests/unit/ImportMarkingRow.spec.ts`
- Test (new): `frontend/tests/unit/layerMark.spec.ts`（如已存在则扩展；否则按本计划新建）
- Test (modify): `frontend/tests/unit/ChapterTreePanel.spec.ts` — 加层级 overlay 行为
- Test (modify): `frontend/tests/unit/TreeRow.spec.ts` — 加 layer mode 渲染断言
- Test (delete): `frontend/tests/unit/EditorLayerMarking.spec.ts`（被 ChapterTreePanel 测试取代）

**职责边界:**
- `utils/layerMark.ts` 纯函数；零 Vue / store 依赖；TDD 主战场
- `store.applyLayerRoles` 编排：先 validate → 再依序执行三类操作
- `ChapterTreePanel.vue` 状态容器：roleMap、indent 派生、Q25 banner、apply 触发
- `TreeRow.vue` 哑组件：layer 模式下接 role + override，发事件不改 store

---

## Pre-flight

### Task 0: 隔离工作区 + 确认 ImportMarkingRow 范围

**Files:**
- Read-only check: 全仓库搜索 `ImportMarkingRow` 引用

- [ ] **Step 1: 创建隔离 worktree**

调用 `superpowers:using-git-worktrees` skill。该 feature 与当前 `feat/batch-pattern-reorganize` 分支无关，应从 `main` 起新分支 `feat/layer-mode-tree-overlay`。

- [ ] **Step 2: 复核 ImportMarkingRow 仅由 EditorLayerMarking 消费**

Run:
```bash
grep -rn "ImportMarkingRow" frontend/ 2>/dev/null
```

Expected hits: `frontend/src/components/shared/ImportMarkingRow.vue`（自身）、`frontend/src/components/editor/EditorLayerMarking.vue`（src 唯一消费者）、`frontend/tests/unit/ImportMarkingRow.spec.ts`（自身 spec）、`frontend/tests/unit/EditorLayerMarking.spec.ts`（stub）。

如果还有别的（如 import 向导），**修订本计划**：保留 ImportMarkingRow 与其 spec，仅删 EditorLayerMarking。

- [ ] **Step 3: 装好测试环境**

Run:
```bash
cd frontend && npm install 2>&1 | tail -3
npx vitest run --reporter=dot tests/unit/layerMark 2>&1 | tail -10
```

Expected: 测试可启动（即便目前 layerMark.spec.ts 不存在，也至少 vitest 自己能跑）。

---

## Phase 1: 纯函数扩展（utils/layerMark.ts，TDD）

### Task 1: 扩展 LayerRole 与 LayerRow 类型 + 默认角色

**Files:**
- Modify: `frontend/src/utils/layerMark.ts:1-22`
- Test: `frontend/tests/unit/layerMark.spec.ts`（新建或扩展已有）

- [ ] **Step 1: 写失败测试**

文件：`frontend/tests/unit/layerMark.spec.ts`（如不存在则建）

```typescript
import { describe, it, expect } from 'vitest'
import { defaultLayerRole } from '@/utils/layerMark'

describe('defaultLayerRole', () => {
  it('章节行：按 level 夹到 chapter_1/2/3', () => {
    expect(defaultLayerRole({ id: 'c', kind: 'chapter', level: 1, hasLeafChildren: false })).toBe('chapter_1')
    expect(defaultLayerRole({ id: 'c', kind: 'chapter', level: 2, hasLeafChildren: false })).toBe('chapter_2')
    expect(defaultLayerRole({ id: 'c', kind: 'chapter', level: 7, hasLeafChildren: false })).toBe('chapter_3')
    expect(defaultLayerRole({ id: 'c', kind: 'chapter', level: 0, hasLeafChildren: false })).toBe('chapter_1')
  })
  it('叶子行：默认 keep', () => {
    expect(defaultLayerRole({ id: 's', kind: 'step', level: 0, hasLeafChildren: false })).toBe('keep')
    expect(defaultLayerRole({ id: 'c', kind: 'content', level: 0, hasLeafChildren: false })).toBe('keep')
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/layerMark.spec.ts -t "defaultLayerRole"`
Expected: FAIL（缺 kind 字段 / 类型不接受 'keep'）

- [ ] **Step 3: 改 layerMark.ts 顶部类型与默认函数**

替换 `frontend/src/utils/layerMark.ts:1-22`：

```typescript
export type LayerRole = 'chapter_1' | 'chapter_2' | 'chapter_3' | 'content' | 'keep'

/** 文档序里参与层级标定的行——含章节与叶子（step / content）。 */
export interface LayerRow {
  id: string
  kind: 'chapter' | 'step' | 'content'
  level: number // chapter 当前层级（叶子行 level=0 占位）
  hasLeafChildren: boolean // 仅 chapter 有意义：挂了步骤/内容块 → 不可降为 content
}

/** 应用层级后单个行的目标归属（tagged union）。 */
export type LayerUpdate =
  | { kind: 'reorder'; parent_id: string | null; sort_order: number; level: number }
  | { kind: 'to-content'; parent_id: string | null; sort_order: number; sourceTitle: string }
  | { kind: 'to-chapter'; parent_id: string | null; sort_order: number; level: number }
  | { kind: 'leaf-reparent'; parent_id: string | null; sort_order: number }

/** 默认角色：chapter 用 level 预填；叶子行预填 keep。 */
export function defaultLayerRole(row: LayerRow): LayerRole {
  if (row.kind !== 'chapter') return 'keep'
  const lv = Math.min(3, Math.max(1, row.level))
  return `chapter_${lv}` as LayerRole
}
```

- [ ] **Step 4: 改下方 `effectiveRole` 与所有调用方签名**

旧的 `effectiveRole(row, roleMap)` 内部调 `defaultLayerRole(row.level)` 需改成 `defaultLayerRole(row)`。同时为叶子行加规则：叶子若 role='keep'，保持 leaf；叶子若 role='content'，**视为无效**（叶子已是 leaf，再选"content"语义重复），夹回 'keep'；叶子若 role='chapter_X'，提升。

替换 `effectiveRole` 函数：

```typescript
function effectiveRole(row: LayerRow, roleMap: Map<string, LayerRole>): LayerRole {
  const role = roleMap.get(row.id) ?? defaultLayerRole(row)
  if (row.kind === 'chapter') {
    // 章节：content 角色受 hasLeafChildren 约束
    if (role === 'content' && row.hasLeafChildren) return defaultLayerRole(row)
    // 章节不可选 'keep'，夹回默认
    if (role === 'keep') return defaultLayerRole(row)
    return role
  }
  // 叶子：'content' 在叶子上无意义，夹回 keep
  if (role === 'content') return 'keep'
  return role
}
```

- [ ] **Step 5: 运行测试**

Run: `cd frontend && npx vitest run tests/unit/layerMark.spec.ts -t "defaultLayerRole"`
Expected: PASS

- [ ] **Step 6: 跑整组 layerMark 测试确认旧测试也仍 PASS**

Run: `cd frontend && npx vitest run tests/unit/layerMark.spec.ts`
Expected: 全部 PASS（如果旧测试调用 `defaultLayerRole(level)` 的旧签名，需要同时更新——把 `defaultLayerRole(1)` 改成 `defaultLayerRole({id:'',kind:'chapter',level:1,hasLeafChildren:false})`）。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/utils/layerMark.ts frontend/tests/unit/layerMark.spec.ts
git commit -m "refactor(layerMark): LayerRow add kind, LayerRole add 'keep' (P1 of overlay)"
```

---

### Task 2: 扩展 `computeLayerUpdates` 处理叶子提升

**Files:**
- Modify: `frontend/src/utils/layerMark.ts:39-78`
- Test: `frontend/tests/unit/layerMark.spec.ts`

- [ ] **Step 1: 写失败测试（提升 step + 中间插入）**

追加到 `layerMark.spec.ts`：

```typescript
import { computeLayerUpdates } from '@/utils/layerMark'

describe('computeLayerUpdates with leaves', () => {
  it('叶子保持 keep → 输出 leaf-reparent，挂到最近标题', () => {
    const rows: LayerRow[] = [
      { id: 'A', kind: 'chapter', level: 1, hasLeafChildren: false },
      { id: 's1', kind: 'step', level: 0, hasLeafChildren: false },
    ]
    const roles = new Map<string, LayerRole>([['A', 'chapter_1']])
    const u = computeLayerUpdates(rows, roles)
    expect(u.get('A')).toEqual({ kind: 'reorder', parent_id: null, sort_order: 0, level: 1 })
    expect(u.get('s1')).toEqual({ kind: 'leaf-reparent', parent_id: 'A', sort_order: 0 })
  })

  it('叶子选 chapter_2 → 输出 to-chapter，并成为新 l2', () => {
    const rows: LayerRow[] = [
      { id: 'A', kind: 'chapter', level: 1, hasLeafChildren: false },
      { id: 's1', kind: 'step', level: 0, hasLeafChildren: false },
      { id: 'c1', kind: 'content', level: 0, hasLeafChildren: false },
      { id: 's2', kind: 'step', level: 0, hasLeafChildren: false },
    ]
    const roles = new Map<string, LayerRole>([
      ['A', 'chapter_1'],
      ['c1', 'chapter_2'],
    ])
    const u = computeLayerUpdates(rows, roles)
    expect(u.get('s1')).toEqual({ kind: 'leaf-reparent', parent_id: 'A', sort_order: 0 })
    expect(u.get('c1')).toEqual({ kind: 'to-chapter', parent_id: 'A', sort_order: 1, level: 2 })
    expect(u.get('s2')).toEqual({ kind: 'leaf-reparent', parent_id: 'c1', sort_order: 0 })
  })

  it('叶子选 chapter_X 但无可挂父：chapter_2 无 l1 → 挂根成 L1', () => {
    const rows: LayerRow[] = [
      { id: 's1', kind: 'step', level: 0, hasLeafChildren: false },
    ]
    const roles = new Map<string, LayerRole>([['s1', 'chapter_2']])
    const u = computeLayerUpdates(rows, roles)
    expect(u.get('s1')).toEqual({ kind: 'to-chapter', parent_id: null, sort_order: 0, level: 1 })
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/layerMark.spec.ts -t "computeLayerUpdates with leaves"`
Expected: FAIL（旧实现返回 undefined for leaves）

- [ ] **Step 3: 改写 computeLayerUpdates**

替换函数体：

```typescript
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
  // 标题级 → 解析出 parent + 实际落定 level（夹紧到祖先链能撑得起的层）。
  const placeChapter = (requestedLevel: number): { parent: string | null; level: number } => {
    if (requestedLevel >= 3 && l2) return { parent: l2, level: 3 }
    if (requestedLevel >= 2 && l1) return { parent: l1, level: 2 }
    return { parent: null, level: 1 }
  }
  const setHeadingContext = (id: string, level: number): void => {
    if (level === 1) { l1 = id; l2 = null; l3 = null }
    else if (level === 2) { l2 = id; l3 = null }
    else { l3 = id }
  }

  for (const row of rows) {
    const role = effectiveRole(row, roleMap)
    if (row.kind === 'chapter') {
      if (role === 'content') {
        // 章节降级为父章节下的内容步骤；不更新 l1/l2/l3 上下文
        const parent = l3 ?? l2 ?? l1
        out.set(row.id, { kind: 'to-content', parent_id: parent, sort_order: nextSort(parent), sourceTitle: '' })
        continue
      }
      const requested = role === 'chapter_3' ? 3 : role === 'chapter_2' ? 2 : 1
      const { parent, level } = placeChapter(requested)
      setHeadingContext(row.id, level)
      out.set(row.id, { kind: 'reorder', parent_id: parent, sort_order: nextSort(parent), level })
      continue
    }
    // 叶子（step / content）
    if (role === 'keep') {
      const parent = l3 ?? l2 ?? l1
      out.set(row.id, { kind: 'leaf-reparent', parent_id: parent, sort_order: nextSort(parent) })
      continue
    }
    // 叶子提升为章节
    const requested = role === 'chapter_3' ? 3 : role === 'chapter_2' ? 2 : 1
    const { parent, level } = placeChapter(requested)
    setHeadingContext(row.id, level)
    out.set(row.id, { kind: 'to-chapter', parent_id: parent, sort_order: nextSort(parent), level })
  }
  return out
}
```

注意 `sourceTitle` 字段需要在 store apply 时填充（仅章节有 title），utils 层留空字符串即可；如果未来要在 utils 测里断言 sourceTitle，应改为可选字段或由 store 注入。

- [ ] **Step 4: 运行测试**

Run: `cd frontend && npx vitest run tests/unit/layerMark.spec.ts`
Expected: PASS（含 Task 1 的 + Task 2 新增 3 个；旧的章节-only 测试也应仍通过——若旧测断言形如 `{parent_id, toContentStep, sort_order}`，需要更新断言到新 tagged union）

- [ ] **Step 5: 提交**

```bash
git add frontend/src/utils/layerMark.ts frontend/tests/unit/layerMark.spec.ts
git commit -m "feat(layerMark): computeLayerUpdates handles leaf promote + reparent"
```

---

### Task 3: 扩展 `computeLayerIndents` 为叶子计算缩进

**Files:**
- Modify: `frontend/src/utils/layerMark.ts:81-98`
- Test: `frontend/tests/unit/layerMark.spec.ts`

- [ ] **Step 1: 写失败测试**

```typescript
import { computeLayerIndents } from '@/utils/layerMark'

describe('computeLayerIndents with leaves', () => {
  it('叶子继承当前 heading level；提升后自身缩进按新 level', () => {
    const rows: LayerRow[] = [
      { id: 'A', kind: 'chapter', level: 1, hasLeafChildren: false },
      { id: 's1', kind: 'step', level: 0, hasLeafChildren: false },
      { id: 'c1', kind: 'content', level: 0, hasLeafChildren: false },
      { id: 's2', kind: 'step', level: 0, hasLeafChildren: false },
    ]
    const roles = new Map<string, LayerRole>([
      ['A', 'chapter_1'],
      ['c1', 'chapter_2'],
    ])
    const m = computeLayerIndents(rows, roles)
    expect(m.get('A')).toBe(0)   // L1 → 0
    expect(m.get('s1')).toBe(1)  // 挂在 L1 下
    expect(m.get('c1')).toBe(1)  // 自己被提升为 L2 → indent=1
    expect(m.get('s2')).toBe(2)  // 挂在新 L2 下
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/layerMark.spec.ts -t "computeLayerIndents with leaves"`
Expected: FAIL（旧实现叶子未处理）

- [ ] **Step 3: 改写 computeLayerIndents**

替换 `frontend/src/utils/layerMark.ts:81-98`：

```typescript
/** 「所见即所选」缩进：章节按其落定 level；叶子 keep 缩在当前 heading 下；叶子提升为章节按新 level。 */
export function computeLayerIndents(
  rows: LayerRow[],
  roleMap: Map<string, LayerRole>,
): Map<string, number> {
  const map = new Map<string, number>()
  let headingLevel = 0
  let l1Set = false
  let l2Set = false
  for (const row of rows) {
    const role = effectiveRole(row, roleMap)
    if (row.kind === 'chapter') {
      if (role === 'content') {
        // 降级为 content：缩进按当前 heading 下一层
        map.set(row.id, headingLevel)
        continue
      }
      const requested = role === 'chapter_3' ? 3 : role === 'chapter_2' ? 2 : 1
      // 夹紧到祖先链能撑得起的层（与 computeLayerUpdates 同算法）
      const lv = requested >= 3 && l2Set ? 3 : requested >= 2 && l1Set ? 2 : 1
      map.set(row.id, lv - 1)
      headingLevel = lv
      if (lv === 1) { l1Set = true; l2Set = false }
      else if (lv === 2) { l2Set = true }
      continue
    }
    // 叶子
    if (role === 'keep') {
      map.set(row.id, headingLevel)
      continue
    }
    // 叶子提升为章节
    const requested = role === 'chapter_3' ? 3 : role === 'chapter_2' ? 2 : 1
    const lv = requested >= 3 && l2Set ? 3 : requested >= 2 && l1Set ? 2 : 1
    map.set(row.id, lv - 1)
    headingLevel = lv
    if (lv === 1) { l1Set = true; l2Set = false }
    else if (lv === 2) { l2Set = true }
  }
  return map
}
```

- [ ] **Step 4: 运行测试**

Run: `cd frontend && npx vitest run tests/unit/layerMark.spec.ts`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/utils/layerMark.ts frontend/tests/unit/layerMark.spec.ts
git commit -m "feat(layerMark): computeLayerIndents handles leaf rows"
```

---

### Task 4: 新增 `validateLayerQ25` — 同级互斥校验

**Files:**
- Modify: `frontend/src/utils/layerMark.ts` (append)
- Test: `frontend/tests/unit/layerMark.spec.ts`

- [ ] **Step 1: 写失败测试**

```typescript
import { validateLayerQ25, type LayerConflict } from '@/utils/layerMark'

describe('validateLayerQ25', () => {
  it('提升中间叶子导致父级 chapter/leaf 混合 → 冲突', () => {
    const rows: LayerRow[] = [
      { id: 'A', kind: 'chapter', level: 1, hasLeafChildren: true },
      { id: 's1', kind: 'step', level: 0, hasLeafChildren: false },
      { id: 'c1', kind: 'content', level: 0, hasLeafChildren: false },
      { id: 's2', kind: 'step', level: 0, hasLeafChildren: false },
    ]
    const updates = computeLayerUpdates(rows, new Map([
      ['A', 'chapter_1'],
      ['c1', 'chapter_2'],
    ]))
    const conflicts = validateLayerQ25(rows, updates)
    expect(conflicts).toHaveLength(1)
    expect(conflicts[0].parent_id).toBe('A')
    expect(conflicts[0].chapterChildren).toEqual(['c1'])
    expect(conflicts[0].leafChildren).toEqual(['s1'])
  })

  it('全 leaf 兄弟（无章节兄弟）无冲突', () => {
    const rows: LayerRow[] = [
      { id: 'A', kind: 'chapter', level: 1, hasLeafChildren: true },
      { id: 's1', kind: 'step', level: 0, hasLeafChildren: false },
      { id: 's2', kind: 'step', level: 0, hasLeafChildren: false },
    ]
    const updates = computeLayerUpdates(rows, new Map([['A', 'chapter_1']]))
    expect(validateLayerQ25(rows, updates)).toEqual([])
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/layerMark.spec.ts -t "validateLayerQ25"`
Expected: FAIL（函数不存在）

- [ ] **Step 3: 实现 validateLayerQ25**

追加到 `frontend/src/utils/layerMark.ts` 末尾：

```typescript
export interface LayerConflict {
  parent_id: string | null
  chapterChildren: string[]
  leafChildren: string[]
}

/** Dry-run Q25 同级互斥：按 updates 推出每行的 target kind，按 parent_id 分组，flag 混合组。 */
export function validateLayerQ25(
  rows: LayerRow[],
  updates: Map<string, LayerUpdate>,
): LayerConflict[] {
  // target kind: chapter | leaf
  const targetKind = new Map<string, 'chapter' | 'leaf'>()
  for (const row of rows) {
    const u = updates.get(row.id)
    if (!u) continue
    if (u.kind === 'reorder' || u.kind === 'to-chapter') targetKind.set(row.id, 'chapter')
    else targetKind.set(row.id, 'leaf') // to-content / leaf-reparent
  }
  // 按 parent_id 分组
  const groups = new Map<string | null, { chapters: string[]; leaves: string[] }>()
  for (const [id, u] of updates) {
    const k = targetKind.get(id)
    if (!k) continue
    const g = groups.get(u.parent_id) ?? { chapters: [], leaves: [] }
    if (k === 'chapter') g.chapters.push(id)
    else g.leaves.push(id)
    groups.set(u.parent_id, g)
  }
  const conflicts: LayerConflict[] = []
  for (const [parent_id, g] of groups) {
    if (g.chapters.length > 0 && g.leaves.length > 0) {
      conflicts.push({ parent_id, chapterChildren: g.chapters, leafChildren: g.leaves })
    }
  }
  return conflicts
}
```

- [ ] **Step 4: 运行测试**

Run: `cd frontend && npx vitest run tests/unit/layerMark.spec.ts -t "validateLayerQ25"`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/utils/layerMark.ts frontend/tests/unit/layerMark.spec.ts
git commit -m "feat(layerMark): validateLayerQ25 sibling-mutex dry-run"
```

---

## Phase 2: Store 改造

### Task 5: 改写 `store.layerRows` getter 输出 chapter+leaf

**Files:**
- Modify: `frontend/src/store/procedureEditor.ts:247-271`
- Test: `frontend/tests/unit/store/procedureEditor.layerRows.spec.ts`（如不存在则建；或加进现有 store spec）

- [ ] **Step 1: 找现有 store 测试位置**

Run: `grep -rln "layerRows" frontend/tests/ 2>/dev/null`

把测试加到首次命中的文件；如完全没命中，新建 `frontend/tests/unit/store/procedureEditor.layerRows.spec.ts`。

- [ ] **Step 2: 写失败测试**

```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useProcedureEditorStore } from '@/store/procedureEditor'

describe('procedureEditor.layerRows (overlay)', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('输出 chapter + step + content 按文档序', () => {
    const store = useProcedureEditorStore()
    store.chapters = [
      { id: 'A', parent_id: null, title: 'A', skip_numbering: false, mark_status: 'unmarked', sort_order: 0 },
      { id: 'B', parent_id: 'A', title: 'B', skip_numbering: false, mark_status: 'unmarked', sort_order: 0 },
    ]
    store.steps = [
      { id: 's1', chapter_id: 'B', kind: 'step', title: 's1', content: '', input_schema: {} as never, attachment_marks: [], skip_numbering: false, sort_order: 0 },
      { id: 'c1', chapter_id: 'B', kind: 'content', title: '', content: '<p>x</p>', input_schema: {} as never, attachment_marks: [], skip_numbering: false, sort_order: 1 },
    ]
    expect(store.layerRows.map((r) => r.id)).toEqual(['A', 'B', 's1', 'c1'])
    expect(store.layerRows.map((r) => r.kind)).toEqual(['chapter', 'chapter', 'step', 'content'])
    expect(store.layerRows[1].hasLeafChildren).toBe(true)
  })
})
```

- [ ] **Step 3: 运行确认失败**

Run: `cd frontend && npx vitest run -t "layerRows (overlay)"`
Expected: FAIL（kind 字段缺失或 steps 没进 layerRows）

- [ ] **Step 4: 改写 layerRows getter**

替换 `frontend/src/store/procedureEditor.ts:247-271`：

```typescript
    layerRows(): LayerRow[] {
      const levels = this.levelMap
      const hasStep = new Set(this.steps.map((s) => s.chapter_id))
      const chByParent = new Map<string | null, EditorChapter[]>()
      for (const c of this.chapters) {
        const g = chByParent.get(c.parent_id) ?? []
        g.push(c)
        chByParent.set(c.parent_id, g)
      }
      const stByChapter = new Map<string | null, EditorStep[]>()
      for (const s of this.steps) {
        const g = stByChapter.get(s.chapter_id) ?? []
        g.push(s)
        stByChapter.set(s.chapter_id, g)
      }
      const cmp = (a: { sort_order: number; id: string }, b: { sort_order: number; id: string }): number =>
        a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1
      const rows: LayerRow[] = []
      const walk = (parent: string | null): void => {
        for (const c of [...(chByParent.get(parent) ?? [])].sort(cmp)) {
          rows.push({
            id: c.id,
            kind: 'chapter',
            level: levels.get(c.id) ?? 1,
            hasLeafChildren: hasStep.has(c.id),
          })
          walk(c.id)
        }
        for (const s of [...(stByChapter.get(parent) ?? [])].sort(cmp)) {
          rows.push({
            id: s.id,
            kind: s.kind === 'content' ? 'content' : 'step',
            level: 0,
            hasLeafChildren: false,
          })
        }
      }
      walk(null)
      return rows
    },
```

注意 `chapterDocRows` getter（`procedureEditor.ts:293-299`）当前从 `layerRows` 派生且只关心章节，需相应过滤：

```typescript
    chapterDocRows(): { id: string; kind: 'chapter' | 'content'; title: string }[] {
      return this.layerRows
        .filter((r) => r.kind === 'chapter')
        .map((r) => ({ id: r.id, kind: 'chapter' as const, title: this.chapterMap.get(r.id)?.title ?? '' }))
    },
```

- [ ] **Step 5: 运行测试**

Run: `cd frontend && npx vitest run`
Expected: 所有 store 单测 PASS。如 `chapterDocRows` 相关旧测出现回归，确认其过滤了叶子。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/store/procedureEditor.ts frontend/tests/unit/
git commit -m "refactor(store): layerRows include leaves; chapterDocRows filters chapters"
```

---

### Task 6: 改写 `store.applyLayerRoles` 为 async + Q25 + 提升分发

**Files:**
- Modify: `frontend/src/store/procedureEditor.ts:938-977`
- Test: `frontend/tests/unit/store/procedureEditor.applyLayerRoles.spec.ts`（新建）

- [ ] **Step 1: 写失败测试**

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useProcedureEditorStore } from '@/store/procedureEditor'

vi.mock('@/api/http', () => ({ http: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }))
vi.mock('@/api/steps', async () => {
  const actual = await vi.importActual<typeof import('@/api/steps')>('@/api/steps')
  return {
    ...actual,
    convertStepToChapter: vi.fn(async () => ({ created: [], deleted: [] })),
  }
})

describe('store.applyLayerRoles (overlay)', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('Q25 冲突 → 返回 conflicts，不修改状态、不调 API', async () => {
    const store = useProcedureEditorStore()
    store.chapters = [{ id: 'A', parent_id: null, title: 'A', skip_numbering: false, mark_status: 'unmarked', sort_order: 0 }]
    store.steps = [
      { id: 's1', chapter_id: 'A', kind: 'step', title: 's1', content: '', input_schema: {} as never, attachment_marks: [], skip_numbering: false, sort_order: 0 },
      { id: 'c1', chapter_id: 'A', kind: 'content', title: '', content: '<p>x</p>', input_schema: {} as never, attachment_marks: [], skip_numbering: false, sort_order: 1 },
      { id: 's2', chapter_id: 'A', kind: 'step', title: 's2', content: '', input_schema: {} as never, attachment_marks: [], skip_numbering: false, sort_order: 2 },
    ]
    const before = JSON.stringify({ ch: store.chapters, st: store.steps })
    const result = await store.applyLayerRoles(new Map([['A', 'chapter_1'], ['c1', 'chapter_2']]))
    expect(result.ok).toBe(false)
    expect(result.conflicts).toHaveLength(1)
    expect(result.conflicts![0].parent_id).toBe('A')
    expect(JSON.stringify({ ch: store.chapters, st: store.steps })).toBe(before)
  })

  it('叶子 chapter_X 选项无冲突 → 调 convertStepToChapter', async () => {
    const { convertStepToChapter } = await import('@/api/steps')
    const store = useProcedureEditorStore()
    store.chapters = [{ id: 'A', parent_id: null, title: 'A', skip_numbering: false, mark_status: 'unmarked', sort_order: 0 }]
    store.steps = [
      { id: 's1', chapter_id: 'A', kind: 'step', title: 's1', content: '', input_schema: {} as never, attachment_marks: [], skip_numbering: false, sort_order: 0 },
    ]
    // ensureSaved 直返、reload 桩
    vi.spyOn(store, 'ensureSaved').mockResolvedValue({})
    vi.spyOn(store, 'reload').mockResolvedValue()
    const result = await store.applyLayerRoles(new Map([['A', 'chapter_1'], ['s1', 'chapter_2']]))
    expect(result.ok).toBe(true)
    expect(convertStepToChapter).toHaveBeenCalledWith('s1')
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run -t "applyLayerRoles (overlay)"`
Expected: FAIL（旧 applyLayerRoles 是同步、不返 conflicts、不调 convertStepToChapter）

- [ ] **Step 3: 改写 applyLayerRoles**

替换 `frontend/src/store/procedureEditor.ts:938-977`：

```typescript
    async applyLayerRoles(roleMap: Map<string, LayerRole>): Promise<{ ok: true } | { ok: false; conflicts: LayerConflict[] }> {
      const rows = this.layerRows
      const updates = computeLayerUpdates(rows, roleMap)
      const conflicts = validateLayerQ25(rows, updates)
      if (conflicts.length > 0) return { ok: false, conflicts }

      // 先持久化所有临时节点，并把 temp id 解析为真实 id
      const idMap = await this.ensureSaved()
      this.pushUndo('layer')

      // 第一步：叶子提升为章节（调后端 API），逐个处理后续 reload 会还原状态
      for (const row of rows) {
        if (row.kind === 'chapter') continue
        const u = updates.get(row.id)
        if (!u || u.kind !== 'to-chapter') continue
        const realId = idMap[row.id] ?? row.id
        await convertStepToChapter(realId)
      }
      // 由于 step→chapter 改了 DB 结构，reload 把本地状态拉齐
      if ([...updates.values()].some((u) => u.kind === 'to-chapter')) {
        await this.reload()
      }

      // 第二步：剩余 chapter 重排 + chapter→content（重做 updates，因为 reload 后行 id 变化但章节 id 不变；这里复用原 updates 中章节相关项）
      const clearReview: string[] = []
      const toContent: { id: string; parent_id: string | null; sort_order: number; title: string }[] = []
      for (const [id, u] of updates) {
        if (u.kind === 'reorder') {
          const ch = this.chapterMap.get(id)
          if (!ch) continue
          if (ch.mark_status === 'review') clearReview.push(id)
          ch.parent_id = u.parent_id
          ch.sort_order = u.sort_order
          this.dirtyChapters.add(id)
        } else if (u.kind === 'to-content') {
          const ch = this.chapterMap.get(id)
          if (!ch) continue
          if (ch.mark_status === 'review') clearReview.push(id)
          toContent.push({ id, parent_id: u.parent_id, sort_order: u.sort_order, title: ch.title })
        }
        // to-chapter 已在第一步完成；leaf-reparent 由 reload 后基于章节重排自然形成
      }
      for (const t of toContent) {
        this.removeNodeLocal(t.id)
        const sid = genTempId()
        this.steps.push({
          id: sid,
          chapter_id: t.parent_id,
          kind: 'content',
          title: '',
          content: t.title.trim() ? `<p>${escapeHtml(t.title)}</p>` : '',
          input_schema: {} as InputSchema,
          attachment_marks: [],
          skip_numbering: false,
          sort_order: t.sort_order,
        })
        this.dirtySteps.add(sid)
      }
      this.layerMode = false
      for (const id of clearReview) void this.setMark(id, 'unmarked')
      return { ok: true }
    },
```

记得在文件顶部 import：

```typescript
import { ..., validateLayerQ25, type LayerConflict, ... } from '@/utils/layerMark'
```

- [ ] **Step 4: 运行测试**

Run: `cd frontend && npx vitest run -t "applyLayerRoles"`
Expected: PASS

- [ ] **Step 5: 跑全 store 测套确认无回归**

Run: `cd frontend && npx vitest run tests/unit/store/`
Expected: 全部 PASS（如有旧测断言 `applyLayerRoles` 同步返回 void，需要更新为 await + ok）

- [ ] **Step 6: 提交**

```bash
git add frontend/src/store/procedureEditor.ts frontend/tests/unit/store/
git commit -m "feat(store): applyLayerRoles async + Q25 validate + leaf→chapter dispatch"
```

---

## Phase 3: UI 叠加层

### Task 7: TreeRow 新增 `layerMode` + role picker + indent override

**Files:**
- Modify: `frontend/src/components/editor/TreeRow.vue`
- Test: `frontend/tests/unit/TreeRow.spec.ts`（如不存在则建）

- [ ] **Step 1: 写失败测试**

```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import TreeRow from '@/components/editor/TreeRow.vue'
import type { FlatRow } from '@/types/node'

const baseRow: FlatRow = {
  id: 'A', kind: 'chapter', parent_id: null, code: '1', title: 'A',
  fallback: '', mark_status: 'unmarked', depth: 0, has_children: false, expanded: true,
  level: 1,
}

function mountRow(extra: Partial<Record<string, unknown>>) {
  return mount(TreeRow, {
    props: {
      row: baseRow, selected: false, markMode: false, selectedForMark: false,
      addState: { canAddChapter: false, canAddContent: false, canAddStep: false },
      editable: true, canMoveUp: false, canMoveDown: false, dropHint: '',
      layerMode: false, layerRole: 'chapter_1',
      ...extra,
    },
    global: { plugins: [ElementPlus] },
  })
}

describe('TreeRow layer mode', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('layer 模式下隐藏 action buttons，显示 role picker', () => {
    const w = mountRow({ layerMode: true })
    expect(w.find('.tr-actions').exists()).toBe(false)
    expect(w.find('.tr-layer-picker').exists()).toBe(true)
  })

  it('chapter 行的 role picker 含 一级/二级/三级/正文', () => {
    const w = mountRow({ layerMode: true })
    const labels = w.findAll('.tr-layer-picker .el-radio-button').map((b) => b.text())
    expect(labels).toEqual(['一级', '二级', '三级', '正文'])
  })

  it('step 行的 role picker 含 保持/一级/二级/三级', () => {
    const stepRow = { ...baseRow, id: 's', kind: 'step' as const }
    const w = mountRow({ row: stepRow, layerMode: true, layerRole: 'keep' })
    const labels = w.findAll('.tr-layer-picker .el-radio-button').map((b) => b.text())
    expect(labels).toEqual(['保持', '一级', '二级', '三级'])
  })

  it('content 行 chapter_X 选项 disabled（Phase 1 限制）', () => {
    const contentRow = { ...baseRow, id: 'c', kind: 'content' as const }
    const w = mountRow({ row: contentRow, layerMode: true, layerRole: 'keep' })
    const disabled = w.findAll('.tr-layer-picker .el-radio-button.is-disabled')
    // 保持 应可点；一级/二级/三级 全 disabled = 3 个
    expect(disabled.length).toBe(3)
  })

  it('indent override 生效', () => {
    const w = mountRow({ layerMode: true, indentOverride: 2 })
    const padding = (w.element as HTMLElement).style.paddingLeft
    // indent=2 → 2*16+6 = 38px
    expect(padding).toBe('38px')
  })

  it('点选 role 触发 layer-role 事件', async () => {
    const w = mountRow({ layerMode: true })
    const btn = w.findAll('.tr-layer-picker .el-radio-button')[1]
    await btn.trigger('click')
    expect(w.emitted('layer-role')).toBeTruthy()
    expect(w.emitted('layer-role')![0]).toEqual(['chapter_2'])
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/TreeRow.spec.ts`
Expected: FAIL（props 未识别 layerMode/layerRole/indentOverride）

- [ ] **Step 3: 改 TreeRow.vue**

加 props 与 emit（`<script setup>` 顶部 Props 接口 与 emit）：

```typescript
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
  layerMode?: boolean
  layerRole?: import('@/utils/layerMark').LayerRole
  indentOverride?: number | null
}
const props = withDefaults(defineProps<Props>(), { layerMode: false, indentOverride: null })
const emit = defineEmits<{
  (e: 'select'): void
  (e: 'toggle'): void
  (e: 'add', kind: 'chapter' | 'content' | 'step'): void
  (e: 'move', dir: 'up' | 'down'): void
  (e: 'remove'): void
  (e: 'convert', dir: 'to-step' | 'to-content' | 'chapter-to-content'): void
  (e: 'check', shift: boolean): void
  (e: 'layer-role', role: import('@/utils/layerMark').LayerRole): void
  (e: 'dragstart', ev: DragEvent): void
  (e: 'dragover', ev: DragEvent): void
  (e: 'drop', ev: DragEvent): void
  (e: 'dragend'): void
}>()

const effectiveIndent = computed(() =>
  props.indentOverride !== null && props.indentOverride !== undefined ? props.indentOverride : props.row.depth,
)
const layerOptions = computed<{ value: import('@/utils/layerMark').LayerRole; text: string; disabled?: boolean }[]>(() => {
  if (props.row.kind === 'chapter') {
    return [
      { value: 'chapter_1', text: '一级' },
      { value: 'chapter_2', text: '二级' },
      { value: 'chapter_3', text: '三级' },
      { value: 'content', text: '正文', disabled: props.row.has_children },
    ]
  }
  const isContent = props.row.kind === 'content'
  return [
    { value: 'keep', text: '保持' },
    { value: 'chapter_1', text: '一级', disabled: isContent },
    { value: 'chapter_2', text: '二级', disabled: isContent },
    { value: 'chapter_3', text: '三级', disabled: isContent },
  ]
})
function onLayerRole(v: string | number | boolean): void {
  emit('layer-role', v as import('@/utils/layerMark').LayerRole)
}
```

模板 `:style` 改：

```vue
:style="{ boxSizing: 'border-box', paddingLeft: `${effectiveIndent * 16 + 6}px` }"
```

模板 actions 区域外层加 `v-if="editable && !markMode && !layerMode"`，紧随其后追加 layer picker：

```vue
<span v-if="layerMode && editable" class="tr-layer-picker" @click.stop>
  <el-radio-group :model-value="layerRole" size="small" @change="onLayerRole">
    <el-radio-button
      v-for="o in layerOptions"
      :key="o.value"
      :value="o.value"
      :disabled="o.disabled"
    >
      {{ o.text }}
    </el-radio-button>
  </el-radio-group>
</span>
```

content 行 disabled 选项上加 tooltip（用 el-tooltip 包裹 el-radio-button），文案：「content 块需先拆分（暂未支持）」——可选改进，先把 disabled 做出来。

css 末尾追加：

```css
.tr-layer-picker {
  flex: none;
  margin-left: auto;
}
```

- [ ] **Step 4: 运行测试**

Run: `cd frontend && npx vitest run tests/unit/TreeRow.spec.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/editor/TreeRow.vue frontend/tests/unit/TreeRow.spec.ts
git commit -m "feat(TreeRow): layer mode overlay with role picker + indent override"
```

---

### Task 8: ChapterTreePanel 切换到 overlay + roleMap 状态 + Q25 banner

**Files:**
- Modify: `frontend/src/components/editor/ChapterTreePanel.vue`
- Test: `frontend/tests/unit/ChapterTreePanel.spec.ts`

- [ ] **Step 1: 写失败测试**

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import ChapterTreePanel from '@/components/editor/ChapterTreePanel.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'

vi.mock('@/api/http', () => ({ http: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }))

function seed() {
  const store = useProcedureEditorStore()
  store.chapters = [
    { id: 'A', parent_id: null, title: 'A', skip_numbering: false, mark_status: 'unmarked', sort_order: 0 },
  ]
  store.steps = [
    { id: 's1', chapter_id: 'A', kind: 'step', title: 's1', content: '', input_schema: {} as never, attachment_marks: [], skip_numbering: false, sort_order: 0 },
    { id: 'c1', chapter_id: 'A', kind: 'content', title: '', content: '<p>x</p>', input_schema: {} as never, attachment_marks: [], skip_numbering: false, sort_order: 1 },
  ]
  store.layerMode = true
  return store
}

describe('ChapterTreePanel layer overlay', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('layer 模式下渲染 TreeRow（而非 EditorLayerMarking）', () => {
    seed()
    const w = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] } })
    expect(w.findAll('.tr').length).toBeGreaterThan(0)
    expect(w.find('.layer-marking').exists()).toBe(false) // 旧组件根 class
  })

  it('layer 模式下 TreeRow 接收 layer-mode + layer-role', () => {
    seed()
    const w = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] } })
    expect(w.find('.tr-layer-picker').exists()).toBe(true)
  })

  it('apply 时 Q25 冲突 → 渲染冲突 banner', async () => {
    const store = seed()
    const w = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] } })
    // 模拟用户把 c1 标 chapter_2（会导致 A 同时含 step s1 + chapter c1）
    // 直接拿组件 vm 调内部方法不优雅，更稳的是通过点击 picker（依赖 EP 渲染）；这里走 store 路径校验 banner 渲染
    vi.spyOn(store, 'applyLayerRoles').mockResolvedValue({
      ok: false,
      conflicts: [{ parent_id: 'A', chapterChildren: ['c1'], leafChildren: ['s1'] }],
    })
    const applyBtn = w.findAll('button').find((b) => b.text().includes('应用'))!
    await applyBtn.trigger('click')
    await new Promise((r) => setTimeout(r, 0))
    expect(w.find('.lm-conflicts').exists()).toBe(true)
    expect(w.text()).toContain('§Q25')
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/ChapterTreePanel.spec.ts -t "layer overlay"`
Expected: FAIL（旧实现走 `<EditorLayerMarking>`，没有 layer picker，没有 banner）

- [ ] **Step 3: 改 ChapterTreePanel.vue**

`<script setup>` 段新增 import + state：

```typescript
import { computeLayerIndents, defaultLayerRole, type LayerRole, type LayerConflict } from '@/utils/layerMark'

const layerRoleMap = ref<Map<string, LayerRole>>(new Map())
const layerConflicts = ref<LayerConflict[]>([])

watch(() => store.layerMode, (on) => {
  if (on) {
    const m = new Map<string, LayerRole>()
    for (const r of store.layerRows) m.set(r.id, defaultLayerRole(r))
    layerRoleMap.value = m
    layerConflicts.value = []
  } else {
    layerRoleMap.value = new Map()
    layerConflicts.value = []
  }
}, { immediate: true })

const layerIndentMap = computed(() => {
  if (!store.layerMode) return new Map<string, number>()
  return computeLayerIndents(store.layerRows, layerRoleMap.value)
})

function onLayerRole(rowId: string, role: LayerRole): void {
  layerRoleMap.value = new Map(layerRoleMap.value).set(rowId, role)
}
async function applyLayer(): Promise<void> {
  const res = await store.applyLayerRoles(layerRoleMap.value)
  if (!res.ok) {
    layerConflicts.value = res.conflicts
    ElMessage.warning(`存在 ${res.conflicts.length} 处 §Q25 冲突，请先解决再应用`)
  } else {
    layerConflicts.value = []
  }
}
function cancelLayer(): void {
  store.toggleLayerMode()
}
function jumpToRow(id: string): void {
  store.expandAncestors(id)
  store.selectNode(id)
}
```

模板：删 `<EditorLayerMarking v-if=...>` 分支；改写 layer 模式的工具栏与冲突 banner；在 TreeRow 循环里传 layer 相关 props/events。

```vue
<div v-if="store.layerMode" class="lm-bar">
  <span class="lm-hint">选择每行的层级；叶子可提升为章节。应用前先解决 §Q25 冲突。</span>
  <span class="lm-spacer" />
  <el-button size="small" @click="cancelLayer">取消</el-button>
  <el-button size="small" type="primary" @click="applyLayer">应用层级</el-button>
</div>
<div v-if="store.layerMode && layerConflicts.length" class="lm-conflicts">
  <p class="lm-conflicts-title">⚠ §Q25 同级互斥冲突，共 {{ layerConflicts.length }} 处：</p>
  <ul>
    <li v-for="(c, i) in layerConflicts" :key="i">
      在父节点
      <a href="#" @click.prevent="c.parent_id && jumpToRow(c.parent_id)">{{ c.parent_id ?? '根级' }}</a>
      下章节
      <span v-for="id in c.chapterChildren" :key="id">
        <a href="#" @click.prevent="jumpToRow(id)">{{ id }}</a>
      </span>
      与叶子
      <span v-for="id in c.leafChildren" :key="id">
        <a href="#" @click.prevent="jumpToRow(id)">{{ id }}</a>
      </span>
      混合。请把叶子一并提升、或撤销章节提升。
    </li>
  </ul>
</div>
```

TreeRow v-for 内追加 props/events：

```vue
:layer-mode="store.layerMode"
:layer-role="layerRoleMap.get(row.id) ?? 'keep'"
:indent-override="store.layerMode ? (layerIndentMap.get(row.id) ?? null) : null"
@layer-role="(role) => onLayerRole(row.id, role)"
```

样式段追加：

```css
.lm-bar { display: flex; align-items: center; gap: 8px; padding: 8px;
  border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5); }
.lm-hint { font-size: 12px; color: #909399; }
.lm-spacer { flex: 1; }
.lm-conflicts { padding: 8px 12px; background: #fef0f0; border: 1px solid #fcdada;
  color: #f56c6c; font-size: 12px; }
.lm-conflicts-title { margin: 0 0 4px 0; font-weight: 600; }
.lm-conflicts ul { margin: 0; padding-left: 16px; }
.lm-conflicts a { color: #d97757; text-decoration: underline; }
```

- [ ] **Step 4: 运行测试**

Run: `cd frontend && npx vitest run tests/unit/ChapterTreePanel.spec.ts`
Expected: PASS（含旧测和新加 layer overlay 三个）

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/editor/ChapterTreePanel.vue frontend/tests/unit/ChapterTreePanel.spec.ts
git commit -m "feat(ChapterTreePanel): layer overlay + roleMap + Q25 conflict banner"
```

---

## Phase 4: 清理 + 验收

### Task 9: 删 EditorLayerMarking 与（确认无消费者后）ImportMarkingRow

**Files:**
- Delete: `frontend/src/components/editor/EditorLayerMarking.vue`
- Delete: `frontend/tests/unit/EditorLayerMarking.spec.ts`
- Conditional delete: `frontend/src/components/shared/ImportMarkingRow.vue`、`frontend/tests/unit/ImportMarkingRow.spec.ts`

- [ ] **Step 1: 再次复核 ImportMarkingRow 引用**

Run: `grep -rn "ImportMarkingRow" frontend/ 2>/dev/null`

如果只剩它自身 + spec + EditorLayerMarking → 一并删；否则只删 EditorLayerMarking 相关。

- [ ] **Step 2: 删文件**

```bash
git rm frontend/src/components/editor/EditorLayerMarking.vue
git rm frontend/tests/unit/EditorLayerMarking.spec.ts
# 如复核通过：
git rm frontend/src/components/shared/ImportMarkingRow.vue
git rm frontend/tests/unit/ImportMarkingRow.spec.ts
```

- [ ] **Step 3: 删 ChapterTreePanel 中残留的 EditorLayerMarking import**

Run: `grep -n "EditorLayerMarking" frontend/src/components/editor/ChapterTreePanel.vue`
Expected: 无（Task 8 已删 import 行）。若仍有，Edit 去掉。

- [ ] **Step 4: 全量 typecheck + lint + test**

Run:
```bash
cd frontend && npm run typecheck 2>&1 | tail -20
cd frontend && npm run lint 2>&1 | tail -20
cd frontend && npx vitest run 2>&1 | tail -30
```

Expected: 三者均 0 error / 0 warning（视项目惯例）

- [ ] **Step 5: 提交**

```bash
git add -A frontend/
git commit -m "chore: remove EditorLayerMarking + ImportMarkingRow (replaced by overlay)"
```

---

### Task 10: MCP 浏览器手验（按场景）

**Files:**
- Output: `.verify-screenshots/layer-overlay-*.png`

- [ ] **Step 1: 启动 dev server + 准备 fixture**

Run（在本仓库 root）：
```bash
cd frontend && npm run dev &
cd backend && .venv/bin/python -m uvicorn app.main:app --port 8000 --reload &
```

等待两个服务 ready；用既有的 Word fixture 跑一遍导入，得到一个含 step + content 叶子的过程。

- [ ] **Step 2: 用 Chrome DevTools MCP 打开编辑器、切到层级标定**

调用 `mcp__chrome-devtools__navigate_page` 到 `http://localhost:5173/...` 编辑器路由；调用 `take_snapshot` 看树。点「层级标定」。

- [ ] **Step 3: 验证用户场景 A — 章节下的 step 行可提升为二级**

定位一个父 chapter 为 L1 的 step 行，点其 picker「二级」。

**Expected:**
- 该行缩进当场左移到 L2 位置
- 后续叶子若有，其缩进/挂靠也实时更新
- 工具栏 banner 无冲突
- 点「应用层级」→ 网络请求 `POST /api/.../convert-to-chapter`，reload 后 step 变成 L2 章节，原 step 的 content 成为新章节下的 content 块

调用 `take_screenshot` 存 `.verify-screenshots/layer-overlay-promote-step.png`。

- [ ] **Step 4: 验证用户场景 B — content 块 chapter_X 选项 disabled**

定位一个 content 行，确认 picker 中「一级/二级/三级」灰显，hover 上若有 tooltip 应提示「content 块需先拆分（暂未支持）」。

调用 `take_screenshot` 存 `.verify-screenshots/layer-overlay-content-disabled.png`。

- [ ] **Step 5: 验证 Q25 冲突 banner**

人造冲突：一个 L1 章节下若有 `[step1, content1, step2]`，把 content1 标 chapter_2。点「应用层级」。

**Expected:**
- 出现红色 banner，列出 parent_id=L1 的冲突
- 点击 banner 里的 step1 链接 → 树滚动并高亮该行
- 把 step1 也标 chapter_2 → banner 消失 → 再点应用成功

存截图 `.verify-screenshots/layer-overlay-q25-conflict.png` 与 `.verify-screenshots/layer-overlay-q25-resolved.png`。

- [ ] **Step 6: 验证未回归——纯章节重排仍然 work**

进入层级标定，把一个 L2 章节标 L1，应用。Expected：reload 后该章节升到根级，子节点跟随。

- [ ] **Step 7: 收尾提交**

```bash
git add .verify-screenshots/
git commit -m "test(verify): layer-overlay MCP 实测验收"
```

---

## Self-review checklist

执行计划前，agent 应：

1. Spec 覆盖：
   - 「叶子在层级标定可见」→ Task 5 (layerRows include leaves) + Task 7 (TreeRow render) + Task 8 (panel wire)
   - 「叶子可提升为章节」→ Task 2 (compute) + Task 6 (store apply dispatch) + Task 7 (UI picker)
   - 「与 mark mode 对齐」→ Task 7 + Task 8 (overlay 模型一致)
   - 「实时预览缩进」→ Task 3 (computeLayerIndents) + Task 7 (indentOverride) + Task 8 (layerIndentMap)
   - 「Q25 dry-run + 用户可修正」→ Task 4 (validateLayerQ25) + Task 6 (store 返回 conflicts) + Task 8 (banner UI + jumpToRow)
   - 「content 块暂不支持提升」→ Task 7 (disabled + tooltip)
   - 「未回归章节重排 / chapter→content」→ Task 6 (复用旧逻辑) + Task 10 Step 6

2. 类型一致性：
   - `LayerRole` 在 utils / TreeRow / ChapterTreePanel / store 全部 import 一致
   - `LayerConflict` 在 utils 出口、store 返回值、panel banner 接收三处同一接口
   - `LayerUpdate` tagged union 的 kind 字段在 utils 与 store 分发处枚举完整（4 个）

3. 无 placeholder：
   - 每个 Step 3「Write implementation」步都给出完整代码
   - 测试断言用具体值（不出现 "appropriate" / "as expected"）

---

## Risks & known gotchas

- **convertStepToChapter 后 reload 会重建本地状态**：reload 会把当前 dirty 改动丢弃。所以 Task 6 中先 `ensureSaved` 保证 dirty 持久化、再调 API、再 reload。如果用户在 layer mode 进入前有未保存改动（比如重排 / 改标题），ensureSaved 会先把这些落库——确认这是可接受的。
- **`pushUndo('layer')`**：当前 undo 栈只记 chapter 重排。叶子提升因走 API 不可本地撤销，undo 这个 layer 操作可能只能部分回滚。这是已知限制，初版接受；写一个 README 注释或后续单独优化。
- **content 行的 chapter_X 选项**：放在 UI 但 disabled，避免误导。未来放宽后端 `CONTENT_BLOCK_NOT_CONVERTIBLE` 时移除 disabled。
- **EP 的 el-radio-button 在 vitest+jsdom 里有时不渲染**：参考 [[el-dropdown-jsdom-test]] 经验，必要时退化为 component $emit 验证而非 DOM 点击。
- **MCP 截图脚本**：依赖既有的 `.verify-screenshots/` 约定与本地 dev server；如果浏览器 MCP 不可用，改用 Playwright 录屏代替，但保留 commit 里的截图作为验收凭证。

---

## 估时

11 tasks，约 10-15 commits，估计 4-7 小时连续工作（subagent 模式下并行可压到 ~3 小时）。
