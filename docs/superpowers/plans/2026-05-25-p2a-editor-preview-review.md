# P2a · 编辑器基座（Word 预览栏 + 携带 review）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 导入把 `review` 带进 draft（不再拦截）；程序编辑器内嵌可折叠 Word 原文预览栏；编辑器只读暴露待确认（行徽标 + 计数）。

**Architecture:** 后端只改 `import_service`（去拦截 + 透传 review）。前端：`http` 加按请求跳过错误 toast 的开关；`fetchSourceDocx` 取回原文 blob（404→null）；纯逻辑 `editorPreview.ts`（折叠/宽度持久化）；新组件 `EditorPreviewPane.vue`（取 blob→`WordPreviewPanel`，折叠复用 `ImportSideRail`，可拖宽，渲染延迟到展开）；接进 `ProcedureEditorView` 最左；`TreeRow`/`ChapterTreePanel` 暴露 review。

**Tech Stack:** 后端 FastAPI + pytest；前端 Vue 3 `<script setup>` + TS + Vitest + Element Plus + @vueuse/core。

**Gate：** 后端（cwd=`backend/`）`.venv/bin/ruff check app tests && .venv/bin/mypy app && .venv/bin/python -m pytest -q`；前端（cwd=`frontend/`）`npm run lint && npm run typecheck && npm run test && npm run build`。

**上位文档：** `docs/superpowers/specs/2026-05-25-p2a-editor-preview-review-design.md`

---

## 关键事实（实现者必读）

- 后端 `import_service.import_procedure`：开头有 `_has_review` → 抛 `REVIEW_NOT_CLEARED`(422)；`_create_node` 把每个节点硬设 `mark_status="unmarked"`。
- 集成测试 `backend/tests/integration/test_word_import.py` 有 `test_smart_unstyled_review_blocks_import`（断言带 review 导入 422），需更新。helpers：`_leaf`、`_upload`、`PARSE`、`IMPORT`、`_clear_review`、`_flatten`、`from tests.unit.parser._docx_builder import unstyled_numbered_sop`。
- 后端 venv：`.venv/bin/python -m pytest` / `.venv/bin/ruff` / `.venv/bin/mypy`。
- 前端 `http`（`frontend/src/api/http.ts`）的响应拦截器对**任何**错误都 `ElMessage.error` 后 reject；blob 请求下 404 的 body 是 Blob，detail 解析不出 → 会弹通用错误。故需"按请求跳过 toast"。
- `EditorChapter.mark_status`/`ChapterTreeNode.mark_status` 已含 `'review'`；`store.chapters: EditorChapter[]`、`store.steps: EditorStep[]` 已暴露（`ChapterTreePanel` 已用 `store.chapters`）。
- `WordPreviewPanel.vue`：props `file: File | null`，docx-preview 渲染，自带头部（标题+缩放），有"未加载/失败"空态。
- `ImportSideRail.vue`：props `{ label, side: 'left'|'right' }`，emit `expand`；左侧展开箭头 `»`。
- 编辑器壳 `ProcedureEditorView.vue` 模板里 `.body` = `<div class="left">(ChapterTreePanel)</div><div class="right">…</div>`；`store.procedure.id` 可用。
- `ChapterTreePanel.vue` 顶部有 `.tree-toolbar`（搜索 + root-add/mark-bar）。`TreeRow.vue` 行内 `FlatRow` 含 `mark_status`；已有 `c-review` 图标配色。
- 提交结尾必带（harness 规定的合法署名，勿当伪造）：`Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`

---

## File Structure

- 改 `backend/app/services/import_service.py` — 去 review 拦截 + 透传 review。
- 改 `backend/tests/integration/test_word_import.py` — 更新 review 测试。
- 改 `frontend/src/api/http.ts` — `skipErrorToast` 开关。
- 改 `frontend/src/api/procedures.ts` — `fetchSourceDocx`。
- 新建 `frontend/src/utils/editorPreview.ts` — 折叠/宽度纯逻辑。
- 新建 `frontend/tests/unit/utils/editorPreview.spec.ts`。
- 新建 `frontend/src/components/editor/EditorPreviewPane.vue` + `frontend/tests/unit/EditorPreviewPane.spec.ts`。
- 改 `frontend/src/views/procedures/ProcedureEditorView.vue` — 接入预览列。
- 改 `frontend/src/components/editor/TreeRow.vue` — review 徽标 + `frontend/tests/unit/TreeRow.spec.ts`（扩展）。
- 改 `frontend/src/components/editor/ChapterTreePanel.vue` — review 计数。

