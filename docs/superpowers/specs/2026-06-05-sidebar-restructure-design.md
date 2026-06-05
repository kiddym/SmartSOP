# 侧边栏重构设计（方案 B）

日期：2026-06-05
状态：已与用户确认，待出实现计划

## 1. 背景与目标

当前侧边栏（`frontend/src/components/AppSidebar.vue`）为 6 分组、27 项的扁平两级结构。
地基（分组标签、陶土橙选中竖条、折叠态、feature/permission/role 三层门控）良好，问题集中在
**归类心智模型**与**命名一致性**：

- 审计日志错置于 SOP 组（实为全局系统日志）。
- 客户错置于「供应」组（营收/服务侧实体，与供货语义冲突）。
- 资产 / 位置（路由 `/maindata/*`，本质主数据）埋在「维护」组，资产主线不突出。
- 通知中心置于「洞察」组，但顶栏已有 `NotificationBell`（`AppTopBar.vue:65`），属重复入口。
- 「平台」与「设置」两组职责重叠（公司设置 vs 系统设置、货币/字段/字典分散），用户二选一困惑。
- 备件库存与多备件套件共用 `Goods` 图标，折叠态无法区分；多备件套件占一级槽位偏重。

目标：重排分组与命名对齐用户心智，合并配置类入口，下沉次级功能，统一错配的路由前缀。

## 2. 目标侧栏结构

```
SOP
 ├ 程序库          /procedures/library      （不变）
 ├ 草稿箱          /procedures/drafts       （不变）
 └ 文件夹          /procedures/folders      （原 /folders，重定向）

维护
 ├ 工单            /maintenance/work-orders （不变）
 ├ 请求            /maintenance/requests    （不变）
 ├ 预防性维护       /maintenance/preventive-maintenances （不变）
 ├ 计量            /maintenance/meters      （不变）
 └ 客户            /maintenance/customers   （原 /inventory/customers，重定向）

资产                                        （原属「维护」，独立成组）
 ├ 资产            /assets                  （原 /maindata/assets，重定向）
 └ 位置            /assets/locations        （原 /maindata/locations，重定向）

库存采购                                     （原「供应」更名）
 ├ 备件库存         /inventory/parts         （页内 Tab：备件 | 多备件套件）
 ├ 采购单          /inventory/purchase-orders （不变）
 └ 供应商          /inventory/vendors       （不变）

分析                                        （原「洞察」更名，去通知中心）
 └ 分析仪表盘       /analytics               （不变）

管理                                        （合并「平台」+「设置」+审计日志，可折叠子菜单）
 ├ 人员与权限：用户 /admin/users · 角色 /admin/roles · 团队 /admin/teams
 ├ 组织配置：  公司设置 /admin/company · 货币 /admin/currencies
 ├ 系统配置：  系统设置 /admin/settings · 字段管理 /admin/fields · 标题字典 /admin/heading-rules
 └ 审计：      审计日志 /admin/audit-logs
```

- 通知中心：从侧栏移除，仅保留顶栏铃铛。
- 多备件套件：下沉为备件库存页内 `el-tabs` 路由 Tab（`/inventory/parts` / `/inventory/parts/kits`）。
- 一级菜单项 27 → 约 22；分组 6 → 6（语义全部对齐）。

### 门控保持不变

- feature gate：`sop`（程序库/草稿箱/文件夹）、`preventive_maintenance`、`meters`、`purchasing`（采购单）、`analytics`。
- permission gate：分析仪表盘 `analytics.view`（无权限隐藏）。
- role gate：货币仅 `super_admin` 可见。
迁移后这些门控逻辑原样保留，仅菜单项所属分组/路径变化。

## 3. 路由前缀统一（务实范围）

原则：每个侧栏分组对齐一个 URL 前缀；**只动错配前缀，保留语义本就正确的 `/procedures/*`**。

