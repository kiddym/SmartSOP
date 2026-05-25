# 数据模型（Data Model）

> 本文件描述 Smart SOP 的完整数据模型。共 **10 张业务表 + 2 张审计表**（`tb_procedure_template` 已删除，Q290/§44）。
>
> 涉及决策的细节请参考 [feature-clarifications.md](feature-clarifications.md)。

## 1. 整体 ER

```
                ┌────────────────────┐
                │     tb_folder      │◄────────┐
                │  树形 max_depth=5  │         │ parent_id
                └────────┬───────────┘         │
                         │ 1                   │
                ┌────────▼───────────┐         │
                │ tb_folder_sequence │         │
                │ (1:1 编号生成器)   │         │
                └────────────────────┘         │
                                                │
                ┌───────────────────────────────┘
                │ folder_id
        ┌───────▼─────────────────┐
        │     tb_procedure        │
        │  procedure_group_id     │◄───┐
        │  is_current 标记当前版本│    │ 同 group
        └────┬───────┬──────┬─────┘    │ 多版本
             │       │      │          │
             │       │      └──────────┘
             │       │
   chapter_id│       │ procedure_id
             │       │
   ┌─────────▼┐ ┌────▼──────────────────┐
   │tb_proc_  │ │ tb_procedure_chapter  │◄─┐
   │step      │ │ 自引用，content_type  │  │ parent_id
   │          │ │ chapter / content     │  │ max 3 级（Q190 二次修订 6→3）
   └──────────┘ └───────────────────────┘  │
                                            │
                                            └─（自引用）

   ┌──────────────────────────┐
   │ tb_procedure_attachment  │  procedure_id → tb_procedure（挂在版本）
   └──────────────────────────┘

   ┌──────────────────────┐   ┌────────────────────────────┐
   │ tb_procedure_asset   │◄──│ tb_procedure_asset_reference│
   │ 图片二进制(sha256去重)│ M:N│ (asset_id, procedure_id)    │
   └──────────────────────┘   └────────────────────────────┘
     rich_content 内 <img src="/api/.../assets/{id}"> 引用（§25.2/Q189/197）

   ┌─────────────────────┐    ┌──────────────────────┐
   │ tb_procedure_field  │    │ tb_procedure_settings│
   │ 全局自定义字段定义  │    │ 全局单例             │
   └─────────────────────┘    └──────────────────────┘

   ┌──────────────────────┐   ┌──────────────────────┐
   │ tb_folder_audit_log  │   │ tb_procedure_audit_  │
   │ 追加表（仅记 IP/UA） │   │ log（同左）          │
   └──────────────────────┘   └──────────────────────┘
```

## 2. 命名与公共字段

| 项 | 约定 |
|----|------|
| 表名前缀 | `tb_` |
| 主键 | UUID v4，应用层生成（`CHAR(36)`） |
| 软删 | `is_active BOOLEAN` + `deleted_at DATETIME NULL` |
| 时间戳 | `created_at` / `updated_at`（`DATETIME(6)`，UTC）|
| JSON 字段 | MySQL 8.0 原生 JSON 类型 |

所有业务表继承上述公共字段（审计日志表例外，仅 `created_at`）。

---

## 3. 表定义

### 3.1 `tb_folder` — 文件夹

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | CHAR(36) | PK | UUID v4 |
| `name` | VARCHAR(100) | NOT NULL | 名称 |
| `prefix` | VARCHAR(20) | NOT NULL DEFAULT '' | 程序编码前缀（如 `QC`）；**叶子（可存程序）文件夹必填非空 + 全局唯一**（Q248 **修订 Q231**，取消「空 prefix=纯序号」）；**中间容器文件夹恒空**（Q247）；**编辑不回填已有 code、仅影响后续新建**（Q230）；**一经生成过 code 即永久占用、不可被其它文件夹复用**（Q249）|
| `parent_id` | CHAR(36) NULL | FK → tb_folder.id | NULL = 根 |
| `system` | BOOLEAN | NOT NULL DEFAULT FALSE | 系统文件夹（如「废止」）禁止删除 / 改名 |
| `full_path` | TEXT | NOT NULL DEFAULT '' | 缓存（如 `质检 / 检验流程`）|
| `is_active`、时间戳 | | | |

**约束**：

- 最大嵌套深度 5（应用层校验）
- 同 parent_id 下 name 唯一（generated column + 唯一索引模拟 partial unique）
- 全 path 唯一
- 移动操作循环引用检测
- **删除策略：硬约束**（Q-B9）—— 含子文件夹或程序即拒绝
- **「标准文件库」**= `system=false` 文件夹树的前端统称（Q246），不引入新表 / 字段
- **容器 xor 叶子**（Q247）—— 程序仅能存于叶子文件夹；**含程序的文件夹禁止新增子文件夹**（应用层校验，拒绝返 `FOLDER_HAS_PROCEDURES`）；中间容器文件夹 `prefix` 恒空、无 `tb_folder_sequence`
- **叶子 prefix 必填非空 + 全局唯一**（Q248）；**prefix 永久占用**（Q249）—— `check-prefix` / 分配 / 改 prefix 的唯一性校验**扩展**到「该 prefix 既不属任何其它文件夹、也从未被任何现存 `tb_procedure.code` 用过」，命中拒绝**复用** `FOLDER_PREFIX_DUPLICATE`（消息扩为「前缀已被占用，含历史程序使用过的前缀」）

