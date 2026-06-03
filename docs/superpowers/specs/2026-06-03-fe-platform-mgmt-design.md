# 设计：FE-1 平台管理前端（5 子模块）

- 日期：2026-06-03
- 范围：前端（Vue 3 + Element Plus + Pinia + vue-router），把已就绪的平台后端（用户/角色/团队/公司设置/货币）变成可用界面。含一个极小只读后端前置（权限目录端点）。
- 分支：feat/fe-platform-mgmt（基于 main 2da56a4）
- 基线约束：仅中文、不做 i18n（沿用现有 zh-CN，不新增 locale）；UI 走 Element Plus `el-table` + `el-dialog` 表单（非独立详情页）；状态以组件内直调 api 为主、轻 Pinia store。净室原创。

## 1. 背景与现状

前端栈：Vue 3 + Vite + TS + Pinia + Element Plus + vue-router + vitest；`vue-tsc --noEmit` typecheck + prettier。

既有约定（须遵循）：
- `src/api/*.ts`：薄封装 `http`（axios 实例，含 401 单飞续期、token 注入），返回 typed promise；类型在 `src/types/*`。
- `src/store/*.ts`：Pinia。`store/auth.ts` 暴露 `user`（CurrentUser：role_code/permissions）、getter `hasPermission(code)`（super_admin 通配 + permissions 包含）。
- `src/views/*`：页面组件。`src/router/index.ts`：扁平路由，`meta.requiresAuth`，`authGuard` 守卫。
- 导航 `src/components/AppSidebar.vue`：数据驱动 `groups: NavGroup[]`，项 `{label, path?, soon?}`；`soon:true` 渲染「即将上线」禁用项。**「平台」组现有 用户/角色/团队/公司设置 四项均为 `soon`**（待接入）。

后端就绪端点（均 `/api/v1`）：

| 子模块 | 端点 | 权限 |
|---|---|---|
| 用户 | GET/POST `/users`、POST `/users/invite`、GET/PATCH/DELETE `/users/{id}` | view/create/edit/delete |
| 角色 | GET/POST `/roles`、PATCH/DELETE `/roles/{id}` | role.view / role.manage |
| 团队 | GET/POST `/teams`、PATCH/DELETE `/teams/{id}`、PUT `/teams/{id}/members` | team.view / team.manage |
| 公司设置 | GET `/company-settings`（任意登录）、PUT（COMPANY_SETTINGS） | — / company_settings |
| 货币 | GET `/currencies`（任意登录）、POST/DELETE（CURRENCY_MANAGE） | — / currency.manage |

## 2. 小后端前置：权限目录端点

角色表单需渲染"可分配权限"勾选框，但后端**无列出全部权限的端点**（仅 RoleCreate 接受 `permissions: list[str]` 并校验合法性）。

新增只读端点 `GET /api/v1/permissions`（权限 ROLE_VIEW），返回 `ALL_PERMISSIONS` 的分组视图，供前端渲染分域勾选：

```json
[
  {"group": "平台", "permissions": [{"code": "user.view", "label": "用户-查看"}, ...]},
  {"group": "工单", "permissions": [...]},
  ...
]
```

实现：在 roles router（或新 permissions router）加端点，从 `app.permissions` 的分组常量（`_PLATFORM`/`_WORKORDER`/…）构造分组 + 中文 label 映射。纯静态、无 DB。这是本轮唯一后端改动。

> 中文 label：可在后端维护 code→中文 映射（集中、随权限演进），或前端维护。**置于后端**（与权限定义同源，避免漂移）。

## 3. 五子模块（前端）

通用：每子模块 = `api/<x>.ts` + `types/<x>.ts` + `views/platform/<X>View.vue`（`el-table` 列表 + `el-dialog` 增改表单）+ 路由 + 导航接线 + RBAC 门控。列表加载/增删改后刷新；错误走 http 统一 toast（预期内失败用 `skipErrorToast`）。

### 3.1 用户 `/platform/users`

- 表格列：姓名、邮箱、角色（按 role_id 映射 RoleRead.name）、状态（UserStatus）、最后登录、操作。
- 动作：**邀请用户**（dialog：email/name/role → POST `/users/invite`，回 InviteResult 提示邀请已发）；**直接建号**（dialog：email/password/name/role → POST `/users`）；**编辑**（dialog：name/role/status/可选新密码 → PATCH，password 字段=管理员重置密码）；**删除**（确认 → DELETE）。
- 门控：列表 user.view；邀请/建号 user.create；编辑 user.edit；删除 user.delete。无权限按钮隐藏。
- 角色下拉来自 GET `/roles`。

### 3.2 角色 `/platform/roles`

