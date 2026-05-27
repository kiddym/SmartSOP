# 前端编辑能力增强 A+B+C 三件套 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不动 parser 与解析数据模型的前提下，为编辑器加上 3 个用户主导的结构后处理操作（树行 tooltip / 章节转内容 / 在光标处拆 heading+content），解决约 180 个融合式 chapter 的 UX 摩擦。

**Architecture:** A 纯前端渲染（el-tooltip 包裹）。B/C 后端各加 1 个原子 endpoint，复用 `conversion_service` 的辅助函数（`_get_chapter` / `_get_proc_editable` / `_chapter_has_children` / `_other_chapter_children_count` / `numbering_service.recompute` / `optimistic_lock.bump` / `audit_service.log_procedure_action`）；前端 store 新增 2 个 action，调用后整段 refetch 以保一致性（沿用 `convertToStep` 模式）；TreeRow 加菜单项 + ChapterDetailPanel 加按钮。

**Tech Stack:** 后端 FastAPI + SQLAlchemy + pytest；前端 Vue 3 + Pinia + Element Plus + vitest。

**Spec source:** [`docs/superpowers/specs/2026-05-27-frontend-editing-affordances-design.md`](../specs/2026-05-27-frontend-editing-affordances-design.md)

**Branch:** 当前 `docs/frontend-editing-affordances-spec`（只含 spec）→ 实施分支建议 `feat/frontend-editing-affordances`（从 main 起；spec 通过 PR 合 main 后切）

---

## 文件结构

### 后端

| 文件 | 责任 | 改动类型 |
|---|---|---|
| `backend/app/services/conversion_service.py` | 加 `convert_to_content(db, chapter_id, meta)` + `split_title_content(db, chapter_id, cursor_offset, meta)` 函数 | 新增 + 复用 helper |
| `backend/app/routers/chapters.py` | 加 2 个 router：`POST /api/v1/chapters/{id}/convert-to-content` + `POST /api/v1/chapters/{id}/split-title-content` | 新增 |
| `backend/app/schemas/node.py` | 加 `SplitTitleContentIn` request schema（包含 `cursor_offset: int`） | 新增 |
| `backend/app/errors.py`（如已有）/ 错误码常量 | `INVALID_CURSOR` / `EMPTY_CONTENT` 错误码 | 字符串常量，无新文件 |
| `backend/tests/unit/services/test_conversion_service.py` | 追加 13 个测试用例（B 6 + C 7） | 修改 |

### 前端

| 文件 | 责任 | 改动类型 |
|---|---|---|
| `frontend/src/utils/editor.ts` | 导出 `TITLE_TOOLTIP_THRESHOLD = 30` | 新增常量 |
| `frontend/src/api/chapters.ts` | 加 `convertChapterToContent(id)` + `splitChapterTitleContent(id, cursorOffset)` API 包装 | 新增 |
| `frontend/src/components/editor/TreeRow.vue` | `.tr-title` 用 el-tooltip 包裹；⋮ 菜单加"转为内容块"项；扩展 onMore 命令类型 | 修改 |
| `frontend/src/components/editor/ChapterDetailPanel.vue` | textarea 下加"在光标处拆为标题+内容"按钮；ref 拿光标 offset；触发 store action | 修改 |
| `frontend/src/store/procedureEditor.ts` | 加 `convertChapterToContent(id)` + `splitChapterTitleContent(id, offset)` + `inflightSplit: Set<string>` 字段 | 新增 action |
| `frontend/tests/unit/TreeRow.spec.ts` | 追加 4 个 case：tooltip disabled 阈值 + 菜单项可见性 | 修改 |
| `frontend/tests/unit/ChapterDetailPanel.spec.ts` | 追加 4 个 case：拆按钮 disabled 规则 + emit | 修改 |
| `frontend/tests/unit/procedureEditorStore.spec.ts` | 追加 6 个 case：action 调用 + selectNode + undo + inflight 拦截 | 修改 |

---

## 实施顺序总览

```
M1 — A 树行 tooltip               (前端独立)
 ↓
M2 — B 后端 convert-to-content     (后端独立)
 ↓
M3 — B 前端 store + 菜单项 + 测试  (依赖 M2 endpoint)
 ↓
M4 — C 后端 split-title-content    (后端独立，但建议在 M2 之后做以复用 helper 经验)
 ↓
M5 — C 前端 ChapterDetailPanel + store + 测试 (依赖 M4 endpoint)
 ↓
M6 — 浏览器实测 + 截图存档 (Chrome DevTools MCP 36 份样本里抽 5 份融合式 chapter 走通整流程)
```

每个 M 一个独立 commit，可独立部署、独立 review。

---

### Task M1: 树行 tooltip（A）

**Files:**
- Modify: `frontend/src/utils/editor.ts`（加常量）
- Modify: `frontend/src/components/editor/TreeRow.vue:92`（包裹 `.tr-title`；当前文件 264 行）
- Modify: `frontend/tests/unit/TreeRow.spec.ts`（追加测试）

- [ ] **Step 1: 加常量 TITLE_TOOLTIP_THRESHOLD**

打开 `frontend/src/utils/editor.ts`，在文件末尾追加：

```ts
// 树行标题 tooltip 阈值（CJK 字符；30 字之内的 chapter 标题在 240-360px 列宽下基本不省略）
export const TITLE_TOOLTIP_THRESHOLD = 30
```

- [ ] **Step 2: 写失败测试 — tooltip 阈值 disabled**

在 `frontend/tests/unit/TreeRow.spec.ts` 中追加（参考文件首部已有的 mount/import 模式；如无可仿照其他 .spec.ts 文件）：

```ts
import { TITLE_TOOLTIP_THRESHOLD } from '@/utils/editor'

describe('TreeRow title tooltip', () => {
  function makeRow(overrides: Partial<FlatRow> = {}): FlatRow {
    return {
      id: 'r1', kind: 'chapter', depth: 0, code: '1',
      title: '短标题', fallback: '未命名章节',
      sort_order: 0, has_children: false, expanded: true,
      mark_status: 'unmarked', skip_numbering: false,
      ...overrides,
    } as FlatRow
  }
  function mountRow(row: FlatRow) {
    return mount(TreeRow, {
      props: {
        row, selected: false, markMode: false, selectedForMark: false,
        addState: { canAddChapter: true, canAddContent: true, canAddStep: true },
        editable: true, canMoveUp: false, canMoveDown: false, dropHint: '',
      },
    })
  }

  it('disables tooltip when chapter title length <= threshold', () => {
    const w = mountRow(makeRow({ title: 'a'.repeat(TITLE_TOOLTIP_THRESHOLD) }))
    const tip = w.findComponent({ name: 'ElTooltip' })
    expect(tip.exists()).toBe(true)
    expect(tip.props('disabled')).toBe(true)
  })

  it('enables tooltip when chapter title length > threshold', () => {
    const w = mountRow(makeRow({ title: 'a'.repeat(TITLE_TOOLTIP_THRESHOLD + 1) }))
    const tip = w.findComponent({ name: 'ElTooltip' })
    expect(tip.props('disabled')).toBe(false)
  })

  it('disables tooltip for non-chapter kind even with long title', () => {
    const w = mountRow(makeRow({ kind: 'content', title: 'a'.repeat(100) }))
    const tip = w.findComponent({ name: 'ElTooltip' })
    expect(tip.props('disabled')).toBe(true)
  })
})
```

