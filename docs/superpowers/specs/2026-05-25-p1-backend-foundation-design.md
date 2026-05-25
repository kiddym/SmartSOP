# P1 · 后端基座 设计

**日期：** 2026-05-25
**状态：** 已批准
**作者：** 协作设计（cui_yuming + Claude）
**上位文档：** `2026-05-25-unified-create-edit-model-overview-design.md`（北极星总览）

---

## 1. 背景：现状已具备大半

探查后端（FastAPI + SQLAlchemy + MySQL/SQLite，Alembic 迁移）后确认，统一模型里的"草稿生命周期"**大部分已经存在**：

- `POST /procedures/import`（`import_service.import_procedure`）**已把导入的程序落库为 `status="DRAFT"`**。
- 状态机 **`DRAFT →(transition)→ PUBLISHED → ARCHIVED`** 已存在（`procedure_service`，`/procedures/{id}/transition`）；仅 `DRAFT` 可编辑（`_assert_editable`）。
- 列表 `GET /procedures` **已支持按 `status` 过滤**。
- 资产机制完备（`tb_procedure_asset`，sha256 去重、引用表、GC）；导入时图片已 `promote_temp` 成永久资产。
- APScheduler 调度器在跑（上传临时目录 24h 清理等）。

**因此 P1 不重做生命周期**，只补齐缺口。

## 2. P1 的决定（来自 brainstorm）

- **D1 ·「完成」= 现有「发布」(PUBLISHED)**：导入→DRAFT→（清待确认）→点完成即走现有 `transition` 到 PUBLISHED；正式后锁定、再改开新版本。P1 **不改状态机**。（"完成时若仍有待确认则拦截"属于 P2 编辑器「完成」按钮的校验。）
- **D2 · 原始 docx 永久存储**：按 **procedure_group** 存（一次导入归属整个版本组，任何版本可追溯回同一份源 Word）；**单独建表 `tb_procedure_source_docx`**（不塞进图片中心的 asset 表）；加取回端点。空白新建的程序无 docx。
- **D3 · 清理 = C（不自动清）**：无调度清理任务；改为"列表草稿过滤 + 手动/批量删除"。P1 只负责**后端能删除当前的、从未发布过的 DRAFT**；列表过滤 UI 与批量删除入口属于 P3。

**从 P1 挪走（→ P2）：** 节点"置信度 / 降型藏存"的 schema——与 P2 编辑器功能耦合，迁移随 P2 做。待确认本就靠现有 `chapter.mark_status='review'` 持久化，P1 无需新字段。

## 3. 目标与非目标

**目标**
1. 导入时把原始 `.docx` 永久存下，按程序（组）可取回，供编辑器预览栏渲染、长期追溯。
2. 让当前的、从未发布过的 DRAFT 可被手动删除（支撑 C 的人工清理）。

**非目标（本 Phase 不做）**
- 编辑器从 draft 加载 / 预览栏 / 层级标定 / 待确认 UI / 「完成」按钮 —— 全在 P2。
- 列表"草稿"过滤 UI、批量删除入口 —— P3。
- 自动清理调度任务 —— 按 D3 不做。
- 节点置信度 / 降型藏存 schema —— P2。
- 重新导入覆盖已有程序 —— 不支持。

## 4. 数据模型

### 4.1 新表 `tb_procedure_source_docx`

按 procedure_group 归属，每组至多一份源 docx。

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | String(36) PK (UUIDMixin) | |
| `procedure_group_id` | String(64), unique, indexed, not null | 归属版本组（对应 `tb_procedure.procedure_group_id`） |
| `filename` | String(255) | 上传时的原始文件名（展示/下载用） |
| `storage_path` | String(500) | 相对存储根的路径 |
| `sha256` | String(64) | 完整性校验（不做跨组去重） |
| `size_bytes` | BigInteger | |
| `created_at` | TimestampMixin | |

- 复用 `UUIDMixin` + `TimestampMixin`（与现有模型一致；不需要 SoftDelete）。
- **唯一约束 `procedure_group_id`**：一组一份；重复导入到新组各自一份。
- 不建外键到 `tb_procedure`（`procedure_group_id` 本身不是 FK，与现有约定一致）。

### 4.2 存储路径

落盘到 `{storage}/source_docx/{procedure_group_id}/source.docx`（沿用 `app/storage.py` 的存储根推导风格，新增一个 `source_docx_root`）。

### 4.3 Alembic 迁移

新增一条迁移：创建 `tb_procedure_source_docx` 表 + `procedure_group_id` 唯一索引。

## 5. API 与服务改动

### 5.1 `ImportRequest` 增加 `upload_token`

- `schemas/parse.py`（或 import 请求所在）`ImportRequest` 增加可选字段 `upload_token: str | None = None`。
- 前端导入时传上传步骤拿到的 token（见 5.4）。

