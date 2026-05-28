# 统一节点模型 Plan B2b — PDF 读取切到 ProcedureNode 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 PDF 渲染的数据来源从旧 `ProcedureChapter`/`ProcedureStep` 切到统一 `ProcedureNode`，视觉**完全不变**（spec §7 line 53「不重做 PDF 视觉，仅适配数据来源」）。

**Architecture:** PDF 的唯一取数口 `services/pdf/context.py:load_render_data` 改为从 `node_service.get_nodes`（含派生 `parent_id`/`code`）装配同样的 `ChapterData`/`StepData` 快照；`sections.py` 等渲染层**一行不改**（吃的是快照，与来源无关）。章节/步骤的「标题」从 node `body` 第一个块级元素派生（spec §2.3）。为此先在 B2a 的 `node_sync` 里把旧 step 的 `title` 折进 step node 的 `body` 首段（B2a 当时只存了 `content`，丢了 `title`）——这样 heading 与 step 的标题都统一「= body 首块」，PDF 可确定性还原 legacy 的 (title, content) 二分。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy 2.0、reportlab、lxml（已是 parser 依赖）、pytest + SQLite in-memory（conftest `db`/`factory`/`client`）。测试用 `backend/.venv/bin/python -m pytest`（本机无 uv，memory `uv-missing-use-venv-python`）。

**Spec:** `docs/superpowers/specs/2026-05-28-unified-node-model-design.md`（§2.3 标题派生、§7 下游适配、§1 line 53「不重做 PDF 视觉」）。本计划是 Plan B 的 **B2b**（B2 = 切下游读取，拆为 [B2a 写补全 已合并] + B2b PDF 读切）。

---

## 范围说明

**做（B2b）：** 仅 PDF 读取从两表切到 `ProcedureNode`；step `title` 折进 node body（补 B2a 的丢失）。

**不做（留给后续阶段）：**
- **B3** — 前端两面板 + 编辑器/`GET /procedures/{id}` 详情读取切到 node（PDF 之外的读取口仍读旧表，前端编辑器仍消费 chapter/step）。**故本期只改 PDF，不动 `procedure_service.get_detail`/editor 读取。**
- **B4 contract** — 删 `numbering_service`（连同 B2a 挂在其上的 rebuild hook）、删 `ProcedureChapter`/`ProcedureStep`、删 `node_sync`；届时编辑器直接写 node，PDF 读的就是编辑器写的 node（本期建立的 `load_render_data`←node 口子原样保留）。

### 调查得出的关键事实（写本计划时用真实代码确认）

1. **`load_render_data` 是 PDF 唯一取数口**，装配 `ChapterData`/`StepData` 快照后，`sections.py` 全部渲染只吃快照、与来源解耦。保持快照**结构形状不变** → `sections.py`、`engine`、`flowables`、`styles` 等**零改动**。
2. **node 已是 PDF 数据的充分来源**：B2a 让所有结构写入（import/editor/颗粒度 mutator/version fork）收尾都经 `numbering_service.recompute` → 重建 node。**所有现存 PDF 测试**渲染内容前都到达 recompute（`test_context`/`test_engine` 显式调；`test_pdf` 经 import；`test_sections` 自建 `RenderData`），故都已有持久 node。**B2b 不做读时 rebuild**——PDF 保持纯读，信任 B2a 持久化的 node（也是 B4 终态：编辑器写 node、PDF 读 node）。
3. **step `title` 在 B2a 被丢**：B2a `node_sync` 设 step node `body=st.content`，未保留 `st.title`。spec §1 删 `ProcedureStep.title`、「标题改由 body 第一段派生」（line 82）。⇒ 正确迁移是把 title 折进 body 首段。
4. **lxml 可用**（parser/`layer_apply_service._try_extract_title_from_body` 已用）；用它实现「body → (首块纯文本, 其余 HTML)」的确定性切分。

### 关键设计点（trade-off，记入 commit 理由，memory `trade-off-auto-decide-with-log`）

