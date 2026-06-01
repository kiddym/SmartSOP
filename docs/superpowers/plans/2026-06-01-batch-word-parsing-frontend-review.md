# 批量解析 Word — Plan 3：前端审阅台 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 前端批量审阅台闭环——多选上传 → 风险导向列表（轮询进度）→ 抽屉速览 / 节点级 diff 改判 → dry-run 影响摘要 → 批量应用，键盘 triage 全程不离手。

**Architecture:** 全新页面 `BatchReviewView`，对接 Plan 1/2 的后端端点。**审阅对象是暂存 blob（`ParseResponse` 形态），不是 `ProcedureNode`**——因此不复用 `nodeEditor` store / `nodes.ts`，改判通过 `PATCH /batch-imports/{job}/items/{item}/review` 写回暂存（`review_revision` 乐观锁，409→reload-wins，复用 `isVersionConflict`）。新建 `api/batchImports.ts` + Pinia `batchReview` store；复用纯 composable `useVirtualRows` 与级联选择 `buildCascadeSelection`。进度靠轮询（无 SSE）。

**Tech Stack:** Vue 3 `<script setup>` + TypeScript / Pinia（options 风格，对齐 `nodeEditor`）/ Element Plus（全局注册）/ axios（`@/api/http`）/ Vitest + @vue/test-utils。

**前置依赖：** **Plan 1 + Plan 2 已完成**（后端所有批次端点可用）。

**非目标：** 多人实时协同 / 在场感知 / SSE（用轮询）；"记住此样式"（动态字典非目标）。

---

## 关键约定（先读）

- **blob = `ParseResponse`**：`GET .../parse-result` 返回的 JSON 与现有 `/parse` 响应同构，直接用现成 `import type { ParseResponse, ParsedNode } from '@/types/parse'`（若类型文件名不同，按现有 parse 响应类型路径引入）。
- **改判走后端 ops**：改判卡的"接受/改为正文/改为步骤/改层级"映射为 `ReviewOp[]`，调 `patchReviewItem(jobId, itemId, { review_revision, ops })`；成功后 `review_revision` 递增，本地刷新 blob。409 → `ElMessage.warning` + 重新拉 blob（reload-wins）。
- **API 解包**：对齐 `parse.ts` 写法——每个 api 函数内部 `const { data } = await http.xxx(...)` 返回 `data`。
- **轮询**：进入审阅台或应用后启动 `setInterval`（3000ms）拉 `job`(含 counts) + `items`；当无 `queued/parsing/applying` 项时停止。组件卸载必清 interval。
- **Element Plus** 全局注册，`el-drawer`/`el-dialog`/`el-button`/`ElMessage`/`ElMessageBox` 直接用。

---

## 文件结构

| 文件 | 责任 | 动作 |
|---|---|---|
| `frontend/src/types/batchImport.ts` | 批次相关 TS 类型 | 创建 |
| `frontend/src/api/batchImports.ts` | 批次 REST 封装 | 创建 |
| `frontend/src/store/batchReview.ts` | 批量审阅 Pinia store | 创建 |
| `frontend/src/composables/useBatchReviewShortcuts.ts` | 键盘 triage | 创建 |
| `frontend/src/components/batch/BatchImportDialog.vue` | 多选上传对话框 | 创建 |
| `frontend/src/components/batch/BatchReviewRow.vue` | 风险列表行 | 创建 |
| `frontend/src/components/batch/ReviewDrawer.vue` | 抽屉速览（只读结构树 + 改判卡） | 创建 |
| `frontend/src/components/batch/DiffRejudgeCard.vue` | 节点级 diff 改判卡 | 创建 |
| `frontend/src/components/batch/ApplyPreviewDialog.vue` | dry-run 影响摘要弹窗 | 创建 |
| `frontend/src/views/procedures/BatchReviewView.vue` | 审阅台页面 | 创建 |
| `frontend/src/router/index.ts` | 注册 `/procedures/batch-review/:jobId` | 修改 |
| `frontend/tests/unit/store/batchReview.spec.ts` | store 测试 | 创建 |
| `frontend/tests/unit/components/BatchReviewRow.spec.ts` | 行组件测试 | 创建 |
| `frontend/tests/unit/components/DiffRejudgeCard.spec.ts` | 改判卡测试 | 创建 |

---

## Task 1: 类型 + API 封装

**Files:**
- Create: `frontend/src/types/batchImport.ts`
- Create: `frontend/src/api/batchImports.ts`
- Test: 由 Task 2 store 测试间接覆盖（api 是薄封装）。

- [ ] **Step 1: 写类型**

Create `frontend/src/types/batchImport.ts`:

```typescript
import type { ParseResponse } from '@/types/parse'

export type BatchItemStatus =
  | 'queued' | 'parsing' | 'review' | 'applying' | 'applied' | 'skipped' | 'failed'

export interface BatchCounts {
  total: number
  parsed: number
  review: number
  applied: number
  failed: number
}

export interface BatchImportJob {
  id: string
  folder_id: string
  parse_mode: string
  status: string
  counts: BatchCounts
  created_at: string
}

export interface BatchImportItem {
  id: string
  job_id: string
  filename: string
  status: BatchItemStatus
  content_hash: string
  summary: { chapter_count?: number; confidence_tier?: string; warning_count?: number }
  error: string | null
}

export type ReviewAction = 'accept' | 'to_content' | 'to_chapter' | 'set_level'

export interface ReviewOp {
  node_id: string
  action: ReviewAction
  level?: number
}

export interface ApplyPreview {
  to_create: number
  duplicate_skip: number
  target_folder_id: string
}

export type BatchBlob = ParseResponse
```

