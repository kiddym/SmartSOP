# 程序库 IA 重构（双栏 + 文件夹树）+ 归档系统文件夹 设计

**日期：** 2026-05-26
**状态：** 待批准
**作者：** 协作设计（cui_yuming + Claude）

## 背景与目标

`docs/design-system.md` §3.1 早期 ASCII 中描绘的「侧栏文件夹树（QC 质量 / QA 保证 / 废止）+ 右侧程序列表」此前被标记为「未落地的未来工作」。同日在 [`2026-05-26-topbar-ia-design.md`](2026-05-26-topbar-ia-design.md) R1 修订中以"backend 改动比预想大"为由撤回了"废止入口"延后实施。

本次 brainstorm 发现：

1. **当前 `程序库` 与 `草稿箱` 列表视图设计重复**——两者只差表头标题，没有清晰职能分工。
2. **现有 `ProcedureLibraryView` 默认不带 status 过滤**——`/procedures` 端点返回所有状态，导致 ARCHIVED / DRAFT 行混入"程序库"中。
3. **「废止」是一个 system folder 而非 status**（`folder.system=true AND folder.name='废止'`），技术上 `folder_id` 过滤即可。
4. 「**归档**」概念缺失：用户希望与「废止」**同级、不同语义**的第二个 system folder——"还在保留备查、但不主推使用"，对应一个新的用户主动 `archive` 动作。

综合考虑，**真正合理的落地不是给侧栏加一个废止入口**，而是把 design-system §3.1 早期 ASCII 的设想真正实现：**程序库内部变双栏**，文件夹树（含废止、归档）就是导航；废止入口随之消失，问题自然解决。

**目标：**

1. **程序库变双栏页**：左 FolderTreePane（含废止 + 归档 system folders）+ 右 ListPane（基于选中文件夹筛选）。
2. **新增「归档」system folder + archive 用户动作**（与现有 deprecate / 废止 对称，语义不同：归档=保留备查 / 废止=不再使用）。
3. **程序库 / 草稿箱 职能边界澄清**：程序库 = PUBLISHED + ARCHIVED（按文件夹路由分配）、草稿箱 = DRAFT only（**保持现状不动**）。
4. **进入程序库自动折叠 AppSidebar**——给文件夹树腾空间，沿用现有 `editorFocus.ts` 自动折叠模式。

## 范围

**做：**

- **Backend**：
  - Alembic migration：seed 「归档」system folder（与废止同级、`system=true`、不可删改）。
  - 新增 `POST /procedures/{id}/archive` 端点 + `version_flow_service.archive_group`（镜像现有 `deprecate_group`：整 group 转 ARCHIVED + folder_id 改归档 + 记原 folder）。
  - 现有 `restore` 路径**通用化**：根据当前 folder 决定恢复源（废止 / 归档），返回原 folder 信息逻辑不变。
  - 单元 + 集成测试。
- **Frontend `ProcedureLibraryView.vue`**：重构为双栏布局，集成现有 `FolderTree` 组件（已在 `FolderManageView` / `CreateProcedureDialog` 用过）。
- **Frontend `ProcedureDetailView.vue`**：在现有"废止"按钮旁加"归档"按钮 + 调起对话框（复用 deprecate dialog 模式）；从归档恢复复用现有 restore 流程。
- **Frontend `AppLayout.vue`**：路由进入 `/procedures/library` 时自动折叠 AppSidebar（用户手动展开后接管）。
- **测试**：LibraryView 组件测、DetailView archive 按钮契约测、AppSidebar 自动折叠 watch 行为测、backend service + router 测。
- **文档同步**：design-system §3.1 ASCII 注释更新（"未落地" 标注移除）+ feature-clarifications §50.2 加 R2 修订脚注 + 同步 `2026-05-26-topbar-ia-design.md` R1 旁路说明"已被本 spec 取代"。

**不做（YAGNI）：**

