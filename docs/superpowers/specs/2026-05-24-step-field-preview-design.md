# 步骤表单字段预览 + 补齐缺失类型配置 — 设计文档

- 日期：2026-05-24
- 状态：已通过 brainstorming 设计评审，待写实施计划
- 关联评估：SmartSOP 相对 DPMS V2.0 唯一明显落后的维度为「步骤预览」（0% 实装）。本设计对标 DPMS `StepInputDisplay`，补齐**表单字段级**只读预览，并顺带补全缺失的类型配置 UI。

## 1. 目标与背景

当前编辑器（`StepDetailPanel.vue`）只能**配置** `input_schema`，无法**预览**该表单在执行时长什么样；用户需脑补效果。DPMS 通过 `StepInputDisplay.vue`（按 `inputType` 的 v-if 分支）做到了所见即所得。

本设计补齐这一短板：新增单文件分发预览组件，按 `schema.type` 渲染 12 型只读控件，复用到执行记录区 + 3 个警示区，并补全 `StepFormFields` 里缺失类型的配置项。

**这是纯前端改动。** `input_schema` 在后端按不透明 JSON 存储（`InputSchema = { type, [key]: unknown }`），新增配置键无需改后端类型或迁移。实施时需验证后端 step schema 校验不拒绝未知子键（预期仅校验 `type` 枚举）。

## 2. 范围

### 做（In scope）

1. 新建 `FormFieldPreview.vue`：12 型只读渲染分发组件（方案 1 单文件 v-if）。
2. 增强 `StepFormFields.vue`：补 YESNO / SIGNATURE / DATE / PHOTO 配置分支；METER 加阈值字段。
3. 改 `StepDetailPanel.vue`：执行记录区 + 3 警示区（非 COMMON 时）改「配置左 / 预览右」并排布局，响应式窄屏堆叠。
4. 单测：`FormFieldPreview.spec.ts`（12 型分支）+ `StepFormFields.spec.ts`（新增配置分支）。
5. 跑通前端门禁：lint / typecheck / build / vitest。

### 不做（Out of scope，YAGNI）

- 执行侧整步骤预览 / `ProcedurePreviewDialog`（执行端超项目范围）。
- 附件实际上传、执行记录数据绑定。
- 组件库拆分（评估中的方案 2，12 独立文件）。
- 任何后端改动。

## 3. 组件设计

### 3.1 `components/editor/FormFieldPreview.vue`（新建）

- **Props**：`{ schema: InputSchema }`。纯展示组件，无 emit、无 store 依赖。
- **依赖**：Element Plus 只读/禁用控件；`FORM_TYPE_META`（utils/editor.ts，已有 12 型标签/色）。
- **渲染规则**（所有交互控件 `disabled`，模拟执行者视角；缺省值用 `??` 兜底）：

| type | 预览内容 | 读取的 schema 键（默认） |
|---|---|---|
| NUMBER | 禁用数字框 + 单位后缀 + 「范围 min~max（n 位小数）」灰字提示 | `unit`、`min`、`max`、`decimals` |
| METER | 仪表卡片：`name`（默认「仪表读数」）+ 禁用数字框 + 单位 + 「下限 lower / 上限 upper」着色提示 | `name`、`unit`、`lower_limit`、`upper_limit`、`decimals` |
| CHECK | 两个禁用按钮 | `pass_label`（默认「通过」）、`fail_label`（默认「不通过」） |
| YESNO | 禁用按钮：是 / 否（+「不适用」当 `na_enabled`） | `yes_label`（默认「是」）、`no_label`（默认「否」）、`na_enabled` |
| CHECKBOX | `options[]` → 禁用复选框列表；空则灰字「未配置选项」 | `options` |
| RADIO | `options[]` → 禁用单选组；空则灰字「未配置选项」 | `options` |
| UPLOAD | 虚线上传占位 + 「接受 accept · 最多 max_count」文案 | `accept`、`max_count` |
| PHOTO | 虚线拍照占位 + 「最多 N 张」 | `max_count`（默认 1） |
| SIGNATURE | 虚线签名占位 + 可选提示文字 | `hint` |
| DATE | 禁用日期选择占位（`with_time` 时显示日期+时间格式） | `with_time` |
| COMMON | 灰字「通用操作说明型，执行时无独立录入控件」 | — |
| NONE | 灰字「该步骤无需填写录入项」 | — |

- **结构**：根 `<div class="field-preview">` + 顶部一行「预览」小标签（带 `<Eye>`/文字），下方 v-if/v-else-if 分支。每分支只读，便于单测按特征断言。

### 3.2 `components/editor/StepFormFields.vue`（增强）

