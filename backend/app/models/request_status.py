"""请求状态机枚举 + 合法转移表（Phase 2A）。"""

from __future__ import annotations

import enum


class RequestStatus(enum.StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELED = "CANCELED"


# 合法状态转移（PENDING 是唯一非终态；审批/拒绝/取消都从 PENDING 出发到终态）。
ALLOWED_TRANSITIONS: dict[RequestStatus, frozenset[RequestStatus]] = {
    RequestStatus.PENDING: frozenset(
        {RequestStatus.APPROVED, RequestStatus.REJECTED, RequestStatus.CANCELED}
    ),
    RequestStatus.APPROVED: frozenset(),
    RequestStatus.REJECTED: frozenset(),
    RequestStatus.CANCELED: frozenset(),
}


def can_transition(src: RequestStatus, dst: RequestStatus) -> bool:
    return dst in ALLOWED_TRANSITIONS.get(src, frozenset())