- [ ] **Step 2: 写 API 封装**

Create `frontend/src/api/batchImports.ts`:

```typescript
import { http } from './http'
import type {
  ApplyPreview, BatchBlob, BatchImportItem, BatchImportJob, ReviewOp,
} from '@/types/batchImport'

export interface BatchCreatePayload {
  folder_id: string
  parse_mode: string
  items: { filename: string; upload_token: string }[]
}

export const createBatchImport = async (payload: BatchCreatePayload): Promise<BatchImportJob> => {
  const { data } = await http.post('/batch-imports', payload)
  return data
}

export const fetchBatchJob = async (jobId: string): Promise<BatchImportJob> => {
  const { data } = await http.get(`/batch-imports/${jobId}`)
  return data
}

export const fetchBatchItems = async (
  jobId: string, status?: string,
): Promise<BatchImportItem[]> => {
  const { data } = await http.get(`/batch-imports/${jobId}/items`, {
    params: status ? { status } : undefined,
  })
  return data
}

export const fetchParseResult = async (jobId: string, itemId: string): Promise<BatchBlob> => {
  const { data } = await http.get(`/batch-imports/${jobId}/items/${itemId}/parse-result`)
  return data
}

export const patchReviewItem = async (
  jobId: string, itemId: string, body: { review_revision: number; ops: ReviewOp[] },
): Promise<{ review_revision: number }> => {
  // skipErrorToast：409 由 store 自管（reload-wins）
  const { data } = await http.patch(
    `/batch-imports/${jobId}/items/${itemId}/review`, body, { skipErrorToast: true },
  )
  return data
}

export const previewApply = async (
  jobId: string, itemIds: string[] | null,
): Promise<ApplyPreview> => {
  const { data } = await http.post(`/batch-imports/${jobId}/apply-preview`, { item_ids: itemIds })
  return data
}

export const applyBatch = async (
  jobId: string, opts: { itemIds?: string[] | null; highConfidenceOnly?: boolean },
): Promise<{ enqueued: number }> => {
  const { data } = await http.post(`/batch-imports/${jobId}/apply`, {
    item_ids: opts.itemIds ?? null,
    high_confidence_only: opts.highConfidenceOnly ?? false,
  })
  return data
}

export const retryItem = (jobId: string, itemId: string): Promise<void> =>
  http.post(`/batch-imports/${jobId}/items/${itemId}/retry`).then(() => undefined)

export const skipItem = (jobId: string, itemId: string): Promise<void> =>
  http.post(`/batch-imports/${jobId}/items/${itemId}/skip`).then(() => undefined)

export const undoItem = (jobId: string, itemId: string): Promise<void> =>
  http.post(`/batch-imports/${jobId}/items/${itemId}/undo`).then(() => undefined)
```

- [ ] **Step 3: 类型检查 + 提交**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 无新增类型错误（若 `@/types/parse` 的 `ParseResponse` 路径不同，按实际调整 import）。

```bash
cd frontend && npx eslint src/types/batchImport.ts src/api/batchImports.ts --fix
git add src/types/batchImport.ts src/api/batchImports.ts
git commit -m "feat(batch-fe): types + batch imports api client"
```

---

## Task 2: `batchReview` Pinia store

**Files:**
- Create: `frontend/src/store/batchReview.ts`
- Test: `frontend/tests/unit/store/batchReview.spec.ts`

- [ ] **Step 1: 写失败测试**

Create `frontend/tests/unit/store/batchReview.spec.ts`:

```typescript
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import * as api from '@/api/batchImports'
import { useBatchReviewStore } from '@/store/batchReview'

const job = {
  id: 'j1', folder_id: 'f1', parse_mode: 'smart', status: 'reviewing',
  counts: { total: 2, parsed: 2, review: 2, applied: 0, failed: 0 }, created_at: '',
}
const items = [
  { id: 'i1', job_id: 'j1', filename: 'a.docx', status: 'review', content_hash: 'h1',
    summary: { chapter_count: 3, confidence_tier: 'high', warning_count: 0 }, error: null },
  { id: 'i2', job_id: 'j1', filename: 'b.docx', status: 'review', content_hash: 'h2',
    summary: { chapter_count: 5, confidence_tier: 'low', warning_count: 2 }, error: null },
]

describe('batchReview store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('loads job + items and computes risk-sorted rows', async () => {
    vi.spyOn(api, 'fetchBatchJob').mockResolvedValue(job as never)
    vi.spyOn(api, 'fetchBatchItems').mockResolvedValue(items as never)
    const store = useBatchReviewStore()
    await store.load('j1')
    expect(store.job?.id).toBe('j1')
    expect(store.items).toHaveLength(2)
    // 风险优先：low 排在 high 前
    expect(store.riskSortedItems[0].id).toBe('i2')
    expect(store.highConfidenceIds).toEqual(['i1'])
  })

  it('applyReviewOps bumps local revision and reloads blob', async () => {
    vi.spyOn(api, 'fetchBatchJob').mockResolvedValue(job as never)
    vi.spyOn(api, 'fetchBatchItems').mockResolvedValue(items as never)
    const blob = { chapters: [], metadata: {}, assets: [], warnings: [],
      detected_patterns: [], validation: null, review_required: 0, parse_method: 'smart' }
    vi.spyOn(api, 'fetchParseResult').mockResolvedValue(blob as never)
    const patchSpy = vi.spyOn(api, 'patchReviewItem').mockResolvedValue({ review_revision: 2 })

    const store = useBatchReviewStore()
    await store.load('j1')
    await store.openItem('i1')
    store.reviewRevision = 1
    await store.applyReviewOps([{ node_id: 'n1', action: 'to_content' }])
    expect(patchSpy).toHaveBeenCalledWith('j1', 'i1', { review_revision: 1, ops: [{ node_id: 'n1', action: 'to_content' }] })
    expect(store.reviewRevision).toBe(2)
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/store/batchReview.spec.ts`
Expected: FAIL — 无法解析 `@/store/batchReview`

