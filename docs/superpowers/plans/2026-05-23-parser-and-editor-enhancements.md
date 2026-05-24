# Parser Body-Start Fix + Editor Hierarchy Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix Word解析正文起点误判（方案C），并增加编辑器章节层级的手动调整能力（P0 类型切换、P1 升级/降级按钮、P2 键盘快捷键）。

**Architecture:** 两个独立子系统串联：①后端解析器修复（Python，方案C：首个"标题后接非标题内容"的样式标题作为正文起点）；②前端编辑器增强（TypeScript/Vue，复用现有 `moveCrossParent` + `updateChapterFields` + `useEditorKeyboard` 路径，零新 API）。

**Tech Stack:** Python 3.12 / python-docx / lxml (backend)；TypeScript / Vue 3 / Pinia / Element Plus (frontend)；pytest (backend tests)；Vitest (frontend tests)。

---

## 注意事项：两个独立子系统

后端（Task 1–3）和前端（Task 4–8）可并行或按需分阶段执行。两者无相互依赖。

---

## 文件地图

### 后端（方案C）

| 文件 | 动作 | 说明 |
|------|------|------|
| `backend/app/parser/body_start.py` | **修改** | 在路径①加入方案C回溯检查：标题后有无非标题内容 |
| `backend/tests/unit/parser/_docx_builder.py` | **修改** | 新增 `manual_toc_sop()` fixture：手动目录 + 正文 |
| `backend/tests/unit/parser/test_body_start.py` | **修改** | 新增方案C场景测试 |

### 前端（P0 / P1 / P2）

| 文件 | 动作 | 说明 |
|------|------|------|
| `frontend/src/store/procedureEditor.ts` | **修改** | 新增 `toggleContentType`、`canPromoteChapter`、`canDemoteChapter`、`promoteChapter`、`demoteChapter` |
| `frontend/src/components/editor/ChapterDetailPanel.vue` | **修改** | 在标题字段上方加类型切换按钮（P0） |
| `frontend/src/components/editor/TreeRow.vue` | **修改** | 新增 promote `⇤` / demote `⇥` 按钮（P1） |
| `frontend/src/components/editor/ChapterTreePanel.vue` | **修改** | 处理 `promote` / `demote` emit（P1） |
| `frontend/src/composables/useEditorKeyboard.ts` | **修改** | 新增 `onPromote` / `onDemote` 到 Handlers，处理 Tab/Shift+Tab（P2） |
| `frontend/src/views/procedures/ProcedureEditorView.vue` | **修改** | 把 `onPromote`/`onDemote` 连接到 store（P2） |
| `frontend/tests/unit/procedureEditorStore.spec.ts` | **修改** | 新增 P0/P1 store action 测试 |
| `frontend/tests/unit/TreeRow.spec.ts` | **修改** | 新增 promote/demote 按钮显示测试 |

---

## Task 1：方案C — 新增 `_has_content_after` 辅助函数

**Files:**
- Modify: `backend/app/parser/body_start.py`

- [ ] **Step 1: 在 `body_start.py` 的 `_has_content` 后添加辅助函数**

打开 [`backend/app/parser/body_start.py`](../../../backend/app/parser/body_start.py)，在 `_has_content` 函数（第15行）后面，在 `find_body_start` 函数之前，插入：

```python
def _has_content_after(block: Block, blocks: Sequence[Block]) -> bool:
    """方案C：判断 block 之后、下一个样式标题之前，是否存在有内容的非标题块。"""
    for b in blocks:
        if b.source_index <= block.source_index:
            continue
        if b.style_level is not None and not b.is_toc_field:
            break  # 遇到下一个样式标题，停止
        if _has_content(b):
            return True
    return False
```

- [ ] **Step 2: 修改 `find_body_start` 路径①（first_styled_heading）**

将原来的步骤①：

```python
    # 1. first_styled_heading
    for block in blocks:
        if (
            block.source_index >= toc_floor
            and block.style_level is not None
            and not block.is_toc_field
        ):
            return block.source_index, "first_styled_heading"
```

替换为：

