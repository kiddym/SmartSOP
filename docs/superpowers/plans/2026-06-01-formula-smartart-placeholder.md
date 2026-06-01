# 公式/SmartArt/chart 占位兜底 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **⚠️ 用户指令 #5：不做任何 git 提交。** 所有「提交」步骤替换为「运行测试确认通过、改动留工作区」。

**Goal:** 检测到公式(`<m:oMath>`)/SmartArt/chart 时原位插入占位（公式行内 `[公式]`；图形有缓存位图当图、否则块状文字占位），含占位的 content 节点标 review，并加完整性兜底计数 C007。

**Architecture:** normalizer 在序列化时插入占位并独立扫描原始数（仿 C001 的 `_count_raw_images` 独立于 `_emit_images`）；structurer 把含占位的 content 块标 `mark_status="review"`；import_service 放行 content 节点 review；completeness 加 C007 比对原始数 vs 插入数（失配→blocking，复用 A 的 severity）。前端加 `.sop-ph` 样式，复查导航零改动（A 机制按 mark_status 工作、类型无关）。

**Tech Stack:** 后端 lxml + SQLAlchemy + pytest（合成 docx 用 `tests/unit/parser/_docx_builder.py`）；前端 Vue3 + Vitest。

---

## 关键设计约束（实现者必读）

1. **占位「插入」与「原始计数」必须独立双路径**：`_serialize_runs` 在实际插入占位时累加 `placeholder_count`；另有独立扫描函数 `_count_raw_placeholders(el)`（仿 `_count_raw_images`）统计原始应占位数 `raw_placeholder_count`。C007 比对二者——插入路径漏插某形态而独立扫描数到 → 失配报警。若用同一段逻辑同时产两数，C007 形同虚设。
2. **图形「是否需占位」判据 = run 作用域无可用位图**：对带 diagram/chart `a:graphicData uri` 的 run，若该 run 内**无任何** `a:blip`/`v:imagedata`（`_emit_images` 会抽到的就不算）→ 需占位；有 → 不占位（图已原位提取，带 fallback 的 SmartArt 即此情形）。插入路径与独立计数路径用**同一判据**但各自独立计算。
3. **公式去重**：`_serialize_runs` 只遍历 container 直接子元素，故 `<m:oMathPara>`（直接子）算一处、其内层 `<m:oMath>` 不会被直接遍历到，无双计；独立扫描用 `el.iter` 会下钻，须按「最外层 math」计（oMathPara 数 + 父非 oMathPara 的 oMath 数）。
4. **作用域限定 top-level 段落**：本期占位检测/计数覆盖正文段落块（`emit_paragraph` 产出的 Block）。表格单元格内的公式/图形不在本期范围（罕见，YAGNI），plan 末尾 §自查 记为已知 limitation。
5. 不追求还原公式/图形真实内容，占位即可。

---

## 文件结构

**后端**
- 修改 `app/parser/utils/opc.py` —— `NS` 加 `m`、`mc`。
- 修改 `app/parser/ir.py` —— `Block` 加 `raw_placeholder_count` / `placeholder_count`。
- 修改 `app/parser/normalizer.py` —— `_serialize_runs` 插占位 + 累加 `placeholder_count`；新增 `_count_raw_placeholders`；`emit_paragraph` 写入两字段；`_RunOut` 加 `placeholder_count`。
- 修改 `app/parser/structurer.py` —— content 块 `placeholder_count>0` → `ParsedNode.mark_status="review"`；`_append_completeness_warnings` 加 C007。
- 修改 `app/parser/validators/completeness.py` —— 新增 `placeholder_count_match`。
- 修改 `app/services/import_service.py:81` —— content 节点放行 review。
- 修改 `tests/unit/parser/_docx_builder.py` —— 加 `formula_para` / `smartart_para` / `chart_para`。

**前端**
- 修改（或新增样式入口）`frontend/src/...` —— `.sop-ph` 占位样式（具体落点见 Task B5）。

