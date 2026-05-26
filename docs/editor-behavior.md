# 编辑器行为规范（Editor Behavior）

> 本文件单列**结构化编辑器**（ProcedureEditor）的前端行为规范。后端约束见 [feature-clarifications.md](feature-clarifications.md)，接口契约见 [api-specification.md](api-specification.md)。

## 1. 编辑器界面布局（Q161-Q163）

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 顶栏：[程序库/质检/启动 SOP]  [v3 ▮DRAFT]  [● 未保存]                   │
│       [标记] [应用标记] [撤销] [重做]   [保存] [发布/升级] [PDF] [⋮]    │
├─────────────────────────────────────────────────────────────────────────┤
│ ▾ 程序详情（默认折叠）                                                   │
│   description 输入框 | risk_level select | quality_level select          │
│   自定义字段表单（按 ProcedureField active 列表渲染）                    │
│   version_update_notes（textarea, DRAFT 可改）                          │
│   PDF 签字栏 [☐ 开启]（signoff_enabled，DRAFT 可改）                    │
│   [已废弃字段] 折叠区（按 Q133 仅读）                                    │
├─────────────────┬──────────────────────────────────────────────────────┤
│ 章节树（左侧）   │ 右侧 Tab 切换：[节点详情][附件][版本历史]            │
│ [🔍 搜索 /]     │ ┌─ 节点详情（默认） ──────────────────────────────┐ │
│                 │ │ chapter: title textarea + 跳号 + 子节点列表       │ │
│ 📘 1. 概述      │ │ content: WangEditor 富文本                        │ │
│   📄 (引言)     │ │ step:    title + type + WangEditor + input_schema│ │
│   📘 1.1 目的   │ │            + 警示×3                              │ │
│ 📘 2. 操作流程  │ └────────────────────────────────────────────────────┘ │
│   ☐ 2.1 启动... │ ┌─ 附件 ──────────────────────────────────────────┐  │
│                 │ │ 上传按钮 + 列表（name/size/上传时间/操作） + 限制 │  │
│ [+章节] [+步骤] │ └────────────────────────────────────────────────────┘ │
│ [+内容块]       │ ┌─ 版本历史 ──────────────────────────────────────┐  │
│                 │ │ 时间线 v3/v2/v1 + 各版本 notes + 回退/查看按钮    │  │
│                 │ └────────────────────────────────────────────────────┘ │
└─────────────────┴────────────────────────────────────────────────────────┘
```

### 1.1 顶栏组件（Q161）

| 区域 | 内容 |
|------|------|
| 面包屑 | `程序库 / {folder.full_path} / {code} {name}` |
| 版本 + 状态 chip | `v{N}` + 状态 chip（Q172 配色）；deprecated group 额外加红色「废止」tag |
| 未保存 chip | `● 未保存`（橙色，仅 dirty 时显示） |
| 主动作按钮组 | **DRAFT**：保存 / 发布 / PDF 预览  **PUBLISHED**：升级版本 / PDF 下载  **ARCHIVED**：仅 PDF 下载 |
| 「⋮ 更多」菜单 | 复制为新程序（§9.7）/ 丢弃此 DRAFT（§17.10，仅 status=DRAFT 且 version>1）/ 废弃整 group（§9.5，仅非 ARCHIVED）/ 恢复（§9.6，仅 deprecated group） |

**status chip 配色**（**修订 Q172 → Q317 / §49.5**，暖盘 + 圆点呈现）：

| 状态 | Hex | 呈现 |
|------|------|------|
| DRAFT 草稿 | `#A89A86` 暖灰 | ○ 空心点 |
| PUBLISHED 已发布 | `#88B07A` 鼠尾草绿 | ● 实心点 |
| ARCHIVED 已归档 | `#6B635A` 暗暖灰 | ● 暗点 |
| 废止（附加，整 group deprecated 时显示）| `#D9685E` 暖红 | 描边小红 tag |

> 旧 EP 默认盘（PUBLISHED = 主蓝 `#409EFF`）已废弃；现行配色以 [feature-clarifications §49.5 Q317](feature-clarifications.md) + [design-system.md §2.1](design-system.md) 为准，EP `--el-*` 重映射见 §49.6 / Q318。

> deprecate / restore / DELETE 单版本的入口归并见 §9.5 / §9.6 / §11；删除单版本**不**在此菜单中。

> 状态决定按钮显隐与 enable/disable；详细行为见 §9。

### 1.2 程序详情折叠面板（Q162）

顶栏下方默认收起的「程序详情」折叠区，含程序级元数据：

- `description` textarea
- `risk_level` / `quality_level` select（按 §6.2 PDF 封面映射）
- 所有 `status='active'` 的 ProcedureField 渲染对应输入控件
- 「已废弃字段」嵌套折叠区（含 archived ProcedureField 在 custom_values 里的旧值，灰色只读）
- `version_update_notes` textarea（仅 DRAFT 可编辑）
- **PDF 签字栏** toggle（`signoff_enabled`，程序级开关，仅 DRAFT 可改；受控文档属性，upgrade/copy 时随程序携带）

折叠 / 展开状态保存到 sessionStorage。

### 1.3 右侧 Tab（Q163）

| Tab | 内容 |
|-----|------|
| 节点详情（默认）| 按选中节点的 type 渲染 (§4.1) |
| 附件 | 「附件」tab：上传 + 列表 + 数量/大小限制提示（§22）|
| 版本历史 | 时间线 + 各版本 notes 展开 + 行内操作按钮（详见 §13.4）|

切换 tab 时**保留**节点详情 tab 内的未保存修改（dirty 状态依赖 store，不依赖 tab）。

## 2. 章节树（左侧）行为

### 2.1 节点视觉表示（Q41-Q43）

#### 图标与颜色

| 节点类型 | 图标 | 默认颜色 | 颜色随 mark_status 变化 |
|---------|------|---------|----------------------|
| chapter（content_type=chapter）| 📘 | 蓝 | unmarked=蓝 / step=绿 / content=灰 |
| step | ☐ | 绿 | （step 不参与标记模式，颜色固定）|
| content（content_type=content）| 📄 | 灰 | unmarked=灰 / step=绿 |

> mark_status 通过**节点图标颜色**直接表达「应用后会变成什么」的预期，不另外加 chip。

#### 节点行布局（信息密度）

从左到右一行内容：

```
[展开 ▸] [节点图标] [code] [title or fallback] [类型色条] [特殊状态图标]
   只 chapter 有      左对齐区                     右对齐区
```

| 位置 | 显示规则 |
|------|---------|
| `code` | 正常显示如 `1.2.3`；**L1 章节显示 `N.0`**（§47/Q305，如 `1.0`）；skip_numbering=true 时显示 **`#`** 灰色占位（§47/Q307）|
| `title` | 主要内容粗体；fallback 时用灰斜体（详见下方）|
| 执行表单类型色条（仅 step） | `▮` 色块标示 12 型（Q261）：COMMON/NONE=灰 / CHECK/YESNO=蓝 / NUMBER/METER=紫 / CHECKBOX/RADIO=青 / UPLOAD/PHOTO/SIGNATURE/DATE=橙；hover 显示型名 |
| 特殊状态图标（仅 step） | `#` = skip_numbering |

#### 标题与 fallback（Q42）

| 节点 | title 不为空 | title 为空时 |
|------|------------|------------|
| chapter | 原样显示 | 显示 `(未命名章节)` 灰斜体（极少出现）|
| step | 原样显示 | 取 `step.content` **首行纯文本前 50 字**，灰斜体加括号显示 |
| step 且 content 也为空 | — | 显示 `(空步骤)` 灰斜体 |
| content（无 title 字段）| — | 取 `rich_content` 首行纯文本前 50 字 |

> step.title 为空**不阻塞编辑**；提交 PUBLISHED 时仅 warning，不报错。

### 2.2 节点操作（右键菜单）

| 操作 | 显示条件 | 调用 API |
|------|---------|---------|
| 重命名 | 任意可编辑节点 | PUT /chapters/{id} 或 /steps/{id} |
| 上移 | 不是首节点 | POST .../move-up |
| 下移 | 不是末节点 | POST .../move-down |
| 切换跳号 | chapter / step | POST .../toggle-skip-numbering |
| 转为步骤 | chapter，无子节点 | POST /chapters/{id}/convert-to-step |
| 内容拆为步骤 | content 节点 | POST /chapters/{id}/content-to-steps |
| 转为章节 | step | POST /steps/{id}/convert-to-chapter |
| 删除 | 任意 | DELETE |

转换操作触发互斥违反时，前端**预先校验**（基于当前树状态）并 disable 菜单项，提示「该操作会让同级节点类型混排」。

### 2.3 新增按钮显隐规则

「+ 子章节」「+ 子步骤」「+ 内容块」按钮的 disabled 逻辑（Q25 互斥）：

```typescript
function getAddButtonState(parent: Chapter | null): AddButtonState {
  // parent=null 表示 procedure 根级
  const children = listDirectChildren(parent)
  const types = new Set(children.map(c => c.actualType))

  return {
    canAddChapter: !types.has('step'),
    canAddContent: !types.has('step'),
    canAddStep: !types.has('chapter') && !types.has('content'),
  }
}
```

disabled 按钮有 tooltip 解释：「该章节包含子章节，无法添加步骤」。

### 2.4 拖拽（drag & drop）

- 支持在树内**跨 parent 拖拽**
- 拖入目标位置时**实时校验互斥规则**，违反时显示红色禁止图标 + tooltip
- 释放有效位置触发 `POST /chapters/{id}/move` 或 `/steps/{id}/move`
- 章节最大嵌套 3 级（Q190 二次修订回 3 级），拖入第 4 级时禁止

### 2.5 新增步骤的完整渲染流程（Q42-Q43）

```
用户在 chapter X 上点「+ 子步骤」
  │
  ├─ 前端检查 Q25 互斥规则
  │   ├─ X 已有子 chapter / 子 content → 按钮 disabled
  │   └─ X 仅有 step 兄弟或无子节点 → 按钮可用
  │
  ├─ 点击后立即在树中插入临时占位节点
  │   ├─ 临时 id（前端 uuid）
  │   ├─ title=''
  │   ├─ type='COMMON'（Q11 默认；text→COMMON 迁移后，Q261）
  │   ├─ 视觉：☐ 绿色 + 灰斜体 `(空步骤)` + 类型色条 ▮text 灰
  │   ├─ code 暂占位「计算中…」灰色
  │   └─ 自动展开 X，高亮新节点 1s
  │
  ├─ 右侧详情面板自动激活该节点，title 输入框 focus
  │
  ├─ 用户填写后点「保存」（或 sessionStorage 自动暂存）
  │
  └─ 提交 POST /steps
      ├─ 服务端再次校验 Q25 互斥（防止前端被绕过）
      ├─ 整树重算 code → 返回新 code（Q15 + Q27）
      ├─ If-Match 校验 revision（Q18）
      └─ 前端用真实 id 替换临时 id，code 占位变实际值，类型色条按 input_schema.type 渲染
```