```python
    # 1. first_styled_heading（方案C：优先取首个"标题后紧跟内容"的样式标题）
    styled_candidates = [
        b for b in blocks
        if b.source_index >= toc_floor
        and b.style_level is not None
        and not b.is_toc_field
    ]
    for block in styled_candidates:
        if _has_content_after(block, blocks):
            return block.source_index, "first_styled_heading"
    # 方案C兜底：全为连续标题（无任何正文段）时退回首个样式标题（如纯目录文档）
    if styled_candidates:
        return styled_candidates[0].source_index, "first_styled_heading"
```

---

## Task 2：新增 `manual_toc_sop` 测试 Fixture

**Files:**
- Modify: `backend/tests/unit/parser/_docx_builder.py`

- [ ] **Step 1: 在 `_docx_builder.py` 末尾（`unstyled_numbered_sop` 之后）添加 fixture**

打开 [`backend/tests/unit/parser/_docx_builder.py`](../../../backend/tests/unit/parser/_docx_builder.py)，在文件末尾追加：

```python
def manual_toc_sop() -> bytes:
    """手动排版目录 SOP（章节标题样式，无 TOC 域）。

    结构：封面 → 手动目录区（连续章节标题，无正文段）→ 正文区（章节标题 + 正文段）。
    方案C 须跳过目录区的三个「章节标题」，从正文区第一个「目的」（后接正文）开始。
    """
    return (
        DocxBuilder()
        .para("公司机密文件", center=True)
        .section_break()
        .para("目 录")
        .styled_heading("目的", "章节标题")        # 目录区：连续标题，无内容跟随
        .styled_heading("范围", "章节标题")
        .styled_heading("程序", "章节标题")
        .styled_heading("目的", "章节标题")        # 正文区：标题后有正文段
        .para("本程序规定了碘吸附器定期试验要求。")
        .styled_heading("范围", "章节标题")
        .para("适用于一期1–4号机组。")
        .styled_heading("程序", "章节标题")
        .para("操作步骤如下。")
        .build()
    )
```

---

## Task 3：编写并运行方案C测试

**Files:**
- Modify: `backend/tests/unit/parser/test_body_start.py`

- [ ] **Step 1: 在 `test_body_start.py` 末尾追加两个新测试**

打开 [`backend/tests/unit/parser/test_body_start.py`](../../../backend/tests/unit/parser/test_body_start.py)，在 `import` 区域补充 `manual_toc_sop`：

```python
from tests.unit.parser._docx_builder import (
    DocxBuilder,
    empty_sop,
    manual_toc_sop,
    styled_sop,
    synonym_sop,
)
```

在文件末尾追加：

```python
def test_method_c_skips_manual_toc_area() -> None:
    """方案C：手动目录区（连续样式标题）被跳过，正文从首个"标题后接内容"的块开始。"""
    nd = _norm(manual_toc_sop())
    idx, source = body_start.find_body_start(nd.blocks, toc_field_end=nd.toc_field_end_index)
    assert source == "first_styled_heading"
    body_block = nd.blocks[idx]
    # 正文起始块本身是"目的"
    assert body_block.text.strip() == "目的"
    # 正文起始块之后、在下一个样式标题之前，存在非标题内容块
    subsequent = [b for b in nd.blocks if b.source_index > body_block.source_index]
    first_content = next((b for b in subsequent if b.style_level is None and b.text.strip()), None)
    assert first_content is not None
    assert first_content.text.strip() == "本程序规定了碘吸附器定期试验要求。"


def test_method_c_fallback_when_all_headings_have_no_content() -> None:
    """方案C兜底：文档全为连续样式标题（无正文段），退回首个样式标题，不崩溃。"""
    data = (
        DocxBuilder()
        .styled_heading("目的", "章节标题")
        .styled_heading("范围", "章节标题")
        .styled_heading("程序", "章节标题")
        .build()
    )
    nd = _norm(data)
    idx, source = body_start.find_body_start(nd.blocks, toc_field_end=nd.toc_field_end_index)
    assert source == "first_styled_heading"
    assert nd.blocks[idx].text.strip() == "目的"
```

- [ ] **Step 2: 运行新测试，确认全部通过**

```bash
cd SmartSOP/backend
python -m pytest tests/unit/parser/test_body_start.py -v
```

期望输出（全部 PASSED，共 7 个）：