- 跨用户 / 跨设备记忆「上次选中的文件夹」（首次进入 = 默认无选中 = 全库 PUBLISHED 汇总）。
- 文件夹树拖拽排序、批量移动、批量归档/废止。
- 草稿箱也加文件夹树（草稿是按用户编辑流转，文件夹归类对它意义不大）。
- 「归档」状态色（沿用 ARCHIVED 现有 token `--st-archived`）。
- 在 ProcedureTable 中按 status 进一步细分行视觉（PUBLISHED vs ARCHIVED 已有 StatusTag 区分）。
- 撤销「归档」=「取消归档」（用户路径走 restore，跟废止恢复同流程，不引入第三个动作）。

## 设计决策矩阵

| # | 维度 | 决策 | 理由 |
|---|---|---|---|
| Q1 | 默认无选中文件夹时右侧显示什么 | **全库 PUBLISHED + is_current=true 汇总** | 不会"进来却是空的"；用户从全局视角往下钻 |
| Q2 | 「已生效」定义 | **仅 PUBLISHED**（is_current=true） | 用户原话；与现有 `list_library` 端点对齐 |
| Q3 | 点 system folder（废止/归档）右侧 status 切换 | **前端检测 `folder.system` 自动切换 query**（PUBLISHED → ARCHIVED） | 数据自然分布：deprecated/archived 都是 ARCHIVED；用户无需额外操作 |
| Q4 | 搜索范围 | **跨全库**（忽略 folder_id），按 backend `list_procedures` 现有约定 | 已有实现；最直觉，搜出来再点对应文件夹会自动收窄 |
| Q5 | 归档 vs 废止 语义边界 | **归档 = 保留备查 / 废止 = 不再使用**；两者都 ARCHIVED + system folder + 不允许编辑；都支持 restore | 类似 Gmail Archive vs Trash |
| Q6 | restore 端点结构 | **复用现有 `POST /procedures/{id}/restore`**，根据当前 folder 字段（废止 vs 归档）判定来源 | 一个端点处理两种来源，前端不感知 |
| Q7 | 进入程序库 AppSidebar 行为 | **自动折叠 + 用户手动展开后接管** | 沿用 [editor-focus 模式](2026-05-25-collapsible-editor-panels-design.md) |
| Q8 | 草稿箱布局 | **不动** | 现有实现已是 DRAFT-only、单栏简单列表，符合用户意图 |
| Q9 | 旧 `/procedures/deprecated` 路由（topbar-IA spec R1 撤回的 deferred） | **永久 retired**——废止现在通过文件夹树访问，不需要独立路由 | R1 的撤回决策被本 spec 升级为最终决策 |

## 数据模型变更

### `backend/app/seed.py` 扩展（**不引入 Alembic migration**）

现有 `seed.py` 已经在应用启动时幂等地 seed 废止 system folder；归档沿用同一模式：

```python
DEPRECATED_FOLDER_NAME = "废止"
ARCHIVED_FOLDER_NAME = "归档"  # 新增

def seed_system_folders(db: Session) -> None:
    """启动时幂等 seed 两个 system folders。"""
    for name in (DEPRECATED_FOLDER_NAME, ARCHIVED_FOLDER_NAME):
        if _get_root_folder(db, name) is None:
            db.add(Folder(
                id=str(uuid4()),
                name=name,
                prefix="",
                parent_id=None,
                system=True,
                full_path=name,
                sequence_digits=5,
            ))
            db.commit()
            logger.info("seed: created system folder %s", name)
```

> **为何不走 alembic migration**：① seed.py 本身已经是"启动时数据初始化"机制，对应升级路径自然；② Alembic 迁移的 SQL 写法跨 DB（PG / SQLite 测试库）成本高且容易踩坑；③ 旧 DB 启动一次即自动补齐归档 folder，零运维步骤。
>
> **`service` 层**引用 `ARCHIVED_FOLDER_NAME` 常量而非硬编码字符串。

### 数据模型层增量

无新表 / 新字段 / 新外键。**完全复用现有 schema**：
- `procedure.folder_id` 可指向归档 folder（与废止同样机制）
- `procedure.status = ARCHIVED` 涵盖归档 + 废止两种语义；区分由 folder_id 决定
- `version_change_log` 写入 `archive` 操作（与 deprecate 平行）

## 后端 API 新增

### `POST /procedures/{procedure_id}/archive`

**入参**：

