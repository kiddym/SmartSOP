from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.company_settings import CompanySettings
from app.models.user import User
from app.schemas.platform import CompanySettingsOut, CompanySettingsUpdate
from app.services import company_settings_service

router = APIRouter(prefix="/api/v1/company-settings", tags=["company-settings"])


@router.get("", response_model=CompanySettingsOut)
def get_settings(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> CompanySettings:
    return company_settings_service.get_or_create(db, user.company_id)


@router.put("", response_model=CompanySettingsOut)
def update_settings(
    payload: CompanySettingsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CompanySettings:
    row = company_settings_service.update(db, user.company_id, payload)
    db.commit()
    return row
