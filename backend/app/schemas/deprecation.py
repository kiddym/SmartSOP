"""资产折旧 schema。

Read 含只读 computed current_value（直线法）：
  年折旧额 = (purchase_price - residual_value) / useful_life_years
  current  = max(residual_value, purchase_price - 年折旧额 × 已过年数)
任一必要字段缺失（purchase_price / residual_value / useful_life_years / purchase_date）
或 useful_life_years <= 0 时，current_value = None。
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field

_CENTS = Decimal("0.01")


class DeprecationUpdate(BaseModel):
    """PUT 载荷：全部字段可空（None 表示清空）。"""

    purchase_price: Decimal | None = None
    purchase_date: date | None = None
    residual_value: Decimal | None = None
    useful_life_years: int | None = Field(default=None, ge=0)
    rate: Decimal | None = None


# PUT upsert 语义下 Create 与 Update 同形；保留别名供路由/测试引用。
DeprecationCreate = DeprecationUpdate


class DeprecationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_id: str
    purchase_price: Decimal | None = None
    purchase_date: date | None = None
    residual_value: Decimal | None = None
    useful_life_years: int | None = None
    rate: Decimal | None = None

    @computed_field  # type: ignore[prop-decorator]  # pydantic computed_field
    @property
    def current_value(self) -> Decimal | None:
        return compute_current_value(
            purchase_price=self.purchase_price,
            purchase_date=self.purchase_date,
            residual_value=self.residual_value,
            useful_life_years=self.useful_life_years,
        )


def compute_current_value(
    *,
    purchase_price: Decimal | None,
    purchase_date: date | None,
    residual_value: Decimal | None,
    useful_life_years: int | None,
) -> Decimal | None:
    """直线法当前价值；缺字段或年限非正时返回 None。已过年数按整年下取整。"""
    if (
        purchase_price is None
        or residual_value is None
        or useful_life_years is None
        or useful_life_years <= 0
        or purchase_date is None
    ):
        return None
    annual = (purchase_price - residual_value) / Decimal(useful_life_years)
    elapsed_years = _elapsed_full_years(purchase_date)
    current = purchase_price - annual * Decimal(elapsed_years)
    if current < residual_value:
        current = residual_value
    return current.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _elapsed_full_years(purchase_date: date) -> int:
    today = date.today()
    if today <= purchase_date:
        return 0
    years = today.year - purchase_date.year
    # 未到周年纪念日则减一年。
    if (today.month, today.day) < (purchase_date.month, purchase_date.day):
        years -= 1
    return max(years, 0)
