# Word Parser — VML 图与文本框补全 + 完整性校验分母修复

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `v:imagedata`（VML 老格式图）和 `w:txbxContent`（文本框正文）不再被 SmartSOP 解析器静默丢失；同时让 C001/C002 完整性校验的 raw 分母覆盖这两种来源，使任何未来的扩散性遗漏都被 warning 捕获。

**Architecture:**
- 后端 `app/parser/normalizer.py` 在 `_emit_images` 增加 `v:imagedata` 抽取分支；在 `normalize()` 主循环对每个 paragraph/table 额外下钻 `w:txbxContent` 子树，把其中的 `<w:p>`/`<w:tbl>` 作为附加 IR Block 顺位插入。
- 引入 `_is_inside_txbx()` guard 防止外层段落与内层抽取双计图片。
- `emit_paragraph` / `emit_table` 的 `raw_image_count` 改用统一 `_count_raw_images()` helper，分母同步增加 `v:imagedata`；txbx 内的图片由内层段落单独计入，外层不重复。
- `app/parser/validators/completeness.py` 接口不变，行为由 IR 计数器变化自动收紧。

**Tech Stack:** Python 3.12 / lxml / python-docx / pytest（仓库现有栈）。本机无 uv：所有 Python 命令用 `backend/.venv/bin/python`（见 memory `uv-missing-use-venv-python`）。

**Scope guard:** 仅改 `backend/app/parser/normalizer.py`、`backend/app/parser/validators/completeness.py`、对应单元/集成测试与 fixture builder。**不动**前端、schema、DB、API、router、import_service、asset_service。

**Known limitation (v1):** 表格 cell 内的文本框会被抽取为独立 IR Block（与表格平级紧邻），而非嵌入回 cell HTML 内；视觉上的"在表格内"位置不保留。若 SOP 模板有"表格 cell 内放注意框"的强约束，可在 v2 让 `_cell_inner` 把 txbx 子段内联到 cell HTML。当前方案不丢内容、不丢图、不双计，已满足"完整提取"目标。

---

## File Structure

**Modify:**
- `backend/app/parser/normalizer.py` — 加 `_is_inside_txbx`、`_count_raw_images`、扩 `_emit_images`、扩 `normalize()` 下钻 txbxContent
- `backend/tests/unit/parser/_docx_builder.py` — 加 `vml_image_para()`、`textbox_para()`、`textbox_with_image_para()` 方法

**Create:**
- `backend/tests/unit/parser/test_completeness.py` — 新单测文件（completeness 当前无独立 test）

**Modify (tests):**
- `backend/tests/unit/parser/test_normalizer.py` — 加 4 个新测试
- `backend/tests/unit/parser/test_pipeline.py` — 加 1 个集成场景

每个文件单一职责：normalizer.py 负责 IR 生成，completeness.py 负责对账，fixture builder 负责合成 docx 字节流。

---

## Task 1: Fixture Builder — VML 图与文本框构造方法

**Files:**
- Modify: `backend/tests/unit/parser/_docx_builder.py`

新增 3 个 builder 方法，让后续测试能合成包含 VML / textbox 的 docx 字节流。直接用 lxml 注入到 python-docx 生成的 run 内部，避开 python-docx 自身对 VML/textbox 的不完整支持。

- [ ] **Step 1: 在 `_docx_builder.py` 顶部 import 处加 lxml 与 namespace 常量**

打开 `backend/tests/unit/parser/_docx_builder.py`，在现有 import 块后追加：

```python
from lxml import etree as _et

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_V_NS = "urn:schemas-microsoft-com:vml"
_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
```

- [ ] **Step 2: 加 `vml_image_para` 方法到 `DocxBuilder` 类**

在 `DocxBuilder.image_para` 方法**之后**插入：

