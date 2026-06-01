# EMF/WMF 无 LibreOffice 阻断告警 + 软依赖探测 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **⚠️ 用户指令 #5：不做任何 git 提交。** 所有「提交」步骤替换为「运行测试确认通过、改动留工作区」。

**Goal:** EMF/WMF 矢量图在无 LibreOffice/转换失败时，换成可见占位 + content 节点标 review + 发 blocking warning 触发 A 的强确认；并加 soffice 软依赖探测（启动日志 + /readyz 字段）。

**Architecture:** `write_temp_media` 追踪转换失败的矢量图并返回其 placeholder 集合（失败者不写盘/不入 assets）；`parse_service` 把失败矢量的 `<img>` 换成 `.sop-ph` 占位、标节点 review、加 blocking warning（复用 A 的 severity + ParseConfirmDialog、B 的 .sop-ph + B3 的 content-review 落库）；`lifespan` 启动探测 soffice 记 warning，`/readyz` 暴露非致命 soffice 字段。

**Tech Stack:** 后端 FastAPI + pytest；前端 Vue3 + Vitest。

---

## 关键约束（实现者必读）

1. 复用既有：A 的 `ParseWarning.severity="blocking"` + 前端 `ParseConfirmDialog`（blocking warning 自动进强确认）；B 的 `.sop-ph` 占位 CSS；B3 已让 `import_service` content 分支放行 `mark_status="review"`（**C 的 import 侧零新增**）。
2. 占位是纯 HTML（无临时 URL），不被 `_promote_temp_urls` 改写，导入即原样落库 → 结果干净、无过期坏图。
3. 矢量「抽取」在 structure 阶段已计入 C001；矢量「转换失败 → 占位」发生在 parse_service（C001 评估之后），二者正交，不改 C001/C007。
4. `write_temp_media` 仅 `parse_service.parse` 一处调用——改返回签名安全，但**须同步更新现有测试** `test_upload_service.py::test_write_temp_media_and_serve`（现解包 2 元组）。

---

## 文件结构

**后端**
- 修改 `app/services/upload_service.py` —— `write_temp_media` 返回 `(mapping, assets, failed_vectors)`，失败矢量不写盘/不入 assets。
- 修改 `app/services/parse_service.py` —— 接 3 元组、新增 `_swap_failed_vectors`、加 blocking warning（import `ParseWarning`）。
- 修改 `app/main.py` —— `lifespan` 加 `_probe_soffice()`；`/readyz` 加 `soffice` 字段。
- 修改 `tests/unit/services/test_upload_service.py` —— 更新 2→3 元组解包 + 加矢量失败用例。

**前端**
- 修改 `frontend/src/components/PdfPreview/PdfPreviewDialog.vue` —— `.sop-ph[data-ph='vector']` 加入块状样式。
- 修改 `frontend/tests/unit/parsePlaceholder.spec.ts` —— 加 vector 占位渲染守护。

**测试**
- `backend/tests/unit/services/test_upload_service.py`、`test_parse_service.py`
- `backend/tests/integration/test_health.py`

---

## Task C1: write_temp_media 追踪矢量转换失败

**Files:**
- Modify: `backend/app/services/upload_service.py`（`write_temp_media`）
- Test: `backend/tests/unit/services/test_upload_service.py`

- [ ] **Step 1: 更新现有测试解包 + 写失败新测**

`test_upload_service.py` 把 `test_write_temp_media_and_serve` 里 `mapping, assets = upload_service.write_temp_media(...)` 改为 `mapping, assets, failed = upload_service.write_temp_media(...)`，并在其断言区加 `assert failed == set()`。

末尾新增：
```python
def test_write_temp_media_vector_conversion_failure(
    storage_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """无 soffice / 转换失败：EMF 矢量图进 failed_vectors、不入 assets、不写盘。"""
    monkeypatch.setattr(upload_service.images, "convert_to_png", lambda *_a, **_k: None)
    res = upload_service.save_upload(styled_sop(), "a.docx")
    refs = [
        ImageRef(
            rid="rId9",
            part_name="word/media/image1.emf",
            data=b"\x01\x00\x00\x00emf-bytes",
            ext=".emf",
            placeholder="media:rId9",
        )
    ]
    mapping, assets, failed = upload_service.write_temp_media(res.upload_token, refs)
    assert "media:rId9" in failed
    assert assets == []
    assert mapping == {}
    # 不写盘：media 目录无该文件
    from app import storage
    media_dir = storage.token_media_dir(res.upload_token)
    assert not any(p.suffix == ".emf" for p in media_dir.iterdir()) if media_dir.exists() else True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/services/test_upload_service.py::test_write_temp_media_vector_conversion_failure -q`
