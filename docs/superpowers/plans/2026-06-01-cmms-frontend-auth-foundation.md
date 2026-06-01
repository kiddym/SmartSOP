# CMMS 前端认证地基 + 导航壳 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 CMMS 前端能登录/注册进入系统、会话被安全管理（access 内存 + refresh localStorage + 401 单飞续期 + 刷新页恢复）、未登录被守卫拦截，并提供预留全模块的导航壳——后续业务模块前端直接挂载于此。

**Architecture:** `authStorage`(内存 access + localStorage refresh) 是 token 存储底座，`http.ts` 只依赖它（避免循环依赖）；`store/auth`(Pinia) 是**身份真相源**（user/role/permissions）；`api/auth` 封装后端 `/auth/*`；router 全局守卫只强制 `requiresAuth`，权限框架(`hasPermission` + `meta.requiredPermission`)就位但不强制。

**Tech Stack:** Vue 3 `<script setup>` + TypeScript / Pinia(options 风格) / Vue Router / axios / Element Plus / vue-i18n / Vitest + @vue/test-utils。

**前置依赖：** 本分支 `feat/cmms-frontend-auth-foundation` 已 = 最新 main(含 phase-0 多租户后端 + 批量解析) + 本 spec。后端 `/api/v1/auth/{login,register,refresh,me}` 已就绪。

**spec：** `docs/superpowers/specs/2026-06-01-cmms-frontend-auth-foundation-design.md`

---

## 关键约定（先读）

- **后端契约**（已核实）：
  - `POST /api/v1/auth/login` body `{email, password, company_slug?}` → `{access_token, refresh_token, token_type}` (200)
  - `POST /api/v1/auth/register` body `{company_name, email, password, name}` → 同 TokenPair (201)
  - `POST /api/v1/auth/refresh` body `{refresh_token}` → TokenPair (200)
  - `GET /api/v1/auth/me` → `{id, email, name, company_id, role_code, permissions: string[]}` (200)
  - 无 logout / 密码重置 / 激活 / 邀请端点。
- **循环依赖红线**：`http.ts` **禁止** import `store/auth` 或 `api/auth`（`api/auth` import `http` → 成环）。token 读取走 `authStorage` 模块变量；401 续期在 `http.ts` 内用 `http.post('/auth/refresh', …)` 直发（不经 `api/auth`）；续期失败跳登录用 `window.location`（不 import router）。
- **access token 不入 Pinia 响应式 state**：存 `authStorage` 内存模块变量（仍是内存、不落盘，符合安全意图）；Pinia store 的真相是 `user/roleCode/permissionCodes`，`isAuthenticated = !!user`。
- **bootstrap 幂等**：`store.bootstrap()` 缓存内部 Promise，多次调用返回同一个；守卫每次 `await store.bootstrap()` 安全。
- **API 解包风格**：对齐 `api/folders.ts`——`async () => (await http.xxx<T>(...)).data`。
- **测试**：vitest，文件放 `frontend/tests/unit/**/*.spec.ts`；`vi.hoisted`+`vi.mock` mock 模块；`setActivePinia(createPinia())`；组件用 `mount(C,{global:{plugins:[...]}})`。运行 `cd frontend && npx vitest run <file>`。

---

## 文件结构

| 文件 | 责任 | 动作 |
|---|---|---|
| `frontend/src/types/auth.ts` | 认证 TS 类型 | 创建 |
| `frontend/src/utils/authStorage.ts` | access(内存)+refresh(localStorage) token 底座 | 创建 |
| `frontend/src/api/auth.ts` | 封装 /auth/login,register,refresh,me | 创建 |
| `frontend/src/store/auth.ts` | 身份真相源(user/role/permissions)+会话动作 | 创建 |
| `frontend/src/api/http.ts` | 加请求拦截器(注入)+401单飞续期 | 改造 |
| `frontend/src/composables/usePermission.ts` | hasPermission 薄封装 | 创建 |
| `frontend/src/router/index.ts` | 加 /login /register + beforeEach 守卫 + meta | 改造 |
| `frontend/src/layouts/AuthLayout.vue` | 登录/注册无壳布局 | 创建 |
| `frontend/src/views/auth/LoginView.vue` | 登录页 | 创建 |
| `frontend/src/views/auth/RegisterView.vue` | 注册页(新建组织) | 创建 |
| `frontend/src/components/UserMenu.vue` | 顶栏用户菜单+登出 | 创建 |
| `frontend/src/components/AppSidebar.vue` | 扩成按域分组导航(占位) | 改造 |
| `frontend/src/components/AppTopBar.vue` | 挂 UserMenu | 改造 |
| `frontend/src/i18n/locales/zh-CN.ts` | 补 auth/nav 字符串 | 改造 |
| `frontend/tests/unit/**` | 各单元测试 | 创建 |

---

## Task 1: 类型 + token 存储底座

**Files:**
- Create: `frontend/src/types/auth.ts`
- Create: `frontend/src/utils/authStorage.ts`
- Test: `frontend/tests/unit/utils/authStorage.spec.ts`

- [ ] **Step 1: 写类型**

Create `frontend/src/types/auth.ts`:

```typescript
export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface LoginPayload {
  email: string
  password: string
  company_slug?: string
}

export interface RegisterPayload {
  company_name: string
  email: string
  password: string
  name: string
}

export interface CurrentUser {
  id: string
  email: string
  name: string
  company_id: string
  role_code: string | null
  permissions: string[]
}
```

- [ ] **Step 2: 写失败测试**

Create `frontend/tests/unit/utils/authStorage.spec.ts`:

