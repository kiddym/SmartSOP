# 通知系统前端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐 task 实现。步骤用 checkbox（`- [ ]`）跟踪。

**Goal:** 把后端在产的通知接出来——顶栏铃铛下拉（未读角标 + 最近10）+ 通知中心列表页（分页/过滤/全部已读）+ 偏好设置 tab；纯前端、后端不动。

**Architecture:** 新 `notifications` Pinia store 持未读数/最近条目/偏好并轮询 60s；`NotificationBell` 顶栏下拉 + `NotificationCenterView`（el-tabs 列表/偏好）消费 store；文案/路由映射集中 `notificationText.ts`。复用既有 `http` 客户端、`PageResult<T>`、Element Plus、dayjs。

**Tech Stack:** Vue 3 `<script setup>` + Pinia + Element Plus + dayjs + Vitest。后端端点已就绪（`/api/v1/notifications*`、`/api/v1/notification-preferences`）。

设计依据：`docs/superpowers/specs/2026-06-05-notification-frontend-design.md`。

---

## 契约（全程以此为准）

- 后端不改。前端对齐：列表 `GET /notifications?page&page_size&is_read?&type?` → `PageResult<Notification>`；`GET /notifications/unread-count` → `{count}`；`POST /notifications/{id}/read`；`POST /notifications/read-all` → `{updated}`；`GET/PUT /notification-preferences` → `{email_enabled,disabled_types}`。
- `Notification`：`id, type, entity_type:string|null, entity_id:string|null, params:Record<string,unknown>, actor_user_id:string|null, is_read:boolean, read_at:string|null, created_at:string`。
- 通知类型（已知）：`WO_ASSIGNED{custom_id,title}` / `WO_STATUS_CHANGED{custom_id,from_status,to_status}` / `WO_AUTO_GENERATED{custom_id,title}` / `REQUEST_SUBMITTED{custom_id,title}` / 采购单 `PO_*{custom_id}`。
- 标记已读 = **乐观更新**（本地先置已读 + unreadCount-1，失败回滚）。
- 轮询 60s + 动作刷新；完整列表仅下拉（最近10）/列表页（分页）拉。
- 净室原创；门禁 `cd frontend && npm run test && npm run typecheck && npm run lint`（--max-warnings 0）每 task 绿。

## 既有代码事实（已核实，直接用）

- `http`（`src/api/http.ts`）：`http.get<T>(path,{params}).then(r=>r.data)`、`http.post<T>(path,body)`、`http.put`。baseURL `/api/v1` + Bearer 拦截器。
- `PageResult<T>`（`src/types/common.ts`）：`{ items:T[]; total:number; page:number; page_size:number; total_pages:number }`。
- `src/utils/format.ts`：`import dayjs` + utc 插件 + `toLocal(value)`（内部，已处理无时区→UTC→本地）+ 导出 `formatDateTime`/`formatDate`。
- `AppLayout.vue`：已认证外壳，`<AppTopBar :collapsed @toggle-sidebar>` + `<AppSidebar>`。
- `AppTopBar.vue`：有死代码「待阅读 N」徽标（`.topbar-unread`，读 `unreadCount?` prop，无人传）+ 主题切换 + 齿轮 + `<UserMenu/>`。`tests/unit/AppTopBar.spec.ts` 有 3 个 `.topbar-unread` 断言（71/76/81 行）须替换。
- `AppSidebar.vue:107`：`items.push({ label: '通知中心', soon: true, icon: Bell })`（`Bell` 已 import）。侧栏 item 支持 `path`（其它项有 path）；`soon:true` 渲染为禁用占位。
- 路由：工单详情 `name:'maintenance-work-order-detail'` `path:'/maintenance/work-orders/:id'`；请求仅列表 `/maintenance/requests`（无 :id 详情）。
- store 测试约定：`const api = vi.hoisted(()=>({...vi.fn()})); vi.mock('@/api/xxx',()=>api)` + `setActivePinia(createPinia())`。
- `ElMessage` 从 `element-plus` 导入用于成功/错误提示。

---

## Task 1: 类型 + API 客户端

**Files:** Create `frontend/src/types/notification.ts`、`frontend/src/api/notifications.ts`

- [ ] **Step 1: 写类型**（`src/types/notification.ts`）：

```typescript
export interface Notification {
  id: string
  type: string
  entity_type: string | null
  entity_id: string | null
  params: Record<string, unknown>
  actor_user_id: string | null
  is_read: boolean
  read_at: string | null
  created_at: string
}

export interface NotificationPreference {
  email_enabled: boolean
  disabled_types: string[]
}

export interface ListNotificationsParams {
  page?: number
  page_size?: number
  is_read?: boolean
  type?: string
}
```

- [ ] **Step 2: 写 API 客户端**（`src/api/notifications.ts`，对齐 `src/api/requests.ts` 风格）：

```typescript
import { http } from './http'
import type { PageResult } from '@/types/common'
import type {
  Notification,
  NotificationPreference,
  ListNotificationsParams,
} from '@/types/notification'

export const listNotifications = (params: ListNotificationsParams = {}) =>
  http.get<PageResult<Notification>>('/notifications', { params }).then((r) => r.data)

export const getUnreadCount = () =>
  http.get<{ count: number }>('/notifications/unread-count').then((r) => r.data)

export const markRead = (id: string) =>
  http.post<Notification>(`/notifications/${id}/read`).then((r) => r.data)

export const markAllRead = () =>
  http.post<{ updated: number }>('/notifications/read-all').then((r) => r.data)

export const getPreference = () =>
  http.get<NotificationPreference>('/notification-preferences').then((r) => r.data)

export const putPreference = (p: NotificationPreference) =>
  http.put<NotificationPreference>('/notification-preferences', p).then((r) => r.data)
```

