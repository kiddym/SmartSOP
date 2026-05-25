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


def test_convert_step_to_chapter_depth_exceeded(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    l1 = factory.chapter(proc.id, title="1", level=1)
    l2 = factory.chapter(proc.id, title="2", parent_id=l1.id, level=2)
    l3 = factory.chapter(proc.id, title="3", parent_id=l2.id, level=3)
    step = factory.step(proc.id, chapter_id=l3.id)
    with pytest.raises(HTTPException) as exc:
        conversion_service.convert_to_chapter(db, step.id, META)
    assert exc.value.detail["code"] == "CHAPTER_DEPTH_EXCEEDED"
