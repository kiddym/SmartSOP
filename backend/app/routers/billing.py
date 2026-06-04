"""公司订阅自查端点（Phase 6）：登录即可查看本公司档位/座席/已解锁功能。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.billing.catalog import (
    PLAN_CATALOG,
    Plan,
    effective_features,
    effective_seat_limit,
)
from app.db import get_db
from app.deps import get_current_user
from app.models.company import Company
from app.models.user import User, UserStatus
from app.schemas.billing import PlanCatalogEntry, SubscriptionRead

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

_CATALOG_VIEW = [
    PlanCatalogEntry(
        plan=plan.value,
        seat_limit=spec.seat_limit,
        features=sorted(f.value for f in spec.features),
    )
    for plan, spec in PLAN_CATALOG.items()
]


@router.get("/subscription", response_model=SubscriptionRead)
def get_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionRead:
    company = db.get(Company, current_user.company_id)
    plan = company.plan if company else Plan.free.value
    status_ = company.subscription_status if company else "active"
    seat_used = db.execute(
        select(func.count())
        .select_from(User)
        .where(User.company_id == current_user.company_id, User.status == UserStatus.active)
    ).scalar_one()
    return SubscriptionRead(
        plan=plan,
        subscription_status=status_,
        seat_used=seat_used,
        seat_limit=effective_seat_limit(plan, status_),
        features=sorted(f.value for f in effective_features(plan, status_)),
        catalog=_CATALOG_VIEW,
    )
