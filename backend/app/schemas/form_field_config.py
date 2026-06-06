"""表单字段配置 schema。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FieldConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    field_name: str
    visible: bool
    required: bool
    sort_order: int


class FieldConfigItem(BaseModel):
    """PUT 批量更新单条：仅 visible/required 可改，field_name 定位。"""

    field_name: str
    visible: bool = True
    required: bool = False