```typescript
import { beforeEach, describe, expect, it } from 'vitest'
import * as authStorage from '@/utils/authStorage'

describe('authStorage', () => {
  beforeEach(() => {
    localStorage.clear()
    authStorage.setAccessToken(null)
  })

  it('access token 只在内存、不落 localStorage', () => {
    authStorage.setAccessToken('acc-1')
    expect(authStorage.getAccessToken()).toBe('acc-1')
    expect(localStorage.getItem('cmms.refresh_token')).toBeNull()
  })

  it('refresh token 落 localStorage 并可读回', () => {
    authStorage.setRefreshToken('ref-1')
    expect(authStorage.getRefreshToken()).toBe('ref-1')
    expect(localStorage.getItem('cmms.refresh_token')).toBe('ref-1')
  })

  it('clearTokens 同时清内存与 localStorage', () => {
    authStorage.setAccessToken('a')
    authStorage.setRefreshToken('r')
    authStorage.clearTokens()
    expect(authStorage.getAccessToken()).toBeNull()
    expect(authStorage.getRefreshToken()).toBeNull()
  })
})
```

- [ ] **Step 3: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/utils/authStorage.spec.ts`
Expected: FAIL — 无法解析 `@/utils/authStorage`

- [ ] **Step 4: 写实现**

Create `frontend/src/utils/authStorage.ts`:

```typescript
// token 存储底座：access 仅内存（不落盘，抗 XSS 持久窃取）；refresh 落 localStorage 以便刷新页恢复。
// http.ts 只依赖本模块读 token，避免 http→store 循环依赖。

const REFRESH_KEY = 'cmms.refresh_token'

let accessToken: string | null = null

export function getAccessToken(): string | null {
  return accessToken
}

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY)
}

export function setRefreshToken(token: string | null): void {
  if (token === null) localStorage.removeItem(REFRESH_KEY)
  else localStorage.setItem(REFRESH_KEY, token)
}

export function clearTokens(): void {
  accessToken = null
  localStorage.removeItem(REFRESH_KEY)
}
```

- [ ] **Step 5: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/utils/authStorage.spec.ts`
Expected: PASS（3 passed）

- [ ] **Step 6: 提交**

```bash
cd frontend && npx eslint src/types/auth.ts src/utils/authStorage.ts tests/unit/utils/authStorage.spec.ts --fix
git add src/types/auth.ts src/utils/authStorage.ts tests/unit/utils/authStorage.spec.ts
git commit -m "feat(auth-fe): types + token storage base (access in-memory, refresh localStorage)"
```

---

## Task 2: api/auth.ts

**Files:**
- Create: `frontend/src/api/auth.ts`
- Test: `frontend/tests/unit/api/auth.spec.ts`

- [ ] **Step 1: 写失败测试**

Create `frontend/tests/unit/api/auth.spec.ts`:

```typescript
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('@/api/http', () => ({ http: { get, post } }))

import { fetchMe, login, refresh, register } from '@/api/auth'

describe('api/auth', () => {
  beforeEach(() => {
    get.mockReset()
    post.mockReset()
  })

  it('login POST /auth/login 并返回 TokenPair', async () => {
    post.mockResolvedValue({ data: { access_token: 'a', refresh_token: 'r', token_type: 'bearer' } })
    const res = await login({ email: 'x@y.com', password: 'pw12345678' })
    expect(post).toHaveBeenCalledWith('/auth/login', { email: 'x@y.com', password: 'pw12345678' })
    expect(res.access_token).toBe('a')
  })

  it('register POST /auth/register', async () => {
    post.mockResolvedValue({ data: { access_token: 'a', refresh_token: 'r', token_type: 'bearer' } })
    await register({ company_name: 'Acme', email: 'x@y.com', password: 'pw12345678', name: 'Neo' })
    expect(post).toHaveBeenCalledWith('/auth/register', {
      company_name: 'Acme', email: 'x@y.com', password: 'pw12345678', name: 'Neo',
    })
  })

  it('fetchMe GET /auth/me', async () => {
    get.mockResolvedValue({ data: { id: '1', email: 'x@y.com', name: 'Neo', company_id: 'c1', role_code: 'admin', permissions: ['user.view'] } })
    const me = await fetchMe()
    expect(get).toHaveBeenCalledWith('/auth/me')
    expect(me.permissions).toEqual(['user.view'])
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/api/auth.spec.ts`
Expected: FAIL — 无法解析 `@/api/auth`

- [ ] **Step 3: 写实现**

Create `frontend/src/api/auth.ts`:

```typescript
import { http } from './http'
import type { CurrentUser, LoginPayload, RegisterPayload, TokenPair } from '@/types/auth'

export const login = async (payload: LoginPayload): Promise<TokenPair> =>
  (await http.post<TokenPair>('/auth/login', payload)).data

export const register = async (payload: RegisterPayload): Promise<TokenPair> =>
  (await http.post<TokenPair>('/auth/register', payload)).data

export const refresh = async (refreshToken: string): Promise<TokenPair> =>
  (await http.post<TokenPair>('/auth/refresh', { refresh_token: refreshToken })).data

export const fetchMe = async (): Promise<CurrentUser> =>
  (await http.get<CurrentUser>('/auth/me')).data
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/api/auth.spec.ts`
Expected: PASS（3 passed）

> 注：`login` 测试断言 body 不含 `company_slug`（undefined 不传）。若实现用 spread 传整 payload 也可，但需与测试一致——此处实现直接传 `payload`，`company_slug` 为 undefined 时 axios 会序列化掉，断言用不含该键的对象匹配（vitest `toHaveBeenCalledWith` 对 undefined 键宽松）。如断言失败，改测试期望为 `{ email, password, company_slug: undefined }`。

