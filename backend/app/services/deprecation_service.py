"""资产折旧服务：按资产取 / upsert（PUT 语义）/ 删除。折旧与资产 1:1。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.deprecation import AssetDeprecation
from app.schemas.deprecation import DeprecationUpdate


def get_by_asset(db: Session, asset_id: str) -> AssetDeprecation | None:
    return db.execute(
        select(AssetDeprecation).where(AssetDeprecation.asset_id == asset_id)
    ).scalar_one_or_none()


def upsert(
    db: Session, asset_id: str, company_id: str, payload: DeprecationUpdate
) -> AssetDeprecation:
    """无则建、有则全量覆盖（PUT 语义；未给字段视为 None 清空）。"""
    row = get_by_asset(db, asset_id)
    if row is None:
        row = AssetDeprecation(asset_id=asset_id, company_id=company_id)
        db.add(row)
    row.purchase_price = payload.purchase_price
    row.purchase_date = payload.purchase_date
    row.residual_value = payload.residual_value
    row.useful_life_years = payload.useful_life_years
    row.rate = payload.rate
    db.commit()
    db.refresh(row)
    return row


def delete(db: Session, row: AssetDeprecation) -> None:
    db.delete(row)
    db.commit()
