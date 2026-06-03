# FE-2 主数据前端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 主数据 4 块前端（位置树 / 资产树 / 资产分类 / 资产停机）——把已就绪的位置·资产·分类·停机后端变成可用界面。

**Architecture:** Vue 3 `<script setup lang="ts">` + Element Plus（**树形 `el-table`** 列表 + `el-dialog` 表单）+ Pinia（仅复用 `auth` store 做 RBAC 门控）+ vue-router 扁平路由。位置/资产树由**单次扁平 GET** 客户端纯函数组装（`buildTree`），父级选择器用 `collectDescendantIds` 排除自身+后代防环。资产分类、停机为资产页内嵌子组件对话框。**纯前端，无后端改动、无迁移。**

**Tech Stack:** Vite + TS + Element Plus + Pinia + vue-router + vitest + `@vue/test-utils`。门禁：`npm run typecheck`（vue-tsc --noEmit）+ prettier + `npm run test`（vitest）。

**全局约定（每任务适用）：**
- 工作目录 `frontend/`；命令 `npm run ...`。分支 `feat/fe-maindata`（基于 main，spec 已提交）。
- 每任务：写测试 → 跑红 → 实现 → `npm run test` + `npm run typecheck` 绿 → prettier → commit。
- commit message 结尾附：`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- 仅中文、不做 i18n。RBAC：`const auth = useAuthStore()`；写动作按钮 `v-if="auth.hasPermission('<code>')"`（super_admin 通配）。
- 精确 `git add`，**勿纳入**仓库根未跟踪产物（`.claude/scheduled_tasks.lock`、`.verify-screenshots/*.png`）。

**既有模式参考（须遵循，FE-1 已落定）：**
- api：`src/api/fields.ts` / FE-1 的 `src/api/users.ts`（`http.get<T>(path).then(r=>r.data)`；delete 用 `http.delete(path).then(()=>undefined)`；http 实例 baseURL 已含 `/api/v1`，路径写 `/locations`）。
- view：`src/views/platform/UsersView.vue`（state 分区 + onMounted 并行 fetch + el-table + 单 dialog 多模式 + submitForm try/catch/finally + 本地化 `ElMessage.error('保存失败，请重试')` + `ElMessageBox.confirm` 删除 + RBAC v-if）。
- api 测试：`tests/unit/platformApi.spec.ts`（`vi.hoisted` + `vi.mock('@/api/http')`）。
- view 测试：`tests/unit/UsersView.spec.ts` / `RolesView.spec.ts`（`vi.mock('@/api/<x>')` + `vi.mock('@/store/auth')` + `mount(View,{global:{plugins:[ElementPlus]}})` + `flushPromises`；断言定位单元格/payload，勿脆弱全文）。
- 导航：`src/components/AppSidebar.vue`（`groups`/computed，「维护」组 6 项现全 `soon`）。
- 路由：`src/router/index.ts`（扁平 + `meta.requiresAuth`；`requiredPermission` 已是合法 meta key）。
- 工具：`src/utils/format.ts` 的 `formatDateTime`（null→兜底）。

**后端契约（已核实，types 以此为准）：**
- LocationRead `{id, custom_id, name, description, parent_id|null, address, longitude|null, latitude|null, assigned_user_ids[], team_ids[]}`；Create/Update 同（Update 全可选）；Mini `{id, name, custom_id}`。
- AssetStatus 7 值：`OPERATIONAL/STANDBY/MODERNIZATION/INSPECTION_SCHEDULED/COMMISSIONING/EMERGENCY_SHUTDOWN/DOWN`。
- AssetRead `{id, custom_id, name, description, parent_id|null, location_id|null, category_id|null, status, serial_number, model, manufacturer, power, warranty_expiration_date|null, in_service_date|null, acquisition_cost|null, barcode|null, nfc_id|null, primary_user_id|null, assigned_user_ids[], team_ids[]}`；Create/Update 同；Mini `{id, name, custom_id}`。
- AssetCategoryRead `{id, name}`；Create `{name}`；Update `{name?}`。
- DowntimeRead `{id, asset_id, started_at, ended_at|null, reason, downtime_type, source_asset_id|null}`；Create `{started_at, ended_at?, reason?, downtime_type?}`；Close `{ended_at}`。
- 端点（baseURL 已含 /api/v1）：`/locations`(GET 无参=全量, POST, PATCH/DELETE /{id})、`/locations/mini`；`/assets`(同) `/assets/mini`、`/assets/{id}/downtimes`(GET/POST)、`/assets/{id}/downtimes/{dtId}`(PATCH 关闭)；`/asset-categories`(GET/POST, PATCH/DELETE /{id})。
- 权限 code：`location.view/create/edit/delete`、`asset.view/create/edit/delete`、`asset_category.view/asset_category.manage`、下拉读 `user.view`/`team.view`。

---

## Task 1: 前端骨架（api + types + 树工具 + 路由 + 导航 + 占位页）

**Files:**
- Create: `src/api/{locations,assets,assetCategories}.ts`
- Create: `src/types/maindata.ts`
- Create: `src/utils/tree.ts`
- Create: `src/views/maindata/{Locations,Assets}View.vue`（占位骨架）
- Modify: `src/router/index.ts`、`src/components/AppSidebar.vue`
- Test: `tests/unit/maindataApi.spec.ts`、`tests/unit/tree.spec.ts`、`tests/unit/AppSidebar.spec.ts`（追加）

- [ ] **Step 1: 写失败测试（树工具）`tests/unit/tree.spec.ts`**

```typescript
import { describe, expect, it } from 'vitest'
import { buildTree, collectDescendantIds } from '@/utils/tree'

interface Node { id: string; parent_id: string | null; name: string }
const flat: Node[] = [
  { id: 'a', parent_id: null, name: 'A' },
  { id: 'b', parent_id: 'a', name: 'B' },
  { id: 'c', parent_id: 'b', name: 'C' },
  { id: 'd', parent_id: null, name: 'D' },
]

describe('buildTree', () => {
  it('按 parent_id 组装为森林并挂 children', () => {
    const tree = buildTree(flat)
    expect(tree.map((n) => n.id)).toEqual(['a', 'd'])
    expect(tree[0].children?.map((n) => n.id)).toEqual(['b'])
    expect(tree[0].children?.[0].children?.map((n) => n.id)).toEqual(['c'])
    expect(tree[1].children).toBeUndefined()
  })
  it('不污染原对象（不给叶子加空 children）', () => {
    const tree = buildTree(flat)
    expect(tree[1].children).toBeUndefined()
  })
})

describe('collectDescendantIds', () => {
  it('返回自身 + 全部后代 id', () => {
    expect([...collectDescendantIds(flat, 'a')].sort()).toEqual(['a', 'b', 'c'])
    expect([...collectDescendantIds(flat, 'b')].sort()).toEqual(['b', 'c'])
    expect([...collectDescendantIds(flat, 'd')].sort()).toEqual(['d'])
  })
})
```

- [ ] **Step 2: 写失败测试（api）`tests/unit/maindataApi.spec.ts`**

```typescript
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get, post, patch, del } = vi.hoisted(() => ({
  get: vi.fn(), post: vi.fn(), patch: vi.fn(), del: vi.fn(),
}))
vi.mock('@/api/http', () => ({ http: { get, post, patch, delete: del } }))

import { listLocations, listLocationsMini, createLocation, updateLocation, deleteLocation } from '@/api/locations'
import {
  listAssets, listAssetsMini, createAsset, updateAsset, deleteAsset,
  listDowntimes, addDowntime, closeDowntime,
} from '@/api/assets'
import { listAssetCategories, createAssetCategory, updateAssetCategory, deleteAssetCategory } from '@/api/assetCategories'

describe('maindata api', () => {
  beforeEach(() => { for (const m of [get, post, patch, del]) m.mockReset().mockResolvedValue({ data: [] }) })

  it('listLocations GET /locations', async () => { await listLocations(); expect(get).toHaveBeenCalledWith('/locations') })
  it('listLocationsMini GET /locations/mini', async () => { await listLocationsMini(); expect(get).toHaveBeenCalledWith('/locations/mini') })
  it('createLocation POST /locations', async () => {
    await createLocation({ name: 'L' }); expect(post).toHaveBeenCalledWith('/locations', { name: 'L' })
  })
  it('updateLocation PATCH /locations/{id}', async () => {
    await updateLocation('l1', { name: 'X' }); expect(patch).toHaveBeenCalledWith('/locations/l1', { name: 'X' })
  })
  it('deleteLocation DELETE /locations/{id}', async () => { await deleteLocation('l1'); expect(del).toHaveBeenCalledWith('/locations/l1') })

  it('listAssets GET /assets', async () => { await listAssets(); expect(get).toHaveBeenCalledWith('/assets') })
  it('listAssetsMini GET /assets/mini', async () => { await listAssetsMini(); expect(get).toHaveBeenCalledWith('/assets/mini') })
  it('createAsset POST /assets', async () => {
    await createAsset({ name: 'A', status: 'OPERATIONAL' }); expect(post).toHaveBeenCalledWith('/assets', { name: 'A', status: 'OPERATIONAL' })
  })
  it('updateAsset PATCH /assets/{id}', async () => {
    await updateAsset('a1', { status: 'DOWN' }); expect(patch).toHaveBeenCalledWith('/assets/a1', { status: 'DOWN' })
  })
  it('deleteAsset DELETE /assets/{id}', async () => { await deleteAsset('a1'); expect(del).toHaveBeenCalledWith('/assets/a1') })
  it('listDowntimes GET /assets/{id}/downtimes', async () => { await listDowntimes('a1'); expect(get).toHaveBeenCalledWith('/assets/a1/downtimes') })
  it('addDowntime POST /assets/{id}/downtimes', async () => {
    await addDowntime('a1', { started_at: '2026-06-01T00:00:00', reason: 'r' })
    expect(post).toHaveBeenCalledWith('/assets/a1/downtimes', { started_at: '2026-06-01T00:00:00', reason: 'r' })
  })
  it('closeDowntime PATCH /assets/{id}/downtimes/{dtId}', async () => {
    await closeDowntime('a1', 'd1', { ended_at: '2026-06-02T00:00:00' })
    expect(patch).toHaveBeenCalledWith('/assets/a1/downtimes/d1', { ended_at: '2026-06-02T00:00:00' })
  })

  it('listAssetCategories GET /asset-categories', async () => { await listAssetCategories(); expect(get).toHaveBeenCalledWith('/asset-categories') })
  it('createAssetCategory POST /asset-categories', async () => {
    await createAssetCategory({ name: 'C' }); expect(post).toHaveBeenCalledWith('/asset-categories', { name: 'C' })
  })
  it('updateAssetCategory PATCH /asset-categories/{id}', async () => {
    await updateAssetCategory('c1', { name: 'C2' }); expect(patch).toHaveBeenCalledWith('/asset-categories/c1', { name: 'C2' })
  })
  it('deleteAssetCategory DELETE /asset-categories/{id}', async () => { await deleteAssetCategory('c1'); expect(del).toHaveBeenCalledWith('/asset-categories/c1') })
})
```

- [ ] **Step 3: 跑红**

Run: `cd frontend && npm run test -- maindataApi tree`
Expected: FAIL（模块不存在）。

- [ ] **Step 4: types `src/types/maindata.ts`**

```typescript
export type AssetStatus =
  | 'OPERATIONAL' | 'STANDBY' | 'MODERNIZATION' | 'INSPECTION_SCHEDULED'
  | 'COMMISSIONING' | 'EMERGENCY_SHUTDOWN' | 'DOWN'

export interface LocationRead {
  id: string; custom_id: string; name: string; description: string
  parent_id: string | null; address: string
  longitude: number | null; latitude: number | null
  assigned_user_ids: string[]; team_ids: string[]
}
export interface LocationCreate {
  name: string; description?: string; parent_id?: string | null; address?: string
  longitude?: number | null; latitude?: number | null
  assigned_user_ids?: string[]; team_ids?: string[]
}
export type LocationUpdate = Partial<LocationCreate>
export interface LocationMini { id: string; name: string; custom_id: string }

export interface AssetRead {
  id: string; custom_id: string; name: string; description: string
  parent_id: string | null; location_id: string | null; category_id: string | null
  status: AssetStatus; serial_number: string; model: string; manufacturer: string; power: string
  warranty_expiration_date: string | null; in_service_date: string | null
  acquisition_cost: string | null; barcode: string | null; nfc_id: string | null
  primary_user_id: string | null; assigned_user_ids: string[]; team_ids: string[]
}
export interface AssetCreate {
  name: string; description?: string; parent_id?: string | null
  location_id?: string | null; category_id?: string | null; status?: AssetStatus
  serial_number?: string; model?: string; manufacturer?: string; power?: string
  warranty_expiration_date?: string | null; in_service_date?: string | null
  acquisition_cost?: string | null; barcode?: string | null; nfc_id?: string | null
  primary_user_id?: string | null; assigned_user_ids?: string[]; team_ids?: string[]
}
export type AssetUpdate = Partial<AssetCreate>
export interface AssetMini { id: string; name: string; custom_id: string }

export interface AssetCategoryRead { id: string; name: string }
export interface AssetCategoryCreate { name: string }
export interface AssetCategoryUpdate { name?: string }

export interface DowntimeRead {
  id: string; asset_id: string; started_at: string; ended_at: string | null
  reason: string; downtime_type: string; source_asset_id: string | null
}
export interface DowntimeCreate { started_at: string; ended_at?: string | null; reason?: string; downtime_type?: string }
export interface DowntimeClose { ended_at: string }
```

- [ ] **Step 5: 树工具 `src/utils/tree.ts`**

```typescript
export interface TreeNode {
  id: string
  parent_id: string | null
  children?: TreeNode[]
}

/** 由扁平表按 parent_id 组装为森林；叶子不挂空 children（避免 el-table 误显展开箭头）。 */
export function buildTree<T extends { id: string; parent_id: string | null }>(
  flat: T[],
): (T & { children?: (T & { children?: unknown[] })[] })[] {
  const byId = new Map<string, T & { children?: unknown[] }>()
  for (const item of flat) byId.set(item.id, { ...item })
  const roots: (T & { children?: unknown[] })[] = []
  for (const node of byId.values()) {
    if (node.parent_id != null && byId.has(node.parent_id)) {
      const parent = byId.get(node.parent_id)!
      ;(parent.children ??= []).push(node)
    } else {
      roots.push(node)
    }
  }
  // eslint 安全：返回类型对 el-table 足够（行对象含可选 children）
  return roots as (T & { children?: (T & { children?: unknown[] })[] })[]
}

