# API 规范（API Specification）

> 本文件定义 Smart SOP 后端 HTTP API 的统一约定。所有路由必须遵守本规范。
>
> 业务语义详见 [feature-clarifications.md](feature-clarifications.md)。

## 1. 总体约定

| 项 | 约定 |
|---|------|
| 协议 | HTTPS（本地开发可 HTTP） |
| 风格 | RESTful + 资源 URL；不可表达的业务动作走子资源 / 动词 |
| 数据格式 | 请求 / 响应均 JSON；文件上传用 `multipart/form-data` |
| 字符集 | UTF-8 |
| 时间 | ISO 8601 UTC（`2026-05-19T10:23:45Z`） |
| 鉴权 | **本项目无登录**，所有接口匿名（部署信任边界 = 受控内网硬前提，Q322）；审计中间件捕获 IP / UA，**信任并解析 `X-Forwarded-For`**（配 `TRUSTED_PROXIES`，取最左侧非可信 IP）记真实客户端 IP；**追溯天花板 = IP / UA / 时间，无人身份**（Q324）|
| 版本 | 路径前缀 `/api/v1` |
| 文档 | FastAPI 自动生成 OpenAPI（`/docs` 与 `/redoc`） |
| 并发控制 | 写接口要求 `If-Match: <revision>` 头（Q18） |

## 2. URL 设计

### 2.1 风格

- 资源用复数名词：`/folders` / `/procedures`
- 资源 id 用 UUID 字符串
- 嵌套不超过 2 层
- 业务动作用动词子路径：`/procedures/{id}/deprecate`、`/procedures/{id}/upgrade-version`、`/procedures/{id}/rollback`
- 多词用 kebab-case：`/audit-logs` / `/apply-marks`

### 2.2 方法语义

| 方法 | 用途 | 幂等 |
|------|------|------|
| GET | 读 | ✅ |
| POST | 创建 / 触发动作 | ❌ |
| PUT | 全量更新 | ✅ |
| DELETE | 软删 | ✅ |

> 本项目 **PUT 用作全量更新**，禁用 PATCH。

## 3. 请求

### 3.1 通用 Header

```
Content-Type: application/json
Accept: application/json
X-Request-Id: <可选 uuid，便于全链路追踪>
If-Match: <revision>     # 写操作必须，未带 → 412
```

### 3.2 分页 / 排序 / 过滤

列表接口统一支持：

| 参数 | 类型 | 默认 | 说明 |
|------|------|-----|------|
| `page` | int | 1 | 从 1 |
| `page_size` | int | 20 | 最大 100 |
| `sort` | str | `-created_at` | 字段名，前缀 `-` 降序 |
| `search` | str | - | 子串搜索（大小写不敏感 `LIKE '%kw%'`，多词空格切分 AND）；`/procedures` 覆盖 code+name+description（§42 Q278/Q281）|

### 3.3 请求体约束

- 字段命名 snake_case
- 字符串字段必须有 `max_length`
- 时间字段用 ISO 8601 字符串

## 4. 响应

### 4.1 成功响应

返回 `2xx` + **裸 JSON 业务对象**：

```json
// GET /api/v1/folders/{id}
{
  "id": "8e3f...",
  "name": "质检流程",
  "prefix": "QC",
  "parent_id": null,
  "system": false,
  "full_path": "质检流程",
  "created_at": "2026-05-19T10:23:45Z",
  "updated_at": "2026-05-19T10:23:45Z"
}
```

### 4.2 列表响应

```json
{
  "items": [ ... ],
  "total": 128,
  "page": 1,
  "page_size": 20,
  "total_pages": 7
}
```

### 4.3 状态码

| 状态码 | 用途 |
|--------|-----|
| 200 OK | GET / PUT / 业务动作 |
| 201 Created | POST 创建 |
| 204 No Content | DELETE |
| 400 Bad Request | 业务错误 |
| 404 Not Found | 资源不存在 |
| 409 Conflict | 唯一约束 / 并发冲突 |
| 412 Precondition Failed | 缺少 If-Match |
| 413 Payload Too Large | 文件 / 内容超限 |
| 422 Unprocessable Entity | 校验失败 |
| 500 Internal Server Error | 异常 |

### 4.4 错误响应结构

```json
{
  "detail": {
    "code": "FOLDER_NAME_DUPLICATE",
    "message": "同一父目录下已存在该名称的文件夹",
    "field": "name"
  }
}
```

