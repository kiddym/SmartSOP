"""动态标题字典 —— 隐式学习闭环（方案 M3，§5）。

编辑器对**样式标题**的改级 / 标题↔正文互转 / review 确认 → 追加一条学习事件，
并按 (style_name) 重聚合成 ``learned`` 规则。三道护栏：
- 投票阈值（防 n=1）：evidence 去重**文档**数 ≥ K_DOCS 且一致率 ≥ MIN_AGREEMENT 才 active。
- 归因粒度（防个例污染）：按文档取**最新**投票——某文档内 23 个标题 + 1 句滥用降级，
  该文档只投 1 票（最终层级），单句例外不单独成票，故 23:1 不会翻规则。
- 手动优先：``source='manual'``（「记住此样式」）规则不被学习覆盖。

仅样式（style_name）；编号体例（numbering_pattern）的学习是 M4。
"""

from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.heading_learning_event import HeadingLearningEvent
from app.models.heading_rule import HeadingStyleRule
from app.models.node import ProcedureNode

K_DOCS = 3  # 生效所需的去重文档证据数
MIN_AGREEMENT = 0.8  # 生效所需的投票一致率


def observe_node_edit(
    db: Session, node: ProcedureNode, *, old_level: int | None, old_mark: str
) -> str | None:
    """采集一条样式标题校正信号。返回被触动的 style_name（供调用方收集后重聚合），无则 None。

    仅对带来源样式名的节点生效（零样式/启发式标题无归因，属 M4）。
    """
    style = node.source_style_name
    if not style:
        return None
    new_level = node.heading_level
    if old_level != new_level:
        if old_level is not None and new_level is None:
            signal = "demote_to_content"
        elif old_level is None and new_level is not None:
            signal = "promote_to_heading"
        else:
            signal = "relevel"
        _append(db, node, style, signal, old_level, new_level)
        return style
    # 未改级但 review→确认 → 投票给当前层级（弱正信号）
    if old_mark == "review" and node.mark_status != "review":
        _append(db, node, style, "review_confirm", new_level, new_level)
        return style
    return None


def reaggregate(db: Session, style_name: str) -> HeadingStyleRule | None:
    """重算 style_name 的 learned 规则（manual 规则不覆盖）。返回受影响规则或 None。

    投票口径（关键，实现归因粒度护栏）：
    - **哪些文档算证据**：仅「用户校验过该样式」的文档（即该样式在该文档有学习事件）——
      避免把解析器自己的输出当证据（循环自证）。
    - **每文档投几票**：1 票，取该文档内 ``source_style_name==style_name`` 的 active 节点的
      **主导最终层级**（节点终态，非事件流）。TP试验程序里 23 个 L1 标题 + 1 句滥用降为正文
      → 主导仍 L1，该文档投 1 票 L1，单句例外不翻规则。
    """
    rule = db.scalars(
        select(HeadingStyleRule).where(
            HeadingStyleRule.is_active.is_(True),
            HeadingStyleRule.style_name == style_name,
        )
    ).first()
    # 手动钉死优先：不被自学习覆盖（方案 §6）
    if rule is not None and rule.source == "manual":
        return rule

    # 用户校验过该样式的文档（有事件）
    doc_ids = db.scalars(
        select(HeadingLearningEvent.procedure_id)
        .where(HeadingLearningEvent.style_name == style_name)
        .distinct()
    ).all()
    if not doc_ids:
        return rule

    votes: Counter[object] = Counter()
    for pid in doc_ids:
        levels = db.scalars(
            select(ProcedureNode.heading_level).where(
                ProcedureNode.procedure_id == pid,
                ProcedureNode.source_style_name == style_name,
                ProcedureNode.is_active.is_(True),
            )
        ).all()
        if not levels:
            continue  # 该文档此样式节点已全删 → 不计票
        doc_vote = Counter(
            "content" if lv is None else lv for lv in levels
        ).most_common(1)[0][0]
        votes[doc_vote] += 1
    evidence = sum(votes.values())
    if evidence == 0:
        return rule
    winner, wcount = votes.most_common(1)[0]
    agreement = wcount / evidence

    if rule is None:
        rule = HeadingStyleRule(style_name=style_name, source="learned")
        db.add(rule)
    rule.source = "learned"
    rule.level_votes = {str(k): v for k, v in votes.items()}
    rule.evidence_count = evidence
    rule.agreement = agreement

    winner_is_level = isinstance(winner, int) and winner >= 1
    if winner_is_level and evidence >= K_DOCS and agreement >= MIN_AGREEMENT:
        rule.level = winner  # type: ignore[assignment]
        rule.status = "active"
    else:
        # 证据不足 / 一致率不够 / 多数判「非标题」→ candidate（不注入解析，维持现状）
        rule.level = winner if winner_is_level else None  # type: ignore[assignment]
        rule.status = "candidate"
    rule.revision = (rule.revision or 0) + 1  # 新建规则 flush 前 revision 仍为 None
    db.flush()
    return rule


def _append(
    db: Session,
    node: ProcedureNode,
    style_name: str,
    signal: str,
    from_level: int | None,
    to_level: int | None,
) -> None:
    db.add(
        HeadingLearningEvent(
            procedure_id=node.procedure_id,
            node_id=node.id,
            style_name=style_name,
            signal_type=signal,
            from_level=from_level,
            to_level=to_level,
        )
    )
    db.flush()
