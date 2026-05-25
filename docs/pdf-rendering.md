# PDF 渲染规范（PDF Rendering）

> 本文件单列 Smart SOP 的 **PDF 生成与渲染规范**。所有 PDF 相关实现以本文件为权威。
>
> 后端实现复用 dpms-2.0 的 `services/pdf/` 包（ReportLab Platypus），仅替换 ORM 调用。
> 数据模型见 [data-model.md](data-model.md)；接口契约见 [api-specification.md](api-specification.md)；高层决策见 [feature-clarifications.md](feature-clarifications.md)。

## 1. 总体

| 项 | 值 |
|---|---|
| PDF 库 | ReportLab（纯代码绘制，无 HTML→PDF）|
| 模板 | 自定义 `ProcedureDocTemplate`（继承 BaseDocTemplate）|
| 页面尺寸 | A4 纵向（210 × 297 mm）|
| 页边距 | 上下 1.27 cm，左右 2.03 cm |
| 行距 | 1.5× |
| 生成方式 | **同步**，两遍渲染（第一遍算总页数，第二遍正式绘制）|
| 超时 | 后端硬超时 60 秒（504 Gateway Timeout） |
| 限流 | nginx 表层 20 req/min/IP（仅 `/pdf-*` 路由） |
| 缓存 | **不缓存**结果，每次请求重新生成（保证内容实时） |
| 文件名 | `{code}_Rev{version}.pdf` |

## 2. 页面结构

PDF 由 4 个区段顺序拼接：

```
┌─────────────────────────────────────────┐
│  1. 封面页（无 header / footer）         │
├─────────────────────────────────────────┤
│  2. 目录页（罗马数字页码 i, ii, ...）    │
├─────────────────────────────────────────┤
│  3. 修订记录页（罗马数字页码续）         │
├─────────────────────────────────────────┤
│  4. 内容页（阿拉伯数字从 1 开始）        │
│     含 header / footer                  │
└─────────────────────────────────────────┘
```

## 3. 封面页

### 3.1 布局元素（从上到下）

| 元素 | 来源 / 内容 |
|------|-----------|
| 大标题 | `procedure.name`，22pt 加粗居中 |
| 副信息块 | `程序编号: {code}` + `版本: Rev.{version}` |
| 用途级别（Q182）| `用途级别: {中文标签} ({英文标签})` —— 来源 `procedure.level_of_use` 字段（`reference` → 参考使用 Reference Use；`continuous` → 连续使用 Continuous Use；`information` → 信息使用 Information Use）；PPA AP-907-005 §4.11 强制必备 |
| 所属文件夹 | `folder.full_path` |
| 风险/质量等级 | 文字分级 + 颜色色块（详见 §3.2） |
| 自定义字段（Q257）| `show_on_cover=true` 的 active ProcedureField，按 `sort_order` 渲染 `{name}: {custom_values[key]}`；select / multi_select 显示选项 label（含归档选项的旧 label，只读）；空值不渲染 |
| 创建/更新日期 | `created_at` / `updated_at` 格式 `YYYY-MM-DD` |
| 签名栏 | 三栏空白「编制 / 审核 / 批准」（详见 §3.3） |

封面页**无 header / footer**，**无 footer 页码**（但**计入** T 总页数，见 §6.1 / Q184）。

### 3.2 风险/质量等级展示（Q52）

格式：`{标签}（{level}）` + 彩色小方块。

| level | 风险标签 | 质量标签 | RGB |
|-------|---------|--------|-----|
| 1 | 低 | 低 | 16, 185, 129（绿） |
| 2 | 中-低 | 中-低 | 132, 204, 22（浅绿） |
| 3 | 中 | 中 | 234, 179, 8（黄） |
| 4 | 中-高 | 中-高 | 249, 115, 22（橙） |
| 5 | 高 | 高 | 220, 38, 38（红） |

示例输出：「风险等级: 中（3）▮ 黄」

### 3.3 签名栏（Q45）

```
┌────────────────┬────────────────┬────────────────┐
│   编制         │   审核         │   批准         │
├────────────────┼────────────────┼────────────────┤
│   签名:        │   签名:        │   签名:        │
├────────────────┼────────────────┼────────────────┤
│   日期:        │   日期:        │   日期:        │
└────────────────┴────────────────┴────────────────┘
```

- 三栏等宽
- 内容全部留空，供纸质打印后手填
- 即使无用户体系也保留，符合行业惯例

### 3.4 版本状态标识与水印（Q225）

按 `procedure.status` 渲染版本状态，防受控文档误用过期 / 未发布版本（呼应 PPA 合规 §23）。

**全文档水印**（封面 + TOC + 修订 + 正文，**所有页**）：

| status | 水印文字 | 样式 |
|--------|---------|------|
| DRAFT | 「草稿 DRAFT」 | 浅灰 RGB(200,200,200) ~30% 透明，45° 斜纹重复平铺，置内容下层不挡正文 |
| ARCHIVED | 「已作废 SUPERSEDED」 | 浅红 RGB(230,150,150) ~35% 透明，45° 斜纹重复平铺 |
| PUBLISHED | **无水印** | 受控正式版 |

**封面额外标识**：