- [ ] **Step 3: 运行测试确认失败**

```bash
cd frontend && npx vitest run tests/unit/TreeRow.spec.ts -t "title tooltip"
```

期望：3 个 case 全失败（el-tooltip 还没加）。

- [ ] **Step 4: 实现 TreeRow.vue 的 tooltip 包裹**

在 `frontend/src/components/editor/TreeRow.vue` 中：

(a) 在 `<script setup>` 顶部 import：
```ts
import { computed } from 'vue'
import { FORM_TYPE_META, TITLE_TOOLTIP_THRESHOLD } from '@/utils/editor'
```

(b) 在 script 末尾加 computed：
```ts
const tooltipDisabled = computed(
  () => props.row.kind !== 'chapter' || display.value.length <= TITLE_TOOLTIP_THRESHOLD
)
```

(c) 把模板里第 92 行 `<span class="tr-title" ...>` 包裹为：
```html
<el-tooltip
  :content="display"
  :disabled="tooltipDisabled"
  placement="top-start"
  :show-after="300"
  popper-class="tr-title-tooltip"
>
  <span class="tr-title" :class="{ 'tr-title--fallback': titleFallback }">{{ display }}</span>
</el-tooltip>
```

(d) 在 `<style scoped>` 末尾追加（注意 popper 是全局 class，需用 `:deep` 或写到非 scoped）：
```html
<style>
.tr-title-tooltip {
  max-width: 400px;
  white-space: normal;
  word-break: break-word;
}
</style>
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd frontend && npx vitest run tests/unit/TreeRow.spec.ts
```

期望：所有 TreeRow 测试通过（包括既有的）。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/utils/editor.ts frontend/src/components/editor/TreeRow.vue frontend/tests/unit/TreeRow.spec.ts
git commit -m "feat(editor): 树行 chapter 长标题 tooltip (A) — 30 字阈值 + el-tooltip 包裹

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task M2: B 后端 — convert-to-content endpoint + service

**Files:**
- Modify: `backend/app/services/conversion_service.py`（加 `convert_to_content`；当前 378 行）
- Modify: `backend/app/routers/chapters.py`（加 1 个 router；当前 149 行）
- Modify: `backend/tests/unit/services/test_conversion_service.py`（追加 6 个 case）

- [ ] **Step 1: 写失败测试 — convert_to_content happy path**

在 `backend/tests/unit/services/test_conversion_service.py` 文件末尾追加：

```python
# --------------------------------------------------------------------------- #
# chapter → content（融合式标题降级）
# --------------------------------------------------------------------------- #
def test_convert_to_content_happy(db: Session, factory: Factory) -> None:
    """无 children 的唯一 chapter → 转换成 content step；chapter 软删；title 搬运到 step.content。"""
    proc = _proc(factory)
    ch = factory.chapter(proc.id, title="3.1质量部是记录的归口管理部门，负责...")

    result = conversion_service.convert_to_content(db, ch.id, META)
    db.commit()

    db.refresh(ch)
    assert ch.is_active is False
    assert result.deleted == [ch.id]
    assert len(result.created) == 1
    new_step = step_service.get_step(db, result.created[0])
    assert new_step.kind == "content"
    assert new_step.title == ""
    assert new_step.content == "3.1质量部是记录的归口管理部门，负责..."
    assert new_step.chapter_id == ch.parent_id  # None for root


def test_convert_to_content_has_child_chapter(db: Session, factory: Factory) -> None:
    """有子 chapter → CHAPTER_HAS_CHILDREN。"""
    proc = _proc(factory)
    parent = factory.chapter(proc.id, title="父章节")
    factory.chapter(proc.id, parent_id=parent.id, title="子章节")

    with pytest.raises(HTTPException) as exc:
        conversion_service.convert_to_content(db, parent.id, META)
    assert exc.value.detail["code"] == "CHAPTER_HAS_CHILDREN"


def test_convert_to_content_has_child_step(db: Session, factory: Factory) -> None:
    """有子 step → CHAPTER_HAS_CHILDREN。"""
    proc = _proc(factory)
    ch = factory.chapter(proc.id, title="章节")
    factory.step(proc.id, chapter_id=ch.id, kind="step", title="子步骤")

    with pytest.raises(HTTPException) as exc:
        conversion_service.convert_to_content(db, ch.id, META)
    assert exc.value.detail["code"] == "CHAPTER_HAS_CHILDREN"


def test_convert_to_content_sibling_chapter_conflict(db: Session, factory: Factory) -> None:
    """同级仍有 chapter → SIBLING_TYPE_CONFLICT（Q25 互斥）。"""
    proc = _proc(factory)
    ch1 = factory.chapter(proc.id, title="章节A")
    factory.chapter(proc.id, title="章节B")  # 同级 sibling

    with pytest.raises(HTTPException) as exc:
        conversion_service.convert_to_content(db, ch1.id, META)
    assert exc.value.detail["code"] == "SIBLING_TYPE_CONFLICT"


def test_convert_to_content_readonly_procedure(db: Session, factory: Factory) -> None:
    """非 DRAFT 程序 → PROCEDURE_READONLY。"""
    proc = _proc(factory)
    proc.status = "RELEASED"
    db.flush()
    ch = factory.chapter(proc.id, title="章节")

    with pytest.raises(HTTPException) as exc:
        conversion_service.convert_to_content(db, ch.id, META)
    assert exc.value.detail["code"] == "PROCEDURE_READONLY"


def test_convert_to_content_bumps_revision(db: Session, factory: Factory) -> None:
    """转换后 procedure version bump + numbering recompute。"""
    proc = _proc(factory)
    ch = factory.chapter(proc.id, title="章节")
    initial_version = proc.version

    conversion_service.convert_to_content(db, ch.id, META)
    db.commit()
    db.refresh(proc)

    assert proc.version > initial_version
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/services/test_conversion_service.py -k convert_to_content -v
```

期望：6 个 case 全失败（`convert_to_content` 函数不存在）。

- [ ] **Step 3: 实现 convert_to_content service 函数**

在 `backend/app/services/conversion_service.py` 末尾追加（在 `convert_to_chapter` 之后）：

