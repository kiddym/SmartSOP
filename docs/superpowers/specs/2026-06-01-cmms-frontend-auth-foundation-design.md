# CMMS 前端认证地基 + 导航壳 — 设计文档

- 日期：2026-06-01
- 状态：设计草案，待评审（实施计划另立 / writing-plans）
- 背景：Smart CMMS 后端 phase 0–5 已 ~85% 完成（含差异化核心 SOP×工单执行），但**前端只有 SOP 一条线**，15 个 CMMS 业务模块前端全缺、连登录页都没有（见 `2026-06-01-remaining-work-audit.md`）。瓶颈在前端。本 spec 是 CMMS 前端主线的**第一份地基**——所有业务模块前端的前置。
- 关联：[剩余工作盘点](./2026-06-01-remaining-work-audit.md) · [总路线图](./2026-05-30-smart-cmms-master-roadmap-design.md)

---

## 1. 目标与范围

### 1.1 目标

为 CMMS 前端建立**认证地基与全局导航壳**，让用户能登录/注册进入系统、会话被安全管理、未登录被拦截，并提供一个预留全模块的导航骨架——后续每个业务模块（工单/资产/库存…）的前端都直接挂在这个地基上。

### 1.2 范围（纯地基）

- 登录页、注册页（注册 = 新建组织）
- token 拦截注入 + 401 自动续期 + 路由守卫
- 全局导航壳（预留全 CMMS 模块菜单，未建模块占位）
- 用户菜单 + 登出
- 权限框架（authz）的**工具就位**（不强制拦截）

### 1.3 明确非目标（排除）

- **密码找回 / 邮箱激活 / 用户邀请**——后端尚未实现，本 spec 不依赖、不做（登录页不放找回入口，或放禁用按钮提示"请联系管理员"）
- 任何业务模块**页面**（仅占位菜单项）
- 权限**强制拦截**（框架就位但本阶段不按权限隐藏/拦截）
- i18n 多语言切换（用现有中文 + 既有 `auth` 字符串；多语言框架后做）

---

## 2. 三个核心决策（已 brainstorm 定稿）

1. **范围 = 纯地基**：业务模块各自独立 spec，不在本 spec 内。
2. **会话 = access 内存(Pinia) + refresh localStorage + 401 单飞续期 + 刷新页 bootstrap 恢复**。契合后端 JWT 双 token（access+refresh，走 Authorization header）。
3. **authz = 框架就位不强制**：store 存角色 + 权限码，提供 `hasPermission(code)` + 路由 `meta.requiresAuth/requiredPermission`；守卫本阶段只强制 `requiresAuth`，权限过滤/菜单显隐留给各业务模块接入时按 meta 启用。

---

## 3. 架构与组件分解

复用现有：`http.ts`(axios)、Pinia、Vue Router、Element Plus、i18n 的 `auth` 字符串。

每个单元单一职责、可独立测试；`store/auth.ts` 是**唯一会话真相源**，`http.ts`/守卫/`usePermission` 都只是它的消费者。

| 文件 | 类型 | 职责 |
|---|---|---|
| `api/auth.ts` | 新增 | 封装后端 `/auth/login`、`/auth/register`、`/auth/refresh`、`/auth/me` |
| `utils/authStorage.ts` | 新增 | refresh token 的 localStorage 集中读写（换存储只改这里） |
| `store/auth.ts` (Pinia) | 新增 | **唯一会话真相源**。state：`accessToken`(内存)、`user`、`roleCode`、`permissionCodes[]`、`ready`；actions：`login/register/logout/refresh/loadMe/bootstrap`；getters：`isAuthenticated`、`hasPermission(code)` |
| `api/http.ts` | 改造 | 请求拦截器注入 `Authorization: Bearer <access>`；响应拦截器 401 → **单飞 refresh** 换新 access 重试原请求，refresh 失败则登出 |
| `composables/usePermission.ts` | 新增 | `hasPermission(code)` 薄封装（读 auth store），供后续业务模块统一用 |
| `router/index.ts` | 改造 | 加 `/login`、`/register` 公开路由 + 全局 `beforeEach` 守卫；现有路由补 `meta.requiresAuth` |
| `layouts/AuthLayout.vue` | 新增 | 登录/注册的无壳布局（居中卡片） |
| `views/auth/LoginView.vue` | 新增 | 登录页 |
| `views/auth/RegisterView.vue` | 新增 | 注册页（新建组织） |
| `components/AppSidebar.vue` | 改造 | 从"程序库/草稿箱"扩成按 roadmap 域分组的全模块导航 |
| `components/UserMenu.vue` | 新增 | 顶栏用户菜单（用户/组织名）+ 登出 |

**边界**：`store/auth.ts` 持有全部会话逻辑；`http.ts` 只从 store 取 token、不自己存；守卫只读 store getter；`usePermission` 是 store 的只读视图。

---

## 4. 数据流

**① 登录**
```
LoginView 提交(email/password) → store.login()
  → api.auth.login → 后端返 TokenPair{access, refresh}
  → 存 access(内存) + refresh(localStorage)
  → store.loadMe() 拉 /me 补 user/roleCode/permissionCodes
  → 跳 redirect 参数指向的原路径，否则默认首页
```
（后端 login 只返 token、不含 user，故登录后必须 `loadMe()`）