Expected: FAIL（`write_temp_media` 返 2 元组，解包 3 报错）。

- [ ] **Step 3: 改 write_temp_media**

`upload_service.py` 的 `write_temp_media` 改为返回 3 元组，矢量失败 `continue`：
```python
def write_temp_media(
    token: str, image_refs: list[ImageRef]
) -> tuple[dict[str, str], list[ParsedAssetOut], set[str]]:
    """把解析抽出的图写入临时 media 目录，返回 placeholder→临时 URL 映射 + asset 描述
    + 转换失败的矢量图 placeholder 集合（failed_vectors，供 parse_service 换占位）。"""
    media = storage.token_media_dir(token)
    media.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, str] = {}
    assets: list[ParsedAssetOut] = []
    failed_vectors: set[str] = set()
    seen: set[str] = set()

    for ref in image_refs:
        if ref.rid in seen:
            continue
        seen.add(ref.rid)
        data, ext = ref.data, ref.ext.lower()
        if ext in images.VECTOR_EXTS:  # emf/wmf → png 以便浏览器预览（Q216）
            png = images.convert_to_png(data, ext)
            if png is None:  # 无 soffice / 转换失败 → 不写盘、不入 assets，交 parse_service 换占位
                failed_vectors.add(ref.placeholder)
                continue
            data, ext = png, ".png"
        filename = f"{_safe_name(ref.rid)}{ext}"
        (media / filename).write_bytes(data)
        url = asset_service.temp_url(token, filename)
        mapping[ref.placeholder] = url
        width, height = images.dimensions(data)
        assets.append(
            ParsedAssetOut(
                temp_id=ref.rid,
                url=url,
                sha256=images.sha256_hex(data),
                mime=images.mime_for_ext(ext),
                size_bytes=len(data),
                width=width,
                height=height,
            )
        )
    return mapping, assets, failed_vectors
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/unit/services/test_upload_service.py -q`
Expected: PASS（新测 + 更新后的既有测试全过）。

- [ ] **Step 5: 改动留工作区，不提交**

---

## Task C2: parse_service 失败矢量 → 占位 + review + blocking warning

**Files:**
- Modify: `backend/app/services/parse_service.py`
- Test: `backend/tests/unit/services/test_parse_service.py`

- [ ] **Step 1: 写失败测试**

`test_parse_service.py` 加（顶部已 import `parse_service`、`upload_service`、`ParseResult`、`ParseMetadata`；需再 import `ParsedNode`）：
```python
def test_swap_failed_vectors_inserts_placeholder_and_review() -> None:
    from app.parser.result import ParsedNode
    content = ParsedNode(
        id="n1", title="", level=2, content_type="content",
        rich_content='<p>前<img src="media:rId9"/>后</p>',
    )
    chapter = ParsedNode(id="c1", title="目的", level=1, content_type="chapter", children=[content])
    result = ParseResult(
        metadata=ParseMetadata(total_chapters=1, image_count=1, table_count=0,
                               body_start_index=0, body_start_detected_by="x"),
        chapters=[chapter], parse_method="smart",
    )
    n = parse_service._swap_failed_vectors(result, {"media:rId9"})
    assert n == 1
    assert 'data-ph="vector"' in content.rich_content
    assert "矢量图无法转换" in content.rich_content
    assert 'media:rId9' not in content.rich_content
    assert content.mark_status == "review"


def test_parse_appends_blocking_warning_for_failed_vectors(
    storage_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.parser.result import ParsedNode
    token = upload_service.save_upload(styled_sop(), "a.docx").upload_token

    def _fake_parse(_data: bytes, _mode: str, **_kw: object) -> ParseResult:
        content = ParsedNode(id="n1", title="", level=2, content_type="content",
                             rich_content='<p><img src="media:rId9"/></p>')
        chapter = ParsedNode(id="c1", title="目的", level=1, content_type="chapter",
                            children=[content])
        return ParseResult(
            metadata=ParseMetadata(total_chapters=1, image_count=1, table_count=0,
                                   body_start_index=0, body_start_detected_by="x"),
            chapters=[chapter], parse_method="smart",
        )

    monkeypatch.setattr(parse_service, "parse_docx", _fake_parse)
    monkeypatch.setattr(
        upload_service, "write_temp_media", lambda *_a, **_k: ({}, [], {"media:rId9"})
    )
    resp = parse_service.parse(token, "smart")
    blocking = [w for w in resp.warnings if w.severity == "blocking" and "矢量图" in w.message]
    assert len(blocking) == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/services/test_parse_service.py::test_swap_failed_vectors_inserts_placeholder_and_review -q`