- **step title 折进 body：恒前置 `<p>title</p>`（含空 title）。** 为让 PDF 能**确定性**地把 step body 切回 (title, content)，`node_sync` 对 `kind='step'` 恒前置一个标题块——即使 `title==''` 也前置 `<p></p>`。这样 PDF「首块=标题（可空）、其余=正文」对所有 step 成立：空 title → 渲染 legacy 的「（步骤）」占位，视觉一致。代价：无标题 step 的 body 有个空 `<p></p>` 前缀（脚手架瑕疵；B3 编辑器直写 node 时规范化、B4 清理）。备选「仅非空才前置」会让无标题 step 的正文首段被误当标题——**否决**。
- **PDF 信任持久 node、不读时 rebuild。** 保持 PDF 纯读（REST GET 不写库）、与 B4 终态一致；依赖「所有结构写入都经 recompute → node 已建」这条 B2a 不变量（已被全部 PDF 测试覆盖）。若未来出现绕过 recompute 造 legacy 数据的新路径，PDF 会渲染空——可在 `load_render_data` 加一行 `node_sync.rebuild_from_legacy` 防御，本期不加（避免 GET 写库 + 与 B2a 冗余）。
- **heading「引言」（多段 body 的非首段）本期不渲染。** B2a 重建的 heading body 恒单段（=标题），无引言可渲染；`ChapterData` 也无引言字段。若未来 heading body 出现多段（编辑器 nicety），其余段当前会被 PDF 丢弃——记为 B3/后续待办，本期数据形态下无影响。
- `content` 节点（`kind='node'` 且 `heading_level=None`）映射为 `StepData(kind='content')`，body 整体内联（沿用 `pdf-content-no-title`，不派生标题）。

---

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `backend/app/services/node_sync.py` | step node body 折入 title 首段（补 B2a 丢失） | 修改（step 分支 1 行） |
| `backend/tests/unit/services/test_node_sync.py` | 更新 step body 断言 + 加 titled/空title 用例 | 修改 |
| `backend/app/services/pdf/context.py` | `load_render_data` 改从 ProcedureNode 装配；加 `_split_first_block` | 修改（重写取数段 + 加 helper） |
| `backend/tests/unit/services/pdf/test_context.py` | 加 title 派生 + node 来源用例（旧用例作回归网） | 修改（加测） |

---

## Task 1: `node_sync` 把 step `title` 折进 node body

**Files:**
- Modify: `backend/app/services/node_sync.py`
- Test: `backend/tests/unit/services/test_node_sync.py`

- [ ] **Step 1: 改测试（先红）**

In `backend/tests/unit/services/test_node_sync.py`, **replace** `test_rebuild_step_node_keeps_form` with the two tests below (titled step folds title into body; empty-title step gets empty leading `<p>`):

```python
def test_rebuild_step_node_folds_title_into_body(factory: Factory, db: Session) -> None:
    pid = _proc(factory)
    c1 = factory.chapter(pid, title="执行", sort_order=0)
    factory.step(
        pid, chapter_id=c1.id, title="步骤一", content="<p>填表</p>", kind="step",
        input_schema={"type": "COMMON"}, sort_order=0,
    )

    node_sync.rebuild_from_legacy(db, pid)

    leaf = node_service.get_nodes(db, pid)[1]
    assert leaf["kind"] == "step"
    assert leaf["heading_level"] is None
    assert leaf["body"] == "<p>步骤一</p><p>填表</p>"  # title 折成首段
    assert leaf["input_schema"] == {"type": "COMMON"}


def test_rebuild_titleless_step_prepends_empty_title_block(factory: Factory, db: Session) -> None:
    pid = _proc(factory)
    c1 = factory.chapter(pid, title="执行", sort_order=0)
    factory.step(pid, chapter_id=c1.id, title="", content="<p>填表</p>", kind="step", sort_order=0)

    node_sync.rebuild_from_legacy(db, pid)

    leaf = node_service.get_nodes(db, pid)[1]
    assert leaf["body"] == "<p></p><p>填表</p>"  # 空 title 也恒前置（PDF 确定性切分）
```

