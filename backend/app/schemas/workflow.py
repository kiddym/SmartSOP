"""Workflow CRUD schema：conditions/actions 用 pydantic 校验枚举。"""

from __future__ import annotations

import enum

from pydantic import BaseModel, ConfigDict, Field


class WorkflowTrigger(enum.StrEnum):
    WORK_ORDER_CREATED = "WORK_ORDER_CREATED"
    WORK_ORDER_STATUS_CHANGED = "WORK_ORDER_STATUS_CHANGED"


class ConditionField(enum.StrEnum):
    STATUS = "status"
    PRIORITY = "priority"
    CATEGORY_ID = "category_id"


class ConditionOp(enum.StrEnum):
    EQ = "eq"
    NE = "ne"


class ActionType(enum.StrEnum):
    SET_PRIORITY = "set_priority"
    SET_STATUS = "set_status"
    SET_CATEGORY = "set_category"
    SET_ASSIGNEE_USER = "set_assignee_user"
    SET_TEAM = "set_team"


class WorkflowCondition(BaseModel):
    field: ConditionField
    op: ConditionOp
    value: str | None = None


class WorkflowAction(BaseModel):
    type: ActionType
    value: str | None = None


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    enabled: bool = True
    trigger: WorkflowTrigger
    conditions: list[WorkflowCondition] = Field(default_factory=list)
    actions: list[WorkflowAction] = Field(default_factory=list)


class WorkflowUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    enabled: bool | None = None
    trigger: WorkflowTrigger | None = None
    conditions: list[WorkflowCondition] | None = None
    actions: list[WorkflowAction] | None = None


class WorkflowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    enabled: bool
    trigger: WorkflowTrigger
    conditions: list[WorkflowCondition]
    actions: list[WorkflowAction]
