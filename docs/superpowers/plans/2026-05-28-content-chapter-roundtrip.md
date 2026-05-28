# 内容↔章节双向桥接 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `_try_extract_title_from_body` to `_phase_a_to_chapter` (promote auto-extract: body → title when pure text ≤50 codepoints) and rewrite `_phase_c_to_content` for editorial flatten (chapter title → content body, optionally merged with 1 mirror-shape child). Surface counts via toast.

**Architecture:** All backend logic lives in two helpers + two existing Phase functions in `backend/app/services/layer_apply_service.py`. `LayerApplyResult` schema gains two optional maps (`extracted_titles`, `collapsed_chapters`). Frontend relaxes `effectiveRole`'s `hasLeafChildren` gate (let backend judge), `ChapterTreePanel` shows toast from the new result fields. ContentDetailPanel placeholder also gets cleaned up.

**Tech Stack:** FastAPI + SQLAlchemy + lxml (backend), Pinia + Vue 3 + Vitest (frontend), pytest, Element Plus (ElMessage).

**Reference spec:** `docs/superpowers/specs/2026-05-28-content-chapter-roundtrip-design.md`

---

## Task 0: Baseline — confirm tests pass before changes

**Files:** None (state check only)

- [ ] **Step 1: Verify spec exists + working tree state**

Run from repo root:
```bash
git log --oneline -3
git status --short
git branch --show-current
```

Expected:
- Top commit is `d52234b docs(specs): add content↔chapter roundtrip design ...` (or later commits if user added more on main)
- Working tree clean OR has only unrelated parser WIP — if there's overlap with `layer_apply_service.py`, STOP and ask
- On `main` (or appropriate feature branch — confirm with user before starting)

- [ ] **Step 2: Run backend layer-apply tests + full unit suite**

Run:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit/services/test_layer_apply_service.py -v 2>&1 | tail -20
backend/.venv/bin/python -m pytest backend/tests/unit -q 2>&1 | tail -3
```

Expected: 12 passed (layer-apply specific) and 430+ passed (full unit).

- [ ] **Step 3: Run frontend layerMark + store specs**

Run:
```bash
cd frontend && npm run test -- --run tests/unit/utils/layerMark.spec.ts tests/unit/store/procedureEditor.applyLayerRoles.spec.ts 2>&1 | tail -10
```

Expected: all pass.

---

## Task 1: Schema — extend `LayerApplyResult` with two optional maps

**Files:** Modify `backend/app/schemas/node.py`

- [ ] **Step 1: Locate the existing `LayerApplyResult`**

Run:
```bash
grep -n "class LayerApplyResult" backend/app/schemas/node.py
```

- [ ] **Step 2: Add the two fields**

Modify `LayerApplyResult` to include two optional dict fields. The class should look like:

```python
class LayerApplyResult(BaseModel):
    """成功:返回本 batch leaf→new_chapter 映射 + 新 revision。
    extracted_titles: 触发了 promote auto-extract 的行映射(old_step_id → 抽取的 title)
    collapsed_chapters: 触发了 demote 1-mirror-child 合并的章节映射(old_chapter_id → 被合并子 step_id)
    """

    chapter_map: dict[str, str] = Field(default_factory=dict)
    revision: int
    extracted_titles: dict[str, str] = Field(default_factory=dict)
    collapsed_chapters: dict[str, str] = Field(default_factory=dict)
```

- [ ] **Step 3: Verify schema parses**

Run:
```bash
backend/.venv/bin/python -c "from app.schemas.node import LayerApplyResult; r = LayerApplyResult(revision=1); print(r.model_dump())"
```

Expected: `{'chapter_map': {}, 'revision': 1, 'extracted_titles': {}, 'collapsed_chapters': {}}`

- [ ] **Step 4: Run existing layer-apply tests to confirm no regression**

Run:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit/services/test_layer_apply_service.py -v 2>&1 | tail -5
```

