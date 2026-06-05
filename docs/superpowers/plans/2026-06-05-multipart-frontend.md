# 多备件套件前端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐 task 实现。步骤用 checkbox（`- [ ]`）跟踪。

**Goal:** 把后端在产的「多备件套件」(MultiPart) 接出前端——库存「供应」组下一个列表页:列表(可展开行看成员) + 创建/编辑对话框(多选 filterable 选成员)，纯前端、后端不动。

**Architecture:** 复刻 `PartsView.vue` 单视图模式(列表 el-table + 创建/编辑 el-dialog，无独立详情页)。新 `api/multiParts.ts` 对齐 `parts.ts`(PATCH/裸数组/204)；`MultiPartsView.vue` 用 `listPartsMini` 同时供成员下拉选项与「id→成员名」映射(展开行用)。

**Tech Stack:** Vue 3 `<script setup>` + Pinia + Element Plus + Vitest。后端端点 `/api/v1/multi-parts*` 已就绪。

设计依据：`docs/superpowers/specs/2026-06-05-multipart-frontend-design.md`。

---

## 契约（全程以此为准）

- 后端不改。端点(裸数组 + PATCH + 204，与 parts 同构)：
  - `GET /multi-parts` → `MultiPartRead[]`（无分页）
  - `POST /multi-parts` → 201 `MultiPartRead`
  - `GET /multi-parts/{id}` → `MultiPartRead`
  - `PATCH /multi-parts/{id}` → `MultiPartRead`（`part_ids` 给出即全量替换）
  - `DELETE /multi-parts/{id}` → 204
- `MultiPartRead`：`{ id, custom_id, name, description, part_ids: string[] }`。
- 权限：复用 `PART_*`（前端门控码 `part.view/create/edit/delete`）。
- 空成员套件允许(`part_ids: []`)，前端不强制至少一个成员。

## 既有代码事实（已核实，直接用）

- `src/api/parts.ts`：`http.get<T[]>('/parts',{params}).then(r=>r.data)`、`http.post<T>`、`http.patch<T>`(**PATCH 非 PUT**)、`http.delete(path).then(()=>undefined)`；`listPartsMini()`→`PartMini[]`。
- `src/types/inventory.ts`：已有 `PartMini = { id; name; custom_id }`；MultiPart 类型追加于此。
- `src/views/inventory/PartsView.vue`：单视图模板——`onMounted` 用 `Promise.all` 并行 fetch；`dialogMode:'create'|'edit'` + `editingId` + `submitting`；`reactive` form；name 空校验 `ElMessage.warning`；`handleDelete` 用 `ElMessageBox.confirm`；按钮 `v-if="auth.hasPermission('part.xxx')"`。
- `tests/unit/PartsView.spec.ts`：**真 ElementPlus plugin**(`mount(View,{ global:{plugins:[ElementPlus]}, attachTo: document.body })`)，mock api 用 `vi.hoisted`+`vi.mock`，mock `@/store/auth` 返回 `{ hasPermission: () => authState.can }`；操作对话框走真实 DOM(`document.querySelector('.el-dialog ...')`)；`afterEach` 清 `document.body.innerHTML`。
- `src/router/index.ts`：`/inventory/parts` 在 140-145，meta `{ title:'备件库存', requiresAuth:true, requiredPermission:'part.view' }`。
- `src/components/AppSidebar.vue`：「供应」组含 `{ label:'备件库存', path:'/inventory/parts', icon: Goods }`（`Goods` 已 import）。

---

## Task 1: 类型 + API 客户端

**Files:** Modify `frontend/src/types/inventory.ts`（追加）；Create `frontend/src/api/multiParts.ts`

- [ ] **Step 1: 追加类型** —— 在 `src/types/inventory.ts` 中 `PartMini` 定义之后追加：

```typescript
// 多备件套件
export interface MultiPartRead {
  id: string
  custom_id: string
  name: string
  description: string
  part_ids: string[]
}
export interface MultiPartCreate {
  name: string
  description?: string
  part_ids: string[]
}
export type MultiPartUpdate = Partial<MultiPartCreate>
```

