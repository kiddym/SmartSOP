"""供应商/客户/成本分类 schema（Phase 3B）。关联 part_ids 由 router 填充。"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class VendorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    vendor_type: str = Field(default="", max_length=120)
    description: str = ""
    rate: Decimal = Decimal("0")
    address: str = Field(default="", max_length=500)
    phone: str = Field(default="", max_length=60)
    email: str = Field(default="", max_length=200)
    website: str = Field(default="", max_length=300)
    part_ids: list[str] = []
    asset_ids: list[str] = []
    location_ids: list[str] = []


class VendorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    vendor_type: str | None = Field(default=None, max_length=120)
    description: str | None = None
    rate: Decimal | None = None
    address: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=60)
    email: str | None = Field(default=None, max_length=200)
    website: str | None = Field(default=None, max_length=300)
    part_ids: list[str] | None = None
    asset_ids: list[str] | None = None
    location_ids: list[str] | None = None


class VendorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    vendor_type: str
    description: str
    rate: Decimal
    address: str
    phone: str
    email: str
    website: str
    part_ids: list[str] = []
    asset_ids: list[str] = []
    location_ids: list[str] = []


class VendorMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    customer_type: str = Field(default="", max_length=120)
    description: str = ""
    rate: Decimal = Decimal("0")
    billing_currency: str = Field(default="", max_length=8)
    billing_name: str | None = Field(default=None, max_length=300)
    billing_address: str | None = Field(default=None, max_length=500)
    billing_address2: str | None = Field(default=None, max_length=500)
    address: str = Field(default="", max_length=500)
    phone: str = Field(default="", max_length=60)
    email: str = Field(default="", max_length=200)
    website: str = Field(default="", max_length=300)
    part_ids: list[str] = []
    asset_ids: list[str] = []
    location_ids: list[str] = []


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    customer_type: str | None = Field(default=None, max_length=120)
    description: str | None = None
    rate: Decimal | None = None
    billing_currency: str | None = Field(default=None, max_length=8)
    billing_name: str | None = Field(default=None, max_length=300)
    billing_address: str | None = Field(default=None, max_length=500)
    billing_address2: str | None = Field(default=None, max_length=500)
    address: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=60)
    email: str | None = Field(default=None, max_length=200)
    website: str | None = Field(default=None, max_length=300)
    part_ids: list[str] | None = None
    asset_ids: list[str] | None = None
    location_ids: list[str] | None = None


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    customer_type: str
    description: str
    rate: Decimal
    billing_currency: str
    billing_name: str | None = None
    billing_address: str | None = None
    billing_address2: str | None = None
    address: str
    phone: str
    email: str
    website: str
    part_ids: list[str] = []
    asset_ids: list[str] = []
    location_ids: list[str] = []


class CustomerMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str


class CostCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    description: str = ""


class CostCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None


class CostCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str