Expected: 12 passed (existing tests don't check these new fields yet, so should still pass).

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/node.py
git commit -m "$(cat <<'EOF'
feat(layer-apply): extend LayerApplyResult with extracted_titles + collapsed_chapters

Two optional maps for surfacing auto-extract (promote) and editorial
flatten (demote) counts/details. Spec §1, §2.2, §3.1.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `_try_extract_title_from_body` helper + 6 unit tests

**Files:**
- Modify `backend/app/services/layer_apply_service.py` (add helper)
- Modify `backend/tests/unit/services/test_layer_apply_service.py` (add tests)

- [ ] **Step 1: Write 6 failing tests covering all extract preconditions**

Append to `backend/tests/unit/services/test_layer_apply_service.py` (after existing tests):

```python
# ---------------------------------------------------------------------------
# _try_extract_title_from_body — pure helper (spec §2.1-§2.3)
# ---------------------------------------------------------------------------


def test_extract_pure_text_short_p_returns_text() -> None:
    assert layer_apply_service._try_extract_title_from_body("<p>3.1 质量部</p>") == "3.1 质量部"


def test_extract_body_too_long_returns_none() -> None:
    body = "<p>" + ("你" * 51) + "</p>"
    assert layer_apply_service._try_extract_title_from_body(body) is None


def test_extract_body_has_bold_returns_none() -> None:
    assert layer_apply_service._try_extract_title_from_body("<p><b>x</b></p>") is None


def test_extract_body_multi_block_returns_none() -> None:
    assert layer_apply_service._try_extract_title_from_body("<p>x</p><p>y</p>") is None


def test_extract_body_with_br_returns_none() -> None:
    assert layer_apply_service._try_extract_title_from_body("<p>x<br>y</p>") is None


def test_extract_html_entity_decoded() -> None:
    assert layer_apply_service._try_extract_title_from_body("<p>3.1 &amp; 4.0</p>") == "3.1 & 4.0"


def test_extract_empty_p_returns_none() -> None:
    assert layer_apply_service._try_extract_title_from_body("<p>  </p>") is None


def test_extract_empty_body_returns_none() -> None:
    assert layer_apply_service._try_extract_title_from_body("") is None
    assert layer_apply_service._try_extract_title_from_body(None) is None  # type: ignore[arg-type]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit/services/test_layer_apply_service.py -k "extract" -v 2>&1 | tail -15
```

Expected: all 8 FAIL with `AttributeError` on `layer_apply_service._try_extract_title_from_body`.

- [ ] **Step 3: Implement the helper**

Add to `backend/app/services/layer_apply_service.py` (after the existing imports + constants, before `_get_proc_editable`):

```python
def _try_extract_title_from_body(body: str | None) -> str | None:
    """promote auto-extract 资格判定(spec §2.1):body 是 1 个 <p>,内部纯文本(无子元素 / 无样式),
    长度 ≤ 50 Unicode 码点 → 返回提取的纯文本;任一不满足返回 None。
    HTML 实体(如 &amp;)在 lxml 解析时解码为对应字符。
    """
    if not body or not body.strip():
        return None
    try:
        from lxml import html as lxml_html

        frag = lxml_html.fragment_fromstring(body, create_parent="div")
    except Exception:  # 异常 HTML / 解析失败,保守返回 None
        return None
    children = list(frag)
    if len(children) != 1:
        return None
    p = children[0]
    if p.tag != "p":
        return None
    if list(p):  # <p> 含任何子元素 (<b><i><span><br><img>) → 不算纯文本
        return None
    text = p.text or ""
    if len(text) > 50:
        return None
    if not text.strip():
        return None
    return text
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit/services/test_layer_apply_service.py -k "extract" -v 2>&1 | tail -15
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/layer_apply_service.py backend/tests/unit/services/test_layer_apply_service.py
git commit -m "$(cat <<'EOF'
feat(layer-apply): _try_extract_title_from_body helper

Strict purity check (1 <p>, all text nodes inside, ≤50 codepoints).
HTML entities decoded by lxml. Returns None on any precondition miss,
including malformed HTML (defensive try/except).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Wire auto-extract into `_phase_a_to_chapter`

**Files:**
- Modify `backend/app/services/layer_apply_service.py` (update Phase A + apply_layer_roles)
- Modify `backend/tests/unit/services/test_layer_apply_service.py` (add 2 integration tests)

- [ ] **Step 1: Read the current Phase A signature + apply_layer_roles**

Run:
```bash
sed -n '125,170p' backend/app/services/layer_apply_service.py
```

Take note of the current function signature for `_phase_a_to_chapter` (returns `dict[str, str]`). It will change to also return extracted_titles.

- [ ] **Step 2: Write failing integration tests**

Append to `backend/tests/unit/services/test_layer_apply_service.py`:

```python
def test_promote_auto_extract_pure_text_short(db: Session, factory: Factory) -> None:
    """parser 漏识别的二级标题场景:content title 空,body 是 1 个短 <p> → 抽取为新章节 title,无子。"""
    from app.models.chapter import ProcedureChapter
    from app.models.step import ProcedureStep

    proc = _proc(factory)
    ch = factory.chapter(proc.id, title="职责", level=1)
    s = factory.step(
        proc.id, chapter_id=ch.id, kind="content", title="", content="<p>3.1 质量部</p>", sort_order=0
    )

    result = layer_apply_service.apply_layer_roles(
        db, proc.id, roles={s.id: "chapter_2"}, expected_revision=proc.revision, meta=META
    )

    new_ch_id = result["chapter_map"][s.id]
    new_ch = db.get(ProcedureChapter, new_ch_id)
    assert new_ch.title == "3.1 质量部"
    # 抽取命中 → 不建子 content step
    children = db.execute(
        select(ProcedureStep).where(ProcedureStep.chapter_id == new_ch_id, ProcedureStep.is_active.is_(True))
    ).scalars().all()
    assert len(children) == 0
    # extracted_titles 记录命中
    assert result["extracted_titles"][s.id] == "3.1 质量部"


def test_promote_no_extract_fallback_creates_child(db: Session, factory: Factory) -> None:
    """body 是多块 → 不抽取,回落:title="未命名章节",body 进子 content step。"""
    from app.models.chapter import ProcedureChapter
    from app.models.step import ProcedureStep

    proc = _proc(factory)
    ch = factory.chapter(proc.id, title="职责", level=1)
    s = factory.step(
        proc.id, chapter_id=ch.id, kind="content", title="", content="<p>a</p><p>b</p>", sort_order=0
    )

    result = layer_apply_service.apply_layer_roles(
        db, proc.id, roles={s.id: "chapter_2"}, expected_revision=proc.revision, meta=META
    )

    new_ch_id = result["chapter_map"][s.id]
    new_ch = db.get(ProcedureChapter, new_ch_id)
    assert new_ch.title == "未命名章节"
    children = db.execute(
        select(ProcedureStep).where(ProcedureStep.chapter_id == new_ch_id, ProcedureStep.is_active.is_(True))
    ).scalars().all()
    assert len(children) == 1
    assert children[0].content == "<p>a</p><p>b</p>"
    assert s.id not in result["extracted_titles"]


def test_promote_no_extract_when_title_already_set(db: Session, factory: Factory) -> None:
    """title 非空 → 即使 body 是短纯文本,也不触发 auto-extract,使用 st.title。"""
    from app.models.chapter import ProcedureChapter
    from app.models.step import ProcedureStep

    proc = _proc(factory)
    ch = factory.chapter(proc.id, title="职责", level=1)
    s = factory.step(
        proc.id, chapter_id=ch.id, kind="content", title="崔宇明", content="<p>3.1 短</p>", sort_order=0
    )

    result = layer_apply_service.apply_layer_roles(
        db, proc.id, roles={s.id: "chapter_2"}, expected_revision=proc.revision, meta=META
    )

    new_ch_id = result["chapter_map"][s.id]
    new_ch = db.get(ProcedureChapter, new_ch_id)
    assert new_ch.title == "崔宇明"  # 用了 st.title,不抽取
    # body 仍走回落 → 进子 content step
    children = db.execute(
        select(ProcedureStep).where(ProcedureStep.chapter_id == new_ch_id, ProcedureStep.is_active.is_(True))
    ).scalars().all()
    assert len(children) == 1
    assert children[0].content == "<p>3.1 短</p>"
    assert s.id not in result["extracted_titles"]
```

Run:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit/services/test_layer_apply_service.py::test_promote_auto_extract_pure_text_short backend/tests/unit/services/test_layer_apply_service.py::test_promote_no_extract_fallback_creates_child -v 2>&1 | tail -15
```

Expected: FAIL (the first one because extract isn't wired; the second one might pass — both should fail until Phase A is updated to return `extracted_titles`).

- [ ] **Step 3: Update `_phase_a_to_chapter` signature + body**

Replace `_phase_a_to_chapter` in `backend/app/services/layer_apply_service.py` with:

```python
def _phase_a_to_chapter(
    db: Session,
    proc: Procedure,
    rows: list[LayerRow],
    updates: dict[str, dict],
) -> tuple[dict[str, str], dict[str, str]]:
    """按文档序执行 to-chapter。
    返回 (chapter_map, extracted_titles):
      - chapter_map: leaf_id → new_chapter_id(parent_id 解析用)
      - extracted_titles: 命中 auto-extract 的 leaf_id → 抽取出的标题文本
    """
    from app.models.base import utcnow

    chapter_map: dict[str, str] = {}
    extracted_titles: dict[str, str] = {}
    step_by_id = {
        s.id: s for s in db.execute(
            select(ProcedureStep).where(
                ProcedureStep.procedure_id == proc.id,
                ProcedureStep.is_active.is_(True),
            )
        ).scalars()
    }
    for row in rows:
        u = updates.get(row.id)
        if not u or u["kind"] != "to-chapter":
            continue
        st = step_by_id[row.id]
        resolved_parent = chapter_map.get(u["parent_id"], u["parent_id"])

        # auto-extract 判定:仅当 st.title 为空时尝试
        extracted = None
        if not (st.title and st.title.strip()):
            extracted = _try_extract_title_from_body(st.content)

        new_ch = ProcedureChapter(
            procedure_id=proc.id,
            parent_id=resolved_parent,
            title=extracted or st.title or "未命名章节",
            sort_order=u["sort_order"],
            level=u["level"],
        )
        db.add(new_ch)
        db.flush()

        if extracted is not None:
            # 命中抽取:body 已搬到 title,不建子 content step
            extracted_titles[row.id] = extracted
        elif st.content and st.content.strip():
            # 回落:body 进子 content step(现行逻辑)
            child = ProcedureStep(
                procedure_id=proc.id,
                chapter_id=new_ch.id,
                kind="content",
                title="",
                content=st.content,
                input_schema={},
                sort_order=0,
            )
            db.add(child)
            db.flush()

        st.is_active = False
        st.deleted_at = utcnow()
        chapter_map[row.id] = new_ch.id

    return chapter_map, extracted_titles
```

- [ ] **Step 4: Update `apply_layer_roles` to consume the tuple**

In the same file, find the line in `apply_layer_roles` that calls `_phase_a_to_chapter` and modify it. Also extend the return dict.

Replace the call site (around the end of `apply_layer_roles`):

```python
    chapter_map, extracted_titles = _phase_a_to_chapter(db, proc, rows, updates)
    _phase_b_reorder(db, updates, chapter_map)
    _phase_c_to_content(db, proc, updates, chapter_map)
    _phase_d_leaf_reparent(db, updates, chapter_map)
    db.flush()

    numbering_service.recompute(db, proc.id)
    optimistic_lock.bump(proc)
    db.flush()

    audit_service.log_procedure_action(
        db,
        target_id=proc.id,
        procedure_group_id=proc.procedure_group_id,
        action="apply-layer-roles",
        meta=meta,
        old_value={"role_count": len(roles)},
        new_value={"chapter_map": chapter_map, "extracted_count": len(extracted_titles)},
    )

    return {
        "chapter_map": chapter_map,
        "revision": proc.revision,
        "extracted_titles": extracted_titles,
        "collapsed_chapters": {},  # Phase C 在 Task 6 填充
    }
```

- [ ] **Step 5: Run the new tests + existing tests**

Run:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit/services/test_layer_apply_service.py -v 2>&1 | tail -25
```

Expected: 23 passed (12 prior + 8 extract helper + 3 promote integration).

If `test_screenshot_scenario_three_l2_promotions_with_adoption` (or other existing tests) now fail, inspect — most likely because:
- Existing tests assume `result["extracted_titles"]` doesn't exist (key error). Fix by changing assertions to `.get("extracted_titles", {})` or adding the key.
- Existing test factories produce content with non-empty title (e.g., "崔宇明") so auto-extract shouldn't trigger — should still work.

If anything breaks, fix it before committing.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/layer_apply_service.py backend/tests/unit/services/test_layer_apply_service.py
git commit -m "$(cat <<'EOF'
feat(layer-apply): promote auto-extract (body → chapter title for short pure text)

When content has empty title and body is exactly 1 <p> with pure text
≤50 codepoints, extract the text as the new chapter's title and skip
creating a child content step. Otherwise fall back to existing
"未命名章节" + child-content behavior.

Solves the parser-missed-heading case (e.g. "3.1 质量部是记录的归口管理部门")
in a single layer-mode apply instead of post-edit manual cleanup.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `_leaf_children` helper + upgrade `_validate_chapter_children_for_content`

**Files:** Modify `backend/app/services/layer_apply_service.py`

- [ ] **Step 1: Read current validator + Phase C location**

Run:
```bash
sed -n '180,260p' backend/app/services/layer_apply_service.py
```

- [ ] **Step 2: Add `_leaf_children` helper**

Insert after `_has_chapter_children` in `backend/app/services/layer_apply_service.py`:

```python
def _leaf_children(db: Session, proc_id: str, chapter_id: str) -> list[ProcedureStep]:
    """返回章节下所有活跃叶子(step + content),按 sort_order 排序。"""
    return list(
        db.execute(
            select(ProcedureStep)
            .where(
                ProcedureStep.procedure_id == proc_id,
                ProcedureStep.chapter_id == chapter_id,
                ProcedureStep.is_active.is_(True),
            )
            .order_by(ProcedureStep.sort_order, ProcedureStep.id)
        ).scalars()
    )
```

- [ ] **Step 3: Upgrade `_validate_chapter_children_for_content` (pre-Apply check)**

Replace the existing `_validate_chapter_children_for_content` body with:

```python
def _validate_chapter_children_for_content(
    db: Session, proc_id: str, updates: dict[str, dict]
) -> None:
    """章节标 to-content 时校验形态(spec §3.2):
    - 有子章节 → 400 CHAPTER_HAS_CHILDREN
    - 叶子子节点 >1 → 400 NOT_MIRROR_SHAPE
    - 1 个叶子子但 (kind != 'content' 或 title 非空) → 400 NOT_MIRROR_SHAPE
    """
    for node_id, u in updates.items():
        if u["kind"] != "to-content":
            continue
        ch = db.get(ProcedureChapter, node_id)
        if ch is None or not ch.is_active:
            continue
        if _has_chapter_children(db, proc_id, ch.id):
            raise bad_request(
                "CHAPTER_HAS_CHILDREN",
                f"章节 {ch.title or ch.id} 仍含子章节,不可降为内容",
            )
        leaves = _leaf_children(db, proc_id, ch.id)
        if len(leaves) > 1:
            raise bad_request(
                "NOT_MIRROR_SHAPE",
                f"章节 {ch.title or ch.id} 有 {len(leaves)} 个叶子子节点,请先手动合并为 0 个或 1 个无标题内容块",
            )
        if len(leaves) == 1:
            child = leaves[0]
            if child.kind != "content" or (child.title or "").strip() != "":
                raise bad_request(
                    "NOT_MIRROR_SHAPE",
                    f"章节 {ch.title or ch.id} 的叶子子节点不是无标题内容块,请先手动重组",
                )
```

- [ ] **Step 4: Verify file parses + existing tests still pass**

Run:
```bash
backend/.venv/bin/python -c "from app.services.layer_apply_service import _leaf_children, _validate_chapter_children_for_content; print('ok')"
backend/.venv/bin/python -m pytest backend/tests/unit/services/test_layer_apply_service.py -v 2>&1 | tail -10
```

Expected: `ok`; 22 passed.

Note: `test_phase_c_chapter_has_children_rejects` still passes because chapter-children check runs first. Other demote tests use 0-child chapters, so the new leaf-count check has nothing to reject yet.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/layer_apply_service.py
git commit -m "$(cat <<'EOF'
feat(layer-apply): _leaf_children helper + tighten to-content pre-validator

Pre-Apply validator now rejects non-mirror shapes (multi-child, step
children, child with title) with NOT_MIRROR_SHAPE before Phase C runs.
Phase C will retain a backstop check in the next commit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Rewrite `_phase_c_to_content` for editorial flatten + 6 demote tests

**Files:**
- Modify `backend/app/services/layer_apply_service.py` (Phase C rewrite + apply_layer_roles wiring)
- Modify `backend/tests/unit/services/test_layer_apply_service.py` (6 new tests)

- [ ] **Step 1: Write failing demote tests**

Append to `backend/tests/unit/services/test_layer_apply_service.py`:

```python
# ---------------------------------------------------------------------------
# demote editorial flatten (spec §3)
# ---------------------------------------------------------------------------


def test_demote_one_child_content_flattens(db: Session, factory: Factory) -> None:
    """镜像形态:chapter("Y", child(body="<p>B</p>")) → content(body="<p>Y</p><p>B</p>"),child 软删。"""
    from app.models.step import ProcedureStep

    proc = _proc(factory)
    a = factory.chapter(proc.id, title="A", level=1, sort_order=0)
    ch = factory.chapter(proc.id, title="Y", parent_id=a.id, level=2, sort_order=0)
    child = factory.step(
        proc.id, chapter_id=ch.id, kind="content", title="", content="<p>B</p>", sort_order=0
    )

    result = layer_apply_service.apply_layer_roles(
        db, proc.id, roles={a.id: "chapter_1", ch.id: "content"}, expected_revision=proc.revision, meta=META
    )

    # ch 被软删,child 被软删
    db.refresh(ch); db.refresh(child)
    assert not ch.is_active
    assert not child.is_active

    # A 下新增 1 个 content step,body 是 <p>Y</p><p>B</p>
    siblings = db.execute(
        select(ProcedureStep).where(ProcedureStep.chapter_id == a.id, ProcedureStep.is_active.is_(True))
    ).scalars().all()
    assert len(siblings) == 1
    assert siblings[0].content == "<p>Y</p><p>B</p>"
    assert siblings[0].title == ""

    # collapsed_chapters 记录命中
    assert result["collapsed_chapters"][ch.id] == child.id


def test_demote_long_title_flattens_no_length_gate(db: Session, factory: Factory) -> None:
    """无 ≤50 门槛:>50 码点的章节标题也能 flatten。"""
    from app.models.step import ProcedureStep

    long_title = "这是一个很长的章节标题" * 8  # 88 codepoints
    proc = _proc(factory)
    a = factory.chapter(proc.id, title="A", level=1, sort_order=0)
    ch = factory.chapter(proc.id, title=long_title, parent_id=a.id, level=2, sort_order=0)
    factory.step(proc.id, chapter_id=ch.id, kind="content", title="", content="<p>B</p>", sort_order=0)

    layer_apply_service.apply_layer_roles(
        db, proc.id, roles={a.id: "chapter_1", ch.id: "content"}, expected_revision=proc.revision, meta=META
    )

    siblings = db.execute(
        select(ProcedureStep).where(ProcedureStep.chapter_id == a.id, ProcedureStep.is_active.is_(True))
    ).scalars().all()
    assert len(siblings) == 1
    assert siblings[0].content == f"<p>{long_title}</p><p>B</p>"


def test_demote_empty_title_one_child_omits_p_prefix(db: Session, factory: Factory) -> None:
    """ch.title 为空时不前缀 <p></p>,直接用 child.body。"""
    from app.models.step import ProcedureStep

    proc = _proc(factory)
    a = factory.chapter(proc.id, title="A", level=1, sort_order=0)
    ch = factory.chapter(proc.id, title="", parent_id=a.id, level=2, sort_order=0)
    factory.step(proc.id, chapter_id=ch.id, kind="content", title="", content="<p>B</p>", sort_order=0)

    layer_apply_service.apply_layer_roles(
        db, proc.id, roles={a.id: "chapter_1", ch.id: "content"}, expected_revision=proc.revision, meta=META
    )

    siblings = db.execute(
        select(ProcedureStep).where(ProcedureStep.chapter_id == a.id, ProcedureStep.is_active.is_(True))
    ).scalars().all()
    assert len(siblings) == 1
    assert siblings[0].content == "<p>B</p>"  # 无前缀空 <p></p>


def test_demote_one_child_content_has_title_refuses(db: Session, factory: Factory) -> None:
    """子 content 自己有 title → NOT_MIRROR_SHAPE。"""
    proc = _proc(factory)
    a = factory.chapter(proc.id, title="A", level=1, sort_order=0)
    ch = factory.chapter(proc.id, title="Y", parent_id=a.id, level=2, sort_order=0)
    factory.step(proc.id, chapter_id=ch.id, kind="content", title="子标题", content="<p>B</p>", sort_order=0)

    with pytest.raises(HTTPException) as ex:
        layer_apply_service.apply_layer_roles(
            db, proc.id, roles={a.id: "chapter_1", ch.id: "content"}, expected_revision=proc.revision, meta=META
        )
    assert ex.value.status_code == 400
    assert ex.value.detail["code"] == "NOT_MIRROR_SHAPE"


def test_demote_one_child_step_refuses(db: Session, factory: Factory) -> None:
    """子是 kind='step' → NOT_MIRROR_SHAPE。"""
    proc = _proc(factory)
    a = factory.chapter(proc.id, title="A", level=1, sort_order=0)
    ch = factory.chapter(proc.id, title="Y", parent_id=a.id, level=2, sort_order=0)
    factory.step(proc.id, chapter_id=ch.id, kind="step", title="", content="<p>B</p>", sort_order=0)

    with pytest.raises(HTTPException) as ex:
        layer_apply_service.apply_layer_roles(
            db, proc.id, roles={a.id: "chapter_1", ch.id: "content"}, expected_revision=proc.revision, meta=META
        )
    assert ex.value.detail["code"] == "NOT_MIRROR_SHAPE"


def test_demote_two_content_children_refuses(db: Session, factory: Factory) -> None:
    """2+ 个 content 子 → NOT_MIRROR_SHAPE。"""
    proc = _proc(factory)
    a = factory.chapter(proc.id, title="A", level=1, sort_order=0)
    ch = factory.chapter(proc.id, title="Y", parent_id=a.id, level=2, sort_order=0)
    factory.step(proc.id, chapter_id=ch.id, kind="content", title="", content="<p>1</p>", sort_order=0)
    factory.step(proc.id, chapter_id=ch.id, kind="content", title="", content="<p>2</p>", sort_order=1)

    with pytest.raises(HTTPException) as ex:
        layer_apply_service.apply_layer_roles(
            db, proc.id, roles={a.id: "chapter_1", ch.id: "content"}, expected_revision=proc.revision, meta=META
        )
    assert ex.value.detail["code"] == "NOT_MIRROR_SHAPE"
```

Run them:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit/services/test_layer_apply_service.py -k "demote_one_child or demote_long_title or demote_empty_title or demote_two_content" -v 2>&1 | tail -15
```

Expected: 6 tests, 3 PASS (the refuse tests already work due to upgraded validator in Task 4) and 3 FAIL (`demote_one_child_content_flattens`, `demote_long_title_flattens_no_length_gate`, `demote_empty_title_one_child_omits_p_prefix` — Phase C doesn't yet handle 1-child case).

- [ ] **Step 2: Rewrite `_phase_c_to_content` for editorial flatten**

Replace the existing `_phase_c_to_content` body in `backend/app/services/layer_apply_service.py` with:

```python
def _phase_c_to_content(
    db: Session,
    proc: Procedure,
    updates: dict[str, dict],
    chapter_map: dict[str, str],
) -> dict[str, str]:
    """章节 → 内容(editorial flatten,spec §3.1):
    - 0 子:body = "<p>title</p>"(标题非空时)
    - 1 mirror 子(kind=content, title 空):body = "<p>title</p>" + child.body,child 软删
    - 其他:NOT_MIRROR_SHAPE(此处兜底;预校验已拦截)
    返回 collapsed_chapters: old_chapter_id → 被合并子 step_id
    """
    from app.models.base import utcnow

    collapsed: dict[str, str] = {}
    for node_id, u in updates.items():
        if u["kind"] != "to-content":
            continue
        ch = db.get(ProcedureChapter, node_id)
        if ch is None or not ch.is_active:
            continue

        # Backstop:与 _validate_chapter_children_for_content 同语义,防绕过 / race
        if _has_chapter_children(db, proc.id, ch.id):
            raise bad_request("CHAPTER_HAS_CHILDREN", f"章节 {ch.title or ch.id} 仍含子章节")
        leaves = _leaf_children(db, proc.id, ch.id)
        if len(leaves) > 1 or (
            len(leaves) == 1
            and (leaves[0].kind != "content" or (leaves[0].title or "").strip() != "")
        ):
            raise bad_request("NOT_MIRROR_SHAPE", f"章节 {ch.title or ch.id} 形态不可逆为内容")

        title_html = f"<p>{_html.escape(ch.title)}</p>" if (ch.title or "").strip() else ""
        if not leaves:
            body = title_html
        else:
            child = leaves[0]
            body = title_html + (child.content or "")
            child.is_active = False
            child.deleted_at = utcnow()
            collapsed[ch.id] = child.id

        new_step = ProcedureStep(
            procedure_id=proc.id,
            chapter_id=chapter_map.get(u["parent_id"], u["parent_id"]),
            kind="content",
            title="",
            content=body,
            input_schema={},
            sort_order=u["sort_order"],
        )
        db.add(new_step)
        db.flush()
        ch.is_active = False
        ch.deleted_at = utcnow()

    return collapsed
```

- [ ] **Step 3: Wire `collapsed_chapters` into `apply_layer_roles`**

In `apply_layer_roles`, change the phase calls + return:

```python
    chapter_map, extracted_titles = _phase_a_to_chapter(db, proc, rows, updates)
    _phase_b_reorder(db, updates, chapter_map)
    collapsed_chapters = _phase_c_to_content(db, proc, updates, chapter_map)
    _phase_d_leaf_reparent(db, updates, chapter_map)
    db.flush()

    numbering_service.recompute(db, proc.id)
    optimistic_lock.bump(proc)
    db.flush()

    audit_service.log_procedure_action(
        db,
        target_id=proc.id,
        procedure_group_id=proc.procedure_group_id,
        action="apply-layer-roles",
        meta=meta,
        old_value={"role_count": len(roles)},
        new_value={
            "chapter_map": chapter_map,
            "extracted_count": len(extracted_titles),
            "collapsed_count": len(collapsed_chapters),
        },
    )

    return {
        "chapter_map": chapter_map,
        "revision": proc.revision,
        "extracted_titles": extracted_titles,
        "collapsed_chapters": collapsed_chapters,
    }
```

- [ ] **Step 4: Run all layer-apply tests**

Run:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit/services/test_layer_apply_service.py -v 2>&1 | tail -30
```

Expected: 29 passed (23 prior + 6 new demote).

If `test_phase_bc_reorder_and_to_content` (an old test) now fails, inspect — that test demotes a chapter with no children, and §3.3 says the behavior is unchanged (`body = "<p>title</p>"`). Should still pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/layer_apply_service.py backend/tests/unit/services/test_layer_apply_service.py
git commit -m "$(cat <<'EOF'
feat(layer-apply): demote editorial flatten — chapter title → content body

Phase C rewrite: 0 child → body=<p>title</p> (unchanged); 1 mirror
child (content, no title) → body=<p>title</p>+child.body, child
soft-deleted, collapsed_chapters tracked. Else → NOT_MIRROR_SHAPE
(predicated, plus Phase C backstop).

Round-trip 2 (content with title+body → promote → demote) is now
explicitly broken in favor of editorial flatten intent. See spec §1.2.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Round-trip + mixed batch tests

**Files:** Modify `backend/tests/unit/services/test_layer_apply_service.py`

- [ ] **Step 1: Add 3 invariant tests**

Append to `backend/tests/unit/services/test_layer_apply_service.py`:

```python
def test_roundtrip_1_auto_extract_path(db: Session, factory: Factory) -> None:
    """Round-trip 1 严格成立:content(空 title + 短纯文本 body) → promote → demote → 起点。"""
    from app.models.step import ProcedureStep

    proc = _proc(factory)
    a = factory.chapter(proc.id, title="A", level=1, sort_order=0)
    s = factory.step(
        proc.id, chapter_id=a.id, kind="content", title="", content="<p>3.1 X</p>", sort_order=0
    )

    # promote
    r1 = layer_apply_service.apply_layer_roles(
        db, proc.id, roles={s.id: "chapter_2"}, expected_revision=proc.revision, meta=META
    )
    new_ch_id = r1["chapter_map"][s.id]

    # demote 回去
    r2 = layer_apply_service.apply_layer_roles(
        db, proc.id, roles={new_ch_id: "content"}, expected_revision=proc.revision, meta=META
    )

    # 验证:A 下应有 1 个 content,title="",body="<p>3.1 X</p>"
    final = db.execute(
        select(ProcedureStep).where(ProcedureStep.chapter_id == a.id, ProcedureStep.is_active.is_(True))
    ).scalars().all()
    assert len(final) == 1
    assert final[0].title == ""
    assert final[0].content == "<p>3.1 X</p>"


def test_roundtrip_2_explicitly_breaks(db: Session, factory: Factory) -> None:
    """Round-trip 2 透明放弃(spec §1.2):content(title="Y", body="<p>B</p>") → promote → demote → 
    content(title="", body="<p>Y</p><p>B</p>"),与起点 NOT 相等。
    
    这个负例锁住设计决策:未来若有人改回严格 round-trip,本测试会挂。
    """
    from app.models.step import ProcedureStep

    proc = _proc(factory)
    a = factory.chapter(proc.id, title="A", level=1, sort_order=0)
    s = factory.step(
        proc.id, chapter_id=a.id, kind="content", title="Y", content="<p>B</p>", sort_order=0
    )

    # promote
    r1 = layer_apply_service.apply_layer_roles(
        db, proc.id, roles={s.id: "chapter_2"}, expected_revision=proc.revision, meta=META
    )
    new_ch_id = r1["chapter_map"][s.id]

    # demote 回去
    layer_apply_service.apply_layer_roles(
        db, proc.id, roles={new_ch_id: "content"}, expected_revision=proc.revision, meta=META
    )

    final = db.execute(
        select(ProcedureStep).where(ProcedureStep.chapter_id == a.id, ProcedureStep.is_active.is_(True))
    ).scalars().all()
    assert len(final) == 1
    # ✗ NOT 相等 — 这就是 round-trip 2 不严格的设计决策
    assert final[0].title == ""  # 起点 title 是 "Y",现在变成 ""
    assert final[0].content == "<p>Y</p><p>B</p>"  # body 多了 <p>Y</p> 前缀


def test_mixed_batch_extract_and_flatten_same_apply(db: Session, factory: Factory) -> None:
    """同一次 apply 内既触发 auto-extract 又触发 lift-child,两个 map 都非空。"""
    proc = _proc(factory)
    root = factory.chapter(proc.id, title="root", level=1, sort_order=0)

    # 第一组:promote 一个空标题短 content → 触发 extract
    short_content = factory.step(
        proc.id, chapter_id=root.id, kind="content", title="", content="<p>新二级</p>", sort_order=0
    )
    # 第二组:demote 一个 1-mirror-child 章节 → 触发 collapse
    target_ch = factory.chapter(proc.id, title="Y", parent_id=root.id, level=2, sort_order=1)
    mirror_child = factory.step(
        proc.id, chapter_id=target_ch.id, kind="content", title="", content="<p>B</p>", sort_order=0
    )

    result = layer_apply_service.apply_layer_roles(
        db,
        proc.id,
        roles={short_content.id: "chapter_2", target_ch.id: "content"},
        expected_revision=proc.revision,
        meta=META,
    )

    assert short_content.id in result["extracted_titles"]
    assert result["extracted_titles"][short_content.id] == "新二级"
    assert target_ch.id in result["collapsed_chapters"]
    assert result["collapsed_chapters"][target_ch.id] == mirror_child.id
```

Run them:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit/services/test_layer_apply_service.py -k "roundtrip or mixed_batch" -v 2>&1 | tail -15
```

Expected: 3 passed.

If `test_roundtrip_1_auto_extract_path` fails, check:
- After promote, chapter has 0 children (Phase A auto-extract didn't create child) — verify with debug print before demote.
- After demote, Phase C 0-child branch produces `<p>3.1 X</p>` body.

If `test_roundtrip_2_explicitly_breaks` PASSES on equality (instead of failing as the negative assertion is structured), the Phase C 1-child logic is wrong — re-read §3.1.

- [ ] **Step 2: Run full backend suite**

Run:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit -q 2>&1 | tail -3
```

Expected: 450+ passed (430 prior + 8 extract helper + 3 promote + 6 demote + 3 invariant = 450).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/services/test_layer_apply_service.py
git commit -m "$(cat <<'EOF'
test(layer-apply): roundtrip invariants + mixed batch

Round-trip 1 (auto-extract path) holds strictly; round-trip 2
(title+body path) is explicitly asserted to NOT equal start state —
lock the editorial-flatten design decision against future regressions.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Frontend — relax `effectiveRole` + update layerMark.spec

**Files:**
- Modify `frontend/src/utils/layerMark.ts:33-46`
- Modify `frontend/tests/unit/utils/layerMark.spec.ts`

- [ ] **Step 1: Read current effectiveRole**

Run:
```bash
sed -n '30,50p' frontend/src/utils/layerMark.ts
```

- [ ] **Step 2: Remove the hasLeafChildren gate**

In `frontend/src/utils/layerMark.ts`, locate the `_effectiveRole` (or `effectiveRole`) function. Remove the line `if (role === 'content' && row.hasLeafChildren) return defaultLayerRole(row)`. The function should end up as:

```typescript
function effectiveRole(row: LayerRow, roleMap: Map<string, LayerRole>): LayerRole {
  const role = roleMap.get(row.id) ?? defaultLayerRole(row)
  if (row.kind === 'chapter') {
    // 章节不可选 'keep'，夹回默认
    if (role === 'keep') return defaultLayerRole(row)
    return role
  }
  // 叶子：'content' 在叶子上无意义，夹回 keep
  if (role === 'content') return 'keep'
  return role
}
```

(Compare your edit with the spec §4.1 diff; exact text may differ in indent/comment but the deletion is the single `if (... hasLeafChildren ...)` line.)

- [ ] **Step 3: Update layerMark.spec.ts**

Find the test that asserts 'content' on a chapter with leaf children gets dismissed. Grep:
```bash
grep -n "hasLeafChildren.*content\|content.*hasLeafChildren" frontend/tests/unit/utils/layerMark.spec.ts
```

Find any test that asserts "chapter with hasLeafChildren=true picking 'content' → effective role flips back". Update the assertion: now picking 'content' on such a row should return 'content' (let backend judge).

If no specific test exists, append:

```typescript
describe('effectiveRole — chapter content role relaxation', () => {
  it('章节有 leaf 子也允许选 content（后端校验镜像形态）', () => {
    const rows: LayerRow[] = [
      { id: 'A', kind: 'chapter', level: 1, hasLeafChildren: true },
    ]
    const updates = computeLayerUpdates(rows, new Map([['A', 'content']]))
    // 旧:被夹回 reorder。新:成为 to-content。
    expect(updates.get('A')?.kind).toBe('to-content')
  })
})
```

- [ ] **Step 4: Run frontend layerMark tests**

Run:
```bash
cd frontend && npm run test -- --run tests/unit/utils/layerMark.spec.ts 2>&1 | tail -10
```

Expected: all pass (existing fixture + Q25 tests don't touch this branch; new test passes).

If an existing test breaks because it expected the old block, fix the assertion to match new behavior (and document why).

- [ ] **Step 5: Commit (from repo root)**

```bash
cd /Users/yuming/Desktop/claude\ projects/HP_smart\ sop/SmartSOP
git add frontend/src/utils/layerMark.ts frontend/tests/unit/utils/layerMark.spec.ts
git commit -m "$(cat <<'EOF'
feat(layer): relax effectiveRole — allow content role on chapter with leaf children

Backend now validates mirror shape (NOT_MIRROR_SHAPE) and editorial
flatten handles the valid 1-mirror-child case. Frontend stops silently
dismissing the role pick; user gets backend banner on non-mirror.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Frontend — extend `LayerApplyResult` type + store action passthrough

**Files:**
- Modify `frontend/src/types/node.ts`
- Modify `frontend/src/store/procedureEditor.ts` (applyLayerRoles return type)

- [ ] **Step 1: Extend type**

In `frontend/src/types/node.ts`, find `LayerApplyResult` and add two optional fields:

```typescript
export interface LayerApplyResult {
  chapter_map: Record<string, string>
  revision: number
  extracted_titles?: Record<string, string>
  collapsed_chapters?: Record<string, string>
}
```

- [ ] **Step 2: Extend store action return type**

Read current `applyLayerRoles` signature:
```bash
grep -n "async applyLayerRoles" frontend/src/store/procedureEditor.ts
```

Modify the signature to also surface counts. Change the success branch to include counts:

```typescript
    async applyLayerRoles(
      roleMap: Map<string, LayerRole>,
    ): Promise<
      | { ok: true; extracted: number; collapsed: number }
      | { ok: false; conflicts: LayerConflict[] }
    > {
      // ... existing dry-run + Q25 check unchanged ...

      try {
        const result = await applyLayerRolesApi(this.procedure!.id, { roles: resolvedRoles }, this.revision)
        await this.reload()
        this.layerMode = false
        return {
          ok: true,
          extracted: Object.keys(result.extracted_titles ?? {}).length,
          collapsed: Object.keys(result.collapsed_chapters ?? {}).length,
        }
      } catch (e: unknown) {
        // ... existing 400 SIBLING_TYPE_CONFLICT handling unchanged ...
      }
    },
```

Note: re-read the existing function carefully and only change the return shape — leave the Q25-conflict handling and other logic alone.

- [ ] **Step 3: Type-check**

Run:
```bash
cd frontend && npx vue-tsc --noEmit 2>&1 | head -30
```

Expected: callers that destructured `{ ok }` continue to work; if any caller pattern-matched on the exact prior shape, fix.

- [ ] **Step 4: Update store spec to match new return type**

In `frontend/tests/unit/store/procedureEditor.applyLayerRoles.spec.ts`, the "happy path" test asserts `result.ok === true`. Add assertions for the new fields:

Find the test ` it('happy path → 调用 applyLayerRolesApi 一次并 reload', ...)` and after the existing `expect(result.ok).toBe(true)` block, add:

```typescript
    if (result.ok) {
      expect(result.extracted).toBe(0)
      expect(result.collapsed).toBe(0)
    }
```

And add a new test for the counts:

```typescript
  it('result 含 extracted + collapsed 计数', async () => {
    const { applyLayerRolesApi } = await import('@/api/procedures')
    ;(applyLayerRolesApi as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      chapter_map: { s1: 'new-ch-1' },
      revision: 2,
      extracted_titles: { s1: '提取的标题' },
      collapsed_chapters: { 'ch-a': 'child-1' },
    })
    const store = useProcedureEditorStore()
    store.procedure = baseProc
    store.chapters = [
      { id: 'A', parent_id: null, title: 'A', skip_numbering: false, mark_status: 'unmarked', sort_order: 0 } as never,
    ]
    store.steps = [
      { id: 's1', chapter_id: 'A', kind: 'content', title: '', content: '', input_schema: {} as never, attachment_marks: [], skip_numbering: false, sort_order: 0 } as never,
    ]
    vi.spyOn(store, 'ensureSaved').mockResolvedValue({})
    vi.spyOn(store, 'reload').mockResolvedValue()
    const result = await store.applyLayerRoles(new Map([['A', 'chapter_1'], ['s1', 'chapter_2']]))
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.extracted).toBe(1)
      expect(result.collapsed).toBe(1)
    }
  })
```

- [ ] **Step 5: Run store spec**

Run:
```bash
cd frontend && npm run test -- --run tests/unit/store/procedureEditor.applyLayerRoles.spec.ts 2>&1 | tail -10
```

Expected: 4 passed (3 prior + 1 new).

- [ ] **Step 6: Commit**

```bash
cd /Users/yuming/Desktop/claude\ projects/HP_smart\ sop/SmartSOP
git add frontend/src/types/node.ts frontend/src/store/procedureEditor.ts frontend/tests/unit/store/procedureEditor.applyLayerRoles.spec.ts
git commit -m "$(cat <<'EOF'
feat(layer-apply): surface extracted/collapsed counts via store action result

LayerApplyResult schema gains optional extracted_titles +
collapsed_chapters maps; store applyLayerRoles re-emits counts on
{ok: true} so the calling view can show a toast.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Frontend — ChapterTreePanel toast + ContentDetailPanel placeholder cleanup

**Files:**
- Modify `frontend/src/components/editor/ChapterTreePanel.vue` (around line 389)
- Modify `frontend/src/components/editor/ContentDetailPanel.vue` (placeholder string)

- [ ] **Step 1: Update apply-handler in ChapterTreePanel**

Find the existing call around line 389:
```bash
sed -n '385,401p' frontend/src/components/editor/ChapterTreePanel.vue
```

Replace the existing `try { const res = await store.applyLayerRoles(...); if (!res.ok) {...} else { layerConflicts.value = [] } }` with:

```typescript
  try {
    const res = await store.applyLayerRoles(layerRoleMap.value)
    if (!res.ok) {
      layerConflicts.value = res.conflicts
      ElMessage.warning(`存在 ${res.conflicts.length} 处 §Q25 冲突，请先解决再应用`)
    } else {
      layerConflicts.value = []
      const parts: string[] = []
      if (res.extracted > 0) parts.push(`已为 ${res.extracted} 个无标题章节自动提取标题`)
      if (res.collapsed > 0) parts.push(`已合并 ${res.collapsed} 个章节为内容块`)
      if (parts.length > 0) ElMessage.success(parts.join('；'))
    }
  } catch {
    ElMessage.error('应用层级失败，状态已与后端重新同步')
    await store.reload()
  }
```

- [ ] **Step 2: Update ContentDetailPanel placeholder**

Find the title input placeholder:
```bash
grep -n "内容块标题" frontend/src/components/editor/ContentDetailPanel.vue
```

Change:
```diff
- placeholder="内容块标题（可选——填了之后才能在层级标定里升为章节）"
+ placeholder="内容块标题（可选）"
```

- [ ] **Step 3: Type-check + lint**

Run:
```bash
cd frontend && npx vue-tsc --noEmit 2>&1 | head -10
cd frontend && npm run lint 2>&1 | tail -10
```

Expected: no errors.

- [ ] **Step 4: Run all frontend tests**

Run:
```bash
cd frontend && npm run test -- --run 2>&1 | tail -5
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/yuming/Desktop/claude\ projects/HP_smart\ sop/SmartSOP
git add frontend/src/components/editor/ChapterTreePanel.vue frontend/src/components/editor/ContentDetailPanel.vue
git commit -m "$(cat <<'EOF'
feat(layer-apply): show extract/collapse toast + cleanup ContentDetailPanel placeholder

ChapterTreePanel reads the new counts from store.applyLayerRoles and
shows ElMessage.success when either fires (count format per spec §4.2).

ContentDetailPanel title placeholder drops the misleading "填了之后
才能在层级标定里升为章节" caveat — that was never strictly true (empty
title rows could always promote, just fell back to 未命名章节) and is
even less true now with auto-extract.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Full backend + frontend verification + manual dev verify handoff

**Files:** None (verification + memory)

- [ ] **Step 1: Backend full unit test pass**

Run:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit -q 2>&1 | tail -5
```

Expected: 450+ passed (target depends on baseline + 20 new tests).

- [ ] **Step 2: Frontend full unit test pass + lint + typecheck**

Run:
```bash
cd frontend && npm run test -- --run 2>&1 | tail -5
cd frontend && npx vue-tsc --noEmit 2>&1 | head -10
cd frontend && npm run lint 2>&1 | tail -10
```

Expected: all green.

- [ ] **Step 3: Confirm running uvicorn picked up new endpoint behavior**

If the user's local dev stack is running (`lsof -nP -iTCP:8000,5173 -sTCP:LISTEN`), uvicorn `--reload` should have picked up the layer_apply_service changes. Quick smoke:

```bash
# Backend route still 405 on GET, 400 on bad POST — same as before, confirms server alive on new code
curl -s -o /dev/null -w "GET: %{http_code}\nPOST(bad): %{http_code}\n" \
  -X GET http://127.0.0.1:8000/api/v1/procedures/x/apply-layer-roles
```

Expected: `GET: 405`. Manual UI verification of the new auto-extract / flatten behavior is a USER-side step (we can't easily seed the screenshot scenario from the orchestrator).

Document the handoff in the final commit message:

- [ ] **Step 4: Manual verify handoff note (user-facing)**

This task does NOT require code changes. The implementer should report:

> "Implementation complete and committed. Manual UI smoke recommended:
> 1. Open `http://localhost:5173/procedures/library`, pick or create a procedure with a content row that has empty title + body like '<p>3.1 短句</p>'.
> 2. Enter 层级标定, mark it 二级, click 应用层级.
> 3. Verify: new chapter title = '3.1 短句', no child content step, toast says '已为 1 个无标题章节自动提取标题'.
> 4. Mark the new chapter 正文, click 应用层级.
> 5. Verify: chapter becomes a content row with body='<p>3.1 短句</p>', toast counts include collapse if applicable."

- [ ] **Step 5: Update memory — note round-trip 2 non-invariant decision**

The user maintains a memory directory at `~/.claude/projects/-Users-yuming-Desktop-claude-projects-HP-smart-sop-SmartSOP/memory/`. Write a new feedback memory documenting the round-trip 2 design call:

Create `~/.claude/projects/-Users-yuming-Desktop-claude-projects-HP-smart-sop-SmartSOP/memory/content-chapter-roundtrip-non-invariant.md`:

```markdown
---
name: content-chapter-roundtrip-non-invariant
description: "content↔chapter 双向桥接:auto-extract 路径 round-trip 严格成立,title+body 路径透明放弃 round-trip 走 editorial flatten"
metadata:
  node_type: memory
  type: project
---

`docs/superpowers/specs/2026-05-28-content-chapter-roundtrip-design.md` 设计:
- **Round-trip 1**(auto-extract 路径): `content(title="", body="<p>X≤50 纯文本</p>")` ↔ `chapter(title="X", 无子)` 严格成立
- **Round-trip 2**(title+body 路径): `content(title="Y", body=B)` → promote → `chapter("Y", child(B))` → demote 不回到起点, 而是 `content(title="", body="<p>Y</p>"+B)`

**Why:** 用户的 demote 真实意图是 editorial flatten("拉平这一级"),而不是 round-trip 分离 title/body。spec §1.2 显式记录这是设计决策,不是 bug。

**How to apply:**
- 看到 demote 路径上 title→body 的行为想"修复"为 title→title 之前,先读 `test_roundtrip_2_explicitly_breaks` 的负例断言(`backend/tests/unit/services/test_layer_apply_service.py`),改了它就挂
- 如果业务确实需要 round-trip 2 严格,得改 spec + 加新行为开关,不是改实现

相关: [[layer-overlay-q25-dryrun-gap]] (auto-nest 上线后被 SUPERSEDED)
```

Update `~/.claude/projects/-Users-yuming-Desktop-claude-projects-HP-smart-sop-SmartSOP/memory/MEMORY.md` index to include this new file (add one line under existing entries, keep ≤150 chars per spec).

- [ ] **Step 6: No further commits required (memory is outside repo)**

```bash
git log --oneline d52234b..HEAD
```

Expected: 9 commits, one per major task (1, 2, 3, 4, 5, 6, 7, 8, 9). Push only with user confirmation.

---

## Self-Review Checklist (run before declaring done)

- [ ] Spec §2.1 触发条件 4 条 — covered by Task 2 (8 unit tests cover each condition).
- [ ] Spec §2.2 helper + Phase A integration — Task 2 + Task 3.
- [ ] Spec §2.3 边界 7 个 — covered across Task 2 helper tests + Task 3 integration tests.
- [ ] Spec §3.1 demote flatten + 1-mirror lift — Task 5.
- [ ] Spec §3.2 _validate_chapter_children_for_content upgrade — Task 4.
- [ ] Spec §3.3 边界 6 个 — Task 5 covers via tests + Phase C code paths.
- [ ] Spec §4.1 effectiveRole 放宽 — Task 7.
- [ ] Spec §4.2 toast 文案规则 — Task 9.
- [ ] Spec §4.3 类型 + placeholder — Task 8 + Task 9.
- [ ] Spec §5.1 后端 19 测试 — Tasks 2, 3, 5, 6 (count: 8 extract helper + 2 promote + 6 demote + 3 invariant = 19).
- [ ] Spec §5.2 前端测试 — Task 7 (effectiveRole) + Task 8 (store spec).
- [ ] Spec §6 风险 — all mitigations encoded in code (try/except in helper, predicated validator with backstop, length 50 as code constant).
- [ ] Spec §7 acceptance 5 — verifiable end-to-end after Task 10 manual smoke.

If anything above isn't covered, add a task before declaring done.
