"""客户 API（/api/v1/customers）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.customer import Customer
from app.models.user import User
from app.schemas.partner import CustomerCreate, CustomerMini, CustomerRead, CustomerUpdate
from app.services import customer_service as svc

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


def _ensure(c: Customer | None, company_id: str) -> Customer:
    if c is None or c.company_id != company_id:
        raise not_found("CUSTOMER_NOT_FOUND", "客户不存在")
    return c


def _read(db: Session, c: Customer) -> CustomerRead:
    data = CustomerRead.model_validate(c)
    data.part_ids = svc.part_ids(db, c.id)
    return data


@router.get("", response_model=list[CustomerRead])
def list_customers(
    part_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.CUSTOMER_VIEW)),
):
    return [_read(db, c) for c in svc.list_customers(db, part_id=part_id)]


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.CUSTOMER_CREATE)),
):
    c = svc.create_customer(db, payload, current_user.company_id, actor_user_id=current_user.id)
    return _read(db, c)


# 注：/mini 必须注册在 /{customer_id} 之前，否则会被路径参数吞掉
@router.get("/mini", response_model=list[CustomerMini])
def list_customers_mini(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.CUSTOMER_VIEW)),
):
    return svc.list_customers(db)


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer(
    customer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.CUSTOMER_VIEW)),
):
    c = _ensure(svc.get_customer(db, customer_id), current_user.company_id)
    return _read(db, c)


@router.patch("/{customer_id}", response_model=CustomerRead)
def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.CUSTOMER_EDIT)),
):
    c = _ensure(svc.get_customer(db, customer_id), current_user.company_id)
    svc.update_customer(db, c, payload, current_user.company_id, actor_user_id=current_user.id)
    return _read(db, c)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.CUSTOMER_DELETE)),
):
    c = _ensure(svc.get_customer(db, customer_id), current_user.company_id)
    svc.delete_customer(db, c)