```python
# --------------------------------------------------------------------------- #
# chapter → content（融合式标题降级；Q25 同级互斥）
# --------------------------------------------------------------------------- #
def convert_to_content(db: Session, chapter_id: str, meta: RequestMeta) -> ConversionResult:
    """章节降级为内容块。原 title 搬运到新 step.content；chapter 软删。

    校验：
    - 章节无任何子节点（CHAPTER_HAS_CHILDREN）
    - 同级 siblings 不混类型（SIBLING_TYPE_CONFLICT；天然覆盖根 chapter 周围还有 chapter 的场景）
    """
    ch = _get_chapter(db, chapter_id)
    proc = _get_proc_editable(db, ch.procedure_id)

    if _chapter_has_children(db, proc.id, ch.id):
        raise bad_request("CHAPTER_HAS_CHILDREN", "章节含子节点，不能转为内容块")
    if _other_chapter_children_count(db, proc.id, ch.parent_id, ch.id) > 0:
        raise bad_request("SIBLING_TYPE_CONFLICT", "同级仍有章节，转换会违反互斥规则")

    step = ProcedureStep(
        procedure_id=proc.id,
        chapter_id=ch.parent_id,
        kind="content",
        title="",
        content=ch.title,
        input_schema={},
        sort_order=0,
    )
    db.add(step)
    ch.is_active = False
    ch.deleted_at = utcnow()
    db.flush()
    numbering_service.recompute(db, proc.id)
    optimistic_lock.bump(proc)
    db.flush()
    _audit(
        db,
        proc,
        target_id=step.id,
        action="chapter-to-content",
        meta=meta,
        old_value={"chapter_id": ch.id, "title": ch.title},
    )
    return ConversionResult(created=[step.id], deleted=[ch.id])
```

- [ ] **Step 4: 加 router**

在 `backend/app/routers/chapters.py` 末尾追加（在 `convert_root_to_step` 之后，line 146 附近）：

```python
@router.post("/{chapter_id}/convert-to-content", response_model=ConversionResult)
def convert_to_content(
    chapter_id: str, db: Session = Depends(get_db), meta: RequestMeta = Depends(get_request_meta)
) -> ConversionResult:
    result = conversion_service.convert_to_content(db, chapter_id, meta)
    db.commit()
    return result
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/services/test_conversion_service.py -k convert_to_content -v
```

期望：6 个 case 通过。再跑全量回归确保未坏既有：

```bash
cd backend && .venv/bin/python -m pytest tests/unit/services/test_conversion_service.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/conversion_service.py backend/app/routers/chapters.py backend/tests/unit/services/test_conversion_service.py
git commit -m "feat(backend): chapter→content 原子转换 endpoint (B) — POST /chapters/:id/convert-to-content

复用 conversion_service 现有 helper（_get_chapter / _other_chapter_children_count /
numbering_service.recompute / optimistic_lock.bump / audit）。

校验：
- 无 children (CHAPTER_HAS_CHILDREN)
- 同级不混类型 (SIBLING_TYPE_CONFLICT, Q25)
- 程序可编辑 (PROCEDURE_READONLY)

6 个单测覆盖 happy path / 3 种校验失败 / revision bump。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task M3: B 前端 — store action + TreeRow 菜单 + 测试

**Files:**
- Modify: `frontend/src/api/chapters.ts`（加 1 个 API 包装）
- Modify: `frontend/src/store/procedureEditor.ts`（加 1 个 action）
- Modify: `frontend/src/components/editor/TreeRow.vue`（菜单加项 + onMore 扩展）
- Modify: `frontend/tests/unit/procedureEditorStore.spec.ts`（追加测试）
- Modify: `frontend/tests/unit/TreeRow.spec.ts`（追加菜单可见性测试）

- [ ] **Step 1: 加 API 包装**

在 `frontend/src/api/chapters.ts` 末尾追加：

```ts
export const convertChapterToContent = async (id: string): Promise<ConversionResult> =>
  (await http.post<ConversionResult>(`/chapters/${id}/convert-to-content`)).data
