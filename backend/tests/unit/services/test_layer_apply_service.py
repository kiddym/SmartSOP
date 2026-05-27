"""layer_apply_service 单测(spec §5.1)。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
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