**测试**
- `backend/tests/unit/parser/test_normalizer.py`（加公式/图形占位用例）
- `backend/tests/unit/parser/test_completeness.py`（加 C007 用例）
- `backend/tests/unit/parser/test_structurer.py`（加占位→review 用例）
- `backend/tests/unit/services/test_import_service.py`（content review 落库）
- `frontend/tests/unit/...`（占位样式 + content review 导航守护）

---

## Task B1: 公式占位 + Block 计数字段 + 命名空间

**Files:**
- Modify: `backend/app/parser/utils/opc.py:17-23`（NS）
- Modify: `backend/app/parser/ir.py:48-49`（Block 字段）
- Modify: `backend/app/parser/normalizer.py`（`_RunOut`、`_serialize_runs`、`_count_raw_placeholders`、`emit_paragraph`）
- Modify: `backend/tests/unit/parser/_docx_builder.py`（`formula_para`）
- Test: `backend/tests/unit/parser/test_normalizer.py`

- [ ] **Step 1: 加构造器方法 `formula_para`**

`_docx_builder.py` 顶部常量区加：
```python
_M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
```
`DocxBuilder` 内（段落区）加方法：
```python
    def formula_para(self, before: str = "", after: str = "") -> DocxBuilder:
        """段落含一个 OMML 公式（<m:oMathPara><m:oMath>...），可选前后文字。"""
        p = self.doc.add_paragraph()
        if before:
            p.add_run(before)
        omathpara = _et.SubElement(p._p, "{%s}oMathPara" % _M_NS)
        omath = _et.SubElement(omathpara, "{%s}oMath" % _M_NS)
        mr = _et.SubElement(omath, "{%s}r" % _M_NS)
        mt = _et.SubElement(mr, "{%s}t" % _M_NS)
        mt.text = "x^2"
        if after:
            p.add_run(after)
        return self
```
> 注意：`p._p` 是段落的 `<w:p>`；oMathPara 作为其直接子元素，位置在已有 run 之后（before run 已在前）。after 文字会再追加 run，故顺序为 before-run → oMathPara → after-run，符合「原位」语义。

- [ ] **Step 2: 写失败测试**

`test_normalizer.py` 末尾加：
```python
def test_formula_inserts_inline_placeholder() -> None:
    from tests.unit.parser._docx_builder import DocxBuilder
    from app.parser.normalizer import normalize
    from app.parser.utils.opc import DocxPackage
    data = DocxBuilder().formula_para(before="见公式", after="所示").build()
    nd = normalize(DocxPackage(data), synonyms={}, style_overrides={})
    para = next(b for b in nd.blocks if b.kind == "paragraph" and "见公式" in b.text)
    assert '<span class="sop-ph" data-ph="formula">[公式]</span>' in para.html
    # 原位：占位在 before 与 after 之间
    assert para.html.index("见公式") < para.html.index("data-ph=\"formula\"") < para.html.index("所示")
    assert para.placeholder_count == 1
    assert para.raw_placeholder_count == 1


def test_formula_independent_raw_count() -> None:
    """独立扫描计数：oMathPara 直接子 + 裸 oMath 各算一处，无双计。"""
    from tests.unit.parser._docx_builder import DocxBuilder
    from app.parser.normalizer import normalize
    from app.parser.utils.opc import DocxPackage
    data = DocxBuilder().formula_para().formula_para().build()
    nd = normalize(DocxPackage(data), synonyms={}, style_overrides={})
    total_raw = sum(b.raw_placeholder_count for b in nd.blocks)
    total_inserted = sum(b.placeholder_count for b in nd.blocks)
    assert total_raw == 2 and total_inserted == 2
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/parser/test_normalizer.py::test_formula_inserts_inline_placeholder -q`
Expected: FAIL（`Block` 无 `placeholder_count` / 占位未插入）。