---

## Task 1: 后端——导入携带 review、不再拦截

**Files:**
- Modify: `backend/app/services/import_service.py`
- Test: `backend/tests/integration/test_word_import.py`

- [ ] **Step 1: 改测试（先让它表达新行为，红）**

把 `test_smart_unstyled_review_blocks_import` 整体替换为：

```python
def test_smart_unstyled_review_carried_into_draft(client: TestClient, storage_tmp: Path) -> None:
    leaf = _leaf(client)
    token = _upload(client, unstyled_numbered_sop())
    parsed = client.post(PARSE, json={"upload_token": token, "parse_mode": "smart"}).json()
    assert parsed["review_required"] >= 2

    # 带 review 直接导入：不再拦截，建成 DRAFT 草稿
    ok = client.post(
        IMPORT, json={"name": "带待确认", "folder_id": leaf, "chapters": parsed["chapters"]}
    )
    assert ok.status_code == 201, ok.text
    pid = ok.json()["id"]

    # review 状态带进草稿：至少一个章节 mark_status == 'review'
    detail = client.get(f"/api/v1/procedures/{pid}").json()
    flat = _flatten(detail["chapters"])
    assert any(n["mark_status"] == "review" for n in flat), "review 应带入草稿"
```

（`_clear_review` helper 现在可能无人使用——若 lint/未用告警，删掉它；否则保留无妨。）

- [ ] **Step 2: 跑测试，确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_word_import.py -q -k review`
Expected: FAIL（当前带 review 导入返 422；且节点 mark_status 全 unmarked）。

- [ ] **Step 3: 实现——去拦截 + 透传 review**

在 `backend/app/services/import_service.py`：

1. `import_procedure` 里删除这段 review 拦截：
```python
    if _has_review(chapters):
        raise unprocessable(
            "REVIEW_NOT_CLEARED",
            "存在未确认的 review 节点，导入前必须全部确认/降级",
            field="chapters",
        )
```

2. `_create_node` 里把 `mark_status="unmarked"` 改为透传 review：
```python
        mark_status="review" if node.mark_status == "review" else "unmarked",
```

3. 删除现在无人调用的 `_has_review` 辅助函数（保留会触发 ruff 未用告警）。若 `unprocessable` 不再被该文件其他处使用，一并从 import 移除（先 grep 确认）。

- [ ] **Step 4: 跑测试 + 后端 Gate**

Run: `cd backend && .venv/bin/python -m pytest -q && .venv/bin/ruff check app tests && .venv/bin/mypy app`
Expected: 全绿；ruff/mypy clean。确认 `test_full_standard_flow` 等仍过（它本就无 review）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/import_service.py backend/tests/integration/test_word_import.py
git commit -m "$(cat <<'EOF'
feat(p2a): import carries review into draft, no longer blocks

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: 前端基础设施——`skipErrorToast` + `fetchSourceDocx` + `editorPreview` 纯逻辑

**Files:**
- Modify: `frontend/src/api/http.ts`, `frontend/src/api/procedures.ts`
- Create: `frontend/src/utils/editorPreview.ts`, `frontend/tests/unit/utils/editorPreview.spec.ts`

- [ ] **Step 1: 写 editorPreview 纯逻辑的失败测试**

新建 `frontend/tests/unit/utils/editorPreview.spec.ts`：

```ts
import { describe, it, expect } from 'vitest'
import {
  PREVIEW_DEFAULTS,
  PREVIEW_MIN,
  PREVIEW_MAX,
  clampPreviewWidth,
  resizePreview,
  sanitizePreview,
} from '@/utils/editorPreview'

