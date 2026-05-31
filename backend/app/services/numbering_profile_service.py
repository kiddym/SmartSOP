"""动态标题字典-编号体例服务（方案 M4b）。

承担：编号体例 CRUD（管理员手动维护）+ ``active_numbering_overrides`` 供解析注入。
事务边界：service 只 flush，由 router 提交（对齐 heading_rule_service 约定）。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import tenant
from app.errors import conflict, not_found
from app.models.base import utcnow
from app.models.numbering_profile import NumberingProfile
from app.schemas.numbering_profile import NumberingProfileCreate, NumberingProfileUpdate

_VALID_KINDS = ("heading", "weak_heading", "list")


def _norm_level(level: int | None) -> int | None:
    return None if level in (None, 0) else level


def active_numbering_overrides(db: Session) -> dict[str, tuple[str, int | None]]:
    """解析注入用：``status='active'`` 的 ``{pattern_key: (kind, level)}``。"""
    rows = db.scalars(
        select(NumberingProfile).where(
            NumberingProfile.is_active.is_(True),
            NumberingProfile.status == "active",
        )
    ).all()
    return {r.pattern_key: (r.kind, r.level) for r in rows}


def list_profiles(db: Session) -> list[NumberingProfile]:
    return list(
        db.scalars(
            select(NumberingProfile)
            .where(NumberingProfile.is_active.is_(True))
            .order_by(NumberingProfile.pattern_key)
        ).all()
    )


def get_or_404(db: Session, profile_id: str) -> NumberingProfile:
    # 显式 company 过滤：do_orm_execute 的 with_loader_criteria 不作用于 Session.get()
    # /identity-map 命中，故 IDOR 须靠带 company_id 的 SELECT（租户上下文为 None 时不加，
    # 与无租户路径行为一致）。
    q = select(NumberingProfile).where(
        NumberingProfile.id == profile_id, NumberingProfile.is_active.is_(True)
    )
    cid = tenant.get_current_company_id()
    if cid is not None:
        q = q.where(NumberingProfile.company_id == cid)
    p = db.scalars(q).first()
    if p is None:
        raise not_found("NUMBERING_PROFILE_NOT_FOUND", "编号体例不存在", field="id")
    return p


def create(db: Session, payload: NumberingProfileCreate) -> NumberingProfile:
    key = payload.pattern_key.strip()
    if payload.kind not in _VALID_KINDS:
        raise conflict("NUMBERING_PROFILE_BAD_KIND", f"非法 kind：{payload.kind}", field="kind")
    exists = db.scalars(
        select(NumberingProfile).where(
            NumberingProfile.is_active.is_(True),
            NumberingProfile.pattern_key == key,
        )
    ).first()
    if exists is not None:
        raise conflict(
            "NUMBERING_PROFILE_DUPLICATE", f"编号体例已存在：{key}", field="pattern_key"
        )
    p = NumberingProfile(
        pattern_key=key,
        kind=payload.kind,
        level=_norm_level(payload.level),
        source="manual",
        status="active",
    )
    db.add(p)
    db.flush()
    return p


def update(db: Session, p: NumberingProfile, payload: NumberingProfileUpdate) -> NumberingProfile:
    if payload.kind is not None:
        if payload.kind not in _VALID_KINDS:
            raise conflict("NUMBERING_PROFILE_BAD_KIND", f"非法 kind：{payload.kind}", field="kind")
        p.kind = payload.kind
    if payload.level is not None:
        p.level = _norm_level(payload.level)
    if payload.status is not None:
        p.status = payload.status
    p.source = "manual"
    p.revision += 1
    db.flush()
    return p


def delete(db: Session, p: NumberingProfile) -> None:
    p.is_active = False
    p.deleted_at = utcnow()
    db.flush()
