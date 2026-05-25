# 编辑器：内容块降为步骤级（并入 step 表）设计

> 日期：2026-05-26
> 范围：把「内容块」从章节树移到步骤级——内容块成为 `ProcedureStep` 的一个种类，可与步骤在同一章节下自由交替。全栈改动（后端模型/迁移/解析/保存/编号/PDF + 前端类型/store/面板）。执行运行时本期仍不实现（Q264），不在范围。

## 背景与问题

当前数据模型把「内容块」实现为章节表（`tb_procedure_chapter`）里 `content_type='content'` 的行：它和「章节」同表、共用 `parent_id` 树、同一层级。规则上（Q25）一个父节点的孩子要么是 {章节 + 内容块}，要么是 {步骤}，二者互斥——因此**内容块与步骤被强制分到不同层级，且不能在同一章节下交替出现**。

但内容块在产品语义上就是「一段只有富文本、没有执行表单字段的内容」，本质和步骤同级：它现在已经是「无编号、无标题、强制叶子」的纯富文本叶子节点，和「只有 `content` 的步骤」几乎一模一样。当前模型导致两个问题：

1. 想在步骤之间穿插一段说明/旁注（SOP 极常见）做不到——Q25 互斥禁止同章节下步骤与内容块共存。
2. 「内容块是个不像章节的章节」概念别扭：它同表于章节却强制叶子、不编号、无标题，还需要 `content_type` 判别与一堆专属校验。

## 目标

- 内容块成为 `ProcedureStep` 的一个种类（`kind='content'`），与步骤同在步骤表、同一层级，可在同一章节下按顺序自由交替。
- 章节表瘦身为纯标题/分组节点，删除 `content_type` 与 `rich_content`。
- 行为保持：内容块仍不编号、不占序号位、无标题、只有富文本；PDF 中仍按所见顺序内联渲染。
- 内容块 ↔ 步骤在编辑器内为「翻一个字段」的轻量互转。

## 非目标

- 执行运行时态：本期不实现（Q264），迁移后仍无影响。
- 生产数据无损迁移：当前为开发数据、可重建，迁移做到「尽力而为 + 1:1 直搬」即可。
- 章节「分组」与「叶子项」之间的互斥**保留**（一个章节要么放子章节，要么放步骤+内容块），不在本轮放开。

---

## 设计

### 1. 数据模型

**`tb_procedure_step` 新增判别列**

- `kind: str`，取值 `'step' | 'content'`，默认 `'step'`，建索引 `ix_..._kind`。
- 内容块 = `kind='content'` 的行：用现有 `content` 富文本字段承载正文；`title=''`、`input_schema={}`、`attachment_marks=[]`、`code=''`（恒不编号）、`skip_numbering` 不参与（内容块永远不编号）。
- 普通步骤 = `kind='step'`，字段与行为完全不变。

**`tb_procedure_chapter` 瘦身**

- 删除 `content_type`、`rich_content` 两列。章节从此只是标题容器。
- 保留 `mark_status`（含 `'content'` 取值）、`conversion_status`、`level`、`code`、`skip_numbering`——服务 Word 解析的「标记/审阅/转换」流程（见 §4）。

### 2. 迁移（alembic）

- DDL：`tb_procedure_step` 加 `kind` 列（默认 `'step'`）；`tb_procedure_chapter` 删 `content_type`、`rich_content` 列。
- 数据搬运：对每个 `content_type='content'` 的章节行，新建一条
  `ProcedureStep(kind='content', content=<原 rich_content>, chapter_id=<原 parent_id>, title='', input_schema={}, sort_order=<原 sort_order>)`，随后删除原章节行。现存内容块均为强制叶子，故为 1:1 直搬，无嵌套需拆解。
- downgrade：反向（step kind='content' 行 → 章节 content 行；恢复两列）。尽力而为即可。
- 迁移后断言：`tb_procedure_chapter` 不再存在任何「非标题容器」行。

