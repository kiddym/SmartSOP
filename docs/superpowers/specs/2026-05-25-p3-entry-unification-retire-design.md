# P3 · 入口统一与下线 设计

**日期：** 2026-05-25
**状态：** 已批准
**作者：** 协作设计（cui_yuming + Claude）
**上位文档：** `2026-05-25-unified-create-edit-model-overview-design.md`（北极星）。P3 是统一模型的收尾。

---

## 1. 背景与范围

P1/P2 已让程序编辑器成为编辑导入程序的唯一场所（预览栏、待确认 triage、批量层级标定）。P3 收尾：把创建入口统一为"新建（空白 / 从 Word）"且都进编辑器；下线老导入向导与 beta2 重对话框；把被编辑器复用的共享组件迁出 import-v2；直接切换、不留 flag（未发布）。

**范围：**
1. 统一"新建"入口（空白 / 从 Word），两者都进编辑器。
2. "从 Word" 瘦身为轻对话框（文件 + 文件夹 → upload/parse/import → 进编辑器）。
3. 修 blank-create 误跳详情页 → 跳 `/edit`。
4. 迁移 3 个共享组件到 `components/shared/`。
5. 彻底删除老向导 + beta2 重对话框及其专用文件/测试；移除对应路由。

**非目标：** 后端任何改动（链路已就绪）；新增 triage 能力（已在编辑器）；灰度/feature flag。

## 2. 关键现状（探查确认）

- `ProcedureLibraryView.vue` 三个入口：「从 Word 导入」→ `/procedures/import`（老向导 `ImportWizardView`）；「导入 v2 (Beta)」→ `/procedures/import-v2`（`ImportDialogView`→`ImportDialog`）；「新建程序」→ `CreateProcedureDialog`，**created 后跳 `/procedures/{id}`（详情）**。
- 后端链 `POST /uploads → /parse → /procedures/import` 就绪；`import` 建 DRAFT、带 review（P2a）、存 docx（需传 `upload_token`）。`importProcedure` 入参：`{name, folder_id, description?, upload_token?, chapters}`。
- 编辑器复用：`WordPreviewPanel`、`ImportSideRail`、`ImportMarkingRow`（均在 `components/import-v2/`）。`ImportMarkingRow` 从 `@/utils/importTree` 取 `LayerRole` 类型。
- 无 feature flag；`main` 领先 `origin/main`（未发布）。
- 已有 `ProcedureDraftsView`（草稿列表）；P1 已让"纯草稿(v1 DRAFT)"可删（后端）。

## 3. 决定

### D1 · 统一"新建"入口
- `ProcedureLibraryView` 用**一个「新建」下拉**（或小选择）取代现三按钮：菜单项「空白程序」「从 Word 导入」。
- 「空白程序」→ 现有 `CreateProcedureDialog`（名称 + 文件夹）→ 创建 → **进编辑器 `/procedures/{id}/edit`**（修正现跳详情的 bug）。
- 「从 Word 导入」→ 新轻对话框（D2）。

### D2 · "从 Word" 轻对话框
- 新建 `CreateFromWordDialog.vue`：字段 = `.docx` 文件 + 目标文件夹（叶子文件夹下拉，复用 `collectLeafFolders(fetchFolderTree())`）+ 名称（默认取文件名去 `.docx`，可改）。
- 提交：`uploadDocx(file)` → `parseDocx(token, 'smart')` → `importProcedure({name, folder_id, upload_token: token, chapters: parsed.chapters})` → 成功跳 `/procedures/{id}/edit`。
- 进度态（上传中 / 解析中 / 创建中）；解析/校验失败（如 `PARSE_NO_HEADINGS`）由拦截器提示、对话框保持打开可重试；**无任何 triage**（树/标定/详情全在编辑器）。
- import 现已带 review、不拦截（P2a），故含待确认的解析也能直接建草稿。

### D3 · 迁移共享组件
- 把 `WordPreviewPanel.vue`、`ImportSideRail.vue`、`ImportMarkingRow.vue` 从 `components/import-v2/` 迁到 **`components/shared/`**。
- 更新引用：`EditorPreviewPane.vue`、`EditorLayerMarking.vue`（及其测试的 import 路径）；以及这 3 个组件各自的测试文件路径。
- `ImportMarkingRow` 的 `LayerRole` 改从 `@/utils/layerMark` 取（与 importTree 解耦），便于 importTree 视情况删除。

