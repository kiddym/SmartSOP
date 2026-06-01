import pytest
from pydantic import ValidationError

from app.models.work_order_status import WorkOrderPriority, WorkOrderStatus
from app.schemas.work_order import (
    StepResultUpdate,
    WorkOrderCreate,
    WorkOrderTransition,
    WorkOrderUpdate,
)


def test_create_defaults():
    c = WorkOrderCreate(title="换油")
    assert c.priority == WorkOrderPriority.NONE
    assert c.description == ""
    assert c.assignee_ids == []
    assert c.procedure_id is None


def test_create_requires_title():
    with pytest.raises(ValidationError):
        WorkOrderCreate(title="")


def test_transition_parses_status():
    t = WorkOrderTransition(to_status="IN_PROGRESS")
    assert t.to_status == WorkOrderStatus.IN_PROGRESS


def test_update_is_partial():
    u = WorkOrderUpdate()
    assert u.model_dump(exclude_unset=True) == {}


def test_step_result_update_partial():
    s = StepResultUpdate(is_done=True)
    data = s.model_dump(exclude_unset=True)
    assert data == {"is_done": True}
