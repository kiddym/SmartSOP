"""工单工时成本 schema（TimeCategory / Labor / AdditionalCost / CostSummary）。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field


class TimeCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    hourly_rate: Decimal = Field(default=Decimal("0"), ge=0)
    description: str = ""


class TimeCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    hourly_rate: Decimal | None = Field(default=None, ge=0)
    description: str | None = None


class TimeCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    hourly_rate: Decimal
    description: str


class LaborCreate(BaseModel):
    """手填一条工时（duration_seconds 必填）。"""

    duration_seconds: int = Field(ge=0)
    time_category_id: str | None = None
    hourly_rate: Decimal | None = Field(default=None, ge=0)
    user_id: str | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    notes: str = ""


class LaborTimerStart(BaseModel):
    """开计时器。"""

    time_category_id: str | None = None
    hourly_rate: Decimal | None = Field(default=None, ge=0)
    user_id: str | None = None
    notes: str = ""


class LaborUpdate(BaseModel):
    duration_seconds: int | None = Field(default=None, ge=0)
    time_category_id: str | None = None
    hourly_rate: Decimal | None = Field(default=None, ge=0)
    user_id: str | None = None
    notes: str | None = None


class LaborRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    work_order_id: str
    user_id: str | None = None
    time_category_id: str | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    duration_seconds: int
    hourly_rate: Decimal
    notes: str

    @computed_field  # type: ignore[prop-decorator]  # pydantic computed_field
    @property
    def running(self) -> bool:
        return self.started_at is not None and self.stopped_at is None

    @computed_field  # type: ignore[prop-decorator]  # pydantic computed_field
    @property
    def cost(self) -> Decimal:
        from decimal import ROUND_HALF_UP

        if self.running:
            return Decimal("0.00")
        raw = Decimal(self.duration_seconds) / Decimal(3600) * self.hourly_rate
        return raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @computed_field  # type: ignore[prop-decorator]  # pydantic computed_field
    @property
    def running_elapsed_seconds(self) -> int | None:
        if not self.running or self.started_at is None:
            return None
        from app.models.base import utcnow

        return max(0, int((utcnow() - self.started_at).total_seconds()))


# ---------------------------------------------------------------------------
# AdditionalCost（工单额外成本）
# ---------------------------------------------------------------------------


class AdditionalCostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    amount: Decimal = Field(ge=0)
    cost_category_id: str | None = None
    description: str = ""


class AdditionalCostUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    amount: Decimal | None = Field(default=None, ge=0)
    cost_category_id: str | None = None
    description: str | None = None


class AdditionalCostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    work_order_id: str
    cost_category_id: str | None = None
    title: str
    amount: Decimal
    description: str
    created_by_user_id: str | None = None


# ---------------------------------------------------------------------------
# CostSummary（工单总成本汇总）
# ---------------------------------------------------------------------------


class CostSummaryRead(BaseModel):
    labor_total: Decimal
    additional_total: Decimal
    parts_total: Decimal
    total: Decimal