### 2.6 详情面板 ↔ 树节点 双向同步（Q44）

| 详情面板的编辑动作 | 树节点同步刷新 |
|-----------------|-------------|
| 改 `title` | 节点 title 实时刷新 |
| 改 `content` 且 title 为空 | 节点 fallback 文本（首行 50 字）实时刷新 |
| 切换 `input_schema.type` | 类型色条颜色实时刷新 |
| 切换 `skip_numbering` | code 变 `#`，下方同级 code 整树重算 |
| 改 chapter `rich_content`（且无 title）| chapter fallback 文本同步 |

树**始终只显示一行**——不在树上展开 step.content / rich_content 预览（Q44）。完整内容仅在右侧详情面板展示。

---

## 3. 标记模式（MarkMode）

### 3.1 进入与退出

- 顶部工具栏「标记模式」按钮（开关）
- 开启时：编辑区**变只读**；章节树每个 chapter / content 节点前出现 checkbox + 三态标签
- 退出方式：再点开关，或点「应用标记」/「清除标记」

### 3.2 标记操作

| 动作 | 行为 |
|------|------|
| 点击节点 | 循环切换 `unmarked` → `step` → `content` → `unmarked` |
| 多选 (Shift+点击) | 范围选择，**仅在同 parent_id 内有效**（跨 parent 的部分自动忽略并提示）|
| 全选 (顶部按钮) | 选中**当前展开**的同层级节点 |
| 标记为步骤（批量按钮）| 选中节点 mark_status 设为 `step` |
| 标记为内容（批量按钮）| 选中节点 mark_status 设为 `content` |

**约束**：

- 单次操作最多 **100 项**（前端校验，超限提示「单次最多标记 100 项，请分批操作」）
- 跨 parent 选择拒绝（错误码 `MARK_SELECTION_CROSS_PARENT`）
- step 节点**不参与标记模式**（标记模式仅作用于 chapter / content）

### 3.3 视觉表示

mark_status 直接通过**节点图标颜色**表达（Q41）：

| mark_status | 节点图标颜色 | 含义 |
|-------------|-----------|------|
| `unmarked` | chapter=蓝 / content=灰 | 无变化（默认色）|
| `step` | 图标变 **绿** | 暗示「应用后会变成 step」 |
| `content` | 图标变 **灰** | 暗示「应用后会变成 content」（chapter→content）|

不另外加 chip / 标签——颜色变化已经足够明显。同时 checkbox 仍出现在节点左侧便于多选。

### 3.4 应用标记

「应用标记」按钮的行为：

```typescript
async function applyMarks() {
  // 1. 收集所有非 unmarked 的节点
  const marked = collectMarkedNodes()
  if (marked.length === 0) {
    toast.warning('没有需要应用的标记')
    return
  }

  // 2. 弹确认对话框，列出将执行的操作
  const summary = summarizeMarks(marked)
  // 例：「将执行 5 个 content-to-steps，共生成 12 个步骤」（§19 后 chapter→content 标记不再触发任何转换）
  const confirmed = await confirm(summary)
  if (!confirmed) return

  // 3. 调用后端原子接口
  try {
    const result = await http.post(`/procedures/${pid}/apply-marks`)
    toast.success(`已应用：新增 ${result.created.length} 个步骤、删除 ${result.deleted.length} 个节点`)
    refreshEditor()
  } catch (e) {
    if (e.code === 'SIBLING_TYPE_CONFLICT') {
      toast.error('应用失败：部分标记会违反子节点互斥规则，请检查后重试')
    } else {
      toast.error('应用失败：' + e.message)
    }
  }
}
```

**关键**：后端是**原子事务**（Q9），失败全部回滚，节点 mark_status 保持不变；成功后所有相关节点 mark_status 清空。

---

## 4. 内容编辑区（右侧）

