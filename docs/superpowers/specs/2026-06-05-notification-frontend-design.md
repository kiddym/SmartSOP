# 通知系统前端 设计

> 后端通知系统完整（`notifications` 列表/未读数/标记已读/全部已读 + `notification-preferences` 偏好读写，service 已接线 `on_wo_assigned`/`on_wo_status_changed` 等），但**前端零对接**——`AppTopBar` 有 `unreadCount` prop + "待阅读" 徽标却无人传值（孤立死代码），侧栏「通知中心」项为 `soon:true` 占位。本轮做纯前端三件套把后端在产的通知接出来。ROI 高（后端就绪、用户可见），见 [[atlas-parity-backfill]] 前端缺位项。

## 范围与已确认决策

- **三件套**：顶栏铃铛下拉 + 通知中心列表页 + 通知偏好设置。
- **未读数新鲜度**：无 WebSocket（实时推送未做），轮询 `GET /unread-count` ~60s + 动作触发刷新（打开铃铛/标记已读/路由切换）。
- **纯前端**：后端不动（所有端点已就绪）。
- **偏好位置**：通知中心页内 tab（非侧栏「设置」组单列）。
- **request 通知**：跳列表页（`/maintenance/requests` 无 `:id` 详情路由）。

## 后端契约（已就绪，前端对齐，不改）

- `GET /api/v1/notifications?page&page_size&is_read?&type?` → `Page<NotificationRead>`。
- `GET /api/v1/notifications/unread-count` → `{count:int}`。
- `POST /api/v1/notifications/{id}/read` → `NotificationRead`。
- `POST /api/v1/notifications/read-all` → `{updated:int}`。
- `GET /api/v1/notification-preferences` → `{email_enabled:bool, disabled_types:string[]}`。
- `PUT /api/v1/notification-preferences` body `{email_enabled, disabled_types}` → 同上。
- `NotificationRead`：`id, type, entity_type, entity_id, params:dict, actor_user_id, is_read, read_at, created_at`。
- 通知类型与 params：`WO_ASSIGNED{custom_id,title}` / `WO_STATUS_CHANGED{custom_id,from_status,to_status}` / `WO_AUTO_GENERATED{custom_id,title}` / `REQUEST_SUBMITTED{custom_id,title}` / 采购单 `PO_*{custom_id}`。entity_type ∈ work_order/request。
- 通知按 `recipient_user_id` 归属当前用户，无额外权限门控（所有认证用户皆有）。

## 组件与改动

### 1. API 客户端 `src/api/notifications.ts`（新建）

对齐既有 `src/api/*.ts` 风格（`import { http } from './http'`，`http.get/post/put(...).then(r=>r.data)`）：
- `interface Notification { id; type; entity_type:string|null; entity_id:string|null; params:Record<string,unknown>; actor_user_id:string|null; is_read:boolean; read_at:string|null; created_at:string }`
- `interface NotificationPreference { email_enabled:boolean; disabled_types:string[] }`
- `listNotifications(params:{page?;page_size?;is_read?:boolean;type?:string})` → `Page<Notification>`（复用既有 `Page<T>` 类型）。
- `getUnreadCount()` → `{count:number}`。
- `markRead(id:string)` → `Notification`。
- `markAllRead()` → `{updated:number}`。
- `getPreference()` → `NotificationPreference`；`putPreference(p:NotificationPreference)` → `NotificationPreference`。

### 2. Pinia store `src/store/notifications.ts`（新建）

- state：`unreadCount:number`、`recent:Notification[]`（下拉用，最近 10）、`prefs:NotificationPreference|null`、`pollTimer`（句柄）。
- getters：无（unreadCount 直读）。
- actions：
  - `fetchUnread()`：`getUnreadCount()` → 写 `unreadCount`。
  - `fetchRecent()`：`listNotifications({page:1,page_size:10})` → 写 `recent`。
  - `markRead(id)`：**乐观**——本地 `recent` 该条 `is_read=true`、`unreadCount=max(0,unreadCount-1)`，再 `markRead(id)`；失败回滚（重新 `fetchUnread`）。
  - `markAllRead()`：`markAllRead()` → `unreadCount=0`、本地 recent 全置已读。
  - `loadPrefs()`/`savePrefs(p)`。
  - `startPolling()`：`fetchUnread()` 立即一次 + `setInterval(fetchUnread, 60000)`；`stopPolling()` 清 interval。重复 start 幂等（先 stop）。
- 启停接线：`AppLayout`（已认证外壳）`onMounted(startPolling)` / `onUnmounted(stopPolling)`；登出时 `stopPolling()` + 清零。与 auth 协同用动态 `import('./notifications')`（参照 `store/billing.ts` 被 auth 动态引用的模式，避免循环依赖）。

### 3. 顶栏铃铛下拉（改 `src/components/AppTopBar.vue` + 子组件 `NotificationBell.vue`）