- [ ] **Step 3: 写 store**

Create `frontend/src/store/batchReview.ts`:

```typescript
import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'

import * as api from '@/api/batchImports'
import { isVersionConflict } from '@/api/http'
import type {
  ApplyPreview, BatchBlob, BatchImportItem, BatchImportJob, ReviewOp,
} from '@/types/batchImport'

const TIER_RANK: Record<string, number> = { failed: 0, low: 1, medium: 2, high: 3 }

interface State {
  jobId: string | null
  job: BatchImportJob | null
  items: BatchImportItem[]
  statusFilter: string | null
  currentItemId: string | null
  blob: BatchBlob | null
  reviewRevision: number
  loading: boolean
  polling: number | null
}

function rank(item: BatchImportItem): number {
  if (item.status === 'failed') return -1
  return TIER_RANK[item.summary.confidence_tier ?? 'high'] ?? 3
}

export const useBatchReviewStore = defineStore('batchReview', {
  state: (): State => ({
    jobId: null, job: null, items: [], statusFilter: null,
    currentItemId: null, blob: null, reviewRevision: 1, loading: false, polling: null,
  }),

  getters: {
    riskSortedItems(state): BatchImportItem[] {
      return [...state.items].sort((a, b) => rank(a) - rank(b))
    },
    highConfidenceIds(state): string[] {
      return state.items
        .filter((i) => i.status === 'review' && i.summary.confidence_tier === 'high')
        .map((i) => i.id)
    },
    inProgress(state): boolean {
      return state.items.some((i) => ['queued', 'parsing', 'applying'].includes(i.status))
    },
    currentItem(state): BatchImportItem | null {
      return state.items.find((i) => i.id === state.currentItemId) ?? null
    },
  },

  actions: {
    async load(jobId: string): Promise<void> {
      this.jobId = jobId
      this.loading = true
      try {
        await this.refresh()
      } finally {
        this.loading = false
      }
    },

    async refresh(): Promise<void> {
      if (!this.jobId) return
      this.job = await api.fetchBatchJob(this.jobId)
      this.items = await api.fetchBatchItems(this.jobId, this.statusFilter ?? undefined)
    },

    startPolling(): void {
      if (this.polling !== null) return
      this.polling = window.setInterval(async () => {
        await this.refresh()
        if (!this.inProgress) this.stopPolling()
      }, 3000)
    },

    stopPolling(): void {
      if (this.polling !== null) {
        window.clearInterval(this.polling)
        this.polling = null
      }
    },

    async openItem(itemId: string): Promise<void> {
      if (!this.jobId) return
      this.currentItemId = itemId
      this.blob = await api.fetchParseResult(this.jobId, itemId)
      this.reviewRevision = 1
    },

    async reloadBlob(): Promise<void> {
      if (this.jobId && this.currentItemId) {
        this.blob = await api.fetchParseResult(this.jobId, this.currentItemId)
      }
    },

    async applyReviewOps(ops: ReviewOp[]): Promise<void> {
      if (!this.jobId || !this.currentItemId) return
      try {
        const res = await api.patchReviewItem(this.jobId, this.currentItemId, {
          review_revision: this.reviewRevision, ops,
        })
        this.reviewRevision = res.review_revision
        await this.reloadBlob()
      } catch (err) {
        if (isVersionConflict(err)) {
          ElMessage.warning('该条目已被修改，已为你刷新最新内容')
          this.reviewRevision += 1
          await this.reloadBlob()
          return
        }
        throw err
      }
    },

    async preview(itemIds: string[] | null): Promise<ApplyPreview> {
      if (!this.jobId) throw new Error('no job')
      return api.previewApply(this.jobId, itemIds)
    },

    async apply(opts: { itemIds?: string[] | null; highConfidenceOnly?: boolean }): Promise<void> {
      if (!this.jobId) return
      await api.applyBatch(this.jobId, opts)
      await this.refresh()
      this.startPolling()
    },

    async retry(itemId: string): Promise<void> {
      if (!this.jobId) return
      await api.retryItem(this.jobId, itemId)
      await this.refresh()
      this.startPolling()
    },

    async skip(itemId: string): Promise<void> {
      if (!this.jobId) return
      await api.skipItem(this.jobId, itemId)
      await this.refresh()
    },

    async undo(itemId: string): Promise<void> {
      if (!this.jobId) return
      await api.undoItem(this.jobId, itemId)
      await this.refresh()
    },
  },
})
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/store/batchReview.spec.ts`
Expected: PASS（2 passed）

