# P2b · 待确认 triage + 完成（发布拦截）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在编辑器里处理"待确认"(review)：逐个/全部接受、只看待确认过滤、下一个跳转、改结构自动清；并让发布在仍有 review 时被拦。

**Architecture:** 后端 `transition→PUBLISHED` 加 review 计数校验。前端：store 加 `acceptReview`/`acceptAllReviews` 并在 `toggleContentType`/`promoteChapter`/`demoteChapter` 内自动清 review；详情面板（章节/内容）加「接受待确认」；树面板加「全部接受/只看待确认/下一个」；`PublishChecklistDialog` 加"无待确认"项。清 review 走既有 `setMark`（mark-status 专用端点；注意 `mark_status` 不在批量保存 payload 内）。

**Tech Stack:** 后端 FastAPI + pytest；前端 Vue 3 + TS + Pinia + Vitest + Element Plus。

**Gate：** 后端（cwd=`backend/`）`.venv/bin/ruff check app tests && .venv/bin/mypy app && .venv/bin/python -m pytest -q`；前端（cwd=`frontend/`）`npm run lint && npm run typecheck && npm run test && npm run build`。

**上位文档：** `docs/superpowers/specs/2026-05-25-p2b-review-triage-finalize-design.md`

---

## 关键事实（实现者必读）

- **`mark_status` 不在批量保存**：`ChapterUpsert` 无 `mark_status` 字段；它只经 `POST /chapters/{id}/mark-status`（前端 `setChapterMarkStatus` / `store.setMark`）持久化，且后端 `set_mark_status` 不校验取值、不 bump revision。故"清 review"必须走 `setMark(id,'unmarked')`，不能靠 `updateChapterFields`。
- `store.setMark(id, status)`（procedureEditor.ts ~725）：本地乐观置 `mark_status` + 真实 id 调端点（失败回滚）；临时 id 只改本地。设置时**同步**赋本地值。
- `toggleContentType(id)`（~445，本地，`updateChapterFields` 改 content_type）；`promoteChapter`/`demoteChapter`（~693/706，调 `moveCrossParent`→**后端即时 + reload 整树**，节点 id 不变）。
- store 测试（`tests/unit/procedureEditorStore.spec.ts`）：mock `@/api/chapters` 的 `setChapterMarkStatus` = `markSpy`（`mockResolvedValue({})`）；`seed()` 建带 `chapters=[chap('a'),chap('b')]` 的 store；`chap(id,parent,sort)` 默认 `mark_status:'unmarked'`，可展开覆盖。
- 后端 `procedure_service.transition`（~286）：`target=='PUBLISHED'` 已校验版本说明 + 必填字段；已 import `select`、`func`、`ProcedureChapter`、`bad_request`。
- `ProcedureDetail` 响应里乐观锁版本在 `detail["procedure"]["revision"]`（嵌套）。`test_word_import.py` 有 `_leaf`/`_upload`/`PARSE`/`IMPORT`/`_flatten` + `unstyled_numbered_sop`。
- `PublishChecklistDialog.vue`：`checks` computed 列表，`canConfirm = checks.every(c => c.ok || c.warning)`。加一条 ok=false 即禁用确认。
- `ChapterDetailPanel.vue`（章节详情，含"节点类型"radio→`toggleContentType`）、`ContentDetailPanel.vue`（仅 `RichTextEditor`）。
- `ChapterTreePanel.vue`：`reviewCount` 已在 P2a 加（`computed(() => store.chapters.filter(c => c.mark_status==='review').length)`）；P2a 在 toolbar 加了 `<div v-if="reviewCount" class="review-count">…</div>`（本计划 T4 会替换它）；`visibleRows` 用 `rowParent` 做祖先保留搜索；`store.flatRows` 文档序。
- 提交结尾必带（harness 规定的合法署名，勿当伪造）：`Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`

---

## File Structure

- 改 `backend/app/services/procedure_service.py`（transition review 校验）+ `backend/tests/integration/test_word_import.py`。
- 改 `frontend/src/store/procedureEditor.ts`（acceptReview/acceptAllReviews + D4 自动清）+ `frontend/tests/unit/procedureEditorStore.spec.ts`。
- 改 `frontend/src/components/editor/ChapterDetailPanel.vue` + `ContentDetailPanel.vue`（接受按钮）+ `frontend/tests/unit/ChapterDetailPanel.spec.ts`（新建）。
- 新建 `frontend/src/utils/reviewNav.ts`（下一个待确认纯逻辑）+ `frontend/tests/unit/utils/reviewNav.spec.ts`。
- 改 `frontend/src/components/editor/ChapterTreePanel.vue`（全部接受 / 只看待确认 / 下一个 / 过滤）。
- 改 `frontend/src/components/editor/PublishChecklistDialog.vue`（无待确认项）+ `frontend/tests/unit/PublishChecklistDialog.spec.ts`（新建）。

