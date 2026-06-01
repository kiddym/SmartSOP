# B 项设计：公式(OMML)/SmartArt/chart 占位兜底

> 状态：设计已与用户确认（2026-06-01）。
> 来源需求：`docs/word-parser-solution.md` §12.2B。
> 复用 A 项地基 `ParseWarning.severity`（见 `docs/superpowers/specs/2026-05-31-completeness-strong-confirm-design.md`）。
> 本 spec 仅覆盖 B 项；A 已完成、C/D 各自独立。

---

## 1. 背景与现状核对

`normalizer.py` 抽文本只认 `<w:t>`（`_serialize_runs` 遍历 run 取 `w:t`），抽图只认 `<a:blip>`/`<v:imagedata>`（`_emit_images`）。因此：
- **公式** `<m:oMath>`（内部 `<m:r>/<m:t>`，math 命名空间）→ 文本看不到、原位变空白，**连 warning 都没有**。
- **SmartArt/chart** 经 `<a:graphic>/<a:graphicData uri=…>` 引用独立 part（diagram rels / chart part），非 blip → 抽图看不到。

**已核实的关键事实**：
- `opc.py` 的 `NS` 映射（`utils/opc.py:17-23`）含 w/r/a/wp/pic/rel，**无 `m`（math）命名空间**——OMML 检测需先加。math NS = `http://schemas.openxmlformats.org/officeDocument/2006/math`。
- `_emit_images`（`normalizer.py:121`）用 `run.iter(qn("a:blip"))` / `qn("v:imagedata")` 扫描，**不区分 `mc:Fallback`**——故**带 VML/blip fallback 缓存图的 SmartArt 今天其实已被提取**。真正静默丢的是：所有公式、纯 chart（`<c:chart>` 引用、通常无 fallback 位图）、无 fallback 的 SmartArt。
- `content` 节点在 import 时被恒置 `mark_status="unmarked"`（`import_service.py:81`）；只有 chapter 节点能带 review（`:93`）。`ProcedureNode` 模型本就有 `mark_status` 列（`models/node.py:52`），支持任意节点 review。
- 解析器单测用合成 docx 构造器 `tests/unit/parser/_docx_builder.py`，**无需真实含公式/SmartArt 的 fixture**。
- 前端复查机制（A 阶段已查）按 `mark_status==='review'` 工作，**与节点类型无关**：`reviewCount` / 「仅看待确认」过滤 / 「下一个」导航 / `NodeTreeRow` 的「待确认」徽标都只看 `mark_status`。故 content 节点带 review 会自动进复查树、计数、可逐个跳转。

相关代码锚点：
- `backend/app/parser/utils/opc.py:17`（NS 映射）、`:34`（qn）、`:40`（local）
- `backend/app/parser/normalizer.py`：`_serialize_runs`（:188）、`_emit_images`（:121）、`_count_raw_images`（:103）、`emit_paragraph`（:260）、`Block`（ir.py:28）
- `backend/app/parser/structurer.py`：`structure()`（content 节点产出 :165-177）、`_append_completeness_warnings`（:371）
- `backend/app/parser/validators/completeness.py`（C001/C002/C003）
- `backend/app/services/import_service.py:81`（content 恒 unmarked，待改）
- 前端：content review 自动可见（A 机制），仅需占位 CSS。

---

## 2. 已确认的设计抉择

| # | 抉择 | 结论 |
|---|---|---|
| 1 | 占位可见机制 | **content 节点可带 review**。含占位的正文块 parse 标 `mark_status="review"`，改 `import_service` 让 content 节点也能携带 review；用户经现有「仅看待确认/下一个」复查导航逐个补。 |
| 2 | 公式占位形态 | 行内文本占位 `<span class="sop-ph" data-ph="formula">[公式]</span>`，原位插入（保位置）。 |
| 3 | SmartArt/chart 占位 | **有可用缓存位图就当图原位提取**（`mc:Fallback` 的 blip/imagedata，走现有抽图路径）；**无则插块状文本占位** `<div class="sop-ph" data-ph="smartart">[SmartArt 图示]</div>` / `data-ph="chart">[图表]`。均标 review。 |
| 4 | 完整性兜底 | **新增计数检查（C007）**：原始 `<m:oMath>` 数 + 无可用图的 graphic 数 vs 实际插入占位数，不等 → `severity="blocking"` warning。专兜「检测逻辑漏抽某形态」。 |

