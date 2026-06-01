# 步骤类型语义层 + 工单挂载移动端执行 — 设计文档

- 日期：2026-06-01
- 状态：设计草案，待评审（实施计划另立）
- 关联背景：SOP 将挂载到**工单**并在**移动端执行**。本设计把系统从「编写 + PDF + 版本」（CBP Type 1）升级为可在现场执行的电子工作包 eWP（CBP Type 2 / PPA Moderate）。
- 理论依据：《基于人因工程的程序设计》第 4、6 章——7 类标准步骤类型（§6.5.4）、NCW 三级体系与强制可见（第 4 章 + 原则九）、自动占位（原则一）、Active Step（原则二）、决策分支 Worker-in-the-Loop（原则七）、通讯自动化（原则八）、ePE/eWP（§6.8）。INL 四电站量化收益：步骤遗漏 -75~100%、分支错误 -80%、占位遗忘 -86%、数据错误 -71%。

---

## 1. 目标与背景

### 1.1 核心问题

当前「步骤字段」由 `input_schema.type` 的 **15 型 FormType**（[types/node.ts:8](../../../frontend/src/types/node.ts)）单一枚举承担，它同时压平了三层语义：

| 现有 FormType | 实际语义 | 对应书中概念 |
|---|---|---|
| NUMBER/METER/CHECKBOX/RADIO/DATE/UPLOAD/PHOTO | 数据采集控件 | Data 步骤 |
| CHECK/YESNO | 完成确认 | Action 步骤 |
| SIGNATURE | 签字 | Hold 步骤的签字屏障 |
| NOTE/CAUTION/WARNING | 富文本警示框 | NCW（非步骤，是屏障） |
| COMMON/NONE | 操作说明 / 无记录 | Action / Information 步骤 |

**结论**：15 型在「采集什么数据」维度上已覆盖甚至超过书中 Data/Action/Information；但它**结构上无法表达「这一步对执行流程做什么」**——Decision 的分支跳转、Wait 的计时、Hold 的门控、Link 的跳转返回，这些是流程控制，不是字段。

### 1.2 为什么移动端执行必须补这一层

桌面 PDF / 纸质上，执行者一眼看到整页、自己翻页判断分支；**移动端屏幕只能显示一个当前步骤（Active Step），"下一步给谁看、能否往下、要不要等、谁来批准"必须由系统替执行者决策**。系统要替他决策，就必须知道每步的流程语义——这正是 `step_type`，而 15 型里没有它的位置。

> 没有 `step_type`，移动端执行会退化为「可滚动的长表单」（屏幕上的 PDF，CBP Type 1），INL 量化的收益一个都拿不到。

### 1.3 设计取向（已与干系人确认）

**不推倒 15 型重排**，而是：

1. 15 型**保留**为 Data/Action 步骤的采集控件（系统强项，不动）；
2. **新增 `step_type` 语义层**（7 类）驱动呈现 / 执行行为 / 流程控制；
3. 把 NCW（NOTE/CAUTION/WARNING）从 `input_schema` **归位**为独立节点本性；
4. 价值集中投到 4 个流程控制类型（Decision/Wait/Hold/Link）+ NCW 强制确认 + 移动端/工单运行时；Data/Action **不做无谓重命名**。

---

## 2. 范围

### 做（In scope）

**编写侧（authoring）**
1. 数据模型新增 `step_type` 枚举 + `step_config`（流程控制只读参数）。
2. 节点本性扩展：章节 / 正文 / 步骤（带 step_type）/ **警示 NCW**。
3. `NodeDetailPanel.vue` 两级编辑：选 step_type → 按类型显示对应配置 / 收窄采集控件下拉 / 锁定非法组合。
4. 解析器（`structurer.py`）启发式推断 step_type，并按类型推导起始 `input_schema`。
5. NCW 同页强制可见的 PDF 分页约束。

**执行侧（execution，工单挂载 + 移动端）**
6. 执行记录数据模型（占位 / 时间戳 / 签字身份 / 分支选择）。
7. 工单挂载关系 + eWP 路由通知（Hold 批准、数据异常推送）。
8. 移动端按 step_type 的运行时行为（见 §6）。