```
PASSED tests/unit/parser/test_body_start.py::test_first_styled_heading_skips_cover_and_toc
PASSED tests/unit/parser/test_body_start.py::test_synonym_heading_is_body_start
PASSED tests/unit/parser/test_body_start.py::test_toc_field_end_fallback_when_no_styled_heading
PASSED tests/unit/parser/test_body_start.py::test_heuristic_heading_when_provided
PASSED tests/unit/parser/test_body_start.py::test_cover_skip_fallback_for_headingless_doc
PASSED tests/unit/parser/test_body_start.py::test_method_c_skips_manual_toc_area
PASSED tests/unit/parser/test_body_start.py::test_method_c_fallback_when_all_headings_have_no_content
```

- [ ] **Step 3: 运行全量解析器单测，确认无回归**

```bash
python -m pytest tests/unit/parser/ -v
```

期望：全部 PASSED，无 FAILED。

- [ ] **Step 4: 提交**

```bash
git add backend/app/parser/body_start.py \
        backend/tests/unit/parser/_docx_builder.py \
        backend/tests/unit/parser/test_body_start.py
git commit -m "fix(parser): method-c body-start skips manual toc areas

Add _has_content_after() check so find_body_start() skips consecutive
styled-heading blocks that have no body content between them (manual TOC
pattern). Falls back to first styled heading when no content-bearing
heading exists (all-heading documents)."
```

---

## Task 4：P0 — Store action：`toggleContentType`

**Files:**
- Modify: `frontend/src/store/procedureEditor.ts`

- [ ] **Step 1: 在 `toggleSkipNumbering` 之后添加 `toggleContentType` action**

打开 [`frontend/src/store/procedureEditor.ts`](../../../frontend/src/store/procedureEditor.ts)，找到 `toggleSkipNumbering` 函数（约第 432 行），在其后插入：

```typescript
    toggleContentType(id: string): void {
      const ch = this.chapterMap.get(id)
      if (!ch) return
      const next: ContentType = ch.content_type === 'chapter' ? 'content' : 'chapter'
      this.updateChapterFields(id, { content_type: next }, `content_type:${id}`)
    },
```

---

## Task 5：P0 — 测试 `toggleContentType`

**Files:**
- Modify: `frontend/tests/unit/procedureEditorStore.spec.ts`

- [ ] **Step 1: 先运行现有测试，确认基线 PASS**

```bash
cd SmartSOP/frontend
npx vitest run tests/unit/procedureEditorStore.spec.ts
```

期望：全部 PASSED。

- [ ] **Step 2: 在 `procedureEditorStore.spec.ts` 中找到辅助函数 `chap()`，确认其签名**

文件约第 58 行：
```typescript
function chap(id: string, parentId: string | null, sort: number): EditorChapter {
  return {
    id,
    parent_id: parentId,
    content_type: 'chapter',
    title: '',
    rich_content: '',
    skip_numbering: false,
    mark_status: 'unmarked',
    sort_order: sort,
  }
}
```

- [ ] **Step 3: 在文件末尾追加 `toggleContentType` 测试**

```typescript
describe('toggleContentType', () => {
  it('switches chapter → content and marks dirty', () => {
    const store = useProcedureEditorStore()
    store.$patch({ procedure: meta(), chapters: [chap('c1', null, 0)], steps: [] })
    expect(store.chapterMap.get('c1')!.content_type).toBe('chapter')

    store.toggleContentType('c1')

    expect(store.chapterMap.get('c1')!.content_type).toBe('content')
    expect(store.dirtyChapters.has('c1')).toBe(true)
  })

  it('switches content → chapter', () => {
    const store = useProcedureEditorStore()
    const c: EditorChapter = { ...chap('c1', null, 0), content_type: 'content' }
    store.$patch({ procedure: meta(), chapters: [c], steps: [] })

    store.toggleContentType('c1')

    expect(store.chapterMap.get('c1')!.content_type).toBe('chapter')
  })

  it('ignores unknown id', () => {
    const store = useProcedureEditorStore()
    store.$patch({ procedure: meta(), chapters: [], steps: [] })
    expect(() => store.toggleContentType('nonexistent')).not.toThrow()
  })
})
```

- [ ] **Step 4: 运行测试，确认新测试 PASS**

```bash
npx vitest run tests/unit/procedureEditorStore.spec.ts
```

期望：全部 PASSED（含三个新用例）。

---

## Task 6：P0 — UI：`ChapterDetailPanel.vue` 类型切换

**Files:**
- Modify: `frontend/src/components/editor/ChapterDetailPanel.vue`