```

- [ ] **Step 2: 写失败测试 — store action 行为**

在 `frontend/tests/unit/procedureEditorStore.spec.ts` 中追加（沿用文件已有的 mock http + setupStore 模式；若无现成 mock 仿照已有 convertToStep 测试）：

```ts
describe('procedureEditorStore.convertChapterToContent', () => {
  it('calls API and selects new step', async () => {
    const mockPost = vi.fn().mockResolvedValue({
      data: { created: ['new-step-id'], deleted: ['ch-1'] },
    })
    vi.mocked(http.post).mockImplementation(mockPost)

    const store = useProcedureEditorStore()
    await store.loadProcedure({ id: 'proc-1', chapters: [{ id: 'ch-1', title: '章节' }], steps: [] })
    const refreshSpy = vi.spyOn(store, 'refreshAfterConversion')

    await store.convertChapterToContent('ch-1')

    expect(mockPost).toHaveBeenCalledWith('/chapters/ch-1/convert-to-content')
    expect(refreshSpy).toHaveBeenCalled()
    expect(store.selectedNodeId).toBe('new-step-id')
  })

  it('records undo on success', async () => {
    vi.mocked(http.post).mockResolvedValue({ data: { created: ['new-id'], deleted: ['ch-1'] } })
    const store = useProcedureEditorStore()
    await store.loadProcedure({ id: 'proc-1', chapters: [{ id: 'ch-1', title: '章节' }], steps: [] })
    const before = store.undoStack.length

    await store.convertChapterToContent('ch-1')

    expect(store.undoStack.length).toBe(before + 1)
  })

  it('does not mutate state on API failure', async () => {
    vi.mocked(http.post).mockRejectedValue(new Error('500 error'))
    const store = useProcedureEditorStore()
    await store.loadProcedure({ id: 'proc-1', chapters: [{ id: 'ch-1', title: '章节' }], steps: [] })
    const before = store.undoStack.length

    await expect(store.convertChapterToContent('ch-1')).rejects.toThrow()

    expect(store.undoStack.length).toBe(before)
    expect(store.chapters.find((c) => c.id === 'ch-1')).toBeDefined()
  })
})
```

- [ ] **Step 3: 运行测试确认失败**

```bash
cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts -t "convertChapterToContent"
```

期望：3 个 case 全失败（action 不存在）。

- [ ] **Step 4: 实现 store action**

在 `frontend/src/store/procedureEditor.ts` 中：

(a) 顶部 import 补充：
```ts
import { convertChapterToContent as convertChapterToContentApi } from '@/api/chapters'
```

(b) 在 `actions` 中（紧挨现有 `convertToStep` 之后）追加：
```ts
async convertChapterToContent(id: string): Promise<void> {
  const map = await this.ensureSaved()
  const realId = map[id] ?? id
  const result = await convertChapterToContentApi(realId)
  await this.refreshAfterConversion(result)
  this.pushUndo(`chapter-to-content:${realId}`)
  if (result.created.length > 0) this.selectNode(result.created[0])
},
```

(c) 如果 store 中尚无 `refreshAfterConversion` helper，仿照现有 `convertToStep` 的成功后处理路径加：
```ts
async refreshAfterConversion(_result: ConversionResult): Promise<void> {
  // 沿用 loadProcedure 的整段刷新；result 参数预留给将来更细的 patch
  await this.reload()
},
```
（如已有等价函数则不重复；查 store 1028 LOC 里的 `reload` / `refetch` / `loadProcedure` 命名按现状）

- [ ] **Step 5: 运行 store 测试确认通过**

```bash
cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts -t "convertChapterToContent"
```

期望：3 个 case 通过。

- [ ] **Step 6: 写失败测试 — TreeRow 菜单可见性**

在 `frontend/tests/unit/TreeRow.spec.ts` 中追加：

```ts
describe('TreeRow chapter-to-content menu item', () => {
  function mountChapterRow(opts: { has_children: boolean }) {
    return mount(TreeRow, {
      props: {
        row: {
          id: 'r1', kind: 'chapter', depth: 0, code: '1',
          title: '章节', fallback: '未命名章节',
          sort_order: 0, has_children: opts.has_children, expanded: true,
          mark_status: 'unmarked', skip_numbering: false,
        } as FlatRow,
        selected: false, markMode: false, selectedForMark: false,
        addState: { canAddChapter: false, canAddContent: false, canAddStep: false },
        editable: true, canMoveUp: false, canMoveDown: false, dropHint: '',
      },
    })
  }

  it('renders chapter-to-content item for chapter without children', async () => {
    const w = mountChapterRow({ has_children: false })
    // 验证菜单项存在（参考 [[el-dropdown-jsdom-test]]：不验证 popper 真实 DOM，验证 dropdown 的 commands 通过 $emit）
    const dropdown = w.findAllComponents({ name: 'ElDropdown' }).find(d => d.vm.$attrs.class === 'more-trigger' || d.vm.$props.trigger === 'click')
    expect(dropdown).toBeDefined()
    // 直接验证内部 DropdownItem
    const items = w.findAllComponents({ name: 'ElDropdownItem' })
    const target = items.find(it => it.attributes('command') === 'chapter-to-content' || it.props('command') === 'chapter-to-content')
    expect(target).toBeDefined()
    expect(target!.props('disabled')).toBe(false)
  })

  it('disables chapter-to-content when chapter has children', () => {
    const w = mountChapterRow({ has_children: true })
    const items = w.findAllComponents({ name: 'ElDropdownItem' })
    const target = items.find(it => it.props('command') === 'chapter-to-content')
    expect(target!.props('disabled')).toBe(true)
  })

  it('emits convert chapter-to-content on item click via $emit (not real DOM)', async () => {
    const w = mountChapterRow({ has_children: false })
    // 走 ElDropdown 的 @command 直接触发，绕过 popper（jsdom 限制）
    const dropdown = w.findAllComponents({ name: 'ElDropdown' })[1]  // 第二个 dropdown = ⋮ 菜单
    await dropdown.vm.$emit('command', 'chapter-to-content')
    expect(w.emitted('convert')).toBeDefined()
    expect(w.emitted('convert')![0]).toEqual(['chapter-to-content'])
  })
})
```

- [ ] **Step 7: 运行测试确认失败**

```bash
cd frontend && npx vitest run tests/unit/TreeRow.spec.ts -t "chapter-to-content"
```

期望：3 个 case 全失败。

- [ ] **Step 8: 实现 TreeRow 菜单项**

在 `frontend/src/components/editor/TreeRow.vue` 中：

(a) 修改 `onMore` 函数（line 34）支持新命令：
```ts
function onMore(c: 'to-step' | 'to-content' | 'chapter-to-content' | 'remove'): void {
  if (c === 'remove') emit('remove')
  else if (c === 'chapter-to-content') emit('convert', 'chapter-to-content' as 'to-step' | 'to-content')
  else emit('convert', c)
}
```

> 注：`emit('convert', ...)` 的类型签名 `(dir: 'to-step' | 'to-content')` 需扩展为 `'to-step' | 'to-content' | 'chapter-to-content'`。修改 `defineEmits<...>` 处对应签名。

(b) 在 `<el-dropdown-menu>` 内（line 120-125 附近）的"删除"项之前追加：
```html
<el-dropdown-item
  v-if="row.kind === 'chapter'"
  command="chapter-to-content"
  :disabled="row.has_children"
>
  转为内容块
</el-dropdown-item>
```

- [ ] **Step 9: 父组件 ChapterTreePanel.vue 接 convert 事件**

打开 `frontend/src/components/editor/ChapterTreePanel.vue`（前面看过 18378 字节），找到现有处理 `@convert` 事件的位置（应当与 `convertToStep` 同处），扩展 switch / if：

```ts
// 现有的 handleConvert 函数（命名以实际为准）
function handleConvert(row: FlatRow, dir: 'to-step' | 'to-content' | 'chapter-to-content'): void {
  if (dir === 'to-step') store.convertToStep(row.id)
  else if (dir === 'to-content') store.setStepKind(row.id, 'content')   // 现有逻辑
  else if (dir === 'chapter-to-content') store.convertChapterToContent(row.id)
}
```

实施时**先 grep 当前实现**：
```bash
grep -n "convertToStep\|to-content\|to-step" frontend/src/components/editor/ChapterTreePanel.vue
```
按现有结构追加分支。

- [ ] **Step 10: 运行测试确认通过**

```bash
cd frontend && npx vitest run tests/unit/TreeRow.spec.ts -t "chapter-to-content"
cd frontend && npx vitest run
```

期望：所有相关测试通过；全量 vitest 不引回归。

- [ ] **Step 11: Commit**

```bash
git add frontend/src/api/chapters.ts frontend/src/store/procedureEditor.ts frontend/src/components/editor/TreeRow.vue frontend/src/components/editor/ChapterTreePanel.vue frontend/tests/unit/procedureEditorStore.spec.ts frontend/tests/unit/TreeRow.spec.ts
git commit -m "feat(editor): 章节转内容 (B) — TreeRow ⋮ 菜单 + store action + API 包装

菜单项规则：仅 chapter kind 显示；has_children 时 disabled。
store action：调 API 后整段 refetch（沿用 convertToStep 模式）+ pushUndo + selectNode 到新 content。
6 个单测覆盖 happy / 失败 / 菜单可见 / 禁用。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task M4: C 后端 — split-title-content endpoint + service

**Files:**
- Modify: `backend/app/services/conversion_service.py`（加 `split_title_content`）
- Modify: `backend/app/routers/chapters.py`（加 1 个 router）
- Modify: `backend/app/schemas/node.py`（加 `SplitTitleContentIn` request schema）
- Modify: `backend/tests/unit/services/test_conversion_service.py`（追加 7 个 case）