- [ ] **Step 5: 提交**

```bash
cd frontend && npx eslint src/store/batchReview.ts tests/unit/store/batchReview.spec.ts --fix
git add src/store/batchReview.ts tests/unit/store/batchReview.spec.ts
git commit -m "feat(batch-fe): batchReview pinia store (load/poll/rejudge/apply)"
```

---

## Task 3: 多选上传对话框 + 路由

**Files:**
- Create: `frontend/src/components/batch/BatchImportDialog.vue`
- Modify: `frontend/src/router/index.ts`
- Test: 由集成手测覆盖（上传依赖浏览器 File 选择，单测价值低）；本任务做编译 + 路由烟测。

- [ ] **Step 1: 写多选上传对话框**

Create `frontend/src/components/batch/BatchImportDialog.vue`（复用 `parse.ts` 的 `uploadDocx` 拿 token，再 `createBatchImport`）:

```vue
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { uploadDocx } from '@/api/parse'
import { createBatchImport } from '@/api/batchImports'

const props = defineProps<{ modelValue: boolean; folderId: string }>()
const emit = defineEmits<{ 'update:modelValue': [boolean] }>()

const router = useRouter()
const files = ref<File[]>([])
const parseMode = ref<'standard' | 'smart'>('smart')
const busy = ref(false)
const progress = ref(0)

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

function onFiles(e: Event): void {
  const list = (e.target as HTMLInputElement).files
  files.value = list ? Array.from(list).filter((f) => f.name.toLowerCase().endsWith('.docx')) : []
}

async function submit(): Promise<void> {
  if (!files.value.length) {
    ElMessage.warning('请至少选择一个 .docx 文件')
    return
  }
  busy.value = true
  progress.value = 0
  try {
    const items: { filename: string; upload_token: string }[] = []
    for (const file of files.value) {
      const up = await uploadDocx(file)
      items.push({ filename: file.name, upload_token: up.upload_token })
      progress.value = Math.round((items.length / files.value.length) * 100)
    }
    const job = await createBatchImport({
      folder_id: props.folderId, parse_mode: parseMode.value, items,
    })
    visible.value = false
    await router.push({ name: 'batch-review', params: { jobId: job.id } })
  } catch {
    ElMessage.error('批量上传失败，请重试')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" title="批量从 Word 导入" width="520px">
    <el-form label-width="96px">
      <el-form-item label="Word 文件">
        <input type="file" accept=".docx" multiple @change="onFiles" />
        <div class="hint">已选 {{ files.length }} 个文件</div>
      </el-form-item>
      <el-form-item label="解析模式">
        <el-select v-model="parseMode">
          <el-option label="智能模式" value="smart" />
          <el-option label="标准模式" value="standard" />
        </el-select>
      </el-form-item>
      <el-progress v-if="busy" :percentage="progress" />
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="busy" @click="submit">上传并解析</el-button>
    </template>
  </el-dialog>
</template>
```

- [ ] **Step 2: 注册路由**

Modify `frontend/src/router/index.ts` — 在 `routes` 数组里追加（与现有 procedures 路由同级）:

```typescript
  {
    path: '/procedures/batch-review/:jobId',
    name: 'batch-review',
    component: () => import('@/views/procedures/BatchReviewView.vue'),
    meta: { title: '批量审阅台' },
  },
```

- [ ] **Step 3: 编译烟测**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 无新增类型错误（`BatchReviewView.vue` 在 Task 4 创建前，路由的懒加载不触发编译错误；若 tsc 对缺失文件报错，可先建空壳 `<template><div/></template>`，Task 4 再填充）。

- [ ] **Step 4: 提交**

```bash
cd frontend && npx eslint src/components/batch/BatchImportDialog.vue src/router/index.ts --fix
git add src/components/batch/BatchImportDialog.vue src/router/index.ts
git commit -m "feat(batch-fe): multi-file import dialog + route"
```

---

## Task 4: 审阅台页面 + 风险列表行

**Files:**
- Create: `frontend/src/components/batch/BatchReviewRow.vue`
- Create: `frontend/src/views/procedures/BatchReviewView.vue`
- Test: `frontend/tests/unit/components/BatchReviewRow.spec.ts`

- [ ] **Step 1: 写行组件失败测试**

Create `frontend/tests/unit/components/BatchReviewRow.spec.ts`:

```typescript
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'

import BatchReviewRow from '@/components/batch/BatchReviewRow.vue'

const item = {
  id: 'i1', job_id: 'j1', filename: 'pump.docx', status: 'review' as const,
  content_hash: 'h', summary: { chapter_count: 8, confidence_tier: 'low', warning_count: 2 },
  error: null,
}

function mountRow(over = {}) {
  return mount(BatchReviewRow, {
    props: { item: { ...item, ...over }, selected: false },
    global: { plugins: [ElementPlus] },
  })
}

describe('BatchReviewRow', () => {
  it('renders filename, chapter count and warning badge', () => {
    const w = mountRow()
    expect(w.text()).toContain('pump.docx')
    expect(w.text()).toContain('8')
    expect(w.text()).toContain('2')
  })

  it('emits open on preview click', async () => {
    const w = mountRow()
    await w.find('[data-test="preview"]').trigger('click')
    expect(w.emitted('open')).toBeTruthy()
  })

  it('emits apply on apply click for review item', async () => {
    const w = mountRow()
    await w.find('[data-test="apply"]').trigger('click')
    expect(w.emitted('apply')).toBeTruthy()
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/components/BatchReviewRow.spec.ts`
Expected: FAIL — 无法解析 `@/components/batch/BatchReviewRow.vue`

