"""邮件通知偏好 API。个人数据：仅本人，无需额外权限码。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.notification_preference import (
    NotificationPreferenceRead,
    NotificationPreferenceUpdate,
)
from app.services import notification_preference_service as svc

router = APIRouter(prefix="/api/v1/notification-preferences", tags=["notification-preferences"])


@router.get("", response_model=NotificationPreferenceRead)
def get_preference(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationPreferenceRead:
    pref = svc.get(db, current_user.company_id, current_user.id)
    return NotificationPreferenceRead(**pref)


@router.put("", response_model=NotificationPreferenceRead)
def put_preference(
    payload: NotificationPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationPreferenceRead:
    svc.upsert(
        db,
        current_user.company_id,
        current_user.id,
        email_enabled=payload.email_enabled,
        disabled_types=payload.disabled_types,
    )
    db.commit()
    pref = svc.get(db, current_user.company_id, current_user.id)
    return NotificationPreferenceRead(**pref)
