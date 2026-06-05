"""公司订阅自查端点（Phase 6）：登录即可查看本公司档位/座席/已解锁功能。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import permissions
from app.billing import stripe_gateway
from app.billing.catalog import (
    PLAN_CATALOG,
    Plan,
    effective_features,
    effective_seat_limit,
)
from app.db import get_db
from app.deps import get_current_user, require_permission
from app.errors import bad_request
from app.models.company import Company
from app.models.user import User, UserStatus
from app.schemas.billing import (
    CheckoutSessionOut,
    PlanCatalogEntry,
    PortalSessionOut,
    SubscriptionRead,
)
from app.services import billing_service

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


@router.post("/checkout-session", response_model=CheckoutSessionOut)
def create_checkout_session(
    current_user: User = Depends(require_permission(permissions.BILLING_MANAGE)),
    db: Session = Depends(get_db),
) -> CheckoutSessionOut:
    company = db.get(Company, current_user.company_id)
    if company is None:
        raise bad_request("COMPANY_NOT_FOUND", "公司不存在")
    return CheckoutSessionOut(url=billing_service.start_checkout(db, company, current_user))


@router.post("/portal-session", response_model=PortalSessionOut)
def create_portal_session(
    current_user: User = Depends(require_permission(permissions.BILLING_MANAGE)),
    db: Session = Depends(get_db),
) -> PortalSessionOut:
    company = db.get(Company, current_user.company_id)
    if company is None:
        raise bad_request("COMPANY_NOT_FOUND", "公司不存在")
    return PortalSessionOut(url=billing_service.open_portal(db, company))


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    # Request-body size is bounded upstream (reverse proxy / future global middleware),
    # not enforced per-route here.
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    # ONLY SignatureError → 400.  Any other exception from handle_event propagates
    # as 500 so that Stripe retries the event — do NOT add a broad except clause.
    try:
        billing_service.handle_event(db, payload, sig)
    except stripe_gateway.SignatureError:
        raise bad_request("INVALID_SIGNATURE", "Webhook 验签失败") from None
    return {"received": True}