(Leave the other 5 `test_node_sync.py` tests unchanged. The content-block test must still assert content-kind node body == raw content with NO prepend.)

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/services/test_node_sync.py -v`
Expected: the two new tests FAIL — current B2a code sets step body = `st.content` (no title fold), so body is `<p>填表</p>` not `<p>步骤一</p><p>填表</p>`.

- [ ] **Step 3: 实现**

In `backend/app/services/node_sync.py`, inside `walk()`'s step loop, change the step node `body` to fold the title into the first block. The current step emit is:

```python
            is_step = st.kind == "step"
            db.add(
                ProcedureNode(
                    procedure_id=procedure_id,
                    sort_order=_next_sort(),
                    heading_level=None,
                    kind="step" if is_step else "node",
                    body=st.content,
                    input_schema=st.input_schema if is_step else {},
                    attachment_marks=st.attachment_marks if is_step else [],
                    skip_numbering=st.skip_numbering,
                    mark_status="unmarked",
                )
            )
```

Change the `body=st.content,` line to (recall `import html` is already imported at the top of node_sync):

```python
                    body=(f"<p>{html.escape(st.title)}</p>{st.content}" if is_step else st.content),
```

(For `kind='step'`:恒前置 `<p>{escape(title)}</p>`，含空 title → `<p></p>`。`content` 节点 `body=st.content` 不变。其余字段不动。)

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/services/test_node_sync.py -v`
Expected: PASS (7 个：原 5 个不变 + 2 个新 step 用例)。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/node_sync.py backend/tests/unit/services/test_node_sync.py
git commit -m "feat(node_sync): fold legacy step title into node body first block (Plan B2b)"
```

---

## Task 2: `load_render_data` 改从 ProcedureNode 装配

**Files:**
- Modify: `backend/app/services/pdf/context.py`
- Test: `backend/tests/unit/services/pdf/test_context.py`

- [ ] **Step 1: 写失败测试**

In `backend/tests/unit/services/pdf/test_context.py`, add a test that exercises node-sourced title derivation (place after the existing `test_chapter_tree_with_content_step_and_steps`; reuse its `_proc`/`factory` style — the file already imports `numbering_service`, `context`, `Factory`):

```python
def test_titles_derived_from_node_body(db: Session, factory: Factory) -> None:
    """B2b: load_render_data 从 ProcedureNode 取数，标题由 body 首块派生。"""
    leaf = factory.folder(name="质检", prefix="QC", full_path="质检")
    factory.sequence(leaf.id)
    proc = factory.procedure(leaf.id, code="QC-00009", name="派生标题")
    ch = factory.chapter(proc.id, title="目的", level=1, sort_order=0)
    factory.step(proc.id, chapter_id=ch.id, title="检查阀门", content="<p>步骤正文</p>",
                 kind="step", sort_order=0)
    factory.step(proc.id, chapter_id=ch.id, title="", content="<p>内容块正文</p>",
                 kind="content", sort_order=1)
    numbering_service.recompute(db, proc.id)  # 经 B2a hook 建 node

    data = context.load_render_data(db, proc.id)

    assert len(data.root_chapters) == 1
    chap = data.root_chapters[0]
    assert chap.title == "目的"        # heading 标题 = body 首块
    assert chap.code == "1"
    assert chap.level == 1
    titles = [(st.kind, st.title, st.content) for st in chap.steps]
    assert titles == [
        ("step", "检查阀门", "<p>步骤正文</p>"),   # step 标题=首块、正文=其余
        ("content", "", "<p>内容块正文</p>"),       # content 无标题、整体内联
    ]
    assert chap.steps[0].code == "1.1"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/bin/python -m pytest "backend/tests/unit/services/pdf/test_context.py::test_titles_derived_from_node_body" -v`
Expected: FAIL — 现 `load_render_data` 仍从旧表取 `ch.title`/`st.title`，但本测试**也**会因新断言形态而失败（content 的 title 等）；关键是它要在切到 node 后通过。先红即可（断言不等，非 500）。

- [ ] **Step 3: 实现**

In `backend/app/services/pdf/context.py`:

(a) Add the title-splitting helper (place near the other module-level helpers, e.g. after `_collect_asset_ids`):

```python
def _split_first_block(body: str) -> tuple[str, str]:
    """把统一 node 的 body 切成 (首个块级元素的纯文本, 其余 HTML)。
    用于从 body 还原 legacy 的 (title, content) 二分（spec §2.3 标题=body 首块）：
    heading/step 的标题取首块文本；step 正文取其余。解析失败 → ('', 原文当正文)。"""
    if not body or not body.strip():
        return "", ""
    try:
        from lxml import html as lxml_html

        frag = lxml_html.fragment_fromstring(body, create_parent="div")
    except Exception:  # 异常 HTML：无标题，整体当正文
        return "", body
    children = list(frag)
    if not children:  # 无块级子元素（裸文本）：整段当标题
        return (frag.text or "").strip(), ""
    first = children[0]
    title = (first.text_content() or "").strip()
    rest = "".join(lxml_html.tostring(c, encoding="unicode") for c in children[1:])
    return title, rest