- [ ] **Step 1: 在模板 `<el-form-item label="章节标题">` 之前插入类型切换器**

打开 [`frontend/src/components/editor/ChapterDetailPanel.vue`](../../../frontend/src/components/editor/ChapterDetailPanel.vue)，在 `<el-form label-position="top">` 开始后（约第 53 行）插入：

```vue
      <el-form-item label="节点类型">
        <el-radio-group
          :model-value="chapter.content_type"
          :disabled="ro"
          size="small"
          @change="store.toggleContentType(chapter.id)"
        >
          <el-radio-button value="chapter">章节</el-radio-button>
          <el-radio-button value="content">内容块</el-radio-button>
        </el-radio-group>
      </el-form-item>
```

- [ ] **Step 2: 启动开发服务器，打开编辑器，选中一个 `chapter` 节点**

验证：
- 面板顶部出现"章节 / 内容块"切换按钮组，当前类型高亮
- 点击"内容块" → 树中该节点的图标变为 `📄`，编号变为 `.0` 样式
- Ctrl+Z 撤销 → 节点恢复为章节
- 点击保存 → 刷新页面后类型保持

---

## Task 7：P1 — Store actions：promote / demote

**Files:**
- Modify: `frontend/src/store/procedureEditor.ts`

- [ ] **Step 1: 在 `moveCrossParent` 之前添加 `canPromoteChapter` 和 `canDemoteChapter` 辅助方法**

在 `moveCrossParent`（约第 623 行）之前插入：

```typescript
    canPromoteChapter(id: string): boolean {
      const ch = this.chapterMap.get(id)
      return !!(ch && ch.parent_id)
    },

    canDemoteChapter(id: string): boolean {
      const ch = this.chapterMap.get(id)
      if (!ch) return false
      const siblings = this.chapters
        .filter((c) => c.parent_id === ch.parent_id)
        .sort((a, b) => (a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1))
      const myIdx = siblings.findIndex((c) => c.id === id)
      if (myIdx <= 0) return false
      return siblings[myIdx - 1].content_type === 'chapter'
    },
```

- [ ] **Step 2: 在 `moveCrossParent` 之后添加 `promoteChapter` 和 `demoteChapter` actions**

```typescript
    async promoteChapter(id: string): Promise<void> {
      if (!this.canPromoteChapter(id)) return
      const ch = this.chapterMap.get(id)!
      const parent = this.chapterMap.get(ch.parent_id!)!
      const grandParentId = parent.parent_id
      // 找到 parent 在其兄弟中的排序位置，把当前节点插到 parent 之后
      const parentSiblings = this.chapters
        .filter((c) => c.parent_id === grandParentId)
        .sort((a, b) => (a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1))
      const parentIdx = parentSiblings.findIndex((c) => c.id === parent.id)
      await this.moveCrossParent(id, grandParentId, parentIdx + 1)
    },

    async demoteChapter(id: string): Promise<void> {
      if (!this.canDemoteChapter(id)) return
      const ch = this.chapterMap.get(id)!
      const siblings = this.chapters
        .filter((c) => c.parent_id === ch.parent_id)
        .sort((a, b) => (a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1))
      const myIdx = siblings.findIndex((c) => c.id === id)
      const prevSibling = siblings[myIdx - 1]
      const prevChildren = this.chapters.filter((c) => c.parent_id === prevSibling.id)
      await this.moveCrossParent(id, prevSibling.id, prevChildren.length)
    },
```

---

## Task 8：P1 — 测试 `canPromoteChapter` / `canDemoteChapter`

**Files:**
- Modify: `frontend/tests/unit/procedureEditorStore.spec.ts`

- [ ] **Step 1: 追加 promote/demote 可用性测试**