```python
class ArchivePayload(BaseModel):
    reason: str  # 必填，记入 version_change_log
```

**出参**：`ProcedureMeta`（与 deprecate 相同）

**行为**：

镜像现有 `version_flow_service.deprecate_group`：

```python
def archive_group(db: Session, procedure_id: str, *, reason: str) -> Procedure:
    proc = _get_procedure(db, procedure_id)
    if proc.folder.system:
        raise bad_request("PROCEDURE_ARCHIVE_SYSTEM_FOLDER", "系统文件夹下的程序不可归档")
    if proc.status == "ARCHIVED":
        raise bad_request("PROCEDURE_ALREADY_ARCHIVED_OR_DEPRECATED", "该程序已归档或已废止")
    archive_folder = _get_root_folder(db, ARCHIVED_FOLDER_NAME)
    assert archive_folder, "归档 system folder 未 seed"

    # 整 group: 所有版本 ARCHIVED + folder_id 改归档 + 记原 folder
    group = _get_group(db, proc.group_id)
    original_folder_id = proc.folder_id
    for version in group:
        version.status = "ARCHIVED"
        version.folder_id = archive_folder.id
        version.deprecated_from_folder_id = original_folder_id  # 复用字段
    _write_change_log(db, proc, "archive", reason=reason, original_folder=original_folder_id)
    db.commit()
    return proc
```

**复用现有 `deprecated_from_folder_id` 字段**作为"原 folder"记录——这字段原本叫 "deprecated_from" 但语义是 "原 folder pre-system-move"，归档也用此字段记录。**字段名不重命名**（成本高、收益低）；新增一个 docstring 说明双用途。

### `POST /procedures/{procedure_id}/restore` 通用化

**当前行为**：从 deprecated_from_folder_id 恢复，新增 DRAFT，原版本保持 ARCHIVED。

**新行为**：**完全不变**——逻辑已经通用，能从废止或归档恢复。只需测试覆盖归档→恢复的路径。

### `bad_request` 错误码新增

- `PROCEDURE_ARCHIVE_SYSTEM_FOLDER` — 试图归档已在系统文件夹下的程序
- `PROCEDURE_ALREADY_ARCHIVED_OR_DEPRECATED` — 试图归档已 ARCHIVED 的程序

## 前端架构

### A. `ProcedureLibraryView.vue` 重构

```
<ProcedureLibraryView>
├── <FolderTreePane>     // 左 ~220px (可拖拽调宽)
│   └── <FolderTree :data="store.tree" @select="onSelectFolder" />
└── <ListPane>           // 右 flex
    ├── 顶部 toolbar：当前文件夹面包屑 / heading + 搜索 + 新建按钮（system folder 时隐藏新建）
    ├── <ProcedureTable :rows="store.rows" :loading="store.loading" @open="open" />
    └── <el-pagination />
```

**关键 state**:

```ts
const selectedFolder = ref<FolderTreeNode | null>(null)  // 树选中态
const query = reactive({
  search: '',
  folder_id: undefined as string | undefined,
  status: 'PUBLISHED' as 'PUBLISHED' | 'ARCHIVED',  // 由 selectedFolder.system 决定
  page: 1,
})

function onSelectFolder(node: FolderTreeNode | null): void {
  selectedFolder.value = node
  query.folder_id = node?.id
  query.status = node?.system ? 'ARCHIVED' : 'PUBLISHED'
  query.page = 1
  void load()
}
```

**默认（无选中）**：`folder_id=undefined, status='PUBLISHED'` → backend list_procedures 自然返回全库 PUBLISHED。

**搜索**：`search` 非空时 backend 自动忽略 folder_id 跨全库（既有逻辑），前端 UI 不需要特别处理。

**Toolbar 新建按钮可见性**：
- 默认（无选中）= **显示**（用户可在"全库视图"下新建，新建对话框自带 folder picker）
- 选中普通文件夹 = **显示**（CreateProcedureDialog 可预填 folder_id）
- 选中 system folder (废止/归档) = **隐藏**（系统文件夹下不允许新建，且有 backend 校验兜底）

判定：`v-show="!selectedFolder?.system"`

### B. `FolderTreePane` 容器（薄封装）

