"""动态标题字典-样式规则服务（动态标题字典与自学习方案 M1）。

承担：样式规则 CRUD（管理员手动维护）+ ``active_style_overrides`` 供解析注入。
事务边界：service 只 flush，由 router 提交（对齐 field_service 约定）。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import conflict, not_found
from app.models.base import utcnow
from app.models.heading_rule import HeadingStyleRule
from app.schemas.heading_rule import HeadingRuleCreate, HeadingRuleUpdate


def _norm_level(level: int | None) -> int | None:
    """归一层级：0 视作 None（「非标题/正文」统一存 null）。"""
    return None if level in (None, 0) else level


def active_style_overrides(db: Session) -> dict[str, int]:
    """解析注入用：``status='active'`` 且 level≥1 的 ``{样式名: 层级}``。

    level=null（「非标题」判定）不进 style_overrides——它表达「不是标题」，
    由编号体例/正文逻辑承载，样式覆盖只表达「是第几级标题」。
    """
    rows = db.scalars(
        select(HeadingStyleRule).where(
            HeadingStyleRule.is_active.is_(True),
            HeadingStyleRule.status == "active",
            HeadingStyleRule.level.is_not(None),
        )
    ).all()
    return {r.style_name: r.level for r in rows if r.level is not None}


def list_rules(db: Session) -> list[HeadingStyleRule]:
    return list(
        db.scalars(
            select(HeadingStyleRule)
            .where(HeadingStyleRule.is_active.is_(True))
            .order_by(HeadingStyleRule.style_name)
        ).all()
    )


def get_or_404(db: Session, rule_id: str) -> HeadingStyleRule:
    rule = db.get(HeadingStyleRule, rule_id)
    if rule is None or not rule.is_active:
        raise not_found("HEADING_RULE_NOT_FOUND", "样式规则不存在", field="id")
    return rule


def _find_by_name(db: Session, style_name: str) -> HeadingStyleRule | None:
    return db.scalars(
        select(HeadingStyleRule).where(
            HeadingStyleRule.is_active.is_(True),
            HeadingStyleRule.style_name == style_name,
        )
    ).first()


def create(db: Session, payload: HeadingRuleCreate) -> HeadingStyleRule:
    name = payload.style_name.strip()
    if _find_by_name(db, name) is not None:
        raise conflict("HEADING_RULE_DUPLICATE", f"样式规则已存在：{name}", field="style_name")
    rule = HeadingStyleRule(
        style_name=name,
        level=_norm_level(payload.level),
        source="manual",
        status="active",
    )
    db.add(rule)
    db.flush()
    return rule


def update(db: Session, rule: HeadingStyleRule, payload: HeadingRuleUpdate) -> HeadingStyleRule:
    if payload.level is not None:
        rule.level = _norm_level(payload.level)
    if payload.status is not None:
        rule.status = payload.status
    # 管理员任何手动干预 → 钉为 manual，自学习（reaggregate）不再覆盖（方案 §6 可回滚/钉死）。
    rule.source = "manual"
    rule.revision += 1
    db.flush()
    return rule


def delete(db: Session, rule: HeadingStyleRule) -> None:
    """软删（对齐业务表 SoftDeleteMixin 约定）。"""
    rule.is_active = False
    rule.deleted_at = utcnow()
    db.flush()