### 3. 后端：保存 / 编号 / PDF

**批量保存 `editor_service.save_procedure` + `schemas/node.py`**

- `ChapterUpsert`：删除 `content_type`、`rich_content`。`StepUpsert`：新增 `kind`。
- `ChapterOut` / `ChapterTreeNode` 删除 `content_type`、`rich_content`；`StepOut` 新增 `kind`。删除 `ContentType` 类型别名（`MarkStatus` 保留）。
- **Q25 重写**：同一父节点下，「子章节」与「叶子项（步骤 + 内容块）」互斥；**步骤与内容块之间不再互斥，可共存交替**。
- 删除旧校验：`CHAPTER_RICH_CONTENT_NOT_ALLOWED`、「content 必须是叶子」。正文 5MB 上限校验移到 `step.content`（当 `kind='content'`）。

**编号 `numbering_service.recompute`**

- `number_steps`：`kind='content'` 的步骤 `code=''` 且不自增序号位（行为等同今天的内容块，仅数据来源从章节表改为步骤表）。其余步骤序号在内容块穿插时保持连续。

**PDF `pdf/context.py` + `pdf/sections.py`**

- `ChapterData` 删除 `content_type`/`rich_content`；`StepData` 增加 `kind`。
- 叶子章节渲染时，遍历其步骤行（按 `sort_order`）：`kind='content'` → 直接渲染富文本（无编号、无标题，同今天的 content 渲染）；`kind='step'` → 按步骤渲染（编号 + 标题 + 正文 + 表单）。两者在输出中按顺序交替，和编辑器所见一致。
- `display_code`：内容块无须特判 `content_type`，改由「该步骤 `kind='content'` → 不取号」实现。

### 4. 后端：Word 解析 / 标记 / 转换

**导入 `import_service`**

- 解析器（`structurer` / `result.py`）中间结果**不动**：标题块仍 `content_type='chapter'`，正文块仍 `content_type='content'`（每块独立，§19）。
- 落库时改映射：`content_type='content'` 的解析节点 → 新建 `ProcedureStep(kind='content', content=block.html, chapter_id=<最近的标题章节>, sort_order=<位序>)`；标题块仍建章节行。
- `schemas/parse.py` 的 `ImportNodeIn` 保留 `content_type`（解析侧分类），仅落库语义改变。

**标记 / apply-marks `mark_service` + `conversion_service` + `chapters.py`**

- `mark_status` 仍存于章节行，服务「启发式标题（`'review'`）确认 / 重分类」。apply-marks 只处理章节节点：
  - 章节标 `'step'` → 建 `ProcedureStep(kind='step', title=<章节标题>, chapter_id=<章节父级>, sort_order=<章节位序>)`，删该章节。
  - 章节标 `'content'` → 建 `ProcedureStep(kind='content', content=<由章节标题包成段落>)`，删该章节。
  - 标 `'review'` 不动（持久态，apply-marks 不碰）。
- **删除**「把 content 章节按顶层 HTML 块拆成多个 step」的旧分支（内容块在导入时已按块拆好，无需再拆）。
- 章节 → 步骤 / 内容块的转换端点保留（解析流程要用）。**内容块 ↔ 步骤互转不再走专用端点**：在编辑器内翻 `step.kind`、随批量保存提交。

### 5. 前端

**类型 `types/node.ts`**

- 删除 `ContentType`；`EditorChapter`、`ChapterTreeNode`、`ChapterOut`、`ChapterUpsert` 去掉 `content_type`/`rich_content`。
- `EditorStep`、`StepOut`、`StepUpsert` 新增 `kind: 'step' | 'content'`。
- `NodeKind`（`'chapter' | 'content' | 'step'`）保留；`'content'` 来源改为 `step.kind`。

**Store `store/procedureEditor.ts`**