- [ ] **Step 2: 写 API 客户端** —— 新建 `src/api/multiParts.ts`（复刻 `parts.ts` 风格，注意 PATCH）：

```typescript
import { http } from './http'
import type { MultiPartRead, MultiPartCreate, MultiPartUpdate } from '@/types/inventory'

export const listMultiParts = () =>
  http.get<MultiPartRead[]>('/multi-parts').then((r) => r.data)
export const getMultiPart = (id: string) =>
  http.get<MultiPartRead>(`/multi-parts/${id}`).then((r) => r.data)
export const createMultiPart = (p: MultiPartCreate) =>
  http.post<MultiPartRead>('/multi-parts', p).then((r) => r.data)
export const updateMultiPart = (id: string, p: MultiPartUpdate) =>
  http.patch<MultiPartRead>(`/multi-parts/${id}`, p).then((r) => r.data)
export const deleteMultiPart = (id: string) =>
  http.delete(`/multi-parts/${id}`).then(() => undefined)
```

- [ ] **Step 3: typecheck** `cd frontend && npm run typecheck` → 0 错误。
- [ ] **Step 4: Commit** `git add -A && git commit -m "feat(multipart): 类型 + API 客户端"`

---

## Task 2: MultiPartsView（列表 + 展开行 + 对话框）

**Files:** Create `frontend/src/views/inventory/MultiPartsView.vue`；Test `frontend/tests/unit/MultiPartsView.spec.ts`

- [ ] **Step 1: 写失败测试** —— 新建 `tests/unit/MultiPartsView.spec.ts`（对齐 PartsView.spec.ts 的真 EP 模式；删除用例需 partial-mock `ElMessageBox`）：

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

// 保留真实 element-plus（组件渲染要用），仅替换 ElMessageBox.confirm（删除确认）。
vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal<typeof import('element-plus')>()
  return { ...actual, ElMessageBox: { confirm: vi.fn().mockResolvedValue(undefined) } }
})

const { lmp, cmp, ump, dmp } = vi.hoisted(() => ({
  lmp: vi.fn(),
  cmp: vi.fn(),
  ump: vi.fn(),
  dmp: vi.fn(),
}))
vi.mock('@/api/multiParts', () => ({
  listMultiParts: lmp,
  getMultiPart: vi.fn(),
  createMultiPart: cmp,
  updateMultiPart: ump,
  deleteMultiPart: dmp,
}))
const { lpm } = vi.hoisted(() => ({ lpm: vi.fn() }))
vi.mock('@/api/parts', () => ({ listPartsMini: lpm }))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can, user: { role_code: 'admin' } }),
}))

import { ElMessageBox } from 'element-plus'
import MultiPartsView from '@/views/inventory/MultiPartsView.vue'

