from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_current_user, get_db, require_permission
from app.models.currency import Currency
from app.models.user import User
from app.schemas.platform import CurrencyCreate, CurrencyOut
from app.services import currency_service

router = APIRouter(prefix="/api/v1/currencies", tags=["currencies"])


@router.get("", response_model=list[CurrencyOut])
def list_currencies(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[Currency]:
    return currency_service.list_currencies(db)


@router.post("", response_model=CurrencyOut, status_code=201)
def create_currency(
    payload: CurrencyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(permissions.CURRENCY_MANAGE)),
) -> Currency:
    cur = currency_service.create_currency(db, payload)
    db.commit()
    return cur


@router.delete("/{currency_id}", status_code=204, response_model=None)
def delete_currency(
    currency_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(permissions.CURRENCY_MANAGE)),
) -> Response:
    currency_service.delete_currency(db, currency_id)
    db.commit()
    return Response(status_code=204)