- [ ] **Step 3: 写行组件**

Create `frontend/src/components/batch/BatchReviewRow.vue`:

```vue
<script setup lang="ts">
import { computed } from 'vue'
import type { BatchImportItem } from '@/types/batchImport'

const props = defineProps<{ item: BatchImportItem; selected: boolean }>()
const emit = defineEmits<{ open: []; apply: []; edit: []; retry: []; skip: [] }>()

const STATUS_LABEL: Record<string, string> = {
  queued: '排队', parsing: '解析中', review: '待确认',
  applying: '应用中', applied: '已应用', skipped: '已跳过', failed: '失败',
}
const TIER_CLASS: Record<string, string> = { high: 'tier-high', medium: 'tier-mid', low: 'tier-low' }

const tier = computed(() => props.item.summary.confidence_tier ?? 'high')
const isReview = computed(() => props.item.status === 'review')
const isFailed = computed(() => props.item.status === 'failed')
</script>

<template>
  <div class="brow" :class="{ selected }">
    <span class="status-chip" :data-status="item.status">{{ STATUS_LABEL[item.status] }}</span>
    <span class="filename" :title="item.filename">{{ item.filename }}</span>
    <span class="tier-bar" :class="TIER_CLASS[tier]" />
    <span class="chapters">{{ item.summary.chapter_count ?? '-' }}</span>
    <span class="warnings" v-if="item.summary.warning_count">{{ item.summary.warning_count }}⚠</span>
    <span class="actions">
      <el-button v-if="isReview" size="small" data-test="preview" @click="emit('open')">预览</el-button>
      <el-button v-if="isReview" size="small" data-test="edit" @click="emit('edit')">精审</el-button>
      <el-button v-if="isReview" size="small" type="primary" data-test="apply" @click="emit('apply')">应用</el-button>
      <el-button v-if="isReview" size="small" data-test="skip" @click="emit('skip')">跳过</el-button>
      <el-button v-if="isFailed" size="small" data-test="retry" @click="emit('retry')">重试</el-button>
    </span>
  </div>
</template>
```

（样式 `.tier-low/.tier-mid/.tier-high` 色条、`.status-chip` 按 `data-status` 着色，按项目既有审阅态配色补 `<style scoped>`，不影响逻辑与测试。）

- [ ] **Step 4: 写审阅台页面**

Create `frontend/src/views/procedures/BatchReviewView.vue`:

```vue
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useBatchReviewStore } from '@/store/batchReview'
import { useVirtualRows } from '@/composables/useVirtualRows'
import { useBatchReviewShortcuts } from '@/composables/useBatchReviewShortcuts'
import BatchReviewRow from '@/components/batch/BatchReviewRow.vue'
import ReviewDrawer from '@/components/batch/ReviewDrawer.vue'
import ApplyPreviewDialog from '@/components/batch/ApplyPreviewDialog.vue'

const route = useRoute()
const store = useBatchReviewStore()

const rowsEl = ref<HTMLElement | null>(null)
const drawerVisible = ref(false)
const previewVisible = ref(false)
const previewItemIds = ref<string[] | null>(null)

const rows = computed(() => store.riskSortedItems)
const { start, end, padTop, padBottom, totalHeight } = useVirtualRows(rowsEl, () => rows.value.length)

onMounted(async () => {
  await store.load(route.params.jobId as string)
  if (store.inProgress) store.startPolling()
})
onUnmounted(() => store.stopPolling())

async function openPreview(itemId: string): Promise<void> {
  await store.openItem(itemId)
  drawerVisible.value = true
}

function openApplyPreview(itemIds: string[] | null): void {
  previewItemIds.value = itemIds
  previewVisible.value = true
}

async function confirmApply(): Promise<void> {
  await store.apply({ itemIds: previewItemIds.value })
  previewVisible.value = false
  ElMessage.success('已提交应用，后台落库中')
}

async function applyAllHighConfidence(): Promise<void> {
  openApplyPreview(store.highConfidenceIds)
}

useBatchReviewShortcuts({
  onPrev: () => store.selectPrev?.(),
  onNext: () => store.selectNext?.(),
  onOpen: () => store.currentItemId && openPreview(store.currentItemId),
  onApply: () => store.currentItemId && openApplyPreview([store.currentItemId]),
  onSkip: () => store.currentItemId && store.skip(store.currentItemId),
})
</script>

<template>
  <div class="batch-review">
    <header class="summary" v-if="store.job">
      <span>待确认 {{ store.job.counts.review }}</span>
      <span>已应用 {{ store.job.counts.applied }}</span>
      <span>失败 {{ store.job.counts.failed }}</span>
      <el-button
        type="primary"
        :disabled="!store.highConfidenceIds.length"
        @click="applyAllHighConfidence"
      >全选高置信并应用（{{ store.highConfidenceIds.length }}）</el-button>
    </header>

    <div ref="rowsEl" class="rows" :style="{ height: '70vh', overflow: 'auto' }">
      <div :style="{ height: totalHeight + 'px', position: 'relative' }">
        <div :style="{ height: padTop + 'px' }" />
        <BatchReviewRow
          v-for="item in rows.slice(start, end)"
          :key="item.id"
          :item="item"
          :selected="item.id === store.currentItemId"
          @open="openPreview(item.id)"
          @edit="openPreview(item.id)"
          @apply="openApplyPreview([item.id])"
          @skip="store.skip(item.id)"
          @retry="store.retry(item.id)"
        />
        <div :style="{ height: padBottom + 'px' }" />
      </div>
    </div>

    <ReviewDrawer v-model="drawerVisible" />
    <ApplyPreviewDialog
      v-model="previewVisible"
      :item-ids="previewItemIds"
      @confirm="confirmApply"
    />
  </div>
</template>
```

