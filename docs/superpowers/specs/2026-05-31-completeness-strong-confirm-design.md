# A 项设计：C001/C002/C003 强确认 + 解析提示可见化

> 状态：设计已与用户确认（2026-05-31）。
> 来源需求：`docs/word-parser-solution.md` §12.2A + §9。
> 本 spec 仅覆盖待补清单 **A 项**；B（公式/SmartArt 占位）、C（EMF/WMF 阻断告警）、D（C005，已决定标 deferred）各自独立。

---

## 1. 背景与现状核对

`docs/word-parser-solution.md` §12.2A 要求把 C001/C003 完整性校验从「静默 warning」升级为「强确认」。核对代码后确认现状，并发现两处文档未提及、且直接改变实现落点的漂移：

1. **前端把 `warnings` 整个丢掉**：`frontend/src/api/parse.ts` 的 `importFromWord()` 拿到 `parsed.warnings` 后完全不转发、不渲染。今天 C001/C002/C003 的 warning 连「塞角落」都没有，彻底到不了用户。
2. **导入是「直通」的**：`CreateFromWordDialog.vue` 的 `submit()` 一次点击串起 upload→parse→**import**，纠偏发生在 import 之后的编辑器。不存在文档 §11 设想的「前端 step3 纠偏后再 import」闸口。

因此 A 项不是「改一个已存在的可见 warning」，而是**从零建 warning 展示面**，并在 parse 与 import 之间插入确认环节。

相关现状代码锚点：
- `backend/app/parser/validators/completeness.py:42` —— C003 阈值 `kept/raw >= 0.95`。
- `backend/app/parser/validators/completeness.py:19` —— C001 `image_count_match` 返回 `raw == extracted`。
- `backend/app/parser/structurer.py:371-393` —— `_append_completeness_warnings`（仅 smart 模式，`structurer.py:184` gate）。
- `backend/app/parser/structurer.py:356-368` —— `_append_discarded_warning`（页眉/页脚）。
- `backend/app/parser/structurer.py:157-164` —— 首标题前内容丢弃 + warning（Q343）。
- `backend/app/parser/result.py` —— `ParseWarning` dataclass。
- `backend/app/schemas/parse.py` —— `ParseWarningOut` / `ParseResponse` / `ImportRequest` / `ImportNodeIn` / `build_parse_response`。
- `backend/app/models/procedure.py` —— `Procedure` 模型（已大量用 JSON 列：`version_change_log`、`custom_values`）。
- `backend/app/services/import_service.py` —— `import_procedure`。
- `frontend/src/api/parse.ts` —— `importFromWord` / `parseDocx` / `importProcedure`。
- `frontend/src/components/CreateFromWordDialog.vue` —— 上传对话框 `submit()`。
- `frontend/src/components/editor/NodeTreePanel.vue` —— 编辑器树面板（「待确认 N」复查区所在）。

---

## 2. 已确认的设计抉择

| # | 抉择 | 结论 |
|---|---|---|
| 1 | 强确认闸口形态 | **仅出问题时拦**。干净文档（C001/C002/C003 全过）保持一键直通、零摩擦。 |
| 2 | 触发集合 | **C001（图片）+ C002（表格）+ C003（段落）任一不匹配** → 阻断式强确认。比 doc 多纳 C002（丢表与丢图同样是静默丢失）。 |
| 3 | 软提示落点 | 页眉/页脚丢弃、首标题前丢弃 = **导入后编辑器常驻提示区**（不弹窗、不拦人）。 |
| 4 | 软提示持久化 | **持久化到 procedure**（新增 JSON 列 + 一次迁移），刷新/事后重访都在。 |
| 5 | 持久化范围 | **持久化全部 warnings（含已放行的 blocking）**。编辑器提示区把已放行 blocking 标「已知缺失（已放行）」、info 标普通提示，便于事后追溯。 |

折中边界：采用**强确认**而非**硬拦截**——拦的是「用户没意识到丢了东西」，而非禁止导入脏文档。

---

## 3. 数据模型（A/B/C 共用地基）

### 3.1 `ParseWarning` 新增 `severity`

- `backend/app/parser/result.py` 的 `ParseWarning` dataclass 增加字段 `severity: str`，取值 `"blocking" | "info"`，默认 `"info"`。
- `backend/app/schemas/parse.py` 的 `ParseWarningOut` 同步增加 `severity: str`，`build_parse_response` 透传。
- 语义：`blocking` = 内容可能静默丢失、需用户显式放行；`info` = 有意裁剪/已知丢弃，知情即可。
- 这是正交轴，A/B/C 复用：A 的 C001/C002/C003 = blocking；页眉页脚/首标题前丢弃 = info；C 的「无 soffice 矢量图」将走 blocking；B 的占位提示走 info。
- 不引入 `code`/`detail` 等额外字段（YAGNI）。count 已嵌在 message；强确认弹窗标题的 N = blocking warning 条数。

### 3.2 `Procedure` 新增 `import_notes` JSON 列

- `backend/app/models/procedure.py`：`import_notes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)`，贴合既有 `version_change_log` / `custom_values` 模式。
- 存导入时刻的完整 warnings 快照：`[{"stage": str, "message": str, "severity": str}, ...]`。
- 新增一支 alembic 迁移（命名遵循仓库现有迁移风格），加该列，默认空数组。

---

## 4. 后端改动

1. **`completeness.py:42` —— C003 阈值 100%**
   `ok = kept / raw >= 0.95` → `ok = kept == raw`。同步更新该函数 docstring（去掉「≥95% pass」表述）。`raw == 0` 分支保持返回 `True`。