- [ ] **Step 4: NS 加 m/mc**

`opc.py` 的 `NS` 字典加两行：
```python
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
```

- [ ] **Step 5: Block 加字段**

`ir.py` 的 `Block` 在 `raw_table_count` 之后加：
```python
    raw_placeholder_count: int = 0  # 独立扫描：原始 oMath + 无可用图的 diagram/chart 数，供 C007 对账
    placeholder_count: int = 0  # 实际插入的占位数（公式 span + 图形块），供 C007 对账
```

- [ ] **Step 6: `_RunOut` 加 placeholder_count + `_serialize_runs` 插公式占位**

`normalizer.py` 的 `_RunOut` dataclass 加字段 `placeholder_count: int`（放在 `max_font` 后）。

`_serialize_runs` 内：函数开头局部变量区加 `placeholder_count = 0`。在 `for child in container:` 循环里、`tag = local(child.tag)` 之后、现有 `if tag in ("hyperlink", ...)` 分支**之前**插入公式分支：
```python
        if tag in ("oMathPara", "oMath"):
            # 直接子层只可能见到最外层 math 容器（oMathPara 内的 oMath 不是 container 直接子）
            parts.append('<span class="sop-ph" data-ph="formula">[公式]</span>')
            placeholder_count += 1
            continue
```
递归分支（hyperlink/ins/smartTag）里把子结果的 placeholder_count 累加：在 `images.extend(sub.images)` 附近加 `placeholder_count += sub.placeholder_count`。
函数末尾 `return _RunOut(...)` 加 `placeholder_count=placeholder_count`。

- [ ] **Step 7: 新增 `_count_raw_placeholders`（独立扫描）**

`normalizer.py` 在 `_count_raw_images` 之后加：
```python
def _count_raw_placeholders(el: etree._Element) -> int:
    """独立统计 el 内应占位的源元素数（供 C007，与插入路径独立）。

    = 最外层 math 容器数（oMathPara + 父非 oMathPara 的 oMath）
      + 无可用位图的 diagram/chart graphic 数（其所属 <w:r> 内无 a:blip/v:imagedata）。
    与 _serialize_runs 的插入判据一致但独立计算。
    """
    n = 0
    # 公式：最外层 math
    for m in el.iter(qn("m:oMathPara")):
        n += 1
    for m in el.iter(qn("m:oMath")):
        parent = m.getparent()
        if parent is None or local(parent.tag) != "oMathPara":
            n += 1
    # 图形：diagram/chart 且所属 run 无位图
    for gd in el.iter(qn("a:graphicData")):
        uri = gd.get("uri") or ""
        if not _is_diagram_or_chart(uri):
            continue
        run = _ancestor_run(gd)
        if run is not None and not _run_has_image(run):
            n += 1
    return n


def _is_diagram_or_chart(uri: str) -> bool:
    return "/diagram" in uri or "/chart" in uri


def _ancestor_run(el: etree._Element) -> etree._Element | None:
    cur = el.getparent()
    while cur is not None:
        if local(cur.tag) == "r":
            return cur
        cur = cur.getparent()
    return None


def _run_has_image(run: etree._Element) -> bool:
    return run.find(".//" + qn("a:blip")) is not None or run.find(".//" + qn("v:imagedata")) is not None
```

- [ ] **Step 8: `emit_paragraph` 写入两字段**

`emit_paragraph` 内 `out = _serialize_runs(para, ctx)` 之后、`raw_blips = _count_raw_images(para)` 附近加：
```python
    raw_placeholders = _count_raw_placeholders(para)
```
`return Block(...)` 加：
```python
        raw_placeholder_count=raw_placeholders,
        placeholder_count=out.placeholder_count,
```

