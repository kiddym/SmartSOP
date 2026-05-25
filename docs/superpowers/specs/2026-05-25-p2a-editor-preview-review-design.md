# P2a · 编辑器基座（Word 预览栏 + 携带 review）设计

**日期：** 2026-05-25
**状态：** 已批准
**作者：** 协作设计（cui_yuming + Claude）
**上位文档：** `2026-05-25-unified-create-edit-model-overview-design.md`（北极星）；P2 拆为 P2a/P2b/P2c，本文是 **P2a**。

---

## 1. 背景与范围

P1 已让导入永久存原始 docx 并提供 `GET /procedures/{id}/source-docx`。P2 让程序编辑器成为编辑导入程序的唯一场所；P2a 是其低风险基座：

1. **导入把 review 带进 draft**（当前导入会拦截 review 且把节点全设 unmarked）。
2. **编辑器内嵌可折叠 Word 原文预览栏**（取 source-docx 渲染）。
3. **编辑器只读暴露 review 状态**（徽标 + 计数；接受/清除的交互留 P2b）。

**非目标（→ 后续）：** 待确认的接受/清除交互与"完成"拦截（P2b）；5 选项层级标定（P2c）；step/content 标记透传与置信度/降型藏存 schema（P2c）。

## 2. 关键现状（探查确认）

- 数据管道**已能携带** `mark_status='review'`：`ChapterTreeNode`/`ChapterOut`/`EditorChapter.mark_status` 都含 `'review'`。缺口只在**导入端**。
- `import_service._create_node` 把所有节点硬设 `mark_status="unmarked"`；`import_procedure` 有 `_has_review` → `REVIEW_NOT_CLEARED`(422) 拦截。
- 编辑器壳 `ProcedureEditorView.vue`：顶栏 / 左侧 `ChapterTreePanel`(340px 固定) / 右侧（程序详情 + 节点详情/附件/版本历史 tab）。`store.load(id)` 拉取。
- `WordPreviewPanel.vue` 纯 props（`file: File | null`），用 docx-preview 渲染，与导入对话框无耦合，可直接复用。
- 可折叠能力：`ImportSideRail.vue`（props `label`/`side`，emit `expand`）可复用作折叠态竖条；列宽百分比/分隔条那套 `importCols` 是为导入 3 列设计，编辑器布局不同，**不直接复用**，按编辑器自身布局实现折叠/拖拽。

## 3. 决定

### D1 · 导入携带 review、不再拦截
- `import_procedure`：**移除** `_has_review` 拦截（允许带 review 导入）。
- `_create_node`：`mark_status = "review" if node.mark_status == "review" else "unmarked"`（只透传 review；step/content 标记仍归 unmarked，留 P2c 一并改，保持 beta2 现行为）。
- 既有断言旧行为的测试 `test_smart_unstyled_review_blocks_import` 改为：带 review 导入成功(201)，且建出的草稿章节带 `mark_status='review'`（重命名为 `test_smart_unstyled_review_carried_into_draft` 之类）。

### D2 · 编辑器最左可折叠"原文预览"列
- 仅当该程序**有 source-docx**时出现（编辑器加载时探 `GET /procedures/{id}/source-docx`；404 → 不渲染该列，空白新建/无源程序无预览）。
- 取回 blob → `new File([blob], filename, {type: docx-mime})` → 传 `WordPreviewPanel`。
- **可折叠**：展开时左侧显示预览；折叠时缩成 32px 竖条（复用 `ImportSideRail`，`label="Word 原文预览"` `side="left"`，点击展开）。一个折叠箭头收起。
- **可调宽 + 记忆**：预览列与右侧之间一个拖拽分隔条调宽；折叠态/宽度持久化到 localStorage（如 `smartsop.editor.preview`）。沿用导入对话框的 pointer 拖拽思路，但作用于编辑器布局（不复用 `importCols` 百分比函数）。
- 布局变为：`顶栏 / [原文预览(可折叠)] [章节树 340] [右侧详情区]`。

### D3 · 只读暴露 review
- `TreeRow.vue`：`mark_status==='review'` 的行显示一个"待确认"徽标/点（与现有按 mark_status 的配色并存）。
- `ChapterTreePanel` 头部显示只读"N 个待确认"计数（统计 `mark_status==='review'` 的章节）。
- P2a **不提供**接受/清除交互（P2b）。

## 4. 数据流

1. 导入（含 review）→ 后端建 DRAFT，章节带 `mark_status='review'`（D1）。
2. 进编辑器 `store.load(id)` → 章节树带 review → TreeRow 徽标 + 头部计数（D3）。
3. 编辑器并行探 `source-docx`：有 → 渲染可折叠预览列（D2）；404 → 无预览列。

## 5. 边界与错误

- **无 source-docx**（空白新建 / 导入未存 / 已丢失）：预览列不渲染；编辑器其余照常。
- **docx 渲染失败**：`WordPreviewPanel` 已有"预览加载失败"空态，沿用。
- **大文档**：编辑器加载时取一次 blob 决定是否渲染该列（404 → 不渲染）；docx 的 `renderAsync` **渲染**延迟到该列首次展开时进行，折叠态不渲染，避免拖慢加载。
- **beta2 现状不破**：beta2 导入前已清 review，D1 改动不影响其结果；它仍可正常导入。

## 6. 测试

- 后端：`import` 带 review → 201 且草稿章节 `mark_status='review'`；更新/重命名 `test_smart_unstyled_review_blocks_import`。（pytest）
- 前端：
  - source-docx 取回 api（`api/procedures.ts` 新增 `fetchSourceDocx(id)` 或类似）。
  - 预览列组件：有 blob → 渲染 `WordPreviewPanel`；折叠 → `ImportSideRail`；折叠/宽度持久化纯逻辑单测。
  - `TreeRow`：`mark_status==='review'` → 渲染待确认徽标。
  - 计数：tree panel 头部 review 计数。
  - Gate：`npm run lint && npm run typecheck && npm run test && npm run build`。

## 7. 文件清单（预估）

- 后端：改 `app/services/import_service.py`（去拦截 + 透传 review）；改 `backend/tests/integration/test_word_import.py`（更新该测试）。
- 前端：
  - 改 `frontend/src/api/procedures.ts`：加 `fetchSourceDocx(id): Promise<Blob>`（404 → null/抛特定）。
  - 新建 `frontend/src/components/editor/EditorPreviewPane.vue`（取 blob → File → `WordPreviewPanel`；折叠态 `ImportSideRail`；空态）。
  - 改 `frontend/src/views/procedures/ProcedureEditorView.vue`：插入最左可折叠预览列 + 拖拽分隔条 + 折叠/宽度持久化。
  - 改 `frontend/src/components/editor/TreeRow.vue`：review 徽标。
  - 改 `frontend/src/components/editor/ChapterTreePanel.vue`：review 计数（头部）。
  - 可能新增 `frontend/src/utils/editorPreview.ts`：折叠/宽度的纯持久化逻辑（便于单测）。

## 8. 留给 P2b/P2c

- 待确认的接受/清除交互、"完成"时拦截待确认（P2b）。
- 5 选项层级标定（一级/二级/三级/正文/步骤），含 step/content 标记透传、置信度/降型藏存 schema、章节↔步骤跨实体处理（P2c）。