| 项 | 旧路径 | 新路径 | 处理 |
|---|---|---|---|
| 文件夹 | `/folders` | `/procedures/folders` | 新路径 + 旧路径 redirect |
| 资产 | `/maindata/assets` | `/assets` | 新路径 + 旧路径 redirect |
| 位置 | `/maindata/locations` | `/assets/locations` | 新路径 + 旧路径 redirect |
| 多备件套件 | `/inventory/multi-parts` | `/inventory/parts/kits` | 新路径（Tab）+ 旧路径 redirect |
| 客户 | `/inventory/customers` | `/maintenance/customers` | 新路径 + 旧路径 redirect |
| 用户 | `/platform/users` | `/admin/users` | 新路径 + 旧路径 redirect |
| 角色 | `/platform/roles` | `/admin/roles` | 新路径 + 旧路径 redirect |
| 团队 | `/platform/teams` | `/admin/teams` | 新路径 + 旧路径 redirect |
| 公司设置 | `/platform/settings` | `/admin/company` | 新路径 + 旧路径 redirect |
| 货币 | `/platform/currencies` | `/admin/currencies` | 新路径 + 旧路径 redirect |
| 系统设置 | `/settings` | `/admin/settings` | 新路径 + 旧路径 redirect |
| 字段管理 | `/settings/fields` | `/admin/fields` | 新路径 + 旧路径 redirect |
| 标题字典 | `/settings/heading-rules` | `/admin/heading-rules` | 新路径 + 旧路径 redirect |
| 审计日志 | `/audit-logs` | `/admin/audit-logs` | 新路径 + 旧路径 redirect |

不变：`/procedures/library`、`/procedures/drafts`、`/maintenance/work-orders|requests|preventive-maintenances|meters`、
`/inventory/parts|purchase-orders|vendors`、`/analytics`。

默认首页重定向 `/` → `/procedures/library` 保持不变。

## 4. 组件改动

### 4.1 AppSidebar.vue

- `groups` 数据按第 2 节重排：新增「资产」组、「供应」→「库存采购」、「洞察」→「分析」、移除通知中心、客户移入维护。
- 「管理」组改用 `el-sub-menu` 折叠分组承载 4 个子分组（人员与权限/组织配置/系统配置/审计），
  与现有 `el-menu-item` 平铺项混排。需处理：
  - 折叠态（`collapsed`）下子菜单的图标显示与弹出行为。
  - 选中态竖条/底色样式适配到子菜单项（现有 `.is-active::before` 规则需覆盖 sub-menu 内项）。
- `activeMenu` 路由匹配逻辑按新前缀全量重写（`/admin/*`、`/assets/*`、`/maintenance/customers`、
  `/inventory/parts/kits` 归到 `/inventory/parts` 等）。
- 图标：保留各项现有图标；备件库存内 Tab 取代多备件套件独立项后，`Goods` 图标重复问题自然消除。

### 4.2 router/index.ts

- 所有变更项改为新路径；为每个旧路径登记 `redirect` 路由保证兼容（任何遗漏内链不至 404）。
- 多备件套件路由改为备件库存的子路由 / Tab 路由（`/inventory/parts/kits`）。

### 4.3 PartsView.vue

- 顶部加 `el-tabs`，两标签「备件库存」「多备件套件」，分别承载 `PartsView` 现内容与 `MultiPartsView`。
- 采用路由驱动 Tab（`/inventory/parts` ↔ `/inventory/parts/kits`），切换更新 URL，刷新保持。
- `MultiPartsView.vue` 复用为 Tab 内容组件，不重写其内部逻辑。

### 4.4 内部跳转链接与测试

- 全库 grep `router-link` / `router.push` / `to=` 指向变更路径处，改为新路径（redirect 仅作兜底，不留旧链接）。
- 更新测试中硬编码的旧路径断言；前端基线 781 测试须保持全绿。

## 5. 实现策略与风险

- **渐进兜底**：先落地新路径 + 全量 redirect，保证不破；再批量替换内链；最后跑回归。
- **最大风险点**：路由统一改动面广（router + 全库内链 + 测试）。需以 grep 清单逐一核对。
- **验证**：
  - 单测/类型/lint 全绿（`npm run test`、`typecheck`、`lint`）。
  - dev 实测（参照 running-smartsop-dev）：暗色下子菜单折叠/展开、选中态竖条、各项导航、
    备件库存 Tab 切换、旧链接 redirect、顶栏铃铛仍为唯一通知入口。
- **范围外**：SOP 的 `/procedures/*` 不改为 `/sop/*`（语义已正确，避免无谓大改与风险）。

## 6. 决策记录（与用户确认）

1. 通知中心 → 从侧栏移除（顶栏铃铛已是入口）。
2. 多备件套件 → 下沉为备件库存页内 Tab。
3. 客户 → 并入维护线（`/maintenance/customers`）。
4. 路由前缀 → 统一并加重定向，收敛为「只改错配前缀、保留 /procedures」。
5. 管理组 → 4 个可折叠子菜单分组。