新建 `frontend/src/components/library/FolderTreePane.vue`：

```vue
<script setup lang="ts">
import { onMounted } from 'vue'
import FolderTree from '@/components/FolderTree.vue'
import { useFolderStore } from '@/store/folders'
import type { FolderTreeNode } from '@/types/folder'

defineEmits<{ (e: 'select', node: FolderTreeNode | null): void }>()
const store = useFolderStore()
onMounted(() => { void store.loadTree() })
</script>

<template>
  <div class="folder-tree-pane">
    <header class="pane-header">
      <span class="title">文件夹</span>
    </header>
    <div class="tree-body">
      <FolderTree :data="store.tree" :loading="store.loading" @select="(n) => $emit('select', n)" />
    </div>
  </div>
</template>
```

宽度 220px，固定不可调（YAGNI：本轮不做 splitter）。

### C. AppSidebar 路由进入自动折叠

新建 `frontend/src/utils/sidebarAutoCollapse.ts`（纯函数），单元测：

```ts
/**
 * 决定路由切换时是否需要自动折叠 AppSidebar。
 *
 * - 进入 /procedures/library 时折叠
 * - 离开时恢复原状态
 * - 用户在 library 内手动展开/折叠后，"接管"标志位置位，此后不再自动管
 */
export type CollapseDecision = 'collapse' | 'restore' | 'noop'

export function decideAutoCollapse(
  fromPath: string,
  toPath: string,
  userOverride: boolean
): CollapseDecision {
  const wasLibrary = fromPath.startsWith('/procedures/library')
  const isLibrary = toPath.startsWith('/procedures/library')
  if (userOverride) return 'noop'
  if (!wasLibrary && isLibrary) return 'collapse'
  if (wasLibrary && !isLibrary) return 'restore'
  return 'noop'
}
```

`AppLayout.vue` 接入 watcher：

```ts
const { collapsed, toggle } = useSidebar()
const route = useRoute()
let preEnterCollapsed = collapsed.value
let userOverride = false

// 用户手动 toggle → 标记接管
const stopWatchToggle = watch(collapsed, () => {
  // 仅在 library route 下，用户点击 toggle 视为接管
  if (route.path.startsWith('/procedures/library')) userOverride = true
})

watch(() => route.path, (to, from) => {
  const decision = decideAutoCollapse(from ?? '', to, userOverride)
  if (decision === 'collapse') {
    preEnterCollapsed = collapsed.value
    collapsed.value = true
  } else if (decision === 'restore') {
    collapsed.value = preEnterCollapsed
    userOverride = false  // 离开后清接管标志
  }
}, { immediate: true })
```

### D. `ProcedureDetailView.vue` 新增"归档"按钮

定位与现有"废止"按钮平级。复用现有 `VersionActionDialog.vue` 流程：

```ts
// 新增按钮点击
function startArchive(): void {
  pending.value = { kind: 'archive', needFolder: false }
}

// pendingTitle 计算扩展
type PendingAction =
  | { kind: 'archive'; needFolder: boolean }
  | { kind: 'deprecate'; needFolder: boolean }
  | { kind: 'restore'; needFolder: boolean }
  | ...

function pendingTitle(p: PendingAction | null): DialogConfig | null {
  if (p?.kind === 'archive') return { title: '归档程序', needReason: true, needFolder: false, needName: false, reasonHint: '归档原因' }
  if (p?.kind === 'deprecate') return { title: '废止程序', ... }
  if (p?.kind === 'restore') return { title: '从废止/归档恢复', ... }  // 标题文案微调以涵盖两种来源
  ...
}

// 提交时调 archiveGroup API
async function commitPending(result: VersionActionResult): Promise<void> {
  if (pending.value?.kind === 'archive') {
    await archiveGroup(id.value, { reason: result.reason })
    ElMessage.success('已归档')
    void refresh()
  }
  ...
}
```

新增 API client：

```ts
// frontend/src/api/procedures.ts
export const archiveGroup = async (id: string, payload: { reason: string }): Promise<ProcedureMeta> =>
  (await http.post<ProcedureMeta>(`/procedures/${id}/archive`, payload)).data
```

### E. 路由变更