- [ ] **Step 1: 加 request schema**

在 `backend/app/schemas/node.py` 末尾追加：

```python
class SplitTitleContentIn(BaseModel):
    """章节标题拆分请求：cursor_offset 必须在 (0, len(title)) 开区间内。"""

    cursor_offset: int = Field(..., gt=0)
```

> `gt=0` 由 pydantic 校验；上界 `< len(title)` 由 service 校验（schema 无 title 上下文）。

- [ ] **Step 2: 写失败测试 — split_title_content happy + 边界**

在 `backend/tests/unit/services/test_conversion_service.py` 末尾追加：

```python
# --------------------------------------------------------------------------- #
# 拆 heading + content（C）
# --------------------------------------------------------------------------- #
def test_split_title_content_happy(db: Session, factory: Factory) -> None:
    """cursor=15 → title 截短到 15；新 content step kind=content content=tail。"""
    proc = _proc(factory)
    full_title = "3.1质量部是记录的归口管理部门，负责组织全公司记录表格的编制和校审。"
    ch = factory.chapter(proc.id, title=full_title)
    cursor = 15  # "3.1质量部是记录的归口管理部" 之后

    result = conversion_service.split_title_content(db, ch.id, cursor, META)
    db.commit()
    db.refresh(ch)

    assert ch.title == full_title[:cursor]
    assert result.deleted == []
    assert len(result.created) == 1
    new_step = step_service.get_step(db, result.created[0])
    assert new_step.kind == "content"
    assert new_step.content == full_title[cursor:]
    assert new_step.chapter_id == ch.id
    assert new_step.sort_order == 0


def test_split_title_content_cursor_zero(db: Session, factory: Factory) -> None:
    """cursor=0 → INVALID_CURSOR。"""
    proc = _proc(factory)
    ch = factory.chapter(proc.id, title="章节标题")

    with pytest.raises(HTTPException) as exc:
        conversion_service.split_title_content(db, ch.id, 0, META)
    assert exc.value.detail["code"] == "INVALID_CURSOR"


def test_split_title_content_cursor_at_end(db: Session, factory: Factory) -> None:
    """cursor=len(title) → INVALID_CURSOR。"""
    proc = _proc(factory)
    title = "章节标题"
    ch = factory.chapter(proc.id, title=title)

    with pytest.raises(HTTPException) as exc:
        conversion_service.split_title_content(db, ch.id, len(title), META)
    assert exc.value.detail["code"] == "INVALID_CURSOR"


def test_split_title_content_empty_tail(db: Session, factory: Factory) -> None:
    """拆点之后是全空白 → EMPTY_CONTENT。"""
    proc = _proc(factory)
    ch = factory.chapter(proc.id, title="章节标题    ")  # 尾部 4 空格
    cursor = 4  # "章节标题" 之后 = "    "（全空白）

    with pytest.raises(HTTPException) as exc:
        conversion_service.split_title_content(db, ch.id, cursor, META)
    assert exc.value.detail["code"] == "EMPTY_CONTENT"


def test_split_title_content_existing_steps_reorder(db: Session, factory: Factory) -> None:
    """chapter 已有 N 个 step children → 新 content step.sort_order=0，其他全部 +1。"""
    proc = _proc(factory)
    ch = factory.chapter(proc.id, title="章节标题ABCDE")
    s1 = factory.step(proc.id, chapter_id=ch.id, kind="step", title="原step1", sort_order=0)
    s2 = factory.step(proc.id, chapter_id=ch.id, kind="step", title="原step2", sort_order=1)

    result = conversion_service.split_title_content(db, ch.id, 4, META)
    db.commit()
    db.refresh(s1)
    db.refresh(s2)

    new_step = step_service.get_step(db, result.created[0])
    assert new_step.sort_order == 0
    assert s1.sort_order == 1
    assert s2.sort_order == 2


def test_split_title_content_with_child_chapter(db: Session, factory: Factory) -> None:
    """chapter 有子 chapter → 不报错，子 chapter 不受影响。"""
    proc = _proc(factory)
    parent = factory.chapter(proc.id, title="父章节ABCDE")
    child = factory.chapter(proc.id, parent_id=parent.id, title="子章节")
    child_id = child.id

    result = conversion_service.split_title_content(db, parent.id, 4, META)
    db.commit()
    db.refresh(child)

    assert child.is_active is True
    assert child.parent_id == parent.id  # 不受影响
    assert len(result.created) == 1


def test_split_title_content_readonly_procedure(db: Session, factory: Factory) -> None:
    """非 DRAFT 程序 → PROCEDURE_READONLY。"""
    proc = _proc(factory)
    proc.status = "RELEASED"
    db.flush()
    ch = factory.chapter(proc.id, title="章节标题")

    with pytest.raises(HTTPException) as exc:
        conversion_service.split_title_content(db, ch.id, 2, META)
    assert exc.value.detail["code"] == "PROCEDURE_READONLY"
```

- [ ] **Step 3: 运行测试确认失败**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/services/test_conversion_service.py -k split_title_content -v
```

期望：7 个 case 全失败。

- [ ] **Step 4: 实现 split_title_content service**

在 `backend/app/services/conversion_service.py` 末尾追加：

```python
# --------------------------------------------------------------------------- #
# 拆 heading + content（C）
# --------------------------------------------------------------------------- #
def split_title_content(
    db: Session, chapter_id: str, cursor_offset: int, meta: RequestMeta
) -> ConversionResult:
    """在 chapter.title 的 cursor_offset 位置拆为标题 + 内容。

    title 截短到 [:cursor]，[cursor:] 部分作为新 content step 插入 chapter 下首位
    （现有 step 全部 sort_order +1 让出 0 位）。

    校验：
    - 0 < cursor_offset < len(title)（INVALID_CURSOR）
    - title[cursor:] strip 非空（EMPTY_CONTENT）
    """
    ch = _get_chapter(db, chapter_id)
    proc = _get_proc_editable(db, ch.procedure_id)

    title = ch.title or ""
    if cursor_offset <= 0 or cursor_offset >= len(title):
        raise bad_request("INVALID_CURSOR", "拆分点必须严格在标题中间")
    new_content_text = title[cursor_offset:]
    if not new_content_text.strip():
        raise bad_request("EMPTY_CONTENT", "拆出的内容为空")

    new_title = title[:cursor_offset]

    # 已有 step children 全部 sort_order +1（让出 0 位）
    existing_steps = (
        db.execute(
            select(ProcedureStep).where(
                ProcedureStep.chapter_id == ch.id, ProcedureStep.is_active.is_(True)
            )
        )
        .scalars()
        .all()
    )
    for s in existing_steps:
        s.sort_order += 1

    ch.title = new_title
    new_step = ProcedureStep(
        procedure_id=proc.id,
        chapter_id=ch.id,
        kind="content",
        title="",
        content=new_content_text,
        input_schema={},
        sort_order=0,
    )
    db.add(new_step)
    db.flush()
    numbering_service.recompute(db, proc.id)
    optimistic_lock.bump(proc)
    db.flush()
    _audit(
        db,
        proc,
        target_id=new_step.id,
        action="split-title-content",
        meta=meta,
        old_value={"chapter_id": ch.id, "original_title": title, "cursor": cursor_offset},
        new_value={"new_title": new_title, "new_content": new_content_text},
    )
    return ConversionResult(created=[new_step.id], deleted=[])