/** 自身 + 全部后代 id（供父级选择器排除，防成环）。 */
export function collectDescendantIds<T extends { id: string; parent_id: string | null }>(
  flat: T[],
  rootId: string,
): Set<string> {
  const childrenOf = new Map<string, string[]>()
  for (const item of flat) {
    if (item.parent_id != null) (childrenOf.get(item.parent_id) ?? childrenOf.set(item.parent_id, []).get(item.parent_id)!).push(item.id)
  }
  const out = new Set<string>()
  const stack = [rootId]
  while (stack.length) {
    const id = stack.pop()!
    if (out.has(id)) continue
    out.add(id)
    for (const child of childrenOf.get(id) ?? []) stack.push(child)
  }
  return out
}
```
> 实现者：若上面 `childrenOf` 的一行 map-or-set 写法触发 lint，改成显式 if 分支即可，行为不变（按 parent_id 归集子 id）。`buildTree` 的 `as` 断言用于满足 vue-tsc；如有更干净写法可替换，但须保持「叶子无 children 键」与测试一致。

- [ ] **Step 6: api 客户端**

`src/api/locations.ts`：
```typescript
import { http } from './http'
import type { LocationRead, LocationCreate, LocationUpdate, LocationMini } from '@/types/maindata'

export const listLocations = () => http.get<LocationRead[]>('/locations').then((r) => r.data)
export const listLocationsMini = () => http.get<LocationMini[]>('/locations/mini').then((r) => r.data)
export const createLocation = (p: LocationCreate) => http.post<LocationRead>('/locations', p).then((r) => r.data)
export const updateLocation = (id: string, p: LocationUpdate) =>
  http.patch<LocationRead>(`/locations/${id}`, p).then((r) => r.data)