```python
    def vml_image_para(self, png: bytes | None = None) -> DocxBuilder:
        """段落 run 内嵌一张 VML 老格式图（v:imagedata），同时复用 docx 的图片关系。"""
        png = png or tiny_png()
        # 先用 add_picture 走标准路径注入图片关系（拿到 rid + 落 media part）
        tmp_p = self.doc.add_paragraph()
        tmp_run = tmp_p.add_run()
        tmp_run.add_picture(io.BytesIO(png), width=Pt(20))
        blip = tmp_run._r.find(".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip")
        assert blip is not None
        rid = blip.get("{%s}embed" % _R_NS)
        # 删除临时段落（关系/媒体已保留）
        tmp_p._p.getparent().remove(tmp_p._p)
        # 构造真正的 VML 段落
        target_p = self.doc.add_paragraph()
        run = target_p.add_run()
        pict = _et.SubElement(run._r, "{%s}pict" % _W_NS)
        shape = _et.SubElement(
            pict, "{%s}shape" % _V_NS, attrib={"style": "width:20pt;height:20pt"}
        )
        _et.SubElement(shape, "{%s}imagedata" % _V_NS, attrib={"{%s}id" % _R_NS: rid})
        return self
```

- [ ] **Step 3: 加 `textbox_para` 方法**

在 `vml_image_para` 之后追加：

```python
    def textbox_para(self, inner_text: str) -> DocxBuilder:
        """段落 run 内嵌一个 VML 文本框，含一段子段落文字。"""
        p = self.doc.add_paragraph()
        run = p.add_run()
        pict = _et.SubElement(run._r, "{%s}pict" % _W_NS)
        shape = _et.SubElement(
            pict, "{%s}shape" % _V_NS, attrib={"style": "width:120pt;height:30pt"}
        )
        tbx = _et.SubElement(shape, "{%s}textbox" % _V_NS)
        tcontent = _et.SubElement(tbx, "{%s}txbxContent" % _W_NS)
        inner_p = _et.SubElement(tcontent, "{%s}p" % _W_NS)
        inner_r = _et.SubElement(inner_p, "{%s}r" % _W_NS)
        inner_t = _et.SubElement(inner_r, "{%s}t" % _W_NS)
        inner_t.text = inner_text
        return self
```

- [ ] **Step 4: 加 `textbox_with_image_para` 方法**（验证图位归属与防双计）

紧接其后追加：

```python
    def textbox_with_image_para(self, inner_text: str, png: bytes | None = None) -> DocxBuilder:
        """文本框内含「文字 + 内联图（a:blip）」的段落——验证 txbx 内图归属内层 block。"""
        png = png or tiny_png()
        # 先借标准 add_picture 注册图片关系
        tmp_p = self.doc.add_paragraph()
        tmp_run = tmp_p.add_run()
        tmp_run.add_picture(io.BytesIO(png), width=Pt(20))
        blip = tmp_run._r.find(".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip")
        rid = blip.get("{%s}embed" % _R_NS)
        # 取出 drawing 子树备用，再删 tmp 段落
        drawing = tmp_run._r.find("{%s}drawing" % _W_NS)
        drawing_copy = _et.fromstring(_et.tostring(drawing))
        tmp_p._p.getparent().remove(tmp_p._p)
        # 构造外层段落 → pict → shape → textbox → txbxContent → p(text + drawing)
        outer = self.doc.add_paragraph()
        run = outer.add_run()
        pict = _et.SubElement(run._r, "{%s}pict" % _W_NS)
        shape = _et.SubElement(
            pict, "{%s}shape" % _V_NS, attrib={"style": "width:140pt;height:60pt"}
        )
        tbx = _et.SubElement(shape, "{%s}textbox" % _V_NS)
        tcontent = _et.SubElement(tbx, "{%s}txbxContent" % _W_NS)
        inner_p = _et.SubElement(tcontent, "{%s}p" % _W_NS)
        inner_r = _et.SubElement(inner_p, "{%s}r" % _W_NS)
        inner_t = _et.SubElement(inner_r, "{%s}t" % _W_NS)
        inner_t.text = inner_text
        inner_r.append(drawing_copy)
        _ = rid  # 用于静默 lint；rid 已经在 drawing_copy 的 r:embed 中
        return self
```

- [ ] **Step 5: 自检：fixture 能成功构造 docx 字节流（不解析、只构造）**

Run:

