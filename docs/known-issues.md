# 已知问题（Known Issues）

> 集中记录已发现、尚未修复的缺陷与契约不一致。每条含：现象 / 证据 / 根因 / 影响 / 建议修复。新问题追加在表后并补一节详述。

| # | 标题 | 区域 | 严重度 | 状态 | 发现 |
|---|---|---|---|---|---|
| KI-1 | SOP 附件上传前后端契约失配（字段名 `files` vs `file`，必然 422） | 前端×后端 / 附件 | 高（功能不可用） | 已修复（fix/sop-attachment-upload-multifile） | 2026-06-02（通用附件特性最终审查） |

---

## KI-1 · SOP 附件上传前后端契约失配

**现象**：在 SOP 程序编辑器的附件面板上传文件，请求被后端以 **422** 拒绝，UI 提示「上传失败，请重试」。SOP 附件上传功能实际不可用。

**证据**：
- 前端 `frontend/src/api/attachments.ts:7-16`：`uploadAttachment(procedureId, files: File[])` 用 `files.forEach(f => fd.append('files', f))`——字段名 **`files`（复数）**，多文件，且声明返回 `Promise<AttachmentOut[]>`（数组）。
- 前端 `frontend/src/components/editor/AttachmentPanel.vue:42-59`：`handleFiles` 收集多选文件 → `uploadAttachment(props.procedureId, filesArray)` → 之后 `fetchAttachments()` 重取（**不消费 POST 响应体**）。
- 后端 `backend/app/routers/attachments.py` 的 `upload_procedure_attachment`：`file: UploadFile = File(...)`——字段名 **`file`（单数）**、必填、**单文件**，返回单个 `AttachmentOut`（201）。

**根因**：三处契约失配：
1. **字段名**：前端 `files` vs 后端必填 `file` → 后端取不到 `file` → **422**（这是导致上传失败的直接原因）。
2. **数量**：前端按多文件设计（`<input>` 多选 + `File[]`），后端只收单文件。
3. **响应形状**：前端类型声明 `AttachmentOut[]`，后端返回单个 `AttachmentOut`（因 `AttachmentPanel` 重取列表、不读响应，此项当前不致运行时错，但类型契约不实）。

**性质**：**pre-existing，非通用附件重构（feat/universal-attachment, merge e620643）引入**——旧 `/procedures/{id}/attachments` POST 端点本就是 `file` 单数；前端 `api/attachments.ts` 未被该重构改动。由通用附件特性的最终整体审查顺带发现。

**影响**：SOP 程序的附件上传不可用（每次 422）。下载/列表/删除不受此影响（字段/路径无失配）。

**建议修复（择一，须前后端对齐）**：
- **方案 A（推荐，支持多文件）**：后端别名 POST `/procedures/{id}/attachments` 改为接收多文件 `files: list[UploadFile] = File(...)`，循环 `upload_for(..., "procedure", ...)` 逐个落库，返回 `list[AttachmentOut]`（201）。与前端现状（多选 + 数组响应类型）对齐，体验更好。注意单/批量上限语义（现 30 个/200MB 总量校验需按"批量后累计"判断）。
- **方案 B（最小改动，单文件）**：前端 `uploadAttachment` 改为单文件：字段名 `file`、`File`（非数组）、返回 `AttachmentOut`；`AttachmentPanel.handleFiles` 改为逐个串行上传或限制单选。改动小但失去多文件体验。

**建议补测**：加一条前端↔后端的上传集成/契约测试（或 e2e），覆盖 SOP 附件上传成功路径，防止此类契约漂移再次无声发生。

**关联**：通用附件基础设施见记忆 `universal-attachment-spec-draft`；通用 `POST /api/v1/attachments`（认证端点）字段为 `file` 单数 + `entity_type/entity_id`，前端若接入需注意与此别名端点的差异。

**修复**：后端别名 POST 改多文件 `files: list[UploadFile]` + 返回 `list[AttachmentOut]`，与前端对齐；2026-06-02。
