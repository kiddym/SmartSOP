"""业务实体自定义字段定义 schema。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.field import FieldValidation as CustomFieldValidation

ENTITY_TYPES = ("work_order", "asset", "request", "location", "part")
FIELD_TYPES = ("text", "number", "date", "select", "multi_select", "checkbox", "textarea")


class CustomFieldOption(BaseModel):
    value: str = Field(min_length=1, max_length=200)
    label: str = Field(default="", max_length=200)
    archived: bool = False


class CustomFieldCreate(BaseModel):
    entity_type: Literal["work_order", "asset", "request", "location", "part"]
    key: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    field_type: Literal["text", "number", "date", "select", "multi_select", "checkbox", "textarea"]
    description: str = ""
    required: bool = False
    default_value: Any | None = None
    options: list[CustomFieldOption] = []
    validation: CustomFieldValidation = Field(default_factory=CustomFieldValidation)
    sort_order: int = 0


class CustomFieldUpdate(BaseModel):
    # key / entity_type / field_type 不可改，不在此出现
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    required: bool = False
    default_value: Any | None = None
    options: list[CustomFieldOption] = []
    validation: CustomFieldValidation = Field(default_factory=CustomFieldValidation)
    sort_order: int = 0


class CustomFieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    entity_type: str
    key: str
    name: str
    field_type: str
    description: str
    required: bool
    default_value: Any | None
    options: list[dict[str, Any]]
    validation_rules: dict[str, Any]
    sort_order: int
    status: str


class CustomFieldReorderIn(BaseModel):
    ordered_ids: list[str] = Field(min_length=1, max_length=500)