### 3.2 `tb_folder_sequence` — 编号序列

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | CHAR(36) | PK | |
| `folder_id` | CHAR(36) | FK UNIQUE | 一对一 |
| `current_value` | INT | NOT NULL DEFAULT 0 | 当前序号 |
| `sequence_digits` | INT | NOT NULL DEFAULT 5 | 补零位数；**默认 4→5**（Q250，生成 `00001`），每叶子可配 |
| `reset_period` | VARCHAR(20) | NOT NULL DEFAULT 'never' | **固定 never、不暴露**（Q251）—— 序列只增不重置；code=`{prefix}-{seq}` 不含年 / 月，重置必重号撞车，故去掉重置配置 |
| `last_reset_at` | DATETIME(6) NULL | | 上次重置时间（reset_period 固定 never 后不再使用，Q251）|
| `is_active`、时间戳 | | | |

**业务规则**：

- 生成下一个编号用 `SELECT ... FOR UPDATE` 行锁
- ~~满足重置条件归零 + 更新 `last_reset_at`~~ —— **Q251 起 reset_period 固定 never，不再有周期重置逻辑**
- 仅叶子文件夹有 `tb_folder_sequence` 记录（中间容器无，Q247）
- 溢出（current + 1 > 10^digits - 1）重置为 1 + WARN 日志
- 返回格式 `f"{n:0{digits}d}"`

### 3.3 `tb_procedure` — 程序主表（多版本模型）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | CHAR(36) | PK | |
| `procedure_group_id` | CHAR(36) | NOT NULL INDEX | **同一逻辑程序的版本族标识** |
| `is_current` | BOOLEAN | NOT NULL DEFAULT TRUE INDEX | 同 group 仅一条 true |
| `folder_id` | CHAR(36) | FK → tb_folder.id | |
| `code` | VARCHAR(100) | NOT NULL | 程序编码（同 group 共享）；由叶子文件夹 `folder_sequence` 生成 `{prefix}-{seq}`（如 `QC-00001`，默认 5 位 Q250）；**叶子 prefix 必填非空**（Q248 **修订 Q231**——不再有「纯序号无前缀」格式）|
| `name` | VARCHAR(200) | NOT NULL | 程序名称 |
| `version` | INT | NOT NULL DEFAULT 1 | 整数版本号 |
| `version_change_log` | JSON | NOT NULL DEFAULT '[]' | 见下方 |
| `description` | TEXT | NOT NULL DEFAULT '' | |
| `status` | VARCHAR(20) | NOT NULL DEFAULT 'DRAFT' | **DRAFT / PUBLISHED / ARCHIVED**（三态干净版）|
| `is_read` | BOOLEAN | NOT NULL DEFAULT FALSE | 全局已读标志（无用户）|
| `read_at` | DATETIME(6) NULL | | |
| `custom_values` | JSON | NOT NULL DEFAULT '{}' | 自定义字段值，结构 `{field_key: value}` |
| `risk_level` | INT | NOT NULL DEFAULT 1 | PDF 封面用 |
| `quality_level` | INT | NOT NULL DEFAULT 1 | PDF 封面用 |
| `level_of_use` | VARCHAR(20) | NOT NULL | **用途级别**（PPA AP-907-005 §4.11 / Q182）：`reference` / `continuous` / `information`，**无 DB 默认值**，创建时必选；PDF 封面强制渲染 |
| `revision` | INT | NOT NULL DEFAULT 0 | **乐观锁版本字段**（与 version 不同） |
| `version_update_notes` | TEXT | NOT NULL DEFAULT '' | **用户手填的本版本更新说明**（纯文本，含摘要 + 详细内容），DRAFT 可改；填入 PDF 修订记录页「说明」列 |
| `signoff_enabled` | BOOLEAN | NOT NULL DEFAULT FALSE | PDF 操作员签字栏总开关（程序级，受控文档属性）|
| `deprecated_from_folder_id` | CHAR(36) NULL | | deprecate 时记录原 folder_id；restore 时还原；同 group 所有版本共享该值 |
| `deprecated_at` | DATETIME(6) NULL | | deprecate 操作时间戳（冗存，同 group 所有版本相同；restore 时清空）；Q180 |
| `deprecated_by` | VARCHAR(128) NULL | | deprecate 操作者标识（冗存，同 group 所有版本相同；restore 时清空）；Q180 |
| `archived_at` | DATETIME(6) NULL | | 该条记录变为 ARCHIVED 的时间戳；publish 时把同 group 原 PUBLISHED 转 ARCHIVED 同步写入；read-only 视图 banner 显示用（Q174）|
| `is_active`、时间戳 | | | |

**约束**：

- `UNIQUE(code, version) WHERE is_active = TRUE`
- 同 procedure_group_id 下仅一条 is_current=TRUE（应用层 + DB 部分唯一约束模拟）
- **同 group 仅一条 DRAFT（Q224）**：生成列 `draft_guard = IF(status='DRAFT' AND is_active=true, procedure_group_id, NULL)` + `UNIQUE(draft_guard)`（NULL 不参与唯一）。根治 §22.9「0/1 DRAFT」应用层 check-then-act 的并发竞态；并发第二个 upgrade-version / rollback 触发冲突返 `PROCEDURE_DRAFT_EXISTS`(409)，应用层守卫保留作快速失败 + 友好提示
- 状态机：DRAFT → PUBLISHED → ARCHIVED；DRAFT 可直接 ARCHIVED；PUBLISHED 不可改为 DRAFT
- **只读判定**：`is_current=true` 且 `status=DRAFT` 方可编辑；其余只读（Q14）

**`version_change_log` 结构**：