```

- [ ] **Step 5: 加 router**

在 `backend/app/routers/chapters.py` 末尾追加（imports 段补 `SplitTitleContentIn`）：

```python
# 顶部 imports 段补
from app.schemas.node import (
    ChapterCreate,
    ChapterMoveIn,
    ChapterOut,
    ChapterUpdate,
    ConversionResult,
    MarkStatusIn,
    SplitTitleContentIn,
)


@router.post("/{chapter_id}/split-title-content", response_model=ConversionResult)
def split_title_content(
    chapter_id: str,
    payload: SplitTitleContentIn,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ConversionResult:
    result = conversion_service.split_title_content(db, chapter_id, payload.cursor_offset, meta)
    db.commit()
    return result
```

- [ ] **Step 6: 运行测试确认通过**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/services/test_conversion_service.py -v
```

期望：所有 test_conversion_service 测试通过（包括新加的 7 + 旧的）。

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/conversion_service.py backend/app/routers/chapters.py backend/app/schemas/node.py backend/tests/unit/services/test_conversion_service.py
git commit -m "feat(backend): 在光标处拆 heading+content (C) — POST /chapters/:id/split-title-content

请求 body: { cursor_offset: int (>0) }；service 二次校验上界与 strip 后非空。

行为：
- ch.title 截短到 [:cursor]
- 新 step kind=content content=[cursor:] sort_order=0
- 已有 step 全部 sort_order +1（让出 0 位）
- numbering recompute + procedure version bump + audit log

7 个单测覆盖 happy / cursor 边界 / 空内容 / 重排 / 子 chapter 保留 / 只读。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task M5: C 前端 — ChapterDetailPanel 按钮 + store + 测试

**Files:**
- Modify: `frontend/src/api/chapters.ts`（加 1 个 API 包装）
- Modify: `frontend/src/store/procedureEditor.ts`（加 1 个 action + inflightSplit 字段）
- Modify: `frontend/src/components/editor/ChapterDetailPanel.vue`（加按钮 + 光标跟踪）
- Modify: `frontend/tests/unit/ChapterDetailPanel.spec.ts`（追加测试）
- Modify: `frontend/tests/unit/procedureEditorStore.spec.ts`（追加测试）

- [ ] **Step 1: 加 API 包装**

在 `frontend/src/api/chapters.ts` 末尾追加：

```ts
export const splitChapterTitleContent = async (
  id: string,
  payload: { cursor_offset: number },
): Promise<ConversionResult> =>
  (await http.post<ConversionResult>(`/chapters/${id}/split-title-content`, payload)).data
```

- [ ] **Step 2: 写失败测试 — store action**

在 `frontend/tests/unit/procedureEditorStore.spec.ts` 中追加：

```ts
describe('procedureEditorStore.splitChapterTitleContent', () => {
  it('calls API with cursor_offset and selects new step', async () => {
    const mockPost = vi.fn().mockResolvedValue({
      data: { created: ['new-step-id'], deleted: [] },
    })
    vi.mocked(http.post).mockImplementation(mockPost)

    const store = useProcedureEditorStore()
    await store.loadProcedure({
      id: 'proc-1',
      chapters: [{ id: 'ch-1', title: '3.1质量部是记录的归口管理部门，负责...' }],
      steps: [],
    })

    await store.splitChapterTitleContent('ch-1', 15)

    expect(mockPost).toHaveBeenCalledWith('/chapters/ch-1/split-title-content', { cursor_offset: 15 })
    expect(store.selectedNodeId).toBe('new-step-id')
  })

  it('blocks duplicate calls via inflight lock', async () => {
    let resolveCall: (v: unknown) => void = () => {}
    const pending = new Promise((r) => { resolveCall = r })
    vi.mocked(http.post).mockReturnValue(pending as never)

    const store = useProcedureEditorStore()
    await store.loadProcedure({
      id: 'proc-1',
      chapters: [{ id: 'ch-1', title: '章节标题ABCDE' }],
      steps: [],
    })

    const p1 = store.splitChapterTitleContent('ch-1', 4)
    const p2 = store.splitChapterTitleContent('ch-1', 4)  // 双击
    resolveCall({ data: { created: ['new-id'], deleted: [] } })
    await Promise.all([p1, p2])

    expect(http.post).toHaveBeenCalledTimes(1)
  })

  it('records undo on success', async () => {
    vi.mocked(http.post).mockResolvedValue({ data: { created: ['new-id'], deleted: [] } })
    const store = useProcedureEditorStore()
    await store.loadProcedure({
      id: 'proc-1',
      chapters: [{ id: 'ch-1', title: '章节标题ABCDE' }],
      steps: [],
    })
    const before = store.undoStack.length

    await store.splitChapterTitleContent('ch-1', 4)
    expect(store.undoStack.length).toBe(before + 1)
  })
})
```

- [ ] **Step 3: 运行测试确认失败**

```bash
cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts -t "splitChapterTitleContent"
```

期望：3 个 case 全失败。

- [ ] **Step 4: 实现 store action**

在 `frontend/src/store/procedureEditor.ts` 中：

(a) 顶部 import：
```ts
import {
  convertChapterToContent as convertChapterToContentApi,
  splitChapterTitleContent as splitChapterTitleContentApi,
} from '@/api/chapters'
```

(b) 在 `state()` return 对象中追加字段：
```ts
inflightSplit: new Set<string>(),
```
（在 state 接口里也补 `inflightSplit: Set<string>`）

(c) 在 actions 中加：
```ts
async splitChapterTitleContent(id: string, cursorOffset: number): Promise<void> {
  const map = await this.ensureSaved()
  const realId = map[id] ?? id
  if (this.inflightSplit.has(realId)) return
  this.inflightSplit.add(realId)
  try {
    const result = await splitChapterTitleContentApi(realId, { cursor_offset: cursorOffset })
    await this.refreshAfterConversion(result)
    this.pushUndo(`split-title-content:${realId}`)
    if (result.created.length > 0) this.selectNode(result.created[0])
  } finally {
    this.inflightSplit.delete(realId)
  }
},
```

- [ ] **Step 5: 运行 store 测试确认通过**

```bash
cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts -t "splitChapterTitleContent"
```

- [ ] **Step 6: 写失败测试 — ChapterDetailPanel 按钮**

在 `frontend/tests/unit/ChapterDetailPanel.spec.ts` 中追加：

```ts
describe('ChapterDetailPanel split button', () => {
  function mountPanel(title: string) {
    const store = useProcedureEditorStore()
    store.$patch({
      chapters: [{ id: 'ch-1', title, parent_id: null } as EditorChapter],
      selectedNodeId: 'ch-1',
      editable: true,
    })
    return mount(ChapterDetailPanel)
  }

  it('disables split button when cursor is null', async () => {
    const w = mountPanel('章节标题ABCDE')
    const btn = w.find('[data-test="split-title-content-btn"]')
    expect(btn.exists()).toBe(true)
    expect(btn.attributes('disabled')).toBeDefined()
  })

  it('enables split button when cursor is in middle', async () => {
    const w = mountPanel('章节标题ABCDE')
    const textarea = w.find('textarea').element as HTMLTextAreaElement
    textarea.focus()
    textarea.setSelectionRange(4, 4)
    await w.find('textarea').trigger('select')
    const btn = w.find('[data-test="split-title-content-btn"]')
    expect(btn.attributes('disabled')).toBeUndefined()
  })

  it('disables split button when cursor at 0 or at end', async () => {
    const w = mountPanel('章节标题')
    const textarea = w.find('textarea').element as HTMLTextAreaElement
    textarea.focus()
    textarea.setSelectionRange(0, 0)
    await w.find('textarea').trigger('select')
    expect(w.find('[data-test="split-title-content-btn"]').attributes('disabled')).toBeDefined()

    textarea.setSelectionRange(4, 4)  // 末尾
    await w.find('textarea').trigger('select')
    expect(w.find('[data-test="split-title-content-btn"]').attributes('disabled')).toBeDefined()
  })

  it('calls store.splitChapterTitleContent on click', async () => {
    const w = mountPanel('章节标题ABCDE')
    const store = useProcedureEditorStore()
    const spy = vi.spyOn(store, 'splitChapterTitleContent').mockResolvedValue()

    const textarea = w.find('textarea').element as HTMLTextAreaElement
    textarea.focus()
    textarea.setSelectionRange(4, 4)
    await w.find('textarea').trigger('select')
    await w.find('[data-test="split-title-content-btn"]').trigger('click')

    expect(spy).toHaveBeenCalledWith('ch-1', 4)
  })
})
```

- [ ] **Step 7: 运行测试确认失败**

```bash
cd frontend && npx vitest run tests/unit/ChapterDetailPanel.spec.ts -t "split button"
```

期望：4 个 case 全失败。

- [ ] **Step 8: 实现 ChapterDetailPanel 按钮 + 光标跟踪**

在 `frontend/src/components/editor/ChapterDetailPanel.vue` 中：

(a) `<script setup>` 顶部补：
```ts
import { computed, onMounted, ref } from 'vue'
```
（如已 import 则补 ref 一项）

(b) 在 `titleRef` 之后加：
```ts
const cursorOffset = ref<number | null>(null)

function refreshCursor(): void {
  const inputEl = titleRef.value as unknown as { textarea?: HTMLTextAreaElement; ref?: HTMLTextAreaElement }
  const el = inputEl?.textarea ?? inputEl?.ref
  if (!el) {
    cursorOffset.value = null
    return
  }
  cursorOffset.value = el.selectionStart
}

const splitDisabled = computed(() => {
  if (ro.value) return true
  const ch = chapter.value
  if (!ch || !ch.title.trim()) return true
  const c = cursorOffset.value
  if (c === null) return true
  if (c <= 0 || c >= ch.title.length) return true
  return false
})

function onSplit(): void {
  const ch = chapter.value
  const c = cursorOffset.value
  if (!ch || c === null) return
  void store.splitChapterTitleContent(ch.id, c)
}
```

(c) 修改 textarea 节点（line 66-77），加 ref 一致性 + 光标事件：
```html
<el-input
  ref="titleRef"
  :model-value="chapter.title"
  type="textarea"
  autosize
  maxlength="500"
  show-word-limit
  :disabled="ro"
  placeholder="输入章节标题"
  @input="onTitle"
  @focus="refreshCursor"
  @blur="refreshCursor"
  @click="refreshCursor"
  @keyup="refreshCursor"
  @select="refreshCursor"
/>
```

(d) 在 `</el-form>` 之前（line 88 之前）加按钮行：
```html
<div class="split-row">
  <el-button
    size="small"
    type="primary"
    plain
    data-test="split-title-content-btn"
    :disabled="splitDisabled"
    @click="onSplit"
  >
    在光标处拆为标题 + 内容
  </el-button>
  <span v-if="!splitDisabled" class="split-hint">将把光标后的文本变为本章节首个内容块</span>
</div>
```

(e) `<style scoped>` 末尾加：
```css
.split-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 8px 0;
}
.split-hint {
  font-size: 12px;
  color: #909399;
}
```

- [ ] **Step 9: 运行 panel 测试确认通过**

```bash
cd frontend && npx vitest run tests/unit/ChapterDetailPanel.spec.ts
```

期望：4 个新 case + 既有 case 全通过。若 `titleRef.value.textarea` 路径在当前 EP 版本不对（spec §7 风险已标），打开 Element Plus 文档或源码查实际暴露字段名调整。

- [ ] **Step 10: 全量 vitest 回归**

```bash
cd frontend && npx vitest run
```

期望：全部通过。

- [ ] **Step 11: Commit**

```bash
git add frontend/src/api/chapters.ts frontend/src/store/procedureEditor.ts frontend/src/components/editor/ChapterDetailPanel.vue frontend/tests/unit/procedureEditorStore.spec.ts frontend/tests/unit/ChapterDetailPanel.spec.ts
git commit -m "feat(editor): 在光标处拆 heading+content (C) — ChapterDetailPanel 按钮 + store action

按钮启用规则：editable && cursorOffset ∈ (0, len(title)) && title 非空。
store action：inflight lock 防双击 + pushUndo + selectNode 到新 content。
7 个单测覆盖按钮启用 / 边界 / store action / inflight。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task M6: 浏览器实测验收（Chrome DevTools MCP）

**Files:**
- Create: `.verify-screenshots/frontend-editing/` 目录（截图归档）
- Create: `docs/verify-frontend-editing-affordances.md`（验收报告）

> 本任务**不产生代码改动**，只是用 Chrome DevTools MCP 在浏览器里真实执行 A+B+C 流程、抽 5 份融合式 chapter 的样本截图存档、产出验收报告。如果实测发现 bug，回到 M1-M5 对应 Task 修复。

- [ ] **Step 1: 启动后端 + 前端 dev 环境**

```bash
# Terminal 1
cd backend && .venv/bin/python -m uvicorn app.main:app --reload --port 8000

# Terminal 2
cd frontend && npm run dev
```

确认浏览器打开 `http://localhost:5173` 能进编辑器。

- [ ] **Step 2: 选取 5 份典型样本**

从 36 份样本里挑 5 份融合式 chapter 密集的（建议从 [`docs/parser-comprehensive-evaluation.md`](../../parser-comprehensive-evaluation.md) §1.2 已识别为 `N.N+CJK直连` 模式的）。建议：
- `1_程序模板.docx`
- `01-公司环境.docx`
- `CW-WI 5.2.docx`
- `QMS QP-08 记录控制程序.docx`
- 任一 Tier 3 模板（如 `CW-QP-02 文件控制程序`）

- [ ] **Step 3: 使用 chrome-devtools MCP 走 A 流程并截图**

对每份样本：导入 → 找到一个长 chapter 标题 → hover 树行验证 tooltip 出现 → `mcp__chrome-devtools__take_screenshot` 存档到 `.verify-screenshots/frontend-editing/A-{sample}-tooltip.png`

- [ ] **Step 4: 走 B 流程并截图**

对同一份样本：选一个融合式 chapter（无 children）→ 点 ⋮ → 点"转为内容块" → 验证树变化（chapter 变成 content 节点）→ 截图存档 `B-{sample}-converted.png`

- [ ] **Step 5: 走 C 流程并截图**

对同一份样本：选另一个融合式 chapter → 在标题 textarea 把光标放到拟拆点 → 点"在光标处拆为标题+内容" → 验证树变化（chapter 缩短 + 下面多了 content 子节点）→ 截图存档 `C-{sample}-split.png`

- [ ] **Step 6: 验证 undo**

对刚拆的 chapter：按 Cmd/Ctrl+Z → 验证树回到拆前；截图 `C-{sample}-undo.png`

> 注意按 spec §5.2：undo 仅恢复前端视图；若用户保存后才 undo，后端是真实改了；这是已知行为，截图记录即可。

- [ ] **Step 7: 撰写验收报告**

创建 `docs/verify-frontend-editing-affordances.md`：

```markdown
# 前端编辑能力增强 A+B+C 浏览器实测验收

**日期：** 2026-05-2X
**版本：** feat/frontend-editing-affordances <commit-sha>
**样本：** 5 份（列举文件名）

## A 树行 tooltip
| 样本 | 长 chapter 标题 | tooltip 触发 | 截图 |
|---|---|:-:|---|
| ... | ... | ✓/✗ | A-xxx-tooltip.png |

## B 章节转内容
... 同上表格 ...

## C 拆 heading+content
... 同上表格 ...

## 发现的问题与处理
（如无：填"未发现回归"）

## 结论
A+B+C 全流程在 5 份样本通过 / 5 份验收。
```

- [ ] **Step 8: Commit 验收报告 + 截图**

```bash
git add docs/verify-frontend-editing-affordances.md .verify-screenshots/frontend-editing/
git commit -m "test(verify): 前端编辑能力 A+B+C 5 份样本浏览器实测验收

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## 完成 → finishing-a-development-branch

所有 6 个 Task 完成后：

- [ ] 全量后端单测 + 前端 vitest 都通过：

```bash
cd backend && .venv/bin/python -m pytest
cd frontend && npx vitest run
```

- [ ] **REQUIRED SUB-SKILL**: superpowers:finishing-a-development-branch

按 finishing 提供的 4 选项（merge 回 main / 推 PR / 保留 / 丢弃）由用户决定。

---

## 自查（writing-plans skill §Self-Review）

### Spec 覆盖

| Spec 章节 | 对应 Task |
|---|---|
| §2 A 树行 tooltip | M1（6 step） |
| §3 B 章节转内容 后端 | M2（6 step） |
| §3.3 / §3.4 B 前端 store + 菜单 | M3（11 step） |
| §4 C 拆 heading+content 后端 | M4（7 step） |
| §4 / §4.5 C 前端 panel + store | M5（11 step） |
| §5.5 顺序保真校验 | 隐含在 M2/M4 单测 case 5/6（sort_order 重排） |
| §5.6 后端日志 | 已在 M2/M4 service 代码中的 `_audit` 调用覆盖 |
| §6 实施顺序 | M1→M2→M3→M4→M5→M6 一一对应 |
| §6 M6 浏览器验收 | M6（8 step） |

### 占位符扫描

- 无 "TBD" / "TODO" / "暂定"
- 每个代码 step 含完整代码块
- "Similar to Task N" 模式未使用（每个 Task 自包含）

### 类型一致性

- 后端：`convert_to_content` / `split_title_content` 两个函数名贯穿全 plan
- 前端：`convertChapterToContent` / `splitChapterTitleContent` 两个 API 函数 + 同名 store action 一致
- Schema：`SplitTitleContentIn` + `ConversionResult`（复用）一致
- 命令字符串：`chapter-to-content` 在 M3 step 8 / 9 多处出现，一致
- store field：`inflightSplit: Set<string>` 在 M5 step 4 定义并使用

---

## 决策与权衡日志（[[trade-off-auto-decide-with-log]]）

| 决策 | 选项 | 选什么 | 理由 |
|---|---|---|---|
| 后端 endpoint 复用还是新加 | 链式 convert→patch / 新原子 endpoint | 新原子 endpoint | 用户 brainstorm 阶段已明确拍板；事务一致性 > 多 2 router |
| ROOT_CHAPTER_PROTECTED 还是 SIBLING_TYPE_CONFLICT | 新错误码 / 复用 Q25 既有 | SIBLING_TYPE_CONFLICT | 与 `convert_to_step` 现有约定一致；天然覆盖根 chapter 周围有 chapter 的场景；少一个错误码概念 |
| 前端 store mutation 还是 refetch | 本地 patch / 整段 refresh | 整段 refresh | 沿用 `convertToStep` 模式；结构变更涉及 numbering recompute，本地 patch 易漂移；一致性更稳 |
| 拆按钮置于树行 ⋮ 还是详情面板 | ⋮ 菜单 + 弹窗 / 面板按钮 + 光标位 | 面板按钮 + 光标位 | brainstorm 拍板；零新手势、最直观；面板已有 textarea，光标位 DOM 直接拿 |
| split-title-content 响应携带新 title 还是省略 | 携带新 title / 仅 created/deleted | 仅 created/deleted（复用 ConversionResult） | 前端整段 refresh，不需要新 title；schema 复用减少类型工程 |

---

## 后续（不在本 plan）

- P2 `detected_patterns` 批量重组面板（spec §7 风险表中标注；待 A+B+C 落地后看用户实际是否需要）
- PDF 渲染折行优化（独立子系统）
- 多人协作版本冲突的高级合并（依赖整体 collab 架构演进）