export const deleteLocation = (id: string) => http.delete(`/locations/${id}`).then(() => undefined)
```

`src/api/assets.ts`：
```typescript
import { http } from './http'
import type {
  AssetRead, AssetCreate, AssetUpdate, AssetMini,
  DowntimeRead, DowntimeCreate, DowntimeClose,
} from '@/types/maindata'

export const listAssets = () => http.get<AssetRead[]>('/assets').then((r) => r.data)
export const listAssetsMini = () => http.get<AssetMini[]>('/assets/mini').then((r) => r.data)
export const createAsset = (p: AssetCreate) => http.post<AssetRead>('/assets', p).then((r) => r.data)
export const updateAsset = (id: string, p: AssetUpdate) => http.patch<AssetRead>(`/assets/${id}`, p).then((r) => r.data)
export const deleteAsset = (id: string) => http.delete(`/assets/${id}`).then(() => undefined)
export const listDowntimes = (assetId: string) =>
  http.get<DowntimeRead[]>(`/assets/${assetId}/downtimes`).then((r) => r.data)
export const addDowntime = (assetId: string, p: DowntimeCreate) =>
  http.post<DowntimeRead>(`/assets/${assetId}/downtimes`, p).then((r) => r.data)
export const closeDowntime = (assetId: string, downtimeId: string, p: DowntimeClose) =>
  http.patch<DowntimeRead>(`/assets/${assetId}/downtimes/${downtimeId}`, p).then((r) => r.data)
```

`src/api/assetCategories.ts`：
```typescript
import { http } from './http'
import type { AssetCategoryRead, AssetCategoryCreate, AssetCategoryUpdate } from '@/types/maindata'