```

(b) Add `from app.services import node_service` to the imports (alongside `from app.services import asset_service`), and **remove** the now-unused legacy imports `from app.models.chapter import ProcedureChapter` and `from app.models.step import ProcedureStep` (confirm by grep they're unused elsewhere in the file after this rewrite).

(c) Replace the chapter/step querying + tree build + the `_to_step` / `build_chapter` helpers — i.e. everything from the `chapters = list(...)` query down to the `root_steps = [...]` line (the current lines that query `ProcedureChapter`/`ProcedureStep`, build `children_by_parent`/`steps_by_chapter`, define `build_chapter`, and set `root_chapters`/`root_steps`) — with node-sourced assembly. Also delete the standalone `_to_step` function (no longer used). The new block:

```python
    rows = node_service.get_nodes(db, proc_id)  # 扁平 + 派生 parent_id/code（B2a 已建 node）

    chapters_by_id: dict[str, ChapterData] = {}
    children_acc: dict[str | None, list[ChapterData]] = {}
    steps_acc: dict[str | None, list[StepData]] = {}
    for r in rows:  # rows 已按 sort_order 升序 → 同父下保持文档序
        if r["heading_level"] is not None:
            cd = ChapterData(
                id=r["id"],
                title=_split_first_block(r["body"])[0],
                code=r["code"],
                level=r["heading_level"],
                skip_numbering=r["skip_numbering"],
            )
            chapters_by_id[r["id"]] = cd
            children_acc.setdefault(r["parent_id"], []).append(cd)
        elif r["kind"] == "step":
            title, content = _split_first_block(r["body"])
            steps_acc.setdefault(r["parent_id"], []).append(
                StepData(
                    id=r["id"],
                    code=r["code"],
                    title=title,
                    content=content,
                    kind="step",
                    skip_numbering=r["skip_numbering"],
                    input_schema=dict(r["input_schema"] or {}),
                    attachment_marks=list(r["attachment_marks"] or []),
                )
            )
        else:  # content 节点：无标题，整体内联（pdf-content-no-title）
            steps_acc.setdefault(r["parent_id"], []).append(
                StepData(
                    id=r["id"],
                    code=r["code"],
                    title="",
                    content=r["body"],
                    kind="content",
                    skip_numbering=r["skip_numbering"],
                    input_schema={},
                    attachment_marks=[],
                )
            )
    for cid, cd in chapters_by_id.items():
        cd.children = children_acc.get(cid, [])
        cd.steps = steps_acc.get(cid, [])
    root_chapters = children_acc.get(None, [])
    root_steps = steps_acc.get(None, [])
```

(d) Change the asset prefetch source from step rows to node bodies. Replace:

```python
    htmls: list[str] = [s.content for s in steps]
```
with:
```python
    htmls: list[str] = [r["body"] for r in rows]