| status | 封面 |
|--------|------|
| DRAFT | 副信息块下加「状态: 草稿 DRAFT」灰字 |
| ARCHIVED | 红色印章样式「已作废 SUPERSEDED · 作废日期 {archived_at}」（来源 `procedure.archived_at`）|
| PUBLISHED | 不加（或可选「受控文件 CONTROLLED」）|

**实现**：ReportLab 每页 `onPage` 回调绘制水印层（`canvas.saveState()` + 半透明 `setFillAlpha` + `rotate(45)` + 平铺重复文字），水印在内容 flowable **之下**。封面状态标识作为封面 flowable 渲染。

**与 Q204 预览的关系**：前端预览层同样按 status 显示水印（CSS `@media` 叠加层）；下载 / 打印 PDF 由 ReportLab 绘制。DRAFT 预览勾选打印（Q213）时水印一并输出。

## 4. 目录页（TOC）

### 4.1 范围（Q46）

只列出：**`content_type='chapter'` 且 `skip_numbering=false` 的节点**。

不进 TOC 的：
- content 节点（无编号无 title）
- step 节点（粒度太细，TOC 会爆炸）
- skip_numbering=true 的章节（前言、附录等"特殊"章节）

### 4.2 渲染规则

| 层级 | 字号 | 缩进 |
|------|-----|-----|
| Level 1 | 14pt 加粗 | 无 |
| Level 2 | 12pt | 1em |
| Level 3 | 12pt | 2em |

> **TOC 深度**（§25.3/Q190 二次修订）：章节最多 3 级，TOC 列全部 3 级（沿 Word `TOC \o "1-3"` 惯例）。

格式：`{code} {title} ........... {page_number}`

- 章节标题与页码之间用点线（dot leader）连接
- 页码为内容页阿拉伯数字编号
- TOC 自身页码为罗马数字 `i / ii / ...`

### 4.3 跨页

TOC 超过一页时自然跨页，每页保留「目录」标题。

## 5. 修订记录页

### 5.1 范围（Q47）

只列出**里程碑事件**的 `version_change_log` 条目：

| change_type | 列入 |
|------------|-----|
| `create` | ✗ 不列（在版本 1 隐含）|
| `update` | ✗ 不列（草稿编辑无外部记录意义）|
| `publish` | ✓ 列 |
| `rollback` | ✓ 列 |
| `deprecate` | ✓ 列 |
| `restore` | ✓ 列 |

### 5.2 表格列

| 列 | 字段 | 宽度 |
|----|-----|-----|
| 版本号 | `version` | 10% |
| 变更类型 | `change_type`（中文翻译）| 14% |
| 变更日期 | `changed_at`（YYYY-MM-DD）| 16% |
| 说明 | `description` + `reason` + `version_update_notes` 拼接 | 60% |

`change_type` 显示翻译：

| 值 | 翻译 |
|---|------|
| publish | 发布 |
| rollback | 回退（注明源版本号）|
| deprecate | 废弃 |
| restore | 恢复 |

#### 「说明」列拼接规则

按以下顺序拼接（任一为空则跳过），段间空行：

1. `version_change_log` 条目的 `description`（系统自动填写，如「发布 v2」）
2. `reason`（rollback / deprecate / restore 时由用户必填）
3. `version_update_notes`（**当前对应版本的用户手填说明**——按 version 关联到对应记录）

> `version_update_notes` 是 `tb_procedure` 字段（每个版本 Procedure 独立），与 `version_change_log` 这种自动审计型字段并存。修订记录页按版本号匹配后拼接。

### 5.3 跨页

记录跨页时使用 ReportLab LongTable，**表头每页重绘**。

## 6. 内容页

### 6.1 Header / Footer 与页码体系（Q184 严格 PPA + Q211 页眉布局）

> Q184 覆盖 Q59：**T = 全文档总页数（含封面 / TOC / 修订 / 正文）**；P 在前置页（TOC / 修订）用罗马小写、正文用阿拉伯整数。
> Q211 调整页码**显示位置**：由页脚移至**页眉右列第三行**（P/T 计算规则不变）。

#### 页眉布局（Q211）—— 一行两列

```
┌────────────────────────────┬───────────────────────────┐
│                            │ 程序编号: QC-0001          │  ← 右列第 1 行
│  启动 SOP                  │ 版本: Rev.2                │  ← 右列第 2 行
│  （程序标题 · 左列居中）   │ 第 3 页 / 共 13 页         │  ← 右列第 3 行（页码）
├────────────────────────────┴───────────────────────────┤
│  ─────────────────────────────────────────────────────  │  ← 分隔线
│                  ...正文内容...                          │
└──────────────────────────────────────────────────────────┘
```

| 区域 | 内容 | 来源 | 对齐 |
|------|-----|------|------|
| 左列 | 程序标题 | `procedure.name` | 左对齐、垂直居中 |
| 右列第 1 行 | `程序编号: {code}` | `procedure.code` | 右对齐 |
| 右列第 2 行 | `版本: Rev.{version}` | `procedure.version` | 右对齐 |
| 右列第 3 行 | `第 {P} 页 / 共 {T} 页` | 渲染时计算 | 右对齐 |

- 列宽：左列约 55%，右列约 45%（右列文本较短）。
- 页眉下方一条横分隔线，再接正文。

#### 页脚（Q211 调整）

页码已移至页眉右列第三行，**页脚不再重复页码**。页脚留空（仅保留底边距）；如未来需要可放固定文案，本轮不放。