function mountView() {
  return mount(MultiPartsView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lmp.mockReset().mockResolvedValue([
    { id: 'k1', custom_id: 'KIT-001', name: '泵维修套件', description: '常用', part_ids: ['p1', 'p2'] },
  ])
  lpm.mockReset().mockResolvedValue([
    { id: 'p1', custom_id: 'P-001', name: '螺栓' },
    { id: 'p2', custom_id: 'P-002', name: '垫片' },
  ])
  cmp.mockReset().mockResolvedValue({})
  ump.mockReset().mockResolvedValue({})
  dmp.mockReset().mockResolvedValue(undefined)
  vi.mocked(ElMessageBox.confirm).mockReset().mockResolvedValue(undefined)
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('MultiPartsView', () => {
  it('加载并渲染套件 + 成员数', async () => {
    const w = mountView()
    await flushPromises()
    expect(lmp).toHaveBeenCalled()
    expect(lpm).toHaveBeenCalled()
    expect(w.text()).toContain('KIT-001')
    expect(w.text()).toContain('泵维修套件')
    expect(w.text()).toContain('2 项') // 成员数列
  })

  it('memberLabel 映射成员名，未知 id 占位', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as unknown as { memberLabel: (id: string) => string }
    expect(vm.memberLabel('p1')).toBe('P-001 螺栓')
    expect(vm.memberLabel('zzz')).toBe('(已删除)')
  })

  it('新建提交携带 name + part_ids', async () => {
    const w = mountView()
    await flushPromises()
    const addBtn = w.findAll('.el-button').find((b) => b.text() === '新建套件')
    await addBtn!.trigger('click')
    await flushPromises()
    const nameInput = document.querySelector(
      '.el-dialog input[placeholder="请输入名称"]',
    ) as HTMLInputElement
    nameInput.value = '新套件'
    nameInput.dispatchEvent(new Event('input'))
    await flushPromises()
    // 直接设置 form.part_ids（避开 el-select 下拉的 DOM 交互）
    const vm = w.vm as unknown as { form: { part_ids: string[] } }
    vm.form.part_ids = ['p1']
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cmp).toHaveBeenCalled()
    expect(cmp.mock.calls[0][0]).toMatchObject({ name: '新套件', part_ids: ['p1'] })
  })

  it('编辑回填并提交 updateMultiPart', async () => {
    const w = mountView()
    await flushPromises()
    const editBtn = w.findAll('.el-button').find((b) => b.text() === '编辑')
    await editBtn!.trigger('click')
    await flushPromises()
    const vm = w.vm as unknown as { form: { name: string; part_ids: string[] } }
    expect(vm.form.name).toBe('泵维修套件')
    expect(vm.form.part_ids).toEqual(['p1', 'p2'])
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(ump).toHaveBeenCalledWith('k1', expect.objectContaining({ name: '泵维修套件' }))
  })

  it('删除确认后调用 deleteMultiPart', async () => {
    const w = mountView()
    await flushPromises()
    const delBtn = w.findAll('.el-button').find((b) => b.text() === '删除')
    await delBtn!.trigger('click')
    await flushPromises()
    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(dmp).toHaveBeenCalledWith('k1')
  })

  it('空成员套件可提交（part_ids 为空）', async () => {
    const w = mountView()
    await flushPromises()
    const addBtn = w.findAll('.el-button').find((b) => b.text() === '新建套件')
    await addBtn!.trigger('click')
    await flushPromises()
    const nameInput = document.querySelector(
      '.el-dialog input[placeholder="请输入名称"]',
    ) as HTMLInputElement
    nameInput.value = '空套件'
    nameInput.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cmp).toHaveBeenCalled()
    expect(cmp.mock.calls[0][0]).toMatchObject({ name: '空套件', part_ids: [] })
  })

  it('无 part.create 隐藏新建按钮', async () => {
    authState.can = false
    const w = mountView()
    await flushPromises()
    expect(w.findAll('.el-button').find((b) => b.text() === '新建套件')).toBeFalsy()
  })
})
```

- [ ] **Step 2: 跑红** `cd frontend && npm run test -- MultiPartsView` → FAIL（组件不存在）。

- [ ] **Step 3: 实现 MultiPartsView** —— 新建 `src/views/inventory/MultiPartsView.vue`：

```vue
<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listMultiParts,
  createMultiPart,
  updateMultiPart,
  deleteMultiPart,
} from '@/api/multiParts'
import { listPartsMini } from '@/api/parts'
import type {
  MultiPartRead,
  MultiPartCreate,
  MultiPartUpdate,
  PartMini,
} from '@/types/inventory'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()

// ── state ──────────────────────────────────────────────────
const loading = ref(false)
const multiParts = ref<MultiPartRead[]>([])
const partsMini = ref<PartMini[]>([])

// ── fetch ──────────────────────────────────────────────────
async function fetchMultiParts() {
  loading.value = true
  try {
    multiParts.value = await listMultiParts()
  } finally {
    loading.value = false
  }
}
async function fetchPartsMini() {
  partsMini.value = await listPartsMini()
}

onMounted(async () => {
  await Promise.all([fetchMultiParts(), fetchPartsMini()])
})