- [ ] **Step 9: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/unit/parser/test_normalizer.py -q`
Expected: PASS（含两条新测 + 既有不回归）。

- [ ] **Step 10: 改动留工作区，不提交**

---

## Task B2: SmartArt/chart 图形占位

**Files:**
- Modify: `backend/app/parser/normalizer.py`（`_serialize_runs` 的 run 分支插图形占位）
- Modify: `backend/tests/unit/parser/_docx_builder.py`（`smartart_para` / `chart_para`）
- Test: `backend/tests/unit/parser/test_normalizer.py`

- [ ] **Step 1: 加构造器方法**

`_docx_builder.py` 加方法：
```python
    def _graphic_run(self, uri: str, with_image: bool, png: bytes | None = None) -> None:
        """在新段落的 run 内放一个 <w:drawing><a:graphic><a:graphicData uri=...>；
        with_image=True 时再在同 run 放一张 v:imagedata（模拟 fallback 缓存图）。"""
        _A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
        p = self.doc.add_paragraph()
        run = p.add_run()
        drawing = _et.SubElement(run._r, "{%s}drawing" % _W_NS)
        graphic = _et.SubElement(drawing, "{%s}graphic" % _A_NS)
        _et.SubElement(graphic, "{%s}graphicData" % _A_NS, attrib={"uri": uri})
        if with_image:
            png = png or tiny_png()
            tmp_p = self.doc.add_paragraph()
            tmp_run = tmp_p.add_run()
            tmp_run.add_picture(io.BytesIO(png), width=Pt(20))
            blip = tmp_run._r.find(".//{%s}blip" % _A_NS)
            rid = blip.get("{%s}embed" % _R_NS)
            tmp_p._p.getparent().remove(tmp_p._p)
            pict = _et.SubElement(run._r, "{%s}pict" % _W_NS)
            shape = _et.SubElement(pict, "{%s}shape" % _V_NS, attrib={"style": "width:20pt;height:20pt"})
            _et.SubElement(shape, "{%s}imagedata" % _V_NS, attrib={"{%s}id" % _R_NS: rid})

    def smartart_para(self, with_fallback: bool = False) -> DocxBuilder:
        self._graphic_run("http://schemas.openxmlformats.org/drawingml/2006/diagram", with_fallback)
        return self

    def chart_para(self) -> DocxBuilder:
        self._graphic_run("http://schemas.openxmlformats.org/drawingml/2006/chart", False)
        return self
```

- [ ] **Step 2: 写失败测试**

`test_normalizer.py` 加：
```python
def test_chart_inserts_block_placeholder() -> None:
    from tests.unit.parser._docx_builder import DocxBuilder
    from app.parser.normalizer import normalize
    from app.parser.utils.opc import DocxPackage
    data = DocxBuilder().chart_para().build()
    nd = normalize(DocxPackage(data), synonyms={}, style_overrides={})
    para = next(b for b in nd.blocks if b.kind == "paragraph" and "sop-ph" in b.html)
    assert 'data-ph="chart"' in para.html
    assert "[图表]" in para.html
    assert para.placeholder_count == 1 and para.raw_placeholder_count == 1


def test_smartart_without_fallback_inserts_placeholder() -> None:
    from tests.unit.parser._docx_builder import DocxBuilder
    from app.parser.normalizer import normalize
    from app.parser.utils.opc import DocxPackage
    data = DocxBuilder().smartart_para(with_fallback=False).build()
    nd = normalize(DocxPackage(data), synonyms={}, style_overrides={})
    para = next(b for b in nd.blocks if b.kind == "paragraph" and "sop-ph" in b.html)
    assert 'data-ph="smartart"' in para.html
    assert para.placeholder_count == 1 and para.raw_placeholder_count == 1