```json
[{
  "version": 2,
  "previous_version": 1,
  "changed_at": "2026-05-19T10:00:00Z",
  "change_type": "create | update | publish | rollback | deprecate | restore",
  "description": "...",
  "rollback_from_version": 5,   // 仅 change_type=rollback 时有
  "reason": "..."                // 仅 rollback / deprecate / restore 时有
}]
```

### 3.4 `tb_procedure_chapter` — 程序章节

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | CHAR(36) | PK | |
| `procedure_id` | CHAR(36) | FK → tb_procedure.id | |
| `parent_id` | CHAR(36) NULL | FK → tb_procedure_chapter.id | 自引用 |
| `title` | VARCHAR(500) | NOT NULL | |
| `code` | VARCHAR(50) | NOT NULL DEFAULT '' | 后端整树重算 |
| `content_type` | VARCHAR(20) | NOT NULL DEFAULT 'chapter' | **chapter / content**（详见 §3.4.1）|
| `rich_content` | LONGTEXT | NOT NULL DEFAULT '' | **仅 content_type='content' 节点使用**（HTML，WangEditor 产物）；chapter 节点该字段恒为空字符串 |
| `sort_order` | INT | NOT NULL DEFAULT 0 | |
| `level` | INT | NOT NULL DEFAULT 1 | **1–3**（Q190 二次修订：原 3，曾改 6，现回 3）；Word 解析最多 3 级，H4-6 / 更深编号压缩为 L3（恢复 Q35）|
| `mark_status` | VARCHAR(20) | NOT NULL DEFAULT 'unmarked' | **unmarked / step / content / review**（标记模式 + 智能解析）|
| `skip_numbering` | BOOLEAN | NOT NULL DEFAULT FALSE | 与 step 一致；true 时整子树不编号 |
| `conversion_status` | VARCHAR(20) | NOT NULL DEFAULT 'pending' | 解析期临时态：pending / applied |
| `is_active`、时间戳 | | | |

**`mark_status` 取值语义**：

| 值 | 来源 | 含义 |
|---|------|------|
| `unmarked` | 默认 | 未标记 |
| `step` | 用户标记模式 | 应用时将转为 step（chapter→convert-to-step / content→content-to-steps）|
| `content` | 用户标记模式 | §19 后此标记**应用时无操作**（chapter 已无 rich_content；convert-to-content 接口 410 废弃）；UI 仍保留循环切换以兼容 mark_status 枚举 |
| `review` | smart 解析中等置信 heading | 前端高亮提示「请人工复查」；不参与应用 |

**节点角色（Q149-Q152 重构后）**：

| content_type | title | rich_content | 子节点 | 角色 |
|------|------|------|------|------|
| `chapter` | 必填 textarea | **恒为空字符串**（不使用）| 可有子 chapter / content / step | 标题容器；自身不承载内容 |
| `content` | 可空 | HTML 富文本 | **不能有子节点**（叶子）| 无编号正文段落 |

**约束**：

- **章节最大嵌套 3 级**（Q190 二次修订回 3，与 Q-C7 一致）—— 应用层校验 level ≤ 3；`CHAPTER_DEPTH_EXCEEDED` 阈值 3；H4-6 / 更深编号压缩为 L3
- **content 节点强制为叶子**（Q6）—— 应用层校验 content_type='content' 时不可有子
- **chapter 节点 rich_content 恒为空**（Q149-Q152 重构）—— 应用层 service 校验拒绝写入 rich_content 到 chapter；DB 列保留但不使用
- **子节点类型互斥**（Q25）—— 见下方 §4
- code 由后端**保存时整树重算**（Q-C4）
- skip_numbering=true 节点 code='' 且子树不编号（Q15）
- Word 解析后产 chapter 节点 + 每个非 heading 顶层块 → **独立 content 子节点**（Q1 重构）；段内**内联图随段保留**在同一 content 节点 `<p>…<img>…</p>`，仅独立成段的图才单独成节点（Q206/§27.2 修订 §9.2）

**索引**：`IX(procedure_id, sort_order)` / `IX(parent_id)` / `IX(mark_status)` / `IX(content_type)`

### 3.5 `tb_procedure_step` — 程序步骤

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | CHAR(36) | PK | |
| `procedure_id` | CHAR(36) | FK → tb_procedure.id | |
| `chapter_id` | CHAR(36) NULL | FK → tb_procedure_chapter.id | NULL = 根 step |
| `title` | VARCHAR(500) | NOT NULL DEFAULT '' | 可空（Q10）；树视图为空时回落到 content 首行 50 字（Q42）|
| `code` | VARCHAR(50) | NOT NULL DEFAULT '' | 父 chapter.code + '.' + 序号；skip_numbering=true 时为空 |
| `content` | LONGTEXT | NOT NULL DEFAULT '' | HTML |
| `sort_order` | INT | NOT NULL DEFAULT 0 | |
| ~~`mark_status`~~ | — | **本期移除**（Q264）：执行状态属移动端执行运行时产物，本期只编写执行表单定义；执行态待执行模块以独立命名（`execution_status`）记在执行记录而非 step 定义 |
| `skip_numbering` | BOOLEAN | NOT NULL DEFAULT FALSE | 与 chapter 一致 |
| `input_schema` | JSON | NOT NULL DEFAULT '{}' | **执行表单类型 12 型**（复刻 DPMS，大写枚举，Q261），见下方 |
| `note` | LONGTEXT | NOT NULL DEFAULT '' | **警示·提示（蓝）富文本**（Q263 方案 A）；亦承载普通备注（原 `notes` 归入此字段）|
| `caution` | LONGTEXT | NOT NULL DEFAULT '' | **警示·小心（黄）富文本**（Q263）|
| `warning` | LONGTEXT | NOT NULL DEFAULT '' | **警示·警告（红）富文本**（Q263）|
| ~~`expected_output`~~ | — | **已移除**：复刻 DPMS 的预留字段，从未被渲染（PDF）/校验/执行消费，确认无用后删除 |
| `attachment_marks` | JSON | NOT NULL DEFAULT '[]' | **步骤级附件标记**（Q203）：数组，每项 `{name, kind, note}`，仅标记不嵌入文件，见下方 |
| ~~`require_confirmation`~~ | — | **已移除**：逐步确认改为程序级 signoff（见 tb_procedure.signoff_enabled）|
| `is_active`、时间戳 | | | |