2. **`structurer.py` —— severity 分流**
   - `_append_completeness_warnings`：C001/C002/C003 三条 warning 均 `severity="blocking"`。
   - `_append_discarded_warning`（页眉/页脚）：`severity="info"`。
   - 首标题前内容丢弃 warning（`structurer.py:157-164`）：`severity="info"`。
   - 维持现状：completeness warning 仅在 smart 模式产出（前端恒走 smart），不扩到 standard。

3. **`import_service.import_procedure` + `ImportRequest`**
   - `ImportRequest`（`schemas/parse.py`）新增 `import_notes: list[ParseWarningOut] = Field(default_factory=list)`（或等价的轻量 in-schema），前端把 parse 拿到的 warnings 原样回传。
   - `import_procedure` 落库到 `Procedure.import_notes`。

4. **编辑器读取端点暴露 `import_notes`**
   - 把 `import_notes` 加到编辑器已在拉取的 procedure detail/meta 响应 schema（`schemas/procedure.py`）。具体挂在哪个响应由 plan 阶段按编辑器实际拉取的端点确定。

---

## 5. 前端改动

1. **拆直通流**（`parse.ts` + `CreateFromWordDialog.vue`）
   - 现 `importFromWord`（upload→parse→import 一锅端）拆为 `uploadAndParse()` 与 `importParsed()`。
   - `CreateFromWordDialog.submit()` 编排：
     - 调 `uploadAndParse()` 得到 `ParseResponse`；
     - 筛 `warnings.filter(w => w.severity === "blocking")`；
     - 若非空 → 弹 `ParseConfirmDialog`：取消则中止（不 import、保留对话框）；确认则继续；
     - 若为空 → 直接 `importParsed()`（同今天，零摩擦）；
     - `importParsed()` 回传 `warnings`（全量）用于持久化。

2. **新组件 `ParseConfirmDialog.vue`**
   - 列出 N 条 blocking warning 的 message；标题「检测到 N 项内容可能未提取，是否仍要继续导入？」；按钮 `[取消导入]` / `[仍要继续导入]`。
   - 纯展示 + 两个事件（confirm / cancel），无副作用，便于独立测试。

3. **新组件 `ParseNoticeBar.vue`**
   - 编辑器顶部可折叠条「解析提示 N 条」，紧邻 `NodeTreePanel` 的「待确认 N」复查区。
   - 渲染从 procedure 加载的 `import_notes`：blocking 项标「已知缺失（已放行）」样式，info 项标普通提示样式。
   - 空数组时不渲染（零提示不占位）。

4. **加载 `import_notes`**
   - 编辑器 store 加载 procedure 时一并取 `import_notes`，传给 `ParseNoticeBar`。

5. **类型**（`frontend/src/types/parse.ts`）
   - `ParseWarning` 增 `severity: 'blocking' | 'info'`。
   - procedure 类型增 `import_notes: ParseWarning[]`。

---

## 6. 数据流（端到端）

```
上传 docx
  → uploadAndParse(): POST /uploads, POST /parse
      ParseResponse.warnings[*].severity ∈ {blocking, info}
  → CreateFromWordDialog 编排：
      blocking 非空? ── 是 → ParseConfirmDialog
      │                      ├─ 取消 → 中止（不落库）
      │                      └─ 继续 ↓
      └─ 否 ───────────────────────→ importParsed()
  → importParsed(): POST /procedures/import { ..., chapters, import_notes: 全量 warnings }
      import_service 落库 Procedure.import_notes
  → 跳转编辑器 /procedures/{id}/edit
      store 加载 procedure（含 import_notes）
      ParseNoticeBar 渲染（blocking=已放行 / info=普通）
      NodeTreePanel「待确认 N」复查区照旧
```

---

## 7. 测试计划（TDD）

### 后端（pytest）
- `completeness.paragraph_count_match`：`kept == raw` → pass；`kept < raw` → fail；`raw == 0` → pass（阈值 100% 行为）。
- `structurer`：含缺图/缺表/缺段文档 → 对应 warning `severity == "blocking"`；含页眉页脚文档 → discard warning `severity == "info"`；首标题前有内容 → 该 warning `severity == "info"`。
- `build_parse_response`：`ParseWarningOut.severity` 正确透传。
- `import_procedure`：传入 `import_notes` → 落库到 `Procedure.import_notes`；procedure detail 端点返回该字段。
- 迁移：升级后 `tb_procedure` 含 `import_notes` 列、默认空数组。

### 前端（vitest）
- `CreateFromWordDialog` / parse 流：有 blocking warning → 弹 `ParseConfirmDialog`；取消 → 不调 import；确认 → 调 import 且回传 import_notes。
- 无 blocking warning → 直接 import、不弹窗。
- `ParseConfirmDialog`：渲染 N 条 message、标题含正确 N、两个按钮各发对应事件。
- `ParseNoticeBar`：渲染 import_notes（blocking/info 两种样式）；空数组不渲染。

### 回归
- 全量后端 pytest + 前端 vitest，确认 C003 阈值收紧与直通流拆分无回归。

---

## 8. 范围边界（YAGNI / 非目标）

- 不做硬拦截（不禁止导入脏文档）。
- 不把 completeness 校验扩到 standard 模式（前端恒走 smart）。
- 不为 warning 引入 `code`/`detail` 结构化字段。
- 不动 B（公式/SmartArt）、C（EMF/WMF）——各自独立 spec。
- C005 已决定标 deferred（见 `word-parser-solution.md` §9 注），不在本 spec。
- 首标题前内容丢弃（Q343）维持「丢弃 + info warning」，本 spec 不升级为 blocking（仅纳入可见提示）。