错误码完整清单见 [feature-clarifications.md §二十三](feature-clarifications.md#二十三最终错误码清单)。

---

## 5. 接口清单（v1）

所有路由前缀 `/api/v1`。

### 5.1 文件夹（folders）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/folders` | 列表 |
| GET | `/folders/tree` | 树形（含 `procedure_count` 统计）|
| GET | `/folders/options` | 下拉选项（id + name + full_path） |
| GET | `/folders/{id}` | 详情 |
| POST | `/folders` | 创建；**对含程序的目标父文件夹拒绝**（容器 xor 叶子，Q247，返 `FOLDER_HAS_PROCEDURES`）；可存程序的叶子 `prefix` 必填非空 + 全局唯一（Q248）|
| PUT | `/folders/{id}` | 更新；**编辑 `prefix` 不回填该文件夹已有程序 code，仅影响后续新建**（Q230）；改 prefix 走扩展唯一校验（Q249，含历史 code 用过的前缀）|
| DELETE | `/folders/{id}` | 软删（含子或程序时拒绝） |
| POST | `/folders/batch-delete` | 批量软删（原子，≤100 项，Q325） |
| GET | `/folders/check-name?parent_id=...&name=...` | 名称唯一性校验 |
| GET | `/folders/check-prefix?prefix=...&exclude_id=...` | 前缀唯一性校验；**校验范围含「历史 code 用过的前缀」**（Q249），命中返 `FOLDER_PREFIX_DUPLICATE` |

### 5.2 程序（procedures）

#### 基础 CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/procedures` | 列表（过滤：folder_id / status / search）；行内含 derived 字段 `version_count_in_group`（Q176，后端聚合，非 column）+ `folder_full_path`（derived from folder.full_path）|
| GET | `/procedures/library` | 已发布程序库（仅 status=PUBLISHED 且 is_current=true） |
| GET | `/procedures/{id}` | 详情**一次拉全部**（Q153）：含 procedure 元 + chapters 嵌套树 + steps + attachments + custom_values + active fields；详见下方 schema |
| POST | `/procedures` | 创建（自动生成 code，初始 version=1，新建 procedure_group_id） |
| PUT | `/procedures/{id}` | 更新（仅 is_current=true 且 status=DRAFT） |
| DELETE | `/procedures/{id}` | 软删（body: `{reason}` 必填）；对 `is_current=true AND status=DRAFT AND version>1` 走"丢弃 DRAFT"特殊路径，返 `{deleted_id, new_current_id, new_current_version}`（Q175 / [feature-clarifications.md §22.11](feature-clarifications.md#2211-draft-丢弃入口q175)）；其余按通用软删，is_current=true AND version=1 拒绝 `PROCEDURE_IS_CURRENT`；group 整体硬删走 `DELETE /procedure-groups/{group_id}`（详见下方版本管理章节） |
| POST | `/procedures/batch-delete` | 批量软删（原子，≤100 项，Q325） |
| POST | `/procedures/batch-move` | **批量移动到文件夹**（body: `{ids:[...], target_folder_id}`，原子，Q273）；目标仅 `system=false` 叶子文件夹（Q247），code 不变（Q22）|

> **列表查询**（程序库列表页 §41）：`GET /procedures` 复用 [§3.2](#32-分页--排序--过滤) `page`/`page_size`/`sort`/`search` + `folder_id`/`status` 过滤；列表页默认 `sort=-updated_at`；每 group 返回一行（is_current）+ derived `version_count_in_group`（Q176/Q267）。
> **搜索语义**（§42 Q278–Q281）：`search` 覆盖 `code`+`name`+`description` 子串（`LIKE`，多词 AND），**仅匹配 is_current**；传 `search` 时**忽略 `folder_id`、跨全库**，响应行附 `folder_full_path` 供前端显示路径列与命中高亮 / snippet。

**POST /procedures 请求体**（创建程序）：

```json
{
  "folder_id": "uuid",            // 必填，仅 system=false 的【叶子】文件夹（Q247；中间容器不可选）
  "name": "...",                  // 必填
  "level_of_use": "continuous",   // 必填，reference / continuous / information（Q182）
  "description": "...",           // 选填
  "risk_level": 3,                // 选填，默认 1
  "quality_level": 2,             // 选填，默认 1
  "custom_values": {}             // 选填，{field_key: value}
}
```

> **`template_id` 已移除（Q290 / §44；模板库亦废，[§56/Q340](feature-clarifications.md#五十六砍模板库纯-copy-自现有程序q340)）**：procedure template 功能彻底废弃，无模板、无模板库。`POST /procedures` 恒建**空白**程序；要「套结构」= 去任意现有程序走 `POST /procedures/{id}/copy`（复制为新程序，§18/Q179）。
- `level_of_use` 缺失或非枚举值返 `VALIDATION_FAILED`（422）（Q182 必填，无默认）。

**GET /procedures/{id} 响应 schema**（Q153 一次拉全部）：

```json
{
  "procedure": {
    "id": "uuid", "procedure_group_id": "uuid", "code": "QC-0001",
    "name": "...", "version": 3, "is_current": true,
    "status": "DRAFT", "folder_id": "uuid", "folder_full_path": "质检/检验",
    "description": "...", "risk_level": 3, "quality_level": 2,
    "level_of_use": "continuous",               // reference/continuous/information（Q182）
    "custom_values": {"field_key": "..."},
    "version_update_notes": "...",
    "signoff_enabled": false,                   // PDF 操作员签字栏总开关（程序级，受控文档属性）
    "revision": 7,                              // 用作 If-Match 来源
    "is_read": false, "read_at": null,
    "deprecated_from_folder_id": null,
    "deprecated_at": null,                      // group 整体废止时间，restore 时清空（Q180）
    "deprecated_by": null,                      // group 整体废止人，restore 时清空（Q180）
    "archived_at": null,                        // 该记录变 ARCHIVED 的时间，用于 read-only 视图 banner（Q174）
    "version_change_log": [],                   // 5 类里程碑追加（Q111；详见 data-model.md）
    "created_at": "...", "updated_at": "..."
  },
  "chapters": [
    /* 嵌套树：每个节点含 children */
    {"id": "uuid", "content_type": "chapter", "title": "1. 概述",
     "code": "1", "level": 1, "sort_order": 0, "skip_numbering": false,
     "mark_status": "unmarked", "rich_content": "",
     "children": [
       {"id": "uuid", "content_type": "content", "title": "",
        "rich_content": "<p>...</p>", "sort_order": 0, "children": []}
     ]}
  ],
  "steps": [
    /* 平铺；前端按 chapter_id 自挂载。step 字段重构见 §40（Q261-Q265）*/
    {"id": "uuid", "chapter_id": "uuid", "title": "启动电源",
     "code": "1.1.1", "content": "<p>...</p>", "sort_order": 0,
     "input_schema": {"type": "CHECK", "pass_label": "通过", "fail_label": "不通过"}, // 12 型大写枚举（Q261）
     "note": "<p>操作前熟悉流程</p>",      // 富文本警示·提示（Q263，蓝）
     "caution": "",                          // 富文本警示·小心（Q263，黄）
     "warning": "<p>高压未泄放可致死</p>",  // 富文本警示·警告（Q263，红）
     "attachment_marks": [{"name": "demo.mp4", "kind": "video", "note": ""}],    // Q203
     "skip_numbering": false}
     /* 已移除：mark_status（Q264 执行态→执行模块）、step_alerts（Q263→三字段）、notes（归入 note）、expected_output（无用预留字段）、require_confirmation（逐步确认改为程序级 signoff_enabled）*/
  ],
  "attachments": [
    {"id": "uuid", "file_name": "...", "size_bytes": 12345, "description": "...",
     "mime_type": "...", "sort_order": 0, "created_at": "..."}
  ],
  "fields": [
    /* 仅 status='active' 的 ProcedureField，用于程序详情面板渲染 */
    {"id": "uuid", "name": "风险类别", "key": "risk_category",
     "field_type": "select", "required": true,
     "options": [{"value": "high", "label": "高"}], "sort_order": 0}
  ]
}
```

> 此 schema 是编辑器加载唯一接口。后续保存接口 PUT /procedures/{id} 同样接受嵌套结构（含 chapters/steps/attachments id 映射）。

#### 状态与版本

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/procedures/{id}/transition` | 状态切换（body: `{status, reason?}`）；同 group 已有 PUBLISHED 时自动 ARCHIVED；非法转换返 `PROCEDURE_STATUS_INVALID`；v2+ 转 PUBLISHED 时 `version_update_notes` 为空返 `VERSION_UPDATE_NOTES_REQUIRED`（Q178 / [feature-clarifications.md §22.14](feature-clarifications.md#2214-publish-时-version_update_notes-是否必填q178)）|
| POST | `/procedures/{id}/upgrade-version` | 升级版本（fork 新 DRAFT 版本记录）；body 为空对象 `{}`，无 reason（Q165 / [§22.1](feature-clarifications.md#221-upgrade-version-输入策略q165)）；source 必须 `is_current=true AND status='PUBLISHED'`，否则返 `PROCEDURE_STATUS_INVALID`（Q173 / [§22.9](feature-clarifications.md#229-多-draft-与-upgrade--rollback-前提q173)）；达 `max_version_number` 返 `PROCEDURE_VERSION_MAX`，引导 copy（Q222 / §31.1）；并发已存在 DRAFT 时 DB 约束返 `PROCEDURE_DRAFT_EXISTS`(409)（Q224 / §31.3）|
| POST | `/procedures/{id}/rollback` | 回退（body: `{target_version, reason}`，reason 必填；source 必须 `is_current=true AND status='PUBLISHED'`，否则 `PROCEDURE_STATUS_INVALID`；target 必须 ARCHIVED + is_active=true + 同 group，否则 `ROLLBACK_TARGET_INVALID`；缺 reason 返 `ROLLBACK_REASON_REQUIRED`；并发已存在 DRAFT 时返 `PROCEDURE_DRAFT_EXISTS`(409)（Q224 / §31.3）；达 `max_version_number` 返 `PROCEDURE_VERSION_MAX`（Q222））|
| POST | `/procedures/{id}/deprecate` | 废弃**整 group**（所有版本 ARCHIVED + 移到「废止」+ 记 deprecated_from_folder_id；body: `{reason}` 必填）|
| GET | `/procedures/{id}/restore-preview` | 恢复前预检查（返 `{folder_exists, deprecated_from_folder_id, folder_full_path, version_count}`，详见 [feature-clarifications.md §22.5](feature-clarifications.md#225-restore-与-restore_folder_missing-交互q169)）|
| POST | `/procedures/{id}/restore` | 恢复（fork 新 DRAFT；body: `{reason, target_folder_id?}`；原 folder 已删时 target_folder_id 必填）|
| POST | `/procedures/{id}/copy` | **复制为新程序**（新 group_id、version=1）；body: `{target_folder_id, name?}`；**源 `{id}` 可为任意状态含 DRAFT**（Q293 扩展、§56/Q340 保留：copy 读源建新、源状态不阻塞——编辑器 ⋮ / 草稿箱行 / 历史只读视图均可作源）；目标 = `system=false` 叶子文件夹，code 按目标 prefix 重生成（Q139）|
| GET | `/procedures/{id}/version-history` | **本版本**的 `version_change_log` 数组（5 类里程碑：create/publish/rollback/deprecate/restore，§13.6 Q111）。与 `/procedure-groups/{group_id}/versions`（跨版本列表）职责区分：前者单版本时间线，后者 group 全景列表 |

**copy 接口详情**（Q137-Q140）：

```json
POST /procedures/{id}/copy
{
  "target_folder_id": "uuid",    // 必填，仅 system=false 文件夹
  "name": "..."                  // 选填，默认 = source.name + " (副本)"
}
```

后端动作：
- 复制**所传 `{id}` 那个版本**（Q238 修订 Q138，所见即复制；历史视图查 v2 即复制 v2，不取 is_current）的 chapters/steps/attachments/custom_values + 程序级字段 `level_of_use`（Q182）/ `risk_level` / `quality_level`（Q52，继承 source，[feature-clarifications §18.2 / Q339](feature-clarifications.md#182-复制范围q138)）
- 新 procedure_group_id、新 code（走 sequence_generator）、version=1、is_current=true、status=DRAFT、revision=0
- `chapter.mark_status`→unmarked、`is_read`→false / `read_at`→null（Q239 重置；`step.mark_status` 已移除 Q264，无需重置）
- `name` 默认 `源名 + " (副本)"`，**同名不去重**（Q240）
- audit_log 记 `action='copy_from'`、new_value 含 `{source_procedure_id, source_code, source_version}`（源侧不记审计、不加外键，Q241）
- version_change_log 首条 description = `复制自 {source_code} v{source_version}`

**deprecated group 限制**：调用 PUT / transition / upgrade-version / rollback / mark-read / deprecate / move folder 等修改类接口返 `PROCEDURE_DEPRECATED`（400）；GET / PDF / attachments/download / restore / DELETE 不受限制。

#### 版本列表与更新说明

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/procedure-groups/{group_id}/versions` | 同 group 所有版本列表（含每版本的 `version_update_notes` 预览前 100 字 + 完整内容 + `operator` + `created_at`）；可选 `?count_only=true` 仅返 `{count: N}` 用于 deprecate modal 等只需计数的场景 |
| DELETE | `/procedure-groups/{group_id}` | **硬删整 group**（body: `{reason}` 必填）；仅 `group 单记录 + v1 + DRAFT + is_current` 可删，否则 `PROCEDURE_GROUP_DELETE_FORBIDDEN`；成功返 `204 No Content`（Q177 / [§22.13](feature-clarifications.md#2213-v1-draft-完全删除q177)）|

> **不提供** 跨版本 diff 算法。用户在程序详情页通过 `version_update_notes` 字段**手填**本次更新的摘要与详细内容；
> 字段语义见 [feature-clarifications.md 三-A5](feature-clarifications.md#三补充功能-a-类决策)；
> UI 规范见 [editor-behavior.md](editor-behavior.md) 详情页章节。

**响应示例**：

```json
{
  "group_id": "uuid",
  "code": "QC-0001",
  "name": "启动 SOP",
  "items": [
    {
      "id": "uuid-v3",
      "version": 3,
      "status": "DRAFT",
      "is_current": true,
      "created_at": "2026-05-19T10:00:00Z",
      "version_update_notes": "本次更新...",
      "version_update_notes_preview": "本次更新..."
    },
    {
      "id": "uuid-v2",
      "version": 2,
      "status": "ARCHIVED",
      "is_current": false,
      ...
    }
  ]
}
```

#### PDF

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/procedures/{id}/pdf-layout` | 分页计算（JSON：总页数 + 元素/章节/step→页号 + TOC 页码 + 附件页码；前端预览层据此渲染逐页视图，Q235） |
| GET | `/procedures/{id}/pdf-download` | 下载（ReportLab 静态 PDF，文件名 `{code}_Rev{version}.pdf`） |

> **预览不再有后端 PDF 端点**（Q234）：旧 `POST /procedures/{id}/pdf-preview`（base64 + toc_data）**已删除**；预览改前端渲染层，正文数据复用 `GET /procedures/{id}`、分页骨架取 `GET /procedures/{id}/pdf-layout`。详见 [feature-clarifications.md §34](feature-clarifications.md#三十四pdf-预览前端渲染层落地q234q237)。
>
> **导出已勾选 PDF（Q236，预留未实现）**：`pdf-download` 请求体可选 `checked_ids: string[]`（前端当前勾选的 signoff / 确认 / 签名区 id），后端对命中项渲染 ☑、其余空框；本轮**不实现**，仅预留形态，带勾选输出由前端 `window.print()` 满足（Q213）。
>
> 完整渲染规格（封面/TOC/修订/内容/特殊元素/字体/性能）详见 [pdf-rendering.md](pdf-rendering.md)。
>
> 限流：表层 nginx 20 req/min/IP（`pdf-layout` / `pdf-download`）；超时：后端硬超时 60s（504 `PDF_TIMEOUT`）。

#### 阅读确认

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/procedures/{id}/mark-read` | 标记已读（修改 is_read 与 read_at） |
| GET | `/procedures/pending-read` | 待阅读列表（is_read=false） |
| GET | `/procedures/completed-read` | 已阅读列表（is_read=true） |

### 5.3 章节（chapters）

#### 基础 CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/chapters` | 列表（过滤：procedure_id / parent_id / content_type / mark_status） |
| GET | `/chapters/{id}` | 详情 |
| POST | `/chapters` | 创建（受 Q25 互斥校验） |
| PUT | `/chapters/{id}` | 更新 |
| DELETE | `/chapters/{id}` | 软删（递归子树）|

#### 排序与编号

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/chapters/{id}/move-up` | 上移（同 parent 内，到顶按钮 disabled）|
| POST | `/chapters/{id}/move-down` | 下移 |
| POST | `/chapters/{id}/move` | 跨 parent 移动（body: `{target_parent_id, target_index}`）|
| POST | `/chapters/{id}/toggle-skip-numbering` | 切换 skip_numbering |

#### 标记模式

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/chapters/{id}/mark-status` | 设置单个 mark_status（body: `{mark_status}`） |

#### 类型转换

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/chapters/{id}/convert-to-step` | 章节 → 步骤（子节点非空时拒绝）|
| POST | `/chapters/{id}/convert-to-content` | **已废弃**：章节模型重构（[§19](feature-clarifications.md#十九章节模型重构q149q152)）后返 **410 Gone** `CONVERT_TO_CONTENT_DEPRECATED` |
| POST | `/chapters/{id}/content-to-steps` | content 节点拆为多个 step（按顶层 HTML 块） |
| POST | `/chapters/batch-content-to-steps` | 批量拆（body: `{chapter_ids: [...]}`，原子） |
| POST | `/chapters/{id}/convert-root-to-step` | 根章节 → 步骤（特殊接口，与 convert-to-step 受同等约束）|

#### 应用标记

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/procedures/{id}/apply-marks` | 应用整个程序的所有 mark_status（原子事务，详见 Q9 / [editor-behavior.md](editor-behavior.md)） |

### 5.4 步骤（steps）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/steps` | 列表（过滤：procedure_id / chapter_id） |
| GET | `/steps/{id}` | 详情 |
| POST | `/steps` | 创建（受 Q25 互斥校验） |
| PUT | `/steps/{id}` | 更新 |
| DELETE | `/steps/{id}` | 软删 |
| POST | `/steps/{id}/move-up` | 上移（同 chapter 内）|
| POST | `/steps/{id}/move-down` | 下移 |
| POST | `/steps/{id}/move` | 跨 chapter 移动（body: `{target_chapter_id, target_index}`）|
| ~~POST~~ | ~~`/steps/{id}/mark-status`~~ | **已移除**（Q264 / §40.4）：执行态归执行模块，step 定义无 mark_status |
| POST | `/steps/{id}/toggle-skip-numbering` | 切换 skip_numbering |
| POST | `/steps/{id}/convert-to-chapter` | 步骤 → 章节（受 Q29 互斥校验，转换后 chapter 为原 step.chapter 的子节点） |

### 5.5 附件（attachments）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/procedures/{id}/attachments` | 列出某版本附件 |
| POST | `/procedures/{id}/attachments` | 上传（multipart，字段 `file` + 可选 `description`）；**仅 `is_current=true AND status=DRAFT`**，否则 `PROCEDURE_READONLY`/`PROCEDURE_DEPRECATED`（Q228）|
| GET | `/attachments/{id}/download` | 下载（响应附件原始字节）；**一律 `Content-Disposition: attachment`** 强制下载、不内联渲染（Q226 防 XSS）；任意类型；含 deprecated group 也可下载（Q118，不受只读限制）|
| GET | `/attachments/{id}/preview` | **在线预览**（Q229）：`Content-Disposition: inline`，**仅白名单类型** `image/png` `image/jpeg` `image/gif` `image/webp` `application/pdf`；非白名单返 `415`（前端不展示预览入口）；deprecated 也可预览 |
| PUT | `/attachments/{id}` | 修改元数据（仅 description / sort_order；仅当前版本生效，不传播）；**仅 `is_current=true AND status=DRAFT`**，否则 `PROCEDURE_READONLY`/`PROCEDURE_DEPRECATED`（Q228）|
| DELETE | `/attachments/{id}` | 软删（文件保留供其他版本引用）；**仅 `is_current=true AND status=DRAFT`**，否则 `PROCEDURE_READONLY`/`PROCEDURE_DEPRECATED`（Q228）|
| POST | `/procedures/{id}/assets` | **编辑器图片直传**（§29.1/Q214，multipart `file`）：WangEditor 插图时上传，后端按 sha256 去重入 `tb_procedure_asset`、即时入库，返回 `{asset_id, url, width, height}`；EMF/WMF 经 LibreOffice 转 PNG（Q216）；单图 > 10MB → `IMAGE_TOO_LARGE`（Q215）|
| GET | `/procedures/{id}/assets/{asset_id}` | **图片资源服务**（§25.2/Q189）：响应 `tb_procedure_asset` 原始字节，供 rich_content `<img src>` 引用；与附件不同，asset 是富文本内嵌图，按 sha256 去重、ref_count GC（§3.10/§3.11）|

**限制**（Q120）：

| 维度 | 限制 |
|------|------|
| 单文件大小 | ≤ 50 MB |
| 单 procedure 数量 | ≤ 30 |
| 单 procedure 总大小 | ≤ 200 MB |

超限返 `ATTACHMENT_LIMIT_EXCEEDED`。同名 file_name 允许并存。

**版本传递规则**（Q113 / Q117）：

- upgrade-version：复制 source.is_current=true 的全部 attachments 元数据（storage_path 复用）
- rollback：复制 **target_version** 的 attachments（不是 current 的）
- copy：复制**所传 `{id}` 那个版本**的 attachments（Q238 修订 Q138，不取 is_current）

**磁盘清理**：独立 `scheduler` 进程每日任务扫描未被任何 `is_active=true` 引用 + 软删 ≥ 30 天的 storage_path → 文件先删 + 行文件同删（Q331/Q332/§53）。详见 [feature-clarifications.md §14](feature-clarifications.md#十四附件版本传递q113q120) 与 [§53](feature-clarifications.md#五十三后台任务调度与清理q331q334)。

### 5.6 Word 解析与导入（parse）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/uploads` | **上传 .docx 到临时区**（multipart `file`），返回 `{upload_token, expires_at}`；24h 后清理（Q141）|
| GET | `/parse/methods` | 列举支持的解析方法（仅 `standard` / `smart` 两种）|
| POST | `/parse` | 解析（body: `{upload_token, parse_mode}`）→ 返回预览 JSON，**不落库** |
| POST | `/procedures/import` | 导入解析结果（body: `{name, folder_id, chapters[]}`）创建新程序 |

> 详细映射规则与边界识别见 [feature-clarifications.md §9](feature-clarifications.md#九word-解析映射规则q33q40)。

#### POST `/parse` 请求（两步式 Q141）

```
Content-Type: application/json

{
  "upload_token": "<token from POST /uploads response>",
  "parse_mode":   "standard" | "smart"   // 默认 "smart"
}
```

> 文件本身由前置 `POST /uploads` 上传（multipart），返回 `upload_token`；`/parse` 仅引用 token，不再重复传文件。

#### POST `/parse` 响应（不含 procedure.name，Q38）

```json
{
  "metadata": {
    "author": "...",
    "totalChapters": 12,
    "imageCount": 3,
    "tableCount": 2,
    "parseTime": 145,
    "format": "docx",
    // 正文起点判定来源（§25.4/Q191/Q196 取代旧 section_break 规则）
    "bodyStartDetectedBy": "first_styled_heading" | "toc_field_end" | "heuristic_heading" | "cover_skip",
    "bodyStartIndex": 53
  },
  "chapters": [
    {
      "id": "uuid-临时",
      "type": "chapter",
      "title": "概述",
      "level": 1,                            // 层级 1–3（§25.3/Q190 二次修订回 3；H4-6 压 L3）
      "order": 0,
      "parentId": null,
      "contentType": "chapter",
      // 图片为 URL 引用（§27/Q189），表格为标准 HTML 含 rowspan/colspan + 表内 <img>（Q205）
      "richContent": "<p>文字<img src=\"/api/.../assets/<id>\">文字</p><table>...</table>",
      "skipNumbering": false,
      // 置信度分级（§25.5/Q199）：HIGH 免确认；MEDIUM/LOW → markStatus='review'
      "confidence": 1.0,                     // 0.0–1.0
      "confidenceTier": "high" | "medium" | "low",
      "markStatus": "unmarked" | "review",   // high→unmarked；medium/low→review
      "headingSource": "style" | "synonym" | "outline" | "based_on" | "heuristic",
      "children": [...]
    }
  ],
  // parse 阶段抽出的临时图片（落 tmp/uploads/{token}/media/，import 时按 sha256 提升为永久 asset，§25.2/Q193）
  "assets": [
    { "tempId": "uuid", "url": "/api/uploads/<token>/media/<file>", "sha256": "...",
      "mime": "image/png", "sizeBytes": 20480, "width": 800, "height": 600 }
  ],
  // 零样式文档的编号模式建议，供前端「一键批量提升」（§25.5/Q200）
  "detectedPatterns": [
    { "pattern": "L1_中文顿号", "suggestedLevel": 1, "count": 5,
      "sampleTitles": ["一、危险源：火灾", "二、危险源：触电"] }
  ],
  "validation": {                              // 仅 standard 模式有
    "passed": true,
    "level": "pass" | "warning" | "error",
    "rules": [...],
    "summary": "校验通过"
  },
  "errors": [],
  "warnings": [
    { "stage": "boundary", "message": "正文起点经 first_styled_heading 定位于第 53 块，前 53 块作为封面/目录跳过" }
  ],
  "reviewRequired": 3,                          // 需用户确认的 medium/low 候选数（§25.5/Q199）
  "parseMethod": "smart"
}
```

> **图片生命周期**：`/parse` 返回的 `assets[].url` 指向临时区；`POST /procedures/import` 时后端按 sha256 去重提升为永久 `tb_procedure_asset`，并把 richContent 内的临时 URL 改写为永久 `/api/procedures/{id}/assets/{asset_id}`，同时写 `tb_procedure_asset_reference`（§25.2/Q193/Q197）。未 import 的临时图随 token 过期清理。
>
> **置信度与 review**：`smart` 模式下 medium/low 候选标 `markStatus='review'`，import 前必须全部清空（用户确认/调级/降为 content），否则拒绝（沿用既有强制约束，§25.5/Q199）。零样式文档（styles.xml 零命中）不再直接返回空 chapters；若启发式也零命中才触发 `PARSE_NO_HEADINGS`。

#### POST `/procedures/import` 请求

```json
{
  "name": "<必填，前端默认填文件名去扩展名>",
  "folder_id": "uuid",
  "description": "",
  "chapters": [ ... ]   // 直接复用 /parse 返回的 chapters，用户可在向导中调整
}
```

> 后端**始终调用 sequence_generator 重新生成 code**（Q-C5），即使原文档有 code 也不复用。

#### POST `/procedures/import` 响应

```json
{
  "id": "uuid",
  "procedure_group_id": "uuid",
  "code": "QC-0001",
  "name": "...",
  "version": 1,
  "is_current": true,
  "status": "DRAFT",
  ...
}
```

#### 错误码（解析与导入专用）

| 错误码 | HTTP | 触发场景 |
|--------|------|---------|
| `PARSE_FILE_INVALID` | 400 | 非 .docx 格式 |
| `PARSE_FILE_TOO_LARGE` | 413 | > 50MB |
| `PARSE_FAILED` | 400 | 解析过程异常（含详情）|
| `PARSE_TEMPLATE_INVALID` | 400 | standard 模式模板校验未通过（含 validation 报告）|
| `VALIDATION_FAILED` | 422 | /procedures/import 未填 name 或必填字段缺失 |
| `PARSE_NO_HEADINGS` | 400 | 解析后 chapters=[]（文档无 heading） |
| `PARSE_TIMEOUT` | 504 | 后端解析超过 30 秒 |
| `UPLOAD_TOKEN_INVALID` | 400 | upload_token 不存在或已过期 |

### 5.7 自定义字段（procedure-fields）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/procedure-fields` | 列表（过滤：field_type / status） |
| GET | `/procedure-fields/options` | 字段选项数据 |
| GET | `/procedure-fields/{id}` | 详情 |
| POST | `/procedure-fields` | 创建 |
| PUT | `/procedure-fields/{id}` | 更新（**key 与 field_type 不可改**，分别返 `FIELD_KEY_IMMUTABLE` / `FIELD_TYPE_IMMUTABLE`；options 删除 = 软代理 archived 保留旧值；validation_rules / required 改变仅约束新保存）|
| DELETE | `/procedure-fields/{id}` | 软删 |
| POST | `/procedure-fields/update-status` | 批量改 status（body: `{ids: [...], status: 'active'|'archived'}`） |
| POST | `/procedure-fields/batch-delete` | 批量软删（原子，≤100 项，Q325）|
| POST | `/procedure-fields/reorder` | 重新排序（body: `{ordered_ids: [...]}`） |

### 5.8 设置（settings）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/settings` | 获取全局设置（单例；与 `/settings/current` 等价，二选一稳定即可） |
| GET | `/settings/current` | 同 `/settings` 的 alias，命名向 dpms 兼容（前端 store hydrate 时偏好 `/settings`） |
| PUT | `/settings` | 更新（必须带 If-Match）；**任何人可改（无登录）**，但写 `tb_procedure_audit_log`（`action='settings_update'` + old/new value + IP/UA）；前端保存前二次确认（Q233）。可改字段：`enable_approval_workflow`（Q242 审批开关）/ `max_version_number` / `require_read_confirmation` / `default_risk_level` / `default_quality_level`（Q260）。隐藏不可改：`enable_version_control` 恒 true（Q232）、`auto_archive_days` 待 Phase 9（Q259）|

### 5.9 审计日志（audit-logs）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/audit-logs/folders` | 文件夹审计 |
| GET | `/audit-logs/procedures` | 程序 / 章节 / 步骤 / 附件 审计（全归此表）|

**过滤参数**（Q126）：

| 参数 | 类型 | 说明 |
|-----|------|------|
| `target_id` | uuid | 单个目标（procedure 版本 id 或 folder id）|
| `procedure_group_id` | uuid | 仅 /procedures：查整族跨版本历史 |
| `action` | string | 单 action 或逗号分隔多个 |
| `date_from` / `date_to` | ISO 8601 | 时间区间 |
| `ip_address` | string | 排查异常 IP |
| `page` / `page_size` | int | 分页 |

详细规范见 [feature-clarifications.md §15](feature-clarifications.md#十五审计日志颗粒度q121q128)。

**查看 UI 相关**（§43）：

- 两个 GET 端点**只读、匿名可看**（与全站无登录一致，Q289）；审计记录不可改 / 不可删（永久保留 Q125），无写接口。
- **导出**（Q288）：加 `export=csv` 参数 → 带相同过滤、**流式导出 CSV、忽略分页**（合规留档，不截断数据）。
- 前端查看页（[editor-behavior.md §21](editor-behavior.md)）：全局页 + 对象详情深链预填 `procedure_group_id` / `target_id`（Q284）；行展开 `old_value`/`new_value` 字段级 diff（Q287）。

### 5.10 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/healthz` | 应用存活（无 DB 检查） |
| GET | `/readyz` | 应用就绪（含 DB 连通） |

---

## 6. 审计中间件

```python
@app.middleware("http")
async def audit_context_middleware(request, call_next):
    request.state.ip = request.client.host
    request.state.user_agent = request.headers.get("user-agent", "")
    return await call_next(request)
```

service 层调用 `audit_service.record(action, target_id, old, new, reason, ip, ua)` 写日志。

---

## 7. 文件上传

| 项 | 约束 |
|----|------|
| Word 解析（.docx） | ≤ 50 MB；MIME `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| 附件 | ≤ 50 MB；任意 MIME |
| 字段名 | `file` |
| 服务器解析超时 | 30 s |

---

## 8. 限流（生产，Q323）

由反向代理（nginx）层做基础 IP 限流（**后端不内置**）：

```
/api/v1/uploads:                        10 req/min/IP   # 上传最重、防灌盘
/api/v1/parse:                          10 req/min/IP
/api/v1/procedures/{id}/pdf-*:          20 req/min/IP
/api/v1/procedures/{id}/apply-marks:    30 req/min/IP
写操作（其余 POST/PUT/DELETE）:           60 req/min/IP   # 防匿名刷写 / 手滑
读操作（GET）:                            300 req/min/IP
```

> 信任边界 = 受控内网硬前提（Q322）；限流只防量，破坏性操作护栏靠软删 + restore + 审计（Q325）。真实客户端 IP 解析见 §1 鉴权（X-Forwarded-For / `TRUSTED_PROXIES`，Q324）。

---

## 9. CORS

- 开发环境：允许 `http://localhost:5173`
- 生产环境：通过 `.env` 配置 `CORS_ORIGINS`

---

## 10. OpenAPI 文档质量

- 每个 router 函数必须有 docstring
- 每个 schema 字段必须 `Field(..., description="...")`
- 错误码在 docstring 中以 markdown 列出
- `tags` 按资源分组，与 routers 文件一一对应

---

## 11. 与 spec 的差异点

下表列出本规范相对于 [06-程序管理模块功能说明.md](../06-程序管理模块功能说明.md) 的偏离，便于后续追溯：

| Spec 中的接口 / 字段 | 本规范处理 | 原因 |
|---------------------|----------|------|
| `submit-approval` / `timeline` | 移除 | B3 砍审批 |
| `approval_status` / `approval_template` / `workflow_instance` | 移除 | B3 |
| `read_by` M2M | 退化为 `is_read` + `read_at` 单标志 | B2 |
| `creator` FK(User) | 移除 | 无用户体系 |
| `ProcedureStep.meter` FK | 移除 | B4 |
| 程序下发 `distribute/*` | 移除 | spec 自标记未实现 |
| `create_mode` | 移除（只留 version_control） | C1 |
| `procedure_group_id` / `is_current` | 新增 | B1（多版本模型）|
| `revision` 字段 | 新增 | Q18 乐观锁 |
| `custom_values` 字段 | 新增 | Q17 |
| `risk_level` / `quality_level` | 新增 | PDF 封面 |
| `tb_procedure_attachment` 表 | 新增 | A10 |
| 章节最大嵌套层级 | 3 级（spec 矛盾时按 §3.7） | C7 |
| 子节点类型互斥规则 | 严格三选一 | Q25 |
| 编号生成位置 | 后端保存时整树重算 | C4 |
| `chapters/{id}/move` 跨 parent 端点 | 新增 | Q26 跨级移动需求 |
| `procedure-groups/{group_id}/versions` 接口 | 新增 | A5 版本列表（含 version_update_notes）|
| `version_update_notes` 字段 | 新增 | A5 用户手填更新说明（取代 diff 算法）|
| `procedures/{id}/rollback` 接口 | 新增 | A6 |
| `apply-marks` 接口 | 新增 | Q3 / Q9 |
| `If-Match` 强制要求 | 新增 | Q18 |