```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
backend/.venv/bin/python -c "
from backend.tests.unit.parser._docx_builder import DocxBuilder
b1 = DocxBuilder().vml_image_para().build()
b2 = DocxBuilder().textbox_para('注意：高压').build()
b3 = DocxBuilder().textbox_with_image_para('内图测试').build()
print('vml bytes:', len(b1), 'txbx bytes:', len(b2), 'txbx+img bytes:', len(b3))
"
```

Expected: 三个 `len(...)` 均 > 0；无异常。

- [ ] **Step 6: Commit**

```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
git add backend/tests/unit/parser/_docx_builder.py
git commit -m "test(parser): add VML imagedata + textbox docx fixture builders"
```

---

## Task 2: TDD — `v:imagedata` 图片抽取

**Files:**
- Test: `backend/tests/unit/parser/test_normalizer.py`
- Modify: `backend/app/parser/normalizer.py:86-109` (`_emit_images`)

- [ ] **Step 1: 写失败测试 — VML 图片应进入 `blk.images`**

在 `backend/tests/unit/parser/test_normalizer.py` 文件**末尾**追加：

```python
def test_vml_imagedata_extracted_as_image_ref() -> None:
    """v:imagedata（VML 老格式图）应当被 _emit_images 抽取，不再静默丢失。"""
    data = DocxBuilder().vml_image_para().build()
    nd = _normalize(data)
    img_blocks = [b for b in nd.blocks if b.images]
    assert len(img_blocks) == 1, f"expected 1 paragraph with image, got {len(img_blocks)}"
    img = img_blocks[0].images[0]
    assert img.rid  # rid 不为空
    assert img.data and len(img.data) > 0  # 媒体字节读到了
    assert img.ext in (".png", ".jpg", ".jpeg")
```

- [ ] **Step 2: 运行测试确认 RED**

```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
backend/.venv/bin/python -m pytest backend/tests/unit/parser/test_normalizer.py::test_vml_imagedata_extracted_as_image_ref -v
```

Expected: FAIL，`expected 1 paragraph with image, got 0`（VML 图未被抽取）。

- [ ] **Step 3: 修改 `_emit_images` 增加 VML 分支**

打开 `backend/app/parser/normalizer.py`，定位到 `_emit_images` 函数（约 L86-109），整体替换为：

```python
def _emit_images(run: etree._Element, ctx: _Ctx) -> list[ImageRef]:
    """收集一个 run 内全部图片（a:blip inline/anchor + v:imagedata VML），按 XML 顺序。

    跳过 w:txbxContent 内的图：那些由 normalize() 的 txbx 下钻分支单独抽取，
    在此重复抽取会导致双计（见 _count_raw_images 同步策略）。
    """
    refs: list[ImageRef] = []
    # a:blip — 现代 DrawingML 图（含 inline / anchor）
    for blip in run.iter(qn("a:blip")):
        if _is_inside_txbx(blip):
            continue
        rid = blip.get(qn("r:embed")) or blip.get(qn("r:link"))
        if not rid:
            continue
        data = ctx.pkg.read_media(rid)
        if data is None:
            continue
        part = ctx.pkg.media_part_for_rid(rid) or ""
        ext = ("." + part.rsplit(".", 1)[1].lower()) if "." in part else ".png"
        anchor = run.find(".//" + qn("wp:anchor")) is not None
        refs.append(
            ImageRef(
                rid=rid,
                part_name=part,
                data=data,
                ext=ext,
                anchor=anchor,
                placeholder=f"media:{rid}",
            )
        )
    # v:imagedata — Word 97-2003 / VML 兼容路径（剪贴画、转存图等）
    for vimg in run.iter(qn("v:imagedata")):
        if _is_inside_txbx(vimg):
            continue
        rid = vimg.get(qn("r:id")) or vimg.get(qn("r:embed"))
        if not rid:
            continue
        data = ctx.pkg.read_media(rid)
        if data is None:
            continue
        part = ctx.pkg.media_part_for_rid(rid) or ""
        ext = ("." + part.rsplit(".", 1)[1].lower()) if "." in part else ".png"
        refs.append(
            ImageRef(
                rid=rid,
                part_name=part,
                data=data,
                ext=ext,
                anchor=False,
                placeholder=f"media:{rid}",
            )
        )
    return refs
```