describe('editorPreview', () => {
  it('clampPreviewWidth 夹到 [MIN, MAX]，NaN 回默认', () => {
    expect(clampPreviewWidth(100)).toBe(PREVIEW_MIN)
    expect(clampPreviewWidth(9999)).toBe(PREVIEW_MAX)
    expect(clampPreviewWidth(500)).toBe(500)
    expect(clampPreviewWidth(Number.NaN)).toBe(PREVIEW_DEFAULTS.width)
  })

  it('resizePreview 按 deltaPx 调宽并夹紧；collapsed 透传', () => {
    expect(resizePreview({ collapsed: false, width: 400 }, 60)).toEqual({ collapsed: false, width: 460 })
    expect(resizePreview({ collapsed: false, width: 400 }, -1000).width).toBe(PREVIEW_MIN)
    expect(resizePreview({ collapsed: true, width: 400 }, 60).collapsed).toBe(true)
  })

  it('sanitizePreview：合法透传；脏值回默认；宽度夹紧', () => {
    expect(sanitizePreview({ collapsed: true, width: 500 })).toEqual({ collapsed: true, width: 500 })
    expect(sanitizePreview(null)).toEqual({ ...PREVIEW_DEFAULTS })
    expect(sanitizePreview({ collapsed: 'x', width: 'y' })).toEqual({ ...PREVIEW_DEFAULTS })
    expect(sanitizePreview({ collapsed: false, width: 99999 }).width).toBe(PREVIEW_MAX)
  })
})
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `cd frontend && npx vitest run tests/unit/utils/editorPreview.spec.ts`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 实现 editorPreview.ts**

新建 `frontend/src/utils/editorPreview.ts`：

```ts
/** 编辑器 Word 预览列的折叠态与宽度（像素）。 */
export interface PreviewState {
  collapsed: boolean
  width: number
}

/** 默认：展开、460px。 */
export const PREVIEW_DEFAULTS: Readonly<PreviewState> = { collapsed: false, width: 460 }
/** 预览列宽度边界（像素）。 */
export const PREVIEW_MIN = 240
export const PREVIEW_MAX = 900

/** 夹到 [MIN, MAX]；非有限值回默认宽度。 */
export function clampPreviewWidth(w: number): number {
  if (!Number.isFinite(w)) return PREVIEW_DEFAULTS.width
  return Math.min(Math.max(w, PREVIEW_MIN), PREVIEW_MAX)
}

/** 按像素增量调宽（夹紧），保持 collapsed。 */
export function resizePreview(start: PreviewState, deltaPx: number): PreviewState {
  return { collapsed: start.collapsed, width: clampPreviewWidth(start.width + deltaPx) }
}

/** 校验持久化值：非对象/脏值回默认；宽度夹紧；collapsed 仅认 boolean。 */
export function sanitizePreview(v: unknown): PreviewState {
  if (typeof v !== 'object' || v === null) return { ...PREVIEW_DEFAULTS }
  const o = v as Record<string, unknown>
  if (typeof o.collapsed !== 'boolean' || typeof o.width !== 'number') return { ...PREVIEW_DEFAULTS }
  return { collapsed: o.collapsed, width: clampPreviewWidth(o.width) }
}
```

- [ ] **Step 4: http skipErrorToast 开关**

改 `frontend/src/api/http.ts`：在文件内（`import` 后）加 axios 配置增强，并让拦截器读它：

```ts
declare module 'axios' {
  // 按请求关闭统一错误 toast（用于"预期内"的失败，如可选资源 404）。
  export interface AxiosRequestConfig {
    skipErrorToast?: boolean
  }
}
```
把拦截器错误分支改为：
```ts
  (error) => {
    if (!error?.config?.skipErrorToast) {
      const detail = error?.response?.data?.detail as ApiErrorDetail | undefined
      ElMessage.error(detail?.message ?? '请求失败，请稍后重试')
    }
    return Promise.reject(error)
  },
```

- [ ] **Step 5: fetchSourceDocx**

在 `frontend/src/api/procedures.ts` 末尾追加：

```ts
// 取回导入程序的原始 .docx（供编辑器预览栏渲染）。无原文 / 取回失败 → null（非关键，不弹错）。
export const fetchSourceDocx = async (
  id: string,
): Promise<{ blob: Blob; filename: string } | null> => {
  try {
    const resp = await http.get(`/procedures/${id}/source-docx`, {
      responseType: 'blob',
      skipErrorToast: true,
    })
    const cd = String(resp.headers['content-disposition'] ?? '')
    const m = /filename\*=UTF-8''([^;]+)/.exec(cd)
    const filename = m ? decodeURIComponent(m[1]) : 'source.docx'
    return { blob: resp.data as Blob, filename }
  } catch {
    return null
  }
}
```

- [ ] **Step 6: 跑测试 + 前端 Gate**

Run: `cd frontend && npx vitest run tests/unit/utils/editorPreview.spec.ts && npm run lint && npm run typecheck`
Expected: editorPreview 测试 PASS；lint/typecheck clean。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/api/http.ts frontend/src/api/procedures.ts frontend/src/utils/editorPreview.ts frontend/tests/unit/utils/editorPreview.spec.ts
git commit -m "$(cat <<'EOF'
feat(p2a): fetchSourceDocx + skipErrorToast + editorPreview state util

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `EditorPreviewPane.vue` + 接入编辑器

