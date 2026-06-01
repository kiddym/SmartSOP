"""Company (tenant) settings API (/api/v1/companies)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_current_user, get_db, require_permission
from app.errors import not_found
from app.models.company import Company
from app.models.user import User
from app.schemas.company import CompanyRead, CompanyUpdate
from app.services import company_service

router = APIRouter(prefix="/api/v1/companies", tags=["companies"])


@router.get("/me", response_model=CompanyRead)
def get_my_company(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Company:
    company = company_service.get_company(db, current_user.company_id)
    if company is None:
        raise not_found("COMPANY_NOT_FOUND", "公司不存在")
    return company


@router.patch("/me", response_model=CompanyRead)
def update_my_company(
    payload: CompanyUpdate,
    current_user: User = Depends(require_permission(permissions.COMPANY_SETTINGS)),
    db: Session = Depends(get_db),
) -> Company:
    company = company_service.update_company(db, current_user.company_id, payload)
    if company is None:
        raise not_found("COMPANY_NOT_FOUND", "公司不存在")
    return company