目标（doc 原则）：不追求完美还原排版，只保证「这里原本有公式/图示」这一事实不丢、用户在复查页看得到并能手动补。

---

## 3. 后端改动

### 3.1 命名空间
`opc.py` 的 `NS` 加 `"m": "http://schemas.openxmlformats.org/officeDocument/2006/math"`。

### 3.2 公式占位（normalizer `_serialize_runs`）
`_serialize_runs` 遍历 `container` 子元素时新增分支：遇 `local(child.tag)` 为 `oMathPara` 或 `oMath` → 追加占位 HTML `<span class="sop-ph" data-ph="formula">[公式]</span>` 到 `parts`，并累计「本块占位数 +1」。
- `oMathPara` 内可能含多个 `oMath`：以 `oMathPara` 为一处占位（一个公式段落算一处），裸 `oMath`（行内）各算一处。实现时只在最外层 math 容器计一次，避免对嵌套 `m:r/m:t` 重复计。
- 不抽取 `m:t` 文本内容（不追求还原公式）。

### 3.3 SmartArt/chart 占位（normalizer，run / drawing 层）
在 run 序列化中识别 `<a:graphic>` 下的 `<a:graphicData uri=…>`：
- uri 含 `.../diagram` → SmartArt；含 `.../chart`（或 chartex）→ chart；含 `.../picture` → 普通图（现有路径，不动）。
- 对 diagram/chart：先看现有 `_emit_images` 是否已为该 run 抽到位图（fallback blip/imagedata）。**已抽到 → 不插占位**（图已原位呈现）。**未抽到 → 插块状文本占位**（diagram=`[SmartArt 图示]`，chart=`[图表]`），累计「本块占位数 +1」。
- 设计注意（交 plan 解决）：避免与 `_emit_images` 的 fallback-blip 提取**双重处理**同一图形——以「该 graphic 是否已产出 ImageRef」为判据。

### 3.4 Block 计数字段（ir.py）
`Block` 新增两个计数字段（默认 0），供 C007 对账。**关键：二者必须由相互独立的代码路径产出**（照搬 C001 的 `_count_raw_images` 独立于 `_emit_images` 的范式），否则同一段逻辑既检测又插入会令两数恒相等、C007 形同虚设：
- `raw_placeholder_count`: int —— 由一个**独立扫描函数**（类似 `_count_raw_images`）统计源元素内「原始 `<m:oMath>`/`<m:oMathPara>` 数 + 无可用图的 diagram/chart graphic 数」。不参与插入。
- `placeholder_count`: int —— 由 `_serialize_runs`/run 序列化在**实际插入占位时**累加的数（formula span + graphic 块）。
- C007 比对二者：检测+插入都正确 → 相等 pass；插入路径漏插某形态（但独立扫描数到了）→ raw>inserted → fail（blocking）。这正是兜底的意义。
（具体口径以 plan 为准；命名可调，但「独立双路径」不可省。）

### 3.5 含占位块 → review（structurer）
`structure()` 产 content 节点时：若该 `Block.placeholder_count > 0` → 该 `ParsedNode.mark_status="review"`（并计入 `review_required`）。当前 content 节点恒不设 review，本处改为按占位置 review。

### 3.6 import 让 content 节点携带 review
`import_service.py:81` 的 content 分支 `mark_status="unmarked"` 改为 `mark_status="review" if n.mark_status == "review" else "unmarked"`（与 chapter 分支一致）。chapter 分支不动。

### 3.7 完整性兜底 C007（completeness.py + structurer）
- `completeness.py` 新增 `placeholder_count_match(body_blocks) -> tuple[bool, int, int]`：`raw = sum(b.raw_placeholder_count)`，`inserted = sum(b.placeholder_count)`，`ok = raw == inserted`。
- `structurer._append_completeness_warnings` 增一条：不等 → `ParseWarning(stage="completeness", message=f"公式/图示可能遗漏：原始 {raw} / 占位 {inserted}", severity="blocking")`。
- C001/C002/C003 不变；图形走文字占位者**不进 C001 图片分母**（概念分离），由 C007 兜。