- [ ] **Step 4: 在 `_emit_images` 之前新增 `_is_inside_txbx` helper**

定位到 `_emit_images` 函数定义**之前**（约 L85），插入：

```python
def _is_inside_txbx(el: etree._Element) -> bool:
    """元素是否处于 w:txbxContent 子树下（用于跳过外层段落对 txbx 内图的重复抽取）。"""
    parent = el.getparent()
    while parent is not None:
        if local(parent.tag) == "txbxContent":
            return True
        parent = parent.getparent()
    return False
```

- [ ] **Step 5: 运行测试确认 GREEN，且既有 normalizer 测试不回退**

```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
backend/.venv/bin/python -m pytest backend/tests/unit/parser/test_normalizer.py -v
```

Expected: 全部通过，包括新 `test_vml_imagedata_extracted_as_image_ref`。

- [ ] **Step 6: Commit**

```bash
git add backend/app/parser/normalizer.py backend/tests/unit/parser/test_normalizer.py
git commit -m "feat(parser): extract v:imagedata (VML legacy images) in _emit_images"
```

---

## Task 3: TDD — `w:txbxContent` 段落抽取

**Files:**
- Test: `backend/tests/unit/parser/test_normalizer.py`
- Modify: `backend/app/parser/normalizer.py:365-402` (`normalize()` 主循环)

- [ ] **Step 1: 写失败测试 — 文本框内文字应作为附加 paragraph block 出现**

在 `test_normalizer.py` 末尾追加：

```python
def test_textbox_content_extracted_as_block() -> None:
    """文本框（v:textbox > w:txbxContent）内的段落应作为独立 IR Block 抽出。"""
    data = (
        DocxBuilder()
        .para("外层段落 A")
        .textbox_para("注意：高压电气设备")
        .para("外层段落 B")
        .build()
    )
    nd = _normalize(data)
    texts = [b.text.strip() for b in nd.blocks if b.kind == "paragraph"]
    assert "外层段落 A" in texts
    assert "外层段落 B" in texts
    assert "注意：高压电气设备" in texts, f"textbox text missing from blocks: {texts}"
```

- [ ] **Step 2: 写第二个失败测试 — 文本框内图归属内层 block，不重复计入外层**

```python
def test_textbox_image_attributed_to_inner_block_not_outer() -> None:
    """txbx 内的图应归属内层 block，外层段落 images 列表为空（防双计）。"""
    data = DocxBuilder().textbox_with_image_para("内图测试").build()
    nd = _normalize(data)
    para_blocks = [b for b in nd.blocks if b.kind == "paragraph"]
    # 应该有 2 个段落 block：外层（无图无字）+ 内层（含字含图）
    inner = next((b for b in para_blocks if "内图测试" in b.text), None)
    assert inner is not None, "inner textbox paragraph missing"
    assert len(inner.images) == 1, f"inner block should own the image, got {len(inner.images)}"
    # 外层段落不应再持有同一张图
    outer = next((b for b in para_blocks if b is not inner and not b.text.strip()), None)
    if outer is not None:
        assert len(outer.images) == 0, "outer paragraph must not double-count txbx image"
    # 全文图总数 == 1
    assert nd.total_image_count == 1
```

- [ ] **Step 3: 运行测试确认 RED**

```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
backend/.venv/bin/python -m pytest backend/tests/unit/parser/test_normalizer.py::test_textbox_content_extracted_as_block backend/tests/unit/parser/test_normalizer.py::test_textbox_image_attributed_to_inner_block_not_outer -v
```

Expected: 两个新测试均 FAIL（txbx 内段落未被抽出 / 图被外层占走或缺失）。

- [ ] **Step 4: 修改 `normalize()` 主循环下钻 `w:txbxContent`**

打开 `backend/app/parser/normalizer.py`，定位到 `normalize()` 函数（约 L365-402），整体替换为：