---

## Task 1: 后端——发布拦截待确认

**Files:** Modify `backend/app/services/procedure_service.py`, `backend/tests/integration/test_word_import.py`

- [ ] **Step 1: 写失败测试（追加到 test_word_import.py，`_flatten` 之前）**

```python
def test_publish_blocked_while_review_pending(client: TestClient, storage_tmp: Path) -> None:
    leaf = _leaf(client)
    token = _upload(client, unstyled_numbered_sop())
    parsed = client.post(PARSE, json={"upload_token": token, "parse_mode": "smart"}).json()
    pid = client.post(
        IMPORT, json={"name": "待发布", "folder_id": leaf, "chapters": parsed["chapters"]}
    ).json()["id"]
    detail = client.get(f"/api/v1/procedures/{pid}").json()
    rev = detail["procedure"]["revision"]

    # 仍有 review → 发布被拦
    blocked = client.post(
        f"/api/v1/procedures/{pid}/transition",
        json={"status": "PUBLISHED"},
        headers={"If-Match": str(rev)},
    )
    assert blocked.status_code == 400
    assert blocked.json()["detail"]["code"] == "REVIEW_PENDING"

    # 清掉所有 review 后可发布
    for n in _flatten(detail["chapters"]):
        if n["mark_status"] == "review":
            client.post(f"/api/v1/chapters/{n['id']}/mark-status", json={"mark_status": "unmarked"})
    rev2 = client.get(f"/api/v1/procedures/{pid}").json()["procedure"]["revision"]
    ok = client.post(
        f"/api/v1/procedures/{pid}/transition",
        json={"status": "PUBLISHED"},
        headers={"If-Match": str(rev2)},
    )
    assert ok.status_code == 200, ok.text
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_word_import.py -q -k review_pending`
Expected: FAIL（当前发布不拦 review，第一段返 200）。

- [ ] **Step 3: 实现**

在 `backend/app/services/procedure_service.py` 的 `transition` 内，找到 `if target == "PUBLISHED":` 校验必填字段那块（`field_service.validate_values(... require_check=True)`），在其后追加：

```python
    if target == "PUBLISHED":
        pending = db.execute(
            select(func.count())
            .select_from(ProcedureChapter)
            .where(
                ProcedureChapter.procedure_id == proc.id,
                ProcedureChapter.is_active.is_(True),
                ProcedureChapter.mark_status == "review",
            )
        ).scalar_one()
        if pending:
            raise bad_request("REVIEW_PENDING", f"仍有 {pending} 个待确认节点，请先全部处理")
```
（与上一处 `if target == "PUBLISHED":` 合并或并列均可；保持在 `proc.status = target` 之前。）

- [ ] **Step 4: 后端 Gate**

Run: `cd backend && .venv/bin/python -m pytest -q && .venv/bin/ruff check app tests && .venv/bin/mypy app`
Expected: 全绿。确认既有 `test_transition_publish` 仍过（它发布的程序无 review）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/procedure_service.py backend/tests/integration/test_word_import.py
git commit -m "$(cat <<'EOF'
feat(p2b): block publish while review nodes remain (REVIEW_PENDING)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: store——accept 动作 + 改结构自动清 review

**Files:** Modify `frontend/src/store/procedureEditor.ts`, `frontend/tests/unit/procedureEditorStore.spec.ts`

- [ ] **Step 1: 写失败测试（追加 describe）**

