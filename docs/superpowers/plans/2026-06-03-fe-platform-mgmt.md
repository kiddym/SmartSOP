# FE-1 平台管理前端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 平台管理 5 子模块前端（用户/角色/团队/公司设置/货币）+ 一个只读后端权限目录端点，把已就绪平台后端变成可用界面。

**Architecture:** Vue 3 `<script setup lang="ts">` + Element Plus（`el-table` 列表 + `el-dialog` 表单）+ Pinia（仅复用 `auth` store 做 RBAC 门控）+ vue-router 扁平路由。每子模块：`api/<x>.ts` 薄封装 + `types/<x>.ts` + `views/platform/<X>View.vue` + 路由 + AppSidebar 接线。组件内直调 api、`onMounted` 拉取、`ElMessage`/`ElMessageBox` 反馈。仅中文。

**Tech Stack:** Vite + TS + Element Plus + Pinia + vue-router + vitest + `@vue/test-utils`。门禁：`npm run typecheck`（vue-tsc --noEmit）+ prettier + `npm run test`（vitest）。后端改动门禁：`backend/.venv/bin/{ruff,mypy,pytest}`。

**全局约定（每任务适用）：**
- 前端工作目录 `frontend/`；命令 `npm run ...`。首次 `npm install`。
- 后端改动（仅 T1）：`backend/`，`.venv/bin/`。
- 每任务：写测试 → 实现 → `npm run test` + `npm run typecheck` 绿 → commit。
- commit message 结尾附：`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- 仅中文、不做 i18n（沿用现有 zh-CN 习惯）。
- RBAC：`const auth = useAuthStore()`；`auth.hasPermission('<code>')`（super_admin 通配）。无权限按钮隐藏（`v-if`）。

**既有模式参考（须遵循）：**
- api：`src/api/fields.ts`（`http.get<T>(path,{params}).then(r=>r.data)`）。
- view：`src/views/settings/FieldManageView.vue`（script setup + state ref + onMounted fetch + dialog）。
- api 测试：`tests/unit/headingRulesApi.spec.ts`（`vi.hoisted` + `vi.mock('@/api/http')`）。
- view 测试：`tests/unit/HeadingRulesView.spec.ts`（`vi.mock('@/api/<x>')` + `mount(View,{global:{plugins:[ElementPlus]}})` + `flushPromises`）。
- 导航：`src/components/AppSidebar.vue`（`groups: NavGroup[]`，项 `{label,path?,soon?}`）。
- 路由：`src/router/index.ts`（扁平 + `meta.requiresAuth`）。

---

## Task 1: 后端权限目录端点 `GET /permissions`

**Files（backend）:**
- Create: `backend/app/routers/permissions.py`
- Modify: `backend/app/main.py`（挂载）
- Create: `backend/app/permission_labels.py`（code→中文 label + 分组）
- Test: `backend/tests/test_permissions_catalog_api.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_permissions_catalog_api.py`：
```python
"""权限目录端点：ROLE_VIEW 鉴权 + 分组结构 + 覆盖 ALL_PERMISSIONS。"""

from __future__ import annotations

from app.permissions import ALL_PERMISSIONS


def _admin(client):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "a@acme.com", "password": "secret123",
              "name": "Admin"},
    ).json()["access_token"]


def test_requires_auth(client):
    assert client.get("/api/v1/permissions").status_code == 401


def test_catalog_covers_all_permissions(client):
    t = _admin(client)
    body = client.get("/api/v1/permissions", headers={"Authorization": f"Bearer {t}"}).json()
    codes = {p["code"] for g in body for p in g["permissions"]}
    assert codes == set(ALL_PERMISSIONS)
    assert all("group" in g and isinstance(g["permissions"], list) for g in body)
    # 每项有中文 label
    assert all(p["label"] for g in body for p in g["permissions"])
```

- [ ] **Step 2: 跑红**

Run: `cd backend && .venv/bin/python -m pytest tests/test_permissions_catalog_api.py -q`
Expected: FAIL（404）。

- [ ] **Step 3: label 映射**

`backend/app/permission_labels.py`：建 `PERMISSION_GROUPS: list[tuple[str, list[str]]]`（组名→该组 permission 常量列表，复用 `app.permissions` 的 `_PLATFORM`/`_WORKORDER`/… 分组）+ `PERMISSION_LABELS: dict[str, str]`（每个 code → 中文，如 `"user.view": "用户-查看"`）。覆盖 `ALL_PERMISSIONS` 全部 code。

```python
"""权限的分组与中文 label（与 app.permissions 同源，供前端权限目录渲染）。"""

