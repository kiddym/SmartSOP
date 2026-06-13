"""动态标题字典-隐式学习闭环单测（方案 M3）：投票阈值 / 归因粒度 / 手动优先 / 钩子接线。"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.heading_learning_event import HeadingLearningEvent
from app.models.node import ProcedureNode
from app.schemas.heading_rule import HeadingRuleCreate
from app.services import heading_learning_service as svc
from app.services import heading_rule_service, node_service

pytestmark = pytest.mark.usefixtures("_tenant_ctx")


def _mk(
    db: Session, proc: str, style: str, level: int | None, mark: str = "unmarked"
) -> ProcedureNode:
    n = ProcedureNode(
        procedure_id=proc,
        sort_order=1000,
        heading_level=level,
        source_style_name=style,
        mark_status=mark,
        revision=1,
    )
    db.add(n)
    db.flush()
    return n


def test_three_docs_consistent_relevel_activates(db: Session) -> None:
    for i in range(3):
        n = _mk(db, f"p{i}", "小标题", 2)  # 终态 L2
        svc.observe_node_edit(db, n, old_level=1, old_mark="unmarked")  # 原 L1 → relevel 事件
    rule = svc.reaggregate(db, "小标题")
    assert rule is not None
    assert rule.source == "learned"
    assert rule.status == "active"
    assert rule.level == 2
    assert rule.evidence_count == 3
    assert rule.agreement == 1.0
    # 生效后即进入解析注入
    assert heading_rule_service.active_style_overrides(db) == {"小标题": 2}


def test_below_threshold_is_candidate(db: Session) -> None:
    for i in range(2):  # 仅 2 文档 < K_DOCS(3)
        n = _mk(db, f"p{i}", "小标题", 2)
        svc.observe_node_edit(db, n, old_level=1, old_mark="unmarked")
    rule = svc.reaggregate(db, "小标题")
    assert rule is not None and rule.status == "candidate"
    assert rule.evidence_count == 2
    # candidate 不注入解析
    assert heading_rule_service.active_style_overrides(db) == {}


def test_conflict_stays_candidate(db: Session) -> None:
    for i, lvl in enumerate([2, 2, 3]):  # 一致率 2/3=0.67 < 0.8
        n = _mk(db, f"p{i}", "小标题", lvl)
        svc.observe_node_edit(db, n, old_level=1, old_mark="unmarked")
    rule = svc.reaggregate(db, "小标题")
    assert rule is not None and rule.status == "candidate"
    assert rule.evidence_count == 3


def test_paragraph_exception_does_not_flip(db: Session) -> None:
    """归因粒度护栏：每文档 3 个 L1 标题 + 1 句滥用降为正文 → 文档主导 L1，单句不翻规则。"""
    for i in range(3):
        for _ in range(3):
            _mk(db, f"p{i}", "章节标题", 1)  # 3 个真标题
        demoted = _mk(db, f"p{i}", "章节标题", None)  # 1 句被降为正文
        svc.observe_node_edit(db, demoted, old_level=1, old_mark="unmarked")  # 降级事件标记该文档
    rule = svc.reaggregate(db, "章节标题")
    assert rule is not None and rule.status == "active"
    assert rule.level == 1  # 主导 L1，未被单句降级翻成「正文」


def test_manual_rule_not_overridden(db: Session) -> None:
    heading_rule_service.create(db, HeadingRuleCreate(style_name="小标题", level=1))
    db.flush()
    for i in range(3):  # 一致改 L2，但手动规则优先
        n = _mk(db, f"p{i}", "小标题", 2)
        svc.observe_node_edit(db, n, old_level=1, old_mark="unmarked")
    rule = svc.reaggregate(db, "小标题")
    assert rule is not None and rule.source == "manual" and rule.level == 1


def test_review_confirm_counts_as_vote(db: Session) -> None:
    for i in range(3):  # 确认（未改级）也投票给当前层级
        n = _mk(db, f"p{i}", "小标题", 1, mark="review")
        n.mark_status = "unmarked"
        svc.observe_node_edit(db, n, old_level=1, old_mark="review")
    rule = svc.reaggregate(db, "小标题")
    assert rule is not None and rule.status == "active" and rule.level == 1


def test_no_source_style_no_event(db: Session) -> None:
    # 零样式/启发式标题（无 source_style_name）不产生学习信号（属 M4）
    n = ProcedureNode(procedure_id="p1", sort_order=1000, heading_level=1, revision=1)
    db.add(n)
    db.flush()
    n.heading_level = 2
    assert svc.observe_node_edit(db, n, old_level=1, old_mark="unmarked") is None
    assert db.scalars(select(HeadingLearningEvent)).all() == []


def test_contradiction_demotes_active_to_candidate(db: Session) -> None:
    """矛盾降级（防自锁，§6）：active 规则在矛盾证据累积、一致率跌破阈值后自动降回 candidate。"""
    # 先 3 文档一致 L2 → active
    for i in range(3):
        n = _mk(db, f"p{i}", "小标题", 2)
        svc.observe_node_edit(db, n, old_level=1, old_mark="unmarked")
    rule = svc.reaggregate(db, "小标题")
    assert rule is not None and rule.status == "active"
    # 再来 2 文档判 L3（votes 3:2，一致率 0.6 < 0.8）→ 下次聚合自动降级
    for i in range(3, 5):
        n = _mk(db, f"p{i}", "小标题", 3)
        svc.observe_node_edit(db, n, old_level=1, old_mark="unmarked")
    rule = svc.reaggregate(db, "小标题")
    assert rule is not None and rule.status == "candidate"
    assert heading_rule_service.active_style_overrides(db) == {}  # 已不再注入


def test_admin_edit_pins_learned_rule(db: Session) -> None:
    """编辑即钉死（§6）：管理员改 learned 规则 → 转 manual，之后自学习不再覆盖。"""
    from app.schemas.heading_rule import HeadingRuleUpdate

    for i in range(3):
        n = _mk(db, f"p{i}", "小标题", 2)
        svc.observe_node_edit(db, n, old_level=1, old_mark="unmarked")
    rule = svc.reaggregate(db, "小标题")
    assert rule is not None and rule.source == "learned"
    # 管理员改成 L1（钉死）
    heading_rule_service.update(db, rule, HeadingRuleUpdate(level=1))
    assert rule.source == "manual" and rule.level == 1
    # 再来一致 L2 证据，reaggregate 不得覆盖 manual
    for i in range(5, 8):
        n = _mk(db, f"p{i}", "小标题", 2)
        svc.observe_node_edit(db, n, old_level=1, old_mark="unmarked")
    rule2 = svc.reaggregate(db, "小标题")
    assert rule2 is not None and rule2.source == "manual" and rule2.level == 1


def test_patch_node_hook_records_event(db: Session) -> None:
    """钩子接线：node_service.patch_node 改级 → 自动落一条学习事件。"""
    # patch_node 现要求宿主程序为当前草稿（审计 #5 守卫），需建真实 Procedure 行。
    import uuid

    from app.models.procedure import Procedure

    proc = Procedure(
        procedure_group_id=str(uuid.uuid4()),
        folder_id=str(uuid.uuid4()),
        code="QC-00001",
        name="P",
        level_of_use="reference",
        version=1,
        status="DRAFT",
        is_current=True,
    )
    db.add(proc)
    db.flush()
    n = _mk(db, proc.id, "小标题", 1)
    node_service.patch_node(db, n.id, {"heading_level": 2}, expected_revision=1)
    events = db.scalars(
        select(HeadingLearningEvent).where(HeadingLearningEvent.style_name == "小标题")
    ).all()
    assert len(events) == 1
    assert events[0].from_level == 1 and events[0].to_level == 2
    assert events[0].signal_type == "relevel"