#### 页码 P/T 体系（Q184，显示位置随 Q211）

P/T 计算规则不变，仅显示位置为页眉右列第三行：

| 区段 | 页眉 | 右列第 3 行页码形式 |
|------|------|-------------------|
| 封面 | **无页眉**（参见 §3.1），但**计入** T | — |
| TOC / 修订记录 | 有页眉 | 罗马小写 `第 i 页 / 共 13 页` |
| 正文 | 有页眉 | 阿拉伯 `第 3 页 / 共 13 页` |

**T 计算**：T = 1（封面）+ TOC 页数 + 修订记录页数 + 正文页数。两遍渲染：第一遍 dry-run 分别统计四区段页数求和得 T，第二遍按区段切换右列第三行 P 的格式（前置页 `roman.toRoman(n)` 转小写罗马）。

#### 完整示例（13 页文档）

| 物理页 | 区段 | 页眉右列第 3 行 |
|--------|-----|----------------|
| 1 | 封面 | （无页眉）|
| 2 | TOC 第 1 页 | 第 i 页 / 共 13 页 |
| 3 | TOC 第 2 页 | 第 ii 页 / 共 13 页 |
| 4 | 修订记录 | 第 iii 页 / 共 13 页 |
| 5 | 正文第 1 页 | 第 1 页 / 共 13 页 |
| ... | ... | ... |
| 13 | 正文第 9 页 | 第 9 页 / 共 13 页 |

TOC 列出的 chapter 页码仍为正文阿拉伯数字（Q46 不受影响）。

### 6.2 章节标题