// ── mapping ────────────────────────────────────────────────
const partMap = computed(() => {
  const m = new Map<string, PartMini>()
  for (const p of partsMini.value) m.set(p.id, p)
  return m
})
function memberLabel(id: string): string {
  const p = partMap.value.get(id)
  return p ? `${p.custom_id} ${p.name}` : '(已删除)'
}

// ── dialog ─────────────────────────────────────────────────
type DialogMode = 'create' | 'edit'

const dialogVisible = ref(false)
const dialogMode = ref<DialogMode>('create')
const editingId = ref<string | null>(null)
const submitting = ref(false)

interface FormState {
  name: string
  description: string
  part_ids: string[]
}
const form = reactive<FormState>({ name: '', description: '', part_ids: [] })

const dialogTitle = computed(() => (dialogMode.value === 'create' ? '新建套件' : '编辑套件'))

function resetForm() {
  form.name = ''
  form.description = ''
  form.part_ids = []
}

function openCreate() {
  resetForm()
  dialogMode.value = 'create'
  editingId.value = null
  dialogVisible.value = true
}

function openEdit(row: MultiPartRead) {
  resetForm()
  Object.assign(form, {
    name: row.name,
    description: row.description,
    part_ids: [...row.part_ids],
  })
  dialogMode.value = 'edit'
  editingId.value = row.id
  dialogVisible.value = true
}

async function submitForm() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写名称')
    return
  }
  submitting.value = true
  try {
    const payload: MultiPartCreate | MultiPartUpdate = {
      name: form.name.trim(),
      description: form.description,
      part_ids: form.part_ids,
    }
    if (dialogMode.value === 'create') {
      await createMultiPart(payload as MultiPartCreate)
      ElMessage.success('套件创建成功')
    } else {
      if (!editingId.value) return
      await updateMultiPart(editingId.value, payload)
      ElMessage.success('套件更新成功')
    }
    dialogVisible.value = false
    await fetchMultiParts()
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    submitting.value = false
  }
}