def test_smartart_with_fallback_uses_image_not_placeholder() -> None:
    """带缓存图的 SmartArt → 当图原位提取，不插占位。"""
    from tests.unit.parser._docx_builder import DocxBuilder
    from app.parser.normalizer import normalize
    from app.parser.utils.opc import DocxPackage
    data = DocxBuilder().smartart_para(with_fallback=True).build()
    nd = normalize(DocxPackage(data), synonyms={}, style_overrides={})
    para = next(b for b in nd.blocks if b.kind == "paragraph" and (b.images or "sop-ph" in b.html))
    assert para.images, "应抽到 fallback 图"
    assert "sop-ph" not in para.html
    assert para.placeholder_count == 0 and para.raw_placeholder_count == 0
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/parser/test_normalizer.py::test_chart_inserts_block_placeholder -q`
Expected: FAIL（图形占位未插入）。

- [ ] **Step 4: `_serialize_runs` run 分支插图形占位**

`_serialize_runs` 内处理 `r` 的分支末尾（现有 `for ref in _emit_images(child, ctx): ...` 之后）加：
```python
        # SmartArt/chart：本 run 有 diagram/chart graphicData 且无位图 → 块状占位
        gd = next(
            (g for g in child.iter(qn("a:graphicData")) if _is_diagram_or_chart(g.get("uri") or "")),
            None,
        )
        if gd is not None and not _run_has_image(child):
            kind = "chart" if "/chart" in (gd.get("uri") or "") else "smartart"
            label = "[图表]" if kind == "chart" else "[SmartArt 图示]"
            parts.append(f'<div class="sop-ph" data-ph="{kind}">{label}</div>')
            placeholder_count += 1
```
> 说明：`child` 即当前 run。判据 `not _run_has_image(child)` 与 `_count_raw_placeholders` 一致——带 fallback 位图者 `_emit_images` 已抽图、`_run_has_image` 为真，不插占位、不双计。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/unit/parser/test_normalizer.py -q`
Expected: PASS（含三条新测 + B1 两条 + 既有不回归）。

- [ ] **Step 6: 改动留工作区，不提交**

---

## Task B3: 含占位 content 块 → review（structurer + import）

**Files:**
- Modify: `backend/app/parser/structurer.py`（content 块产出处，约 165-177 行）
- Modify: `backend/app/services/import_service.py:81`
- Test: `backend/tests/unit/parser/test_structurer.py`、`backend/tests/unit/services/test_import_service.py`

- [ ] **Step 1: 写失败测试（structurer）**

`test_structurer.py` 加（沿用该文件已有的 normalize→structure 调用方式；下例给出独立可跑形态，若文件已有 helper 构造 pkg 可复用）：
```python
def test_content_block_with_placeholder_marked_review() -> None:
    from tests.unit.parser._docx_builder import DocxBuilder
    from app.parser.normalizer import normalize
    from app.parser.structurer import structure
    from app.parser.utils.opc import DocxPackage
    data = (
        DocxBuilder()
        .heading("目的", level=1)
        .formula_para(before="计算式")
        .para("普通正文无占位")
        .build()
    )
    pkg = DocxPackage(data)
    nd = normalize(pkg, synonyms={}, style_overrides={})
    result = structure(nd, pkg=pkg, mode="smart", synonyms={}, style_overrides={})
    # 找「目的」章节下的 content 子节点
    chapter = result.chapters[0]
    contents = [c for c in chapter.children if c.content_type == "content"]
    ph_node = next(c for c in contents if "sop-ph" in c.rich_content)
    plain_node = next(c for c in contents if "普通正文" in c.rich_content)
    assert ph_node.mark_status == "review"
    assert plain_node.mark_status == "unmarked"
    assert result.review_required >= 1
```

- [ ] **Step 2: 确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/parser/test_structurer.py::test_content_block_with_placeholder_marked_review -q`
Expected: FAIL（content 节点恒 unmarked，无 review）。

- [ ] **Step 3: structurer 给含占位 content 块标 review**

`structurer.py` 的 content 子节点产出处（现为）：
```python
        current = stack[-1][1]
        content_node = ParsedNode(
            id=_new_id(),
            title="",
            level=current.level + 1,
            content_type="content",
            rich_content=block.html,
        )
        current.children.append(content_node)
        image_refs.extend(block.images)
        image_count += len(block.images)
        if block.kind == "table":
            table_count += 1