在 `frontend/tests/unit/procedureEditorStore.spec.ts` 顶部（与现有 import 同处）确保有：
```ts
import { flushPromises } from '@vue/test-utils'
```
追加：
```ts
describe('待确认 triage (P2b)', () => {
  it('acceptReview 清 review 并持久化', async () => {
    const s = seed()
    s.chapters = [{ ...chap('a', null, 0), mark_status: 'review' }]
    await s.acceptReview('a')
    expect(s.chapterMap.get('a')?.mark_status).toBe('unmarked')
    expect(markSpy).toHaveBeenCalledWith('a', 'unmarked')
  })

  it('acceptAllReviews 清全部 review', async () => {
    const s = seed()
    s.chapters = [
      { ...chap('a', null, 0), mark_status: 'review' },
      { ...chap('b', null, 1), mark_status: 'review' },
      { ...chap('c', null, 2), mark_status: 'unmarked' },
    ]
    await s.acceptAllReviews()
    expect(s.chapters.every((c) => c.mark_status === 'unmarked')).toBe(true)
    expect(markSpy).toHaveBeenCalledTimes(2)
  })

  it('toggleContentType 在 review 节点上自动清 review', async () => {
    const s = seed()
    s.chapters = [{ ...chap('a', null, 0), mark_status: 'review' }]
    s.toggleContentType('a')
    await flushPromises()
    expect(s.chapterMap.get('a')?.content_type).toBe('content')
    expect(s.chapterMap.get('a')?.mark_status).toBe('unmarked')
    expect(markSpy).toHaveBeenCalledWith('a', 'unmarked')
  })
})
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts -t 待确认`
Expected: FAIL（`acceptReview` 等未定义）。

- [ ] **Step 3: 实现 store 动作 + D4**

在 `frontend/src/store/procedureEditor.ts` 的 actions 内（例如紧接 `setMark` 之后）新增：
```ts
    // 接受单个待确认：清 review（保留解析判定的类型/结构）。
    async acceptReview(id: string): Promise<void> {
      await this.setMark(id, 'unmarked')
    },

    // 接受全部待确认。
    async acceptAllReviews(): Promise<void> {
      await this.ensureSaved()
      const ids = this.chapters.filter((c) => c.mark_status === 'review').map((c) => c.id)
      for (const id of ids) await this.setMark(id, 'unmarked')
    },
```

D4 自动清 review：
1. `toggleContentType` 改为：
```ts
    toggleContentType(id: string): void {
      const ch = this.chapterMap.get(id)
      if (!ch) return
      const wasReview = ch.mark_status === 'review'
      const next: ContentType = ch.content_type === 'chapter' ? 'content' : 'chapter'
      this.updateChapterFields(id, { content_type: next }, `content_type:${id}`)
      if (wasReview) void this.setMark(id, 'unmarked')
    },
```
2. `promoteChapter`：开头取 `const wasReview = this.chapterMap.get(id)?.mark_status === 'review'`；在末尾 `await this.moveCrossParent(...)` 之后追加 `if (wasReview) await this.setMark(id, 'unmarked')`。
3. `demoteChapter`：同理（开头记 `wasReview`，`await this.moveCrossParent(...)` 之后 `if (wasReview) await this.setMark(id, 'unmarked')`）。

- [ ] **Step 4: 跑测试 + 前端 lint/type**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts && npm run lint && npm run typecheck`
Expected: 全绿（含 3 新测试 + 既有 promote/demote 测试不回归）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/store/procedureEditor.ts frontend/tests/unit/procedureEditorStore.spec.ts
git commit -m "$(cat <<'EOF'
feat(p2b): acceptReview/acceptAllReviews + auto-clear review on retype/relevel

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: 详情面板——「接受待确认」按钮

**Files:** Modify `frontend/src/components/editor/ChapterDetailPanel.vue`, `ContentDetailPanel.vue`; Create `frontend/tests/unit/ChapterDetailPanel.spec.ts`

- [ ] **Step 1: 写失败测试**

新建 `frontend/tests/unit/ChapterDetailPanel.spec.ts`：
```ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/http', () => ({ http: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }))
vi.mock('@/api/chapters', () => ({ setChapterMarkStatus: vi.fn().mockResolvedValue({}) }))

import ChapterDetailPanel from '@/components/editor/ChapterDetailPanel.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'

function mountWith(markStatus: 'review' | 'unmarked') {
  const store = useProcedureEditorStore()
  // @ts-expect-error 直接注入最小 procedure
  store.procedure = { id: 'p1', version: 1, status: 'DRAFT', revision: 1 }
  store.chapters = [{
    id: 'a', parent_id: null, content_type: 'chapter', title: '章', rich_content: '',
    skip_numbering: false, mark_status: markStatus, sort_order: 0,
  }]
  store.steps = []
  store.selectedId = 'a'
  return mount(ChapterDetailPanel, { global: { plugins: [ElementPlus] } })
}