Expected: FAIL（`_swap_failed_vectors` 不存在）。

- [ ] **Step 3: 改 parse_service**

`parse_service.py` 顶部 import 加 `ParseWarning`：
```python
from app.parser.result import ParsedNode, ParseResult, ParseWarning, ValidationReport
```
`parse` 函数里把：
```python
    mapping, assets = upload_service.write_temp_media(token, result.image_refs)
    _rewrite_placeholders(result, mapping)
    parse_time_ms = int((time.monotonic() - start) * 1000)
    return build_parse_response(result, assets, parse_time_ms)
```
改为：
```python
    mapping, assets, failed_vectors = upload_service.write_temp_media(token, result.image_refs)
    _rewrite_placeholders(result, mapping)
    n_failed = _swap_failed_vectors(result, failed_vectors)
    if n_failed:
        result.warnings.append(
            ParseWarning(
                stage="image",
                message=f"本环境无法转换 {n_failed} 张矢量图（EMF/WMF），将以占位符导入",
                severity="blocking",
            )
        )
    parse_time_ms = int((time.monotonic() - start) * 1000)
    return build_parse_response(result, assets, parse_time_ms)
```
在 `_rewrite_placeholders` 之后加新函数：
```python
_VECTOR_PLACEHOLDER = '<div class="sop-ph" data-ph="vector">[矢量图无法转换]</div>'


def _swap_failed_vectors(result: ParseResult, failed_vectors: set[str]) -> int:
    """把失败矢量图的 <img src="media:rid"/> 换成可见占位，含占位的节点标 review。返回替换图片数。"""
    if not failed_vectors:
        return 0
    count = 0

    def walk(nodes: list[ParsedNode]) -> None:
        nonlocal count
        for node in nodes:
            swapped_here = 0
            for placeholder in failed_vectors:
                target = f'<img src="{placeholder}"/>'
                occurrences = node.rich_content.count(target)
                if occurrences:
                    node.rich_content = node.rich_content.replace(target, _VECTOR_PLACEHOLDER)
                    swapped_here += occurrences
            if swapped_here:
                node.mark_status = "review"
                count += swapped_here
            walk(node.children)

    walk(result.chapters)
    return count
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/unit/services/test_parse_service.py -q`
Expected: PASS。

- [ ] **Step 5: 改动留工作区，不提交**

---