**② 注册（新建组织）**
```
RegisterView 提交(组织名/邮箱/密码) → store.register()
  → api.auth.register → 后端建 Company+默认角色+管理员 + 返 TokenPair
  → 同①后续（存 token + loadMe + 跳转）
```

**③ 请求注入**：请求拦截器从 store 读 `accessToken`，有则加 `Authorization: Bearer`。

**④ 401 单飞续期（关键正确性点）**
```
响应 401（且非 refresh 请求本身）：
  已有进行中的 refresh Promise → 等它，成功后用新 access 重试自己
  否则 → 发起唯一一个 refresh（用 localStorage refresh token）：
        成功 → 更新 store.access → 重试所有挂起的原请求
        失败 → store.logout() + 跳 /login
```
**单飞(single-flight)**：多个并发请求同时 401 时只发一个 refresh，其余共享结果，杜绝刷新风暴/竞态。

**⑤ 刷新页面恢复（bootstrap，关键正确性点）**
```
app 启动 → store.bootstrap()：
  localStorage 有 refresh → refresh 换 access → loadMe() → 会话恢复
  失败/无 → 清空 → 视为未登录
守卫必须 await store.ready（bootstrap 完成）再放行，避免"刷新后瞬间被误判未登录"的闪烁
```

**⑥ 登出**：清 access(内存) + refresh(localStorage) + 身份 → 跳 /login（后端若无 logout 端点则纯前端清除）。

**⑦ 路由守卫 `beforeEach`**（按"authz 框架就位不强制"）：
```
1. await store.ready（bootstrap 完成）
2. meta.requiresAuth && !isAuthenticated → /login?redirect=原路径
3. 已登录访问 /login | /register → 跳首页
4. meta.requiredPermission → 本阶段【不拦截】（meta 先声明、备用），权限强制留给业务模块阶段
```

**⑧ 权限框架**：`/me` 的角色 + 权限码进 store；`hasPermission(code)` = `super_admin 全通过 || permissionCodes.includes(code)`；`usePermission` 暴露给组件/菜单。本阶段菜单不强制按权限隐藏。

---

## 5. 导航壳（`AppSidebar` 改造）

按 roadmap 域分组，每项声明 `route name + requiredPermission(备用)`：

| 分组 | 菜单项 | 本阶段状态 |
|---|---|---|
| SOP | 程序库·草稿箱·文件夹·字段·标题字典·审计 | ✅ 现有可用 |
| 维护 | 工单·资产·位置·请求·预防性维护·计量 | 占位"即将上线"（禁用 + tooltip） |
| 供应 | 备件库存·采购单·供应商·客户 | 占位 |
| 洞察 | 分析仪表盘·通知中心 | 占位 |
| 平台 | 用户·角色·团队·公司设置 | 占位 |

顶栏 `UserMenu`：显示当前用户名/组织名 + 登出。

---

## 6. 错误处理

- 登录失败（401/凭证错）→ 表单内联错误（复用 `errorMessage`）
- refresh 失败 → 登出 + 跳登录 + 提示"会话已过期，请重新登录"
- 网络错误 → toast
- 注册失败（如 slug 冲突/邮箱已存在）→ 表单内联错误

---

## 7. 测试策略（vitest + @vue/test-utils，对齐项目）

- `store/auth`：login / logout / refresh / bootstrap / hasPermission（mock api）
- **`http` 拦截器：401 单飞续期**（并发 401 只发一个 refresh、refresh 失败登出）— 最关键
- 路由守卫：未登录拦截 / 已登录重定向 / bootstrap 等待
- `LoginView` / `RegisterView`：表单提交 → 调 store → 跳转（mock store）
- `usePermission` / `hasPermission` 取值逻辑

---

## 8. 后端依赖

复用现有、已就绪的：
- `POST /auth/login`（返 TokenPair）、`POST /auth/register`（建 Company+默认角色+管理员）、`POST /auth/refresh`、`GET /auth/me`（返用户 + 角色）
- RBAC：`require_permission` / `effective_codes` / 内置角色 / `deps.get_current_user`（设租户上下文）

后端尚缺、本 spec **不依赖**：密码重置、邮箱激活、用户邀请。

---

## 9. 实现顺序建议（细化留给 writing-plans）

1. `api/auth.ts` + `utils/authStorage.ts` + `store/auth.ts`（会话真相源 + 单测）
2. `api/http.ts` 拦截器改造（请求注入 + 401 单飞续期 + 单测）
3. `router` 守卫 + `meta.requiresAuth` + bootstrap 接线
4. `usePermission` + 权限码消费
5. `AuthLayout` + `LoginView` + `RegisterView`
6. `AppSidebar` 导航壳改造 + `UserMenu`

依赖：① → ②/③ → ④ → ⑤/⑥。

---

## 10. 与批量解析的关系

批量解析（SOP 模块增强）已在 `feat/batch-word-parsing` 完成实现（Plan 1+2+3）。本 spec 属 CMMS 前端主线，与之并行、互不依赖。两条线最终都汇入 `main`。