### 5.2 `import_service.import_procedure` 存 docx

- 入参接收 `upload_token`。
- 创建 DRAFT 程序后，若 `upload_token` 有值且对应临时 `source.docx` 仍在（未过期）：
  - 读取 `{tmp}/uploads/{token}/source.docx`；
  - 拷贝到 `{storage}/source_docx/{group_id}/source.docx`；
  - 写入 `tb_procedure_source_docx`（group_id、filename 取自上传 meta、sha256、size）。
- **优雅降级**：token 缺失或临时文件已过期 → 不存 docx、不报错（与现有图片 `promote_temp` 的降级一致）。
- 新建 `services/source_docx_service.py` 承载存/取逻辑（与 `asset_service` 平行、互不耦合）。

### 5.3 取回端点 `GET /procedures/{procedure_id}/source-docx`

- 由 `procedure_id` → 查其 `procedure_group_id` → 查 `tb_procedure_source_docx` → 读盘返回原始字节。
- 响应头：`Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document`；`Content-Disposition: inline; filename="<原始名>"`。
- 无源 docx（空白新建 / 导入时未存）→ 404（前端据此不显示预览栏）。
- 前端（P2 预览栏）将以 blob 取回后用 `docx-preview` 的 `renderAsync` 渲染（与现有 `WordPreviewPanel` 同一渲染路径）。

### 5.4 让现有导入立即受益（小尾巴）

- 更新前端 `api/parse.ts` 的 `importProcedure` 调用，把 `upload_token` 一并发出；`ImportDialog.vue`/`useImportDialog.ts` 在上传时已持有 `uploadToken`，透传即可。
- 这样**当前 beta2 导入也能立刻产生可追溯的 docx**，不必等到 P3。（纯增量，不改 beta2 其它行为。）

### 5.5 允许删除当前的未发布 DRAFT

- 现有 `procedure_service.delete_procedure()` 对 `is_current=true` 一律拒绝（`PROCEDURE_IS_CURRENT`）。
- 放宽：当程序是 **`is_current=true` 且 `status="DRAFT"` 且该组从未有过 PUBLISHED 版本**（即纯草稿、唯一版本）时，**允许删除**——删除程序及其章节/步骤；并删除该组的 `tb_procedure_source_docx`（含落盘文件）。
- 其它情况（当前 PUBLISHED 版本等）维持现拒绝行为不变。
- 实现者须先读现 `delete_procedure` 实际逻辑确认精确条件再放宽。

## 6. 边界与错误处理

- **无图片的文档**：现在靠图片 URL 反推 token，无图就拿不到 token；5.1 显式传 token 解决。
- **token 过期**：导入时临时 docx 可能已被 24h 清理 → 降级不存（5.2）。
- **空白新建**：无 docx；取回端点 404；删除走 5.5。
- **重复导入**：每次导入建新组、各存一份；不做覆盖/去重。
- **删除已发布或非当前版本**：维持现有行为（5.5 只放宽纯草稿）。

## 7. 测试（pytest，参照 `tests/integration/test_word_import.py`）

- **存 + 取**：upload → parse → import（带 token）→ 断言 `tb_procedure_source_docx` 有行、文件落盘；`GET /procedures/{id}/source-docx` 返回 200 + 正确 content-type + 字节非空。
- **降级**：import 不带 token（或 token 过期）→ 不建行、不报错；取回 404。
- **追溯跨版本**（若版本流易于构造）：同组新版本仍能取回源 docx。
- **删除纯草稿**：create/import 一个 DRAFT → `DELETE` 成功；source docx 行与文件被清。
- **删除保护**：PUBLISHED 当前版本 → `DELETE` 仍拒绝。
- 迁移：在测试 DB（SQLite）上能 `upgrade` 建表。

后端 Gate：`cd backend && pytest`（按仓库现有测试命令）。

## 8. 文件清单（预估）

- 新建 `backend/app/models/source_docx.py`（`tb_procedure_source_docx`）。
- 新建 `backend/alembic/versions/<ts>_add_source_docx.py`。
- 新建 `backend/app/services/source_docx_service.py`（存/取/删）。
- 改 `backend/app/schemas/parse.py`：`ImportRequest` +`upload_token`。
- 改 `backend/app/services/import_service.py`：接收 token、调用 source_docx_service 存盘。
- 改 `backend/app/routers/procedures.py`：新增 `GET /{id}/source-docx`；删除端点放宽纯草稿。
- 改 `backend/app/services/procedure_service.py`：`delete_procedure` 放宽 + 连带删 source docx。
- 改 `backend/app/storage.py`：新增 `source_docx_root`。
- 改前端 `frontend/src/api/parse.ts` + 导入调用处：透传 `upload_token`。
- 测试：`backend/tests/integration/test_source_docx.py`（或并入 `test_word_import.py`）。