```typescript
describe('canPromoteChapter', () => {
  it('returns false for root chapter', () => {
    const store = useProcedureEditorStore()
    store.$patch({ procedure: meta(), chapters: [chap('c1', null, 0)], steps: [] })
    expect(store.canPromoteChapter('c1')).toBe(false)
  })

  it('returns true for nested chapter', () => {
    const store = useProcedureEditorStore()
    store.$patch({
      procedure: meta(),
      chapters: [chap('c1', null, 0), chap('c2', 'c1', 0)],
      steps: [],
    })
    expect(store.canPromoteChapter('c2')).toBe(true)
  })
})

describe('canDemoteChapter', () => {
  it('returns false when no previous sibling', () => {
    const store = useProcedureEditorStore()
    store.$patch({ procedure: meta(), chapters: [chap('c1', null, 0)], steps: [] })
    expect(store.canDemoteChapter('c1')).toBe(false)
  })

  it('returns true when previous sibling is chapter', () => {
    const store = useProcedureEditorStore()
    store.$patch({
      procedure: meta(),
      chapters: [chap('c1', null, 0), chap('c2', null, 1)],
      steps: [],
    })
    expect(store.canDemoteChapter('c2')).toBe(true)
  })

  it('returns false when previous sibling is content', () => {
    const store = useProcedureEditorStore()
    const contentNode: EditorChapter = { ...chap('c1', null, 0), content_type: 'content' }
    store.$patch({
      procedure: meta(),
      chapters: [contentNode, chap('c2', null, 1)],
      steps: [],
    })
    expect(store.canDemoteChapter('c2')).toBe(false)
  })
})
```

- [ ] **Step 2: 运行测试，确认 PASS**

```bash
npx vitest run tests/unit/procedureEditorStore.spec.ts
```

期望：全部 PASSED。

---

## Task 9：P1 — TreeRow 增加 promote/demote 按钮

**Files:**
- Modify: `frontend/src/components/editor/TreeRow.vue`

- [ ] **Step 1: 在 `defineEmits` 中添加新事件**

打开 [`frontend/src/components/editor/TreeRow.vue`](../../../frontend/src/components/editor/TreeRow.vue)，找到 `defineEmits`（约第 19 行）：

```typescript
const emit = defineEmits<{
  (e: 'select'): void
  (e: 'toggle'): void
  (e: 'check', shift: boolean): void
  (e: 'add', kind: 'chapter' | 'content' | 'step'): void
  (e: 'move', dir: 'up' | 'down'): void
  (e: 'remove'): void
  (e: 'dragstart', ev: DragEvent): void
  (e: 'dragover', ev: DragEvent): void
  (e: 'drop', ev: DragEvent): void
  (e: 'dragend'): void
}>()
```

改为：

```typescript
const emit = defineEmits<{
  (e: 'select'): void
  (e: 'toggle'): void
  (e: 'check', shift: boolean): void
  (e: 'add', kind: 'chapter' | 'content' | 'step'): void
  (e: 'move', dir: 'up' | 'down'): void
  (e: 'promote'): void
  (e: 'demote'): void
  (e: 'remove'): void
  (e: 'dragstart', ev: DragEvent): void
  (e: 'dragover', ev: DragEvent): void
  (e: 'drop', ev: DragEvent): void
  (e: 'dragend'): void
}>()
```

- [ ] **Step 2: 在 props 中添加 `canPromote` / `canDemote`**

找到 `props` 定义，添加两个新属性：

```typescript
const props = defineProps<{
  row: FlatRow
  selected: boolean
  editable: boolean
  markMode: boolean
  addState: AddButtonState
  canMoveUp: boolean
  canMoveDown: boolean
  canPromote: boolean
  canDemote: boolean
}>()
```

- [ ] **Step 3: 在操作按钮区插入 promote/demote 按钮**

找到 `↑` 按钮之前（`<el-button size="small" text :disabled="!canMoveUp"...`，约第 116 行），在其前面插入：

```vue
      <el-button
        v-if="row.kind === 'chapter' || row.kind === 'content'"
        size="small"
        text
        :disabled="!canPromote"
        title="提升层级（Shift+Tab）"
        @click="emit('promote')"
      >⇤</el-button>
      <el-button
        v-if="row.kind === 'chapter' || row.kind === 'content'"
        size="small"
        text
        :disabled="!canDemote"
        title="降低层级（Tab）"
        @click="emit('demote')"
      >⇥</el-button>
```

---

## Task 10：P1 — ChapterTreePanel 处理 promote/demote

**Files:**
- Modify: `frontend/src/components/editor/ChapterTreePanel.vue`

- [ ] **Step 1: 找到 `<TreeRow>` 的使用位置（约第 150 行），在属性列表中添加 `canPromote`/`canDemote`，并绑定事件**

找到模板中的 `<TreeRow ...>` 组件（在 `<template v-for="{ data: row } in list"...>` 内），完整替换为：