### 不做（Out of scope，YAGNI）

- Data/Action 的 15 型重命名 / 强制迁移（保持现状）。
- CBP Adaptive 级（实时 DCS 数据驱动步骤）——超出 Type 2 范围。
- CCV 正确部件验证（扫码 / RFID）——独立后续 epic。
- 并行步骤卡片、循环计数器（§6.4 特性 3/7）——本期 Decision/Wait/Hold/Link 优先。
- 工单系统本体（假定外部已有，本设计只做挂载契约）。

---

## 3. 数据模型设计

### 3.1 三种「字段」必须分清（融合的核心边界）

| 性质 | 谁产生 / 何时 | 存哪 | 例 |
|---|---|---|---|
| **采集字段** capture | 执行者运行时填 | `input_schema`（现状不动） | 读数、备注、勾选 |
| **配置参数** config | 作者编写时设、执行只读 | **新增 `step_config`** | Wait 时长、Link 目标、Decision 分支映射 |
| **执行痕迹** trace | 执行态产生 | **新增执行记录表** | 占位、时间戳、签字人、分支选择 |

> 三者绝不可混存一处：把 Hold 的签字塞进普通 `input_schema` 文本，就丢了身份认证 / 不可篡改（违背 §6.5.5 三层签字屏障）；把 Wait 时长当采集字段，执行者会以为要手填。

### 3.2 `ProcedureNode` 变更（[models/node.py](../../../backend/app/models/node.py)）

```text
step_type   : str|null   新增。kind='step' 时取 7 类之一；NCW 节点取 'notice'；其余 null
                         枚举：action|data|decision|wait|information|hold|link|notice
step_config : JSON        新增。流程控制只读参数（见 §3.4）。仅相关类型非空
notice_level: str|null    新增。step_type='notice' 时：note|caution|warning
input_schema: JSON        不变。仅 step_type='data'（及 action 的确认）使用
```

`kind` 保留（node/step），`step_type` 是 step 内部的细分；NCW 作为新本性，落地时可用 `step_type='notice'` 表达（避免再加一个顶层 kind 值，复用既有 step 通道但语义独立）。

### 3.3 `step_type` 与现有 15 型的映射（迁移无损）

| 现有 input_schema.type | step_type | 残留 input_schema | notice_level |
|---|---|---|---|
| NUMBER/METER/CHECKBOX/RADIO/DATE/UPLOAD/PHOTO | data | 原样保留 | — |
| CHECK/YESNO | action | 转「完成确认」 | — |
| SIGNATURE | hold | 保留 hint，门控默认 off（保守） | — |
| COMMON | action | 富文本 | — |
| NONE | action（无记录） | 空 | — |
| NOTE/CAUTION/WARNING | notice | — | note/caution/warning |

迁移脚本仅读 `input_schema.type` 即可推导，无歧义。

### 3.4 `step_config` 各类型结构

| step_type | step_config 关键字段 | 说明 |
|---|---|---|
| decision | `branches: [{option, target_node_id}]` | 每个选项绑定跳转目标 |
| wait | `mode: timer\|condition`、`duration_sec`、`condition_text` | 定时或条件等待 |
| hold | `gated: bool`、`approver_role`、`require_signature: bool` | 门控 + 批准角色 |
| link | `target_procedure_id`、`target_node_id`、`return_to_origin: bool` | 跳转并返回 |
| notice | （用 notice_level + body） | 强制确认见 §5/§6 |
| data/action/information | 空 | 用 input_schema / 纯文本 |

### 3.5 执行记录数据模型（执行侧）

新增执行实例与逐步痕迹（详细字段在实施计划展开）：

- **ExecutionRun**：work_order_id、procedure_id、procedure_revision（快照绑定版本，单一数据源）、executor、status、started_at、completed_at。
- **ExecutionStepRecord**：run_id、node_id、step_type、`completed_at`（秒级时间戳）、`completed_by`、采集值（对应 input_schema）、`decision_choice`、`signed_by` + 身份认证、`acknowledged`（NCW 强制阅读）。完成标记**不可逆**（回退需监督员权限，原则一）。

---