> 注：`store.selectPrev/selectNext` 为键盘导航选区动作——在 store 追加两个简单 action（按 `riskSortedItems` 顺序移动 `currentItemId`）：

在 `frontend/src/store/batchReview.ts` 的 actions 追加：

```typescript
    selectPrev(): void {
      const ids = this.riskSortedItems.map((i) => i.id)
      const idx = ids.indexOf(this.currentItemId ?? '')
      this.currentItemId = ids[Math.max(0, idx - 1)] ?? ids[0] ?? null
    },
    selectNext(): void {
      const ids = this.riskSortedItems.map((i) => i.id)
      const idx = ids.indexOf(this.currentItemId ?? '')
      this.currentItemId = ids[Math.min(ids.length - 1, idx + 1)] ?? null
    },
```

- [ ] **Step 5: 运行行组件测试**

Run: `cd frontend && npx vitest run tests/unit/components/BatchReviewRow.spec.ts`
Expected: PASS（3 passed）

- [ ] **Step 6: 提交**

```bash
cd frontend && npx eslint src/components/batch/BatchReviewRow.vue src/views/procedures/BatchReviewView.vue src/store/batchReview.ts --fix
git add src/components/batch/BatchReviewRow.vue src/views/procedures/BatchReviewView.vue src/store/batchReview.ts tests/unit/components/BatchReviewRow.spec.ts
git commit -m "feat(batch-fe): review board view + risk list row"
```

---

## Task 5: 抽屉速览 + 节点级 diff 改判卡

**Files:**
- Create: `frontend/src/components/batch/DiffRejudgeCard.vue`
- Create: `frontend/src/components/batch/ReviewDrawer.vue`
- Test: `frontend/tests/unit/components/DiffRejudgeCard.spec.ts`

- [ ] **Step 1: 写改判卡失败测试**

Create `frontend/tests/unit/components/DiffRejudgeCard.spec.ts`:

```typescript
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'

import DiffRejudgeCard from '@/components/batch/DiffRejudgeCard.vue'

const node = {
  id: 'n1', title: '3.2 操作步骤', level: 2, order: 0, parent_id: null,
  content_type: 'chapter', rich_content: '', skip_numbering: false,
  confidence: 0.55, confidence_tier: 'medium', mark_status: 'review',
  heading_source: 'heuristic', children: [],
}

describe('DiffRejudgeCard', () => {
  it('shows recognized type + confidence and emits op on action', async () => {
    const w = mount(DiffRejudgeCard, { props: { node }, global: { plugins: [ElementPlus] } })
    expect(w.text()).toContain('3.2 操作步骤')
    expect(w.text()).toContain('中')
    await w.find('[data-test="to-content"]').trigger('click')
    expect(w.emitted('op')?.[0]).toEqual([{ node_id: 'n1', action: 'to_content' }])
  })

  it('emits accept op', async () => {
    const w = mount(DiffRejudgeCard, { props: { node }, global: { plugins: [ElementPlus] } })
    await w.find('[data-test="accept"]').trigger('click')
    expect(w.emitted('op')?.[0]).toEqual([{ node_id: 'n1', action: 'accept' }])
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/components/DiffRejudgeCard.spec.ts`
Expected: FAIL — 无法解析 `@/components/batch/DiffRejudgeCard.vue`

- [ ] **Step 3: 写改判卡**

Create `frontend/src/components/batch/DiffRejudgeCard.vue`:

```vue
<script setup lang="ts">
import { computed } from 'vue'
import type { ParsedNode } from '@/types/parse'
import type { ReviewOp } from '@/types/batchImport'

const props = defineProps<{ node: ParsedNode }>()
const emit = defineEmits<{ op: [ReviewOp] }>()

const TIER_LABEL: Record<string, string> = { high: '高', medium: '中', low: '低' }
const recognized = computed(() =>
  props.node.content_type === 'chapter' ? `${props.node.level} 级章节` : '正文',
)

function emitOp(action: ReviewOp['action'], level?: number): void {
  emit('op', level === undefined ? { node_id: props.node.id, action } : { node_id: props.node.id, action, level })
}
</script>

<template>
  <div class="rejudge-card" :class="`tier-${node.confidence_tier}`">
    <div class="line">
      <span class="warn">⚠</span>
      <span class="title">{{ node.title || '（正文片段）' }}</span>
      <span class="judged">→ 识别为 {{ recognized }}（置信 {{ TIER_LABEL[node.confidence_tier] }}）</span>
    </div>
    <div class="ops">
      <el-button size="small" data-test="accept" @click="emitOp('accept')">接受</el-button>
      <el-button size="small" data-test="to-content" @click="emitOp('to_content')">改为正文</el-button>
      <el-button size="small" data-test="to-chapter" @click="emitOp('to_chapter')">改为章节</el-button>
      <el-button size="small" data-test="lvl1" @click="emitOp('set_level', 1)">改为一级</el-button>
    </div>
  </div>
</template>
```