`frontend/src/router/index.ts`：**保持现状不变**。`/procedures/library` 路由依然指向 `ProcedureLibraryView.vue`——是组件内容重构，不动路由配置。

## 测试

### 后端

`backend/tests/unit/services/test_version_flow_service.py` 扩展：

```python
def test_archive_group_moves_to_archive_folder():
    proc = make_procedure(folder=normal_folder, status="PUBLISHED")
    version_flow_service.archive_group(db, proc.id, reason="过时不再推广")
    assert proc.status == "ARCHIVED"
    assert proc.folder.name == "归档"
    assert proc.deprecated_from_folder_id == normal_folder.id

def test_archive_group_rejects_system_folder():
    proc = make_procedure(folder=deprecate_folder, status="ARCHIVED")
    with pytest.raises(BadRequest, match="PROCEDURE_ARCHIVE_SYSTEM_FOLDER"):
        version_flow_service.archive_group(db, proc.id, reason="-")

def test_archive_group_rejects_already_archived():
    proc = make_procedure(folder=normal_folder, status="ARCHIVED")
    with pytest.raises(BadRequest, match="PROCEDURE_ALREADY_ARCHIVED_OR_DEPRECATED"):
        version_flow_service.archive_group(db, proc.id, reason="-")

def test_restore_from_archive():
    """from-archive 走与 from-deprecate 相同的 restore 代码路径"""
    proc = archive(make_procedure(folder=normal_folder))
    new_draft = version_flow_service.restore(db, proc.id, reason="重新启用")
    assert new_draft.status == "DRAFT"
    assert new_draft.folder.name == normal_folder.name  # 恢复到原 folder

def test_seed_archive_folder_idempotent():
    """重复 migration 不会创建重复"""
    seed.seed_system_folders(db)
    seed.seed_system_folders(db)  # 二次调用
    count = db.query(Folder).filter_by(system=True, name="归档").count()
    assert count == 1
```

`backend/tests/integration/test_procedures.py` 扩展：

```python
def test_archive_endpoint_full_flow(client):
    proc = create_procedure_via_api(folder=normal_folder)
    publish(proc.id)
    res = client.post(f"/procedures/{proc.id}/archive", json={"reason": "stale"})
    assert res.status_code == 200
    assert res.json()["status"] == "ARCHIVED"
    assert res.json()["folder_name"] == "归档"

def test_archive_then_restore_round_trip(client):
    proc = create_procedure_via_api(folder=normal_folder)
    publish(proc.id)
    client.post(f"/procedures/{proc.id}/archive", json={"reason": "stale"})
    res = client.post(f"/procedures/{proc.id}/restore", json={"reason": "back"})
    assert res.status_code == 200
    assert res.json()["folder_id"] == normal_folder.id  # 恢复到原 folder
    assert res.json()["status"] == "DRAFT"
```

### 前端

**`frontend/tests/unit/sidebarAutoCollapse.spec.ts`**（纯函数）：

```ts
describe('decideAutoCollapse', () => {
  it('进入 library 路由折叠', () => {
    expect(decideAutoCollapse('/procedures/drafts', '/procedures/library', false)).toBe('collapse')
  })
  it('离开 library 路由恢复', () => {
    expect(decideAutoCollapse('/procedures/library', '/folders', false)).toBe('restore')
  })
  it('userOverride=true 永远 noop', () => {
    expect(decideAutoCollapse('/procedures/drafts', '/procedures/library', true)).toBe('noop')
  })
  it('在 library 内部跳转不动作', () => {
    expect(decideAutoCollapse('/procedures/library', '/procedures/library', false)).toBe('noop')
  })
  it('library 之外的跳转不动作', () => {
    expect(decideAutoCollapse('/folders', '/settings', false)).toBe('noop')
  })
})
```

**`frontend/tests/unit/ProcedureLibraryView.spec.ts`**（新建）：

1. mount 时 onSelectFolder(null) 默认 query.status='PUBLISHED'、folder_id=undefined
2. onSelectFolder(normalFolder) → query.status='PUBLISHED' + folder_id=normalFolder.id
3. onSelectFolder(systemFolder /* 废止 或 归档 */) → query.status='ARCHIVED' + folder_id=systemFolder.id
4. 新建按钮在 system folder 选中时隐藏
5. 搜索时 folder_id 仍传递（backend 自己忽略），不在前端清空（信任后端约定）

