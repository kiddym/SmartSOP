from app.models.work_order_status import (
    ALLOWED_TRANSITIONS,
    WorkOrderPriority,
    WorkOrderStatus,
    can_transition,
)


def test_status_values():
    assert {s.value for s in WorkOrderStatus} == {
        "OPEN",
        "IN_PROGRESS",
        "ON_HOLD",
        "COMPLETE",
        "CANCELED",
    }


def test_priority_values():
    assert {p.value for p in WorkOrderPriority} == {"NONE", "LOW", "MEDIUM", "HIGH"}


def test_legal_transitions():
    assert can_transition(WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS)
    assert can_transition(WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.ON_HOLD)
    assert can_transition(WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.COMPLETE)
    assert can_transition(WorkOrderStatus.ON_HOLD, WorkOrderStatus.IN_PROGRESS)
    assert can_transition(WorkOrderStatus.COMPLETE, WorkOrderStatus.IN_PROGRESS)  # 重开
    assert can_transition(WorkOrderStatus.OPEN, WorkOrderStatus.CANCELED)


def test_illegal_transitions():
    assert not can_transition(WorkOrderStatus.OPEN, WorkOrderStatus.COMPLETE)
    assert not can_transition(WorkOrderStatus.CANCELED, WorkOrderStatus.IN_PROGRESS)
    assert not can_transition(WorkOrderStatus.COMPLETE, WorkOrderStatus.ON_HOLD)
    assert not can_transition(WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.IN_PROGRESS)


def test_canceled_is_terminal():
    assert ALLOWED_TRANSITIONS[WorkOrderStatus.CANCELED] == frozenset()
