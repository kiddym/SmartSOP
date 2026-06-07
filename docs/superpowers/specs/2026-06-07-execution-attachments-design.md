# 工单执行态 UPLOAD/PHOTO/SIGNATURE 附件上传设计

> 日期：2026-06-07 ｜ 状态：设计待实现 ｜ 关联：净室重写基线、通用附件基础设施、H4 工单执行可写界面、SOP step_type 执行

## 1. 背景与目标

H4 已交付工单执行可写界面（PC），但 SOP 步骤类型 `UPLOAD`/`PHOTO`/`SIGNATURE` 仅"备注+勾选完成"，**附件上传未接通**。本设计补齐：执行人在这三类步骤上传文件/拍照选图/手写签名，落为该执行步骤的附件，完成时对必填项硬校验。

### 现状（已勘察）
- `UPLOAD`/`PHOTO`/`SIGNATURE` 是 SOP 节点 `ProcedureNode.input_schema["type"]` 的字符串常量（后端无 Python Enum，仅 PDF 渲染层 `app/services/pdf/sections.py` 有 if 分支）。
- 执行态 `WorkOrderStepResult`（`tb_work_order_step_result`）：`response`(JSON 无约束)/`is_done`/`notes`/`done_by_user_id`/`done_at`；继承 `UUIDMixin/TimestampMixin/TenantMixin`，**无 `SoftDeleteMixin`（缺 is_active/deleted_at）**。
- `update_step`（`app/services/work_order_execution_service.py`）盲存 `response`，`is_done=True` 时只校验 `_required_fields`（response key 非空）；`assert_completable` 要求所有步骤 is_done。
- 通用 `Attachment` 多态单表（`entity_type`+`entity_id`+`storage_path`...）+ `ENTITY_REGISTRY`（`app/services/attachment_entities.py`）；`work_order` 已注册，**`work_order_step_result` 未注册**。端点 `POST/GET/DELETE /api/v1/attachments`（multipart）已全。文件经 storage backend（Local/S3）存储。
- 工单级 `signature_url`（完成签名，String(512) URL，非文件上传，走 transition body）——与本设计的"步骤内签名"正交，二者共存。
- 前端 `ExecutionTab.vue` 对三类走兜底 `<span>本步骤无录入项…</span>`，无控件。

### 已澄清的决策
- **绑定粒度**：步骤级 `work_order_step_result`（精确挂到具体执行步骤行）。
- **完成校验**：必填的 UPLOAD/PHOTO/SIGNATURE 步骤，`is_done=True` 时后端硬校验"该步骤下确实存在 active 附件"，无则 422。
- **前端控件（PC）**：UPLOAD/PHOTO 走文件选择上传（PHOTO `accept=image/*`）；SIGNATURE 走 canvas 签名画板，导出 PNG 作附件上传。
- **净室红线**：全新原创，不复制第三方代码/命名。

### 非目标（YAGNI / 留后续）
- PDF 报告嵌入执行态上传的图片/签名（现 PDF 只画占位框，留后续一轮）。
- 移动端相机拍照 / 移动端手写（移动端整体已暂缓）。
- 附件批注/标记、离线上传、附件版本。
- 把 attachment_id 写进 `response`（附件按宿主查询，不与 response 耦合）。

## 2. 架构方案

**步骤级附件 = 复用通用 Attachment 基础设施，新增一个 entity_type 注册 + 宿主软删列 + 完成校验分支 + 前端三控件。** 不新增附件端点（复用 `/api/v1/attachments`）。

- 附件按 `entity_type="work_order_step_result"` + `entity_id=<step_result.id>` 直接绑定到执行步骤行。
- 完成校验在执行服务内做（与既有 `_required_fields` 并行）。
- 前端在 `ExecutionTab.vue` 为三类型加控件，最终都落为该 step_result 的附件；SIGNATURE 的画板产物也走同一附件通道，后端统一。

> 已否决：① 工单级绑定 + response 记 attachment_id（关联是软约定、跨步骤共享一个工单附件池，精确度差）；② 为执行附件单建专表（重复造 Attachment 已有能力，违背 DRY）。

## 3. 数据模型与迁移

### 3.1 模型变更
`app/models/work_order_step_result.py` 的 `WorkOrderStepResult` 加 `SoftDeleteMixin`（继承链变为 `UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin`）。`is_active`/`deleted_at` 来自 mixin。

### 3.2 迁移 `20260607_0019_step_result_soft_delete.py`
- down_revision = 当前单 head（`custom_field`；写前 `alembic heads` 确认）。
- `batch_alter_table("tb_work_order_step_result")` 加 `is_active`（Boolean, NOT NULL, `server_default=sa.true()`）+ `deleted_at`（DATETIME6 可空）；建 `ix_tb_work_order_step_result_is_active`。
- downgrade：SQLite 显式删索引 + 删两列。
- 验证单 head + upgrade/downgrade/upgrade 重放。