- [ ] **Step 4: 写抽屉速览**

Create `frontend/src/components/batch/ReviewDrawer.vue`（只读结构树 + 列出需改判节点；改判 op 汇聚后调 store.applyReviewOps）:

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useBatchReviewStore } from '@/store/batchReview'
import type { ParsedNode } from '@/types/parse'
import type { ReviewOp } from '@/types/batchImport'
import DiffRejudgeCard from './DiffRejudgeCard.vue'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [boolean] }>()

const store = useBatchReviewStore()
const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

function flatten(nodes: ParsedNode[]): ParsedNode[] {
  const out: ParsedNode[] = []
  const walk = (ns: ParsedNode[]): void => {
    for (const n of ns) { out.push(n); walk(n.children) }
  }
  walk(nodes)
  return out
}

const allNodes = computed(() => (store.blob ? flatten(store.blob.chapters) : []))
const reviewNodes = computed(() =>
  allNodes.value.filter((n) => n.mark_status === 'review' || n.confidence_tier !== 'high'),
)

async function onOp(op: ReviewOp): Promise<void> {
  await store.applyReviewOps([op])
}
</script>

<template>
  <el-drawer v-model="visible" :title="store.currentItem?.filename ?? '速览'" size="640px">
    <div class="drawer-body">
      <section class="rejudge" v-if="reviewNodes.length">
        <h4>待确认节点（{{ reviewNodes.length }}）</h4>
        <DiffRejudgeCard
          v-for="n in reviewNodes" :key="n.id" :node="n" @op="onOp"
        />
      </section>
      <section class="tree">
        <h4>结构预览</h4>
        <div
          v-for="n in allNodes" :key="n.id" class="tree-node"
          :class="{ low: n.confidence_tier === 'low' }"
          :style="{ paddingLeft: (n.level * 12) + 'px' }"
        >{{ n.title || '（正文）' }}</div>
      </section>
    </div>
  </el-drawer>
</template>
```

- [ ] **Step 5: 运行改判卡测试**

Run: `cd frontend && npx vitest run tests/unit/components/DiffRejudgeCard.spec.ts`
Expected: PASS（2 passed）

- [ ] **Step 6: 提交**

```bash
cd frontend && npx eslint src/components/batch/DiffRejudgeCard.vue src/components/batch/ReviewDrawer.vue --fix
git add src/components/batch/DiffRejudgeCard.vue src/components/batch/ReviewDrawer.vue tests/unit/components/DiffRejudgeCard.spec.ts
git commit -m "feat(batch-fe): preview drawer + node-level diff rejudge card"
```

---

## Task 6: dry-run 弹窗 + 键盘 triage

**Files:**
- Create: `frontend/src/components/batch/ApplyPreviewDialog.vue`
- Create: `frontend/src/composables/useBatchReviewShortcuts.ts`
- Test: `frontend/tests/unit/components/ApplyPreviewDialog.spec.ts`

- [ ] **Step 1: 写键盘 triage composable**

Create `frontend/src/composables/useBatchReviewShortcuts.ts`（对齐 `useEditorShortcuts`：聚焦在表单元素时不接管）:

```typescript
import { onMounted, onUnmounted } from 'vue'

interface Handlers {
  onPrev: () => void
  onNext: () => void
  onOpen: () => void
  onApply: () => void
  onSkip: () => void
}

function inEditable(el: EventTarget | null): boolean {
  const node = el as HTMLElement | null
  if (!node) return false
  const tag = node.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || node.isContentEditable
}