> **重要**：本章按 [feature-clarifications.md §19](feature-clarifications.md#十九章节模型重构q149q152) 章节模型重构后的 UI 描述。chapter 节点**不再有 WangEditor**。

### 4.1 三种节点的 UI 形态

**Chapter 节点**（仅标题容器，无 rich_content）：

```
┌────────────────────────────────────────────────┐
│ 标题: ┌──────────────────────────┐ [跳号开关]   │
│       │ textarea (autosize)       │              │
│       │ 默认 1 行高，长 title 自动 │              │
│       │ 增高，500 字上限           │              │
│       └──────────────────────────┘              │
├────────────────────────────────────────────────┤
│ 子节点列表（仅信息展示）：                       │
│   ▸ 1.1 (子 chapter) 操作前提                   │
│   ▸ (content) 适用范围说明...                   │
│ ↑ 实际增删走左侧树的「+ 子章节 / + 内容块 / + 步骤」│
└────────────────────────────────────────────────┘
```

**Content 节点**（无 title，仅富文本）：

```
┌────────────────────────────────────────────────┐
│ rich_content（WangEditor，标准工具栏）         │
│  ┌───────────────────────────────────────┐    │
│  │ B I U | 标题 | 列表 | 表格 |           │    │
│  │ 图片 | 注意/小心/警告 | 签名栏 | HoldPoint│    │
│  ├───────────────────────────────────────┤    │
│  │   富文本编辑区                          │    │
│  └───────────────────────────────────────┘    │
└────────────────────────────────────────────────┘
```

**Step 节点**（分组折叠面板，顺序对齐 PDF step 渲染 §6.3 / Q221；**§40 重构**：12 型 + 三富文本警示）：

```
┌────────────────────────────────────────────────┐
│ ▼ 基本信息                                       │
│   标题: [文本框]   执行表单类型: [COMMON▼]  [跳号]│
├────────────────────────────────────────────────┤
│ ▼ 警示（note/caution/warning · Q263）            │
│   ▮蓝 注意 Note:   [富文本编辑器]                │
│   ▮黄 小心 Caution:[富文本编辑器]                │
│   ▮红 警告 Warning:[富文本编辑器]                │
├────────────────────────────────────────────────┤
│ ▼ 正文                                           │
│   content（WangEditor）；COMMON 型操作说明即此   │
├────────────────────────────────────────────────┤
│ ▼ 附件标记（attachment_marks · Q220）            │
│   [+ 附件标记]                                   │
│   文件名:[demo.mp4] 类型:[视频▼] 备注:[.] [↕][✕]│
├────────────────────────────────────────────────┤
│ ▼ 执行记录（执行表单类型，12 型切换显示）        │
│   COMMON:    （无额外字段，正文即说明 + 勾选执行）│
│   CHECK:     通过标签 [.]  不通过标签 [.]        │
│   YESNO:     （无额外字段）                      │
│   NUMBER:    单位 [.] min [.] max [.] 小数位 [.] │
│   METER:     单位 [.]（本期简化，Q265）          │
│   CHECKBOX:  选项列表 [+项]                      │
│   RADIO:     选项列表 [+项]                      │
│   UPLOAD:    accept [.] max_count [.]            │
│   SIGNATURE / DATE / PHOTO / NONE: （无/少量字段）│
├────────────────────────────────────────────────┤
│ ▼ 其他                                           │
│   预期输出: [文本框]                            │
└────────────────────────────────────────────────┘
```

- **分组折叠（Q221）**：6 组可独立折叠/展开，顺序对齐 PDF step 渲染（[pdf-rendering.md §6.3](pdf-rendering.md)）：基本信息 → 警示 → 正文 → 附件标记 → 执行记录 → 其他。
- **警示子区（Q263 方案 A，修订 Q219）**：**三个固定富文本编辑器**（note 蓝 / caution 黄 / warning 红），各对应 `step.note` / `step.caution` / `step.warning`（[data-model.md §3.5](data-model.md)）；固定顺序、各自可空；样式与 [pdf-rendering.md §7](pdf-rendering.md) 三色一致。**取代**原 step_alerts 数组行编辑器。普通备注归入 `note`（原 `notes` 字段已移除）。
- **执行表单类型（12 型，Q261/Q262）**：基本信息区下拉选 `COMMON`/`CHECK`/`YESNO`/`NUMBER`/`METER`/`CHECKBOX`/`RADIO`/`UPLOAD`/`SIGNATURE`/`DATE`/`PHOTO`/`NONE`；执行记录区按选中型显示对应配置字段。
- **附件标记子区（Q220，不变）**：每条 = 文件名 + `kind` 下拉 + 备注 + 排序/删除；纯标记，不校验文件已上传（Q203）。来源 `step.attachment_marks`。
- **执行运行时不做（Q264）**：本面板仅编写"执行表单定义"；执行态（移动端勾选/录入）属执行模块，编辑器不涉及。

### 4.2 WangEditor 配置

**完整工具栏**（chapter / content 节点）：

```
B I U | 标题(H1/H2/H3) | 段落 | 列表(有序/无序) | 表格 | 代码块 |
图片(本地上传) | 链接 | 引用 | 注意 | 小心 | 警告 | 签名栏 | HoldPoint | 撤销 | 重做
```

**简化工具栏**（step.content 节点）：

```
B I U | 列表(有序/无序) | 图片 | 链接
```

### 4.3 特殊元素插入（B8）

- 「注意」按钮 → 插入 `<div class="note-block">在此输入提示内容</div>`（蓝，Q183）
- 「小心」按钮 → 插入 `<div class="caution-block">在此输入设备风险警示</div>`（黄，Q183）
- 「警告」按钮 → 插入 `<div class="warning-block">在此输入人身风险警示</div>`（红，Q183）
- 「签名栏」按钮 → 插入 `<div class="signature-bar" data-columns="3">在此配置签名栏</div>`
- 「HoldPoint」按钮 → 插入 `<div class="hold-point">在此输入 hold point 内容</div>`

这些 class 在 PDF 生成时由 ReportLab 识别并渲染为特殊样式块。

> **双轨说明（Q202 调整 / Q263）**：以上 `note/caution/warning-block` 是 chapter 正文级警示的**辅通道**（content 节点富文本内嵌）；**step 级**警示走 step 编辑面板「警示」子区的 **note/caution/warning 三个富文本字段**（§4.1 / Q263，取代原 step_alerts），二者样式一致、各自渲染。

---

## 5. 图片处理（Q30）

> **图片改走 assets（§25.1/Q189 取代原 base64）**：rich_content 内图片统一为 `<img src="/api/procedures/{id}/assets/{asset_id}">`，不再 base64 内联。下述插入流程相应改为「上传→得 asset URL→插图」。
> **上传端点**（§29.1/Q214）：`POST /procedures/{id}/assets`（multipart `file`）直传、即时入库、按 sha256 去重，返回 `{asset_id, url}`。

### 5.1 插入流程

1. 用户点 WangEditor 工具栏「图片」→ 选本地文件
2. **前端立即校验**：
   - 单图大小 ≤ 10 MB（原始字节，Q207）
   - 格式 ∈ {JPG, PNG, GIF, BMP, WebP, EMF, WMF}（EMF/WMF 由后端转 PNG，Q207）
   - 当前节点已有图片数 < 20
3. 校验失败：拒绝插入，弹 toast 错误
4. 校验通过：**上传到 `POST /procedures/{id}/assets`（§29.1/Q214）→ 后端按 sha256 去重入 `tb_procedure_asset` → 返回 `{asset_id, url}` → 插入 `<img src="/api/procedures/{id}/assets/{asset_id}">`**（§25.2/Q189）

### 5.2 保存时校验

后端在 PUT chapter / step 时校验 rich_content / step.content 总字节数 ≤ 5 MB（图片已外置为 URL，正文 HTML 本身一般远小于此），超限返回 413 `CONTENT_TOO_LARGE`。保存时同步重建 `tb_procedure_asset_reference`（Q197）。

### 5.3 错误提示

| 场景 | toast 文本 |
|------|----------|
| 单图 > 10MB | 「图片大小超过 10 MB，请压缩后重试」|
| 格式不支持 | 「仅支持 JPG/PNG/GIF/BMP/WebP/EMF/WMF 格式」|
| 节点图片数 > 20 | 「单节点最多 20 张图片」|
| 总量 > 5MB | 「该节点内容过大，请精简或拆分」|

---

## 6. 撤销 / 重做（Q23）

### 6.1 作用范围

- **本地未保存**改动可撤销
- 用户点「保存」后**清空撤销栈**
- 切换节点不清空栈
- 关闭编辑器（路由离开）→ 清空栈

### 6.2 栈管理

```typescript
interface EditorAction {
  type: 'update_title' | 'update_content' | 'add_node' | 'delete_node' | 'reorder' | ...
  payload: any        // 反向操作所需数据
  inverse_payload: any // 对应的反向数据
}

const undoStack: EditorAction[] = []
const redoStack: EditorAction[] = []
const MAX_STACK = 50

function applyAction(action: EditorAction) {
  // 1. 执行 action 到 store
  doAction(action)
  // 2. 推 undo 栈，清 redo 栈
  undoStack.push(action)
  if (undoStack.length > MAX_STACK) undoStack.shift()
  redoStack.length = 0
}

function undo() {
  const action = undoStack.pop()
  if (!action) return
  doAction({ ...action, payload: action.inverse_payload })
  redoStack.push(action)
}
```

### 6.3 不进入撤销栈的操作

以下操作**直接调后端**且**不可撤销**：

- 删除（DELETE，软删）
- 类型转换（convert-*）
- 应用标记（apply-marks）
- 升级版本 / 回退
- 移动跨 parent（move with target_parent_id）

这些操作前**弹确认对话框**。

### 6.4 快捷键

| 快捷键 | 动作 |
|--------|------|
| `Cmd/Ctrl + Z` | 撤销 |
| `Cmd/Ctrl + Shift + Z` | 重做 |
| `Cmd/Ctrl + S` | 保存 |

---

## 7. sessionStorage 自动保存

### 7.1 保存时机

- 用户每次 action（输入、移动、新增、删除等）后 **debounce 1s** 写入 sessionStorage
- key 格式：`procedure_editor_${procedure_id}`
- value 结构：

```typescript
interface SessionDraft {
  procedure_id: string
  version: number       // 防止跨版本误恢复
  revision: number      // 防止跨乐观锁版本误恢复
  saved_at: string      // ISO 8601
  state: EditorState    // 完整编辑器状态
}
```

### 7.2 恢复时机

进入编辑器（`onMounted`）：

```typescript
async function tryRestoreDraft() {
  const key = `procedure_editor_${procedureId}`
  const raw = sessionStorage.getItem(key)
  if (!raw) return
  
  const draft = JSON.parse(raw) as SessionDraft
  const remote = await fetchProcedureDetail(procedureId)
  
  // 跨版本不恢复
  if (draft.version !== remote.version) {
    sessionStorage.removeItem(key)
    return
  }
  
  // 远程已被其他人改过 → 提示风险
  if (draft.revision !== remote.revision) {
    const overwrite = await confirm(
      '检测到本地未保存的草稿，但远程版本已变更。是否丢弃本地草稿使用远程最新版？'
    )
    if (overwrite) {
      sessionStorage.removeItem(key)
      return
    }
  }
  
  // 弹确认是否恢复
  const restore = await confirm(
    `检测到 ${dayjs(draft.saved_at).fromNow()} 的本地未保存草稿，是否恢复？`
  )
  if (restore) {
    loadState(draft.state)
  } else {
    sessionStorage.removeItem(key)
  }
}
```

### 7.3 清理时机

- 保存成功 → 清除
- 用户主动「丢弃草稿」按钮 → 清除
- 路由离开且无未保存改动 → 清除
- 进入编辑器恢复失败（跨版本）→ 清除

---

## 8. 保存流程

### 8.1 保存按钮行为

```typescript
async function save() {
  // 1. 客户端校验
  const errors = validate(state)
  if (errors.length) {
    toast.error('请先修复以下错误: ' + errors.join('; '))
    return
  }
  
  // 2. 携带 If-Match 头
  try {
    const response = await http.put(
      `/procedures/${pid}`,
      buildPayload(state),
      { headers: { 'If-Match': remoteRevision } }
    )
    // 3. 成功
    remoteRevision = response.revision
    clearUndoStack()
    clearSessionDraft()
    toast.success('已保存')
  } catch (e) {
    if (e.status === 409 && e.code === 'VERSION_CONFLICT') {
      // 4. 并发冲突处理
      const action = await confirm(
        '远程版本已被其他人修改。是否：[加载远程版本(放弃本地)] / [取消]'
      )
      if (action === 'reload') {
        await reload()
      }
    } else {
      toast.error('保存失败: ' + e.message)
    }
  }
}
```

### 8.2 客户端预校验

- 章节 title 不为空
- 步骤 title 可空（保存前提示但允许）
- 章节嵌套不超过 3 级
- 子节点互斥规则
- 富文本图片大小 / 总量
- 自定义字段 validation_rules

---

## 9. 状态机切换

### 9.1 「发布」按钮

仅在 `is_current=true 且 status=DRAFT` 时显示：

```typescript
async function publish() {
  // 1. 客户端校验：是否有未应用的标记
  const unappliedMarks = collectMarkedNodes()
  if (unappliedMarks.length > 0) {
    const proceed = await confirm(
      `存在 ${unappliedMarks.length} 个未应用的标记，发布后将被清空。继续？`
    )
    if (!proceed) return
  }
  
  // 2. 客户端校验：content 节点是否最终化（PDF 渲染检查）
  // ...
  
  // 3. 调用 transition（后端 publish 前调预留 ApprovalGate.check()，本期 stub 放行，Q243）
  await http.post(`/procedures/${pid}/transition`, {
    status: 'PUBLISHED'
  })
  toast.success('已发布')
  reload()  // 重载后编辑区变只读
}
```

**审批模式徽标（Q245）**：当全局设置 `enable_approval_workflow=true` 时，在「发布」按钮旁显示徽标「审批模式已开启（模块待上线）」。**本期闸门放行、不阻断发布**——徽标仅提示审批模块未来生效，publish 行为不变（Q243）。开关 OFF 时不显示。

### 9.2 「升级版本」按钮

> 权威决策见 [feature-clarifications.md §22.1（Q165）](feature-clarifications.md#221-upgrade-version-输入策略q165) 与 [§22.4（Q168）](feature-clarifications.md#224-操作成功后页面跳转q168)。

仅在 `is_current=true 且 status=PUBLISHED` 时显示。**不弹 reason 输入**；用户在新 DRAFT 的「程序详情 → 版本更新说明」textarea 自行填写。

```typescript
async function upgradeVersion() {
  const confirmed = await confirmDialog(
    `将创建版本 v${current.version + 1}，当前版本会被归档。是否继续？`
  )
  if (!confirmed) return

  const newProc = await http.post(`/procedures/${pid}/upgrade-version`, {})
  router.push(`/procedures/${newProc.id}/edit`)
  setSuccessBanner({
    kind: 'upgrade',
    sourceVersion: current.version,
    newVersion: newProc.version,
  })
  toast.success(`已升级到 v${newProc.version}`)
}
```

### 9.3 「回退到此版本」按钮（行内）

> 权威决策见 [feature-clarifications.md §22.3（Q167）](feature-clarifications.md#223-rollback-target-选择-uiq167) 与 [§22.4（Q168）](feature-clarifications.md#224-操作成功后页面跳转q168)。

入口位置：**版本历史 tab 的时间线**，每一行如满足 `status='ARCHIVED' AND is_active=true AND is_current=false`，在操作按钮组位置显示「回退到此版本」按钮。

点击按钮 → 弹 modal（reason textarea 必填、空值禁用确认按钮）：

```typescript
async function rollbackTo(targetVersion: number) {
  const { reason, confirmed } = await openRollbackModal({ targetVersion })
  if (!confirmed) return  // 取消

  const newProc = await http.post(`/procedures/${pid}/rollback`, {
    target_version: targetVersion,
    reason,
  })
  router.push(`/procedures/${newProc.id}/edit`)
  setSuccessBanner({
    kind: 'rollback',
    targetVersion,
    newVersion: newProc.version,
  })
  toast.success(`已基于 v${targetVersion} 创建新版本 v${newProc.version}`)
}
```

modal 内文案：

```
┌─ 回退到 v{target_version} ─────────────┐
│ 将创建新 DRAFT v{N+1}，当前 v{current} │
│ 自动归档。                             │
│                                        │
│ 回退原因（必填）:                      │
│ [textarea, 5 行]                       │
│                                        │
│            [取消]  [确认回退]          │
└────────────────────────────────────────┘
```

### 9.4 成功 banner（upgrade / rollback / restore 通用）

新版本编辑器载入后，顶栏正下方显示非阻塞 banner（Element Plus `<el-alert type="success" closable>`，不自动消失）：

| kind | banner 文案 |
|------|------------|
| upgrade | `已基于 v{sourceVersion} 创建新 DRAFT v{newVersion}，可在「程序详情 → 版本更新说明」编辑摘要。` |
| rollback | `已基于 v{targetVersion} 创建新 DRAFT v{newVersion}。初始版本说明已预填，可继续编辑。` |
| restore（原 folder 存在）| `已从「废止」恢复并创建新 DRAFT v{newVersion}（原文件夹: {folder.full_path}）。` |
| restore（原 folder 已删，用户选了新位置）| `已从「废止」恢复并创建新 DRAFT v{newVersion}（已移至: {target_folder.full_path}）。` |
| copy | `已从 {sourceCode} v{sourceVersion} 复制创建，新 code: {newCode}（v1 DRAFT）。` |

### 9.5 「废弃整 group」入口（Q170）

> 权威决策见 [feature-clarifications.md §22.6（Q170）](feature-clarifications.md#226-deprecate-入口与影响范围提示q170)。

两处入口（弹同款 modal）：

| 位置 | 显示条件 |
|------|---------|
| 编辑器顶栏「⋮ 更多」菜单 → 「废弃整 group」 | 当前查看版本不为 ARCHIVED |
| 程序库列表行「⋮」菜单 → 「废弃整 group」 | 非「废止」文件夹下的行 |

```typescript
async function deprecateGroup() {
  const versionCount = await fetchVersionCount(procedureGroupId)  // 或读缓存
  const { reason, acknowledged, confirmed } = await openDeprecateModal({
    procedureName: current.name,
    versionCount,
  })
  if (!confirmed || !acknowledged || !reason) return

  await http.post(`/procedures/${pid}/deprecate`, { reason })
  toast.success('已废止整 group')
  // 编辑器入口 → reload；列表入口 → 刷新当前行
}
```

modal 形态（含「我已了解此操作不可逆」checkbox + reason textarea，未勾或未填 reason 时确认按钮禁用）：

```
┌─ 废弃程序「{procedure.name}」 ─────────────────┐
│ ⚠ 此操作将废止整 group 共 {N} 个版本，         │
│   并移动到「废止」系统文件夹。                  │
│                                                │
│ 操作不可逆（仅可通过「恢复」fork 新 DRAFT）。 │
│                                                │
│ 废弃原因（必填）:  [textarea, 5 行]            │
│ ☐ 我已了解此操作不可逆                          │
│                                                │
│              [取消]   [确认废弃]                │
└────────────────────────────────────────────────┘
```

### 9.6 「恢复」入口（Q169）

> 权威决策见 [feature-clarifications.md §22.5（Q169）](feature-clarifications.md#225-restore-与-restore_folder_missing-交互q169) 与 [§二十二 总览](feature-clarifications.md#二十二版本管理-ui-流程q165q180)。

显示条件：当前 group 已 deprecate（编辑器内 status chip 显示「废止」标签时）。两处入口：

| 位置 | 显示条件 |
|------|---------|
| 编辑器顶栏「⋮ 更多」菜单 → 「恢复」 | deprecated group |
| 「废止」文件夹列表行「⋮」菜单 → 「恢复」 | 任意行 |

流程使用预检查接口（避免后端错误兜底）：

```typescript
async function startRestore(pid: string) {
  const preview = await http.get(`/procedures/${pid}/restore-preview`)
  let body: any

  if (preview.folder_exists) {
    // 分支 A：原 folder 仍在 → 仅 reason
    const r = await openRestoreReasonModal({
      folderPath: preview.folder_full_path,
      versionCount: preview.version_count,
    })
    if (!r.confirmed) return
    body = { reason: r.reason }
  } else {
    // 分支 B：原 folder 已删 → reason + folder picker
    const r = await openRestoreWithFolderPickerModal({
      versionCount: preview.version_count,
    })
    if (!r.confirmed) return
    body = { reason: r.reason, target_folder_id: r.target_folder_id }
  }

  const newProc = await http.post(`/procedures/${pid}/restore`, body)
  router.push(`/procedures/${newProc.id}/edit`)
  setSuccessBanner({
    kind: 'restore',
    newVersion: newProc.version,
    folderPath: preview.folder_exists ? preview.folder_full_path : null,
  })
  toast.success('已从「废止」恢复')
}
```

分支 A modal：

```
┌─ 恢复程序「{name}」 ──────────────────────────┐
│ 将基于历史最高版本 fork 新 DRAFT，并移回      │
│ 原文件夹：{folder_full_path}                  │
│ 共 {N} 个版本保留 ARCHIVED 状态。             │
│                                              │
│ 恢复原因（必填）:  [textarea, 5 行]          │
│                                              │
│             [取消]    [确认恢复]              │
└──────────────────────────────────────────────┘
```

分支 B modal：

```
┌─ 恢复程序「{name}」（原文件夹已删除） ────────┐
│ 原文件夹已删除，请选择恢复目标位置：           │
│ [文件夹选择器（仅 system=false）]              │
│                                                │
│ 恢复原因（必填）:  [textarea, 5 行]            │
│                                                │
│              [取消]   [确认恢复]                │
└────────────────────────────────────────────────┘
```

### 9.7 「复制为新程序」入口（Q179）

> 权威决策见 [feature-clarifications.md §22.15（Q179）](feature-clarifications.md#2215-复制为新程序-ui-入口q179)。

入口位置：

| 位置 | 显示条件 |
|------|---------|
| 编辑器顶栏「⋮ 更多」 → 「复制为新程序」 | 任意状态（含 deprecated group 的只读视图，复制源为当前查看的版本）|
| 程序库列表行「⋮」 → 「复制为新程序」 | 非「废止」文件夹下的行 |

> ⚠ 「废止」文件夹的列表行**不**直接显示复制入口（§22.16 行为矩阵）；如需复制 deprecated group 中的某版本，先点行进入只读视图（`/procedures/{id}/view`），再走顶栏 ⋮。

两处入口弹出同款 form modal：

```typescript
async function copyAsNewProcedure() {
  const { targetFolderId, name, confirmed } = await openCopyForm({
    sourceName: current.name,
    sourceVersion: current.version,
  })
  if (!confirmed) return

  const newProc = await http.post(`/procedures/${pid}/copy`, {
    target_folder_id: targetFolderId,
    name,  // 可选，后端 default = source.name + ' (副本)'
  })
  router.push(`/procedures/${newProc.id}/edit`)
  setSuccessBanner({
    kind: 'copy',
    sourceCode: current.code,
    sourceVersion: current.version,
    newCode: newProc.code,
  })
  toast.success('已复制')
}
```

modal：

```
┌─ 复制程序「{source.name} v{source.version}」 ─┐
│ 目标文件夹（必填）:                           │
│ [文件夹选择器（仅 system=false）]              │
│                                               │
│ 新程序名（选填，默认 = 源名 + " (副本)"）:    │
│ [text input]                                  │
│                                               │
│             [取消]   [确认复制]                │
└───────────────────────────────────────────────┘
```

成功 banner（kind='copy'）：`已从 {sourceCode} v{sourceVersion} 复制创建，新 code: {newCode}（v1 DRAFT）。`

---

## 10. PDF 预览（前端渲染层，Q204 / Q213 / Q234–Q237）

按钮显示条件：任意 `is_current=true` 的程序均可预览。

> **预览不再调后端 base64 PDF**（Q234，旧 `POST /pdf-preview` 已删除）。预览是**前端可交互渲染层**：正文数据复用 `GET /procedures/{id}`，分页骨架取 `GET /procedures/{id}/pdf-layout`，前端**一次性完整复刻**本规范全版式（封面/TOC/修订/正文/警示/签名/水印），hold-point / 封面 / signature-bar 签名区可勾选（程序级签字栏为静态行，见 §10.2），打印走 `window.print()`。详见 [feature-clarifications.md §34](feature-clarifications.md) 与 [pdf-rendering.md §6.7](pdf-rendering.md)。

### 10.1 预览流程

```typescript
async function preview() {
  loading.value = true
  try {
    // 正文结构化数据 + 分页骨架（页号/TOC 页码/附件页码，由后端同一分页逻辑算好）
    const [detail, layout] = await Promise.all([
      http.get(`/procedures/${pid}`),
      http.get(`/procedures/${pid}/pdf-layout`),
    ])
    openPreviewLayer(detail, layout)   // 前端渲染层逐页复刻版式
  } finally {
    loading.value = false
  }
}
```

### 10.2 预览渲染层

- **前端复刻全版式**（一次性，Q237）：封面 / TOC / 修订记录 / 正文 / 警示三类（ANSI Z535 三色）/ step / hold-point 签名区 / 程序级附件表格 / 版本状态水印（Q225，CSS `@media` 叠加层）。
- **分页**：按 `pdf-layout` 返回的页号把内容切到对应「纸张」容器，**逐页与下载版 PDF 对齐**（页码一致、TOC 跳转准确，Q235）；前端不自行估算精确页码。
- **可勾选 signoff**（Q204）：hold-point 签名区、封面 / signature-bar 签名区可点击勾选；状态仅前端组件 state 临时保存，**不写库、刷新即丢**（Q213）。程序级签字栏（`signoff_enabled`）为静态纸质行（`签字: __________   日期: __________`），不提供电子勾选。
- **打印**（Q213，主路径）：「打印」按钮触发 `window.print()` + 打印 CSS（`@media print` 隐藏工具栏、仅留文档版式），勾选 ☑ 所见即所得输出。
- **下载**：右上角「下载」按钮调 `GET /procedures/{id}/pdf-download`（后端 ReportLab 静态空框，正式电子交付物）。
- **导出已勾选 PDF**（Q236）：本轮不实现，仅预留；带勾选输出用 `window.print()` 即可。

---

## 11. 性能优化

| 场景 | 优化 |
|------|------|
| 大量章节树（> 100 节点）| Element Plus 虚拟滚动 + 懒展开 |
| WangEditor 长内容 | 切换节点时延迟初始化 |
| sessionStorage 写入 | debounce 1s + 最多每节点一次 |
| 章节树拖拽 | 用 `transform: translate` 避免 reflow |

---

## 12. 错误处理与用户提示

### 12.1 标准错误码 → 中文文案

| 错误码 | 用户提示 |
|--------|---------|
| `VERSION_CONFLICT` | 远程版本已被其他人修改，是否加载最新版本？ |
| `SIBLING_TYPE_CONFLICT` | 该操作会让同级节点类型混排，请先处理其他同级节点 |
| `CHAPTER_HAS_CHILDREN` | 该章节包含子节点，请先清空后再转换 |
| `CHAPTER_DEPTH_EXCEEDED` | 章节最多 3 级嵌套 |
| `MARK_SELECTION_TOO_LARGE` | 单次最多标记 100 项 |
| `IMAGE_TOO_LARGE` | 图片大小超过 10 MB |
| `CONTENT_TOO_LARGE` | 内容过大（> 5 MB），请精简 |
| `PROCEDURE_READONLY` | 该版本为只读，无法编辑 |
| `PROCEDURE_IS_CURRENT` | 该版本是当前版本，无法删除；请先升级或废止整 group |
| `PROCEDURE_DEPRECATED` | 程序已被废止，请先恢复后再操作 |
| `PROCEDURE_STATUS_INVALID` | 当前状态不允许此操作 |
| `RESTORE_FOLDER_MISSING` | 原文件夹已删除，请选择新的恢复目标 |
| `ROLLBACK_REASON_REQUIRED` | 回退必须填写原因 |
| `ROLLBACK_TARGET_INVALID` | 回退目标版本不存在或不属于当前 group |
| `VERSION_UPDATE_NOTES_REQUIRED` | 请先填写本次版本的更新说明 |
| `PROCEDURE_GROUP_DELETE_FORBIDDEN` | 该程序不满足删除条件（仅 v1 DRAFT 且无历史版本可完全删除）|
| `FOLDER_NAME_DUPLICATE` | 同级文件夹已存在相同名称 |
| `FOLDER_PREFIX_DUPLICATE` | 前缀已被占用（含历史程序使用过的前缀），请换一个 |
| `FOLDER_DEPTH_EXCEEDED` | 文件夹最多 5 级嵌套 |
| `FOLDER_CYCLE_DETECTED` | 移动会形成循环结构，已阻止 |
| `FOLDER_NOT_EMPTY` | 文件夹含子文件夹或程序，请先清空后再删除 |
| `FOLDER_HAS_PROCEDURES` | 该文件夹已存放程序，不能再新建子文件夹（请先移走程序）|
| `FOLDER_SYSTEM_PROTECTED` | 系统文件夹不可删除或修改 |
| `PROCEDURE_CODE_DUPLICATE` | 程序编码冲突 |
| `PROCEDURE_FOLDER_REQUIRED` | 请先选择文件夹 |
| `PROCEDURE_VERSION_MAX` | 已达到最大版本号上限 |
| `MARK_SELECTION_CROSS_PARENT` | 标记必须在同一父节点下，已忽略跨层级选择 |
| `APPLY_MARKS_FAILED` | 应用标记失败，请查看详情后重试 |
| `PARSE_FILE_INVALID` | 仅支持 .docx 格式文件 |
| `PARSE_FILE_TOO_LARGE` | Word 文件超过 50 MB，请压缩后上传 |
| `PARSE_FAILED` | 解析失败，请检查文档结构后重试 |
| `PARSE_TEMPLATE_INVALID` | 标准模板校验未通过，请查看报告 |
| `PARSE_NO_HEADINGS` | 文档未检测到任何标题，无法生成章节树 |
| `PARSE_TIMEOUT` | 解析超时（> 30 秒），请简化文档后重试 |
| `UNSUPPORTED_IMAGE_FORMAT` | 仅支持 JPG / PNG / GIF / WebP 图片格式 |
| `UPLOAD_TOKEN_INVALID` | 上传令牌已过期，请重新上传文件 |
| `FIELD_KEY_DUPLICATE` | 字段 key 已被占用 |
| `FIELD_KEY_RESERVED` | 该 key 是系统保留字，请换一个 |
| `FIELD_VALUE_INVALID` | 字段值不符合校验规则 |
| `FIELD_KEY_IMMUTABLE` | 字段 key 不可修改 |
| `FIELD_TYPE_IMMUTABLE` | 字段类型不可修改，如需变更请新建字段 |
| `ATTACHMENT_TOO_LARGE` | 附件单文件不能超过 50 MB |
| `ATTACHMENT_NOT_FOUND` | 附件文件不存在或已被清理 |
| `ATTACHMENT_LIMIT_EXCEEDED` | 附件数量或总大小超出上限（最多 30 个 / 200 MB）|
| `PDF_TIMEOUT` | PDF 生成超时（> 60 秒），请简化内容后重试 |
| `PDF_GENERATION_FAILED` | PDF 生成失败，请稍后重试或联系管理员 |
| `CHAPTER_RICH_CONTENT_NOT_ALLOWED` | 章节节点不再承载内容，请改用「内容块」子节点 |
| `CONVERT_TO_CONTENT_DEPRECATED` | 该转换已废弃，请使用「内容块」类型节点 |
| `IF_MATCH_REQUIRED` | 缺少 If-Match 标头，请求被拒绝 |
| `VALIDATION_FAILED` | 数据校验未通过，请检查表单 |
| `NOT_FOUND` | 资源不存在或已被删除 |
| `INTERNAL_ERROR` | 服务器异常，请稍后重试 |

> 兜底：未识别的错误码统一显示 `error.detail.message`（后端 message 字段），保证不出现裸 code 文本。

### 12.2 危险操作二次确认

| 操作 | 确认形态 |
|------|---------|
| 删除章节 | 「将删除该章节及其全部子节点（共 N 个），是否继续？」|
| 应用标记 | 「将执行 X 个转换、生成 Y 个新步骤，是否继续？」|
| 升级版本 | 「将创建版本 v{N+1}，当前版本会被归档。是否继续？」（**不再要求输入 reason**，详见 §9.2） |
| 回退到某历史版本 | 行内「回退到此版本」按钮 → modal：「将创建新 DRAFT v{N+1}，当前 v{current} 自动归档。回退原因（必填）：[textarea]」（详见 §9.3） |
| 废弃整 group | modal：「⚠ 此操作将废止整 group 共 {N} 个版本到「废止」文件夹。操作不可逆。」+ reason textarea 必填 + checkbox「我已了解此操作不可逆」（详见 §9.5）|
| 恢复程序 | 分支 modal（按原文件夹是否存在；详见 §9.6），reason textarea 必填，必要时含 folder picker |
| 删除单历史版本 | 时间线行内 🗑 图标 → modal：「⚠ 删除后此版本不可作为 rollback 目标。原始数据可在审计日志查询。」+ reason textarea 必填（详见 §13.4 / §22.7）|
| 丢弃此 DRAFT（v2+）| ⋮ 菜单 →「丢弃此 DRAFT」→ modal「⚠ 此操作将软删此 DRAFT，且无法通过 UI 恢复...」+ reason 必填（详见 §17.10 / §22.11）|
| 删除整个程序（v1 DRAFT）| **列表行 ⋮** →「删除整个程序」→ modal「⚠ 此操作将完全删除此程序及其全部数据，不可恢复...」+ reason 必填（详见 §22.13；编辑器内不提供此入口）|

---

## 13. 版本更新说明（version_update_notes）

> 用户手填的本次版本变更摘要与详细内容，**替代**自动版本 diff 算法。

### 13.1 位置

程序详情页**头部信息区**（标题 + 元字段下方、章节树之前）单列一栏：

```
┌─────────────────────────────────────────────────────────────────────┐
│ 程序: QC-0001 启动 SOP  v2 [PUBLISHED]                              │
│                   [保存][升级版本][PDF 下载][⋮]                     │ ← 主动作按钮组按状态显隐（§1.1）
├─────────────────────────────────────────────────────────────────────┤
│ 文件夹: 质检/检验流程   风险:中(3) 质量:高(5)                       │
├─────────────────────────────────────────────────────────────────────┤
│ 本次版本更新说明:                                                   │
│ ┌─────────────────────────────────────────────────────────────┐    │
│ │ [textarea, 6 行高，纯文本]                                   │    │
│ │ 写摘要 + 详细变更内容...                                     │    │
│ │                                                              │    │
│ └─────────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────────┤
│  章节树（左）        |        内容编辑区（右）                       │
│  ...                 |        ...                                    │
└─────────────────────────────────────────────────────────────────────┘
```

> 「回退」「查看历史」按钮不再贴 textarea，统一进编辑器右侧「版本历史」tab 的时间线行内（§13.4 / Q166-Q167）；「废弃」「复制」「丢弃 DRAFT」「恢复」全部归入顶栏「⋮ 更多」菜单（§1.1）。

### 13.2 字段规格

| 项 | 规格 |
|---|------|
| 输入类型 | `<textarea>`（纯文本，**非** WangEditor） |
| 行数 | 默认 6 行高，自动增长，最多 20 行可见后内滚 |
| 长度限制 | 后端 `TEXT` 类型；前端软提示 ≥ 10000 字时给警告 |
| 占位提示 | `示例：本次更新调整了启动流程的步骤顺序，并新增 2 个测量点...` |
| 可编辑条件 | `is_current=true 且 status=DRAFT`（与 Q14 一致）|
| 只读态展示 | 灰色背景文本块，保留换行；点击可全屏查看 |
| 字段名 | `version_update_notes` |

### 13.3 保存

- 与程序基础信息一起在 `PUT /procedures/{id}` 提交
- 携带 `If-Match: <revision>` 头（Q18）
- 受 sessionStorage 自动保存（与 §7 一致）

### 13.4 版本历史时间线展示

> 权威决策见 [feature-clarifications.md §22.2（Q166）/ §22.3（Q167）/ §22.7（Q171）/ §22.8（Q172）](feature-clarifications.md#二十二版本管理-ui-流程q165q180)。

位置：编辑器右侧第三个 tab「版本历史」（§1.3）。

> 与审计日志分工（Q285）：本时间线只展示**版本里程碑**（publish/rollback/deprecate/restore + notes）；tab 内提供「查看完整审计」链接 → 跳全局审计页并预填本 group 过滤（§21 / §43）。字段级 CRUD diff / IP·UA 在审计页看，不在此。

形态：`created_at DESC` 倒序时间线，每行：

```
┌──────────────────────────────────────────────────────────┐
│ 版本历史 (按需展开任意行的完整 notes)                     │
├──────────────────────────────────────────────────────────┤
│ ● v3  [DRAFT 灰]   2026-05-19 14:32 by 张三              │
│   本次更新调整了启动流程的步骤顺序...                     │
│   [展开全文]                                              │
├──────────────────────────────────────────────────────────┤
│ ○ v2  [ARCHIVED 暗灰]   2026-05-15 09:10 by 李四          │
│   增加紧急停机检查项...                                   │
│   [展开全文]  [回退到此版本]  [🗑 删除此版本]              │
├──────────────────────────────────────────────────────────┤
│ ○ v1  [ARCHIVED 暗灰]   2026-05-10 08:00 by 李四          │
│   （未填写更新说明）                                       │
│   [回退到此版本]  [🗑 删除此版本]                          │
└──────────────────────────────────────────────────────────┘
```

行字段：

| 字段 | 说明 |
|------|------|
| `●` / `○` 标记 | `●` is_current=true；`○` 其他 |
| `v{N}` | 加粗 |
| status chip | 按 §1.1 表格配色 |
| operator + time | 例 `2026-05-19 14:32 by 张三` |
| notes 预览 | 前 100 字，超出截断 `...` |
| `[展开全文]` | 仅 notes 非空时显示；点击行就地展开 |
| `[📖 查看]` | 所有 `is_current=false` 行显示；跳 `/procedures/{id}/view` 只读视图（Q174）|
| `[回退到此版本]` | 仅满足 `status='ARCHIVED' AND is_active=true AND is_current=false` 时显示（Q167） |
| `[🗑 删除此版本]` | 同样的条件下显示（Q171）|

数据源：`GET /procedure-groups/{group_id}/versions`（默认全部加载，不分页）。

软删除版本（is_active=false）**不显示**在时间线（与 §13.5 列表过滤公式一致）。

按钮触发流程：

- **回退到此版本**：弹 reason modal → POST /procedures/{id}/rollback → 跳新版本编辑器 + 成功 banner（§9.3 / §9.4）
- **删除此版本**：弹 reason modal → DELETE /procedures/{id} body `{reason}` → 时间线移除该行（§11 错误处理对 PROCEDURE_IS_CURRENT 的兜底）

### 13.5 PDF 修订记录页

- `version_update_notes` 拼接到 PDF 修订记录页的「说明」列（[pdf-rendering.md §5.2](pdf-rendering.md)）
- 拼接顺序：`description + reason + version_update_notes`（任一为空跳过）

### 13.6 与 upgrade-version 的交互

- 升级版本时，新版本（v{N+1}）的 `version_update_notes` **不复制旧版**——初始为空（Q112 / §13.7）
- 用户进入新版本（DRAFT 态）后**自行填写**本次更新说明
- 发布（DRAFT → PUBLISHED）时：
  - **v1**（首版）：notes 为空 → 仅 warning，可发布（§22.14 / Q178）
  - **v2+**：notes 为空 → ✗ 阻塞，前端 publish 检查列表显示阻塞项；后端兜底返 `VERSION_UPDATE_NOTES_REQUIRED` 400

---

## 14. 导入向导（Q73–Q96）

> 详细决策见 [feature-clarifications.md §12](feature-clarifications.md#十二导入向导规范q73q96)。

### 14.1 5 步线性结构

| Step | 主区域 | 后退 | 取消 |
|------|--------|------|------|
| ① 上传 | 拖拽 / 点选 .docx；三档预警（20MB 提示 / 40MB 警告 / 50MB 拒绝）；非 .docx 拒接 | ✗ | 直接退出 |
| ② 模式 | radio: standard / smart（默认 smart） | ✓ | 直接退出 |
| ③ 报告 | standard: 8 条模板校验报告（error 拒、warning-only 二次确认）；smart: 解析概览（metadata + warnings + review 预告） | ✓ | 二次确认 |
| ④ 树审查 | 详见 §14.3 | ✓ | 二次确认 |
| ⑤ 表单 | name（默认文件名）+ folder_id（仅非系统） | ✓ | 二次确认 |

step indicator：Element Plus Steps；已完成步骤可点击跳回（同 Q74 行为）。

### 14.2 解析过程反馈

step1 → step2/3 过渡页：spinner + 「正在解析…」文字；后端 30s 超时返 `PARSE_TIMEOUT`，前端显示「文档过大或过复杂，建议拆分」。

### 14.3 step4 树审查可编辑范围

| 操作 | UI 表现 |
|------|--------|
| 改 title | 内联编辑 |
| 切换 skip_numbering | 节点行的「跳号」开关 |
| 删除节点 | **递归子树软删** + 二次确认「将删除 N 个章节」|
| 上移 / 下移 | 同 parent 内 sort_order 交换 |
| 「重置为初始解析」按钮 | 右上角；点击后弹「将清除 step4 的所有修改、恢复为初始解析结果；表单 (step5) 保留。是否继续？」|

**不可编辑**：rich_content、level、content_type（始终 chapter）。

**review 节点**：黄色边框 + 小 `?` 图标；hover 显示「智能解析识别不肯定，请核实」；不阻塞 step5；用户修改 title 后自动清 review。

### 14.4 状态持久化

- sessionStorage key：`procedure_import_wizard_v1`（含 createdAt 字段）
- step2-5 数据持久；.docx 文件**不存**（刷新需重新上传）
- 清理时机：提交成功 / 取消 / createdAt 距今 ≥ 24h

### 14.5 错误恢复

| 阶段 | 错误 | 处理 |
|------|------|------|
| 上传 | 网络中断 / 超时 | toast「上传失败，请重试」，留 step1 |
| 解析 | 网络 / 后端异常 / 30s 超时 | 跳 step3 错误页 + 「上一步」/「重试」按钮 |
| 提交 | 4xx / 5xx | 弹框显示错误码 + 中文 + 原始 message；留 step5；VALIDATION_FAILED 高亮字段 |

### 14.6 成功着陆

POST /procedures/import 成功 → 跳转 `/procedures/{new_id}` 详情页（DRAFT 态）。

---

## 15. 多 tab 同时编辑（Q129–Q132）

### 15.1 多 tab 同程序

**不主动检测**。两 tab 独立加载、各自编辑。冲突时后提交者拿 409 `VERSION_CONFLICT`，UI 弹「远程版本已变更，是否加载最新？」。

**不使用 BroadcastChannel**。

### 15.2 sessionStorage 隔离

key = `procedure_editor_${procedure_id}`。sessionStorage 本就按 tab 隔离，无需额外 tab_uid 后缀。

### 15.3 同 tab 切换程序的 beforeRouteLeave

```typescript
beforeRouteLeave((to, from) => {
  if (hasUnsavedChanges()) {
    return showConfirm({
      title: '未保存的修改',
      message: '本程序有未保存的改动，离开会怎么处理？',
      options: [
        { label: '保留（不离开）', value: 'cancel' },
        { label: '丢弃（清除草稿后离开）', value: 'discard' },
        { label: '取消', value: 'cancel' },  // 同保留
      ]
    })
  }
})
```

仅「丢弃」时清 `procedure_editor_${procedure_id}` 的 sessionStorage。

---

## 16. 自定义字段「已废弃字段」展示（Q133）

详情页表单分两区：

```
┌──────────────────────────────────────────┐
│ 自定义字段                                 │
├──────────────────────────────────────────┤
│ 风险类别:     [select 高/中/低]            │  ← status='active' 字段
│ 适用设备型号:  [text]                      │
│ ...                                        │
├──────────────────────────────────────────┤
│ ▸ 已废弃字段（点击展开）  共 N 个          │  ← 折叠区，默认收起
│   旧字段A: 历史值1     (灰色, 只读)        │
│   旧字段B: 历史值2     (灰色, 只读)        │
└──────────────────────────────────────────┘
```

- 折叠区源数据：`Procedure.custom_values` 中 key 不在当前 active ProcedureField 列表中的项
- 仅读，不可编辑
- 在审计 / PDF 中不出现

---

## 17. 编辑器主流程（Q153-Q164）

### 17.1 加载策略（Q153）

进入 `/procedures/{id}/edit` 时**一次拉全部**：

```
GET /procedures/{id}
→ {
    procedure: {id, code, name, version, status, is_current, description,
                risk_level, quality_level, custom_values, version_update_notes,
                revision, ...},
    chapters: [/* 嵌套树：chapter / content 节点 */],
    steps: [/* 平铺，前端按 chapter_id 挂载 */],
    attachments: [...],
    fields: [/* 所有 status='active' 的 ProcedureField */]
  }
```

- 单一 spinner 全屏，无骨架屏
- 失败 → 全屏错误页 + 重试按钮
- revision 进入 Pinia store 作为 If-Match 来源

### 17.2 保存策略（Q154）

**手动保存 + sessionStorage 防丢失**：

```
用户操作 (改 title / 移动节点 / 改 rich_content / 删除 / 切类型 / ...)
   │
   ▼ 全部进 Pinia store（dirty=true，节点级 track）
   │
   ├─→ sessionStorage 1s debounce 写入（防丢失）
   │
   ▼ 用户点「保存」按钮（或 Ctrl+S）
   │
   ▼ PUT /procedures/{id}（含所有 dirty 节点 + 程序级元字段）
     headers: If-Match: <revision>
   │
   ├─ 成功 → revision++、dirty=false、sessionStorage 清、顶栏「已保存」chip 2s
   └─ 失败 409 → 弹「远程版本已变更，加载最新？」
            其他失败 → 弹错误码 + 留 dirty
```

未保存离开 → §15.3 beforeRouteLeave 三选拦截。

### 17.3 节点切换 dirty 保留（Q155）

修改全部在 Pinia store。切换节点 = 切换详情面板显示的节点 id；store 中的 dirty 节点保留。顶栏「未保存」chip 只要任一节点 dirty 就显示。保存时一次提交所有 dirty 节点（含程序级元字段）。

### 17.4 publish 触发（Q156）

「发布」按钮（DRAFT + is_current 可见）→ 检查列表弹框：

```
✓ name 非空
✓ 至少 1 个 chapter
✓ folder 非「废止」
✓ 必填自定义字段「适用设备」已填
✓ version_update_notes 非空            ← 仅 v2+ 必填（Q178）；v1 不显示此项
✗ 有 3 个节点未保存修改 [一键保存]
✗ Step 1.2.3 未命名（仅 warning，不阻塞）
```

- 任一 ✗（除 warning）→ 「确认发布」按钮 disabled
- 全 ✓ → 「确认发布 v{version}」启用
- 提交 → POST `/procedures/{id}/transition` body=`{status: 'PUBLISHED'}` → 同 group 原 PUBLISHED 自动 ARCHIVED
- 后端兜底：v2+ 且 version_update_notes 空时返 `VERSION_UPDATE_NOTES_REQUIRED`（Q178 / §22.14）

### 17.5 upgrade-version 入口（Q157 / Q165 / Q173）

仅 `is_current=true AND status=PUBLISHED` 时显示「升级版本」按钮（替代「发布」按钮）。DRAFT / ARCHIVED 状态下不显示（Q173）。

点击 → 二次确认「将创建版本 v{N+1}，当前版本会被归档。是否继续？」（**不弹 reason 输入**）→ POST `/procedures/{id}/upgrade-version` → 跳 `/procedures/{new_id}/edit` + 成功 banner（详见 §9.2 / §9.4）。

### 17.6 历史版本只读查看（Q158 / Q174）

> 权威决策见 [feature-clarifications.md §22.10](feature-clarifications.md#2210-历史版本只读查看q174--q158-细化)。

入口：右侧「版本历史」tab 内每个 `is_current=false` 的行显示「📖 查看」按钮 → 跳 `/procedures/{old_id}/view`（注意路径后缀 `/view`，与 `/edit` 区分）。

**路由进入守卫**：用户访问 `/procedures/{id}/edit` 但记录不满足 `is_current=true AND status=DRAFT`（如 deprecated 整 group 的当前版本 status=ARCHIVED）→ 路由守卫 `router.replace('/procedures/{id}/view')`（不留历史，避免假可编辑态）。

read-only 模式细则：

- 顶栏正下方黄底 banner（不可关闭）：`正在查看历史版本 v{K}（已归档于 {archived_at}）。`
- 顶栏主动作按钮组**完全隐藏**（保存 / 发布 / 升级版本 / 应用标记 / 撤销重做全部不显示）
- 顶栏右侧仅保留：「PDF 下载」按钮 + 「返回当前版本」按钮（跳 `/procedures/{current_id}/edit`）
- 所有输入框 / WangEditor `readonly` / `disabled`
- 右侧 tab 保留三个全部（节点详情 / 附件 / 版本历史）；版本历史 tab 中仍可继续切其他历史版本
- 「⋮ 更多」菜单仅保留「复制为新程序」（复制源 = 当前查看的历史版本）
- 行内 rollback / delete 按钮**仍在版本历史 tab 中**（满足条件的行）；不在 ⋮ 菜单

### 17.7 大型程序性能（Q159）

| 优化点 | 触发 |
|--------|------|
| 章节树虚拟滚动 | 节点数 > 50 启用（vueuse `useVirtualList` 或 Element Plus el-tree-v2）|
| WangEditor 按需实例化 | 仅选中节点时创建实例；切换节点销毁原实例 |
| 仅提交 dirty 节点 | 保存时遍历 store dirty set，只发改过的 |
| sessionStorage debounce | 改一次写一次（debounce 1s），避免抖动 |
| 节点详情面板 v-if 切换 | 不同 type 的 panel 用 v-if 而非 v-show 释放内存 |

### 17.8 编辑器内搜索（Q160）

树顶部固定搜索框：

- 输入实时（debounce 200ms）过滤章节树
- 匹配 chapter.title / step.title / content.rich_content 纯文本前 100 字
- 匹配节点高亮；匹配节点的 ancestor 路径保留可见；其他节点隐藏
- 清空 → 恢复完整树
- 快捷键 `/` 聚焦搜索框
- 不影响 store 状态、不影响 dirty

### 17.9 键盘快捷键（Q164）

| 快捷键 | 行为 | 作用域 |
|--------|------|------|
| `Ctrl+S` (Mac: `Cmd+S`) | 保存 | 全局，阻止浏览器默认行为 |
| `Ctrl+Z` / `Cmd+Z` | 撤销 | 编辑器内，非输入框 focus 时 |
| `Ctrl+Shift+Z` / `Cmd+Shift+Z` | 重做 | 同上 |
| `Delete` / `Backspace` | 删除选中节点（二次确认）| 章节树选中节点时 |
| `/` | 聚焦搜索框 | 全局，非输入框 focus 时 |
| `Esc` | 关闭最上层 dialog / 弹层 / 退出标记模式 | 全局 |
| `?` | 弹出快捷键帮助 | 全局（参考） |

WangEditor 内的输入交互优先级 > 全局快捷键（避免冲突）。

### 17.10 丢弃 DRAFT（Q175）

> 权威决策见 [feature-clarifications.md §22.11](feature-clarifications.md#2211-draft-丢弃入口q175)。

入口：编辑器顶栏「⋮ 更多」菜单中的「丢弃此 DRAFT」。显示条件：

```
is_current=true AND status='DRAFT' AND version > 1
```

v1 DRAFT 不显示此入口。

```typescript
async function discardDraft() {
  const { reason, confirmed } = await openDiscardDraftModal({ version: current.version })
  if (!confirmed) return

  // DELETE 在 DRAFT 特殊路径下直接返新 current 信息（api-spec L163）
  const { new_current_id, new_current_version } = await http.delete(`/procedures/${pid}`, {
    body: { reason },
  })
  router.push(`/procedures/${new_current_id}/edit`)
  toast.success(`已丢弃 DRAFT v${current.version}，已回到 v${new_current_version}`)
}
```

modal 文案：

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

---

## 18. 后续待补

| 项 | 触发时机 |
|----|---------|
| 多 tab 同时编辑同一程序的协调（broadcast channel）| **按设计不做（Q335）**：乐观锁 409 + per-tab sessionStorage 仲裁 |
| 实时协作编辑 | 远期，不立项 |
| 离线编辑 | 不在范围 |
| 编辑器自动保存到后端（不仅 session）| **按设计不做（Q336）**：显式保存 + sessionStorage 恢复 |

## 19. 程序配置与文件夹设置（§33 / §36–§39）

> 权威决策见 [feature-clarifications.md §36–§39](feature-clarifications.md)（Q242–Q260）+ §33（Q230–Q233）。

### 19.1 全局设置页（Q260）

路径：设置入口 →「全局设置」。单页表单：

| 控件 | 字段 | 说明 |
|------|------|------|
| 开关 | `enable_approval_workflow` | 审批模式（Q242）；ON 时发布区显示「审批模式已开启（模块待上线）」徽标（Q245 / §9.1），本期不阻断发布 |
| 数字 | `max_version_number` | 版本上限（默认 100，Q222）|
| 开关 | `require_read_confirmation` | 是否强制 mark-read（B2）|
| 下拉 | `default_risk_level` | 1–5 文字分级（低/中-低/中/中-高/高 + 色块，Q52/Q260），默认 1 |
| 下拉 | `default_quality_level` | 1–5 文字分级，默认 1 |

- **隐藏**：`enable_version_control`（Q232）、`auto_archive_days`（Q259 待 Phase 9）。
- 保存：**二次确认对话框 + 写审计**（Q233）；PUT /settings 带 If-Match。

### 19.2 自定义字段管理子页（Q253–Q258）

路径：设置 →「自定义字段」子页。

- 列表：name / key / 类型 / 必填 / 状态 / 上封面（show_on_cover）；拖拽排序（sort_order）。
- 增删改弹窗：
  - `name`（中文显示名）、`key`（手填英文 小写字母 / 数字 / 下划线，**创建后不可改**，Q254）、`field_type`（text/number/date/select/multi_select/checkbox/textarea）。
  - `required` 开关（改为 required **不追溯**历史，仅新建 + DRAFT 保存校验，Q256）。
  - **校验规则表单化**（必填 / 最小值 / 最大值 / 最小长度 / 最大长度 / 正则）→ 后端转标准 JSON Schema（Q253 / Q-C6）。
  - select / multi_select 的 `options`：增删改 + 单项归档。
  - `show_on_cover` 开关（Q257）：勾选则上 PDF 封面元数据区。
- 归档字段 / 选项：**已填值保留只读、新建 / 编辑不再出现**（Q255）；程序编辑页「已废弃字段」折叠区展示旧值（§16 / Q133）。

### 19.3 文件夹配置 + 文件夹管理（Q246–Q251）

- 前端「文件夹配置」导航 = `system=false` 文件夹树（Q246）；「废止」等 `system=true` 单列。
- 文件夹 CRUD 沿用 B9 / Q22 / 5 级深度：
  - **容器 xor 叶子**（Q247）：仅叶子能存程序；含程序的文件夹「新建子文件夹」入口禁用（后端兜底 `FOLDER_HAS_PROCEDURES`）。
  - 叶子建 / 改弹窗：`prefix` 必填非空（Q248）+ 实时 `check-prefix`（含历史 code 占用，Q249，命中 `FOLDER_PREFIX_DUPLICATE`）；`sequence_digits` 可配默认 5（Q250）；无重置周期配置（Q251）。
  - 中间容器：无 prefix / 序列输入。

### 19.4 新建程序选文件夹（Q252）

新建程序表单「文件夹」字段 = **搜索下拉**：

```
┌─ 文件夹（必填）────────────────────────┐
│ [🔍 搜索文件夹...]                       │
│ ▸ 质检 / 检验流程 / 来料检验   QC        │
│ ▸ 生产 / 装配 / 总装线         AS        │
│   （仅列叶子，中间容器不可选）            │
└────────────────────────────────────────┘
选定后预览：将生成编码 QC-00001
```

- 输入关键词过滤匹配的**叶子**文件夹，显示完整路径 + prefix；中间容器不可选。
- 选定后**预览将生成的 code**（`{prefix}-{下一序号}`，Q252）。
- 后端 POST /procedures 仅接受 `system=false` 叶子 folder_id（Q247）。

## 20. 程序库列表页（§41）

> 权威决策见 [feature-clarifications.md §41](feature-clarifications.md)（Q266–Q277）。核心日常入口。（注：§40 / Q261–Q265 为并行会话「步骤执行表单」，本节让号 §41 / Q266–Q277。）

### 20.1 布局（Q266/Q269）

```
┌──────────────┬────────────────────────────────────────────┐
│ 文件夹配置    │  质检 / 检验流程 / 来料检验    [+ 新建程序] │
│ ▾ 质检       │ ┌────────────────────────────────────────┐ │
│   ▾ 检验流程 │ │ ☐ code     name     版本 状态 用途 更新 ⋮│ │
│     来料检验⁵│ │ ☐ QC-00001 进料检验 v2▸3 已发布 连续 …  │ │
│   出货检验   │ │ ☐ QC-00002 抽样SOP  v1   草稿  参考 …   │ │
│ ▸ 生产       │ └────────────────────────────────────────┘ │
│ ──────────   │  [🔍搜索][状态▾][排序:更新时间▾]   〈分页〉 │
│ 🗑 废止       │                                            │
└──────────────┴────────────────────────────────────────────┘
```

- 左：文件夹配置树（`system=false`，节点带 `procedure_count` 角标 A12）；点叶子 → 右列表。
- 「废止」**树外独立入口**（Q269），点它列已废弃 group（§22.16 行 UI）。
- 右：程序列表，顶部面包屑 + 操作区。

### 20.2 数据与列（Q267/Q270）

- 拉取：`GET /procedures?folder_id=&status=&search=&sort=-updated_at&page=&page_size=`；**每 group 一行**（is_current 版本），derived `version_count_in_group`。
- 列：code / name / 版本（`v{version}` + `▸{count}` 徽标）/ status 徽标 / 用途级别 / 更新时间 / ⋮。
- **跨文件夹搜索**命中时加「路径」列显示 `folder_full_path`。

### 20.3 过滤 / 排序 / 分页（Q268/Q274）

- 过滤：左树选文件夹 + status 多选 + 搜索框（不新增其它过滤项）。
- 排序：更新时间（默认 desc）/ code / name（`sort` 参数，§3.2 通用约定）。
- 分页：页码 + 每页 20 / 50 / 100（默认 20）。

### 20.4 行交互（Q271/Q272）

- 点行（非 ⋮ 区）→ `/procedures/{id}/view` 只读详情（§22）。
- ⋮ 菜单（按状态动态）：编辑（is_current+DRAFT）/ PDF 下载 / 复制为新程序 / 升级版本（is_current+PUBLISHED）/ 废弃整 group / 删除 / 查看版本历史。

### 20.5 批量操作（Q273）

- 行首多选 → 顶部批量条：删除（`POST /procedures/batch-delete`）/ 移动到文件夹（`POST /procedures/batch-move`，目标=叶子文件夹搜索下拉 Q252）。
- 批量删除二次确认。

### 20.6 新建程序（Q276）

双入口：右上「+ 新建程序」+ 左树叶子悬浮「+」。弹窗：

```
┌─ 新建程序 ──────────────────────────┐
│ 文件夹*  [🔍 质检/检验流程/来料检验] │  ← Q252 搜索下拉，预填当前叶子
│          将生成编码: QC-00006        │  ← code 预览
│ 名称*    [____________________]      │
│ 用途级别* [连续使用 ▾]               │  ← Q182 必填
│ 描述     [____________________]      │
│              [取消]  [创建并编辑]     │
└──────────────────────────────────────┘
```

- **新建恒空白程序**（`POST /procedures`）：模板与模板库均已废（§56/Q340）。要"套结构"= 去任意现有程序行 / 编辑器 `⋮ → 复制为新程序`（§18/Q179）。
- risk / quality 取 settings 默认（Q260），进编辑器再调；创建后跳 `/procedures/{newId}/edit`。

> **模板库已废除**（§56/Q340）：不再有「📋 模板库」文件夹 / 维护入口 / 样板程序。新建恒空白；模板需求由"复制现有程序"（§18/Q179）满足。唯一系统文件夹 =「废止」。

### 20.7 空状态（Q275）

| 场景 | 文案 | CTA |
|------|-----|-----|
| 文件夹无程序 | 该文件夹暂无程序 | + 新建程序 |
| 搜索无结果 | 未找到匹配「{q}」 | 清除搜索 |
| 全库为空 | 还没有任何程序 | 新建文件夹 / 新建程序 |

### 20.8 已读显示（Q277）

- `require_read_confirmation=true`：列表加「已读 / 未读」圆点指示 + 「待阅读」快捷筛选（`GET /procedures/pending-read`）。
- `false`：不显示已读相关 UI。

### 20.9 程序库搜索（§42 / Q278–Q283）

> 与编辑器内**章节树**搜索（§17.8 / Q160，单程序内）不同，这是**程序库**搜索。

- **覆盖**（Q278）：`code` + `name` + `description` 子串（后端 `LIKE`，无全文索引）；不搜章节 / 步骤正文。
- **跨全库**（Q279）：输入即忽略左树文件夹、跨全库搜，结果显示「路径」列；清空回到当前文件夹视图。
- **范围**（Q280）：仅匹配各 group 的 is_current 版本，结果每 group 一行。
- **语义**（Q281）：大小写不敏感子串、多词空格 AND、无相关性排序（按 `sort`）。
- **呈现**（Q282）：`name` / `code` 命中 `<mark>` 高亮；`description` 命中显示 ±N 字 snippet。
- **输入**（Q283）：实时 debounce **300ms** + `×` 清除 + ≥1 字符触发。

## 21. 审计日志查看页（§43）

> 权威决策见 [feature-clarifications.md §43](feature-clarifications.md)（Q284–Q289）。受控文档合规追溯；区别于版本历史时间线（§13.4，版本里程碑）。

### 21.1 入口（Q284 / Q285）

- **全局页**：顶栏 `⚙` 菜单 →「审计日志」，单一视图（§50 Q321：审计归管理类、入 ⚙；非侧栏）。
- **对象深链**：程序 / 文件夹详情的「查看此对象审计」→ 跳全局页并预填过滤（程序 `procedure_group_id`、文件夹 `target_id`）。
- 版本历史 tab（§13.4）的「查看完整审计」链接亦走此深链。

### 21.2 过滤（Q286）

`GET /audit-logs/{procedures|folders}` 全部过滤：action（多选）/ 时间范围 / 对象（group 或 target）/ IP / 分页（§5.9）。

### 21.3 列表与字段级 diff（Q287）

```
时间                动作      对象           摘要               IP        
2026-05-20 10:23   update    QC-00001 程序  name: A→B          10.0.0.5  ▸
2026-05-20 09:50   rollback  QC-00001 程序  回退至 v2(原因…)   10.0.0.5  ▸
   └─ 展开：字段级 diff 表  | 字段 | 旧值 | 新值 |
                          | name | A    | B    |
```

- 行：时间 / 动作 / 对象+类型 / 一句话摘要 / IP·UA / 展开箭头。
- 展开：`old_value`/`new_value` 渲染为 `字段 | 旧值 | 新值` 表。
- 批量（`{ids, count}`）显示「影响 N 项」+ ids；`reason`（rollback/deprecate/restore/delete）行内显著。

### 21.4 导出（Q288）

「导出当前过滤结果」→ `GET /audit-logs/{...}?export=csv`（同过滤、流式 CSV、忽略分页）。

### 21.5 权限（Q289）

无登录、**任何人只读查看**；审计只读、不可改不可删（永久保留）。

## 22. 附件上传与管理（§45）

> 权威决策见 [feature-clarifications.md §45](feature-clarifications.md)（Q294–Q299）。后端 / 限制 / 端点已齐全（[api-spec §5.5](api-specification.md) / [data-model §3.6](data-model.md)），本节定前端 UX。

### 22.1 位置（Q294）

编辑器右侧「附件」tab（与 节点详情 / 版本历史 / 审计 并列，§1.3）；附件挂 **procedure 版本**（非章节 / 步骤）。

### 22.2 上传（Q295）

- 拖拽放置区 + 点选按钮；多文件队列、逐文件进度条、失败可重试 → `POST /procedures/{id}/attachments`（multipart `file` + 可选 `description`）。
- **仅 `is_current + DRAFT` 可上传**（Q228）；否则 tab 只读（仅下载 / 预览）。

### 22.3 限制反馈（Q296）

上传前前端预校验 + 即时提示：单文件 ≤ **50MB**、单版本 ≤ **30 个**、总 ≤ **200MB**（Q120，超限 `ATTACHMENT_LIMIT_EXCEEDED`）；不限制类型（任意 MIME，Q226）。

### 22.4 列表 / 管理（Q297）

```
📎 附件（DRAFT 可编辑）                    [拖拽文件到此 / 点选上传]
┌──────────────────────────────────────────────────────────┐
│ ⠿ 🎬 装配演示.mp4  18MB  2026-05-20  [说明…] [下载][删除]      │
│ ⠿ 📄 检验记录.pdf   1MB  2026-05-20  [说明…] [下载][预览][删除] │
└──────────────────────────────────────────────────────────┘
```

- 行：类型图标 / `file_name` / 大小 / 上传时间 / `description` / 操作。
- 操作：下载 / 预览（白名单）/ 编辑描述 / 拖拽排序（`sort_order`）/ 删除（二次确认）。
- 只读态（非 is_current+DRAFT）仅留下载 / 预览；同名文件允许并存（Q119）。

### 22.5 预览（Q298）

白名单（png/jpg/gif/webp/pdf）显示「预览」入口 → 模态 / 抽屉内联（`GET /attachments/{id}/preview`，`inline`）；非白名单仅下载（Q229）。

### 22.6 与 step.attachment_marks 区分（Q299）

本 tab = **程序级真文件附件**（`tb_procedure_attachment`）；step.attachment_marks（§4.1 / Q203/Q220）= **步骤级纯标记**（文件名 + kind，不校验文件），在 step 面板。二者独立、互不耦合。

## 23. 已读确认（mark-read）流程（§46）

> 权威决策见 [feature-clarifications.md §46](feature-clarifications.md)（Q300–Q304）。复用 B2 既有字段 / 端点，无新增。

### 23.1 标记入口（Q300）

`is_current` + `PUBLISHED` 程序的只读视图（`/procedures/{id}/view`）顶部：`is_read=false` → 显「标记已读」按钮 / banner → `POST /procedures/{id}/mark-read`；标记后转「✓ 已读 {read_at}」。DRAFT / ARCHIVED 不显示。

### 23.2 require_read_confirmation 语义（Q301）

- `=true`：未读生效版顶部**黄条「请确认已读」**（强提示）+ 全局「待阅读(N)」入口；**不阻断任何操作**（"强制"=强提示，无登录无可阻断动作）。
- `=false`：静默，仅保留可选手动「标记已读」，不提示、不显待办。

### 23.3 范围与全局语义（Q302）

仅 is_current+PUBLISHED 可标记；`is_read` **全局单标志**（任何人点击即全局已读），`read_at` 记最后标记时间、不记人；一次即已读，不提供取消。

### 23.4 新版本自动重置（Q303）

发布新版本 → 新记录 `is_read=false`，生效版自动回「未读」、重新进入待阅读；旧 ARCHIVED 版 `is_read` 不变。无需额外机制。

### 23.5 待阅读入口（Q304）

`require_read_confirmation=true` 时：全局导航「待阅读」入口 + 计数徽标（`GET /procedures/pending-read`）+ 列表「待阅读」筛选（§20.8 / Q277）。`=false` 不显示。
