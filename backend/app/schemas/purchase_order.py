"""采购单 schema（Phase 3C）。lines/total_cost 由 router 填充。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.purchase_order_status import PurchaseOrderStatus


class POLineCreate(BaseModel):
    part_id: str = Field(min_length=1)
    quantity: Decimal
    unit_cost: Decimal = Decimal("0")


class POLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    part_id: str
    quantity: Decimal
    unit_cost: Decimal

    @computed_field
    @property
    def line_total(self) -> Decimal:
        # 量化到 4 位（与 Numeric(18,4) 一致；避免 scale-8 乘积噪声）
        return (self.quantity * self.unit_cost).quantize(Decimal("0.0001"))


class PurchaseOrderCreate(BaseModel):
    vendor_id: str = Field(min_length=1)
    notes: str = ""
    lines: list[POLineCreate] = []


class PurchaseOrderUpdate(BaseModel):
    vendor_id: str | None = Field(default=None, min_length=1)
    notes: str | None = None
    lines: list[POLineCreate] | None = None


class PurchaseOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    custom_id: str
    vendor_id: str
    status: PurchaseOrderStatus
    notes: str
    resolution_note: str
    resolved_by_user_id: str | None
    resolved_at: datetime | None
    lines: list[POLineRead] = []
    total_cost: Decimal = Decimal("0")


class PurchaseOrderMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    custom_id: str
    vendor_id: str
    status: PurchaseOrderStatus


class POActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    activity_type: str
    actor_user_id: str | None
    from_status: str | None
    to_status: str | None
    comment: str
    created_at: datetime


class POResolve(BaseModel):
    note: str = ""
