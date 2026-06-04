"""商业化订阅 schema（Phase 6）。"""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from app.billing.catalog import ALL_STATUSES, Plan


class SubscriptionUpdate(BaseModel):
    plan: str
    subscription_status: str

    @field_validator("plan")
    @classmethod
    def _valid_plan(cls, v: str) -> str:
        if v not in {p.value for p in Plan}:
            raise ValueError("无效的套餐档位")
        return v

    @field_validator("subscription_status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        if v not in ALL_STATUSES:
            raise ValueError("无效的订阅状态")
        return v


class PlanCatalogEntry(BaseModel):
    plan: str
    seat_limit: int | None
    features: list[str]


class SubscriptionRead(BaseModel):
    plan: str
    subscription_status: str
    seat_used: int
    seat_limit: int | None
    features: list[str]
    catalog: list[PlanCatalogEntry]