export const listAssetCategories = () => http.get<AssetCategoryRead[]>('/asset-categories').then((r) => r.data)
export const createAssetCategory = (p: AssetCategoryCreate) =>
  http.post<AssetCategoryRead>('/asset-categories', p).then((r) => r.data)
export const updateAssetCategory = (id: string, p: AssetCategoryUpdate) =>
  http.patch<AssetCategoryRead>(`/asset-categories/${id}`, p).then((r) => r.data)
export const deleteAssetCategory = (id: string) => http.delete(`/asset-categories/${id}`).then(() => undefined)
```

- [ ] **Step 7: 占位视图**

`src/views/maindata/LocationsView.vue` 与 `AssetsView.vue` 先建最简骨架（懒加载用）：
```vue
<script setup lang="ts"></script>
<template><div class="page">位置</div></template>
```
（AssetsView 标题「资产」。）

- [ ] **Step 8: 路由 `src/router/index.ts` 加 2 条**

```typescript
  { path: '/maindata/locations', name: 'maindata-locations',
    component: () => import('@/views/maindata/LocationsView.vue'),
    meta: { title: '位置', requiresAuth: true, requiredPermission: 'location.view' } },
  { path: '/maindata/assets', name: 'maindata-assets',
    component: () => import('@/views/maindata/AssetsView.vue'),
    meta: { title: '资产', requiresAuth: true, requiredPermission: 'asset.view' } },
```

- [ ] **Step 9: 导航接线 `src/components/AppSidebar.vue`**

「维护」组：把 `{ label: '资产', soon: true }` 改 `{ label: '资产', path: '/maindata/assets' }`，`{ label: '位置', soon: true }` 改 `{ label: '位置', path: '/maindata/locations' }`；其余四项（工单/请求/预防性维护/计量）保持 `soon`。
`activeMenu` computed 增加：`if (route.path.startsWith('/maindata/')) return route.path`。

`tests/unit/AppSidebar.spec.ts`：先读其现有结构，追加断言——「维护」组中 资产/位置 两项有 `path`、无 `soon`（不渲染「即将上线」）；工单/请求/预防性维护/计量 仍 `soon`。既有断言不破。

- [ ] **Step 10: 跑绿 + 门禁**

Run: `cd frontend && npm run test && npm run typecheck`
Expected: PASS / 0 errors。prettier：`npx prettier --write "src/api/{locations,assets,assetCategories}.ts" "src/types/maindata.ts" "src/utils/tree.ts" "src/views/maindata/*.vue" "tests/unit/{maindataApi,tree}.spec.ts" "src/router/index.ts" "src/components/AppSidebar.vue" "tests/unit/AppSidebar.spec.ts"`

- [ ] **Step 11: commit**

```bash
git add src/api/locations.ts src/api/assets.ts src/api/assetCategories.ts src/types/maindata.ts src/utils/tree.ts src/views/maindata/ src/router/index.ts src/components/AppSidebar.vue tests/unit/maindataApi.spec.ts tests/unit/tree.spec.ts tests/unit/AppSidebar.spec.ts
git commit -m "feat(fe-maindata): api clients + types + tree utils + routes + sidebar + placeholders

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: 位置 View（模板任务，完整展开）

**Files:** `src/views/maindata/LocationsView.vue`；Test: `tests/unit/LocationsView.spec.ts`