- 新建 `src/components/NotificationBell.vue`：`el-dropdown`（trigger=click）+ Bell 图标 + 未读角标（`unreadCount>0` 显示，`>99` 显 `99+`）。下拉内容：标题行「通知」+「全部已读」；`recent` 列表（每条：`formatNotification` 文案 + 相对时间 + 未读圆点）；空态「暂无通知」；底部「查看全部 →」跳通知中心。打开下拉时 `fetchRecent()`。
- 点单条：`store.markRead(id)` + `router.push(entityRoute(n))`（无映射则只标记不跳）。
- `AppTopBar.vue`：移除死代码「待阅读 N」文本徽标，改挂 `<NotificationBell />`（topbar-spacer 之后、主题切换之前）。`AppTopBar.spec.ts` 同步调整。

### 4. 通知中心页 `src/views/notifications/NotificationCenterView.vue`（新建）

- `el-tabs`：
  - **【通知】**：过滤栏（`el-radio-group` 全部/未读 + `el-select` 按类型）；**行式列表**（非 `el-table`——每行：`formatNotification` 文案 + 相对时间 + 已读/未读态指示，整行可点）；分页（`el-pagination`，page_size 20）；顶部「全部已读」。点击行同铃铛行为（markRead + 跳转）。
  - **【偏好设置】**：`NotificationPreferences.vue`（见 5）。
- 路由：`src/router/index.ts` 加 `{ path:'/notifications', name:'notification-center', component, meta:{title:'通知中心', requiresAuth:true} }`。侧栏 `AppSidebar.vue` 把「通知中心」项的 `soon:true` 去掉、加 `path:'/notifications'`。

### 5. 偏好子组件 `src/components/notifications/NotificationPreferences.vue`（新建）

- `onMounted` `store.loadPrefs()`；`el-switch` email_enabled；**按通知类型逐一开关**（on=接收，off=加入 `disabled_types`）；「保存」→ `store.savePrefs()`，成功 `ElMessage`。类型集合 + 中文 label 集中在一处常量（如 `notificationText.ts` 旁的 `NOTIFICATION_TYPES`），实现时**以 backend `notification_service.py` 实际 type 常量为准**枚举（当前已知：WO_ASSIGNED / WO_STATUS_CHANGED / WO_AUTO_GENERATED / REQUEST_SUBMITTED + 采购单类型；实现时核实全集）。

### 6. 文案/路由映射 `src/utils/notificationText.ts`（新建）

- `formatNotification(n:Notification):string`：按 `type`+`params` 出中文（zh-CN 集中此处）：
  - `WO_ASSIGNED` → `工单 {custom_id}「{title}」已指派给你`
  - `WO_STATUS_CHANGED` → `工单 {custom_id} 状态 {from_status} → {to_status}`
  - `WO_AUTO_GENERATED` → `自动生成工单 {custom_id}「{title}」`
  - `REQUEST_SUBMITTED` → `新请求 {custom_id}「{title}」`
  - `PO_*` → `采购单 {custom_id} …`
  - 未知 type / 缺字段 → 兜底通用文案（不崩，缺字段以空串/占位）。
- `entityRoute(n):RouteLocationRaw|null`：`work_order`→`{name:'maintenance-work-order-detail',params:{id:entity_id}}`；`request`→`{path:'/maintenance/requests'}`；其它/`entity_id` 空 → `null`（不跳）。

## 测试策略（Vitest）

- `store/notifications.spec.ts`（mock `@/api/notifications`）：fetchUnread 写值；markRead 乐观（recent 该条已读 + unreadCount 递减）+ 失败回滚；markAllRead 清零；startPolling 幂等 + stopPolling 清 interval（用 `vi.useFakeTimers`）。
- `utils/notificationText.spec.ts`：5 类型文案断言 + 未知 type 兜底 + 缺 params 字段不抛。
- `components/NotificationBell.spec.ts`：未读>0 显角标；渲染 recent 文案；点击条目触发 markRead + router.push（mock router）；空态。
- `views/NotificationCenterView.spec.ts`：tab 切换；过滤（全部/未读、类型）；分页；全部已读。
- `components/NotificationPreferences.spec.ts`：加载、切换类型开关写 disabled_types、保存调用 putPreference。
- `AppTopBar.spec.ts`：同步——铃铛替换「待阅读」徽标后调整断言（不再断言 `.topbar-unread`，改断言 `NotificationBell` 存在）。
- 门禁：`cd frontend && npm run test && npm run typecheck && npm run lint`（--max-warnings 0）。

## 边界与非目标

- 不做 WebSocket 实时推送（轮询 60s）；不改后端任何代码/迁移。
- 不做通知声音 / 浏览器桌面通知 / 邮件发送（后端 email_outbox 既有，前端仅读写 `email_enabled` 开关）。
- 不做通知删除/归档（后端无此端点）。

## 净室红线

全新原创，不复制任何第三方（尤其 Atlas）的代码/命名/文案。见 [[cmms-clean-room-baseline]]。

## 验收标准

- 顶栏铃铛显未读角标（轮询 60s + 动作刷新）；下拉显最近 10 条、可标记已读/全部已读、点击跳转实体（WO 深链 / request 列表）。
- 通知中心页：列表分页 + 过滤（全部/未读 + 类型）+ 全部已读；偏好 tab 可改 email 开关 + 按类型开关并保存。
- 侧栏「通知中心」由 `soon` 占位变为可达路由。
- 5 类型文案正确、未知类型兜底不崩。
- 前端 `npm run test`/`typecheck`/`lint(--max-warnings 0)` 全绿；既有 AppTopBar 测试同步通过。
- 净室红线不破。
