# 设计：程序级操作员签字栏（signoff）

**日期**：2026-05-25
**状态**：设计已确认，待实施
**作者**：cui_yuming + Claude

## 1. 背景与动机

当前步骤模型有一个逐步布尔字段 `step.require_confirmation`，勾选后 PDF 在该步骤末尾渲染一行
`☐ 已确认完成    签名: ____  日期: ____`（左对齐，仅对勾选的步骤）。

经讨论确认，这与最初设计意图不符。原意是：

- 在**程序级别**激活"签字栏"（一个总开关），而非逐步勾选；
- 激活后，**默认所有步骤**在 PDF 右侧带一个手写签字区；
- 它的消费者**仅是 PDF**，与移动端执行无关（移动端执行运行时本期不存在，Q264）。

本设计将 `require_confirmation`（逐步）替换为 `signoff_enabled`（程序级），并相应调整 PDF 渲染、编辑器、预览与版本传播。

## 2. 已确认的设计决策

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | 开关层级 | **每个 Procedure 各自设**（Procedure 模型上的持久化字段） |
| 2 | 字段性质 | **受控文档属性**：持久化、锁版本、所有人打印一致；开关放**编辑器**（草稿态可改），预览/下载如实反映 |
| 3 | PDF 版式 | **方案 B**：保持现有流式版式，在每步末尾**右对齐**一个签字块；不做表格列重构 |
| 4 | 适用范围 | **除警示型（NOTE/CAUTION/WARNING）外全部**步骤类型（含 NONE） |
| 5 | 迁移策略 | **保留意图到程序级**：凡有 ≥1 个步骤 `require_confirmation=true` 的 Procedure，回填 `signoff_enabled=true`，再删 step 列 |
| 6 | 签字块文案 | `签字: __________   日期: __________`，右对齐，**无勾选框、无"已确认完成"**（手写签字，非打勾） |

## 3. 数据模型与迁移

### 3.1 模型变更
- **`Procedure`**（`backend/app/models/procedure.py`）：新增
  ```python
  signoff_enabled: Mapped[bool] = mapped_column(default=False, server_default="0")
  ```
- **`ProcedureStep`**（`backend/app/models/step.py`）：删除 `require_confirmation` 列。

### 3.2 Alembic 迁移
一条迁移，`down_revision = 'drop_expected_output'`，`revision = 'procedure_signoff'`：

`upgrade()`：
1. `add_column` `tb_procedure.signoff_enabled`（Boolean, server_default '0', not null）；
2. 回填：
   ```sql
   UPDATE tb_procedure SET signoff_enabled = 1
   WHERE id IN (SELECT DISTINCT procedure_id FROM tb_procedure_step WHERE require_confirmation = 1)
   ```
3. `drop_column` `tb_procedure_step.require_confirmation`。

`downgrade()`：反向——`add_column` step.`require_confirmation`（默认 0），`drop_column` procedure.`signoff_enabled`（不还原回填值）。

> 注：seed 中无示例模板携带 `require_confirmation`（模板已废弃，Q340），故回填仅影响真实库数据。

## 4. 后端

### 4.1 PDF 渲染（核心）
- `pdf/context.py`：
  - `StepData` 删 `require_confirmation`；
  - `ProcedureData` 新增 `signoff_enabled: bool`，`_to_*` 装配时从 `procedure.signoff_enabled` 取。
- `pdf/styles.py`：新增样式 `step_signoff` = 继承 `step_placeholder` + `alignment=TA_RIGHT`（引入 `reportlab.lib.enums.TA_RIGHT`）。
- `pdf/sections.py:_render_step`：将原"确认行"分支替换为——
  ```python
  if data.procedure.signoff_enabled and ftype not in ("NOTE", "CAUTION", "WARNING"):
      out.append(Paragraph("签字: __________   日期: __________", s("step_signoff")))
  ```
  （`_render_step` 已持有 `data: RenderData`，可直接访问 `data.procedure.signoff_enabled`。）