### D4 · 彻底下线（直接切换）
**删除（含各自测试）：**
- 老向导：`views/procedures/ImportWizardView.vue` + `components/import/*`（UploadStep/ModeStep/ReviewReportStep/BlockMarkingStep/TreeReviewStep/ImportFormStep/ImportTreeNode 等）+ `composables/useImportWizardPersistence.ts` + `utils/importBlocks.ts`。
- beta2 对话框：`views/procedures/ImportDialogView.vue` + `components/import-v2/ImportDialog.vue` + import-v2 仅 beta2 用组件（`ImportTreePanel`/`ImportDetailPanel`/`ImportTreeRow`/`ChapterDetailCard`/`ContentDetailCard`/`StepAnnotationCard`）+ `composables/useImportDialog.ts` + `utils/importCols.ts`。
- 路由：移除 `procedure-import`、`procedure-import-v2`。
- `utils/importTree.ts`：迁移 `LayerRole` 解耦后，若 grep 确认仅被已删代码引用 → 一并删除其与 `importTreeOps`/`importTree` 测试；若仍被保留代码引用则保留被用部分。
- **实现者须 grep 确认每个删除目标无残留引用后再删；删后全量 Gate 必须绿。**

## 4. 数据流（新）

```
程序列表 ─「新建」┬─ 空白 → CreateProcedureDialog（名+夹）→ 建 DRAFT → /procedures/{id}/edit
                  └─ 从 Word → CreateFromWordDialog（文件+夹）
                                → upload → parse → import(建 DRAFT, 带 review, 存 docx)
                                → /procedures/{id}/edit
                                          │
                                    编辑器：预览栏 + 待确认 triage + 层级标定 + 编辑 → 完成(发布)
```

## 5. 边界与错误

- **解析失败**（无标题/非法 docx）：对话框保持打开、提示、可换文件重试；不创建程序。
- **无叶子文件夹**：文件夹下拉为空 → 提示先建文件夹（沿用现有校验风格）。
- **旧书签** `/procedures/import`、`/procedures/import-v2`：路由移除后 404（未发布，可接受）。
- **草稿清理（P1 决定 C）**：`ProcedureDraftsView` 已有草稿列表；纯草稿(v1 DRAFT)后端已可删 → 验证草稿列表的删除入口能删纯草稿（若缺，补一个删除动作；属小尾巴，不扩大范围）。

## 6. 测试

- 新 `CreateFromWordDialog.spec.ts`：mock api（upload/parse/import），提交后按序调用并 emit/跳转到 `/edit`；解析失败不跳转。
- 统一入口：`ProcedureLibraryView` 的「新建」菜单两项 → 分别开对应对话框；blank-create created → 跳 `/edit`（更新/新增断言）。
- 迁移：3 个共享组件测试改路径后仍绿；编辑器组件（`EditorPreviewPane`/`EditorLayerMarking`）引用更新后仍绿。
- 删除：移除的测试文件随源码删；删后 `npm run lint && typecheck && test && build` 全绿（无悬挂引用）。
- 后端无改动；`backend` 测试不应受影响（`/procedures/import` 等仍在）。

## 7. 文件清单（预估）

**新增：** `components/procedures/CreateFromWordDialog.vue`（或与 `CreateProcedureDialog` 同目录）+ 测试。
**迁移：** `components/import-v2/{WordPreviewPanel,ImportSideRail,ImportMarkingRow}.vue` → `components/shared/`（+ 测试路径）。
**改：** `ProcedureLibraryView.vue`（统一「新建」+ blank-create 跳 /edit）；`EditorPreviewPane.vue`/`EditorLayerMarking.vue`（import 路径）；`ImportMarkingRow.vue`（LayerRole 改 layerMark）；`router/index.ts`（删两路由）。
**删：** 见 D4。

## 8. 收尾与回顾

- P3 完成即统一模型全部落地：一个编辑器、一个创建心智（空白/从 Word 都进编辑器）、源 docx 可追溯、待确认与层级标定皆在编辑器、旧双导入路径下线、共享组件归位。
- 直接切换、未发布、无 flag；最终双 Gate 全绿。