## Task C3: soffice 软依赖探测（启动日志 + /readyz 字段）

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/integration/test_health.py`

- [ ] **Step 1: 写失败测试**

`test_health.py` 顶部确认或加 `import pytest`。加：
```python
def test_readyz_reports_soffice_up(client, engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.main.engine", engine)
    monkeypatch.setattr("app.main.images.soffice_available", lambda: True)
    resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["soffice"] == "up"


def test_readyz_reports_soffice_down_but_still_200(
    client, engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.main.engine", engine)
    monkeypatch.setattr("app.main.images.soffice_available", lambda: False)
    resp = client.get("/readyz")
    assert resp.status_code == 200  # soffice 缺失非致命
    assert resp.json()["soffice"] == "down"


def test_probe_soffice_warns_when_missing(monkeypatch: pytest.MonkeyPatch, caplog) -> None:
    import logging
    from app import main as main_mod
    monkeypatch.setattr(main_mod.images, "soffice_available", lambda: False)
    with caplog.at_level(logging.WARNING):
        main_mod._probe_soffice()
    assert any("soffice" in r.message.lower() or "LibreOffice" in r.message for r in caplog.records)
```
> 若 `engine` fixture 名/签名与该文件既有 readyz 测试不同，对齐既有 `test_readyz_ok_when_db_reachable` 的 fixture 用法。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/integration/test_health.py::test_probe_soffice_warns_when_missing -q`
Expected: FAIL（`_probe_soffice` / `app.main.images` 不存在）。

- [ ] **Step 3: 改 main.py**

`main.py` 顶部 import 区加：
```python
from app.parser.utils import images
```
在 `lifespan` 定义之前加探测函数：
```python
def _probe_soffice() -> None:
    """启动探测 LibreOffice 软依赖；缺失记 warning（EMF/WMF 将无法转换）。"""
    if not images.soffice_available():
        logger.warning(
            "LibreOffice (soffice) 不可用：EMF/WMF 矢量图将无法转换，导入时以占位符代替"
        )
```
`lifespan` 内（`run_seed` 之后、`yield` 之前）加 `_probe_soffice()`：
```python
    with SessionLocal() as db:
        run_seed(db)
    _probe_soffice()
    yield
```
`/readyz` 成功（200）分支的返回加 `soffice` 字段：
```python
    return JSONResponse(
        content={
            "status": "ok",
            "db": "up",
            "soffice": "up" if images.soffice_available() else "down",
        }
    )
```
（db down 的 503 分支不变、不含 soffice。）

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/integration/test_health.py -q`
Expected: PASS（含既有 healthz/readyz 测试不回归）。

- [ ] **Step 5: 后端全量回归**

Run: `cd backend && .venv/bin/pytest -q`
Expected: 全 PASS。

- [ ] **Step 6: 改动留工作区，不提交**

---

## Task C4: 前端 vector 占位样式 + 守护

**Files:**
- Modify: `frontend/src/components/PdfPreview/PdfPreviewDialog.vue`
- Test: `frontend/tests/unit/parsePlaceholder.spec.ts`

- [ ] **Step 1: 写失败/守护测试**

`parsePlaceholder.spec.ts` 加：
```typescript
  it('vector 占位渲染为带 class 的 div', () => {
    const w = mount(Host, { props: { html: '<div class="sop-ph" data-ph="vector">[矢量图无法转换]</div>' } })
    const ph = w.find('div.sop-ph[data-ph="vector"]')
    expect(ph.exists()).toBe(true)
    expect(ph.text()).toBe('[矢量图无法转换]')
  })
```
（结构契约测试，验证 v-html 渲染；此条本应直接过——确认占位 HTML 契约。）

- [ ] **Step 2: 跑测试**

Run: `cd frontend && npx vitest run tests/unit/parsePlaceholder.spec.ts`
Expected: PASS（结构契约成立）。

- [ ] **Step 3: 加 vector 到块状样式**

`PdfPreviewDialog.vue` 的 B 项块状占位样式选择器（现为 `:deep(.sop-ph[data-ph='smartart']), :deep(.sop-ph[data-ph='chart'])`）加 `vector`：
```css
:deep(.sop-ph[data-ph='smartart']),
:deep(.sop-ph[data-ph='chart']),
:deep(.sop-ph[data-ph='vector']) {
  display: block;
  padding: 8px 12px;
  margin: 6px 0;
  text-align: center;
}
```
（若 B 的实际选择器写法不同，对齐 B 已落的 `.sop-ph` 块状规则，把 `vector` 并入同组。）

- [ ] **Step 4: 前端全量回归 + 类型**

Run: `cd frontend && npx vitest run`
Expected: 全 PASS。
Run: `cd frontend && npx vue-tsc --noEmit -p tsconfig.json 2>&1 | tail -10`
Expected: 无新增类型错误。

- [ ] **Step 5: 改动留工作区，不提交**

---

## 自查（spec 覆盖 / 占位 / 类型一致）

**Spec 覆盖：**
- §3.1 write_temp_media 追踪失败矢量（3 元组、不写盘/不入 assets）→ C1 ✓
- §3.2 parse_service 换占位 + review + blocking warning → C2 ✓
- §3.3 soffice 探测（lifespan log + /readyz 字段）→ C3 ✓
- §3.4 不触 C001/C007 → 设计上矢量替换在 C001 评估后、不进 placeholder_count；无代码触碰这两检查（C1-C4 均不改 completeness/structurer）✓
- §4 前端 vector 样式 → C4；强确认/复查复用 A/B/B3 零新增 ✓
- §6 测试 → 各 Task TDD + 后端全量（C3 Step5）+ 前端全量（C4 Step4）✓

**占位扫描：** C3 Step1 留「engine fixture 对齐既有 readyz 测试」、C4 Step3 留「对齐 B 实际 `.sop-ph` 块状选择器写法」的弹性说明——因夹具/既有样式写法需就地对齐；最小契约已给死（soffice up/down + 200、vector 占位结构）。其余为完整代码。

**类型/契约一致：** `write_temp_media` 3 元组（C1 定义）↔ `parse_service` 解包（C2）一致；占位 HTML 契约 `<div class="sop-ph" data-ph="vector">[矢量图无法转换]</div>` 后端产出（C2 `_VECTOR_PLACEHOLDER`）↔ 前端测试（C4）一致；`/readyz` `soffice` 字段（C3）↔ 测试（C3）一致。import 侧零新增（B3 已放行 content review）——`_swap_failed_vectors` 设 `mark_status="review"` 的 ParsedNode 经 import 落库为 review，依赖 B3 已完成。

**依赖说明：** C 依赖 A（severity + ParseConfirmDialog）、B（.sop-ph 样式）、B3（import 放行 content review）均已完成。
