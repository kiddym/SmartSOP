"""Company settings service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.company import Company
from app.schemas.company import CompanyUpdate


def get_company(db: Session, company_id: str) -> Company | None:
    return db.get(Company, company_id)


def update_company(db: Session, company_id: str, payload: CompanyUpdate) -> Company | None:
    company = db.get(Company, company_id)
    if company is None:
        return None
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(company, k, v)
    db.commit()
    db.refresh(company)
    return company