from __future__ import annotations

from app import permissions as P

# (组名, 该组 code 列表)；顺序即前端展示顺序。
PERMISSION_GROUPS: list[tuple[str, list[str]]] = [
    ("平台", P._PLATFORM),
    ("工单", P._WORKORDER),
    ("工单分类", P._WORK_ORDER_CATEGORY),
    ("工时分类", P._TIME_CATEGORY),
    ("主数据", P._BASE_DOMAIN),
    ("请求", P._REQUEST),
    ("预防性维护", P._PREVENTIVE_MAINTENANCE),
    ("计量", P._METER + P._READING),
    ("备件", P._PART + P._PART_CATEGORY),
    ("供应商客户", P._VENDOR + P._CUSTOMER),
    ("采购", P._PURCHASE_ORDER + P._PURCHASE_ORDER_CATEGORY),
    ("成本分类", P._COST_CATEGORY),
    ("分析", P._ANALYTICS),
]

PERMISSION_LABELS: dict[str, str] = {
    P.USER_VIEW: "用户-查看", P.USER_CREATE: "用户-创建", P.USER_EDIT: "用户-编辑",
    P.USER_DELETE: "用户-删除",
    # … 逐一补全 ALL_PERMISSIONS 每个 code 的中文 label …
}
```
> 实现者：逐一核对 `app/permissions.py` 的全部分组常量名（如 `_WORK_ORDER_CATEGORY`/`_PURCHASE_ORDER_CATEGORY` 是否存在），并把 `PERMISSION_LABELS` 补到覆盖 `ALL_PERMISSIONS`（测试会校验 code 集合相等 + 每项 label 非空）。分组并集须等于 `ALL_PERMISSIONS`。

- [ ] **Step 4: 路由**

`backend/app/routers/permissions.py`：
```python
"""权限目录（只读）：分组 + 中文 label，供前端角色表单渲染。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app import permissions
from app.deps import require_permission
from app.models.user import User
from app.permission_labels import PERMISSION_GROUPS, PERMISSION_LABELS

router = APIRouter(prefix="/api/v1/permissions", tags=["permissions"])


@router.get("")
def list_permissions(
    current_user: User = Depends(require_permission(permissions.ROLE_VIEW)),
) -> list[dict[str, Any]]:
    return [
        {
            "group": group,
            "permissions": [{"code": c, "label": PERMISSION_LABELS[c]} for c in codes],
        }
        for group, codes in PERMISSION_GROUPS
    ]
```
`backend/app/main.py`：import 并 `app.include_router(permissions_router.router)`（注意避免与 `app.permissions` 模块名冲突，import 时取别名如 `from app.routers import permissions as permissions_router`）。

- [ ] **Step 5: 跑绿 + 门禁**

Run: `cd backend && .venv/bin/python -m pytest tests/test_permissions_catalog_api.py -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: PASS / 净。

- [ ] **Step 6: commit**

```bash
git add -A && git commit -m "feat(platform): GET /permissions catalog endpoint for role UI

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: 前端骨架（api + types + 路由 + 导航接线 + 占位页）

**Files（frontend）:**
- Create: `src/api/{users,roles,teams,companySettings,currencies,permissions}.ts`
- Create: `src/types/platform.ts`
- Create: `src/views/platform/{Users,Roles,Teams,CompanySettings,Currencies}View.vue`（占位骨架）
- Modify: `src/router/index.ts`、`src/components/AppSidebar.vue`
- Test: `tests/unit/platformApi.spec.ts`、`tests/unit/AppSidebar.spec.ts`（追加平台项断言）

- [ ] **Step 1: 写失败测试（api）**

`tests/unit/platformApi.spec.ts`（仿 headingRulesApi.spec.ts）：
```typescript
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get, post, put, patch, del } = vi.hoisted(() => ({
  get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn(),
}))
vi.mock('@/api/http', () => ({ http: { get, post, put, patch, delete: del } }))

import { listUsers, inviteUser, updateUser } from '@/api/users'
import { listRoles } from '@/api/roles'
import { setTeamMembers } from '@/api/teams'
import { getCompanySettings, updateCompanySettings } from '@/api/companySettings'
import { listCurrencies } from '@/api/currencies'
import { listPermissions } from '@/api/permissions'

describe('platform api', () => {
  beforeEach(() => {
    for (const m of [get, post, put, patch, del]) m.mockReset().mockResolvedValue({ data: [] })
  })
  it('listUsers GET /users', async () => { await listUsers(); expect(get).toHaveBeenCalledWith('/users') })
  it('inviteUser POST /users/invite', async () => {
    await inviteUser({ email: 'x@y.com', name: 'X', role_id: 'r1' })
    expect(post).toHaveBeenCalledWith('/users/invite', { email: 'x@y.com', name: 'X', role_id: 'r1' })
  })
  it('updateUser PATCH /users/{id}', async () => {
    await updateUser('u1', { status: 'inactive' })
    expect(patch).toHaveBeenCalledWith('/users/u1', { status: 'inactive' })
  })
  it('listRoles GET /roles', async () => { await listRoles(); expect(get).toHaveBeenCalledWith('/roles') })
  it('setTeamMembers PUT /teams/{id}/members', async () => {
    await setTeamMembers('t1', ['u1']); expect(put).toHaveBeenCalledWith('/teams/t1/members', { user_ids: ['u1'] })
  })
  it('getCompanySettings GET /company-settings', async () => {
    await getCompanySettings(); expect(get).toHaveBeenCalledWith('/company-settings')
  })
  it('updateCompanySettings PUT /company-settings', async () => {
    await updateCompanySettings({ auto_assign: true }); expect(put).toHaveBeenCalledWith('/company-settings', { auto_assign: true })
  })
  it('listCurrencies GET /currencies', async () => { await listCurrencies(); expect(get).toHaveBeenCalledWith('/currencies') })
  it('listPermissions GET /permissions', async () => { await listPermissions(); expect(get).toHaveBeenCalledWith('/permissions') })
})
```

- [ ] **Step 2: 跑红**

Run: `cd frontend && npm run test -- platformApi`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: types**

`src/types/platform.ts`：
```typescript
export type UserStatus = 'active' | 'inactive'

export interface UserRead {
  id: string; email: string; name: string; status: UserStatus
  role_id: string | null; locale: string; last_login_at: string | null; created_at: string
}
export interface UserCreate { email: string; password: string; name: string; role_id?: string | null }
export interface UserInvite { email: string; name: string; role_id?: string | null }
export interface UserUpdate { name?: string; role_id?: string | null; status?: UserStatus; password?: string }
export interface InviteResult { user_id: string; invited: boolean }  // 按后端 InviteResult 实际字段核对

export interface RoleRead { id: string; code: string; name: string; is_builtin: boolean; permissions: string[] }
export interface RoleCreate { code: string; name: string; permissions: string[] }
export interface RoleUpdate { name?: string; permissions?: string[] }

export interface TeamRead { id: string; name: string; description: string; member_ids: string[] }
export interface TeamCreate { name: string; description?: string }
export interface TeamUpdate { name?: string; description?: string }

export interface CompanySettings { date_format: string; timezone: string; default_currency_code: string; auto_assign: boolean }
export type CompanySettingsUpdate = Partial<CompanySettings>

export interface Currency { id: string; code: string; name: string; symbol: string }
export interface CurrencyCreate { code: string; name: string; symbol?: string }

export interface PermissionItem { code: string; label: string }
export interface PermissionGroup { group: string; permissions: PermissionItem[] }
```
> `InviteResult` 字段按后端 `app/schemas/user.py` 实际核对调整。

- [ ] **Step 4: api 客户端**

各文件仿 `api/fields.ts`：
`src/api/users.ts`：
```typescript
import { http } from './http'
import type { UserRead, UserCreate, UserInvite, UserUpdate, InviteResult } from '@/types/platform'

export const listUsers = () => http.get<UserRead[]>('/users').then(r => r.data)
export const createUser = (p: UserCreate) => http.post<UserRead>('/users', p).then(r => r.data)
export const inviteUser = (p: UserInvite) => http.post<InviteResult>('/users/invite', p).then(r => r.data)
export const updateUser = (id: string, p: UserUpdate) => http.patch<UserRead>(`/users/${id}`, p).then(r => r.data)
export const deleteUser = (id: string) => http.delete(`/users/${id}`).then(() => undefined)
```
`src/api/roles.ts`：listRoles GET `/roles`、createRole POST、updateRole PATCH `/roles/{id}`、deleteRole DELETE。
`src/api/teams.ts`：listTeams GET、createTeam POST、updateTeam PATCH、deleteTeam DELETE、setTeamMembers PUT `/teams/{id}/members` `{user_ids}`。
`src/api/companySettings.ts`：getCompanySettings GET `/company-settings`、updateCompanySettings PUT。
`src/api/currencies.ts`：listCurrencies GET、createCurrency POST、deleteCurrency DELETE `/currencies/{id}`。
`src/api/permissions.ts`：listPermissions GET `/permissions` → `PermissionGroup[]`。

- [ ] **Step 5: 占位视图**

`src/views/platform/UsersView.vue` 等 5 个先建最简骨架（`<template><div class="page">用户</div></template>` + `<script setup lang="ts">`），后续任务填充。让路由可懒加载。

- [ ] **Step 6: 路由**

`src/router/index.ts` 加 5 条（`/platform/users|roles|teams|settings|currencies`）：
```typescript
  { path: '/platform/users', name: 'platform-users',
    component: () => import('@/views/platform/UsersView.vue'),
    meta: { title: '用户', requiresAuth: true, requiredPermission: 'user.view' } },
  { path: '/platform/roles', name: 'platform-roles',
    component: () => import('@/views/platform/RolesView.vue'),
    meta: { title: '角色', requiresAuth: true, requiredPermission: 'role.view' } },
  { path: '/platform/teams', name: 'platform-teams',
    component: () => import('@/views/platform/TeamsView.vue'),
    meta: { title: '团队', requiresAuth: true, requiredPermission: 'team.view' } },
  { path: '/platform/settings', name: 'platform-settings',
    component: () => import('@/views/platform/CompanySettingsView.vue'),
    meta: { title: '公司设置', requiresAuth: true } },
  { path: '/platform/currencies', name: 'platform-currencies',
    component: () => import('@/views/platform/CurrenciesView.vue'),
    meta: { title: '货币', requiresAuth: true, requiredPermission: 'currency.manage' } },
```

- [ ] **Step 7: 导航接线**

`src/components/AppSidebar.vue`：「平台」组改为：
```typescript
  {
    label: '平台',
    items: [
      { label: '用户', path: '/platform/users' },
      { label: '角色', path: '/platform/roles' },
      { label: '团队', path: '/platform/teams' },
      { label: '公司设置', path: '/platform/settings' },
      { label: '货币', path: '/platform/currencies' },
    ],
  },
```
`activeMenu` computed 加：`if (route.path.startsWith('/platform/')) return route.path`（或逐项匹配）。
> 货币项 super_admin 显隐：在 `groups` 计算化（`computed`）中按 `useAuthStore().user?.role_code === 'super_admin'` 过滤「货币」项；或保留项但路由内自行守卫。最简：computed groups 过滤。

`tests/unit/AppSidebar.spec.ts`：追加断言「平台」组含 5 项、无 `soon`。

- [ ] **Step 8: 跑绿 + 门禁**

Run: `cd frontend && npm run test && npm run typecheck`
Expected: PASS / 0 errors。prettier：`npx prettier --write "src/**/*.{ts,vue}"`。

- [ ] **Step 9: commit**

```bash
git add -A && git commit -m "feat(fe-platform): api clients + types + routes + sidebar wiring + placeholder views

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 用户 View（模板任务，完整展开）

**Files:** `src/views/platform/UsersView.vue`；Test: `tests/unit/UsersView.spec.ts`

- [ ] **Step 1: 写失败测试**

`tests/unit/UsersView.spec.ts`（仿 HeadingRulesView.spec.ts）：
```typescript
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lu, cu, iu, uu, du, lr } = vi.hoisted(() => ({
  lu: vi.fn(), cu: vi.fn(), iu: vi.fn(), uu: vi.fn(), du: vi.fn(), lr: vi.fn(),
}))
vi.mock('@/api/users', () => ({
  listUsers: lu, createUser: cu, inviteUser: iu, updateUser: uu, deleteUser: du,
}))
vi.mock('@/api/roles', () => ({ listRoles: lr }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => true, user: { role_code: 'admin' } }),
}))

import UsersView from '@/views/platform/UsersView.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  lu.mockReset().mockResolvedValue([
    { id: 'u1', email: 'a@b.com', name: '张三', status: 'active', role_id: 'r1',
      locale: 'zh', last_login_at: null, created_at: '2026-06-01T00:00:00Z' },
  ])
  lr.mockReset().mockResolvedValue([{ id: 'r1', code: 'admin', name: '管理员', is_builtin: true, permissions: [] }])
})

it('加载并渲染用户行', async () => {
  const w = mount(UsersView, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  expect(lu).toHaveBeenCalled()
  expect(w.text()).toContain('张三')
  expect(w.text()).toContain('管理员')  // role_id→name 映射
})
```

- [ ] **Step 2: 跑红**

Run: `cd frontend && npm run test -- UsersView`
Expected: FAIL。

- [ ] **Step 3: 实现 UsersView**

`src/views/platform/UsersView.vue`：`<script setup lang="ts">` 含：
- import：`ref/reactive/computed/onMounted` from vue；`ElMessage/ElMessageBox` from element-plus；`listUsers/createUser/inviteUser/updateUser/deleteUser`、`listRoles`、`useAuthStore`、types。
- state：`loading`、`users: ref<UserRead[]>([])`、`roles: ref<RoleRead[]>([])`、`roleName = computed(() => id => roles.value.find(r=>r.id===id)?.name ?? '—')`、dialog state（`dialogVisible`、`dialogMode: 'invite'|'create'|'edit'`、`form: reactive<...>`、`editingId`）。
- `onMounted(async () => { await Promise.all([fetchUsers(), fetchRoles()]) })`。
- 表格：`el-table` 列 姓名/邮箱/角色(roleName)/状态/最后登录(formatDate)/操作；操作列按 `auth.hasPermission` `v-if` 显示 编辑/删除。顶部按钮「邀请用户」(user.create)、「直接建号」(user.create)。
- dialog：`el-form` 按 mode 显示字段（invite: email/name/role_select；create: email/password/name/role_select；edit: name/role_select/status_select/新密码可选）。提交调对应 api → 成功 `ElMessage.success` + 刷新 + 关闭。
- 删除：`ElMessageBox.confirm` → `deleteUser` → 刷新。
- 角色下拉 `el-select` options 来自 `roles`。

> 完整 Element Plus 表格/对话框写法参照 `FieldManageView.vue`。RBAC：所有写动作按钮 `v-if="auth.hasPermission('user.create'|'user.edit'|'user.delete')"`。

- [ ] **Step 4: 跑绿 + 门禁**

Run: `cd frontend && npm run test -- UsersView && npm run typecheck`
Expected: PASS。prettier 格式化。

- [ ] **Step 5: commit**：`feat(fe-platform): users management view`。

---

## Task 4: 角色 View

**Files:** `src/views/platform/RolesView.vue`、`tests/unit/RolesView.spec.ts`

按 T3 结构，delta：
- api：`listRoles/createRole/updateRole/deleteRole` + `listPermissions`（@/api/permissions）。
- 表格列：名称、code、类型（`is_builtin ? '内置' : '自定义'`）、权限数（`permissions.length`）、操作。
- 新建 dialog：code（仅新建）、name、**权限分域勾选**——`listPermissions()` 得 `PermissionGroup[]`，渲染分组 `el-checkbox-group`（每组一块，组内 `el-checkbox` label=权限.label value=权限.code），收集选中 code 数组 → `createRole({code,name,permissions})`。
- 编辑 dialog：name + 权限勾选（预填 role.permissions）→ `updateRole(id,{name,permissions})`。
- **内置守卫**：`is_builtin` 行的 编辑/删除按钮禁用（`:disabled="row.is_builtin"`）或 `v-if="!row.is_builtin"`。
- 门控：列表 role.view；增改删按钮 `v-if="auth.hasPermission('role.manage')"`。
- 测试：渲染角色行 + 内置角色删除按钮不可用 + 新建提交带选中 permissions。
- commit：`feat(fe-platform): roles management view with permission picker`。

---

## Task 5: 团队 View

**Files:** `src/views/platform/TeamsView.vue`、`tests/unit/TeamsView.spec.ts`

按 T3 结构，delta：
- api：`listTeams/createTeam/updateTeam/deleteTeam/setTeamMembers` + `listUsers`（成员选择）。
- 表格列：名称、描述、成员数（`member_ids.length`）、操作（编辑/成员/删除）。
- 新建/编辑 dialog：name/description。
- **成员管理 dialog**：`el-transfer` 或多选 `el-select`（左/全部用户来自 `listUsers`，右/已选=team.member_ids）→ `setTeamMembers(id, user_ids)`。
- 门控：列表 team.view；增改删/成员 `v-if="auth.hasPermission('team.manage')"`。
- 测试：渲染团队行 + 成员管理提交带 user_ids。
- commit：`feat(fe-platform): teams management view with member assignment`。

---

## Task 6: 公司设置 View

**Files:** `src/views/platform/CompanySettingsView.vue`、`tests/unit/CompanySettingsView.spec.ts`

- api：`getCompanySettings/updateCompanySettings` + `listCurrencies`（币种下拉）。
- **表单**（非表格）：`el-form`：date_format（输入或下拉常见格式）、timezone（输入）、default_currency_code（`el-select` options 来自 currencies 的 code）、auto_assign（`el-switch`）。`onMounted` GET 载入填表 → 「保存」PUT。
- 门控：读任意登录；保存按钮 `v-if="auth.hasPermission('company_settings')"`（无则表单 disabled 只读）。
- 测试：载入回填 + 保存调 updateCompanySettings 带改动字段。
- commit：`feat(fe-platform): company settings view`。

---

## Task 7: 货币 View

**Files:** `src/views/platform/CurrenciesView.vue`、`tests/unit/CurrenciesView.spec.ts`

- api：`listCurrencies/createCurrency/deleteCurrency`。
- 表格列：code、name、symbol、操作（删除）。顶部「新增货币」按钮。
- 新增 dialog：code/name/symbol → POST。**无编辑**（后端不支持）。
- 删除：`ElMessageBox.confirm` → DELETE。
- 门控：**super_admin 限定**——`v-if="auth.user?.role_code === 'super_admin'"` 控制新增/删除（或 `auth.hasPermission('currency.manage')`）。
- 测试：渲染货币行 + 新增提交 + 非 super_admin 隐藏新增。
- commit：`feat(fe-platform): currencies view (super_admin)`。

---

## Task 8: RBAC 门控统一核对 + 收尾

**Files:** 跨 views（核对）；Test: 跑全量

- [ ] **Step 1:** 逐 view 核对：所有写动作按钮均经 `auth.hasPermission(<正确 code>)` 门控（用户 create/edit/delete、角色/团队 manage、设置 company_settings、货币 super_admin）；列表 view 权限由路由 requiresAuth + 后端真闸兜底。
- [ ] **Step 2:** AppSidebar：货币项 super_admin 显隐生效；`activeMenu` 对所有 `/platform/*` 高亮正确。
- [ ] **Step 3:** 全量门禁：`cd frontend && npm run test && npm run typecheck && npx prettier --check "src/**/*.{ts,vue}"`。后端：`cd backend && .venv/bin/ruff check app/ && .venv/bin/mypy app/ && .venv/bin/python -m pytest -q`。
- [ ] **Step 4: commit**：`chore(fe-platform): RBAC gating audit + wrap-up`。

---

## 收尾

完成 T1–T8 后派发最终 code review，再用 `superpowers:finishing-a-development-branch`。

**自查清单：**
- 后端仅加一个只读 `GET /permissions`（ROLE_VIEW），ruff/mypy/pytest 绿。
- 5 子模块 view 均 el-table + el-dialog、组件内直调 api、`onMounted` 拉取。
- RBAC：写动作按 hasPermission 隐藏；货币 super_admin 限定；内置角色守卫。
- 导航平台组 5 项接入、无残留 soon；路由 5 条 requiresAuth。
- 仅中文、无新增 locale。
- `npm run typecheck` 0 错、vitest 全绿、prettier 干净。
