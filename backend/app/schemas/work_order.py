"""工单 schema（Phase 1B）。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.work_order_status import WorkOrderPriority, WorkOrderRelationType, WorkOrderStatus


class WorkOrderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    priority: WorkOrderPriority = WorkOrderPriority.NONE
    due_date: date | None = None
    asset_id: str | None = None
    location_id: str | None = None
    primary_user_id: str | None = None
    assignee_ids: list[str] = []
    team_ids: list[str] = []
    category_id: str | None = None
    # 建单时可选立即挂接已发布 SOP
    procedure_id: str | None = None
    # 完成是否强制签名
    required_signature: bool = False


class WorkOrderUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    priority: WorkOrderPriority | None = None
    due_date: date | None = None
    asset_id: str | None = None
    location_id: str | None = None
    primary_user_id: str | None = None
    category_id: str | None = None
    required_signature: bool | None = None


class WorkOrderTransition(BaseModel):
    to_status: WorkOrderStatus
    note: str = ""
    # 完成转移时可携带签名存档；其他转移忽略
    signature_url: str | None = Field(default=None, max_length=512)


class AssigneesSet(BaseModel):
    user_ids: list[str] = []


class TeamsSet(BaseModel):
    team_ids: list[str] = []


class WorkOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    custom_id: str
    title: str
    description: str
    status: WorkOrderStatus
    priority: WorkOrderPriority
    due_date: date | None = None
    asset_id: str | None = None
    location_id: str | None = None
    primary_user_id: str | None = None
    procedure_id: str | None = None
    procedure_group_id: str | None = None
    completed_at: datetime | None = None
    category_id: str | None = None
    created_by_user_id: str | None = None
    completed_by_user_id: str | None = None
    feedback: str | None = None
    urgent: bool = False
    estimated_duration: int | None = None
    estimated_start_date: date | None = None
    first_responded_at: datetime | None = None
    archived: bool = False
    is_compliant: bool | None = None
    signature_url: str | None = None
    required_signature: bool = False
    assignee_ids: list[str] = []
    team_ids: list[str] = []
    can_be_edited: bool = False


class CalendarEvent(BaseModel):
    """日历事件：聚合工单（按 due_date）与启用 PM（按 next_due_date）。

    work_order 事件携带 status/priority 供前端按状态/优先级上色并跳详情；
    pm 事件 status/priority 缺省（PM 无对应概念）。
    """

    type: Literal["work_order", "pm"]
    id: str
    custom_id: str | None = None
    title: str
    date: date
    status: WorkOrderStatus | None = None
    priority: WorkOrderPriority | None = None


class StepResultUpdate(BaseModel):
    response: dict[str, Any] | None = None
    is_done: bool | None = None
    notes: str | None = None


class StepResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    node_id: str
    node_code: str
    node_sort_order: int
    input_schema: dict[str, Any] = {}
    response: dict[str, Any] = {}
    is_done: bool
    done_by_user_id: str | None = None
    done_at: datetime | None = None
    notes: str


class OutlineNode(BaseModel):
    node_id: str
    heading_level: int | None = None
    kind: str
    body: str
    code: str
    sort_order: int


class ProcedureRef(BaseModel):
    id: str
    group_id: str | None = None
    code: str
    name: str
    version: int


class ExecutionView(BaseModel):
    procedure: ProcedureRef | None = None
    outline: list[OutlineNode] = []
    steps: list[StepResultRead] = []


class AttachProcedure(BaseModel):
    procedure_id: str


class CommentCreate(BaseModel):
    comment: str = Field(min_length=1)


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    activity_type: str
    actor_user_id: str | None = None
    from_status: str | None = None
    to_status: str | None = None
    comment: str
    created_at: datetime


class WorkOrderRelationCreate(BaseModel):
    target_work_order_id: str
    relation_type: WorkOrderRelationType


class WorkOrderRelationRead(BaseModel):
    id: str
    relation_type: WorkOrderRelationType
    direction: Literal["symmetric", "outgoing", "incoming"]
    related_work_order_id: str
    related_custom_id: str | None = None
    related_title: str | None = None
    related_status: WorkOrderStatus | None = None