- [ ] **Step 1: 写失败测试 `tests/unit/LocationsView.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { ll, cl, ul, dl, lu, lt } = vi.hoisted(() => ({
  ll: vi.fn(), cl: vi.fn(), ul: vi.fn(), dl: vi.fn(), lu: vi.fn(), lt: vi.fn(),
}))
vi.mock('@/api/locations', () => ({
  listLocations: ll, createLocation: cl, updateLocation: ul, deleteLocation: dl,
}))
vi.mock('@/api/users', () => ({ listUsers: lu }))
vi.mock('@/api/teams', () => ({ listTeams: lt }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => true, user: { role_code: 'admin' } }),
}))

import LocationsView from '@/views/maindata/LocationsView.vue'

function mountView() {
  return mount(LocationsView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

beforeEach(() => {
  setActivePinia(createPinia())
  ll.mockReset().mockResolvedValue([
    { id: 'l1', custom_id: 'L-001', name: '总部大楼', description: '', parent_id: null, address: '北京', longitude: null, latitude: null, assigned_user_ids: [], team_ids: [] },
    { id: 'l2', custom_id: 'L-002', name: '3 楼', description: '', parent_id: 'l1', address: '', longitude: null, latitude: null, assigned_user_ids: [], team_ids: [] },
  ])
  cl.mockReset().mockResolvedValue({})
  ul.mockReset().mockResolvedValue({})
  dl.mockReset().mockResolvedValue(undefined)
  lu.mockReset().mockResolvedValue([{ id: 'u1', name: '张三', email: 'a@b.com', status: 'active', role_id: null, locale: 'zh', last_login_at: null, created_at: '2026-01-01T00:00:00Z' }])
  lt.mockReset().mockResolvedValue([{ id: 't1', name: '机械组', description: '', member_ids: [] }])
})

describe('LocationsView', () => {
  it('加载并渲染位置树行（含父子）', async () => {
    const w = mountView()
    await flushPromises()
    expect(ll).toHaveBeenCalled()
    expect(w.text()).toContain('总部大楼')
    expect(w.text()).toContain('3 楼')
    expect(w.text()).toContain('L-001')
  })

  it('新建提交携带 name', async () => {
    const w = mountView()
    await flushPromises()
    const addBtn = w.findAll('.el-button').find((b) => b.text() === '新建位置')
    expect(addBtn).toBeTruthy()
    await addBtn!.trigger('click')
    await flushPromises()
    const nameInput = document.querySelector('.el-dialog input[placeholder="请输入名称"]') as HTMLInputElement
    nameInput.value = '新机房'
    nameInput.dispatchEvent(new Event('input'))
    await flushPromises()
    const submitBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    submitBtn.click()
    await flushPromises()
    expect(cl).toHaveBeenCalled()
    expect(cl.mock.calls[0][0]).toMatchObject({ name: '新机房' })
  })

  it('删除经确认调用 deleteLocation', async () => {
    const { ElMessageBox } = await import('element-plus')
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    const w = mountView()
    await flushPromises()
    const delBtn = w.findAll('.el-button').find((b) => b.text() === '删除')
    await delBtn!.trigger('click')
    await flushPromises()
    expect(dl).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: 跑红** `cd frontend && npm run test -- LocationsView` → FAIL。

- [ ] **Step 3: 实现 `src/views/maindata/LocationsView.vue`**

`<script setup lang="ts">` 含（严格仿 `UsersView.vue` 的分区与流程）：
- import：vue 的 `ref/reactive/computed/onMounted`；`ElMessage/ElMessageBox`；`listLocations/createLocation/updateLocation/deleteLocation`、`listUsers`、`listTeams`、`useAuthStore`、`buildTree`/`collectDescendantIds`、types。
- state：`loading`、`locations = ref<LocationRead[]>([])`、`users`、`teams`、`tree = computed(() => buildTree(locations.value))`、dialog（`dialogVisible`、`dialogMode: 'create'|'edit'`、`editingId`、`submitting`、`form = reactive<{name,description,parent_id,address,longitude,latitude,assigned_user_ids,team_ids}>`）。
- `onMounted(async () => { await Promise.all([fetchLocations(), fetchUsers(), fetchTeams()]) })`。`fetchLocations` 内 `loading` try/finally。
- 父级下拉选项：`parentOptions = computed(() => { const excluded = dialogMode==='edit' && editingId.value ? collectDescendantIds(locations.value, editingId.value) : new Set<string>(); return locations.value.filter((l) => !excluded.has(l.id)) })`（编辑时排除自身+后代防环）。
- 表格：树形 `el-table`（`:data="tree"` `row-key="id"` `:tree-props="{ children: 'children' }"` `default-expand-all`），列：名称(prop name)、编号(custom_id)、地址(address)、操作。
- 顶部「新建位置」按钮 `v-if="auth.hasPermission('location.create')"`；行内 编辑 `v-if="auth.hasPermission('location.edit')"`、删除 `v-if="auth.hasPermission('location.delete')"`。
- dialog（`el-form`）：名称(必填, placeholder「请输入名称」)、描述、父位置(`el-select clearable` options=parentOptions，label=`name`，value=`id`)、地址、经度(`el-input-number` 或 number input)、纬度、负责人(`el-select multiple filterable` options=users，label=`name`，value=`id`)、团队(`el-select multiple` options=teams，label=`name`，value=`id`)。提交按钮文本「保存」。
- `openCreate`：`resetForm()` + mode='create' + visible。`openEdit(row)`：`resetForm()` + 回填 `Object.assign(form, { ...row, assigned_user_ids: [...row.assigned_user_ids], team_ids: [...row.team_ids] })` + mode='edit' + editingId。
- `submitForm`：校验 `form.name.trim()`；create→`createLocation(payload)`、edit→`updateLocation(editingId, payload)`，payload 含全部表单字段（经纬度空→null）；`try { submitting=true; ...; ElMessage.success; visible=false; await fetchLocations() } catch { ElMessage.error('保存失败，请重试') } finally { submitting=false }`。
- `handleDelete(row)`：`ElMessageBox.confirm('确认删除位置「'+row.name+'」？','提示',{type:'warning'})` → `deleteLocation(row.id)` → `ElMessage.success` + `fetchLocations()`；catch 静默。
- 模板根 `<div class="page">` + `.page-title` + `.toolbar`，样式仿 UsersView。

- [ ] **Step 4: 跑绿 + 门禁** `npm run test -- LocationsView && npm run test && npm run typecheck`。`npx prettier --write "src/views/maindata/LocationsView.vue" "tests/unit/LocationsView.spec.ts"`。

- [ ] **Step 5: commit**

```bash
git add src/views/maindata/LocationsView.vue tests/unit/LocationsView.spec.ts
git commit -m "feat(fe-maindata): locations tree view

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 资产分类管理对话框组件

**Files:** Create `src/components/maindata/AssetCategoryManageDialog.vue`；Test: `tests/unit/AssetCategoryManageDialog.spec.ts`

子组件：受控 `v-model:visible`（或 prop `visible` + emit `update:visible`），内部表格 + 增改删；分类变更后 `emit('changed')` 让父组件重拉分类。门控 `asset_category.manage`（读 `asset_category.view`）。

- [ ] **Step 1: 写失败测试 `tests/unit/AssetCategoryManageDialog.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lac, cac, uac, dac } = vi.hoisted(() => ({ lac: vi.fn(), cac: vi.fn(), uac: vi.fn(), dac: vi.fn() }))
vi.mock('@/api/assetCategories', () => ({
  listAssetCategories: lac, createAssetCategory: cac, updateAssetCategory: uac, deleteAssetCategory: dac,
}))
vi.mock('@/store/auth', () => ({ useAuthStore: () => ({ hasPermission: () => true }) }))

import AssetCategoryManageDialog from '@/components/maindata/AssetCategoryManageDialog.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  lac.mockReset().mockResolvedValue([{ id: 'c1', name: '泵' }, { id: 'c2', name: '电机' }])
  cac.mockReset().mockResolvedValue({})
  uac.mockReset().mockResolvedValue({})
  dac.mockReset().mockResolvedValue(undefined)
})

describe('AssetCategoryManageDialog', () => {
  it('可见时加载并渲染分类', async () => {
    mount(AssetCategoryManageDialog, { props: { visible: true }, global: { plugins: [ElementPlus] }, attachTo: document.body })
    await flushPromises()
    expect(lac).toHaveBeenCalled()
    expect(document.body.textContent).toContain('泵')
    expect(document.body.textContent).toContain('电机')
  })

  it('新增提交并 emit changed', async () => {
    const w = mount(AssetCategoryManageDialog, { props: { visible: true }, global: { plugins: [ElementPlus] }, attachTo: document.body })
    await flushPromises()
    const addBtn = Array.from(document.querySelectorAll('.el-button')).find((b) => b.textContent?.trim() === '新增分类') as HTMLElement
    addBtn.click()
    await flushPromises()
    const input = document.querySelector('.el-dialog input[placeholder="请输入分类名称"]') as HTMLInputElement
    input.value = '阀门'; input.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-button')).find((b) => b.textContent?.trim() === '保存') as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cac).toHaveBeenCalledWith({ name: '阀门' })
    expect(w.emitted('changed')).toBeTruthy()
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- AssetCategoryManageDialog` → FAIL。