**Files:**
- Create: `frontend/src/components/editor/EditorPreviewPane.vue`, `frontend/tests/unit/EditorPreviewPane.spec.ts`
- Modify: `frontend/src/views/procedures/ProcedureEditorView.vue`

- [ ] **Step 1: 写组件失败测试**

新建 `frontend/tests/unit/EditorPreviewPane.spec.ts`：

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

vi.mock('@/api/procedures', () => ({
  fetchSourceDocx: vi.fn(),
}))
// 避免 jsdom 跑 docx-preview：把子组件 stub 掉（用 global stubs）。
import { fetchSourceDocx } from '@/api/procedures'
import EditorPreviewPane from '@/components/editor/EditorPreviewPane.vue'

const stubs = {
  WordPreviewPanel: { template: '<div class="stub-preview" />' },
  ImportSideRail: {
    props: ['label', 'side'],
    emits: ['expand'],
    template: '<div class="stub-rail" @click="$emit(\'expand\')">{{ label }}</div>',
  },
}

beforeEach(() => {
  localStorage.clear()
  vi.mocked(fetchSourceDocx).mockReset()
})

describe('EditorPreviewPane', () => {
  it('无原文（null）时不渲染预览列', async () => {
    vi.mocked(fetchSourceDocx).mockResolvedValue(null)
    const w = mount(EditorPreviewPane, { props: { procedureId: 'p1' }, global: { stubs } })
    await flushPromises()
    expect(w.find('.preview-col').exists()).toBe(false)
    expect(w.find('.stub-preview').exists()).toBe(false)
  })

  it('有原文时渲染预览面板', async () => {
    vi.mocked(fetchSourceDocx).mockResolvedValue({ blob: new Blob(['x']), filename: 'a.docx' })
    const w = mount(EditorPreviewPane, { props: { procedureId: 'p1' }, global: { stubs } })
    await flushPromises()
    expect(w.find('.preview-col').exists()).toBe(true)
    expect(w.find('.stub-preview').exists()).toBe(true)
  })

  it('点折叠按钮 → 显示竖条；点竖条 → 还原', async () => {
    vi.mocked(fetchSourceDocx).mockResolvedValue({ blob: new Blob(['x']), filename: 'a.docx' })
    const w = mount(EditorPreviewPane, { props: { procedureId: 'p1' }, global: { stubs } })
    await flushPromises()
    await w.get('.collapse-btn').trigger('click')
    expect(w.find('.stub-rail').exists()).toBe(true)
    expect(w.find('.stub-preview').exists()).toBe(false)
    await w.get('.stub-rail').trigger('click')
    expect(w.find('.stub-preview').exists()).toBe(true)
  })
})
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `cd frontend && npx vitest run tests/unit/EditorPreviewPane.spec.ts`
Expected: FAIL（组件不存在）。

- [ ] **Step 3: 实现组件**

新建 `frontend/src/components/editor/EditorPreviewPane.vue`：

