# MultiPart 多备件套件前端 设计

> 后端「多备件套件」(MultiPart) 已就绪——`tb_multi_part`(custom_id `KIT-xxx` 自动生成 + name + description) + `tb_multi_part_item` 关联表(纯分组,无库存/无消耗),5 个 CRUD 端点复用 `PART_*` 权限、TenantMixin 隔离。但**前端零对接**(`frontend/src` 无 multiParts.ts、无 `/inventory/multi-parts` 路由、侧栏无入口)。本轮做纯前端 CRUD 把它接出来。属 [[atlas-parity-backfill]] 前端缺位项(优先级中低)。

## 范围与已确认决策

- **纯前端 CRUD**,后端零改动(所有端点已就绪)。
- **复刻 `PartsView` 单视图模式**:列表 el-table + 创建/编辑 el-dialog,无独立详情页。
- **成员选择控件**:`el-select multiple filterable`(选项来自 `listPartsMini`)。
- **列表成员展示**:列显示成员数「N 项」+ el-table **可展开行**(展开渲染成员清单 `custom_id + name`)。
- **空成员套件**:后端 `part_ids` 允许为空,前端**不强制**至少一个成员(跟随后端),留空正常提交。
- **侧栏文案**:「多备件套件」,挂「供应」组(`备件库存` 之后)。

## 后端契约(已就绪,前端对齐,不改)

裸数组 + PATCH + 204,与既有 `parts` 完全同构:

| 方法 | 路径 | 用途 | 权限 | 返回 |
|---|---|---|---|---|
| GET | `/api/v1/multi-parts` | 列表 | `PART_VIEW` | `MultiPartRead[]`(裸数组,无分页) |
| POST | `/api/v1/multi-parts` | 新建 | `PART_CREATE` | 201 `MultiPartRead` |
| GET | `/api/v1/multi-parts/{id}` | 详情 | `PART_VIEW` | `MultiPartRead` |
| PATCH | `/api/v1/multi-parts/{id}` | 更新(成员全量替换) | `PART_EDIT` | `MultiPartRead` |
| DELETE | `/api/v1/multi-parts/{id}` | 软删 | `PART_DELETE` | 204 |

- `MultiPartRead`:`{ id, custom_id, name, description, part_ids: string[] }`(`part_ids` 由 router 层填充)。
- `MultiPartCreate`:`{ name, description?, part_ids: string[] }`。
- `MultiPartUpdate`:`{ name?, description?, part_ids? }`(`part_ids` 给出即**全量替换**成员,无增量)。
- 跨租户由 TenantMixin 自动隔离;他租户 / 不存在 → 404。

## 既有代码事实(已核实,直接用)

- `src/api/parts.ts` 风格:`http.get<T[]>('/parts',{params}).then(r=>r.data)`、`http.post`、`http.patch`(**注意是 PATCH 非 PUT**)、`http.delete(...).then(()=>undefined)`;`listPartsMini()` → `PartMini[]`(`{id,name,custom_id}`)。
- `src/types/inventory.ts`:已有 `PartMini`、`PartRead/Create/Update` 等;MultiPart 类型追加于此文件。
- `src/views/inventory/PartsView.vue`:列表 + 对话框(`dialogVisible` / `dialogMode:'create'|'edit'`)单视图;按钮级权限 `auth.hasPermission('part.create'|'part.edit'|'part.delete')`;删除前 `ElMessageBox` 确认;`onMounted` 并行加载关联下拉。
- `src/router/index.ts`:库存路由集中在 `/inventory/*`(parts 在 140-145)。已核实 `/inventory/parts` 的 meta = `{ title, requiresAuth:true, requiredPermission:'part.view' }`(`requiredPermission` 为预留字段,当前守卫不强制但按约定填)。MultiPart 路由照此填 `requiredPermission:'part.view'`。
- `src/components/AppSidebar.vue`:「供应」组,`{ label:'备件库存', path:'/inventory/parts', icon: Goods }`。MultiPart 项加在其后,复用 `Goods` 类图标(实现时选一个已 import 的合适图标,如 `Goods`/`Box`)。

## 组件与改动

### 1. 类型 `src/types/inventory.ts`(追加)