## 4. 编写侧前端设计（`NodeDetailPanel.vue`）

现状：[NodeDetailPanel.vue:127](../../../frontend/src/components/editor/NodeDetailPanel.vue) 有「作为步骤」开关，[:152](../../../frontend/src/components/editor/NodeDetailPanel.vue) 有 15 型下拉。改造为两级：

### 4.1 一级：节点本性
顶部把「作为步骤」开关升级为本性选择：`正文 / 步骤 / 警示(NCW)`。
- 选 **警示** → 仅显示 notice_level（注意/小心/警告，复用 `ALERT_TYPES` 色条）+ 富文本，**不显示任何采集表单**。
- 选 **步骤** → 出现 step_type 一级下拉。

### 4.2 二级：step_type 下拉（7 类，带色条 + 图标）

| step_type | 色条 | 选中后配置区 |
|---|---|---|
| action 执行 | 灰 | 完成确认：无 / 通过-不通过(CHECK) / 是-否(YESNO) |
| data 记录 | 紫 | 直接展开现有 `StepFormFields`（采集控件下拉**收窄**到 NUMBER/METER/CHECKBOX/RADIO/DATE/UPLOAD/PHOTO），近零改动复用 |
| decision 判断 | 青 | 分支选项列表，每项绑定**跳转目标节点** |
| wait 等待 | 蓝 | 等待方式：定时(时长+单位) / 条件(文本)，标注只读配置 |
| information 信息 | 灰 | 配置区**锁死隐藏**，仅富文本 |
| hold 暂停 | 橙 | 门控开关 + 批准角色 + 签字要求(复用 SIGNATURE) |
| link 跳转 | 蓝 | 目标程序/章节选择 + 返回原位开关 |

### 4.3 约束、默认与切换确认

- **默认预填**：选 data→`input_schema.type='NUMBER'`；hold→`SIGNATURE`+门控 on；action→`COMMON`。
- **非法拦截**：information 隐藏采集控件；data 若控件清空，保存校验报错「记录步骤至少需一个采集控件」。
- **采集下拉收窄**：data 类型下拉不再出现 WARNING 等——这是边界划分在 UI 的直接体现。
- **切换清空确认**：复用现有 [onTypeChange](../../../frontend/src/components/editor/NodeDetailPanel.vue) 的 `ElMessageBox`，切到不兼容类型时弹确认并重置 step_config / input_schema。

### 4.4 呈现联动

- `NodeTreeRow.vue`：行首显示 step_type 色条 + 图标（建立 §6.5.4 视觉-行为条件反射）。
- `FormFieldPreview.vue` / `EditorPreviewPane.vue`：hold 红框门控提示、wait 倒计时占位、notice 强制可见框。

---

## 5. 解析侧（`structurer.py`）

- 启发式推断 step_type：含「记录/填写/读数」→data；「如果…则/是否」→decision；「等待/保持 N 分钟」→wait；「警告/注意/CAUTION/WARNING」→notice(对应 level)；「批准/会签/暂停」→hold。
- 推断后按类型推导起始 input_schema / step_config，命中存疑 → 维持现有 `mark_status='review'` 通道交人工确认。
- 保守原则（对齐原则三 NA 判定）：不确定时归 action，由作者改判，不臆造分支/门控。

---

## 6. 执行侧：移动端按 step_type 的运行时行为（价值所在）

移动端一次显示一个 Active Step（原则二），完成即自动占位推进（原则一），断网可续接（§6.4 特性 4）。各类型行为：