- `ingestChapters`：章节全为标题容器；步骤携 `kind`。
- **`flatRows`**：叶子章节下，把其步骤行（两种 `kind`）按 `sort_order` 排出，每行 `kind` 取自 `step.kind`——步骤与内容块同缩进、按序交替。
- 新增收敛：`addStepNode(chapterId, afterId, kind='step')` 兼建步骤与内容块；`addChapterNode` 只剩 `'chapter'`。
- 内容块 ↔ 步骤互转：翻该步骤 `kind` 并标脏。
- `selectedChapter` / `selectedStep` getter 与详情面板选择按 `kind` 对齐（见下）。

**编号镜像 `utils/editor.ts`**

- `recomputeCodes` 的 `numberSteps`：跳过 `kind='content'`（`code=''`、不占位），与后端 `numbering_service` 逐行等价（单测锁定）。
- `getAddButtonState`（Q25）重写：`canAddChapter` 仅当无 step/content 子项；`canAddStep`、`canAddContent` 仅当无 chapter 子项（step 与 content 可共存）。
- `formatCode`：`kind='content'` → `''`。
- `computeFallback`：`'content'` → `(空内容块)`（已有）。

**详情面板 + 树行**

- `ProcedureEditorView` 按 `kind` 选面板：`chapter`→`ChapterDetailPanel`、`step`→`StepDetailPanel`、`content`→`ContentDetailPanel`。
- `ContentDetailPanel`：改为绑定一条内容块步骤，仅富文本编辑器（绑 `step.content`，无标题/表单/附件）。**移除 `mark_status==='review'` 待确认横幅与 `acceptReview`**——内容块（步骤）不带 `mark_status`，review/接受流程仅留在章节（`ChapterDetailPanel`）。
- `StepDetailPanel`：`kind='step'` 不变。
- `TreeRow`：下拉新增「内容块」入口（按 Q25 启停）；新增「内容块 ↔ 步骤」互转菜单项。图标沿用 📘章节 / 📄内容块 / ☐步骤。jsdom 下 el-dropdown 菜单不渲染，测 `@command` 走组件 `$emit`，不手搓菜单。
- `ChapterTreePanel`：`addTargetFor` 的可选项纳入「内容块」；`onAdd` 对内容块走 `addStepNode(..., 'content')`。

### 6. 待确认点：`promoteContentToChapter` /「提升为章节」

现状：`ChapterDetailPanel` 有「提升为章节」按钮调 `store.promoteContentToChapter(id)`，把 content 章节行就地改为 chapter（同表转换）。

新模型下内容块是步骤行，「内容块 → 章节」变为**跨表 + 跨层级**转换。本设计的处置：

- 改为 `convertContentToChapter(stepId)`：在内容块步骤所在父级、同位序处新建一个空标题章节，删除该内容块步骤；因章节不承载正文，**原富文本正文随转换丢弃**（与旧实现「转章节后正文清空」的净效果一致）。
- 按钮从 `ChapterDetailPanel` 迁到 `ContentDetailPanel`（内容块自己的面板）。

> 这是一处行为取舍（正文丢弃）。若更希望「转章节时保留正文」或「干脆移除此入口、让用户走 内容块→步骤→重排」，请在评审时指出。

---

## 涉及文件汇总