```
改为：在构造 `content_node` 时按占位置 review，并计数：
```python
        current = stack[-1][1]
        content_mark = "review" if block.placeholder_count > 0 else "unmarked"
        content_node = ParsedNode(
            id=_new_id(),
            title="",
            level=current.level + 1,
            content_type="content",
            rich_content=block.html,
            mark_status=content_mark,
        )
        current.children.append(content_node)
        if content_mark == "review":
            review_required += 1
        image_refs.extend(block.images)
        image_count += len(block.images)
        if block.kind == "table":
            table_count += 1
```

- [ ] **Step 4: 确认通过（structurer）**

Run: `cd backend && .venv/bin/pytest tests/unit/parser/test_structurer.py::test_content_block_with_placeholder_marked_review -q`
Expected: PASS。

- [ ] **Step 5: 写失败测试（import 放行 content review）**

`test_import_service.py` 加：
```python
def test_content_node_review_persisted(db: Session, factory: Factory, storage_tmp) -> None:
    from app.models.node import ProcedureNode
    proc = import_service.import_procedure(
        db, name="P", folder_id=_leaf(factory), description="",
        chapters=[ImportNodeIn(title="目的", content_type="chapter", children=[
            ImportNodeIn(content_type="content", rich_content='<p><span class="sop-ph">[公式]</span></p>',
                         mark_status="review"),
        ])],
        meta=META,
    )
    nodes = db.query(ProcedureNode).filter_by(procedure_id=proc.id, is_active=True).all()
    content = next(n for n in nodes if n.heading_level is None)
    assert content.mark_status == "review"
```

- [ ] **Step 6: 确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/services/test_import_service.py::test_content_node_review_persisted -q`
Expected: FAIL（import_service:81 恒置 content 为 unmarked）。

- [ ] **Step 7: import_service 放行 content review**

`import_service.py` 的 content 分支（约 :69-79）`mark_status="unmarked"` 改为：
```python
                        mark_status="review" if n.mark_status == "review" else "unmarked",
```

- [ ] **Step 8: 确认通过**

Run: `cd backend && .venv/bin/pytest tests/unit/services/test_import_service.py -q`
Expected: PASS。

- [ ] **Step 9: 改动留工作区，不提交**

---

## Task B4: 完整性兜底 C007

**Files:**
- Modify: `backend/app/parser/validators/completeness.py`
- Modify: `backend/app/parser/structurer.py`（`_append_completeness_warnings`）
- Test: `backend/tests/unit/parser/test_completeness.py`

- [ ] **Step 1: 写失败测试**

`test_completeness.py` 加：
```python
def test_c007_passes_when_raw_equals_inserted() -> None:
    blocks = [
        Block(kind="paragraph", source_index=0, raw_placeholder_count=2, placeholder_count=2),
        Block(kind="paragraph", source_index=1, raw_placeholder_count=0, placeholder_count=0),
    ]
    ok, raw, inserted = completeness.placeholder_count_match(blocks)
    assert ok is True and raw == 2 and inserted == 2


def test_c007_fails_when_placeholder_missing() -> None:
    """独立扫描数到 3，插入只 2（模拟插入路径漏插一种形态）→ fail。"""
    blocks = [
        Block(kind="paragraph", source_index=0, raw_placeholder_count=3, placeholder_count=2),
    ]
    ok, raw, inserted = completeness.placeholder_count_match(blocks)
    assert ok is False and raw == 3 and inserted == 2
```