| step_type | 移动端运行时行为 | 15 型为何做不到 | 收益 |
|---|---|---|---|
| **data** | 输入即时范围校验、必填不填不放行、值回灌工单/CMMS | NUMBER min/max 已能做（本就强项） | 转录错误 -71%、漏记 -89% |
| **action** | 完成勾选 + 时间戳 + Continuous Use 门控（未标记不能进下一步，§6.5.3） | CHECK 无「门控」语义 | 步骤遗漏 -75~100% |
| **decision** ⭐ | 选分支后**自动跳到对应步骤、隐藏 NA 分支** | RADIO 记下选择但运行时无处读「选项→目标步骤」，手机上只能手动滚 100 步 | 分支错误 -80% |
| **hold** ⭐ | **硬门控**：到此拦截，自动推批准请求给监督员手机，远程电子签字+身份认证后解锁 | SIGNATURE 仅采集签名，无门控/远程路由/身份认证 | 监督员无需到场（原则八） |
| **wait** | 倒计时，到点震动/自动推进，可收起手机 | 15 型无时长概念，只能盯表 | 取代人工计时，防早退/遗漏 |
| **link** | 跳转关联程序/图纸后**一键回原位** | attachment_marks 是静态标记，无跳转返回 | 上下文不丢（原则五） |
| **notice(NCW)** | 强制可见，Warning 必须点「我已阅读」才继续 | NOTE/WARNING 仅彩色框，无强制确认门控 | 防小屏「扫读跳过」（原则九） |

---

## 7. 工单挂载（eWP）集成

- **挂载契约**：工单引用 `procedure_id + revision`（绑定快照版本 = 单一数据源，§6.5.1）。一个工单可挂多份 SOP。
- **路由通知（原则八）**：hold 到达 → 推批准给 approver_role；data 超限 / 必填漏填 → 推工程师。
- **数据回流**：data 采集值随工单结构化回流设备台账，消除二次转录。
- **进度透明（解 Scheduling 痛点）**：上报结构化进度（「卡在第 3 个 Hold 点等批准」），非「滚动 60%」。

---

## 8. 分期落地

| 阶段 | 内容 | 产出 |
|---|---|---|
| **P0 叠加（不破坏）** | 新增 `step_type` 与 15 型并存联动；只驱动色条/图标 + 解析推断 + NCW 同页 PDF | 编写侧拿到 7 类语义，零迁移 |
| **P1 流程控制建模** | step_config + decision/wait/hold/link 编写 UI + 校验 | 流程语义可编写 |
| **P2 执行记录 + 移动端** | ExecutionRun/StepRecord、移动端 Active Step / 占位 / 门控 / 倒计时 / 强制确认 | 移动端可执行 |
| **P3 工单挂载 + eWP** | 挂载契约、路由通知、数据回流、进度上报 | 工单驱动执行闭环 |
| **P4 归位迁移（可选）** | NCW 独立、采集下拉按类型收窄、存量数据迁移（§3.3） | 模型彻底分层 |

P0 先行验证价值且零风险；执行态价值在 P2/P3 兑现。

---

## 9. 验收（按阶段）

- **P0**：step_type 写入/读出；树与预览显示色条；解析推断命中存疑入 review；NCW 与被保护步骤 PDF 同页；后端 step schema 不拒新键；前端门禁（lint/typecheck/build/vitest）通过。
- **P1**：decision 分支目标可配且校验非空；hold 门控/角色可配；wait/link 配置完整；切换类型清空确认正确。
- **P2**：移动端单步呈现 + 自动占位 + 不可逆完成 + 断网续接；hold 拦截、wait 倒计时、decision 自动跳转、NCW 强制确认按 §6 表现；执行痕迹含秒级时间戳 + 签字身份。
- **P3**：工单挂载绑定 revision；hold 远程批准走通；data 值回流；进度结构化上报。

---

## 10. 风险与缓解

- **范围大、跨前后端 + 移动端**：严格分期，P0/P1 编写侧先落地、可独立交付；执行态 P2/P3 单独立项。
- **存量数据**：P0/P1 不迁移（叠加并存）；P4 才做归位，迁移脚本按 §3.3 无损映射，先灰度。
- **后端 input_schema 子键校验**：实施首步核查 [schemas/node.py](../../../backend/app/schemas/node.py) 与 step 校验是否拒未知键（参考 step-field-preview 设计同款风险）。
- **门控/不可逆占位的紧急回退**：须配套监督员授权回退流程（原则一设计约束），否则现场卡死。
- **监管/签名法律效力**（若用于受监管场景）：电子签名 + Flattened 归档（§6.5.11）另行评估，不阻塞 P0~P2。
- **移动端离线**：弱网/屏蔽区需本地缓存 + 续接 + 冲突合并策略（§6.4 特性 4）。
