# Word→结构化 SOP 解析方案（方案 A：自动解析）

> 本文档是 **Word 解析器实现设计**，由一轮 grill + 对 5 份真实 SOP 的验证产出。
> 业务语义最高权威仍是 [feature-clarifications.md](feature-clarifications.md)。
> **⚠️ 本方案与 feature-clarifications.md 的若干「不可变设计」存在冲突，见 [§11 待对齐项](#11-与既有权威设计的冲突与待对齐项)。落地前必须先解决冲突。**

---

## 0. 验证状态

已用 `docs/reference doc/typical word doc/` 下 5 份真实 SOP 验证（脚本见 `scripts/validate_*.py`）：

| 文件 | 总块 | 正文起点 | 识别 heading 数 | 关键命中点 |
|---|---:|---:|---:|---|
| 1_程序模板.docx | 129 | 53（'目的'）| 12 | heading 1-5 标准样式 |
| TP试验程序.docx | 189 | 10（'目的'）| 65 | **靠 "章节标题" 中文同义词** |
| 公司运营管理.docx | 90 | 54（'目的'）| 7 | heading 1-2 标准样式 |
| 公司运营管理_表格图片.docx | 93 | 54（'目的'）| 7 | heading 1-2 标准样式 |
| 电厂管理巡视规定.docx | 147 | 44（'目的'）| 26 | heading 1-2 标准样式 |

**核心验证结论**：

1. **100% 标题识别在 5/5 文档可达，无需启发式** —— 前提是 `styles.xml` 反查 + 中文同义词词典。
2. **first_styled_heading 是权威正文起点信号** —— 5/5 精准命中第一个真实章节"目的"。
3. **DPMS 报告高估的失败面在真实 SOP 上不存在**：anchor 图 / 同段多图 / 嵌套表 / 文本框 / SDT 在 5 份文档上**全 0**。
4. **真正必修的硬约束**：表内嵌图（4/5 命中）+ vMerge 真实跨度（2/5 命中）。

---

## 1. 目标与硬约束

| 维度 | 硬约束（100% 必达） | 软约束（best-effort，标 review） |
|---|---|---|
| 标题 | 多级标题全部识别，层级正确 | — |
| 文本 | 章节正文文字（含表内文字、文本框正文） | 脚注/批注/修订 |
| 图片 | inline + 同段多图 + anchor + 表内嵌图 | — |
| 表格 | 顶层 + 嵌套 + 合并（rowspan/colspan 真实跨度） + 单元格递归 blocks | — |
| 顺序 | 章节内块顺序与原 docx 完全一致 | — |
| 列表/超链接/格式/公式 | — | 全部 placeholder + review |
| 页眉/页脚 | **完全不提取** | — |

「100%」精确定义 = **解析 + 用户校对协同 100%**：低置信度节点不静默丢弃也不误判，全部进 draft 由用户在 commit 前确认。

---

## 2. 架构（3 阶段）

```
.docx
  │
  ▼ Stage 1: DocxNormalizer
  │   - OPC 解压：document.xml + footnotes.xml + comments.xml +
  │     media/* + numbering.xml + styles.xml（不读 header*/footer*）
  │   - lxml 严格按 XML child order 流式产出块
  │   - 表格递归展开（嵌套表/单元格内段落/表内图）
  │   - SDT/textbox 递归展开
  │   - anchor 图按锚定段落位置插入块流
  │   - 同段多图全部产出独立 Image 块
  │   - 图片资源同时落 Asset 仓库（sha256 去重）
  │
  ▼ IR：顺序块数组 [{type, attrs, children, source_ref, asset_ref}]
  │
  ▼ Stage 2: SectionStructurer
  │   - find_body_start：定位正文起点（见 §5）
  │   - Tier 1：styles.xml 反查 4 级判定（见 §5）
  │   - Tier 2（仅兜底）：6 信号启发式 + 阈值相对化
  │   - 标题层级归并 → ChapterTree
  │   - 章节前悬空块 → 虚拟 preamble 章节
  │
  ▼ ChapterTree：[{level, title, content_blocks[], confidence, review}]
  │
  ▼ Stage 3: AstSerializer
  │   - content_blocks → 富文本（schema 见 §7，待与既有 HTML 模型对齐）
  │   - 图片用 asset_id 占位（待与既有 base64 模型对齐）
  │   - 表格 → 结构化 JSON
  │
  ▼ ProcedureDraft：{procedure_meta, chapters[], assets[], warnings[], completeness}
```

每层独立可测；新增内容类型只改 Normalizer。

---

## 3. Normalizer 关键实现（消除 DPMS 真实丢失点）

### 3.1 库选型
- **python-docx**：拿 metadata / styles / numbering 便利 helper
- **lxml**：直接遍历 `document.xml.body` 的子元素，**不走 doc.paragraphs**

### 3.2 块流产出（按 XML child order，保证顺序保真）
```python
def iter_body_blocks(body):
    for child in body.iterchildren():
        tag = local(child.tag)
        if tag == 'p':
            yield from emit_paragraph(child)   # 1 段落 + N 图片块
        elif tag == 'tbl':
            yield emit_table(child)            # 递归 cell 内 iter_body_blocks
        elif tag == 'sdt':
            yield from iter_body_blocks(child.find('.//w:sdtContent', NS))
        elif tag == 'sectPr':
            continue
```

### 3.3 段内多图 + anchor 图（修复 DPMS xml_traversal.py:135-167）
- 一段中遍历所有 `<a:blip>`，**收集为 list 返回**，不在 for 内 `return`。
- 区分 `<wp:inline>` vs `<wp:anchor>`，两者都产块。
- 按段内 XML 位置先产段落（含全部 runs），再按位置产图片块。

### 3.4 表格递归 + vMerge 真实跨度（修复 DPMS xml_traversal.py:224-230）
- **双 pass**：第一 pass 扫每个 `vMerge restart` 单元格向下连续多少 `continue`，算真实 rowspan。
- `gridSpan` → colspan。
- cell 内递归 `iter_body_blocks`（支持嵌套表、表内图、表内段落）。

### 3.5 其他 OPC part
- `footnotes.xml` / `comments.xml` → placeholder + review（软约束）
- `numbering.xml` → 解析编号映射，供 list 还原（软约束）
- **不读 `header*.xml` / `footer*.xml`**（确认无需页眉页脚）

---

## 4. 资源层（图片/嵌入对象）

- 解压 `word/media/` 全部资源，按 `rId` 建映射。
- 每张图：`asset_id`(uuid) + `sha256`(全库去重) + mime + size + width/height + `source_meta`(docx_rid/anchor_type/page_position) + `ref_count`。
- 同段多图、表内图、anchor 图统一走此路径。
- **GC**：ref_count 归零时物理删除。

> ⚠️ 此节与既有「base64 内联」模型冲突，见 §11。

---

## 5. Structurer：标题识别（核心，已验证 5/5）

### 5.1 styles.xml 反查 4 级判定（Tier 1，权威）
```python
def classify_heading_style(sid, styles_index, depth=0):
    s = styles_index.get(sid)
    if s is None or depth > 10:
        return None
    name = (s.name or '').strip()
    # 1. 标准 heading 名
    if name.lower() in {'heading 1'..'heading 9'} or name in {'标题 1'..'标题 9', '标题1'..'标题9'}:
        return level_from_name(name)
    # 2. 中文/自定义同义词词典（可配置，见 5.4）
    if name in CN_SYNONYM_LEVEL:
        return CN_SYNONYM_LEVEL[name]
    # 3. 该样式自身 pPr.outlineLvl
    if s.outline_lvl is not None:
        return int(s.outline_lvl) + 1
    # 4. 沿 basedOn 链递归上溯
    if s.based_on:
        return classify_heading_style(s.based_on, styles_index, depth+1)
    return None
```

**关键**：body 段落的 `pStyle` 是数字 sid（如 "2"、"13"、"28"），**必须先反查 styles.xml** 才能映射到 `name='heading 1'`。直接拿 sid 比对会全 miss（这是初版脚本的 bug）。

### 5.2 find_body_start（决策树，已验证 5/5）
```python
def find_body_start(children, styles_index):
    first_h = find_first_styled_heading(children, styles_index)  # 权威信号
    toc_end = find_toc_field_end(children)                       # 兜底
    early_sect = find_early_section_break(children, max_offset=min(len(children)//5, 100))  # 兜底

    if first_h is not None:
        return first_h, 'first_styled_heading'
    if toc_end is not None:
        return scan_past_toc_entries(children, toc_end, styles_index), 'post_toc_scan'
    if early_sect is not None:
        return early_sect, 'early_sectpr'
    return scan_cover_skip(children), 'cover_skip_fallback'
```

- **删除 DPMS / 初版的 `bookmark _Toc` 信号**：`_Toc*` 是 TOC 跳转目标（每个正文标题段都有），用它判边界会跳到文档末尾，灾难性误判（实测跳过 85%-97% 正文）。
- **不无脑取 max**：first_styled_heading 命中即采用（5/5 精准命中"目的"）。
- TOC fldChar end / early sectPr 仅在无样式标题时兜底。

### 5.3 Tier 2（仅兜底）
6 信号加权（字号相对化 / bold / 编号 / 短段 / 后跟正文 / outline 编号），**仅对 Tier 1 完全失败的文档启用**，低置信度标 review。

### 5.4 中文同义词词典（配置项）
```yaml
# config/heading_synonyms.yaml
heading_synonyms:
  level_1: ["章节标题", "章标题", "一级标题"]
  level_2: ["节标题", "小节标题", "二级标题"]
  level_3: ["条标题", "三级标题"]
```
命中记 `confidence=1.0`，不进 review。TP试验程序.docx 的 65 个标题全靠 `章节标题` 命中。

### 5.5 章节前悬空内容（2026-06-01 对齐实现 Q343）

第一个标题之前的正文块 → **丢弃 + warning**（不建虚拟前言章节）。见 `structurer.py` `structure()`：首标题之前的非标题块不挂任何章节，逐块产一条 `stage="boundary"` 的 warning（`severity="info"`，A 项后纳入编辑器常驻提示区可见）。

> 注：本节早期设计曾写「虚拟 chapter（level=0, title=（前言）, review=true）」，与最终实现 **Q343「丢弃+warning」** 不符，已于 2026-06-01 对齐。决策依据：parser 角色是「忠实表达」而非「编辑」，正文起点之前多为封面/目录残留，建虚拟前言会把噪音当正文；真有内容丢失由 info 提示让用户知情（§12.2 原则）。

---

## 6. 顺序保真不变量

**IR 块流 = 原 docx XML child order 的同构投影**。Normalizer 不重排，Structurer 仅在标题位置切分章节，不重排内容块。完整性校验 C005 对每章节的 `(type, source_ref.xpath)` 序列与原 XML 访问序列对账，差异需为 0。

### 6.1 段落粒度 1:1（强化条款，2026-05-27）

**原 docx 1 个 `<w:p>` 段落 ↔ IR 1 个 Block ↔ ParsedNode 1 个节点**。不允许：

- 把"号+正文同段"的融合式段落（如 `3.1质量部是记录的归口管理部门...`）切成 heading + content 两块
- 把多个相邻段落合并为一块
- 在段落内做任何重写、补字、删字、归一标点之外的内容改动

理由：parser 的角色是**"忠实表达"**，不是**"编辑"**。融合式段落的可读性问题（标题过长、content 节点空）属于编辑器 UX 范畴，由前端的「类型转换 / 手势切分 / 模式批量」用户主导操作解决，不在 parser 范围。决策权归属是这条边界的核心：UI 切分=用户主导；parser 切分=算法猜测，违反 §C.0 「人机分工」。

详见 [`parser-comprehensive-evaluation.md`](parser-comprehensive-evaluation.md) §3.5「L2 设计抉择记录」。

---

## 7. Serializer：富文本 schema

> ⚠️ 本方案 grill 选了 **类 ProseMirror 节点树 + marks**（doc/heading/paragraph/image/table/list + bold/italic/link）。
> 既有权威用 **块结构 HTML 字符串**（rich_content）。两者冲突，见 §11。

placeholder 策略：公式 / 批注 / 修订 / 文本框 / 不可识别块 → placeholder 节点 + reason + raw_xml_ref + review=true，前端渲染为占位卡片。

---

## 8. API（同步 + 两步）

- `POST /api/procedure/parse`：multipart docx → `{draft_id, procedure_meta, chapters[], assets[], warnings[], completeness, review_required}`，30s 超时返 504。
- `POST /api/procedure/commit`：`{draft_id, ast, procedure_meta}`（允许用户编辑后的完整 ast）→ `{procedure_id}`。后端校验 schema / asset_id / 无 review 残留。
- `GET /api/procedure/asset/{asset_id}?sig=...`：短期签名 URL（itsdangerous TTL 10min），FileResponse 流式返回。
- draft 存独立临时表 `procedure_draft`（user_id + ast + ttl_at，默认 7 天清理）。

---

## 9. 完整性校验

| 码 | 校验 | 失败动作 |
|---|---|---|
| C001 | 原始 inline+anchor blip 数（正文范围 + 表内）= 解析 image 块数 | warning → **待升级为强确认，见 §12.2A** |
| C002 | 原始 `<w:tbl>` 数（含嵌套，正文范围）= 解析 table 块数 | warning |
| C003 | 正文范围非空 `<w:p>` 数 vs 解析 paragraph 数 ≥ 95% | warning → **阈值待提至 100% + 强确认，见 §12.2A** |
| C004 | 章节数 ≥ 1 且每个标题 level 合法 | error |
| C005 | 块流 (type, position) 序列 = 原 XML child order 同构投影 | **deferred（未实现）** —— 见下方注 |
| C006 | find_body_start 必须返回非 None | error |

校验范围均为 `body_start_idx` 之后的正文（封面/目录里的图片表格不参与对账）。

> **注（2026-05-31，C005 状态对齐）**：C005 在 `validators/completeness.py` 中**未实现**，状态为 **deferred**。理由（见该文件 docstring）：运行时对账需要把原始 body 子序列与 blocks 的 source_index 做结构化 diff，infra 成本高、real-world 价值低，而 normalize 本就严格按 XML child order 流式产块（见 §6「顺序保真不变量」），顺序保真是**结构性保证**而非运行时校验项。§6 描述的「差异需为 0」是设计不变量，不代表存在运行时 C005 检查。若未来出现顺序错乱的真实反例，再实现 C005。

---

## 10. 阶段实施计划（9 周，单人后端）

| Phase | 内容 | 工期 |
|---|---|---|
| P1 | Normalizer 骨架（OPC 遍历 + 段落/表格/SDT 块流 + 表内嵌图 + vMerge 真实跨度 + find_body_start） | 2 周 |
| P2 | Structurer Tier 1（styles.xml 反查 + 中文同义词；5 份 fixture 100% 命中） | 1 周 |
| P3 | Serializer + 富文本 schema + assets 落盘 | 1 周 |
| P4 | 图片/表格扩展收尾（C001/C002 全通过） | 1.5 周 |
| P5 | Structurer Tier 2（6 信号兜底，不需精调） | 0.5 周 |
| P6 | C001-C006 完整性校验 + draft/commit 两步 API | 1 周 |
| P7 | fixture 套件（3 合成 + 5 真实）+ golden test | 1 周 |
| P8 | 边缘扩展（anchor / 文本框 / SDT / 嵌套表 / 公式占位） | 2 周 |

---

## 11. 与既有权威设计的冲突 —— 已通过 Q189–Q200 grill 解决 ✅

> 6 处冲突已在新一轮 grill（决策 Q189–Q200）中全部裁定，落地到 [feature-clarifications.md §25](feature-clarifications.md)。
> **最终方向：保留既有 content 子节点 + 块 HTML + WangEditor 5 模型，仅做针对性改进（图片外置、层级保真、正文起点、置信度纠偏）。本方案 v3 原设计中与不可变设计 #1 冲突的部分（3 表 / ProseMirror / content_ast）被否决。**

| # | 本方案 v3 原设计 | 裁定结果（Q189–Q200） |
|---|---|---|
| 1 | 3 表 chapter + content_ast(JSON) + assets(FK) | **否决**（Q189）。保留既有 content 子节点 + 块 HTML；仅新增 assets 表存图片二进制 |
| 2 | 图片 assets 表 + 签名 URL | **采纳（targeted）**（Q189/Q193）。rich_content 里 `<img src>` 改指 `/api/.../asset/{id}`；parse 抽图到 `tmp/uploads/{token}/media/`，import 提升为永久 assets（sha256 去重 + ref_count，Q197 关联表追踪 GC）|
| 3 | 富文本 = ProseMirror 节点树 + marks | **否决**（Q189）。保留块结构 HTML 字符串（对齐 WangEditor 5）|
| 4 | 标题层级 | **最多 3 级**（Q190 二次修订：曾改 6 级，因 31 份真实文档最深仅 N.N.N=3 级 + 用户思路而回退至 3）。H4-6 / 更深编号压缩为 L3（保留 Q35）|
| 5 | 正文起点 = first_styled_heading | **采纳**（Q191/Q196）。删除「最后 section break」规则（实测 0/5）；兜底链 = first_styled_heading → TOC field end → 启发式首个高分标题 → 跳封面。**取代 Q37**|
| 6 | 删除 bookmark _Toc 信号 | **确认**（仅踩坑记录，既有未用此信号）|

**新增（非冲突）**：方案 C 纳入既有 parse 管线（Q192）—— smart 模式升级为「自动预标 + 置信度分级 + 纠偏面板 + 模式批量」，覆盖零样式文档。详见 [feature-clarifications.md §25](feature-clarifications.md)。

**流程对齐**：沿用既有 parse→import（parse 返 JSON 不落库，纠偏在前端 step3，import 才落库）；**废弃早期会话 Q183/Q184/Q185 的同步两步 + procedure_draft 临时表设计**（Q195）。

**实现细节（Q205–Q208，[feature-clarifications.md §27](feature-clarifications.md)）**：表格落标准 `<table>` HTML 含 rowspan/colspan + 表内 `<img>`（Q205）；内联图随段保留为一个 content 节点、修订 §9.2（Q206）；单图限制 1MB→10MB、白名单含 emf/wmf 转 png（Q207）；非标准标题两层词典 = `heading_synonyms.yaml` 默认 + `heading_style_map` 组织级表覆盖（Q208）。

> 注：本文档内早期局部编号（v3 的"Q165–Q188""Q183–Q185"）与 feature-clarifications.md 全局编号无关；本轮落地的全局编号是 **Q189–Q200（§25）+ Q205–Q208（§27）**。

---

## 附：验证脚本

- [scripts/validate_fixtures.py](../scripts/validate_fixtures.py) — OPC 结构 + 内容分布 + DPMS bug 命中
- [scripts/validate_styles.py](../scripts/validate_styles.py) — styles.xml 反查
- [scripts/validate_v2.py](../scripts/validate_v2.py) — 修正后的 heading 识别（5/5 命中）
- [scripts/validate_fixtures.json](../scripts/validate_fixtures.json) — 完整数据
- [scripts/validate_unstyled.py](../scripts/validate_unstyled.py) — 零样式文档启发式探查（方案 C 形态④⑤）
- [scripts/validate_unstyled_v2.py](../scripts/validate_unstyled_v2.py) — 方案 C v2 启发式 + ground truth precision/recall（2 份零样式文档 F1：0→1.0）
- [scripts/validate_unstyled_v3.py](../scripts/validate_unstyled_v3.py) — 5 份零样式 fixture + 三测量模式（自动/批量）；v4 编号字典（C.10/C.11）
- [scripts/survey_extra.py](../scripts/survey_extra.py) — 规模化 survey（26 份 QMS），无需 GT 找失败模式（C.11）

---
---

# 方案 C：自动预标 + 手工纠偏（针对非标准标题）

> 方案 A（全自动）对**标准/半标准样式**标题已 5/5 命中。
> 但真实项目存在**非标准标题**（无样式、纯视觉、纯编号）——方案 A 在这类文档上会失败。
> 方案 C 不是另起炉灶，而是方案 A 同一管线的**人机协作延伸**：机器有把握的自动标，没把握的给带置信度候选让用户纠正。
> **方案 A 是方案 C 在"全 HIGH 命中"时的退化情形**（用户 0 操作）。

## C.0 核心理念

把标题识别从二元判定改为**置信度分级 + 人机分工**：

- 机器有把握（标准样式）→ 自动标好，用户不管
- 机器没把握（非标准）→ 给带置信度的候选，用户只确认/纠正这部分
- 机器无信号 → 用户手工标，但用**模式批量**避免逐条点

目标：标准文档 0 操作，非标准文档**几次批量操作**而非几十次逐条点。

## C.1 非标准标题的 5 种形态

| 形态 | 例子 | styles.xml 能识别? | 处理路径 |
|---|---|---|---|
| ① 标准样式 | pStyle→`heading 1` | ✅ 直接 | Tier 1 自动 HIGH |
| ② 自定义命名样式 | `章节标题`、`MyHeading` | ⚠️ 需同义词词典或学习 | Tier 1 同义词 / 样式记忆 |
| ③ 仅 outlineLvl | 段落 pPr 带 outlineLvl | ✅ 兜底 | Tier 1 outlineLvl |
| ④ 纯视觉标题 | 手工加粗+居中+大字号，无结构标记 | ❌ 仅启发式 | Tier 2 启发式 MEDIUM |
| ⑤ 仅靠编号 | "一、目的" "1.1 范围"，无样式无加粗 | ❌ 仅编号正则 | Tier 2 启发式 + 模式批量 |

**痛点主战场是 ④⑤（及未登记的 ②）**。①②③ 方案 A 已自动 100%。

## C.2 三层置信度预标管线

```
正文块流（Stage 1 已提取全部内容）
    │
    ▼ 对每个 paragraph 算 heading_score + 推断 level + 定 confidence 档
    │
    ├─ HIGH (≥0.85)   仅样式类信号命中  → 自动应用，绿色，免复查
    ├─ MEDIUM (0.5-0.84) 启发式强信号    → 预标 + 黄色"待确认"
    ├─ LOW (0.3-0.49)  启发式弱信号      → 灰色虚线"候选"，一键采纳
    └─ NONE (<0.3)     视为 content      → 不预标，可手工提升
```

对应既有 `markStatus='review'`（§9.1）：HIGH 不进 review，MEDIUM/LOW 进 review 面板。

## C.3 启发式评分（处理非标准标题的核心）

```python
def heading_score(p, doc_stats):
    # ── 样式类（短路，直接 HIGH）──
    if styles_hit(p):             return 1.00, level_from_style(p)    # 形态①
    if synonym_hit(p):            return 0.95, level_from_synonym(p)  # 形态②
    if p.outline_lvl is not None: return 0.90, p.outline_lvl + 1      # 形态③

    # ── 启发式（形态④⑤，封顶 0.84，永不自动 HIGH）──
    s = 0.0
    if font_size(p) >= doc_stats.font_p85:  s += 0.25  # 字号 top15%（相对化）
    if bold_ratio(p) >= 0.5:                s += 0.20  # 加粗占比
    if numbering_pattern(p):                s += 0.25  # 一、/1./1.1/第X章/（一）
    if len(text(p)) <= 30:                  s += 0.10  # 短段
    if followed_by_body(p):                 s += 0.10  # 后跟正文
    if is_standalone(p):                    s += 0.05  # 独占段
    if distinct_align(p):                   s += 0.05  # 居中/特殊对齐
    return min(s, 0.84), infer_level_heuristic(p, doc_stats)
```

- **阈值相对化**：`font_p85` 先扫全文字号分布算 85 分位，不写死 "≥18pt"。
- 启发式封顶 0.84 → 非标准标题**必经用户确认**，不会机器误判直接入库。

## C.4 层级推断（非标准标题无 level 信息）

按可靠性排序：
1. **编号深度**（最可靠）：`1.`→L1，`1.1`→L2，`1.1.1`→L3；`一、`→L1，`（一）`→L2
2. **字号聚类**：候选标题字号聚 N 簇，最大簇=L1，次之=L2…
3. **缩进/大纲**：左缩进档位映射层级

## C.5 模式批量提升（解决"非标准也要点 N 次"）

非标准标题往往遵循一致模式。解析后扫描 MEDIUM/LOW 候选归纳模式，主动提示：

```
🔍 检测到 12 个段落以「数字、」开头且加粗（目的、适用范围、职责…）
   [全部标为一级标题]  [逐个查看]  [忽略]
🔍 检测到 31 个段落匹配「1.1 / 1.2」编号
   [全部标为二级标题]  [逐个查看]  [忽略]
```

一次点击 = 提升一整类。模式来源：编号正则同构 / 字号相同 / 样式 sid 相同 / 加粗+居中组合相同。

## C.6 纠偏 UI 交互

左树 + 复查面板双视图，每节点操作：✓确认 / ✗降级为 content / 调级(L1↔L2↔L3) / content 提升为标题。
键盘流：`↑↓`移动、`Enter`确认、`Tab/Shift+Tab`调级、`Esc`降级——快速处理大批候选。

## C.7 样式映射记忆（结构性解决痛点）

非标准文档的痛点是第一份要纠偏，但同源文档重复出现相同非标准样式/模式。纠偏结果要学习：
- **文档内**：确认样式 `MyHeading`=L1 → 立即应用本文档所有该样式段落
- **跨文档（可选）**：写入 `config/heading_synonyms.yaml` 或组织级样式映射表 → 下一份同样式文档自动 HIGH，0 操作

用得越多，手工越少。

## C.8 与既有设计 / 数据流衔接

- 既有 `markStatus='review'`（§9.1）是种子，扩展为：① review 从"少数中置信 heading"扩为"全部 MEDIUM/LOW 候选面板"；② 加模式批量 + 样式记忆。
- 数据流不变：`POST /parse` 返回 chapters **带 confidence**，draft 存全部正文 + 候选；用户纠偏在前端 state；`POST /commit` 提交最终结构。
- **方案 A / C 同源**：方案 A = 全 HIGH 命中的退化情形；非标准文档自动落 MEDIUM/LOW 触发纠偏 UI。同一管线两端，非两套代码。

## C.9 端到端示例（零样式文档，形态⑤）

```
原文（无 heading 样式，纯编号+加粗）：1. 目的 / 正文 / 2. 适用范围 / 2.1 厂内 …（20 编号段）
管线：
  ① Stage1 提取 20 编号段 + 正文（0 丢失）
  ② styles.xml 反查：0 命中
  ③ 启发式：20 段命中"加粗+编号+短段" → score≈0.55 MEDIUM
  ④ 层级推断：编号深度 "1."=L1, "2.1"=L2
  ⑤ 模式批量提示："13 个『N.』段 + 7 个『N.M』段"
  ⑥ 用户 2 次点击：[N.→L1] [N.M→L2] → 20 标题就位
  ⑦ commit
结果：零样式文档，用户 2 次操作（vs 纯方案B 20 次，vs 方案A 解析失败）
```

## C.10 零样式 fixture 验证结果（已扩到 5 份）

`typical word doc/无格式标题word/` 现有 **5 份**零样式 SOP（全部 styles.xml 零命中）。脚本 [scripts/validate_unstyled_v3.py](../scripts/validate_unstyled_v3.py) 带 ground truth，对比 v2 vs v3 vs 模式批量：

| 文档 | GT 标题 | v2 自动 P/R/F1 | v3 自动 P/R/F1 | v3+模式批量 |
|---|---:|---|---|---|
| 3.危险源监控措施 | 5 | 1.00/1.00/1.00 | 1.00/1.00/1.00 | 1.00/1.00/1.00 |
| 有限空间作业管理办法 | 6 | 1.00/1.00/1.00 | 1.00/1.00/1.00 | 0.15/1.00/0.27 |
| 02记录控制程序 | 21 | 0.82/0.67/0.74 | **1.00**/0.67/0.80 | 1.00/1.00/1.00 |
| 05人力资源控制程序 | 22 | 0.80/0.91/0.85 | **1.00**/0.91/0.95 | 1.00/0.95/0.98 |
| CW-WI-7.4-01外发 | 20 | 1.00/0.35/0.52 | 1.00/0.35/0.52 | 0.71/1.00/0.83 |
| **micro 汇总** | 74 | 0.87/0.70/0.78 | **1.00**/0.70/**0.83** | 0.64/0.99/0.78 |

**3 份新 fixture 暴露并修复的泛化缺口（v2→v3）**：

1. **「数字+空格+标题」**（`1 目的` `2 范围`）：v2 编号字典只认 `1.`/`1、`，漏掉空格分隔 → 02/05 的 5 个 L1 全 miss。v3 加 `^\d+\s+(?![/\d])` 模式（排除 `1 / 2` 页码）。
2. **页眉表格重复混入正文**：`第X章 …` 重复 3-5 次、`程序文件/版本/页码` 等 → v3 剔除「出现 ≥3 次的相同文本」+ `N / M` 页码。
3. **封面/签名块误判**：CW-WI 的 `编制:/审核:/杨正行`（15pt 粗体短块）→ v3 `find_body_start` 跳到首个「带编号或样式」的标题（跳过封面），消除全部误报。

**关键结论（人机分工边界已量化）**：

- **v3 自动：Precision 1.0、Recall 0.70**——机器自动只升 confident 标题，**零误报**，泛化到 5 份无 FP。
- **Recall 0.70 的缺口 = 融合式子标题**（`3.1 质量部是记录的归口…` 号+正文同段）：机器故意压低（避免把编号正文误判），不自动升。
- **模式批量必须「按模式分组选择性提升」，不能一键全提升**：blanket 全提升使 micro-precision 跌到 0.64（元凶 有限空间：`第X条` 也被升）。正确 Q200 流程 = 用户看到分组（`第X章×6` / `第X条×30` / `N.N×7`），**按组勾选**——3 份"所有编号都是标题"的文档选择性批量后达 1.00/0.95+。
- **detected_patterns 必须扫描全部正文段（含 NONE 档长段）按编号前缀归组**，否则融合式子标题（NONE 档）不进任何分组、无法批量。

**残留已知 limitation（交人工/选择性批量，非 bug）**：
- 融合式「号+正文同段」子标题：靠选择性模式批量兜，不自动升。
- `5记录`（数字直接接中文、无空格/点）：1 例 miss；不加专门规则（避免误吃 `2017年` 等），交人工。
- `第X条` / 阿拉伯顿号 是否算标题：语义模糊，文档级开关 + 人工定（Q217）。

**已验证的设计要点**：分级编号字典（含数字+空格）/ 等字号自适应 / 误报抑制 / 弱标题分级 / 重复块剔除 / cover-skip body_start / 选择性模式批量。

## C.11 规模化打磨：26 份 ISO 9001 QMS 程序（extra doc）

`typical word doc/extra doc/` 下 26 份同模板 QMS 控制程序（全部零样式），脚本 [scripts/survey_extra.py](../scripts/survey_extra.py)。**暴露并修复一个会推翻 Q217 的关键 bug**：

**Bug：`N、`（阿拉伯数字+顿号）被 Q217 硬判为 list → QMS 的 L1 章节全丢**。
QMS 章节用 `1、目的` `2、范围` `3、权责` `4、定义` `5、工作流程` `6相关文件` `7 表单` 作 L1（粗体），子节点用 `3.1、` `5.2.1、`。Q217「`N、` 默认 list」把这些 L1 全压制，body_start 错跳到 `3.1`。

**这与危险源文档冲突**：危险源 `1、设有消防…`（长、非粗体）是正文条款。同一 `N、` 记号两种语义。

**修复（v4，已验证不退化）**：`N、` 与 `N+中文直接`（`6相关文件`）改为 **weak_heading**（需粗体/上下文才升），不再硬判 list；`N+空格`（`1 目的`）、`N.` 保持 heading。判别核心 = **粗体**：
- QMS `1、目的`（粗体短）→ weak+bold = MEDIUM ✓
- 危险源 `7、车间…`（非粗体短）→ weak = LOW（不误判）✓
- 02/05 `1 目的`（N+空格非粗体）→ heading = MEDIUM ✓（不退化）

**验证结果**：

| 测试集 | 文档数 | 修复后 |
|---|---|---|
| 5 份零样式 fixture（回归）| 5 | v3 自动 P=1.0 / R=0.70（无退化，危险源 P 恢复 1.0）|
| 26 份 QMS（survey）| 26 | body_start 全部修正到首个 L1（1/2），L1 章节 1-7 全捞回 |
| QMS doc01 定量 GT | 1 | **P=1.00 / R=0.69 / FP=0** |

QMS 的 R=0.69 缺口与 fixture 同源——融合式 `3.3、管理者代表：组织各部门…`（号+正文同段长）靠选择性模式批量兜。**跨 31 份文档 P 恒为 1.0、零新增误报，泛化稳。**

**异常**：`程序文件目录.docx`（程序清单/目录，非 SOP）解析 0 章节——属正确行为（它本就无章节结构），前端可提示「非标准程序文档」。

> **本节修订 Q217**：`N、` 从「默认 list」改为「**weak_heading（上下文/粗体判定）**」。原 Q217 的文档级「视为标题」开关保留为边缘兜底。详见下方 §27.4 更新。

---

# 12. 内容完整性：范围决策与待补清单（2026-05-31）

围绕「能否保证文字/表格/图片 100% 不丢失」的评估结论：**正文范围内的常规文字 / 表格 / 内联与锚定图片接近无损，且有 C001/C002 对账 + 人工审查兜底；但不是逐字节无损转换**。本节固化哪些遗漏是**有意裁剪**、哪些是**待补缺口**。

贯穿原则：当前管线在「可能丢内容」时倾向 **静默降级 + 一条没人看的 warning**；要逼近「不丢」，须把每个丢失点改成 **要么不丢，要么用户被迫知情并主动放行**。「手动调节」能兜底的前提是用户先知道这里少了东西——所以下列补全的本质，都是把「看不见的丢失」变成「看得见的 review 项」。

## 12.1 有意裁剪（不补，已决策）

**不解析页眉 / 页脚（`header*.xml` / `footer*.xml`），不补回页脚正文。** 理由：
1. 页眉页脚的典型内容（文档标题、章节名、页码、"第 X 页 共 Y 页"）是**导航性 / 重复性元素**，非正文；页码尤其在构建目录树后**重新生成**，保留原值反成脏数据。
2. 对 SOP/QMS 文件，页眉页脚里真正有信息量的是**受控元数据**（文件编号、版本/修订号、生效日期、密级、公司/LOGO、受控章）。这些在本系统里**本就是结构化字段**（procedure code、version、生效日期，由导入表单 + 审批流维护），应来自系统字段而非 docx 页眉文本——解析它们反而会产生与结构化字段冲突的重复内容。

**保留的边缘风险（低概率，暂不处理）**：极少数不规范文档把实质内容（适用范围说明、签批栏、分发清单）塞进页眉页脚区域。规范 QMS 里签批栏/修订记录/分发清单几乎都是正文独立表格（会被表格解析正常抽取）。**复核触发条件**：真实文档批量跑后若出现「关键内容仅存在于页眉页脚」的反例，再针对性补。

## 12.2 待补清单（已接受，按收益排序）

### A. C001 / C003 升级为「强确认」（非静默 warning）

> **✅ 已实现（2026-05-31）**，且扩展为 C001+C002+C003 任一不匹配触发。设计见 `docs/superpowers/specs/2026-05-31-completeness-strong-confirm-design.md`。实现期发现并修正两处文档未提的漂移：①前端原本把 warnings 整个丢弃；②导入是 upload→parse→import 直通、无 step3 闸口（强确认插在 parse 与 import 之间）。`ParseWarning.severity`(blocking/info) 为 A/B/C 共用地基。
- **C003 阈值 95% → 100%**（`completeness.py:42`，`kept / raw >= 0.95` 改为 `raw == kept`）：现状允许最多 5% 段落静默丢失仍判通过，仅靠"normalize 与口径 1:1"的信任假设。
- **C001 图片数不匹配、C003 段落数不足 → 由 warning 升级为「强确认」**：不让用户在"有图/有段丢失"状态下默默完成导入，须弹出「检测到 N 项未能提取，是否仍要继续」并显式放行。
- 折中说明：采用**强确认**而非**硬拦截**——拦住的是"用户没意识到丢了东西"，而非禁止导入不规范文档（硬拦截会在遇到脏文档时卡死用户）。

### B. 公式（OMML）/ SmartArt / 图表 占位兜底

> **✅ 已实现（2026-06-01）**。设计见 `docs/superpowers/specs/2026-06-01-formula-smartart-placeholder-design.md`。公式行内 `[公式]` 占位；SmartArt/chart 有 run 内缓存位图就当图、否则块状 `[SmartArt 图示]`/`[图表]` 占位；含占位 content 节点标 review（改 import_service 放行 content review）；新增完整性兜底 C007（独立扫描原始数 vs 插入占位数，失配 blocking）。已知 limitation：表格单元格内公式/图形不在范围。
- **现状静默消失**：公式存于 `<m:oMath>`（内部 `<m:r>/<m:t>`，非 `<w:t>`），抽文本逻辑看不到；SmartArt/chart 经 `<a:graphic>` 引用独立 part，非 `blip`，抽图逻辑看不到。两者在原位置变空白，**连 warning 都没有**。
- **补**：检测到 `<m:oMath>` → 原位插入占位块（`[公式]` 文本占位，或公式渲染/截图成图）+ `mark_status="review"`；检测到 SmartArt/chart 引用 → 插入图片/文字占位 + review，优先提取 Word 缓存的 fallback PNG 作替代图。**并把这些计入 C001/计数分母**，否则丢失无人知。
- 目标不是完美还原排版，而是保证"这里原本有东西"这一事实不丢、用户在审查页能看到并处理。

### C. EMF/WMF 无 LibreOffice 时阻断告警

> **✅ 已实现（2026-06-01）**。设计见 `docs/superpowers/specs/2026-06-01-emf-wmf-blocking-warning-design.md`。
> **修正本节原"现状"描述的漂移**：原文称转换失败「降级占位符 + review」，但实现前的真实现状是 `write_temp_media` **既不加占位、也不标 review**，原样保留无法渲染的 EMF（导入后临时 URL 还会过期）——即「静默留一张坏图」。C 项把现状补成本节设想的「占位 + review」并加阻断告警。

- **原"现状"（已被 C 项改写）**：EMF/WMF 矢量图（常见于 Visio/旧 Office 粘贴的流程图）需 `soffice` headless 转 PNG；机器无 LibreOffice 或转换失败 → `convert_to_png` 返回 `None`（`images.py:57-78`）。
- **补**：
  - 解析含 EMF/WMF 的文档时若 `soffice_available()` 为假 → 给**醒目阻断式告警**（而非埋进 warnings），明确"本环境无法转换矢量图，N 张图将以占位符导入"并要求确认。
  - 部署/健康检查把 LibreOffice 列为**软依赖探测项**：服务启动探测一次，缺失则在管理后台亮警示，避免"悄悄缺能力"。

## 12.3 不丢失的最终兜底（已具备）
`source_docx_service` **永久保存原始 .docx**（按 procedure_group 存档）。故原始文档本身永不丢失、可随时下载追溯——这保障"数据可追溯"，但不等于"解析进结构化数据的内容 100% 完整"，二者需区分对待。