- [ ] **Step 2: 确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/parser/test_completeness.py::test_c007_passes_when_raw_equals_inserted -q`
Expected: FAIL（`placeholder_count_match` 不存在）。

- [ ] **Step 3: 加 `placeholder_count_match`**

`completeness.py` 末尾加：
```python
def placeholder_count_match(body_blocks: Sequence[Block]) -> tuple[bool, int, int]:
    """C007：原始应占位数（独立扫描）vs 实际插入占位数。

    公式/SmartArt/chart 的兜底——独立扫描计 raw、序列化插入计 inserted，二者
    本应相等；不等说明插入路径漏插某形态，须报警以免静默丢失。
    """
    raw = sum(b.raw_placeholder_count for b in body_blocks)
    inserted = sum(b.placeholder_count for b in body_blocks)
    return raw == inserted, raw, inserted
```

- [ ] **Step 4: structurer 加 C007 warning**

`structurer.py` 的 `_append_completeness_warnings` 末尾加：
```python
    ph_ok, ph_raw, ph_ins = completeness.placeholder_count_match(body_blocks)
    if not ph_ok:
        warnings.append(
            ParseWarning(
                stage="completeness",
                message=f"公式/图示可能遗漏：原始 {ph_raw} / 占位 {ph_ins}",
                severity="blocking",
            )
        )
```

- [ ] **Step 5: 确认通过**

Run: `cd backend && .venv/bin/pytest tests/unit/parser/test_completeness.py -q`
Expected: PASS。

- [ ] **Step 6: 后端全量回归**

Run: `cd backend && .venv/bin/pytest -q`
Expected: 全 PASS（确认占位/计数/review/C007 无回归；尤其既有 normalizer/structurer/completeness/import 套件）。

- [ ] **Step 7: 改动留工作区，不提交**

---

## Task B5: 前端占位样式 + content review 导航守护

**Files:**
- Modify: `frontend/src/...`（占位样式落点见下）
- Test: `frontend/tests/unit/...`

- [ ] **Step 1: 定位占位渲染与样式落点**

先读 `frontend/src/components/editor/RichTextEditor.vue` 与 `frontend/src/components/PdfPreview/PdfPreviewDialog.vue`，确认 content `rich_content` 经 v-html / WangEditor 渲染（A 阶段勘察已知）。占位 `.sop-ph` 是 rich_content 内的 HTML，需要一处**全局或编辑器作用域**的 CSS 命中 `.sop-ph`。落点二选一（按仓库既有特殊元素样式惯例，如 §4.3 `.alert`/`.note` 的处理方式）：
  - 若已有「正文特殊元素全局样式表」（grep `.alert` / `.note` 的 css）→ 在同文件加 `.sop-ph` 规则。
  - 否则在编辑器预览样式处（RichTextEditor / EditorPreviewPane 的 `<style>`，非 scoped 或用 `:deep()`）加。

- [ ] **Step 2: 写失败测试（占位样式存在性 / 渲染）**

新建 `frontend/tests/unit/parsePlaceholder.spec.ts`，对承载占位的渲染组件做最小守护——挂载一个含 `<span class="sop-ph" data-ph="formula">[公式]</span>` 的 content，断言渲染出该元素且带 `sop-ph` class：
```typescript
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

// 以最小宿主组件验证 sop-ph HTML 能被渲染（v-html 路径）
const Host = {
  props: { html: { type: String, default: '' } },
  template: '<div class="content-node" v-html="html" />',
}