```vue
<TreeRow
  :row="row"
  :selected="store.selectedId === row.id"
  :editable="store.editable"
  :mark-mode="store.markMode"
  :add-state="addStateFor(row)"
  :can-move-up="moveFlags.get(row.id)?.up ?? false"
  :can-move-down="moveFlags.get(row.id)?.down ?? false"
  :can-promote="row.kind !== 'step' && store.canPromoteChapter(row.id)"
  :can-demote="row.kind !== 'step' && store.canDemoteChapter(row.id)"
  @select="onSelect(row)"
  @toggle="store.toggleExpanded(row.id)"
  @check="(shift) => onCheck(row, shift)"
  @add="(kind) => onAdd(row.id, kind)"
  @move="(dir) => onMove(row, dir)"
  @promote="void store.promoteChapter(row.id)"
  @demote="void store.demoteChapter(row.id)"
  @remove="onRemove(row)"
  @dragstart="(ev) => onDragStart(row, ev)"
  @dragover="(ev) => onDragOver(row, ev)"
  @drop="(ev) => onDrop(row, ev)"
  @dragend="onDragEnd"
/>
```

- [ ] **Step 2: 验证 promote/demote 按钮在浏览器中可见且功能正常**

打开编辑器，选择一个二级章节（level 2）：
- 应出现 `⇤`（提升，enabled）和 `⇥`（降低，enabled/disabled 视情况）
- 点击 `⇤` → 该章节移至其父章节的同级（level 1）
- 根章节（level 1）的 `⇤` 应为 disabled

---

## Task 11：P1 — TreeRow 测试

**Files:**
- Modify: `frontend/tests/unit/TreeRow.spec.ts`

- [ ] **Step 1: 运行现有 TreeRow 测试，确认基线**

```bash
npx vitest run tests/unit/TreeRow.spec.ts
```

- [ ] **Step 2: 追加 promote/demote 按钮可见性测试**

在文件末尾追加（参考现有测试中的 `wrapper` 构建方式）：

```typescript
describe('promote/demote buttons', () => {
  function makeRow(kind: 'chapter' | 'content' | 'step'): FlatRow {
    return {
      id: 'r1', kind, depth: 1, parent_id: 'p1',
      title: '测试', code: '1.0', skip_numbering: false,
      mark_status: 'unmarked', form_type: null,
      require_confirmation: false, has_children: false,
      expanded: false, fallback: '',
    }
  }

  it('shows promote/demote buttons for chapter', () => {
    const wrapper = mount(TreeRow, {
      props: {
        row: makeRow('chapter'), selected: false, editable: true, markMode: false,
        addState: { canAddChapter: false, canAddContent: false, canAddStep: false },
        canMoveUp: false, canMoveDown: false, canPromote: true, canDemote: true,
      },
    })
    expect(wrapper.text()).toContain('⇤')
    expect(wrapper.text()).toContain('⇥')
  })

  it('shows promote/demote buttons for content', () => {
    const wrapper = mount(TreeRow, {
      props: {
        row: makeRow('content'), selected: false, editable: true, markMode: false,
        addState: { canAddChapter: false, canAddContent: false, canAddStep: false },
        canMoveUp: false, canMoveDown: false, canPromote: false, canDemote: false,
      },
    })
    expect(wrapper.text()).toContain('⇤')
    expect(wrapper.text()).toContain('⇥')
  })

  it('does not show promote/demote for step', () => {
    const wrapper = mount(TreeRow, {
      props: {
        row: makeRow('step'), selected: false, editable: true, markMode: false,
        addState: { canAddChapter: false, canAddContent: false, canAddStep: false },
        canMoveUp: false, canMoveDown: false, canPromote: false, canDemote: false,
      },
    })
    expect(wrapper.text()).not.toContain('⇤')
    expect(wrapper.text()).not.toContain('⇥')
  })
})
```

- [ ] **Step 3: 运行 TreeRow 测试，确认 PASS**

```bash
npx vitest run tests/unit/TreeRow.spec.ts
```

期望：全部 PASSED。

- [ ] **Step 4: 提交 P0 + P1**