- [ ] **Step 5: 提交**

```bash
cd frontend && npx eslint src/api/auth.ts tests/unit/api/auth.spec.ts --fix
git add src/api/auth.ts tests/unit/api/auth.spec.ts
git commit -m "feat(auth-fe): auth api client (login/register/refresh/me)"
```

---

## Task 3: store/auth.ts（身份真相源）

**Files:**
- Create: `frontend/src/store/auth.ts`
- Test: `frontend/tests/unit/store/auth.spec.ts`

- [ ] **Step 1: 写失败测试**

Create `frontend/tests/unit/store/auth.spec.ts`:

```typescript
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const api = vi.hoisted(() => ({ login: vi.fn(), register: vi.fn(), refresh: vi.fn(), fetchMe: vi.fn() }))
vi.mock('@/api/auth', () => api)
const storage = vi.hoisted(() => ({
  setAccessToken: vi.fn(), setRefreshToken: vi.fn(), getRefreshToken: vi.fn(), clearTokens: vi.fn(),
}))
vi.mock('@/utils/authStorage', () => storage)

import { useAuthStore } from '@/store/auth'

const ME = { id: '1', email: 'x@y.com', name: 'Neo', company_id: 'c1', role_code: 'admin', permissions: ['user.view'] }

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    Object.values(api).forEach((f) => f.mockReset())
    Object.values(storage).forEach((f) => f.mockReset())
  })

  it('login 成功：写 token + loadMe + isAuthenticated', async () => {
    api.login.mockResolvedValue({ access_token: 'a', refresh_token: 'r', token_type: 'bearer' })
    api.fetchMe.mockResolvedValue(ME)
    const s = useAuthStore()
    await s.login({ email: 'x@y.com', password: 'pw12345678' })
    expect(storage.setAccessToken).toHaveBeenCalledWith('a')
    expect(storage.setRefreshToken).toHaveBeenCalledWith('r')
    expect(s.user?.email).toBe('x@y.com')
    expect(s.isAuthenticated).toBe(true)
    expect(s.permissionCodes).toEqual(['user.view'])
  })

  it('hasPermission：super_admin 全通过；普通角色按码', async () => {
    api.fetchMe.mockResolvedValue({ ...ME, role_code: 'super_admin', permissions: [] })
    api.login.mockResolvedValue({ access_token: 'a', refresh_token: 'r', token_type: 'bearer' })
    const s = useAuthStore()
    await s.login({ email: 'x@y.com', password: 'pw12345678' })
    expect(s.hasPermission('anything.at.all')).toBe(true)
  })

  it('logout 清 token 与身份', async () => {
    const s = useAuthStore()
    s.user = ME
    s.logout()
    expect(storage.clearTokens).toHaveBeenCalled()
    expect(s.user).toBeNull()
    expect(s.isAuthenticated).toBe(false)
  })

  it('bootstrap：无 refresh → 未登录、ready', async () => {
    storage.getRefreshToken.mockReturnValue(null)
    const s = useAuthStore()
    await s.bootstrap()
    expect(s.isAuthenticated).toBe(false)
    expect(api.refresh).not.toHaveBeenCalled()
  })

  it('bootstrap：有 refresh → 换 access + loadMe 恢复会话（且幂等）', async () => {
    storage.getRefreshToken.mockReturnValue('r')
    api.refresh.mockResolvedValue({ access_token: 'a2', refresh_token: 'r2', token_type: 'bearer' })
    api.fetchMe.mockResolvedValue(ME)
    const s = useAuthStore()
    await Promise.all([s.bootstrap(), s.bootstrap()]) // 幂等：只跑一次
    expect(api.refresh).toHaveBeenCalledTimes(1)
    expect(s.isAuthenticated).toBe(true)
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/store/auth.spec.ts`
Expected: FAIL — 无法解析 `@/store/auth`

- [ ] **Step 3: 写实现**

Create `frontend/src/store/auth.ts`:

```typescript
import { defineStore } from 'pinia'
import * as authApi from '@/api/auth'
import * as authStorage from '@/utils/authStorage'
import type { CurrentUser, LoginPayload, RegisterPayload } from '@/types/auth'

interface State {
  user: CurrentUser | null
  loading: boolean
  _bootstrapPromise: Promise<void> | null
}

export const useAuthStore = defineStore('auth', {
  state: (): State => ({
    user: null,
    loading: false,
    _bootstrapPromise: null,
  }),

  getters: {
    isAuthenticated: (s): boolean => s.user !== null,
    roleCode: (s): string | null => s.user?.role_code ?? null,
    permissionCodes: (s): string[] => s.user?.permissions ?? [],
    hasPermission(): (code: string) => boolean {
      const role = this.user?.role_code
      const codes = this.user?.permissions ?? []
      return (code: string): boolean => role === 'super_admin' || codes.includes(code)
    },
  },

  actions: {
    async login(payload: LoginPayload): Promise<void> {
      this.loading = true
      try {
        const pair = await authApi.login(payload)
        this._applyTokens(pair.access_token, pair.refresh_token)
        await this.loadMe()
      } finally {
        this.loading = false
      }
    },

    async register(payload: RegisterPayload): Promise<void> {
      this.loading = true
      try {
        const pair = await authApi.register(payload)
        this._applyTokens(pair.access_token, pair.refresh_token)
        await this.loadMe()
      } finally {
        this.loading = false
      }
    },

    async loadMe(): Promise<void> {
      this.user = await authApi.fetchMe()
    },

    logout(): void {
      authStorage.clearTokens()
      this.user = null
    },

    bootstrap(): Promise<void> {
      if (this._bootstrapPromise) return this._bootstrapPromise
      this._bootstrapPromise = this._doBootstrap()
      return this._bootstrapPromise
    },

    async _doBootstrap(): Promise<void> {
      const refreshToken = authStorage.getRefreshToken()
      if (!refreshToken) return
      try {
        const pair = await authApi.refresh(refreshToken)
        this._applyTokens(pair.access_token, pair.refresh_token)
        await this.loadMe()
      } catch {
        authStorage.clearTokens()
        this.user = null
      }
    },

    _applyTokens(access: string, refresh: string): void {
      authStorage.setAccessToken(access)
      authStorage.setRefreshToken(refresh)
    },
  },
})
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/store/auth.spec.ts`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
cd frontend && npx eslint src/store/auth.ts tests/unit/store/auth.spec.ts --fix
git add src/store/auth.ts tests/unit/store/auth.spec.ts
git commit -m "feat(auth-fe): auth store (identity source + login/register/logout/bootstrap)"
```

---

## Task 4: http.ts 改造（token 注入 + 401 单飞续期）

**Files:**
- Modify: `frontend/src/api/http.ts`
- Test: `frontend/tests/unit/api/httpAuth.spec.ts`

- [ ] **Step 1: 写失败测试**

Create `frontend/tests/unit/api/httpAuth.spec.ts`:

```typescript
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as authStorage from '@/utils/authStorage'
import { __test_onRequest, __test_refreshOn401 } from '@/api/http'

