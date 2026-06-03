# 末期① 工单管理 PC 前端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PC 端工单管理——把已就绪的工单后端变成列表 + 独立详情页(el-tabs)界面：CRUD/状态流转/指派/工时/额外成本/成本汇总/活动/SOP 挂接/执行只读/分类。

**Architecture:** Vue 3 `<script setup lang="ts">` + Element Plus + Pinia(auth RBAC) + vue-router。两路由：列表 `/maintenance/work-orders` + 详情 `/maintenance/work-orders/:id`(el-tabs:概览/工时成本/活动/执行)。复用 FE-6 的 `KpiCard`(成本汇总)。**纯前端，无后端改动、无迁移。** SOP 逐步执行填写留移动端，PC 执行 tab 只读。

**Tech Stack:** Vite + TS + Element Plus + Pinia + vue-router + vitest。门禁：`npm run typecheck`(vue-tsc) + `npm run lint`(eslint --max-warnings 0) + prettier + `npm run test`(vitest)。

**全局约定(每任务适用)：**
- 工作目录 `frontend/`；命令 `npm run ...`。分支 `feat/fe-workorders`(基于 main，spec 已提交)。
- 每任务：写测试 → 跑红 → 实现 → `npm run test` + `typecheck` + `lint` 绿 → prettier → commit。
- commit message 结尾附：`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- 仅中文、不做 i18n。RBAC：`const auth = useAuthStore()`；写动作按钮 `v-if="auth.hasPermission('<code>')"`(super_admin 通配)。
- 精确 `git add`，**勿纳入**仓库根未跟踪产物(`.claude/scheduled_tasks.lock`、`.verify-screenshots/*.png`)。
- 净室原创：复刻功能，绝不出现 "Atlas" 字样或复制其代码/文案。

**既有模式参考(须遵循)：**
- api：`src/api/requests.ts`(`http.get<T>(path,{params}).then(r=>r.data)`；delete `.then(()=>undefined)`；baseURL 含 `/api/v1`，路径写 `/work-orders`)。
- view：`src/views/maintenance/RequestsView.vue`、`src/views/inventory/PurchaseOrdersView.vue`(state 分区 + helper 函数化映射 + 单 dialog 多模式 + submitForm try/catch/finally + 本地化 `ElMessage.error('保存失败，请重试')` + `ElMessageBox.confirm` 删除 + RBAC v-if + scoped `.page/.page-title/.toolbar` + defineExpose 供测试)。
- 嵌套对话框：`src/components/inventory/PartCategoryManageDialog.vue`(props `visible` + emit `update:visible`/`changed`；`watch(visible,{immediate:true})` 拉取；提交 trim；删除 confirm)。
- 子组件对话框测试：`src/components/maintenance/MeterTriggerDialog.vue` + `tests/unit/MeterTriggerDialog.spec.ts`(props 驱动 + defineExpose + saved emit)。
- api 测试：`tests/unit/maintenanceApi.spec.ts`(`vi.hoisted` + `vi.mock('@/api/http')`)。
- view 测试：`tests/unit/PurchaseOrdersView.spec.ts`(可变 auth mock + `mount(...,{global:{plugins:[ElementPlus]},attachTo:document.body})` + flushPromises + `afterEach(()=>{document.body.innerHTML=''})` + defineExpose vm 驱动)。
- 导航：`src/components/AppSidebar.vue`(「维护」组「工单」现 `{ label:'工单', soon:true }`；`activeMenu` 多 `if startsWith` 串联)。
- 路由：`src/router/index.ts`(扁平 + `meta.requiresAuth` + `requiredPermission`；已有 `/maintenance/{requests,preventive-maintenances,meters}`)。
- 复用 api：`listAssetsMini`(`@/api/assets`)、`listLocationsMini`(`@/api/locations`)、`listUsers`(`@/api/users`)、`listTeams`(`@/api/teams`)、`listProceduresMini`(`@/api/procedures`)。`AssetMini`/`LocationMini` 在 `@/types/maindata`，`UserRead`/`TeamRead` 在 `@/types/platform`，`ProcedureMini` 在 `@/types/maintenance`。
- 工具：`src/utils/format.ts` 的 `formatDate`/`formatDateTime`(null→兜底)。
- 复用组件：`src/components/analytics/KpiCard.vue`(props `label`/`value`/`unit?`/`hint?`)。

**后端契约(已核实，types 以此为准；Decimal→`string`、int→`number`、date/datetime→`string`；baseURL 含 `/api/v1`)：**
- `WorkOrderStatus = 'OPEN'|'IN_PROGRESS'|'ON_HOLD'|'COMPLETE'|'CANCELED'`；`WorkOrderPriority = 'NONE'|'LOW'|'MEDIUM'|'HIGH'`。
- ALLOWED_TRANSITIONS：OPEN→[IN_PROGRESS,CANCELED]；IN_PROGRESS→[ON_HOLD,COMPLETE,CANCELED]；ON_HOLD→[IN_PROGRESS,CANCELED]；COMPLETE→[IN_PROGRESS]；CANCELED→[]。
- 端点(权限)：
  - `GET /work-orders`(查询 status/priority/asset_id/location_id/assignee_id/procedure_attached) `work_order.view`；`POST /work-orders` `work_order.create`；`GET/PATCH/DELETE /work-orders/{id}`(view/edit/delete)；`PUT /{id}/assignees`、`PUT /{id}/teams`、`POST /{id}/transition`、`POST /{id}/attach-procedure`、`DELETE /{id}/procedure` 均 `work_order.edit`；`GET /{id}/execution`、`GET/POST /{id}/activities` `work_order.view`。
  - labor：`GET /{id}/labor` view；`POST /{id}/labor`、`POST /{id}/labor/start`、`POST /{id}/labor/{lid}/stop`、`PATCH /{id}/labor/{lid}`、`DELETE /{id}/labor/{lid}` edit。
  - cost：`GET /{id}/additional-costs` view；`POST`/`PATCH /{cid}`/`DELETE /{cid}` edit；`GET /{id}/cost-summary` view。
  - `GET /work-order-categories` view；`POST`/`PATCH /{id}`/`DELETE /{id}` manage。`GET /time-categories`、`GET /cost-categories`(view)。
- 门控码：`work_order.view/create/edit/delete`；状态流转·指派·SOP·labor·cost = `work_order.edit`；分类 `work_order_category.view`/`work_order_category.manage`。执行 tab 只读不涉 `work_order.execute`。

---

## Task 1: 骨架(types + 4 api + 2 路由 + 导航 + 占位)

**Files:**
- Create: `src/types/workOrder.ts`
- Create: `src/api/{workOrders,workOrderCategories,timeCategories,costCategories}.ts`
- Create: `src/views/maintenance/WorkOrdersView.vue`、`src/views/maintenance/WorkOrderDetailView.vue`(占位)
- Modify: `src/router/index.ts`、`src/components/AppSidebar.vue`
- Test: `tests/unit/workOrdersApi.spec.ts`、`tests/unit/AppSidebar.spec.ts`(追加)

- [ ] **Step 1: 写失败测试 `tests/unit/workOrdersApi.spec.ts`**

```typescript
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get, post, patch, put, del } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
}))
vi.mock('@/api/http', () => ({ http: { get, post, patch, put, delete: del } }))

import {
  listWorkOrders,
  getWorkOrder,
  createWorkOrder,
  updateWorkOrder,
  deleteWorkOrder,
  setAssignees,
  setTeams,
  transitionWorkOrder,
  attachProcedure,
  detachProcedure,
  listWorkOrderActivities,
  addWorkOrderComment,
  getExecution,
  listLabor,
  createLabor,
  startTimer,
  stopTimer,
  updateLabor,
  deleteLabor,
  listAdditionalCosts,
  createAdditionalCost,
  updateAdditionalCost,
  deleteAdditionalCost,
  getCostSummary,
} from '@/api/workOrders'
import {
  listWorkOrderCategories,
  createWorkOrderCategory,
  updateWorkOrderCategory,
  deleteWorkOrderCategory,
} from '@/api/workOrderCategories'
import { listTimeCategories } from '@/api/timeCategories'
import { listCostCategories } from '@/api/costCategories'

describe('work orders api', () => {
  beforeEach(() => {
    for (const m of [get, post, patch, put, del]) m.mockReset().mockResolvedValue({ data: {} })
  })

  it('listWorkOrders GET /work-orders (no params)', async () => {
    await listWorkOrders()
    expect(get).toHaveBeenCalledWith('/work-orders', { params: {} })
  })
  it('listWorkOrders GET with filters', async () => {
    await listWorkOrders({ status: 'OPEN', assignee_id: 'u1', procedure_attached: true })
    expect(get).toHaveBeenCalledWith('/work-orders', {
      params: { status: 'OPEN', assignee_id: 'u1', procedure_attached: true },
    })
  })
  it('getWorkOrder GET /work-orders/{id}', async () => {
    await getWorkOrder('w1')
    expect(get).toHaveBeenCalledWith('/work-orders/w1')
  })
  it('createWorkOrder POST /work-orders', async () => {
    await createWorkOrder({ title: 'T' })
    expect(post).toHaveBeenCalledWith('/work-orders', { title: 'T' })
  })
  it('updateWorkOrder PATCH /work-orders/{id}', async () => {
    await updateWorkOrder('w1', { title: 'T2' })
    expect(patch).toHaveBeenCalledWith('/work-orders/w1', { title: 'T2' })
  })
  it('deleteWorkOrder DELETE /work-orders/{id}', async () => {
    await deleteWorkOrder('w1')
    expect(del).toHaveBeenCalledWith('/work-orders/w1')
  })
  it('setAssignees PUT /assignees', async () => {
    await setAssignees('w1', { user_ids: ['u1'] })
    expect(put).toHaveBeenCalledWith('/work-orders/w1/assignees', { user_ids: ['u1'] })
  })
  it('setTeams PUT /teams', async () => {
    await setTeams('w1', { team_ids: ['t1'] })
    expect(put).toHaveBeenCalledWith('/work-orders/w1/teams', { team_ids: ['t1'] })
  })
  it('transitionWorkOrder POST /transition', async () => {
    await transitionWorkOrder('w1', { to_status: 'IN_PROGRESS', note: '' })
    expect(post).toHaveBeenCalledWith('/work-orders/w1/transition', {
      to_status: 'IN_PROGRESS',
      note: '',
    })
  })
  it('attachProcedure POST /attach-procedure', async () => {
    await attachProcedure('w1', { procedure_id: 'p1' })
    expect(post).toHaveBeenCalledWith('/work-orders/w1/attach-procedure', { procedure_id: 'p1' })
  })
  it('detachProcedure DELETE /procedure', async () => {
    await detachProcedure('w1')
    expect(del).toHaveBeenCalledWith('/work-orders/w1/procedure')
  })
  it('listWorkOrderActivities GET /activities', async () => {
    await listWorkOrderActivities('w1')
    expect(get).toHaveBeenCalledWith('/work-orders/w1/activities')
  })
  it('addWorkOrderComment POST /activities', async () => {
    await addWorkOrderComment('w1', { comment: 'hi' })
    expect(post).toHaveBeenCalledWith('/work-orders/w1/activities', { comment: 'hi' })
  })
  it('getExecution GET /execution', async () => {
    await getExecution('w1')
    expect(get).toHaveBeenCalledWith('/work-orders/w1/execution')
  })
  it('listLabor GET /labor', async () => {
    await listLabor('w1')
    expect(get).toHaveBeenCalledWith('/work-orders/w1/labor')
  })
  it('createLabor POST /labor', async () => {
    await createLabor('w1', { duration_seconds: 600 })
    expect(post).toHaveBeenCalledWith('/work-orders/w1/labor', { duration_seconds: 600 })
  })
  it('startTimer POST /labor/start', async () => {
    await startTimer('w1', { user_id: 'u1' })
    expect(post).toHaveBeenCalledWith('/work-orders/w1/labor/start', { user_id: 'u1' })
  })
  it('stopTimer POST /labor/{lid}/stop', async () => {
    await stopTimer('w1', 'l1')
    expect(post).toHaveBeenCalledWith('/work-orders/w1/labor/l1/stop')
  })
  it('updateLabor PATCH /labor/{lid}', async () => {
    await updateLabor('w1', 'l1', { notes: 'x' })
    expect(patch).toHaveBeenCalledWith('/work-orders/w1/labor/l1', { notes: 'x' })
  })
  it('deleteLabor DELETE /labor/{lid}', async () => {
    await deleteLabor('w1', 'l1')
    expect(del).toHaveBeenCalledWith('/work-orders/w1/labor/l1')
  })
  it('listAdditionalCosts GET /additional-costs', async () => {
    await listAdditionalCosts('w1')
    expect(get).toHaveBeenCalledWith('/work-orders/w1/additional-costs')
  })
  it('createAdditionalCost POST /additional-costs', async () => {
    await createAdditionalCost('w1', { title: 'C', amount: '10' })
    expect(post).toHaveBeenCalledWith('/work-orders/w1/additional-costs', { title: 'C', amount: '10' })
  })
  it('updateAdditionalCost PATCH /additional-costs/{cid}', async () => {
    await updateAdditionalCost('w1', 'c1', { amount: '20' })
    expect(patch).toHaveBeenCalledWith('/work-orders/w1/additional-costs/c1', { amount: '20' })
  })
  it('deleteAdditionalCost DELETE /additional-costs/{cid}', async () => {
    await deleteAdditionalCost('w1', 'c1')
    expect(del).toHaveBeenCalledWith('/work-orders/w1/additional-costs/c1')
  })
  it('getCostSummary GET /cost-summary', async () => {
    await getCostSummary('w1')
    expect(get).toHaveBeenCalledWith('/work-orders/w1/cost-summary')
  })

  it('listWorkOrderCategories GET /work-order-categories', async () => {
    await listWorkOrderCategories()
    expect(get).toHaveBeenCalledWith('/work-order-categories')
  })
  it('createWorkOrderCategory POST', async () => {
    await createWorkOrderCategory({ name: 'C' })
    expect(post).toHaveBeenCalledWith('/work-order-categories', { name: 'C' })
  })
  it('updateWorkOrderCategory PATCH /{id}', async () => {
    await updateWorkOrderCategory('c1', { name: 'C2' })
    expect(patch).toHaveBeenCalledWith('/work-order-categories/c1', { name: 'C2' })
  })
  it('deleteWorkOrderCategory DELETE /{id}', async () => {
    await deleteWorkOrderCategory('c1')
    expect(del).toHaveBeenCalledWith('/work-order-categories/c1')
  })
  it('listTimeCategories GET /time-categories', async () => {
    await listTimeCategories()
    expect(get).toHaveBeenCalledWith('/time-categories')
  })
  it('listCostCategories GET /cost-categories', async () => {
    await listCostCategories()
    expect(get).toHaveBeenCalledWith('/cost-categories')
  })
})
```

- [ ] **Step 2: 跑红** `cd frontend && npm run test -- workOrdersApi` → FAIL。

- [ ] **Step 3: types `src/types/workOrder.ts`**

```typescript
export type WorkOrderStatus = 'OPEN' | 'IN_PROGRESS' | 'ON_HOLD' | 'COMPLETE' | 'CANCELED'
export type WorkOrderPriority = 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH'

export interface WorkOrderRead {
  id: string
  custom_id: string
  title: string
  description: string
  status: WorkOrderStatus
  priority: WorkOrderPriority
  due_date: string | null
  asset_id: string | null
  location_id: string | null
  primary_user_id: string | null
  procedure_id: string | null
  procedure_group_id: string | null
  completed_at: string | null
  category_id: string | null
  created_by_user_id: string | null
  assignee_ids: string[]
  team_ids: string[]
}
export interface WorkOrderCreate {
  title: string
  description?: string
  priority?: WorkOrderPriority
  due_date?: string | null
  asset_id?: string | null
  location_id?: string | null
  primary_user_id?: string | null
  assignee_ids?: string[]
  team_ids?: string[]
  category_id?: string | null
  procedure_id?: string | null
}
export interface WorkOrderUpdate {
  title?: string
  description?: string
  priority?: WorkOrderPriority
  due_date?: string | null
  asset_id?: string | null
  location_id?: string | null
  primary_user_id?: string | null
  category_id?: string | null
}
export interface WorkOrderTransition {
  to_status: WorkOrderStatus
  note?: string
}
export interface AssigneesSet {
  user_ids: string[]
}
export interface TeamsSet {
  team_ids: string[]
}

export interface WorkOrderActivityRead {
  id: string
  activity_type: string
  actor_user_id: string | null
  from_status: string | null
  to_status: string | null
  comment: string
  created_at: string
}
export interface WorkOrderCommentCreate {
  comment: string
}

export interface TimeCategoryRead {
  id: string
  name: string
  hourly_rate: string
  description: string
}
export interface CostCategoryRead {
  id: string
  name: string
  description: string
}

export interface LaborRead {
  id: string
  work_order_id: string
  user_id: string | null
  time_category_id: string | null
  started_at: string | null
  stopped_at: string | null
  duration_seconds: number
  hourly_rate: string
  notes: string
  running: boolean
  cost: string
  running_elapsed_seconds: number | null
}
export interface LaborCreate {
  duration_seconds: number
  time_category_id?: string | null
  hourly_rate?: string | null
  user_id?: string | null
  started_at?: string | null
  stopped_at?: string | null
  notes?: string
}
export interface LaborTimerStart {
  time_category_id?: string | null
  hourly_rate?: string | null
  user_id?: string | null
  notes?: string
}
export interface LaborUpdate {
  duration_seconds?: number
  time_category_id?: string | null
  hourly_rate?: string | null
  user_id?: string | null
  notes?: string
}

export interface AdditionalCostRead {
  id: string
  work_order_id: string
  cost_category_id: string | null
  title: string
  amount: string
  description: string
  created_by_user_id: string | null
}
export interface AdditionalCostCreate {
  title: string
  amount: string
  cost_category_id?: string | null
  description?: string
}
export interface AdditionalCostUpdate {
  title?: string
  amount?: string
  cost_category_id?: string | null
  description?: string
}

export interface CostSummaryRead {
  labor_total: string
  additional_total: string
  parts_total: string
  total: string
}

export interface OutlineNode {
  node_id: string
  heading_level: number | null
  kind: string
  body: string
  code: string
  sort_order: number
}
export interface StepResultRead {
  id: string
  node_id: string
  node_code: string
  node_sort_order: number
  input_schema: Record<string, unknown>
  response: Record<string, unknown>
  is_done: boolean
  done_by_user_id: string | null
  done_at: string | null
  notes: string
}
export interface ProcedureRef {
  id: string
  group_id: string | null
  code: string
  name: string
  version: number
}
export interface ExecutionView {
  procedure: ProcedureRef | null
  outline: OutlineNode[]
  steps: StepResultRead[]
}

export interface WorkOrderCategoryRead {
  id: string
  name: string
  description: string
}
export interface WorkOrderCategoryCreate {
  name: string
  description?: string
}
export type WorkOrderCategoryUpdate = Partial<WorkOrderCategoryCreate>
```

- [ ] **Step 4: api 客户端**

`src/api/workOrders.ts`：
```typescript
import { http } from './http'
import type {
  WorkOrderRead,
  WorkOrderCreate,
  WorkOrderUpdate,
  WorkOrderStatus,
  WorkOrderPriority,
  WorkOrderTransition,
  AssigneesSet,
  TeamsSet,
  WorkOrderActivityRead,
  WorkOrderCommentCreate,
  ExecutionView,
  LaborRead,
  LaborCreate,
  LaborTimerStart,
  LaborUpdate,
  AdditionalCostRead,
  AdditionalCostCreate,
  AdditionalCostUpdate,
  CostSummaryRead,
} from '@/types/workOrder'

export interface ListWorkOrdersParams {
  status?: WorkOrderStatus
  priority?: WorkOrderPriority
  asset_id?: string
  location_id?: string
  assignee_id?: string
  procedure_attached?: boolean
}

export const listWorkOrders = (params: ListWorkOrdersParams = {}) =>
  http.get<WorkOrderRead[]>('/work-orders', { params }).then((r) => r.data)
export const getWorkOrder = (id: string) =>
  http.get<WorkOrderRead>(`/work-orders/${id}`).then((r) => r.data)
export const createWorkOrder = (p: WorkOrderCreate) =>
  http.post<WorkOrderRead>('/work-orders', p).then((r) => r.data)
export const updateWorkOrder = (id: string, p: WorkOrderUpdate) =>
  http.patch<WorkOrderRead>(`/work-orders/${id}`, p).then((r) => r.data)
export const deleteWorkOrder = (id: string) =>
  http.delete(`/work-orders/${id}`).then(() => undefined)
export const setAssignees = (id: string, p: AssigneesSet) =>
  http.put<WorkOrderRead>(`/work-orders/${id}/assignees`, p).then((r) => r.data)
export const setTeams = (id: string, p: TeamsSet) =>
  http.put<WorkOrderRead>(`/work-orders/${id}/teams`, p).then((r) => r.data)
export const transitionWorkOrder = (id: string, p: WorkOrderTransition) =>
  http.post<WorkOrderRead>(`/work-orders/${id}/transition`, p).then((r) => r.data)
export const attachProcedure = (id: string, p: { procedure_id: string }) =>
  http.post<WorkOrderRead>(`/work-orders/${id}/attach-procedure`, p).then((r) => r.data)
export const detachProcedure = (id: string) =>
  http.delete<WorkOrderRead>(`/work-orders/${id}/procedure`).then((r) => r.data)
export const listWorkOrderActivities = (id: string) =>
  http.get<WorkOrderActivityRead[]>(`/work-orders/${id}/activities`).then((r) => r.data)
export const addWorkOrderComment = (id: string, p: WorkOrderCommentCreate) =>
  http.post<WorkOrderActivityRead>(`/work-orders/${id}/activities`, p).then((r) => r.data)
export const getExecution = (id: string) =>
  http.get<ExecutionView>(`/work-orders/${id}/execution`).then((r) => r.data)

export const listLabor = (id: string) =>
  http.get<LaborRead[]>(`/work-orders/${id}/labor`).then((r) => r.data)
export const createLabor = (id: string, p: LaborCreate) =>
  http.post<LaborRead>(`/work-orders/${id}/labor`, p).then((r) => r.data)
export const startTimer = (id: string, p: LaborTimerStart = {}) =>
  http.post<LaborRead>(`/work-orders/${id}/labor/start`, p).then((r) => r.data)
export const stopTimer = (id: string, laborId: string) =>
  http.post<LaborRead>(`/work-orders/${id}/labor/${laborId}/stop`).then((r) => r.data)
export const updateLabor = (id: string, laborId: string, p: LaborUpdate) =>
  http.patch<LaborRead>(`/work-orders/${id}/labor/${laborId}`, p).then((r) => r.data)
export const deleteLabor = (id: string, laborId: string) =>
  http.delete(`/work-orders/${id}/labor/${laborId}`).then(() => undefined)

export const listAdditionalCosts = (id: string) =>
  http.get<AdditionalCostRead[]>(`/work-orders/${id}/additional-costs`).then((r) => r.data)
export const createAdditionalCost = (id: string, p: AdditionalCostCreate) =>
  http.post<AdditionalCostRead>(`/work-orders/${id}/additional-costs`, p).then((r) => r.data)
export const updateAdditionalCost = (id: string, costId: string, p: AdditionalCostUpdate) =>
  http.patch<AdditionalCostRead>(`/work-orders/${id}/additional-costs/${costId}`, p).then((r) => r.data)
export const deleteAdditionalCost = (id: string, costId: string) =>
  http.delete(`/work-orders/${id}/additional-costs/${costId}`).then(() => undefined)
export const getCostSummary = (id: string) =>
  http.get<CostSummaryRead>(`/work-orders/${id}/cost-summary`).then((r) => r.data)
```
> 注：`stopTimer` 测试断言 `post` 仅以 path 调用(无 body)；其余带 body。

`src/api/workOrderCategories.ts`：
```typescript
import { http } from './http'
import type {
  WorkOrderCategoryRead,
  WorkOrderCategoryCreate,
  WorkOrderCategoryUpdate,
} from '@/types/workOrder'

export const listWorkOrderCategories = () =>
  http.get<WorkOrderCategoryRead[]>('/work-order-categories').then((r) => r.data)
export const createWorkOrderCategory = (p: WorkOrderCategoryCreate) =>
  http.post<WorkOrderCategoryRead>('/work-order-categories', p).then((r) => r.data)
export const updateWorkOrderCategory = (id: string, p: WorkOrderCategoryUpdate) =>
  http.patch<WorkOrderCategoryRead>(`/work-order-categories/${id}`, p).then((r) => r.data)
export const deleteWorkOrderCategory = (id: string) =>
  http.delete(`/work-order-categories/${id}`).then(() => undefined)
```

`src/api/timeCategories.ts`：
```typescript
import { http } from './http'
import type { TimeCategoryRead } from '@/types/workOrder'

export const listTimeCategories = () =>
  http.get<TimeCategoryRead[]>('/time-categories').then((r) => r.data)
```

`src/api/costCategories.ts`：
```typescript
import { http } from './http'
import type { CostCategoryRead } from '@/types/workOrder'

export const listCostCategories = () =>
  http.get<CostCategoryRead[]>('/cost-categories').then((r) => r.data)
```

- [ ] **Step 5: 占位视图**

`src/views/maintenance/WorkOrdersView.vue`：
```vue
<script setup lang="ts"></script>
<template><div class="page">工单</div></template>
```
`src/views/maintenance/WorkOrderDetailView.vue`：
```vue
<script setup lang="ts"></script>
<template><div class="page">工单详情</div></template>
```

- [ ] **Step 6: 路由 `src/router/index.ts` 加 2 条**

先 Read 现有 `/maintenance/*` 路由块，仿照在其后加入：
```typescript
  {
    path: '/maintenance/work-orders',
    name: 'maintenance-work-orders',
    component: () => import('@/views/maintenance/WorkOrdersView.vue'),
    meta: { title: '工单', requiresAuth: true, requiredPermission: 'work_order.view' },
  },
  {
    path: '/maintenance/work-orders/:id',
    name: 'maintenance-work-order-detail',
    component: () => import('@/views/maintenance/WorkOrderDetailView.vue'),
    meta: { title: '工单详情', requiresAuth: true, requiredPermission: 'work_order.view' },
  },
```

- [ ] **Step 7: 导航 `src/components/AppSidebar.vue`**

先 Read。「维护」组「工单」项由 `{ label: '工单', soon: true }` 改为：
```typescript
      { label: '工单', path: '/maintenance/work-orders' },
```
`activeMenu` computed：现有 `if (route.path.startsWith('/maintenance/')) return route.path` 已覆盖详情页路径——但详情页 `/maintenance/work-orders/:id` 会返回完整含 id 的 path，导致菜单项(index `/maintenance/work-orders`)不高亮。**修正**：在 `/maintenance/` 分支前加一条 `if (route.path.startsWith('/maintenance/work-orders')) return '/maintenance/work-orders'`（列表与详情都高亮「工单」项）。

`tests/unit/AppSidebar.spec.ts`：先 Read，追加断言——「维护」组「工单」有 path `/maintenance/work-orders`、无 soon；`activeMenu` 对 `/maintenance/work-orders/abc`(详情)返回 `/maintenance/work-orders`。既有断言不破。

- [ ] **Step 8: 跑绿 + 门禁**

Run: `cd frontend && npm run test && npm run typecheck && npm run lint`
Expected: PASS / 0 errors / 0 warnings。
prettier：`npx prettier --write "src/types/workOrder.ts" "src/api/workOrders.ts" "src/api/workOrderCategories.ts" "src/api/timeCategories.ts" "src/api/costCategories.ts" "src/views/maintenance/WorkOrdersView.vue" "src/views/maintenance/WorkOrderDetailView.vue" "tests/unit/workOrdersApi.spec.ts" "src/router/index.ts" "src/components/AppSidebar.vue" "tests/unit/AppSidebar.spec.ts"`

- [ ] **Step 9: commit**

```bash
git add src/types/workOrder.ts src/api/workOrders.ts src/api/workOrderCategories.ts src/api/timeCategories.ts src/api/costCategories.ts src/views/maintenance/WorkOrdersView.vue src/views/maintenance/WorkOrderDetailView.vue src/router/index.ts src/components/AppSidebar.vue tests/unit/workOrdersApi.spec.ts tests/unit/AppSidebar.spec.ts
git commit -m "feat(fe-workorders): api clients + types + routes + sidebar + placeholders

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: 列表 View(过滤 + 新建/编辑对话框 + 删除 + 跳详情)

**Files:**
- Create: `src/components/workorder/WorkOrderFormDialog.vue`、`src/views/maintenance/WorkOrdersView.vue`(覆盖占位)
- Test: `tests/unit/WorkOrderFormDialog.spec.ts`、`tests/unit/WorkOrdersView.spec.ts`

### 2A WorkOrderFormDialog

- [ ] **Step 1: 写失败测试 `tests/unit/WorkOrderFormDialog.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { cw, uw } = vi.hoisted(() => ({ cw: vi.fn(), uw: vi.fn() }))
vi.mock('@/api/workOrders', () => ({ createWorkOrder: cw, updateWorkOrder: uw }))
vi.mock('@/api/assets', () => ({ listAssetsMini: vi.fn().mockResolvedValue([{ id: 'a1', name: '泵' }]) }))
vi.mock('@/api/locations', () => ({ listLocationsMini: vi.fn().mockResolvedValue([{ id: 'l1', name: '车间' }]) }))
vi.mock('@/api/users', () => ({ listUsers: vi.fn().mockResolvedValue([{ id: 'u1', name: '张三' }]) }))
vi.mock('@/api/teams', () => ({ listTeams: vi.fn().mockResolvedValue([{ id: 't1', name: '机修组' }]) }))
vi.mock('@/api/procedures', () => ({ listProceduresMini: vi.fn().mockResolvedValue([{ id: 'pr1', name: '保养SOP' }]) }))
vi.mock('@/api/workOrderCategories', () => ({ listWorkOrderCategories: vi.fn().mockResolvedValue([{ id: 'c1', name: '常规' }]) }))

import WorkOrderFormDialog from '@/components/workorder/WorkOrderFormDialog.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  cw.mockReset().mockResolvedValue({ id: 'w9' })
  uw.mockReset().mockResolvedValue({})
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('WorkOrderFormDialog', () => {
  it('create 提交调 createWorkOrder 带 title + emit saved', async () => {
    const w = mount(WorkOrderFormDialog, {
      props: { visible: true, mode: 'create', editing: null },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    const vm = w.vm as any
    vm.form.title = '泵检修'
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cw).toHaveBeenCalled()
    expect(cw.mock.calls[0][0]).toMatchObject({ title: '泵检修' })
    expect(w.emitted('saved')).toBeTruthy()
  })

  it('edit 提交调 updateWorkOrder(id, 基本字段)', async () => {
    const editing = {
      id: 'w1',
      custom_id: 'WO-001',
      title: '原标题',
      description: '',
      status: 'OPEN',
      priority: 'HIGH',
      due_date: null,
      asset_id: null,
      location_id: null,
      primary_user_id: null,
      procedure_id: null,
      procedure_group_id: null,
      completed_at: null,
      category_id: null,
      created_by_user_id: null,
      assignee_ids: [],
      team_ids: [],
    }
    const w = mount(WorkOrderFormDialog, {
      props: { visible: true, mode: 'edit', editing },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    const vm = w.vm as any
    vm.form.title = '新标题'
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(uw).toHaveBeenCalled()
    expect(uw.mock.calls[0][0]).toBe('w1')
    expect(uw.mock.calls[0][1]).toMatchObject({ title: '新标题' })
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- WorkOrderFormDialog` → FAIL。

- [ ] **Step 3: 实现 `src/components/workorder/WorkOrderFormDialog.vue`**

`<script setup lang="ts">`：
- props：`visible: boolean`、`mode: 'create' | 'edit'`、`editing: WorkOrderRead | null`。emits：`update:visible`、`saved`。
- import：`createWorkOrder`/`updateWorkOrder`、`listAssetsMini`/`listLocationsMini`/`listUsers`/`listTeams`/`listProceduresMini`、`listWorkOrderCategories`、`useAuthStore` 不需(对话框已由入口门控)、`ElMessage`、types。
- 常量 `PRIORITY_OPTIONS`(NONE/LOW/MEDIUM/HIGH → 无/低/中/高)。
- state：`assetsMini`/`locationsMini`/`users`/`teams`/`procedures`/`categories`(ref [])、`submitting`、`form = reactive<{title,description,priority,due_date,asset_id,location_id,primary_user_id,assignee_ids,team_ids,category_id,procedure_id}>`(priority 'NONE'，due_date/asset/location/primary/category/procedure null，描述 ''，数组 [])。
- `watch(() => props.visible, (v) => { if (v) { fetchOptions(); resetOrFill() } }, { immediate: true })`：打开时并行拉下拉源 + 按 editing 回填/重置。
  - `resetOrFill`：create→重置默认；edit→回填基本字段（title/description/priority/due_date/asset_id/location_id/primary_user_id/category_id；assignee/team/procedure 在 edit 模式不在此对话框改——edit 模式隐藏指派/SOP 字段，仅基本信息）。
- 模板 `el-dialog :model-value="visible" @update:model-value="(v)=>emit('update:visible',v)" :title="mode==='create' ? '新建工单' : '编辑工单'" width="640px"` 内 `el-form`：
  - 标题(必填 placeholder「请输入标题」)、描述(textarea)、优先级(`el-select` PRIORITY_OPTIONS)、到期日(`el-date-picker type="date" value-format="YYYY-MM-DD"`)、资产(`el-select clearable` assetsMini)、位置(同 locationsMini)、分类(`el-select clearable` categories)、负责人(`el-select clearable filterable` users)。
  - **仅 create 模式**额外：指派用户(`el-select multiple filterable` users)、指派团队(`el-select multiple` teams)、关联 SOP(`el-select clearable filterable` procedures)。（edit 不含这三项——后端 Update 不接受。）
  - footer：「保存」→ submitForm、「取消」→ emit update:visible false。
- `submitForm`：校验 `form.title.trim()`(空→`ElMessage.warning('请填写标题')` 返回)；
  - create payload `{ title: trim, description, priority, due_date: form.due_date||null, asset_id: form.asset_id||null, location_id: form.location_id||null, primary_user_id: form.primary_user_id||null, category_id: form.category_id||null, assignee_ids: form.assignee_ids, team_ids: form.team_ids, procedure_id: form.procedure_id||null }` → `createWorkOrder`。
  - edit payload(仅 WorkOrderUpdate 字段) `{ title: trim, description, priority, due_date: form.due_date||null, asset_id, location_id, primary_user_id, category_id }`(各 `||null`) → `updateWorkOrder(props.editing!.id, payload)`。
  - 成功 `ElMessage.success('保存成功')` + `emit('saved', <返回的 WorkOrderRead 或 id>)` + `emit('update:visible', false)`；try/catch 本地化 `ElMessage.error('保存失败，请重试')`，finally submitting=false。
- `defineExpose({ form, submitForm })`。

### 2B WorkOrdersView

- [ ] **Step 4: 写失败测试 `tests/unit/WorkOrdersView.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const push = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))

const { lw, dw } = vi.hoisted(() => ({ lw: vi.fn(), dw: vi.fn() }))
vi.mock('@/api/workOrders', () => ({ listWorkOrders: lw, deleteWorkOrder: dw }))
vi.mock('@/api/assets', () => ({ listAssetsMini: vi.fn().mockResolvedValue([{ id: 'a1', name: '泵' }]) }))
vi.mock('@/api/locations', () => ({ listLocationsMini: vi.fn().mockResolvedValue([{ id: 'l1', name: '车间' }]) }))
vi.mock('@/api/users', () => ({ listUsers: vi.fn().mockResolvedValue([{ id: 'u1', name: '张三' }]) }))
// FormDialog 与 category 对话框 stub，避免其内部 onMounted 拉取
vi.mock('@/components/workorder/WorkOrderFormDialog.vue', () => ({
  default: { name: 'WorkOrderFormDialog', props: ['visible', 'mode', 'editing'], emits: ['update:visible', 'saved'], template: '<div class="form-dialog-stub" />' },
}))
vi.mock('@/components/maintenance/WorkOrderCategoryManageDialog.vue', () => ({
  default: { name: 'WorkOrderCategoryManageDialog', props: ['visible'], emits: ['update:visible', 'changed'], template: '<div class="cat-dialog-stub" />' },
}))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can, user: { role_code: 'admin' } }),
}))

import WorkOrdersView from '@/views/maintenance/WorkOrdersView.vue'

function mountView() {
  return mount(WorkOrdersView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

const wo = {
  id: 'w1',
  custom_id: 'WO-001',
  title: '泵检修',
  description: '',
  status: 'IN_PROGRESS',
  priority: 'HIGH',
  due_date: null,
  asset_id: 'a1',
  location_id: 'l1',
  primary_user_id: 'u1',
  procedure_id: null,
  procedure_group_id: null,
  completed_at: null,
  category_id: null,
  created_by_user_id: null,
  assignee_ids: [],
  team_ids: [],
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  push.mockReset()
  lw.mockReset().mockResolvedValue([wo])
  dw.mockReset().mockResolvedValue(undefined)
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('WorkOrdersView', () => {
  it('加载并渲染工单 + 状态中文 + 资产/负责人名', async () => {
    const w = mountView()
    await flushPromises()
    expect(lw).toHaveBeenCalled()
    expect(w.text()).toContain('WO-001')
    expect(w.text()).toContain('泵检修')
    expect(w.text()).toContain('进行中')
    expect(w.text()).toContain('泵')
    expect(w.text()).toContain('张三')
  })

  it('点详情跳路由', async () => {
    const w = mountView()
    await flushPromises()
    const detailBtn = w.findAll('.el-button').find((b) => b.text() === '详情')
    await detailBtn!.trigger('click')
    expect(push).toHaveBeenCalledWith('/maintenance/work-orders/w1')
  })

  it('删除经确认调 deleteWorkOrder', async () => {
    const { ElMessageBox } = await import('element-plus')
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    const w = mountView()
    await flushPromises()
    const delBtn = w.findAll('.el-button').find((b) => b.text() === '删除')
    await delBtn!.trigger('click')
    await flushPromises()
    expect(dw).toHaveBeenCalledWith('w1')
  })

  it('无权限隐藏新建工单按钮', async () => {
    authState.can = false
    const w = mountView()
    await flushPromises()
    expect(w.findAll('.el-button').find((b) => b.text() === '新建工单')).toBeFalsy()
  })
})
```

- [ ] **Step 5: 跑红** `npm run test -- WorkOrdersView` → FAIL。

- [ ] **Step 6: 实现 `WorkOrdersView.vue`**

仿 `RequestsView.vue`，delta：
- import：`useRouter`(vue-router)、`listWorkOrders`/`deleteWorkOrder`、`listAssetsMini`/`listLocationsMini`/`listUsers`、`WorkOrderFormDialog`、`WorkOrderCategoryManageDialog`、`useAuthStore`、`formatDate`、types、`ElMessage`/`ElMessageBox`。
- 常量：`WO_STATUS_LABELS`/`WO_STATUS_TAG`/`PRIORITY_LABELS`(见 spec)；helper `statusLabel`/`statusTag`/`priorityLabel`(类型化函数避免模板内索引 Record)。
- state：`workOrders = ref<WorkOrderRead[]>([])`、`assetsMini`/`locationsMini`/`users`、`loading`；过滤 `filterStatus`/`filterPriority`/`filterAsset`/`filterLocation`/`filterAssignee`(ref '')、`filterProcedure = ref<'' | 'true' | 'false'>('')`；dialog `formVisible`/`formMode`/`editingWO = ref<WorkOrderRead | null>(null)`；`categoryDialogVisible`。
- `const router = useRouter()`。映射 `assetName`/`locationName`/`userName`。
- `fetchWorkOrders`：params 仅非空键（filterProcedure 转 boolean：`if (filterProcedure.value) params.procedure_attached = filterProcedure.value === 'true'`）。onMounted 并行 `Promise.all([fetch, fetchAssetsMini, fetchLocationsMini, fetchUsers])`。过滤 `@change="fetchWorkOrders"`。
- 列表列：编号、标题、状态(`<el-tag :type="statusTag(row.status)">{{ statusLabel(row.status) }}</el-tag>`)、优先级(`priorityLabel`)、资产、位置、负责人(`userName(row.primary_user_id)`)、到期(`row.due_date ? formatDate : '—'`)、操作(「详情」→ `goDetail(row)`、「删除」`work_order.delete`)。
- 顶部：「新建工单」`work_order.create` → `openCreate`、「管理分类」`work_order_category.view` → categoryDialogVisible=true、过滤器若干。
- `goDetail(row)`：`router.push('/maintenance/work-orders/' + row.id)`。
- `openCreate`：`editingWO=null; formMode='create'; formVisible=true`。
- `handleDelete(row)`：`ElMessageBox.confirm('确认删除工单「'+row.custom_id+'」？','提示',{type:'warning'})` → `deleteWorkOrder(row.id)` → success + fetch；catch 静默。
- 内嵌 `<WorkOrderFormDialog v-model:visible="formVisible" :mode="formMode" :editing="editingWO" @saved="fetchWorkOrders" />` + `<WorkOrderCategoryManageDialog v-model:visible="categoryDialogVisible" />`。
- `defineExpose({ openCreate, goDetail, handleDelete })`。
- 模板根 `.page` + page-title + toolbar，scoped 样式仿 RequestsView。
- **前向依赖处理**：WorkOrdersView import 了 `@/components/maintenance/WorkOrderCategoryManageDialog.vue`，但该组件 T7 才实现。**本任务先创建其最小占位**避免 typecheck 失败：`src/components/maintenance/WorkOrderCategoryManageDialog.vue` 内容 `<script setup lang="ts">defineProps<{ visible: boolean }>(); defineEmits<{ 'update:visible': [boolean]; changed: [] }>()</script><template><div /></template>`（T7 覆盖为真实实现）。本任务 git add 须含此占位文件。

- [ ] **Step 7: 跑绿 + 门禁** `npm run test -- WorkOrderFormDialog WorkOrdersView && npm run test && npm run typecheck && npm run lint`。`npx prettier --write "src/components/workorder/WorkOrderFormDialog.vue" "src/views/maintenance/WorkOrdersView.vue" "tests/unit/WorkOrderFormDialog.spec.ts" "tests/unit/WorkOrdersView.spec.ts"`。

- [ ] **Step 8: commit**
```bash
git add src/components/workorder/WorkOrderFormDialog.vue src/views/maintenance/WorkOrdersView.vue src/components/maintenance/WorkOrderCategoryManageDialog.vue tests/unit/WorkOrderFormDialog.spec.ts tests/unit/WorkOrdersView.spec.ts
git commit -m "feat(fe-workorders): work orders list view + form dialog

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 详情壳 + 状态流转 + 概览 tab

**Files:**
- Create: `src/components/workorder/OverviewTab.vue`、`src/views/maintenance/WorkOrderDetailView.vue`(覆盖占位)
- Test: `tests/unit/WorkOrderDetailView.spec.ts`、`tests/unit/OverviewTab.spec.ts`

- [ ] **Step 1: 写失败测试 `tests/unit/WorkOrderDetailView.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const push = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
  useRoute: () => ({ params: { id: 'w1' } }),
}))

const { gw, tr } = vi.hoisted(() => ({ gw: vi.fn(), tr: vi.fn() }))
vi.mock('@/api/workOrders', () => ({ getWorkOrder: gw, transitionWorkOrder: tr }))
// 各 tab stub，隔离详情壳测试
vi.mock('@/components/workorder/OverviewTab.vue', () => ({
  default: { name: 'OverviewTab', props: ['workOrder'], emits: ['changed'], template: '<div class="overview-stub" />' },
}))
vi.mock('@/components/workorder/LaborCostTab.vue', () => ({
  default: { name: 'LaborCostTab', props: ['workOrderId'], template: '<div class="laborcost-stub" />' },
}))
vi.mock('@/components/workorder/ActivityTab.vue', () => ({
  default: { name: 'ActivityTab', props: ['workOrderId'], template: '<div class="activity-stub" />' },
}))
vi.mock('@/components/workorder/ExecutionTab.vue', () => ({
  default: { name: 'ExecutionTab', props: ['workOrderId'], template: '<div class="execution-stub" />' },
}))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can, user: { role_code: 'admin' } }),
}))

import WorkOrderDetailView from '@/views/maintenance/WorkOrderDetailView.vue'

function mountView() {
  return mount(WorkOrderDetailView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

const wo = {
  id: 'w1',
  custom_id: 'WO-001',
  title: '泵检修',
  description: '',
  status: 'OPEN',
  priority: 'HIGH',
  due_date: null,
  asset_id: null,
  location_id: null,
  primary_user_id: null,
  procedure_id: null,
  procedure_group_id: null,
  completed_at: null,
  category_id: null,
  created_by_user_id: null,
  assignee_ids: [],
  team_ids: [],
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  push.mockReset()
  gw.mockReset().mockResolvedValue(wo)
  tr.mockReset().mockResolvedValue({ ...wo, status: 'IN_PROGRESS' })
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('WorkOrderDetailView', () => {
  it('加载工单 + 渲染编号标题状态', async () => {
    const w = mountView()
    await flushPromises()
    expect(gw).toHaveBeenCalledWith('w1')
    expect(w.text()).toContain('WO-001')
    expect(w.text()).toContain('泵检修')
    expect(w.text()).toContain('待处理') // OPEN
  })

  it('OPEN 显示「开始」「取消」流转按钮，点「开始」调 transition(IN_PROGRESS)', async () => {
    const w = mountView()
    await flushPromises()
    const startBtn = w.findAll('.el-button').find((b) => b.text() === '开始')
    expect(startBtn).toBeTruthy()
    expect(w.findAll('.el-button').find((b) => b.text() === '取消')).toBeTruthy()
    await startBtn!.trigger('click')
    await flushPromises()
    expect(tr).toHaveBeenCalled()
    expect(tr.mock.calls[0][0]).toBe('w1')
    expect(tr.mock.calls[0][1]).toMatchObject({ to_status: 'IN_PROGRESS' })
  })

  it('无 edit 权限时不显示流转按钮', async () => {
    authState.can = false
    const w = mountView()
    await flushPromises()
    expect(w.findAll('.el-button').find((b) => b.text() === '开始')).toBeFalsy()
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- WorkOrderDetailView` → FAIL。

- [ ] **Step 3: 实现 `WorkOrderDetailView.vue`**

`<script setup lang="ts">`：
- import：`useRoute`/`useRouter`、`getWorkOrder`/`transitionWorkOrder`、`OverviewTab`/`LaborCostTab`/`ActivityTab`/`ExecutionTab`、`useAuthStore`、`ElMessage`/`ElMessageBox`、types。
- 常量 `WO_STATUS_LABELS`/`WO_STATUS_TAG`；**流转表**：
  ```typescript
  const TRANSITIONS: Record<WorkOrderStatus, { to: WorkOrderStatus; label: string }[]> = {
    OPEN: [{ to: 'IN_PROGRESS', label: '开始' }, { to: 'CANCELED', label: '取消' }],
    IN_PROGRESS: [{ to: 'ON_HOLD', label: '挂起' }, { to: 'COMPLETE', label: '完成' }, { to: 'CANCELED', label: '取消' }],
    ON_HOLD: [{ to: 'IN_PROGRESS', label: '恢复' }, { to: 'CANCELED', label: '取消' }],
    COMPLETE: [{ to: 'IN_PROGRESS', label: '重开' }],
    CANCELED: [],
  }
  ```
- state：`route=useRoute()`、`router=useRouter()`、`woId = route.params.id as string`、`wo = ref<WorkOrderRead | null>(null)`、`loading`、`activeTab = ref('overview')`、`auth=useAuthStore()`。
- `transitions = computed(() => (wo.value ? TRANSITIONS[wo.value.status] : []))`。
- `load = async () => { loading=true; try { wo.value = await getWorkOrder(woId) } catch { ElMessage.error('加载工单失败，请重试'); router.push('/maintenance/work-orders') } finally { loading=false } }`。`onMounted(load)`。
- `doTransition(t)`：对「完成」「取消」先 `ElMessageBox.confirm`（完成「确认标记完成？若有未完成步骤将被后端拒绝」/取消「确认取消该工单？」），其它直接；`try { wo.value = await transitionWorkOrder(woId, { to_status: t.to, note: '' }); ElMessage.success('操作成功') } catch { ElMessage.error('操作失败，请重试') }`。confirm 取消（reject）走 `.catch` 提前 return。
  - > 简化以利测试：「开始/恢复/重开/挂起」无 confirm 直接 transition；「完成/取消」加 confirm。测试点「开始」无 confirm 直接调 tr。
- 页头模板：返回按钮(`router.push('/maintenance/work-orders')`)、`{{ wo.custom_id }} {{ wo.title }}`、状态 `el-tag`、流转按钮组 `v-if="auth.hasPermission('work_order.edit')"` `v-for="t in transitions"` `@click="doTransition(t)"`{{ t.label }}、「编辑」按钮 `work_order.edit`(打开 FormDialog edit——本任务可接 FormDialog；若 FormDialog 已在 T2 建好，import 复用，`editingWO=wo`)。
- `el-tabs v-model="activeTab"`：
  - 「概览」`name="overview"` → `<OverviewTab :work-order="wo" @changed="load" />`（wo 非空时）。
  - 「工时成本」`name="labor-cost"` lazy → `<LaborCostTab :work-order-id="woId" />`。
  - 「活动」`name="activity"` lazy → `<ActivityTab :work-order-id="woId" />`。
  - 「执行」`name="execution"` lazy，`v-if="wo?.procedure_id"` → `<ExecutionTab :work-order-id="woId" />`。
- 编辑用 `WorkOrderFormDialog`(import)：`<WorkOrderFormDialog v-model:visible="editVisible" mode="edit" :editing="wo" @saved="load" />`；「编辑」按钮 `editVisible=true`。
- `defineExpose({ doTransition, load, wo })`。
- 模板根 `.page`，scoped 样式。

> 本任务依赖 T4/T5/T6 的 tab 组件尚未实现——为使 T3 可独立编译/测试，**先创建 LaborCostTab/ActivityTab/ExecutionTab 的最小占位**(`defineProps<{ workOrderId: string }>()` + `<template><div /></template>`)，后续任务覆盖。OverviewTab 本任务实现(见下)。测试已 stub 这些 tab。

### 3B OverviewTab

- [ ] **Step 4: 写失败测试 `tests/unit/OverviewTab.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { sa, st, ap, dp } = vi.hoisted(() => ({ sa: vi.fn(), st: vi.fn(), ap: vi.fn(), dp: vi.fn() }))
vi.mock('@/api/workOrders', () => ({
  setAssignees: sa,
  setTeams: st,
  attachProcedure: ap,
  detachProcedure: dp,
}))
vi.mock('@/api/users', () => ({ listUsers: vi.fn().mockResolvedValue([{ id: 'u1', name: '张三' }]) }))
vi.mock('@/api/teams', () => ({ listTeams: vi.fn().mockResolvedValue([{ id: 't1', name: '机修组' }]) }))
vi.mock('@/api/assets', () => ({ listAssetsMini: vi.fn().mockResolvedValue([{ id: 'a1', name: '泵' }]) }))
vi.mock('@/api/locations', () => ({ listLocationsMini: vi.fn().mockResolvedValue([{ id: 'l1', name: '车间' }]) }))
vi.mock('@/api/procedures', () => ({ listProceduresMini: vi.fn().mockResolvedValue([{ id: 'pr1', name: '保养SOP' }]) }))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({ useAuthStore: () => ({ hasPermission: () => authState.can }) }))

import OverviewTab from '@/components/workorder/OverviewTab.vue'

const wo = {
  id: 'w1',
  custom_id: 'WO-001',
  title: '泵检修',
  description: '检修描述',
  status: 'OPEN',
  priority: 'HIGH',
  due_date: null,
  asset_id: 'a1',
  location_id: 'l1',
  primary_user_id: 'u1',
  procedure_id: null,
  procedure_group_id: null,
  completed_at: null,
  category_id: null,
  created_by_user_id: null,
  assignee_ids: [],
  team_ids: [],
}

function mountTab(workOrder = wo) {
  return mount(OverviewTab, {
    props: { workOrder },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  sa.mockReset().mockResolvedValue(wo)
  st.mockReset().mockResolvedValue(wo)
  ap.mockReset().mockResolvedValue(wo)
  dp.mockReset().mockResolvedValue(wo)
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('OverviewTab', () => {
  it('渲染基本信息 + 资产/负责人名', async () => {
    const w = mountTab()
    await flushPromises()
    expect(w.text()).toContain('检修描述')
    expect(w.text()).toContain('泵')
    expect(w.text()).toContain('张三')
  })

  it('保存指派调 setAssignees + setTeams', async () => {
    const w = mountTab()
    await flushPromises()
    const vm = w.vm as any
    vm.assigneeIds = ['u1']
    vm.teamIds = ['t1']
    await vm.saveAssignment()
    await flushPromises()
    expect(sa).toHaveBeenCalledWith('w1', { user_ids: ['u1'] })
    expect(st).toHaveBeenCalledWith('w1', { team_ids: ['t1'] })
  })

  it('挂接 SOP 调 attachProcedure', async () => {
    const w = mountTab()
    await flushPromises()
    const vm = w.vm as any
    vm.selectedProcedure = 'pr1'
    await vm.doAttach()
    await flushPromises()
    expect(ap).toHaveBeenCalledWith('w1', { procedure_id: 'pr1' })
  })
})
```

- [ ] **Step 5: 跑红** `npm run test -- OverviewTab` → FAIL。

- [ ] **Step 6: 实现 `OverviewTab.vue`**

`<script setup lang="ts">`：
- props：`workOrder: WorkOrderRead`。emits：`changed`(指派/SOP 改动后通知详情壳 reload)。
- import：`setAssignees`/`setTeams`/`attachProcedure`/`detachProcedure`、`listUsers`/`listTeams`/`listAssetsMini`/`listLocationsMini`/`listProceduresMini`、`useAuthStore`、`formatDate`、`ElMessage`/`ElMessageBox`、types。
- state：`users`/`teams`/`assetsMini`/`locationsMini`/`procedures`(ref [])、`assigneeIds = ref<string[]>([])`、`teamIds = ref<string[]>([])`、`selectedProcedure = ref('')`、`savingAssign`/`attaching`。`auth=useAuthStore()`。
- `onMounted`：并行拉 users/teams/assetsMini/locationsMini/procedures；`assigneeIds.value=[...workOrder.assignee_ids]`、`teamIds.value=[...workOrder.team_ids]`。`watch(() => props.workOrder, (w) => { assigneeIds.value=[...w.assignee_ids]; teamIds.value=[...w.team_ids] })`(工单 reload 后同步)。
- 映射：`assetName`/`locationName`/`userName`/`priorityLabel`。
- 模板分区：
  - **基本信息**(`el-descriptions` 或 `dl`)：编号/标题/描述/优先级(中文)/资产(assetName)/位置(locationName)/负责人(userName)/分类/到期(formatDate)/创建人。
  - **指派**(`work_order.edit` 才可改)：用户多选(`el-select multiple filterable` users)、团队多选(teams)、「保存指派」按钮 → `saveAssignment`。
  - **SOP**：已挂(`workOrder.procedure_id`)→ 显示「已挂接 SOP」+ 「解绑」按钮(`work_order.edit`，confirm→`doDetach`)；未挂→ proceduresMini 选择 + 「挂接」按钮 → `doAttach`。
- `saveAssignment`：`try { savingAssign=true; await setAssignees(props.workOrder.id, { user_ids: assigneeIds.value }); await setTeams(props.workOrder.id, { team_ids: teamIds.value }); ElMessage.success('指派已保存'); emit('changed') } catch { ElMessage.error('保存失败，请重试') } finally { savingAssign=false }`。
- `doAttach`：`if (!selectedProcedure.value) { ElMessage.warning('请选择 SOP'); return }; try { await attachProcedure(props.workOrder.id, { procedure_id: selectedProcedure.value }); ElMessage.success('已挂接'); selectedProcedure.value=''; emit('changed') } catch { ElMessage.error('操作失败，请重试') }`。
- `doDetach`：`ElMessageBox.confirm('解绑 SOP 将清除执行步骤，确认？','提示',{type:'warning'}).catch(()=>'__cancel__')` 若取消 return；`await detachProcedure(props.workOrder.id); ElMessage.success('已解绑'); emit('changed')`；catch 本地化。
- `defineExpose({ assigneeIds, teamIds, selectedProcedure, saveAssignment, doAttach, doDetach })`。

- [ ] **Step 7: 跑绿 + 门禁** `npm run test -- WorkOrderDetailView OverviewTab && npm run test && npm run typecheck && npm run lint`。prettier 相关文件 + 占位 tab。

- [ ] **Step 8: commit**
```bash
git add src/views/maintenance/WorkOrderDetailView.vue src/components/workorder/OverviewTab.vue src/components/workorder/LaborCostTab.vue src/components/workorder/ActivityTab.vue src/components/workorder/ExecutionTab.vue tests/unit/WorkOrderDetailView.spec.ts tests/unit/OverviewTab.spec.ts
git commit -m "feat(fe-workorders): detail shell + status transitions + overview tab

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: 工时成本 tab(成本汇总 + 工时 CRUD/计时器 + 额外成本 CRUD)

**Files:**
- Create: `src/components/workorder/{LaborDialog,AdditionalCostDialog}.vue`、`src/components/workorder/LaborCostTab.vue`(覆盖占位)
- Test: `tests/unit/LaborCostTab.spec.ts`、`tests/unit/LaborDialog.spec.ts`

- [ ] **Step 1: 写失败测试 `tests/unit/LaborDialog.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { cl, ul } = vi.hoisted(() => ({ cl: vi.fn(), ul: vi.fn() }))
vi.mock('@/api/workOrders', () => ({ createLabor: cl, updateLabor: ul }))
vi.mock('@/api/users', () => ({ listUsers: vi.fn().mockResolvedValue([{ id: 'u1', name: '张三' }]) }))
vi.mock('@/api/timeCategories', () => ({ listTimeCategories: vi.fn().mockResolvedValue([{ id: 'tc1', name: '常规工时', hourly_rate: '50.00', description: '' }]) }))

import LaborDialog from '@/components/workorder/LaborDialog.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  cl.mockReset().mockResolvedValue({})
  ul.mockReset().mockResolvedValue({})
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('LaborDialog', () => {
  it('create 提交按分钟转 duration_seconds 调 createLabor', async () => {
    const w = mount(LaborDialog, {
      props: { visible: true, workOrderId: 'w1', editing: null },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    const vm = w.vm as any
    vm.form.minutes = 30
    vm.form.user_id = 'u1'
    vm.form.time_category_id = 'tc1'
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cl).toHaveBeenCalled()
    expect(cl.mock.calls[0][0]).toBe('w1')
    expect(cl.mock.calls[0][1]).toMatchObject({ duration_seconds: 1800, user_id: 'u1', time_category_id: 'tc1' })
    expect(w.emitted('saved')).toBeTruthy()
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- LaborDialog` → FAIL。

- [ ] **Step 3: 实现 `LaborDialog.vue`**
- props：`visible`、`workOrderId: string`、`editing: LaborRead | null`。emits `update:visible`/`saved`。
- import：`createLabor`/`updateLabor`、`listUsers`、`listTimeCategories`、`ElMessage`、types。
- state：`users`/`timeCategories`(ref [])、`submitting`、`form = reactive<{minutes,user_id,time_category_id,hourly_rate,notes}>`(minutes 0，user/time_category null，hourly_rate ''，notes '')。
- `watch(visible,{immediate})` 拉 users/timeCategories + resetOrFill（editing→`minutes = Math.round(editing.duration_seconds/60)`、user_id/time_category_id/hourly_rate/notes 回填）。
- 模板字段：用户(`el-select clearable filterable` users)、工时类别(`el-select clearable` timeCategories，label=name)、时长分钟(`el-input-number :min="0"`)、费率(`el-input` placeholder「留空则按类别」)、备注(textarea)。footer 保存/取消。
- `submitForm`：`duration_seconds = Math.round(form.minutes) * 60`；payload `{ duration_seconds, user_id: form.user_id||null, time_category_id: form.time_category_id||null, hourly_rate: form.hourly_rate || null, notes: form.notes }`；editing?`updateLabor(workOrderId, editing.id, payload)`:`createLabor(workOrderId, payload)`；成功 emit saved + close；try/catch 本地化。
- `defineExpose({ form, submitForm })`。

- [ ] **Step 4: 写失败测试 `tests/unit/LaborCostTab.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { ll, dl, st, lac, dac, gcs } = vi.hoisted(() => ({
  ll: vi.fn(),
  dl: vi.fn(),
  st: vi.fn(),
  lac: vi.fn(),
  dac: vi.fn(),
  gcs: vi.fn(),
}))
vi.mock('@/api/workOrders', () => ({
  listLabor: ll,
  deleteLabor: dl,
  stopTimer: st,
  startTimer: vi.fn(),
  createLabor: vi.fn(),
  updateLabor: vi.fn(),
  listAdditionalCosts: lac,
  deleteAdditionalCost: dac,
  createAdditionalCost: vi.fn(),
  updateAdditionalCost: vi.fn(),
  getCostSummary: gcs,
}))
vi.mock('@/api/users', () => ({ listUsers: vi.fn().mockResolvedValue([{ id: 'u1', name: '张三' }]) }))
vi.mock('@/api/timeCategories', () => ({ listTimeCategories: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/costCategories', () => ({ listCostCategories: vi.fn().mockResolvedValue([]) }))
vi.mock('@/components/workorder/LaborDialog.vue', () => ({
  default: { name: 'LaborDialog', props: ['visible', 'workOrderId', 'editing'], emits: ['update:visible', 'saved'], template: '<div class="labor-dialog-stub" />' },
}))
vi.mock('@/components/workorder/AdditionalCostDialog.vue', () => ({
  default: { name: 'AdditionalCostDialog', props: ['visible', 'workOrderId', 'editing'], emits: ['update:visible', 'saved'], template: '<div class="cost-dialog-stub" />' },
}))
vi.mock('@/components/analytics/KpiCard.vue', () => ({
  default: { name: 'KpiCard', props: ['label', 'value', 'unit', 'hint'], template: '<div class="kpi-stub">{{ label }}:{{ value }}</div>' },
}))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({ useAuthStore: () => ({ hasPermission: () => authState.can }) }))

import LaborCostTab from '@/components/workorder/LaborCostTab.vue'

function mountTab() {
  return mount(LaborCostTab, {
    props: { workOrderId: 'w1' },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  ll.mockReset().mockResolvedValue([
    { id: 'l1', work_order_id: 'w1', user_id: 'u1', time_category_id: null, started_at: null, stopped_at: '2026-06-01T01:00:00', duration_seconds: 3600, hourly_rate: '50.00', notes: '', running: false, cost: '50.00', running_elapsed_seconds: null },
  ])
  dl.mockReset().mockResolvedValue(undefined)
  st.mockReset().mockResolvedValue({})
  lac.mockReset().mockResolvedValue([
    { id: 'c1', work_order_id: 'w1', cost_category_id: null, title: '运费', amount: '100.00', description: '', created_by_user_id: null },
  ])
  dac.mockReset().mockResolvedValue(undefined)
  gcs.mockReset().mockResolvedValue({ labor_total: '50.00', additional_total: '100.00', parts_total: '0.00', total: '150.00' })
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('LaborCostTab', () => {
  it('加载成本汇总 + 工时 + 额外成本', async () => {
    const w = mountTab()
    await flushPromises()
    expect(ll).toHaveBeenCalledWith('w1')
    expect(lac).toHaveBeenCalledWith('w1')
    expect(gcs).toHaveBeenCalledWith('w1')
    expect(w.text()).toContain('150.00') // total
    expect(w.text()).toContain('张三') // labor user
    expect(w.text()).toContain('运费') // additional cost title
  })

  it('删除工时调 deleteLabor 并重取汇总', async () => {
    const { ElMessageBox } = await import('element-plus')
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    const w = mountTab()
    await flushPromises()
    const vm = w.vm as any
    await vm.removeLabor({ id: 'l1' })
    await flushPromises()
    expect(dl).toHaveBeenCalledWith('w1', 'l1')
    expect(gcs).toHaveBeenCalledTimes(2) // 初次 + 删后重取
  })
})
```

- [ ] **Step 5: 跑红** `npm run test -- LaborCostTab` → FAIL。

- [ ] **Step 6: 实现 `AdditionalCostDialog.vue` 与 `LaborCostTab.vue`**

`AdditionalCostDialog.vue`：
- props `visible`/`workOrderId`/`editing: AdditionalCostRead | null`。emits `update:visible`/`saved`。
- import `createAdditionalCost`/`updateAdditionalCost`、`listCostCategories`、`ElMessage`、types。
- state `costCategories`、`submitting`、`form = reactive<{title,amount,cost_category_id,description}>`。`watch(visible,{immediate})` 拉 costCategories + resetOrFill。
- 字段：标题(必填)、金额(必填 `el-input`)、成本类别(clearable costCategories)、描述(textarea)。
- submitForm：校验 title.trim() + amount；payload `{ title:trim, amount: form.amount, cost_category_id: form.cost_category_id||null, description: form.description }`；editing?update:create；emit saved + close；try/catch 本地化。defineExpose({form,submitForm})。

`LaborCostTab.vue`：
- props `workOrderId: string`。
- import `listLabor`/`deleteLabor`/`stopTimer`/`startTimer`/`listAdditionalCosts`/`deleteAdditionalCost`/`getCostSummary`、`listUsers`、`LaborDialog`/`AdditionalCostDialog`、`KpiCard`、`useAuthStore`、`ElMessage`/`ElMessageBox`、`formatDateTime`、types。
- state：`labor = ref<LaborRead[]>([])`、`costs = ref<AdditionalCostRead[]>([])`、`summary = ref<CostSummaryRead | null>(null)`、`users`、`loading`；`laborDialogVisible`/`editingLabor`、`costDialogVisible`/`editingCost`。`auth`。
- `reloadAll = async () => { labor.value = await listLabor(p); costs.value = await listAdditionalCosts(p); summary.value = await getCostSummary(p) }`(p=props.workOrderId)。onMounted 拉 users + reloadAll。
- 成本汇总：4 张 `KpiCard`(工时合计 labor_total / 额外合计 additional_total / 备件合计 parts_total / 总计 total)。
- 工时子表：列 用户(userName)/时长(`durationText(duration_seconds)`=「Xh Ym」)/费率(hourly_rate)/成本(cost)/状态(`running` ? `el-tag`「计时中」:'')/备注（**不展示工时类别列**，类别在 LaborDialog 内编辑即可，省一次 timeCategories 拉取）；操作：编辑(`work_order.edit` → editingLabor=row;laborDialogVisible)、停止(`row.running && work_order.edit` → `stopTimer(p,row.id)`+reloadAll)、删除(`removeLabor`)。顶部「新增工时」(`work_order.edit` → editingLabor=null;laborDialogVisible)、「开始计时」(`work_order.edit` → `startTimer(p)`+reloadAll)。
- 额外成本子表：列 标题/金额/类别/备注；操作 编辑/删除。顶部「新增成本」。
- `removeLabor(row)`：`ElMessageBox.confirm('确认删除该工时？',...)`→`deleteLabor(p,row.id)`→reloadAll；catch 静默。`removeCost(row)`：同→`deleteAdditionalCost(p,row.id)`→reloadAll。
- 内嵌 `<LaborDialog v-model:visible="laborDialogVisible" :work-order-id="workOrderId" :editing="editingLabor" @saved="reloadAll" />` + `<AdditionalCostDialog ... :editing="editingCost" @saved="reloadAll" />`。
- `durationText(sec)`：`const h=Math.floor(sec/3600); const m=Math.floor((sec%3600)/60); return h>0 ? `${h}h ${m}m` : `${m}m``。
- `defineExpose({ removeLabor, removeCost, reloadAll })`。
- 模板根 `<div v-loading="loading">` + 汇总卡行 + 工时区 + 成本区。

- [ ] **Step 7: 跑绿 + 门禁** `npm run test -- LaborDialog LaborCostTab && npm run test && npm run typecheck && npm run lint`。prettier 相关文件。

- [ ] **Step 8: commit**
```bash
git add src/components/workorder/LaborDialog.vue src/components/workorder/AdditionalCostDialog.vue src/components/workorder/LaborCostTab.vue tests/unit/LaborDialog.spec.ts tests/unit/LaborCostTab.spec.ts
git commit -m "feat(fe-workorders): labor & cost tab with cost summary, labor CRUD/timer & additional costs

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: 活动 tab(时间线 + 评论)

**Files:** Create `src/components/workorder/ActivityTab.vue`(覆盖占位)；Test `tests/unit/ActivityTab.spec.ts`

- [ ] **Step 1: 写失败测试 `tests/unit/ActivityTab.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { la, ac } = vi.hoisted(() => ({ la: vi.fn(), ac: vi.fn() }))
vi.mock('@/api/workOrders', () => ({ listWorkOrderActivities: la, addWorkOrderComment: ac }))
vi.mock('@/api/users', () => ({ listUsers: vi.fn().mockResolvedValue([{ id: 'u1', name: '张三' }]) }))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({ useAuthStore: () => ({ hasPermission: () => authState.can }) }))

import ActivityTab from '@/components/workorder/ActivityTab.vue'

function mountTab() {
  return mount(ActivityTab, {
    props: { workOrderId: 'w1' },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  la.mockReset().mockResolvedValue([
    { id: 'a1', activity_type: 'STATUS_CHANGE', actor_user_id: 'u1', from_status: 'OPEN', to_status: 'IN_PROGRESS', comment: '', created_at: '2026-06-01T00:00:00' },
    { id: 'a2', activity_type: 'COMMENT', actor_user_id: 'u1', from_status: null, to_status: null, comment: '已开始', created_at: '2026-06-01T01:00:00' },
  ])
  ac.mockReset().mockResolvedValue({})
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('ActivityTab', () => {
  it('加载并渲染活动时间线', async () => {
    const w = mountTab()
    await flushPromises()
    expect(la).toHaveBeenCalledWith('w1')
    expect(w.text()).toContain('已开始') // comment
    expect(w.text()).toContain('待处理') // from OPEN 中文
    expect(w.text()).toContain('进行中') // to IN_PROGRESS 中文
  })

  it('发评论调 addWorkOrderComment 并重拉', async () => {
    const w = mountTab()
    await flushPromises()
    const vm = w.vm as any
    vm.commentText = '检查完毕'
    await vm.submitComment()
    await flushPromises()
    expect(ac).toHaveBeenCalledWith('w1', { comment: '检查完毕' })
    expect(la).toHaveBeenCalledTimes(2)
  })

  it('空评论不调用', async () => {
    const w = mountTab()
    await flushPromises()
    const vm = w.vm as any
    vm.commentText = '   '
    await vm.submitComment()
    expect(ac).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- ActivityTab` → FAIL。

- [ ] **Step 3: 实现 `ActivityTab.vue`**
- props `workOrderId: string`。
- import `listWorkOrderActivities`/`addWorkOrderComment`、`listUsers`、`useAuthStore`、`formatDateTime`、types、`ElMessage`。
- 常量 `WO_STATUS_LABELS`(状态键→中文)。helper `statusText(s: string | null)`=`s ? (WO_STATUS_LABELS[s] ?? s) : '—'`、`userName(id)`。
- state：`activities = ref<WorkOrderActivityRead[]>([])`、`users`、`commentText = ref('')`、`loading`、`submitting`。
- `load = async () => { activities.value = await listWorkOrderActivities(props.workOrderId) }`。onMounted 拉 users + load。
- `submitComment`：`if (!commentText.value.trim()) return; try { submitting=true; await addWorkOrderComment(props.workOrderId, { comment: commentText.value.trim() }); commentText.value=''; await load() } catch { ElMessage.error('操作失败，请重试') } finally { submitting=false }`。
- 模板：`el-timeline` over activities：`el-timeline-item :timestamp="formatDateTime(a.created_at)"`；内容按 activity_type：STATUS_CHANGE → `userName(actor) + ' ' + statusText(from) + ' → ' + statusText(to)`；COMMENT → `userName(actor) + '：' + comment`；其它 → `userName(actor) + ' ' + a.activity_type + (comment ? '：'+comment : '')`。底部评论输入(`el-input` + 「发表评论」按钮 `work_order.view`)。
- `defineExpose({ commentText, submitComment, load })`。

- [ ] **Step 4: 跑绿 + 门禁** + prettier。
- [ ] **Step 5: commit** `feat(fe-workorders): activity tab`。

---

## Task 6: 执行 tab(只读)

**Files:** Create `src/components/workorder/ExecutionTab.vue`(覆盖占位)；Test `tests/unit/ExecutionTab.spec.ts`

- [ ] **Step 1: 写失败测试 `tests/unit/ExecutionTab.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { ge } = vi.hoisted(() => ({ ge: vi.fn() }))
vi.mock('@/api/workOrders', () => ({ getExecution: ge }))
vi.mock('@/api/users', () => ({ listUsers: vi.fn().mockResolvedValue([{ id: 'u1', name: '张三' }]) }))

import ExecutionTab from '@/components/workorder/ExecutionTab.vue'

function mountTab() {
  return mount(ExecutionTab, {
    props: { workOrderId: 'w1' },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  ge.mockReset().mockResolvedValue({
    procedure: { id: 'p1', group_id: 'g1', code: 'SOP-1', name: '泵保养', version: 2 },
    outline: [
      { node_id: 'n1', heading_level: 1, kind: 'heading', body: '准备', code: 'H1', sort_order: 1 },
    ],
    steps: [
      { id: 's1', node_id: 'n2', node_code: 'S1', node_sort_order: 2, input_schema: {}, response: {}, is_done: true, done_by_user_id: 'u1', done_at: '2026-06-01T02:00:00', notes: '完成' },
      { id: 's2', node_id: 'n3', node_code: 'S2', node_sort_order: 3, input_schema: {}, response: {}, is_done: false, done_by_user_id: null, done_at: null, notes: '' },
    ],
  })
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('ExecutionTab', () => {
  it('加载执行视图 + 渲染 SOP 名 + 步骤完成态', async () => {
    const w = mountTab()
    await flushPromises()
    expect(ge).toHaveBeenCalledWith('w1')
    expect(w.text()).toContain('泵保养') // procedure name
    expect(w.text()).toContain('已完成') // is_done true tag
    expect(w.text()).toContain('未完成') // is_done false tag
    expect(w.text()).toContain('S1') // node_code
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- ExecutionTab` → FAIL。

- [ ] **Step 3: 实现 `ExecutionTab.vue`**
- props `workOrderId: string`。
- import `getExecution`、`listUsers`、`formatDateTime`、types、`ElMessage`。
- state：`exec = ref<ExecutionView | null>(null)`、`users`、`loading`。`userName(id)`。
- onMounted 拉 users + `try { exec.value = await getExecution(props.workOrderId) } catch { ElMessage.error('加载执行视图失败，请重试') }`(loading try/finally)。
- 模板(只读)：`v-if="exec?.procedure"` 显示 procedure（code/name/version）；**步骤列表**(`el-table :data="exec.steps"` 或卡片列表)：列 节点(node_code)、状态(`<el-tag :type="row.is_done?'success':'info'">{{ row.is_done?'已完成':'未完成' }}</el-tag>`)、完成人(`userName(done_by_user_id)`)、完成时间(`formatDateTime(done_at)`)、备注(notes)。outline 可作分组标题或略(本轮步骤表为主，outline 可选展示标题层级)。**无任何填写/编辑控件**（只读）。
- `defineExpose({ exec })`。

- [ ] **Step 4: 跑绿 + 门禁** + prettier。
- [ ] **Step 5: commit** `feat(fe-workorders): execution tab (read-only)`。

---

## Task 7: 工单分类对话框

**Files:** Create `src/components/maintenance/WorkOrderCategoryManageDialog.vue`；Test `tests/unit/WorkOrderCategoryManageDialog.spec.ts`

- [ ] **Step 1: 写失败测试 `tests/unit/WorkOrderCategoryManageDialog.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lc, cc, uc, dc } = vi.hoisted(() => ({ lc: vi.fn(), cc: vi.fn(), uc: vi.fn(), dc: vi.fn() }))
vi.mock('@/api/workOrderCategories', () => ({
  listWorkOrderCategories: lc,
  createWorkOrderCategory: cc,
  updateWorkOrderCategory: uc,
  deleteWorkOrderCategory: dc,
}))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({ useAuthStore: () => ({ hasPermission: () => authState.can }) }))

import WorkOrderCategoryManageDialog from '@/components/maintenance/WorkOrderCategoryManageDialog.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lc.mockReset().mockResolvedValue([
    { id: 'c1', name: '常规', description: '' },
    { id: 'c2', name: '紧急', description: '' },
  ])
  cc.mockReset().mockResolvedValue({})
  uc.mockReset().mockResolvedValue({})
  dc.mockReset().mockResolvedValue(undefined)
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('WorkOrderCategoryManageDialog', () => {
  it('可见时加载并渲染分类', async () => {
    mount(WorkOrderCategoryManageDialog, {
      props: { visible: true },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    expect(lc).toHaveBeenCalled()
    expect(document.body.textContent).toContain('常规')
    expect(document.body.textContent).toContain('紧急')
  })

  it('新增提交并 emit changed', async () => {
    const w = mount(WorkOrderCategoryManageDialog, {
      props: { visible: true },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    const addBtn = Array.from(document.querySelectorAll('.el-button')).find(
      (b) => b.textContent?.trim() === '新增分类',
    ) as HTMLElement
    addBtn.click()
    await flushPromises()
    const input = document.querySelector(
      '.el-dialog input[placeholder="请输入分类名称"]',
    ) as HTMLInputElement
    input.value = '预防'
    input.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cc).toHaveBeenCalledWith({ name: '预防', description: '' })
    expect(w.emitted('changed')).toBeTruthy()
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- WorkOrderCategoryManageDialog` → FAIL。

- [ ] **Step 3: 实现** 复刻 `src/components/inventory/PartCategoryManageDialog.vue`(先 Read)，delta：
- api 换 `@/api/workOrderCategories`(`listWorkOrderCategories/createWorkOrderCategory/updateWorkOrderCategory/deleteWorkOrderCategory`)。
- 类型换 `WorkOrderCategoryRead/Create/Update`。
- 门控 `work_order_category.manage`(新增/编辑/删除 v-if)。
- 其余（名称必填 placeholder「请输入分类名称」+ 描述 textarea、主表格列 名称/描述/操作、create payload `{ name: trim, description }` description 默认空串、「新增分类」/「保存」文案、`changed` 事件、删除 confirm、`watch(visible,{immediate})`、try/catch 本地化）完全一致。

- [ ] **Step 4: 跑绿 + 门禁** + prettier。
- [ ] **Step 5: commit** `feat(fe-workorders): work order category manage dialog`。

---

## Task 8: RBAC 门控核对 + 收尾

**Files:** 跨 views/components(核对)；Test：跑全量

- [ ] **Step 1:** 门控核对：`grep -rn "hasPermission('" src/views/maintenance/WorkOrdersView.vue src/views/maintenance/WorkOrderDetailView.vue src/components/workorder/ src/components/maintenance/WorkOrderCategoryManageDialog.vue`，逐个对照后端 `backend/app/permissions.py`：
  - 新建工单=`work_order.create`、编辑/状态流转/指派/SOP挂接解绑/labor·cost CRUD=`work_order.edit`、删除=`work_order.delete`、评论=`work_order.view`、管理分类入口=`work_order_category.view`、分类增改删=`work_order_category.manage`。
  - 执行 tab 只读，**不应**出现 `work_order.execute`。
  有误最小修正，否则记「无需修改」。
- [ ] **Step 2:** 导航/路由：AppSidebar「维护」组「工单」path `/maintenance/work-orders`、无 soon；`activeMenu` 对 `/maintenance/work-orders` 与 `/maintenance/work-orders/:id` 均高亮；与 router 两路由 path 一致。
- [ ] **Step 3:** 全量门禁：
  ```
  cd frontend && npm run test && npm run typecheck && npm run lint && npx prettier --check "src/**/*.{ts,vue}" "tests/**/*.ts"
  ```
  test 全绿、typecheck 0 错、lint 0 警告；prettier 关注本分支 `git diff main...HEAD --name-only` 的 .ts/.vue。
- [ ] **Step 4: commit**(若有修正)：`chore(fe-workorders): RBAC gating audit + wrap-up`。若全部正确无改动，不造空 commit，汇报「核对通过」。

---

## 收尾

完成 T1–T8 后派发最终 code review，再用 `superpowers:finishing-a-development-branch`(合并/push 交人决定，不自动 push、不自合 main)。**本轮无 alembic 迁移**，合并 `--no-ff`。

**自查清单：**
- 列表(6 维过滤 + 状态/优先级中文 + 资产/负责人名映射 + 详情跳转 + 删除)。
- 详情壳(页头状态流转按 ALLOWED_TRANSITIONS 动态显隐 + 编辑 + 返回；el-tabs 概览/工时成本/活动/执行，后三 lazy，执行仅挂 SOP 显示)。
- 概览(基本信息 + 指派 setAssignees/setTeams 替换 + SOP attach/detach；改动 emit changed → 详情壳 reload)。
- 工时成本(成本汇总 KpiCard×4 + 工时子表 CRUD/计时器起停(不实时跳秒)+ LaborDialog 分钟→秒 + 额外成本子表 CRUD + AdditionalCostDialog；增删改后重取 summary)。
- 活动(时间线按 activity_type 渲染 + 评论)。执行(只读 outline/steps + is_done tag)。
- 工单分类对话框(work_order_category.manage)。
- 创建/编辑工单(FormDialog；create 含指派/SOP，edit 仅 WorkOrderUpdate 字段)。
- RBAC：写动作 hasPermission 隐藏；门控码精确(状态流转·指派·labor·cost=edit；分类=manage；执行只读不涉 execute)。
- 导航工单接入、无 soon；2 路由 requiresAuth；activeMenu 详情页也高亮工单项。
- 仅中文、无新增 locale。`typecheck` 0 错、`lint` 0 警告、vitest 全绿、prettier 干净。
