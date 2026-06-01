"""站内通知 API（/api/v1/notifications）。个人数据：仅本人，无需额外权限码。"""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.errors import not_found
from app.models.base import utcnow
from app.models.notification import Notification
from app.models.user import User
from app.schemas.common import Page
from app.schemas.notification import NotificationRead, ReadAllResult, UnreadCount

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


def _to_read(n: Notification) -> NotificationRead:
    return NotificationRead(
        id=n.id,
        type=n.type,
        entity_type=n.entity_type,
        entity_id=n.entity_id,
        params=json.loads(n.params or "{}"),
        actor_user_id=n.actor_user_id,
        is_read=n.is_read,
        read_at=n.read_at,
        created_at=n.created_at,
    )


@router.get("", response_model=Page[NotificationRead])
def list_notifications(
    is_read: bool | None = None,
    type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[NotificationRead]:
    conds = [Notification.recipient_user_id == current_user.id]
    if is_read is not None:
        conds.append(Notification.is_read.is_(is_read))
    if type is not None:
        conds.append(Notification.type == type)
    if date_from is not None:
        conds.append(
            Notification.created_at >= datetime(date_from.year, date_from.month, date_from.day)
        )
    if date_to is not None:
        end = datetime(date_to.year, date_to.month, date_to.day)
        conds.append(Notification.created_at < end + timedelta(days=1))

    total = db.execute(select(func.count()).select_from(Notification).where(*conds)).scalar_one()
    rows = (
        db.execute(
            select(Notification)
            .where(*conds)
            .order_by(Notification.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        .scalars()
        .all()
    )
    return Page[NotificationRead](
        items=[_to_read(n) for n in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.get("/unread-count", response_model=UnreadCount)
def unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UnreadCount:
    n = db.execute(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.recipient_user_id == current_user.id,
            Notification.is_read.is_(False),
        )
    ).scalar_one()
    return UnreadCount(count=n)


@router.post("/{notification_id}/read", response_model=NotificationRead)
def mark_read(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationRead:
    n = db.get(Notification, notification_id)
    if n is None or n.recipient_user_id != current_user.id:
        raise not_found("NOTIFICATION_NOT_FOUND", "通知不存在")
    if not n.is_read:
        n.is_read = True
        n.read_at = utcnow()
        db.commit()
        db.refresh(n)
    return _to_read(n)


@router.post("/read-all", response_model=ReadAllResult)
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReadAllResult:
    rows = (
        db.execute(
            select(Notification).where(
                Notification.recipient_user_id == current_user.id,
                Notification.is_read.is_(False),
            )
        )
        .scalars()
        .all()
    )
    now = utcnow()
    for n in rows:
        n.is_read = True
        n.read_at = now
    db.commit()
    return ReadAllResult(updated=len(rows))
