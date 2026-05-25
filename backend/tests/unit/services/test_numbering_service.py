"""编号引擎单测（§47 / Q15 / Q27 / Q305-Q311）。

验证内部 code 递归（render-only 的 L1 `.0` 不入库）、skip 不计数+子树静默、
content 永远无号且不占位、step 子码最深 4 段、根级 step。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services import numbering_service
from tests.conftest import Factory


def _proc(factory: Factory) -> str:
    leaf = factory.folder(name="叶子", prefix="QC", full_path="叶子")
    factory.sequence(leaf.id)
    return factory.procedure(leaf.id).id


def test_l1_internal_code_has_no_dot_zero(db: Session, factory: Factory) -> None:
    pid = _proc(factory)
    a = factory.chapter(pid, title="目的", sort_order=0)
    b = factory.chapter(pid, title="范围", sort_order=1)
    numbering_service.recompute(db, pid)
    db.refresh(a)
    db.refresh(b)
    assert a.code == "1"  # 内部码无 .0，渲染层才追加
    assert b.code == "2"


def test_nested_chapters_recursive_code(db: Session, factory: Factory) -> None:
    pid = _proc(factory)
    l1 = factory.chapter(pid, title="一级", sort_order=0, level=1)
    l2 = factory.chapter(pid, title="二级", parent_id=l1.id, sort_order=0, level=2)
    l3 = factory.chapter(pid, title="三级", parent_id=l2.id, sort_order=0, level=3)
    numbering_service.recompute(db, pid)
    db.refresh(l1)
    db.refresh(l2)
    db.refresh(l3)
    assert (l1.code, l2.code, l3.code) == ("1", "1.1", "1.1.1")


def test_skip_chapter_not_counted_and_subtree_silent(db: Session, factory: Factory) -> None:
    pid = _proc(factory)
    pre = factory.chapter(pid, title="前言", sort_order=0, skip_numbering=True)
    pre_child = factory.chapter(pid, title="前言子", parent_id=pre.id, sort_order=0, level=2)
    purpose = factory.chapter(pid, title="目的", sort_order=1)
    scope = factory.chapter(pid, title="范围", sort_order=2)
    numbering_service.recompute(db, pid)
    for n in (pre, pre_child, purpose, scope):
        db.refresh(n)
    assert pre.code == ""  # skip 节点自身无号
    assert pre_child.code == ""  # 子树静默
    assert purpose.code == "1"  # 连续编号、不被 skip 占位（Q306）
    assert scope.code == "2"


def test_content_nodes_never_numbered_and_dont_consume(db: Session, factory: Factory) -> None:
    """内容块 step（kind='content'）无号且不占步骤序号位。"""
    pid = _proc(factory)
    ch = factory.chapter(pid, title="操作", sort_order=0)
    s1 = factory.step(pid, chapter_id=ch.id, title="第一步", sort_order=0)
    x = factory.step(pid, chapter_id=ch.id, content="<p>说明</p>", sort_order=1, kind="content")
    s2 = factory.step(pid, chapter_id=ch.id, title="第二步", sort_order=2)
    numbering_service.recompute(db, pid)
    for n in (s1, x, s2):
        db.refresh(n)
    assert s1.code == "1.1"
    assert x.code == ""   # content 块永远无号
    assert s2.code == "1.2"  # content 不占序号位


def test_step_code_is_parent_chapter_code_plus_seq(db: Session, factory: Factory) -> None:
    pid = _proc(factory)
    ch = factory.chapter(pid, title="操作", sort_order=0)
    s1 = factory.step(pid, chapter_id=ch.id, sort_order=0)
    s2 = factory.step(pid, chapter_id=ch.id, sort_order=1)
    numbering_service.recompute(db, pid)
    db.refresh(ch)
    db.refresh(s1)
    db.refresh(s2)
    assert ch.code == "1"
    assert s1.code == "1.1"
    assert s2.code == "1.2"


def test_step_skip_numbering_not_counted(db: Session, factory: Factory) -> None:
    pid = _proc(factory)
    ch = factory.chapter(pid, title="操作", sort_order=0)
    s1 = factory.step(pid, chapter_id=ch.id, sort_order=0, skip_numbering=True)
    s2 = factory.step(pid, chapter_id=ch.id, sort_order=1)
    numbering_service.recompute(db, pid)
    db.refresh(s1)
    db.refresh(s2)
    assert s1.code == ""
    assert s2.code == "1.1"  # skip 不占位


def test_step_under_l3_chapter_reaches_four_segments(db: Session, factory: Factory) -> None:
    pid = _proc(factory)
    l1 = factory.chapter(pid, title="一", sort_order=0, level=1)
    l2 = factory.chapter(pid, title="二", parent_id=l1.id, sort_order=0, level=2)
    l3 = factory.chapter(pid, title="三", parent_id=l2.id, sort_order=0, level=3)
    s = factory.step(pid, chapter_id=l3.id, sort_order=0)
    numbering_service.recompute(db, pid)
    db.refresh(s)
    assert s.code == "1.1.1.1"  # Q308 最深 4 段


def test_root_level_steps_have_bare_sequence(db: Session, factory: Factory) -> None:
    pid = _proc(factory)
    s1 = factory.step(pid, chapter_id=None, sort_order=0)
    s2 = factory.step(pid, chapter_id=None, sort_order=1)
    numbering_service.recompute(db, pid)
    db.refresh(s1)
    db.refresh(s2)
    assert s1.code == "1"
    assert s2.code == "2"


def test_steps_under_skip_chapter_are_silent(db: Session, factory: Factory) -> None:
    pid = _proc(factory)
    ch = factory.chapter(pid, title="附录", sort_order=0, skip_numbering=True)
    s = factory.step(pid, chapter_id=ch.id, sort_order=0)
    numbering_service.recompute(db, pid)
    db.refresh(s)
    assert s.code == ""


def test_content_step_unnumbered_and_not_counted(db: Session, factory: Factory) -> None:
    pid = _proc(factory)
    ch = factory.chapter(pid, title="操作", sort_order=0, level=1)
    s1 = factory.step(pid, chapter_id=ch.id, title="第一步", sort_order=0)
    c = factory.step(pid, chapter_id=ch.id, content="<p>说明</p>", sort_order=1, kind="content")
    s2 = factory.step(pid, chapter_id=ch.id, title="第二步", sort_order=2)
    numbering_service.recompute(db, pid)
    for s in (s1, c, s2):
        db.refresh(s)
    assert s1.code == "1.1"
    assert c.code == ""        # 内容块不编号
    assert s2.code == "1.2"    # 内容块不占序号位
