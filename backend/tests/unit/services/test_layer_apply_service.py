"""layer_apply_service 单测(spec §5.1)。"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.models.procedure import Procedure
from app.services import layer_apply_service
from tests.conftest import Factory

META = RequestMeta(ip_address="203.0.113.11", user_agent="pytest", request_id="r-la")


def _proc(factory: Factory) -> Procedure:
    leaf = factory.folder(name="叶子", prefix="QC", full_path="叶子")
    factory.sequence(leaf.id)
    return factory.procedure(leaf.id)


def test_q25_conflict_when_promoted_leaves_remaining_siblings(
    db: Session, factory: Factory
) -> None:
    """父 P 下两个 step 兄弟,只升一个 → 末态混合 → 400 SIBLING_TYPE_CONFLICT。"""
    proc = _proc(factory)
    ch = factory.chapter(proc.id, title="A", level=1)
    # s2 在文档序中先于 s1:s2 保持叶子,s1 升章节 → 二者末态同属 ch → 混合冲突
    s2 = factory.step(proc.id, chapter_id=ch.id, kind="content", title="s2", sort_order=0)
    s1 = factory.step(proc.id, chapter_id=ch.id, kind="content", title="s1", sort_order=1)

    with pytest.raises(HTTPException) as ex:
        layer_apply_service.apply_layer_roles(
            db, proc.id, roles={s1.id: "chapter_2"}, expected_revision=proc.revision, meta=META
        )
    assert ex.value.status_code == 400
    assert ex.value.detail["code"] == "SIBLING_TYPE_CONFLICT"
    # DB 未变
    db.refresh(s1)
    db.refresh(s2)
    assert s1.is_active and s2.is_active


def test_phase_a_single_leaf_promoted_no_siblings(db: Session, factory: Factory) -> None:
    """父 P 下唯一 leaf 升 L2 → 创建新 L2 chapter,原 leaf 软删,body 转 child content。"""
    from app.models.chapter import ProcedureChapter
    from app.models.step import ProcedureStep

    proc = _proc(factory)
    ch = factory.chapter(proc.id, title="A", level=1)
    s1 = factory.step(
        proc.id, chapter_id=ch.id, kind="content", title="崔宇明", content="<p>负责...</p>", sort_order=0
    )

    result = layer_apply_service.apply_layer_roles(
        db, proc.id, roles={s1.id: "chapter_2"}, expected_revision=proc.revision, meta=META
    )

    # 新章节存在
    assert len(result["chapter_map"]) == 1
    new_ch_id = result["chapter_map"][s1.id]
    db.refresh(s1)
    assert not s1.is_active  # 原 leaf 软删

    new_ch = db.get(ProcedureChapter, new_ch_id)
    assert new_ch is not None
    assert new_ch.title == "崔宇明"
    assert new_ch.parent_id == ch.id
    assert new_ch.level == 2

    # body 转为子 content step
    children = db.execute(
        select(ProcedureStep).where(ProcedureStep.chapter_id == new_ch_id, ProcedureStep.is_active.is_(True))
    ).scalars().all()
    assert len(children) == 1
    assert children[0].kind == "content"
    assert children[0].content == "<p>负责...</p>"


def test_phase_bc_reorder_and_to_content(db: Session, factory: Factory) -> None:
    """A(L1) + B(L1) 调整为 A(L1) + B(content under A)。"""
    from app.models.step import ProcedureStep

    proc = _proc(factory)
    a = factory.chapter(proc.id, title="A", level=1, sort_order=0)
    b = factory.chapter(proc.id, title="B", level=1, sort_order=1)

    layer_apply_service.apply_layer_roles(
        db,
        proc.id,
        roles={a.id: "chapter_1", b.id: "content"},
        expected_revision=proc.revision,
        meta=META,
    )

    db.refresh(a)
    db.refresh(b)
    assert a.is_active and a.parent_id is None and a.level == 1
    assert not b.is_active  # chapter B 被软删
    # A 下有一个 content step,title 为空,body = "<p>B</p>"
    children = db.execute(
        select(ProcedureStep).where(ProcedureStep.chapter_id == a.id, ProcedureStep.is_active.is_(True))
    ).scalars().all()
    assert len(children) == 1
    assert children[0].kind == "content"
    assert children[0].content == "<p>B</p>"


def test_phase_c_chapter_has_children_rejects(db: Session, factory: Factory) -> None:
    """有子 chapter 的章节不可降为 content → 400 CHAPTER_HAS_CHILDREN。"""
    proc = _proc(factory)
    a = factory.chapter(proc.id, title="A", level=1, sort_order=0)
    factory.chapter(proc.id, title="A.1", parent_id=a.id, level=2, sort_order=0)

    with pytest.raises(HTTPException) as ex:
        layer_apply_service.apply_layer_roles(
            db,
            proc.id,
            roles={a.id: "content"},
            expected_revision=proc.revision,
            meta=META,
        )
    assert ex.value.status_code == 400
    assert ex.value.detail["code"] == "CHAPTER_HAS_CHILDREN"


def test_screenshot_scenario_three_l2_promotions_with_adoption(
    db: Session, factory: Factory
) -> None:
    """截图场景:3.0 下三组(姓名 + 2 描述),三个姓名升 L2,各吃 2 个描述。"""
    from app.models.chapter import ProcedureChapter

    proc = _proc(factory)
    r = factory.chapter(proc.id, title="职责", level=1, sort_order=0)
    a = factory.step(proc.id, chapter_id=r.id, kind="content", title="崔宇明", sort_order=0)
    a1 = factory.step(proc.id, chapter_id=r.id, kind="content", content="<p>负责编制本程序</p>", sort_order=1)
    a2 = factory.step(proc.id, chapter_id=r.id, kind="content", content="<p>全面负责财务</p>", sort_order=2)
    b = factory.step(proc.id, chapter_id=r.id, kind="content", title="王覆宇", sort_order=3)
    b1 = factory.step(proc.id, chapter_id=r.id, kind="content", content="<p>架构设计</p>", sort_order=4)
    b2 = factory.step(proc.id, chapter_id=r.id, kind="content", content="<p>服务器部署</p>", sort_order=5)
    c = factory.step(proc.id, chapter_id=r.id, kind="content", title="于星河", sort_order=6)
    c1 = factory.step(proc.id, chapter_id=r.id, kind="content", content="<p>前端开发</p>", sort_order=7)
    c2 = factory.step(proc.id, chapter_id=r.id, kind="content", content="<p>开发流程</p>", sort_order=8)

    result = layer_apply_service.apply_layer_roles(
        db,
        proc.id,
        roles={a.id: "chapter_2", b.id: "chapter_2", c.id: "chapter_2"},
        expected_revision=proc.revision,
        meta=META,
    )

    new_a = result["chapter_map"][a.id]
    new_b = result["chapter_map"][b.id]
    new_c = result["chapter_map"][c.id]
    for nid, expected_title in [(new_a, "崔宇明"), (new_b, "王覆宇"), (new_c, "于星河")]:
        ch = db.get(ProcedureChapter, nid)
        assert ch is not None and ch.parent_id == r.id and ch.level == 2 and ch.title == expected_title

    db.refresh(a1); db.refresh(a2); db.refresh(b1); db.refresh(b2); db.refresh(c1); db.refresh(c2)
    assert a1.chapter_id == new_a and a2.chapter_id == new_a
    assert b1.chapter_id == new_b and b2.chapter_id == new_b
    assert c1.chapter_id == new_c and c2.chapter_id == new_c
    # 描述行的 sort_order 应该是 0, 1(在各自新章节下)
    assert sorted([a1.sort_order, a2.sort_order]) == [0, 1]


def test_l3_clamped_to_l1_when_no_l2_context(db: Session, factory: Factory) -> None:
    """根级叶子标 L3 → walk 夹到 L1。"""
    from app.models.chapter import ProcedureChapter

    proc = _proc(factory)
    s = factory.step(proc.id, chapter_id=None, kind="content", title="孤行", sort_order=0)
    result = layer_apply_service.apply_layer_roles(
        db, proc.id, roles={s.id: "chapter_3"}, expected_revision=proc.revision, meta=META
    )
    new_ch = db.get(ProcedureChapter, result["chapter_map"][s.id])
    assert new_ch.parent_id is None
    assert new_ch.level == 1


def test_l2_then_l3_nested_adoption(db: Session, factory: Factory) -> None:
    """L2 + L3,L3 成为 L2 的子章节,L3 的收养块(y1)在 L3 下,L2 之后的块(x1)在 L2 下。

    文档序: R > x(升L2) > y(升L3) > y1(leaf) > x1(leaf)
    walk 末态: y 挂在 x 下(L3),y1 挂在 y 下,x1 挂在 y 下(因为 l3=y 在 x1 前)。
    注:x1 在 y1 后,walk 时 l3=y,x1 → leaf-reparent(parent=y)。
    """
    from app.models.chapter import ProcedureChapter

    proc = _proc(factory)
    r = factory.chapter(proc.id, title="R", level=1)
    x = factory.step(proc.id, chapter_id=r.id, kind="content", title="X", sort_order=0)
    y = factory.step(proc.id, chapter_id=r.id, kind="content", title="Y", sort_order=1)
    y1 = factory.step(proc.id, chapter_id=r.id, kind="content", content="<p>y1</p>", sort_order=2)
    x1 = factory.step(proc.id, chapter_id=r.id, kind="content", content="<p>x1</p>", sort_order=3)

    result = layer_apply_service.apply_layer_roles(
        db,
        proc.id,
        roles={x.id: "chapter_2", y.id: "chapter_3"},
        expected_revision=proc.revision,
        meta=META,
    )
    new_x, new_y = result["chapter_map"][x.id], result["chapter_map"][y.id]
    assert db.get(ProcedureChapter, new_x).parent_id == r.id
    assert db.get(ProcedureChapter, new_x).level == 2
    assert db.get(ProcedureChapter, new_y).parent_id == new_x
    assert db.get(ProcedureChapter, new_y).level == 3
    # y1 and x1 both fall under y (l3) since they come after y in doc order
    db.refresh(y1); db.refresh(x1)
    assert y1.chapter_id == new_y
    assert x1.chapter_id == new_y


def test_depth_validator_rejects_level_4() -> None:
    """Walk 总是夹紧到 ≤3,所以 depth 校验是 defense-in-depth,直接构造 updates 测试。"""
    fake_updates = {
        "x": {"kind": "to-chapter", "parent_id": "y", "sort_order": 0, "level": 4}
    }
    with pytest.raises(HTTPException) as ex:
        layer_apply_service._validate_depth(fake_updates)
    assert ex.value.detail["code"] == "CHAPTER_DEPTH_EXCEEDED"


def test_optimistic_lock_conflict(db: Session, factory: Factory) -> None:
    """传递错误的 expected_revision → 409 VERSION_CONFLICT。"""
    proc = _proc(factory)
    with pytest.raises(HTTPException) as ex:
        layer_apply_service.apply_layer_roles(
            db, proc.id, roles={}, expected_revision=proc.revision + 1, meta=META
        )
    assert ex.value.status_code == 409


def test_empty_roles_noop(db: Session, factory: Factory) -> None:
    """空 roles 仍返回 chapter_map=空,不抛错。"""
    proc = _proc(factory)
    ch = factory.chapter(proc.id, title="A", level=1)
    factory.step(proc.id, chapter_id=ch.id, kind="content", title="x", sort_order=0)
    result = layer_apply_service.apply_layer_roles(
        db, proc.id, roles={}, expected_revision=proc.revision, meta=META
    )
    assert result["chapter_map"] == {}


def test_to_content_empty_title_produces_empty_body(db: Session, factory: Factory) -> None:
    """空标题章节降为 content → content="" 而非 "<p></p>"。"""
    from app.models.step import ProcedureStep

    proc = _proc(factory)
    a = factory.chapter(proc.id, title="A", level=1, sort_order=0)
    b = factory.chapter(proc.id, title="", level=1, sort_order=1)  # 空标题章节
    layer_apply_service.apply_layer_roles(
        db, proc.id, roles={a.id: "chapter_1", b.id: "content"}, expected_revision=proc.revision, meta=META
    )
    children = db.execute(
        select(ProcedureStep).where(ProcedureStep.chapter_id == a.id, ProcedureStep.is_active.is_(True))
    ).scalars().all()
    assert len(children) == 1
    assert children[0].content == ""  # 不是 "<p></p>"


def test_router_smoke(engine, factory: Factory) -> None:
    """通过 FastAPI TestClient 端到端跑一次 happy path,验证 If-Match + JSON body + 路由路径。

    注:不使用 conftest 的 `client` fixture,因为 `with TestClient(app)` 会触发 lifespan,
    后者直接调 `SessionLocal()` 连真实 DB(本地无 MySQL → MySQL 连接拒绝)。
    我们绕过 lifespan,直接覆盖 `get_db` dep。
    """
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session as _Session

    from app.deps import get_db
    from app.main import app

    leaf = factory.folder(name="叶子-router", prefix="QC", full_path="叶子-router")
    factory.sequence(leaf.id)
    proc = factory.procedure(leaf.id, code="QC-router")
    ch = factory.chapter(proc.id, title="A", level=1)
    s = factory.step(proc.id, chapter_id=ch.id, kind="content", title="X", sort_order=0)
    initial_revision = proc.revision

    def _override():
        with _Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = _override
    try:
        tc = TestClient(app)  # no `with` — skip lifespan
        resp = tc.post(
            f"/api/v1/procedures/{proc.id}/apply-layer-roles",
            json={"roles": {s.id: "chapter_2"}},
            headers={"If-Match": str(initial_revision)},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert s.id in body["chapter_map"]
    assert body["revision"] > initial_revision


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


# ---------------------------------------------------------------------------
# Round-trip invariants (spec §1.2)
# ---------------------------------------------------------------------------


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
    layer_apply_service.apply_layer_roles(
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
    """同一次 apply 内既触发 auto-extract 又触发 lift-child,两个 map 都非空。

    拓扑:
      sect_a (L1) → short_content (content, 空 title, 短纯文本 body) 升 L2  → extract
      sect_b (L1) → target_ch   (L2)  → content 降 → flatten           → collapse
    两个 parent 不同,避免 Q25 末态混合冲突。
    """
    proc = _proc(factory)

    # 第一组:sect_a 下 promote 一个空标题短 content → 触发 extract
    sect_a = factory.chapter(proc.id, title="A", level=1, sort_order=0)
    short_content = factory.step(
        proc.id, chapter_id=sect_a.id, kind="content", title="", content="<p>新二级</p>", sort_order=0
    )

    # 第二组:sect_b 下 demote 一个 1-mirror-child 章节 → 触发 collapse
    sect_b = factory.chapter(proc.id, title="B", level=1, sort_order=1)
    target_ch = factory.chapter(proc.id, title="Y", parent_id=sect_b.id, level=2, sort_order=0)
    mirror_child = factory.step(
        proc.id, chapter_id=target_ch.id, kind="content", title="", content="<p>B</p>", sort_order=0
    )

    result = layer_apply_service.apply_layer_roles(
        db,
        proc.id,
        roles={
            sect_a.id: "chapter_1",
            short_content.id: "chapter_2",
            sect_b.id: "chapter_1",
            target_ch.id: "content",
        },
        expected_revision=proc.revision,
        meta=META,
    )

    assert short_content.id in result["extracted_titles"]
    assert result["extracted_titles"][short_content.id] == "新二级"
    assert target_ch.id in result["collapsed_chapters"]
    assert result["collapsed_chapters"][target_ch.id] == mirror_child.id