> **本轮 step 字段重构（Q261-Q264，复刻 DPMS V2.0 步骤模型）**：①`input_schema` 三型 → **12 型**（A9 覆盖，Q261）；②新增 `note`/`caution`/`warning` 三个富文本警示字段（方案 A，Q263），**移除** `step_alerts` JSON（Q201 修订）与 `notes`（归入 `note`）；③**移除** `mark_status`（Q264）；④现有 3 型迁移 `text→COMMON` / `pass_fail→CHECK` / `measurement→NUMBER`。

**`input_schema` 12 型（复刻 DPMS，大写枚举，Q261/Q262）**：

执行表单类型 = 这一步在**移动端执行通道**采集什么数据 / 在 **PDF 通道**渲染什么纸质占位符（双通道，Q264）。

```json
// COMMON 通用：富文本说明（复用 step.content，方案 X）+ 勾选执行；input_schema 仅 { "type": "COMMON" }
// CHECK 通过/不通过：{ "type": "CHECK", "pass_label": "通过", "fail_label": "不通过" }
// YESNO 是/否：    { "type": "YESNO" }
// NUMBER 数字：     { "type": "NUMBER", "unit": "℃", "min": 0, "max": 100, "decimal_places": 2 }  // 承接原 measurement 上下限/精度
// METER 仪表：      { "type": "METER", "unit": "" }  // 本期简化仅数字+单位（Q265）；name/上下限/超限动作/设备关联待仪表模块
// CHECKBOX 多选：   { "type": "CHECKBOX", "items": ["选项1", "选项2"] }
// RADIO 单选：      { "type": "RADIO", "options": ["选项1", "选项2"] }
// UPLOAD 文件上传： { "type": "UPLOAD", "accept": "*/*", "max_count": 1 }
// SIGNATURE 签名：  { "type": "SIGNATURE" }
// DATE 日期：       { "type": "DATE" }
// PHOTO 拍照：      { "type": "PHOTO", "max_count": 1 }
// NONE 无采集：     { "type": "NONE" }
```

- `type` 为**开放大写枚举**（应用层校验）；新类型只加渲染器/编辑器，不改表结构。
- 现有 3 型迁移：`text→COMMON`、`pass_fail→CHECK`、`measurement→NUMBER`（measurement 的 upper_limit/lower_limit→min/max，decimal_places 保留）。不保留旧小写命名（A9 覆盖）。
- 双通道渲染：PDF 占位符见 [pdf-rendering.md §6.3](pdf-rendering.md)；移动端真控件待执行模块（本期不做执行运行时，Q264）。

**`note` / `caution` / `warning` 三警示字段（Q263 方案 A）**：

- 三个**独立富文本字段**（LONGTEXT，HTML），分别对应 ANSI Z535 三色（提示蓝 / 小心黄 / 警告红，[pdf-rendering.md §7](pdf-rendering.md)）。
- 取代原 `step_alerts` JSON 数组（Q201 修订）：固定 `note→caution→warning` 顺序天然满足 PPA §4.15 递进，富文本支持加粗/列表/红字。
- 原 `notes`（普通备注）**归入 `note`**（移除独立 `notes` 字段，消除 `notes`/`note` 撞名）。
- 与 content 节点正文内嵌 `note-block`/`caution-block`/`warning-block`（Q183 HTML class，**章节正文级辅通道 C**）双轨并存（Q202 调整：主通道由 step_alerts 改为三字段）。

**`attachment_marks` 结构（Q203）**：

```json
[
  { "name": "operation_demo.mp4", "kind": "video", "note": "完整操作演示" },
  { "name": "wiring_diagram.pdf", "kind": "doc",   "note": "" }
]
```

- `kind` 建议值：`video` / `image` / `doc` / `audio` / `other`（应用层弱校验，不入库约束）。
- **仅作标记**：PDF 渲染为「📎 附件: {name}（{kind 中文}）」纯文本，**不嵌入文件、不生成链接、不要求文件已上传**。
- 与程序级 `tb_procedure_attachment`（Q185-Q188，真实上传文件）相互独立、并存（Q203）。

**索引**：`IX(procedure_id, sort_order)` / `IX(chapter_id)`

### 3.6 `tb_procedure_attachment` — 程序附件（新表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | CHAR(36) | PK | |
| `procedure_id` | CHAR(36) | FK → tb_procedure.id | **挂在版本**，upgrade 时复制元数据 |
| `file_name` | VARCHAR(255) | NOT NULL | 原始文件名 |
| `storage_path` | VARCHAR(500) | NOT NULL | 物理路径（upgrade 时复用） |
| `mime_type` | VARCHAR(100) | NOT NULL | |
| `size_bytes` | BIGINT | NOT NULL | |
| `description` | TEXT | NOT NULL DEFAULT '' | |
| `sort_order` | INT | NOT NULL DEFAULT 0 | |
| `is_active`、时间戳 | | | |