沿用现有 `set()/str()/num()` + `:disabled="readonly"` 模式，新增/改动分支：

- **YESNO**（现落到「无需配置」兜底）→ 新增：
  - `yes_label`（el-input，占位「是」）
  - `no_label`（el-input，占位「否」）
  - `na_enabled`（el-switch，「包含『不适用』」）
- **METER**（现仅 `unit`）→ 增加：
  - `name`（el-input，仪表名称）
  - `lower_limit` / `upper_limit`（el-input-number）
  - `decimals`（el-input-number，0~6）
- **SIGNATURE** → 新增 `hint`（el-input，签名提示文字，可选）
- **DATE** → 新增 `with_time`（el-switch，「包含时间」）
- **PHOTO** → 新增 `max_count`（el-input-number，min 1，复用 UPLOAD 同款）

兜底 `<el-text>「该类型无需额外配置」` 仅保留给 COMMON / NONE。

### 3.3 `components/editor/StepDetailPanel.vue`（集成）

引入一个轻量并排布局（CSS class，不新建组件），用于 4 处：

```
┌─ .config-preview (flex, gap 16, wrap) ──────────────┐
│ ┌ .cp-config ────────┐  ┌ .cp-preview ────────────┐ │
│ │ <StepFormFields>   │  │ <FormFieldPreview>      │ │
│ └────────────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

- **执行记录区**（`name="exec"`）：现 `<StepFormFields>` 包进 `.config-preview`，右侧加 `<FormFieldPreview :schema="step.input_schema" />`；下方保留「需要操作员确认」。
- **3 警示区**（note/caution/warning）：现 `v-else`（非 COMMON）分支里的 `<StepFormFields>` 同样包进 `.config-preview` + 对应 `*_schema` 的 `<FormFieldPreview>`。COMMON 分支（富文本）不变。
- **布局 CSS**：`.config-preview { display:flex; gap:16px; flex-wrap:wrap }`，`.cp-config`/`.cp-preview { flex:1 1 280px; min-width:0 }`——窄于 ~576px 自动换行堆叠。编辑器右栏较窄，用 `flex-wrap` + `flex-basis` 实现，无需媒体查询硬断点。
- **只读态**（`ro`）：配置禁用，预览照常显示（预览本就只读）。
- 预览随 store 响应式实时更新（schema 变即变），无需手动刷新。

## 4. 测试计划（TDD）

测试位于 `frontend/tests/unit/`，沿用现有约定：`@vue/test-utils` `mount` + `global:{ plugins:[ElementPlus] }`，jsdom。

### 4.1 `FormFieldPreview.spec.ts`（先写，红 → 绿）

逐型断言渲染特征（示例）：
- NUMBER：含单位文本、含「范围」提示。
- METER：含仪表名称 / 下限上限文本。
- CHECK：渲染两个按钮，文本含 pass/fail label（含默认值场景）。
- YESNO：含「是」「否」；`na_enabled` 时含「不适用」，否则不含。
- CHECKBOX / RADIO：options 长度 = 渲染项数；空 options 显示「未配置选项」。
- UPLOAD / PHOTO / SIGNATURE / DATE：含各自占位文案。
- COMMON / NONE：含对应灰字提示。

### 4.2 `StepFormFields.spec.ts`（新增配置分支）

- YESNO：出现 yes_label / no_label 输入 + na 开关。
- METER：出现 name / lower / upper / decimals。
- SIGNATURE：出现 hint 输入。
- DATE：出现 with_time 开关。
- PHOTO：出现 max_count。
- 改动事件：编辑某字段触发 `update:schema` 且 payload 含该键。

## 5. 验收

- 新增/改动文件通过 `npm run lint` / `npm run typecheck`（或项目等价命令）/ `npm run build` / `npx vitest run`。
- 4 处（exec + 3 警示）切换类型时预览实时正确反映。
- 只读态下配置禁用、预览正常。
- 不引入新 npm 依赖；不改后端；不改 `types/node.ts` 与 `utils/editor.ts`（仅复用 `FORM_TYPE_META`）。

## 6. 风险与缓解

- **后端可能校验 input_schema 子键**：实施第一步先核查 `backend/app/schemas/node.py` 与 step_service「12 型校验」逻辑，确认新键不被拒；若被拒，则在该层放开子键（仍属小改，但会扩范围，需先告知）。
- **Element Plus 禁用控件样式**：预览用 disabled 控件可能视觉偏灰；如需更「执行态」观感，后续可换静态展示，不在本期。
- **警示区变高**：3 警示区加预览后纵向变长；用 flex-wrap 堆叠 + 紧凑间距缓解，必要时预览区可设较小 min-width。