```python
def normalize(
    pkg: DocxPackage,
    *,
    synonyms: dict[str, int],
    style_overrides: dict[str, int],
) -> NormalizedDoc:
    body = pkg.body
    if body is None:
        return NormalizedDoc(blocks=[])
    ctx = _Ctx(
        pkg=pkg,
        style_index=styles_mod.build_style_index(pkg.styles),
        synonyms=synonyms,
        style_overrides=style_overrides,
    )
    tracker = _FieldTracker()
    blocks: list[Block] = []
    table_count = 0
    image_count = 0

    def _append(blk: Block) -> None:
        nonlocal image_count
        blocks.append(blk)
        image_count += len(blk.images)

    def _emit_txbx_descendants(el: etree._Element, source_index: int) -> None:
        """下钻 el 内所有 w:txbxContent，把内嵌段落/表作为附加 IR Block 追加。

        共享父级 source_index，确保在 structurer 排序中紧邻外层块。
        对表格调用时，el.iter() 会下钻到所有 cell，故 cell 内 txbx 同样被抽取
        为独立块（与表平级，不内联回 cell HTML——见 plan 的 Known limitation）。
        """
        nonlocal table_count
        for txbx in el.iter(qn("w:txbxContent")):
            for sub in txbx:
                sub_tag = local(sub.tag)
                if sub_tag == "p":
                    _append(emit_paragraph(sub, ctx, source_index))
                elif sub_tag == "tbl":
                    _append(emit_table(sub, ctx, source_index))
                    table_count += 1

    for i, el in enumerate(_iter_body_children(body)):
        tag = local(el.tag)
        if tag == "p":
            block = emit_paragraph(el, ctx, i)
            block.is_toc_field = tracker.scan(el, i)
            _append(block)
            _emit_txbx_descendants(el, i)
        else:  # tbl
            block = emit_table(el, ctx, i)
            table_count += 1
            _append(block)
            _emit_txbx_descendants(el, i)

    return NormalizedDoc(
        blocks=blocks,
        total_image_count=image_count,
        total_table_count=table_count,
        toc_field_end_index=tracker.toc_end_index,
        style_index=ctx.style_index,
    )
```

- [ ] **Step 5: 运行测试确认 GREEN**

```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
backend/.venv/bin/python -m pytest backend/tests/unit/parser/test_normalizer.py -v
```

Expected: 全部通过，包括 Task 2 / Task 3 的 3 个新测试。

- [ ] **Step 6: Commit**

```bash
git add backend/app/parser/normalizer.py backend/tests/unit/parser/test_normalizer.py
git commit -m "feat(parser): hoist w:txbxContent paragraphs/tables into IR block stream"
```

---

## Task 4: TDD — `raw_image_count` 分母同步 (`v:imagedata` 计入 + txbx 排除)

**Files:**
- Test: `backend/tests/unit/parser/test_normalizer.py`
- Modify: `backend/app/parser/normalizer.py` (`emit_paragraph` L210, `emit_table` L336，新增 `_count_raw_images` helper)

目标：当 `_emit_images` 因任何原因（媒体损坏、未注册的图源等）丢图时，`raw_image_count - len(images) > 0`，C001 应能告警。当前 raw 只数 `a:blip` 而不数 `v:imagedata`，VML 丢图分母错位看不见。

- [ ] **Step 1: 写失败测试 — 含 VML 图的段落 `raw_image_count == 1`**

在 `test_normalizer.py` 末尾追加：

```python
def test_raw_image_count_includes_vml_imagedata() -> None:
    """raw_image_count 应将 v:imagedata 计入分母，与 _emit_images 的抽取范围对齐。"""
    data = DocxBuilder().vml_image_para().build()
    nd = _normalize(data)
    blk = next(b for b in nd.blocks if b.images)
    assert blk.raw_image_count == 1
    assert len(blk.images) == blk.raw_image_count  # 分母分子一致 → C001 pass


def test_raw_image_count_excludes_txbx_blips_on_outer_paragraph() -> None:
    """外层段落的 raw_image_count 不应包含 txbx 内部图（避免与内层 block 重复计数）。"""
    data = DocxBuilder().textbox_with_image_para("内图测试").build()
    nd = _normalize(data)
    para_blocks = [b for b in nd.blocks if b.kind == "paragraph"]
    outer = next(b for b in para_blocks if not b.text.strip())
    inner = next(b for b in para_blocks if "内图测试" in b.text)
    assert outer.raw_image_count == 0
    assert inner.raw_image_count == 1
    assert len(inner.images) == 1
```