```vue
<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useStorage, useEventListener } from '@vueuse/core'
import WordPreviewPanel from '@/components/import-v2/WordPreviewPanel.vue'
import ImportSideRail from '@/components/import-v2/ImportSideRail.vue'
import { fetchSourceDocx } from '@/api/procedures'
import {
  PREVIEW_DEFAULTS,
  resizePreview,
  sanitizePreview,
  type PreviewState,
} from '@/utils/editorPreview'

const props = defineProps<{ procedureId: string }>()

const DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
const file = ref<File | null>(null)
const everShown = ref(false) // 渲染延迟：首次展开后才挂载 WordPreviewPanel

const state = useStorage<PreviewState>('smartsop.editor.preview', { ...PREVIEW_DEFAULTS })
state.value = sanitizePreview(state.value)

onMounted(async () => {
  const got = await fetchSourceDocx(props.procedureId)
  if (!got) return
  file.value = new File([got.blob], got.filename, { type: DOCX_MIME })
  if (!state.value.collapsed) everShown.value = true
})

watch(
  () => state.value.collapsed,
  (c) => { if (!c) everShown.value = true },
)

// 拖拽调宽
const drag = ref<{ startX: number; startW: number } | null>(null)
function onDragStart(e: PointerEvent): void {
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  drag.value = { startX: e.clientX, startW: state.value.width }
  document.body.style.userSelect = 'none'
  document.body.style.cursor = 'col-resize'
}
function endDrag(): void {
  if (!drag.value) return
  drag.value = null
  document.body.style.userSelect = ''
  document.body.style.cursor = ''
}
useEventListener(window, 'pointermove', (e: PointerEvent) => {
  if (!drag.value) return
  state.value = resizePreview({ collapsed: false, width: drag.value.startW }, e.clientX - drag.value.startX)
})
useEventListener(window, 'pointerup', endDrag)
useEventListener(window, 'pointercancel', endDrag)
function resetWidth(): void {
  state.value = { collapsed: false, width: PREVIEW_DEFAULTS.width }
}
</script>

<template>
  <div
    v-if="file"
    class="preview-col"
    :style="{ width: (state.collapsed ? 32 : state.width) + 'px' }"
  >
    <ImportSideRail
      v-if="state.collapsed"
      label="Word 原文预览"
      side="left"
      @expand="state.collapsed = false"
    />
    <template v-else>
      <WordPreviewPanel v-if="everShown" :file="file" class="preview-body" />
      <div class="preview-splitter" title="拖拽调宽，双击重置" @pointerdown="onDragStart" @dblclick="resetWidth">
        <button class="collapse-btn" title="折叠原文预览" @click.stop="state.collapsed = true" @pointerdown.stop>«</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.preview-col {
  flex: none;
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-right: 1px solid var(--el-border-color-lighter, #ebeef5);
}
.preview-body { flex: 1; min-height: 0; }
.preview-splitter {
  position: absolute;
  top: 0;
  right: -3px;
  width: 6px;
  height: 100%;
  cursor: col-resize;
  z-index: 2;
  touch-action: none;
}
.collapse-btn {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 18px;
  height: 36px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 4px;
  background: #fff;
  color: #909399;
  font-size: 12px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s, border-color 0.15s;
}
.preview-splitter:hover .collapse-btn { opacity: 1; }
.collapse-btn:hover { color: var(--el-color-primary, #d97757); border-color: var(--el-color-primary, #d97757); }
</style>
```

- [ ] **Step 4: 跑组件测试，确认通过**

Run: `cd frontend && npx vitest run tests/unit/EditorPreviewPane.spec.ts`
Expected: 3 测试 PASS。

- [ ] **Step 5: 接入编辑器壳**

改 `frontend/src/views/procedures/ProcedureEditorView.vue`：
1. import 区加：`import EditorPreviewPane from '@/components/editor/EditorPreviewPane.vue'`
2. 模板 `.body` 内、`.left` 之前插入（`store.procedure` 在该分支已非空）：
```html
      <div class="body">
        <EditorPreviewPane :procedure-id="store.procedure.id" />
        <div class="left">
          <ChapterTreePanel ref="treeRef" />
        </div>
```
（`EditorPreviewPane` 无原文时自身不渲染，不占位。）

- [ ] **Step 6: 前端全量 Gate**

Run: `cd frontend && npm run lint && npm run typecheck && npm run test && npm run build`
Expected: 全绿（含本任务新测试）。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/components/editor/EditorPreviewPane.vue frontend/tests/unit/EditorPreviewPane.spec.ts frontend/src/views/procedures/ProcedureEditorView.vue
git commit -m "$(cat <<'EOF'
feat(p2a): collapsible Word preview pane in the procedure editor

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: 只读暴露 review（行徽标 + 计数）

**Files:**
- Modify: `frontend/src/components/editor/TreeRow.vue`, `frontend/src/components/editor/ChapterTreePanel.vue`
- Test: `frontend/tests/unit/TreeRow.spec.ts`

- [ ] **Step 1: 写 TreeRow 徽标失败测试**

在 `frontend/tests/unit/TreeRow.spec.ts` 追加（若无该文件则新建，参照下方最小挂载）。最小挂载需要一个 `FlatRow` 与必填 props：

