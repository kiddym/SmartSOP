"""自定义字段 schema（api-specification §5.7 / data-model §3.7 / §38 / Q253-Q258 / Q367）。

输入用「表单化校验项」（Q253），后端 compile 成标准 JSON Schema 存 validation_rules；
输出回带 validation_rules 原样（前端编辑弹窗据此回填表单）。key / field_type 创建后
不可改（Q254/Q134/Q136），PUT 传入不同值分别返 FIELD_KEY_IMMUTABLE / FIELD_TYPE_IMMUTABLE。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

FieldType = Literal["text", "number", "date", "select", "multi_select", "checkbox", "textarea"]
FieldStatus = Literal["active", "archived"]


class FieldOption(BaseModel):
    """选项（select / multi_select / checkbox）。archived 选项保留旧值、新建不出现（Q24/Q255）。"""

    value: str = Field(min_length=1, max_length=200)
    label: str = Field(min_length=1, max_length=200)
    archived: bool = False


class FieldValidation(BaseModel):
    """表单化校验项（Q253）：后端 compile 成 JSON Schema 存 validation_rules。"""

    minimum: float | None = None
    maximum: float | None = None
    min_length: int | None = Field(default=None, ge=0)
    max_length: int | None = Field(default=None, ge=0)
    pattern: str | None = Field(default=None, max_length=500)


class FieldCreate(BaseModel):
    """创建自定义字段（POST /procedure-fields）。key 手填英文、建后不可改（Q254）。"""

    name: str = Field(min_length=1, max_length=100)
    key: str = Field(min_length=1, max_length=100)
    field_type: FieldType
    description: str = Field(default="", max_length=2000)
    required: bool = False
    default_value: Any | None = None
    options: list[FieldOption] = Field(default_factory=list)
    validation: FieldValidation = Field(default_factory=FieldValidation)
    sort_order: int = Field(default=0, ge=0)
    show_on_cover: bool = False


class FieldUpdate(BaseModel):
    """更新自定义字段（PUT /procedure-fields/{id}）。key / field_type 传入会被拒。"""

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    required: bool = False
    default_value: Any | None = None
    options: list[FieldOption] = Field(default_factory=list)
    validation: FieldValidation = Field(default_factory=FieldValidation)
    sort_order: int = Field(default=0, ge=0)
    show_on_cover: bool = False
    # 不可变字段：仅用于侦测前端误传并返回 IMMUTABLE 错误（Q134/Q136）。
    key: str | None = None
    field_type: str | None = None


class FieldDetailOut(BaseModel):
    """字段完整定义（管理页列表 / 详情）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    key: str
    field_type: str
    description: str
    required: bool
    default_value: Any | None
    options: list[dict[str, Any]]
    validation_rules: dict[str, Any]
    sort_order: int
    show_on_cover: bool
    status: str
    created_at: datetime
    updated_at: datetime


class FieldOptionsOut(BaseModel):
    """字段选项数据（GET /procedure-fields/options）：active 字段 + 非归档选项，供表单渲染。"""

    id: str
    key: str
    name: str
    field_type: str
    required: bool
    options: list[dict[str, Any]]


class FieldStatusBatchIn(BaseModel):
    """批量改 status（POST /procedure-fields/update-status）。"""

    ids: list[str] = Field(min_length=1, max_length=100)
    status: FieldStatus


class FieldBatchDeleteIn(BaseModel):
    """批量软删（POST /procedure-fields/batch-delete，原子，≤100，Q325）。"""

    ids: list[str] = Field(min_length=1, max_length=100)


class FieldReorderIn(BaseModel):
    """重新排序（POST /procedure-fields/reorder）。"""

    ordered_ids: list[str] = Field(min_length=1, max_length=500)


class FieldStatusBatchResult(BaseModel):
    """批量改 status 结果。"""

    updated_ids: list[str]