### 4.2 Schema
- `schemas/procedure.py`：`ProcedureUpdate`（`ProcedureSaveIn` 自动继承）、`ProcedureOut`、`ProcedureMeta` 各加 `signoff_enabled: bool`。
- `schemas/node.py`：`StepCreate` / `StepUpdate` / `StepUpsert` / `StepOut` 删 `require_confirmation`。

### 4.3 Service
- `services/step_service.py`（create/update）、`services/editor_service.py`（upsert）：删 `require_confirmation` 赋值。
- `services/version_flow_service.py`：
  - `_STEP_COPY` 去掉 `"require_confirmation"`（该文件中 `require_confirmation` 仅此一处引用）；
  - `_fork()` 的 `Procedure(...)` 构造新增 `signoff_enabled=source.signoff_enabled`（随升级/回退/复制版本走）。

## 5. 前端

### 5.1 类型
- `types/node.ts`：`EditorStep` / `StepUpsert` / `StepOut` / `FlatRow` 删 `require_confirmation`；`ProcedureMeta` 加 `signoff_enabled: boolean`。

### 5.2 编辑器
- `components/editor/ProcedureDetailsPanel.vue`：在"版本更新说明"之后新增一个 `el-switch`，label「PDF 启用操作员签字栏」，`:disabled` 跟随只读态，`@change` → `store.setMetaField('signoff_enabled', v)`。
- `components/editor/StepDetailPanel.vue`：删除"需要操作员确认"复选框（§内容面板）。
- `components/editor/TreeRow.vue`：删除 `⚠` 图标行（原 line 91）。
- `store/procedureEditor.ts`：
  - `emptyStep` / `ingestStep` 删 step 的 `require_confirmation`；
  - `buildPayload` 程序级返回新增 `signoff_enabled: p.signoff_enabled`（`ProcedureMeta` 类型 + 泛型 `setMetaField` 自动支持）。

### 5.3 PDF 预览
- `utils/pdfModel.ts`：步骤块签字块不再读 `step.require_confirmation`，改为读程序级 `signoff_enabled` + 步骤类型（非警示型）。
- `components/PdfPreview/PdfPreviewDialog.vue`：签字块改为**右对齐静态签字行**（`签字: __ 日期: __`），去掉可勾选交互（手写签字无可勾项）。hold-point / signature-bar / 封面签名区的勾选不受影响。

## 6. 测试

- 后端：
  - `test_sections.py`：`signoff_enabled=true` → 非警示型步骤出右对齐签字行、警示型不出；`false` → 都不出；删除 `StepData.require_confirmation` 相关断言/构造。
  - `test_context.py`：装配带上 `signoff_enabled`。
  - `test_version_flow_service.py`：新增/调整 `_fork` 传播 `signoff_enabled` 用例。
- 前端：
  - `pdfModel.spec.ts`：按程序级开关 + 步骤类型断言签字块；删除 fixture 的 `require_confirmation`。
  - `procedureEditorStore.spec.ts` / `editorNumbering.spec.ts` / `treeDnd.spec.ts`：删 fixture 的 `require_confirmation`。
  - `TreeRow` / `StepDetailPanel` 相关断言相应调整。

## 7. 文档同步

- `data-model.md`：step 表删 `require_confirmation`；procedure 表加 `signoff_enabled`。
- `pdf-rendering.md`：§6.3 顺序 6 改为"程序级签字栏（右对齐，排除警示型）"。
- `editor-behavior.md`：去掉 `⚠` 图标说明；加程序级签字开关。
- `api-specification.md`：示例 payload 同步。

## 8. 不在范围内（YAGNI）

- 不做真正的表格列版式（方案 A 已否）。
- 不做移动端执行（本期无执行运行时）。
- 不保留"逐步选择性签字"能力（已改为程序级一刀切）。
- 预览页不承载 signoff 开关（已确认为受控文档属性，归编辑器）。