- [ ] **Step 2: 运行测试确认 RED**

```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
backend/.venv/bin/python -m pytest backend/tests/unit/parser/test_normalizer.py::test_raw_image_count_includes_vml_imagedata backend/tests/unit/parser/test_normalizer.py::test_raw_image_count_excludes_txbx_blips_on_outer_paragraph -v
```

Expected: 两个新测试 FAIL — 第一个 `0 != 1`（VML 未计入），第二个外层 `1 != 0`（txbx 内 blip 被外层 iter 抓到）。

- [ ] **Step 3: 新增 `_count_raw_images` helper（紧贴 `_is_inside_txbx` 之后插入）**

打开 `backend/app/parser/normalizer.py`，在 `_is_inside_txbx` 函数之后插入：

```python
def _count_raw_images(el: etree._Element) -> int:
    """与 _emit_images 同口径的原始图源计数：a:blip + v:imagedata，跳过 txbxContent 内。

    供 emit_paragraph / emit_table 写入 Block.raw_image_count，让 C001 完整性校验
    的分母覆盖 VML 老格式图；txbx 内图归内层 block 计数，外层不重复。
    """
    n = 0
    for blip in el.iter(qn("a:blip")):
        if not _is_inside_txbx(blip):
            n += 1
    for vimg in el.iter(qn("v:imagedata")):
        if not _is_inside_txbx(vimg):
            n += 1
    return n
```

- [ ] **Step 4: 修改 `emit_paragraph` 使用新 helper**

定位到 `emit_paragraph` 内（约 L210）：

```python
    out = _serialize_runs(para, ctx)
    raw_blips = sum(1 for _ in para.iter(qn("a:blip")))
```

替换为：

```python
    out = _serialize_runs(para, ctx)
    raw_blips = _count_raw_images(para)
```

- [ ] **Step 5: 修改 `emit_table` 使用新 helper**

定位到 `emit_table`（约 L336）：

```python
    table_html, images = _table_html(tbl, ctx)
    raw_blips = sum(1 for _ in tbl.iter(qn("a:blip")))
    raw_tables = sum(1 for _ in tbl.iter(qn("w:tbl")))
```

替换为：

```python
    table_html, images = _table_html(tbl, ctx)
    raw_blips = _count_raw_images(tbl)
    raw_tables = sum(1 for _ in tbl.iter(qn("w:tbl")))
```

（`raw_tables` 暂不调整：表内嵌表已由 cell 递归正确抽取，C002 当前公式对齐良好；改动留待 v2 评估。）

- [ ] **Step 6: 运行测试确认 GREEN**

```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
backend/.venv/bin/python -m pytest backend/tests/unit/parser/test_normalizer.py -v
```

Expected: 全部通过（含 Task 2/3/4 共 5 个新测试 + 既有 8 个）。

- [ ] **Step 7: Commit**

```bash
git add backend/app/parser/normalizer.py backend/tests/unit/parser/test_normalizer.py
git commit -m "fix(parser): align raw_image_count with _emit_images (count v:imagedata, skip txbx)"
```

---

## Task 5: TDD — Completeness 校验在丢图时能 RED

**Files:**
- Create: `backend/tests/unit/parser/test_completeness.py`

为 `validators/completeness.py` 补单测（之前缺失），证明在"raw 计数 > extracted 计数"时 `image_count_match` 返回 `(False, raw, extracted)`，从而下游 `_append_completeness_warnings` 会推一条 warning。

- [ ] **Step 1: 创建 `test_completeness.py`**

文件路径：`backend/tests/unit/parser/test_completeness.py`

完整内容：