export function useBatchReviewShortcuts(h: Handlers): void {
  function onKey(e: KeyboardEvent): void {
    if (inEditable(e.target)) return
    switch (e.key) {
      case 'ArrowUp': case 'k': e.preventDefault(); h.onPrev(); break
      case 'ArrowDown': case 'j': e.preventDefault(); h.onNext(); break
      case 'Enter': e.preventDefault(); h.onOpen(); break
      case 'a': case 'A': e.preventDefault(); h.onApply(); break
      case 's': case 'S': e.preventDefault(); h.onSkip(); break
    }
  }
  onMounted(() => window.addEventListener('keydown', onKey))
  onUnmounted(() => window.removeEventListener('keydown', onKey))
}
```

- [ ] **Step 2: 写 dry-run 弹窗失败测试**

Create `frontend/tests/unit/components/ApplyPreviewDialog.spec.ts`:

```typescript
import { describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

import * as api from '@/api/batchImports'
import ApplyPreviewDialog from '@/components/batch/ApplyPreviewDialog.vue'

describe('ApplyPreviewDialog', () => {
  it('loads preview on open and shows counts', async () => {
    setActivePinia(createPinia())
    vi.spyOn(api, 'fetchBatchJob').mockResolvedValue({ id: 'j1' } as never)
    vi.spyOn(api, 'fetchBatchItems').mockResolvedValue([] as never)
    vi.spyOn(api, 'previewApply').mockResolvedValue({
      to_create: 12, duplicate_skip: 1, target_folder_id: 'f1',
    })
    const { useBatchReviewStore } = await import('@/store/batchReview')
    const store = useBatchReviewStore()
    store.jobId = 'j1'

    const w = mount(ApplyPreviewDialog, {
      props: { modelValue: true, itemIds: ['i1'] },
      global: { plugins: [ElementPlus] },
    })
    await flushPromises()
    expect(w.text()).toContain('12')
    expect(w.text()).toContain('1')
  })
})
```

- [ ] **Step 3: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/components/ApplyPreviewDialog.spec.ts`
Expected: FAIL — 无法解析 `@/components/batch/ApplyPreviewDialog.vue`

- [ ] **Step 4: 写 dry-run 弹窗**

Create `frontend/src/components/batch/ApplyPreviewDialog.vue`:

```vue
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useBatchReviewStore } from '@/store/batchReview'
import type { ApplyPreview } from '@/types/batchImport'

const props = defineProps<{ modelValue: boolean; itemIds: string[] | null }>()
const emit = defineEmits<{ 'update:modelValue': [boolean]; confirm: [] }>()

const store = useBatchReviewStore()
const preview = ref<ApplyPreview | null>(null)
const loading = ref(false)

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

watch(
  () => props.modelValue,
  async (open) => {
    if (open) {
      loading.value = true
      try {
        preview.value = await store.preview(props.itemIds)
      } finally {
        loading.value = false
      }
    }
  },
)
</script>

<template>
  <el-dialog v-model="visible" title="应用前确认" width="460px">
    <div v-loading="loading" v-if="preview">
      <p>将应用 <strong>{{ preview.to_create }}</strong> 份到目标文件夹</p>
      <p>· {{ preview.to_create }} 份新建程序</p>
      <p v-if="preview.duplicate_skip">· {{ preview.duplicate_skip }} 份内容重复 → 跳过</p>
    </div>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :disabled="!preview || !preview.to_create" @click="emit('confirm')">
        确认应用
      </el-button>
    </template>
  </el-dialog>
</template>
```

- [ ] **Step 5: 运行 + 全量前端测试 + 提交**

```bash
cd frontend && npx vitest run && npx vue-tsc --noEmit && npx eslint src/components/batch/ApplyPreviewDialog.vue src/composables/useBatchReviewShortcuts.ts --fix
git add src/components/batch/ApplyPreviewDialog.vue src/composables/useBatchReviewShortcuts.ts tests/unit/components/ApplyPreviewDialog.spec.ts
git commit -m "feat(batch-fe): apply-preview dialog + keyboard triage"
```

---

## 手动验证清单（需运行 dev 环境，参考 running-smartsop-dev）

- [ ] 后端起 API + scheduler 进程（`python -m app.tasks.scheduler` 跑 parse/apply tick），前端起 Vite。
- [ ] 入口触发 `BatchImportDialog` 多选 3+ 份 docx → 跳转审阅台。
- [ ] 列表按风险排序，汇总条计数随轮询实时跳动；解析完成后高置信折叠、低置信顶部。
- [ ] 低置信项开抽屉 → 改判卡"改为正文/接受"→ blob 刷新、`review_revision` 递增；并发两标签页改判触发 409 → 自动 reload。
- [ ] "全选高置信并应用" → dry-run 弹窗显示新建/重复数 → 确认 → 行变"已应用"带程序链接。
- [ ] 键盘：`j/k` 移动、`Enter` 开抽屉、`A` 应用、`S` 跳过；焦点在输入框时快捷键不接管。
- [ ] 失败项 `重试` 回排队并重新解析。

---

## Self-Review（计划作者已核对）

- **Spec 覆盖**：覆盖 spec §6.1（风险列表+汇总条+虚拟滚动）、§6.2（三路径：批量直通/抽屉速览/精审）、§6.3（节点级 diff 改判卡，已去"记住此样式"）、§6.4（dry-run 弹窗）、§6.5（轮询+应用反馈，撤销经 Plan 2 undo 端点）、§6.6 边界（高置信折叠/失败重试）、§6.7（复用 `useVirtualRows`/`buildCascadeSelection`/`isVersionConflict`，新写清单一致）。
- **方案纠偏**：勘察 agent 曾按"审阅已落库节点（复用 nodeEditor/confirmReview）"设想——本计划已纠正为**纯暂存审阅**：审阅对象是 blob，改判调 `PATCH .../review`，不触碰 `ProcedureNode`/`nodeEditor` store。
- **占位扫描**：无 TBD/TODO。`<style scoped>` 配色标注为"按既有审阅态配色补"，属样式细节非逻辑占位；`store.selectPrev/selectNext` 已在 Task 4 补定义，消除前向引用。
- **类型一致性**：`api/batchImports.ts` 导出与 store actions、组件 props/emits 跨 Task 一致；`ReviewOp` 形态与 Plan 2 后端 schema（`node_id/action/level`）一致；`BatchBlob = ParseResponse`；状态字符串与 Plan 1/2 一致。
- **依赖前提**：Plan 1/2 后端端点全部可用；复用的 `@/api/http`（`http`/`isVersionConflict`）、`@/api/parse`（`uploadDocx`）、`useVirtualRows` 均为现有。`@/types/parse` 的 `ParseResponse`/`ParsedNode` 若路径/命名不同，按现有 parse 响应类型调整 import（Task 1 已提示）。
```
