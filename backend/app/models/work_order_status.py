"""工单状态机与优先级枚举 + 合法转移表（Phase 1B）。"""

from __future__ import annotations

import enum


class WorkOrderStatus(enum.StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    ON_HOLD = "ON_HOLD"
    COMPLETE = "COMPLETE"
    CANCELED = "CANCELED"


class WorkOrderPriority(enum.StrEnum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# 合法状态转移（CANCELED 为终态；COMPLETE 仅能重开回 IN_PROGRESS）。
ALLOWED_TRANSITIONS: dict[WorkOrderStatus, frozenset[WorkOrderStatus]] = {
    WorkOrderStatus.OPEN: frozenset({WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.CANCELED}),
    WorkOrderStatus.IN_PROGRESS: frozenset(
        {WorkOrderStatus.ON_HOLD, WorkOrderStatus.COMPLETE, WorkOrderStatus.CANCELED}
    ),
    WorkOrderStatus.ON_HOLD: frozenset({WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.CANCELED}),
    WorkOrderStatus.COMPLETE: frozenset({WorkOrderStatus.IN_PROGRESS}),
    WorkOrderStatus.CANCELED: frozenset(),
}


def can_transition(src: WorkOrderStatus, dst: WorkOrderStatus) -> bool:
    return dst in ALLOWED_TRANSITIONS.get(src, frozenset())


class WorkOrderRelationType(enum.StrEnum):
    DUPLICATE = "DUPLICATE"
    RELATED = "RELATED"
    SPLIT = "SPLIT"
    BLOCKS = "BLOCKS"


SYMMETRIC_RELATION_TYPES: frozenset[WorkOrderRelationType] = frozenset(
    {WorkOrderRelationType.DUPLICATE, WorkOrderRelationType.RELATED}
)
