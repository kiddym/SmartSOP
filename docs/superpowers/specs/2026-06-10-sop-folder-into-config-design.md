# SOP 文件夹管理移入配置中心 — 设计文档

- 日期:2026-06-10
- 类型:前端信息架构(IA)重构,纯前端,无后端/数据模型改动
- 状态:已批准,待写实现计划

## 背景与动机

SOP「文件夹管理」(`FolderManageView`,路由 `/procedures/folders`)当前挂在侧栏 **SOP 一级分组**下,与「程序库」「草稿箱」并列。但它的职责是**租户级全局配置**:管理 SOP 分类目录树结构、设置编码前缀(prefix)与编号位数(sequence_digits),系统文件夹不可改不可删。

这是典型的「管理员配一次、日常很少动」的元配置,与日常生产入口(程序库、草稿箱)在频率与角色上错配。同时,配置中心的「SOP 配置」聚合页(`/admin/config/sop`)已经收纳了同类元配置——「程序字段」「标题字典」。文件夹规则与它们是同一层抽象(都定义「SOP 如何被组织/校验」),理应并列。

本次改动是 2026-06-09 那波「侧栏管理组收敛为单一配置中心」(commit `f7fb24f`)逻辑下漏扫的尾项。

## 关键区分(避免误解影响范围)

程序库左侧已内置 **`FolderTreePane`**(`ProcedureLibraryView.vue:82`),它与被移动的 `FolderManageView` 是**两个独立组件**:

| 组件 | 位置 | 职责 | 本次改动 |
|---|---|---|---|
| `FolderTreePane` | 程序库左侧 | **只读**:点文件夹 → 筛选该目录下的 SOP | **不动** |
| `FolderManageView` | (待移动) | **管理**:新建/重命名/移动/删除目录、设前缀编码 | 移入配置中心 |

两者仅共用底层 `FolderTree` 渲染组件与 `useFolderStore`,职责不同。因此本次改动后,**程序库左侧文件夹树照常显示,运营用户看树/按目录筛选 SOP 完全不受影响**;被收走的只是「增删改目录结构」这一低频管理动作。

## 设计决策

### 1. 落点:作为「SOP 配置」聚合页的第三个 tab
`SopConfigView` 当前有「程序字段」「标题字典」两个 tab。新增「文件夹」tab,内嵌现有 `FolderManageView`,与现有两个 tab 的 `lazy` 加载模式一致。tab 的 `name` 用 `folders`。

### 2. 不新增快捷入口(已与用户确认)
不在程序库工具栏或 `FolderTreePane` 头部新增「管理文件夹」入口。理由:
- 日常高频需求是「看树/按目录找 SOP」,这一直由 `FolderTreePane` 满足,不受影响。
- 「改目录结构」是低频管理操作,绕到配置中心是合理的,符合 YAGNI(与「货币」「审计日志」进配置中心同理)。
- 若日后运营反馈「改目录太绕」,在 `FolderTreePane` 头部加齿轮成本极低,届时再加。

### 3. 门控维持现状,不新增
现有路由门控统一为 `requiresAuth: true`,无逐权限 gate;`config-sop` 路由(`SopConfigView`)同样如此。文件夹管理移入后门控自然一致,**无需新增权限校验**。后端 `/folders` API 的权限边界保持不变。

### 4. 内嵌视图保留自带标题
现有 tab 内嵌视图 `FieldManageView`(`:262 <h2 class="page-title">字段管理</h2>`)、`HeadingRulesView`(`:212 <h2 class="page-title">标题字典</h2>`)均**保留自带 `<h2>` 标题**。因此 `FolderManageView` 嵌入时同样保留其 `<h2>文件夹配置</h2>` 标题栏即可,与现有模式一致,无需改其内部模板。

## 改动清单(4 处,纯前端)

### ① `frontend/src/views/admin/config/SopConfigView.vue`
新增第三个 tab:
```
[程序字段 fields] [标题字典 heading-rules] [文件夹 folders]   ← 新增
```
- import `FolderManageView`
- 新增 `<el-tab-pane label="文件夹" name="folders" lazy><FolderManageView /></el-tab-pane>`

### ② `frontend/src/components/AppSidebar.vue:151`
删除 SOP 分组下的「文件夹」叶子项:
```
{ label: '文件夹', path: '/procedures/folders', feature: 'sop', icon: Folder },   ← 删除
```
SOP 分组收敛为「程序库 / 草稿箱」两项。若 `Folder` 图标 import 在删除后无其他引用,一并移除以免 lint 报未使用。

### ③ `frontend/src/router/routes.ts`
旧路径改为重定向到新 tab(与 `:158-164` 那批 `/admin/fields`、`/admin/heading-rules` 重定向对称):
- `/procedures/folders`(原 74-78 行,组件路由)→ 改为 `{ path: '/procedures/folders', redirect: { path: '/admin/config/sop', query: { tab: 'folders' } } }`
- `/folders`(79 行,原 `redirect: '/procedures/folders'`)→ 直接改指 `{ path: '/admin/config/sop', query: { tab: 'folders' } }`,避免链式二跳

### ④ `frontend/src/views/admin/config/ConfigConsoleView.vue:25`(可选润色)
SOP 配置 Hub 卡片现为 `{ label: 'SOP 配置', to: '/admin/config/sop' }`。若其他卡片无子标题描述,保持一致、不改;若决定点明子功能,可在卡片描述中含「文件夹」。**默认 skip,保持与其他卡片一致**。

## 明确不动

- `FolderTreePane`(程序库左侧只读筛选树)
- `FolderManageView` 的功能逻辑与内部模板
- `frontend/src/api/folders.ts`、`frontend/src/store/folders`、`frontend/src/types/folder.ts`
- 后端 `/folders` 相关一切(路由/服务/模型/迁移)

## 测试

1. **`redirects.spec`**(沿用 `NEW_PATHS` 模式,即 commit `8d57242` 做法):新增断言
   - `/procedures/folders` → 解析到 `/admin/config/sop?tab=folders`
   - `/folders` → 解析到 `/admin/config/sop?tab=folders`
   - 同时从该 spec 既有「旧字段路径已转 redirect」清单中移除 `/procedures/folders` 的「仍为独立页」假设(若存在)
2. **侧栏单测/快照**(若存在):断言 SOP 分组 entries 不再含 `/procedures/folders`
3. **`SopConfigView` 组件测试**:断言渲染出 `name="folders"` 的 tab 且内嵌 `FolderManageView`
4. **回归**:`FolderManageView` 既有测试(若有)在新挂载位置下仍绿;程序库 `FolderTreePane` 筛选行为不受影响

## 验收标准

- 侧栏 SOP 分组仅剩「程序库」「草稿箱」
- 配置中心 → SOP 配置 出现「文件夹」tab,功能(新建/重命名/移动/删除/前缀编码)与原页面完全一致
- 访问旧地址 `/procedures/folders`、`/folders` 自动跳转到 `/admin/config/sop?tab=folders`
- 程序库左侧文件夹树照常显示、筛选正常
- 前端 typecheck / lint / 单测全绿