```python
"""Completeness validators 单测：C001 图片对账、C002 表格对账。

覆盖正向（分母分子相等→pass）与反向（分母 > 分子→fail，触发 warning 路径）。
"""

from __future__ import annotations

from app.parser.ir import Block, ImageRef
from app.parser.validators import completeness


def _img(rid: str = "rId1") -> ImageRef:
    return ImageRef(rid=rid, part_name="word/media/x.png", data=b"x", ext=".png")


def test_c001_passes_when_raw_equals_extracted() -> None:
    blocks = [
        Block(kind="paragraph", source_index=0, raw_image_count=2, images=[_img("a"), _img("b")]),
        Block(kind="paragraph", source_index=1, raw_image_count=0, images=[]),
    ]
    ok, raw, ext = completeness.image_count_match(blocks)
    assert ok is True
    assert raw == 2 and ext == 2


def test_c001_fails_when_raw_exceeds_extracted() -> None:
    """模拟一张图被 _emit_images 跳过（损坏 / rid 未注册）—— C001 应能识别。"""
    blocks = [
        Block(kind="paragraph", source_index=0, raw_image_count=2, images=[_img("only_one")]),
    ]
    ok, raw, ext = completeness.image_count_match(blocks)
    assert ok is False
    assert raw == 2 and ext == 1


def test_c002_passes_when_table_raw_equals_serialized() -> None:
    blocks = [
        Block(
            kind="table",
            source_index=0,
            html="<table><tr><td>x</td></tr></table>",
            raw_table_count=1,
        ),
    ]
    ok, raw, ser = completeness.table_count_match(blocks)
    assert ok is True
    assert raw == 1 and ser == 1


def test_c002_fails_when_nested_table_not_serialized() -> None:
    """嵌套表：原始 2 个 w:tbl（外+内）但 HTML 只渲染了 1 个 → C002 fail。"""
    blocks = [
        Block(
            kind="table",
            source_index=0,
            html="<table><tr><td>only_outer</td></tr></table>",  # 内嵌表丢失
            raw_table_count=2,
        ),
    ]
    ok, raw, ser = completeness.table_count_match(blocks)
    assert ok is False
    assert raw == 2 and ser == 1
```

- [ ] **Step 2: 运行新测试确认通过**

```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
backend/.venv/bin/python -m pytest backend/tests/unit/parser/test_completeness.py -v
```

Expected: 4 个测试全部 PASS。

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/parser/test_completeness.py
git commit -m "test(parser): add unit tests for C001/C002 completeness validators"
```

---

## Task 6: 集成 — 含 VML + 文本框的合成 SOP 走完整 pipeline

**Files:**
- Modify: `backend/tests/unit/parser/test_pipeline.py`

证明从 docx 字节流 → normalize → structure → ParseResult 整条链路不丢 VML 图、不丢文本框文字、且 warnings 列表不出"图片可能遗漏"或"表格可能遗漏"。

- [ ] **Step 1: 在 `test_pipeline.py` 末尾追加集成测试**

打开 `backend/tests/unit/parser/test_pipeline.py`，末尾追加（沿用既有 `from app.parser import parse_docx` 风格，与文件已 import 的 `DocxBuilder` 共用）：

```python
def test_parse_docx_handles_vml_and_textbox_without_completeness_warnings() -> None:
    """端到端 parse_docx：含 VML 图 + 文本框 + 普通段落的合成 SOP，
    解析后 warnings 中不应出现「图片可能遗漏 / 表格可能遗漏」，
    且 image_refs 含 VML 图、章节树含文本框内文字。"""
    from tests.unit.parser._docx_builder import DocxBuilder

    data = (
        DocxBuilder()
        .heading("目的", level=1)
        .para("本程序适用于全公司。")
        .textbox_para("注意：操作前务必断电")
        .heading("范围", level=1)
        .vml_image_para()
        .build()
    )
    res = parse_docx(data, "standard")
    # 完整性校验：分母分子一致 → 无 completeness warning
    completeness_warns = [w for w in res.warnings if w.stage == "completeness"]
    assert completeness_warns == [], f"unexpected completeness warnings: {completeness_warns}"
    # VML 图作为 image_ref 出现（asset 阶段会落盘）
    assert any(r.placeholder.startswith("media:") for r in res.image_refs)
    # 文本框文字进入 rich_content（被挂在某个 chapter 的 content 子节点下）
    def _all_rich(nodes):  # type: ignore[no-untyped-def]
        for n in nodes:
            yield n.rich_content
            yield from _all_rich(n.children)
    all_rich = " ".join(_all_rich(res.chapters))
    assert "断电" in all_rich, f"textbox content missing from chapters: {all_rich[:200]}"