// ── delete ─────────────────────────────────────────────────
async function handleDelete(row: MultiPartRead) {
  try {
    await ElMessageBox.confirm(`确认删除套件「${row.name}」？`, '提示', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteMultiPart(row.id)
    ElMessage.success('已删除')
    await fetchMultiParts()
  } catch {
    // cancelled or error handled by interceptor
  }
}

defineExpose({ memberLabel, form })
</script>

<template>
  <div class="page">
    <h2 class="page-title">多备件套件</h2>

    <!-- toolbar -->
    <div class="toolbar">
      <el-button v-if="auth.hasPermission('part.create')" type="primary" @click="openCreate">
        新建套件
      </el-button>
    </div>

    <!-- table -->
    <el-table
      v-loading="loading"
      :data="multiParts"
      row-key="id"
      border
      style="width: 100%; margin-top: 16px"
    >
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="member-list">
            <span v-if="row.part_ids.length === 0" class="member-empty">(无成员)</span>
            <el-tag v-for="pid in row.part_ids" :key="pid" class="member-tag" type="info">
              {{ memberLabel(pid) }}
            </el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="custom_id" label="编号" min-width="120" />
      <el-table-column prop="name" label="名称" min-width="180" />
      <el-table-column prop="description" label="描述" min-width="200" />
      <el-table-column label="成员数" min-width="100" align="center">
        <template #default="{ row }">{{ row.part_ids.length }} 项</template>
      </el-table-column>
      <el-table-column label="操作" width="160" align="center" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="auth.hasPermission('part.edit')"
            link
            type="primary"
            @click="openEdit(row)"
          >
            编辑
          </el-button>
          <el-button
            v-if="auth.hasPermission('part.delete')"
            link
            type="danger"
            @click="handleDelete(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- create / edit dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="640px"
      :close-on-click-modal="false"
    >
      <el-form label-width="100px" @submit.prevent="submitForm">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="请输入名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item label="成员备件">
          <el-select
            v-model="form.part_ids"
            multiple
            filterable
            placeholder="选择成员备件"
            style="width: 100%"
          >
            <el-option
              v-for="p in partsMini"
              :key="p.id"
              :label="`${p.custom_id} ${p.name}`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm"> 保存 </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page {
  max-width: 1100px;
  padding: 20px 24px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 20px;
  color: var(--text-primary, #1a1a1a);
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.member-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 16px;
}
.member-empty {
  color: var(--text-tertiary, #909399);
  font-size: 13px;
}
</style>
```

- [ ] **Step 4: 跑绿** `npm run test -- MultiPartsView` → PASS（7 用例）。
- [ ] **Step 5: 门禁 + Commit** `npm run typecheck` + `npm run lint`（--max-warnings 0）净；`git add -A && git commit -m "feat(multipart): MultiPartsView 列表+展开行+对话框 + 测试"`

---

## Task 3: 路由 + 侧栏接线 + 全量门禁 + dev 冒烟

**Files:** Modify `frontend/src/router/index.ts`、`frontend/src/components/AppSidebar.vue`

- [ ] **Step 1: 路由** —— 在 `src/router/index.ts` 的 `/inventory/parts` 路由对象（140-145 行）之后，插入：

```typescript
  {
    path: '/inventory/multi-parts',
    name: 'inventory-multi-parts',
    component: () => import('@/views/inventory/MultiPartsView.vue'),
    meta: { title: '多备件套件', requiresAuth: true, requiredPermission: 'part.view' },
  },
```

- [ ] **Step 2: 侧栏** —— 在 `src/components/AppSidebar.vue` 「供应」组里 `{ label: '备件库存', path: '/inventory/parts', icon: Goods }` 之后插入：

```typescript
      { label: '多备件套件', path: '/inventory/multi-parts', icon: Goods },
```
> `Goods` 已在文件顶部 import，直接复用。

- [ ] **Step 3: 全量前端门禁** `cd frontend && npm run test && npm run typecheck && npm run lint`（--max-warnings 0）→ 全绿、无回归。

- [ ] **Step 4: dev 实测（视觉冒烟）** —— 前后端 dev 通常在跑（见 [[running-smartsop-dev]]，端口 8000/5173）；前端 Vite 有新路由/新文件，`navigate_page` 到 `http://localhost:5173/inventory/multi-parts`（必要时 `ignoreCache=true` reload）。用 chrome-devtools：
  1. 侧栏「供应」组应见「多备件套件」可点项。
  2. 进页面看列表渲染（若该租户无套件则空表，正常）。
  3. 点「新建套件」开对话框，填名称、在成员下拉选 1-2 个备件、保存 → 列表出现新套件、成员数正确。
  4. 展开该行看成员清单标签渲染。
  5. 截图 `.verify-screenshots/multipart-view.png`，Read 确认非空白、暗色协调。记录结论。
  > 若后端无备件数据导致成员下拉为空，先在备件库存页建 1-2 个备件再验。

- [ ] **Step 5: Commit + 汇报** `git commit -am "feat(multipart): 路由 + 侧栏接线"`；汇报新增/改动文件、前端通过数、dev 冒烟结论。

---

## Self-Review（执行后记录结论）

**Spec 覆盖**：类型/API→T1 ✓；列表+成员数+展开行→T2 ✓；多选 filterable 对话框→T2 ✓；新建/编辑/删除→T2 ✓；空成员可提交→T2 ✓；权限门控→T2 ✓；路由→T3 ✓；侧栏→T3 ✓；dev 冒烟→T3 ✓。

**执行注意**：
1. API 用 **PATCH**（`http.patch`）非 PUT；list 是裸数组非分页；delete `.then(()=>undefined)`。
2. `part_ids` 全量替换；空成员套件不强制校验，仅 name 必填。
3. 展开行成员名走 `memberLabel`（partsMini 映射），缺失成员显示「(已删除)」、空成员显示「(无成员)」。
4. 测试用真 ElementPlus plugin + partial-mock `ElMessageBox.confirm`；新建用例直接设 `vm.form.part_ids` 避开 el-select 下拉 DOM 交互。
5. 路由 meta 含 `requiredPermission:'part.view'`（对齐 parts）；侧栏复用已 import 的 `Goods` 图标。
6. 后端零改动、无迁移。