- [ ] **Step 3: 实现 `src/components/maindata/AssetCategoryManageDialog.vue`**
- props：`visible: boolean`；emits：`update:visible`、`changed`。
- 用 `el-dialog :model-value="visible" @update:model-value="$emit('update:visible',$event)" title="管理分类"`。
- `watch(() => props.visible, v => { if (v) fetchCategories() })`（打开时拉取）。
- state：`categories = ref<AssetCategoryRead[]>([])`、内层编辑用小 dialog 或行内：用一个嵌套 `el-dialog`（`formVisible`、`form = reactive<{name}>`、`editingId`、`mode`）。
- 主 dialog 内：顶部「新增分类」按钮 `v-if="auth.hasPermission('asset_category.manage')"`；`el-table` 列 名称 + 操作（编辑/删除，`v-if asset_category.manage`）。
- 表单 dialog：`el-input` 名称(placeholder「请输入分类名称」)；保存按钮「保存」→ create `createAssetCategory({name})` / edit `updateAssetCategory(id,{name})` → `ElMessage.success` + 关表单 + `fetchCategories()` + `emit('changed')`；try/catch 本地化。
- 删除：`ElMessageBox.confirm` → `deleteAssetCategory(id)` → `fetchCategories()` + `emit('changed')`。

- [ ] **Step 4: 跑绿 + 门禁** `npm run test -- AssetCategoryManageDialog && npm run test && npm run typecheck`。prettier 两文件。

- [ ] **Step 5: commit**：`feat(fe-maindata): asset category manage dialog`。

---

## Task 4: 资产停机对话框组件

**Files:** Create `src/components/maindata/AssetDowntimeDialog.vue`；Test: `tests/unit/AssetDowntimeDialog.spec.ts`

子组件：props `visible` + `asset: AssetMini | AssetRead | null`（取 id/name）+ `assetName` 映射用的来源资产名（可传 `assetNameById: (id)=>string`，或仅显示 source_asset_id 原值并由父传映射函数；最简：props 传 `nameOf: (id: string|null)=>string` 用于来源列）。打开时拉 `listDowntimes(asset.id)`；新增手动停机 + 关闭未结束；操作后 `emit('changed')`（父可据此重拉资产以反映状态）。门控写=`asset.edit`。

- [ ] **Step 1: 写失败测试 `tests/unit/AssetDowntimeDialog.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { ld, ad, cd } = vi.hoisted(() => ({ ld: vi.fn(), ad: vi.fn(), cd: vi.fn() }))
vi.mock('@/api/assets', () => ({ listDowntimes: ld, addDowntime: ad, closeDowntime: cd }))
vi.mock('@/store/auth', () => ({ useAuthStore: () => ({ hasPermission: () => true }) }))

import AssetDowntimeDialog from '@/components/maindata/AssetDowntimeDialog.vue'

const asset = { id: 'a1', name: '泵 1', custom_id: 'A-001' }

beforeEach(() => {
  setActivePinia(createPinia())
  ld.mockReset().mockResolvedValue([
    { id: 'd1', asset_id: 'a1', started_at: '2026-06-01T08:00:00', ended_at: null, reason: '故障', downtime_type: 'manual', source_asset_id: null },
  ])
  ad.mockReset().mockResolvedValue({})
  cd.mockReset().mockResolvedValue({})
})

describe('AssetDowntimeDialog', () => {
  it('可见时加载并渲染停机历史', async () => {
    mount(AssetDowntimeDialog, { props: { visible: true, asset, nameOf: () => '—' }, global: { plugins: [ElementPlus] }, attachTo: document.body })
    await flushPromises()
    expect(ld).toHaveBeenCalledWith('a1')
    expect(document.body.textContent).toContain('故障')
  })

  it('关闭未结束停机调用 closeDowntime', async () => {
    const w = mount(AssetDowntimeDialog, { props: { visible: true, asset, nameOf: () => '—' }, global: { plugins: [ElementPlus] }, attachTo: document.body })
    await flushPromises()
    const closeBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find((b) => b.textContent?.trim() === '关闭') as HTMLElement
    expect(closeBtn).toBeTruthy()
    closeBtn.click()
    await flushPromises()
    // 关闭表单出现 → 选时间 → 确认；简化：组件用当前时间默认值，点确认即可
    const confirmBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find((b) => b.textContent?.trim() === '确认关闭') as HTMLElement
    confirmBtn.click()
    await flushPromises()
    expect(cd).toHaveBeenCalled()
    expect(cd.mock.calls[0][0]).toBe('a1')
    expect(w.emitted('changed')).toBeTruthy()
  })
})
```
> 实现者：关闭流程可设计为「点行内『关闭』→ 弹出 ended_at 选择（默认当前时间，用 el-date-picker type=datetime value-format=YYYY-MM-DDTHH:mm:ss）→『确认关闭』提交」。若你的交互按钮文案不同，请同步调整测试文案（保持断言语义：closeDowntime 被以 assetId 调用、emit changed）。

- [ ] **Step 2: 跑红** `npm run test -- AssetDowntimeDialog` → FAIL。