describe('sop-ph 占位渲染', () => {
  it('formula 占位渲染为带 class 的 span', () => {
    const w = mount(Host, { props: { html: '<p><span class="sop-ph" data-ph="formula">[公式]</span></p>' } })
    const ph = w.find('span.sop-ph')
    expect(ph.exists()).toBe(true)
    expect(ph.attributes('data-ph')).toBe('formula')
    expect(ph.text()).toBe('[公式]')
  })

  it('chart 占位渲染为带 class 的 div', () => {
    const w = mount(Host, { props: { html: '<div class="sop-ph" data-ph="chart">[图表]</div>' } })
    expect(w.find('div.sop-ph[data-ph="chart"]').exists()).toBe(true)
  })
})
```
> 该测试守护占位 HTML 结构契约（前后端一致）；视觉样式由 Step 3 的 CSS 提供，不在单测断言范围。

- [ ] **Step 3: 确认失败 → 加样式 → 确认通过**

Run: `cd frontend && npx vitest run tests/unit/parsePlaceholder.spec.ts`（结构测试此时应已能过，因为只验证 v-html 渲染；若过，说明结构契约已满足）。
然后在 Step 1 选定的样式落点加：
```css
.sop-ph {
  display: inline-block;
  padding: 0 6px;
  margin: 0 2px;
  font-size: 12px;
  color: #b88230;
  background: #fdf6ec;
  border: 1px dashed #f5dab1;
  border-radius: 3px;
}
.sop-ph[data-ph="smartart"],
.sop-ph[data-ph="chart"] {
  display: block;
  padding: 8px 12px;
  margin: 6px 0;
  text-align: center;
}
```

- [ ] **Step 4: content review 导航守护（vitest）**

确认 A 阶段的复查机制对 content 节点同样生效。先 grep 现有复查计数/导航测试（如 `tests/unit/utils/` 下针对 `reviewCount` / `nextReviewId` / `visibleRows` 的测试，或 `NodeTreePanel.spec.ts`），加一条断言：一棵含 `content_type==='content'` 且 `mark_status==='review'` 的节点 → 进入复查计数 / 「仅看待确认」可见 / 「下一个」可达。具体断言形态对齐你找到的现有同类测试的构造方式（节点 fixture + 调 store/util）。最小目标：证明 content review 节点不被复查逻辑按类型过滤掉。

- [ ] **Step 5: 前端全量回归**

Run: `cd frontend && npx vitest run`
Expected: 全 PASS。再 `npx vue-tsc --noEmit -p tsconfig.json 2>&1 | tail -20` 确认无新增类型错误。

- [ ] **Step 6: 改动留工作区，不提交**

---

## 自查（spec 覆盖 / 占位 / 类型一致）

**Spec 覆盖：**
- §3.1 NS m/mc → B1 ✓
- §3.2 公式行内占位 → B1 ✓
- §3.3 SmartArt/chart 有图用图、无图文字占位、不双重处理 → B2（判据 `_run_has_image` 一致）✓
- §3.4 Block 双字段、独立双路径 → B1（`placeholder_count` 插入侧 + `_count_raw_placeholders` 独立侧）✓
- §3.5 含占位 content 块 → review → B3 ✓
- §3.6 import 放行 content review → B3 ✓
- §3.7 C007 → B4 ✓
- §4.1 占位样式 → B5 ✓
- §4.2 复查导航零逻辑改动（守护）→ B5 Step4 ✓
- §6 测试计划 → 各 Task TDD + 后端全量（B4 Step6）+ 前端全量（B5 Step5）✓

**占位扫描：** B5 Step1/Step4 留了「按仓库既有惯例定样式落点 / 对齐现有复查测试构造」的弹性说明——因前端样式落点与复查测试夹具形态需就地对齐，最小契约已给死（`.sop-ph` 结构、content review 不被类型过滤）。后端步骤均为完整代码。

**类型/判据一致：** 插入侧（`_serialize_runs`）与独立计数侧（`_count_raw_placeholders`）共用 `_is_diagram_or_chart` / `_run_has_image` 判据，保证 C007 在「检测完整」时恒相等、仅插入 bug 时失配。占位 HTML 契约（`sop-ph` / `data-ph` / `[公式]`/`[图表]`/`[SmartArt 图示]`）后端产出（B1/B2）与前端测试（B5）一致。`raw_placeholder_count`/`placeholder_count` 字段名在 ir.py 定义、normalizer 写入、completeness 读取三处一致。

**已知 limitation（YAGNI，已记）：** 表格单元格内的公式/图形不在本期占位/计数范围（罕见）；如未来出现真实反例再扩到 `emit_table`/`_cell_inner`。
