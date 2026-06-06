"""备件 schema（Phase 3A）。is_low_stock 计算字段只读；关联 ids 由 router 填充。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field


class PartCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    description: str = ""
    cost: Decimal = Decimal("0")
    quantity: Decimal = Decimal("0")
    min_quantity: Decimal = Decimal("0")
    unit: str = Field(default="", max_length=50)
    barcode: str | None = Field(default=None, max_length=120)
    non_stock: bool = False
    category_id: str | None = None
    area: str | None = Field(default=None, max_length=200)
    additional_infos: str | None = None
    assignee_ids: list[str] = []
    team_ids: list[str] = []
    asset_ids: list[str] = []
    location_ids: list[str] = []
    pm_ids: list[str] = []
    vendor_ids: list[str] = []
    customer_ids: list[str] = []


class PartUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    cost: Decimal | None = None
    quantity: Decimal | None = None
    min_quantity: Decimal | None = None
    unit: str | None = Field(default=None, max_length=50)
    barcode: str | None = Field(default=None, max_length=120)
    non_stock: bool | None = None
    category_id: str | None = None
    area: str | None = Field(default=None, max_length=200)
    additional_infos: str | None = None
    assignee_ids: list[str] | None = None
    team_ids: list[str] | None = None
    asset_ids: list[str] | None = None
    location_ids: list[str] | None = None
    pm_ids: list[str] | None = None
    vendor_ids: list[str] | None = None
    customer_ids: list[str] | None = None


class PartRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    custom_id: str
    name: str
    description: str
    cost: Decimal
    quantity: Decimal
    min_quantity: Decimal
    unit: str
    barcode: str | None = None
    non_stock: bool
    is_low_stock: bool
    category_id: str | None = None
    area: str | None = None
    additional_infos: str | None = None
    assignee_ids: list[str] = []
    team_ids: list[str] = []
    asset_ids: list[str] = []
    location_ids: list[str] = []
    pm_ids: list[str] = []
    vendor_ids: list[str] = []
    customer_ids: list[str] = []


class PartMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    custom_id: str


class PartCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    description: str = ""


class PartCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None


class PartCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str


class PartConsumptionCreate(BaseModel):
    part_id: str
    quantity: Decimal


class PartConsumptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    part_id: str
    work_order_id: str
    quantity: Decimal
    unit_cost: Decimal
    consumed_by_user_id: str | None = None
    consumed_at: datetime

    @computed_field  # type: ignore[prop-decorator]  # pydantic computed_field
    @property
    def total_cost(self) -> Decimal:
        return self.quantity * self.unit_cost


class MultiPartCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    description: str = ""
    part_ids: list[str] = []


class MultiPartUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    part_ids: list[str] | None = None


class MultiPartRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    custom_id: str
    name: str
    description: str
    part_ids: list[str] = []