- 表格列：名称、code、类型（is_builtin ? 内置 : 自定义）、权限数、操作。
- 动作：**新建**（dialog：code/name + 权限分域勾选，来自 §2 `GET /permissions` → POST `/roles`）；**编辑**（name + 权限勾选 → PATCH；**内置角色 is_builtin 禁止编辑/删除**，按钮禁用）；**删除**（仅自定义）。
- 门控：列表 role.view；增改删 role.manage。

### 3.3 团队 `/platform/teams`

- 表格列：名称、描述、成员数（member_ids.length）、操作。
- 动作：**新建/编辑**（name/description）；**成员管理**（dialog：多选用户 transfer/select，来自 GET `/users` → PUT `/teams/{id}/members` {user_ids}）；**删除**。
- 门控：列表 team.view；增改删/成员 team.manage。

### 3.4 公司设置 `/platform/settings`

- 表单（非表格）：date_format、timezone、default_currency_code（下拉来自 GET `/currencies`）、auto_assign（开关）。GET 载入 → PUT 保存。
- 门控：读任意登录；保存按钮 COMPANY_SETTINGS（无则只读）。

### 3.5 货币 `/platform/currencies`

- 表格列：code、name、symbol、操作。
- 动作：**新增**（code/name/symbol → POST）；**删除**（DELETE）。**无编辑**（后端不支持）。
- 门控：**super_admin 限定**——菜单项与路由按 `auth.user.role_code === 'super_admin'`（或 hasPermission('currency.manage')）显隐；增删 currency.manage。

## 4. 接线与横切

### 4.1 导航（AppSidebar）

「平台」组：用户/角色/团队/公司设置 四项去 `soon`、加 `path`（`/platform/users` `/platform/roles` `/platform/teams` `/platform/settings`）；**新增「货币」项**（path `/platform/currencies`，按 super_admin 显隐）。`activeMenu` computed 加各 `/platform/*` 分支。

> RBAC 菜单显隐：可选地按 `hasPermission` 过滤组内项（如无 user.view 隐藏「用户」）。本轮最简：平台组对有任一平台权限者可见，货币项额外 super_admin 限定。

### 4.2 路由

`router/index.ts` 加 5 条：`/platform/users|roles|teams|settings|currencies`，组件懒加载 `views/platform/*`，`meta: { title, requiresAuth: true, requiredPermission: <code> }`（requiredPermission 为预留，守卫当前不强制；UI 层 hasPermission 门控为准）。

### 4.3 RBAC 门控

统一用 `auth.hasPermission(code)` 控制增改删按钮（隐藏优先于禁用）；货币模块额外 super_admin 门。无后端守卫变更（后端 require_permission 已是真正闸口；前端门控仅 UX）。

### 4.4 i18n / 文案

沿用现有 zh-CN 用法（与既有 views 一致；不新增 locale、不做多语言）。中文文案直接写（或经现有 i18n，按既有 view 习惯）。

## 5. 测试策略

vitest（项目已配）：
- api 层：各 `api/<x>.ts` 调用路径/参数正确（mock http）。
- 组件：列表渲染、增改删 dialog 提交调用正确 api、RBAC 门控（无权限隐藏按钮）、货币 super_admin 显隐。
- 后端权限目录端点：pytest（ROLE_VIEW 鉴权、分组结构、覆盖 ALL_PERMISSIONS）。
- 门禁：`vue-tsc --noEmit`（typecheck）+ prettier + vitest 绿；后端改动 ruff + mypy + pytest 绿。

## 6. 任务切分（供 plan 细化，~8）

1. **后端权限目录端点** `GET /permissions`（+ 中文 label 映射 + pytest）。
2. **共享前端骨架**：5 个 `api/*.ts` + `types/*` + 5 条路由 + AppSidebar 平台组接线（去 soon/加 path/加货币项/activeMenu）+ `views/platform/` 占位页。
3. **用户** View（列表/邀请/建号/编辑/删除 + 门控）+ 测试。
4. **角色** View（列表/增改删 + 权限分域勾选 + 内置守卫）+ 测试。
5. **团队** View（列表/增改删 + 成员管理）+ 测试。
6. **公司设置** View（表单 GET/PUT）+ 测试。
7. **货币** View（列表/增删 + super_admin 门）+ 测试。
8. **RBAC 门控统一核对 + 收尾**（typecheck/prettier/vitest 全绿，导航/路由联调）。

> T1 后端独立；T2 提供骨架，T3–T7 各子模块依赖 T2；T8 收尾。

## 7. 不在本轮

- 用户/角色/团队的高级项（批量、导入、头像上传等）。
- 路由级权限强制（守卫当前不强制 requiredPermission；后端 require_permission 已是真闸）。
- 响应式/移动端（现有 `min-width:1024px`，本轮不做）。
- 其它前端模块（FE-2 主数据 / FE-5 库存等，另轮）。