describe('http auth 拦截', () => {
  beforeEach(() => {
    authStorage.clearTokens()
  })

  it('请求拦截器注入 Authorization', () => {
    authStorage.setAccessToken('acc-9')
    const cfg = __test_onRequest({ headers: {} } as never)
    expect((cfg.headers as Record<string, string>).Authorization).toBe('Bearer acc-9')
  })

  it('无 access 时不加 Authorization', () => {
    const cfg = __test_onRequest({ headers: {} } as never)
    expect((cfg.headers as Record<string, string>).Authorization).toBeUndefined()
  })

  it('401 单飞：并发只发一个 refresh', async () => {
    authStorage.setRefreshToken('r')
    let calls = 0
    const doRefresh = vi.fn(async () => { calls += 1; await Promise.resolve(); return 'new-acc' })
    const [a, b] = await Promise.all([__test_refreshOn401(doRefresh), __test_refreshOn401(doRefresh)])
    expect(calls).toBe(1)
    expect(a).toBe('new-acc')
    expect(b).toBe('new-acc')
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/api/httpAuth.spec.ts`
Expected: FAIL — `__test_onRequest` 未导出

- [ ] **Step 3: 改造 http.ts**

Modify `frontend/src/api/http.ts` — 顶部 import 区加 `import * as authStorage from '@/utils/authStorage'`，并追加请求拦截器、单飞 refresh、401 响应处理。在现有响应拦截器**之前**插入以下逻辑，并导出测试钩子：

```typescript
import type { AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios'

// —— 请求拦截：注入 access token —— //
function onRequest(config: InternalAxiosRequestConfig): InternalAxiosRequestConfig {
  const token = authStorage.getAccessToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
}
http.interceptors.request.use(onRequest)

// —— 401 单飞续期 —— //
let refreshing: Promise<string> | null = null

// 用 doRefresh 注入便于测试；生产调用 performRefresh。
async function refreshOn401(doRefresh: () => Promise<string>): Promise<string> {
  if (!refreshing) {
    refreshing = doRefresh().finally(() => { refreshing = null })
  }
  return refreshing
}

async function performRefresh(): Promise<string> {
  const rt = authStorage.getRefreshToken()
  if (!rt) throw new Error('no refresh token')
  // 直发，不经 api/auth（避免循环依赖）
  const { data } = await http.post<{ access_token: string; refresh_token: string }>(
    '/auth/refresh', { refresh_token: rt }, { skipErrorToast: true },
  )
  authStorage.setAccessToken(data.access_token)
  authStorage.setRefreshToken(data.refresh_token)
  return data.access_token
}

function redirectToLogin(): void {
  authStorage.clearTokens()
  const redirect = encodeURIComponent(window.location.pathname + window.location.search)
  window.location.assign(`/login?redirect=${redirect}`)
}

// 测试钩子
export const __test_onRequest = onRequest
export const __test_refreshOn401 = refreshOn401
```

然后把**现有响应拦截器**替换为带 401 处理的版本（保留原 toast 行为于非 401 分支）：

```typescript
http.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error?.response?.status
    const original = error?.config as (AxiosRequestConfig & { _retried?: boolean }) | undefined
    const isRefreshCall = original?.url?.includes('/auth/refresh')

    if (status === 401 && original && !original._retried && !isRefreshCall) {
      original._retried = true
      try {
        const newAccess = await refreshOn401(performRefresh)
        original.headers = { ...original.headers, Authorization: `Bearer ${newAccess}` }
        return http(original)
      } catch {
        redirectToLogin()
        return Promise.reject(error)
      }
    }

    if (!error?.config?.skipErrorToast) {
      const detail = error?.response?.data?.detail as ApiErrorDetail | undefined
      ElMessage.error(detail?.message ?? '请求失败，请稍后重试')
    }
    return Promise.reject(error)
  },
)
```

（删除原先单独的 `http.interceptors.response.use(...)` 块，避免双重注册。）

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/api/httpAuth.spec.ts`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
cd frontend && npx eslint src/api/http.ts tests/unit/api/httpAuth.spec.ts --fix && npx vue-tsc --noEmit
git add src/api/http.ts tests/unit/api/httpAuth.spec.ts
git commit -m "feat(auth-fe): http token injection + 401 single-flight refresh"
```

---

## Task 5: usePermission composable

**Files:**
- Create: `frontend/src/composables/usePermission.ts`
- Test: `frontend/tests/unit/composables/usePermission.spec.ts`

- [ ] **Step 1: 写失败测试**

Create `frontend/tests/unit/composables/usePermission.spec.ts`:

```typescript
import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/store/auth'
import { usePermission } from '@/composables/usePermission'

describe('usePermission', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('代理 store.hasPermission', () => {
    const s = useAuthStore()
    s.user = { id: '1', email: 'a@b.c', name: 'n', company_id: 'c', role_code: 'viewer', permissions: ['asset.view'] }
    const { hasPermission } = usePermission()
    expect(hasPermission('asset.view')).toBe(true)
    expect(hasPermission('asset.edit')).toBe(false)
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/composables/usePermission.spec.ts`
Expected: FAIL — 无法解析 `@/composables/usePermission`

- [ ] **Step 3: 写实现**

Create `frontend/src/composables/usePermission.ts`:

```typescript
import { useAuthStore } from '@/store/auth'

export function usePermission(): { hasPermission: (code: string) => boolean } {
  const auth = useAuthStore()
  return {
    hasPermission: (code: string): boolean => auth.hasPermission(code),
  }
}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/composables/usePermission.spec.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd frontend && npx eslint src/composables/usePermission.ts tests/unit/composables/usePermission.spec.ts --fix
git add src/composables/usePermission.ts tests/unit/composables/usePermission.spec.ts
git commit -m "feat(auth-fe): usePermission composable"
```

---

## Task 6: 路由守卫 + 公开路由 + meta

**Files:**
- Modify: `frontend/src/router/index.ts`
- Test: `frontend/tests/unit/router/guard.spec.ts`

- [ ] **Step 1: 写失败测试**

Create `frontend/tests/unit/router/guard.spec.ts`:

```typescript
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { authGuard } from '@/router/guard'
import { useAuthStore } from '@/store/auth'

describe('authGuard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('未登录访问受保护路由 → 重定向 /login 带 redirect', async () => {
    const s = useAuthStore()
    vi.spyOn(s, 'bootstrap').mockResolvedValue()
    const to = { path: '/folders', fullPath: '/folders', meta: { requiresAuth: true } } as never
    const res = await authGuard(to, {} as never)
    expect(res).toEqual({ name: 'login', query: { redirect: '/folders' } })
  })

  it('已登录访问 /login → 重定向首页', async () => {
    const s = useAuthStore()
    s.user = { id: '1', email: 'a@b.c', name: 'n', company_id: 'c', role_code: 'admin', permissions: [] }
    vi.spyOn(s, 'bootstrap').mockResolvedValue()
    const to = { path: '/login', fullPath: '/login', name: 'login', meta: {} } as never
    const res = await authGuard(to, {} as never)
    expect(res).toEqual({ path: '/' })
  })

  it('已登录访问受保护路由 → 放行(true)', async () => {
    const s = useAuthStore()
    s.user = { id: '1', email: 'a@b.c', name: 'n', company_id: 'c', role_code: 'admin', permissions: [] }
    vi.spyOn(s, 'bootstrap').mockResolvedValue()
    const to = { path: '/folders', fullPath: '/folders', meta: { requiresAuth: true } } as never
    const res = await authGuard(to, {} as never)
    expect(res).toBe(true)
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/router/guard.spec.ts`
Expected: FAIL — 无法解析 `@/router/guard`

- [ ] **Step 3: 写守卫（独立文件便于测试）**

Create `frontend/src/router/guard.ts`:

```typescript
import type { RouteLocationNormalized, RouteLocationRaw } from 'vue-router'
import { useAuthStore } from '@/store/auth'

const PUBLIC_NAMES = new Set(['login', 'register'])

export async function authGuard(
  to: RouteLocationNormalized,
  _from: RouteLocationNormalized,
): Promise<boolean | RouteLocationRaw> {
  const auth = useAuthStore()
  await auth.bootstrap() // 幂等，确保刷新页恢复完成再判定

  const isPublic = PUBLIC_NAMES.has((to.name as string) ?? '')

  if (auth.isAuthenticated && isPublic) {
    return { path: '/' }
  }
  if (!auth.isAuthenticated && to.meta.requiresAuth) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  return true
}
```

- [ ] **Step 4: 接入 router/index.ts**

Modify `frontend/src/router/index.ts`：
1. 给现有每个业务路由的 `meta` 加 `requiresAuth: true`（如 `meta: { title: '程序库', requiresAuth: true }`）。
2. 在 `routes` 数组**开头**加两条公开路由：
```typescript
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { title: '登录' },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/auth/RegisterView.vue'),
    meta: { title: '注册' },
  },
```
3. 在 `const router = createRouter({...})` 之后、`export default router` 之前接守卫：
```typescript
import { authGuard } from './guard'
router.beforeEach(authGuard)
```
（import 放文件顶部 import 区。）

为给 `meta.requiresAuth` 提供类型，在 `router/index.ts` 顶部加模块增强：
```typescript
declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    requiresAuth?: boolean
    requiredPermission?: string
  }
}
```

- [ ] **Step 5: 运行 + 编译 + 提交**

Run: `cd frontend && npx vitest run tests/unit/router/guard.spec.ts && npx vue-tsc --noEmit`
Expected: PASS（3 passed）+ 无类型错误

```bash
git add src/router/index.ts src/router/guard.ts tests/unit/router/guard.spec.ts
git commit -m "feat(auth-fe): route guard + public login/register routes + requiresAuth meta"
```

---

## Task 7: AuthLayout + 登录页 + 注册页

**Files:**
- Create: `frontend/src/layouts/AuthLayout.vue`
- Create: `frontend/src/views/auth/LoginView.vue`
- Create: `frontend/src/views/auth/RegisterView.vue`
- Test: `frontend/tests/unit/views/LoginView.spec.ts`

- [ ] **Step 1: 写无壳布局**

Create `frontend/src/layouts/AuthLayout.vue`:

```vue
<script setup lang="ts"></script>

<template>
  <div class="auth-layout">
    <div class="auth-card">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.auth-layout { display: flex; align-items: center; justify-content: center; min-height: 100vh; background: var(--el-fill-color-light, #f5f7fa); }
.auth-card { width: 360px; padding: 32px; background: #fff; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,.08); }
</style>
```

- [ ] **Step 2: 写登录页失败测试**

Create `frontend/tests/unit/views/LoginView.spec.ts`:

```typescript
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import LoginView from '@/views/auth/LoginView.vue'
import { useAuthStore } from '@/store/auth'

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: { template: '<div/>' } },
      { path: '/login', name: 'login', component: { template: '<div/>' } },
      { path: '/register', name: 'register', component: { template: '<div/>' } },
    ],
  })
}

describe('LoginView', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('提交表单调用 store.login 并跳转 redirect', async () => {
    const router = makeRouter()
    await router.push('/login?redirect=/folders')
    await router.isReady()
    const s = useAuthStore()
    const loginSpy = vi.spyOn(s, 'login').mockResolvedValue()
    const push = vi.spyOn(router, 'push')

    const w = mount(LoginView, { global: { plugins: [ElementPlus, router] } })
    await w.find('[data-test="email"]').setValue('x@y.com')
    await w.find('[data-test="password"]').setValue('pw12345678')
    await w.find('[data-test="submit"]').trigger('click')
    await flushPromises()

    expect(loginSpy).toHaveBeenCalledWith({ email: 'x@y.com', password: 'pw12345678' })
    expect(push).toHaveBeenCalledWith('/folders')
  })
})
```

- [ ] **Step 3: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/views/LoginView.spec.ts`
Expected: FAIL — 无法解析 `@/views/auth/LoginView.vue`

- [ ] **Step 4: 写登录页**

Create `frontend/src/views/auth/LoginView.vue`:

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/store/auth'
import { errorMessage } from '@/api/http'
import AuthLayout from '@/layouts/AuthLayout.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const email = ref('')
const password = ref('')
const submitting = ref(false)

async function submit(): Promise<void> {
  if (!email.value || !password.value) {
    ElMessage.warning(t('auth.fillEmailPassword'))
    return
  }
  submitting.value = true
  try {
    await auth.login({ email: email.value, password: password.value })
    const redirect = (route.query.redirect as string) || '/'
    await router.push(redirect)
  } catch (err) {
    ElMessage.error(errorMessage(err) ?? t('auth.loginFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthLayout>
    <h2 class="auth-title">{{ t('auth.login') }}</h2>
    <el-form @submit.prevent="submit">
      <el-form-item :label="t('auth.email')">
        <el-input v-model="email" data-test="email" type="email" autocomplete="username" />
      </el-form-item>
      <el-form-item :label="t('auth.password')">
        <el-input v-model="password" data-test="password" type="password" show-password autocomplete="current-password" @keyup.enter="submit" />
      </el-form-item>
      <el-button type="primary" :loading="submitting" data-test="submit" style="width: 100%" @click="submit">
        {{ t('auth.login') }}
      </el-button>
      <div class="auth-foot">
        {{ t('auth.noAccount') }}
        <router-link :to="{ name: 'register' }">{{ t('auth.register') }}</router-link>
      </div>
    </el-form>
  </AuthLayout>
</template>

<style scoped>
.auth-title { margin: 0 0 24px; text-align: center; }
.auth-foot { margin-top: 16px; text-align: center; font-size: 13px; color: #888; }
</style>
```

- [ ] **Step 5: 写注册页**（新建组织）

Create `frontend/src/views/auth/RegisterView.vue`:

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/store/auth'
import { errorMessage } from '@/api/http'
import AuthLayout from '@/layouts/AuthLayout.vue'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()

const companyName = ref('')
const name = ref('')
const email = ref('')
const password = ref('')
const submitting = ref(false)

async function submit(): Promise<void> {
  if (!companyName.value || !name.value || !email.value || password.value.length < 8) {
    ElMessage.warning(t('auth.registerHint'))
    return
  }
  submitting.value = true
  try {
    await auth.register({ company_name: companyName.value, name: name.value, email: email.value, password: password.value })
    await router.push('/')
  } catch (err) {
    ElMessage.error(errorMessage(err) ?? t('auth.registerFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthLayout>
    <h2 class="auth-title">{{ t('auth.register') }}</h2>
    <el-form @submit.prevent="submit">
      <el-form-item :label="t('auth.companyName')">
        <el-input v-model="companyName" data-test="companyName" />
      </el-form-item>
      <el-form-item :label="t('auth.name')">
        <el-input v-model="name" data-test="name" />
      </el-form-item>
      <el-form-item :label="t('auth.email')">
        <el-input v-model="email" data-test="email" type="email" />
      </el-form-item>
      <el-form-item :label="t('auth.password')">
        <el-input v-model="password" data-test="password" type="password" show-password />
      </el-form-item>
      <el-button type="primary" :loading="submitting" data-test="submit" style="width: 100%" @click="submit">
        {{ t('auth.register') }}
      </el-button>
      <div class="auth-foot">
        {{ t('auth.haveAccount') }}
        <router-link :to="{ name: 'login' }">{{ t('auth.login') }}</router-link>
      </div>
    </el-form>
  </AuthLayout>
</template>

<style scoped>
.auth-title { margin: 0 0 24px; text-align: center; }
.auth-foot { margin-top: 16px; text-align: center; font-size: 13px; color: #888; }
</style>
```

- [ ] **Step 6: 补 i18n 字符串**（本 task 用到的新键，Task 8 再补导航键）

Modify `frontend/src/i18n/locales/zh-CN.ts` 的 `auth` 块，补齐：

```typescript
  auth: {
    login: '登录', register: '注册', email: '邮箱', password: '密码', companyName: '公司名称',
    name: '姓名',
    noAccount: '还没有账号？', haveAccount: '已有账号？',
    fillEmailPassword: '请输入邮箱和密码',
    loginFailed: '登录失败，请检查邮箱或密码',
    registerHint: '请完整填写，密码至少 8 位',
    registerFailed: '注册失败，请重试',
    logout: '退出登录',
  },
```

- [ ] **Step 7: 运行 + 编译 + 提交**

Run: `cd frontend && npx vitest run tests/unit/views/LoginView.spec.ts && npx vue-tsc --noEmit`
Expected: PASS + 无类型错误

```bash
git add src/layouts/AuthLayout.vue src/views/auth/ src/i18n/locales/zh-CN.ts tests/unit/views/LoginView.spec.ts
git commit -m "feat(auth-fe): auth layout + login/register views"
```

---

## Task 8: 导航壳改造 + UserMenu + bootstrap 接线

**Files:**
- Create: `frontend/src/components/UserMenu.vue`
- Modify: `frontend/src/components/AppSidebar.vue`
- Modify: `frontend/src/components/AppTopBar.vue`
- Modify: `frontend/src/i18n/locales/zh-CN.ts`
- Test: `frontend/tests/unit/components/UserMenu.spec.ts`

- [ ] **Step 1: 写 UserMenu 失败测试**

Create `frontend/tests/unit/components/UserMenu.spec.ts`:

```typescript
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import UserMenu from '@/components/UserMenu.vue'
import { useAuthStore } from '@/store/auth'

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: { template: '<div/>' } },
      { path: '/login', name: 'login', component: { template: '<div/>' } },
    ],
  })
}

describe('UserMenu', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('显示用户名；登出调用 store.logout 并跳 /login', async () => {
    const router = makeRouter()
    await router.isReady()
    const s = useAuthStore()
    s.user = { id: '1', email: 'a@b.c', name: 'Neo', company_id: 'c', role_code: 'admin', permissions: [] }
    const logoutSpy = vi.spyOn(s, 'logout')
    const push = vi.spyOn(router, 'push')

    const w = mount(UserMenu, { global: { plugins: [ElementPlus, router] } })
    expect(w.text()).toContain('Neo')
    await w.find('[data-test="logout"]').trigger('click')
    await flushPromises()
    expect(logoutSpy).toHaveBeenCalled()
    expect(push).toHaveBeenCalledWith({ name: 'login' })
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/components/UserMenu.spec.ts`
Expected: FAIL — 无法解析 `@/components/UserMenu.vue`

- [ ] **Step 3: 写 UserMenu**

Create `frontend/src/components/UserMenu.vue`:

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/store/auth'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const displayName = computed(() => auth.user?.name ?? auth.user?.email ?? '')

async function logout(): Promise<void> {
  auth.logout()
  await router.push({ name: 'login' })
}
</script>

<template>
  <el-dropdown>
    <span class="user-menu-trigger">{{ displayName }}</span>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item data-test="logout" @click="logout">{{ t('auth.logout') }}</el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<style scoped>
.user-menu-trigger { cursor: pointer; padding: 0 8px; color: var(--el-text-color-primary); }
</style>
```

- [ ] **Step 4: AppSidebar 按域分组改造**

Replace `frontend/src/components/AppSidebar.vue` 的 `<template>` 菜单部分为按域分组（SOP 真实可用，其余占位禁用）。在 `<script setup>` 增导航数据 + 占位提示，模板用分组渲染：

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

defineProps<{ collapsed: boolean }>()
const route = useRoute()

interface NavItem { label: string; path?: string; soon?: boolean }
interface NavGroup { label: string; items: NavItem[] }

const groups: NavGroup[] = [
  { label: 'SOP', items: [
    { label: '程序库', path: '/procedures/library' },
    { label: '草稿箱', path: '/procedures/drafts' },
    { label: '文件夹', path: '/folders' },
    { label: '审计日志', path: '/audit-logs' },
  ]},
  { label: '维护', items: [
    { label: '工单', soon: true }, { label: '资产', soon: true }, { label: '位置', soon: true },
    { label: '请求', soon: true }, { label: '预防性维护', soon: true }, { label: '计量', soon: true },
  ]},
  { label: '供应', items: [
    { label: '备件库存', soon: true }, { label: '采购单', soon: true },
    { label: '供应商', soon: true }, { label: '客户', soon: true },
  ]},
  { label: '洞察', items: [{ label: '分析仪表盘', soon: true }, { label: '通知中心', soon: true }] },
  { label: '平台', items: [
    { label: '用户', soon: true }, { label: '角色', soon: true },
    { label: '团队', soon: true }, { label: '公司设置', soon: true },
  ]},
]

const activeMenu = computed<string>(() => {
  if (route.path.startsWith('/procedures/drafts')) return '/procedures/drafts'
  if (route.path.startsWith('/procedures')) return '/procedures/library'
  if (route.path.startsWith('/folders')) return '/folders'
  if (route.path.startsWith('/audit-logs')) return '/audit-logs'
  return ''
})

function onSoon(): void {
  ElMessage.info('该模块即将上线')
}
</script>

<template>
  <aside class="app-aside" :class="{ collapsed }">
    <el-menu :default-active="activeMenu" :collapse="collapsed" :collapse-transition="false" router
      text-color="#3a3530" background-color="transparent"
      :style="{ '--el-menu-active-color': 'var(--accent)' }">
      <template v-for="g in groups" :key="g.label">
        <div v-if="!collapsed" class="menu-group-label">{{ g.label }}</div>
        <el-menu-item v-for="it in g.items" :key="it.label"
          :index="it.path ?? `soon:${it.label}`"
          :disabled="it.soon"
          @click="it.soon ? onSoon() : undefined">
          <template #title>
            {{ it.label }}<span v-if="it.soon" class="soon-tag">即将上线</span>
          </template>
        </el-menu-item>
      </template>
    </el-menu>
  </aside>
</template>

<style scoped>
.menu-group-label { padding: 8px 16px 4px; font-size: 12px; color: #999; }
.soon-tag { margin-left: 6px; font-size: 10px; color: #bbb; }
.app-aside { height: 100%; }
</style>
```

> 注：占位项 `:disabled` 阻止导航；`@click` 在 disabled 下 Element Plus 不触发，故 `onSoon` 主要供将来去掉 disabled 时用——本阶段占位项纯禁用即可，`onSoon`/`@click` 可保留备用（lint 若报未用可在 onSoon 加 `void 0`）。

- [ ] **Step 5: AppTopBar 挂 UserMenu**

Modify `frontend/src/components/AppTopBar.vue`：在 `<script setup>` import `UserMenu`，在模板的 ⚙菜单（设置下拉）**之后**插入 `<UserMenu />`：

```vue
<!-- 在顶栏右侧、设置⚙菜单之后 -->
<UserMenu />
```
（import：`import UserMenu from '@/components/UserMenu.vue'`）

- [ ] **Step 6: main.ts 预热 bootstrap（可选优化，守卫已兜底）**

Modify `frontend/src/main.ts`：在 `app.use(createPinia())` 之后、`app.use(router)` 之前预热 bootstrap（守卫已 `await bootstrap` 兜底，这里只是让首屏更快进入恢复流程）：

```typescript
import { useAuthStore } from '@/store/auth'
// ...
const pinia = createPinia()
app.use(pinia)
void useAuthStore(pinia).bootstrap() // 预热（不阻塞 mount；守卫会 await 同一 Promise）
app.use(router)
app.use(ElementPlus)
app.use(i18n)
app.mount('#app')
```

- [ ] **Step 7: 运行全量前端测试 + 编译 + 提交**

Run: `cd frontend && npx vitest run && npx vue-tsc --noEmit`
Expected: 全部 PASS + 无类型错误

```bash
cd frontend && npx eslint src/components/UserMenu.vue src/components/AppSidebar.vue src/components/AppTopBar.vue src/main.ts --fix
git add src/components/UserMenu.vue src/components/AppSidebar.vue src/components/AppTopBar.vue src/main.ts src/i18n/locales/zh-CN.ts tests/unit/components/UserMenu.spec.ts
git commit -m "feat(auth-fe): nav shell (domain groups + placeholders) + UserMenu + bootstrap wiring"
```

---

## 手动验证清单（需 dev 环境，参考 running-smartsop-dev）

- [ ] 起后端 API + 前端 Vite，访问任意受保护页 → 自动跳 `/login?redirect=…`
- [ ] 注册新组织 → 自动登录进入首页；导航壳显示 SOP 可用、其余"即将上线"禁用
- [ ] 登出 → 跳 `/login`；手动改 URL 进受保护页仍被拦
- [ ] 登录后**刷新页面** → 不闪回登录（bootstrap 用 refresh 静默恢复）
- [ ] 让 access 过期（或等其过期）后操作 → 401 自动续期、原请求成功；refresh 也失效 → 跳登录
- [ ] 并发多请求同时 401 → 网络面板只有一个 `/auth/refresh`（单飞）

---

## Self-Review（计划作者已核对）

- **Spec 覆盖**：§3 组件分解 → Task 1-8 一一对应（authStorage/api/store/http/usePermission/router/views/导航壳）；§4 数据流 → 登录(Task7+3)、注册(Task7+3)、请求注入+401单飞(Task4)、bootstrap(Task3+6)、守卫(Task6)、hasPermission(Task3+5)；§5 导航壳(Task8)；§6 错误处理(LoginView/RegisterView/http)；§7 测试(每 task 含 vitest)。§1.3 排除项（密码找回/激活/邀请/权限强制）未建任务，符合非目标。
- **占位扫描**：无 TBD/TODO；每个代码步骤含完整可粘贴代码。
- **类型一致性**：`CurrentUser`(含 permissions)/`TokenPair`/`LoginPayload`/`RegisterPayload` 在 Task1 定义，Task2/3/7 一致使用；`authStorage` 的 get/setAccessToken/get/setRefreshToken/clearTokens 跨 Task1/3/4 一致；`useAuthStore` 的 login/register/logout/loadMe/bootstrap/hasPermission/isAuthenticated/permissionCodes 跨 Task3/5/6/7/8 一致；`authGuard` 跨 Task6 定义与接入一致。
- **关键工程点**：循环依赖（http 不 import store/api，token 走 authStorage、401 续期直发 + window.location 跳转）、bootstrap 幂等（缓存 Promise）、401 单飞（模块级 refreshing Promise）均已在对应 task 落实并测试。
- **依赖前提**：后端 `/auth/*` 契约已核实（含 /me 返回 permissions）；前端 http/main/router/store/api 模板均按现状对齐。