```

(Everything else — `proc`/`folder` load at the top, `attachments`, `cover_fields`, the `assets` loop body, `ProcedureData`, the final `RenderData(...)` — stays unchanged.)

- [ ] **Step 4: 运行确认通过 + PDF 回归网**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/services/pdf/ tests/integration/test_pdf.py -v`
Expected: PASS — 新 `test_titles_derived_from_node_body` 通过；**所有现存 PDF 测试**（`test_context` / `test_engine` / `test_sections` / `test_html_render` / `test_pdf`）仍绿。它们渲染前都到达 recompute（→ B2a 建 node），故 node 来源产出与旧表等价。若某条旧断言因 node 来源有细微差异（如空 title step 现渲染「（步骤）」一致、code 一致）而红，逐条核对是否真不等价；若是等价但断言写死了旧实现细节，最小改断言（不要改 `sections.py` 视觉）。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/pdf/context.py backend/tests/unit/services/pdf/test_context.py
git commit -m "feat(pdf): source render data from ProcedureNode; derive titles from body (Plan B2b)"
```

---

## Task 3: 全量回归 + mypy

**Files:** 无新增

- [ ] **Step 1: 跑全部后端测试**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: 绿。算术基线：main 现 **662 passed + 1 先存失败**（`test_editor.py::test_create_chapter_and_nested_get`）。B2b 净变动：Task1 step 测试 −1（替换 1 个为 2 个 = 净 +1）、Task2 +1（title 派生测试）= **约 664 passed + 1 先存失败**。⚠️ 若有 PDF 旧测试新红，按 Task2 Step4 的判据处理（区分「真不等价 bug」与「断言写死旧实现」），用 superpowers:systematic-debugging 定位。

- [ ] **Step 2: 类型检查**

Run: `cd backend && .venv/bin/python -m mypy app/services/pdf/context.py app/services/node_sync.py 2>&1 | tail -20`
Expected: 无 **新增** error。`context.py` 可能有先存 error（逐条确认非本计划新增）；lxml 无类型存根时 `fragment_fromstring`/`tostring`/`text_content` 可能报 `import-untyped`/`no-any-return` —— 与 `layer_apply_service` 既有 lxml 用法一致即可（若该处用了 `# type: ignore`，本处比照）。

- [ ] **Step 3: Commit（若有修正）**

```bash
git add -A
git commit -m "chore: type/regression fixes for Plan B2b"
```

---

## 完成标准（B2b）

1. `load_render_data` 完全从 `ProcedureNode`（`node_service.get_nodes`）装配 `RenderData`，不再查 `ProcedureChapter`/`ProcedureStep`；`sections.py` 等渲染层零改动。
2. heading 标题 = node `body` 首块文本；`kind='step'` 标题 = body 首块、正文 = 其余；`content` 节点无标题、整体内联。step `title` 已由 `node_sync` 折进 body 首段（含空 title 恒前置 `<p></p>`）。
3. **所有现存 PDF 测试全绿**（node 来源产出与旧表等价），新增 title 派生测试通过。
4. 编号、章节层级、附件、封面字段、TOC 在新数据源下正确（由现存 PDF 测试覆盖）。
5. 编辑器/`GET /procedures/{id}` 详情读取、sign-off、attachment、version 读取**零改动**（仍读旧表，留给 B3）；parser/schema/前端零改动。

## 交接给 B3 / B4 的事实

- PDF 现读 node。`procedure_service.get_detail`（编辑器详情）+ 前端编辑器仍读 chapter/step —— B3 把这些切到 node，并让编辑器**直接写** node。
- B4：删 `numbering_service`（连同 B2a 的 rebuild hook）、删 `node_sync`、删旧两表后，`load_render_data`←node 的口子原样保留（届时 node 由编辑器直写）。step body 的「空 `<p></p>` 前缀」瑕疵由 B3 编辑器写 node 时规范化。
- 潜在待办：heading 多段 body 的「引言」段当前 PDF 不渲染（现数据形态下 heading body 恒单段，无影响）；若 B3 编辑器允许 heading 内多段，需在 `ChapterData` + `sections._render_chapter` 加引言渲染。