**`frontend/tests/unit/ProcedureDetailView.spec.ts`**（已存在，扩展）：

1. 渲染"归档"按钮
2. 点击 → 派发 `pending = { kind: 'archive', ... }`
3. 对话框 title 为"归档程序"
4. commitPending 调用 `archiveGroup` API（mock）

### 已有测试不需改

- `useSidebar.spec.ts`：composable 不动
- `AppTopBar.spec.ts` / `AppSidebar.spec.ts`：组件契约不变
- `AppLayout.spec.ts`：不存在；watcher 行为通过 `sidebarAutoCollapse.ts` 纯函数测覆盖

## 风险与已知未解

| 项 | 风险 | 缓解 |
|---|---|---|
| 复用 `deprecated_from_folder_id` 给归档恢复 | 字段名误导（"deprecated_from" 在归档场景下读起来怪） | 加 docstring + sqlalchemy `Column.comment`；将来字段重命名作为独立 topic |
| AppSidebar 自动折叠 + `useStorage` 持久化的耦合 | 用户上次主动折叠的状态在跨 session 持续；进入 library 还会再次"折叠"形成无效操作 | `decideAutoCollapse` 在 `collapsed=true` 时返回 'noop'（已经折叠就不重复折）—— 实施时添加守护 |
| FolderTreePane 220px 固定 vs design-system §3.1 描述的 240px | 数字不一致 | 220 是树面板（内层）；240 是 AppSidebar（外层） —— 不同层级，不矛盾 |
| 归档与废止并列后 UI 重复度上升 | 用户混淆"归档"与"废止"该选哪个 | 详情页两个按钮加 tooltip 区分语义（"归档：保留备查" vs "废止：不再使用"） |
| 搜索时 folder_id 被 backend 忽略，但 selectedFolder 仍高亮 | 用户搜索时仍看到选中文件夹，可能误以为是文件夹内搜 | 搜索框 placeholder 写明"跨全库搜索"；右侧 list header 在搜索时改文案"搜索结果：N 项" |
| 旧 spec `2026-05-26-topbar-ia-design.md` R1 撤回的废止入口 | 历史记录不清晰 | 本 spec 在引用段标注"取代 R1 撤回决策" |

## 引用

- [`docs/design-system.md`](../../design-system.md) §3.1（外壳）/ §3.2（侧栏/文件夹树）
- [`docs/feature-clarifications.md`](../../feature-clarifications.md) §13（deprecate/restore 数据流）/ §50（IA 归位 Q321）
- [`docs/superpowers/specs/2026-05-26-topbar-ia-design.md`](2026-05-26-topbar-ia-design.md) R1 修订——废止入口被本 spec 永久取代
- [`docs/superpowers/specs/2026-05-25-collapsible-editor-panels-design.md`](2026-05-25-collapsible-editor-panels-design.md) —— sidebar auto-collapse 模式（沿用 `editorFocus.ts` 思路）
- 内存提示：`[[el-dropdown jsdom test]]`（dropdown 测试规避坑）

## 文档同步任务

实施期间还需 sync：

- **design-system.md §3.1** ASCII 中的 "▸ QC 质量 ▸ QA 保证" 树状结构旁的"术语演变 (2026-05-26)"注释——将"未落地"段落改为"已实现于 ProcedureLibraryView 双栏布局，见 [`2026-05-26-library-ia-archive-folder-design.md`]"
- **feature-clarifications.md §50.2** 加 R2 修订脚注："2026-05-26 R2：'废止'入口实现路径再次修订——从'独立路由 + 侧栏系统区'最终回归 design-system §3.1 原设想：内嵌于程序库 FolderTreePane 双栏视图；新增'归档' system folder 与之同级"
- **`2026-05-26-topbar-ia-design.md`** 在 R1 修订段附"——本 R1 决策被 [`2026-05-26-library-ia-archive-folder-design.md`] 永久取代"

## 修订日志

（初版，无修订）
