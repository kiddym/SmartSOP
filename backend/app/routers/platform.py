"""平台运营端点（Phase 6）：手动设公司套餐/订阅状态。仅 is_platform_admin。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_platform_admin
from app.errors import not_found
from app.models.company import Company
from app.models.user import User
from app.schemas.billing import SubscriptionUpdate

router = APIRouter(prefix="/api/v1/platform", tags=["platform"])


@router.patch("/companies/{company_id}/subscription")
def set_company_subscription(
    company_id: str,
    payload: SubscriptionUpdate,
    _admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    # Company 非 tenant-scoped，db.get 直取任意公司。
    company = db.get(Company, company_id)
    if company is None:
        raise not_found("COMPANY_NOT_FOUND", "公司不存在")
    company.plan = payload.plan
    company.subscription_status = payload.subscription_status
    db.commit()
    return {"plan": company.plan, "subscription_status": company.subscription_status}
