# FE-4 请求 / PM / 计量 前端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 维护域 3 块前端（请求审批 / 预防性维护排程 / 计量读数与触发器）——把已就绪的后端变成可用界面。

**Architecture:** Vue 3 `<script setup lang="ts">` + Element Plus（扁平 `el-table` 列表 + `el-dialog` 表单/详情）+ Pinia（仅复用 `auth` store 做 RBAC）+ vue-router 扁平路由。请求审批走「审批指派」对话框、PM 含排程字段与启用/生成、计量用宽详情对话框分区（读数历史 + 快速录入 + 触发器子表 + 嵌套 `MeterTriggerDialog`）。**纯前端，无后端改动、无迁移。**

**Tech Stack:** Vite + TS + Element Plus + Pinia + vue-router + vitest + `@vue/test-utils`。门禁：`npm run typecheck`（vue-tsc --noEmit）+ `npm run lint`（eslint --max-warnings 0）+ prettier + `npm run test`（vitest）。

**全局约定（每任务适用）：**
- 工作目录 `frontend/`；命令 `npm run ...`。分支 `feat/fe-maintenance`（基于 main，spec 已提交）。
- 每任务：写测试 → 跑红 → 实现 → `npm run test` + `npm run typecheck` + `npm run lint` 绿 → prettier → commit。
- commit message 结尾附：`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- 仅中文、不做 i18n。RBAC：`const auth = useAuthStore()`；写动作按钮 `v-if="auth.hasPermission('<code>')"`（super_admin 通配）。
- 精确 `git add`，**勿纳入**仓库根未跟踪产物（`.claude/scheduled_tasks.lock`、`.verify-screenshots/*.png`）。
- 净室原创：复刻功能，绝不出现 "Atlas" 字样或复制其代码/文案。

**既有模式参考（须遵循，FE-5 已落定）：**
- api：`src/api/locations.ts`（`http.get<T>(path).then(r=>r.data)`；delete 用 `http.delete(path).then(()=>undefined)`；http baseURL 已含 `/api/v1`，路径写 `/requests`）。
- view：`src/views/inventory/{Vendors,Parts,PurchaseOrders}View.vue`（state 分区 + onMounted 并行 fetch + el-table + 单 dialog 多模式 + submitForm try/catch/finally + 本地化 `ElMessage.error('保存失败，请重试')` + `ElMessageBox.confirm` 删除 + RBAC v-if + `<style scoped>` 的 `.page`/`.page-title`/`.toolbar`）。PurchaseOrdersView 含宽对话框分区 + 状态流转 footer + `defineExpose` 供测试驱动 + 活动时间线 `el-timeline`，是请求/计量的直接范本。
- 嵌套对话框：`src/components/inventory/PartCategoryManageDialog.vue`（props `visible` + emit `update:visible`/`changed`；`watch(visible,{immediate:true})` 打开拉取；嵌套表单 dialog；提交 trim；删除 `ElMessageBox.confirm`）。
- api 测试：`tests/unit/inventoryApi.spec.ts`（`vi.hoisted` + `vi.mock('@/api/http')`）。
- view 测试：`tests/unit/PurchaseOrdersView.spec.ts`、`VendorsView.spec.ts`（`vi.mock('@/api/<x>')` + 可变 auth mock + `mount(View,{global:{plugins:[ElementPlus]},attachTo:document.body})` + `flushPromises` + `afterEach(() => { document.body.innerHTML = '' })` 清 teleport；teleported dialog 用 `document.querySelector('.el-dialog ...')`；复杂交互用 `defineExpose` + `vm` 驱动，绕开脆弱 DOM）。
- 导航：`src/components/AppSidebar.vue`（`groups` computed；「维护」组 工单(soon)/资产/位置/请求(soon)/预防性维护(soon)/计量(soon)，本计划把后三项去 soon 挂 path；`activeMenu` 多 `if startsWith` 串联）。
- 路由：`src/router/index.ts`（扁平 + `meta.requiresAuth` + `requiredPermission`）。已有前缀 `/platform/`、`/maindata/`、`/inventory/`；本计划新增 `/maintenance/`。
- 复用 api：`listAssetsMini`（`@/api/assets`，`AssetMini[]` 有 `name`）、`listLocationsMini`（`@/api/locations`，`LocationMini[]` 有 `name`）、`listUsers`（`@/api/users`，`UserRead[]` 有 `name`）、`listTeams`（`@/api/teams`，`TeamRead[]` 有 `name`）。`AssetMini`/`LocationMini` 在 `@/types/maindata`，`UserRead`/`TeamRead` 在 `@/types/platform`。procedures 列表：`fetchProcedureList`（`@/api/procedures`，返回 `PageResult<ProcedureRow>`，`ProcedureRow` 有 `id`/`name`/`is_current`）。
- 工具：`src/utils/format.ts` 的 `formatDateTime`（null→兜底「—」）、`formatDate`（YYYY-MM-DD）。

**后端契约（已核实，types 以此为准；Decimal/Numeric 字段 JSON 序列化为字符串 → 前端用 `string`；baseURL 含 `/api/v1`）：**

请求（Requests）：
- `RequestRead {id, custom_id, title, description, priority, due_date|null, asset_id|null, location_id|null, status, work_order_id|null, resolution_note, resolved_by_user_id|null, resolved_at|null, created_at, updated_at}`。
- `WorkOrderPriority = 'NONE'|'LOW'|'MEDIUM'|'HIGH'`；`RequestStatus = 'PENDING'|'APPROVED'|'REJECTED'|'CANCELED'`。
- `RequestCreate {title, description?, priority?, due_date?|null, asset_id?|null, location_id?|null}`；`RequestUpdate = Partial<RequestCreate>`。
- `RequestApprove {note?, primary_user_id?|null, assignee_ids?, team_ids?, procedure_id?|null}`；`RequestReason {reason}`；`CommentCreate {comment}`；`ActivityRead {id, activity_type, actor_user_id|null, comment, created_at}`。
- 端点：`/requests`(GET 查询 `status`/`priority`/`asset_id`/`location_id`，POST)、`/requests/{id}`(GET/PATCH/DELETE 204)、`/requests/{id}/approve|reject|cancel`(POST)、`/requests/{id}/activities`(GET/POST)。
- 门控：GET/活动读=`request.view`；POST 创建 & PATCH 编辑=`request.create`；DELETE=`request.delete`；approve & reject=`request.approve`；cancel=`request.cancel`；评论=`request.view`。

PM（Preventive Maintenance）：
- `PMRead {id, custom_id, title, description, priority, asset_id|null, location_id|null, primary_user_id|null, procedure_id|null, start_date, frequency_unit, frequency_value, next_due_date, is_enabled, last_generated_at|null, last_work_order_id|null, assignee_ids[], team_ids[], created_at, updated_at}`。
- `PMFrequencyUnit = 'DAY'|'WEEK'|'MONTH'`；`frequency_value` number ≥1。
- `PMCreate {title, description?, priority?, asset_id?|null, location_id?|null, primary_user_id?|null, procedure_id?|null, start_date, frequency_unit, frequency_value, assignee_ids?, team_ids?}`；`PMUpdate = Partial<PMCreate>`；`PMActivityRead` 同 `ActivityRead`。
- 端点：`/preventive-maintenances`(GET 查询 `is_enabled`/`asset_id`/`location_id`，POST)、`/preventive-maintenances/{id}`(GET/PATCH/DELETE 204)、`/{id}/enable|disable`(POST)、`/{id}/generate`(POST→WorkOrderRead 201)、`/{id}/activities`(GET)、`/{id}/comments`(POST)。
- 门控：GET/活动读/评论=`preventive_maintenance.view`；POST 创建=`preventive_maintenance.create`；PATCH=`preventive_maintenance.edit`；DELETE=`preventive_maintenance.delete`；enable/disable=`preventive_maintenance.edit`；**generate=`preventive_maintenance.create`**。

计量（Meters）：
- `MeterRead {id, custom_id, name, unit, update_frequency_days|null, asset_id|null, location_id|null, created_at, updated_at}`。
- `MeterReadingRead {id, meter_id, value, reading_at, recorded_by_user_id|null}`（`value` string）。
- `TriggerRead {id, meter_id, name, comparator, threshold, is_armed, is_enabled, priority, title, description, primary_user_id|null, procedure_id|null, last_triggered_at|null, last_work_order_id|null, assignee_ids[], team_ids[]}`。
- `MeterComparator = 'LESS_THAN'|'MORE_THAN'`；`threshold` string。
- `MeterCreate {name, unit?, update_frequency_days?|null, asset_id?|null, location_id?|null}`；`MeterUpdate = Partial<MeterCreate>`。
- `MeterReadingCreate {value, reading_at?|null}`；`ReadingResult {reading: MeterReadingRead, generated_work_order_ids: string[]}`。
- `TriggerCreate {name, comparator, threshold, priority?, title?, description?, primary_user_id?|null, procedure_id?|null, assignee_ids?, team_ids?, is_enabled?}`；`TriggerUpdate = Partial<TriggerCreate>`。
- 端点：`/meters`(GET 查询 `asset_id`/`location_id`，POST)、`/meters/{id}`(GET/PATCH/DELETE 204)、`/meters/{id}/readings`(GET，POST→ReadingResult 201)、`/meters/{id}/triggers`(GET，POST 201)、`/meters/{id}/triggers/{tid}`(GET/PATCH/DELETE 204)、`/meters/{id}/triggers/{tid}/enable|disable`(POST)。
- 门控：meter GET=`meter.view`、POST=`meter.create`、PATCH=`meter.edit`、DELETE=`meter.delete`；读数 GET=`reading.view`、POST=`reading.create`；触发器 GET=`meter.view`、**POST create=`meter.create`**、PATCH=`meter.edit`、DELETE=`meter.delete`、enable/disable=`meter.edit`。

---

## Task 1: 共享骨架（types + 3 api + listProceduresMini + 路由 + 导航 + 占位页）

**Files:**
- Create: `src/types/maintenance.ts`
- Create: `src/api/{requests,preventiveMaintenances,meters}.ts`
- Modify: `src/api/procedures.ts`（追加 `listProceduresMini` + 类型）
- Create: `src/views/maintenance/{Requests,PreventiveMaintenances,Meters}View.vue`（占位骨架）
- Modify: `src/router/index.ts`、`src/components/AppSidebar.vue`
- Test: `tests/unit/maintenanceApi.spec.ts`、`tests/unit/AppSidebar.spec.ts`（追加）

- [ ] **Step 1: 写失败测试 `tests/unit/maintenanceApi.spec.ts`**

```typescript
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get, post, patch, del } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  del: vi.fn(),
}))
vi.mock('@/api/http', () => ({ http: { get, post, patch, delete: del } }))

import {
  listRequests,
  getRequest,
  createRequest,
  updateRequest,
  deleteRequest,
  approveRequest,
  rejectRequest,
  cancelRequest,
  listRequestActivities,
  addRequestComment,
} from '@/api/requests'
import {
  listPMs,
  getPM,
  createPM,
  updatePM,
  deletePM,
  enablePM,
  disablePM,
  generatePM,
  listPMActivities,
  addPMComment,
} from '@/api/preventiveMaintenances'
import {
  listMeters,
  getMeter,
  createMeter,
  updateMeter,
  deleteMeter,
  listReadings,
  submitReading,
  listTriggers,
  createTrigger,
  updateTrigger,
  deleteTrigger,
  enableTrigger,
  disableTrigger,
} from '@/api/meters'

describe('maintenance api', () => {
  beforeEach(() => {
    for (const m of [get, post, patch, del]) m.mockReset().mockResolvedValue({ data: [] })
  })

  // requests
  it('listRequests GET /requests (no params)', async () => {
    await listRequests()
    expect(get).toHaveBeenCalledWith('/requests', { params: {} })
  })
  it('listRequests GET /requests with filters', async () => {
    await listRequests({ status: 'PENDING', priority: 'HIGH', asset_id: 'a1', location_id: 'l1' })
    expect(get).toHaveBeenCalledWith('/requests', {
      params: { status: 'PENDING', priority: 'HIGH', asset_id: 'a1', location_id: 'l1' },
    })
  })
  it('getRequest GET /requests/{id}', async () => {
    await getRequest('r1')
    expect(get).toHaveBeenCalledWith('/requests/r1')
  })
  it('createRequest POST /requests', async () => {
    await createRequest({ title: 'T' })
    expect(post).toHaveBeenCalledWith('/requests', { title: 'T' })
  })
  it('updateRequest PATCH /requests/{id}', async () => {
    await updateRequest('r1', { title: 'T2' })
    expect(patch).toHaveBeenCalledWith('/requests/r1', { title: 'T2' })
  })
  it('deleteRequest DELETE /requests/{id}', async () => {
    await deleteRequest('r1')
    expect(del).toHaveBeenCalledWith('/requests/r1')
  })
  it('approveRequest POST /approve', async () => {
    await approveRequest('r1', { note: 'ok', primary_user_id: 'u1', assignee_ids: [], team_ids: [] })
    expect(post).toHaveBeenCalledWith('/requests/r1/approve', {
      note: 'ok',
      primary_user_id: 'u1',
      assignee_ids: [],
      team_ids: [],
    })
  })
  it('rejectRequest POST /reject', async () => {
    await rejectRequest('r1', { reason: 'no' })
    expect(post).toHaveBeenCalledWith('/requests/r1/reject', { reason: 'no' })
  })
  it('cancelRequest POST /cancel', async () => {
    await cancelRequest('r1', { reason: 'x' })
    expect(post).toHaveBeenCalledWith('/requests/r1/cancel', { reason: 'x' })
  })
  it('listRequestActivities GET /activities', async () => {
    await listRequestActivities('r1')
    expect(get).toHaveBeenCalledWith('/requests/r1/activities')
  })
  it('addRequestComment POST /activities', async () => {
    await addRequestComment('r1', { comment: 'hi' })
    expect(post).toHaveBeenCalledWith('/requests/r1/activities', { comment: 'hi' })
  })

  // PM
  it('listPMs GET /preventive-maintenances (no params)', async () => {
    await listPMs()
    expect(get).toHaveBeenCalledWith('/preventive-maintenances', { params: {} })
  })
  it('listPMs GET with filters', async () => {
    await listPMs({ is_enabled: true, asset_id: 'a1', location_id: 'l1' })
    expect(get).toHaveBeenCalledWith('/preventive-maintenances', {
      params: { is_enabled: true, asset_id: 'a1', location_id: 'l1' },
    })
  })
  it('getPM GET /{id}', async () => {
    await getPM('p1')
    expect(get).toHaveBeenCalledWith('/preventive-maintenances/p1')
  })
  it('createPM POST', async () => {
    await createPM({ title: 'T', start_date: '2026-06-03', frequency_unit: 'DAY', frequency_value: 7 })
    expect(post).toHaveBeenCalledWith('/preventive-maintenances', {
      title: 'T',
      start_date: '2026-06-03',
      frequency_unit: 'DAY',
      frequency_value: 7,
    })
  })
  it('updatePM PATCH /{id}', async () => {
    await updatePM('p1', { title: 'T2' })
    expect(patch).toHaveBeenCalledWith('/preventive-maintenances/p1', { title: 'T2' })
  })
  it('deletePM DELETE /{id}', async () => {
    await deletePM('p1')
    expect(del).toHaveBeenCalledWith('/preventive-maintenances/p1')
  })
  it('enablePM POST /enable', async () => {
    await enablePM('p1')
    expect(post).toHaveBeenCalledWith('/preventive-maintenances/p1/enable')
  })
  it('disablePM POST /disable', async () => {
    await disablePM('p1')
    expect(post).toHaveBeenCalledWith('/preventive-maintenances/p1/disable')
  })
  it('generatePM POST /generate', async () => {
    await generatePM('p1')
    expect(post).toHaveBeenCalledWith('/preventive-maintenances/p1/generate')
  })
  it('listPMActivities GET /activities', async () => {
    await listPMActivities('p1')
    expect(get).toHaveBeenCalledWith('/preventive-maintenances/p1/activities')
  })
  it('addPMComment POST /comments', async () => {
    await addPMComment('p1', { comment: 'hi' })
    expect(post).toHaveBeenCalledWith('/preventive-maintenances/p1/comments', { comment: 'hi' })
  })

  // meters
  it('listMeters GET /meters (no params)', async () => {
    await listMeters()
    expect(get).toHaveBeenCalledWith('/meters', { params: {} })
  })
  it('listMeters GET with filters', async () => {
    await listMeters({ asset_id: 'a1', location_id: 'l1' })
    expect(get).toHaveBeenCalledWith('/meters', { params: { asset_id: 'a1', location_id: 'l1' } })
  })
  it('getMeter GET /{id}', async () => {
    await getMeter('m1')
    expect(get).toHaveBeenCalledWith('/meters/m1')
  })
  it('createMeter POST', async () => {
    await createMeter({ name: 'M' })
    expect(post).toHaveBeenCalledWith('/meters', { name: 'M' })
  })
  it('updateMeter PATCH /{id}', async () => {
    await updateMeter('m1', { unit: 'h' })
    expect(patch).toHaveBeenCalledWith('/meters/m1', { unit: 'h' })
  })
  it('deleteMeter DELETE /{id}', async () => {
    await deleteMeter('m1')
    expect(del).toHaveBeenCalledWith('/meters/m1')
  })
  it('listReadings GET /readings', async () => {
    await listReadings('m1')
    expect(get).toHaveBeenCalledWith('/meters/m1/readings')
  })
  it('submitReading POST /readings', async () => {
    await submitReading('m1', { value: '12.5' })
    expect(post).toHaveBeenCalledWith('/meters/m1/readings', { value: '12.5' })
  })
  it('listTriggers GET /triggers', async () => {
    await listTriggers('m1')
    expect(get).toHaveBeenCalledWith('/meters/m1/triggers')
  })
  it('createTrigger POST /triggers', async () => {
    await createTrigger('m1', { name: 'T', comparator: 'MORE_THAN', threshold: '100' })
    expect(post).toHaveBeenCalledWith('/meters/m1/triggers', {
      name: 'T',
      comparator: 'MORE_THAN',
      threshold: '100',
    })
  })
  it('updateTrigger PATCH /triggers/{tid}', async () => {
    await updateTrigger('m1', 't1', { threshold: '200' })
    expect(patch).toHaveBeenCalledWith('/meters/m1/triggers/t1', { threshold: '200' })
  })
  it('deleteTrigger DELETE /triggers/{tid}', async () => {
    await deleteTrigger('m1', 't1')
    expect(del).toHaveBeenCalledWith('/meters/m1/triggers/t1')
  })
  it('enableTrigger POST /enable', async () => {
    await enableTrigger('m1', 't1')
    expect(post).toHaveBeenCalledWith('/meters/m1/triggers/t1/enable')
  })
  it('disableTrigger POST /disable', async () => {
    await disableTrigger('m1', 't1')
    expect(post).toHaveBeenCalledWith('/meters/m1/triggers/t1/disable')
  })
})
```

- [ ] **Step 2: 跑红** `cd frontend && npm run test -- maintenanceApi` → FAIL（模块不存在）。

- [ ] **Step 3: types `src/types/maintenance.ts`**

```typescript
// 公共
export type WorkOrderPriority = 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH'

export interface ActivityRead {
  id: string
  activity_type: string
  actor_user_id: string | null
  comment: string
  created_at: string
}
export interface CommentCreate {
  comment: string
}

// 请求
export type RequestStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'CANCELED'

export interface RequestRead {
  id: string
  custom_id: string
  title: string
  description: string
  priority: WorkOrderPriority
  due_date: string | null
  asset_id: string | null
  location_id: string | null
  status: RequestStatus
  work_order_id: string | null
  resolution_note: string
  resolved_by_user_id: string | null
  resolved_at: string | null
  created_at: string
  updated_at: string
}
export interface RequestCreate {
  title: string
  description?: string
  priority?: WorkOrderPriority
  due_date?: string | null
  asset_id?: string | null
  location_id?: string | null
}
export type RequestUpdate = Partial<RequestCreate>
export interface RequestApprove {
  note?: string
  primary_user_id?: string | null
  assignee_ids?: string[]
  team_ids?: string[]
  procedure_id?: string | null
}
export interface RequestReason {
  reason: string
}

// PM
export type PMFrequencyUnit = 'DAY' | 'WEEK' | 'MONTH'

export interface PMRead {
  id: string
  custom_id: string
  title: string
  description: string
  priority: WorkOrderPriority
  asset_id: string | null
  location_id: string | null
  primary_user_id: string | null
  procedure_id: string | null
  start_date: string
  frequency_unit: PMFrequencyUnit
  frequency_value: number
  next_due_date: string
  is_enabled: boolean
  last_generated_at: string | null
  last_work_order_id: string | null
  assignee_ids: string[]
  team_ids: string[]
  created_at: string
  updated_at: string
}
export interface PMCreate {
  title: string
  description?: string
  priority?: WorkOrderPriority
  asset_id?: string | null
  location_id?: string | null
  primary_user_id?: string | null
  procedure_id?: string | null
  start_date: string
  frequency_unit: PMFrequencyUnit
  frequency_value: number
  assignee_ids?: string[]
  team_ids?: string[]
}
export type PMUpdate = Partial<PMCreate>

// 计量
export type MeterComparator = 'LESS_THAN' | 'MORE_THAN'

export interface MeterRead {
  id: string
  custom_id: string
  name: string
  unit: string
  update_frequency_days: number | null
  asset_id: string | null
  location_id: string | null
  created_at: string
  updated_at: string
}
export interface MeterCreate {
  name: string
  unit?: string
  update_frequency_days?: number | null
  asset_id?: string | null
  location_id?: string | null
}
export type MeterUpdate = Partial<MeterCreate>

export interface MeterReadingRead {
  id: string
  meter_id: string
  value: string
  reading_at: string
  recorded_by_user_id: string | null
}
export interface MeterReadingCreate {
  value: string
  reading_at?: string | null
}
export interface ReadingResult {
  reading: MeterReadingRead
  generated_work_order_ids: string[]
}

export interface TriggerRead {
  id: string
  meter_id: string
  name: string
  comparator: MeterComparator
  threshold: string
  is_armed: boolean
  is_enabled: boolean
  priority: WorkOrderPriority
  title: string
  description: string
  primary_user_id: string | null
  procedure_id: string | null
  last_triggered_at: string | null
  last_work_order_id: string | null
  assignee_ids: string[]
  team_ids: string[]
}
export interface TriggerCreate {
  name: string
  comparator: MeterComparator
  threshold: string
  priority?: WorkOrderPriority
  title?: string
  description?: string
  primary_user_id?: string | null
  procedure_id?: string | null
  assignee_ids?: string[]
  team_ids?: string[]
  is_enabled?: boolean
}
export type TriggerUpdate = Partial<TriggerCreate>

// procedure 下拉
export interface ProcedureMini {
  id: string
  name: string
}
```

- [ ] **Step 4: api 客户端**

`src/api/requests.ts`：
```typescript
import { http } from './http'
import type {
  RequestRead,
  RequestCreate,
  RequestUpdate,
  RequestApprove,
  RequestReason,
  RequestStatus,
  WorkOrderPriority,
  ActivityRead,
  CommentCreate,
} from '@/types/maintenance'

export interface ListRequestsParams {
  status?: RequestStatus
  priority?: WorkOrderPriority
  asset_id?: string
  location_id?: string
}

export const listRequests = (params: ListRequestsParams = {}) =>
  http.get<RequestRead[]>('/requests', { params }).then((r) => r.data)
export const getRequest = (id: string) =>
  http.get<RequestRead>(`/requests/${id}`).then((r) => r.data)
export const createRequest = (p: RequestCreate) =>
  http.post<RequestRead>('/requests', p).then((r) => r.data)
export const updateRequest = (id: string, p: RequestUpdate) =>
  http.patch<RequestRead>(`/requests/${id}`, p).then((r) => r.data)
export const deleteRequest = (id: string) => http.delete(`/requests/${id}`).then(() => undefined)
export const approveRequest = (id: string, p: RequestApprove = {}) =>
  http.post<RequestRead>(`/requests/${id}/approve`, p).then((r) => r.data)
export const rejectRequest = (id: string, p: RequestReason) =>
  http.post<RequestRead>(`/requests/${id}/reject`, p).then((r) => r.data)
export const cancelRequest = (id: string, p: RequestReason) =>
  http.post<RequestRead>(`/requests/${id}/cancel`, p).then((r) => r.data)
export const listRequestActivities = (id: string) =>
  http.get<ActivityRead[]>(`/requests/${id}/activities`).then((r) => r.data)
export const addRequestComment = (id: string, p: CommentCreate) =>
  http.post<ActivityRead>(`/requests/${id}/activities`, p).then((r) => r.data)
```

`src/api/preventiveMaintenances.ts`：
```typescript
import { http } from './http'
import type {
  PMRead,
  PMCreate,
  PMUpdate,
  ActivityRead,
  CommentCreate,
} from '@/types/maintenance'

export interface ListPMsParams {
  is_enabled?: boolean
  asset_id?: string
  location_id?: string
}

export const listPMs = (params: ListPMsParams = {}) =>
  http.get<PMRead[]>('/preventive-maintenances', { params }).then((r) => r.data)
export const getPM = (id: string) =>
  http.get<PMRead>(`/preventive-maintenances/${id}`).then((r) => r.data)
export const createPM = (p: PMCreate) =>
  http.post<PMRead>('/preventive-maintenances', p).then((r) => r.data)
export const updatePM = (id: string, p: PMUpdate) =>
  http.patch<PMRead>(`/preventive-maintenances/${id}`, p).then((r) => r.data)
export const deletePM = (id: string) =>
  http.delete(`/preventive-maintenances/${id}`).then(() => undefined)
export const enablePM = (id: string) =>
  http.post<PMRead>(`/preventive-maintenances/${id}/enable`).then((r) => r.data)
export const disablePM = (id: string) =>
  http.post<PMRead>(`/preventive-maintenances/${id}/disable`).then((r) => r.data)
export const generatePM = (id: string) =>
  http.post(`/preventive-maintenances/${id}/generate`).then((r) => r.data)
export const listPMActivities = (id: string) =>
  http.get<ActivityRead[]>(`/preventive-maintenances/${id}/activities`).then((r) => r.data)
export const addPMComment = (id: string, p: CommentCreate) =>
  http.post<ActivityRead>(`/preventive-maintenances/${id}/comments`, p).then((r) => r.data)
```
> 注：`enablePM`/`disablePM`/`generatePM` 测试断言 `post` 仅以 path 调用（无 body）。

`src/api/meters.ts`：
```typescript
import { http } from './http'
import type {
  MeterRead,
  MeterCreate,
  MeterUpdate,
  MeterReadingRead,
  MeterReadingCreate,
  ReadingResult,
  TriggerRead,
  TriggerCreate,
  TriggerUpdate,
} from '@/types/maintenance'

export interface ListMetersParams {
  asset_id?: string
  location_id?: string
}

export const listMeters = (params: ListMetersParams = {}) =>
  http.get<MeterRead[]>('/meters', { params }).then((r) => r.data)
export const getMeter = (id: string) => http.get<MeterRead>(`/meters/${id}`).then((r) => r.data)
export const createMeter = (p: MeterCreate) =>
  http.post<MeterRead>('/meters', p).then((r) => r.data)
export const updateMeter = (id: string, p: MeterUpdate) =>
  http.patch<MeterRead>(`/meters/${id}`, p).then((r) => r.data)
export const deleteMeter = (id: string) => http.delete(`/meters/${id}`).then(() => undefined)

export const listReadings = (meterId: string) =>
  http.get<MeterReadingRead[]>(`/meters/${meterId}/readings`).then((r) => r.data)
export const submitReading = (meterId: string, p: MeterReadingCreate) =>
  http.post<ReadingResult>(`/meters/${meterId}/readings`, p).then((r) => r.data)

export const listTriggers = (meterId: string) =>
  http.get<TriggerRead[]>(`/meters/${meterId}/triggers`).then((r) => r.data)
export const createTrigger = (meterId: string, p: TriggerCreate) =>
  http.post<TriggerRead>(`/meters/${meterId}/triggers`, p).then((r) => r.data)
export const updateTrigger = (meterId: string, triggerId: string, p: TriggerUpdate) =>
  http.patch<TriggerRead>(`/meters/${meterId}/triggers/${triggerId}`, p).then((r) => r.data)
export const deleteTrigger = (meterId: string, triggerId: string) =>
  http.delete(`/meters/${meterId}/triggers/${triggerId}`).then(() => undefined)
export const enableTrigger = (meterId: string, triggerId: string) =>
  http.post<TriggerRead>(`/meters/${meterId}/triggers/${triggerId}/enable`).then((r) => r.data)
export const disableTrigger = (meterId: string, triggerId: string) =>
  http.post<TriggerRead>(`/meters/${meterId}/triggers/${triggerId}/disable`).then((r) => r.data)
```

- [ ] **Step 5: `listProceduresMini` 追加到 `src/api/procedures.ts`**

先 Read 文件头部确认 `fetchProcedureList` 与 `PageResult`/`ProcedureRow` import。在文件末尾追加：
```typescript
import type { ProcedureMini } from '@/types/maintenance'

// 维护域（PM/请求审批/触发器）的 procedure 下拉源：取当前版本行，扁平为 {id,name}
export const listProceduresMini = async (): Promise<ProcedureMini[]> => {
  const page = await fetchProcedureList({ page: 1, page_size: 200 })
  return page.items.filter((p) => p.is_current).map((p) => ({ id: p.id, name: p.name }))
}
```
> 若 `fetchProcedureList` 不在本文件（实现期核对实际导出名），改用文件内既有的程序列表函数；保持返回 `ProcedureMini[]`。

- [ ] **Step 6: 占位视图**

`src/views/maintenance/RequestsView.vue`（其余两个同结构，标题分别「预防性维护」「计量」，文件名 `PreventiveMaintenancesView.vue`/`MetersView.vue`）：
```vue
<script setup lang="ts"></script>
<template><div class="page">请求</div></template>
```

- [ ] **Step 7: 路由 `src/router/index.ts` 加 3 条**

先 Read 现有 `/inventory/*` 路由块的结构与缩进，仿照在其后加入：
```typescript
  {
    path: '/maintenance/requests',
    name: 'maintenance-requests',
    component: () => import('@/views/maintenance/RequestsView.vue'),
    meta: { title: '请求', requiresAuth: true, requiredPermission: 'request.view' },
  },
  {
    path: '/maintenance/preventive-maintenances',
    name: 'maintenance-preventive-maintenances',
    component: () => import('@/views/maintenance/PreventiveMaintenancesView.vue'),
    meta: { title: '预防性维护', requiresAuth: true, requiredPermission: 'preventive_maintenance.view' },
  },
  {
    path: '/maintenance/meters',
    name: 'maintenance-meters',
    component: () => import('@/views/maintenance/MetersView.vue'),
    meta: { title: '计量', requiresAuth: true, requiredPermission: 'meter.view' },
  },
```

- [ ] **Step 8: 导航接线 `src/components/AppSidebar.vue`**

先 Read。「维护」组：把 请求/预防性维护/计量 三项改为带 path（去 `soon`）：
```typescript
      { label: '请求', path: '/maintenance/requests' },
      { label: '预防性维护', path: '/maintenance/preventive-maintenances' },
      { label: '计量', path: '/maintenance/meters' },
```
（保留「工单」`soon: true`、「资产」「位置」原样不动。）
`activeMenu` computed 增加（与已有 `/inventory/` 分支并列）：
```typescript
  if (route.path.startsWith('/maintenance/')) return route.path
```

`tests/unit/AppSidebar.spec.ts`：先 Read 现有结构（已有平台/维护/供应组断言），追加断言——「维护」组中 请求/预防性维护/计量 三项均有 `path`、无 `soon`（不渲染「即将上线」）；「工单」仍为 soon。既有断言不破。

- [ ] **Step 9: 跑绿 + 门禁**

Run: `cd frontend && npm run test && npm run typecheck && npm run lint`
Expected: PASS / 0 errors / 0 warnings。
prettier：`npx prettier --write "src/types/maintenance.ts" "src/api/requests.ts" "src/api/preventiveMaintenances.ts" "src/api/meters.ts" "src/api/procedures.ts" "src/views/maintenance/*.vue" "tests/unit/maintenanceApi.spec.ts" "src/router/index.ts" "src/components/AppSidebar.vue" "tests/unit/AppSidebar.spec.ts"`

- [ ] **Step 10: commit**

```bash
git add src/types/maintenance.ts src/api/requests.ts src/api/preventiveMaintenances.ts src/api/meters.ts src/api/procedures.ts src/views/maintenance/ src/router/index.ts src/components/AppSidebar.vue tests/unit/maintenanceApi.spec.ts tests/unit/AppSidebar.spec.ts
git commit -m "feat(fe-maintenance): api clients + types + procedures mini + routes + sidebar + placeholders

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: 请求 View（列表/过滤 + 创建编辑 + 审批指派对话框 + 驳回/取消 + 活动时间线）

**Files:** Create `src/views/maintenance/RequestsView.vue`（覆盖占位）；Test `tests/unit/RequestsView.spec.ts`

- [ ] **Step 1: 写失败测试 `tests/unit/RequestsView.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lr, gr, cr, ur, dr, ar, rr, cnr, la, addc } = vi.hoisted(() => ({
  lr: vi.fn(),
  gr: vi.fn(),
  cr: vi.fn(),
  ur: vi.fn(),
  dr: vi.fn(),
  ar: vi.fn(),
  rr: vi.fn(),
  cnr: vi.fn(),
  la: vi.fn(),
  addc: vi.fn(),
}))
vi.mock('@/api/requests', () => ({
  listRequests: lr,
  getRequest: gr,
  createRequest: cr,
  updateRequest: ur,
  deleteRequest: dr,
  approveRequest: ar,
  rejectRequest: rr,
  cancelRequest: cnr,
  listRequestActivities: la,
  addRequestComment: addc,
}))
vi.mock('@/api/assets', () => ({ listAssetsMini: vi.fn().mockResolvedValue([{ id: 'a1', name: '泵' }]) }))
vi.mock('@/api/locations', () => ({ listLocationsMini: vi.fn().mockResolvedValue([{ id: 'l1', name: '车间' }]) }))
vi.mock('@/api/users', () => ({ listUsers: vi.fn().mockResolvedValue([{ id: 'u1', name: '张三' }]) }))
vi.mock('@/api/teams', () => ({ listTeams: vi.fn().mockResolvedValue([{ id: 't1', name: '机修组' }]) }))
vi.mock('@/api/procedures', () => ({ listProceduresMini: vi.fn().mockResolvedValue([{ id: 'pr1', name: '保养SOP' }]) }))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can, user: { role_code: 'admin' } }),
}))

import RequestsView from '@/views/maintenance/RequestsView.vue'

function mountView() {
  return mount(RequestsView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

const pendingReq = {
  id: 'r1',
  custom_id: 'RQ-001',
  title: '泵漏油',
  description: '',
  priority: 'HIGH',
  due_date: null,
  asset_id: 'a1',
  location_id: 'l1',
  status: 'PENDING',
  work_order_id: null,
  resolution_note: '',
  resolved_by_user_id: null,
  resolved_at: null,
  created_at: '2026-06-01T00:00:00',
  updated_at: '2026-06-01T00:00:00',
}
const approvedReq = { ...pendingReq, id: 'r2', custom_id: 'RQ-002', status: 'APPROVED', work_order_id: 'wo1' }

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lr.mockReset().mockResolvedValue([pendingReq, approvedReq])
  gr.mockReset().mockResolvedValue(pendingReq)
  cr.mockReset().mockResolvedValue({})
  ur.mockReset().mockResolvedValue({})
  dr.mockReset().mockResolvedValue(undefined)
  ar.mockReset().mockResolvedValue({})
  rr.mockReset().mockResolvedValue({})
  cnr.mockReset().mockResolvedValue({})
  la.mockReset().mockResolvedValue([
    { id: 'ac1', activity_type: 'COMMENT', actor_user_id: 'u1', comment: '已查看', created_at: '2026-06-01T01:00:00' },
  ])
  addc.mockReset().mockResolvedValue({})
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('RequestsView', () => {
  it('加载并渲染请求 + 状态中文 + 资产名 + 已生成工单徽标', async () => {
    const w = mountView()
    await flushPromises()
    expect(lr).toHaveBeenCalled()
    expect(w.text()).toContain('RQ-001')
    expect(w.text()).toContain('泵漏油')
    expect(w.text()).toContain('待审批') // PENDING
    expect(w.text()).toContain('已批准') // APPROVED
    expect(w.text()).toContain('泵') // asset_id→name
    expect(w.text()).toContain('已生成工单') // work_order_id 存在
  })

  it('新建提交携带 title', async () => {
    const w = mountView()
    await flushPromises()
    const addBtn = w.findAll('.el-button').find((b) => b.text() === '新建请求')
    await addBtn!.trigger('click')
    await flushPromises()
    const titleInput = document.querySelector(
      '.el-dialog input[placeholder="请输入标题"]',
    ) as HTMLInputElement
    titleInput.value = '电机异响'
    titleInput.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cr).toHaveBeenCalled()
    expect(cr.mock.calls[0][0]).toMatchObject({ title: '电机异响' })
  })

  it('审批指派对话框提交调 approveRequest 带指派', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    vm.openApprove(pendingReq)
    await flushPromises()
    vm.approveForm.primary_user_id = 'u1'
    vm.approveForm.assignee_ids = ['u1']
    vm.approveForm.team_ids = ['t1']
    await flushPromises()
    const confirmBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '批准并生成工单',
    ) as HTMLElement
    confirmBtn.click()
    await flushPromises()
    expect(ar).toHaveBeenCalled()
    expect(ar.mock.calls[0][0]).toBe('r1')
    expect(ar.mock.calls[0][1]).toMatchObject({
      primary_user_id: 'u1',
      assignee_ids: ['u1'],
      team_ids: ['t1'],
    })
  })

  it('驳回经 prompt 调 rejectRequest 带 reason', async () => {
    const { ElMessageBox } = await import('element-plus')
    vi.spyOn(ElMessageBox, 'prompt').mockResolvedValue({ value: '信息不足' } as never)
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    await vm.handleReject(pendingReq)
    await flushPromises()
    expect(rr).toHaveBeenCalledWith('r1', { reason: '信息不足' })
  })

  it('无权限隐藏新建按钮', async () => {
    authState.can = false
    const w = mountView()
    await flushPromises()
    expect(w.findAll('.el-button').find((b) => b.text() === '新建请求')).toBeFalsy()
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- RequestsView` → FAIL。

- [ ] **Step 3: 实现 `src/views/maintenance/RequestsView.vue`**

`<script setup lang="ts">`，仿 `PurchaseOrdersView.vue` 结构：
- import：vue `ref/reactive/computed/onMounted`；`ElMessage/ElMessageBox`；`@/api/requests` 全部函数；`listAssetsMini`、`listLocationsMini`、`listUsers`、`listTeams`、`listProceduresMini`、`useAuthStore`、`formatDate`/`formatDateTime`、types。
- 常量映射：
  ```typescript
  const PRIORITY_LABELS: Record<WorkOrderPriority, string> = { NONE: '无', LOW: '低', MEDIUM: '中', HIGH: '高' }
  const STATUS_LABELS: Record<RequestStatus, string> = { PENDING: '待审批', APPROVED: '已批准', REJECTED: '已驳回', CANCELED: '已取消' }
  const STATUS_TAG: Record<RequestStatus, string> = { PENDING: 'warning', APPROVED: 'success', REJECTED: 'danger', CANCELED: 'info' }
  const STATUS_OPTIONS = (Object.keys(STATUS_LABELS) as RequestStatus[]).map((v) => ({ value: v, label: STATUS_LABELS[v] }))
  const PRIORITY_OPTIONS = (Object.keys(PRIORITY_LABELS) as WorkOrderPriority[]).map((v) => ({ value: v, label: PRIORITY_LABELS[v] }))
  ```
- state：`requests = ref<RequestRead[]>([])`、`assetsMini`、`locationsMini`、`users`、`teams`、`procedures`、`loading`；过滤 `filterStatus = ref<RequestStatus | ''>('')`、`filterPriority = ref<WorkOrderPriority | ''>('')`、`filterAsset = ref('')`、`filterLocation = ref('')`。
- 编辑/创建 dialog：`dialogVisible`、`dialogMode:'create'|'edit'`、`editingId`、`submitting`、`form = reactive<{title,description,priority,due_date,asset_id,location_id}>`（priority 默认 'NONE'，due_date 默认 null，asset_id/location_id 默认 null）。
- 审批对话框：`approveVisible = ref(false)`、`approvingId = ref('')`、`approveSubmitting`、`approveForm = reactive<{primary_user_id,assignee_ids,team_ids,procedure_id,note}>`（primary_user_id/procedure_id 默认 null，数组默认 []，note 默认 ''）。
- 详情/活动：`activityVisible = ref(false)`、`activities = ref<ActivityRead[]>([])`、`activeReqId = ref('')`、`commentText = ref('')`。
- 映射：`assetName(id)`、`locationName(id)`、`userName(id)`（查 users，'—'）。
- `fetchRequests`：构造 params（仅非空键），loading try/finally。`onMounted` 并行 `Promise.all([fetchRequests(), fetchAssetsMini(), fetchLocationsMini(), fetchUsers(), fetchTeams(), fetchProcedures()])`。过滤器 `@change="fetchRequests"`。
- 列表表格列：编号(custom_id)、标题、优先级(`PRIORITY_LABELS[row.priority]`)、状态(`<el-tag :type="STATUS_TAG[row.status]">{{ STATUS_LABELS[row.status] }}</el-tag>`)、资产(`assetName`)、位置(`locationName`)、到期(`row.due_date ? formatDate(row.due_date) : '—'`)、已生成工单(`<el-tag v-if="row.work_order_id" type="info">已生成工单</el-tag>`)、操作。
- 顶部：「新建请求」`v-if="auth.hasPermission('request.create')"`；过滤 状态/优先级/资产/位置 `el-select clearable`。
- 行操作（按 status + 权限显隐）：
  - 「编辑」`v-if="row.status === 'PENDING' && auth.hasPermission('request.create')"` → `openEdit(row)`。
  - 「审批」`v-if="row.status === 'PENDING' && auth.hasPermission('request.approve')"` → `openApprove(row)`。
  - 「驳回」`v-if="row.status === 'PENDING' && auth.hasPermission('request.approve')"` → `handleReject(row)`。
  - 「取消」`v-if="row.status === 'PENDING' && auth.hasPermission('request.cancel')"` → `handleCancel(row)`。
  - 「活动」（始终，`request.view`，所有人可见此页即有 view）→ `openActivities(row)`。
  - 「删除」`v-if="auth.hasPermission('request.delete')"` → `handleDelete(row)`。
- 创建/编辑 dialog（`el-form`）：标题(必填, placeholder「请输入标题」)、描述(textarea)、优先级(`el-select` PRIORITY_OPTIONS)、到期日(`el-date-picker type="date" value-format="YYYY-MM-DD"`)、资产(`el-select clearable` assetsMini)、位置(同 locationsMini)。保存按钮「保存」。
  - `openCreate`：resetForm + mode='create' + visible。`openEdit(row)`：resetForm + `Object.assign(form, { title: row.title, description: row.description, priority: row.priority, due_date: row.due_date, asset_id: row.asset_id, location_id: row.location_id })` + mode='edit' + editingId + visible。
  - `submitForm`：校验 `form.title.trim()`（空→`ElMessage.warning('请填写标题')` 返回）；payload `{ title: form.title.trim(), description: form.description, priority: form.priority, due_date: form.due_date || null, asset_id: form.asset_id || null, location_id: form.location_id || null }`；create→`createRequest`、edit→`updateRequest(editingId.value, payload)`；try { submitting=true; ...; ElMessage.success('保存成功'); dialogVisible=false; await fetchRequests() } catch { ElMessage.error('保存失败，请重试') } finally { submitting=false }。
- 审批 dialog（`el-dialog` 标题「审批请求」）：负责人(`el-select clearable filterable` users，label=name value=id，v-model approveForm.primary_user_id)、协办人(`el-select multiple filterable` users)、团队(`el-select multiple` teams)、关联程序(`el-select clearable filterable` procedures，label=name value=id)、备注(textarea)。footer：「批准并生成工单」按钮 → `submitApprove`；「关闭」按钮（visible=false）。
  - `openApprove(row)`：重置 approveForm（primary_user_id=null、数组=[]、procedure_id=null、note=''）+ approvingId=row.id + approveVisible=true。
  - `submitApprove`：payload `{ note: approveForm.note, primary_user_id: approveForm.primary_user_id || null, assignee_ids: approveForm.assignee_ids, team_ids: approveForm.team_ids, procedure_id: approveForm.procedure_id || null }`；`try { approveSubmitting=true; await approveRequest(approvingId.value, payload); ElMessage.success('审批通过，已生成工单'); approveVisible=false; await fetchRequests() } catch { ElMessage.error('操作失败，请重试') } finally { approveSubmitting=false }`。
- `handleReject(row)`：`const { value } = await ElMessageBox.prompt('请输入驳回原因', '驳回请求', { inputType: 'textarea' }).catch(() => ({ value: undefined }))`；若 `value === undefined` 直接 return（用户取消）；`await rejectRequest(row.id, { reason: value || '' }); ElMessage.success('已驳回'); await fetchRequests()`；外层 try/catch 本地化错误。
  - > 注意：测试 spy `ElMessageBox.prompt` resolve `{ value: '信息不足' }`，期望 `rejectRequest('r1', { reason: '信息不足' })`。故 prompt 正常 resolve 时直接取 `value`。把「用户取消」用 `.catch` 转成 `{ value: undefined }` 并提前 return；正常路径 `rejectRequest(row.id, { reason: value })`（value 已是字符串）。
- `handleCancel(row)`：同 `handleReject` 结构，文案「取消原因」/「取消请求」，调 `cancelRequest(row.id, { reason: value })` → `ElMessage.success('已取消')` → fetchRequests。
- `openActivities(row)`：`activeReqId=row.id; activities.value = await listRequestActivities(row.id); commentText=''; activityVisible=true`。dialog 内 `el-timeline` over activities：每项 `el-timeline-item :timestamp="formatDateTime(a.created_at)"`，内容 `a.comment`（空则显示 a.activity_type）。底部评论输入 `el-input` + 「发表评论」按钮（`request.view`）→ `submitComment`。
  - `submitComment`：`if (!commentText.value.trim()) return; await addRequestComment(activeReqId.value, { comment: commentText.value.trim() }); commentText=''; activities.value = await listRequestActivities(activeReqId.value)`；catch 本地化。
- `handleDelete(row)`：`ElMessageBox.confirm('确认删除请求「'+row.custom_id+'」？','提示',{type:'warning'})` → `deleteRequest(row.id)` → success + fetchRequests；catch 静默。
- `defineExpose({ openApprove, approveForm, openEdit, openCreate, handleReject, handleCancel, openActivities })`（供测试驱动）。
- 模板根 `<div class="page">` + page-title + toolbar，scoped style 仿 PurchaseOrdersView。

- [ ] **Step 4: 跑绿 + 门禁** `npm run test -- RequestsView && npm run test && npm run typecheck && npm run lint`。`npx prettier --write "src/views/maintenance/RequestsView.vue" "tests/unit/RequestsView.spec.ts"`。

- [ ] **Step 5: commit**

```bash
git add src/views/maintenance/RequestsView.vue tests/unit/RequestsView.spec.ts
git commit -m "feat(fe-maintenance): requests view with approve-assign dialog, reject/cancel & activity timeline

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 预防性维护 View（排程字段 + 启用/停用/手动生成 + 活动时间线）

**Files:** Create `src/views/maintenance/PreventiveMaintenancesView.vue`（覆盖占位）；Test `tests/unit/PreventiveMaintenancesView.spec.ts`

- [ ] **Step 1: 写失败测试 `tests/unit/PreventiveMaintenancesView.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lp, gp, cp, up, dp, ep, dsp, gen, la, addc } = vi.hoisted(() => ({
  lp: vi.fn(),
  gp: vi.fn(),
  cp: vi.fn(),
  up: vi.fn(),
  dp: vi.fn(),
  ep: vi.fn(),
  dsp: vi.fn(),
  gen: vi.fn(),
  la: vi.fn(),
  addc: vi.fn(),
}))
vi.mock('@/api/preventiveMaintenances', () => ({
  listPMs: lp,
  getPM: gp,
  createPM: cp,
  updatePM: up,
  deletePM: dp,
  enablePM: ep,
  disablePM: dsp,
  generatePM: gen,
  listPMActivities: la,
  addPMComment: addc,
}))
vi.mock('@/api/assets', () => ({ listAssetsMini: vi.fn().mockResolvedValue([{ id: 'a1', name: '泵' }]) }))
vi.mock('@/api/locations', () => ({ listLocationsMini: vi.fn().mockResolvedValue([{ id: 'l1', name: '车间' }]) }))
vi.mock('@/api/users', () => ({ listUsers: vi.fn().mockResolvedValue([{ id: 'u1', name: '张三' }]) }))
vi.mock('@/api/teams', () => ({ listTeams: vi.fn().mockResolvedValue([{ id: 't1', name: '机修组' }]) }))
vi.mock('@/api/procedures', () => ({ listProceduresMini: vi.fn().mockResolvedValue([{ id: 'pr1', name: '保养SOP' }]) }))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can, user: { role_code: 'admin' } }),
}))

import PreventiveMaintenancesView from '@/views/maintenance/PreventiveMaintenancesView.vue'

function mountView() {
  return mount(PreventiveMaintenancesView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

const pm1 = {
  id: 'p1',
  custom_id: 'PM-001',
  title: '月度保养',
  description: '',
  priority: 'MEDIUM',
  asset_id: 'a1',
  location_id: 'l1',
  primary_user_id: 'u1',
  procedure_id: null,
  start_date: '2026-06-01',
  frequency_unit: 'MONTH',
  frequency_value: 1,
  next_due_date: '2026-07-01',
  is_enabled: true,
  last_generated_at: null,
  last_work_order_id: 'wo1',
  assignee_ids: [],
  team_ids: [],
  created_at: '2026-06-01T00:00:00',
  updated_at: '2026-06-01T00:00:00',
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lp.mockReset().mockResolvedValue([pm1])
  gp.mockReset().mockResolvedValue(pm1)
  cp.mockReset().mockResolvedValue({})
  up.mockReset().mockResolvedValue({})
  dp.mockReset().mockResolvedValue(undefined)
  ep.mockReset().mockResolvedValue({})
  dsp.mockReset().mockResolvedValue({})
  gen.mockReset().mockResolvedValue({})
  la.mockReset().mockResolvedValue([])
  addc.mockReset().mockResolvedValue({})
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('PreventiveMaintenancesView', () => {
  it('加载并渲染 PM + 频率中文 + 下次到期 + 已生成工单徽标', async () => {
    const w = mountView()
    await flushPromises()
    expect(lp).toHaveBeenCalled()
    expect(w.text()).toContain('PM-001')
    expect(w.text()).toContain('月度保养')
    expect(w.text()).toContain('每 1 月') // 频率合成
    expect(w.text()).toContain('2026-07-01') // next_due_date
    expect(w.text()).toContain('已生成工单') // last_work_order_id
  })

  it('新建提交携带 title + 排程字段', async () => {
    const w = mountView()
    await flushPromises()
    const addBtn = w.findAll('.el-button').find((b) => b.text() === '新建预防性维护')
    await addBtn!.trigger('click')
    await flushPromises()
    const vm = w.vm as any
    vm.form.title = '周度点检'
    vm.form.start_date = '2026-06-10'
    vm.form.frequency_unit = 'WEEK'
    vm.form.frequency_value = 2
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cp).toHaveBeenCalled()
    expect(cp.mock.calls[0][0]).toMatchObject({
      title: '周度点检',
      start_date: '2026-06-10',
      frequency_unit: 'WEEK',
      frequency_value: 2,
    })
  })

  it('手动生成经确认调 generatePM', async () => {
    const { ElMessageBox } = await import('element-plus')
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    await vm.handleGenerate(pm1)
    await flushPromises()
    expect(gen).toHaveBeenCalledWith('p1')
  })

  it('停用调 disablePM（当前启用，toggle 不弹确认）', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    await vm.toggleEnabled(pm1)
    await flushPromises()
    expect(dsp).toHaveBeenCalledWith('p1')
  })

  it('无权限隐藏新建按钮', async () => {
    authState.can = false
    const w = mountView()
    await flushPromises()
    expect(w.findAll('.el-button').find((b) => b.text() === '新建预防性维护')).toBeFalsy()
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- PreventiveMaintenancesView` → FAIL。

- [ ] **Step 3: 实现 `src/views/maintenance/PreventiveMaintenancesView.vue`**

仿 RequestsView/PurchaseOrdersView 结构，delta：
- import：`@/api/preventiveMaintenances` 全部；`listAssetsMini`、`listLocationsMini`、`listUsers`、`listTeams`、`listProceduresMini`、`useAuthStore`、`formatDate`/`formatDateTime`、types。
- 常量：`PRIORITY_LABELS`/`PRIORITY_OPTIONS`（同 Task 2）；`FREQUENCY_LABELS: Record<PMFrequencyUnit,string> = { DAY: '天', WEEK: '周', MONTH: '月' }`；`FREQUENCY_OPTIONS`。`frequencyText(pm)`：``每 ${pm.frequency_value} ${FREQUENCY_LABELS[pm.frequency_unit]}``。
- state：`pms = ref<PMRead[]>([])`、`assetsMini`、`locationsMini`、`users`、`teams`、`procedures`、`loading`；过滤 `filterEnabled = ref<'' | 'true' | 'false'>('')`、`filterAsset`、`filterLocation`。dialog state + `form = reactive<{title,description,priority,asset_id,location_id,primary_user_id,procedure_id,start_date,frequency_unit,frequency_value,assignee_ids,team_ids}>`（priority 'NONE'，asset/location/primary/procedure null，start_date ''，frequency_unit 'MONTH'，frequency_value 1，数组 []）。
- 活动 dialog（同 Task 2 结构，调 `listPMActivities`/`addPMComment`）。
- 映射：`assetName`/`locationName`/`userName`。
- `fetchPMs`：params 仅非空键（filterEnabled 转 boolean：`if (filterEnabled.value) params.is_enabled = filterEnabled.value === 'true'`）。onMounted 并行拉全部。过滤器 `@change="fetchPMs"`。
- 列表列：编号、标题、资产(assetName)、位置(locationName)、频率(`frequencyText(row)`)、下次到期(`row.next_due_date`)、状态(`<el-tag :type="row.is_enabled ? 'success' : 'info'">{{ row.is_enabled ? '启用' : '停用' }}</el-tag>`)、已生成工单(`<el-tag v-if="row.last_work_order_id" type="info">已生成工单</el-tag>`)、操作。
- 顶部：「新建预防性维护」`preventive_maintenance.create`；过滤 启用状态(options 启用/停用)/资产/位置。
- 行操作：「编辑」`preventive_maintenance.edit` → openEdit；「启用/停用」（按 is_enabled 显示文案，`preventive_maintenance.edit`）→ `toggleEnabled`；「手动生成」`preventive_maintenance.create` → `handleGenerate`；「活动」→ openActivities；「删除」`preventive_maintenance.delete`。
- dialog（`el-form`）：标题(必填 placeholder「请输入标题」)、描述、优先级、资产(clearable)、位置(clearable)、负责人(`el-select clearable filterable` users)、协办人(`el-select multiple filterable` users)、团队(`el-select multiple` teams)、关联程序(`el-select clearable filterable` procedures)、首期日(`el-date-picker type="date" value-format="YYYY-MM-DD"`)、频率单位(`el-select` FREQUENCY_OPTIONS)、频率值(`el-input-number :min="1"`)。编辑模式额外只读展示「下次到期：{{ editingNextDue }}」。保存「保存」。
- `openCreate`/`openEdit(row)`：openEdit 逐字段回填 + 数组深拷贝 `[...row.assignee_ids]`/`[...row.team_ids]` + `editingNextDue.value = row.next_due_date`。
- `submitForm`：校验 `form.title.trim()` 与 `form.start_date`（空→warning 返回）；payload 含全部字段（`title: form.title.trim()`、`frequency_value: Number(form.frequency_value)`，关联 id `|| null`，数组照传）；create→`createPM`、edit→`updatePM(editingId.value, payload)`；try/catch/finally 本地化。
- `toggleEnabled(row)`：`row.is_enabled ? await disablePM(row.id) : await enablePM(row.id)`；`ElMessage.success(row.is_enabled ? '已停用' : '已启用')`；await fetchPMs；外层 try/catch 本地化。
  - > 测试：pm1.is_enabled=true，`toggleEnabled(pm1)` 期望调 `disablePM('p1')`。
- `handleGenerate(row)`：`const ok = await ElMessageBox.confirm('确认按此 PM 立即生成一张工单？','提示',{type:'warning'}).catch(()=>'__cancel__'); if (ok === '__cancel__') return; await generatePM(row.id); ElMessage.success('已生成工单'); await fetchPMs()`；外层 try/catch 本地化 `ElMessage.error('操作失败，请重试')`。（测试已 spy `ElMessageBox.confirm` resolve，故走 generate 分支。）
- `handleDelete(row)`：confirm「确认删除预防性维护「custom_id」？」→ deletePM → fetchPMs；catch 静默。
- `openActivities`/`submitComment`：同 Task 2（调 listPMActivities/addPMComment）。
- `defineExpose({ openCreate, openEdit, form, handleGenerate, toggleEnabled, openActivities })`。
- 模板根 `.page` + scoped style。
- > `toggleEnabled` 不弹确认（直接调 enable/disable）；`handleGenerate` 弹确认后再生成。测试对应用例已分别处理（generate 用例 spy confirm，toggle 用例无）。

- [ ] **Step 4: 跑绿 + 门禁** `npm run test -- PreventiveMaintenancesView && npm run test && npm run typecheck && npm run lint`。`npx prettier --write "src/views/maintenance/PreventiveMaintenancesView.vue" "tests/unit/PreventiveMaintenancesView.spec.ts"`。

- [ ] **Step 5: commit**

```bash
git add src/views/maintenance/PreventiveMaintenancesView.vue tests/unit/PreventiveMaintenancesView.spec.ts
git commit -m "feat(fe-maintenance): preventive maintenance view with scheduling, enable/generate & activity timeline

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: 计量 View + 触发器嵌套对话框（宽详情对话框：读数历史 + 快速录入 + 触发器子表）

**Files:**
- Create: `src/components/maintenance/MeterTriggerDialog.vue`
- Create: `src/views/maintenance/MetersView.vue`（覆盖占位）
- Test: `tests/unit/MeterTriggerDialog.spec.ts`、`tests/unit/MetersView.spec.ts`

### 4A 触发器嵌套对话框

- [ ] **Step 1: 写失败测试 `tests/unit/MeterTriggerDialog.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { ct, ut } = vi.hoisted(() => ({ ct: vi.fn(), ut: vi.fn() }))
vi.mock('@/api/meters', () => ({ createTrigger: ct, updateTrigger: ut }))
vi.mock('@/api/users', () => ({ listUsers: vi.fn().mockResolvedValue([{ id: 'u1', name: '张三' }]) }))
vi.mock('@/api/teams', () => ({ listTeams: vi.fn().mockResolvedValue([{ id: 't1', name: '机修组' }]) }))
vi.mock('@/api/procedures', () => ({ listProceduresMini: vi.fn().mockResolvedValue([{ id: 'pr1', name: '保养SOP' }]) }))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({ useAuthStore: () => ({ hasPermission: () => authState.can }) }))

import MeterTriggerDialog from '@/components/maintenance/MeterTriggerDialog.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  ct.mockReset().mockResolvedValue({})
  ut.mockReset().mockResolvedValue({})
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('MeterTriggerDialog', () => {
  it('新增提交调 createTrigger 带 meterId + 字段', async () => {
    const w = mount(MeterTriggerDialog, {
      props: { visible: true, meterId: 'm1', editing: null },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    const vm = w.vm as any
    vm.form.name = '高温触发'
    vm.form.comparator = 'MORE_THAN'
    vm.form.threshold = '80'
    vm.form.title = '降温处理'
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(ct).toHaveBeenCalled()
    expect(ct.mock.calls[0][0]).toBe('m1')
    expect(ct.mock.calls[0][1]).toMatchObject({
      name: '高温触发',
      comparator: 'MORE_THAN',
      threshold: '80',
      title: '降温处理',
    })
    expect(w.emitted('saved')).toBeTruthy()
  })

  it('编辑模式提交调 updateTrigger', async () => {
    const editing = {
      id: 't1',
      meter_id: 'm1',
      name: '高温',
      comparator: 'MORE_THAN',
      threshold: '80',
      is_armed: true,
      is_enabled: true,
      priority: 'HIGH',
      title: '降温',
      description: '',
      primary_user_id: null,
      procedure_id: null,
      last_triggered_at: null,
      last_work_order_id: null,
      assignee_ids: [],
      team_ids: [],
    }
    const w = mount(MeterTriggerDialog, {
      props: { visible: true, meterId: 'm1', editing },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    const vm = w.vm as any
    vm.form.threshold = '90'
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(ut).toHaveBeenCalled()
    expect(ut.mock.calls[0][0]).toBe('m1')
    expect(ut.mock.calls[0][1]).toBe('t1')
    expect(ut.mock.calls[0][2]).toMatchObject({ threshold: '90' })
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- MeterTriggerDialog` → FAIL。

- [ ] **Step 3: 实现 `src/components/maintenance/MeterTriggerDialog.vue`**

`<script setup lang="ts">`：
- props：`visible: boolean`、`meterId: string`、`editing: TriggerRead | null`。emits：`update:visible`、`saved`。
- import：`createTrigger`/`updateTrigger`、`listUsers`/`listTeams`/`listProceduresMini`、`useAuthStore`、types、`ElMessage`。
- 常量：`COMPARATOR_OPTIONS = [{ value: 'LESS_THAN', label: '小于' }, { value: 'MORE_THAN', label: '大于' }]`；`PRIORITY_OPTIONS`（同前）。
- state：`users`/`teams`/`procedures`、`submitting`、`form = reactive<{name,comparator,threshold,priority,title,description,primary_user_id,procedure_id,assignee_ids,team_ids}>`（comparator 'MORE_THAN'，threshold ''，priority 'NONE'，title ''，description ''，primary/procedure null，数组 []）。
  - > 注：后端 `TriggerCreate` **无 `is_enabled` 字段**（启用/停用经独立 `/enable`·`/disable` 端点，在 MetersView 触发器子表行操作里做）；新建触发器默认启用。故本对话框**不放启用开关**、payload 不含 is_enabled。`title`（生单标题）后端**必填**。
- `watch(() => props.visible, (v) => { if (v) { fetchOptions(); resetOrFill() } }, { immediate: true })`：打开时拉 users/teams/procedures，并按 `props.editing` 回填或重置 form。
  - `resetOrFill`：editing 为 null→重置默认；否则逐字段回填（name/comparator/threshold/priority/title/description/primary_user_id/procedure_id）+ 数组深拷贝 `[...editing.assignee_ids]`/`[...editing.team_ids]`。
- 模板：`el-dialog :model-value="visible" @update:model-value="(v)=>emit('update:visible',v)" title="触发器" width="640px"` 内 `el-form`：名称(必填 placeholder「请输入触发器名称」)、比较符(`el-select` COMPARATOR_OPTIONS)、阈值(`el-input` placeholder「阈值」)、优先级、生单标题(必填 placeholder「触发时生成的工单标题」)、描述(textarea)、负责人(`el-select clearable filterable` users)、协办人(multiple)、团队(multiple)、关联程序(clearable filterable procedures)。footer：「保存」→ submitForm、「取消」→ emit update:visible false。
- `submitForm`：校验 `form.name.trim()`、`form.threshold`、`form.title.trim()`（任一空→`ElMessage.warning('请填写名称、阈值与生单标题')` 返回）；payload `{ name: form.name.trim(), comparator: form.comparator, threshold: form.threshold, priority: form.priority, title: form.title.trim(), description: form.description, primary_user_id: form.primary_user_id || null, procedure_id: form.procedure_id || null, assignee_ids: form.assignee_ids, team_ids: form.team_ids }`；`props.editing ? updateTrigger(props.meterId, props.editing.id, payload) : createTrigger(props.meterId, payload)`；成功 `ElMessage.success('保存成功')` + `emit('saved')` + `emit('update:visible', false)`；try/catch 本地化 `ElMessage.error('保存失败，请重试')`，finally submitting=false。
- `defineExpose({ form, submitForm })`（供测试驱动）。

### 4B 计量 View

- [ ] **Step 4: 写失败测试 `tests/unit/MetersView.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lm, gm, cm, um, dm, lrd, sr, lt, et, dt2 } = vi.hoisted(() => ({
  lm: vi.fn(),
  gm: vi.fn(),
  cm: vi.fn(),
  um: vi.fn(),
  dm: vi.fn(),
  lrd: vi.fn(),
  sr: vi.fn(),
  lt: vi.fn(),
  et: vi.fn(),
  dt2: vi.fn(),
}))
vi.mock('@/api/meters', () => ({
  listMeters: lm,
  getMeter: gm,
  createMeter: cm,
  updateMeter: um,
  deleteMeter: dm,
  listReadings: lrd,
  submitReading: sr,
  listTriggers: lt,
  createTrigger: vi.fn(),
  updateTrigger: vi.fn(),
  deleteTrigger: vi.fn(),
  enableTrigger: et,
  disableTrigger: dt2,
}))
vi.mock('@/api/assets', () => ({ listAssetsMini: vi.fn().mockResolvedValue([{ id: 'a1', name: '泵' }]) }))
vi.mock('@/api/locations', () => ({ listLocationsMini: vi.fn().mockResolvedValue([{ id: 'l1', name: '车间' }]) }))
vi.mock('@/api/users', () => ({ listUsers: vi.fn().mockResolvedValue([{ id: 'u1', name: '张三' }]) }))
vi.mock('@/api/teams', () => ({ listTeams: vi.fn().mockResolvedValue([{ id: 't1', name: '机修组' }]) }))
vi.mock('@/api/procedures', () => ({ listProceduresMini: vi.fn().mockResolvedValue([]) }))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can, user: { role_code: 'admin' } }),
}))

import MetersView from '@/views/maintenance/MetersView.vue'

function mountView() {
  return mount(MetersView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

const meter1 = {
  id: 'm1',
  custom_id: 'MTR-001',
  name: '油位计',
  unit: '小时',
  update_frequency_days: 30,
  asset_id: 'a1',
  location_id: 'l1',
  created_at: '2026-06-01T00:00:00',
  updated_at: '2026-06-01T00:00:00',
}
const reading1 = { id: 'rd1', meter_id: 'm1', value: '120.0000', reading_at: '2026-06-02T00:00:00', recorded_by_user_id: 'u1' }
const trigger1 = {
  id: 'tg1',
  meter_id: 'm1',
  name: '高位',
  comparator: 'MORE_THAN',
  threshold: '100',
  is_armed: true,
  is_enabled: true,
  priority: 'HIGH',
  title: '排油',
  description: '',
  primary_user_id: null,
  procedure_id: null,
  last_triggered_at: null,
  last_work_order_id: null,
  assignee_ids: [],
  team_ids: [],
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lm.mockReset().mockResolvedValue([meter1])
  gm.mockReset().mockResolvedValue(meter1)
  cm.mockReset().mockResolvedValue({})
  um.mockReset().mockResolvedValue({})
  dm.mockReset().mockResolvedValue(undefined)
  lrd.mockReset().mockResolvedValue([reading1])
  sr.mockReset().mockResolvedValue({ reading: reading1, generated_work_order_ids: ['wo9'] })
  lt.mockReset().mockResolvedValue([trigger1])
  et.mockReset().mockResolvedValue({})
  dt2.mockReset().mockResolvedValue({})
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('MetersView', () => {
  it('加载并渲染计量行 + 名称/单位/资产名', async () => {
    const w = mountView()
    await flushPromises()
    expect(lm).toHaveBeenCalled()
    expect(w.text()).toContain('MTR-001')
    expect(w.text()).toContain('油位计')
    expect(w.text()).toContain('小时')
    expect(w.text()).toContain('泵') // asset
  })

  it('新建提交携带 name', async () => {
    const w = mountView()
    await flushPromises()
    const addBtn = w.findAll('.el-button').find((b) => b.text() === '新建计量')
    await addBtn!.trigger('click')
    await flushPromises()
    const nameInput = document.querySelector(
      '.el-dialog input[placeholder="请输入名称"]',
    ) as HTMLInputElement
    nameInput.value = '温度计'
    nameInput.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cm).toHaveBeenCalled()
    expect(cm.mock.calls[0][0]).toMatchObject({ name: '温度计' })
  })

  it('打开详情拉读数与触发器', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    await vm.openDetail(meter1)
    await flushPromises()
    expect(gm).toHaveBeenCalledWith('m1')
    expect(lrd).toHaveBeenCalledWith('m1')
    expect(lt).toHaveBeenCalledWith('m1')
    expect(document.body.textContent).toContain('120') // reading value
    expect(document.body.textContent).toContain('高位') // trigger name
  })

  it('提交读数调 submitReading 并提示触发工单', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    await vm.openDetail(meter1)
    await flushPromises()
    vm.readingValue = '150'
    await vm.handleSubmitReading()
    await flushPromises()
    expect(sr).toHaveBeenCalled()
    expect(sr.mock.calls[0][0]).toBe('m1')
    expect(sr.mock.calls[0][1]).toMatchObject({ value: '150' })
  })

  it('无权限隐藏新建按钮', async () => {
    authState.can = false
    const w = mountView()
    await flushPromises()
    expect(w.findAll('.el-button').find((b) => b.text() === '新建计量')).toBeFalsy()
  })
})
```

- [ ] **Step 5: 跑红** `npm run test -- MetersView` → FAIL。

- [ ] **Step 6: 实现 `src/views/maintenance/MetersView.vue`**

仿 PurchaseOrdersView（列表 + 宽详情对话框 + defineExpose），核心 delta：
- import：`@/api/meters` 全部 + `listAssetsMini`/`listLocationsMini`/`listUsers`/`listProceduresMini`、`MeterTriggerDialog`、`useAuthStore`、`formatDateTime`、types。
- 常量：`COMPARATOR_LABELS: Record<MeterComparator,string> = { LESS_THAN: '小于', MORE_THAN: '大于' }`；`PRIORITY_LABELS`。
- state：`meters = ref<MeterRead[]>([])`、`assetsMini`、`locationsMini`、`users`、`loading`；过滤 `filterAsset`、`filterLocation`。
- 创建/编辑 dialog（基本信息）：`metaVisible`、`metaMode:'create'|'edit'`、`editingId`、`metaSubmitting`、`metaForm = reactive<{name,unit,update_frequency_days,asset_id,location_id}>`（name ''，unit ''，update_frequency_days null，asset/location null）。
- 详情 dialog：`detailVisible`、`detailMeter = ref<MeterRead | null>(null)`、`readings = ref<MeterReadingRead[]>([])`、`triggers = ref<TriggerRead[]>([])`、`readingValue = ref('')`、`readingAt = ref<string | null>(null)`、`readingSubmitting`；触发器嵌套 `triggerDialogVisible = ref(false)`、`editingTrigger = ref<TriggerRead | null>(null)`。
- 映射：`assetName`/`locationName`/`userName`。
- `fetchMeters`：params 仅非空键，loading try/finally。onMounted 并行 `Promise.all([fetchMeters(), fetchAssetsMini(), fetchLocationsMini(), fetchUsers()])`。过滤 `@change`。
- 列表列：编号、名称、单位、资产(assetName)、位置(locationName)、推荐频率(`row.update_frequency_days ?? '—'`)、操作（详情/编辑、删除）。
- 顶部：「新建计量」`meter.create`；过滤 资产/位置。
- 基本信息 dialog：名称(必填 placeholder「请输入名称」)、单位、推荐更新频率天数(`el-input-number :min="0"` 可空)、资产(clearable)、位置(clearable)。保存「保存」。
  - `openCreate`/`openEdit(row)`：仿既有；`submitMeta` 校验 name.trim()；payload `{ name: metaForm.name.trim(), unit: metaForm.unit, update_frequency_days: metaForm.update_frequency_days, asset_id: metaForm.asset_id || null, location_id: metaForm.location_id || null }`；create→createMeter、edit→updateMeter；try/catch/finally；成功后 fetchMeters。
- **宽详情对话框（`el-dialog width="900px"` 标题「计量详情」）**三分区（`el-divider content-position="left"`）：
  1. **基本信息**：只读展示 名称/单位/资产/位置/推荐频率（或提供「编辑」入口走 openEdit）。
  2. **读数历史**：快速录入行（`reading.create` 才显示）：`el-input v-model="readingValue"` placeholder「读数值」 + `el-date-picker v-model="readingAt" type="datetime"` 可空（占位「默认现在」）+ 「提交读数」按钮 → `handleSubmitReading`。下方只读 `el-table :data="readings"`：值(value)、时间(`formatDateTime(reading_at)`)、记录人(`userName(recorded_by_user_id)`)。
  3. **触发器**：`el-table :data="triggers"`：名称、比较(`COMPARATOR_LABELS[row.comparator]`)、阈值(threshold)、优先级(`PRIORITY_LABELS[row.priority]`)、启用(`<el-tag :type="row.is_enabled ? 'success':'info'">{{ row.is_enabled?'启用':'停用' }}</el-tag>`)、武装(`<el-tag :type="row.is_armed?'warning':'info'">{{ row.is_armed?'武装':'已触发' }}</el-tag>`)、操作（编辑 `meter.edit`、启用/停用 `meter.edit`、删除 `meter.delete`）。底部「新增触发器」`meter.create` → 打开 `MeterTriggerDialog`（create 模式）。
- `openDetail(row)`：`detailMeter.value = await getMeter(row.id)`；`readings.value = await listReadings(row.id)`；`triggers.value = await listTriggers(row.id)`；`readingValue=''; readingAt=null; detailVisible=true`。try/catch 本地化「加载计量详情失败，请重试」，失败不开窗。
- `handleSubmitReading`：`if (!readingValue.value.trim()) { ElMessage.warning('请输入读数值'); return }`；`const res = await submitReading(detailMeter.value!.id, { value: readingValue.value.trim(), reading_at: readingAt.value || null })`；`if (res.generated_work_order_ids.length) ElMessage.success(`本次读数触发 ${res.generated_work_order_ids.length} 张工单`) else ElMessage.success('读数已记录')`；`readingValue=''; readingAt=null`；刷新 `readings.value = await listReadings(...)` 与 `triggers.value = await listTriggers(...)`（is_armed 可能变）；try/catch 本地化 `ElMessage.error('提交失败，请重试')`，finally readingSubmitting=false。
- 触发器行操作：
  - `openTriggerCreate()`：`editingTrigger.value = null; triggerDialogVisible.value = true`。
  - `openTriggerEdit(t)`：`editingTrigger.value = t; triggerDialogVisible.value = true`。
  - `onTriggerSaved()`（监听 dialog `@saved`）：`triggers.value = await listTriggers(detailMeter.value!.id)`。
  - `toggleTrigger(t)`：`t.is_enabled ? await disableTrigger(meterId, t.id) : await enableTrigger(meterId, t.id)`；刷新 triggers；try/catch 本地化。
  - `deleteTriggerRow(t)`：confirm「确认删除触发器「t.name」？」→ `deleteTrigger(meterId, t.id)` → 刷新 triggers；catch 静默。（`deleteTrigger` 从 `@/api/meters` import。）
- 内嵌：`<MeterTriggerDialog v-model:visible="triggerDialogVisible" :meter-id="detailMeter?.id || ''" :editing="editingTrigger" @saved="onTriggerSaved" />`。
- `handleDelete(row)`：confirm「确认删除计量「custom_id」？」→ deleteMeter → fetchMeters；catch 静默。
- `defineExpose({ openDetail, handleSubmitReading, readingValue, openCreate, openEdit })`。
- 模板根 `.page` + scoped style（详情分区间距）。

- [ ] **Step 7: 跑绿 + 门禁** `npm run test -- MeterTriggerDialog MetersView && npm run test && npm run typecheck && npm run lint`。`npx prettier --write "src/components/maintenance/MeterTriggerDialog.vue" "src/views/maintenance/MetersView.vue" "tests/unit/MeterTriggerDialog.spec.ts" "tests/unit/MetersView.spec.ts"`。

- [ ] **Step 8: commit**

```bash
git add src/components/maintenance/MeterTriggerDialog.vue src/views/maintenance/MetersView.vue tests/unit/MeterTriggerDialog.spec.ts tests/unit/MetersView.spec.ts
git commit -m "feat(fe-maintenance): meters view with readings history, quick entry & trigger sub-CRUD

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: RBAC 门控统一核对 + 收尾

**Files:** 跨 views/components（核对）；Test：跑全量

- [ ] **Step 1:** 逐文件核对写动作门控 code 与后端 `backend/app/permissions.py` 一致：
  - RequestsView：新建/编辑=`request.create`、审批/驳回=`request.approve`、取消=`request.cancel`、删除=`request.delete`、评论用 `request.view`（页面可见即有）。
  - PreventiveMaintenancesView：新建=`preventive_maintenance.create`、编辑=`preventive_maintenance.edit`、启用/停用=`preventive_maintenance.edit`、**手动生成=`preventive_maintenance.create`**、删除=`preventive_maintenance.delete`。
  - MetersView：新建=`meter.create`、编辑=`meter.edit`、删除=`meter.delete`、读数提交=`reading.create`、触发器新增=`meter.create`、触发器编辑/启用停用=`meter.edit`、触发器删除=`meter.delete`。
  - MeterTriggerDialog：保存动作不单独门控（入口已门控）。
  用 `grep -rn "hasPermission('" src/views/maintenance/ src/components/maintenance/` 列出全部，逐个对照后端常量值核实拼写；有误最小修正，否则记「无需修改」。
- [ ] **Step 2:** AppSidebar：维护组 请求/预防性维护/计量 三项 path 正确、无 soon、工单仍 soon；`activeMenu` 对 `/maintenance/*` 高亮；与 `router/index.ts` 三路由 path 一致。
- [ ] **Step 3:** 全量门禁：
  ```
  cd frontend && npm run test && npm run typecheck && npm run lint && npx prettier --check "src/**/*.{ts,vue}" "tests/**/*.ts"
  ```
  test 全绿、typecheck 0 错、lint 0 警告；prettier 关注本分支 `git diff main...HEAD --name-only` 的 .ts/.vue（预存无关脏文件不动，本分支文件须干净）。
  > 后端无改动，不跑后端门禁。
- [ ] **Step 4: commit**（若有修正）：`chore(fe-maintenance): RBAC gating audit + wrap-up`。若全部正确无改动，不造空 commit，汇报「核对通过」。

---

## 收尾

完成 T1–T5 后派发最终 code review，再用 `superpowers:finishing-a-development-branch`（合并/push 交人决定，不自动 push、不自合 main）。**本轮无 alembic 迁移**，合并 `--no-ff` 无需 down_revision 协调。

**自查清单：**
- 3 个 view 均扁平 `el-table` + `el-dialog`，组件内直调 api、`onMounted` 拉取。
- 请求：状态/优先级中文映射 + 已生成工单徽标 + 审批指派对话框(approve 带 primary/assignees/teams/procedure) + 驳回/取消 prompt(reason) + 活动时间线 + 评论。
- PM：频率中文合成 + 下次到期只读 + 启用/停用(toggle) + 手动生成(confirm→generate) + 活动时间线；排程字段(start_date/frequency_unit/frequency_value)提交完整。
- 计量：宽详情对话框三分区(基本信息 + 读数历史/快速录入 + 触发器子表)；读数提交按 ReadingResult.generated_work_order_ids 提示；触发器走嵌套 MeterTriggerDialog(create/edit)；is_armed 只读(武装/已触发)；启用/停用/删除触发器。
- procedure 下拉：listProceduresMini 取 is_current 行、{id,name}。
- RBAC：写动作按 hasPermission 隐藏；PM 生成=create、触发器新增=meter.create（易错点已核）。
- 导航维护组三项接入、无残留 soon(工单仍 soon)；路由 3 条 requiresAuth。
- 仅中文、无新增 locale。`npm run typecheck` 0 错、`npm run lint` 0 警告、vitest 全绿、prettier 干净。
