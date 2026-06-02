"""附件 schema（通用多态 + procedure 兼容别名）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field


class AttachmentOut(BaseModel):
    """附件元数据（通用 list/upload 响应）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_type: str
    entity_id: str
    file_name: str
    mime_type: str
    size_bytes: int
    description: str
    sort_order: int
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def procedure_id(self) -> str | None:
        """兼容别名：procedure 附件返回 entity_id（前端 SOP 仍读 procedure_id）；其余实体为 None，避免误导。"""
        return self.entity_id if self.entity_type == "procedure" else None


class AttachmentUpdate(BaseModel):
    """修改附件元数据（仅 description / sort_order）。"""

    description: str | None = Field(default=None, max_length=2000)
    sort_order: int | None = Field(default=None, ge=0)
