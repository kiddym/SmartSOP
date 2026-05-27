"""conversion_service 单测（决策 §五 Q1-Q12 / §19 / 错误码 §二十三）。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.models.procedure import Procedure
from app.services import conversion_service, step_service
from tests.conftest import Factory

META = RequestMeta(ip_address="203.0.113.11", user_agent="pytest", request_id="r-cv")


def _proc(factory: Factory) -> Procedure:
    leaf = factory.folder(name="叶子", prefix="QC", full_path="叶子")
    factory.sequence(leaf.id)
    return factory.procedure(leaf.id)


# --------------------------------------------------------------------------- #
# 顶层块拆分
# --------------------------------------------------------------------------- #
def test_split_top_level_blocks() -> None:
    blocks = conversion_service.split_top_level_blocks(
        "<p>第一段</p><ul><li>a</li><li>b</li></ul><table><tr><td>x</td></tr></table>"
    )
    assert len(blocks) == 3
    assert blocks[0] == "<p>第一段</p>"
    assert blocks[1].startswith("<ul>")
    assert blocks[2].startswith("<table>")


def test_split_empty_returns_single_block() -> None:
    assert conversion_service.split_top_level_blocks("") == [""]


def test_split_preserves_void_tags_no_data_loss() -> None:
    # 评审 C1：<img> 等空元素不得吞掉其后顶层块
    blocks = conversion_service.split_top_level_blocks('<p>说明</p><img src="/a.png"><p>结尾</p>')
    assert blocks == ["<p>说明</p>", '<img src="/a.png">', "<p>结尾</p>"]


def test_split_void_tag_inside_block_keeps_single_block() -> None:
    blocks = conversion_service.split_top_level_blocks("<p>a<br>b</p><p>c</p>")
    assert blocks == ["<p>a<br>b</p>", "<p>c</p>"]


def test_split_loose_top_level_entity_preserved() -> None:
    # 评审 H1：顶层游离文本中的实体不丢、不误拆
    blocks = conversion_service.split_top_level_blocks("题注 &amp; 更多")
    assert blocks == ["题注 &amp; 更多"]


# --------------------------------------------------------------------------- #
# chapter → step
# --------------------------------------------------------------------------- #
def test_convert_chapter_to_step(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = factory.chapter(proc.id, title="单章")
    result = conversion_service.convert_to_step(db, ch.id, META)
    assert result.deleted == [ch.id]
    assert len(result.created) == 1
    db.refresh(ch)
    assert ch.is_active is False
    step = step_service.get_step(db, result.created[0])
    assert step.title == "单章"
    assert step.content == ""
    assert step.kind == "step"
    assert step.code == "1"  # 根级 step


def test_convert_chapter_with_children_rejected(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    parent = factory.chapter(proc.id, title="父")
    factory.chapter(proc.id, title="子", parent_id=parent.id, level=2)
    with pytest.raises(HTTPException) as exc:
        conversion_service.convert_to_step(db, parent.id, META)
    assert exc.value.detail["code"] == "CHAPTER_HAS_CHILDREN"


def test_convert_chapter_to_step_sibling_conflict(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    a = factory.chapter(proc.id, title="A")
    factory.chapter(proc.id, title="B")  # 同级仍有章节
    with pytest.raises(HTTPException) as exc:
        conversion_service.convert_to_step(db, a.id, META)
    assert exc.value.detail["code"] == "SIBLING_TYPE_CONFLICT"


def test_convert_root_to_step_requires_root(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    parent = factory.chapter(proc.id, title="父")
    child = factory.chapter(proc.id, title="子", parent_id=parent.id, level=2)
    with pytest.raises(HTTPException) as exc:
        conversion_service.convert_root_to_step(db, child.id, META)
    assert exc.value.detail["code"] == "SIBLING_TYPE_CONFLICT"


# --------------------------------------------------------------------------- #
# step → chapter
# --------------------------------------------------------------------------- #
def test_convert_step_to_chapter_with_body(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    parent = factory.chapter(proc.id, title="父")
    step = factory.step(proc.id, chapter_id=parent.id, title="步骤", content="<p>正文</p>")
    result = conversion_service.convert_to_chapter(db, step.id, META)
    assert result.deleted == [step.id]
    assert len(result.created) == 2  # 新 chapter + kind='content' 内容块步骤
    # 第一个：新建章节
    new_steps = step_service.list_steps(db, procedure_id=proc.id, chapter_id=result.created[0])
    assert len(new_steps) == 1
    content_step = new_steps[0]
    assert content_step.id == result.created[1]
    assert content_step.kind == "content"
    assert "正文" in content_step.content


def test_convert_step_to_chapter_no_body_creates_only_chapter(
    db: Session, factory: Factory
) -> None:
    proc = _proc(factory)
    parent = factory.chapter(proc.id, title="父")
    step = factory.step(proc.id, chapter_id=parent.id, title="空步骤", content="")
    result = conversion_service.convert_to_chapter(db, step.id, META)
    assert result.deleted == [step.id]
    assert len(result.created) == 1  # 正文为空，只建章节，不建内容块步骤


def test_convert_step_to_chapter_sibling_conflict(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    parent = factory.chapter(proc.id, title="父")
    s1 = factory.step(proc.id, chapter_id=parent.id)
    factory.step(proc.id, chapter_id=parent.id)  # 同级另有 step
    with pytest.raises(HTTPException) as exc:
        conversion_service.convert_to_chapter(db, s1.id, META)
    assert exc.value.detail["code"] == "SIBLING_TYPE_CONFLICT"


def test_convert_content_step_to_chapter_rejected(db: Session, factory: Factory) -> None:
    """content 块语义上是"无标题正文"，不应能被提升为章节（无 heading）。"""
    proc = _proc(factory)
    parent = factory.chapter(proc.id, title="父")
    content_step = factory.step(
        proc.id, chapter_id=parent.id, kind="content", title="", content="<p>说明</p>"
    )
    with pytest.raises(HTTPException) as exc:
        conversion_service.convert_to_chapter(db, content_step.id, META)
    assert exc.value.detail["code"] == "CONTENT_BLOCK_NOT_CONVERTIBLE"


def test_convert_step_to_chapter_depth_exceeded(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    l1 = factory.chapter(proc.id, title="1", level=1)
    l2 = factory.chapter(proc.id, title="2", parent_id=l1.id, level=2)
    l3 = factory.chapter(proc.id, title="3", parent_id=l2.id, level=3)
    step = factory.step(proc.id, chapter_id=l3.id)
    with pytest.raises(HTTPException) as exc:
        conversion_service.convert_to_chapter(db, step.id, META)
    assert exc.value.detail["code"] == "CHAPTER_DEPTH_EXCEEDED"


# --------------------------------------------------------------------------- #
# chapter → content（融合式标题降级）
# --------------------------------------------------------------------------- #
def test_convert_to_content_happy(db: Session, factory: Factory) -> None:
    """无 children 的唯一 chapter → 转换成 content step；chapter 软删；title 搬运到 step.content。"""
    proc = _proc(factory)
    ch = factory.chapter(proc.id, title="3.1质量部是记录的归口管理部门，负责...")

    result = conversion_service.convert_to_content(db, ch.id, META)
    db.commit()

    db.refresh(ch)
    assert ch.is_active is False
    assert result.deleted == [ch.id]
    assert len(result.created) == 1
    new_step = step_service.get_step(db, result.created[0])
    assert new_step.kind == "content"
    assert new_step.title == ""
    assert new_step.content == "3.1质量部是记录的归口管理部门，负责..."
    assert new_step.chapter_id == ch.parent_id  # None for root


def test_convert_to_content_has_child_chapter(db: Session, factory: Factory) -> None:
    """有子 chapter → CHAPTER_HAS_CHILDREN。"""
    proc = _proc(factory)
    parent = factory.chapter(proc.id, title="父章节")
    factory.chapter(proc.id, parent_id=parent.id, title="子章节")

    with pytest.raises(HTTPException) as exc:
        conversion_service.convert_to_content(db, parent.id, META)
    assert exc.value.detail["code"] == "CHAPTER_HAS_CHILDREN"


def test_convert_to_content_has_child_step(db: Session, factory: Factory) -> None:
    """有子 step → CHAPTER_HAS_CHILDREN。"""
    proc = _proc(factory)
    ch = factory.chapter(proc.id, title="章节")
    factory.step(proc.id, chapter_id=ch.id, kind="step", title="子步骤")

    with pytest.raises(HTTPException) as exc:
        conversion_service.convert_to_content(db, ch.id, META)
    assert exc.value.detail["code"] == "CHAPTER_HAS_CHILDREN"


def test_convert_to_content_sibling_chapter_conflict(db: Session, factory: Factory) -> None:
    """同级仍有 chapter → SIBLING_TYPE_CONFLICT（Q25 互斥）。"""
    proc = _proc(factory)
    ch1 = factory.chapter(proc.id, title="章节A")
    factory.chapter(proc.id, title="章节B")  # 同级 sibling

    with pytest.raises(HTTPException) as exc:
        conversion_service.convert_to_content(db, ch1.id, META)
    assert exc.value.detail["code"] == "SIBLING_TYPE_CONFLICT"


def test_convert_to_content_readonly_procedure(db: Session, factory: Factory) -> None:
    """非 DRAFT 程序 → PROCEDURE_READONLY。"""
    proc = _proc(factory)
    proc.status = "RELEASED"
    db.flush()
    ch = factory.chapter(proc.id, title="章节")

    with pytest.raises(HTTPException) as exc:
        conversion_service.convert_to_content(db, ch.id, META)
    assert exc.value.detail["code"] == "PROCEDURE_READONLY"


def test_convert_to_content_bumps_revision(db: Session, factory: Factory) -> None:
    """转换后 procedure revision bump + numbering recompute。"""
    proc = _proc(factory)
    ch = factory.chapter(proc.id, title="章节")
    initial_revision = proc.revision

    conversion_service.convert_to_content(db, ch.id, META)
    db.commit()
    db.refresh(proc)

    assert proc.revision > initial_revision


# --------------------------------------------------------------------------- #
# 拆 heading + content（C）
# --------------------------------------------------------------------------- #
def test_split_title_content_happy(db: Session, factory: Factory) -> None:
    """cursor=15 → title 截短到 15；新 content step kind=content content=tail。"""
    proc = _proc(factory)
    full_title = "3.1质量部是记录的归口管理部门，负责组织全公司记录表格的编制和校审。"
    ch = factory.chapter(proc.id, title=full_title)
    cursor = 15  # "3.1质量部是记录的归口管理部" 之后

    result = conversion_service.split_title_content(db, ch.id, cursor, META)
    db.commit()
    db.refresh(ch)

    assert ch.title == full_title[:cursor]
    assert result.deleted == []
    assert len(result.created) == 1
    new_step = step_service.get_step(db, result.created[0])
    assert new_step.kind == "content"
    assert new_step.content == full_title[cursor:]
    assert new_step.chapter_id == ch.id
    assert new_step.sort_order == 0


def test_split_title_content_cursor_zero(db: Session, factory: Factory) -> None:
    """cursor=0 → INVALID_CURSOR。"""
    proc = _proc(factory)
    ch = factory.chapter(proc.id, title="章节标题")

    with pytest.raises(HTTPException) as exc:
        conversion_service.split_title_content(db, ch.id, 0, META)
    assert exc.value.detail["code"] == "INVALID_CURSOR"


def test_split_title_content_cursor_at_end(db: Session, factory: Factory) -> None:
    """cursor=len(title) → INVALID_CURSOR。"""
    proc = _proc(factory)
    title = "章节标题"
    ch = factory.chapter(proc.id, title=title)

    with pytest.raises(HTTPException) as exc:
        conversion_service.split_title_content(db, ch.id, len(title), META)
    assert exc.value.detail["code"] == "INVALID_CURSOR"


def test_split_title_content_empty_tail(db: Session, factory: Factory) -> None:
    """拆点之后是全空白 → EMPTY_CONTENT。"""
    proc = _proc(factory)
    ch = factory.chapter(proc.id, title="章节标题    ")  # 尾部 4 空格
    cursor = 4  # "章节标题" 之后 = "    "（全空白）

    with pytest.raises(HTTPException) as exc:
        conversion_service.split_title_content(db, ch.id, cursor, META)
    assert exc.value.detail["code"] == "EMPTY_CONTENT"


def test_split_title_content_existing_steps_reorder(db: Session, factory: Factory) -> None:
    """chapter 已有 N 个 step children → 新 content step.sort_order=0，其他全部 +1。"""
    proc = _proc(factory)
    ch = factory.chapter(proc.id, title="章节标题ABCDE")
    s1 = factory.step(proc.id, chapter_id=ch.id, kind="step", title="原step1", sort_order=0)
    s2 = factory.step(proc.id, chapter_id=ch.id, kind="step", title="原step2", sort_order=1)

    result = conversion_service.split_title_content(db, ch.id, 4, META)
    db.commit()
    db.refresh(s1)
    db.refresh(s2)

    new_step = step_service.get_step(db, result.created[0])
    assert new_step.sort_order == 0
    assert s1.sort_order == 1
    assert s2.sort_order == 2


def test_split_title_content_with_child_chapter(db: Session, factory: Factory) -> None:
    """chapter 有子 chapter → 不报错，子 chapter 不受影响。"""
    proc = _proc(factory)
    parent = factory.chapter(proc.id, title="父章节ABCDE")
    child = factory.chapter(proc.id, parent_id=parent.id, title="子章节")

    result = conversion_service.split_title_content(db, parent.id, 4, META)
    db.commit()
    db.refresh(child)

    assert child.is_active is True
    assert child.parent_id == parent.id  # 不受影响
    assert len(result.created) == 1


def test_split_title_content_readonly_procedure(db: Session, factory: Factory) -> None:
    """非 DRAFT 程序 → PROCEDURE_READONLY。"""
    proc = _proc(factory)
    proc.status = "RELEASED"
    db.flush()
    ch = factory.chapter(proc.id, title="章节标题")

    with pytest.raises(HTTPException) as exc:
        conversion_service.split_title_content(db, ch.id, 2, META)
    assert exc.value.detail["code"] == "PROCEDURE_READONLY"