describe('ChapterDetailPanel 接受待确认', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('review 节点显示「接受待确认」并点按调 store.acceptReview', async () => {
    const w = mountWith('review')
    const store = useProcedureEditorStore()
    const spy = vi.spyOn(store, 'acceptReview').mockResolvedValue()
    const btn = w.findAll('button').find((b) => b.text().includes('接受待确认'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    expect(spy).toHaveBeenCalledWith('a')
  })

  it('非 review 节点不显示该按钮', () => {
    const w = mountWith('unmarked')
    expect(w.findAll('button').some((b) => b.text().includes('接受待确认'))).toBe(false)
  })
})
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `cd frontend && npx vitest run tests/unit/ChapterDetailPanel.spec.ts`
Expected: FAIL（无按钮）。

- [ ] **Step 3: 实现——两个详情面板加横幅按钮**

`ChapterDetailPanel.vue`：模板根 `<div v-if="chapter" class="chapter-detail">` 内最前面插入：
```html
    <div v-if="chapter.mark_status === 'review' && !ro" class="review-banner">
      <span>⚠ 解析存疑（待确认）——确认结构无误后接受</span>
      <el-button size="small" type="warning" plain @click="store.acceptReview(chapter.id)">接受待确认</el-button>
    </div>
```
样式追加：
```css
.review-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
  padding: 6px 10px;
  font-size: 13px;
  color: #b88230;
  background: #fdf6ec;
  border: 1px solid #f5dab1;
  border-radius: 4px;
}
```

`ContentDetailPanel.vue`：模板根 `<div v-if="content" class="content-detail">` 内 `RichTextEditor` 之前插入同样的横幅（把 `chapter` 换成 `content`）：
```html
    <div v-if="content.mark_status === 'review' && !ro" class="review-banner">
      <span>⚠ 解析存疑（待确认）——确认结构无误后接受</span>
      <el-button size="small" type="warning" plain @click="store.acceptReview(content.id)">接受待确认</el-button>
    </div>
```
并加同样的 `.review-banner` 样式。

- [ ] **Step 4: 跑测试 + 前端 Gate**

Run: `cd frontend && npx vitest run tests/unit/ChapterDetailPanel.spec.ts && npm run lint && npm run typecheck`
Expected: 2 测试 PASS；lint/type clean。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/editor/ChapterDetailPanel.vue frontend/src/components/editor/ContentDetailPanel.vue frontend/tests/unit/ChapterDetailPanel.spec.ts
git commit -m "$(cat <<'EOF'
feat(p2b): accept-review banner in chapter/content detail panels

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: 树面板——全部接受 / 只看待确认 / 下一个

**Files:** Create `frontend/src/utils/reviewNav.ts`, `frontend/tests/unit/utils/reviewNav.spec.ts`; Modify `frontend/src/components/editor/ChapterTreePanel.vue`

- [ ] **Step 1: 写 reviewNav 纯逻辑失败测试**

新建 `frontend/tests/unit/utils/reviewNav.spec.ts`：
```ts
import { describe, it, expect } from 'vitest'
import { nextReviewId } from '@/utils/reviewNav'

const rows = [
  { id: 'a', mark_status: 'unmarked' as const },
  { id: 'b', mark_status: 'review' as const },
  { id: 'c', mark_status: 'review' as const },
  { id: 'd', mark_status: 'unmarked' as const },
]

describe('nextReviewId', () => {
  it('无选中 → 第一个 review', () => {
    expect(nextReviewId(rows, null)).toBe('b')
  })
  it('从某 review → 下一个 review', () => {
    expect(nextReviewId(rows, 'b')).toBe('c')
  })
  it('最后一个 review → 循环回第一个', () => {
    expect(nextReviewId(rows, 'c')).toBe('b')
  })
  it('当前在非 review 行 → 文档序之后的第一个 review（环绕）', () => {
    expect(nextReviewId(rows, 'd')).toBe('b')
  })
  it('无 review → null', () => {
    expect(nextReviewId([{ id: 'a', mark_status: 'unmarked' as const }], 'a')).toBeNull()
  })
})
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `cd frontend && npx vitest run tests/unit/utils/reviewNav.spec.ts`
Expected: FAIL（模块缺失）。

- [ ] **Step 3: 实现 reviewNav.ts**

新建 `frontend/src/utils/reviewNav.ts`：
```ts
interface ReviewRow {
  id: string
  mark_status: string
}

/**
 * 文档序里 currentId 之后的下一个 review 行 id（环绕）；当前非 review / 无选中时取其后第一个 review。
 * 无 review → null。
 */
export function nextReviewId(rows: ReviewRow[], currentId: string | null): string | null {
  const reviews = rows.filter((r) => r.mark_status === 'review')
  if (reviews.length === 0) return null
  if (currentId === null) return reviews[0].id
  const curIdx = rows.findIndex((r) => r.id === currentId)
  if (curIdx === -1) return reviews[0].id
  // 从 curIdx 之后环绕找第一个 review
  for (let i = 1; i <= rows.length; i++) {
    const r = rows[(curIdx + i) % rows.length]
    if (r.mark_status === 'review') return r.id
  }
  return reviews[0].id
}
```

- [ ] **Step 4: 跑测试，确认通过**

Run: `cd frontend && npx vitest run tests/unit/utils/reviewNav.spec.ts`
Expected: 5 测试 PASS。

- [ ] **Step 5: 树面板接线**

`frontend/src/components/editor/ChapterTreePanel.vue`：

1. `<script setup>` import 区加：
```ts
import { nextReviewId } from '@/utils/reviewNav'
```
（`ElMessageBox` 已 import。）

2. 加状态与方法（`reviewCount` 已存在）：
```ts
const reviewFilter = ref(false)

function keepWithAncestors(rows: FlatRow[], pred: (r: FlatRow) => boolean): FlatRow[] {
  const keep = new Set<string>()
  for (const r of rows) if (pred(r)) keep.add(r.id)
  for (const id of [...keep]) {
    let pid = rowParent(id)
    while (pid) {
      keep.add(pid)
      pid = rowParent(pid)
    }
  }
  return rows.filter((r) => keep.has(r.id))
}

function gotoNextReview(): void {
  const id = nextReviewId(store.flatRows, store.selectedId)
  if (id) store.selectNode(id)
}

function acceptAll(): void {
  if (!reviewCount.value) return
  ElMessageBox.confirm(`将接受 ${reviewCount.value} 个待确认节点，确认其解析结构无误？`, '全部接受', {
    type: 'warning',
  })
    .then(() => store.acceptAllReviews())
    .catch(() => {})
}
```

3. 把 `visibleRows` computed 改为复用 `keepWithAncestors`，并叠加 review 过滤：
```ts
const visibleRows = computed<FlatRow[]>(() => {
  let rows = store.flatRows
  if (reviewFilter.value) rows = keepWithAncestors(rows, (r) => r.mark_status === 'review')
  const q = debounced.value.trim().toLowerCase()
  if (q) rows = keepWithAncestors(rows, (r) => `${r.code} ${r.title} ${r.fallback}`.toLowerCase().includes(q))
  return rows
})
```
（这替换原有内联搜索过滤逻辑；语义不变 + 叠加 review 过滤。`rowParent` 已在文件内定义。）

4. 模板：把 P2a 加的 `<div v-if="reviewCount" class="review-count">…</div>` 整行替换为：
```html
      <div v-if="reviewCount" class="review-bar">
        <span class="review-count" title="解析存疑，待确认">⚠ {{ reviewCount }} 个待确认</span>
        <el-button size="small" @click="gotoNextReview">下一个</el-button>
        <el-button size="small" type="primary" plain @click="acceptAll">全部接受</el-button>
        <el-checkbox v-model="reviewFilter" size="small">只看待确认</el-checkbox>
      </div>
```

5. 样式：把 P2a 的 `.review-count` 规则补一个容器（保留原 `.review-count` 颜色）：
```css
.review-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.review-count {
  font-size: 12px;
  color: #e6a23c;
}
```

- [ ] **Step 6: 前端全量 Gate**

Run: `cd frontend && npm run lint && npm run typecheck && npm run test && npm run build`
Expected: 全绿（reviewNav 测试 + 既有 ChapterTreePanel 测试不回归）。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/utils/reviewNav.ts frontend/tests/unit/utils/reviewNav.spec.ts frontend/src/components/editor/ChapterTreePanel.vue
git commit -m "$(cat <<'EOF'
feat(p2b): tree-panel review controls (accept all / filter / next)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: 发布清单——无待确认项

**Files:** Modify `frontend/src/components/editor/PublishChecklistDialog.vue`; Create `frontend/tests/unit/PublishChecklistDialog.spec.ts`

- [ ] **Step 1: 写失败测试**

新建 `frontend/tests/unit/PublishChecklistDialog.spec.ts`：
```ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/http', () => ({ http: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }))

import PublishChecklistDialog from '@/components/editor/PublishChecklistDialog.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'

function setup(reviewCount: number) {
  const store = useProcedureEditorStore()
  // @ts-expect-error 最小 procedure
  store.procedure = { id: 'p1', version: 1, name: 'X', custom_values: {}, version_update_notes: '' }
  store.fields = []
  store.chapters = Array.from({ length: reviewCount + 1 }, (_, i) => ({
    id: `c${i}`, parent_id: null, content_type: 'chapter', title: 'c', rich_content: '',
    skip_numbering: false, mark_status: i < reviewCount ? 'review' : 'unmarked', sort_order: i,
  }))
  store.steps = []
  return mount(PublishChecklistDialog, { props: { modelValue: true }, global: { plugins: [ElementPlus] } })
}

describe('PublishChecklistDialog 待确认拦截', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('有待确认 → 列出未通过项且确认按钮禁用', () => {
    const w = setup(2)
    expect(w.text()).toContain('无待确认')
    const confirm = w.findAll('button').find((b) => b.text().includes('确认发布'))
    expect(confirm?.attributes('disabled')).toBeDefined()
  })

  it('无待确认 → 该项通过', () => {
    const w = setup(0)
    // 至少"无待确认"项为 ✓（不因 review 阻塞；其余项可能因 dirty 等另算）
    const li = w.findAll('li').find((n) => n.text().includes('无待确认'))
    expect(li?.classes()).not.toContain('fail')
  })
})
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `cd frontend && npx vitest run tests/unit/PublishChecklistDialog.spec.ts`
Expected: FAIL（无"无待确认"项）。