- [ ] **Step 3: 实现 `src/components/maindata/AssetDowntimeDialog.vue`**
- props：`visible: boolean`、`asset: { id: string; name: string } | null`、`nameOf: (id: string | null) => string`（来源资产名映射）。emits：`update:visible`、`changed`。
- `watch(() => props.visible, v => { if (v && props.asset) fetchDowntimes() })`。
- 主 `el-dialog` 标题 `'停机记录 — ' + (asset?.name ?? '')`。
- 表格列：开始(`formatDateTime(started_at)`)、结束(`ended_at ? formatDateTime : '—'`)、原因、类型(`downtime_type==='manual' ? '手动' : '级联'`)、来源(`nameOf(source_asset_id)`)、操作（未结束行显「关闭」按钮 `v-if="auth.hasPermission('asset.edit')"`）。
- 顶部「新增停机」按钮 `v-if="auth.hasPermission('asset.edit')"` → 内层表单 dialog：started_at(`el-date-picker type=datetime value-format="YYYY-MM-DDTHH:mm:ss"`，必填)、reason(`el-input`)；保存按钮「保存」→ `addDowntime(asset.id, {started_at, reason})` → 成功 + 关表单 + `fetchDowntimes()` + `emit('changed')`。
- 关闭流程：行内「关闭」→ 设置 `closingId` + 内层「关闭停机」dialog（ended_at date-picker，默认当前时间字符串）→「确认关闭」→ `closeDowntime(asset.id, closingId, {ended_at})` → 成功 + `fetchDowntimes()` + `emit('changed')`。
- 所有写动作 try/catch 本地化 `ElMessage.error`。

- [ ] **Step 4: 跑绿 + 门禁** 同上模式。prettier 两文件。

- [ ] **Step 5: commit**：`feat(fe-maindata): asset downtime dialog`。

---

## Task 5: 资产 View（主体，内嵌分类 + 停机对话框）

**Files:** `src/views/maindata/AssetsView.vue`；Test: `tests/unit/AssetsView.spec.ts`

按 Task 2（位置 View）的结构与流程，delta 如下。

- [ ] **Step 1: 写失败测试 `tests/unit/AssetsView.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { la, ca, ua, da } = vi.hoisted(() => ({ la: vi.fn(), ca: vi.fn(), ua: vi.fn(), da: vi.fn() }))
vi.mock('@/api/assets', () => ({
  listAssets: la, createAsset: ca, updateAsset: ua, deleteAsset: da,
  listDowntimes: vi.fn().mockResolvedValue([]), addDowntime: vi.fn(), closeDowntime: vi.fn(),
}))
const { lac } = vi.hoisted(() => ({ lac: vi.fn() }))
vi.mock('@/api/assetCategories', () => ({
  listAssetCategories: lac, createAssetCategory: vi.fn(), updateAssetCategory: vi.fn(), deleteAssetCategory: vi.fn(),
}))
const { llm } = vi.hoisted(() => ({ llm: vi.fn() }))
vi.mock('@/api/locations', () => ({ listLocationsMini: llm }))
vi.mock('@/api/users', () => ({ listUsers: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/teams', () => ({ listTeams: vi.fn().mockResolvedValue([]) }))
vi.mock('@/store/auth', () => ({ useAuthStore: () => ({ hasPermission: () => true, user: { role_code: 'admin' } }) }))

import AssetsView from '@/views/maindata/AssetsView.vue'

function mountView() {
  return mount(AssetsView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

beforeEach(() => {
  setActivePinia(createPinia())
  la.mockReset().mockResolvedValue([
    { id: 'a1', custom_id: 'A-001', name: '泵 1', description: '', parent_id: null, location_id: 'l1', category_id: 'c1', status: 'OPERATIONAL', serial_number: '', model: '', manufacturer: '', power: '', warranty_expiration_date: null, in_service_date: null, acquisition_cost: null, barcode: null, nfc_id: null, primary_user_id: null, assigned_user_ids: [], team_ids: [] },
    { id: 'a2', custom_id: 'A-002', name: '子泵', description: '', parent_id: 'a1', location_id: null, category_id: null, status: 'DOWN', serial_number: '', model: '', manufacturer: '', power: '', warranty_expiration_date: null, in_service_date: null, acquisition_cost: null, barcode: null, nfc_id: null, primary_user_id: null, assigned_user_ids: [], team_ids: [] },
  ])
  ca.mockReset().mockResolvedValue({})
  ua.mockReset().mockResolvedValue({})
  da.mockReset().mockResolvedValue(undefined)
  lac.mockReset().mockResolvedValue([{ id: 'c1', name: '泵类' }])
  llm.mockReset().mockResolvedValue([{ id: 'l1', name: '总部大楼', custom_id: 'L-001' }])
})

describe('AssetsView', () => {
  it('加载并渲染资产树 + 状态/位置/分类映射', async () => {
    const w = mountView()
    await flushPromises()
    expect(la).toHaveBeenCalled()
    expect(w.text()).toContain('泵 1')
    expect(w.text()).toContain('子泵')        // 子行（树）
    expect(w.text()).toContain('总部大楼')     // location_id→name
    expect(w.text()).toContain('泵类')         // category_id→name
    expect(w.text()).toContain('运行中')       // OPERATIONAL→中文状态
  })

  it('新建提交携带 name+status', async () => {
    const w = mountView()
    await flushPromises()
    const addBtn = w.findAll('.el-button').find((b) => b.text() === '新建资产')
    await addBtn!.trigger('click')
    await flushPromises()
    const nameInput = document.querySelector('.el-dialog input[placeholder="请输入名称"]') as HTMLInputElement
    nameInput.value = '新设备'; nameInput.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find((b) => b.textContent?.trim() === '保存') as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(ca).toHaveBeenCalled()
    expect(ca.mock.calls[0][0]).toMatchObject({ name: '新设备' })
    expect(ca.mock.calls[0][0]).toHaveProperty('status')
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- AssetsView` → FAIL。

- [ ] **Step 3: 实现 `src/views/maindata/AssetsView.vue`**

仿 LocationsView 结构，delta：
- 额外 import：`listAssetCategories`、`listLocationsMini`、`AssetCategoryManageDialog`、`AssetDowntimeDialog`、`AssetStatus` 等。
- 状态中文映射常量：
  ```typescript
  const STATUS_LABELS: Record<AssetStatus, string> = {
    OPERATIONAL: '运行中', STANDBY: '待机', MODERNIZATION: '改造中',
    INSPECTION_SCHEDULED: '待检', COMMISSIONING: '调试中',
    EMERGENCY_SHUTDOWN: '紧急停机', DOWN: '停机',
  }
  const UP_STATUSES = new Set<AssetStatus>(['OPERATIONAL', 'STANDBY', 'INSPECTION_SCHEDULED', 'COMMISSIONING'])
  const STATUS_OPTIONS = (Object.keys(STATUS_LABELS) as AssetStatus[]).map((v) => ({ value: v, label: STATUS_LABELS[v] }))
  ```
  状态 tag type：`UP_STATUSES.has(status) ? 'success' : 'danger'`。