### 3.3 查询过滤
`list_step_results` 等执行态查询补 `is_active.is_(True)` 过滤（与全库软删约定一致）。既有创建/读取行为不变（新行默认 is_active=True）。

## 4. 后端：附件注册 + 完成校验

### 4.1 ENTITY_REGISTRY 注册
`app/services/attachment_entities.py` 加：
```python
"work_order_step_result": EntitySpec(
    WorkOrderStepResult, WORK_ORDER_VIEW, WORK_ORDER_EDIT, scoped=True
),
```
读=`work_order.view`、写=`work_order.edit`（执行步骤附件 = 编辑工单执行）；`scoped=True` 多租户隔离。复用 `_lookup_host`（依赖宿主 is_active——3.1 已补）。无需新端点，沿用 `POST/GET/DELETE /api/v1/attachments`。

### 4.2 附件类型常量
执行服务内新增原创常量：`ATTACHMENT_STEP_TYPES = frozenset({"UPLOAD", "PHOTO", "SIGNATURE"})`。

### 4.3 完成校验
`work_order_execution_service.update_step`：`is_done` 置 True 时，在既有 `_required_fields` 校验之后，新增——取该 step 节点 `input_schema`：若 `type ∈ ATTACHMENT_STEP_TYPES` 且 `required` 为真，统计该 `step_result` 下 active 附件数（`select count(Attachment) where entity_type="work_order_step_result", entity_id=sr.id, is_active`）；为 0 → `bad_request("STEP_ATTACHMENT_REQUIRED", "本步骤需上传附件后才能完成")`。非必填或非附件类型不卡。

`assert_completable` 不变（仍靠各 step is_done；附件硬校验已前置在 step 完成时）。

### 4.4 读出
`StepResultRead`（及 `ExecutionView` 内步骤项）加 `attachment_count: int = 0`，由执行服务在构造视图时按 step_result 批量统计填充（一次查询聚合，避免 N+1）。前端据此回显"已传 N 个"并驱动只读展示。

## 5. 前端：ExecutionTab 三类控件

### 5.1 控件分支
`src/components/workorder/ExecutionTab.vue` 为 `UPLOAD/PHOTO/SIGNATURE` 替换兜底占位：
- **UPLOAD**：`el-upload`（`:http-request` 自定义）选文件 → 调附件上传。
- **PHOTO**：同上但 `accept="image/*"`。
- **SIGNATURE**：原创组件 `src/components/workorder/SignaturePad.vue`（canvas 手写 + 清除/确认），确认时 `canvas.toBlob()` 出 PNG → 作附件上传。
- 三类上传成功后刷新该 step 附件列表（缩略图/文件名 + 删除按钮）；展示 `attachment_count`。
- **只读态**（工单已完成 / 无 `work_order.edit` 权限）：只展示已传附件（可下载/预览），不渲染上传控件与删除。

### 5.2 附件 api
`src/api/attachments.ts` 提供 per-entity 封装（如缺则补）：`uploadAttachment(entityType, entityId, file)`（FormData multipart）、`listAttachments(entityType, entityId)`、`deleteAttachment(id)`。entity_type 传 `'work_order_step_result'`，entity_id 传 step_result.id。

### 5.3 文案
全中文字面量。

## 6. 权限、多租户、边界
- 上传/删除步骤附件 = `work_order.edit`；查看 = `work_order.view`（EntitySpec 承载）。
- 多租户：`work_order_step_result` `scoped=True` + Attachment 自身租户列，自动隔离。
- 完成校验只查当前 step_result 的 active 附件，不跨工单/租户。
- 工单已完成（COMPLETE）后执行态只读：上传控件不渲染（前端）；后端 `update_step` 既有完成态约束沿用。

## 7. 测试策略
- 后端：迁移单 head 可重放（加列+索引）；`work_order_step_result` 注册后经 `/api/v1/attachments` 能上传/列出/删除（租户隔离、`work_order.edit` 门控 403）；必填附件步骤无附件 `is_done` → 422、有附件 → 通过；非必填不卡；`attachment_count` 正确聚合；既有执行态测试（update_step/assert_completable/list_step_results）不破。
- 门禁：`import app.main`、ruff check + format --check + mypy；前端 vue-tsc + eslint + vitest。
- 前端：ExecutionTab 三类渲染对应控件；上传调用 attachments api 带正确 entity_type/id；SignaturePad 导出 PNG 并上传；只读态不渲染上传/删除。

## 8. 实现顺序（增量）
1. `WorkOrderStepResult` 加 SoftDeleteMixin + 迁移 + 查询过滤（不破既有执行测试）。
2. ENTITY_REGISTRY 注册 work_order_step_result（附件上传/列出/删除经既有端点打通 + 测试）。
3. 完成校验分支（必填附件步骤无附件 422）+ `attachment_count` 读出。
4. 前端 attachments api 封装（如需）+ ExecutionTab UPLOAD/PHOTO 控件。
5. SignaturePad 组件 + SIGNATURE 接入 + 只读态。

每步独立 commit、门禁全绿。