- [ ] **Step 3: 实现**

`frontend/src/components/editor/PublishChecklistDialog.vue` 的 `checks` computed 内，在 `list.push({ label: '至少包含 1 个章节', ... })` 之后追加：
```ts
  const reviewPending = store.chapters.filter((c) => c.mark_status === 'review').length
  list.push({ label: `无待确认节点${reviewPending ? `（剩 ${reviewPending}）` : ''}`, ok: reviewPending === 0 })
```
（`canConfirm` 已是 `checks.every(c => c.ok || c.warning)`，故 review 未清时自动禁用确认。）

- [ ] **Step 4: 跑测试 + 前端全量 Gate**

Run: `cd frontend && npx vitest run tests/unit/PublishChecklistDialog.spec.ts && npm run lint && npm run typecheck && npm run test && npm run build`
Expected: 全绿。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/editor/PublishChecklistDialog.vue frontend/tests/unit/PublishChecklistDialog.spec.ts
git commit -m "$(cat <<'EOF'
feat(p2b): publish checklist blocks while review nodes remain

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## 收尾

- 最终双 Gate：后端 `ruff + mypy + pytest`，前端 `lint + typecheck + test + build`。
- 可选手动冒烟：导入带待确认 docx → 编辑器看到徽标/计数 → 「只看待确认」+「下一个」逐条核 →「接受」/「全部接受」清零 → 改某 review 节点类型/层级自动清 → 发布前清单"无待确认"通过、可发布；未清完点发布被拦。
- 用 superpowers:finishing-a-development-branch 收束。

## Self-Review 记录

- **Spec 覆盖**：D1 逐个接受（T3 按钮 + T2 acceptReview）；D2 全部接受（T2 acceptAllReviews + T4 按钮）；D3 只看待确认 + 下一个（T4 reviewNav + 过滤）；D4 自动清（T2 toggleContentType/promote/demote）；D5 发布拦截（T1 后端 + T5 清单）。
- **占位符**：无；每步含完整代码与命令。
- **类型/契约一致**：`acceptReview`/`acceptAllReviews`（T2 定义，T3/T4 用）；`nextReviewId`（T4 定义+用）；`reviewCount`（P2a 既有，T4/T5 用）；`mark_status` 清理统一走 `setMark`（不入批量保存 payload）。
- **不破坏既有**：`visibleRows` 重构保持搜索语义、叠加 review 过滤；`set_mark_status` 不 bump revision，发布乐观锁不受影响；既有 promote/demote 测试不回归（仅在 review 节点上多一次 setMark）。
- **测试环境**：组件测试用 ElementPlus 插件 + mock `@/api/http`、`@/api/chapters`；store 测试复用 `seed()`/`markSpy`；纯逻辑 `reviewNav` 独立可测。
