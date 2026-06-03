# FE-5 库存与采购前端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 库存采购 4 块前端（备件库存 / 采购单 / 供应商 / 客户）——把已就绪的备件·采购单·供应商·客户后端变成可用界面。

**Architecture:** Vue 3 `<script setup lang="ts">` + Element Plus（扁平 `el-table` 列表 + `el-dialog` 表单）+ Pinia（仅复用 `auth` store 做 RBAC 门控）+ vue-router 扁平路由。备件分类、采购单分类为页内嵌「管理分类」子组件对话框（复刻 FE-2 资产分类）。采购单用宽对话框分区（基本信息 / 可编辑明细行子表 / 活动时间线 + 状态流转）。**纯前端，无后端改动、无迁移。**

**Tech Stack:** Vite + TS + Element Plus + Pinia + vue-router + vitest + `@vue/test-utils`。门禁：`npm run typecheck`（vue-tsc --noEmit）+ prettier + `npm run test`（vitest）。

**全局约定（每任务适用）：**
- 工作目录 `frontend/`；命令 `npm run ...`。分支 `feat/fe-inventory`（基于 main，spec 已提交）。
- 每任务：写测试 → 跑红 → 实现 → `npm run test` + `npm run typecheck` 绿 → prettier → commit。
- commit message 结尾附：`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- 仅中文、不做 i18n。RBAC：`const auth = useAuthStore()`；写动作按钮 `v-if="auth.hasPermission('<code>')"`（super_admin 通配）。
- 精确 `git add`，**勿纳入**仓库根未跟踪产物（`.claude/scheduled_tasks.lock`、`.verify-screenshots/*.png`）。

**既有模式参考（须遵循，FE-1/FE-2 已落定）：**
- api：`src/api/locations.ts`（`http.get<T>(path).then(r=>r.data)`；delete 用 `http.delete(path).then(()=>undefined)`；http baseURL 已含 `/api/v1`，路径写 `/parts`）。
- view：`src/views/maindata/LocationsView.vue`、`src/views/platform/UsersView.vue`（state 分区 + onMounted 并行 fetch + el-table + 单 dialog 多模式 + submitForm try/catch/finally + 本地化 `ElMessage.error('保存失败，请重试')` + `ElMessageBox.confirm` 删除 + RBAC v-if + `<style scoped>` 的 `.page`/`.page-title`/`.toolbar`）。
- 子组件对话框：`src/components/maindata/AssetCategoryManageDialog.vue`（props `visible` + emit `update:visible`/`changed`；`watch(visible,{immediate:true})` 打开拉取；嵌套表单 dialog；提交 name `trim()`；删除 `ElMessageBox.confirm`）。
- api 测试：`tests/unit/maindataApi.spec.ts`（`vi.hoisted` + `vi.mock('@/api/http')`）。
- view 测试：`tests/unit/LocationsView.spec.ts`、`AssetCategoryManageDialog.spec.ts`（`vi.mock('@/api/<x>')` + 可变 auth mock + `mount(View,{global:{plugins:[ElementPlus]},attachTo:document.body})` + `flushPromises` + `afterEach(() => { document.body.innerHTML = '' })` 清 teleport；teleported dialog 用 `document.querySelector('.el-dialog ...')`；断言定位单元格/payload，勿脆弱全文）。
- 导航：`src/components/AppSidebar.vue`（`groups`/`activeMenu` computed；「供应」组 4 项现全 `soon`：备件库存/采购单/供应商/客户）。
- 路由：`src/router/index.ts`（扁平 + `meta.requiresAuth`；`requiredPermission` 是合法 meta key）。
- 复用 api：`listUsers`（`@/api/users`，返回 `UserRead[]`，有 `name`）、`listTeams`（`@/api/teams`，`TeamRead[]`，有 `name`）、`listAssetsMini`（`@/api/assets`）、`listLocationsMini`（`@/api/locations`）。类型 `UserRead`/`TeamRead` 在 `src/types/platform.ts`。
- 工具：`src/utils/format.ts` 的 `formatDateTime`（null→兜底）。

**后端契约（已核实，types 以此为准；Decimal 字段 JSON 序列化为字符串 → 前端用 `string`）：**
- Part：`PartRead {id, custom_id, name, description, cost, quantity, min_quantity, unit, barcode|null, non_stock, is_low_stock, category_id|null, assignee_ids[], team_ids[], asset_ids[], location_ids[], pm_ids[]}`；Create 同（除 id/custom_id/is_low_stock，全可选有默认）；Update 全可选；`PartMini {id, name, custom_id}`。
- PartCategory：`{id, name, description}`；Create `{name, description?}`；Update `{name?, description?}`。
- PurchaseOrderStatus 5 值：`DRAFT/SUBMITTED/APPROVED/REJECTED/CANCELED`。
- POLine：`POLineRead {id, part_id, quantity, unit_cost, line_total}`；`POLineCreate {part_id, quantity, unit_cost?}`。
- PurchaseOrder：`PurchaseOrderRead {id, custom_id, vendor_id, status, notes, category_id|null, shipping_address, shipping_method, terms_of_payment, expected_delivery_date|null, resolution_note, resolved_by_user_id|null, resolved_at|null, lines: POLineRead[], total_cost}`；`PurchaseOrderCreate {vendor_id, notes?, category_id?|null, shipping_address?, shipping_method?, terms_of_payment?, expected_delivery_date?|null, lines?: POLineCreate[]}`；Update 全可选（lines 全量替换）；`PurchaseOrderMini {id, custom_id, vendor_id, status}`。
- POActivity：`{id, activity_type, actor_user_id|null, from_status|null, to_status|null, comment, created_at}`。POResolve body：`{note?}`。
- PurchaseOrderCategory：`{id, name, description}`；Create/Update `{name, description?}`。
- Vendor：`VendorRead {id, name, vendor_type, description, rate, address, phone, email, website, part_ids[], asset_ids[], location_ids[]}`；Create 同（除 id，全可选有默认）；Update 全可选；`VendorMini {id, name}`。
- Customer：同 Vendor + `billing_currency`（裸码字符串）；`CustomerMini {id, name}`。
- 端点（baseURL 含 /api/v1）：
  - `/parts`(GET 查询 `category_id`/`asset_id`/`low_stock`，POST)、`/parts/mini`、`/parts/{id}`(GET/PATCH/DELETE)；`/part-categories`(GET/POST)、`/part-categories/{id}`(GET/PATCH/DELETE)。
  - `/purchase-orders`(GET 查询 `status`/`vendor_id`，POST)、`/purchase-orders/mini`、`/purchase-orders/{id}`(GET/PATCH/DELETE)、`/purchase-orders/{id}/submit|approve|reject|cancel`(POST)、`/purchase-orders/{id}/activities`(GET)；`/purchase-order-categories`(GET/POST)、`/{id}`(GET/PATCH/DELETE)。
  - `/vendors`(GET 查询 `part_id`，POST)、`/vendors/mini`、`/vendors/{id}`(GET/PATCH/DELETE)。
  - `/customers`(同 vendors)、`/customers/mini`、`/customers/{id}`。
- 权限 code：`part.view/create/edit/delete`、`part_category.view/part_category.manage`、`purchase_order.view/create/edit/delete/approve`、`purchase_order_category.view/purchase_order_category.manage`、`vendor.view/create/edit/delete`、`customer.view/create/edit/delete`；关联下拉读 `asset.view`/`location.view`/`user.view`/`team.view`（门控从宽，本轮多选选择器不单独门控）。

---

## Task 1: 共享骨架（api + types + 路由 + 导航 + 占位页）

**Files:**
- Create: `src/types/inventory.ts`
- Create: `src/api/{parts,partCategories,purchaseOrders,purchaseOrderCategories,vendors,customers}.ts`
- Create: `src/views/inventory/{Parts,PurchaseOrders,Vendors,Customers}View.vue`（占位骨架）
- Modify: `src/router/index.ts`、`src/components/AppSidebar.vue`
- Test: `tests/unit/inventoryApi.spec.ts`、`tests/unit/AppSidebar.spec.ts`（追加）

- [ ] **Step 1: 写失败测试（api）`tests/unit/inventoryApi.spec.ts`**

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
  listParts,
  listPartsMini,
  createPart,
  updatePart,
  deletePart,
} from '@/api/parts'
import {
  listPartCategories,
  createPartCategory,
  updatePartCategory,
  deletePartCategory,
} from '@/api/partCategories'
import {
  listPurchaseOrders,
  getPurchaseOrder,
  createPurchaseOrder,
  updatePurchaseOrder,
  deletePurchaseOrder,
  submitPurchaseOrder,
  approvePurchaseOrder,
  rejectPurchaseOrder,
  cancelPurchaseOrder,
  listPurchaseOrderActivities,
} from '@/api/purchaseOrders'
import {
  listPurchaseOrderCategories,
  createPurchaseOrderCategory,
  updatePurchaseOrderCategory,
  deletePurchaseOrderCategory,
} from '@/api/purchaseOrderCategories'
import {
  listVendors,
  listVendorsMini,
  createVendor,
  updateVendor,
  deleteVendor,
} from '@/api/vendors'
import {
  listCustomers,
  listCustomersMini,
  createCustomer,
  updateCustomer,
  deleteCustomer,
} from '@/api/customers'

describe('inventory api', () => {
  beforeEach(() => {
    for (const m of [get, post, patch, del]) m.mockReset().mockResolvedValue({ data: [] })
  })

  // parts
  it('listParts GET /parts (no params)', async () => {
    await listParts()
    expect(get).toHaveBeenCalledWith('/parts', { params: {} })
  })
  it('listParts GET /parts low_stock', async () => {
    await listParts({ low_stock: true })
    expect(get).toHaveBeenCalledWith('/parts', { params: { low_stock: true } })
  })
  it('listPartsMini GET /parts/mini', async () => {
    await listPartsMini()
    expect(get).toHaveBeenCalledWith('/parts/mini')
  })
  it('createPart POST /parts', async () => {
    await createPart({ name: 'P' })
    expect(post).toHaveBeenCalledWith('/parts', { name: 'P' })
  })
  it('updatePart PATCH /parts/{id}', async () => {
    await updatePart('p1', { quantity: '5' })
    expect(patch).toHaveBeenCalledWith('/parts/p1', { quantity: '5' })
  })
  it('deletePart DELETE /parts/{id}', async () => {
    await deletePart('p1')
    expect(del).toHaveBeenCalledWith('/parts/p1')
  })

  // part categories
  it('listPartCategories GET /part-categories', async () => {
    await listPartCategories()
    expect(get).toHaveBeenCalledWith('/part-categories')
  })
  it('createPartCategory POST /part-categories', async () => {
    await createPartCategory({ name: 'C' })
    expect(post).toHaveBeenCalledWith('/part-categories', { name: 'C' })
  })
  it('updatePartCategory PATCH /part-categories/{id}', async () => {
    await updatePartCategory('c1', { name: 'C2' })
    expect(patch).toHaveBeenCalledWith('/part-categories/c1', { name: 'C2' })
  })
  it('deletePartCategory DELETE /part-categories/{id}', async () => {
    await deletePartCategory('c1')
    expect(del).toHaveBeenCalledWith('/part-categories/c1')
  })

  // purchase orders
  it('listPurchaseOrders GET /purchase-orders (no params)', async () => {
    await listPurchaseOrders()
    expect(get).toHaveBeenCalledWith('/purchase-orders', { params: {} })
  })
  it('listPurchaseOrders GET /purchase-orders with filters', async () => {
    await listPurchaseOrders({ status: 'DRAFT', vendor_id: 'v1' })
    expect(get).toHaveBeenCalledWith('/purchase-orders', { params: { status: 'DRAFT', vendor_id: 'v1' } })
  })
  it('getPurchaseOrder GET /purchase-orders/{id}', async () => {
    await getPurchaseOrder('po1')
    expect(get).toHaveBeenCalledWith('/purchase-orders/po1')
  })
  it('createPurchaseOrder POST /purchase-orders', async () => {
    await createPurchaseOrder({ vendor_id: 'v1', lines: [] })
    expect(post).toHaveBeenCalledWith('/purchase-orders', { vendor_id: 'v1', lines: [] })
  })
  it('updatePurchaseOrder PATCH /purchase-orders/{id}', async () => {
    await updatePurchaseOrder('po1', { notes: 'x' })
    expect(patch).toHaveBeenCalledWith('/purchase-orders/po1', { notes: 'x' })
  })
  it('deletePurchaseOrder DELETE /purchase-orders/{id}', async () => {
    await deletePurchaseOrder('po1')
    expect(del).toHaveBeenCalledWith('/purchase-orders/po1')
  })
  it('submitPurchaseOrder POST /submit', async () => {
    await submitPurchaseOrder('po1')
    expect(post).toHaveBeenCalledWith('/purchase-orders/po1/submit')
  })
  it('approvePurchaseOrder POST /approve with note', async () => {
    await approvePurchaseOrder('po1', { note: 'ok' })
    expect(post).toHaveBeenCalledWith('/purchase-orders/po1/approve', { note: 'ok' })
  })
  it('rejectPurchaseOrder POST /reject', async () => {
    await rejectPurchaseOrder('po1', { note: 'no' })
    expect(post).toHaveBeenCalledWith('/purchase-orders/po1/reject', { note: 'no' })
  })
  it('cancelPurchaseOrder POST /cancel', async () => {
    await cancelPurchaseOrder('po1', { note: '' })
    expect(post).toHaveBeenCalledWith('/purchase-orders/po1/cancel', { note: '' })
  })
  it('listPurchaseOrderActivities GET /activities', async () => {
    await listPurchaseOrderActivities('po1')
    expect(get).toHaveBeenCalledWith('/purchase-orders/po1/activities')
  })

  // purchase order categories
  it('listPurchaseOrderCategories GET /purchase-order-categories', async () => {
    await listPurchaseOrderCategories()
    expect(get).toHaveBeenCalledWith('/purchase-order-categories')
  })
  it('createPurchaseOrderCategory POST', async () => {
    await createPurchaseOrderCategory({ name: 'C' })
    expect(post).toHaveBeenCalledWith('/purchase-order-categories', { name: 'C' })
  })
  it('updatePurchaseOrderCategory PATCH /{id}', async () => {
    await updatePurchaseOrderCategory('c1', { name: 'C2' })
    expect(patch).toHaveBeenCalledWith('/purchase-order-categories/c1', { name: 'C2' })
  })
  it('deletePurchaseOrderCategory DELETE /{id}', async () => {
    await deletePurchaseOrderCategory('c1')
    expect(del).toHaveBeenCalledWith('/purchase-order-categories/c1')
  })

  // vendors
  it('listVendors GET /vendors', async () => {
    await listVendors()
    expect(get).toHaveBeenCalledWith('/vendors')
  })
  it('listVendorsMini GET /vendors/mini', async () => {
    await listVendorsMini()
    expect(get).toHaveBeenCalledWith('/vendors/mini')
  })
  it('createVendor POST /vendors', async () => {
    await createVendor({ name: 'V' })
    expect(post).toHaveBeenCalledWith('/vendors', { name: 'V' })
  })
  it('updateVendor PATCH /vendors/{id}', async () => {
    await updateVendor('v1', { phone: '1' })
    expect(patch).toHaveBeenCalledWith('/vendors/v1', { phone: '1' })
  })
  it('deleteVendor DELETE /vendors/{id}', async () => {
    await deleteVendor('v1')
    expect(del).toHaveBeenCalledWith('/vendors/v1')
  })

  // customers
  it('listCustomers GET /customers', async () => {
    await listCustomers()
    expect(get).toHaveBeenCalledWith('/customers')
  })
  it('listCustomersMini GET /customers/mini', async () => {
    await listCustomersMini()
    expect(get).toHaveBeenCalledWith('/customers/mini')
  })
  it('createCustomer POST /customers', async () => {
    await createCustomer({ name: 'C' })
    expect(post).toHaveBeenCalledWith('/customers', { name: 'C' })
  })
  it('updateCustomer PATCH /customers/{id}', async () => {
    await updateCustomer('c1', { billing_currency: 'CNY' })
    expect(patch).toHaveBeenCalledWith('/customers/c1', { billing_currency: 'CNY' })
  })
  it('deleteCustomer DELETE /customers/{id}', async () => {
    await deleteCustomer('c1')
    expect(del).toHaveBeenCalledWith('/customers/c1')
  })
})
```

- [ ] **Step 2: 跑红**

Run: `cd frontend && npm run test -- inventoryApi`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: types `src/types/inventory.ts`**

```typescript
// 备件
export interface PartRead {
  id: string
  custom_id: string
  name: string
  description: string
  cost: string
  quantity: string
  min_quantity: string
  unit: string
  barcode: string | null
  non_stock: boolean
  is_low_stock: boolean
  category_id: string | null
  assignee_ids: string[]
  team_ids: string[]
  asset_ids: string[]
  location_ids: string[]
  pm_ids: string[]
}
export interface PartCreate {
  name: string
  description?: string
  cost?: string
  quantity?: string
  min_quantity?: string
  unit?: string
  barcode?: string | null
  non_stock?: boolean
  category_id?: string | null
  assignee_ids?: string[]
  team_ids?: string[]
  asset_ids?: string[]
  location_ids?: string[]
  pm_ids?: string[]
}
export type PartUpdate = Partial<PartCreate>
export interface PartMini {
  id: string
  name: string
  custom_id: string
}

export interface PartCategoryRead {
  id: string
  name: string
  description: string
}
export interface PartCategoryCreate {
  name: string
  description?: string
}
export type PartCategoryUpdate = Partial<PartCategoryCreate>

// 采购单
export type PurchaseOrderStatus = 'DRAFT' | 'SUBMITTED' | 'APPROVED' | 'REJECTED' | 'CANCELED'

export interface POLineRead {
  id: string
  part_id: string
  quantity: string
  unit_cost: string
  line_total: string
}
export interface POLineCreate {
  part_id: string
  quantity: string
  unit_cost?: string
}

export interface PurchaseOrderRead {
  id: string
  custom_id: string
  vendor_id: string
  status: PurchaseOrderStatus
  notes: string
  category_id: string | null
  shipping_address: string
  shipping_method: string
  terms_of_payment: string
  expected_delivery_date: string | null
  resolution_note: string
  resolved_by_user_id: string | null
  resolved_at: string | null
  lines: POLineRead[]
  total_cost: string
}
export interface PurchaseOrderCreate {
  vendor_id: string
  notes?: string
  category_id?: string | null
  shipping_address?: string
  shipping_method?: string
  terms_of_payment?: string
  expected_delivery_date?: string | null
  lines?: POLineCreate[]
}
export type PurchaseOrderUpdate = Partial<PurchaseOrderCreate>
export interface PurchaseOrderMini {
  id: string
  custom_id: string
  vendor_id: string
  status: PurchaseOrderStatus
}

export interface POActivityRead {
  id: string
  activity_type: string
  actor_user_id: string | null
  from_status: string | null
  to_status: string | null
  comment: string
  created_at: string
}
export interface POResolve {
  note?: string
}

export interface PurchaseOrderCategoryRead {
  id: string
  name: string
  description: string
}
export interface PurchaseOrderCategoryCreate {
  name: string
  description?: string
}
export type PurchaseOrderCategoryUpdate = Partial<PurchaseOrderCategoryCreate>

// 供应商
export interface VendorRead {
  id: string
  name: string
  vendor_type: string
  description: string
  rate: string
  address: string
  phone: string
  email: string
  website: string
  part_ids: string[]
  asset_ids: string[]
  location_ids: string[]
}
export interface VendorCreate {
  name: string
  vendor_type?: string
  description?: string
  rate?: string
  address?: string
  phone?: string
  email?: string
  website?: string
  part_ids?: string[]
  asset_ids?: string[]
  location_ids?: string[]
}
export type VendorUpdate = Partial<VendorCreate>
export interface VendorMini {
  id: string
  name: string
}

// 客户
export interface CustomerRead {
  id: string
  name: string
  customer_type: string
  description: string
  rate: string
  billing_currency: string
  address: string
  phone: string
  email: string
  website: string
  part_ids: string[]
  asset_ids: string[]
  location_ids: string[]
}
export interface CustomerCreate {
  name: string
  customer_type?: string
  description?: string
  rate?: string
  billing_currency?: string
  address?: string
  phone?: string
  email?: string
  website?: string
  part_ids?: string[]
  asset_ids?: string[]
  location_ids?: string[]
}
export type CustomerUpdate = Partial<CustomerCreate>
export interface CustomerMini {
  id: string
  name: string
}
```

- [ ] **Step 4: api 客户端**

`src/api/parts.ts`：
```typescript
import { http } from './http'
import type { PartRead, PartCreate, PartUpdate, PartMini } from '@/types/inventory'

export interface ListPartsParams {
  category_id?: string
  asset_id?: string
  low_stock?: boolean
}

export const listParts = (params: ListPartsParams = {}) =>
  http.get<PartRead[]>('/parts', { params }).then((r) => r.data)
export const listPartsMini = () => http.get<PartMini[]>('/parts/mini').then((r) => r.data)
export const createPart = (p: PartCreate) => http.post<PartRead>('/parts', p).then((r) => r.data)
export const updatePart = (id: string, p: PartUpdate) =>
  http.patch<PartRead>(`/parts/${id}`, p).then((r) => r.data)
export const deletePart = (id: string) => http.delete(`/parts/${id}`).then(() => undefined)
```

`src/api/partCategories.ts`：
```typescript
import { http } from './http'
import type {
  PartCategoryRead,
  PartCategoryCreate,
  PartCategoryUpdate,
} from '@/types/inventory'

export const listPartCategories = () =>
  http.get<PartCategoryRead[]>('/part-categories').then((r) => r.data)
export const createPartCategory = (p: PartCategoryCreate) =>
  http.post<PartCategoryRead>('/part-categories', p).then((r) => r.data)
export const updatePartCategory = (id: string, p: PartCategoryUpdate) =>
  http.patch<PartCategoryRead>(`/part-categories/${id}`, p).then((r) => r.data)
export const deletePartCategory = (id: string) =>
  http.delete(`/part-categories/${id}`).then(() => undefined)
```

`src/api/purchaseOrders.ts`：
```typescript
import { http } from './http'
import type {
  PurchaseOrderRead,
  PurchaseOrderCreate,
  PurchaseOrderUpdate,
  PurchaseOrderStatus,
  POActivityRead,
  POResolve,
} from '@/types/inventory'

export interface ListPurchaseOrdersParams {
  status?: PurchaseOrderStatus
  vendor_id?: string
}

export const listPurchaseOrders = (params: ListPurchaseOrdersParams = {}) =>
  http.get<PurchaseOrderRead[]>('/purchase-orders', { params }).then((r) => r.data)
export const getPurchaseOrder = (id: string) =>
  http.get<PurchaseOrderRead>(`/purchase-orders/${id}`).then((r) => r.data)
export const createPurchaseOrder = (p: PurchaseOrderCreate) =>
  http.post<PurchaseOrderRead>('/purchase-orders', p).then((r) => r.data)
export const updatePurchaseOrder = (id: string, p: PurchaseOrderUpdate) =>
  http.patch<PurchaseOrderRead>(`/purchase-orders/${id}`, p).then((r) => r.data)
export const deletePurchaseOrder = (id: string) =>
  http.delete(`/purchase-orders/${id}`).then(() => undefined)
export const submitPurchaseOrder = (id: string) =>
  http.post<PurchaseOrderRead>(`/purchase-orders/${id}/submit`).then((r) => r.data)
export const approvePurchaseOrder = (id: string, p: POResolve = {}) =>
  http.post<PurchaseOrderRead>(`/purchase-orders/${id}/approve`, p).then((r) => r.data)
export const rejectPurchaseOrder = (id: string, p: POResolve = {}) =>
  http.post<PurchaseOrderRead>(`/purchase-orders/${id}/reject`, p).then((r) => r.data)
export const cancelPurchaseOrder = (id: string, p: POResolve = {}) =>
  http.post<PurchaseOrderRead>(`/purchase-orders/${id}/cancel`, p).then((r) => r.data)
export const listPurchaseOrderActivities = (id: string) =>
  http.get<POActivityRead[]>(`/purchase-orders/${id}/activities`).then((r) => r.data)
```
> 注：`submitPurchaseOrder` 测试断言 `post` 仅以 path 调用（无 body）；approve/reject/cancel 带 `POResolve` body。保持与测试一致。

`src/api/purchaseOrderCategories.ts`：
```typescript
import { http } from './http'
import type {
  PurchaseOrderCategoryRead,
  PurchaseOrderCategoryCreate,
  PurchaseOrderCategoryUpdate,
} from '@/types/inventory'

export const listPurchaseOrderCategories = () =>
  http.get<PurchaseOrderCategoryRead[]>('/purchase-order-categories').then((r) => r.data)
export const createPurchaseOrderCategory = (p: PurchaseOrderCategoryCreate) =>
  http.post<PurchaseOrderCategoryRead>('/purchase-order-categories', p).then((r) => r.data)
export const updatePurchaseOrderCategory = (id: string, p: PurchaseOrderCategoryUpdate) =>
  http.patch<PurchaseOrderCategoryRead>(`/purchase-order-categories/${id}`, p).then((r) => r.data)
export const deletePurchaseOrderCategory = (id: string) =>
  http.delete(`/purchase-order-categories/${id}`).then(() => undefined)
```

`src/api/vendors.ts`：
```typescript
import { http } from './http'
import type { VendorRead, VendorCreate, VendorUpdate, VendorMini } from '@/types/inventory'

export const listVendors = () => http.get<VendorRead[]>('/vendors').then((r) => r.data)
export const listVendorsMini = () => http.get<VendorMini[]>('/vendors/mini').then((r) => r.data)
export const createVendor = (p: VendorCreate) =>
  http.post<VendorRead>('/vendors', p).then((r) => r.data)
export const updateVendor = (id: string, p: VendorUpdate) =>
  http.patch<VendorRead>(`/vendors/${id}`, p).then((r) => r.data)
export const deleteVendor = (id: string) => http.delete(`/vendors/${id}`).then(() => undefined)
```

`src/api/customers.ts`：
```typescript
import { http } from './http'
import type { CustomerRead, CustomerCreate, CustomerUpdate, CustomerMini } from '@/types/inventory'

export const listCustomers = () => http.get<CustomerRead[]>('/customers').then((r) => r.data)
export const listCustomersMini = () =>
  http.get<CustomerMini[]>('/customers/mini').then((r) => r.data)
export const createCustomer = (p: CustomerCreate) =>
  http.post<CustomerRead>('/customers', p).then((r) => r.data)
export const updateCustomer = (id: string, p: CustomerUpdate) =>
  http.patch<CustomerRead>(`/customers/${id}`, p).then((r) => r.data)
export const deleteCustomer = (id: string) => http.delete(`/customers/${id}`).then(() => undefined)
```

- [ ] **Step 5: 占位视图**

`src/views/inventory/PartsView.vue`（其余三个同结构，标题分别为「采购单」「供应商」「客户」，文件名 `PurchaseOrdersView.vue`/`VendorsView.vue`/`CustomersView.vue`）：
```vue
<script setup lang="ts"></script>
<template><div class="page">备件库存</div></template>
```

- [ ] **Step 6: 路由 `src/router/index.ts` 加 4 条**

先 Read 现有路由数组结构与缩进，仿照加入：
```typescript
  {
    path: '/inventory/parts',
    name: 'inventory-parts',
    component: () => import('@/views/inventory/PartsView.vue'),
    meta: { title: '备件库存', requiresAuth: true, requiredPermission: 'part.view' },
  },
  {
    path: '/inventory/purchase-orders',
    name: 'inventory-purchase-orders',
    component: () => import('@/views/inventory/PurchaseOrdersView.vue'),
    meta: { title: '采购单', requiresAuth: true, requiredPermission: 'purchase_order.view' },
  },
  {
    path: '/inventory/vendors',
    name: 'inventory-vendors',
    component: () => import('@/views/inventory/VendorsView.vue'),
    meta: { title: '供应商', requiresAuth: true, requiredPermission: 'vendor.view' },
  },
  {
    path: '/inventory/customers',
    name: 'inventory-customers',
    component: () => import('@/views/inventory/CustomersView.vue'),
    meta: { title: '客户', requiresAuth: true, requiredPermission: 'customer.view' },
  },
```

- [ ] **Step 7: 导航接线 `src/components/AppSidebar.vue`**

先 Read。「供应」组：把四项改为带 path（去 `soon`）：
```typescript
      { label: '备件库存', path: '/inventory/parts' },
      { label: '采购单', path: '/inventory/purchase-orders' },
      { label: '供应商', path: '/inventory/vendors' },
      { label: '客户', path: '/inventory/customers' },
```
`activeMenu` computed 增加：`if (route.path.startsWith('/inventory/')) return route.path`（按该文件现有 `activeMenu` 写法适配，与已有 `/platform/`、`/maindata/` 分支并列）。

`tests/unit/AppSidebar.spec.ts`：先 Read 现有结构（已有平台/维护组断言），追加断言——「供应」组中 备件库存/采购单/供应商/客户 四项均有 `path`、无 `soon`（不渲染「即将上线」）。既有断言不破。

- [ ] **Step 8: 跑绿 + 门禁**

Run: `cd frontend && npm run test && npm run typecheck`
Expected: PASS / 0 errors。
prettier：`npx prettier --write "src/types/inventory.ts" "src/api/parts.ts" "src/api/partCategories.ts" "src/api/purchaseOrders.ts" "src/api/purchaseOrderCategories.ts" "src/api/vendors.ts" "src/api/customers.ts" "src/views/inventory/*.vue" "tests/unit/inventoryApi.spec.ts" "src/router/index.ts" "src/components/AppSidebar.vue" "tests/unit/AppSidebar.spec.ts"`

- [ ] **Step 9: commit**

```bash
git add src/types/inventory.ts src/api/parts.ts src/api/partCategories.ts src/api/purchaseOrders.ts src/api/purchaseOrderCategories.ts src/api/vendors.ts src/api/customers.ts src/views/inventory/ src/router/index.ts src/components/AppSidebar.vue tests/unit/inventoryApi.spec.ts tests/unit/AppSidebar.spec.ts
git commit -m "feat(fe-inventory): api clients + types + routes + sidebar + placeholders

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: 供应商 View（模板任务，完整展开）

**Files:** Create `src/views/inventory/VendorsView.vue`（覆盖占位）；Test `tests/unit/VendorsView.spec.ts`

- [ ] **Step 1: 写失败测试 `tests/unit/VendorsView.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lv, cv, uv, dv } = vi.hoisted(() => ({ lv: vi.fn(), cv: vi.fn(), uv: vi.fn(), dv: vi.fn() }))
vi.mock('@/api/vendors', () => ({
  listVendors: lv,
  createVendor: cv,
  updateVendor: uv,
  deleteVendor: dv,
}))
vi.mock('@/api/parts', () => ({ listPartsMini: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/assets', () => ({ listAssetsMini: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/locations', () => ({ listLocationsMini: vi.fn().mockResolvedValue([]) }))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can, user: { role_code: 'admin' } }),
}))

import VendorsView from '@/views/inventory/VendorsView.vue'

function mountView() {
  return mount(VendorsView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lv.mockReset().mockResolvedValue([
    {
      id: 'v1',
      name: '一号供应商',
      vendor_type: '本地',
      description: '',
      rate: '4.5',
      address: '北京',
      phone: '010-111',
      email: 'a@v.com',
      website: '',
      part_ids: [],
      asset_ids: [],
      location_ids: [],
    },
  ])
  cv.mockReset().mockResolvedValue({})
  uv.mockReset().mockResolvedValue({})
  dv.mockReset().mockResolvedValue(undefined)
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('VendorsView', () => {
  it('加载并渲染供应商行', async () => {
    const w = mountView()
    await flushPromises()
    expect(lv).toHaveBeenCalled()
    expect(w.text()).toContain('一号供应商')
    expect(w.text()).toContain('本地')
    expect(w.text()).toContain('a@v.com')
  })

  it('新建提交携带 name', async () => {
    const w = mountView()
    await flushPromises()
    const addBtn = w.findAll('.el-button').find((b) => b.text() === '新建供应商')
    expect(addBtn).toBeTruthy()
    await addBtn!.trigger('click')
    await flushPromises()
    const nameInput = document.querySelector(
      '.el-dialog input[placeholder="请输入名称"]',
    ) as HTMLInputElement
    nameInput.value = '新供应商'
    nameInput.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cv).toHaveBeenCalled()
    expect(cv.mock.calls[0][0]).toMatchObject({ name: '新供应商' })
  })

  it('删除经确认调用 deleteVendor', async () => {
    const { ElMessageBox } = await import('element-plus')
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    const w = mountView()
    await flushPromises()
    const delBtn = w.findAll('.el-button').find((b) => b.text() === '删除')
    await delBtn!.trigger('click')
    await flushPromises()
    expect(dv).toHaveBeenCalled()
  })

  it('无权限隐藏新建/编辑/删除按钮', async () => {
    authState.can = false
    const w = mountView()
    await flushPromises()
    expect(w.findAll('.el-button').find((b) => b.text() === '新建供应商')).toBeFalsy()
    expect(w.findAll('.el-button').find((b) => b.text() === '编辑')).toBeFalsy()
    expect(w.findAll('.el-button').find((b) => b.text() === '删除')).toBeFalsy()
  })
})
```

- [ ] **Step 2: 跑红** `cd frontend && npm run test -- VendorsView` → FAIL。

- [ ] **Step 3: 实现 `src/views/inventory/VendorsView.vue`**

`<script setup lang="ts">`，严格仿 `LocationsView.vue` 分区与流程：
- import：vue `ref/reactive/computed/onMounted`；`ElMessage/ElMessageBox`；`listVendors/createVendor/updateVendor/deleteVendor`、`listPartsMini`、`listAssetsMini`、`listLocationsMini`、`useAuthStore`、types。
- state：`loading`、`vendors = ref<VendorRead[]>([])`、`partsMini`、`assetsMini`、`locationsMini`；dialog（`dialogVisible`、`dialogMode:'create'|'edit'`、`editingId`、`submitting`、`form = reactive<{name,vendor_type,description,rate,address,phone,email,website,part_ids,asset_ids,location_ids}>`，rate 默认 `''`，数组默认 `[]`）。
- `const auth = useAuthStore()`。
- `onMounted(async () => { await Promise.all([fetchVendors(), fetchPartsMini(), fetchAssetsMini(), fetchLocationsMini()]) })`。`fetchVendors` 内 `loading` try/finally。
- 表格列：名称(name)、类型(vendor_type)、评分(rate)、电话(phone)、邮箱(email)、操作。
- 顶部「新建供应商」按钮 `v-if="auth.hasPermission('vendor.create')"`；行内 编辑 `v-if="auth.hasPermission('vendor.edit')"`、删除 `v-if="auth.hasPermission('vendor.delete')"`。
- dialog（`el-form`）：名称(必填, placeholder「请输入名称」)、类型、描述、评分(`el-input`)、地址、电话、邮箱、网址、关联备件(`el-select multiple filterable` options=partsMini，label=`name`，value=`id`)、关联资产(同 assetsMini)、关联位置(同 locationsMini)。提交按钮文本「保存」。
- `openCreate`：`resetForm()` + mode='create' + visible。`openEdit(row)`：`resetForm()` + 回填 `Object.assign(form, { ...row, part_ids:[...row.part_ids], asset_ids:[...row.asset_ids], location_ids:[...row.location_ids] })` + mode='edit' + editingId + visible。
- `submitForm`：校验 `form.name.trim()`（空则 `ElMessage.warning('请填写名称')` 返回）；payload 含全部表单字段（`name: form.name.trim()`，数组照传）；create→`createVendor(payload)`、edit→`updateVendor(editingId.value, payload)`；`try { submitting=true; ...; ElMessage.success(...); dialogVisible=false; await fetchVendors() } catch { ElMessage.error('保存失败，请重试') } finally { submitting=false }`。
- `handleDelete(row)`：`ElMessageBox.confirm('确认删除供应商「'+row.name+'」？','提示',{type:'warning'})` → `deleteVendor(row.id)` → `ElMessage.success` + `fetchVendors()`；catch 静默。
- 模板根 `<div class="page">` + `.page-title` + `.toolbar`，`<style scoped>` 仿 LocationsView。

- [ ] **Step 4: 跑绿 + 门禁** `npm run test -- VendorsView && npm run test && npm run typecheck`。`npx prettier --write "src/views/inventory/VendorsView.vue" "tests/unit/VendorsView.spec.ts"`。

- [ ] **Step 5: commit**

```bash
git add src/views/inventory/VendorsView.vue tests/unit/VendorsView.spec.ts
git commit -m "feat(fe-inventory): vendors view

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 客户 View（仿供应商 + billing_currency）

**Files:** Create `src/views/inventory/CustomersView.vue`（覆盖占位）；Test `tests/unit/CustomersView.spec.ts`

- [ ] **Step 1: 写失败测试 `tests/unit/CustomersView.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lc, cc, uc, dc } = vi.hoisted(() => ({ lc: vi.fn(), cc: vi.fn(), uc: vi.fn(), dc: vi.fn() }))
vi.mock('@/api/customers', () => ({
  listCustomers: lc,
  createCustomer: cc,
  updateCustomer: uc,
  deleteCustomer: dc,
}))
vi.mock('@/api/parts', () => ({ listPartsMini: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/assets', () => ({ listAssetsMini: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/locations', () => ({ listLocationsMini: vi.fn().mockResolvedValue([]) }))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can, user: { role_code: 'admin' } }),
}))

import CustomersView from '@/views/inventory/CustomersView.vue'

function mountView() {
  return mount(CustomersView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lc.mockReset().mockResolvedValue([
    {
      id: 'c1',
      name: '甲方公司',
      customer_type: '大客户',
      description: '',
      rate: '5',
      billing_currency: 'CNY',
      address: '上海',
      phone: '021-222',
      email: 'b@c.com',
      website: '',
      part_ids: [],
      asset_ids: [],
      location_ids: [],
    },
  ])
  cc.mockReset().mockResolvedValue({})
  uc.mockReset().mockResolvedValue({})
  dc.mockReset().mockResolvedValue(undefined)
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('CustomersView', () => {
  it('加载并渲染客户行（含结算货币）', async () => {
    const w = mountView()
    await flushPromises()
    expect(lc).toHaveBeenCalled()
    expect(w.text()).toContain('甲方公司')
    expect(w.text()).toContain('CNY')
  })

  it('新建提交携带 name + billing_currency', async () => {
    const w = mountView()
    await flushPromises()
    const addBtn = w.findAll('.el-button').find((b) => b.text() === '新建客户')
    await addBtn!.trigger('click')
    await flushPromises()
    const nameInput = document.querySelector(
      '.el-dialog input[placeholder="请输入名称"]',
    ) as HTMLInputElement
    nameInput.value = '乙方'
    nameInput.dispatchEvent(new Event('input'))
    const currencyInput = document.querySelector(
      '.el-dialog input[placeholder="如 CNY / USD"]',
    ) as HTMLInputElement
    currencyInput.value = 'USD'
    currencyInput.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cc).toHaveBeenCalled()
    expect(cc.mock.calls[0][0]).toMatchObject({ name: '乙方', billing_currency: 'USD' })
  })

  it('无权限隐藏新建按钮', async () => {
    authState.can = false
    const w = mountView()
    await flushPromises()
    expect(w.findAll('.el-button').find((b) => b.text() === '新建客户')).toBeFalsy()
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- CustomersView` → FAIL。

- [ ] **Step 3: 实现 `src/views/inventory/CustomersView.vue`**

与 Task 2 VendorsView **结构完全相同**，delta：
- api 换 `@/api/customers`（`listCustomers/createCustomer/updateCustomer/deleteCustomer`）。
- `form` 增加 `billing_currency`（默认 `''`），`reactive<{name,customer_type,description,rate,billing_currency,address,phone,email,website,part_ids,asset_ids,location_ids}>`。
- 表格列：名称、类型(customer_type)、结算货币(billing_currency)、电话、邮箱、操作。
- dialog 字段在「类型」后增加 结算货币(`el-input` placeholder「如 CNY / USD」)；其余同 Vendor（类型字段 placeholder 与标签用「类型」）。
- 文案：「新建客户」、删除确认「确认删除客户「...」？」。
- `submitForm` payload 含 `billing_currency: form.billing_currency`。

- [ ] **Step 4: 跑绿 + 门禁** `npm run test -- CustomersView && npm run test && npm run typecheck`。`npx prettier --write "src/views/inventory/CustomersView.vue" "tests/unit/CustomersView.spec.ts"`。

- [ ] **Step 5: commit**

```bash
git add src/views/inventory/CustomersView.vue tests/unit/CustomersView.spec.ts
git commit -m "feat(fe-inventory): customers view

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: 备件库存 View + 备件分类对话框

**Files:**
- Create: `src/components/inventory/PartCategoryManageDialog.vue`
- Create: `src/views/inventory/PartsView.vue`（覆盖占位）
- Test: `tests/unit/PartCategoryManageDialog.spec.ts`、`tests/unit/PartsView.spec.ts`

### 4A 备件分类对话框

- [ ] **Step 1: 写失败测试 `tests/unit/PartCategoryManageDialog.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lpc, cpc, upc, dpc } = vi.hoisted(() => ({
  lpc: vi.fn(),
  cpc: vi.fn(),
  upc: vi.fn(),
  dpc: vi.fn(),
}))
vi.mock('@/api/partCategories', () => ({
  listPartCategories: lpc,
  createPartCategory: cpc,
  updatePartCategory: upc,
  deletePartCategory: dpc,
}))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({ useAuthStore: () => ({ hasPermission: () => authState.can }) }))

import PartCategoryManageDialog from '@/components/inventory/PartCategoryManageDialog.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lpc.mockReset().mockResolvedValue([
    { id: 'c1', name: '轴承', description: '' },
    { id: 'c2', name: '密封件', description: '' },
  ])
  cpc.mockReset().mockResolvedValue({})
  upc.mockReset().mockResolvedValue({})
  dpc.mockReset().mockResolvedValue(undefined)
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('PartCategoryManageDialog', () => {
  it('可见时加载并渲染分类', async () => {
    mount(PartCategoryManageDialog, {
      props: { visible: true },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    expect(lpc).toHaveBeenCalled()
    expect(document.body.textContent).toContain('轴承')
    expect(document.body.textContent).toContain('密封件')
  })

  it('新增提交并 emit changed', async () => {
    const w = mount(PartCategoryManageDialog, {
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
    input.value = '联轴器'
    input.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cpc).toHaveBeenCalledWith({ name: '联轴器', description: '' })
    expect(w.emitted('changed')).toBeTruthy()
  })

  it('无权限隐藏新增分类按钮', async () => {
    authState.can = false
    mount(PartCategoryManageDialog, {
      props: { visible: true },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    const addBtn = Array.from(document.querySelectorAll('.el-button')).find(
      (b) => b.textContent?.trim() === '新增分类',
    )
    expect(addBtn).toBeFalsy()
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- PartCategoryManageDialog` → FAIL。

- [ ] **Step 3: 实现 `src/components/inventory/PartCategoryManageDialog.vue`**

复刻 `src/components/maindata/AssetCategoryManageDialog.vue`（先 Read 它），delta：
- api 换 `@/api/partCategories`（`listPartCategories/createPartCategory/updatePartCategory/deletePartCategory`）。
- 分类对象多一个 `description` 字段：表单 dialog 除名称(必填, placeholder「请输入分类名称」)外，增加 描述(`el-input type="textarea"`，可空)。主表格列：名称、描述、操作。
- 提交 payload：create `createPartCategory({ name: form.name.trim(), description: form.description })`、edit `updatePartCategory(editingId, { name: form.name.trim(), description: form.description })`。**注意测试断言 `createPartCategory({ name: '联轴器', description: '' })`** —— description 默认空串。
- 门控 `part_category.manage`（新增/编辑/删除按钮 `v-if`）。
- emit `update:visible`/`changed`；`watch(() => props.visible, v => { if (v) fetchCategories() }, { immediate: true })`；删除 `ElMessageBox.confirm`；try/catch 本地化 `ElMessage.error('保存失败，请重试')`。

### 4B 备件库存 View

- [ ] **Step 4: 写失败测试 `tests/unit/PartsView.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lp, cp, up, dp } = vi.hoisted(() => ({ lp: vi.fn(), cp: vi.fn(), up: vi.fn(), dp: vi.fn() }))
vi.mock('@/api/parts', () => ({
  listParts: lp,
  listPartsMini: vi.fn().mockResolvedValue([]),
  createPart: cp,
  updatePart: up,
  deletePart: dp,
}))
const { lpc } = vi.hoisted(() => ({ lpc: vi.fn() }))
vi.mock('@/api/partCategories', () => ({
  listPartCategories: lpc,
  createPartCategory: vi.fn(),
  updatePartCategory: vi.fn(),
  deletePartCategory: vi.fn(),
}))
vi.mock('@/api/assets', () => ({ listAssetsMini: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/locations', () => ({ listLocationsMini: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/users', () => ({ listUsers: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/teams', () => ({ listTeams: vi.fn().mockResolvedValue([]) }))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can, user: { role_code: 'admin' } }),
}))

import PartsView from '@/views/inventory/PartsView.vue'

function mountView() {
  return mount(PartsView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lp.mockReset().mockResolvedValue([
    {
      id: 'p1',
      custom_id: 'P-001',
      name: '深沟球轴承',
      description: '',
      cost: '12.5',
      quantity: '3',
      min_quantity: '5',
      unit: '个',
      barcode: null,
      non_stock: false,
      is_low_stock: true,
      category_id: 'c1',
      assignee_ids: [],
      team_ids: [],
      asset_ids: [],
      location_ids: [],
      pm_ids: [],
    },
  ])
  cp.mockReset().mockResolvedValue({})
  up.mockReset().mockResolvedValue({})
  dp.mockReset().mockResolvedValue(undefined)
  lpc.mockReset().mockResolvedValue([{ id: 'c1', name: '轴承', description: '' }])
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('PartsView', () => {
  it('加载并渲染备件 + 分类映射 + 低库存标记', async () => {
    const w = mountView()
    await flushPromises()
    expect(lp).toHaveBeenCalled()
    expect(w.text()).toContain('深沟球轴承')
    expect(w.text()).toContain('P-001')
    expect(w.text()).toContain('轴承') // category_id→name
    expect(w.text()).toContain('低库存') // is_low_stock tag
  })

  it('新建提交携带 name', async () => {
    const w = mountView()
    await flushPromises()
    const addBtn = w.findAll('.el-button').find((b) => b.text() === '新建备件')
    await addBtn!.trigger('click')
    await flushPromises()
    const nameInput = document.querySelector(
      '.el-dialog input[placeholder="请输入名称"]',
    ) as HTMLInputElement
    nameInput.value = '新备件'
    nameInput.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cp).toHaveBeenCalled()
    expect(cp.mock.calls[0][0]).toMatchObject({ name: '新备件' })
  })

  it('低库存过滤开关触发带参重拉', async () => {
    const w = mountView()
    await flushPromises()
    lp.mockClear()
    // 找到低库存过滤开关（el-switch / el-checkbox），切换后应以 { low_stock: true } 重拉
    const sw = w.find('.el-switch')
    expect(sw.exists()).toBe(true)
    await sw.trigger('click')
    await flushPromises()
    expect(lp).toHaveBeenCalledWith({ low_stock: true })
  })

  it('无权限隐藏新建备件按钮', async () => {
    authState.can = false
    const w = mountView()
    await flushPromises()
    expect(w.findAll('.el-button').find((b) => b.text() === '新建备件')).toBeFalsy()
  })
})
```

- [ ] **Step 5: 跑红** `npm run test -- PartsView` → FAIL。

- [ ] **Step 6: 实现 `src/views/inventory/PartsView.vue`**

仿 `LocationsView.vue` 结构（扁平表格，非树形），delta：
- import：`listParts/listPartsMini/createPart/updatePart/deletePart`（listPartsMini 本 view 暂不直接用，但 mock 已提供，可不 import）、`listPartCategories`、`listAssetsMini`、`listLocationsMini`、`listUsers`、`listTeams`、`PartCategoryManageDialog`、`useAuthStore`、types。
- state：`parts = ref<PartRead[]>([])`、`categories`、`assetsMini`、`locationsMini`、`users`、`teams`、`loading`、`lowStockOnly = ref(false)`；`categoryDialogVisible = ref(false)`；dialog 状态 + `form = reactive<{name,description,cost,quantity,min_quantity,unit,barcode,non_stock,category_id,assignee_ids,team_ids,asset_ids,location_ids}>`（数值字段默认 `''`，non_stock 默认 false，数组 []，category_id/barcode 默认 null/''）。
- 映射：`categoryName(id)`（查 categories，未命中/null→'—'）。
- `fetchParts`：`async () => { loading=true; try { parts.value = await listParts(lowStockOnly.value ? { low_stock: true } : {}) } finally { loading=false } }`。**低库存开关**：`el-switch v-model="lowStockOnly"` + `@change="fetchParts"`（旁标签「仅看低库存」）。测试点击 `.el-switch` 后期望 `listParts({ low_stock: true })`。
- `onMounted` 并行：`Promise.all([fetchParts(), fetchCategories(), fetchAssetsMini(), fetchLocationsMini(), fetchUsers(), fetchTeams()])`。
- 表格列：编号(custom_id)、名称、分类(`categoryName(row.category_id)`)、库存数量(quantity)、单位(unit)、单价(cost)、低库存(`<el-tag v-if="row.is_low_stock" type="danger">低库存</el-tag>`)、操作（编辑 `part.edit` / 删除 `part.delete`）。
- 顶部：「新建备件」`v-if="auth.hasPermission('part.create')"`、「管理分类」按钮（打开 categoryDialogVisible；建议 `v-if="auth.hasPermission('part_category.view')"`）、「仅看低库存」开关。
- dialog（`el-form`，分组用 `el-divider content-position="left"`）：
  - 基本：名称(必填, placeholder「请输入名称」)、描述、分类(`el-select clearable` options=categories，label=name，value=id)。
  - 库存：库存数量(`el-input`，提示「直接修改即入库/校正」)、最低库存阈值(`el-input`)、单位(`el-input`)、单价(`el-input`)、非库存(`el-switch` 绑 non_stock，标签「非库存件」)。
  - 标识：条码(`el-input`)。
  - 关联：负责人(`el-select multiple filterable` options=users，label=name，value=id)、团队(`el-select multiple` options=teams)、资产(`el-select multiple filterable` options=assetsMini)、位置(`el-select multiple` options=locationsMini)。
  - 保存按钮「保存」。
- `openCreate`/`openEdit(row)`/`resetForm()`：仿 LocationsView；openEdit 回填数组深拷贝、`barcode: row.barcode ?? ''`、数值字段直接用 row 字符串值。
- `submitForm`：校验 name.trim();payload：`name: form.name.trim()`，`barcode: form.barcode || null`，数值字段空串→省略或传原值（统一传字符串原值，空串按 `form.cost || '0'`？——**简化：数值字段直接传 form 值字符串**，后端接受 Decimal 字符串；`pm_ids` 不在表单，提交时**不带该字段**或传 `[]`，本 view 不传 pm_ids）。create→`createPart`、edit→`updatePart(editingId.value, payload)`；成功 + 重拉 + 关闭；try/catch 本地化。
  - > payload 数值字段建议：`cost: form.cost || '0'`、`quantity: form.quantity || '0'`、`min_quantity: form.min_quantity || '0'`（空串兜底为 '0'，避免后端 Decimal 解析空串失败）。
- `handleDelete`：`ElMessageBox.confirm('确认删除备件「'+row.name+'」？',...)` → `deletePart` → 重拉；catch 静默。
- 模板内嵌：`<PartCategoryManageDialog v-model:visible="categoryDialogVisible" @changed="fetchCategories" />`。
- 模板根 `<div class="page">` + page-title + toolbar，scoped style 仿 LocationsView。

- [ ] **Step 7: 跑绿 + 门禁** `npm run test -- PartCategoryManageDialog PartsView && npm run test && npm run typecheck`。`npx prettier --write "src/components/inventory/PartCategoryManageDialog.vue" "src/views/inventory/PartsView.vue" "tests/unit/PartCategoryManageDialog.spec.ts" "tests/unit/PartsView.spec.ts"`。

- [ ] **Step 8: commit**

```bash
git add src/components/inventory/PartCategoryManageDialog.vue src/views/inventory/PartsView.vue tests/unit/PartCategoryManageDialog.spec.ts tests/unit/PartsView.spec.ts
git commit -m "feat(fe-inventory): parts view with category dialog + low-stock filter

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: 采购单分类对话框

**Files:** Create `src/components/inventory/PurchaseOrderCategoryManageDialog.vue`；Test `tests/unit/PurchaseOrderCategoryManageDialog.spec.ts`

- [ ] **Step 1: 写失败测试 `tests/unit/PurchaseOrderCategoryManageDialog.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lpc, cpc, upc, dpc } = vi.hoisted(() => ({
  lpc: vi.fn(),
  cpc: vi.fn(),
  upc: vi.fn(),
  dpc: vi.fn(),
}))
vi.mock('@/api/purchaseOrderCategories', () => ({
  listPurchaseOrderCategories: lpc,
  createPurchaseOrderCategory: cpc,
  updatePurchaseOrderCategory: upc,
  deletePurchaseOrderCategory: dpc,
}))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({ useAuthStore: () => ({ hasPermission: () => authState.can }) }))

import PurchaseOrderCategoryManageDialog from '@/components/inventory/PurchaseOrderCategoryManageDialog.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lpc.mockReset().mockResolvedValue([
    { id: 'c1', name: '常规采购', description: '' },
    { id: 'c2', name: '紧急采购', description: '' },
  ])
  cpc.mockReset().mockResolvedValue({})
  upc.mockReset().mockResolvedValue({})
  dpc.mockReset().mockResolvedValue(undefined)
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('PurchaseOrderCategoryManageDialog', () => {
  it('可见时加载并渲染分类', async () => {
    mount(PurchaseOrderCategoryManageDialog, {
      props: { visible: true },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    expect(lpc).toHaveBeenCalled()
    expect(document.body.textContent).toContain('常规采购')
    expect(document.body.textContent).toContain('紧急采购')
  })

  it('新增提交并 emit changed', async () => {
    const w = mount(PurchaseOrderCategoryManageDialog, {
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
    input.value = '备件采购'
    input.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cpc).toHaveBeenCalledWith({ name: '备件采购', description: '' })
    expect(w.emitted('changed')).toBeTruthy()
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- PurchaseOrderCategoryManageDialog` → FAIL。

- [ ] **Step 3: 实现 `src/components/inventory/PurchaseOrderCategoryManageDialog.vue`**

与 Task 4A 的 `PartCategoryManageDialog.vue` **结构完全相同**（先复刻它），delta：
- api 换 `@/api/purchaseOrderCategories`（`listPurchaseOrderCategories/createPurchaseOrderCategory/updatePurchaseOrderCategory/deletePurchaseOrderCategory`）。
- 门控 `purchase_order_category.manage`（读 `purchase_order_category.view`）。
- 其余（名称+描述字段、「新增分类」/「保存」文案、name trim、`changed` 事件、删除确认、try/catch 本地化）完全一致。

- [ ] **Step 4: 跑绿 + 门禁** `npm run test -- PurchaseOrderCategoryManageDialog && npm run test && npm run typecheck`。prettier 两文件。

- [ ] **Step 5: commit**

```bash
git add src/components/inventory/PurchaseOrderCategoryManageDialog.vue tests/unit/PurchaseOrderCategoryManageDialog.spec.ts
git commit -m "feat(fe-inventory): purchase order category manage dialog

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: 采购单 View（最复杂：宽对话框分区 + 明细行子表 + 活动时间线 + 状态流转）

**Files:** Create `src/views/inventory/PurchaseOrdersView.vue`（覆盖占位）；Test `tests/unit/PurchaseOrdersView.spec.ts`

- [ ] **Step 1: 写失败测试 `tests/unit/PurchaseOrdersView.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lpo, gpo, cpo, upo, dpo, sub, app, rej, can, acts } = vi.hoisted(() => ({
  lpo: vi.fn(),
  gpo: vi.fn(),
  cpo: vi.fn(),
  upo: vi.fn(),
  dpo: vi.fn(),
  sub: vi.fn(),
  app: vi.fn(),
  rej: vi.fn(),
  can: vi.fn(),
  acts: vi.fn(),
}))
vi.mock('@/api/purchaseOrders', () => ({
  listPurchaseOrders: lpo,
  getPurchaseOrder: gpo,
  createPurchaseOrder: cpo,
  updatePurchaseOrder: upo,
  deletePurchaseOrder: dpo,
  submitPurchaseOrder: sub,
  approvePurchaseOrder: app,
  rejectPurchaseOrder: rej,
  cancelPurchaseOrder: can,
  listPurchaseOrderActivities: acts,
}))
vi.mock('@/api/vendors', () => ({ listVendorsMini: vi.fn().mockResolvedValue([{ id: 'v1', name: '一号供应商' }]) }))
vi.mock('@/api/parts', () => ({ listPartsMini: vi.fn().mockResolvedValue([{ id: 'p1', name: '轴承', custom_id: 'P-001' }]) }))
vi.mock('@/api/purchaseOrderCategories', () => ({
  listPurchaseOrderCategories: vi.fn().mockResolvedValue([]),
  createPurchaseOrderCategory: vi.fn(),
  updatePurchaseOrderCategory: vi.fn(),
  deletePurchaseOrderCategory: vi.fn(),
}))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can, user: { role_code: 'admin' } }),
}))

import PurchaseOrdersView from '@/views/inventory/PurchaseOrdersView.vue'

function mountView() {
  return mount(PurchaseOrdersView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

const draftPO = {
  id: 'po1',
  custom_id: 'PO-001',
  vendor_id: 'v1',
  status: 'DRAFT',
  notes: '',
  category_id: null,
  shipping_address: '',
  shipping_method: '',
  terms_of_payment: '',
  expected_delivery_date: null,
  resolution_note: '',
  resolved_by_user_id: null,
  resolved_at: null,
  lines: [{ id: 'l1', part_id: 'p1', quantity: '10', unit_cost: '5', line_total: '50' }],
  total_cost: '50',
}
const submittedPO = { ...draftPO, id: 'po2', custom_id: 'PO-002', status: 'SUBMITTED' }

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lpo.mockReset().mockResolvedValue([draftPO, submittedPO])
  gpo.mockReset().mockImplementation((id: string) =>
    Promise.resolve(id === 'po2' ? submittedPO : draftPO),
  )
  cpo.mockReset().mockResolvedValue({})
  upo.mockReset().mockResolvedValue({})
  dpo.mockReset().mockResolvedValue(undefined)
  sub.mockReset().mockResolvedValue({})
  app.mockReset().mockResolvedValue({})
  rej.mockReset().mockResolvedValue({})
  can.mockReset().mockResolvedValue({})
  acts.mockReset().mockResolvedValue([
    {
      id: 'a1',
      activity_type: 'STATUS_CHANGE',
      actor_user_id: null,
      from_status: 'DRAFT',
      to_status: 'SUBMITTED',
      comment: '',
      created_at: '2026-06-01T00:00:00',
    },
  ])
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('PurchaseOrdersView', () => {
  it('加载并渲染采购单 + 供应商名 + 状态中文 + 总额', async () => {
    const w = mountView()
    await flushPromises()
    expect(lpo).toHaveBeenCalled()
    expect(w.text()).toContain('PO-001')
    expect(w.text()).toContain('一号供应商') // vendor_id→name
    expect(w.text()).toContain('草稿') // DRAFT→中文
    expect(w.text()).toContain('已提交') // SUBMITTED→中文
  })

  it('新建提交携带 vendor_id + lines', async () => {
    const w = mountView()
    await flushPromises()
    const addBtn = w.findAll('.el-button').find((b) => b.text() === '新建采购单')
    await addBtn!.trigger('click')
    await flushPromises()
    // 选供应商
    const vm = w.vm as any
    vm.form.vendor_id = 'v1'
    // 添加一明细行
    vm.addLine()
    vm.form.lines[0].part_id = 'p1'
    vm.form.lines[0].quantity = '2'
    vm.form.lines[0].unit_cost = '3'
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cpo).toHaveBeenCalled()
    expect(cpo.mock.calls[0][0]).toMatchObject({
      vendor_id: 'v1',
      lines: [{ part_id: 'p1', quantity: '2', unit_cost: '3' }],
    })
  })

  it('打开 DRAFT 采购单显示提交按钮并调 submit', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    await vm.openEdit(draftPO)
    await flushPromises()
    expect(gpo).toHaveBeenCalledWith('po1')
    const submitBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '提交',
    ) as HTMLElement
    expect(submitBtn).toBeTruthy()
    submitBtn.click()
    await flushPromises()
    expect(sub).toHaveBeenCalledWith('po1')
  })

  it('打开 SUBMITTED 采购单显示批准/驳回并调 approve', async () => {
    const { ElMessageBox } = await import('element-plus')
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    await vm.openEdit(submittedPO)
    await flushPromises()
    const approveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '批准',
    ) as HTMLElement
    expect(approveBtn).toBeTruthy()
    approveBtn.click()
    await flushPromises()
    expect(app).toHaveBeenCalled()
    expect(app.mock.calls[0][0]).toBe('po2')
  })

  it('无权限时不显示批准按钮', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    // 关闭权限后打开 SUBMITTED 单：批准按钮应因无 purchase_order.approve 而隐藏
    authState.can = false
    await vm.openEdit(submittedPO)
    await flushPromises()
    const approveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '批准',
    )
    expect(approveBtn).toBeFalsy()
  })
})
```
> 实现者：测试通过 `vm` 直接驱动 `form`/`addLine`/`openEdit`（绕开 el-select 与明细子表的脆弱 DOM 交互）。因此组件须 `defineExpose({ form, addLine, removeLine, openEdit, openCreate })`。状态流转按钮与「保存」按钮的文案须精确为「提交」「批准」「驳回」「取消」「保存」「删除」。`openEdit` 须 `await getPurchaseOrder(id)` 拉详情 + `listPurchaseOrderActivities(id)` 拉活动。若你的交互/文案不同，须同步调整测试，但保持断言语义（submit/approve 以正确 id 调用、按状态/权限显隐）。

- [ ] **Step 2: 跑红** `npm run test -- PurchaseOrdersView` → FAIL。

- [ ] **Step 3: 实现 `src/views/inventory/PurchaseOrdersView.vue`**

仿 view 结构（列表 + 单宽 dialog），核心 delta：

**import**：`listPurchaseOrders/getPurchaseOrder/createPurchaseOrder/updatePurchaseOrder/deletePurchaseOrder/submitPurchaseOrder/approvePurchaseOrder/rejectPurchaseOrder/cancelPurchaseOrder/listPurchaseOrderActivities`、`listVendorsMini`、`listPartsMini`、`PurchaseOrderCategoryManageDialog`、`useAuthStore`、`formatDateTime`、types。

**状态映射常量**：
```typescript
const STATUS_LABELS: Record<PurchaseOrderStatus, string> = {
  DRAFT: '草稿',
  SUBMITTED: '已提交',
  APPROVED: '已批准',
  REJECTED: '已驳回',
  CANCELED: '已取消',
}
const STATUS_TAG: Record<PurchaseOrderStatus, string> = {
  DRAFT: 'info',
  SUBMITTED: 'warning',
  APPROVED: 'success',
  REJECTED: 'danger',
  CANCELED: 'info',
}
const STATUS_OPTIONS = (Object.keys(STATUS_LABELS) as PurchaseOrderStatus[]).map((v) => ({
  value: v,
  label: STATUS_LABELS[v],
}))
function statusLabel(s: PurchaseOrderStatus) {
  return STATUS_LABELS[s]
}
function statusTag(s: PurchaseOrderStatus) {
  return STATUS_TAG[s]
}
```

**state**：`orders = ref<PurchaseOrderRead[]>([])`、`vendorsMini`、`partsMini`、`loading`、过滤 `filterStatus = ref<PurchaseOrderStatus | ''>('')`、`filterVendor = ref('')`；`categoryDialogVisible = ref(false)`；dialog 状态 `dialogVisible`、`dialogMode`、`editingId`、`editingStatus = ref<PurchaseOrderStatus>('DRAFT')`、`submitting`、`activities = ref<POActivityRead[]>([])`；`form = reactive<{ vendor_id, category_id, shipping_address, shipping_method, terms_of_payment, expected_delivery_date, notes, lines: { part_id, quantity, unit_cost }[] }>`（lines 元素是可编辑行对象，默认 `[]`）。
- 映射：`vendorName(id)`（查 vendorsMini，'—'）、`partName(id)`（查 partsMini，'—'）。
- `readonly = computed(() => dialogMode.value === 'edit' && editingStatus.value !== 'DRAFT')`（非草稿只读）。

**fetch/onMounted**：`fetchOrders` 用 `listPurchaseOrders({ status: filterStatus.value || undefined, vendor_id: filterVendor.value || undefined })`（注意：传 undefined 不传该键 → 用对象构造时省略空值；可写 `const params: ListPurchaseOrdersParams = {}; if (filterStatus.value) params.status = filterStatus.value; if (filterVendor.value) params.vendor_id = filterVendor.value; return listPurchaseOrders(params)`）。`onMounted` 并行 `Promise.all([fetchOrders(), fetchVendorsMini(), fetchPartsMini()])`。过滤器 `el-select` `@change="fetchOrders"`。

**列表表格列**：编号(custom_id)、供应商(`vendorName(row.vendor_id)`)、状态(`<el-tag :type="statusTag(row.status)">{{ statusLabel(row.status) }}</el-tag>`)、明细行数(`row.lines.length`)、总额(`row.total_cost`)、预计交付(`row.expected_delivery_date ?? '—'`)、操作（编辑/详情 `purchase_order.view`、删除 `purchase_order.delete`）。
- 顶部：「新建采购单」`v-if="auth.hasPermission('purchase_order.create')"`、「管理分类」按钮（`v-if="auth.hasPermission('purchase_order_category.view')"`，打开 categoryDialogVisible）、状态过滤 `el-select`（options=STATUS_OPTIONS，clearable）、供应商过滤 `el-select`（options=vendorsMini，clearable）。

**明细行操作**：
```typescript
function addLine() {
  form.lines.push({ part_id: '', quantity: '1', unit_cost: '0' })
}
function removeLine(idx: number) {
  form.lines.splice(idx, 1)
}
function lineSubtotal(line: { quantity: string; unit_cost: string }): string {
  const q = Number(line.quantity) || 0
  const c = Number(line.unit_cost) || 0
  return (q * c).toFixed(2)
}
```

**openCreate**：`resetForm()`（vendor_id=''、category_id=null、各字符串=''、expected_delivery_date=null、lines=[]）+ mode='create' + editingStatus='DRAFT' + activities=[] + visible。
**openEdit(row)**：`mode='edit'`、`editingId=row.id`；`const full = await getPurchaseOrder(row.id)`；`editingStatus.value = full.status`；回填 `form`（vendor_id/category_id/各字段，`expected_delivery_date: full.expected_delivery_date`，`lines: full.lines.map(l => ({ part_id: l.part_id, quantity: l.quantity, unit_cost: l.unit_cost }))`）；`activities.value = await listPurchaseOrderActivities(row.id)`；visible=true。（按测试，openEdit 须先 `getPurchaseOrder(row.id)`。）

**宽 dialog（`el-dialog width="900px"`）内部分区**（用 `el-divider content-position="left"` 分隔）：
- **基本信息**（`el-form`）：供应商(`el-select` 必选 options=vendorsMini，`:disabled="readonly"`)、分类(`el-select clearable`，options 来自分类——本 view 可不拉分类列表用于选择？**简化：分类选择本轮可省**，仅「管理分类」入口；或拉 `listPurchaseOrderCategories` 填充。**为减依赖，分类选择省略**，category_id 提交时传 `form.category_id`（默认 null）)、运输地址、运输方式、付款条款（`el-input`，`:disabled="readonly"`）、预计交付(`el-date-picker type="date" value-format="YYYY-MM-DD"` `:disabled="readonly"`)、备注(`el-input type="textarea"`)。
  - > 注：分类选择器本轮省略以控制复杂度（spec §4.2 未强制下拉选分类，「管理分类」入口已满足分类 CRUD）。category_id 保持表单字段、默认 null、提交携带。
- **明细行**（`el-table :data="form.lines"`，`:show-header="true"`）：列 备件(`el-select` options=partsMini，`v-model="row.part_id"`，`:disabled="readonly"`)、数量(`el-input v-model="row.quantity"` `:disabled="readonly"`)、单价(`el-input v-model="row.unit_cost"` `:disabled="readonly"`)、小计(`lineSubtotal(row)` 只读)、操作(删行按钮 `removeLine(idx)`，`v-if="!readonly"`)。底部「+ 添加明细行」按钮 `@click="addLine"` `v-if="!readonly"`。
- **活动时间线**（仅 `dialogMode==='edit'` 显示）：`el-timeline` over `activities`，每项 `el-timeline-item :timestamp="formatDateTime(a.created_at)"`，内容 `(a.from_status ? statusLabel(a.from_status) : '—') + ' → ' + (a.to_status ? statusLabel(a.to_status) : '—')` + `a.comment`。
  - > `from_status`/`to_status` 是宽松 string，映射时用 `STATUS_LABELS[s as PurchaseOrderStatus] ?? s` 兜底。

**dialog footer 状态流转按钮**（按 `editingStatus` + 权限显隐；create 模式仅「保存」「取消」）：
- 「保存」`v-if="dialogMode==='create' || editingStatus==='DRAFT'"` 且有 create/edit 权限：`submitForm`。
- 「提交」`v-if="dialogMode==='edit' && editingStatus==='DRAFT' && auth.hasPermission('purchase_order.edit')"` → `submitPurchaseOrder(editingId.value)` → 成功 + 关闭 + fetchOrders。
- 「批准」`v-if="dialogMode==='edit' && editingStatus==='SUBMITTED' && auth.hasPermission('purchase_order.approve')"` → `ElMessageBox.confirm('批准后将按明细自动入库，确认？','提示',{type:'warning'})` → `approvePurchaseOrder(editingId.value, { note: '' })` → 成功 + 关闭 + fetchOrders。
- 「驳回」`v-if="...SUBMITTED && purchase_order.approve"` → `rejectPurchaseOrder(editingId.value, { note: '' })` → 成功 + 关闭 + fetchOrders。
- 「取消」`v-if="dialogMode==='edit' && (editingStatus==='DRAFT' || editingStatus==='SUBMITTED') && auth.hasPermission('purchase_order.edit')"` → `cancelPurchaseOrder(editingId.value, { note: '' })` → 成功 + 关闭 + fetchOrders。
- 「关闭对话框」按钮（始终，文案用「关闭对话框」避免与状态「取消」/表单文案冲突）。

> 状态流转各动作统一封装：`async function runAction(fn: () => Promise<unknown>) { try { actionLoading=true; await fn(); ElMessage.success('操作成功'); dialogVisible.value=false; await fetchOrders() } catch { ElMessage.error('操作失败，请重试') } finally { actionLoading=false } }`。批准前先 `await ElMessageBox.confirm(...)`（用户取消则不进 runAction）。

**submitForm**（保存，仅 create 或 DRAFT 编辑）：校验 `form.vendor_id`（空则 `ElMessage.warning('请选择供应商')` 返回）；payload：
```typescript
const payload = {
  vendor_id: form.vendor_id,
  category_id: form.category_id,
  notes: form.notes,
  shipping_address: form.shipping_address,
  shipping_method: form.shipping_method,
  terms_of_payment: form.terms_of_payment,
  expected_delivery_date: form.expected_delivery_date || null,
  lines: form.lines.map((l) => ({
    part_id: l.part_id,
    quantity: l.quantity,
    unit_cost: l.unit_cost,
  })),
}
```
create→`createPurchaseOrder(payload)`、edit→`updatePurchaseOrder(editingId.value, payload)`；成功 + ElMessage.success + 关闭 + fetchOrders；try/catch 本地化。

**handleDelete(row)**：`ElMessageBox.confirm('确认删除采购单「'+row.custom_id+'」？',...)` → `deletePurchaseOrder(row.id)` → 重拉；catch 静默。

**内嵌**：`<PurchaseOrderCategoryManageDialog v-model:visible="categoryDialogVisible" />`（无 changed 消费——本 view 不展示分类列表；或 `@changed` 空操作。简化：不绑 changed）。

**defineExpose**：`defineExpose({ form, addLine, removeLine, openEdit, openCreate })`（供测试驱动）。

模板根 `<div class="page">` + page-title + toolbar，scoped style 仿 LocationsView（dialog 内分区可加少量间距样式）。

- [ ] **Step 4: 跑绿 + 门禁** `npm run test -- PurchaseOrdersView && npm run test && npm run typecheck`。`npx prettier --write "src/views/inventory/PurchaseOrdersView.vue" "tests/unit/PurchaseOrdersView.spec.ts"`。

- [ ] **Step 5: commit**

```bash
git add src/views/inventory/PurchaseOrdersView.vue tests/unit/PurchaseOrdersView.spec.ts
git commit -m "feat(fe-inventory): purchase orders view with editable lines, activity timeline & status transitions

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: RBAC 门控统一核对 + 收尾

**Files:** 跨 views/components（核对）；Test：跑全量

- [ ] **Step 1:** 逐文件核对写动作门控 code 与后端 `backend/app/permissions.py` 一致：
  - VendorsView：`vendor.create/edit/delete`。
  - CustomersView：`customer.create/edit/delete`。
  - PartsView：`part.create/edit/delete`；管理分类入口 `part_category.view`。
  - PartCategoryManageDialog：增改删 `part_category.manage`。
  - PurchaseOrdersView：`purchase_order.create/edit/delete`、状态流转 提交/取消=`purchase_order.edit`、批准/驳回=`purchase_order.approve`；管理分类入口 `purchase_order_category.view`。
  - PurchaseOrderCategoryManageDialog：增改删 `purchase_order_category.manage`。
  用 `grep -rn "hasPermission('" src/views/inventory/ src/components/inventory/` 列出全部，逐个对照后端常量值核实拼写；有误最小修正，否则记「无需修改」。
- [ ] **Step 2:** AppSidebar：供应组 4 项 path 正确、无 soon；`activeMenu` 对 `/inventory/*` 高亮；与 `router/index.ts` 四路由 path 一致。
- [ ] **Step 3:** 全量门禁：
  ```
  cd frontend && npm run test && npm run typecheck && npx prettier --check "src/**/*.{ts,vue}" "tests/**/*.ts"
  ```
  test 全绿、typecheck 0 错；prettier 关注本分支 `git diff main...HEAD --name-only` 的 .ts/.vue（预存无关脏文件不动，本分支文件须干净）。
  > 后端无改动，不跑后端门禁。
- [ ] **Step 4: commit**（若有修正）：`chore(fe-inventory): RBAC gating audit + wrap-up`。若全部正确无改动，不造空 commit，汇报「核对通过」。

---

## 收尾

完成 T1–T7 后派发最终 code review，再用 `superpowers:finishing-a-development-branch`（合并/push 交人决定，不自动 push、不自合 main）。**本轮无 alembic 迁移**，合并无需 down_revision 协调，直接 `--no-ff`。

**自查清单：**
- 4 个 view 均扁平 `el-table` + `el-dialog`，组件内直调 api、`onMounted` 拉取。
- 备件：分类映射名 + 低库存 tag + 低库存过滤开关；表单全字段分组；数值字段字符串、空串兜底 '0'；不传 pm_ids。
- 采购单：宽对话框分区（基本信息 + 可编辑明细行子表 + 活动时间线）；状态流转按钮按 status + 权限显隐；批准前确认弹窗；非 DRAFT 只读；供应商名/状态中文映射；明细行增删 + 小计计算。
- 备件分类、采购单分类为页内嵌子组件对话框（含 description 字段），`changed` 事件驱动父重拉（采购单分类可不消费 changed）。
- RBAC：写动作按 hasPermission 隐藏；采购单状态按钮 edit/approve 分权；分类 manage。
- 导航供应组 4 项接入、无残留 soon；路由 4 条 requiresAuth。
- 仅中文、无新增 locale。`npm run typecheck` 0 错、vitest 全绿、prettier 干净。
