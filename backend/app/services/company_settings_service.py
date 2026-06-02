from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company_settings import CompanySettings
from app.schemas.platform import CompanySettingsUpdate


def get_or_create(db: Session, company_id: str) -> CompanySettings:
    row = db.execute(
        select(CompanySettings).where(CompanySettings.company_id == company_id)
    ).scalar_one_or_none()
    if row is None:
        row = CompanySettings(company_id=company_id)
        db.add(row)
        db.flush()
    return row


def update(db: Session, company_id: str, data: CompanySettingsUpdate) -> CompanySettings:
    row = get_or_create(db, company_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(row, field, value)
    db.flush()
    return row