> **重要**（[§19 重构](feature-clarifications.md#十九章节模型重构q149q152)）：chapter 节点**仅渲染标题**，无 rich_content；正文走 content 子节点（§6.4）。

| level | 字号 | 加粗 | 上间距 | 下间距 | 缩进 |
|-------|-----|-----|--------|-------|------|
| 1 | 16pt | 是 | 24pt | 8pt | 0 |
| 2 | 14pt | 是 | 18pt | 6pt | 0 |
| 3 | 12pt | 是 | 14pt | 4pt | 0 |

> **最多 3 级**（§25.3/Q190 二次修订回 3 级；曾短暂改 6 级，因 31 份真实文档最深仅 3 级而回退）。Word 解析遇 H4-6 / 更深编号 → 压缩为 L3（恢复 Q35，可加 `<strong>` 标记体现降级）。

格式：`{code} {title}`，编号与标题中间留一个全角空格。chapter 渲染后**直接进入子节点**（content / 子 chapter / step）。

> **L1 章节渲染 `N.0`**（§47/Q305）：内部 `code` 递归（L1=`N`、L2=`N.M`、L3=`N.M.K`），**渲染时对 level==1 chapter 追加 `.0`**（→ `1.0 目的` … `13.0 附件`，DPMS/§15.2 习惯）。L2/L3 与 step 不加 `.0`；TOC（§4）/ 树视图同此显示。

#### skip_numbering 章节（Q54）

- **字号字体完全相同**
- 仅编号位置留空（PDF 成品留空白；编辑器 / 树视图用灰「#」，§47/Q307），标题直接顶到 code 列右端
- 不出现在 TOC（Q46）
- **不计入序号**（§47/Q306）：skip 节点不占序号位、编号节点连续——前言(skip)+目的+范围 → 空白、`1.0`、`2.0`

### 6.3 step 渲染（Q48 + Q57 + Q261-Q265）

> **本节随 §40 重构**：执行表单 3 型 → **12 型占位符**（Q261/Q262）；警示由 `step_alerts` → **note/caution/warning 三富文本字段**（Q263）。

#### step 渲染顺序（自上而下）

| 序 | 元素 | 来源 | 条件 |
|----|-----|------|------|
| 1 | 标题 `{code} {title}` | step.title / code | 总是 |
| 2 | **警示块**（note→caution→warning 固定序）| `step.note` / `step.caution` / `step.warning`（Q263）| 各字段非空时；按 §7.1-7.3 三色样式渲染 |
| 3 | 正文 | `step.content`（HTML；COMMON 型即此）| 非空时 |
| 4 | **附件标记**「📎 附件: {name}（{kind}）」| `step.attachment_marks`（Q203）| 数组非空时；每条一行纯文本 |
| 5 | 执行记录区（PDF 纸质占位符）| `step.input_schema.type`（12 型，见下）| 总是 |
| 6 | 签字栏 | `procedure.signoff_enabled` | 开启且步骤非警示型（NOTE/CAUTION/WARNING）时 |

> **警示置于动作之前**（顺序 2 在正文 3 之前）符合 PPA §4.15「警示先于其所修饰的步骤」。固定 `note→caution→warning` 顺序天然满足递进。

```
1.2.1 启动电源                                      ← 14pt 加粗（顺序 1）
    ┌ ⛔ 警告 WARNING ───────────────────────┐    ← step.warning（顺序 2，三字段按序）
    │ 高压未泄放，强行打开可致死。            │
    └────────────────────────────────────────┘
    检查所有阀门处于关闭状态，按下绿色启动按钮。     ← step.content 正文（顺序 3）
    📎 附件: operation_demo.mp4（视频）              ← attachment_marks（顺序 4）
    执行结果:  ☐ 通过    ☐ 不通过                   ← 执行记录区（顺序 5，依 12 型）
                               签字: __________   日期: __________  ← 签字栏（顺序 6，procedure.signoff_enabled=true 且非警示型）
```

#### 警示三字段渲染（Q263 / 方案 A）

- 数据来源 `step.note` / `step.caution` / `step.warning`（三个富文本字段，[data-model.md §3.5](data-model.md#35-tb_procedure_step--程序步骤)）。
- **固定渲染顺序** note→caution→warning（PPA §4.15 递进），各非空字段渲染为对应三色框（§7.1-7.3：提示蓝 / 小心黄 / 警告红）；富文本内容支持加粗/列表。
- 与 content 节点正文内嵌 HTML class 警示（§7，Q183，**章节正文级辅通道 C**）双轨并存，各自渲染不去重。

#### attachment_marks 附件标记（Q203，不变）

- 数据来源 `step.attachment_marks` JSON 数组；每条渲染为单行 `📎 附件: {name}（{kind 中文}）` + 可选 `— {note}`。
- `kind` 中文映射：video=视频 / image=图片 / doc=文档 / audio=音频 / other=其他。
- **纯文本标记**，不嵌入文件、不生成链接（与程序级附件表格 §6.6 并存）。

#### 执行记录区：12 型纸质占位符（Q262）

PDF 通道把 `input_schema.type` 渲染成语义化纸质填写控件（移动端执行通道则为真控件，本期不做执行运行时）：

| type | PDF 纸质占位符 |
|------|---------------|
| `COMMON` | （正文即 step.content）+ `☐ 已完成` 勾选执行框 |
| `CHECK` | `执行结果:  ☐ {pass_label}    ☐ {fail_label}`（默认 通过/不通过）|
| `YESNO` | `☐ 是    ☐ 否` |
| `NUMBER` | `{label}: __________ {unit}　(合格范围 {min}~{max})`（承接原 measurement 上下限/精度）|
| `METER` | `{label}: __________ {unit}`（本期简化，Q265）|
| `CHECKBOX` | `☐ 选项1   ☐ 选项2   ☐ 选项3`（多选）|
| `RADIO` | `○ 选项1   ○ 选项2`（单选）|
| `UPLOAD` | `附件: ____________（见附页 / 粘贴）` |
| `SIGNATURE` | `签名: ________________` |
| `DATE` | `日期: ______ 年 ___ 月 ___ 日` |
| `PHOTO` | 虚线矩形「照片粘贴区」框 |
| `NONE` | 不渲染采集区 |

#### signoff_enabled 签字栏（程序级）

签字栏由 `procedure.signoff_enabled` 控制；开启且步骤非警示型（NOTE/CAUTION/WARNING）时，步末追加右对齐一行：

```
                               签字: __________   日期: __________
```

无勾选框、无"已确认完成"——此为纸质手写签字占位，不含电子勾选控件。

### 6.4 content 节点渲染（Q58）

- 与正文段落**完全同格式**（同字体、同字号、无背景、无边框）
- 上下各加 1em 内边距，与上下文章节正文区分
- 无编号、无标题
- 直接渲染 `rich_content` HTML

### 6.5 跨页保护（Q53）

| 元素 | 保护策略 | ReportLab 实现 |
|------|---------|---------------|
| 章节标题 | 不独立页底；后跟 ≥ 2 行正文 | `KeepWithNext` flowable |
| step 整体 | 不拆页 | `KeepInFrame` |
| 超页高 step | 强制拆页，页底加「未完」、页顶加「续 step {code}」 | 自定义 ContinuedFlowable |
| 表格 | 自动跨页（Q31）| `LongTable` |

### 6.6 附件区段（Q185-Q188 / PPA §4.13.13）

> 仅元数据清单 + 正文最后一节 + 沿用正文页码 + 表格式。详细决策见 [feature-clarifications.md §23.5](feature-clarifications.md#235-q185q188-附件渲染入-pdfppa-41313)。
>
> **粒度区分（Q203）**：本节是**程序级**附件（`tb_procedure_attachment`，真实上传文件，末节表格）。**步骤级**附件标记（`step.attachment_marks`，如 mp4，仅标记不嵌入）在 §6.3 渲染，二者并存、互不替代。

#### 6.6.1 触发条件

- 程序存在 ≥ 1 条 `is_active=true` 的 `tb_procedure_attachment` 记录 → 渲染附件区段。
- 程序无附件 → **整段省略**（不渲染空表头、不占页）。

#### 6.6.2 区段标题

附件区段作为正文的最后一个 chapter 渲染，标题文本「**{编号} 附件 / Attachments**」：

- **若用户已自行创建** `name='附件'` 或 `name='Attachments'` 的 level-1 chapter（与 §15.2.13 参考清单对齐）→ 附件表渲染为该 chapter 的内容；编号沿用用户已分配的 chapter code。
- **若用户未创建** → 渲染流水线**自动追加**一个虚拟 chapter「{next_code} 附件 / Attachments」，编号 next_code = 最后一个正文 chapter 编号 + 1（如正文最后 chapter 为 `12.0` → 附件区段标题 `13.0 附件 / Attachments`）。

虚拟 chapter **不**写入 `tb_procedure_chapter` 数据库，仅在 PDF 渲染时存在。

**与 procedure 模板（§28）的衔接**：[feature-clarifications.md §28.2](feature-clarifications.md#282-q210-模板内容多套模板--对应-step-类型) 的三套预设模板**不**预生成「附件 / Attachments」section，因此用模板创建的程序默认走上面**第二分支**（自动追加虚拟 chapter）。仅当用户**手工**创建 `name='附件'/'Attachments'` 的 level-1 chapter 时才走**第一分支**（附件表渲染进该 chapter，并因此进 TOC）。两分支由 chapter 名匹配决定、互斥。

#### 6.6.3 表格列定义

| 列 | 来源字段 | 宽度 | 渲染规则 |
|----|---------|------|---------|
| 序号 | `sort_order` 排序后从 1 顺序枚举 | 6% | 居中 |
| 文件名 | `file_name` | 30% | 左对齐，过长自动换行 |
| 大小 | `size_bytes` | 10% | 居右；< 1024 显示 `B`，< 1024² 显示 `KB`，否则 `MB`（保留 2 位小数）|
| 类型 | `mime_type` | 12% | 左对齐 |
| 上传日期 | `created_at` | 14% | 居中，格式 `YYYY-MM-DD` |
| 描述 | `description` | 28% | 左对齐；空字符串显示「—」 |

#### 6.6.4 表格行为

- ReportLab `LongTable`，**表头每页重绘**（沿用 §9.2 表格规范）。
- 排序：按 `sort_order` 升序；同 `sort_order` 按 `created_at` 升序兜底。
- **不**过滤 `is_active=false` 的记录之外的任何条件（mime_type、扩展名一视同仁）。
- 每行高度由内容自适应；行 padding 4px。
- 表格上方 8pt 间距，下方与正文章节一致。

#### 6.6.5 页码与编号

- 沿用正文阿拉伯页码（与正文连续）。
- 不独立分页、不重置编号、不重绘 footer 格式。
- 附件区段计入 T。

#### 6.6.6 不渲染内容

- **不**嵌入文件本体（图片不 inline、PDF 不缩略、Office 不解析）。
- **不**生成下载链接（PDF 是离线交付物）。
- **不**生成 SHA256 / MD5 校验和（本轮 Q188 未引入该字段）。
- 用户须通过 Smart SOP 系统的附件下载接口单独获取文件本体。

#### 6.6.7 与 PPA §4.13.13 的偏差

- PPA 要求"独立编号 Attachment X Page 1 of N + 继承父 header" → Smart SOP **不实现**（Q187），沿用正文页码。
- PPA 要求附件作为"程序的组成部分"在 TOC 中出现 → 若用户创建对应 chapter，TOC 自然包含（Q46）；虚拟 chapter 不进 TOC。

### 6.7 signoff 预览交互（Q204）

> **勾选目的（Q213）= 展示 + 打印**：用户在预览层勾选，然后**所见即所得地打印出带勾选的版本**。勾选**不**用于执行留痕或跨会话持久化。

**四条路径**：

| 场景 | 渲染路径 | signoff / 确认框 / hold-point 签名区 |
|------|---------|-------------------------------------|
| **屏幕预览** | **前端渲染层**（基于后端结构化数据复刻本规范版式）| **可点击勾选激活**；状态仅前端组件 state 临时保存 |
| **打印**（Q213，主）| **浏览器打印前端预览层**（`window.print()` + 打印 CSS）| **勾选 ☑ 所见即所得输出**（先勾选再打印）|
| **下载 PDF** | **后端 ReportLab** 生成静态 PDF（§1）| 留空框（☐ / 下划线），正式电子交付物 |
| **导出已勾选 PDF**（Q213 可选增强）| 后端 ReportLab + 前端传当前勾选项 id 列表 | 按勾选渲染 ☑（与下载版同版式）|

**可交互元素**（预览层，可勾选后随打印输出）：
- `hold-point` 块的签名 / 日期区 → 可点击激活（高亮 / 标记已签）。
- 封面 / `signature-bar` 三栏签名区 → 可点击激活。

> **程序级签字栏（`signoff_enabled`）为静态元素**：渲染为右对齐 `签字: __________   日期: __________` 纯文本行，供打印后在纸上手写签字，**不**提供电子勾选交互。

**约束**：
- 勾选状态服务于**展示 + 打印**（Q213），**不持久化**到程序数据、**不写回**数据库；刷新即丢失。
- **打印**走浏览器打印前端预览层，勾选所见即所得（无需后端往返）。
- **下载 PDF** 始终是空框静态交付物（受控电子文档惯例）；如需带勾选的 PDF 文件，走「导出已勾选 PDF」可选增强。
- 前端预览层需复刻本规范版式（含打印 CSS `@media print`），**一次性完整复刻、不分阶段**（Q237，修订原「可分阶段」）；正文数据复用 `GET /procedures/{id}`，**页码 / TOC 页码 / 附件页码取自后端 `GET /procedures/{id}/pdf-layout`**（Q235，与本节下载版同一分页逻辑，逐页对齐），**不再有后端 base64 预览端点**（Q234，旧 `POST /pdf-preview` 已删除）。详见 [feature-clarifications.md §34](feature-clarifications.md#三十四pdf-预览前端渲染层落地q234q237)；UI 细节见 [editor-behavior.md §10](editor-behavior.md)。

## 7. 特殊元素（HTML class 协议）

WangEditor 提供专门按钮插入这些标签，PDF 生成器识别 class 后特殊渲染。

### 7.0 警示三类总述（Q183 / PPA §4.15）

**警示按风险递增**分为 Note / Caution / Warning 三类独立 class，对应递进语义：

| class | 风险层级 | 适用语义 |
|-------|---------|---------|
| `note-block` | 提示性 | 重要信息，**不**涉及风险 |
| `caution-block` | 设备/程序 | 操作不当损坏设备 / 数据 / 程序结果；**不**涉及人身伤害 |
| `warning-block` | 人身伤害 | 操作不当造成人身伤害甚至死亡 |

**顺序约束**：同一上下文出现多类警示时，**强制顺序 Note → Caution → Warning**（按风险递增）。检测到逆序时打 `app.services.pdf` warning 日志（不阻塞生成）。

**共享布局参数**：
- 内边距：8px 上下，12px 左右
- 与上下文段落间距：8px
- 边框：1px 实线（颜色按类）
- 内容字号：12pt（与正文一致）

**重要变更（Q183 破坏性）**：旧版本 `warning-block`（黄底「⚠ 警告」）已**重定义为红底「⛔ 警告 WARNING」**。旧 rich_content 中已有的 `<div class="warning-block">` 节点重新生成 PDF 时直接渲染新视觉，无数据迁移。

**数据来源（双轨，Q202 调整 / Q263）**：本节定义的三类样式被**两条通道**复用，样式完全一致：

| 通道 | 来源 | 粒度 | 渲染位置 |
|------|-----|------|---------|
| `step.note` / `step.caution` / `step.warning`（Q263，**主**）| step **三个富文本字段**（取代原 step_alerts JSON）| step 级 | §6.3 step 标题后、正文前 |
| HTML class（Q183，辅）| content 节点 rich_content 内 `<div class="...-block">` | chapter 正文级 | §6.4 content 节点正文内嵌 |

> Q263 修订：主通道由 `step_alerts` JSON 数组改为 note/caution/warning 三个**富文本字段**（固定顺序，富文本内容）。下文 §7.1-7.3 的颜色 / 图标 / 标题规格对两轨同时生效。

### 7.1 note-block（Q183 新增）

```html
<div class="note-block">
  操作前请熟悉本程序的整体流程，确认所有前置条件已就绪。
</div>
```

```
┌────────────────────────────────────────────┐
│ ▌ ℹ 注意 NOTE                              │  ← 加粗深蓝标题
│ ▌─────────────────────────────────────     │
│ ▌ 操作前请熟悉本程序的整体流程...          │  ← 内容
└────────────────────────────────────────────┘
   ↑ 浅蓝底（RGB 204, 229, 255）+ 深蓝（RGB 13, 71, 161）1px 边框
```

参数：
- 背景色：RGB(204, 229, 255) — ANSI Z535 提示蓝
- 边框颜色：RGB(13, 71, 161) — 深蓝
- 标题：「ℹ 注意 NOTE」12pt 加粗深蓝
- 共享布局见 §7.0

### 7.2 caution-block（Q183 新增）

```html
<div class="caution-block">
  操作前必须断电，否则可能造成设备损坏。
</div>
```

```
┌────────────────────────────────────────────┐
│ ▌ ⚠ 小心 CAUTION                           │  ← 加粗黑字标题
│ ▌─────────────────────────────────────     │
│ ▌ 操作前必须断电，否则可能造成设备损坏。   │  ← 内容
└────────────────────────────────────────────┘
   ↑ 浅黄底（RGB 255, 217, 102）+ 黑色 1px 边框
```

参数：
- 背景色：RGB(255, 217, 102) — ANSI Z535 安全黄（沿用原 warning-block 黄）
- 边框颜色：黑色
- 标题：「⚠ 小心 CAUTION」12pt 加粗黑字
- 共享布局见 §7.0

### 7.3 warning-block（Q183 重定义；原 Q49 已覆盖）

```html
<div class="warning-block">
  高压未泄放，强行打开可能导致严重烫伤甚至死亡。
</div>
```

```
┌────────────────────────────────────────────┐
│ ▌ ⛔ 警告 WARNING                          │  ← 加粗红字标题
│ ▌─────────────────────────────────────     │
│ ▌ 高压未泄放，强行打开可能...              │  ← 内容
└────────────────────────────────────────────┘
   ↑ 浅红底（RGB 255, 205, 210）+ 红色（RGB 220, 38, 38）1px 边框
```

参数：
- 背景色：RGB(255, 205, 210) — ANSI Z535 警示红的浅化版本（保持可读性）
- 边框颜色：RGB(220, 38, 38) — 警示红
- 标题：「⛔ 警告 WARNING」12pt 加粗红字
- 共享布局见 §7.0

### 7.4 hold-point（Q50）

```html
<div class="hold-point">
  需现场监督员签名确认后方可进入下一步骤。
</div>
```

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ◈ HOLD POINT 检查点                        ┃  ← 加粗红字标题
┃━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┃
┃ 需现场监督员签名确认后方可进入下一步骤。   ┃
┃                                            ┃
┃ 签名: __________   日期: __________        ┃  ← 自动追加
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
   ↑ 红色（RGB 220, 38, 38）双圈边框，2px
```

参数：
- 边框：红色 RGB(220, 38, 38)，2px 双圈
- 标题：「◈ HOLD POINT 检查点」红色 14pt 加粗
- 自动追加：签名行 + 日期行
- 与上下文段落间距：12px

### 7.5 signature-bar（inline，Q51）

```html
<div class="signature-bar"></div>
```

```
┌──────────────┬──────────────┬──────────────┐
│   编制       │   审核       │   批准       │
├──────────────┼──────────────┼──────────────┤
│  签名: ___   │  签名: ___   │  签名: ___   │
│  日期: ___   │  日期: ___   │  日期: ___   │
└──────────────┴──────────────┴──────────────┘
```

参数：
- 三列等宽
- 与封面签名栏样式一致
- 不需 HTML 属性配置
- 与上下文段落间距：8px

## 8. 字体（Q55）

| 用途 | 字体 | 字号 | 注 |
|------|-----|-----|----|
| 中文正文 | SimSun（宋体）| 12pt（小四）| 内置字体包 |
| 英文正文 | Times New Roman | 12pt | |
| 加粗中文 | SimHei（黑体）| 同上 | |
| 加粗英文 | Times New Roman Bold | 同上 | |
| 等宽（代码）| Consolas | 11pt | 备选 Courier New |

### 8.1 中英文混排实现

ReportLab 中通过 `<font name="...">...</font>` 内联标签切换：

```python
# 段落级混排示例
text = '中文文本 <font name="TimesNewRoman">English Text</font> 继续中文'
Paragraph(text, style_with_simsun)
```

字体配置初始化时一次性注册：

```python
pdfmetrics.registerFont(TTFont('SimSun', '/path/to/simsun.ttf'))
pdfmetrics.registerFont(TTFont('SimHei', '/path/to/simhei.ttf'))
pdfmetrics.registerFont(TTFont('TimesNewRoman', '/path/to/times.ttf'))
pdfmetrics.registerFont(TTFont('TimesNewRomanBold', '/path/to/timesbd.ttf'))
pdfmetrics.registerFont(TTFont('Consolas', '/path/to/consola.ttf'))
```

字体文件**内置于** `backend/app/assets/fonts/`（与代码同 deploy）。

## 9. 图片与表格

> **不做图表题注 / 编号 / 交叉引用**（§48/Q312）：渲染器**不**为 `<img>`/`<table>` 注入「图 N / 表 N」题注、**不**解析「见图 X」交叉引用。作者若需题注 / 引用，在富文本里作为**普通文字手工书写**，渲染器**原样输出**。无 `<figure>`/`data-ref` 等约定、无新字段。（章节大纲号由 §47 引擎自动维护，图表号属富文本内容、交作者掌控。）

### 9.1 图片（Q32）

- 等比缩放到页宽（页宽 = A4 - 左右边距 = ~17 cm）
- **始终独占一行，居中**（忽略富文本中的 float / align 属性）
- 支持格式：PNG / JPG / GIF 首帧 / WebP
- 超高（> 单页可用高度）→ 强制缩放至单页可用高度
- 不支持格式（如 SVG）→ 插入占位 `[不支持的图片格式: type]`

### 9.2 表格（Q31）

- 超宽 → 等比缩放至页宽
- 行数多 → 自动跨页（LongTable），表头每页重绘
- **嵌套表格**（Q56）→ 内层降级为缩进列表：
  ```
  外层表格（正常渲染）：
    第 N 行：
      • 内层列 1: 值 1
      • 内层列 2: 值 2
      • 内层列 3: 值 3
  ```
- 配 warning 日志「检测到嵌套表格，已降级为缩进列表」

## 10. PDF metadata（Q56）

| 字段 | 值 |
|------|---|
| `title` | `{code} {name} Rev.{version}` |
| `author` | `Smart SOP` |
| `subject` | `procedure.description` 前 200 字（去 HTML） |
| `keywords` | `procedure.folder.full_path` |
| `producer` | `Smart SOP / ReportLab` |
| `creationDate` | 生成时间（UTC） |

## 11. 性能与限流（Q60）

### 11.1 生成方式

- **同步**：与 FastAPI 同步路由一致
- 调用 `generate_procedure_pdf(procedure_id) -> (bytes, toc_data)`
- 两遍渲染：第一遍 dry-run 算总页数，第二遍正式绘制 + 准确页码

### 11.2 超时

- 后端硬超时 **60 秒**
- 触发条件：单次 ReportLab 调用执行时间超过 60 秒
- 响应：504 Gateway Timeout + 错误码 `PDF_TIMEOUT`

### 11.3 限流

| 路径 | 限制 |
|------|------|
| `GET /procedures/{id}/pdf-layout` | 20 req/min/IP |
| `GET /procedures/{id}/pdf-download` | 20 req/min/IP |

由 nginx 反向代理层实现，后端不内置。

### 11.4 不缓存

每次请求重新生成（保证内容实时）。如确有性能问题，优先**优化 ReportLab 代码**（缓存样式对象、复用 Paragraph、减少 Flowable 数量），而非引入 Celery。

## 12. 边缘场景

### 12.1 空程序

无 chapter 也无根 step 的程序：

- 封面页正常
- TOC 显示「（无章节）」
- 修订记录页正常
- 内容页显示「（程序无内容）」单页

### 12.2 仅根 step

无 chapter，仅有 `chapter_id=null` 的 step（受 Q25 互斥约束）：

- TOC 显示「（无章节）」
- 内容页直接列出 step 序列

### 12.3 极长 rich_content

- 单 chapter 的 `rich_content` 跨多页自然换页
- 不做特殊缩减

## 13. 错误码

| 错误码 | HTTP | 触发场景 |
|--------|------|---------|
| `PDF_TIMEOUT` | 504 | 渲染超时 60 秒 |
| `PDF_GENERATION_FAILED` | 500 | ReportLab 内部异常 |
| `PROCEDURE_NOT_FOUND` | 404 | 程序不存在 |

## 14. 调试

PDF 生成日志统一打到 `app.services.pdf` logger：

```
2026-05-19 10:23:45 [INFO] app.services.pdf: pdf generation started procedure_id=... version=1
2026-05-19 10:23:45 [DEBUG] app.services.pdf: first pass complete pages=9 toc_entries=12
2026-05-19 10:23:46 [INFO] app.services.pdf: pdf generation complete size_bytes=234567 time_ms=145
```

开发期可通过 `?debug=1` 查询参数返回**第一遍 dry-run 的 toc_data**，方便排查目录页码错乱。

## 15. 附录：PPA 标准 section 参考清单（Q181 / 非强制）

> 本附录列出 PPA AP-907-005 §4.13.1 Table 1 对**标准 procedure** 强制 / 推荐的章节。Smart SOP **不**强制此结构（Q181 决策），仅作为编写者组织章节树时的最佳实践参考。

### 15.1 PPA 适用程序类别

PPA 把 procedure 分四类（与 Smart SOP 不绑定字段，仅供编写者自查）：

| 英文 | 中文 | 典型示例 |
|------|-----|---------|
| Operating | 运行类 | 启动 SOP、停机 SOP、应急响应 |
| Maintenance | 维护类 | 设备检修、校准、更换 |
| Testing | 测试类 | 性能验证、合规试验、QA 检验 |
| Administrative | 行政类 | 文件管理流程、培训流程、采购流程 |

### 15.2 标准章节清单（按 PPA 推荐顺序）

R = Required（强制）；O = Optional（视情况）；类型列示意 PPA 对该类 procedure 的要求级别。

| 序 | 章节名（建议中文 / 英文）| PPA 章节 | Operating | Maintenance | Testing | Administrative |
|----|-----------------------|--------|-----------|-------------|---------|----------------|
| 1 | 1.0 目的 / Purpose | §4.13.2 | R | R | R | R |
| 2 | 2.0 范围 / Scope | §4.13.3 | R | R | R | R |
| 3 | 3.0 引用文件 / References | §4.13.4 | R | R | R | R |
| 4 | 4.0 术语定义 / Definitions | §4.13.5 | O | O | O | O |
| 5 | 5.0 职责 / Responsibilities | §4.13.6 | R | R | R | R |
| 6 | 6.0 注意事项与限制 / Precautions and Limitations | §4.13.7 | R | R | R | O |
| 7 | 7.0 前提条件 / Prerequisites | §4.13.8 | R | R | R | O |
| 8 | 8.0 专用工具与材料 / Special Tools, Equipment, Parts, and Supplies | §4.13.9 | O | R | R | O |
| 9 | 9.0 验收准则 / Acceptance Criteria | §4.13.10 | O | O | **R** | O |
| 10 | 10.0 操作步骤 / Instructions（或 Procedure）| §4.13.11 | R | R | R | R |
| 11 | 11.0 记录保存 / Retention of Records | §4.13.12 | R | R | R | R |
| 12 | 12.0 修订摘要 / Summary of Alterations | §4.13.14 | R | R | R | R |
| 13 | 13.0 附件 / Attachments | §4.13.13 | O | O | O | O |

### 15.3 编写者操作建议

- 创建程序时，**建议**按上表顺序手动创建 13 个 level-1 chapter 节点（skip_numbering=false），编号 1.0–13.0 由 §27 编号引擎自动生成。
- 不适用的 section 可省略（如 Administrative 类一般不需要 §15.2.7 / §15.2.8）。
- 操作步骤章节（§15.2.10）下挂 step / sub-chapter 节点，承载真正可执行的工序。
- 附件章节（§15.2.13）作为 chapter 节点存在；具体附件文件通过 `tb_procedure_attachment` 上传（与 PDF 渲染独立，PDF 不会内嵌附件文件本体）。

### 15.4 与 §19 章节模型重构的关系

- 上述 13 个章节均为 chapter 节点，**rich_content 必须为空**（§19 / Q149-Q152 不可变设计）。
- 每个 chapter 的正文放在其**第一个 content 子节点**（rich_content 富文本）。
- 这一约束与 PPA 没有冲突：PPA 关心"标准 section 存在 + 顺序合规"，对内容载体不约束。

### 15.5 合规判定边界

- Smart SOP **不阻止**用户偏离上述结构，PDF 也**不强制校验**。
- 若交付目标为 PPA AP-907-005 严格合规，编写者**自行**对照本清单组织章节树并自查。
- 评估文档 [docs/reference doc/pa-procedure-writer-s-manual-pdf-hidden-hippo.md](../docs/reference%20doc/pa-procedure-writer-s-manual-pdf-hidden-hippo.md) 列出未来 P1/P2 改进项，本附录覆盖范围限于"参考清单"。