- state：`assets`、`categories`、`locationsMini`、`users`、`teams`；`tree = computed(() => buildTree(assets.value))`；映射函数 `locationName(id)`、`categoryName(id)`、`assetName(id)`（用于停机来源）。
- `onMounted` 并行：`Promise.all([fetchAssets(), fetchCategories(), fetchLocationsMini(), fetchUsers(), fetchTeams()])`。
- 表格树形（同 Task 2 props），列：名称、编号、状态（`el-tag :type` + `STATUS_LABELS`）、位置（`locationName(row.location_id)`）、分类（`categoryName(row.category_id)`）、操作（编辑 `asset.edit` / 停机记录 `asset.view` / 删除 `asset.delete`）。
- 顶部：「新建资产」`v-if="asset.create"`、「管理分类」按钮（打开 `AssetCategoryManageDialog`）。
- 资产 dialog（`el-form`，全字段分组，用 `el-divider` 或小标题分组）：
  - 基本：名称(必填, placeholder「请输入名称」)、描述、状态(`el-select` options=STATUS_OPTIONS；旁 `el-text`/提示「切换 运行↔停机 类状态将自动级联子资产」)。
  - 层级与归属：父资产(`el-select clearable` options=parentOptions[排除自身+后代]，label=name，value=id)、位置(`el-select clearable` options=locationsMini，label=name，value=id)、分类(`el-select clearable` options=categories，label=name，value=id)。
  - 设备：序列号、型号、制造商、功率（均 `el-input`）。
  - 采购与保修：购置成本(`el-input`，提交时空串→null，非空→字符串原样)、启用日期(`el-date-picker type=date value-format="YYYY-MM-DD"`)、保修到期(同)。
  - 标识：条码、NFC（`el-input`）。
  - 人员与团队：主负责人(`el-select clearable filterable` options=users)、分配用户(`el-select multiple filterable`)、团队(`el-select multiple`)。
  - 保存按钮「保存」。`form` 默认 `status: 'OPERATIONAL'`。
- `openEdit`：回填 row（数组字段深拷贝；date/cost 字段直接用 row 值，null→''）。`parentOptions` 编辑时排除 `collectDescendantIds(assets.value, editingId)`。
- `submitForm`：payload 含全部字段；空字符串的可选标识/日期/成本→`null`，数组照传；create→`createAsset`、edit→`updateAsset`；成功 + 重拉 + 关闭；try/catch 本地化。
- 行内「停机记录」：设 `downtimeAsset = row` + 打开 `AssetDowntimeDialog`（传 `:asset`、`:nameOf="assetName"`，`@changed="fetchAssets"`）。
- 「管理分类」：`AssetCategoryManageDialog`（`v-model:visible`，`@changed="fetchCategories"`）。
- 删除：`ElMessageBox.confirm` → `deleteAsset` → 重拉。

- [ ] **Step 4: 跑绿 + 门禁** `npm run test -- AssetsView && npm run test && npm run typecheck`。prettier 两文件。

- [ ] **Step 5: commit**：`feat(fe-maindata): assets tree view with full form, category & downtime dialogs`。

---

## Task 6: RBAC 门控统一核对 + 收尾

**Files:** 跨 views/components（核对）；Test: 跑全量

- [ ] **Step 1:** 逐文件核对写动作门控 code 与后端一致：
  - LocationsView：`location.create/edit/delete`。
  - AssetsView：`asset.create/edit/delete`；停机记录入口与停机写=`asset.edit`（`AssetDowntimeDialog` 内写按钮 `asset.edit`）。
  - AssetCategoryManageDialog：增改删=`asset_category.manage`。
  对照 `backend/app/permissions.py`（`location.*`、`asset.*`、`asset_category.manage`）逐个 grep 核实拼写；有误最小修正，否则记「无需修改」。
- [ ] **Step 2:** AppSidebar：维护组 资产/位置 path 正确、无 soon；`activeMenu` 对 `/maindata/*` 高亮；与 `router/index.ts` 两路由 path 一致。
- [ ] **Step 3:** 全量门禁：
  ```
  cd frontend && npm run test && npm run typecheck && npx prettier --check "src/**/*.{ts,vue}" "tests/**/*.ts"
  ```
  test 全绿、typecheck 0 错；prettier 仅关注本分支 `git diff main...HEAD --name-only` 的 .ts/.vue（预存无关脏文件不动，本分支文件须干净）。
  > 后端无改动，不跑后端门禁。
- [ ] **Step 4: commit**（若有修正）：`chore(fe-maindata): RBAC gating audit + wrap-up`。若全部正确无改动，不造空 commit，汇报「核对通过」。

---

## 收尾

完成 T1–T6 后派发最终 code review，再用 `superpowers:finishing-a-development-branch`（合并/push 交人决定，不自动 push、不自合 main）。**本轮无 alembic 迁移**，合并无需 down_revision 协调，直接 `--no-ff`。

**自查清单：**
- 位置/资产 均树形 `el-table`（客户端 buildTree 组装）+ `el-dialog`，组件内直调 api、`onMounted` 拉取。
- 父级选择器排除自身+后代防环（`collectDescendantIds`）。
- 资产全字段分组表单；状态 7 值中文 tag；位置/分类映射名。
- 资产分类、停机为资产页内嵌子组件对话框，`changed` 事件驱动父重拉。
- RBAC：写动作按 hasPermission 隐藏；停机写=asset.edit；分类=asset_category.manage。
- 导航维护组 资产/位置 接入、无残留 soon；路由 2 条 requiresAuth。
- 仅中文、无新增 locale。`npm run typecheck` 0 错、vitest 全绿、prettier 干净。