```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import TreeRow from '@/components/editor/TreeRow.vue'
import type { FlatRow } from '@/types/node'

function row(partial: Partial<FlatRow>): FlatRow {
  return {
    id: 'n1', kind: 'chapter', depth: 0, parent_id: null, title: 'T', code: '1',
    skip_numbering: false, mark_status: 'unmarked', form_type: null,
    require_confirmation: false, has_children: false, expanded: false, fallback: '(空)',
    ...partial,
  }
}
const base = {
  selected: false, markMode: false, selectedForMark: false,
  addState: { canAddChapter: false, canAddContent: false, canAddStep: false },
  editable: false, canMoveUp: false, canMoveDown: false,
  canPromote: false, canDemote: false, dropHint: '' as const,
}

describe('TreeRow review 徽标', () => {
  it('mark_status=review 显示「待确认」徽标', () => {
    const w = mount(TreeRow, { props: { row: row({ mark_status: 'review' }), ...base } })
    expect(w.find('.tr-review').exists()).toBe(true)
    expect(w.find('.tr-review').text()).toContain('待确认')
  })
  it('非 review 不显示徽标', () => {
    const w = mount(TreeRow, { props: { row: row({ mark_status: 'unmarked' }), ...base } })
    expect(w.find('.tr-review').exists()).toBe(false)
  })
})
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `cd frontend && npx vitest run tests/unit/TreeRow.spec.ts`
Expected: FAIL（无 `.tr-review`）。

- [ ] **Step 3: TreeRow 加徽标**

在 `frontend/src/components/editor/TreeRow.vue` 模板里，`tr-title` 之后、`tr-typebar` 之前插入：
```html
    <span v-if="row.mark_status === 'review'" class="tr-review" title="解析存疑，待确认">待确认</span>
```
样式区追加：
```css
.tr-review {
  flex: none;
  font-size: 11px;
  line-height: 1;
  padding: 1px 4px;
  border-radius: 3px;
  color: #b88230;
  background: #fdf6ec;
  border: 1px solid #f5dab1;
}
```

- [ ] **Step 4: ChapterTreePanel 加计数**

在 `frontend/src/components/editor/ChapterTreePanel.vue`：
1. `<script setup>` 内（`store` 之后）加：
```ts
const reviewCount = computed(() => store.chapters.filter((c) => c.mark_status === 'review').length)
```
（`computed` 已 import。）
2. 模板 `.tree-toolbar` 内、搜索 `el-input` 之后插入：
```html
      <div v-if="reviewCount" class="review-count" title="解析存疑，待确认">⚠ {{ reviewCount }} 个待确认</div>
```
3. 样式区追加：
```css
.review-count { font-size: 12px; color: #e6a23c; padding: 2px 0; }
```

- [ ] **Step 5: 前端全量 Gate**

Run: `cd frontend && npm run lint && npm run typecheck && npm run test && npm run build`
Expected: 全绿。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/components/editor/TreeRow.vue frontend/src/components/editor/ChapterTreePanel.vue frontend/tests/unit/TreeRow.spec.ts
git commit -m "$(cat <<'EOF'
feat(p2a): surface review state read-only (row badge + tree count)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## 收尾

- 最终双 Gate：后端 `ruff + mypy + pytest`，前端 `lint + typecheck + test + build`。
- 可选手动冒烟：导入一份带待确认的 docx → 进编辑器 → 左侧出现可折叠 Word 预览（折叠/展开/拖宽/重开记忆）→ 树行有"待确认"徽标 + 头部计数；空白新建的程序无预览列。
- 用 superpowers:finishing-a-development-branch 收束（合并 / PR / 保留 / 丢弃，由用户选）。

## Self-Review 记录

- **Spec 覆盖**：D1 导入携带 review（T1）；D2 可折叠预览列（T2 取回+持久化逻辑、T3 组件+接入）；D3 只读暴露 review（T4）。renderAsync 延迟到首次展开（T3 `everShown`）。仅有原文才显示（T3 `v-if="file"`）。
- **占位符**：无 TBD；每步含完整代码与确切命令。
- **类型一致**：`PreviewState`/`sanitizePreview`/`resizePreview`/`clampPreviewWidth`（T2 定义、T3 用）；`fetchSourceDocx` 返回 `{blob,filename}|null`（T2 定义、T3 用）；`skipErrorToast`（T2 augment、fetchSourceDocx 用）。
- **不破坏既有**：`http` 仅在显式 `skipErrorToast` 时静默；预览列无原文不渲染、不占位；beta2 导入前清 review，不受 T1 影响。
- **测试环境**：组件测试 stub 掉 `WordPreviewPanel`(docx-preview) 与 `ImportSideRail`，避免 jsdom 渲染问题；`EditorPreviewPane` 不直接用 `el-*` 交互组件（折叠按钮是原生 `button`）。