```

注意：`DocxBuilder` 已在 Task 1 加过 `textbox_para` / `vml_image_para` 方法，且 `test_pipeline.py` 顶部已 `from tests.unit.parser._docx_builder import ...`——只需补 import `DocxBuilder` 到既有 import 列表（若尚未引入）。

- [ ] **Step 2: 如需要，补 `DocxBuilder` 到 import**

打开 `backend/tests/unit/parser/test_pipeline.py`，顶部的：

```python
from tests.unit.parser._docx_builder import styled_sop, unstyled_numbered_sop
```

改为：

```python
from tests.unit.parser._docx_builder import DocxBuilder, styled_sop, unstyled_numbered_sop
```

（若 Step 1 内的测试函数顶部已 import 了 `DocxBuilder` 就跳过此 Step。两种都可，挑一个保持文件风格统一。）

- [ ] **Step 3: 运行新测试**

```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
backend/.venv/bin/python -m pytest backend/tests/unit/parser/test_pipeline.py::test_parse_docx_handles_vml_and_textbox_without_completeness_warnings -v
```

Expected: PASS。

- [ ] **Step 4: 跑全套 parser 单测确认无回退**

```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
backend/.venv/bin/python -m pytest backend/tests/unit/parser/ -v
```

Expected: 全绿。

- [ ] **Step 5: Commit**

```bash
git add backend/tests/unit/parser/test_pipeline.py
git commit -m "test(parser): integration test for VML + textbox completeness end-to-end"
```

---

## Task 7: 最终验证 — 整仓 backend 测试 + 健康跑一遍真实样本（如有）

**Files:** (no edits)

- [ ] **Step 1: 跑整个 backend 测试套**

```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
backend/.venv/bin/python -m pytest backend/tests/ -x --tb=short
```

Expected: 全绿。`-x` 在第一个失败处停下方便调试。

- [ ] **Step 2: 若 `tests/fixtures/eval_gt/` 下有真实 docx，跑评估脚本验证不回退**

```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
ls tests/fixtures/eval_gt/ 2>/dev/null | head -5
```

若有 .docx 样本，跑（按仓库现有评估脚本约定）：

```bash
backend/.venv/bin/python scripts/eval/run_eval.py --quick 2>/dev/null || echo "eval script signature differs—skip"
```

若评估脚本签名不符或不存在，跳过此步——不阻断。

- [ ] **Step 3: 自检 git log 显示 6 个干净 commit**

```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
git log --oneline -7
```

Expected: 看到 Task 1-6 的 6 个 commit + 之前的 main HEAD。

- [ ] **Step 4: 决定是否合入 main / 开 PR**

参考 superpowers:finishing-a-development-branch 决策。本计划范围在 backend parser，不动 schema/DB/前端，PR 风险低。

---

## Done Criteria

执行完成时应满足：

1. `backend/.venv/bin/python -m pytest backend/tests/unit/parser/ -v` 全绿。
2. `backend/tests/unit/parser/test_normalizer.py` 新增 5 个测试（VML 抽取、txbx 段落、txbx 图归属、raw_image_count VML、raw_image_count 排除 txbx）全绿。
3. `backend/tests/unit/parser/test_completeness.py` 新文件 4 个测试全绿。
4. `backend/tests/unit/parser/test_pipeline.py` 新增 1 个集成测试全绿。
5. 既有 normalizer / pipeline / structurer 测试零回退。
6. 内含 VML 图 + 文本框文字的 docx，经 `normalize → structure` 后 `result.warnings` 不出 "图片可能遗漏 / 表格可能遗漏"。
7. 6 个独立 commit（每 Task 一个），分别覆盖：fixture / VML 抽取 / txbx 抽取 / raw 计数修复 / completeness 单测 / 集成测试。