- [ ] **Step 3: typecheck** `cd frontend && npm run typecheck` → 0 错误。
- [ ] **Step 4: Commit** `git add -A && git commit -m "feat(notif): 通知类型 + API 客户端"`

---

## Task 2: 文案 + 路由映射（notificationText.ts）

**Files:** Create `frontend/src/utils/notificationText.ts`；Test `frontend/tests/unit/utils/notificationText.spec.ts`

- [ ] **Step 1: 写失败测试**（`tests/unit/utils/notificationText.spec.ts`）：

```typescript
import { describe, it, expect } from 'vitest'
import { formatNotification, entityRoute, NOTIFICATION_TYPES } from '@/utils/notificationText'
import type { Notification } from '@/types/notification'

function n(over: Partial<Notification>): Notification {
  return {
    id: 'x', type: 'WO_ASSIGNED', entity_type: 'work_order', entity_id: 'wo1',
    params: {}, actor_user_id: null, is_read: false, read_at: null,
    created_at: '2026-06-05T00:00:00', ...over,
  }
}

describe('formatNotification', () => {
  it('WO_ASSIGNED 含编码与标题', () => {
    const s = formatNotification(n({ type: 'WO_ASSIGNED', params: { custom_id: 'C-1', title: '巡检' } }))
    expect(s).toContain('C-1')
    expect(s).toContain('巡检')
    expect(s).toContain('指派')
  })
  it('WO_STATUS_CHANGED 含状态迁移', () => {
    const s = formatNotification(n({ type: 'WO_STATUS_CHANGED', params: { custom_id: 'C-2', from_status: 'OPEN', to_status: 'DONE' } }))
    expect(s).toContain('C-2'); expect(s).toContain('OPEN'); expect(s).toContain('DONE')
  })
  it('REQUEST_SUBMITTED 含请求编码', () => {
    const s = formatNotification(n({ type: 'REQUEST_SUBMITTED', entity_type: 'request', params: { custom_id: 'R-1', title: '报修' } }))
    expect(s).toContain('R-1'); expect(s).toContain('报修')
  })
  it('未知 type 兜底不崩', () => {
    expect(formatNotification(n({ type: 'WHATEVER_NEW', params: {} }))).toBeTruthy()
  })
  it('缺 params 字段不抛', () => {
    expect(() => formatNotification(n({ type: 'WO_ASSIGNED', params: {} }))).not.toThrow()
  })
})

describe('entityRoute', () => {
  it('work_order → 详情命名路由', () => {
    expect(entityRoute(n({ entity_type: 'work_order', entity_id: 'wo9' }))).toEqual({
      name: 'maintenance-work-order-detail', params: { id: 'wo9' },
    })
  })
  it('request → 列表路径', () => {
    expect(entityRoute(n({ entity_type: 'request', entity_id: 'r1' }))).toEqual({ path: '/maintenance/requests' })
  })
  it('无 entity_id → null', () => {
    expect(entityRoute(n({ entity_type: 'work_order', entity_id: null }))).toBeNull()
  })
})

describe('NOTIFICATION_TYPES', () => {
  it('含已知类型与中文 label', () => {
    const codes = NOTIFICATION_TYPES.map((t) => t.code)
    expect(codes).toContain('WO_ASSIGNED')
    expect(NOTIFICATION_TYPES.every((t) => typeof t.label === 'string' && t.label.length > 0)).toBe(true)
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- notificationText` → FAIL（模块不存在）。

- [ ] **Step 3: 实现**（`src/utils/notificationText.ts`）：

```typescript
import type { RouteLocationRaw } from 'vue-router'
import type { Notification } from '@/types/notification'

/** 通知类型清单（code + 中文 label）。偏好开关、类型过滤共用。
 *  实现时核实 backend app/services/notification_service.py 的 type 全集，缺则补。 */
export const NOTIFICATION_TYPES: { code: string; label: string }[] = [
  { code: 'WO_ASSIGNED', label: '工单指派' },
  { code: 'WO_STATUS_CHANGED', label: '工单状态变更' },
  { code: 'WO_AUTO_GENERATED', label: '自动生成工单' },
  { code: 'REQUEST_SUBMITTED', label: '新请求提交' },
  { code: 'PO_SUBMITTED', label: '采购单' },
]

function p(n: Notification, key: string): string {
  const v = n.params?.[key]
  return v == null ? '' : String(v)
}

/** 按 type + params 出中文文案（集中处）。未知 type / 缺字段兜底不崩。 */
export function formatNotification(n: Notification): string {
  const cid = p(n, 'custom_id')
  const title = p(n, 'title')
  switch (n.type) {
    case 'WO_ASSIGNED':
      return `工单 ${cid}「${title}」已指派给你`
    case 'WO_STATUS_CHANGED':
      return `工单 ${cid} 状态 ${p(n, 'from_status')} → ${p(n, 'to_status')}`
    case 'WO_AUTO_GENERATED':
      return `自动生成工单 ${cid}「${title}」`
    case 'REQUEST_SUBMITTED':
      return `新请求 ${cid}「${title}」`
    default:
      if (n.type.startsWith('PO_')) return `采购单 ${cid} 有更新`
      return cid ? `通知 ${cid}` : '你有一条新通知'
  }
}

/** 点击通知的跳转目标；无映射 / 无 entity_id → null（仅标记已读不跳）。 */
export function entityRoute(n: Notification): RouteLocationRaw | null {
  if (!n.entity_id) return null
  if (n.entity_type === 'work_order') {
    return { name: 'maintenance-work-order-detail', params: { id: n.entity_id } }
  }
  if (n.entity_type === 'request') {
    return { path: '/maintenance/requests' }
  }
  return null
}
```

