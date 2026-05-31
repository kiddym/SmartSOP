"""采购单状态机（DRAFT→SUBMITTED→APPROVED/REJECTED/CANCELED 终态）。"""
from __future__ import annotations

import enum


class PurchaseOrderStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELED = "CANCELED"


# 合法状态转移（DRAFT/SUBMITTED 为非终态；APPROVED/REJECTED/CANCELED 为终态，无出边）。
ALLOWED_TRANSITIONS: dict[PurchaseOrderStatus, frozenset[PurchaseOrderStatus]] = {
    PurchaseOrderStatus.DRAFT: frozenset(
        {PurchaseOrderStatus.SUBMITTED, PurchaseOrderStatus.CANCELED}
    ),
    PurchaseOrderStatus.SUBMITTED: frozenset(
        {PurchaseOrderStatus.APPROVED, PurchaseOrderStatus.REJECTED,
         PurchaseOrderStatus.CANCELED}
    ),
    PurchaseOrderStatus.APPROVED: frozenset(),
    PurchaseOrderStatus.REJECTED: frozenset(),
    PurchaseOrderStatus.CANCELED: frozenset(),
}


def can_transition(src: PurchaseOrderStatus, dst: PurchaseOrderStatus) -> bool:
    return dst in ALLOWED_TRANSITIONS.get(src, frozenset())