**业务规则**：

- 单文件 ≤ 50 MB
- 单 procedure（单版本）数量 ≤ **30**，总大小 ≤ **200MB**（Q120）→ 超限 `ATTACHMENT_LIMIT_EXCEEDED`
- 支持任意格式（含 .nc / .gcode / .docx / .pdf / .png / ...）
- 物理路径：`uploads/procedure/{procedure_id}/{uuid_filename}`
- upgrade-version / rollback / copy 时复制本表记录（storage_path 复用，文件不复制）（Q113 / Q117）
- rollback 继承 **target_version** 的附件集合（不是 current 的）
- 同名 file_name **允许并存**（每次上传生成独立 storage_path）（Q119）
- 软删（is_active=false）后磁盘文件保留；**独立 `scheduler` 进程每日任务**（Q331）清理：未被任何 active 记录引用 + 软删 ≥ 30 天 → **先删文件再硬删本行（行 + 文件同删；文件先删、缺失视为成功）**（Q115 / Q332）
- deprecated group 仍可下载附件（Q118）
- 同 storage_path 的不同版本元数据互相独立，修改不传播（Q116）

**索引**：`IX(procedure_id)`、`IX(storage_path)`（清理任务用）

### 3.7 `tb_procedure_field` — 自定义字段定义（全局）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | CHAR(36) | PK | |
| `name` | VARCHAR(100) | NOT NULL | 显示名 |
| `key` | VARCHAR(100) | UNIQUE NOT NULL | 编程键；**用户手填英文（小写字母 / 数字 / 下划线）、创建后不可改**（Q254，改 key 会孤立已填 `custom_values`）|
| `field_type` | VARCHAR(20) | NOT NULL | text / number / date / select / multi_select / checkbox / textarea |
| `description` | TEXT | NOT NULL DEFAULT '' | |
| `required` | BOOLEAN | NOT NULL DEFAULT FALSE | |
| `default_value` | JSON | NULL | |
| `options` | JSON | NOT NULL DEFAULT '[]' | `[{value, label, archived?: bool}]`（Q24） |
| `validation_rules` | JSON | NOT NULL DEFAULT '{}' | **标准 JSON Schema**（Q-C6）|
| `sort_order` | INT | NOT NULL DEFAULT 0 | |
| `show_on_cover` | BOOLEAN | NOT NULL DEFAULT FALSE | **勾选则按 `sort_order` 渲染到 PDF 封面元数据区**（Q257，与 level_of_use/risk/quality 同区）|
| `status` | VARCHAR(20) | NOT NULL DEFAULT 'active' | active / archived；**archived 后已填值保留只读、新建不出现**（Q255）|
| `is_active`、时间戳 | | | |

### 3.8 `tb_procedure_settings` — 全局设置（单例）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | CHAR(36) | PK | |
| `enable_version_control` | BOOLEAN | NOT NULL DEFAULT TRUE | **本期恒 true、UI 不暴露开关**（Q232）：多版本模型 B1 是核心架构，关闭会破坏 group/is_current/upgrade/rollback，字段保留待未来 |
| `enable_approval_workflow` | BOOLEAN | NOT NULL DEFAULT FALSE | **审批模式开关**（Q242，受控反转 B3）：ON 时 publish 前调预留 `ApprovalGate.check()` hook、本期 stub 放行、**不改三态机**（Q243）；设置页显示、发布区徽标（Q245）；改它继承 Q233 审计 + 二次确认 |
| `max_version_number` | INT | NOT NULL DEFAULT 100 | 设置页显示可改（Q222 达限语义）|
| `auto_archive_days` | INT | NOT NULL DEFAULT 365 | 0 = 不自动归档；**0.1.0 不接线、设置页隐藏**（Q259 / Q337，未来作 §53 scheduler 第 4 任务接入，同 enable_version_control 思路）|
| `require_read_confirmation` | BOOLEAN | NOT NULL DEFAULT FALSE | 控制 mark-read 强制；设置页显示 |
| `default_risk_level` | INT | NOT NULL DEFAULT 1 | PDF 封面默认值；**设置页 1–5 文字分级下拉**（低/中-低/中/中-高/高，Q52/Q260）|
| `default_quality_level` | INT | NOT NULL DEFAULT 1 | PDF 封面默认值；**设置页 1–5 文字分级下拉**（Q52/Q260）|
| `is_active`、时间戳 | | | |

**设置页可见性**（Q260）：显示=`enable_approval_workflow` / `max_version_number` / `require_read_confirmation` / `default_risk_level` / `default_quality_level`；隐藏=`enable_version_control`（Q232）/ `auto_archive_days`（Q259）。

**已移除**（vs spec）：

- `default_approval_template` / `notification_*` / `create_mode`（`enable_approval_workflow` 已于 Q242 **恢复**，仅作全局开关 + 预留闸门，不恢复审批状态 / 字段 / API）

### 3.9 `tb_folder_audit_log` / `tb_procedure_audit_log`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK AUTO_INCREMENT | |
| `target_id` | CHAR(36) | NOT NULL INDEX | folder.id / procedure.id（具体版本）|
| `procedure_group_id` | CHAR(36) NULL INDEX | （仅 procedure_audit_log）| 冲存便于查询整族历史（Q127）|
| `action` | VARCHAR(30) | NOT NULL | 见下方 |
| `old_value` | JSON | NOT NULL DEFAULT '{}' | 字段级 diff（Q123）|
| `new_value` | JSON | NOT NULL DEFAULT '{}' | 字段级 diff；批量操作含 `{ids: [...], count: N}` |
| `reason` | TEXT | NOT NULL DEFAULT '' | rollback / deprecate / restore / delete 必填（Q128） |
| `ip_address` | VARCHAR(45) | NOT NULL DEFAULT '' | 真实客户端 IP：审计中间件解析 `X-Forwarded-For`（配 `TRUSTED_PROXIES`，Q324），非代理 IP |
| `user_agent` | VARCHAR(500) | NOT NULL DEFAULT '' | |
| `created_at` | DATETIME(6) | NOT NULL | |

