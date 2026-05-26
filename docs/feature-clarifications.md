# 功能澄清汇编（Feature Clarifications）

> 本文件沉淀 Smart SOP **三轮 grill with doc** 的全部决策。当 plan / data-model / api-specification 之间出现歧义时，**以本文件为权威**。
>
> 来源：基于 [06-程序管理模块功能说明.md](../06-程序管理模块功能说明.md) 的全面澄清。

## 目录

- [一、定位与范围](#一定位与范围)
- [二、整体架构调整](#二整体架构调整-b-类决策)
- [三、补充功能（A 类决策）](#三补充功能-a-类决策)
- [四、细节规范（C 类决策）](#四细节规范-c-类决策)
- [五、Word 解析与编辑器语义（Q1–Q12）](#五word-解析与编辑器语义q1q12)
- [六、版本、附件、并发（Q13–Q24）](#六版本附件并发q13q24)
- [七、结构性约束（Q25–Q32）](#七结构性约束q25q32)
- [八、自定义默认值](#八自定义默认值)
- [九、Word 解析映射规则（Q33–Q40）](#九word-解析映射规则q33q40)
- [十、树视图渲染规范（Q41–Q44）](#十树视图渲染规范q41q44)
- [十一、PDF 渲染规范（Q45–Q60）](#十一pdf-渲染规范q45q60)
- [十二、导入向导规范（Q73–Q96）](#十二导入向导规范q73q96)
- [十三、状态机与生命周期（Q97–Q112）](#十三状态机与生命周期q97q112)
- [十四、附件版本传递（Q113–Q120）](#十四附件版本传递q113q120)
- [十五、审计日志颗粒度（Q121–Q128）](#十五审计日志颗粒度q121q128)
- [十六、多 tab 同时编辑（Q129–Q132）](#十六多-tab-同时编辑q129q132)
- [十七、自定义字段值生命周期（Q133–Q136）](#十七自定义字段值生命周期q133q136)
- [十八、程序复制（Q137–Q140）](#十八程序复制q137q140)
- [十九、章节模型重构（Q149–Q152）](#十九章节模型重构q149q152)
- [二十、导入向导补充（Q141–Q148）](#二十导入向导补充q141q148)
- [二十一、编辑器主流程（Q153–Q164）](#二十一编辑器主流程q153q164)
- [二十二、版本管理 UI 流程（Q165–Q180）](#二十二版本管理-ui-流程q165q180)
- [二十三、PPA AP-907-005 合规修订（Q181–Q188）](#二十三ppa-ap-907-005-合规修订q181q188)
- [二十四、最终错误码清单](#二十四最终错误码清单)
- [二十五、Word 解析器重构（Q189–Q200）](#二十五word-解析器重构q189q200)
- [二十六、PDF 预览交互与步骤字段化（Q201–Q204、Q213）](#二十六pdf-预览交互与步骤字段化q201q204q213)
- [二十七、Word 解析器实现细节（Q205–Q208）](#二十七word-解析器实现细节q205q208)
- [二十八、procedure 模板与页眉布局（Q209–Q212）](#二十八procedure-模板与页眉布局q209q212)
- [二十九、Word 解析器补充实现决策（Q214–Q217）](#二十九word-解析器补充实现决策q214q217)
- [三十、模板管理与步骤编辑器 UI（Q218–Q221）](#三十模板管理与步骤编辑器-uiq218q221)
- [三十一、版本管理流程审视（Q222–Q225）](#三十一版本管理流程审视q222q225)
- [三十二、附件流程审视（Q226–Q229）](#三十二附件流程审视q226q229)
- [三十三、文件夹与设置流程审视（Q230–Q233）](#三十三文件夹与设置流程审视q230q233)
- [三十四、PDF 预览前端渲染层落地（Q234–Q237）](#三十四pdf-预览前端渲染层落地q234q237)
- [三十五、程序复制遗留落地（Q238–Q241）](#三十五程序复制遗留落地q238q241)
- [三十六、审批模式开关（Q242–Q245）](#三十六审批模式开关q242q245)
- [三十七、文件夹 + 文件夹配置（Q246–Q252）](#三十七文件夹--文件夹配置q246q252)
- [三十八、自定义字段配置（Q253–Q258）](#三十八自定义字段配置q253q258)
- [三十九、全局设置页（Q259–Q260）](#三十九全局设置页q259q260)
- [四十、步骤执行表单类型与警示字段（Q261–Q265）](#四十步骤执行表单类型与警示字段q261q265)
- [四十一、程序库列表页 UI（Q266–Q277）](#四十一程序库列表页-uiq266q277)
- [四十二、程序库全文搜索（Q278–Q283）](#四十二程序库全文搜索q278q283)
- [四十三、审计日志查看 UI（Q284–Q289）](#四十三审计日志查看-uiq284q289)
- [四十四、模板库替代 procedure template（Q290–Q293）](#四十四模板库替代-procedure-templateq290q293)
- [四十五、附件上传与管理 UI（Q294–Q299）](#四十五附件上传与管理-uiq294q299)
- [四十六、已读确认（mark-read）流程（Q300–Q304）](#四十六已读确认mark-read流程q300q304)
- [四十七、编号引擎多级规则（Q305–Q311）](#四十七编号引擎多级规则q305q311)
- [四十八、图表编号与交叉引用不自动化（Q312）](#四十八图表编号与交叉引用不自动化q312)
- [四十九、UI 设计系统（Q313–Q319）](#四十九ui-设计系统q313q319)
- [五十、工作台/首页 IA（Q320–Q321）](#五十工作台首页-iaq320q321)
- [五十一、安全姿态与匿名写防护（Q322–Q325）](#五十一安全姿态与匿名写防护q322q325)
- [五十二、跨切面范围确认（Q326–Q330）](#五十二跨切面范围确认q326q330)
- [五十三、后台任务调度与清理（Q331–Q334）](#五十三后台任务调度与清理q331q334)
- [五十四、遗留延期项的收口（Q335–Q338）](#五十四遗留延期项的收口q335q338)
- [五十五、copy 继承 risk/quality（Q339）](#五十五copy-继承-riskqualityq339)
- [五十六、砍模板库，纯 copy 自现有程序（Q340）](#五十六砍模板库纯-copy-自现有程序q340)
- [五十七、Word 解析器实现落地决策（Q341–Q350）](#五十七word-解析器实现落地决策q341q348)
- [五十八、M4 前端整段落地决策（Q351–Q358）](#五十八m4-前端整段落地决策q351q358)

---

## 一、定位与范围

Smart SOP 是从 DPMS V2.0 `procedure` 模块剥离的**独立产品**：

**保留**：

- SOP 程序的 CRUD、结构化编辑
- Word 文档（.docx）转结构化 SOP
- 程序版本控制（多记录模型）+ 版本对比 + 版本回退
- 文件夹体系（树形最大 5 层）+ 前缀编码 + 序列号
- PDF 预览 / 下载（ReportLab + 中文字体 + PPA 规范）
- 标记模式（mark mode）
- 章节 / 步骤的全部类型转换
- 自定义字段（ProcedureField）
- 程序级附件
- 程序废弃 / 恢复
- 全量审计日志（IP / UA / 时间）

**移除**：

- 用户 / 角色 / 权限 / 登录
- 审批工作流（workflow_instance / approval_template / submit-approval / timeline）
- 通知系统
- 仪表（Meter）关联
- NC / G代码 / PLC 程序文件下发
- 已读追踪 M2M（退化为全局单标志）

---

## 二、整体架构调整（B 类决策）

### B1 多版本数据模型

| 子项 | 决策 |
|------|------|
| B1.a 版本绑定 | **新增 `procedure_group_id` 字段**标识同一逻辑程序；同 group 内多条 Procedure 记录，每条对应一个版本 |
| B1.b 当前版本 | **新增 `is_current` 布尔字段**；同 group 仅一条 is_current=true |
| Code 处理 | 同 group 内**不同版本共享同一 code**；唯一约束改为 `(code, version) WHERE is_active=true` |

**关键实现点**：

- 查询"程序库"时统一带 `is_current=true` 过滤
- `upgrade-version` 创建新 Procedure 记录 + 复制所有 chapters / steps + 复制附件元数据
- `rollback` = 以旧版为模板 fork 出新版（version+1，新记录 is_current=true，原 is_current=ARCHIVED）

### B2 阅读确认

退化为**全局单标志**：

- 移除 `read_by` M2M 字段
- 新增 `is_read BOOLEAN` + `read_at DATETIME` 字段
- `POST /procedures/{id}/mark-read` 仅改这条记录的状态
- `GET /procedures/pending-read` 过滤 `is_read=false`
- `GET /procedures/completed-read` 过滤 `is_read=true`
- 由 `ProcedureSettings.require_read_confirmation` 控制前端是否要求显式 mark-read

### B3 状态机三态化

`Procedure.status` 仅保留：`DRAFT` / `PUBLISHED` / `ARCHIVED`

- 移除 PENDING / REJECTED 状态
- 移除 `approval_status` 字段
- 移除 `approval_template_id` / `workflow_instance_id` / `creator_id`
- 移除所有审批相关 API：`submit-approval` / `timeline`
- 状态切换走 `POST /procedures/{id}/transition`

### B4 仪表（Meter）解耦

- 移除 `ProcedureStep.meter` 外键
- measurement 类型步骤的上下限 / 单位**手工**写入 `input_schema`
- `input_schema` 字段命名：`upper_limit` / `lower_limit` / `unit` / `decimal_places`（沉净版本，不嵌套标准 JSON Schema）

### B5 NC/G/PLC 程序

- **不实现**程序文件下发
- 附件可上传 .nc / .gcode / .plc 文件，但仅作通用附件保存，无下发逻辑

### B6 表名规范

所有业务表添加 **`tb_` 前缀**：`tb_folder` / `tb_procedure` / `tb_procedure_chapter` / ... （与 dpms 一致）

> ⓘ B7 在 grill 过程中被合并到 B6（原 B7 = `审计表 _audit_log 后缀规范`，落地后归入 B6 表名规范），保留跳号以维持决策编号稳定。

### B8 PDF 特殊元素

复用 dpms 的 **HTML class 标记协议**：

| 类名 | PDF 渲染效果 |
|------|-------------|
| `<div class="note-block">` | 蓝底框（ANSI Z535 蓝）+ ℹ 图标 + 「注意 NOTE」标题（Q183 新增）|
| `<div class="caution-block">` | 黄底框（ANSI Z535 黄）+ ⚠ 图标 + 「小心 CAUTION」标题（Q183 新增）|
| `<div class="warning-block">` | 红底框（ANSI Z535 红）+ ⛔ 图标 + 「警告 WARNING」标题（Q183 改：原为黄底「警告」单类，现重定义为红底人身风险类）|
| `<div class="signature-bar">` | 签名栏（多列签名 + 日期）|
| `<div class="hold-point">` | 红框 + 加粗提示 + 内容 |

WangEditor 提供专门按钮插入这些 class 标记的 div。warning-block 视觉变更属 Q183 破坏性修订：旧版本（Q49）渲染为黄底，**新版本**（Q183，从 Q184 决策落地起生效）渲染为红底；Q183 落地后所有 PDF 重新生成都将使用新视觉，无回溯迁移（Smart SOP 不缓存 PDF）。

### B9 文件夹删除策略

**硬约束**：

- 含子文件夹 → 拒绝（`FOLDER_NOT_EMPTY`）
- 含程序 → 拒绝（同上）
- 系统文件夹（system=true） → 永远拒绝删除（`FOLDER_SYSTEM_PROTECTED`）

---

## 三、补充功能（A 类决策）

### A1 标记模式（MarkMode）

完整复刻：

- 三态：`unmarked` / `step` / `content`（章节节点的 mark_status 字段）
- 选择上限：100 项（前端约束）
- 同层级 = **同 parent_id**（详见 Q7）
- 单项点击循环切换：unmarked → step → content → unmarked
- 应用机制：详见 Q3 / Q9

### A2 编辑器高级特性

- 撤销 / 重做：本地未保存改动可撤；保存后清空栈；最多 50 步（详见 Q23）
- sessionStorage 自动保存：key 用 `procedure_editor_${procedure_id}`，进入编辑器检测已有草稿提示恢复
- 防意外丢失

### A3 类型转换全套

- `chapters/{id}/convert-to-step`
- ~~`chapters/{id}/convert-to-content`~~ **已废弃**（§19 章节模型重构后返 410 Gone；保留路径与错误码 `CONVERT_TO_CONTENT_DEPRECATED` 兼容旧客户端）
- `chapters/{id}/convert-root-to-step`（特殊接口，详见 Q21）
- `chapters/{id}/content-to-steps`
- `chapters/batch-content-to-steps`
- `steps/{id}/convert-to-chapter`

### A4 编号控制

- `chapters/{id}/toggle-skip-numbering`
- `steps/{id}/toggle-skip-numbering`
- 后端在保存时整树重算编号（详见 Q-C4 / Q15 / Q27）

### A5 版本更新说明（取代版本对比）

> 原 spec 中的"版本对比 + 差异导出"功能 **不实现**自动 diff 算法。

替代方案：

- `tb_procedure.version_update_notes TEXT` 字段：**用户在程序详情页手填**本次版本的摘要与详细内容（纯文本）
- DRAFT 状态可编辑；PUBLISHED / ARCHIVED 只读（Q14）
- `GET /procedure-groups/{group_id}/versions` 返回所有版本及其 `version_update_notes` 全文与预览
- PDF 修订记录页「说明」列由 `description + reason + version_update_notes` 拼接（§11.2）

**理由**：自动 diff 算法（stable_node_id、节点匹配、HTML 块 diff、三栏视图等）实现复杂度高，且对 SOP 业务场景而言用户主动撰写的"变更说明"语义更明确、可读性更强。

### A6 版本回退

`POST /procedures/{id}/rollback?target_version=N`

- **必填 reason**
- 实现机制：Fork（详见 Q12）

### A7 / A8 章节 / 步骤独立 API

| 接口 | 适用 |
|------|------|
| `chapters/{id}/move-up` / `move-down` | 章节 |
| `chapters/{id}/mark-status` | 章节标记模式 |
| `steps/{id}/move-up` / `move-down` | 步骤 |
| ~~`steps/{id}/mark-status`~~ | ~~步骤执行状态~~ —— **已移除**（Q264 / §40.4：执行态归执行模块，step 定义无 mark_status）|

### A9 步骤类型三类

> **本决策被 §40（Q261）覆盖**：执行表单类型由 3 型扩展为复刻 DPMS V2.0 的 **12 型**（大写枚举），术语正名为「执行表单类型」。下表 3 型迁移：`text→COMMON` / `pass_fail→CHECK` / `measurement→NUMBER`。详见 [§40.1](#401-q261-执行表单类型复刻-dpms-12-型覆盖-a9)。

~~通过 `input_schema.type` 区分：~~

| ~~type~~ | ~~input_schema 形态~~ |
|------|------|
| ~~`text`~~ | ~~`{ "type": "text", "placeholder": "..." }`~~ |
| ~~`pass_fail`~~ | ~~`{ "type": "pass_fail", "pass_label": "通过", "fail_label": "不通过" }`~~ |
| ~~`measurement`~~ | ~~`{ "type": "measurement", "upper_limit": 100, "lower_limit": 0, "unit": "℃", "decimal_places": 2 }`~~ |

### A10 附件管理

新增 `tb_procedure_attachment` 表：

- 本地文件系统存储（`uploads/procedure/{procedure_id}/` 目录）
- 单文件 ≤ 50 MB
- 支持任意格式（含 .nc / .gcode / .pdf / .xlsx / .png / ...）
- 挂在版本 Procedure，upgrade/rollback 时元数据复制（storage_path 复用，不复制文件）
- 软删（is_active=false），磁盘文件保留供历史版本引用

### A11 ProcedureField 批量操作

完整复刻：

- `procedure-fields/update-status`（批量改 active/archived）
- `procedure-fields/batch-delete`
- `procedure-fields/reorder`
- `procedure-fields/options`（选项下拉数据）

### A12 文件夹树带统计

`GET /folders/tree` 返回值含 `procedure_count` 字段（每节点的程序数）。

---

## 四、细节规范（C 类决策）

| 项 | 决定 |
|---|------|
| C1 创建模式 | **只留 version_control**，移除 simple；`create_mode` 字段去除 |
| C2 PDF 文件名 | `{code}_Rev{version}.pdf` |
| C3+C8 富文本编辑器 | **WangEditor 5**；rich_content 存 **HTML 字符串** |
| C4 编号生成 | **后端保存时**整树重算 code |
| C5 Word 导入 code | **始终调用 sequence_generator** 重新分配，不复用原文档 code |
| C6 validation_rules | **标准 JSON Schema**，后端用 `jsonschema` 库校验 |
| C7 章节嵌套层级 | **最多 3 级**（Q190 二次修订：曾改 6，现回 3；符合真实文档观测 + 用户思路；H4-6 压 L3）|
| C-删除语义 | **三种并存**：软删（DELETE，is_active=false）/ 废弃（deprecate，转「废止」+ ARCHIVED）/ 硬删（仅管理 API） |

---

## 五、Word 解析与编辑器语义（Q1–Q12）

### Q1 解析产物形态（Q149-Q152 重构）

**Heading → ProcedureChapter（仅标题，rich_content 恒为空）；每个非 heading 顶层 HTML 块（`<p>` / `<table>` / `<ul>` / `<ol>` / `<div>` 含 dpms class）→ 独立的 content 子节点**，挂在最近的 chapter 下。

→ 解析后产物：chapter（仅 title）+ content（rich_content 含 HTML 块）的混合树。

> 这是 Q149-Q152 重构后的新规则。`tb_procedure_chapter.rich_content` 列保留但**仅 content 节点使用**；chapter 节点该字段恒为空。
> 原 spec / dpms 是 "段落汇入 chapter.rich_content"，已废弃。

### Q2 / Q3 标记模式语义

| 维度 | 决定 |
|------|------|
| 标记对象 | chapter 和 content 节点都可标 |
| 标记 vs 应用 | mark_status 仅记**意图**；用户点「应用标记」触发事务批量转换 |

**应用时的语义映射**（事务内执行）：

| 节点 content_type | 标记为 | 应用时执行 |
|---|---|---|
| chapter | step | `convert-to-step` |
| chapter | content | **§19 后：无操作**（chapter 已无 rich_content 可承载，convert-to-content 接口 410 废弃）；UI 仍可循环切此标记但 apply 时跳过 |
| content | step | `content-to-steps` |
| content | content | 无操作 |
| 任意 | unmarked | 仅清除 mark_status |

### Q4 / Q6 转换约束（含子节点）

| 转换 | 子节点非空时 |
|------|------|
| chapter → step | 拒绝 `CHAPTER_HAS_CHILDREN` |
| chapter → content | 拒绝 `CHAPTER_HAS_CHILDREN` |

content 节点强制为**叶子**（应用层校验）。

### Q5 content-to-steps 拆分规则

按 **rich_content 的顶层 HTML 块**拆分：

- 顶层块 = `<p>` / `<table>` / `<ul>` / `<ol>` / `<div>`（含 dpms class）
- 每个块 → 一个 ProcedureStep
- 样式保留在 step.content 内

### Q7 「同层级」定义

= **同 parent_id**（同一父节点下的兄弟），不跨 parent。

### Q8 step → chapter 归属

- 新 chapter 的 `parent` = 原 step 的 chapter（成为子章节）
- `step.content` → 新 `chapter.rich_content`
- `step.input_schema` → 新 `chapter.rich_content` 末尾的 `<div class="hint">原 input_schema</div>`（注：保留以备追溯）
- `step.notes` → 新 `chapter.rich_content` 末尾的 `<p class="notes">...`

### Q9 应用标记执行机制

**原子事务**：

- 一次调用应用所有 mark_status 非 unmarked 的节点
- 任一失败全部回滚
- 成功后清空所有涉及节点的 mark_status
- 返回值含：新建/删除节点的 ID 列表

### Q10 content-to-steps 后 step.title

**留空让用户填**；step.content = 完整 HTML 块。

### Q11 转换生成的 step 默认类型

- 默认 `type='COMMON'`（Q261 起 12 型大写枚举；旧 `text` → `COMMON`）
- 各类型 input_schema UI 见 §40.1（Q261）12 型表；常见三型：
  - COMMON：仅 content 文本框（原 text）
  - NUMBER：显示 min / max / unit / decimal_places 字段（原 measurement，upper/lower_limit → min/max）
  - CHECK：显示 pass_label / fail_label 字段（原 pass_fail）

### Q12 版本回退机制

**Fork 新版**：

1. 以旧版为模板**复制**所有 chapters / steps（深拷贝）
2. 创建新 Procedure 记录，version+1，is_current=true
3. 原当前版置 ARCHIVED（is_current=false）
4. audit log 记录 rollback 操作含**必填 reason**
5. 附件元数据复制（storage_path 复用）

---

## 六、版本、附件、并发（Q13–Q24）

### Q13 附件版本归属

- 挂在版本 Procedure（`procedure_id` 指向具体版本记录）
- upgrade-version / rollback 时**复制附件元数据**
- 物理文件不复制（storage_path 在不同版本间共享）
- 软删附件时磁盘文件保留

### Q14 旧版本可编辑性

**仅 `is_current=true 且 status=DRAFT` 可编辑**；其余版本全部只读。

后端 service 层守卫：每次 PUT/POST chapter/step/attachment 前校验所属 Procedure 是否可编辑。

### Q15 编号体系（计数语义 / L1 `.0` 见 §47 修订）

> **§47（Q305/Q306）修订**：①L1 章节显示 `N.0`（DPMS 习惯），但 **`.0` 仅渲染层**——内部 `code` 仍按下表递归（L1=`N`、L2=`N.M`、L3=`N.M.K`），PDF/TOC/树视图显示时 L1 追加 `.0`（Q305）。②skip_numbering 节点**不计入序号**、编号节点连续编号（Q306，下方原「不跳号语义」整段作废）。

| 节点类型 | 编号规则（内部 code） |
|---------|--------|
| chapter，skip_numbering=false | 参与编号；code = 父 code + '.' + 序号（**跳过的兄弟不计数**，Q306）；**L1 显示追加 `.0`**（Q305）|
| chapter，skip_numbering=true | 节点自身 code='';**整个子树不编号**；**不占序号位**（Q306）|
| content | 永远 code='' |
| step，skip_numbering=false | code = 父 chapter.code + '.' + 同级 step 序号（可达 4 段 `1.1.1.1`，Q308）|
| step，skip_numbering=true | code='' |

~~**不跳号语义**：1, 2(skip), 3 实际呈现 1, ?, 3，下一同级是 4（不是 5）。~~ **⛔ 被 Q306 推翻**：skip 节点不计数、编号连续——前言(skip)+目的+范围 → （无号）、`1.0`、`2.0`。

### Q16 rich_content 内图片

~~**base64 嵌入 HTML**（`<img src="data:image/...;base64,..."/>`），不走附件。~~
**已被 §25.1/Q189 取代**：图片改为 **assets 表 + URL 引用**（`<img src="/api/procedures/{id}/assets/{asset_id}">`），不再 base64 内联，也不走附件表（assets 是独立资源表，见 [data-model.md §3.10/§3.11](data-model.md)）。

### Q17 自定义字段值存储

`tb_procedure.custom_values JSON` 字段，结构 `{field_key: value}`。

### Q18 并发编辑保护

**乐观锁**：

- `tb_procedure.revision INT` 字段，每次更新 +1
- PUT / PATCH 请求**必须携带 `If-Match: <revision>` 头**
- 不匹配返回 409 `VERSION_CONFLICT`

### Q19 章节删除级联

**递归软删整个子树**（与文件夹的硬约束不同）：

- 删 chapter X → X 自身 + 所有子 chapter / 子 content / 子 step 全部 `is_active=false`
- audit log 单条记录主对象 + 影响范围

### Q20 批量操作 atomicity

**全原子**：

- `batch-content-to-steps` / `batch-delete` 等：单事务
- 一项失败全部回滚
- 返回值含成功 ID 列表 + 错误详情

### Q21 convert-root-to-step

- 后端逻辑与 convert-to-step 共用（自动检测 parent=null）
- 但 URL **保留独立路径**以便前端语义清晰
- 同样受 Q29 互斥规则约束

### Q22 跨文件夹移动

- 支持，PUT /procedures/{id} 可改 folder_id
- **code 不变**（即使新文件夹 prefix 不同）
- 记 audit log

### Q23 撤销 / 重做

- 仅限**本会话未保存改动**
- 保存后清空撤销栈
- 上限 50 步

### Q24 ProcedureField.options 变更

**软代理**：

- options 数组结构 `[{value, label, archived?: bool}]`
- 删除 = 标记 archived=true
- 新程序不可选 archived 项；已使用值仍保留显示

---

## 七、结构性约束（Q25–Q32）

### Q25 子节点类型互斥（核心约束）

同一 chapter 下子节点**三种类型严格互斥**：

```
chapter X
  └── 子节点群（互斥三选一）
       ├── 类型 A: 子 chapter（可与 content 节点混排）
       ├── 类型 B: step
       └── 类型 C: 单独 content 节点
```

UI 表现：

| 已有子节点类型 | disabled 的「新增」按钮 |
|---------------|---------------------|
| 含子 chapter / 子 content | 「新增步骤」 |
| 含子 step | 「新增子章节」「新增内容块」 |
| 无子节点 | 三个按钮都可用 |

procedure 根级同样受互斥约束（根 chapter 与根 step 互斥）。

错误码：`SIBLING_TYPE_CONFLICT`（HTTP 400）。

### Q26 上移 / 下移

- 仅在**同 parent 内交换 sort_order**
- 到顶 / 到底时按钮 disabled
- **不跨 parent**；跨级移动需用拖拽 API（单独提供）

### Q27 步骤编号

- step 也有 `skip_numbering` 字段（与 chapter 一致）
- step.code = 父 chapter.code + '.' + 同级 step 序号（如 `1.2.1` / `1.2.2`）
- **深度不受章节 3 级上限约束**（Q308/§47）：L3 章节下的 step 可达 4 段 `1.1.1.1`；3 级上限仅约束 chapter。step 为**叶子**（无子步骤，深层结构用子章节表达）。

### Q28 content 节点独立价值

**持久独立态**，PDF 中作为**无编号正文段落**：

| 维度 | content | step |
|---|---|---|
| 编号 | 永远无 | 有 |
| input_schema | 无 | 有 |
| mark_status | 标记模式用（unmarked/step/content） | 无 —— 执行态 `mark_status` 已移除（Q264 / §40.4）|
| PDF 渲染 | 无编号富文本段落 | 编号 + 标题 + 内容 + 输入字段 |
| 典型场景 | "插入一段说明" | "操作员需要做的动作" |

### Q29 转换互斥冲突处理

**一律拒绝**：返回 400 `SIBLING_TYPE_CONFLICT`。

典型场景：

- step S 转 chapter，但同 parent 下还有其他 step → 拒绝
- 根 chapter 转 step，但 procedure 还有其他根 chapter → 拒绝
- chapter C 转 step，但有子节点 → 拒绝（Q4，错误码 `CHAPTER_HAS_CHILDREN`）

### Q30 富文本图片约束

| 项 | 值 |
|---|---|
| 单图（原始字节）| ≤ **10 MB**（§27.3/Q207 取代 1MB；图片外置 assets 无 base64 膨胀）|
| 总 rich_content | ≤ 5 MB（HTML 文本；图片已外置为 `<img src>` URL，**不再含 base64**）|
| 支持格式 | JPG / PNG / GIF（静态首帧）/ BMP / WebP / EMF / WMF（EMF/WMF 转 PNG，§27.3/Q207）；不支持 SVG |
| 单节点图片数 | ≤ 20 |
| 检测时机（前）| WangEditor 插入时即检测 |
| 校验时机（后）| 保存时按字节数校验 |
| 错误码 | `IMAGE_TOO_LARGE` / `CONTENT_TOO_LARGE` / `UNSUPPORTED_IMAGE_FORMAT` |

### Q31 PDF 表格处理

| 场景 | 处理 |
|---|---|
| 超宽 | 等比缩放到页宽（A4 内边距后约 17 cm）|
| 行多 | 自动跨页（ReportLab LongTable），表头每页重绘 |
| 嵌套 | 拒嵌套；内层降级为文本占位「[嵌套表格]」+ warning |

### Q32 PDF 图片处理

| 场景 | 处理 |
|---|---|
| 超宽 | 等比缩放到页宽 |
| 位置 | **始终独占一行 + 居中**（忽略富文本中的浮动 / 对齐属性）|
| 格式 | PNG / JPG / GIF 首帧 / WebP；其他格式跳过并插入占位 |
| 超高 | 强制缩放至页高 - 上下边距 |

---

## 八、自定义默认值

> 以下项 grill 中未单独问，由实现侧依据合理默认确定。

| 项 | 默认 |
|---|------|
| 撤销栈深度上限 | 50 |
| sessionStorage key | `procedure_editor_${procedure_id}` |
| 标记模式选择上限 | 100 |
| PDF 缓存策略 | 不缓存，每次重新生成 |
| 程序复制（克隆） | 不单独提供（upgrade-version 已覆盖） |
| 程序列表过滤维度 | folder_id / status / search（移除 approval_status / creator） |
| Word 解析策略 | 仅暴露 `standard` / `smart` 两种 |
| `auto_archive_days` 实现 | Phase 9（附件+收尾）定时任务，初期可缺省（与 development-plan §6 待决一致）|
| 自定义字段值校验时机 | 保存程序时一次校验，失败返回 422 |
| 删除附件 | 软删（is_active=false）；磁盘文件保留 |
| skip_numbering 节点子树 | 整树无编号（code 全空）|
| chapter 自带 rich_content | 与子节点群独立，不受互斥规则影响 |
| step.title 编辑器内可选 | 可空；保存前提示但允许提交 |

---

## 九、Word 解析映射规则（Q33–Q40）

### 9.1 整体数据流（两步式 Q36）

```
.docx 文件
   │
   ▼ POST /parse
   │
   ├─ 1. 边界识别（Q37）
   │    ├─ 主要规则：查找最后一个 section break，之后为正文起点
   │    └─ fallback：找不到 section break 时，定位第一个 Heading 1
   │    之前的 cover / TOC / 前言一律 skip
   │
   ├─ 2. 顺序遍历正文 block
   │    ├─ 遇到 heading → 创建 ParsedChapter
   │    │   ├─ Heading 1/2/3 → level 1/2/3
   │    │   └─ Heading 4/5/6 → 压缩为 level=3，title 前加 <strong>…</strong>（Q35）
   │    └─ 遇到非 heading 块 → 追加到「最后激活 heading」的 rich_content（Q39）
   │
   ├─ 3. 模板校验（仅 standard 模式，Q40）
   │    ├─ standard：任一 error → 拒绝 PARSE_TEMPLATE_INVALID
   │    └─ smart：仅 warning，且中等置信 heading 标记 markStatus='review'
   │
   └─ 返回 ParseResult JSON（不落库）
   │
   ▼ POST /procedures/import （用户审查后）
   │
   ├─ 用户在向导必填 name（默认填文件名去扩展名，Q38）
   ├─ 后端调用 sequence_generator 生成 code（Q-C5）
   ├─ 创建 Procedure（新 procedure_group_id, version=1, is_current=true, DRAFT）
   └─ 递归创建 ProcedureChapter；无任何 step、无任何 content 节点
```

### 9.2 Word 元素 → Smart SOP 字段映射

| Word 元素 | 落到 Smart SOP 哪里 |
|----------|-------------------|
| Cover page / 封面 | **丢弃** |
| Table of Contents | **丢弃** |
| 第一个 section break / Heading 1 之前的"前言" | **丢弃** |
| docx core property `title` | **不使用** |
| Heading 1 / 2 / 3 | `ProcedureChapter`，level=1/2/3，content_type='chapter'，**rich_content 为空** |
| Heading 4 / 5 / 6 | `ProcedureChapter`，**level=3**，title 加 `<strong>` 标记体现降级 |
| 普通段落 `<p>` | **独立 content 子节点**：content_type='content'，title='',rich_content=`<p>...</p>` |
| 表格 | **独立 content 子节点**：rich_content=`<table>...</table>` |
| 图片 | **独立 content 子节点**：rich_content=`<p><img src="data:..."/></p>` |
| Word 自带编号字段 | **抛弃**，后端 save 时整树重算（Q15 + Q27） |
| 警告框 / 签名栏 / HoldPoint 自定义样式 | **独立 content 子节点**：rich_content=`<div class="warning-block|signature-bar|hold-point">...</div>`（B8） |
| 有序/无序列表 | **独立 content 子节点**：rich_content=`<ul>...</ul>` 或 `<ol>...</ol>` |

> Q149-Q152 重构：所有非 heading 块**不再汇入 chapter.rich_content**，而是各自成为最近 chapter 的 content 子节点。Q1 已更新。
>
> **Q212 警示映射**：Word 解析**不识别警示语义**——语义上是「警告/注意/小心」的段落统一走普通 `<p>` content 节点，**不**自动映射为 `note/caution/warning-block` 或 `step_alerts`。上表「警告框 / 签名栏 / HoldPoint 自定义样式」行仅适用于 Word 源 HTML **已显式含**对应 class 的罕见情形（如本系统往返导出再导入）；常规 docx 不产生这些 class。用户导入后手工归类（填 step 的 `note`/`caution`/`warning` 三字段，Q263 取代原 step_alerts；见 §28.4 / §40.3）。

### 9.3 标准 vs 智能模式差异

| 维度 | standard | smart |
|------|---------|-------|
| 模板违规处理 | error 即**拒绝**（PARSE_TEMPLATE_INVALID） | 仅 warning 不拒绝 |
| Heading 检测 | 仅看样式名是否为 Heading 1-6 | 多信号融合：style / outline / numbering / font / structure |
| 不规范段落 | 不识别为 heading | 中等置信识别为 heading，标记 markStatus='review' |
| 适用场景 | 团队有规范模板 | 历史 / 外部不规范文档 |

### 9.4 关键不变量

- **解析完成后，树中只有 chapter 节点**（无 content、无 step）
- **rich_content 是块结构 HTML**，可空、可任意 HTML 内容
- 用户后续在编辑器里通过 `content-to-steps` 或标记模式 + apply-marks 来产出 step 节点；content 节点已在解析阶段直接产出（§19）

### 9.5 procedure.name 来源（Q38）

- /parse 响应不含 name 字段
- /procedures/import 请求体**必须**带 name
- 前端导入向导表单 **默认填充 docx 文件名（去扩展名）**，用户可改但不可清空提交
- 后端强制校验：`name.trim() != ''`，否则 422

---

## 十、树视图渲染规范（Q41–Q44）

> 详细 UI 行为见 [editor-behavior.md](editor-behavior.md) 的「树视图节点渲染规则」。本节仅锚定数据→视觉的映射。

### 10.1 节点视觉（Q41）

| 节点 | 图标 | 默认颜色 | mark_status 时颜色 |
|------|------|---------|------------------|
| chapter | 📘（书） | 蓝 | unmarked=蓝 / step=绿 / content=灰 |
| step | ☐（复选框） | 绿 | 不参与（step 无 mark mode）|
| content | 📄（文档） | 灰 | unmarked=灰 / step=绿 |

### 10.2 标题与 fallback（Q42）

| 节点 | title 显示 | 空时 fallback |
|------|----------|--------------|
| chapter | 原样 | `(未命名章节)` 灰斜体（极少出现）|
| step | 原样 | 取 `step.content` **首行纯文本前 50 字**，灰斜体加括号 |
| step 且 content 也空 | — | `(空步骤)` 灰斜体 |
| content | （无 title 字段）| 取 `rich_content` 首行纯文本前 50 字 |

> step.title 为空**不阻塞编辑**；PUBLISHED 时 warning。

### 10.3 节点行信息密度（Q43）

`[展开 ▸] [节点图标] [code] [title or fallback] [类型色条] [特殊状态图标]`

| 位置 | 显示规则 |
|------|---------|
| code | `1.2.3`；skip_numbering=true 时显示 `#` 灰色占位 |
| title | 主要文本；fallback 时灰斜体 |
| 类型色条（仅 step） | 按 `input_schema.type` 着色（12 型，Q261/§40.1；原 text/pass_fail/measurement → COMMON/CHECK/NUMBER）；具体色板实现期定 |
| 特殊状态图标（仅 step） | `⚠` = require_confirmation；`#` = skip_numbering |
| mark_status（chapter/content）| 通过节点图标颜色表达，不加额外标记 |

### 10.4 树不展开内容预览（Q44）

- 树**始终只显示一行**，不预览 content / rich_content
- 单击节点 → 右侧详情面板加载完整内容
- 双击节点 → 进入名称内联编辑模式

### 10.5 双向同步规则

| 编辑动作（详情面板） | 树即时刷新 |
|-------------------|----------|
| 改 title | 节点 title 实时刷新 |
| 改 content（且 title 为空）| 节点 fallback 文本实时刷新 |
| 切换 step.type | 类型色条实时刷新 |
| 切换 require_confirmation | ⚠ 图标实时出现/消失 |
| 切换 skip_numbering | code 变 `#` 灰色，下方同级 code 整树重算 |

---

## 十一、PDF 渲染规范（Q45–Q60）

> 详细规格见 [pdf-rendering.md](pdf-rendering.md)。本节为决策索引。

### 11.1 封面页

| Q | 决策 |
|---|------|
| Q45 签名栏 | 保留三栏空白「编制 / 审核 / 批准」，纸质打印后手填 |
| Q52 风险/质量等级 | 文字分级（低/中-低/中/中-高/高）+ 颜色色块 |
| Q182 用途级别（Level of Use）| 新增 `tb_procedure.level_of_use` 字段（物理 VARCHAR(20) NOT NULL + 应用层枚举校验，与 `status` 字段惯例一致；逻辑枚举 `reference` / `continuous` / `information`），创建程序时必选，无 DB 默认。封面强制渲染「用途级别: {中文标签} ({英文标签})」。详见 §23.2 |

### 11.2 目录页 / 修订记录页

| Q | 决策 |
|---|------|
| Q46 TOC 范围 | 仅 chapter；skip_numbering 章节不进 TOC；content / step 不进 TOC |
| Q47 修订记录页 | 仅显示 publish / rollback / deprecate / restore 四种里程碑事件 |
| ~~Q59 页码体系~~ | ~~封面无页码；TOC / 修订用罗马数字 i/ii/iii；内容页阿拉伯数字从 1~~ **被 Q184 覆盖** |
| Q184 页码体系（覆盖 Q59）| 严格匹配 PPA AP-907-005 §4.6 step 3：封面无 footer 页码；TOC / 修订记录用罗马数字 `i / ii / iii`；正文用阿拉伯数字 `1 / 2 / 3`；**T（总页数）= 全文档所有页之和**（含封面 / TOC / 修订 / 正文）；footer 格式 `第 {P} 页 / 共 {T} 页`，P 在前置页是罗马数字、正文是阿拉伯数字，T 始终阿拉伯数字。详见 §23.4 |

### 11.3 内容页

| Q | 决策 |
|---|------|
| Q48 step 渲染 | 各 type 共享标题格式，仅执行记录区不同（12 型，Q261/§40.1；原 text/pass_fail/measurement → COMMON/CHECK/NUMBER）|
| Q53 跨页保护 | 标题不独留页底（KeepWithNext）+ step 不拆页（KeepInFrame，超高 fallback 拆页 + 续标记）|
| Q54 skip_numbering 章节标题 | 完全同常规章节，仅编号位留空 |
| Q57 step 编号 | 「{code} {title}」最简格式，无「步骤」前缀 |
| Q58 content 节点 | 与正文段落同格式，仅留 1em 上下内边距 |
| Q185-Q188 附件区段（PPA §4.13.13）| 作为正文最后一节渲染；**仅元数据清单**（文件名 / 大小 / MIME / 上传日期 / 描述），文件本体不嵌入；表格形式 + LongTable 跨页表头重绘；沿用正文阿拉伯页码（Q187），不独立编号。详见 §23.5 |

### 11.4 特殊元素（HTML class 协议）

| Q | 决策 |
|---|------|
| ~~Q49 warning-block~~ | ~~黄底（ANSI Z535）+ 黑边框 + 「⚠ 警告」加粗黑字标题~~ **被 Q183 拆分覆盖** |
| Q183 警示三类块（覆盖 Q49）| 严格匹配 PPA AP-907-005 §4.15，警示按递进语义拆为三类独立 class，颜色采用 ANSI Z535 配色：`note-block`（蓝底，提示性信息）/ `caution-block`（黄底，设备风险）/ `warning-block`（红底，人身风险）。三类同框时强制顺序 Note→Caution→Warning。详见 §23.3 与 pdf-rendering.md §7 |
| Q50 hold-point | 红双圈边框 + 「◈ HOLD POINT 检查点」加粗红字标题 + 内容 + 签名行（自动追加）|
| Q51 signature-bar inline | 三列：编制 / 审核 / 批准（各含签名 + 日期行）|

### 11.5 字体与排版

| Q | 决策 |
|---|------|
| Q55 字体 | 中文 SimSun 小四（12pt）；英文 Times New Roman 12pt；加粗 SimHei / TNR Bold；等宽 Consolas |
| Q31 表格超宽/跨页 | 等比缩放至页宽 + 自动跨页（LongTable）|
| Q56 嵌套表格 | 外层正常 + 内层降级为缩进列表（信息不丢，PDF 不死）|
| Q32 图片 | 等比缩放至页宽 + 独占一行居中；GIF 取首帧；不支持格式插入占位 |

### 11.6 metadata 与性能

| Q | 决策 |
|---|------|
| Q56 PDF metadata | title=`{code} {name} Rev.{version}`；author=`Smart SOP` |
| Q56 文件名 | `{code}_Rev{version}.pdf` |
| Q60 生成性能 | 同步生成 + 后端 60s 硬超时（504 PDF_TIMEOUT）+ nginx 限流 20 req/min/IP；不缓存结果 |

### 11.7 新增错误码

| 错误码 | HTTP | 触发场景 |
|--------|------|---------|
| `PDF_TIMEOUT` | 504 | 渲染超过 60 秒 |
| `PDF_GENERATION_FAILED` | 500 | ReportLab 内部异常 |

---

## 十二、导入向导规范（Q73–Q96）

> 详细 UX 见 [editor-behavior.md](editor-behavior.md) 导入向导章节。

### 12.1 5 步线性向导（Q73-Q76）

| Step | 内容 | 后退 | 取消 |
|------|-----|------|------|
| ① 上传 | 拖拽/选 .docx（≤50MB）| ✗ | 直接退出 |
| ② 模式 | standard / smart（默认 smart）| ✓ 保留状态 | 同上 |
| ③ 报告 | standard 模板校验 / smart 解析概览 | ✓ | 二次确认 |
| ④ 树审查 | 中量编辑：title / skip_numbering / 删除（递归子树） / move-up/down；不可改 rich_content / level / content_type；review 节点黄色提示但不阻塞 | ✓ | 二次确认 |
| ⑤ 表单 | 最小集：name（默认文件名）+ folder_id（仅非系统）| ✓ | 二次确认 |

### 12.2 流转与状态（Q77-Q80）

- sessionStorage：step2-5 数据，key=`procedure_import_wizard_v1`（含 createdAt）；24h 超期清理
- 提交失败：弹框 + 留 step5 + 重试
- 提交成功：跳转 `/procedures/{new_id}`

### 12.3 模式与边界（Q81-Q88）

- standard warning-only：可下一步 + 二次确认
- 空树：返 `PARSE_NO_HEADINGS` 拒绝
- folder 下拉：仅 `system=false` 文件夹，「废止」不可选

### 12.4 边缘场景（Q89-Q96）

- 图片超 **10MB**：拒绝（`IMAGE_TOO_LARGE`，§27.3/Q207）。**不自动压缩**（§29.2/Q215）：≤10MB 原样存（图片外置 assets 无膨胀动因，保真优先）；原「超 1MB 自动压缩」逻辑已删除
- step indicator：Element Plus Steps；可点已完成步骤跳回
- 文件大小三档预警：20MB 提示 / 40MB 警告 / 50MB 拒绝
- 非 .docx：前端 accept 限制 + MIME 双校验
- 网络中断：上传失败 toast 重试；解析失败跳 step3 错误页

---

## 十三、状态机与生命周期（Q97–Q112）

### 13.1 状态机

```
DRAFT ──(publish)──► PUBLISHED ──(被替代/deprecate)──► ARCHIVED  ◄── 终态
```

**单向硬约束**：拒绝 PUBLISHED→DRAFT、DRAFT→ARCHIVED（用 DELETE 软删）、ARCHIVED→任何 → 统一 `PROCEDURE_STATUS_INVALID`。

### 13.2 核心操作语义

| 操作 | 颗粒度 | 行为 |
|------|--------|------|
| **publish** | 单版本 | transition status=PUBLISHED；同 group 原 PUBLISHED **自动**转 ARCHIVED + is_current=false |
| **rollback(target)** | 单版本→新单版本 | target 必须 ARCHIVED + 同 group + is_active=true；fork 新 DRAFT 版（version+1, is_current=true）；原 current 转 ARCHIVED；reason 必填 |
| **deprecate** | **整 group** | 所有版本 status=ARCHIVED + folder_id 改「废止」；记 deprecated_from_folder_id；reason 必填 |
| **restore** | **整 group** | 以 group 中 version 最高记录为模板 fork 新 DRAFT 版；移回原 folder；其余记录保持 ARCHIVED；reason 必填 |
| **DELETE 单版本** | 单记录 | is_active=false；**拒绝**删 is_current（`PROCEDURE_IS_CURRENT`）；删后不能作 rollback target；reason 必填 |

### 13.3 数据模型增量（Q103）

```diff
tb_procedure:
+ deprecated_from_folder_id   CHAR(36) NULL    # deprecate 时记录原 folder；restore 用
```

### 13.4 已 deprecate group 的可用操作（Q105）

仅允许：`GET / PDF / restore / DELETE / 附件下载 / 附件预览`；其余（PUT、transition、upgrade-version、rollback、mark-read、deprecate、move folder、**附件 POST/PUT/DELETE**）一律 400 `PROCEDURE_DEPRECATED`（附件写约束见 Q228 / §32.3）。

### 13.5 列表过滤公式（Q110）

| 页面 | SQL where |
|------|-----------|
| 程序库 | `is_active=true AND status='PUBLISHED' AND is_current=true AND folder.system=false` |
| 草稿箱 | `is_active=true AND status='DRAFT' AND is_current=true` |
| 「废止」 | `is_active=true AND folder.system=true AND is_current=true` |
| 待阅读 | 程序库条件 AND `is_read=false` |

### 13.6 version_change_log 写入触发（Q111）

仅 5 类里程碑：`create` / `publish` / `rollback` / `deprecate` / `restore`。不记 update（DRAFT 期保存）/ 自动 ARCHIVED / DELETE 软删（仅 audit_log）。

### 13.7 version_update_notes 初始化（Q112）

| 触发 | 初始值 |
|------|--------|
| upgrade-version | 空 |
| rollback | `回退自 v{target_version}\n原因：{reason}` |
| restore | `从「废止」恢复，原文件夹: {folder.full_path}` |

### 13.8 restore 原文件夹丢失（Q106）

restore 时若 deprecated_from_folder_id 指向的文件夹已软删 → 返 `RESTORE_FOLDER_MISSING`；POST body 可传 `target_folder_id` 覆盖。

---

## 十四、附件版本传递（Q113–Q120）

### 14.1 复制规则（Q113）

upgrade-version / rollback / restore **全部默认复制附件元数据**（新 id、新 procedure_id 指向新版本，但 file_name / storage_path / size_bytes 复用原值，物理文件不复制）。

### 14.2 独立软删（Q114）

每个版本的 attachment 是独立记录；某版本软删某附件不影响其他版本对同一 storage_path 的引用。

### 14.3 磁盘清理（Q115）

后端 **每日定时任务**：扫描 storage_path 未被任何 `is_active=true` 的 attachment 引用 + 软删时间 ≥ 30 天 → 物理删除磁盘文件。

### 14.4 元数据隔离（Q116）

修改某版本 attachment 的 name / description 仅影响当前版本，不传播。

### 14.5 rollback 附件来源（Q117）

rollback fork 出的新版本继承 **target_version**（被回退到的旧版）的附件集合，不继承 current 的。

### 14.6 deprecated 附件下载（Q118）

GET /attachments/{id}/download 不受 PROCEDURE_DEPRECATED 限制，仍允许（与 Q105 view/PDF 一致）。

### 14.7 同名上传（Q119）

允许并存：每次上传生成独立 storage_path（UUID + 原名）；file_name 可重复。

### 14.8 数量与总量上限（Q120）

单 procedure 单版本：附件数量 ≤ **30**，附件总大小 ≤ **200MB**；超限返 `ATTACHMENT_LIMIT_EXCEEDED`。

---

## 十五、审计日志颗粒度（Q121–Q128）

### 15.1 表与归属（Q121, Q127）

- `tb_folder_audit_log`：folder 操作专用
- `tb_procedure_audit_log`：procedure / chapter / step / attachment 全归此表
  - `target_id` = procedure 记录 id（具体版本）
  - **额外冲存** `procedure_group_id CHAR(36) NOT NULL INDEX`（便于查询整族历史）

### 15.2 action 范围（Q122）

**记**：

- Procedure：create / publish / rollback / deprecate / restore / upgrade_version / move（跨文件夹） / transition / copy
- Chapter / Step：create / update / delete / move（位置）/ convert-*
- Attachment：upload / delete / update
- Folder：create / update / delete / move / batch_delete

**不记**：

- DRAFT 期频繁字段保存的逐次记录（合并为一条 update）
- GET / PDF / view / mark-read（无业务变更）
- mark-status（标记状态切换，频繁）

### 15.3 old/new_value 内容（Q123）

仅字段级 diff：`{field1: old_val, field2: old_val}` 与对应 new。批量操作 new_value 含 `{ids: [...], count: N}`。

### 15.4 reason 必填场景（Q128）

破坏性操作必填：`rollback / deprecate / restore / delete`。其余可选。

### 15.5 保留与清理（Q125）

**永久保留**；运维手动归档（导出 + 截断脚本，需 ≥ 2 年）。

### 15.6 查询过滤维度（Q126）

`GET /audit-logs/procedures` 支持：`target_id` / `action` / `date_from` / `date_to` / `ip_address` / `procedure_group_id` / 分页。

---

## 十六、多 tab 同时编辑（Q129–Q132）

### 16.1 多 tab 同程序（Q129, Q130）

**不主动检测**，靠乐观锁兜底；冲突时后提交者拿 409 `VERSION_CONFLICT`，UI 弹「远程版本已变更，是否加载最新？」。

**不使用 BroadcastChannel**。

### 16.2 sessionStorage key（Q131）

key = `procedure_editor_${procedure_id}`，依 sessionStorage 原生 tab 隔离。

### 16.3 同 tab 切换程序未保存改动（Q132）

`beforeRouteLeave` 拦截 + 弹三选：

- **保留**（不跳，继续编辑）
- **丢弃**（清 sessionStorage 后跳）
- **取消**

---

## 十七、自定义字段值生命周期（Q133–Q136）

### 17.1 archived 字段的旧值（Q133）

详情页设「**已废弃字段**」折叠区，灰色只读展示 archived field 的旧值（值在 `Procedure.custom_values` 中保留）；正常字段区仅列 `status='active'` 的字段。

### 17.2 field_type 不可变（Q134）

PUT /fields/{id} **拒绝**修改 field_type；改类型必须先 archived 旧字段、新建同名不同 key 的新字段 → `FIELD_TYPE_IMMUTABLE`。

### 17.3 validation_rules / required 变更（Q135）

- 仅在**保存程序时**校验最新规则
- 旧不合规值保留不报错
- required false→true 仅约束新保存；旧空值不强制回填

### 17.4 key 不可变（Q136）

PUT /fields/{id} **拒绝**修改 key；UI 创建后 disabled → `FIELD_KEY_IMMUTABLE`。

---

## 十八、程序复制（Q137–Q140）

### 18.1 接口（Q137）

`POST /procedures/{id}/copy`

创建独立的新 procedure_group_id；与原程序完全无版本关系。

### 18.2 复制范围（Q138，**复制源版本修订见 Q238/§35.1**）

**复制所传 `{id}` 对应的那个版本**（所见即复制，**修订 Q138** 原「仅 is_current」，见 [Q238/§35.1](#351-q238-复制源版本语义修订-q138)）的：

- chapters / steps（整树深拷贝，重生节点 id）；step 的 `note`/`caution`/`warning`（Q263 取代 `step_alerts`）/ `attachment_marks`（Q203）随 steps 复制（§33.5）
- attachments（元数据复制，storage_path 复用，与 Q113 一致）
- custom_values（原样 JSON 拷贝；archived field 旧值同样保留）
- `level_of_use`（Q182）/ `risk_level` / `quality_level`（Q52，**Q339/§55 补漏字段**）继承 source（§33.5）

**不复制（重置为默认，Q239/§35.2）**：
- version_change_log（新 group 起始）、version_update_notes、audit_log
- `chapter.mark_status` → `unmarked`（运行期标记态不随内容复制；`step.mark_status` 已随 Q264 移除，见 §40.4）
- `is_read` → `false`、`read_at` → `null`（新程序未读）

### 18.3 目标文件夹与名称（Q139）

```json
POST /procedures/{id}/copy
{
  "target_folder_id": "uuid",    // 必填，仅非系统文件夹
  "name": "..."                  // 选填，默认 source.name + " (副本)"；同名允许并存、不去重（Q240/§35.3）
}
```

后端：

- procedure_group_id 新生成
- code 重新走 `sequence_generator`（按 target_folder.prefix）
- version=1，is_current=true，status=DRAFT
- revision=0
- name **不校验唯一**：`code` 才是唯一标识，多个同名「X (副本)」允许并存（Q240/§35.3）

### 18.4 追溯（Q140）

- `audit_log`：action='copy_from'，new_value=`{source_procedure_id, source_code, source_version}`
- `version_change_log` 首条 description：`复制自 {source_code} v{source_version}`
- **不**在 tb_procedure 表加 copied_from 外键字段

---

## 十九、章节模型重构（Q149–Q152）

> 这是对前面所有 chapter / Word 解析决策的**根本性调整**。当本节与 §五-Q1 / §九 / §四 等内容冲突时，**以本节为准**（相关章节已同步更新）。

### 19.1 核心调整

`tb_procedure_chapter` 表保持，但**职责分离**：

| 节点 | 角色 | rich_content |
|------|------|------|
| `content_type='chapter'` | **仅标题容器**，不承载内容 | **恒为空字符串**（DB 列保留兼容） |
| `content_type='content'` | 无编号正文段落 | HTML 富文本（用 WangEditor 编辑）|
| `tb_procedure_step` | 步骤 | step.content 富文本（不变）|

### 19.2 Word 解析规则更新

每个非 heading 顶层 HTML 块 → **独立的 content 子节点**（详见 §9.2）。chapter 不再"吃"段落。

### 19.3 接口废弃

| 接口 | 状态 |
|------|------|
| `POST /chapters/{id}/convert-to-content` | **废弃**，返回 410 Gone + detail「该接口在章节模型重构后不再支持」|
| `POST /chapters/{id}/convert-to-step` | 保留（仍要求 chapter 无子节点；转出 step.content 为空让用户补）|
| `POST /chapters/{id}/convert-root-to-step` | 保留（同上） |

### 19.4 UI 变更

- chapter 节点详情面板：仅 `title` (textarea) + `skip_numbering` 开关 + 子节点管理；**移除 WangEditor**
- content 节点详情面板：仅 WangEditor 编辑 rich_content（无 title 字段）
- step 节点详情面板：title + type + input_schema + WangEditor + 其他元字段

详细 UI 规范见 [editor-behavior.md §4.1](editor-behavior.md)。

### 19.5 PDF 渲染

- chapter 仅渲染标题（编号 + title）
- content 节点继续作为无编号正文段落渲染（详见 [pdf-rendering.md §6.4](pdf-rendering.md)）

### 19.6 chapter.title textarea（Q149）

- 输入控件 `<textarea>` + autosize（自动增高）
- 默认 1 行高度，max 上限 500 字符
- 不支持加粗 / 换行格式化（纯文本）

### 19.7 兼容与迁移

- 现有迁移：Phase 1 初始 schema 直接按重构后建表（rich_content 列保留供 content 节点）
- 应用层 service 强约束：chapter 节点写入时 rich_content 强制空字符串
- 旧 dpms 数据导入（如有）：需要专门迁移脚本把 chapter.rich_content 拆为 content 子节点

---

## 二十、导入向导补充（Q141–Q148）

> §12 的细化决议。

### 20.1 上传与 parse 时序（Q141）

**两步式**：

```
step1 上传：
  POST /uploads (multipart, file)
  → 返回 { upload_token, expires_at: now + 24h }
  → 文件存到后端临时区 tmp/uploads/{token}/file.docx

step2 → step3 触发 parse：
  POST /parse { upload_token, parse_mode }
  → 后端从临时区读文件解析
  → 返回 ParseResult JSON

模式切换：复用 upload_token，重调 /parse 即可，无需重传

24h 后端清理：未被 import 消费的 upload_token + 临时文件清除
```

### 20.2 step4 重置数据源（Q142）

前端 sessionStorage 同时存 `raw_chapters` + `edited_chapters`（深拷贝隔离）；点「重置」 → `edited = deep_clone(raw)`。无需后端缓存。

### 20.3 import body 设计（Q143）

`POST /procedures/import`

```json
{
  "name": "...",
  "folder_id": "uuid",
  "chapters": [
    {
      "title": "...",
      "level": 1,
      "sort_order": 0,
      "content_type": "chapter",
      "skip_numbering": false,
      "mark_status": "unmarked",
      "children": [
        { "content_type": "content", "rich_content": "...", "sort_order": 0 },
        { "content_type": "chapter", "title": "...", "children": [...] }
      ]
    }
  ]
}
```

后端递归创建 ProcedureChapter；校验 Q25 互斥与 3 级嵌套。

### 20.4 提交后着陆（Q144）

成功跳 `/procedures/{new_id}/edit`（编辑器模式），顶部 toast「导入成功，请补充其他详情」。

### 20.5 step3 报告 UI（Q145）

共享「顶部汇总卡片 + 底部可折叠详情区」框架：

- standard：「模板校验：N 项通过 / M 警告 / K 错误」+ 状态色 + 8 条规则详情列表
- smart：「解析概览：N 章节 / M 表格 / K 图片 / X 需复查」+ warnings + review 节点路径预告

### 20.6 step4 树 + 预览面板（Q146-Q147 重新解读）

**Q146-Q147 决策重读**：

按 §19 重构，step4 中：

- 左侧树：chapter / content / step 节点（解析后已有 content 节点）
- 右侧预览面板（只读）：
  - 点中 chapter → 显示 title textarea（**可编辑**）+ skip_numbering 开关 + 删除按钮
  - 点中 content → 显示 **只读 WangEditor** 预览 rich_content + 删除按钮（不可改内容）
  - 点中 step（解析不会产 step，但用户可能转换出）→ 显示标题 + 只读内容预览

### 20.7 上传进度（Q148）

axios `onUploadProgress` 进度条 + 百分比；上传完成后变 spinner「服务器检查中…」直到拿到 upload_token。

---

## 二十一、编辑器主流程（Q153–Q164）

> 详细 UI 与行为见 [editor-behavior.md §17](editor-behavior.md)。本节为决策索引。

| Q | 决策 |
|---|------|
| Q153 加载策略 | 一次拉全部：GET /procedures/{id} 返嵌套树 + steps + attachments + custom_values + fields |
| Q154 保存策略 | 手动保存按钮 + sessionStorage 1s debounce 防丢失 + Ctrl+S 快捷键 |
| Q155 节点切换 | 修改集中在 Pinia store；切换节点保留 dirty；保存时一次提交所有 dirty |
| Q156 publish 触发 | 顶栏「发布」按钮 + 检查列表弹框（name / folder / chapters / 必填字段 / 未保存 → 全 ✓ 才能发布）|
| Q157 upgrade 入口 | 顶栏「升级版本」按钮（仅 PUBLISHED + is_current 可见）|
| Q158 历史版本 | 编辑器 read-only 模式；URL 携版本 id；黄色 banner + 返回当前按钮 |
| Q159 性能 | 虚拟滚动（> 50 节点）+ WangEditor 按需实例化 + 仅提交 dirty 节点 |
| Q160 搜索 | 树顶部固定搜索框；输入实时过滤；`/` 快捷键聚焦 |
| Q161 顶栏 | 面包屑 + 状态 chip + 未保存 chip + 主动作组（保存/发布/升级/PDF）+ ⋮ 更多菜单 |
| Q162 程序级字段 UI | 顶栏下方「程序详情」折叠面板（默认收起），含 description / risk / quality / 自定义字段 / version_update_notes |
| Q163 附件 + notes 位置 | 右侧 3 tab：节点详情 / 附件 / 版本历史；notes 在「程序详情」面板内 |
| Q164 快捷键 | Ctrl+S / Ctrl+Z / Ctrl+Shift+Z / Delete（选中节点）/ `/`（搜索）/ Esc |

---

## 二十二、版本管理 UI 流程（Q165–Q180）

> 本节定义 upgrade / rollback / deprecate / restore / 版本历史的端到端 UI 与跳转。当与 [editor-behavior.md](editor-behavior.md) §9 / §12.2 中早期写法不一致时，**以本节为准**。

### 22.1 upgrade-version 输入策略（Q165）

**决策**：upgrade 不弹 reason / prompt；fork 出新 DRAFT 后跳新版本编辑器（见 22.4），用户在「程序详情」面板的 `version_update_notes` textarea 自行填写更新说明。

理由：
- §13.2 表格仅要求 rollback / deprecate / restore / delete 必填 reason；upgrade 不属破坏性操作
- §13.7 定义 upgrade 后 `version_update_notes` 初始为空，无需额外 reason 通道
- 与 §二十一 编辑器主流程的顺滑性一致：少弹框，多就地编辑

**调用形态**：

```typescript
async function upgradeVersion() {
  const confirmed = await confirmDialog(
    `将创建版本 v${current.version + 1}，当前版本会被归档。是否继续？`
  )
  if (!confirmed) return
  const newProc = await http.post(`/procedures/${pid}/upgrade-version`, {})
  router.push(`/procedures/${newProc.id}/edit`)
  setSuccessBanner({ kind: 'upgrade', sourceVersion: current.version, newVersion: newProc.version })
  toast.success(`已升级到 v${newProc.version}`)
}
```

**影响 editor-behavior.md**：§9.2 删除 `prompt('请输入升级原因')` 行；POST body 不再带 `reason` 字段。§12.2 升级版本确认文案保持「将创建版本 v{N+1}，当前版本会被归档。是否继续？」（无 reason 输入）。

### 22.2 版本历史承载形式（Q166）

**决策**：编辑器右侧 tab 区域的第三个 tab「版本历史」（与 Q163 一致）。时间线**倒序**展示同 group 所有 `is_active=true` 的版本，含 ARCHIVED / DRAFT / PUBLISHED。

时间线每行字段（自上而下、自左到右）：

| 元素 | 说明 |
|------|------|
| 版本号 `v{N}` | 加粗，is_current=true 行额外加「●当前」标记 |
| status chip | DRAFT（灰）/ PUBLISHED（蓝）/ ARCHIVED（暗灰） |
| operator + 操作时间 | 例：`2026-05-19 14:32 by 张三` |
| version_update_notes 预览前 100 字 | 灰色斜体；超出截断 `...`；点击行其他位置展开完整内容 |
| 操作按钮组 | 条件性显示，详见 22.3 |

排序：`created_at DESC`（最新在上）。

加载策略：默认一次性拉全部（同 group 版本通常 ≤ 50）。后端 `GET /procedure-groups/{group_id}/versions` 已支持完整列表（见 [api-specification.md](api-specification.md) §程序版本）。

软删除版本（is_active=false）**不显示**在时间线（与 §13.5 列表过滤公式一致）。

### 22.3 rollback target 选择 UI（Q167）

**决策**：版本历史时间线中，每行如果满足

```
status='ARCHIVED' AND is_active=true AND is_current=false
```

则在操作按钮组位置显示 **「回退到此版本」按钮**（图标 + 文字）。

点击按钮 → 弹 modal：

```
┌─ 回退到 v{target_version} ──────────────┐
│ 将创建新 DRAFT v{N+1}，当前 v{current}  │
│ 自动归档。                              │
│                                         │
│ 回退原因（必填）:                       │
│ ┌──────────────────────────────────┐   │
│ │ [textarea, 5 行]                 │   │
│ └──────────────────────────────────┘   │
│                                         │
│              [取消]  [确认回退]         │
└────────────────────────────────────────┘
```

- reason 为空时「确认回退」按钮禁用
- 提交后调 `POST /procedures/{id}/rollback { target_version, reason }`，再跳转新版本（见 22.4）

按钮**不显示**的行类型：

| 行类型 | 不显示原因 |
|--------|----------|
| is_current=true | 当前版本无需回退到自己 |
| DRAFT | rollback target 必须 ARCHIVED |
| PUBLISHED | PUBLISHED 是过渡态，业务上不允许回退到一个 PUBLISHED（§13.2 表硬约束） |

不使用 radio / checkbox 多选机制：rollback 一次只回退到一个 target，行内按钮已经足够。

**影响 editor-behavior.md**：§9.3 重写为按行内按钮触发 modal 的流程；不再用 `prompt`。

### 22.4 操作成功后页面跳转（Q168）

upgrade / rollback / restore 三者都 fork 出新 DRAFT 记录。统一行为：

1. 后端返回 `newProc = { id, version, ... }`
2. 前端 `router.push('/procedures/${newProc.id}/edit')`（替换当前路由，不保留历史）
3. 进入新版本编辑器后，顶栏正下方显示 **非阻塞 banner**（绿底）

banner 文案与 kind 映射：

| 触发 | banner 文案 |
|------|------------|
| upgrade | `已基于 v{source_version} 创建新 DRAFT v{newProc.version}，可在「程序详情 → 版本更新说明」编辑摘要。` |
| rollback | `已基于 v{target_version} 创建新 DRAFT v{newProc.version}。初始版本说明已预填，可继续编辑。` |
| restore | `已从「废止」恢复并创建新 DRAFT v{newProc.version}（原文件夹: {folder.full_path}）。` |

banner 实现细节：

- 用 Element Plus `<el-alert type="success">` + `closable=true`
- **不自动消失**（与表单类提示一致，避免用户漏看）
- 不阻断编辑（与 modal 区分）
- 同时弹 toast 轻量反馈（`升级成功 v{N+1}` / `已回退` / `已恢复`）

**影响 editor-behavior.md**：§9.2 / §9.3 的 `toast.success` 改为 `setSuccessBanner({...})` + toast 双层提示。

### 22.5 restore 与 RESTORE_FOLDER_MISSING 交互（Q169）

**决策**：触发 restore 前先调预检查接口；按结果分叉弹不同 modal，**一次提交一并带齐**。

新增后端接口：

```
GET /procedures/{id}/restore-preview
→ 200 { folder_exists: boolean, deprecated_from_folder_id: string|null, folder_full_path: string|null, version_count: number }
```

前端流程：

```typescript
async function startRestore(pid: string) {
  const preview = await http.get(`/procedures/${pid}/restore-preview`)

  if (preview.folder_exists) {
    // 分支 A：原 folder 存在 → 仅弹 reason modal
    const { reason, confirmed } = await openRestoreReasonModal({
      folderPath: preview.folder_full_path,
      versionCount: preview.version_count,
    })
    if (!confirmed) return
    return doRestore(pid, { reason })
  } else {
    // 分支 B：原 folder 已软删 → 弹 form modal（含 folder picker + reason）
    const { reason, target_folder_id, confirmed } = await openRestoreWithFolderPickerModal({
      versionCount: preview.version_count,
    })
    if (!confirmed) return
    return doRestore(pid, { reason, target_folder_id })
  }
}

async function doRestore(pid: string, body: any) {
  const newProc = await http.post(`/procedures/${pid}/restore`, body)
  router.push(`/procedures/${newProc.id}/edit`)
  setSuccessBanner({ kind: 'restore', newVersion: newProc.version, folderPath: ... })
}
```

理由：
- 一次提交而不是先 POST 失败再二次弹框，对用户更顺
- 复用现有 POST /restore 接口，新增 preview 是只读廉价查询
- restore-preview 也顺带返 `version_count`，可在 reason modal 内文案显示「将恢复整 group 共 {N} 个版本」

### 22.6 deprecate 入口与影响范围提示（Q170）

**决策**：deprecate 有**两处入口**，统一弹同款 modal 强调「整 group」语义。

入口：

| 位置 | 触发 |
|------|------|
| 编辑器顶栏「⋮ 更多」菜单 | 当前查看版本不为 ARCHIVED 时显示「废弃整 group」 |
| 程序库列表行「⋮」菜单 | 任意非「废止」文件夹下的行显示「废弃整 group」 |

modal 形态：

```
┌─ 废弃程序「{procedure.name}」 ─────────────────┐
│ ⚠ 此操作将废止**整 group 共 {N} 个版本**，    │
│   并移动到「废止」系统文件夹。                │
│                                               │
│ 操作不可逆（仅可通过「恢复」fork 新 DRAFT）。│
│                                               │
│ 废弃原因（必填）:                             │
│ ┌────────────────────────────────────────┐   │
│ │ [textarea, 5 行]                       │   │
│ └────────────────────────────────────────┘   │
│                                               │
│ ☐ 我已了解此操作不可逆                        │
│                                               │
│           [取消]      [确认废弃]               │
└───────────────────────────────────────────────┘
```

- {N} 由编辑器内缓存的 `version_count`（或 list 行携带的字段）即时填充；若上下文无 N，载入 modal 时调 `GET /procedure-groups/{group_id}/versions?count_only=true` 拉
- checkbox 未勾选时「确认废弃」按钮禁用
- reason 为空时「确认废弃」按钮禁用
- 调 `POST /procedures/{id}/deprecate { reason }`
- 成功后：编辑器入口的版本会被 ARCHIVED，前端 reload 当前页或跳转「废止」文件夹列表（按用户偏好；当前默认 reload）
- 列表入口的版本直接刷新当前列表行（消失）

### 22.7 DELETE 单版本的入口（Q171）

**决策**：**仅在版本历史 tab 的时间线行**显示「删除」小图标，编辑器顶栏与列表行均不开放删除入口。

显示条件（行级判断）：

```
status='ARCHIVED' AND is_active=true AND is_current=false
```

UI 形态：每行操作按钮组中，「回退到此版本」按钮的右侧紧邻一个垃圾桶图标按钮（hover 显示 tooltip「删除此版本」）。

点击 → 弹 modal：

```
┌─ 删除版本 v{version} ─────────────────────────┐
│ ⚠ 删除后此版本不可作为 rollback 目标。       │
│   原始数据可在「审计日志」中查询。           │
│                                              │
│ 删除原因（必填）:                            │
│ [textarea, 5 行]                             │
│                                              │
│           [取消]      [确认删除]              │
└──────────────────────────────────────────────┘
```

- 调 `DELETE /procedures/{id}` body `{reason}`
- 成功后：从时间线移除该行；刷新统计数（如有显示）
- 不影响当前编辑器（用户不会身处被删行；is_current 行不显示该按钮）

理由：
- 防止误删当前版本：唯一入口在版本历史，且仅满足条件的行显示按钮
- 与 Q167「回退到此版本」入口同列对称，UI 自洽
- 列表行不开放：列表展示的都是 is_current，按规则不可删；显示按钮反而产生误导

### 22.8 status chip 配色规范（Q172）

> **已修订（§49 / Q317）**：UI 设计系统改暖炭黑暗壳后，本节 EP 默认盘（已发布 = 主蓝 `#409EFF`）已被**暖盘**取代（已发布 = 鼠尾草绿 `#88B07A`），呈现由填充 tag 改为圆点 + 等宽标签。下表为历史原始决策，**现行配色以 [§49 Q317](#四十九ui-设计系统q313q319) + [design-system.md §2.1](design-system.md) 为准**。

**决策（原始，已被 Q317 修订）**：与 Element Plus 默认调色板对齐，三态 + 废止特殊标记：

| 状态 | 颜色名 | Hex | Element Plus 类型 |
|------|--------|------|-------------------|
| DRAFT | 中性灰 | `#909399` | `info` |
| PUBLISHED | 主蓝 | `#409EFF` | `primary` |
| ARCHIVED | 暗灰 | `#606266` | （regular text 色，自定义 tag 背景） |
| 废止标记（附加） | 警示红 | `#F56C6C` | `danger` |

「废止」标记规则：当整 group 已 deprecate 时，在 status chip **右侧**追加红色小 tag「废止」。例：

```
[v3 ARCHIVED] [废止]      ← deprecated group
[v2 PUBLISHED]            ← 正常 PUBLISHED
[v1 DRAFT]                ← 正常 DRAFT
```

ARCHIVED chip 文字使用白色（保证对比度），其余三种 chip 文字按 Element Plus 默认（深色）。

**影响 editor-behavior.md**：§5 顶栏的状态 chip 说明补充具体色值；版本历史时间线渲染时引用同套规则。

### 22.9 多 DRAFT 与 upgrade / rollback 前提（Q173）

**决策**：同 group 同时只能有 **0 或 1 个** DRAFT。`upgrade-version` 与 `rollback` **仅当 `is_current=true 且 status=PUBLISHED`** 时可触发。

后端 service 层守卫：

| 接口 | 守卫规则 | 失败错误码 |
|------|---------|-----------|
| `POST /procedures/{id}/upgrade-version` | source.is_current=true AND source.status='PUBLISHED' | `PROCEDURE_STATUS_INVALID` |
| `POST /procedures/{id}/rollback` | source.is_current=true AND source.status='PUBLISHED' | `PROCEDURE_STATUS_INVALID` |

前端 UI 守卫（双保险）：

| 当前状态 | 顶栏「升级版本」 | 版本历史「回退到此版本」 |
|---------|----------------|------------------------|
| is_current AND status=DRAFT | 不显示 | 不显示 |
| is_current AND status=PUBLISHED | 显示 | 显示（满足行条件时）|
| is_current AND status=ARCHIVED | 不显示 | 不显示（编辑器只读，参考 22.10）|
| 历史版本（非 is_current） | 不显示 | 不显示（仅当前 PUBLISHED 视角才能触发） |

理由：
- DRAFT 是 group 的"在编辑草稿"，本应先发布或丢弃，不应基于它再做 fork
- 若允许在 DRAFT 状态 rollback，会出现"自动归档一个 DRAFT"的反直觉语义
- 大改方案（多 DRAFT 并存）暂不考虑，与 B1 模型冲突过大

### 22.10 历史版本只读查看（Q174 / Q158 细化）

**决策**：版本历史时间线每行新增 **「📖 查看」按钮**（所有 is_current=false 的行都显示）；点击跳独立路由 `/procedures/{id}/view`，复用编辑器组件的 read-only 模式渲染。

路由设计：

| 路由 | 用途 |
|------|------|
| `/procedures/{id}/edit` | 当前版本可编辑（仅 is_current=true AND status=DRAFT 实际可写）|
| `/procedures/{id}/view` | 任意只读查看（id 为该版本的具体 procedure.id）|

**路由进入守卫**：当用户访问 `/procedures/{id}/edit` 但加载到的记录 **不满足** `is_current=true AND status=DRAFT`（典型场景：deprecated group 的 is_current=true 但 status=ARCHIVED；或访问历史 ARCHIVED 版本的 /edit），前端路由守卫**自动 replace 为 `/procedures/{id}/view`**（不留浏览器历史），避免出现"假可编辑"状态。

只读模式渲染规则：

- 所有输入框 `readonly` / `disabled`
- 主动作按钮组 **完全隐藏**（保存 / 发布 / 升级 / 编辑相关全部不显示）
- 顶栏右侧仅保留：「PDF 下载」按钮 + 「返回当前版本」按钮（跳转到 `/procedures/{current_id}/edit`）
- 顶栏正下方黄底 banner（不可关闭）：`正在查看历史版本 v{N}（已归档于 {archived_at}）。`
- 右侧 tab 保留：节点详情 / 附件 / **版本历史**（在只读视图也能继续切换查看其他历史版本）
- ⋮ 更多菜单：仅保留「复制为新程序」（复制源始终是当前查看的版本）；其余动作隐藏

实现路径：
- 编辑器组件加 `readonly: boolean` prop
- store 加载时根据路由判断 read-only 上下文
- 节点详情面板的所有 input / textarea / WangEditor 透传 `readonly`

不复用 PDF 预览作为查看器（C 选项被否）：PDF 不能精准还原结构化树形操作，且查看历史时用户期望与编辑器一致的 UI。

### 22.11 DRAFT 丢弃入口（Q175）

**决策**：编辑器顶栏「⋮ 更多」菜单中提供 **「丢弃此 DRAFT」**入口；显示条件：

```
is_current=true AND status='DRAFT' AND version > 1
```

v1 DRAFT 不开放此入口（即整个 group 仅一条 DRAFT 记录时不可单独丢弃；删除整个程序的入口见 [§22.13（Q177）](#2213-v1-draft-完全删除q177)）。

点击 → 弹 modal：

```
┌─ 丢弃 DRAFT v{N} ──────────────────────────────┐
│ ⚠ 此操作将软删此 DRAFT，且无法通过 UI 恢复。   │
│   该 group 将回到上一个有效版本（已归档）       │
│   作为当前版本。                               │
│                                                 │
│ 丢弃原因（必填）:  [textarea, 5 行]            │
│                                                 │
│              [取消]   [确认丢弃]                │
└────────────────────────────────────────────────┘
```

调用：`DELETE /procedures/{id}` body `{reason}`；响应 `{deleted_id, new_current_id, new_current_version}`。

后端额外行为（Q175 特殊路径）：

1. 若 `is_current=true AND status='DRAFT' AND version > 1`：
   - 当前记录 `is_active=false`
   - 在同 group 内找 `is_active=true AND status='ARCHIVED'` 中 version 最大的记录 → 设为 `is_current=true`
   - 该原 ARCHIVED 记录的 `status` **保持 ARCHIVED**（不回滚到 PUBLISHED；group 的"上次有效版本"已被归档，要重新进入可编辑态需要 rollback 或 upgrade）
2. 若 `is_current=true AND status='DRAFT' AND version = 1`：拒绝，返 `PROCEDURE_IS_CURRENT`（保留 §13.2 既有约束）
3. 其他场景（非 is_current 删除）：按 §13.2 既有规则

> v1 DRAFT 完全删除（删整个 group）路径见 §22.13（Q177）。

成功后：跳转到新 is_current 版本的编辑器 `/procedures/{new_current_id}/edit`，toast「已丢弃 DRAFT v{N}」。

### 22.12 列表行的版本号与版本数（Q176）

**决策**：程序库列表行的 `name` 旁显 `v{current}` 小灰字；metadata 列显示 `共 {N} 版本` 并支持 hover popover 展开详情。

列表行示意：

```
[QC-0001] 启动 SOP v3   [DRAFT 灰]  · 共 3 版本     2026-05-19  [⋮]
```

字段定义：

| 字段 | 来源 | 说明 |
|------|------|------|
| `v{current}` | 当前行 procedure.version | 小灰字、紧贴 name 右侧 |
| `共 {N} 版本` | 后端 list 接口新增 `version_count_in_group` | metadata 列；hover 展开 popover |

hover popover 内容（按 created_at DESC，最多 10 行 + 「查看更多」链接到 `/procedures/{group_id}/versions` 或版本历史 tab）：

```
┌─ 所有版本 ───────────────────────┐
│ ● v3  DRAFT      2026-05-19      │
│ ○ v2  ARCHIVED   2026-05-15      │
│ ○ v1  ARCHIVED   2026-05-10      │
│                                  │
│            [查看更多]             │
└──────────────────────────────────┘
```

后端 list 接口扩展：

```
GET /procedures?folder_id=...&...
→ 200 { items: [ {id, code, name, version, status, version_count_in_group, ...} ], total }
```

`version_count_in_group` = 同 group 内 `is_active=true` 的所有版本数（含 ARCHIVED）。

deprecated group 因列表过滤已排除（§13.5），此字段在「废止」文件夹列表中可选不返回（或保留显示，按列表上下文一致即可）。

### 22.13 v1 DRAFT 完全删除（Q177）

**决策**：列表行「⋮」菜单中提供 **「删除整个程序」** 入口，仅满足

```
group 中仅 1 条记录 AND version=1 AND is_current=true AND status='DRAFT'
```

时显示。专用接口硬删整 group（含唯一那条 procedure 记录）。

新增后端接口：

```
DELETE /procedure-groups/{group_id}
body: {reason}  # 必填
→ 204 No Content    # 成功硬删
→ 400 PROCEDURE_GROUP_DELETE_FORBIDDEN  # 不满足上述条件
```

后端守卫：

| 检查 | 通过 | 失败 |
|------|------|------|
| group 中 is_active=true 记录数 == 1 | 继续 | `PROCEDURE_GROUP_DELETE_FORBIDDEN` |
| 该记录 version=1 AND is_current=true AND status='DRAFT' | 继续 | 同上 |

成功后：
- 硬删 procedure 记录（同时级联 chapters / steps / attachments / custom_values）
- audit_log 记一条 `action='delete_group_v1_draft'`（特殊 action，永久保留）
- 物理文件清理（attachment storage_path）走 Q115 每日定时任务

modal 文案：

```
┌─ 删除程序「{name}」 ────────────────────────┐
│ ⚠ 此操作将**完全删除**此程序及其全部数据，  │
│   不可恢复（包括章节、步骤、附件）。         │
│                                              │
│ 删除原因（必填）:  [textarea, 5 行]         │
│                                              │
│            [取消]   [确认完全删除]            │
└──────────────────────────────────────────────┘
```

UI 入口位置：
- **仅程序库列表行「⋮」菜单**显示（含「草稿箱」过滤视图）
- 编辑器内**不**提供此入口（避免编辑中误删整个程序）

理由：
- 满足条件 = "刚创建立即反悔"场景；用户不可能在编辑器深度编辑后才走这条路（一旦保存就有 chapters/steps）
- 真正硬删，不走"先废止再永久删"两步路径，对用户更直接
- 列表行更适合作为"管理性"操作的入口，编辑器是"内容性"操作的舞台

### 22.14 publish 时 version_update_notes 是否必填（Q178）

**决策**：分版本号区别处理：

| 当前 version | publish 时 version_update_notes 检查 |
|------|----------------------------------------|
| v1（首次发布） | **可空**；publish 检查列表不显示此项 |
| v2+（升级后发布） | **必填**；publish 检查列表中作为 ✗ 阻塞项 |

publish 检查列表更新（基于 §17.4）：

```
✓ name 非空
✓ 至少 1 个 chapter
✓ folder 非「废止」
✓ 必填自定义字段「适用设备」已填
✓ version_update_notes 非空            ← 新增（仅 v2+ 校验）
✗ 有 3 个节点未保存修改 [一键保存]
✗ Step 1.2.3 未命名（warning，不阻塞）
```

后端 service 守卫（与前端双保险）：在 `POST /procedures/{id}/transition` body `{status: 'PUBLISHED'}` 时校验：

```
if procedure.version > 1 AND empty(procedure.version_update_notes):
    return 400 VERSION_UPDATE_NOTES_REQUIRED
```

新错误码：`VERSION_UPDATE_NOTES_REQUIRED`（400），中文提示：「请先填写本次版本的更新说明」。

理由：
- v1 是程序的"初版"，版本演进信息不适用；强制填会逼用户写"初版"之类的废话
- v2+ 是对已有发布版本的增量改进，需要明确记录"改了什么"，是版本管理的核心价值

**覆盖**：[editor-behavior.md §13.6](editor-behavior.md) 之前的"warning 不阻塞"表述在 v2+ 下被本节覆盖；v1 仍保留 warning 行为。

### 22.15 复制为新程序 UI 入口（Q179）

**决策**：两处入口（编辑器顶栏「⋮ 更多」+ 列表行「⋮」），同款 form modal，提交后跳新程序编辑器。

入口条件：

| 位置 | 显示条件 |
|------|---------|
| 编辑器顶栏「⋮ 更多」 → 「复制为新程序」 | 任意 group 状态（含 deprecated；复制源不变只读时仍允许）|
| 程序库列表行「⋮」 → 「复制为新程序」 | 任意非「废止」文件夹下的行；「废止」内复制需先进入历史视图再用编辑器 ⋮ |

form modal：

```
┌─ 复制程序「{source.name} v{source.version}」 ─┐
│                                                │
│ 目标文件夹（必填）:                            │
│ [文件夹选择器（仅 system=false）]               │
│                                                │
│ 新程序名（选填，默认 = 源名 + " (副本)"）:     │
│ [text input, 默认填 source.name + " (副本)"]   │
│                                                │
│              [取消]   [确认复制]                │
└────────────────────────────────────────────────┘
```

提交：`POST /procedures/{id}/copy` body `{target_folder_id, name?}`

成功后：

1. 后端返回 `{newProc: {id, code, version, ...}}`
2. 前端 `router.push('/procedures/${newProc.id}/edit')`
3. 顶栏正下方非阻塞 banner：`已从 {source.code} v{source.version} 复制创建，新 code: {newProc.code}（v1 DRAFT）。`（kind='copy'）
4. 同时弹 toast `已复制`

> 复制语义见 §十八（Q137-Q140）：复制**所传 `{id}` 那个版本**（Q238 修订 Q138，所见即复制——历史视图查 v2 即复制 v2）的 chapters/steps/attachments 元数据 + custom_values；新 group_id、新 code、version=1、is_current=true、status=DRAFT；mark_status/is_read 重置（Q239）。

§22.4 banner 表扩展加入 `copy` kind：

| 触发 | banner 文案 |
|------|------------|
| copy | `已从 {source.code} v{source.version} 复制创建，新 code: {newProc.code}（v1 DRAFT）。` |

### 22.16 「废止」文件夹列表行的特殊 UI（Q180）

**决策**：复用 ProcedureList 组件但加差异化样式与字段；行为受限。

视觉差异：

- 行整体灰色背景（`#FAFAFA`）+ 比普通行稍降低对比度
- name 旁仍显 `v{current}` 与 `共 {N} 版本`（与 §22.12 一致）
- 额外显示元数据：
  - `废止时间: {deprecated_at}`（取 group 中 deprecate 操作的 audit_log）
  - `废止人: {deprecated_by}`（同上）
  - status chip 后红色「废止」tag（§22.8 配色）

行为受限：

| 操作 | 在「废止」列表行是否可用 |
|------|-----------------------|
| 「⋮」→ 恢复 | ✅（详见 §22.5 / §9.6） |
| 「⋮」→ PDF 下载 | ✅（§13.4 Q105 / Q118）|
| 「⋮」→ 查看审计 | ✅（跳 audit log 视图，过滤 procedure_group_id）|
| 「⋮」→ 复制为新程序 | ❌（如需复制，先恢复或进入编辑器 ⋮）|
| 「⋮」→ 废弃整 group | ❌（已废止）|
| 「⋮」→ 删除整个程序 | ❌（v1 DRAFT 删除入口仅在草稿箱）|
| 「⋮」→ 升级版本 / 回退 | ❌（PROCEDURE_DEPRECATED）|
| 「⋮」→ 移动文件夹 | ❌（PROCEDURE_DEPRECATED）|
| 单击行 / 双击行 | 进入 `/procedures/{id}/view` 只读视图（不可编辑）|

后端 list 接口在 folder.system=true（即「废止」）下需额外返回 `deprecated_at` / `deprecated_by`（从 audit_log JOIN，按性能优化的话可冗存至 procedure 表）：

```diff
tb_procedure:
+ deprecated_at      DATETIME(6) NULL  # 整 group 废止时间（冗存，全 group 一致）
+ deprecated_by      VARCHAR(128) NULL # 操作者标识（冗存）
+ archived_at        DATETIME(6) NULL  # 该条记录转 ARCHIVED 的时间戳（read-only 视图 banner 用）
```

字段在 deprecate 触发时由后端写入所有 group 内记录（同一时间戳与操作者）；restore 时清空（与 deprecated_from_folder_id 一并）。

---

## 二十三、PPA AP-907-005 合规修订（Q181–Q188）

> 来源：基于 `docs/reference doc/pa-procedure-writer-s-manual-pdf-hidden-hippo.md` 的差距评估，对照 *PPA AP-907-005 Procedure Writer's Manual (Rev. 2, 2016)* 标准 procedure 要求，识别出 9 项重大不符。
> 本节只落地 P0（合规必须）4 项决策。P1 / P2 项参见评估文档"四、若要达到 PPA 合规，须做的改动"清单，未来另起 grill 轮次。

### 23.1 Q181 PPA 标准 section 模板

**决策**：**不**在 `tb_procedure` 引入 `procedure_type` enum；**不**强制 PPA 标准 12-section 结构。仅在 [pdf-rendering.md §15](pdf-rendering.md) 列出 PPA Table 1 的 R 类章节作为**最佳实践参考清单**，供编写者手工组织章节树时对照。

**与 PPA §4.13.1 差距**：PPA 要求标准 procedure 强制含 Purpose / Scope / References / Definitions / Responsibilities / Precautions & Limitations / Prerequisites / Instructions / Acceptance Criteria / Retention of Records / Summary of Alterations / Attachments 等章节，本系统**显式接受不强制合规**，标 risk。

**约束变更**：无（不改 data-model，不改 API）。

**Why**：
- 不可变设计第 1 条 §19 章节模型重构刚落地，再加强制模板会冲突（chapter.rich_content 恒空，章节即标题，强制 12 个 chapter 节点会让"自由树"语义破碎）。
- Smart SOP 服务的国内 SOP 场景远超核电 PPA 范畴（工厂作业、行政流程、医院、教培 …）；强制单一行业模板将损害产品通用性。
- 评估报告标注此项为"重大缺失"，但该缺失是**合规判定层**而非**功能层**，可通过文档披露 + 用户自律规避。

**How to apply**：
- 创建 procedure 时编辑器**不**自动生成任何骨架章节，与现状一致（§19）。
- pdf-rendering.md §15 列出 12 个推荐 section 名、用途、PPA 章节号，作为编写者参考。
- 不实现"插入 PPA 标准结构"按钮（保留未来增强空间，但本轮不做）。

### 23.2 Q182 用途级别（Level of Use）

**决策**：`tb_procedure` 新增字段 `level_of_use`，**物理类型 VARCHAR(20) NOT NULL + 应用层枚举校验**（与 `status` 字段惯例一致；逻辑枚举值 `reference` / `continuous` / `information`），创建程序时必选，**无数据库默认值**，对应 PPA §4.11 封面四项必备字段之一。

**字段语义**（PPA §3 Definitions）：

| enum | 中文标签 | 英文标签 | 使用语境 |
|------|---------|---------|---------|
| `reference` | 参考使用 | Reference Use | 操作者熟悉本程序，仅在需要时查阅；不要求逐步对照 |
| `continuous` | 连续使用 | Continuous Use | 操作者必须在执行过程中**逐步对照**程序；安全关键、首次执行、高风险场景 |
| `information` | 信息使用 | Information Use | 程序仅用于背景知识传达（培训材料、概念文档），不直接驱动操作 |

**封面渲染**：在副信息块「程序编号 / 版本」之后增加一行「用途级别: {中文标签} ({英文标签})」。详见 [pdf-rendering.md §3.1](pdf-rendering.md)。

**Why**：PPA §4.11 把 Level of Use 列为封面四项必备字段（与 title / number / revision 同级），是合规底线。enum 三值与 PPA 标准取值一一对应，避免歧义。

**How to apply**：
- 数据库迁移：`ALTER TABLE tb_procedure ADD COLUMN level_of_use VARCHAR(20) NOT NULL`，应用层枚举校验；旧记录初次升级时需要数据迁移脚本逐条回填（默认 `continuous`，由项目业主复核）。
- 创建程序 API（`POST /procedures`）的 body 增加 `level_of_use` 必填字段；缺失返 422 `VALIDATION_FAILED`。
- 编辑器"程序属性"面板增加下拉框，与 risk_level / quality_level 同区。
- PDF 封面强制渲染该行；如旧数据回填错误，封面会显示业主复核值。

### 23.3 Q183 Notes / Cautions / Warnings 三类警示块

> **后续修订**：Q201/Q202（§26.1/§26.2）曾将警示主通道下沉为 `step_alerts` JSON，**再经 Q263（§40.3）改为 `note`/`caution`/`warning` 三个富文本字段**（移除 step_alerts）；本节定义的 HTML class 转为**双轨中的辅通道**（content 节点富文本内嵌）。视觉样式（ANSI Z535 三色）两轨共用，本节样式定义仍然有效。

**决策**：PPA §4.15 三类警示按递进风险语义独立成块，HTML class 拆分为 `note-block` / `caution-block` / `warning-block` 三类，颜色采用 ANSI Z535 标准映射。

**视觉规格**：

| HTML class | 风险等级 | 背景色 | 边框 | 图标 | 标题 | PPA §4.15 对应语义 |
|-----------|---------|-------|-----|-----|-----|------------------|
| `note-block` | 提示性信息 | 浅蓝 RGB(204, 229, 255) | 深蓝 1px 实线 RGB(13, 71, 161) | ℹ | 「注意 NOTE」加粗深蓝 | 强调重要信息，**不**涉及风险 |
| `caution-block` | 设备 / 程序风险 | 浅黄 RGB(255, 217, 102) | 黑色 1px 实线 | ⚠ | 「小心 CAUTION」加粗黑字 | 操作不当会损坏设备、损失数据或导致程序失败；**不**涉及人身伤害 |
| `warning-block` | 人身伤害风险 | 浅红 RGB(255, 205, 210) | 红色 1px 实线 RGB(220, 38, 38) | ⛔ | 「警告 WARNING」加粗红字 | 操作不当会造成人身伤害或死亡 |

**顺序约束（PPA §4.15）**：当同一上下文需同时给出多类警示时，**强制顺序 Note → Caution → Warning**（按严重性递增）。编辑器不做强制校验，但 pdf-rendering.md §7 渲染管线在检测到逆序时打 warning 日志（不阻塞生成）。

**破坏性变更披露**：
- 旧 `warning-block`（Q49，黄底「⚠ 警告」）视觉重定义为**红底「⛔ 警告 WARNING」**。
- 旧版本的 rich_content 中已存在的 `<div class="warning-block">` 节点**重新生成 PDF 时直接渲染为新视觉**（红底），无数据迁移需求。
- 旧含义"设备警告"如需保留语义，编写者须**手工**改为 `caution-block`（PPA 语义对齐）。本轮**不**提供自动转换。

**HTML 协议**：

```html
<div class="note-block">操作前请熟悉本程序的整体流程。</div>
<div class="caution-block">操作前必须断电，否则可能造成设备损坏。</div>
<div class="warning-block">高压未泄放，强行打开可能导致严重烫伤甚至死亡。</div>
```

**Why**：PPA §4.15 三级风险递进是 procedure 安全语义的核心约定（呼应 ANSI Z535 工业警示标准）。原 Q49 单类合并丢失了"设备风险"与"人身风险"的区分，是评估报告标记的"重大不符"。

**How to apply**：
- pdf-rendering.md §7 重写为三个独立子节，每类 class 独立样式定义。
- WangEditor 编辑器需新增"插入 Note / Caution / Warning"三个工具栏按钮（参见 [editor-behavior.md](editor-behavior.md) ，本节落地后另起 PR 调整编辑器）。
- B8 表格（§二 整体架构）同步扩展三类 class 行。

### 23.4 Q184 页码 P/T 统计口径（严格 PPA）

> **后续调整**：Q211（§28.3）把页码**显示位置**从页脚移到**页眉右列第三行**；本节的 P/T 计算口径不变，仅渲染位置变更。下表的「footer 显示」列在 Q211 后改读为「页眉右列第三行显示」。

**决策**：覆盖 Q59；页码体系严格匹配 PPA AP-907-005 §4.6 step 3。

**规则**：

| 页类型 | footer 显示 | P 形式 | T 形式 |
|--------|------------|-------|-------|
| 封面 | **无 footer** | — | — |
| TOC | 显示 | 罗马小写 `i / ii / iii` | 阿拉伯整数（全文档总页数）|
| 修订记录 | 显示 | 罗马小写（接 TOC 续编）| 阿拉伯整数 |
| 正文 | 显示 | 阿拉伯 `1 / 2 / 3` | 阿拉伯整数 |

**T 计算**：T = 封面页数（1）+ TOC 页数 + 修订记录页数 + 正文页数，**含所有页**。

**示例**（封面 1 页 + TOC 2 页 + 修订 1 页 + 正文 9 页，共 13 页）：

| 物理页 | 区段 | footer |
|--------|-----|--------|
| 1 | 封面 | （无）|
| 2 | TOC 第 1 页 | 第 i 页 / 共 13 页 |
| 3 | TOC 第 2 页 | 第 ii 页 / 共 13 页 |
| 4 | 修订记录 | 第 iii 页 / 共 13 页 |
| 5 | 正文第 1 页 | 第 1 页 / 共 13 页 |
| ... | ... | ... |
| 13 | 正文第 9 页 | 第 9 页 / 共 13 页 |

**Why**：PPA §4.6 step 3 字面要求"Page X of Y, where Y is the total number of pages of the procedure, **including the cover**"。原 Q59 决策 T 仅含正文，与 PPA 字面相反，是评估报告标记的"重大不符"。

**How to apply**：
- pdf-rendering.md §6.1 改 footer 公式。
- ReportLab 实现：第一遍 dry-run 时分别统计四个区段页数（cover_pages=1, toc_pages, revision_pages, content_pages），第二遍 footer 渲染时按区段切换 P 的格式（roman.toRoman 转换前置页页码）。
- 不影响 TOC 的页码列：TOC 列出的 chapter 页码仍为正文阿拉伯数字（与 Q46 一致），TOC 列页码不混入罗马数字。

### 23.5 Q185–Q188 附件渲染入 PDF（PPA §4.13.13）

> **后续补充**：Q203（§26.3）新增 `tb_procedure_step.attachment_marks` **步骤级附件标记**（如 mp4，仅标记不嵌入），与本节的**程序级**附件元数据表格**并存**——二者面向不同粒度，互不替代。

#### Q185 渲染范围 — **仅元数据清单**

PDF **只渲染附件的元数据**（文件名 / 大小 / MIME / 上传日期 / 描述），**不嵌入任何文件本体**（不 inline 图片、不缩略 PDF、不解析 Office 文档）。附件文件本身通过 Smart SOP 系统单独访问（与 PDF 同一程序的附件下载接口）。

**Why**：PPA §4.13.13 要求附件作为程序的"组成部分"被列出（可定位、可追溯），但不要求嵌入文件本体；嵌入会让 PDF 体积不可控、生成超时风险陡增；分离访问更符合"程序 + 受控附件"的工业实践。

#### Q186 区段位置 — **正文最后一节**

附件区段渲染为**正文最后一节**，标题与 §15.2.13「13.0 附件 / Attachments」对齐（编号由 §27 编号引擎生成，与其他正文章节统一编排）。

#### Q187 页码与编号 — **沿用正文阿拉伯页码**

附件区段**不独立编号**，页码沿用正文阿拉伯数字（Q184），与正文连续递增。例如正文 1-9，附件 10-12，T = 13。**牺牲** PPA §4.13.13 字面"Attachment X Page 1 of N"独立编号要求，**换取** Q184 整体页码体系的简单一致；评估文档 P1 项可在未来 grill 重新决定。

#### Q188 渲染格式 — **表格式**

附件列表用 ReportLab `LongTable` 渲染，跨页表头重绘（与 [pdf-rendering.md §9.2](pdf-rendering.md) 表格规范一致）。

**列定义**：

| 列 | 字段（来源 [`tb_procedure_attachment`](data-model.md#36-tb_procedure_attachment--程序附件新表)）| 宽度 |
|----|--------------------------------|------|
| 序号 | `sort_order` 升序枚举，从 1 起 | 6% |
| 文件名 | `file_name` | 30% |
| 大小 | `size_bytes`（自动单位转换：KB / MB）| 10% |
| 类型 | `mime_type` | 12% |
| 上传日期 | `created_at`（YYYY-MM-DD）| 14% |
| 描述 | `description`（空则显示「—」）| 28% |

**空附件场景**：若程序无附件，附件区段**整章省略**（不渲染空表头），同时 §15.2.13 对应的 chapter 节点也不强制创建。

#### 数据模型与接口影响

- `tb_procedure_attachment` 已在 [data-model.md §3.6](data-model.md) 定义，**无新增字段**（本轮决策不引入 SHA256 校验和）。
- 附件按 procedure_id 关联，rollback / upgrade 时按 §14 附件版本传递规则复制，已存在的逻辑无需调整。
- PDF 生成流水线在收集附件清单时**仅查询元数据列**，不读 `file_path` 对应的实际文件，磁盘 I/O 不增加。

#### 与 P0-4 评估清单的对照

| 评估项 | 落地状态 |
|--------|---------|
| 附件作为最后 section 渲染 | ✓ Q186 |
| 至少元数据 + 独立编号 "Page 1 of N" | △ 元数据 ✓ / 独立编号 ✗（Q187 沿用正文页码）|
| 文件本身另发链接 | ✓ Q185（通过 Smart SOP 附件下载接口）|

---

## 二十四、最终错误码清单

| 错误码 | HTTP | 触发场景 |
|--------|------|---------|
| `VALIDATION_FAILED` | 422 | 参数校验 |
| `NOT_FOUND` | 404 | 资源不存在 |
| `INTERNAL_ERROR` | 500 | 服务异常 |
| `VERSION_CONFLICT` | 409 | If-Match 不匹配 |
| `IF_MATCH_REQUIRED` | 412 | 修改类请求缺少 If-Match 标头（与 api-spec §4.3 412 状态码对应）|
| `FOLDER_NAME_DUPLICATE` | 409 | 文件夹同父同名 |
| `FOLDER_PREFIX_DUPLICATE` | 409 | 文件夹前缀全局重复（**含历史 code 用过的前缀**，Q249）|
| `FOLDER_DEPTH_EXCEEDED` | 400 | 超过 5 层嵌套 |
| `FOLDER_CYCLE_DETECTED` | 400 | 移动形成循环 |
| `FOLDER_NOT_EMPTY` | 400 | 文件夹含子或程序（删除时）|
| `FOLDER_HAS_PROCEDURES` | 400 | 含程序的文件夹禁止新增子文件夹（容器 xor 叶子，Q247）|
| `FOLDER_SYSTEM_PROTECTED` | 400 | 系统文件夹 |
| `PROCEDURE_CODE_DUPLICATE` | 409 | 程序 code 冲突 |
| `PROCEDURE_FOLDER_REQUIRED` | 400 | 必须指定文件夹 |
| `PROCEDURE_READONLY` | 400 | 非 `is_current=true AND status=DRAFT` 的记录不可改（含 ARCHIVED 与历史版本）|
| `PROCEDURE_STATUS_INVALID` | 400 | 非法状态切换 |
| `PROCEDURE_VERSION_MAX` | 400 | 达到 max_version_number 上限 |
| `CHAPTER_DEPTH_EXCEEDED` | 400 | 章节超过 3 级嵌套（Q190 二次修订回 3 级）|
| `CHAPTER_HAS_CHILDREN` | 400 | 转换 chapter→step/content 时含子节点 |
| `SIBLING_TYPE_CONFLICT` | 400 | 子节点类型互斥违反 |
| `MARK_SELECTION_TOO_LARGE` | 400 | 标记超过 100 项 |
| `MARK_SELECTION_CROSS_PARENT` | 400 | 标记跨 parent |
| `APPLY_MARKS_FAILED` | 400 | 应用标记事务失败（含详情）|
| `PARSE_FILE_INVALID` | 400 | 非 .docx 格式 |
| `PARSE_FILE_TOO_LARGE` | 413 | 超 50 MB |
| `PARSE_FAILED` | 400 | 解析过程报错 |
| `PARSE_TEMPLATE_INVALID` | 400 | 标准模式模板校验未通过 |
| `IMAGE_TOO_LARGE` | 413 | 单图 > 10 MB（Q207 由 1MB 放宽至 10MB）|
| `CONTENT_TOO_LARGE` | 413 | rich_content > 5 MB |
| `UNSUPPORTED_IMAGE_FORMAT` | 400 | 不支持的图片格式 |
| `FIELD_KEY_DUPLICATE` | 409 | 自定义字段 key 全局重复 |
| `FIELD_KEY_RESERVED` | 400 | 与系统保留字冲突 |
| `FIELD_VALUE_INVALID` | 422 | 字段值不符合 validation_rules |
| `ATTACHMENT_TOO_LARGE` | 413 | 附件单文件 > 50 MB |
| `ATTACHMENT_NOT_FOUND` | 404 | 附件被引用但文件已删 |
| `ROLLBACK_REASON_REQUIRED` | 400 | rollback 未填 reason |
| `ROLLBACK_TARGET_INVALID` | 400 | rollback 目标版本不存在或非同 group |
| `PDF_TIMEOUT` | 504 | PDF 渲染超时 60 秒 |
| `PDF_GENERATION_FAILED` | 500 | ReportLab 内部异常 |
| `PARSE_NO_HEADINGS` | 400 | 解析后 chapters=[]（文档无 heading）|
| `PARSE_TIMEOUT` | 504 | 后端解析超过 30 秒 |
| `PROCEDURE_DEPRECATED` | 400 | 对已 deprecate 的 group 调修改类接口 |
| `PROCEDURE_IS_CURRENT` | 400 | 试图 DELETE is_current=true 的记录 |
| `PROCEDURE_DRAFT_EXISTS` | 409 | 并发 upgrade-version / rollback 时同 group 已存在 DRAFT（DB 部分唯一约束冲突，Q224）|
| `RESTORE_FOLDER_MISSING` | 400 | restore 时原文件夹已软删 |
| `ATTACHMENT_LIMIT_EXCEEDED` | 400 | 单 procedure 附件数 > 30 或总大小 > 200MB |
| `FIELD_TYPE_IMMUTABLE` | 400 | 试图修改 ProcedureField.field_type |
| `FIELD_KEY_IMMUTABLE` | 400 | 试图修改 ProcedureField.key |
| `CONVERT_TO_CONTENT_DEPRECATED` | 410 | 章节模型重构后该接口废弃 |
| `UPLOAD_TOKEN_INVALID` | 400 | upload_token 不存在或已过期 |
| `CHAPTER_RICH_CONTENT_NOT_ALLOWED` | 400 | 试图给 chapter 节点写入 rich_content |
| `PROCEDURE_GROUP_DELETE_FORBIDDEN` | 400 | DELETE /procedure-groups/{group_id} 守卫不通过（非 v1+DRAFT+唯一记录）|
| `VERSION_UPDATE_NOTES_REQUIRED` | 400 | publish 时 v2+ 版本 version_update_notes 为空 |

---

## 二十五、Word 解析器重构（Q189–Q200）

> 本节基于对 7 份真实 SOP（`docs/reference doc/typical word doc/`，含 2 份零样式文档）的实测验证 + 一轮 grill 得出，
> 解决 [word-parser-solution.md §11](word-parser-solution.md) 标注的 6 处冲突。
> **总方向：保留既有 content 子节点 + 块 HTML + WangEditor 5 模型，仅做 4 项针对性改进。**
> 详细实现设计与验证脚本见 [word-parser-solution.md](word-parser-solution.md)。

### 25.1 数据模型 / 图片 / 富文本（Q189）

- **保留**既有：chapter + content 子节点、rich_content = 块结构 HTML、WangEditor 5。**否决** word-parser-solution v3 的 3 表 / content_ast(JSON) / ProseMirror 设计（不推翻不可变设计 #1）。
- **唯一改动**：图片从 base64 内联改为 **assets 表 + URL 引用**。rich_content 里 `<img src="data:...">` → `<img src="/api/procedures/{id}/assets/{asset_id}">`。
- **理由**：base64 内联导致单 TEXT 字段可达 40MB、无去重、无 CDN、无独立鉴权。外置图片是低风险高收益的针对性修复。

### 25.2 图片抽取时机与生命周期（Q193 / Q197）

- **parse 阶段**：抽图到 `tmp/uploads/{token}/media/`，rich_content 在 review 阶段引用临时 URL。**parse 不落库**（与 §9.1 一致）。
- **import 阶段**：临时图提升为永久 `asset`（uuid + sha256 全库去重 + mime + size + width/height）。
- **引用追踪与 GC**：维护 `asset_reference` 关联表（asset_id, procedure_id）。每次 save/import 解析 rich_content 里的 asset URL 重建引用；`ref_count = 关联表 count`；count=0 时 GC 物理删除。token 过期连同 docx + 临时图一起清理（孤儿临时图不入永久表）。

### 25.3 标题层级（Q190 / Q194；Q190 二次修订回最多 3 级）

- **章节最多 3 级**（Q190 二次修订：曾改 6 级，现回 3 级——31 份真实文档最深仅 N.N.N=3 级，且与用户思路一致）。**保留 Q35 的「H4-6 / 更深编号压缩为 L3」**（可加 `<strong>` 标记体现降级）。
- 后端整树重算编号最多 3 级（`1.1.1`）；解析遇更深编号 → cap 到 L3。
- PDF / UI **可配置**「>N 级折叠 / 缩进」渲染——显示压缩只是渲染参数，与存储保真解耦。
- 错误码 `CHAPTER_DEPTH_EXCEEDED` 阈值由 3 改为 **6**。

### 25.4 正文起点判定（Q191 / Q196）—— 取代 Q37

- **删除**既有「最后一个 section break」规则（7 份实测 **0/5 命中**：真实 SOP 的 section break 散落正文中段，取最后一个会跳到文档末尾）。
- **新规则（兜底链）**：`first_styled_heading` → `TOC field end` → 启发式首个高分标题 → 跳封面兜底。
  - `first_styled_heading`：styles.xml 反查后的首个样式标题段（5/5 精准命中"目的"）。
  - 反查 4 级：标准名(`heading N`/`标题 N`) → 中文同义词词典 → 自身 outlineLvl → basedOn 链上溯。
  - **TOC 防陷阱约束**：若文档存在 TOC 字段，`first_styled_heading` 取值必须 **≥ `toc_field_end`**（先跳过目录区再找首个样式标题）。否则目录项若带 heading 样式（手工搭 TOC、或 basedOn 上溯到 heading 的样式）会令起点误落在目录内。验证的 5 份用 `toc 1/2/3` 样式（非 heading）才未触发，不能依赖此巧合。
- **删除** word-parser-solution 初版的 `bookmark _Toc` 信号（`_Toc*` 是 TOC 跳转目标遍布正文标题，会误判到末尾）。

### 25.5 smart 模式升级为「自动预标 + 置信度 + 纠偏」（Q192 / Q199 / Q200 / Q198）

零样式文档（无 heading 样式、纯编号/纯视觉，如「危险源监控措施」「有限空间作业管理办法」）在旧 smart 模式下解析出 **0 章节**。升级方案 C：

- **置信度分级**（heading_score）：
  - HIGH（≥0.85，仅样式类信号）→ 自动应用，**免确认**。
  - MEDIUM（0.5–0.84，启发式强信号）/ LOW（0.3–0.49，弱信号）→ `markStatus='review'`，**进纠偏面板**。
  - 启发式封顶 0.84，永不自动 HIGH → 非标准标题必经人工确认。
- **import 前必须清空所有 review**（沿用既有强制约束，保 100% 人机协同）。
- **启发式信号**（无样式时）：字号相对化(p85) + 加粗占比 + 编号模式 + 短段 + 后跟正文。**等字号自适应**：检测全篇单一字号时字号信号归零、编号信号补偿。
- **编号分级字典**（v4，26 份 QMS 打磨后）：`一、`/`第X章`→L1，`第X节`→L2，`第X条`→L3 弱标题，`1.1`/`1.1.1`按点深度→L2/L3，`N.`/`N 空格`（`1 目的`）→L1（排除 `N / M` 页码），**`N、`（`1、目的`）与 `N+中文直接`（`6相关文件`）→ weak_heading（顿号歧义，需粗体/上下文才升，Q217 修订）**，`(一)`/`(1)`/`N)`/`N）`→list 不升。**误报抑制**：标题型编号需附加短段判据，长段（号+正文同段）大幅降权。
- **重复块剔除 + cover-skip**：出现 ≥3 次的相同文本（页眉表格如 `第X章…`/`程序文件`/`页码`）与 `N / M` 页码 → 解析时剔除（防页眉混入正文）；`find_body_start` 跳到首个「带编号或样式」的标题（跳过封面/签名块，§25.4）。
- **模式批量提升（Q200，按组选择性）**：parse 返回 `detected_patterns[]`（**扫描全部正文段含融合式长段**按编号前缀归组：模式 + 计数 + 建议 level + 样例）；前端 step3 纠偏面板**按组勾选提升**（如选 `第X章×6`、跳过 `第X条×30`）——**不可一键全提升**（实测 blanket 全升使 precision 跌至 0.64，`第X条` 被误升）。
- **样式映射记忆（Q198）**：用户确认非标准样式（如「章节标题」=L1）后，默认仅本文档生效；纠偏面板提供「记住此样式」勾选 → 写组织级 `heading_style_map` 表，下次同样式自动 HIGH。
- **验证（5 份零样式 fixture，[word-parser-solution.md C.10](word-parser-solution.md)）**：v3 自动 **Precision 1.0 / Recall 0.70 / F1 0.83**（零误报，泛化无 FP）；recall 缺口 = 融合式「号+正文同段」子标题（`3.1 质量部是…`），机器故意不自动升、靠按组选择性模式批量兜，达 micro Recall 0.99。脚本 scripts/validate_unstyled_v3.py。

### 25.6 流程对齐（Q195）

- **沿用既有 parse→import**：parse 返回 ParseResult JSON（不落库），纠偏在前端 step3，import 才落库。前端用 sessionStorage 暂存（既有机制）。
- **废弃** word-parser-solution 早期会话（Q183/Q184/Q185）的「同步两步 + procedure_draft 临时表」设计——那是被否决的 v3 模型的遗留。

### 25.7 本节取代/修订的既有决策

| 既有决策 | 状态 |
|---|---|
| Q35（H4-6 压 L3 + `<strong>`）| **保留**（Q190 二次修订回 3 级后，Q35 压缩规则继续有效）|
| Q-C7（章节最大嵌套 3 级 / level ≤ 3）| **保留 3 级**（Q190 曾改 6、现二次修订回 3，与 Q-C7 一致）；`CHAPTER_DEPTH_EXCEEDED` = 3 |
| Q37（最后 section break 为正文起点）| **取代** → first_styled_heading 兜底链（25.4）|
| §9.2 图片 = base64 内联 | **修订** → assets 表 + URL（25.1/25.2）|
| §9.3 smart 模式 Heading 检测 | **增强** → 置信度分级 + 纠偏 + 模式批量（25.5）|
| `CHAPTER_DEPTH_EXCEEDED` = 3 级 | **修订** → 6 级 |
| `PARSE_NO_HEADINGS`（chapters=[]）| **修订** → 仅 standard 模式或启发式也零命中时触发；smart 模式零样式文档应产出 review 候选而非空 |
| word-parser-solution v3：3 表 / ProseMirror / content_ast | **否决**（保留既有 content-node + HTML）|
| word-parser-solution 早期 Q183-185：draft 临时表 | **废弃**（沿用 parse→import）|

> **不变**：content 子节点模型、rich_content 块 HTML、WangEditor 5、parse 不落库、import 前清 review、整树重算编号 —— 均保留。

---

## 二十六、PDF 预览交互与步骤字段化（Q201–Q204、Q213）

> 来源：用户对 PDF 预览的 PPA 化补充要求。核心方向：把**警示**与**附件标记**从「富文本/程序级」下沉到**步骤结构化字段**，并把 signoff 在**预览层**做成可勾选交互。本节修订/补充 §23 的 Q183、Q185-Q188。
> 编号说明：Q189–Q200 已被 §25 Word 解析器重构占用，本批顺延至 Q201。
>
> **⛔ 部分推翻**：本节 Q201/Q202 的 `step_alerts` JSON 主通道已被 **Q263（§40.3）推翻** → 改为 `note` / `caution` / `warning` 三个富文本字段，**移除 `step_alerts`**。下文 Q201/Q202 关于 step_alerts 字段形态仅作历史保留；现行以 [§40.3](#403-q263-警示三富文本字段-notecautionwarning方案-a修订-q201q202q219q220) 为准。Q203 attachment_marks、Q204 signoff 维持不变。

### 26.1 Q201 警示三类下沉为步骤字段（step_alerts）

**决策**：`tb_procedure_step` 新增 `step_alerts` JSON 字段（数组，每项 `{level: note|caution|warning, content, sort_order}`），作为 PPA §4.15 三类警示的**结构化主通道**。详见 [data-model.md §3.5](data-model.md#35-tb_procedure_step--程序步骤)。

- 一个 step 可含多条、任意类型警示；PDF 渲染时**强制按 Note→Caution→Warning 排序**，同级按 `sort_order`。
- 现有 `notes` TEXT 字段**语义收窄**为「普通备注」，不再承载警示。
- 编辑器在 step 编辑区提供「+ Note / + Caution / + Warning」三个按钮，逐条增删改排（UI 细节见 [editor-behavior.md](editor-behavior.md)，本节落地后另起 PR）。

**Why**：用户要求"Notes/Cautions/Warning 在步骤字段中填写"。结构化字段相比富文本 div 的优势：可校验 level 枚举、可程序化排序（保证 PPA 顺序）、可被执行/审计系统读取、不依赖编写者在 WangEditor 里手插 class。

**How to apply**：
- 数据迁移：旧 `notes` 内容保留为普通备注；不自动迁移为 warning（语义不明，由编写者手工归类）。
- step 渲染顺序见 [pdf-rendering.md §6.3](pdf-rendering.md)。

### 26.2 Q202 step_alerts 与 HTML class 双轨并存

**决策**：警示有**两条渲染通道**，并存不互斥：

| 通道 | 载体 | 适用 | 主/辅 |
|------|-----|------|------|
| `step_alerts` 字段 | `tb_procedure_step.step_alerts` JSON | **step 级**警示（绑定到具体步骤）| 主 |
| HTML class（Q183）| content 节点 `rich_content` 内 `<div class="note/caution/warning-block">` | **chapter 正文级**警示（非 step 的正文段落中内嵌）| 辅 |

- 两轨**视觉样式完全一致**（ANSI Z535 三色，见 [pdf-rendering.md §7](pdf-rendering.md)）。
- step 既可填 `step_alerts`，其 content 富文本里也可有 class block；PDF 各自渲染，互不去重。

**Why**：step 有结构化字段最干净，但 chapter 正文（非 step 的 content 节点）也需要警示能力，HTML class 不能废。双轨覆盖两种粒度。

### 26.3 Q203 步骤级附件标记（attachment_marks）

**决策**：`tb_procedure_step` 新增 `attachment_marks` JSON 字段（数组，每项 `{name, kind, note}`），作为**步骤级附件标记**。详见 [data-model.md §3.5](data-model.md#35-tb_procedure_step--程序步骤)。

- **仅作标记**：PDF 渲染为「📎 附件: {name}（{kind 中文}）」纯文本，**不嵌入文件、不生成链接、不要求文件已上传**。典型用途：在步骤里标注「见 operation_demo.mp4」。
- `kind` 建议值：`video` / `image` / `doc` / `audio` / `other`。
- **与程序级附件表格（Q185-Q188）并存**：
  - 程序级 `tb_procedure_attachment` = 真实上传文件 + 元数据表格（程序末节渲染）。
  - 步骤级 `attachment_marks` = 步骤内的引用标记（无文件实体）。
  - 二者面向不同粒度，互不替代、互不同步。

**Why**：用户要求"附件仅作附件标记，比如 mp4，在步骤字段中填写"。视频等大文件不适合上传/嵌入 PDF，但步骤需要标注其存在与位置。轻量标记满足该场景，又不破坏已落地的程序级附件表格。

**How to apply**：step 渲染位置见 [pdf-rendering.md §6.3](pdf-rendering.md)。

### 26.4 Q204 signoff 可勾选激活（前端预览层交互）

**决策**：PDF **预览**采用**前端渲染层**（基于后端返回的结构化数据在前端渲染可交互视图），signoff / `require_confirmation` 勾选框 / hold-point 签名区在预览中**可点击勾选激活**；勾选状态**仅前端临时记录**（组件内 state），**不写回程序数据、不改后端生成的 PDF 文件**。

**路径**（Q213 细化为四路径，详见 §26.6）：预览层可勾选 → **打印**走浏览器打印预览层（勾选所见即所得）；**下载 PDF** 仍后端 ReportLab 空框（正式电子交付物）。

**Why**：用户要求"signoff 在 PDF 预览页面设置成可勾选激活的模式"。真 PDF 的 AcroForm 表单域中文字体坑多、实现复杂；前端预览层交互更轻、体验更好，且不污染作为受控交付物的下载版 PDF（下载版仍是空框手签，符合 §3.3 / §6.3 纸质惯例）。

**待澄清/影响**：
- 前端预览层需复刻 ReportLab 的版式（封面/TOC/正文/警示/签名），是较大前端工程；分阶段问题**已由 Q237（§34.4）定为「一次性完整复刻、不分阶段」**。
- 数据来源**已由 Q234（§34.1）定为**复用 `GET /procedures/{id}` + 删除后端 base64 `/pdf-preview`；页码取后端 `pdf-layout`（Q235）。
- 勾选状态的目的**已由 Q213（§26.6）澄清**：服务于"展示 + 打印"，不持久化、不留痕、刷新即丢失。

### 26.5 本节修订/补充的既有决策

| 既有决策 | 状态 |
|---|---|
| Q183（警示 HTML class 三类）| **补充** → 降为双轨辅通道，主通道改 `step_alerts`（26.1/26.2）|
| Q185-Q188（程序级附件元数据表格）| **补充** → 新增并存的步骤级 `attachment_marks`（26.3），程序级表格不变 |
| step `notes` 字段语义 | **收窄** → 仅普通备注，警示移至 `step_alerts`（26.1）|
| PDF 预览=后端静态 PDF（隐含）| **修订** → 预览改前端可交互渲染层，下载仍后端 ReportLab（26.4）|

> **后续已落地（§28 / Q209-Q212）**：procedure 模板推荐 → §28.1/§28.2；页眉页面统计 → §28.3；Word 解析警示映射 → §28.4（最终决策为「**不识别**警示语义」，**非**补 note/caution class 映射）。

### 26.6 Q213 signoff 勾选的目的与打印路径

**决策**：signoff / `require_confirmation` 确认框 / hold-point 签名区的勾选，目的是**展示 + 打印**——用户在预览层勾选后，**所见即所得地打印出带勾选的版本**。勾选**不**用于执行留痕、**不**跨会话持久化。

**四条路径**（详见 [pdf-rendering.md §6.7](pdf-rendering.md)）：

| 路径 | 实现 | 勾选呈现 |
|------|------|---------|
| 屏幕预览 | 前端渲染层 | 可点击勾选（state 临时）|
| **打印**（主）| 浏览器 `window.print()` 打印前端预览层 + 打印 CSS | **勾选 ☑ 所见即所得输出** |
| 下载 PDF | 后端 ReportLab 静态 PDF | 空框 ☐（正式电子交付物）|
| 导出已勾选 PDF（可选增强）| 后端 ReportLab + 前端传当前勾选项 id 列表 | 按勾选渲染 ☑（与下载版同版式）|

**Why**：用户明确勾选目的 = 展示打印（非执行追踪）。Smart SOP 是 SOP 编写/发布平台，不是执行追踪系统，故勾选无需持久化或留痕——用户在预览勾好、即时打印一份带勾选的工作副本即可。浏览器打印预览层是所见即所得、零后端往返的最直接实现；下载版保持空框作为受控电子交付物。

**How to apply**：
- 前端预览组件维护勾选 state；提供「打印」按钮触发 `window.print()`，配打印 CSS（`@media print` 隐藏工具栏、仅保留文档版式）。
- 勾选 state 刷新即丢失（符合一次性展示打印目的，不写库）。
- 「导出已勾选 PDF」为可选增强：前端把勾选项 id 列表 POST 给后端 PDF 接口，ReportLab 对命中项渲染 ☑；本轮可不实现，仅预留接口形态。

**修订**：本节细化 §26.4（Q204）——把原「下载 / 打印」合并路径**拆开**：打印走预览层（带勾选所见即所得），下载走 ReportLab（空框正式交付物）。

---

## 二十七、Word 解析器实现细节（Q205–Q208）

> 续 §25 Word 解析器重构，把保留既有 content 子节点 + 块 HTML 模型的方向具体化到实现。
> 编号说明：Q201–Q204 已被 §26 PDF 预览占用，本批顺延至 Q205。
> 实现设计与验证脚本见 [word-parser-solution.md](word-parser-solution.md)。

### 27.1 Q205 表格落 rich_content 标准 HTML（含 vMerge 真实跨度 + 表内图）

**决策**：表格序列化为**标准 `<table>` HTML** 存入 content 节点 rich_content：

- 合并单元格用 `<td rowspan colspan>`；Normalizer **双 pass** 计算 vMerge 真实纵向跨度（修复 DPMS rowspan 恒=1 的 bug）。
- 表内图嵌入单元格 `<td>...<img src="/api/.../assets/{asset_id}">...</td>`。
- 对齐 WangEditor 5 原生表格 HTML 能力，可直接编辑。

**Why**：实测 2/5 文档有 vMerge、4/5 有表内图，是真实硬约束。标准 HTML 与既有 rich_content=HTML 模型一致，WangEditor 可直编，无需额外渲染层。**否决**结构化 JSON 独立字段（与 HTML 模型冲突）与拍平纯文本（违反 100% 表格）。

### 27.2 Q206 含内联图的段落整体保留为一个 content 节点

**决策**：含内联图的段落整体作**一个** content 节点，rich_content = `<p>文字<img src=asset>文字</p>`，保留图在句中的原位置。

- **修订 §9.2** 的「图片必拆独立 content 节点」→ 改为「**独立成段**的图才拆独立节点；**段中内联图**随段落保留」。
- 保证顺序保真（图相对文字的位置不丢）。

**Why**：Word 内联图在段落 run 里。严格拆分会丢失"图在句中"的位置。保内联与 Q189 保 HTML 模型一致。

### 27.3 Q207 图片大小/格式限制放宽

**决策**：图片外置 assets 后（不再 base64 膨胀）：

- 单图上限 **1MB → 10MB**（错误码 `IMAGE_TOO_LARGE` 阈值改 10MB）。
- 格式白名单：`png / jpg / jpeg / gif / bmp / webp / emf / wmf`（覆盖 Word 常见）。
- **`emf / wmf`（粘贴矢量图）服务端转 png** 后入 assets，保渲染兼容。

**Why**：base64 内联时 1MB 限制是为控单字段膨胀；外置后无此顾虑，真实 SOP 截图/流程图常 >1MB。emf/wmf 是 Word 粘贴常见矢量格式，需转码。

### 27.4 Q208 非标准标题学习闭环：两层词典

**决策**：

- `heading_synonyms.yaml`：**内置默认词典**（`章节标题`/`章标题`/`节标题`/`小节标题`/`条标题`…），随代码发布。
- `heading_style_map`：**运行时组织级表**，用户在纠偏面板「记住此样式」（Q198）写入。
- **优先级**：查询时 `heading_style_map`（DB）**覆盖** `heading_synonyms.yaml`（静态）。

**Why**：默认词典随代码走、改动可控；用户学习结果入库，跨文档复用，不需发版。两层兼顾稳定性与可学习性。

**编号分级字典补充（§29.4/Q217，26 份 QMS 打磨后修订）**：`1、2、3、`（阿拉伯+顿号）**不再硬判 list**，改 **weak_heading（上下文/粗体判定）**——`1、目的`（QMS 章节，粗体短）→ 标题；`1、设有消防…`（危险源条款，长/非粗体）→ content。同理 `6相关文件`（数字直接接中文）→ weak_heading。纠偏面板「本文档将 N、视为标题」开关保留为边缘兜底。

### 27.5 本节修订的既有决策

| 既有决策 | 状态 |
|---|---|
| §9.2 图片必拆独立 content 节点 | **修订** → 仅独立成段的图拆节点，内联图随段保留（27.2）|
| §25.1 表格 HTML（方向）| **细化** → 标准 `<table>` + rowspan/colspan + 表内 `<img>`（27.1）|
| `IMAGE_TOO_LARGE` = 1MB | **修订** → 10MB（27.3）|
| `UNSUPPORTED_IMAGE_FORMAT` 白名单 | **明确** → png/jpg/gif/bmp/webp/emf/wmf，emf/wmf 转 png（27.3）|

---

## 二十八、procedure 模板与页眉布局（Q209–Q212）

> 来源：用户对 PDF 预览的 PPA 化补充需求（第二批）。本节落地 procedure 模板机制、页眉布局、Word 警示映射策略。
> 编号说明：Q205–Q208 已被 §27 占用，本批顺延至 Q209。

### 28.1 Q209 procedure 模板机制（创建时可选，不引入 type）

> **⛔ 本决策被 §44（Q290）推翻**：procedure template 功能整体废弃——其能力与已成熟的**程序复制（copy）**高度重叠，改用「**模板库系统文件夹 + copy**」模式（模板 = 模板库里的样板程序，新建 = 从模板库复制）。`tb_procedure_template` 表删除。详见 [§44](#四十四模板库替代-procedure-templateq290q293)。下文 Q209/Q210/Q218 仅作历史保留。
>
> ~~后续修订（Q218 / §30.1）：模板存储从「后端硬编码常量」升级为 `tb_procedure_template` 表全功能管理~~（已被 Q290 整体废弃）。

**决策**：提供**后端预设模板集**，创建程序时**可选**一个模板 → 自动生成章节树骨架（真实 `tb_procedure_chapter` + 预置 `tb_procedure_step` 记录）；不选则空白程序。模板仅是**一次性脚手架**，**不引入** `procedure_type` 字段，生成后用户可自由增删改（无强制约束）。**与已落地 Q181 兼容**（Q181 是"不强制结构"，Q209 是"可选脚手架"，二者不冲突）。

**实现要点**：
- 模板定义为**后端预设常量**（如 `backend/app/services/template/presets.py`），不入库、不可在线编辑（本轮）。
- 创建程序 API（`POST /procedures`）增加**可选**参数 `template_key`（`general` / `testing` / `maintenance`，缺省 = 空白）。
- 后端按 template_key 在事务内批量创建 chapter + step 记录，编号由 §27 编号引擎生成。
- 生成的章节/步骤与手工创建的**完全等价**，无特殊标记。

**Why**：用户要"根据本系统步骤配置推荐 procedure 模板"。可选脚手架既满足"开箱即用的 PPA 结构 + 示例 step"，又不牺牲 Q181 的通用性（不强制、不锁类型）。

### 28.2 Q210 模板内容（多套模板 × 对应 step 类型）

> **⛔ 被 §44（Q290）推翻**：不再有 tb_procedure_template 的 `body`；三套预设改为**模板库系统文件夹里的三个样板程序**（种子）。下述三套**结构内容仍是样板程序的初始内容蓝本**，但载体从 JSON body 改为真实 procedure。详见 [§44](#四十四模板库替代-procedure-templateq290q293)。
>
> **⛔ 型名/字段已更名（Q261/Q263）**：实现种子时下文 step 类型按现行 12 型映射 `text→COMMON` / `pass_fail→CHECK` / `measurement→NUMBER`（NUMBER 用 min/max/unit/decimal_places）；`step_alerts` 已废，警示改填 `note`/`caution`/`warning` 三富文本字段。蓝本结构不变，仅术语对齐。

**决策**：提供三套预设模板，各自侧重本系统不同 `input_schema` 类型，均含 PPA 核心 section 骨架（对齐 [pdf-rendering.md §15](pdf-rendering.md) 参考清单）。

**通用类 `general`**（text 为主）：

| 编号 | section（chapter）| 预置子节点 |
|------|------------------|-----------|
| 1.0 | 目的 Purpose | 空 content 节点 |
| 2.0 | 范围 Scope | 空 content 节点 |
| 3.0 | 引用文件 References | 空 content 节点 |
| 4.0 | 职责 Responsibilities | 空 content 节点 |
| 5.0 | 注意事项与限制 Precautions | 空 content 节点 |
| 6.0 | 前提条件 Prerequisites | 空 content 节点 |
| 7.0 | 操作步骤 Instructions | 1 个 **text** 示例 step |
| 8.0 | 记录保存 Retention of Records | 空 content 节点 |
| 9.0 | 修订摘要 Summary of Alterations | 空 content 节点 |

**测试类 `testing`**（measurement 为主）= 通用类 + 以下调整：

| 调整 | 内容 |
|------|------|
| 7.0 操作步骤 | 预置 1 个 **measurement** step（含 upper_limit/lower_limit/unit 占位）|
| 新增 8.0 专用工具与材料 Special Tools | 空 content 节点（原 8.0/9.0 顺延为 9.0/10.0）|
| 新增 验收准则 Acceptance Criteria | 下挂 1 个 **measurement** step（合格判定）|

**维护类 `maintenance`**（pass_fail + hold-point 为主）= 通用类 + 以下调整：

| 调整 | 内容 |
|------|------|
| 7.0 操作步骤 | 预置 1 个 **pass_fail** step + 1 个含 `step_alerts`（caution）且 `require_confirmation=true` 的 step |
| 新增 8.0 专用工具与材料 Special Tools | 空 content 节点 |

**Why**：三套模板覆盖本系统三种执行记录类型（text/pass_fail/measurement），让模板"开箱即用地演示系统能力"，并把 step_alerts（Q201）/ require_confirmation 等字段在示例里展示。

**附件 section 说明**：三套模板均**不**预生成「附件 / Attachments」section（PPA §15.2.13）——附件区段由 PDF 渲染层（[pdf-rendering.md §6.6](pdf-rendering.md)）在程序有附件时**自动追加**虚拟 chapter，无需模板预建空 chapter（预建空 chapter 在无附件时会渲染出空标题）。若用户希望附件章节出现在 TOC，可手工创建 `name='附件'/'Attachments'` 的 chapter（衔接逻辑见 [pdf-rendering.md §6.6.2](pdf-rendering.md)）。

### 28.3 Q211 页眉布局（一行两列）

**决策**：页眉改为**一行两列**，页码从页脚移到页眉右列第三行。详见 [pdf-rendering.md §6.1](pdf-rendering.md)。

| 区域 | 内容 | 来源 |
|------|-----|------|
| 左列 | 程序标题（垂直居中、左对齐）| `procedure.name` |
| 右列第 1 行 | `程序编号: {code}` | `procedure.code` |
| 右列第 2 行 | `版本: Rev.{version}` | `procedure.version` |
| 右列第 3 行 | `第 {P} 页 / 共 {T} 页` | 渲染计算（P/T 规则见 Q184）|

- 页脚**不再重复页码**（Q184 的 P/T 计算规则不变，仅显示位置变更，见 §23.4 调整注）。
- 前置页（TOC/修订）右列第三行用罗马小写；封面无页眉。

**Why**：用户指定页眉布局——左标题、右三行（编号/版次/页码），把"页面统计"集中到页眉。页码单点显示（页眉）避免页眉页脚重复。

### 28.4 Q212 Word 导入警示映射（暂不识别）

**决策**：Word 解析**不主动做警示语义识别**——不扫描「警告/注意/小心/Note/Caution/Warning」关键词、不把特定样式段落识别为警示。所有段落（含语义上是警示的）统一作为**普通 content 节点正文**导入。用户导入后**手工**归类：在 step 编辑区填 `note`/`caution`/`warning` 三字段（Q263 取代原 step_alerts），或在富文本手插 `note/caution/warning-block` class（Q183）。

**Why**：自动识别警示语义在中文 SOP 里误判率高（"注意"等词常作普通用语），且与已落地的双轨警示（Q202）归属逻辑复杂。暂不识别、由用户手工归类，最稳妥；待积累样本后再考虑启发式（未来 grill）。

**对 §9.2 的影响**：§9.2 Word 映射表加注「不识别警示语义，警示段落走普通 `<p>` content 节点」。原表中 `warning-block` 等 class 映射仅适用于 Word 源 HTML 已显式含该 class 的罕见情形（如本系统往返），常规 docx 不产生 class。

### 28.5 本节落地/影响

| 项 | 落地 |
|----|------|
| Q209 模板机制 | 后端预设 + `POST /procedures` 加可选 `template_key`；无数据模型字段变更（不引入 procedure_type）|
| Q210 模板内容 | 三套预设（general/testing/maintenance），见 28.2 |
| Q211 页眉布局 | [pdf-rendering.md §6.1](pdf-rendering.md) 重写；§23.4 加位置调整注 |
| Q212 Word 映射 | §9.2 加注；不识别警示语义 |

> **本节遗留已全部落地**（原「仍未落地」三项后续均已 grill 解决）：① 模板在线自定义 → §44（Q290–Q293）废弃后端硬编码模板，改「模板库系统文件夹 + copy」，模板即可在线编辑的程序；② 签名/勾选状态前端持久化（Q204 遗留）→ Q213/§26.6 明确**决定不持久化**（勾选刷新即丢，目的=展示+打印）+ Q236 导出已勾选 PDF 仅预留；③ 步骤级附件标记的编辑器 UI → §30.3（Q220）独立「附件标记」子区。

---

## 二十九、Word 解析器补充实现决策（Q214–Q217）

> 续 §25/§27，补齐 4 个实现层开放项（独立设计评估发现）。
> 编号说明：本批 grill 本地标 Q213–Q216，落地避让并行会话已占用的 Q213，**全局取 Q214–Q217**。

### 29.1 Q214 编辑器图片上传端点

**决策**：新增 `POST /procedures/{id}/assets`（multipart `file`）。WangEditor 选图即上传，后端按 sha256 去重入 `tb_procedure_asset`、返回 asset URL，编辑器插入 `<img src="/api/procedures/{id}/assets/{asset_id}">`。procedure 已存在 → **即时入库**（不走 parse 的 tmp 暂存）。

**Why**：编辑器图片必须与 Q189 一致走 assets（不再 base64）。编辑场景 procedure 已落库，直传即时入库最直接；save 时 `asset_reference` 重建顺便对账（Q197）。区别于附件通道（attachment 是独立文件，asset 是富文本内嵌图，去重/GC 语义不同）。

### 29.2 Q215 大图不自动压缩

**决策**：单图 ≤ 10MB **原样存**（不自动压缩、不转码，emf/wmf 除外见 29.3）；> 10MB → `IMAGE_TOO_LARGE`。原「> 1MB 自动压到 1280px/JPEG80」逻辑**删除**。

**Why**：图片外置 assets 后无 base64 膨胀，压缩失去存储动因；SOP 流程图/截图清晰度重要，PNG→JPEG 有损、透明底丢失。保真优先。（若未来 PDF 体积成问题，再考虑"存原图 / 渲染时降采样"的存渲分离，本轮不做。）

### 29.3 Q216 emf/wmf→png 转换工具链

**决策**：用 **LibreOffice headless**（`soffice --headless --convert-to png`）转 emf/wmf 为 png 后入 asset；转换失败 → 该图降为 `placeholder` + review，不阻断整体解析。

**Why**：LibreOffice 对 Office 矢量格式原生支持最鲁棒，且常已是后端依赖。ImageMagick 的 emf delegate 不稳、Inkscape 重且慢。失败降级保证不卡流程。

### 29.4 Q217 阿拉伯顿号编号归类（26 份 QMS 打磨后修订）

**决策（修订）**：`1、2、3、`（阿拉伯数字 + 顿号）**不再硬判 list，改 weak_heading（上下文/粗体判定）**：短 + 粗体 + 后跟正文 → 标题；长 / 非粗体 → content（误报抑制）。同理 `N+中文直接`（`6相关文件`）→ weak_heading。`N)`/`N）`/`(N)`/`(一)` 仍为 list。纠偏面板「本文档将 N、视为标题」开关保留为边缘兜底。

**Why（修订原因）**：原决策（默认 list）在 26 份 ISO 9001 QMS 程序上**整批失效**——这些文档用 `1、目的` `2、范围` `3、权责`（阿拉伯顿号 + 粗体）作 L1 章节，被硬判 list 后 L1 全丢、body_start 错跳到 `3.1`。而「危险源监控措施」的 `1、设有消防…` 是正文条款。**同一 `N、` 记号两种语义，唯一可靠判别是粗体**：QMS 章节粗体、危险源条款非粗体。改 weak_heading（需粗体）后：QMS `1、目的`→标题、危险源 `1、设有…`→content，跨 31 份文档（5 fixture + 26 QMS）precision 恒 1.0、零新增误报。验证见 [word-parser-solution.md C.11](word-parser-solution.md) + scripts/survey_extra.py。

### 29.5 本节落地/影响

| 项 | 落地 |
|----|------|
| Q214 | [api-specification.md](api-specification.md) 加 `POST /procedures/{id}/assets`；[editor-behavior.md §5](editor-behavior.md) 端点确定（去"待定"标注）|
| Q215 | §12.4 删除自动压缩；[data-model.md](data-model.md) `MAX_IMAGE_SIZE=10MB` 已同步 |
| Q216 | [data-model.md §3.10](data-model.md) asset 表加 emf/wmf 经 LibreOffice 转 png 注 |
| Q217 | §27.4 / §25.5 编号分级字典：`N、`/`N+中文` 改 weak_heading（上下文/粗体），保留文档级「N、视为标题」开关；26 份 QMS 验证（C.11）|

---

## 三十、模板管理与步骤编辑器 UI（Q218–Q221）

> 编号说明：Q214–Q217 已被 §29 占用，本批顺延至 Q218。
> 本节**修订** §28 的 Q209/Q210（模板机制），并补 step_alerts/attachment_marks（§26）的编辑器 UI 与 step 面板布局。
>
> **⛔ 后续修订**：①Q218 procedure 模板已被 **Q290（§44）整体推翻**（改「模板库 + copy」，见 §30.1 banner）；②Q219 / Q221 的「警示」子区由 `step_alerts` 数组行编辑器改为 **`note`/`caution`/`warning` 三个固定富文本字段**（**Q263 / §40.3** 修订；现行以 [editor-behavior.md §4.1](editor-behavior.md) 为准）；§30.4 表「其他」组的 `notes` 也已并入 `note`。下文 step_alerts / notes 字段形态仅作历史保留。

### 30.1 Q218 procedure 模板全功能管理（修订 Q209/Q210）

> **⛔ 本决策被 §44（Q290）整体推翻**：`tb_procedure_template` 表删除，procedure template 功能废弃，改用「模板库系统文件夹 + copy」（模板=样板程序，全功能管理=用编辑器编样板程序，远比维护 body JSON 直观）。详见 [§44](#四十四模板库替代-procedure-templateq290q293)。下文仅作历史保留。

**决策**：模板从「后端硬编码三套」升级为**全功能在线管理**。新增 `tb_procedure_template` 表（[data-model.md §3.12](data-model.md#312-tb_procedure_template--程序模板新表q218)），可增删改建任意套模板；`general` / `testing` / `maintenance` 三套作为**系统预设种子**入表（`is_preset=true`）。

- 创建程序 API（`POST /procedures`）的 `template_key` 改为 `template_id`（引用 `tb_procedure_template.id`）；缺省 = 空白程序。
- 管理界面（设置页）CRUD 模板：名称 / 说明 / 章节树 + step 定义（`body` JSON）。
- `body` JSON 定义嵌套章节树（chapter / content / step + 各自配置，含 step_alerts / input_schema 等）。

**Why**：用户选「全功能模板管理」。组织需要沉淀自己的 SOP 模板（如本厂特定检验流程骨架），硬编码三套不够。独立表比 `tb_procedure_settings` 单例更适合可增删的多模板。

**How to apply / 约束**：
- 新表 `tb_procedure_template`，`body` JSON 存模板树。
- **模板与程序解耦**：模板仅在创建程序时一次性展开为 chapter/step 记录，程序**不引用**模板；故删除/修改模板**不影响**已据此创建的程序。
- 系统预设（`is_preset=true`）可改、可禁用（`is_active=false` 则不在创建选择列表出现）；**默认不允许物理删除预设**（保底，避免清空内置模板）。
- 这是对 §28.1（Q209 后端硬编码）+ §28.2（Q210 三套内容）的**修订**：三套从硬编码常量改为预设种子数据；§28.2 的三套内容定义仍是种子的初始 `body`。

### 30.2 Q219 step_alerts 编辑 UI（独立「警示」子区）

**决策**：step 编辑面板内独立「警示」子区，三按钮「+ 注意 Note / + 小心 Caution / + 警告 Warning」，每条一行：类型色标（蓝 / 黄 / 红）+ 文本输入，可拖拽排序、删除。详见 [editor-behavior.md](editor-behavior.md) §4.1。

- 渲染顺序自动按 Note→Caution→Warning（PPA §4.15）+ 同级 `sort_order`。
- 色标与 PDF 三色（[pdf-rendering.md §7](pdf-rendering.md)）一致。

### 30.3 Q220 attachment_marks 编辑 UI（独立「附件标记」子区）

**决策**：step 编辑面板内独立「附件标记」子区，与「警示」子区**复用同款数组行编辑器**。每条：文件名输入 + `kind` 下拉（视频 / 图片 / 文档 / 音频 / 其他）+ 备注，可增删。详见 [editor-behavior.md](editor-behavior.md) §4.1。

- 纯标记，**不校验文件是否已上传**（与 Q203 一致：如 mp4 太大不上传，仅标注）。

### 30.4 Q221 step 编辑面板布局（分组折叠，按渲染顺序）

**决策**：step 编辑面板重组为**分组折叠面板**，分组顺序对齐 PDF step 渲染顺序（[pdf-rendering.md §6.3](pdf-rendering.md)）：

| 序 | 折叠分组 | 字段 |
|----|---------|------|
| 1 | 基本信息 | 标题 / 类型 / 跳号 |
| 2 | 警示（Q219）| step_alerts |
| 3 | 正文 | content（WangEditor 简化工具栏）|
| 4 | 附件标记（Q220）| attachment_marks |
| 5 | 执行记录 | input_schema 配置 + require_confirmation |
| 6 | 其他 | expected_output / notes |

各组可折叠；顺序与 PDF 渲染一致，降低「所填 ≠ 所见」的认知负担。详见 [editor-behavior.md](editor-behavior.md) §4.1。

### 30.5 本节落地/影响

| 项 | 落地 |
|----|------|
| Q218 | [data-model.md §3.12](data-model.md) 新增 `tb_procedure_template`；§28.1/§28.2 改为预设种子；`POST /procedures` 的 `template_key` → `template_id`（[api-specification.md](api-specification.md) 已同步）|
| Q219 | [editor-behavior.md](editor-behavior.md) §4.1 step 面板加「警示」子区 |
| Q220 | [editor-behavior.md](editor-behavior.md) §4.1 step 面板加「附件标记」子区 |
| Q221 | [editor-behavior.md](editor-behavior.md) §4.1 step 面板分组折叠重组 |

> **附带补漏**：[editor-behavior.md](editor-behavior.md) §4.2/§4.3 的「警告块」工具栏按钮拆为 note / caution / warning 三类（补 Q183 在编辑器的落地遗漏）。

---

## 三十一、版本管理流程审视（Q222–Q225）

> 来源：版本管理流程审视。核心机制（§13 状态机、§22 版本管理 UI、§14 附件版本传递、B1 多版本模型）已完整；本节补 4 个未覆盖的边缘 / 未决场景。

### 31.1 Q222 版本号上限策略

**决策**：`max_version_number` **已存在于** [`tb_procedure_settings`](data-model.md#38-tb_procedure_settings--全局设置单例)（默认 **100**），本节明确其达限流程语义：达上限时 `upgrade-version` 返 `PROCEDURE_VERSION_MAX`(400)，前端提示「已达版本上限，请『复制为新程序』另起版本族」（复用 Q179 copy）。

- 上限针对 group 内 `version` 最大值（非记录数）。
- copy 出的新 group `version=1`，不继承旧 group 版本计数。

**Why**：无限版本累积无实际意义；达上限引导 copy 复用已有机制，不引入清理复杂度。

### 31.2 Q223 ARCHIVED 版本累积清理

**决策**：**不自动清理**，ARCHIVED 版本全量保留（合规留痕优先）。如需清理由用户手工 `DELETE` 单版本（Q171 入口，仍不能删 `is_current`）。

- 符合 SOP 受控文档「版本可追溯」原则。
- 与附件磁盘清理（Q115，软删后后台物理删）**不同**：版本记录不设后台自动清理。

### 31.3 Q224 并发 upgrade/rollback 竞态防护

**决策**：在 DB 层加**部分唯一约束**——同 group 仅一条 `status='DRAFT' AND is_active=true`。并发的第二个 `upgrade-version` / `rollback` 请求触发约束冲突，返 `PROCEDURE_DRAFT_EXISTS`(409)。

- 根治 §22.9「0/1 DRAFT」应用层 check-then-act 的 TOCTOU 竞态。
- 与 B1「同 group 仅一条 `is_current`」同思路：DB 约束兜底应用层守卫。
- **实现**：MySQL 8 部分唯一靠生成列 `draft_guard = IF(status='DRAFT' AND is_active=true, procedure_group_id, NULL)` + `UNIQUE(draft_guard)`（NULL 不参与唯一）。详见 [data-model.md §3.3](data-model.md)。
- §22.9 应用层守卫**保留**作快速失败 + 友好提示；DB 约束作最终防线。

### 31.4 Q225 PDF 版本状态水印

**决策**：PDF 按 `procedure.status` 加状态标识，受控文档防误用过期版本：

| status | 标识 |
|--------|------|
| DRAFT | 全页斜纹水印「草稿 DRAFT」（浅灰，不挡正文）+ 封面状态文字 |
| ARCHIVED | 全页水印「已作废 SUPERSEDED」（浅红）+ 封面红章 |
| PUBLISHED | **无**水印（受控正式版）|

详见 [pdf-rendering.md §3.4](pdf-rendering.md)（全文档水印 + 封面状态标识）。

**Why**：DRAFT/ARCHIVED 打印件与 PUBLISHED 无视觉区分会导致现场误用过期/未发布版本，这是受控文档（呼应 PPA 合规 §23）的安全底线。

### 31.5 本节落地/影响

| 项 | 落地 |
|----|------|
| Q222 | `max_version_number` **已存在** [data-model.md §3.8](data-model.md)（默认 100）；本节明确达限语义：`upgrade-version` 返 `PROCEDURE_VERSION_MAX`，引导 copy（Q179）|
| Q223 | 无新增；明确 ARCHIVED **不自动清理**，手工 DELETE 单版本（Q171）。注：§3.8 `auto_archive_days` 是另一机制（控制 active→ARCHIVED 自动归档，当前 §13 状态机未接线），与本决策「ARCHIVED 不自动删除」不冲突 |
| Q224 | [data-model.md §3.3](data-model.md) tb_procedure 加 `draft_guard` 生成列 + 部分唯一约束；新错误码 `PROCEDURE_DRAFT_EXISTS`(409)；[api-specification.md](api-specification.md) upgrade/rollback 守卫补充 |
| Q225 | [pdf-rendering.md §3.4](pdf-rendering.md) 版本状态水印 |

---

## 三十二、附件流程审视（Q226–Q229）

> 来源：附件流程审视。附件 CRUD（[api-spec §5.5](api-specification.md)）、版本传递（§14 Q113-Q120）、上限（Q120）、审计已完整；本节补 4 个未覆盖的安全 / 约束 / 体验空白。

### 32.1 Q226 附件类型安全

**决策**：保持**任意类型上传**（SOP 常需附 .nc / .gcode 等工程文件），但**下载端点一律 `Content-Disposition: attachment`**（强制浏览器下载、不内联渲染），杜绝 .html / .svg 等内联 XSS 与脚本执行。预览另走受控预览端点（Q229，仅白名单安全类型 inline）。

- **不设**上传黑 / 白名单（保通用性）。
- 安全靠「下载强制 attachment + 预览端点白名单」双层。

**Why**：黑名单挡合法工程文件、白名单限制通用性；真正的风险是**浏览器内联渲染**恶意文件（.html 脚本、.svg XSS）。强制 attachment 让任意文件都只能下载、不在浏览器执行，是成本最低的根治。

### 32.2 Q227 附件下载访问控制

**决策**：维持**公开下载**（无鉴权）。依据：本项目无登录、所有接口匿名（[api-spec §1](api-specification.md)）；附件 id 为 UUID（不可枚举）；面向内网 / 受信环境部署。nginx 层可选限流防爬。

**Why**：与既定「所有接口匿名」前提一致；引入签名 URL / session 校验会与无用户体系冲突，收益有限。

### 32.3 Q228 附件增删改的可编辑性约束

**决策**：附件 **增 / 删 / 改 遵循程序只读判定**（与 `PUT /procedures` 一致）：

| 操作 | 约束 | 失败 |
|------|------|------|
| POST / PUT / DELETE 附件 | 仅 `is_current=true AND status=DRAFT` | PUBLISHED/ARCHIVED/历史版本 → `PROCEDURE_READONLY`(400)|
| 同上，deprecated group | — | `PROCEDURE_DEPRECATED`(400)|
| GET 下载 | **不受限** | 始终允许（Q118，deprecated 也可下载）|

- §13.4 deprecated 限制列表补充含附件写操作。

**Why**：附件是程序版本内容的一部分；已发布 / 归档版本应整体不可变（含附件），否则破坏「PUBLISHED 不可改」语义与版本可追溯性。下载是只读，不受限。

### 32.4 Q229 附件在线预览

**决策**：图片（png / jpg / gif / webp）+ PDF 在程序详情页**内联预览**（lightbox / iframe），走**专门预览端点** `GET /attachments/{id}/preview`（`Content-Disposition: inline`，**仅限白名单安全类型**）；其余类型仅显示下载图标。

- 预览端点（inline，白名单）与下载端点（attachment，任意类型，Q226）**分离**，互不冲突。
- 复用浏览器原生图片 / PDF 渲染，不引入第三方预览组件。
- 预览白名单：`image/png` `image/jpeg` `image/gif` `image/webp` `application/pdf`（这些类型浏览器内联渲染无脚本执行风险）。

### 32.5 本节落地/影响

| 项 | 落地 |
|----|------|
| Q226 | [api-spec §5.5](api-specification.md) download 端点强制 `Content-Disposition: attachment` |
| Q227 | 无新增；明确公开下载（与 api-spec §1 匿名一致）|
| Q228 | [api-spec §5.5](api-specification.md) 附件 POST/PUT/DELETE 加只读判定；§13.4 deprecated 限制补附件写 |
| Q229 | [api-spec §5.5](api-specification.md) 新增 `GET /attachments/{id}/preview`（inline + 白名单）|

---

## 三十三、文件夹与设置流程审视（Q230–Q233）

> 来源：文件夹管理 + 设置管理流程审视。文件夹 CRUD / 移动（Q22）/ 删除（B9）/ 编号（Q-C4），设置字段（§3.8）已有；本节补 prefix 编辑 / 空值、版本开关、设置保护 4 个空白。**程序复制（§18）无新空白**——fork 复制规则补充见 §33.5。

### 33.1 Q230 文件夹 prefix 编辑对已有程序 code

**决策**：编辑 `folder.prefix`（如 QC→QA）**不回填**已有程序 code，仅影响该文件夹**后续新建**程序的 code。

- code 是已发布 / 外部引用的稳定标识，不应随 prefix 变动。
- 与 Q22「移动 code 不变」一致。
- 同文件夹内可能并存旧 prefix 的 code（QC-0001）与新 prefix 的 code（QA-0002），属正常。

### 33.2 Q231 prefix 为空时 code 生成格式

> ⚠ **已被 Q248 修订/作废（§37.3）**：叶子 prefix 现为**必填非空 + 全局唯一**，**不再有「空 prefix=纯序号」格式**。以下为历史决策原文，仅留档。

**决策（已作废）**：~~`folder.prefix` 为空（`''`）时，code = **纯序号**（如 `0001`，无前缀、无连字符）。~~

- ~~code 格式：prefix 非空 → `{prefix}-{seq}`（如 `QC-0001`）；prefix 空 → `{seq}`（如 `0001`）。~~
- ~~允许无前缀文件夹建程序。~~

### 33.3 Q232 enable_version_control=false 行为

**决策**：保留 `enable_version_control` 字段，但**本期恒为 true、UI 不暴露开关**。

- 多版本模型（B1）是核心架构，关闭会破坏 group / is_current / upgrade / rollback 等大量逻辑。
- settings 页不显示该开关；代码不读取它做分支（恒按多版本走）；字段在 DB 保留（默认 true）待未来。

### 33.4 Q233 设置修改的保护与审计

**决策**：任何人可改（与无登录一致）+ **设置变更记 `tb_procedure_audit_log`**（`action='settings_update'`，old / new value + IP / UA）+ 前端保存前**二次确认**。

- settings 单例 PUT 时写审计。
- 前端「保存设置」二次确认对话框。

### 33.5 程序复制 fork 新字段补充（§18.2）

`copy`（Q138 复制范围）随 fork 复制**所传 `{id}` 版本**（Q238 修订 Q138，不取 is_current）的全部字段，**含后续新增字段**：
- `level_of_use`（procedure 字段，Q182）/ `risk_level` / `quality_level`（Q52，Q339/§55 补）→ 继承 source。
- `note` / `caution` / `warning`（step 警示字段，Q263 取代 `step_alerts`）/ `attachment_marks`（Q203）→ 随 steps 复制。
- 新 group `version=1`、`status=DRAFT`、新 code（按 target_folder.prefix 走 sequence_generator，Q139；目标叶子 prefix 必填非空，Q248 修订 Q231）。

### 33.6 本节落地/影响

| 项 | 落地 |
|----|------|
| Q230 | [data-model.md §3.1](data-model.md) folder prefix 说明；[api-spec](api-specification.md) PUT /folders 注明 prefix 编辑不回填 |
| Q231 | ~~prefix 空 = 纯序号~~ **已被 Q248 修订/作废**（§37.3，叶子 prefix 必填非空唯一）|
| Q232 | [data-model.md §3.8](data-model.md) `enable_version_control` 注明本期恒 true 不暴露 |
| Q233 | [api-spec](api-specification.md) settings PUT 写审计；前端二次确认 |
| §18.2 | 复制范围补 level_of_use / note·caution·warning（Q263 取代 step_alerts）/ attachment_marks |

---

## 三十四、PDF 预览前端渲染层落地（Q234–Q237）

> 来源：PDF 预览遗留问题审视。§26（Q204/Q213）已把预览**修订为前端可交互渲染层**（取代后端静态 PDF），但该修订**未传导**到 api-specification.md §5.2（仍是 `POST /pdf-preview → base64 + toc_data` 旧模型）与 editor-behavior.md §10（仍是「调 /pdf-preview 拿 base64 → iframe」旧流程）。本节落实修订的剩余设计点并消除跨文档不一致。
> 编号：续 §33（Q230–Q233），本批 Q234–Q237。

### 34.1 Q234 预览数据来源 + 删除旧 base64 端点

**决策**：前端预览渲染层**直接复用 `GET /procedures/{id}`** 的结构化详情数据自行渲染版式；**删除**后端 `POST /procedures/{id}/pdf-preview`（base64 + toc_data）端点。

- 预览不再走「后端生成 PDF → base64 → iframe」；改由前端按结构化数据复刻本规范版式（封面/TOC/正文/警示/签名）。
- `POST /pdf-preview` 端点废弃移除；`GET /procedures/{id}/pdf-download`（ReportLab 静态正式交付物）**保留不变**。
- 与 Q204 一致：预览=可交互前端渲染层，下载=后端 ReportLab 空框。

**Why**：base64 PDF 预览无法支持 Q204 的可勾选 signoff / Q213 的 `window.print()` 所见即所得；前端用已有详情数据自渲染即可，无需为预览单开后端 PDF 渲染往返。最简、零新增「预览专用」数据接口（页码除外，见 Q235）。

### 34.2 Q235 页码 / TOC 由后端分页计算接口提供

**决策**：页码、TOC 页码、Attachment 页码（Q184 / Q59 的 PPA 规则在后端 ReportLab）由**后端新增分页计算接口**提供；前端预览层按返回的分页数据渲染**逐页分页视图**。

- 新增端点（建议 `GET /procedures/{id}/pdf-layout`，inline JSON）：返回总页数 + **每个版式元素 / 章节 / step → 所在页号**的分页归属 + TOC 条目页码 + 附件表格页码。
- 分页计算复用与 ReportLab **同一套**分页规则，保证前端预览**逐页与下载版 PDF 对齐**（页号一致、TOC 跳转准确）。
- 前端不自行估算精确页码（避免与下载版不一致）；正文内容来自 `GET /procedures/{id}`（Q234），分页骨架来自本接口。

**Why**：用户选「后端分页接口」而非「前端连续滚动」或「CSS 分页」——因为受控 SOP 的页码具规范含义（PPA §4.6 / Q184「Page X of N」覆盖全文档），预览页码必须与下载版严格一致，唯一可靠来源是后端同一分页逻辑。前端 CSS 分页无法保证与 ReportLab 逐页对齐。

**How to apply**：
- 后端把 ReportLab 的分页结果（或等价的分页测量）暴露为结构化 JSON，不渲染像素、不返回 PDF。
- 前端按页号把内容切到对应「纸张」容器渲染，配合 Q237 的完整版式复刻。

### 34.3 Q236 「导出已勾选 PDF」仅预留接口形态（本轮不实现）

**决策**：Q213 的「导出已勾选 PDF」可选增强**本轮不实现**，仅在 api-specification.md 中**预留端点形态**。

- 预留形态：`POST /procedures/{id}/pdf-download`（或独立 `…/pdf-export`）请求体可选 `checked_ids: string[]`（前端当前勾选的 signoff / 确认 / 签名区 id 列表），后端对命中项渲染 ☑、其余空框。
- 本轮带勾选输出由 `window.print()` 打印前端预览层满足（Q213 主路径，所见即所得）。
- 标注「预留、未实现」，待用户确有「带勾选的正式 PDF 文件」需求再实现。

**Why**：用户明确勾选目的=展示+打印（Q213），打印路径已覆盖该目的；导出带勾选 PDF 文件是低频增强，先预留接口形态避免未来破坏式改动，本轮不投入实现成本（符合不过度设计）。

### 34.4 Q237 前端预览层一次性完整复刻全版式

**决策**：前端预览渲染层**一次性完整复刻**本规范全版式——封面 / TOC / 修订记录 / 正文 / 警示三类（ANSI Z535 三色）/ 步骤 / hold-point 签名区 / 程序级附件表格 / 版本状态水印（Q225）——**不分阶段**。**修订** Q204 第 2091 行「是否分阶段需另议」。

- 一期即交付完整版式 + 可勾选 signoff（Q204）+ 打印 CSS（`@media print`，Q213）+ 状态水印 CSS 叠加层（Q225）。
- 不做「先只读 / 先正文」的中间态。

**Why**：用户选「一次性完整复刻」而非分两期或先只读——预览层若版式不全（缺封面/TOC/警示样式）则与下载版差异大、误导编写者；一步到位保证预览=打印=下载三者版式一致，避免分期产生的临时不一致与返工。

### 34.5 本节修订/补充的既有决策

| 既有决策 | 状态 |
|---|---|
| Q204（预览=前端渲染层）| **落实** → 数据源定为 `GET /procedures/{id}`（Q234）；分阶段问题定为「一次性完整复刻」（Q237，修订第 2091 行待澄清）|
| Q213（打印 / 导出已勾选）| **补充** → 导出已勾选 PDF 本轮仅预留接口形态（Q236）|
| api-specification.md §5.2 `POST /pdf-preview`（base64）| **删除** → 预览改前端自渲染（Q234）|
| editor-behavior.md §10 PDF 预览（base64 + iframe）| **重写** → 前端渲染层 + 可勾选 + window.print()（Q234/Q237）|

### 34.6 本节落地/影响

| 项 | 落地 |
|----|------|
| Q234 | [api-specification.md §5.2](api-specification.md) 删 `POST /pdf-preview`；[editor-behavior.md §10](editor-behavior.md) 改前端渲染层 |
| Q235 | [api-specification.md §5.2](api-specification.md) 新增 `GET /procedures/{id}/pdf-layout` 分页接口；[pdf-rendering.md §6.7](pdf-rendering.md) 注明页码来源 |
| Q236 | [api-specification.md §5.2](api-specification.md) `pdf-download` 预留可选 `checked_ids`（标「未实现」）|
| Q237 | [pdf-rendering.md §6.7](pdf-rendering.md) 删「可分阶段实现」，改「一次性完整复刻」 |

---

## 三十五、程序复制遗留落地（Q238–Q241）

> 来源：程序复制设计审视。§18（Q137–Q140）+ §22.15/§22.16 复制 UI + §33.5 fork 字段补充已较完整、跨文档基本一致；本节消除一处真矛盾（复制源版本语义）+ 补 3 个空白（重置字段、副本名去重、源侧追溯）。
> 编号：续 §34（Q234–Q237），本批 Q238–Q241。

### 35.1 Q238 复制源版本语义（修订 Q138）

**决策**：`POST /procedures/{id}/copy` 复制**所传 `{id}` 对应的那个版本**的内容（所见即复制），**不再**恒取 group 的 `is_current`。**修订 Q138**（原「仅复制 `source.is_current=true` 那个版本」）。

- 从历史只读视图（§22.10）查看 v2（group 的 is_current 是 v5）并点「复制为新程序」→ 复制 **v2**，不是 v5。
- 后端按 `{id}` 直接深拷贝该版本的 chapters/steps/attachments/custom_values，不解析到 is_current。
- `version_change_log` 首条 / `copy_from` 审计的 `source_version` 取所传版本号（与 §18.4 一致，原本就用 source_version，无需改）。

**Why**：§22.10 行 1474 已建 UI 明确「复制源始终是当前查看的版本」、§22.15 弹窗标题显示 `v{source.version}`，与原 Q138「仅 is_current」直接冲突。用户选「所见即复制」——查哪个版本就复制哪个，符合直觉且与既有 UI 一致；恒 is_current 会造成「查 v2 却复制出 v5」的困惑。Smart SOP 复制本就与版本族无关（独立新 group），复制任意历史版本内容是合理诉求。

### 35.2 Q239 copy 重置状态字段

**决策**：copy 出的新 DRAFT，以下状态字段**重置为默认**，不从源继承：

| 字段 | 重置为 | 理由 |
|------|--------|------|
| `chapter.mark_status` | `unmarked` | 标记模式属解析期临时态，新 DRAFT 从干净态起 |
| ~~`step.mark_status`~~ | — | **字段已移除**（Q264 / §40.4），无需重置 |
| `procedure.is_read` / `read_at` | `false` / `null` | 新程序未读 |
| `revision` | `0` | （§18.3 已定）|

**Why**：copy 是全新独立 DRAFT，标记/执行/已读都是源程序的运行期状态，不属于「内容」，不应带过来。补全 §18.2 原「不复制」清单未覆盖的字段。

### 35.3 Q240 副本默认名允许同名（不去重）

**决策**：副本默认名 = `源名 + " (副本)"`（§18.3 / Q139 不变）；同一程序复制多次产生多个同名「X (副本)」**允许并存，不去重、不自动加序号**。

- `code`（走 sequence_generator）才是唯一标识；`name` 非唯一键，无需校验。
- 用户可在复制弹窗自行改名。

**Why**：名称去重/自动序号是额外校验复杂度，而 SOP 用 code 唯一标识、name 仅展示，允许同名最简且不引入冲突处理。符合不过度设计。

### 35.4 Q241 源侧追溯保持现状

**决策**：复制追溯**保持 Q140 现状**——仅在**新程序**记 `audit_log` `action='copy_from'`（含 `source_procedure_id/source_code/source_version`）；**不**给源程序记审计、**不**加 `copied_from` 外键。

- 源程序无需知道「被复制去哪」；如需排查可在 audit_log 按 `copy_from.new_value` 反查。

**Why**：源侧留痕/外键属低频追溯需求，Q140 已定「复制与版本族无关、不加外键」，维持现状最简、不推翻既有决策。

### 35.5 文档清理（无新决策）

- §18.2 行原「整树深拷贝，重生 id 与 `stable_node_id` 无需」→ 改为「整树深拷贝，重生节点 id」。`stable_node_id` 是**已砍的版本 diff 算法**概念（仅见 §13 行说明为何不做 diff），从未进数据模型，此处为残留措辞。

### 35.6 本节修订/补充的既有决策

| 既有决策 | 状态 |
|---|---|
| Q138（仅复制 is_current）| **修订** → 复制所传 `{id}` 版本（Q238）|
| Q139（副本默认名）| **补充** → 同名允许并存、不去重（Q240）|
| Q140（copy_from 追溯）| **维持** → 源侧不留痕、不加外键（Q241）|
| §18.2 复制/不复制清单 | **补充** → 新增重置字段清单（Q239）+ 清理 stable_node_id 残留（§35.5）|

### 35.7 本节落地/影响

| 项 | 落地 |
|----|------|
| Q238 | [§18.2](#182-复制范围q138) 改「复制所传版本」；[api-specification.md §5.2](api-specification.md) copy 详情 + [§14 附件传递](api-specification.md) copy 行改「所传版本」；[data-model.md](data-model.md) 附件/asset 复制说明改「所传版本」；[§22.15](#2215-复制为新程序-ui-入口q179) 措辞对齐 |
| Q239 | [§18.2](#182-复制范围q138) 不复制清单补 mark_status/is_read/read_at 重置 |
| Q240 | [§18.3](#183-目标文件夹与名称q139) 注明同名允许 |
| Q241 | 维持 §18.4 / Q140，无改动 |
| 清理 | [§18.2](#182-复制范围q138) 删 stable_node_id 残留 |

---

## 三十六、审批模式开关（Q242–Q245）

> 来源：程序配置审视——新增「审批模式开关」需求。**注意：本节是对决策 B3（状态机三态化、移除审批工作流）的受控反转**，但采「最小预留」策略：仅恢复一个全局开关 + 一个内部预留闸门 hook，**不恢复 PENDING/REJECTED 状态、不恢复 approval_status 字段、不恢复审批 API**，故**不触碰不可变设计 #2（DRAFT→PUBLISHED→ARCHIVED 单向三态）**。审批模块本身本期不开发。
> 编号：续 §35（Q238–Q241），本批 Q242–Q245。

### 36.1 Q242 审批开关粒度=全局 settings 单例

**决策**：审批模式开关为**全局单例设置**，在 `tb_procedure_settings` **恢复** `enable_approval_workflow`（BOOLEAN，默认 `false`）。全系统统一一个开关，不做文件夹级 / 程序级粒度。

- 与「程序配置 / 设置」定位一致；最简。
- **更新 data-model §3.8「已移除」清单**：`enable_approval_workflow` 从已移除恢复（仅此字段；`default_approval_template` / `notification_*` / `create_mode` 仍移除）。

### 36.2 Q243 开关 ON 行为=三态不变 + 预留审批闸门

**决策**：开关打开时，**状态机保持 DRAFT→PUBLISHED→ARCHIVED 不变**；`publish`（`transition` 到 PUBLISHED）前调用一个**预留审批闸门** `ApprovalGate.check(procedure)`，**本期 stub 直接放行**（返回通过）。

- **不反转 B3 的状态机部分、不动不可变设计 #2**：不新增 PENDING_APPROVAL 等状态。
- 开关 OFF（默认）时行为完全等同现状（直接发布）。
- 未来接入审批模块时，仅替换 `ApprovalGate` 实现（届时是否引入待审状态需新一轮 grill）。

**Why**：用户要「打开开关程序走审批通道、但本期不开发审批模块、接口预留」。在不开发模块前提下，最小且不破坏既有架构的方式是预留一个发布前闸门 hook，本期放行。加占位状态会反转不可变状态机，代价过高且当前无收益。

### 36.3 Q244 预留形态=仅内部 service hook

**决策**：审批闸门**仅预留为内部 service hook**（`ApprovalGate.check()` 抽象点，本期返回放行）。**不加** DB 字段（不恢复 `approval_status`）、**不加** HTTP 端点（不恢复 `submit-approval`）。

- 现阶段仍是设计文档，未来接模块时再加字段与 API，数据模型保持干净。
- 与「暂不开发审批模块」一致——避免占位字段 / 端点。

### 36.4 Q245 开关 ON 的可见效果=发布区徽标

**决策**：开关 ON 时（闸门放行、不阻断发布），在程序详情 / 发布按钮旁显示徽标「审批模式已开启（模块待上线）」，**不阻断发布**。

- 让开关不是纯隐形 no-op，又不破坏发布流程。
- 改 `enable_approval_workflow`（settings 字段）**继承 Q233**：写 `tb_procedure_audit_log`（`action='settings_update'`）+ 前端二次确认。

### 36.5 本节修订/反转的既有决策

| 既有决策 | 状态 |
|---|---|
| B3（移除审批工作流）| **受控反转（部分）** → 仅恢复全局开关 + 预留闸门 hook（Q242/Q243/Q244）；状态机部分不反转 |
| data-model §3.8「已移除」`enable_approval_workflow` | **恢复**该字段（默认 false，Q242）|
| 不可变设计 #2（单向三态）| **不变**（Q243 明确不引入待审状态）|

### 36.6 本节落地/影响

| 项 | 落地 |
|----|------|
| Q242 | [data-model.md §3.8](data-model.md) 恢复 `enable_approval_workflow`；更新「已移除」清单 |
| Q243 | publish/transition 流程加 `ApprovalGate.check()` 预留点（[development-plan.md](development-plan.md) 注明）；状态机不变 |
| Q244 | 无新字段 / 端点；仅 service 层 hook |
| Q245 | [editor-behavior.md](editor-behavior.md) 发布区徽标；[api-specification.md](api-specification.md) settings PUT 加 `enable_approval_workflow`（审计同 Q233）|

---

## 三十七、文件夹 + 文件夹配置（Q246–Q252）

> 来源：文件夹设置审视——程序文件夹自定义增删改查（多级）+「文件夹配置」呈现 + 编码前缀 / 路径 + 新建程序选文件夹。补 §33（Q230–Q233）未覆盖的模型决策，并修订 Q231。
> 编号：续 §36（Q242–Q245），本批 Q246–Q252。

### 37.1 Q246 「文件夹配置」=用户文件夹树前端统称

**决策**：「文件夹配置」是**所有非系统文件夹**（`tb_folder.system=false`）组成的用户文件夹树的**前端统称**，可建多级、可（在叶子）存程序。**不引入新表 / 新结构**——就是现有 `tb_folder` 树的前端呈现名称，与「废止」等 `system=true` 文件夹区分。

- 前端「文件夹配置」导航区列出 `system=false` 的文件夹树。

### 37.2 Q247 仅叶子文件夹存程序 + 容器/叶子互斥

**决策**：程序**仅能存放在叶子文件夹**（无子文件夹的文件夹）。中间层是纯分类容器，不存程序、不需要 `prefix` / 序列。**含程序的文件夹禁止再加子文件夹**（须先把程序移走 / 清空）——保证「容器 xor 叶子」不变式。

- 含程序的文件夹收到「新建子文件夹」请求 → 拒绝（建议错误码 `FOLDER_HAS_PROCEDURES`）。
- 中间容器文件夹：`prefix` 恒空、无 `tb_folder_sequence` 记录。
- 移动 / 删除沿用既有：删除硬约束 B9（含子或程序即拒）、移动 code 不变（Q22）、最大深度 5、system 文件夹禁删改。

### 37.3 Q248 叶子 prefix 必填非空 + 全局唯一（修订 Q231）

**决策**：可存程序的**叶子文件夹** `prefix` **必填非空 + 全局唯一**。**修订 Q231**（原「prefix 可空、空时 code=纯序号」作废）。

- code 生成：`{prefix}-{seq}`（如 `QC-00001`）；不再有「纯序号无前缀」格式。
- 编辑 prefix 仍不回填已有 code（Q230 不变）。

**Why**：用户设想「选文件夹→自动生成 前缀+00001」，前缀始终存在；且 prefix 全局唯一可从根本上杜绝跨文件夹 code 撞车（两文件夹同 prefix 各自序列从 1 → 都生成同一 code，违反 `UNIQUE(code, version)`）。空 prefix 会让多个空前缀文件夹都生成 `00001` 撞车，故取消。

### 37.4 Q249 prefix 永久占用、不可复用（防撞车 A）

**决策**：某 prefix **一经生成过 code 即永久占用**，改名 / 释放后**不可被其它文件夹复用**。把既有 prefix 唯一性校验（`/folders/check-prefix` + `FOLDER_PREFIX_DUPLICATE`）**扩展**为「该 prefix 既不属任何其它文件夹、也从未被任何现存 `tb_procedure.code` 使用过」，命中则拒绝。

- **复用既有 `FOLDER_PREFIX_DUPLICATE`**（消息扩为「前缀已被占用，含历史程序使用过的前缀」），不新造错误码。
- 无需新表：直接查现存 code 的前缀部分即可。

**Why**：Q230 规定改 prefix 不回填旧 code。若改 `QC→QA` 后 `QC` 释放、另建文件夹又用 `QC`（序列从 1 起）→ 重新生成 `QC-00001`，撞已存在旧程序。永久占用杜绝此撞车。

### 37.5 Q250 编号位数可配、默认 5

**决策**：每叶子的 `tb_folder_sequence.sequence_digits` **可配**，**默认值 4 → 5**（生成 `00001`）。

- 贴合用户「前缀+00001」写法；保留 per-folder 可配灵活性。

### 37.6 Q251 序列重置 reset_period 固定 never、不暴露（防撞车 B）

**决策**：序列**只增不重置**——`reset_period` **固定 `never`、不在 UI 暴露、去掉重置配置**（字段可保留 DB 默认 never，或一并移除 `reset_period` / `last_reset_at`，由实现定）。

**Why**：现 code=`{prefix}-{seq}` 不含年 / 月，按年 / 月重置回 1 必然重号撞车。要支持周期重置须把周期嵌入 code（如 `QC-2025-00001`），属更大改动，本期不做。

### 37.7 Q252 新建程序选文件夹 UI=搜索下拉 + 路径 + code 预览

**决策**：新建程序时选文件夹的交互 = **搜索下拉**：输入关键词，下拉列出匹配的**叶子文件夹**及其完整路径（如 `质检 / 检验流程 / 来料检验`），单选；**中间容器不可选**；选定后**预览将生成的 code**（`{prefix}-{下一序号}`）。

- 仅叶子可选（呼应 Q247）。

### 37.8 本节修订/补充的既有决策

| 既有决策 | 状态 |
|---|---|
| Q231（空 prefix=纯序号）| **修订 / 作废** → 叶子 prefix 必填非空唯一（Q248）|
| Q230（改 prefix 不回填）| **维持 + 补充** → 旧 prefix 永久占用不可复用（Q249）|
| `tb_folder_sequence.sequence_digits` 默认 4 | **修订** → 默认 5（Q250）|
| `tb_folder_sequence.reset_period` | **收紧** → 固定 never、不暴露（Q251）|
| B9 删除 / Q22 移动 / 最大深度 5 / system 文件夹 | **维持不变** |

### 37.9 本节落地/影响

| 项 | 落地 |
|----|------|
| Q246 | [editor-behavior.md](editor-behavior.md) 前端「文件夹配置」导航；data-model §3.1 注明统称 |
| Q247 | [data-model.md §3.1](data-model.md) 容器 / 叶子互斥、中间容器无 prefix / 序列；新错误码 `FOLDER_HAS_PROCEDURES`；[api-specification.md](api-specification.md) 建子文件夹校验 |
| Q248 | [data-model.md §3.1/§3.3](data-model.md) prefix 必填非空唯一、code 生成去纯序号 |
| Q249 | [data-model.md §3.1](data-model.md) prefix 永久占用；**扩展** `check-prefix` 校验 + 复用 `FOLDER_PREFIX_DUPLICATE` |
| Q250 | [data-model.md §3.2](data-model.md) sequence_digits 默认 5 |
| Q251 | [data-model.md §3.2](data-model.md) reset_period 固定 never 不暴露 |
| Q252 | [editor-behavior.md](editor-behavior.md) 新建程序选文件夹搜索下拉 + code 预览；[api-specification.md](api-specification.md) POST /procedures 仅接受叶子 folder_id |

---

## 三十八、自定义字段配置（Q253–Q258）

> 来源：程序配置审视——自定义字段（`tb_procedure_field`）的配置 UI 与生命周期。数据模型（§3.7）已有 name/key/类型/required/options/validation_rules 等。
> 编号：续 §37（Q246–Q252），本批 Q253–Q258。

### 38.1 Q253 校验规则=表单化常用项→JSON Schema

**决策**：`validation_rules`（存储恒为标准 JSON Schema，Q-C6）的**配置 UI = 表单化常用项**（必填 / 最小值 / 最大值 / 最小长度 / 最大长度 / 正则等），保存时后端转成 JSON Schema。普通用户无需懂 Schema。

### 38.2 Q254 key=手填英文、建后不可改

**决策**：字段 `key`（UNIQUE，作 `custom_values` 的键）= **用户手填英文**（小写字母 / 数字 / 下划线）+ 前端校验唯一与格式；**创建后不可修改**（改 key 会孤立已填 `custom_values`）。`name` 为中文显示名。

### 38.3 Q255 archived 字段 / 选项=保留值、只读、新建不出现

**决策**：字段或其 `options` 选项被 `archived` 后，**已填值保留**并在程序里**只读展示**；归档字段 / 选项**不再出现**在新建 / 编辑的可选项里。与 Q24（`options[].archived`）一致。

### 38.4 Q256 required 不追溯

**决策**：把字段改为 `required` **不追溯**——仅对**新建程序** + **DRAFT 下次编辑保存**时强制；已 PUBLISHED / 未填的历史程序不报不合规。与「改 prefix 不回填」「改设置不追溯」一贯。

### 38.5 Q257 每字段「上封面」开关→PDF 封面

**决策**：`tb_procedure_field` **新增** `show_on_cover` BOOLEAN（默认 false）。勾选的字段按 `sort_order` 渲染到 **PDF 封面元数据区**（与 `level_of_use` / `risk_level` / `quality_level` 同区）。

**Why**：不同组织 SOP 需要上封面的元数据不同（如部门 / 生效日期），逐字段可控最灵活；不勾选的仅系统内展示。

### 38.6 Q258 管理 UI=设置页「自定义字段」子页

**决策**：自定义字段管理 = **设置页下「自定义字段」子页**：列表（name/key/类型/必填/状态）+ 增删改弹窗（含 `options` 增删改 / 归档）+ 拖拽排序（`sort_order`）+ 归档 / 启用切换。

### 38.7 本节落地/影响

| 项 | 落地 |
|----|------|
| Q253 | [editor-behavior.md](editor-behavior.md) 字段编辑弹窗表单化校验；后端转 JSON Schema |
| Q254 | [data-model.md §3.7](data-model.md) key 建后不可改说明 |
| Q255 | [editor-behavior.md](editor-behavior.md) 归档字段 / 选项只读展示规则 |
| Q256 | required 校验时机=新建 + DRAFT 保存；[api-specification.md](api-specification.md) 校验说明 |
| Q257 | [data-model.md §3.7](data-model.md) 加 `show_on_cover`；[pdf-rendering.md](pdf-rendering.md) 封面渲染自定义字段 |
| Q258 | [editor-behavior.md](editor-behavior.md) 设置页「自定义字段」子页 |

---

## 三十九、全局设置页（Q259–Q260）

> 来源：程序配置审视——全局设置页（`tb_procedure_settings` 单例）。多数字段语义已被既有决策定死，本节补 auto_archive 处理 + 默认等级控件 + 设置页字段集。
> 编号：续 §38（Q253–Q258），本批 Q259–Q260。

### 39.1 Q259 auto_archive_days 隐藏待 Phase 9

**决策**：`auto_archive_days`（active→ARCHIVED 自动归档，定时任务列在 development-plan Phase 9、本期未接线）**字段保留 DB，设置页不显示**；Phase 9 接线时再暴露。同 `enable_version_control`（Q232）「字段留、UI 不暴露」思路。

### 39.2 Q260 设置页字段集 + 默认等级控件

**决策**：

设置页**显示可改**字段集：
- `enable_approval_workflow`（审批开关，Q242，徽标见 Q245）
- `max_version_number`（版本上限，Q222 语义）
- `require_read_confirmation`（已读确认强制，B2）
- `default_risk_level` / `default_quality_level`（默认风险 / 质量等级）

**隐藏**：`enable_version_control`（Q232）、`auto_archive_days`（Q259）。

`default_risk_level` / `default_quality_level` 控件 = **1–5 文字分级下拉**（低(1)/中-低(2)/中(3)/中-高(4)/高(5) + 色块，沿用 Q52），存 INT，**默认沿用 1**。

保存：**二次确认 + 写审计**（Q233）。

### 39.3 本节落地/影响

| 项 | 落地 |
|----|------|
| Q259 | [data-model.md §3.8](data-model.md) auto_archive_days 注明隐藏待 Phase 9 |
| Q260 | [editor-behavior.md](editor-behavior.md) 设置页字段集 + 默认等级 1–5 下拉；[data-model.md §3.8](data-model.md) 字段可见性说明 |

---

## 四十、步骤执行表单类型与警示字段（Q261–Q265）

> 来源：用户要求步骤字段**复刻参考系统 DPMS V2.0**（`D:\project devleoment\Huawei\DPMS_V2.0`）。本节重构 step 模型——执行表单类型 3→12、警示三富文本字段、双通道定位、执行边界、仪表简化。**覆盖 A9，修订 Q201/Q202/Q219/Q220，限定 Q213**。
> grill 方式：grill-with-docs 逐分支深挖（一次一题）+ 探索 DPMS step 模型对照确认。step 完整字段见 [data-model.md §3.5](data-model.md#35-tb_procedure_step--程序步骤)。

### 40.1 Q261 执行表单类型复刻 DPMS 12 型（覆盖 A9）

**决策**：`step.input_schema.type` 从 3 型扩展为复刻 DPMS 的 **12 型**，大写枚举：`COMMON` / `CHECK` / `YESNO` / `NUMBER` / `METER` / `CHECKBOX` / `RADIO` / `UPLOAD` / `SIGNATURE` / `DATE` / `PHOTO` / `NONE`。

- **术语正名**：这不是"步骤类型"（step 就是 step），而是「**执行表单类型**」(execution form type)——描述这一步执行时**采集什么数据**。
- 命名用 **DPMS 大写枚举**：与移动端执行通道值一致、对接零成本；与 `status` 大写风格统一。
- `type` 为**开放枚举**：新类型只加渲染器/编辑器，不改表结构（JSON 存储的价值）。
- **现有 3 型迁移**：`text→COMMON`、`pass_fail→CHECK`、`measurement→NUMBER`（measurement 的 upper_limit/lower_limit→`min`/`max`，`decimal_places` 保留）。**不保留旧小写命名（A9 覆盖）**。
- 12 型 input_schema 结构见 [data-model.md §3.5](data-model.md)。

### 40.2 Q262 双通道渲染 + COMMON 复用 content（方案 X）

**决策**：12 型在**双通道**渲染（双通道见 40.4）：

- **PDF 通道**：语义化纸质占位符（见 [pdf-rendering.md §6.3](pdf-rendering.md)）——`CHECK→☐通过 ☐不通过`、`NUMBER→___ {unit}(范围 min~max)`、`SIGNATURE→签名:___`、`DATE→日期:___`、`PHOTO→照片粘贴框`、`UPLOAD→附件:___`、`CHECKBOX→☐多选`、`RADIO→○单选`、`YESNO→☐是 ☐否`、`NONE→无采集`、`METER→___ {unit}`、`COMMON→富文本 + ☐已完成`。
- **移动端执行通道**：真交互控件（待执行模块）。
- **COMMON 复用 step.content（方案 X）**：COMMON 型**不另存富文本**，操作说明就是 `step.content`，`input_schema` 仅 `{type:"COMMON"}`；执行 = 读说明 + 勾选完成。**COMMON vs NONE**：COMMON 有「☐已完成」勾选执行、NONE 纯展示无执行交互。

### 40.3 Q263 警示三富文本字段 note/caution/warning（方案 A，修订 Q201/Q202/Q219/Q220）

**决策**：step 新增 `note` / `caution` / `warning` **三个独立富文本字段**（LONGTEXT），承载 PPA §4.15 三类警示；PDF 渲染加对应边框 + 底色（ANSI Z535 三色，复用 [pdf-rendering.md §7](pdf-rendering.md)）。

- **修订 Q201**：废弃 `step_alerts` JSON 数组，改三个固定富文本字段（方案 A）。理由：固定 `note→caution→warning` 顺序天然满足 PPA §4.15 递进；富文本表达力强（加粗/列表/红字）；编辑就是填三个框，最简。
- **移除 `notes`**：原普通备注归入 `note`（消除 `notes`/`note` 撞名）。
- **C 保留（修订 Q202）**：content 节点正文内嵌 `note-block`/`caution-block`/`warning-block`（Q183 HTML class，**章节正文级辅通道**）保留并存；主通道由 step_alerts 改为三字段，两轨共用 PDF 三色样式。
- **修订 Q219/Q220**：[editor-behavior.md](editor-behavior.md) §4.1 step 编辑面板「警示子区」从「数组行编辑器」改为「三个富文本框」；attachment_marks 子区不变。

### 40.4 Q264 双通道定位 + 执行落库边界（移除 mark_status）

**决策**：明确 Smart SOP **双输出通道**：

| 通道 | 形态 | 执行字段角色 |
|---|---|---|
| **PDF 通道** | 纸质打印交付物 | input_schema → 占位符、纸质手填；勾选不回写 |
| **移动端执行通道** | 在线执行（DPMS 式，未来/对接）| input_schema → 真控件、真执行 |

- **本期边界**：**只编写"执行表单定义"**（input_schema 12 型 + note/caution/warning + expected_output + require_confirmation 等字段），**不做执行运行时**（移动端 APP 采集、执行记录表、执行人/工单概念）。
- **移除 `step.mark_status`**（执行态 pending/completed/skipped）：属执行运行时产物，本期不做；待执行模块以独立命名（`execution_status`）记在**执行记录表**而非 step 定义（同一 SOP 多次执行，状态不应覆盖在定义上）。顺带消除与 `chapter.mark_status` 撞名。
- **限定 Q213**：「勾选不持久化、无执行追踪」仅指 **PDF 预览通道**，**非**否定移动端执行。

### 40.5 Q265 仪表（METER）本期简化

**决策**：METER 型本期**仅渲染数字输入框 + 单位输入框**，`input_schema` 仅 `{type:"METER", unit:""}`。

- `name` / 上下限 / 超限动作（upperLimitAction/lowerLimitAction）/ 真实仪表设备关联（meter_id 外键）**全部待仪表模块**建立后联通。
- 与 `NUMBER` 分工：NUMBER = 手填数字带 min/max 合格范围（承接原 measurement）；METER = 未来绑真实检测设备/量具的读数（本期占位简化）。
- 待仪表模块建立后，METER input_schema 扩展为完整 DPMS 结构 + `meter_id` 关联。

### 40.6 本节修订/影响

| 决策 | 状态 |
|---|---|
| A9 步骤类型三类 | **覆盖** → 执行表单 12 型（40.1）|
| Q201 step_alerts JSON | **修订** → note/caution/warning 三富文本字段（40.3）|
| Q202 双轨 | **调整** → 主通道改三字段，C（content class）保留辅通道（40.3）|
| Q219/Q220 编辑面板警示子区 | **修订** → 三富文本框（40.3，editor-behavior §4.1）|
| Q203 attachment_marks | **不变**（维持，#5）|
| Q213 勾选不持久化 | **限定** → 仅 PDF 预览通道（40.4）|
| step.mark_status | **移除**（40.4）|
| measurement input_schema | **迁移** → NUMBER（40.1）|

**落地**：[data-model.md §3.5](data-model.md)（已改）、[pdf-rendering.md §6.3/§7](pdf-rendering.md)、[editor-behavior.md §4.1](editor-behavior.md)、[api-specification.md](api-specification.md) GET schema。

---

## 四十一、程序库列表页 UI（Q266–Q277）

> 来源：程序库列表页是核心日常入口，此前仅有 `GET /procedures` 过滤参数 + §22 版本操作 + A12 文件夹树统计，**列表页本身**（布局 / 视图模型 / 列 / 过滤 / 排序 / 分页 / 批量 / 空状态 / 新建入口）未成体系 grill。本节补齐。
> **编号注**：本节因与并行会话同时落地的「步骤执行表单」（§40 / Q261–Q265）撞号，让号为 §41 / Q266–Q277；§40 在前、本节在后（已重排为正序）。

### 41.1 Q266 页面布局=左树 + 右列表

左侧常驻「文件夹配置」文件夹树（`system=false`，复用 Q246 + A12 `procedure_count`）；点叶子文件夹 → 右侧列出该文件夹程序，顶部面包屑显示 `full_path`。

### 41.2 Q267 列表粒度=每 group 一行 + 状态过滤

每个程序 group 显示**一行**（其 `is_current` 版本，任意状态都算）+ `version_count_in_group` 徽标；status 过滤器收窄；点行进详情看版本历史（§22）。`GET /procedures/library`（PUBLISHED + is_current）**保留给只读门户 / 外部集成，不单独建前端 tab**。

### 41.3 Q268 过滤 + 排序维度（保持最简）

- 过滤：文件夹（左树）/ status / search（沿用现 API，**不新增过滤项**）。
- 排序：复用 [api-spec §3.2](api-specification.md) 通用 `sort`；本列表默认 `-updated_at`，可切 code / name。

### 41.4 Q269 已废弃程序入口=标准库外独立入口

「废止」（`system=true`）不在文件夹配置树内，作为**树外独立入口 / 特殊节点**；点它列出已废弃 group，沿用 §22.16 deprecated 行特殊 UI。与 Q246（文件夹配置=`system=false`）分离一致。

### 41.5 Q270 列表列

默认列：`code` / `name` / 版本（`v{version}` + count 徽标）/ status 徽标 / 用途级别 / 更新时间 / 操作 ⋮。folder 因左树已选不每行显示；**跨文件夹搜索结果时额外显示路径列**。

### 41.6 Q271 行点击=进只读详情

点行 → `/procedures/{id}/view` 只读详情（§22 体系）；DRAFT 行也**先进详情**，详情内若 `is_current + DRAFT`（Q14 只读判定）显「编辑」入口。行为统一可预测。

### 41.7 Q272 行 ⋮ 菜单=按状态动态

按当前行状态显隐 / 启用，全部复用既有决策、无新语义：

| 菜单项 | 可用条件 / 依据 |
|--------|----------------|
| 编辑 | `is_current + DRAFT`（Q14）|
| PDF 下载 | 任意 |
| 复制为新程序 | Q179 |
| 升级版本 | `is_current + PUBLISHED`（Q165）|
| 废弃整 group | Q100 |
| 删除 | 按 Q109 / Q175 规则 |
| 查看版本历史 | §22 |

### 41.8 Q273 批量操作=删除 + 移动

多选后：批量删除（已有 `POST /procedures/batch-delete`）+ **批量移动到文件夹**（新增，复用 Q22 移动语义 code 不变；目标限叶子文件夹 Q247）。

- 新增端点 `POST /procedures/batch-move`，body `{ids:[...], target_folder_id}`。

### 41.9 Q274 分页=传统分页 + 可调每页

复用 [api-spec §3.2](api-specification.md) `page` / `page_size`；前端页码分页 + 每页条数可选 20 / 50 / 100（默认 20）。受控文档库需定位 / 引用特定项，分页比无限滚动可控。

### 41.10 Q275 空状态=三态分别文案 + CTA

- 文件夹无程序 → 「该文件夹暂无程序」+「+ 新建程序」。
- 搜索无结果 → 「未找到匹配」+ 清除搜索。
- 全库为空 → 引导建文件夹 / 新建程序。

### 41.11 Q276 新建程序入口 + 弹窗

- **双入口**：列表页右上「+ 新建程序」按钮 + 左树叶子节点悬浮「+」。
- 弹窗字段：folder（Q252 搜索下拉，预填当前选中叶子）/ name / level_of_use（必填 Q182）/ description（选填）；risk / quality 取 settings 默认（Q260），建后程序详情面板可改。
- **新建恒空白程序**（模板库已废，[§56/Q340](#五十六砍模板库纯-copy-自现有程序q340)）；要"套结构"= 去任意现有程序 `⋮ → 复制为新程序`（§18/Q179）。
- 建后进编辑器（空白程序）。

### 41.12 Q277 列表「已读」显示=与设置联动

`require_read_confirmation=true` 时列表显示已读 / 未读指示 + 「待阅读」筛选；`false` 时不显示（不打扰）。**完整 mark-read 交互流程见 §46**，本节仅定列表呈现。

### 41.13 本节落地/影响

| 项 | 落地 |
|----|------|
| Q266–Q277 | 新增 [editor-behavior.md §20 程序库列表页](editor-behavior.md) |
| Q268 / Q274 | 复用 [api-spec §3.2](api-specification.md) `sort` / `page` / `page_size`；列表默认 `sort=-updated_at` |
| Q273 | [api-specification.md](api-specification.md) 新增 `POST /procedures/batch-move` |

---

## 四十二、程序库全文搜索（Q278–Q283）

> 来源：`GET /procedures` 的 `search` 参数此前仅空标注「全文搜索」，未定义覆盖范围 / 实现 / 呈现。本节定清。注意与编辑器内**章节树**搜索（Q160 / editor §17.8，单程序内过滤）区分——本节是**程序库**搜索。
> 编号：续 §41（Q266–Q277）；本批 Q278–Q283。

### 42.1 Q278 搜索覆盖字段=code + name + description

**决策**：`search` 匹配 `procedure.code` + `name` + `description` 三字段（元信息级）。**不**搜章节 / 步骤标题与正文（**确认 Q328 / §52.3**）。

- 覆盖绝大多数「按编号 / 名称 / 简述找 SOP」。
- 后端 `LIKE '%kw%'`，**无需全文索引**；本期数据量小可接受，未来量大再上 fulltext。

### 42.2 Q279 搜索跨全库（忽略左树文件夹）

**决策**：一旦输入 `search`，**忽略左树选中的文件夹、跨全库搜**；结果列表显示路径列（呼应 Q270）。清空搜索回到当前文件夹视图。

### 42.3 Q280 仅匹配 is_current 版本

**决策**：搜索仅匹配各 group 的 `is_current` 版本，结果仍每 group 一行（与 §41 列表粒度 Q267 一致）；不搜历史版本。

### 42.4 Q281 匹配语义=子串包含 + 多词 AND

**决策**：大小写不敏感**子串包含**（`LIKE '%kw%'`）；多关键词按空格切分、**全部命中（AND）**；**无相关性排序**，结果按列表 `sort`（默认 `-updated_at`）排。

- code 按子串匹配（搜 `QC` 或 `00001` 均可命中 `QC-00001`）。

### 42.5 Q282 命中呈现=高亮 + 描述 snippet

**决策**：`name` / `code` 命中词 `<mark>` 高亮；`description` 命中时行下显示一段摘要 snippet（高亮词 ±N 字）。

### 42.6 Q283 输入交互=实时 debounce 300ms

**决策**：输入即搜，debounce **300ms**；`×` 清除按钮；**≥1 字符即触发**（中文单字有意义）。

### 42.7 本节落地/影响

| 项 | 落地 |
|----|------|
| Q278 / Q281 | [api-spec](api-specification.md) `GET /procedures` `search` 说明：`LIKE` 子串匹配 code/name/description、多词 AND、仅 is_current |
| Q279 | [editor-behavior.md §20.3](editor-behavior.md) 搜索跨全库 + 路径列 |
| Q282 / Q283 | [editor-behavior.md §20.3](editor-behavior.md) 高亮 + snippet + debounce 300ms |

---

## 四十三、审计日志查看 UI（Q284–Q289）

> 来源：审计数据已全量记录（§15 + 两张 audit 表，字段级 old/new diff + IP/UA + reason，**永久保留** Q125），端点 + 过滤参数齐全（[api-spec §5.9](api-specification.md)），但**查看 UI 未定**。受控文档合规追溯刚需。
> 编号：续 §42（Q278–Q283）；本批 Q284–Q289。

### 43.1 Q284 入口/结构=单一全局页 + 对象深链

**决策**：建**单一全局「审计日志」页**（全量 + 过滤，合规巡检）；程序 / 文件夹详情放「查看此对象审计」入口，**深链跳全局页并预填** `procedure_group_id`（程序）/ `target_id`（文件夹）过滤。**不**单建对象级独立视图（DRY）。

### 43.2 Q285 与版本历史时间线（§13.4）分工、不合并

**决策**：两者**职责分离、互不合并**：

| 视图 | 内容 | 面向 |
|------|------|------|
| 版本历史 tab（§13.4）| 版本里程碑（`version_change_log`：publish/rollback/deprecate/restore + notes + 回退按钮）| 用户操作 |
| 审计日志（本节）| 全量字段级追溯（含 chapter/step/附件 CRUD + IP/UA + old/new diff）| 合规 |

- 版本历史 tab 加一个「查看完整审计」链接 → 走 Q284 深链（预填该 group）。

### 43.3 Q286 过滤器=全部暴露

**决策**：查看页暴露 [§5.9](api-specification.md) 全部过滤：`action`（多选）/ 时间范围（`date_from`/`date_to`）/ 对象（`procedure_group_id` 或 `target_id`）/ `ip_address` / 分页。

### 43.4 Q287 记录呈现 + 字段级 diff

**决策**：列表行（时间 / 动作 / 对象 + 类型 / 一句话摘要 / IP·UA）+ 点击**就地展开字段级 diff 表**（`字段 | 旧值 | 新值`，来自 `old_value`/`new_value` JSON）。

- 批量操作（`{ids, count}`）显示「影响 N 项」+ ids 列表。
- `reason`（rollback/deprecate/restore/delete 必填）行内显著显示。
- 摘要按 action 生成（如 `name: A→B`、`移动到 {folder}`、`发布 v2`）。

### 43.5 Q288 导出=当前过滤结果 CSV

**决策**：支持「导出当前过滤结果」为 **CSV**（合规留档）；新增 `GET /audit-logs/{procedures|folders}?export=csv`（带相同过滤、流式导出、忽略分页）。不做复杂报表 / 图表。

- 与 §15「运维手动归档（导出 + 截断）」区分：本项是**用户侧按过滤导出**、不截断数据。

### 43.6 Q289 权限/范围=任何人只读

**决策**：无登录前提下**任何人可只读查看**审计（与全站匿名一致）；审计记录**只读、不可改、不可删**（永久保留 Q125）；无写接口。

### 43.7 本节落地/影响

| 项 | 落地 |
|----|------|
| Q284 / Q286 / Q287 | 新增 [editor-behavior.md §21 审计日志查看页](editor-behavior.md) |
| Q285 | [editor-behavior.md §13.4](editor-behavior.md) 版本历史 tab 加「查看完整审计」链接 |
| Q288 | [api-specification.md §5.9](api-specification.md) 新增 `export=csv` |
| Q289 | [api-specification.md §5.9](api-specification.md) 注明只读 / 匿名可看 |

---

## 四十四、模板库替代 procedure template（Q290–Q293）

> **⛔ 本节 Q291 / Q292 / Q293（模板库 `system` 文件夹 + 三套样板种子 + 新建「从模板库复制」）已被 [§56 / Q340](#五十六砍模板库纯-copy-自现有程序q340) 整体推翻**：模板库与 copy 重叠纯属"换名重长"，砍掉模板库、删三套骨架，模板功能彻底归零；要套结构 = 去任意现有程序 `⋮ → 复制为新程序`（§18/Q179）。**仅 Q290（废弃 procedure template 表/功能）保留有效**；Q293 的「copy 允许 DRAFT 源」子项亦保留。下文 Q291–Q293 仅作历史保留。

> 来源：用户质疑 procedure template 与已成熟的**程序复制（copy）**高度重叠、提议用 copy 替代。评估确认重叠且 copy 更强（能带程序级元数据），采纳。**整体推翻 Q209/Q210/Q218**，删 `tb_procedure_template` 表，改「模板库系统文件夹 + copy」。grill-with-docs 方式（一次一题）。

### 44.1 Q290 废弃 procedure template，改「模板库 + copy」（推翻 Q209/Q210/Q218）

**决策**：废弃 procedure template 功能（`tb_procedure_template` 表 + Q218 全功能管理 + Q209/Q210 机制），改用「**模板库系统文件夹 + copy**」：模板 = 模板库（system 文件夹）里的样板程序；新建套结构 = 从模板库 copy。

**Why**：template 展开与 copy 深拷贝本质同构（都「以某结构为蓝本生成新 DRAFT 程序」），copy 已成熟（版本/附件/字段/Q238-241 全处理好）且**更强**（带 level_of_use/risk/quality/custom_values 程序级元数据，template body 只有章节树；其中 risk/quality 继承经 [Q339/§55](#五十五copy-继承-riskqualityq339) 补 §18.2 漏字段后坐实）。砍 template = 净简化：少一表、少 body JSON + 展开逻辑、少模板编辑 UI、消除 body 同步难题（样板天然用最新 step 12 型/三字段）+ 预设升级难题（样板就是程序，直接编辑）。

### 44.2 Q291 模板库系统文件夹

**决策**：新增单个 `system=true` 叶子文件夹「📋 模板库」（复用「废止」文件夹同款 system 机制：禁删 / 禁改名）。

- 模板 = 模板库里的**样板程序**，状态 **DRAFT**（用结构化编辑器维护，所见即所得）。
- prefix = `TPL`，样板 code `TPL-00001…`（仅模板库内标识；copy 到正常文件夹时按目标 prefix 重生成正式 code，Q139）。
- 模板库 `system=true` → 程序库列表 / 门户 / 统计天然过滤排除（§13.5 过滤 system=false）。
- **不分类**（单层平铺，模板少；未来需要再议）。

### 44.3 Q292 维护入口 + 新建「从模板库复制」

**决策**：
- **维护入口**：模板库**独立入口**（仿「废止」文件夹 Q269/§22.16），进去用结构化编辑器编样板程序。
- **新建入口**（修订 §41 Q276）：新建弹窗「模板（可选）」改为「**从模板库复制（可选）**」——选样板 → 内联走 copy 到目标文件夹 + 弹窗 name/level_of_use 覆盖；不选 = 空白新建。
- **取代** `POST /procedures` 的 `template_id`（Q218）：新建套结构走 copy，不再有 template_id 参数。

### 44.4 Q293 copy 允许 DRAFT 源 + 预设种子

**决策**：
- **copy 允许源为 DRAFT**：模板库样板是 DRAFT，copy 从 DRAFT 源复制（copy 是读源建新，源 DRAFT 不阻塞）。原 copy「从所见版本」（Q238）扩展容纳 DRAFT 源。
- **预设种子**：启动初始化「模板库」system 文件夹 + 三个样板程序（general / testing / maintenance 结构，内容蓝本沿 §28.2，载体改真实 procedure），取代原 tb_procedure_template 种子。

### 44.5 本节推翻/影响

| 决策 | 状态 |
|---|---|
| Q209 procedure 模板机制 | **推翻** → 模板库 + copy（44.1）|
| Q210 三套预设 body | **推翻** → 三套样板程序种子（44.4）|
| Q218 tb_procedure_template 全功能管理 | **推翻** → 编辑器编样板程序（44.1/44.3）|
| data-model §3.12 表 | **删除**（44.1）|
| `POST /procedures` 的 template_id | **移除**（44.3，套结构走 copy）|
| §41 Q276 新建弹窗「模板可选」 | **修订** → 「从模板库复制」（44.3）|
| copy 源状态 | **扩展** → 允许 DRAFT（44.4）|
| 启动种子 | tb_procedure_template 种子 → 模板库 + 三样板程序（44.4）|

**落地**：data-model（删 §3.12 + §3.1 模板库 + §6 种子）、api-spec（POST /procedures 删 template_id + copy DRAFT）、editor-behavior（模板库入口 + 新建弹窗）、本章 §44。

---

## 四十五、附件上传与管理 UI（Q294–Q299）

> 来源：程序级附件的数据模型 / 限制 / 端点已**全部齐全**（[data-model §3.6](data-model.md)：50MB/文件、≤30 个、≤200MB 总 Q120、任意类型；[api-spec §5.5](api-specification.md)：list/upload/download/preview/PUT/DELETE；§14 版本传递；§32 下载/预览/只读策略）。**唯独前端上传 / 管理 UX 未定**（editor §1 仅一行「上传+列表+限制提示」）。本节补齐。
> 编号：**§44 为并行会话「模板库替代 procedure template」（Q290–Q293），本节让号为 §45 / Q294–Q299**（同一并行会话第二次撞号，本会话再次让号）。

### 45.1 Q294 位置=编辑器「附件」tab

**决策**：程序级附件在**编辑器右侧「附件」tab**（与 节点详情 / 版本历史 并列，§1.3）管理；附件挂 **procedure 版本**（非章节 / 步骤）。

### 45.2 Q295 上传=拖拽 + 点选 + 多文件进度

**决策**：拖拽放置区 + 点选按钮；多文件队列、逐文件进度条、失败可重试；调 `POST /procedures/{id}/attachments`（multipart）。**仅 `is_current + DRAFT` 可上传**（Q228），否则 tab 进只读态（仅下载 / 预览）。

### 45.3 Q296 限制反馈=前端预校验（复用 Q120）

**决策**：前端上传前预校验并即时提示——单文件 **≤ 50MB**、单版本 **≤ 30 个**、总 **≤ 200MB**（Q120）；超限文案对应 `ATTACHMENT_LIMIT_EXCEEDED`。**不限制类型**（任意 MIME，Q226）。

### 45.4 Q297 列表 / 管理

**决策**：列表每行 = 类型图标 / `file_name` / 大小 / 上传时间 / `description`；操作 = 下载 / 预览（白名单）/ 编辑描述 / **拖拽排序**（`sort_order`）/ 删除（二次确认）。**只读态**（非 is_current+DRAFT）仅留下载 / 预览，隐藏增删改（Q228）。同名文件允许并存（Q119）。

### 45.5 Q298 预览=白名单 inline 模态（Q229）

**决策**：白名单类型（png/jpg/gif/webp/pdf）显示「预览」入口 → 模态 / 抽屉内联展示（`GET /attachments/{id}/preview`，`inline`）；非白名单**无预览入口、仅下载**（Q229）。

### 45.6 Q299 与 step.attachment_marks 区分

**决策**：本 tab 管**程序级真文件附件**（`tb_procedure_attachment`）；**step.attachment_marks**（Q203/Q220）是**步骤级纯标记 / 引用提示**（文件名 + kind，不校验文件是否上传），在 step 编辑面板，二者**独立、互不耦合**。

### 45.7 本节落地/影响

| 项 | 落地 |
|----|------|
| Q294–Q299 | 新增 [editor-behavior.md §22 附件上传与管理](editor-behavior.md)；§1 布局表「附件」指向 §22 |
| 后端 | 无新增——[data-model §3.6](data-model.md) / [api-spec §5.5](api-specification.md) 已齐全 |

---

## 四十六、已读确认（mark-read）流程（Q300–Q304）

> 来源：B2 已读基建齐全（`is_read`/`read_at` 全局单标志 + `POST mark-read` + `GET pending-read`/`completed-read` + `require_read_confirmation`），但**交互流程**未定（§41 Q277 标注的「独立主题」）。**纯前端流程 + 复用既有字段端点，无新增字段 / 表。**
> 编号：续 §45（Q294–Q299）；本批 Q300–Q304。

### 46.1 Q300 标记入口=已发布只读视图顶部

**决策**：在 **`is_current` + `PUBLISHED`** 程序的只读视图（`/procedures/{id}/view`）顶部，若 `is_read=false` 显「标记已读」按钮 / banner → `POST /procedures/{id}/mark-read`。DRAFT / ARCHIVED 不显示（仅生效版需确认）。

### 46.2 Q301 require_read_confirmation 语义=强提示、非强阻断

**决策**：`require_read_confirmation=true` 时，未读的生效版**显著待办提示**（只读视图顶部黄条「请确认已读」+ 全局「待阅读(N)」入口 Q304）；**不阻断任何操作**（无登录、无可阻断的下游动作，"强制"=强提示）。`=false` 时静默——不提示，仅保留手动「标记已读」（可选）。

**Why**：系统无登录、无"读完才能做 X"的下游门槛，强阻断无落点；require 的合理落点是把未读 SOP 推到用户面前（提示 + 待办计数），而非拦截。

### 46.3 Q302 范围 + 全局语义

**决策**：仅 **`is_current` + `PUBLISHED`** 可标记已读；`is_read` 是**全局单标志**（无登录，任何人点击即全局已读），`read_at` 记最后标记时间，不记标记人（无用户，B2）。一次标记即「已读」，不提供取消（除非新版本重置，Q303）。

### 46.4 Q303 新版本发布自动重置已读

**决策**：发布新版本 → 新 `tb_procedure` 记录 `is_read=false`（天然），新生效版自动回到「未读 / 待确认」；旧版本转 ARCHIVED 其 `is_read` 不变（历史留痕）。**即「发布新版自动要求重新确认已读」**，无需额外机制（与 copy 重置 Q239 同款字段语义）。

### 46.5 Q304 待阅读入口=全局徽标 + 列表筛选

**决策**：`require_read_confirmation=true` 时——全局导航「待阅读」入口带计数徽标（N = `GET /procedures/pending-read`，即程序库条件 PUBLISHED+is_current AND `is_read=false`，§13.5）+ 程序库列表「待阅读」快捷筛选（§41 Q277 已定）。`=false` 时不显示。

### 46.6 本节落地/影响

| 项 | 落地 |
|----|------|
| Q300–Q304 | 新增 [editor-behavior.md §23 已读确认流程](editor-behavior.md) |
| 后端 | 无新增——`is_read`/`read_at` + mark-read/pending-read/completed-read + `require_read_confirmation` 已齐全（B2 / [api-spec §5.2](api-specification.md)）|

---

## 四十七、编号引擎多级规则（Q305–Q311）

> 来源：编号规则散见 Q15（编号体系）/ Q27（步骤编号）/ §15.2-15.3（L1 标准章节 1.0–13.0）/ pdf §6.2 §6.6，**彼此不一致**——Q15 递归算出 L1=`N`，但 §15/§6.6 要 `N.0`；Q15 skip「占位消耗序号」会把 PPA「1.0 目的」挤位。本节钉死多级编号引擎规则并修矛盾。grill-with-docs 方式（一次一题）。
> 编号：续 §46（Q300–Q304）；本批 Q305–Q311。

### 47.1 Q305 L1 `.0` = 仅渲染层（内部 code 递归）

**决策**：L1 章节显示 `N.0`（DPMS/§15.2 习惯：`1.0 目的` … `13.0 附件`），但 **`.0` 仅渲染层**——内部 `code` 仍递归（L1=`N`、L2=`N.M`、L3=`N.M.K`），PDF / TOC / 树视图渲染时对 **level==1 的 chapter** 追加 `.0`。

- Q15 递归规则不动，只补一条「L1 显示追加 .0」。
- step 子码天然 = 父 chapter.code + 序号 = `N.M`（不含 .0），与 DPMS step 习惯一致，不受 .0 影响。
- 附件自动章节（pdf §6.6）一并按此显示（最后正文 chapter `12.0` → 附件 `13.0`）。

**Why**：`.0` 存进 code 会逼子节点构造时剥离父级 `.0`（否则 step=`10.0.1`），引擎多特例易错；render-only 让数据层干净、显示层合规。

### 47.2 Q306 skip_numbering = 跳过不计数、编号连续（推翻 Q15「占位消耗序号」）

**决策**：skip_numbering 节点**不计入序号**；同级编号节点**连续编号**。例：前言(skip) + 目的 + 范围 → （无号）、`1.0`、`2.0`。

- **推翻 Q15 原「不跳号语义」**（`1, ?, 3` 占位消耗、下一个 `4`）。
- skip 子树整体不编号（沿用 Q15）；skip 节点本身**不占序号位**。

**Why**：占位消耗会把 skip（前言/附录等非标准章节）夹在标准章节间时整体错位，违反 PPA「1.0 目的」恒为首。跳过不计数 = 与 Word 自动重排一致、最直觉、PPA 合规。

### 47.3 Q307 skip 显示 = 编辑器/树「#」、PDF 空白（统一 Q15「?」）

**决策**：skip 节点「编号位」——**编辑器 / 树视图**用灰「#」（便于编写者识别 skip 态）；**PDF 成品**留空白（标题顶到编号列右端）。**统一掉 Q15 的「?」**（作废）。

- 树视图 `#` 已是现状（pdf §10 / editor）；PDF 空白已是现状（pdf §6.2 / §3）；本决策仅消除 Q15「?」这第三种写法。

### 47.4 Q308 step 编号最深 4 段（3 级上限仅约束 chapter）

**决策**：章节 3 级上限（Q190）**仅约束 chapter**；step 是末端执行项，可在任意层级章节下编号，最深 = L3 章节下 step → 4 段 `1.1.1.1`。**step 为叶子**（无子步骤，深层结构用子章节表达）。

### 47.5 Q309 全自动、不可手工改号

**决策**：编号一律由引擎按 `sort_order` 自动生成，**用户不可手工改号、不设自定义起始号**。调顺序用上移 / 下移 / 拖拽（Q26）。

**Why**：PPA 不强制结构（Q181），无固定号需求；全自动最简、无脱节风险（呼应「别堆配置项」）。

### 47.6 Q310 结构变更即时重算

**决策**：每次结构变更（增 / 删 / 移 / skip 切换）后**即时自动重算**受影响兄弟链 + 子树 code。与 Q15「整树重算」、pdf §10「下方同级 code 整树重算」一致；所见即所得，无「保存才更新」延迟、无手动「重新编号」按钮。

### 47.7 Q311 省略可选章节 = 顺序号自然前移

**决策**：编号纯按 `sort_order` 连续，**省略 / 删除可选标准章节时后续号自然前移**（如省略可选「术语定义」→「职责」变 `4.0`）。**不**锁定 PPA 固定号、不留缺口。

**Why**：与 Q181（不强制 PPA 结构）一致；编号只是顺序，不绑定章节语义。锁定固定号需「标题→PPA 章节」映射，复杂且越界。

### 47.8 本节修订/影响的既有决策

| 既有决策 | 状态 |
|---|---|
| Q15「不跳号语义」（占位消耗序号）| **推翻** → 跳过不计数（47.2）|
| Q15 L1 编号 = `N` | **补充** → 内部仍 `N`，L1 显示追加 `.0`（47.1）|
| Q15 skip 显示「?」| **作废** → 编辑器 `#` / PDF 空白（47.3）|
| Q27 步骤编号 | **补充** → 最深 4 段、step 为叶子（47.4）|
| §15.2/§15.3 L1=1.0–13.0、§6.6 附件 13.0 | **确认** → 由 render-only `.0` 实现（47.1）|

### 47.9 本节落地/影响

| 项 | 落地 |
|----|------|
| Q305 | pdf-rendering §6.2 L1 渲染追加 `.0`；data-model `code` 注明 render-only；editor 树视图 L1 显示 `N.0` |
| Q306 | 本文件 Q15 已改；pdf / editor 编号连续（跳过不计数）|
| Q307 | editor 树 `#` / pdf 空白；Q15「?」作废 |
| Q308 | 本文件 Q27 已注明（最深 4 段、step 叶子）|
| Q309/Q310/Q311 | 引擎实现说明（development-plan 编号引擎任务）；纯计算、无新字段 / 表 |

---

## 四十八、图表编号与交叉引用不自动化（Q312）

> 来源：grill「图表编号 + 交叉引用」主题。勘察确认图/表均**内嵌富文本 HTML**（非树节点），自动编号须靠渲染期扫描、交叉引用须稳定 token（中等复杂度）。grill 中**用户改变主意，决定不做自动化**，编号 / 题注 / 引用交用户在富文本手工书写。
> 编号：续 §47（Q305–Q311）；本节 Q312。

### 48.1 Q312 图表不自动编号、不解析交叉引用（手工）

**决策**：Smart SOP **不提供**图 / 表的自动题注、自动编号、交叉引用解析。图仍为 `<img>`、表仍为 `<table>`，内嵌 content / step 富文本（**现状不变**）。作者若需「图 1：…」题注或「见图 1」引用，**在富文本里作为普通文字 / 段落手工书写**；PDF / 预览**原样渲染**，不注入编号、不匹配引用。

- **不新增**：无 `<figure>`/`<figcaption>` 约定、无 caption 字段、无 `data-fig-id`/`data-ref` token、无渲染期编号扫描、无编辑器「插入引用」按钮、**无新字段 / 表 / 端点**。
- 与既有「图片走 assets + 内联 `<img>`」（Q189）、「表格标准 `<table>` HTML」（Q205/Q31）完全一致，无改动。

**Why**：图表埋在富文本 HTML（非树节点），自动化须渲染期全文扫描 + 稳定 token，中等复杂度；PPA 不强制结构（Q181），手工书写零基建、最简，符合「别堆基建」。章节大纲号已由 §47 引擎自动维护，图表号属富文本内容范畴、交作者掌控。

### 48.2 本节落地/影响

| 项 | 落地 |
|----|------|
| Q312 | [pdf-rendering §9](pdf-rendering.md) 注明：不做图表题注 / 编号 / 交叉引用，作者富文本手工书写、渲染器原样输出；无新字段 / 表 / 端点 |

---

## 四十九、UI 设计系统（Q313–Q319）

> 来源：UI 视觉风格 grill。用户要「工业风 / Claude Code 桌面版」。本节钉死整套视觉调性与 Element Plus 改造策略；详细令牌表 / 组件规范见 [design-system.md](design-system.md)。
> 编号：续 §48（Q312）；本批 Q313–Q319。**注意：撞号教训**——立项时 memory 记「下一个 Q305」已过期（并行会话已用 Q305–Q312 / §47–§48），落地前 grep 全库才定到 Q313 / §49。

### 49.1 Q313 整体调子 = 暖炭黑 · Claude Code 本色

**决策**：暖炭黑暗壳（`bg-surface #211E1B`）+ 陶土橙强调（`accent #D97757`）+ 暖白文字（`text-primary #ECE6DD`）；应用框架（导航 / 侧栏 / 列表 / 工具栏 / 弹层）走暗壳，**文档区**（编辑器画布 / PDF 预览）保持亮纸底（`paper-bg #FAF8F4`）。

**Why**：最忠实于用户点名的 Claude Code 桌面版；SOP 文档最终要打印成 PDF，编辑 / 预览用亮纸既不刺眼又「所编即所印」。

### 49.2 Q314 字体 = 数据等宽 / 正文无衬线

**决策**：编号 `QC-0001`、版本 `v3`、测量值、状态枚举、日期等「数据」走等宽（`JetBrains Mono / Sarasa Mono SC`）；标题 / 正文 / 菜单 / 按钮 / 状态词走无衬线（`Inter` + 既有 CJK 栈）。

**Why**：等宽让数据列天然对齐、辨识度高，是 Claude Code 的做法，工业 / 技术感恰到好处。

### 49.3 Q315 信息密度适中 + 工业线条

**决策**：列表行 40px、表格行 36–40px（适中）；小圆角（按钮 / 输入 4px、卡片 6px、模态 8px）；**分隔靠 1px 线不靠阴影**，阴影仅留给下拉 / 模态。

**Why**：贴合 Claude Code 桌面版观感；线条 + 小圆角是工业骨架，日常编写 / 阅读不累。

### 49.4 Q316 强调色克制（陶土橙仅交互）

**决策**：陶土橙只用于主按钮、选中 / 激活态、焦点环、激活竖条；其余一律中性暖白 / 灰。**陶土橙不当状态色**。

**Why**：克制 = 专业冷静；让「橙」语义唯一（交互），避免视觉噪点。

### 49.5 Q317 状态色暖盘（**修订 Q172**）

**决策**：状态配色由 EP 默认盘改为暖盘，呈现由填充 tag 改为圆点 + 等宽标签：

| 状态 | 新 Hex | 原 Q172 | 呈现 |
|---|---|---|---|
| DRAFT 草稿 | `#A89A86` 暖灰 | `#909399` | ○ 空心点 |
| PUBLISHED 已发布 | `#88B07A` 鼠尾草绿 | ~~`#409EFF` 主蓝~~ | ● 实心点 |
| ARCHIVED 已归档 | `#6B635A` 暗暖灰 | `#606266` | ● 暗点 |
| 废止 DEPRECATED | `#D9685E` 暖红 | `#F56C6C` | 描边小红 tag |

**Why**：新暗壳里 EP 主蓝 `#409EFF` 与暖调 + 陶土橙打架；且 EP `primary` 已重映射成陶土橙，「已发布 = primary 蓝」不再成立。已发布改鼠尾草绿，使陶土橙语义唯一（交互）。用户已明确同意修订 Q172。

### 49.6 Q318 Element Plus 改造策略

**决策**：令牌单一来源（`tokens.css` CSS 变量）→ Tailwind 与 EP 都读它；EP 启用暗模式 + 在 `element-overrides.css` 把 `--el-*` 重映射到令牌（含 primary 阶梯 → 陶土橙、语义色 → 状态盘、圆角 4px）；亮纸区用 `.paper` 容器局部把变量切回浅色（EP 弹层 teleport 到 body 故自动保持暗壳）；WangEditor 另起 `wangeditor-overrides.css`。全部走集中覆盖通道（合规 §8.1）。

**Why**：变量重映射不动 EP 组件结构、改一处全局生效；单一来源杜绝 Tailwind / EP 配色漂移。

### 49.7 Q319 自建 vs EP 分工

**决策**：表单控件 / 日期 / 对话框 / 下拉 / 消息 / 分页 / tabs / 上传 / el-table 用 EP（变量重映射即可）；应用框架 / 侧栏项 / 状态点 + 标签 / 程序库列表行 / 卡片自建（Tailwind + scoped）。

**Why**：列表行视觉（等宽编号 + 左激活条 + 圆点状态）特化，自建比硬掰 el-table 划算；表单密集处用 EP 省事。

### 49.8 本节修订 / 影响的既有决策

| 既有决策 | 状态 |
|---|---|
| Q172 status chip = EP 默认盘（已发布主蓝）| **修订** → 暖盘 + 圆点呈现（49.5 / Q317）|
| frontend-coding-standards §8.2 色板表 | **回填** → 改为本暖盘令牌 |
| tailwind.config.js `primary:#409eff` | **替换** → 令牌色板（实现期落地）|

### 49.9 本节落地 / 影响

| 项 | 落地 |
|----|------|
| Q313–Q319 | 新增 [design-system.md](design-system.md)（令牌 / 组件 / EP 改造完整规范）|
| Q317 | [§22.8 Q172](#二十二版本管理-ui-流程q165q180) 加修订注；[frontend-coding-standards §8.2](frontend-coding-standards.md) 色板回填 |
| 实现期 | `tokens.css` / `element-overrides.css` / `wangeditor-overrides.css` 新建、`tailwind.config.js` 令牌化、`<html class="dark">`、EP 暗模式引入（writing-plans 排期，本节不含代码）|

---

## 五十、工作台/首页 IA（Q320–Q321）

> 来源：grill「工作台/首页 IA」。design-system §3.1 仅定**视觉外壳**（顶栏/侧栏/主区），未定打开应用后的**落地页 IA**。无登录硬约束（无用户、`is_read` 全局单标志 B2）→ 收藏/我的/跨设备最近无落点。本节定落地页 + 全局入口归位。
> 编号：续 §49（Q313–Q319，并行会话占）；本批 Q320–Q321。

### 50.1 Q320 落地页 = 程序库列表，不建独立工作台

**决策**：应用根路由 `/` **直接 = 程序库列表**（§41），**不**建独立工作台 / dashboard。复用顶栏已有：全库搜索 + 待阅读(N) 徽标（点击即筛列表 `PUBLISHED + is_current + 未读`，Q304）+ ⚙ 设置。

- **不新增**：无 dashboard 页、无收藏 / 我的（无用户）、无 session 级「最近」、**无新字段 / 表 / 端点**。
- 待阅读、搜索、新建（列表右上 + 左树叶子悬浮 `+`，Q276）入口均已在外壳 / 列表，dashboard 增量有限。

**Why**：无登录→个性化（收藏 / 我的 / 跨设备最近）无落点；待阅读已是顶栏全局徽标、搜索已在顶栏，dashboard 相比直接落列表增量有限。最简、零基建。

### 50.2 Q321 全局入口归位 = 混合（内容进侧栏 / 管理进 ⚙）

**决策**：全局 / 系统入口按「内容容器 vs 管理类」两分——
- **侧栏底部系统区**（文件夹树下方、独立分隔）：**废止**（§41 Q269）——程序容器（模板库已废，[§56/Q340](#五十六砍模板库纯-copy-自现有程序q340)）。
- **顶栏 ⚙ 菜单**：**设置**（§39）+ **审计日志**（§43 全局页，原入口未定、本节定为此）——都是「管理类」。

- 待阅读(N) + 全库搜索保持顶栏（design-system §3.1）；新建保持列表内（Q276）。
- 审计的对象级深链（§43 Q284「查看此对象审计」）不变；**全局**审计页经 ⚙ 进。

**Why**：语义清晰（内容容器归侧栏、管理动作归 ⚙）、对现状最小改（侧栏已有废止、⚙ 已有设置）；避免 ⚙ 菜单或侧栏单边过载。

> **修订 (2026-05-26)**：「文件夹配置」（原称「标准文件库」）实际是 admin 配置页（定义文件夹分类与编号规则），归 ⚙ 配置组而非侧栏内容容器；同时撤回"侧栏底部系统区放废止入口"的 §3.1 设想——「废止」按 §13 的逻辑应当走 `folder.system=true` 文件夹过滤，需要 ProcedureLibraryView 加 folder_id 支持，留作独立 topic。Q321 原决策"内容容器 vs 管理类"两分法仍然成立。

> **R2 修订 (2026-05-26)**：上述"废止入口留作独立 topic"已落地——通过 ProcedureLibraryView 双栏重构（左 FolderTreePane + 右 ListPane）原生承载，"废止"成为文件夹树中的一员、无需独立路由或侧栏入口。同时新增"归档"系统文件夹与之同级（语义：保留备查 / 废止：不再使用）。详见 [`docs/superpowers/specs/2026-05-26-library-ia-archive-folder-design.md`]。

### 50.3 本节落地/影响

| 项 | 落地 |
|----|------|
| Q320 | 前端路由 `/` = 程序库列表（§41 / [editor §20](editor-behavior.md)）；无 dashboard 页 |
| Q321 | [design-system.md §3.1](design-system.md) 外壳补：侧栏底部系统区（废止；模板库已废 §56/Q340）、⚙ 菜单（设置 + 审计）；[editor §21](editor-behavior.md) 全局审计页入口 = ⚙ 菜单；无新字段 / 表 / 端点 |

---

## 五十一、安全姿态与匿名写防护（Q322–Q325）

> 来源：grill「匿名写接口的生产安全姿态」。§1 移除用户 / 鉴权后，整套安全模型 = 匿名 + nginx IP 限流 + CORS；限流只防量不防质，且隐含「部署于受信任网络」的前提从未写明。本节钉死信任边界、补齐写 / 上传限流、修审计真实 IP、确认破坏性操作护栏。
> 编号：续 §50（Q320–Q321）；本批 Q322–Q325。落地前 grep 全库确认上限为 Q321（撞号教训见 §49）。

### 51.1 Q322 部署信任边界 = 受控内网为硬前提（App 纯匿名，门禁下沉网络层）

**决策**：Smart SOP 以「**仅部署于受信任内网 / LAN**」为**硬性前提**。App 层维持全匿名（不违背 §1 移除用户体系），任何写保护 / 门禁一律下沉**网络层**（nginx / VPN / 防火墙），由部署方负责。需暴露公网者，文档提供**可选**反代门禁指引（Basic-Auth / IP allowlist），**不强制、不进 App**。

**Why**：匿名可写只在受控网络成立；把门禁放回 App 等于重新引入 §1 删掉的鉴权。受控内网前提下「全匿名被恶意刷写」风险由中→低。最简、零基建、忠于定位。

### 51.2 Q323 写 / 上传接口限流扩展（仍纯 nginx 层、后端不内置）

**决策**：在既有 `/parse`(10) / `/pdf-*`(20) / `/apply-marks`(30) 限流基础上**补齐写与上传路由**：

| 路由组 | 限流 |
|---|---|
| `POST /uploads` | **10 req/min/IP**（+ `client_max_body_size` / 50MB）|
| 写操作（POST/PUT/DELETE 其余写路由）| **60 req/min/IP** |
| 读操作（GET）| **300 req/min/IP** |
| `/parse` / `/pdf-*` / `/apply-marks` | **维持** 10 / 20 / 30 |

**Why**：原「其他 120/min」把匿名写与上传一并放行，内网里一个跑飞脚本即可灌盘 / 刷写。上传最重故最严（10）；写 60 足够正常编辑；读无破坏性放宽到 300。

### 51.3 Q324 审计真实 IP（X-Forwarded-For）+ IP 级追溯封顶

**决策**：审计中间件**信任并解析 `X-Forwarded-For`**（nginx 已设 `X-Real-IP` / `X-Forwarded-For`，见 deployment §5.3），配 `TRUSTED_PROXIES`（env，默认信任直连反代），取最左侧非可信 IP 写 `tb_*_audit_log.ip_address`。明确**追溯天花板 = IP / UA / 时间，无人身份**（匿名设计的必然）。

**Why**：App 坐 nginx 后，不解析 XFF 则审计记的全是代理容器 IP，IP 级追溯报废。无登录 → 追责只能到 IP 级，须写明以免高估审计能力。

### 51.4 Q325 破坏性操作护栏 = 既有软删 + restore + 审计（batch-delete 加上限）

**决策**：`DELETE` / `deprecate 整 group` / `batch-delete` 维持现有兜底——**软删 `is_active` + deprecated / restore 流程 + reason 必填（deprecate / rollback / restore / delete，Q128）+ 全量审计**，即刻意安全网，**不加写 token / 额外确认**。补一条：`batch-delete` 加**服务端条数上限 ≤100**（类比 apply-marks 100 上限）限制爆炸半径。

**Why**：受控内网 + 软删可恢复 + 审计可溯，已足够；再加 App 级闸违背 §1。batch-delete 上限防一次误删过多。

### 51.5 本节落地 / 影响

| 项 | 落地 |
|----|------|
| Q322 | [deployment.md §5](deployment.md) 加「受控内网硬前提」+ 可选反代门禁指引；无 App 改动 |
| Q323 | [api-specification.md §8](api-specification.md) 限流表补 uploads / 写 / 读；[deployment.md §5.3](deployment.md) nginx 加 `limit_req` zone |
| Q324 | [api-specification.md §1 鉴权](api-specification.md) 注 XFF + IP 级追溯；[data-model.md §3.9](data-model.md) 审计表注真实 IP 来源；[deployment.md §2](deployment.md) env 加 `TRUSTED_PROXIES`；development-plan Phase 1 审计中间件含 XFF 解析 |
| Q325 | batch-delete service 加 ≤100 上限（[api-specification.md](api-specification.md) 批量端点注）；既有软删 / restore / 审计不变 |

---

## 五十二、跨切面范围确认（Q326–Q330）

> 来源：grill「未 grill 透的横切问题」批量确认。本批 5 条均为「**确认 / 收紧既有倾向**」而非新机制：数据迁移、i18n、搜索边界、可观测性、响应式 / 浏览器矩阵。多数既有文档已隐含，本节正式定号。
> 编号：续 §51（Q322–Q325）；本批 Q326–Q330。落地前 grep 全库确认上限为 Q325。

### 52.1 Q326 存量数据迁移 = 不做，全新起步（greenfield）

**决策**：本期**不实现**任何 DPMS V2.0 存量数据迁移，**全新起步**。需导入历史 SOP 者走 Word 导入向导（§6 / §25）兜底。

**Why**：Smart SOP 是剥离的独立产品，DPMS 是异构 Django 表（含已删的用户 / 审批 / 仪表耦合）；一次性迁移属独立项目，强行内置会污染数据模型。data-model 已多处按 greenfield 假设（如 §3.10 legacy base64 仅防御性保留）。

### 52.2 Q327 语言 = 中文 only，不引 i18n 框架

**决策**：UI 与 PDF 输出**仅中文**；**不引入 i18n 框架 / locale 文件**。唯一前向准备 = 代码不拼接句子（用户可见文本写完整中文字面量）。

**Why**：产品面向中文场景；PPA 合规约束的是**结构**（section 模板 / 警示分级 / 页眉）不是语言。i18n 框架是未发生需求的过度工程；保留「不拼句」习惯使将来真要 i18n 时低成本接入。

### 52.3 Q328 搜索边界 = 维持 code+name+description（正文不可搜）

**决策**：程序库全文搜索维持 §42（Q278）——仅 `code` + `name` + `description`；**章节 / 步骤标题与富文本正文不进搜索**（§42.1 已明确，本条确认并定号）。

**Why**：正文是块结构 HTML，全文索引（MySQL FULLTEXT on HTML / 额外搜索引擎）成本高、收益边际；按编号 / 名称 / 简述定位已覆盖绝大多数场景。有真实需求再评估。

### 52.4 Q329 可观测性 = 最小化（结构化日志 + request-id；无 APM / 指标 / 链路栈）

**决策**：
- **日志**：生产输出**结构化 JSON**（字段 `time/level/logger/message/request_id`），开发用人读文本；按 `APP_ENV` 切 formatter（`app/config.py`）。
- **request-id**：中间件读 `X-Request-Id`，缺失则生成 uuid，贯穿日志与响应头。
- **健康探针**：维持 `GET /healthz`（liveness）/ `readyz`（readiness + DB 连通）。
- **不做**：APM / 应用内指标后端（Prometheus 等）/ 分布式链路追踪。业务可观测性由审计日志覆盖；基础设施指标（HTTP 码分布 / 时延 / DB 池 / 慢查询 / 磁盘）由反代访问日志 + 容器平台采集（deployment §7.2），非应用内嵌。

**Why**：单体同步服务 + 受控内网，结构化日志 + request-id + 审计已足够定位问题；引 APM / 指标栈是过度工程。

### 52.5 Q330 终端范围 = 桌面 only（现代浏览器，min-width ~1280，不做移动）

**决策**：仅面向**桌面**。支持现代常青浏览器（Chromium 系 / Firefox / Edge 近 2 个大版本）；**最小适配宽度 ~1280px**；**不做移动端 / 平板布局**（窄屏不保证可用，可后期再议只读降级）。

**Why**：design-system 即「Claude Code 桌面版」观感，SOP 编辑（左树 + 右内容 + 多 tab）是重桌面任务；移动布局投入大、与编辑场景不匹配。

### 52.6 本节落地 / 影响

| 项 | 落地 |
|----|------|
| Q326 | [data-model.md §7](data-model.md) 注明 greenfield、无 DPMS 数据迁移；历史导入走 Word 向导 |
| Q327 | [frontend-coding-standards.md §9](frontend-coding-standards.md) 收紧：中文 only、不引 i18n 框架 / locale 文件，仅保留「不拼句」前向准备 |
| Q328 | [§42.1](#421-q278-搜索覆盖字段code--name--description) 确认正文不可搜（无新接口 / 字段）|
| Q329 | [backend-coding-standards.md §7.2](backend-coding-standards.md) 日志 prod=JSON / dev=text + request-id 中间件；[deployment.md §7.2](deployment.md) 指标走基础设施侧、不内嵌 APM；healthz/readyz 维持 |
| Q330 | [frontend-coding-standards.md §13](frontend-coding-standards.md) 加「支持范围」：桌面 only / 浏览器矩阵 / min-width ~1280 |

---

## 五十三、后台任务调度与清理（Q331–Q334）

> 来源：grill「后台任务调度器」。3 个周期任务（附件磁盘清理 Q115 / asset GC Q197 / 临时上传清理 Q141）此前只散见各处定义，**未定运行器、单次执行保证、幂等、删除顺序、asset-GC 竞态**。本节钉死。备份 / 恢复留 operations-runbook.md（Phase 9）。
> 编号：续 §52（Q326–Q330）；本批 Q331–Q334。落地前 grep 全库确认上限为 Q330。
> 范围外（已另决）：`auto_archive_days` 定时归档（Q259 未接线）、>365 天软删物理清除（database-spec 暂不实现）。

### 53.1 Q331 运行器 = 独立 APScheduler 进程（replicas=1，无 broker）

**决策**：周期任务由**独立 `scheduler` 服务**承载——compose 内单独 service、**replicas=1**、跑 APScheduler；**不引 Celery / broker / Redis**。任务直接 import 应用代码与 SQLAlchemy session。每个任务同时是 CLI 入口 `python -m app.tasks.<name> --once`（调度器内部调用 + 运维手动触发共用）。

**Why**：单实例天然「单次执行」，免去多 gunicorn worker 重跑所需的分布式锁；Python 原生、复用 ORM；零 broker 契合最简定位（Q329）。

### 53.2 Q332 执行语义 = 定时 + 幂等 + 逐项提交 + 文件先删

**决策**：
- **调度**（env 可配）：附件清理 + asset GC **每日 `CLEANUP_HOUR`（默认 03:00 服务器时区）**顺序跑；临时上传清理**每 1h** 扫 `expires_at` 过期 token。
- **幂等**：任务皆状态驱动，重跑只删「当前仍满足条件」者；无 catch-up。
- **逐项提交**：逐候选独立删除 + 提交，单项失败记日志并继续（不中断整批），失败项下轮自然再选中。
- **删除顺序（防孤儿）**：**先删物理文件**（文件已不存在视为成功）→ **再硬删 DB 行**；unlink 失败则保留行、下轮重试自愈。附件 / asset 行**与文件一并硬删**（历史留痕在 `tb_*_audit_log`，行本身无需保留）。

**Why**：单实例 + 逐项提交 = 一个坏文件不拖垮整批；文件先删保证「行存在但文件已删」的错配不发生，最坏只剩「文件已删行还在」→ 下轮幂等收敛。

### 53.3 Q333 asset-GC 竞态防护（sha256 去重 × GC 物删）

**决策**：sha256 全库去重下，asset 可能 `ref_count=0` 后被新 import（同 sha256）重新引用，若此时 GC 已删文件 → 悬挂引用。三重防护：
- **(a) grace 窗**：仅删 `ref_count=0` 且**持续 ≥24h** 者（用 `asset.updated_at` 判断归零时长，见下方契约）。
- **(b) 行 + 文件同删**（承 Q332）：GC 删文件时**一并硬删 asset 行**，故 sha256 去重查找永不返回「无文件的 asset 行」；之后同 sha256 的 import 查无行 → 用手上 docx 字节**重建新 asset**（无数据丢失）。
- **(c) 序列化**：GC 删除前 `SELECT ... FOR UPDATE` 锁 asset 行并**重核 `ref_count=0`**；import 的「按 sha256 找-或-建」依赖 `UNIQUE(sha256)`（已存在，§3.10）+ 取同一行锁。import 先 → count>0，GC 跳过；GC 先 → import 查无行，建新。

**契约**：asset_reference 重建（Q197，save/import）在引用集变化时**顺带 bump 对应 `asset.updated_at`**（含归零），使 grace 计时可靠——**无需新列**。

**Why**：grace + 行文件同删 + 行锁重核，任一独立都能堵大部分竞态，三者叠加彻底关闭「悬挂引用」窗口，且不加新字段（复用既有 `UNIQUE(sha256)` 与 `updated_at`）。

### 53.4 Q334 失败可观测 + 手动触发

**决策**：
- 每次运行输出**一条结构化 run 摘要日志**（`task / started_at / scanned / deleted / errors[]`）+ 逐项错误日志（承 Q329 结构化 JSON）。
- **不做**告警后端 / 心跳表（本期）。
- 每任务 = CLI `python -m app.tasks.<name> --once`，运维手动触发；列入 operations-runbook.md（Phase 9 补）。

**Why**：受控内网 + 日志可查 + 幂等可重跑，结构化 run 摘要足够定位；告警 / 心跳属过度工程（Q329）。

### 53.5 本节落地 / 影响

| 项 | 落地 |
|----|------|
| Q331 | [docker-compose.yml](../docker-compose.yml) 加 `scheduler` service（replicas=1）；[deployment.md §5.1](deployment.md) 架构补 scheduler；development-plan 任务注明独立 APScheduler 进程 |
| Q332 | [deployment.md §2](deployment.md) env 加 `CLEANUP_HOUR`；[data-model.md §3.6](data-model.md) 附件清理注删除顺序 + 行文件同删 |
| Q333 | [data-model.md §3.10/§3.11](data-model.md) GC 规则补 grace 24h + 行锁重核 + 行文件同删 + `updated_at` bump 契约；`UNIQUE(sha256)` 已存在 |
| Q334 | run 摘要日志（承 Q329）；CLI 入口；operations-runbook.md（Phase 9）记手动触发 |

---

## 五十四、遗留延期项的收口（Q335–Q338）

> 来源：清理「待决 / 暂不 / 视优先级」遗留项——按用户要求**自动给出推荐并定案**，不再 grill。已明确「不在范围 / 远期」者（实时协作、离线编辑、非图附件预览、程序导出 Word）维持不变、不再立项。
> 编号：续 §53（Q331–Q334）；本批 Q335–Q338。落地前 grep 全库确认上限为 Q334。

### 54.1 Q335 多 tab 同程序编辑 = 不做专门协调，乐观锁即仲裁

**决策**：**不实现**跨 tab 协调机制（BroadcastChannel / 跨 tab 锁）。多 tab 编辑同一程序时：各 tab 独立 sessionStorage 草稿（`procedure_editor_${id}`，sessionStorage 本就 per-tab），保存走乐观锁（`If-Match: revision`，Q18）；先到先得，后到 **409** → 「载入远程版本」一键解决。

**Why**：乐观锁已杜绝丢写（核心风险），409 + 载入远程是足够恢复路径；受控内网 + 匿名场景下跨 tab 实时同步收益边际、成本（broadcast / 锁生命周期）不值。真实冲突频发再议。

### 54.2 Q336 编辑器自动保存 = 仅 sessionStorage，不落后端

**决策**：编辑器**不做后端自动保存**。模型 = 显式保存（PUT，仅 DRAFT 可写）+ sessionStorage 自动暂存（1s debounce，崩溃 / 误关恢复）。

**Why**：后端自动保存会与「显式 DRAFT 保存 + 乐观锁 + 审计合并」模型冲突，且制造版本 / 审计噪声与高频写。sessionStorage 已覆盖单 tab 崩溃恢复。数据丢失反馈再议。

### 54.3 Q337 auto_archive_days = 0.1.0 不实现，未来作 scheduler 第 4 任务

**决策**：`auto_archive_days`（active→ARCHIVED 自动归档）**0.1.0 不实现（不接线）**；DB 字段与默认值（365）保留、设置页隐藏（维持 Q259）。未来需要时作为 **§53 scheduler 第 4 个每日任务**接入：扫 `PUBLISHED + is_current` 且距上次发布 > `auto_archive_days` 天者转 ARCHIVED（`0` = 不归档）；接入时设置页才暴露、由管理员显式确认语义后启用。

**Why**：自动归档「当前发布版」语义有歧义（归档后该 group 无 current published 后继），无紧迫需求；从「Phase 9 视优先级」收口为「0.1.0 不做、未来 scheduler add-on」最稳，复用 §53 已建 scheduler、届时零新基建。

### 54.4 Q338 编号引擎性能 = 单趟 O(n) 即时重算，软上限 ~2000 节点

**决策**：结构变更时（Q310 即时触发）后端**单趟 O(n) 内存遍历整树重算 code**——纯算术，**无需分批 / 异步**。设**软上限 ~2000 节点**（chapter+step）：超出仅**非阻断提示**（建议拆分程序），不硬阻止保存。

**Why**：真实 SOP 极少超数百节点，O(n) 单趟 < 50ms；原风险表「大程序分批处理」属过度设计，去掉。软上限给极端情形心理预期，不牺牲可用性。

### 54.5 本节落地 / 影响

| 项 | 落地 |
|----|------|
| Q335 / Q336 | [development-plan §6](development-plan.md) 待决表 + [editor-behavior §18](editor-behavior.md) 后续待补：「多 tab 协调 / 后端自动保存」由「暂不 / 看反馈」改为**按设计不做**（乐观锁 + sessionStorage 足够）|
| Q337 | [development-plan §6](development-plan.md) 改「0.1.0 不实现、未来 §53 scheduler 第 4 任务」；[data-model.md §3.8](data-model.md) auto_archive_days 注同步；Q259 字段隐藏不变 |
| Q338 | [development-plan §5](development-plan.md) 风险表「编号实时重算性能」对策改单趟 O(n) + 软上限 ~2000、去「分批处理」；概率维持低、影响降为低 |
| 维持不立项 | 实时协作 / 离线编辑 / 非图附件预览 / 程序导出 Word = 远期（development-plan §6 / editor §18 原样）|
| 风险表 | [development-plan §5](development-plan.md)「全匿名被恶意刷写」对策更新、概率中→低（受控内网前提）|

---

## 五十五、copy 继承 risk/quality（Q339）

> 来源：grill「确认 procedure template 已取消（§44）」时发现 [§44.1](#441-q290-废弃-procedure-template改模板库--copy推翻-q209q210q218) Why（砍 template 的核心理由「copy 带 risk/quality 程序级元数据」）与 [§18.2](#182-复制范围q138) copy 复制清单（只列 `level_of_use`、漏 `risk_level`/`quality_level`）自相矛盾。判定 §18.2 为漏字段，补齐并一并收口连带项。
> 编号：续 §54（Q335–Q338）；本项 Q339。落地前 grep 全库确认上限为 Q338。

### 55.1 Q339 copy 继承 risk_level / quality_level（修订 §18.2 漏字段）

**决策**：`POST /procedures/{id}/copy` 复制清单（[§18.2](#182-复制范围q138)）补 `risk_level` / `quality_level`（Q52）——与 `level_of_use`（Q182）同列、**继承 source**。判定原 §18.2 只列 `level_of_use` 为**漏写**（非故意排除）。连带三项一并定案：

- **① 作用域 = 所有 copy**：本改动落在 copy 端点总清单，故[「复制为新程序」（Q179）](#2215-复制为新程序-ui-入口q179)普通复制路径同样继承 risk/quality——与既有 `level_of_use` 继承一致，仅补齐到对齐，**非新增特例**。
- **② 空白新建（新建弹窗）risk/quality 取 settings 默认**：弹窗只收 folder/name/level_of_use（必填）/description；risk/quality 不进弹窗、取 settings 默认（Q260），建后「程序详情」面板（Q162）改。（**§56/Q340 后修订**：原"从模板库复制随样板继承"路径随模板库废除而消失。）
- **③ 空白新建 vs「复制为新程序」= 两个独立操作**：空白新建 level_of_use 由弹窗必填、risk/quality 取 settings 默认；「复制为新程序」（Q179）则 level_of_use + risk/quality **全继承源**（①）。**§56/Q340 废模板库后不再有"新建弹窗内联 copy"路径**，故无此前的入口不对称。

**Why**：risk/quality（Q52）与 level_of_use（Q182）同为 Q162「程序详情」面板的程序级属性，同源 settings 默认、同可逐程序改，copy 没有理由继承前者却丢后者；且 §44.1 砍 template 的核心论证（copy 带 risk/quality 比 template body 强）依赖此继承成立，不补则论证落空。（原 ②③ 涉及"新建弹窗从模板库复制"，**模板库已被 §56/Q340 废除**，简化为：空白新建取 settings 默认、level_of_use 弹窗必填；「复制为新程序」全继承源；两者独立无交叉。）

**落地**：
- [§18.2](#182-复制范围q138)「继承 source」行：`level_of_use` → `level_of_use` / `risk_level` / `quality_level`（已改）
- [§33.5](#335-程序复制-fork-新字段补充182) fork 字段补充：同步补 risk/quality（已改）
- §41/3071 新建弹窗字段：恒空白新建、risk/quality 取 settings 默认（§56/Q340 废模板库后新建无 copy 路径；copy 继承见 ①/§18.2）（已改）
- §44.1 Why：加指回本节，确认 risk/quality 继承坐实（已改）
- api-specification.md `POST /procedures/{id}/copy` 后端动作字段清单：原仅 chapters/steps/attachments/custom_values，**补齐 level_of_use + risk_level/quality_level**（已改；该处此前连 level_of_use 也漏列）
- data-model.md：经核**不列举 copy 的程序级字段清单**（仅附件 §3.6 / rich_content §3.x 有复制说明），无需改

---

## 五十六、砍模板库，纯 copy 自现有程序（Q340）

> 来源：grill「确认 procedure template 已取消」延伸——用户质疑 §44 的「模板库 system 文件夹 + copy」其实是把刚砍掉的 template 功能"换名重长"出来：模板库样板**恒 DRAFT、永不生效**，与"copy 自现有程序"高度重叠，却凭空带来一整套复杂度（加样板入口缺失、删除/种子保护、生命周期屏蔽、草稿箱漏过滤 defect）。评估确认重叠，采纳"彻底砍模板库"。**推翻 §44 的 Q291 / Q292 / Q293-种子（仅 Q290 废 template 表/功能、Q293「copy 允许 DRAFT 源」保留）。**
> 编号：续 §55（Q339）；本项 Q340。落地前 grep 全库确认上限为 Q339。

### 56.1 Q340 废除模板库，模板需求由「复制现有程序」满足（推翻 Q291/Q292/Q293-种子）

**决策**：彻底废除"模板库"方案——
- **不建任何模板库文件夹**（取消 Q291 的「📋 模板库」`system=true` 文件夹 / `TPL` prefix）。
- **不 seed 任何样板程序**（取消 Q293 三套 general/testing/maintenance 种子；三套 PPA 骨架**直接删除**，不保留、不降级为参考程序）。
- **新建弹窗删除「从模板库复制」字段**（取消 Q292）；新建恒建空白程序（`POST /procedures`）。
- **模板需求 = 去任意现有程序 `⋮ → 复制为新程序`**（[§18](#十八程序复制q137q140) / Q179）。模板功能彻底不存在。
- **唯一保留的系统文件夹 = 「废止」**（§41 Q269）。
- **copy 允许 DRAFT 源保留**（Q293 该子项**不回退**）：copy 读源建新、源状态不阻塞；编辑器 ⋮ / 草稿箱行 / 历史只读视图均可作源。删去其"为模板库样板"的理由，能力本身保留（移除反需给这些入口加拦截，是增复杂度）。

**Why**：§44.1 砍 template 的论证就是「copy 已够」，模板库却又用 procedure 把 template 重新实现一遍，违背初衷。砍模板库后，上一轮 grill 暴露的 4 个洞（加样板无入口 / 删除与种子保护 / 样板生命周期屏蔽 / 草稿箱漏 `system` 过滤 defect）**全部消失**——草稿箱过滤 `status='DRAFT'` 不再漏，因为剩下唯一 `system` 文件夹「废止」装 DEPRECATED 非 DRAFT。代价仅"新装系统无 PPA 骨架可 copy"，用户接受删除三套骨架（PPA 结构改由 [pdf-rendering §15](pdf-rendering.md) 最佳实践参考清单 + Q181 手工对照承载）。

### 56.2 本节推翻/影响

| §44 决策 | 状态 |
|---|---|
| Q290 废弃 procedure template 表/功能 | **保留有效** |
| Q291 模板库 `system` 文件夹（TPL）| **推翻**（不建）|
| Q292 维护入口 + 新建「从模板库复制」| **推翻**（新建恒空白）|
| Q293 三套样板种子 | **推翻 / 删除**（不 seed）|
| Q293 copy 允许 DRAFT 源 | **保留**（去模板库理由，能力留）|
| 上轮 grill 待补的 4 个洞 | **全部失效**（无模板库即无洞）|

**落地**：
- feature-clarifications：§44 加 ⛔ 反转 banner；[§41/Q276](#4111-q276-新建程序入口--弹窗) 新建弹窗删「从模板库复制」→ 恒空白；[§50/Q321](#502-q321-全局入口归位--混合内容进侧栏--管理进-) 侧栏系统区删"模板库"；[§55/Q339](#五十五copy-继承-riskqualityq339) ②③ 去"从模板库复制"措辞（copy 继承 risk/quality 核心不变）（均已改）
- data-model：[§6 种子](data-model.md) 删模板库文件夹 + 三样板两行；§3.12 banner 改"模板库亦废"（已改）
- api-spec：`POST /procedures` template_id 注 + copy 端点去模板库措辞（DRAFT 源保留）（已改）
- editor-behavior：§20.6 新建弹窗删「从模板库复制」字段 + 删模板库维护入口段（已改）
- design-system：§3.1 侧栏系统区删"模板库"（已改）
- development-plan：Phase 1 seed.py 注去模板库（已改）
- **backend 代码**：`seed.py` 删 `TEMPLATE_FOLDER_NAME`/`TEMPLATE_PREFIX` + 模板库创建块（+ 去未用 `FolderSequence` 导入）；`test_seed.py` 删模板库断言 + `test_template_folder_has_sequence`、idempotent 系统文件夹 2→1 / 序列 1→0；`test_procedure_service.py` / `test_folder_service.py` "模板库" fixture 改「废止」（已改）

---

## 五十七、Word 解析器实现落地决策（Q341–Q348）

> 来源：Phase 6 后端开工前通读 §9/§19/§25/§27/§29/§53 + word-parser-solution.md + api-specification.md + data-model.md 后，发现若干**实现层开放项**（spec 未钉死的机制 / 表 / 兜底），按「决策不臆测、落库」原则在此一次性钉死，供解析器实现遵循。
> 编号：续 §56（Q340）；本批 Q341–Q348。落地前已 grep 全库确认上限为 Q340。
> 范围：仅落地机制，不改既有业务语义（§9/§19/§25/§27 的映射规则、置信度分级、正文起点链全部沿用）。

### 57.1 Q341 upload_token = 纯文件系统（无 DB 表）

**决策**：`POST /uploads` 的临时上传**不建 DB 表**。token = uuid4；docx 落 `{tmp_upload_dir}/{token}/source.docx`，解析抽图落 `{tmp_upload_dir}/{token}/media/`；token 元信息写**同目录 sidecar `meta.json`**（`{created_at, expires_at, filename}`，UTC ISO8601）。`expires_at = created_at + 24h`（§20/Q141）。临时上传清理任务（§53.2）每 1h **扫 `{tmp_upload_dir}/*/meta.json`**，`now > expires_at` 即整 token 目录递归删除；`meta.json` 缺失/损坏时回退用目录 mtime + 24h 判定。

**Why**：临时上传是短命的纯文件态，无跨请求关系数据需查询，建表是过度设计；sidecar + 目录扫描与 §53.2「扫 `expires_at` 过期 token」「先删文件」语义天然契合，且零迁移。data-model 本就未列 upload_token 表，印证此取向。

### 57.2 Q342 存储根目录与临时图服务端点

**决策**：
- 新增配置 `storage_dir`（默认 `var/storage`，env `STORAGE_DIR`）。永久 asset = `{storage_dir}/asset/{sha256[:2]}/{sha256}.{ext}`（data-model §3.10）；临时上传 `tmp_upload_dir` = `{storage_dir}/tmp/uploads`。
- 临时图在 review 阶段经新端点 **`GET /api/v1/uploads/{token}/media/{filename}`** 服务（`FileResponse` 流式；token 过期 / 路径穿越 → 404）；`/parse` 返回的 `assets[].url` 即指向该端点。
- 永久图经既有 **`GET /api/v1/procedures/{id}/assets/{asset_id}`** 服务（§25.2）。
- **URL 前缀统一为实际路由前缀 `/api/v1/...`**（api-specification 示例里的 `/api/procedures/...`/`/api/uploads/...` 省略 `v1` 仅为简写，以 `/api/v1` 实路由为准）。

**Why**：集中存储根便于部署挂卷与备份；临时图必须可被前端 step4 树审查预览，故需独立服务端点；URL 前缀对齐实路由避免 `<img src>` 失效。

### 57.3 Q343 正文首个标题之前的正文块 → 丢弃 + 警告（不建虚拟前言章节）

**决策**：`find_body_start`（§25.4）定位正文起点后，迭代正文块时维护「当前章节」。**正文起点之后、第一个 heading 之前**出现的非 heading 块（罕见）→ **丢弃**（遵 §9.2「Heading 之前的前言一律丢弃」），但**每丢弃一块计一条 `warnings[]`**（`stage='boundary'`）使其不静默。**推翻** word-parser-solution.md §5.5 的「虚拟 preamble 章节（level=0）」设计。

**Why**：§9.2（canon）明文 discard，与 word-parser-solution §5.5「不丢失、建虚拟章节」冲突；canon 优先。但「静默丢弃」违反 §25「不静默丢弃」原则，故以 warning 兜底——既不建违反 3 级模型的 level=0 节点，又保留可观测性。正常文档 `body_start` 即首个 heading，此路径几乎不触发。

### 57.4 Q344 heading_style_map DB 表 + 写入端点延后至 M4 前端；Phase 6 仅交付内置词典 + 注入缝

**决策**：两层词典（Q208）中——
- **第一层 `heading_synonyms.yaml`（内置默认）**：Phase 6 **完整交付**，随代码发布于 `app/parser/data/heading_synonyms.yaml`，含 `章节标题/章标题/一级标题`(L1) `节标题/小节标题/二级标题`(L2) `条标题/三级标题`(L3) 等。
- **第二层 `heading_style_map`（运行时组织级表，Q198/Q208）**：其 **DB 表 + 写入端点延后至 M4 前端**（写触发器 = 纠偏面板「记住此样式」勾选，纯前端交互，本期前端整段后补）。Phase 6 在分类器 `classify_heading_style` 留 **`style_overrides: dict[str, int]` 注入参数**（默认空 `{}`），未来落表后只需把 `style_map_service.list_active()` 结果传入即可，无需改解析核心。

**Why**：data-model / api-specification **均未定义** `heading_style_map` 的表结构或读写端点；其唯一写入路径是 M4 前端纠偏面板，本期不存在触发方。且 31 份语料验证（5 styled + 5 unstyled + 26 QMS，[word-parser-solution.md C.10/C.11](word-parser-solution.md)）的解析准确度**不依赖**该层（依赖的是 synonyms.yaml + 启发式）。故按「不建投机表、只留缝」最低风险落地，避免臆测表形态。M4 前端整段时一并补表 + `style_map_service` + `GET/POST /parse/style-map`，届时注入即生效。

### 57.5 Q345 /parse 30s 超时 = 线程执行器 + future 超时

**决策**：`/parse` 在 `ThreadPoolExecutor` 中跑 CPU 密集解析，`future.result(timeout=parse_timeout_seconds)`（配置 `parse_timeout_seconds` 默认 30，env `PARSE_TIMEOUT_SECONDS`）；超时 → `PARSE_TIMEOUT` 504。超时后**孤儿线程允许继续跑完**（Python 无法安全 kill 线程；受控内网下偶发超时可接受，token 24h 后随清理回收）。

**Why**：同步 FastAPI 端点对纯 CPU 的 python-docx/lxml 无法用 asyncio 取消；线程 + `future.result(timeout)` 是标准、可测（小超时 + monkeypatch 慢解析）的硬超时实现。孤儿线程在受控内网 + 幂等清理下无害。

### 57.6 Q346 上传双校验 = 扩展名 + OPC 嗅探

**决策**：`POST /uploads` 双校验：① 文件名 `.docx` 结尾（大小写不敏感）；② **OPC 嗅探**——字节是合法 zip（magic `PK\x03\x04`）且含 `word/document.xml` part。任一不满足 → `PARSE_FILE_INVALID` 400。大小 > `upload_max_size_mb`（50MB）→ `PARSE_FILE_TOO_LARGE` 413（流式累计字节，超限即断，防灌盘）。`.doc`（旧二进制）不支持 → `PARSE_FILE_INVALID`。

**Why**：仅查扩展名易被伪装；仅查 magic 无法区分普通 zip 与 docx。扩展名 + OPC 内容嗅探双管是「MIME 双校验」（kickoff）的可靠落地，且复用解析必读的 zip 结构，零额外依赖。

### 57.7 Q347 standard 模式模板校验规则集（最小可用集）

**决策**：DPMS 的 8 条规则（H001–T002）未逐条移植为 Smart SOP 规范；standard 模式落**最小可用规则集**，返回 `validation={passed, level, rules[], summary}`：
- **H001（error）**：至少识别出 1 个**样式标题**（styles.xml 反查命中）。0 个 → `level='error'` → `/parse` 拒绝 `PARSE_TEMPLATE_INVALID`（与 §9.3「standard error 即拒绝」一致）。
- **H002（warning）**：标题层级不跳级（无 L1 直接到 L3）。
- **C001（warning）**：原始正文范围 inline+anchor 图数 = 解析 image 块数。
- **C002（warning）**：原始正文范围 `<w:tbl>` 数 = 解析 table 块数。

每条 `{code, level, passed, message}`。`level` 取规则中最高级（error > warning > pass）。standard 模式**仅样式标题**（不启用启发式）；warning 不拒绝（前端 step3 二次确认）。

**Why**：canon 只定义了 standard「error 即拒绝」的行为契约，未列规则明细；DPMS 8 条多为内容完整性（已由 C001/C002 覆盖）+ 样式存在性（H001）。最小集覆盖「有无可用标题结构」这一 standard 模式核心判据，避免臆造一堆未经语料验证的规则。规则集可后续按真实模板扩充。

### 57.8 Q348 完整性对账（completeness）落地子集

**决策**：移植蓝本 C001–C006 落**子集**，结果进 `warnings[]`（smart）/ `validation.rules[]`（standard 的 C001/C002 见 Q347）：
- **C001 图片数对账** / **C002 表格数对账**：正文范围（`body_start` 之后）原始计数 vs 解析块数，差异 → warning。
- **C004 章节数 ≥ 1**：驱动 `PARSE_NO_HEADINGS`（standard 或 smart 启发式也零命中时，§25.7）。
- **C006 body_start 必须非 None**：`find_body_start` 兜底链保证总返回（cover_skip 兜底返 0），故恒满足；记 `metadata.bodyStartDetectedBy`。
- **C003（段落 95% 对账）/ C005（XML child order 同构）**：本期**不实现**（C005 需完整 source_ref xpath 记账，成本高且 Normalizer 顺序保真已由 lxml child-order 遍历结构性保证）。

**Why**：C001/C002/C004/C006 低成本高价值（直接支撑「内容可能遗漏」提示 + 空树判定）；C003/C005 成本高、收益边际（顺序保真已由实现方式保证），按 YAGNI 暂不做，留待真实漏提取反馈再补。

### 57.9 本节落地 / 影响

| 项 | 落地 |
|----|------|
| Q341 | upload 纯文件系统 + sidecar `meta.json`；清理任务扫目录；无迁移 |
| Q342 | `config.py` 加 `storage_dir`/`tmp_upload_dir`/`asset_dir` 派生；新增 `GET /api/v1/uploads/{token}/media/{filename}`；URL 前缀统一 `/api/v1` |
| Q343 | Normalizer/Structurer：首标题前正文块丢弃 + `warnings[]` 计数；word-parser-solution §5.5 虚拟前言**作废** |
| Q344 | `app/parser/data/heading_synonyms.yaml` 内置；`classify_heading_style(..., style_overrides={})` 注入缝；`heading_style_map` 表 + `GET/POST /parse/style-map` 延后 M4 |
| Q345 | `parse_service` 线程执行器 + `parse_timeout_seconds`（默认 30）→ `PARSE_TIMEOUT` 504 |
| Q346 | `upload_service` 扩展名 + OPC 嗅探双校验；流式大小限制 |
| Q347 | `validators/template_validator.py` 最小规则集（H001 error / H002·C001·C002 warning）|
| Q348 | `validators/completeness.py` C001/C002/C004/C006；C003/C005 暂不实现 |

### 57.10 Q349 H4-6 压 L3 时 title 保持纯文本（不注入 `<strong>`）

**决策**：解析遇 Heading 4-6 / 更深标题压缩为 L3 时，章节 `title` **保持纯文本**，**不注入 `<strong>`**。覆盖 §9.2 表「Heading 4/5/6 → title 加 `<strong>`」——该标记为 Q35「**可加**」（可选），与 [§19.6](#196-chaptertitle-textareaq149) 「chapter.title 为纯文本 textarea、不支持加粗/换行格式化」冲突；以 §19.6 为准。

**Why**：chapter.title 是纯文本字段，注入 `<strong>` 会在 textarea 里渲染为字面量 `<strong>…</strong>`，污染纯文本契约。H4-6 是边缘情形（31 份真实文档最深仅 N.N.N=3 级，Q190），层级压缩已由树构建保证（H4-6 capped 到 stack-level 3 成 L3 兄弟），无需再在 title 体现降级。Q35 的「压缩为 L3」规则保留，仅其「可加 `<strong>`」可选项不采纳。

### 57.11 Q350 解析/导入响应 snake_case + 落地补充（错误码 / 默认值 / 空树 precedence）

**决策**（实现期一并钉死的小项）：
- **响应 snake_case**：`/parse`、`/procedures/import`、`/uploads`、assets 直传响应字段统一 **snake_case**（对齐既有已落地 API ProcedureOut 等；api-specification.md `/parse` 示例的 camelCase 仅文档书写，实现以项目 snake_case 约定为准）。
- **新增错误码**：`IMAGE_CONVERT_FAILED` 400（编辑器直传 emf/wmf 转换失败，无法降级为 placeholder 故拒绝，区别于解析期降级）；`REVIEW_NOT_CLEARED` 422（import 前仍有 `mark_status='review'` 节点，§25.5 强制清 review）。
- **空树 precedence**：standard 模式零样式标题 → 走 `PARSE_TEMPLATE_INVALID`（H001 error，detail 携 `validation` 报告，§9.3）；smart 模式启发式也零命中（`total_chapters==0`）→ 走 `PARSE_NO_HEADINGS`。二者不重叠（standard 的零标题已被模板 error 拦截在前）。
- **import 默认 `level_of_use`**：导入向导 step5 仅收 `name` + `folder_id`（dev-plan），而 `level_of_use` 为 Q182 必填——import 落库默认取 `"reference"`，建后由「程序详情」面板（Q162）改。

**Why**：snake_case 保持全 API 一致（M3 前端已按 snake_case 消费），避免 parse 单独 camelCase 制造混用；两个新错误码补齐既有清单未覆盖的真实失败路径；空树 precedence 消解 §9.3 与 §25.7 的表面重叠；import 默认 level_of_use 让向导表单最简（与「建后详情面板可改」一致），不臆造向导新字段。

### 57.12 本节补充落地 / 影响

| 项 | 落地 |
|----|------|
| Q349 | `structurer` 压级保留纯文本 title；覆盖 §9.2 `<strong>` 可选标记（§19.6 优先）|
| Q350 | `schemas/parse.py` 全 snake_case；`IMAGE_CONVERT_FAILED`/`REVIEW_NOT_CLEARED` 入错误码；`import_service` 默认 `level_of_use="reference"`；空树 precedence 落 `parse_service` |

## 五十八、M4 前端整段落地决策（Q351–Q358）

> 后端 Phase 6/7 已全绿。本节钉死 **M4 前端整段**（五步导入向导 + 版本管理 UI + 编辑器图片菜单接通）的实现层决策。前端类型/契约一律对齐后端 snake_case（Q350），不引入 camelCase 映射层。

### 58.1 Q351 导入向导状态机 + 上传/解析触发时机

**决策**：五步线性向导（Element Plus `el-steps`，已完成步可点回退），状态机：
- **step1 上传**：选文件即客户端校验（`.docx` 扩展名 + 三档体积预警 Q352）；点「下一步」时 `POST /uploads` 落临时区拿 `upload_token`（纯文件系统，§5.3）。重选文件作废旧 token（前端丢弃引用，旧 token 由 scheduler 24h 清）。
- **step2 模式**：`standard` / `smart`（默认 `smart`）；`GET /parse/methods` 拉取 key/label/description 渲染。
- **step3 校验报告 / 解析概览**：进入即 `POST /parse {upload_token, parse_mode}`（解析不落库，两步式 §9.1）。standard 走 `validation` 模板规则（warning-only 二次确认，error 阻断回 step1/2）；smart 走 `metadata + warnings + review_required` 预告。spinner + 进度文字 + 30s 超时提示（Q352）。
- **step4 树审查**：中量编辑（title / skip_numbering / 递归删除 / 上下移）+ review 黄标 + 「重置为初始解析」。
- **step5 表单**：`name` 默认上传文件名（去 `.docx`）+ `folder_id`（仅非系统叶子）；提交 `POST /procedures/import` → 跳 `/procedures/{new_id}`。

**Why**：上传与解析分两次网络往返对齐后端两步式（parse 不落库），token 在 step1 末尾拿可让 step2/3 随时重解析（换模式不必重传）；解析放 step3 入口触发，使 step1/2 纯本地零延迟。

### 58.2 Q352 三档体积预警阈值 + 解析超时提示

**决策**：上传体积三档（对齐后端 `upload_max_size_mb=50`）：`<20MB` 正常；`20–40MB` info 提示「文件较大」；`40–50MB` warning「文件很大，解析可能较慢」；`>50MB` **前端直接阻断**（不发请求，提示对齐后端 `PARSE_FILE_TOO_LARGE`）。解析 spinner 显示进度文字；axios 30s 超时（`ECONNABORTED`）或后端 30s 线程超时错误码 → 专门提示「文档过大或过于复杂，解析超时（30s），请拆分后重试」。

**Why**：三档让用户在传前预期解析耗时；前端阻断 >50MB 省一次必失败的大上传；超时双路（客户端 abort + 后端 Q345）统一话术。

### 58.3 Q353 向导 sessionStorage 持久化模型

**决策**：key=`procedure_import_wizard_v1`，单一全局键（向导无 procedure id）。持久化 `{created_at, step, upload_token, filename, parse_mode, parse_result(含已编辑树/assets/warnings/validation/detected_patterns), form}`——**不持久化 `File` 对象**（不可序列化；token 已足够断点续解析）。挂载时若存在且 `created_at` 在 24h 内 → 询问恢复；超 24h → 静默清除。`beforeRouteLeave`：向导已推进（已上传 / 已编辑树）时确认拦截。提交成功或显式重置时清键。

**Why**：File 不可入 sessionStorage，但 upload_token 24h 有效，恢复后可直接从 step3+ 续；24h 与临时上传 TTL（Q141）一致，避免恢复到已被 scheduler 清掉的 token。

### 58.4 Q354 review 清除时机 + UI

**决策**：smart 解析出的 `mark_status='review'` 节点在 step4 以**黄色高亮** + 顶部横幅「N 个低置信度节点需确认，继续即视为接受」。到达 step5 并提交 = 用户确认 → **构建导入载荷时统一 `review→unmarked`**（`clearReview`），对齐后端 `REVIEW_NOT_CLEARED`（422）守卫与集成测试 `_clear_review`。不做逐节点勾选确认（保持向导轻量；用户可在 step4 删除/编辑不认可的节点）。

**Why**：后端强制 import 前清 review；「走到 step5 提交」本身即审查完成的语义信号，逐节点勾选属过度设计；横幅 + 黄标已足够告知。

### 58.5 Q355 编辑器图片菜单接通（M3 遗留补全）

**决策**：`RichTextEditor.vue` 接入 WangEditor `MENU_CONF.uploadImage.customUpload` → `POST /procedures/{id}/assets`（multipart，sha256 去重即时入库，Q214），插入返回的永久 asset URL。**仅在已有 `procedure_id` 的编辑器内可用**（RichTextEditor 增 `procedureId` prop；缺失时仍隐藏图片菜单，保持 M3 行为）。**向导内不提供图片上传**——向导树审查阶段图片沿用临时 token URL 预览（`GET /uploads/{token}/media/...`），import 时后端按 sha256 提升为永久 asset。单图 >10MB 由后端 `IMAGE_TOO_LARGE`（413）拦截，前端 toast。

**Why**：M3 显式把图片菜单延到 Phase 6，后端直传端点现已就绪，本批补全闭环；绑定 procedureId 因 asset 必挂在已存在程序上（向导尚无 id，故向导不开图片上传，靠 import 提升）。

### 58.6 Q356 版本管理 UI 落点

**决策**：
- **ProcedureDetailView**：头部「本次版本更新说明」textarea（DRAFT 当前版可改、随快速编辑保存，其余只读展示）；版本动作按钮区（升级 / 回退 / 废弃 / 恢复 / 复制）按状态条件显示；**版本列表面板**（`GET /procedure-groups/{group_id}/versions`，可展开 notes 全文，每行据状态给动作）替换原 version_change_log 卡片为更完整的版本族视图（保留本版变更日志时间线）。
- **EditorTopBar**：占位接通——「升级版本」（current+PUBLISHED）、「丢弃此 DRAFT」（DRAFT v>1 当前版）、「复制为新程序」（任意）三个动作发 emit，由 `ProcedureEditorView` 调 API。
- 版本动作 reason 必填者统一走 `VersionActionDialog`（标题 + reason textarea + 可选额外字段如 restore 的 target_folder_id）。版本号 / 目标版本由后端定，前端只传 `reason` / `target_version`。

**Why**：详情页是版本族的天然落点（已有头部动作 + 变更日志）；编辑器顶栏占位本就是 Phase 7 预留；统一 reason 弹框避免 5 个近乎重复的弹框组件。

### 58.7 Q357 版本动作前端契约

**决策**：`upgrade-version` / `rollback` / `deprecate` / `restore` / `copy` 五个端点**均不带 If-Match**（后端路由不读该头，仅 PUT 整批保存与 transition 走乐观锁）。`copy` 返 201。**丢弃 DRAFT** = `DELETE /procedures/{id}`（reason 必填）：DRAFT 当前版 v>1 返 200 + `DiscardDraftResult{deleted_id,new_current_id,new_current_version}`，前端据此跳转新当前版详情；否则 204（普通软删）跳回程序库。前端 `deleteProcedure` 返回类型改为 `DiscardDraftResult | null`。

**Why**：精确对齐后端各端点的鉴权/返回形态，避免前端误加 If-Match 触发 412；丢弃 DRAFT 的 200/204 分支决定跳转目标。

### 58.8 Q358 restore 两步流程

**决策**：恢复走两步——先 `GET /procedures/{id}/restore-preview` 得 `{folder_exists, deprecated_from_folder_id, folder_full_path, version_count}`；`folder_exists=false` 时 `VersionActionDialog` 追加必填「目标文件夹」（叶子选择），对齐后端 `RESTORE_FOLDER_MISSING`；reason 始终必填。确认后 `POST /procedures/{id}/restore {reason, target_folder_id?}`。

**Why**：原废止来源文件夹可能已删，预检查让 UI 仅在必要时索取 target_folder_id，避免无谓表单字段。

### 58.9 本节落地 / 影响

| 项 | 落地 |
|----|------|
| Q351 | `views/procedures/ImportWizardView.vue` + `components/import/*` + 路由 `/procedures/import` + 库视图「导入 Word」入口 |
| Q352 | `UploadStep.vue` 三档预警；`ImportWizardView` 解析 spinner + 超时话术 |
| Q353 | `composables/useImportWizardPersistence.ts`（key=`procedure_import_wizard_v1`，24h）+ `beforeRouteLeave` |
| Q354 | `utils/importTree.ts` `clearReview`/`toImportNodes`；`TreeReviewStep.vue` 黄标 + 横幅 |
| Q355 | `RichTextEditor.vue` 增 `procedureId` prop + `customUpload`；`api/parse.ts` `uploadAsset` |
| Q356 | `ProcedureDetailView.vue` 改造 + `components/version/VersionListPanel.vue` + `VersionActionDialog.vue`；`EditorTopBar.vue` 接通 emit |
| Q357 | `api/procedures.ts` 版本动作函数（无 If-Match）；`deleteProcedure` 返 `DiscardDraftResult \| null` |
| Q358 | `api/procedures.ts` `restorePreview`/`restoreGroup`；`VersionActionDialog` 条件 target_folder_id |

---

## 五十九、Phase 8 PDF 生成实现落地决策（Q359–Q366）

> 来源：Phase 8 开工锁定 PDF 渲染架构。pdf-rendering.md（主规范）+ §11/§23.4/§34 已定**渲染规格与对外契约**；本节钉死规范未覆盖的**实现层**决策（字体落地形态、layout JSON 字段、引擎遍数、超时实现、端点访问语义、富文本解析、包结构），消除「照过时 dev-plan 清单」风险。
> 编号：续 §58（Q351–Q358）；本批 Q359–Q364 为开工锁定，Q365–Q366 为实现后子代理评审收尾追加。grill 方式：开工通读 11 份权威文档 + 勘察后端现状（services/pdf 为空壳、无 dpms 源、字体目录空）后逐项锁定。

### 59.1 Q359 中文字体落地 = 开源 Noto CJK（默认母版内嵌）+ CID 内置回退

**决策**：§8/Q55 的「SimSun/SimHei/Times New Roman」按**视觉等价 + 授权干净**替换为开源 Noto CJK（思源同源，OFL 可商用可再分发）：

| 逻辑字体 | 主字体（assets/fonts 内置）| 用途 |
|---------|--------------------------|------|
| 宋体（正文）| `NotoSerifSC`（衬线，默认 Regular 母版）| 中英文正文、content 节点、表格、附件清单 |
| 黑体（标题/加粗）| `NotoSansSC`（无衬线）| 章节标题、警示标题、加粗中文（§8「加粗中文=黑体」）|
| 等宽（代码）| reportlab 内置 `Courier` | 代码块（无需内嵌二进制）|

- **reportlab 只接受 TrueType(glyf) 静态字体**：Noto/思源官方 **CJK** 包是 OTF(CFF) 无法内嵌；改用 google/fonts 的 **glyf 可变 Noto Serif/Sans SC**，reportlab 内嵌其**默认母版（wght=400 Regular）**（reportlab 不读 gvar 增量，等价嵌入 Regular 字重，渲染正确、可子集化）。英文/数字复用 Noto（含完整 Latin），**不再单独内嵌 Times New Roman**。
- **加粗策略**：`registerFontFamily(宋体, bold=黑体)` —— 正文 `<b>`/`<strong>` 自动切黑体（天然满足「加粗中文=黑体」）；标题类样式直接指定黑体。Serif(正文) vs Sans(标题) 的字形差天然区分层级，即便同为 Regular 字重视觉仍清晰。
- **优雅回退（安全网）**：`pdf/fonts.py` 优先从 `settings.pdf_font_dir` 加载 Noto TTF；**任一缺失则该逻辑字体回退 reportlab 内置 Adobe CJK CID 字体 `STSong-Light`**（零二进制、离线即用），保证字体未就位时 PDF 生成**绝不崩**、测试离线确定性。注册全程幂等。

**Why**：用户选「开源思源/Noto CJK（推荐）」（授权风险见开工说明）。微软 SimSun/SimHei 再分发受 EULA 限制（弃）；reportlab 内置 CID 虽零依赖但偏离「内嵌 TTF」且无简体黑体，故仅作回退。可变字体默认母版内嵌是「拿到 glyf 静态字重」的零额外工具（无需 fonttools instancer）的最简路径。

**落地**：`backend/app/assets/fonts/NotoSerifSC.ttf` + `NotoSansSC.ttf`（OFL，附 `OFL.txt`）；`pdf/fonts.py` `register_fonts()` + `song()/song_bold()/hei()/hei_bold()/mono()` 访问器 + 家族注册 + CID 回退。修订 pdf-rendering.md §8 字体族选择（视觉等价替换说明）。

### 59.2 Q360 `GET /pdf-layout` 响应 JSON 契约

**决策**：§34.2/Q235 只定「返回总页数 + 元素/章节/step→页号 + TOC/附件页码」未定字段名；钉死如下 schema（前端预览层据此逐页复刻、与下载版对齐）：

```jsonc
{
  "total_pages": 13,                       // T（含封面，§6.1/Q184）
  "sections": {                            // 四区段物理页边界（start_page 1-based 物理页）
    "cover":    {"start_page": 1, "page_count": 1},
    "toc":      {"start_page": 2, "page_count": 2},
    "revision": {"start_page": 4, "page_count": 1},
    "content":  {"start_page": 5, "page_count": 9}
  },
  "page_labels": ["", "i", "ii", "iii", "1", "2", ...],   // 每物理页页眉右列第3行 P（封面="" 无页眉；前置罗马；正文阿拉伯）；长度 = total_pages
  "toc_entries": [                         // 仅 chapter 且 skip_numbering=false（Q46）
    {"chapter_id": "...", "code": "1.0", "title": "目的", "level": 1,
     "physical_page": 5, "display_page": "1"}              // display_page = 正文阿拉伯（Q46 TOC 列正文页码）
  ],
  "chapters":   {"<chapter_id>": 5, ...},  // chapter_id → 物理页
  "steps":      {"<step_id>": 6, ...},     // step_id → 物理页
  "attachments_page": 12,                  // 附件区段起始物理页；无附件 = null
  "debug": null                            // ?debug=1 时填 dry-run 诊断信息（Q362）
}
```

- 元素→页号一律用**物理页**（1-based），前端按物理页切「纸张」容器；`page_labels[physical-1]` 给该页应印的 P 文案。`toc_entries.display_page` 额外给 TOC 列应印的正文阿拉伯页码。
- **下载与 layout 同引擎产出**，逐页严格一致（Q361）。

**Why**：物理页是前端分页容器的天然主键；page_labels 把「PPA 罗马/阿拉伯混合页码」一次算好交前端、避免前端重算口径分歧（§34.2 用户选「后端分页接口」的初衷）。

**落地**：`pdf/layout.py` 组装；`schemas/pdf.py` `PdfLayoutOut`；路由 `GET /procedures/{id}/pdf-layout`。

### 59.3 Q361 渲染引擎 = 迭代收敛多遍构建（落实「两遍渲染」）

**决策**：§11.1「两遍渲染」落实为**迭代收敛**：TOC 列正文页码 ↔ 正文分页存在互相影响（TOC 数字位数变化可能令长标题换行、改变 TOC 页数、连带推移正文页码），故需多遍直至「全量页归属」稳定（通常 2–3 遍，上限 5 遍，超限取末遍并打 warning 日志）。

- **pdf-download 与 pdf-layout 共用同一引擎** `render(data) -> RenderResult(pdf_bytes, layout)`：download 返 `pdf_bytes`、layout 返 `layout`，二者页码天然一致。
- 第一遍 dry-run 的诊断（toc/页码映射）即 `?debug=1`（Q362）返回内容；收敛后末遍即正式 PDF 字节。
- 页眉 P/T 与 TOC 数字只改**文本内容不改 flowable 高度**，故收敛快、分页稳定。

**Why**：字面「两遍」不足以处理 TOC↔正文互依（鸡生蛋）；reportlab 标准 `multiBuild` 即同理。单引擎双产出是「pdf-layout 必须与 pdf-download 页码一致」（开工说明）的唯一可靠实现。

**落地**：`pdf/document.py`（`ProcedureDocTemplate(BaseDocTemplate)` + 三 PageTemplate cover/front/content + onPage 页眉页码 + 水印；`afterFlowable` 收集 element→page）；`pdf/engine.py`（迭代循环 + 收敛判定 + 产出 RenderResult）。

### 59.4 Q362 60s 硬超时 + 异常归一 + 端点访问语义

**决策**：
- **超时**：`render` 跑在 `ThreadPoolExecutor`，`future.result(timeout=PDF_TIMEOUT_SECONDS=60)`；`TimeoutError` → 504 `PDF_TIMEOUT`（§11.2 字面「单次 ReportLab 调用超 60s」）。
- **异常归一**：引擎内任何 ReportLab/渲染异常 → 500 `PDF_GENERATION_FAILED`（原始异常打 `app.services.pdf` logger，§14）。
- **404**：程序不存在 → 404 `PROCEDURE_NOT_FOUND`（**注意**：PDF 端点用此码，区别于既有 `procedure_service` 的通用 `NOT_FOUND`，以符合 pdf-rendering §13；PDF 取数自有 loader 抛 `PROCEDURE_NOT_FOUND`）。
- **访问语义**：`pdf-layout`/`pdf-download` 对**任意 status（DRAFT/PUBLISHED/ARCHIVED）与 deprecated group 均可访问**（与 §13.4「GET/PDF 不受限」一致，呼应水印 Q225 区分草稿/作废）；**不写审计**（§15.2「不记 GET/PDF」）；限流在 nginx（§11.3，后端不内置）。`?debug=1` 仅 `pdf-download` 支持（返 layout JSON 而非 PDF）。

**Why**：线程池 future.result 是同步 CPU 任务硬超时的标准手段（无法 kill 线程，但请求按时返 504，符合「硬超时」语义）。PROCEDURE_NOT_FOUND 对齐 PDF 规范专属错误码表。访问不设状态门禁正是水印（草稿/作废标识）存在的前提。

**落地**：`pdf/engine.py` 超时包装；`pdf/errors.py`（`pdf_timeout()`/`pdf_failed()`，复用 `app.errors.app_error` 补 504/500）；`routers/procedures.py` 两端点。

### 59.5 Q363 富文本 HTML 解析 = stdlib `html.parser`（渲染层零第三方依赖）

**决策**：content 节点 `rich_content` 与 step 三警示富文本的 HTML → reportlab flowable，用 **stdlib `html.parser`** 解析（渲染层不引 bs4/lxml-html）：

- **块级识别**：`<div class="note-block|caution-block|warning-block|hold-point|signature-bar">`（对齐编辑器 `SPECIAL_BLOCKS` 协议，§7）、`<table>`、独立成段 `<img>`、`<p>/<ul>/<ol>/<li>/<h*>`。
- **内联**：`<b>/<strong>/<i>/<em>/<u>/<br>/<font>/<a>` → reportlab `<para>` 内联标记（其余未知标签**降级为纯文本**，不报错）。
- **图片**：`<img src=".../assets/{asset_id}">` → 经 `asset_service.extract_asset_ids` 取 id + `get_asset(db,id)` 取字节 → PIL 校验 → 等比缩放页宽、独占居中（§9.1）；不支持格式/取不到 → 占位文本 `[不支持的图片格式: ...]` / `[图片缺失]`。
- **嵌套表格**（Q56）→ 内层降级缩进列表 + warning 日志（§9.2）。
- **警示逆序**（§7.0）→ warning 日志（不阻塞）。

**Why**：rich_content 由 WangEditor 产出、结构规整，stdlib html.parser 足矣且零依赖（解析器包虽用 lxml，渲染层不必耦合）。未知标签降级保证「极长/异形 rich_content」（§12.3）不致渲染崩溃。

**落地**：`pdf/html_render.py`（解析器 → flowable 列表）；`pdf/flowables.py`（AlertBox/HoldPoint/SignatureBar/Watermark/ContinuedStep 自定义 flowable）。

### 59.6 Q364 `pdf/` 子包模块划分 + 数据快照解耦 ORM

**决策**：`backend/app/services/pdf/` 模块划分（SQLAlchemy 取数与渲染解耦——渲染层只吃 `RenderData` 快照、不碰 Session）：

| 模块 | 职责 |
|------|------|
| `fonts.py` | 字体注册 + 逻辑名访问器 + CID 回退（Q359）|
| `constants.py` | 页面尺寸/边距/行距、风险等级 RGB、ANSI Z535 三色、水印参数、change_type/kind 中文映射 |
| `context.py` | `RenderData` dataclass + `load_render_data(db, proc_id)`：取 procedure 元 + 章节树 + 步骤 + 附件 + active 自定义字段 + folder.full_path；404=`PROCEDURE_NOT_FOUND` |
| `styles.py` | ParagraphStyle 工厂（缓存复用，§11.4 性能）|
| `html_render.py` | rich_content/警示 HTML → flowable（Q363）|
| `flowables.py` | 自定义 flowable |
| `sections.py` | 封面/TOC/修订/正文/附件区段 flowable 构建（编号 render-only `.0`，Q305）|
| `document.py` | `ProcedureDocTemplate` + PageTemplate + onPage 页眉页码/水印 + afterFlowable 收页号 |
| `layout.py` | RenderResult → `PdfLayoutOut`（Q360）|
| `engine.py` | 迭代收敛 + 超时包装 + 异常归一（Q361/Q362）|
| `errors.py` | PDF 错误助手（Q362）|
| `__init__.py` | 导出 `render_pdf` / `compute_layout` |

- **空程序/仅根 step**（§12）：TOC「（无章节）」、正文「（程序无内容）」占位。
- **附件虚拟章节**（§6.6.2）：用户无「附件/Attachments」L1 chapter 时自动追加虚拟章节（编号 = 末正文 L1 序号+1，render `{N}.0`）；不进 TOC、不入库。

**Why**：渲染层吃快照、不持有 Session → 可在线程池跑超时（Q362）不踩 SQLAlchemy 线程边界；模块单一职责便于子代理评审与单测。无 dpms 源可移植（开工说明），按本划分从零建。

**落地**：上表 11 模块 + `schemas/pdf.py` + 路由两端点 + 字体资产 + 测试（layout 为主测面 + 纯函数单测 + bytes sanity）。

### 59.7 本节落地/影响

| 项 | 落地 |
|----|------|
| Q359 | `assets/fonts/NotoSerifSC.ttf`+`NotoSansSC.ttf`+`OFL.txt`；`pdf/fonts.py`；pdf-rendering.md §8 字体族说明 |
| Q360 | `schemas/pdf.py` `PdfLayoutOut`；`pdf/layout.py`；api-specification.md §5.2 layout 响应示例 |
| Q361 | `pdf/engine.py`+`pdf/document.py`（迭代收敛单引擎双产出）|
| Q362 | `pdf/engine.py`（超时/异常）+`pdf/errors.py`+`pdf/context.py`（PROCEDURE_NOT_FOUND）|
| Q363 | `pdf/html_render.py`+`pdf/flowables.py` |
| Q364 | `pdf/` 11 模块 + 路由两端点 |

### 59.8 实现后子代理评审收尾决策（Q365–Q366）

> 实现全绿后做独立子代理评审，发现 1 个必修（字体）+ 4 个中等（前端预览与下载不一致）+ 若干 LOW。字体（H1）直接补齐，不另立决策。以下两项为需钉死的实现策略。

#### Q365 步骤跨页保护 = 仅标题 `keepWithNext` 防孤行，不做整步 `KeepTogether`（推迟）

- **决策**：步骤渲染只在标题 Paragraph 上设 `keepWithNext=1`（章节标题同），保证标题不会孤悬页底；**不**把「标题+警示+正文+占位符+确认行」整体 `KeepTogether`。整步保护推迟为后续增强。
- **Why**：
  1. `KeepTogether` 会把整组移至下一页，对**高于一页**的步骤（长正文/大图/多警示）反而强制溢出、布局更差；
  2. 本引擎页码追踪靠 `afterFlowable` 对带 `_pdf_key` 的标题回调收页号（Q361 迭代收敛的输入），`KeepTogether` 包裹后子 flowable 的回调时机不确定，**有打断页码追踪 → layout/bytes 不一致**的风险，与「单引擎双产出一致」（Q361）冲突；
  3. `keepWithNext` 已消除最常见的「标题落在页底、内容翻页」孤行问题，性价比最高。
- **落地**：`sections.py:_keyed()` 设 `keepWithNext=1`（现状保留）。整步 `KeepTogether` 不实现；如未来要做，须先验证其不破坏 `afterFlowable` 页码追踪，并对超页步骤定义降级（允许从标题处断页）。

#### Q366 前端预览层与下载版一致性收尾（preview ≈ download）

- **决策**：前端预览（`PdfPreviewDialog.vue` + `pdfModel.ts`）须与 ReportLab 下载版**同口径**呈现以下五点：
  1. **封面自定义字段**：仅 `show_on_cover=true` 且有值的字段上封面；`select/multi_select/checkbox` 解析为 option `label`（与后端 `context._resolve_field_value` 一致）。为此 `FieldOut` 增 `show_on_cover` 字段。
  2. **附件清单区段**：渲染「序号/文件名/大小/类型/上传日期/描述」表；用户自建「附件/Attachments」L1 章节时不再重复标题（标题已在正文章节渲染），否则显示虚拟章节标题 `{N}.0 附件 / Attachments`（与后端 `_virtual_attachment_chapter` 同编号规则）；页码取后端 `layout.attachments_page`。
  3. **步骤附件标注**：统一走 `attachmentMarkText(mark)` 输出「▶ 附件: 名称（中文类型）— 备注」，不再裸显 `kind`。
  4. **水印透明度**：`DRAFT` alpha 0.30、`ARCHIVED` 0.35，与后端 `constants.WATERMARK` 对齐。
  5. **修订说明换行**：后端 `_revision_desc` 内文换行转 `<br/>`（`_esc_multiline`）；前端用 `white-space: pre-wrap` 呈现，二者均保留多行。
- **Why**：预览是「所见即所得」的下载前确认面（Q235 页码一律取后端 layout）。封面字段不过滤/不解析、附件区段缺失、标注裸显英文，都会让用户在预览里看到与下载 PDF 不同的内容，破坏信任。
- **落地**：`schemas/procedure.py:FieldOut`（+`show_on_cover`）；`types/procedure.ts:ProcedureFieldView`；`pdfModel.ts`（`resolveFieldValue`/`coverFieldRows`/`attachmentChapterTitle`/model 增 `coverFields`+`attachmentChapterTitle`）；`PdfPreviewDialog.vue`（封面字段、附件区段、`attachmentMarkText`、水印 alpha）；`sections.py:_esc_multiline`。

---

## 六十、Phase 9 实现层收口（Q367–Q371）

> 来源：Phase 9（附件 + 自定义字段 + 设置 + 审计 + 收尾）开工前通读 dev-plan §3 Phase 9 / §53 / 风险表 + feature-clarifications §14（附件传递）/§15（审计颗粒度）/§38（自定义字段）/§39（设置）/§53（调度清理）/§54（遗留收口）+ api-specification §5.5/§5.7/§5.8/§5.9 + data-model §3.6/§3.7/§3.8/§3.9 后，发现 4 个 spec 未钉死、臆测有成本的实现层分叉（经 grill 定案）+ 1 批自决实现细节。落库供实现遵循。
> 编号：续 §59（Q359–Q366）；本批 Q367–Q371。落地前已 grep 全库确认上限为 Q366。
> 现状勘察结论（不重造）：① fields/settings/attachment/审计表 + `tb_procedure.procedure_group_id` 列已全在初始迁移建好——**Phase 9 无需新迁移**（dev-plan「procedure 表加 procedure_group_id 列」已由 Phase 1/7 满足）；② scheduler 进程 + `cleanup_uploads`/`asset_gc` 两任务已在 Phase 6 建好——Phase 9 仅**新增第 3 个附件清理任务并挂载**（非从零搭 3 个）；③ `audit_service.log_*_action` 写入已被 8 个 service 接入（chapter/step 等 `target_id`=对象自身 id、`procedure_group_id`=所属族），审计读接口可查到真实数据；④ `auto_archive_days` 定时任务 Q337 定 0.1.0 不实现。

### 60.1 Q367 自定义字段值校验 = 手写子集校验器（不引 jsonschema 库）

**决策**：`custom_values` 对字段 `validation_rules`（存储恒为标准 JSON Schema，Q-C6）的校验，用**手写子集校验器**，**不引入 `jsonschema` 运行时依赖**。校验器只覆盖 Q253「表单化常用项」对应的 JSON Schema 关键字：`type`、`required`（字段级 `required` 标志）、`minimum`/`maximum`、`minLength`/`maxLength`、`pattern`，叠加按 `field_type` 的形态校验（`number`→数值、`date`→ISO 日期串 `YYYY-MM-DD`、`select`→单值 ∈ 选项值、`multi_select`/`checkbox`→列表 ⊆ 选项值、`text`/`textarea`→字符串）。选项校验对 active **与 archived** 选项值均放行（旧值保留只读，Q255），仅彻底未知值才拒。命中违规返 `CUSTOM_FIELD_INVALID`（422，`field` 指向出错的字段 key）。字段配置变更**不写审计**（Q122 未列字段动作；settings 才审计，§5.8/Q233）；新增错误码 `FIELD_KEY_DUPLICATE`（409，创建时 key 撞已存在记录）。

**Why**：Q253 已把字段校验框死为「表单化常用项」，对应的 JSON Schema 是可控子集；手写校验器零新依赖、`mypy --strict` 友好、与 Q253 范围严格对齐。代价（用户手贴超出该子集的 schema 关键字会被忽略）在「校验规则由表单生成」前提下不会发生。

**落地**：`field_service.compile_form_to_schema()`（表单项→JSON Schema，保存字段时调用，承 Q253）+ `field_service.validate_values()`（custom_values × active fields 校验，供 procedure 创建/保存/发布调用）；`errors` 加 `CUSTOM_FIELD_INVALID`。

### 60.2 Q368 required 校验时机 = 新建 + DRAFT 保存 + 发布；未知/归档键容忍

**决策**：`required`/`validation_rules` 校验在 **3 个时机**强制——① 新建程序、② DRAFT 保存（PUT /procedures/{id}）、③ **发布（transition → PUBLISHED）**（扩展 Q256，发布前补一道 active+required 闸门，防止「正式发布」一个缺必填项的程序）。校验**仅针对当前 active 字段**；`custom_values` 中**未定义键 / 已归档字段对应的键一律容忍保留**（不报错、程序里只读展示，承 Q255）。已 PUBLISHED 历史程序不追溯（承 Q256）。

**Why**：发布=对外正式生效，缺必填元数据上线风险高；新建/保存的两道闸门挡不住「先建空草稿、改字段为 required 后直接发布」的路径，发布闸门补齐。容忍未知/归档键是 Q255「归档值保留只读」的直接要求，不能因校验误删历史值。

**落地**：`field_service.validate_values()` 接入 `procedure_service.create` / `procedure_service.update` / 状态机 publish 分支（DRAFT→PUBLISHED）。

### 60.3 Q369 PUT /settings 并发控制 = `updated_at` 弱 ETag（零迁移）

**决策**：settings 单例**不加 `revision` 列**（维持 Phase 9 零迁移）；`PUT /settings` 的 If-Match（api-spec §5.8「必须带」）以 `updated_at` 的 ISO-8601 串作弱 ETag——`GET /settings` 响应回带 `updated_at`，PUT 须带 `If-Match: <updated_at>`，与 DB 当前 `updated_at` 不一致返 **412 `VERSION_CONFLICT`**（复用既有 `precondition_failed`）。改动写 `tb_procedure_audit_log`（`target_id`=settings.id、`procedure_group_id`=NULL、`action='settings_update'` + 字段级 diff + IP/UA，承 §5.8）。

**Why**：settings 单例、低频、匿名，`updated_at` 弱 ETag 足以挡「读后被他人改再覆盖」的丢写，且不破坏「Phase 9 无新迁移」基调；加 revision 列收益边际、引入迁移成本不值；放宽不强制则违背 api-spec 字面契约。

**落地**：`settings_service.get_singleton()` / `update()`（校验 If-Match → diff → 审计）；`/settings` 路由（GET + `/current` alias + PUT 注入 `If-Match` header + RequestMeta）。

### 60.4 Q370 审计读接口 = JSON 查询 + `export=csv` 流式导出（本期实现）

**决策**：`GET /audit-logs/folders`、`GET /audit-logs/procedures` 本期实现**全部过滤**（`target_id` / `action` 逗号分隔多选 / `date_from` / `date_to` / `ip_address` / `procedure_group_id`〔仅 procedures〕 / `page` / `page_size`，承 Q126）**+ `export=csv`**（承 Q288：带相同过滤、`StreamingResponse` 流式、**忽略分页不截断**、UTF-8 BOM 便于 Excel）。只读、匿名可看、无写接口（承 Q125/Q289）。`target_id` 语义：可为 procedure 版本 id / chapter id / step id / attachment id / folder id（按写入侧 `target_id`=对象自身 id）；`procedure_group_id` 跨版本+跨章节/步骤/附件聚合整族历史。

**Why**：两端点的过滤维度与 CSV 导出均已在 api-spec §5.9 列入契约（合规巡检/留档刚需），后端成本低（同一查询构造 + 流式序列化）；本期一次做齐避免遗留半截契约。

**落地**：`audit_service.query_*()`（构造过滤 + 分页 / 流式）；`/audit-logs` 路由两端点（`export` 分支返 `StreamingResponse`）；`schemas` 加 `AuditLogOut` / 分页信封。

### 60.5 Q371 附件落盘布局 + storage_path 复制 + 30 天孤儿清理（自决实现细节）

**决策**：
- **落盘布局**：附件**不去重**（区别于 sha256 去重的 asset），每次上传生成独立 `storage_path`（承 Q119）= `attachment/{uuid前2}/{uuid}{原扩展名}`（沿用 asset 分桶风格；`storage.attachment_path(uuid, ext)` 助手）。`file_name` 存原始名（同名可并存）。
- **元数据复制**（承 Q113/Q117）：`_fork`（upgrade/restore）复制 `content_source` 版本的 active 附件行（新 id、新 `procedure_id`，`file_name`/`storage_path`/`mime_type`/`size_bytes`/`description`/`sort_order` 复用，**物理文件不复制**）；`rollback` 取 **target_version** 的附件（已在 `_fork` 以 `content_source=target` 传入）；`copy_procedure` 取所传 `{id}` 版本的附件（Q238）。
- **30 天孤儿清理**（新 task `cleanup_attachments`，每日 `CLEANUP_HOUR`，承 Q115/Q332/§53.2）：取「软删（`is_active=false`）且 `deleted_at ≤ now-30d`」的附件行，按 `storage_path` 分组；对每组 **若该 path 无任何 `is_active=true` 行引用** → **先删物理文件**（缺失视为成功；`OSError` 保留行下轮重试）→ **再硬删该 path 下全部软删行**（行+文件同删）。逐项提交、单项失败记日志续跑、结构化 run 摘要（承 §53.2/§53.4）；CLI `python -m app.tasks.cleanup_attachments --once`；挂入 scheduler 第 3 个 daily job。

**Why**：附件去重无意义（用户文件非内容寻址、同名并存是显式需求 Q119），独立 `storage_path` 最简；元数据复制挂在既有 `_fork`/`copy_procedure` 零新路径；清理按 `storage_path` 分组判 active 引用，精确实现「跨版本复用的 storage_path 仅在全无 active 引用时才删文件」，与 asset GC 的「行+文件同删/文件先删/grace」语义一致、复用既有 task 模板。

**落地**：`storage.attachment_path()`；`attachment_service`（上传落盘+上限校验+CRUD+`copy_for_version()`+`cleanup_orphans()`）；`version_flow_service._fork`/`copy_procedure` 调 `copy_for_version`；`tasks/cleanup_attachments.py` + `scheduler.build_scheduler()` 加 job；`errors` 加 `ATTACHMENT_LIMIT_EXCEEDED`。