```typescript
export interface MultiPartRead {
  id: string
  custom_id: string
  name: string
  description: string
  part_ids: string[]
}
export interface MultiPartCreate {
  name: string
  description?: string
  part_ids: string[]
}
export type MultiPartUpdate = Partial<MultiPartCreate>
```

### 2. API 客户端 `src/api/multiParts.ts`(新建,复刻 parts.ts)

`listMultiParts()` → `MultiPartRead[]`;`getMultiPart(id)`;`createMultiPart(p)`;`updateMultiPart(id,p)`(PATCH);`deleteMultiPart(id)`(then undefined)。

### 3. 视图 `src/views/inventory/MultiPartsView.vue`(新建)

- 工具栏:「新建套件」按钮(`part.create` 门控)。
- el-table:列 `custom_id`、名称、描述、**成员数**(`row.part_ids.length` → 「N 项」)、操作(编辑 `part.edit` / 删除 `part.delete`)。
- **可展开行**(`type="expand"`):展开渲染该套件成员清单——用 `partsMini` 的 `id → {custom_id,name}` 映射把 `part_ids` 渲成 `custom_id + name` 列表;映射缺失的成员(Part 已软删)显示占位「(已删除)」;空成员显示「(无成员)」。
- 创建/编辑 el-dialog:`name`(必填)、`description`、`part_ids`(`el-select multiple filterable`,选项 = `partsMini`,label 显示 `custom_id name`)。提交整列表(全量替换语义)。
- 数据加载:`onMounted` 并行 `listMultiParts()` + `listPartsMini()`(既供下拉选项,又建成员映射)。增删改后刷新列表。

### 4. 路由 `src/router/index.ts`(改)

加 `{ path:'/inventory/multi-parts', name:'inventory-multi-parts', component: () => import('@/views/inventory/MultiPartsView.vue'), meta:{ title:'多备件套件', requiresAuth:true, requiredPermission:'part.view' } }`(紧邻 `/inventory/parts` 之后)。

### 5. 侧栏 `src/components/AppSidebar.vue`(改)

「供应」组 `备件库存` 之后加 `{ label:'多备件套件', path:'/inventory/multi-parts', icon: Goods }`。

## 测试策略(Vitest)

`tests/unit/views/MultiPartsView.spec.ts`(mock `@/api/multiParts` + `@/api/parts` 的 `listPartsMini`;`@/store/auth` 给全权限或按用例门控):
- 挂载并行加载 → 渲染套件列表(custom_id/name/成员数)。
- 展开行用 partsMini 映射渲染成员名称(含「已删除」占位用例)。
- 新建:填 name + 选 part_ids → 提交调用 `createMultiPart({name,part_ids})` → 刷新。
- 编辑:打开回填 name/description/part_ids → 改 → 提交 `updateMultiPart(id, ...)`。
- 删除:确认后调用 `deleteMultiPart(id)`(`ElMessageBox` mock 为 resolve)。
- 权限门控:无 `part.create` 时新建按钮不渲染(按用例)。
- 空成员套件:part_ids 留空可提交(不阻塞)。

门禁:`cd frontend && npm run test && npm run typecheck && npm run lint`(--max-warnings 0)。

## 边界与非目标

- 不做独立详情页(复刻 Part 单视图)。
- 不做成员增量编辑(全量替换,跟随后端)。
- 不做套件自身库存/消耗(后端无此概念,MultiPart 纯分组)。
- 不做套件→工单引用 / 套件批量消耗(后端未提供端点,超范围)。
- 后端零改动、无迁移。

## 净室红线

全新原创,不复制任何第三方(尤其 Atlas)的代码/命名/文案。见 [[cmms-clean-room-baseline]]。

## 验收标准

- 侧栏「供应」组出现「多备件套件」可达项 → `/inventory/multi-parts`。
- 列表显示套件 custom_id/名称/描述/成员数,可展开行查看成员清单(含已删成员占位)。
- 新建/编辑对话框可设 name/description + 多选 filterable 选成员并保存(全量替换);删除有确认。
- 按钮级权限门控正确(create/edit/delete);空成员套件可提交。
- 前端 `npm run test`/`typecheck`/`lint(--max-warnings 0)` 全绿;无回归。
- 净室红线不破。
