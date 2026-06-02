from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import conflict, not_found
from app.models.currency import Currency
from app.schemas.platform import CurrencyCreate


def list_currencies(db: Session) -> list[Currency]:
    return list(db.execute(select(Currency).order_by(Currency.code)).scalars())


def create_currency(db: Session, data: CurrencyCreate) -> Currency:
    if db.execute(select(Currency).where(Currency.code == data.code)).scalar_one_or_none():
        raise conflict("CURRENCY_EXISTS", f"币种已存在：{data.code}")
    cur = Currency(code=data.code, name=data.name, symbol=data.symbol)
    db.add(cur)
    db.flush()
    return cur


def delete_currency(db: Session, currency_id: str) -> None:
    cur = db.get(Currency, currency_id)
    if cur is None:
        raise not_found("CURRENCY_NOT_FOUND", "币种不存在")
    db.delete(cur)
    db.flush()