```bash
git add frontend/src/store/procedureEditor.ts \
        frontend/src/components/editor/ChapterDetailPanel.vue \
        frontend/src/components/editor/TreeRow.vue \
        frontend/src/components/editor/ChapterTreePanel.vue \
        frontend/tests/unit/procedureEditorStore.spec.ts \
        frontend/tests/unit/TreeRow.spec.ts
git commit -m "feat(editor): P0 content-type toggle + P1 promote/demote

P0: Add toggleContentType() store action and chapter/content radio-button
switcher in ChapterDetailPanel. Uses existing save path (ChapterUpsert),
no new API needed.

P1: Add promoteChapter()/demoteChapter() store actions + canPromote/
canDemote helpers. TreeRow shows ⇤/⇥ buttons for chapter/content nodes."
```

---

## Task 12：P2 — 键盘快捷键 Tab / Shift+Tab

**Files:**
- Modify: `frontend/src/composables/useEditorKeyboard.ts`
- Modify: `frontend/src/views/procedures/ProcedureEditorView.vue`

- [ ] **Step 1: 扩展 `Handlers` 接口，添加 Tab 快捷键处理**

打开 [`frontend/src/composables/useEditorKeyboard.ts`](../../../frontend/src/composables/useEditorKeyboard.ts)，将 `Handlers` 接口改为：

```typescript
interface Handlers {
  onSave: () => void
  onUndo: () => void
  onRedo: () => void
  onFocusSearch: () => void
  onDelete: () => void
  onEsc: () => void
  onPromote: () => void
  onDemote: () => void
}
```

- [ ] **Step 2: 在 `handler` 函数中，在 `Escape` 处理之前插入 Tab 处理**

在 `if (e.key === 'Escape') h.onEsc()` 之前插入：

```typescript
    if (e.key === 'Tab' && !isTyping(e.target)) {
      e.preventDefault()
      if (e.shiftKey) h.onPromote()
      else h.onDemote()
      return
    }
```

- [ ] **Step 3: 在 `ProcedureEditorView.vue` 的 `useEditorKeyboard` 调用中补充新 handler**

打开 [`frontend/src/views/procedures/ProcedureEditorView.vue`](../../../frontend/src/views/procedures/ProcedureEditorView.vue)，找到 `useEditorKeyboard({...})`（约第 177 行），在 `onEsc` 之后追加：

```typescript
  onPromote: () => {
    const id = store.selectedId
    if (id && store.editable) void store.promoteChapter(id)
  },
  onDemote: () => {
    const id = store.selectedId
    if (id && store.editable) void store.demoteChapter(id)
  },
```

- [ ] **Step 4: 验证键盘快捷键**

打开编辑器，选中一个二级章节节点（不在输入框内）：
- 按 `Shift+Tab` → 章节升级（提升到上一层）
- 按 `Tab` → 章节降级（进入前一兄弟的子节点）
- 在输入框内按 Tab → 正常 Tab 缩进，不触发升降级

- [ ] **Step 5: 提交 P2**

```bash
git add frontend/src/composables/useEditorKeyboard.ts \
        frontend/src/views/procedures/ProcedureEditorView.vue
git commit -m "feat(editor): P2 Tab/Shift+Tab keyboard shortcuts for promote/demote

Wire Tab → demoteChapter and Shift+Tab → promoteChapter in
useEditorKeyboard. Skipped when focus is inside an input/textarea/
contenteditable element."
```

---

## 完整回归验证

- [ ] **后端全量测试**

```bash
cd SmartSOP/backend
python -m pytest tests/ -v --tb=short
```

期望：全部 PASSED。

- [ ] **前端全量测试**

```bash
cd SmartSOP/frontend
npx vitest run
```

期望：全部 PASSED。

---

## 自审核清单

### 规格覆盖
- [x] 方案C：手动目录 TOC 跳过 → Task 1–3
- [x] P0：章节↔内容块切换 → Task 4–6
- [x] P1：升级/降级按钮 → Task 7–11
- [x] P2：Tab/Shift+Tab 快捷键 → Task 12

### 边界情况
- [x] 全标题无正文文档不崩溃（Task 3 第二个测试）
- [x] 根节点 promote disabled（`canPromoteChapter` 返回 false）
- [x] 无前驱兄弟时 demote disabled（`canDemoteChapter` 返回 false）
- [x] 前驱兄弟为 content 类型时 demote disabled（不能作为父节点）
- [x] Step 节点不显示 promote/demote 按钮
- [x] 输入框内 Tab 不触发快捷键（`isTyping` 守卫）
- [x] content_type 切换支持 Ctrl+Z 撤销（走 `updateChapterFields` → `pushUndo`）
