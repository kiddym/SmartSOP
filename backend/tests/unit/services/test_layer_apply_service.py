"""layer_apply_service 单测(spec §5.1)。"""

from __future__ import annotations

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