- [ ] **Step 4: 跑绿** `npm run test -- notificationText` → PASS。
- [ ] **Step 5: 门禁 + Commit** typecheck + lint 净；`git commit -am "feat(notif): 文案/路由映射 notificationText + 测试"`

---

## Task 3: 相对时间 helper（format.ts）

**Files:** Modify `frontend/src/utils/format.ts`；Test `frontend/tests/unit/utils/relativeTime.spec.ts`

- [ ] **Step 1: 写失败测试**（`tests/unit/utils/relativeTime.spec.ts`）：

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { relativeTime } from '@/utils/format'

describe('relativeTime', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-06-05T12:00:00Z'))
  })
  afterEach(() => vi.useRealTimers())

  it('30 秒内 → 刚刚', () => {
    expect(relativeTime('2026-06-05T11:59:40Z')).toBe('刚刚')
  })
  it('分钟级', () => {
    expect(relativeTime('2026-06-05T11:55:00Z')).toBe('5 分钟前')
  })
  it('小时级', () => {
    expect(relativeTime('2026-06-05T09:00:00Z')).toBe('3 小时前')
  })
  it('天级', () => {
    expect(relativeTime('2026-06-03T12:00:00Z')).toBe('2 天前')
  })
  it('空值 → 空串', () => {
    expect(relativeTime(null)).toBe('')
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- relativeTime` → FAIL（`relativeTime` 未导出）。

- [ ] **Step 3: 实现** —— 在 `src/utils/format.ts` 末尾加（复用文件内既有 `dayjs` + `toLocal` + `formatDate`；`toLocal` 已定义于文件内，直接调用）：

```typescript
/** 相对时间（自定义中文，无需 dayjs locale 配置；超 30 天显日期）。 */
export function relativeTime(value: string | null | undefined): string {
  if (!value) return ''
  const then = toLocal(value)
  const diffSec = dayjs().diff(then, 'second')
  if (diffSec < 60) return '刚刚'
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin} 分钟前`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour} 小时前`
  const diffDay = Math.floor(diffHour / 24)
  if (diffDay < 30) return `${diffDay} 天前`
  return formatDate(value)
}
```

> 执行时核实 `toLocal` 与 `formatDate` 在 `format.ts` 内可直接引用（`toLocal` 是文件内函数，`formatDate` 已 export 于同文件）。

- [ ] **Step 4: 跑绿** `npm run test -- relativeTime` → PASS。
- [ ] **Step 5: 门禁 + Commit** `git commit -am "feat(notif): relativeTime 相对时间 helper + 测试"`

---

## Task 4: Pinia store（notifications）

**Files:** Create `frontend/src/store/notifications.ts`；Test `frontend/tests/unit/store/notifications.spec.ts`

- [ ] **Step 1: 写失败测试**（`tests/unit/store/notifications.spec.ts`）：

```typescript
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const api = vi.hoisted(() => ({
  listNotifications: vi.fn(),
  getUnreadCount: vi.fn(),
  markRead: vi.fn(),
  markAllRead: vi.fn(),
  getPreference: vi.fn(),
  putPreference: vi.fn(),
}))
vi.mock('@/api/notifications', () => api)

import { useNotificationStore } from '@/store/notifications'

function notif(over = {}) {
  return {
    id: 'n1', type: 'WO_ASSIGNED', entity_type: 'work_order', entity_id: 'wo1',
    params: {}, actor_user_id: null, is_read: false, read_at: null,
    created_at: '2026-06-05T00:00:00', ...over,
  }
}

describe('useNotificationStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    api.getUnreadCount.mockReset().mockResolvedValue({ count: 3 })
    api.listNotifications.mockReset().mockResolvedValue({ items: [notif()], total: 1, page: 1, page_size: 10, total_pages: 1 })
    api.markRead.mockReset().mockResolvedValue(notif({ is_read: true }))
    api.markAllRead.mockReset().mockResolvedValue({ updated: 3 })
    api.getPreference.mockReset().mockResolvedValue({ email_enabled: true, disabled_types: [] })
    api.putPreference.mockReset().mockImplementation(async (p) => p)
  })
  afterEach(() => vi.useRealTimers())

  it('fetchUnread 写 unreadCount', async () => {
    const s = useNotificationStore()
    await s.fetchUnread()
    expect(s.unreadCount).toBe(3)
  })

  it('fetchRecent 写 recent', async () => {
    const s = useNotificationStore()
    await s.fetchRecent()
    expect(s.recent).toHaveLength(1)
  })

  it('markRead 乐观：本地置已读 + unreadCount 递减', async () => {
    const s = useNotificationStore()
    await s.fetchUnread()           // 3
    await s.fetchRecent()           // recent[0] 未读
    await s.markRead('n1')
    expect(s.recent[0].is_read).toBe(true)
    expect(s.unreadCount).toBe(2)
    expect(api.markRead).toHaveBeenCalledWith('n1')
  })

  it('markRead 失败回滚（重新拉未读数）', async () => {
    const s = useNotificationStore()
    await s.fetchUnread()
    api.markRead.mockRejectedValueOnce(new Error('x'))
    api.getUnreadCount.mockResolvedValueOnce({ count: 9 })
    await s.markRead('n1')
    expect(s.unreadCount).toBe(9)   // 回滚=重新 fetchUnread
  })

  it('markAllRead 清零', async () => {
    const s = useNotificationStore()
    await s.fetchUnread()
    await s.fetchRecent()
    await s.markAllRead()
    expect(s.unreadCount).toBe(0)
    expect(s.recent.every((n) => n.is_read)).toBe(true)
  })

  it('startPolling 立即拉一次并定时；stopPolling 清', async () => {
    vi.useFakeTimers()
    const s = useNotificationStore()
    s.startPolling()
    await vi.advanceTimersByTimeAsync(0)
    expect(api.getUnreadCount).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(60000)
    expect(api.getUnreadCount).toHaveBeenCalledTimes(2)
    s.stopPolling()
    await vi.advanceTimersByTimeAsync(120000)
    expect(api.getUnreadCount).toHaveBeenCalledTimes(2)   // 停后不再增
  })

  it('startPolling 幂等（重复 start 不叠定时器）', async () => {
    vi.useFakeTimers()
    const s = useNotificationStore()
    s.startPolling(); s.startPolling()
    await vi.advanceTimersByTimeAsync(60000)
    // 立即各一次? 幂等保证只有一个定时器：start 内先 stop。此处断言 60s 后总调用次数为 2（2×立即 + 1×tick 会是 3，故幂等实现须 start 内 stop 旧的）
    s.stopPolling()
    expect(api.getUnreadCount.mock.calls.length).toBeLessThanOrEqual(3)
  })

  it('loadPrefs / savePrefs', async () => {
    const s = useNotificationStore()
    await s.loadPrefs()
    expect(s.prefs).toEqual({ email_enabled: true, disabled_types: [] })
    await s.savePrefs({ email_enabled: false, disabled_types: ['WO_ASSIGNED'] })
    expect(api.putPreference).toHaveBeenCalledWith({ email_enabled: false, disabled_types: ['WO_ASSIGNED'] })
    expect(s.prefs?.email_enabled).toBe(false)
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- store/notifications` → FAIL。

- [ ] **Step 3: 实现**（`src/store/notifications.ts`，对齐 `store/billing.ts` 风格）：

```typescript
import { defineStore } from 'pinia'

import * as api from '@/api/notifications'
import type { Notification, NotificationPreference } from '@/types/notification'

const POLL_MS = 60000

interface State {
  unreadCount: number
  recent: Notification[]
  prefs: NotificationPreference | null
  pollTimer: ReturnType<typeof setInterval> | null
}

export const useNotificationStore = defineStore('notifications', {
  state: (): State => ({ unreadCount: 0, recent: [], prefs: null, pollTimer: null }),
  actions: {
    async fetchUnread(): Promise<void> {
      this.unreadCount = (await api.getUnreadCount()).count
    },
    async fetchRecent(): Promise<void> {
      this.recent = (await api.listNotifications({ page: 1, page_size: 10 })).items
    },
    async markRead(id: string): Promise<void> {
      const item = this.recent.find((n) => n.id === id)
      const wasUnread = item ? !item.is_read : false
      if (item) item.is_read = true
      if (wasUnread) this.unreadCount = Math.max(0, this.unreadCount - 1)
      try {
        await api.markRead(id)
      } catch {
        if (item) item.is_read = false
        await this.fetchUnread() // 回滚到权威值
      }
    },
    async markAllRead(): Promise<void> {
      await api.markAllRead()
      this.unreadCount = 0
      this.recent = this.recent.map((n) => ({ ...n, is_read: true }))
    },
    async loadPrefs(): Promise<void> {
      this.prefs = await api.getPreference()
    },
    async savePrefs(p: NotificationPreference): Promise<void> {
      this.prefs = await api.putPreference(p)
    },
    startPolling(): void {
      this.stopPolling() // 幂等：先清旧定时器
      void this.fetchUnread()
      this.pollTimer = setInterval(() => void this.fetchUnread(), POLL_MS)
    },
    stopPolling(): void {
      if (this.pollTimer) {
        clearInterval(this.pollTimer)
        this.pollTimer = null
      }
    },
  },
})
```

- [ ] **Step 4: 跑绿** `npm run test -- store/notifications` → PASS。
- [ ] **Step 5: 门禁 + Commit** typecheck + lint 净；`git commit -am "feat(notif): notifications store（未读/最近/乐观已读/偏好/轮询）+ 测试"`

---

## Task 5: 顶栏铃铛（NotificationBell）+ AppTopBar 接线

**Files:** Create `frontend/src/components/NotificationBell.vue`；Modify `frontend/src/components/AppTopBar.vue`；Test `frontend/tests/unit/NotificationBell.spec.ts`；Modify `frontend/tests/unit/AppTopBar.spec.ts`

- [ ] **Step 1: 写 NotificationBell 失败测试**（`tests/unit/NotificationBell.spec.ts`）：

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import NotificationBell from '@/components/NotificationBell.vue'
import { useNotificationStore } from '@/store/notifications'

const push = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))

const slot = { template: '<div><slot /></div>' }
function mountBell() {
  return mount(NotificationBell, {
    global: {
      stubs: { 'el-dropdown': slot, 'el-dropdown-menu': slot, 'el-badge': slot, 'el-icon': slot, 'el-button': slot, 'router-link': slot },
    },
  })
}

describe('NotificationBell', () => {
  beforeEach(() => { setActivePinia(createPinia()); push.mockReset() })

  it('未读>0 显示数字角标', () => {
    const s = useNotificationStore()
    s.unreadCount = 5
    const w = mountBell()
    expect(w.text()).toContain('5')
  })

  it('渲染 recent 文案', () => {
    const s = useNotificationStore()
    s.recent = [{
      id: 'n1', type: 'WO_ASSIGNED', entity_type: 'work_order', entity_id: 'wo1',
      params: { custom_id: 'C-1', title: '巡检' }, actor_user_id: null, is_read: false, read_at: null,
      created_at: '2026-06-05T00:00:00',
    }]
    const w = mountBell()
    expect(w.text()).toContain('C-1')
  })

  it('点击条目 markRead + 跳转', async () => {
    const s = useNotificationStore()
    s.recent = [{
      id: 'n1', type: 'WO_ASSIGNED', entity_type: 'work_order', entity_id: 'wo1',
      params: { custom_id: 'C-1' }, actor_user_id: null, is_read: false, read_at: null,
      created_at: '2026-06-05T00:00:00',
    }]
    const markRead = vi.spyOn(s, 'markRead').mockResolvedValue()
    const w = mountBell()
    await w.find('[data-test="notif-item"]').trigger('click')
    expect(markRead).toHaveBeenCalledWith('n1')
    expect(push).toHaveBeenCalledWith({ name: 'maintenance-work-order-detail', params: { id: 'wo1' } })
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- NotificationBell` → FAIL。

- [ ] **Step 3: 实现 NotificationBell**（`src/components/NotificationBell.vue`）：

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Bell } from '@element-plus/icons-vue'
import { useNotificationStore } from '@/store/notifications'
import { formatNotification, entityRoute } from '@/utils/notificationText'
import { relativeTime } from '@/utils/format'
import type { Notification } from '@/types/notification'

const store = useNotificationStore()
const router = useRouter()
const badge = computed(() => (store.unreadCount > 99 ? '99+' : store.unreadCount))

function onOpen(visible: boolean): void {
  if (visible) void store.fetchRecent()
}
async function onItem(n: Notification): Promise<void> {
  await store.markRead(n.id)
  const to = entityRoute(n)
  if (to) router.push(to)
}
function text(n: Notification): string {
  return formatNotification(n)
}
</script>

<template>
  <el-dropdown trigger="click" popper-class="notif-bell-popper" @visible-change="onOpen">
    <el-badge :value="badge" :hidden="store.unreadCount === 0" :max="9999">
      <button class="notif-bell-btn" aria-label="通知">
        <el-icon><Bell /></el-icon>
      </button>
    </el-badge>
    <template #dropdown>
      <div class="notif-dropdown">
        <div class="notif-head">
          <span>通知</span>
          <el-button text size="small" :disabled="store.unreadCount === 0" @click="store.markAllRead()">
            全部已读
          </el-button>
        </div>
        <div v-if="store.recent.length === 0" class="notif-empty">暂无通知</div>
        <ul v-else class="notif-list">
          <li
            v-for="n in store.recent"
            :key="n.id"
            data-test="notif-item"
            class="notif-item"
            :class="{ unread: !n.is_read }"
            @click="onItem(n)"
          >
            <span v-if="!n.is_read" class="dot" />
            <span class="msg">{{ text(n) }}</span>
            <span class="time">{{ relativeTime(n.created_at) }}</span>
          </li>
        </ul>
        <div class="notif-foot">
          <router-link to="/notifications">查看全部 →</router-link>
        </div>
      </div>
    </template>
  </el-dropdown>
</template>

<style scoped>
.notif-bell-btn {
  width: 28px; height: 28px; border: none; background: transparent; border-radius: 4px;
  cursor: pointer; color: var(--text-regular); display: inline-flex; align-items: center; justify-content: center;
}
.notif-bell-btn:hover { background: var(--bg-hover); }
.notif-dropdown { width: 320px; }
.notif-head { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; border-bottom: 1px solid var(--border-subtle); }
.notif-empty { padding: 24px; text-align: center; color: var(--text-tertiary); font-size: 13px; }
.notif-list { list-style: none; margin: 0; padding: 0; max-height: 360px; overflow-y: auto; }
.notif-item { display: flex; align-items: center; gap: 8px; padding: 10px 12px; cursor: pointer; font-size: 13px; }
.notif-item:hover { background: var(--bg-hover); }
.notif-item.unread .msg { color: var(--text-primary); font-weight: 500; }
.notif-item .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); flex-shrink: 0; }
.notif-item .msg { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.notif-item .time { color: var(--text-tertiary); font-size: 11px; flex-shrink: 0; }
.notif-foot { padding: 8px 12px; text-align: center; border-top: 1px solid var(--border-subtle); }
.notif-foot a { color: var(--el-color-primary); font-size: 12px; text-decoration: none; }
</style>
```

> 执行时核实 `el-badge` 的 `:value`/`:hidden`/`:max` 用法（EP 标准）。若 stub 测试需要，给铃铛根节点保留 `data-test` 非必需（测试用 `notif-item` + 文本）。

- [ ] **Step 4: AppTopBar 接线** —— 改 `src/components/AppTopBar.vue`：
  - `<script setup>` 顶部加 `import NotificationBell from '@/components/NotificationBell.vue'`。
  - 移除 `defineProps` 里的 `unreadCount?: number`（连同模板里 `v-if="(unreadCount ?? 0) > 0"` 的整个 `.topbar-unread` 块删除）。
  - 在 `<span class="topbar-spacer" />` 之后、主题切换 `<button class="topbar-theme">` 之前插 `<NotificationBell />`。

- [ ] **Step 5: 改 AppTopBar.spec** —— 删 `tests/unit/AppTopBar.spec.ts` 中 3 个 `.topbar-unread` 测试（"unreadCount 默认不渲染"/"=0 不渲染"/"=3 渲染徽标"），新增一条断言铃铛存在（NotificationBell 内含 store，须在 `global.plugins` 已有 pinia——`beforeEach(setActivePinia(createPinia()))` 已有；mountTopBar 不再传 unreadCount prop）：

```typescript
import NotificationBell from '@/components/NotificationBell.vue'
// ...
it('顶栏含通知铃铛', () => {
  const w = mountTopBar()
  expect(w.findComponent(NotificationBell).exists()).toBe(true)
})
```
> 执行时核实 `mountTopBar` 的 `global.plugins`/`stubs`：NotificationBell 用 `el-dropdown`/`el-badge`/`el-icon`，若 AppTopBar 测试未全局注册 EP，给 mountTopBar 的 `global.stubs` 补这些（或 `global.plugins` 加 ElementPlus）。以测试实际报错为准最小补齐。

- [ ] **Step 6: 跑绿** `npm run test -- NotificationBell AppTopBar` → PASS。
- [ ] **Step 7: 门禁 + Commit** typecheck + lint 净；`git commit -am "feat(notif): NotificationBell 铃铛下拉 + AppTopBar 接线（替换待阅读死代码）"`

---

## Task 6: 通知中心列表页 + 路由 + 侧栏接线

**Files:** Create `frontend/src/views/notifications/NotificationCenterView.vue`；Modify `frontend/src/router/index.ts`、`frontend/src/components/AppSidebar.vue`；Test `frontend/tests/unit/views/NotificationCenterView.spec.ts`

- [ ] **Step 1: 写失败测试**（`tests/unit/views/NotificationCenterView.spec.ts`）：

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const api = vi.hoisted(() => ({
  listNotifications: vi.fn(),
  markRead: vi.fn(),
  markAllRead: vi.fn(),
  getUnreadCount: vi.fn(),
  getPreference: vi.fn(),
  putPreference: vi.fn(),
}))
vi.mock('@/api/notifications', () => api)
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))

import NotificationCenterView from '@/views/notifications/NotificationCenterView.vue'

const slot = { template: '<div><slot /></div>' }
const stubs = {
  'el-tabs': slot, 'el-tab-pane': slot, 'el-radio-group': slot, 'el-radio-button': slot,
  'el-select': slot, 'el-option': slot, 'el-pagination': true, 'el-button': slot,
  'el-empty': true, 'el-switch': true, NotificationPreferences: true,
}

describe('NotificationCenterView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    api.listNotifications.mockReset().mockResolvedValue({
      items: [{ id: 'n1', type: 'WO_ASSIGNED', entity_type: 'work_order', entity_id: 'wo1',
        params: { custom_id: 'C-1', title: '巡检' }, actor_user_id: null, is_read: false,
        read_at: null, created_at: '2026-06-05T00:00:00' }],
      total: 1, page: 1, page_size: 20, total_pages: 1,
    })
    api.markAllRead.mockReset().mockResolvedValue({ updated: 1 })
    api.markRead.mockReset().mockResolvedValue({})
    api.getUnreadCount.mockReset().mockResolvedValue({ count: 0 })
  })

  it('挂载拉列表并渲染文案', async () => {
    const w = mount(NotificationCenterView, { global: { stubs } })
    await flushPromises()
    expect(api.listNotifications).toHaveBeenCalled()
    expect(w.text()).toContain('C-1')
  })

  it('切到未读过滤重新拉（is_read=false）', async () => {
    const w = mount(NotificationCenterView, { global: { stubs } })
    await flushPromises()
    await (w.vm as unknown as { setFilter: (v: string) => void }).setFilter('unread')
    await flushPromises()
    expect(api.listNotifications).toHaveBeenLastCalledWith(expect.objectContaining({ is_read: false }))
  })

  it('全部已读调用 api', async () => {
    const w = mount(NotificationCenterView, { global: { stubs } })
    await flushPromises()
    await (w.vm as unknown as { onMarkAll: () => Promise<void> }).onMarkAll()
    expect(api.markAllRead).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- NotificationCenterView` → FAIL。

- [ ] **Step 3: 实现 NotificationCenterView**（`src/views/notifications/NotificationCenterView.vue`）：

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import * as api from '@/api/notifications'
import { useNotificationStore } from '@/store/notifications'
import { formatNotification, entityRoute, NOTIFICATION_TYPES } from '@/utils/notificationText'
import { relativeTime } from '@/utils/format'
import NotificationPreferences from '@/components/notifications/NotificationPreferences.vue'
import type { Notification } from '@/types/notification'

const router = useRouter()
const store = useNotificationStore()

const tab = ref<'list' | 'prefs'>('list')
const items = ref<Notification[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const filter = ref<'all' | 'unread'>('all')
const typeFilter = ref<string>('')
const loading = ref(false)

async function load(): Promise<void> {
  loading.value = true
  try {
    const res = await api.listNotifications({
      page: page.value,
      page_size: pageSize,
      ...(filter.value === 'unread' ? { is_read: false } : {}),
      ...(typeFilter.value ? { type: typeFilter.value } : {}),
    })
    items.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function setFilter(v: 'all' | 'unread'): Promise<void> {
  filter.value = v
  page.value = 1
  return load()
}
function setType(v: string): void {
  typeFilter.value = v
  page.value = 1
  void load()
}
function onPage(p: number): void {
  page.value = p
  void load()
}
async function onItem(n: Notification): Promise<void> {
  await store.markRead(n.id)
  n.is_read = true
  const to = entityRoute(n)
  if (to) router.push(to)
}
async function onMarkAll(): Promise<void> {
  await store.markAllRead()
  await load()
}

onMounted(load)
defineExpose({ setFilter, setType, onPage, onMarkAll })
</script>

<template>
  <div class="notif-center">
    <h2>通知中心</h2>
    <el-tabs v-model="tab">
      <el-tab-pane label="通知" name="list">
        <div class="notif-toolbar">
          <el-radio-group :model-value="filter" @update:model-value="setFilter">
            <el-radio-button label="all">全部</el-radio-button>
            <el-radio-button label="unread">未读</el-radio-button>
          </el-radio-group>
          <el-select :model-value="typeFilter" placeholder="全部类型" clearable @update:model-value="setType">
            <el-option v-for="t in NOTIFICATION_TYPES" :key="t.code" :label="t.label" :value="t.code" />
          </el-select>
          <span class="spacer" />
          <el-button size="small" :disabled="store.unreadCount === 0" @click="onMarkAll">全部已读</el-button>
        </div>
        <el-empty v-if="items.length === 0" description="暂无通知" />
        <ul v-else class="notif-rows" v-loading="loading">
          <li
            v-for="n in items"
            :key="n.id"
            class="notif-row"
            :class="{ unread: !n.is_read }"
            @click="onItem(n)"
          >
            <span v-if="!n.is_read" class="dot" />
            <span class="msg">{{ formatNotification(n) }}</span>
            <span class="time">{{ relativeTime(n.created_at) }}</span>
          </li>
        </ul>
        <el-pagination
          v-if="total > pageSize"
          layout="prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          @current-change="onPage"
        />
      </el-tab-pane>
      <el-tab-pane label="偏好设置" name="prefs">
        <NotificationPreferences />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.notif-center { padding: 4px 2px; }
.notif-toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.notif-toolbar .spacer { flex: 1; }
.notif-rows { list-style: none; margin: 0; padding: 0; }
.notif-row { display: flex; align-items: center; gap: 10px; padding: 12px; border-bottom: 1px solid var(--border-subtle); cursor: pointer; }
.notif-row:hover { background: var(--bg-hover); }
.notif-row.unread .msg { color: var(--text-primary); font-weight: 500; }
.notif-row .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); flex-shrink: 0; }
.notif-row .msg { flex: 1; }
.notif-row .time { color: var(--text-tertiary); font-size: 12px; flex-shrink: 0; }
</style>
```

> `setFilter` 返回 `load()` 以便测试 `await` 到刷新完成；`defineExpose` 暴露给测试驱动。执行时若 lint 嫌 `return load() as unknown as void` 别扭，改为 `void load()` 并在测试用 `flushPromises()`（测试已 flush）。

- [ ] **Step 4: 路由 + 侧栏接线** ——
  - `src/router/index.ts`：在合适位置（认证后路由组）加：
    ```typescript
    {
      path: '/notifications',
      name: 'notification-center',
      component: () => import('@/views/notifications/NotificationCenterView.vue'),
      meta: { title: '通知中心', requiresAuth: true },
    },
    ```
  - `src/components/AppSidebar.vue:107`：把 `items.push({ label: '通知中心', soon: true, icon: Bell })` 改为 `items.push({ label: '通知中心', path: '/notifications', icon: Bell })`。

- [ ] **Step 5: 跑绿** `npm run test -- NotificationCenterView` → PASS（Task 7 的 NotificationPreferences 此时已 stub；本 task 先建一个最小占位 `src/components/notifications/NotificationPreferences.vue`：`<template><div /></template>` 使 import 不报错，Task 7 再实现）。

> **Step 5 补**：先创建占位 `src/components/notifications/NotificationPreferences.vue` 内容 `<template><div /></template>`，避免本 task typecheck/import 失败；Task 7 替换为真实现。

- [ ] **Step 6: 门禁 + Commit** typecheck + lint 净；`git commit -am "feat(notif): 通知中心列表页 + 路由 + 侧栏接线（去 soon 占位）"`

---

## Task 7: 通知偏好 tab（NotificationPreferences）

**Files:** Modify `frontend/src/components/notifications/NotificationPreferences.vue`（Task 6 的占位 → 真实现）；Test `frontend/tests/unit/NotificationPreferences.spec.ts`

- [ ] **Step 1: 写失败测试**（`tests/unit/NotificationPreferences.spec.ts`）：

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const api = vi.hoisted(() => ({
  getPreference: vi.fn(),
  putPreference: vi.fn(),
  getUnreadCount: vi.fn(),
  listNotifications: vi.fn(),
  markRead: vi.fn(),
  markAllRead: vi.fn(),
}))
vi.mock('@/api/notifications', () => api)
vi.mock('element-plus', () => ({ ElMessage: { success: vi.fn(), error: vi.fn() } }))

import NotificationPreferences from '@/components/notifications/NotificationPreferences.vue'

const slot = { template: '<div><slot /></div>' }
const stubs = { 'el-switch': true, 'el-button': slot, 'el-form': slot, 'el-form-item': slot }

describe('NotificationPreferences', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    api.getPreference.mockReset().mockResolvedValue({ email_enabled: true, disabled_types: ['WO_ASSIGNED'] })
    api.putPreference.mockReset().mockImplementation(async (p) => p)
  })

  it('挂载加载偏好', async () => {
    mount(NotificationPreferences, { global: { stubs } })
    await flushPromises()
    expect(api.getPreference).toHaveBeenCalled()
  })

  it('保存把关闭的类型写入 disabled_types', async () => {
    const w = mount(NotificationPreferences, { global: { stubs } })
    await flushPromises()
    // 模拟：关闭 WO_STATUS_CHANGED（在组件内 toggle 后 save）
    await (w.vm as unknown as { toggleType: (c: string, on: boolean) => void; save: () => Promise<void> }).toggleType('WO_STATUS_CHANGED', false)
    await (w.vm as unknown as { save: () => Promise<void> }).save()
    expect(api.putPreference).toHaveBeenCalled()
    const arg = api.putPreference.mock.calls[0][0]
    expect(arg.disabled_types).toContain('WO_STATUS_CHANGED')
    expect(arg.disabled_types).toContain('WO_ASSIGNED') // 原有保留
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- NotificationPreferences` → FAIL（占位无逻辑）。

- [ ] **Step 3: 实现**（`src/components/notifications/NotificationPreferences.vue`）：

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useNotificationStore } from '@/store/notifications'
import { NOTIFICATION_TYPES } from '@/utils/notificationText'

const store = useNotificationStore()
const emailEnabled = ref(true)
const disabled = ref<Set<string>>(new Set())
const saving = ref(false)

function isOn(code: string): boolean {
  return !disabled.value.has(code)
}
function toggleType(code: string, on: boolean): void {
  if (on) disabled.value.delete(code)
  else disabled.value.add(code)
  disabled.value = new Set(disabled.value) // 触发响应
}
async function save(): Promise<void> {
  saving.value = true
  try {
    await store.savePrefs({ email_enabled: emailEnabled.value, disabled_types: [...disabled.value] })
    ElMessage.success('已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await store.loadPrefs()
  emailEnabled.value = store.prefs?.email_enabled ?? true
  disabled.value = new Set(store.prefs?.disabled_types ?? [])
})

defineExpose({ toggleType, save })
</script>

<template>
  <el-form label-width="140px" class="notif-prefs">
    <el-form-item label="邮件通知">
      <el-switch v-model="emailEnabled" />
    </el-form-item>
    <el-form-item v-for="t in NOTIFICATION_TYPES" :key="t.code" :label="t.label">
      <el-switch :model-value="isOn(t.code)" @update:model-value="(v: boolean) => toggleType(t.code, v)" />
    </el-form-item>
    <el-form-item>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </el-form-item>
  </el-form>
</template>

<style scoped>
.notif-prefs { max-width: 480px; }
</style>
```

- [ ] **Step 4: 跑绿** `npm run test -- NotificationPreferences` → PASS。
- [ ] **Step 5: 门禁 + Commit** typecheck + lint 净；`git commit -am "feat(notif): 通知偏好 tab（email + 按类型开关）+ 测试"`

---

## Task 8: AppLayout 轮询接线 + 登出协同 + 全量门禁

**Files:** Modify `frontend/src/layouts/AppLayout.vue`、`frontend/src/store/auth.ts`（登出停轮询）

- [ ] **Step 1: AppLayout 启停轮询** —— 改 `src/layouts/AppLayout.vue` `<script setup>`：加 `import { onMounted, onUnmounted, watch } from 'vue'`（合并既有 `watch` import）、`import { useNotificationStore } from '@/store/notifications'`；
  ```typescript
  const notif = useNotificationStore()
  onMounted(() => notif.startPolling())
  onUnmounted(() => notif.stopPolling())
  ```

- [ ] **Step 2: 登出停轮询** —— 在 `src/store/auth.ts` 的登出 action（执行时核实其名，如 `logout`）内，清理通知 store（动态 import 防循环，参照 billing 在 auth 内被动态引用的模式）：
  ```typescript
  const { useNotificationStore } = await import('./notifications')
  const n = useNotificationStore()
  n.stopPolling()
  n.$reset()
  ```
  > 执行时核实 auth store 登出 action 名与是否 async；若非 async，用 `import('./notifications').then(({ useNotificationStore }) => { const n = useNotificationStore(); n.stopPolling(); n.$reset() })`。

- [ ] **Step 3: 全量前端门禁** `cd frontend && npm run test && npm run typecheck && npm run lint` → 全绿（含既有 AppTopBar/AppSidebar 测试同步通过）。

- [ ] **Step 4: dev 实测（视觉冒烟）** —— 起 dev（见 [[running-smartsop-dev]]，前后端已可能在跑，重启前端确保新代码）；chrome-devtools 登录后看顶栏铃铛渲染、点开下拉、进 `/notifications` 看列表/偏好 tab。截图 `.verify-screenshots/`，读图确认非空白、暗色协调。记录结论。

- [ ] **Step 5: Commit + 汇报** `git commit -am "feat(notif): AppLayout 轮询启停 + 登出协同"`；汇报新增/改动文件、前端通过数、dev 实测结论、遗留项。

---

## Self-Review（执行后记录结论）

**Spec 覆盖**：§1 API→T1 ✓；§2 store→T4 ✓；§3 铃铛→T5 ✓；§4 列表页→T6 ✓；§5 偏好→T7 ✓；§6 文案/路由→T2 ✓；相对时间→T3 ✓；轮询启停→T8 ✓；测试策略→各 task TDD + T8 dev 冒烟 ✓。

**执行注意**：
1. 标记已读乐观更新 + 失败回滚（重新 fetchUnread）；markAllRead 清零本地。
2. startPolling 幂等（内部先 stop）；AppLayout 挂载启、卸载/登出停。
3. AppTopBar 移除 `unreadCount` prop + `.topbar-unread` 死代码 → 删对应 3 个旧测试、加铃铛存在断言；mountTopBar 按报错补 EP stub/plugin。
4. Task 6 先建 NotificationPreferences 占位再 Task 7 实现，避免 import 失败。
5. 侧栏 `通知中心` 由 `soon:true` 改 `path:'/notifications'`。
6. request 无详情路由→跳列表；WO→详情命名路由。
7. 文案/类型集合集中 notificationText.ts；类型全集实现时核实后端 notification_service.py。