**action 取值**（Q122）：

- Procedure 级：`create / publish / rollback / deprecate / restore / upgrade_version / transition / move / copy_from / apply_marks / delete / delete_group_v1_draft`
- Chapter 级（target_id=procedure.id，action 前缀 chapter_）：`chapter_create / chapter_update / chapter_delete / chapter_move / chapter_convert_to_step / chapter_content_to_steps` （`chapter_convert_to_content` 已随接口 410 废弃移除，§19）
- Step 级：`step_create / step_update / step_delete / step_move / step_convert_to_chapter`
- Attachment 级：`attachment_upload / attachment_delete / attachment_update`
- Folder 级（folder_audit_log）：`create / update / delete / move / batch_delete`

**不记**：DRAFT 期字段保存的逐次记录（合并为 1 条 update）、GET / PDF / view / mark-read / mark-status。

**索引**：`IX(target_id, created_at DESC)` / `IX(procedure_group_id, created_at DESC)`（procedure_audit_log）/ `IX(action, created_at DESC)` / `IX(created_at DESC)`

**保留期**：**永久保留**（Q125）；运维手动归档（导出 + 截断，建议 ≥ 2 年才归档）。

### 3.10 `tb_procedure_asset` — 图片资源（新表，§25.2 / Q189 / Q193 / Q197）

Word 解析图片不再 base64 内联 rich_content，改抽出为独立资源；rich_content 内以 `<img src="/api/procedures/{procedure_id}/assets/{asset_id}">` 引用。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | CHAR(36) | PK | UUID v4 = asset_id |
| `sha256` | CHAR(64) | UNIQUE NOT NULL | 全库去重键（Q188/§25.2）|
| `storage_path` | VARCHAR(500) | NOT NULL | 物理路径 `uploads/asset/{sha256前2}/{sha256}.{ext}` |
| `mime_type` | VARCHAR(100) | NOT NULL | png/jpeg/gif/bmp/webp（emf/wmf 已转 png，Q207）|
| `size_bytes` | BIGINT | NOT NULL | 原始字节，≤ 10MB（Q207）|
| `width` | INT | NULL | 像素 |
| `height` | INT | NULL | 像素 |
| `source_meta` | JSON | NOT NULL DEFAULT '{}' | 回溯信息 `{docx_rid, anchor_type, page_position}`（§25.2）|
| `is_active`、时间戳 | | | |

**业务规则**：

- **生命周期**：parse 时图先落 `tmp/uploads/{token}/media/`（不入本表）；**import 时**按 sha256 去重提升为永久 asset（已存在则复用，Q193）。
- **格式**：`emf/wmf` 入库前经 **LibreOffice headless**（`soffice --headless --convert-to png`）转 png（Q207/§29.3）；转换失败 → 该图降 placeholder + review，不阻断解析；其他不支持格式 → `UNSUPPORTED_IMAGE_FORMAT`。
- **不自动压缩**（§29.2/Q215）：≤10MB 原样存（保真优先），不降采样不转码（emf/wmf 除外）。
- **大小**：单图 > 10MB → `IMAGE_TOO_LARGE`（Q207）。
- **GC**（Q197 / Q333）：仅删 `ref_count=0` 且**持续 ≥24h**（按 `updated_at`）的 asset；删除在 `SELECT ... FOR UPDATE` 锁定本行并**重核 ref_count=0** 的事务内进行——**先删物理文件**（缺失视为成功）**再硬删本行**（行 + 文件同删，防 sha256 去重悬挂引用）。由独立 `scheduler` 进程每日执行（Q331）。
- **legacy**：遇 rich_content 内既有 `<img src="data:...">` base64 → **原样保留、不入本表、不参与 GC**（greenfield 无存量，仅防御）。

**索引**：`UNIQUE(sha256)` / `IX(is_active)`

### 3.11 `tb_procedure_asset_reference` — 资源引用（新表，Q197）

图片在 rich_content 里是 URL 字符串（无外键），用本关联表追踪引用以支持去重 + GC。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | CHAR(36) | PK | |
| `asset_id` | CHAR(36) | FK → tb_procedure_asset.id | |
| `procedure_id` | CHAR(36) | FK → tb_procedure.id | **挂在版本**；fork（upgrade/rollback/copy）时随 rich_content 复制引用 |
| `created_at` | DATETIME(6) | NOT NULL | |

**业务规则**：

- **重建时机**：每次 save / import 时解析该 procedure 全部 content 节点 rich_content，提取 `<img src=".../assets/{id}">` → 重写本 procedure 的引用行（先删后插，单事务）（Q197）。
- `ref_count(asset) = COUNT(asset_reference WHERE asset_id = ?)`。
- 多版本：同一物理图被多版本引用时 ref_count > 1；deprecate（整组归档，不删）保留引用；仅 DELETE 版本时减引用。
- **唯一**：`UNIQUE(asset_id, procedure_id)`（同版本同图记一行）。
- **去重并发 + grace 计时（Q333）**：引用集变化（含归零）时**顺带 bump 对应 `tb_procedure_asset.updated_at`**，供 GC grace 计时。import 按 sha256「找-或-建」asset 依赖 `UNIQUE(sha256)`（§3.10）+ 对命中行 `SELECT ... FOR UPDATE`，与 GC 删除序列化（防悬挂引用）。