---

## 4. 前端改动

### 4.1 占位样式
新增 `.sop-ph` 样式（全局或编辑器作用域，跟随既有 rich_content 渲染管线——content 节点 HTML 经 v-html / WangEditor 渲染）：
- 行内 `span.sop-ph[data-ph="formula"]`：醒目行内标签（如灰底/虚线边框 + 小字），表「[公式]」。
- 块状 `div.sop-ph[data-ph="smartart"|"chart"]`：卡片式占位块。
- 目标：用户一眼看出「这里原本有公式/图示」，可删除占位后手动补真实内容。

### 4.2 复查导航（零逻辑改动，确认即可）
content 节点带 review 后，A 阶段已有的「待确认 N」计数、「仅看待确认」过滤、「下一个」导航、`NodeTreeRow` 徽标自动覆盖 content 节点（均按 `mark_status` 工作）。本 spec 仅需确认这些在 content 节点上正常工作（加一两条 vitest 守护），无需改逻辑。

---

## 5. 数据流（端到端）

```
docx 含 <m:oMath> / SmartArt / chart
  → normalize：
      _serialize_runs 遇 oMath → 插 [公式] span，块 placeholder_count++
      run 内 diagram/chart 无可用图 → 插块状占位，placeholder_count++；有图 → 现有抽图
      Block.raw_placeholder_count = 原始 oMath + 无图 graphic 数
  → structurer：placeholder_count>0 的 content 块 → ParsedNode.mark_status=review
      _append_completeness_warnings：raw≠inserted → blocking warning（C007）
  → /parse 响应：chapters 含带 review 的 content 节点 + rich_content 内占位 HTML；warnings 含 C007（若失配）
  → import：content 节点 review 落库（import_service 改后）
  → 编辑器：复查树显示带「待确认」的 content 占位节点，占位 HTML 经 .sop-ph 醒目呈现
```

---

## 6. 测试计划（TDD）

### 后端（pytest，合成 docx 用 `_docx_builder`，可能需扩展构造器支持 oMath/graphic）
- normalizer：含 `<m:oMath>` 段落 → rich_content 原位含 `[公式]` span、位置在原 oMath 处；`placeholder_count`/`raw_placeholder_count` 正确。
- normalizer：含 fallback 位图的 SmartArt → 当图提取、**不**插占位；无 fallback 的 diagram/chart → 插块状占位、计数正确；不与抽图双重处理。
- structurer：含占位 content 块 → `mark_status="review"` 且计入 `review_required`；无占位 content 块仍 unmarked。
- completeness：`placeholder_count_match` raw==inserted → pass；人为制造 raw>inserted（模拟漏抽）→ fail。
- structurer `_append_completeness_warnings`：C007 失配 → 产 `severity="blocking"` warning。
- import_service：传入 `mark_status="review"` 的 content 节点 → 落库为 review（验证 :81 改动）。
- 回归：后端全量。

### 前端（vitest）
- 占位 HTML（`.sop-ph` formula/smartart/chart）渲染：在 content 渲染路径下样式/结构正确。
- 复查导航对 content review 节点生效：构造含 `mark_status='review'` 的 content 节点 → `reviewCount` 计入、「仅看待确认」可见、「下一个」可跳。
- 回归：前端全量。

---

## 7. 范围边界（YAGNI / 非目标）
- 不还原公式真实排版/不解析 `m:t` 成可编辑公式；占位即可。
- 不渲染 SmartArt/chart 真实图形；有缓存位图才用，否则文字占位。
- 不改 C001/C002/C003 语义；图形文字占位不进 C001 分母（由 C007 兜）。
- 不动 A（强确认）、C（EMF/WMF）。
- 不为占位引入可编辑公式编辑器等重型 UI。
- 首标题前占位等边缘：沿用 Q343（首标题前内容丢弃+info），不为占位破例。