| 文件 | 改动 |
| --- | --- |
| `backend/app/models/step.py` | 新增 `kind` 列 + 索引 |
| `backend/app/models/chapter.py` | 删除 `content_type`、`rich_content` 列 |
| `backend/app/schemas/node.py` | 删 `ContentType` 与章节 content 字段；`StepOut/StepUpsert` 加 `kind` |
| `backend/app/schemas/parse.py` | `ImportNodeIn` 保留 `content_type`（落库语义改变，schema 不变或微调） |
| `backend/app/services/editor_service.py` | 保存：删 content 字段处理、Q25 重写、5MB 校验移到 step.content |
| `backend/app/services/numbering_service.py` | `number_steps` 跳过 `kind='content'` |
| `backend/app/services/import_service.py` | content 解析节点 → `kind='content'` 步骤 |
| `backend/app/services/mark_service.py` | 章节标 step/content → 对应 kind 步骤；移除 content 拆分分支 |
| `backend/app/services/conversion_service.py` | 章节 → 步骤/内容块转换；内容块拆分逻辑移除 |
| `backend/app/services/pdf/context.py` | `ChapterData` 删 content 字段；`StepData` 加 `kind` |
| `backend/app/services/pdf/sections.py` | 叶子章节按 sort_order 交替渲染步骤/内容块；`display_code` 改判 kind |
| `backend/app/routers/chapters.py` | 转换端点：保留 章节→步骤/内容块；内容块↔步骤改客户端 |
| `backend/alembic/versions/<new>.py` | 加 step.kind、删章节两列、1:1 数据搬运 |
| `frontend/src/types/node.ts` | 删 `ContentType`/章节 content 字段；step 系列加 `kind` |
| `frontend/src/store/procedureEditor.ts` | ingest/flatRows 交替；addStepNode(kind)；内容块↔步骤互转；promoteContentToChapter 跨表化 |
| `frontend/src/utils/editor.ts` | numberSteps 跳过 content；getAddButtonState 重写；formatCode 改判 kind |
| `frontend/src/components/editor/ContentDetailPanel.vue` | 绑定内容块步骤、仅富文本；移除 review 横幅；承接「转为章节」按钮 |
| `frontend/src/components/editor/ChapterDetailPanel.vue` | 移除「提升为章节」按钮；章节仅标题 |
| `frontend/src/components/editor/TreeRow.vue` | 新增「内容块」入口 + 内容块↔步骤互转菜单 |
| `frontend/src/components/editor/ChapterTreePanel.vue` | addTargetFor 纳入内容块；onAdd 走 addStepNode('content') |
| `frontend/src/views/procedures/ProcedureEditorView.vue` | 按 `kind` 选详情面板 |

## 测试

**后端**

- `numbering_service`：内容块步骤不编号、不占位；步骤序号在内容块穿插时连续。
- `editor_service` 保存校验：新 Q25（步骤+内容块共存、与子章节互斥）；旧 content 校验已删；5MB 校验落在 step.content。
- `import_service`：非标题块 → `kind='content'` 步骤，挂最近标题章节下，位序正确。
- `mark_service`：章节标 step/content → 对应 kind 步骤；确认旧拆分分支移除；`'review'` 不被 apply-marks 触碰。
- `pdf`：内容块与步骤按 sort_order 交替渲染，内容块无编号无标题。
- 迁移：跑 upgrade 后章节表无非标题行、内容块数据落步骤表；downgrade 可逆。

**前端**

- `recomputeCodes` 与后端 `numbering_service` 等价（含内容块穿插场景）。
- `getAddButtonState` 新规则全分支（步骤+内容块可加、与章节互斥）。
- `flatRows` 交替顺序正确（按 sort_order）。
- store：addStepNode 两种 kind；内容块↔步骤互转标脏；convertContentToChapter。
- `ContentDetailPanel` 只渲染富文本、无 review 横幅。
- `TreeRow` 菜单按 Q25 启停、互转命令（走 `$emit`，不手搓 el-dropdown 菜单）。

## 风险与权衡

- **改动面大**：横跨模型/迁移/解析/保存/编号/PDF/前端。缓解：执行运行时未实现、数据可重建，且内容块行为（不编号/无标题/叶子）与现状一致，多为「换数据来源」而非「换行为」。
- **`recomputeCodes` 与后端编号必须保持等价**：单测锁定；内容块跳过逻辑两端对齐。
- **「提升为章节」正文丢弃**：见 §6 待确认点。
- **解析侧仍用 `content_type` 分类**：仅落库语义改变，避免改动解析器本体，降低风险。