**索引**：`UNIQUE(asset_id, procedure_id)` / `IX(procedure_id)` / `IX(asset_id)`

### 3.12 ~~`tb_procedure_template` — 程序模板~~（**已删除**，Q290 / §44）

> **⛔ 本表被 Q290（[feature-clarifications §44](feature-clarifications.md#四十四模板库替代-procedure-templateq290q293)）删除**：procedure template 功能废弃。**「模板库」方案亦已废除**（[§56/Q340](feature-clarifications.md#五十六砍模板库纯-copy-自现有程序q340)）——不建任何模板库文件夹、无样板种子；要「套结构」= 直接 copy 任意现有程序（§18/Q179）。不再有独立模板表 / body JSON / 模板库。下方表定义仅作历史保留，**不实现**。

~~创建程序时可选模板 → 一次性展开为 chapter/step 记录（§30.1）。~~（已废弃）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | CHAR(36) | PK | |
| `name` | VARCHAR(100) | NOT NULL | 模板名（如「测试类」）|
| `description` | TEXT | NOT NULL DEFAULT '' | 模板说明 |
| `body` | JSON | NOT NULL | 模板树定义，见下方结构 |
| `is_preset` | BOOLEAN | NOT NULL DEFAULT FALSE | 系统预设（general/testing/maintenance 种子）；预设不可物理删除（保底）|
| `sort_order` | INT | NOT NULL DEFAULT 0 | 创建程序时下拉列表排序 |
| `is_active`、时间戳 | | | `is_active=false` = 禁用，不在创建选择列表出现 |

**业务规则**：

- 三套系统预设（`general` / `testing` / `maintenance`，§28.2）作为**种子数据**入表（`is_preset=true`）；其 `body` 初值即 §28.2 定义的章节树。
- 管理界面 CRUD：可新建 / 编辑 / 禁用 / 删除（**预设禁删，仅可禁用**）。
- 创建程序 API（`POST /procedures`）传 `template_id`（缺省 = 空白）；后端读 `body`，在事务内批量创建 chapter + step 记录，编号由编号引擎生成。
- **删除/修改模板不影响已据此创建的程序**（模板仅创建时一次性展开，程序无外键指向模板）。

**`body` JSON 结构**（嵌套章节树）：

```json
{
  "nodes": [
    {
      "type": "chapter",
      "title": "操作步骤 Instructions",
      "skip_numbering": false,
      "children": [
        {
          "type": "step",
          "title": "示例步骤",
          "input_schema": { "type": "measurement", "unit": "", "upper_limit": null, "lower_limit": null },
          "step_alerts": [{ "level": "caution", "content": "...", "sort_order": 0 }],
          "skip_numbering": false
        }
      ]
    },
    { "type": "chapter", "title": "记录保存 Retention of Records", "children": [
      { "type": "content", "rich_content": "" }
    ]}
  ]
}
```

- 节点 `type` ∈ `chapter` / `content` / `step`，遵守子节点类型互斥（§4.1 / Q25）。
- step 节点可预置 `input_schema` / `step_alerts` / `attachment_marks` 等字段。
- `code` 不存模板（创建时由编号引擎重算）。

**索引**：`IX(is_active, sort_order)`

---

## 4. 关键约束规则

### 4.1 子节点类型互斥（Q25）

同一 chapter 下子节点**严格三选一**：

```
chapter X
  └── 子节点群（互斥三选一）
       ├── 类型 A: 子 chapter（可与 content 节点混排）
       ├── 类型 B: step
       └── 类型 C: 单独 content 节点（无子，可作为叶子）
```

procedure 根级同样受互斥约束（根 chapter 与根 step 互斥）。

**Service 层强制校验**：

```python
def assert_sibling_type_compatible(parent_chapter, new_child_type):
    """
    parent_chapter: 父章节实例，None 表示 procedure 根
    new_child_type: 'chapter' | 'content' | 'step'
    """
    existing_children = list_children(parent_chapter)
    existing_types = {c.actual_type for c in existing_children}
    # 'chapter' 与 'content' 视为同一兼容组
    if new_child_type in ('chapter', 'content'):
        if 'step' in existing_types:
            raise ConflictError('SIBLING_TYPE_CONFLICT')
    elif new_child_type == 'step':
        if existing_types & {'chapter', 'content'}:
            raise ConflictError('SIBLING_TYPE_CONFLICT')
```

### 4.2 转换约束（Q4 / Q6 / Q29）

| 操作 | 前置条件 |
|------|---------|
| chapter → step | 无子节点；转换后不违反互斥规则 |
| chapter → content | 无子节点；转换后不违反互斥规则 |
| step → chapter | 转换后不违反互斥规则（无其他同级 step） |
| convert-root-to-step | 同 chapter → step，且 procedure 无其他根 chapter |

### 4.3 上 / 下移（Q26）

- `move-up` / `move-down` 仅交换同 parent_id 内 sort_order
- 到顶 / 到底返回 200 但状态不变（前端按钮 disabled）
- **不跨 parent**；跨级移动用单独的 `move` 端点（含 target_parent_id 参数）

### 4.4 编号生成（Q-C4 / Q15 / Q27）

后端在 chapter / step **保存（含批量）后即时**触发整树重算（§47/Q310；编号全自动不可手改，§47/Q309）：

```
对每个 parent，按 sort_order 遍历子节点，seq 仅对「编号节点」自增（跳过不计数，§47/Q306）：
  seq = 0
  for node in parent.children(按 sort_order):
    if node.skip_numbering:   node.code=''; 整个子树 code=''; continue   # 不占序号位
    if node.content_type=='content': node.code=''; continue            # content 不编号、不占位
    seq += 1
    if node 是 root chapter:  node.code = str(seq)                      # 内部 code（渲染时 L1 追加 '.0'）
    else:                     node.code = parent.code + '.' + str(seq)  # step 同理：父 chapter.code + '.' + seq
```

> **内部 `code` vs 显示**（§47/Q305）：上算得**内部** `code`（L1=`N`、L2=`N.M`、L3=`N.M.K`、step=`N.M[.K[.L]]`，最深 4 段 Q308）。**渲染层**（PDF/TOC/树视图）对 **level==1 chapter** 追加 `.0`（→ `1.0` … `13.0`）；L2/L3/step 不加 `.0`。
> **skip 计数语义**（§47/Q306，**推翻原「占位消耗序号」**）：skip 节点不计入 seq——前言(skip)+目的+范围 → 空白、`1.0`、`2.0`（连续）。显示位：编辑器/树 `#`、PDF 空白（§47/Q307）。

### 4.5 旧版本只读（Q14）

仅 `is_current=true 且 status=DRAFT` 的 Procedure 可写。任何 chapter / step / attachment 的 PUT / POST / DELETE 前在 service 层守卫：

```python
def assert_procedure_editable(procedure):
    if not procedure.is_current:
        raise BadRequestError('PROCEDURE_READONLY')
    if procedure.status != 'DRAFT':
        raise BadRequestError('PROCEDURE_READONLY')
```

### 4.6 乐观锁（Q18）

所有 PUT / PATCH 请求必须携带 `If-Match: <revision>` 头：

```python
def update_procedure(db, id, payload, expected_revision):
    proc = db.get(Procedure, id)
    if proc.revision != expected_revision:
        raise ConflictError('VERSION_CONFLICT')
    apply_changes(proc, payload)
    proc.revision += 1
```

### 4.7 内容大小（Q30）

```python
MAX_IMAGE_SIZE = 10 * 1024 * 1024      # 10 MB（原始字节，Q207 由 1MB 放宽；图片外置 assets 后无 base64 膨胀）
MAX_RICH_CONTENT_BYTES = 5 * 1024 * 1024  # 5 MB（HTML 文本；图片已外置为 <img src> URL，不再含 base64）
MAX_IMAGES_PER_NODE = 20
# 白名单（Q207）：emf/wmf 入库前服务端转 png
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/bmp',
                       'image/webp', 'image/emf', 'image/wmf'}
```

校验时机：保存 chapter.rich_content / step.content 时；单图大小在 import 抽图入 asset 时校验（`IMAGE_TOO_LARGE` 阈值 10MB）。

---

## 5. 状态机

### 5.1 `procedure.status`（三态干净版）

```
DRAFT ──publish──→ PUBLISHED ──archive──→ ARCHIVED
  │
  └────────────archive────────────────────→ ARCHIVED
```

- 初始 DRAFT
- DRAFT → PUBLISHED：状态切换 + is_current 仍为 true
- PUBLISHED → ARCHIVED：状态切换（手动 / auto_archive_days 触发）
- DRAFT 也可直接 ARCHIVED（草稿放弃）
- 任意 → ARCHIVED 为终态，不可逆

### 5.2 多版本切换

```
upgrade-version：
  原 current (status=PUBLISHED, is_current=true)
  ──→ 原 (status=ARCHIVED, is_current=false)
     + 新版本 (status=DRAFT, is_current=true, version=N+1)

rollback (target_version=K)：
  原 current (status=*, is_current=true)
  ──→ 原 (status=ARCHIVED, is_current=false)
     + 新版本 fork-from-K (status=DRAFT, is_current=true, version=N+1)
```

### 5.3 ~~`step.mark_status`（执行状态）~~（**已移除**，Q264 / §40.4）

> **⛔ `step.mark_status` 本期移除**（Q264 / [feature-clarifications §40.4](feature-clarifications.md)）：执行状态属移动端执行运行时产物，本期只编写执行表单定义；待执行模块以独立命名（`execution_status`）记在**执行记录表**而非 step 定义。下方状态机仅留作未来执行模块参考，本期不实现。

```
pending ──→ completed
   ├──→ skipped
   └──→ pending（重置）
```

### 5.4 `chapter.mark_status`（标记模式）

```
unmarked → step → content → unmarked （循环切换）
```

**应用后**所有 mark_status 复位 unmarked。

---

## 6. 启动种子数据

| 操作 | 时机 | 说明 |
|------|------|------|
| 创建「废止」根文件夹 | 首次启动 | `name="废止", system=true, parent_id=null`（唯一系统文件夹）|
| 创建 ProcedureSettings 单例 | 首次启动 | 默认值 |
| 创建示例 ProcedureField（如「风险等级」select）| 首次启动 | 便于演示，可在后续删除 |

实现见 `backend/app/seed.py`。

---

## 7. 数据迁移与版本

- **全新起步（greenfield，Q326）**：本期**不做** DPMS V2.0 存量数据迁移；需导入历史 SOP 走 Word 导入向导（§25 / feature-clarifications §6）。模型多处按 greenfield 假设（如 §3.10 legacy base64 仅防御性保留）。
- 初始 schema：Alembic migration `20260519_initial_schema.py`（Phase 1 产出）
- 每个 PR 涉及结构变更：随附一个 migration
- 变更同步更新本文件
