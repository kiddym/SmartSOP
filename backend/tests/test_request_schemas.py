import pytest
from pydantic import ValidationError

from app.models.work_order_status import WorkOrderPriority
from app.schemas.request import (
    RequestApprove,
    RequestCreate,
    RequestReason,
    RequestUpdate,
)


def test_create_defaults():
    c = RequestCreate(title="漏水")
    assert c.priority == WorkOrderPriority.NONE
    assert c.description == ""
    assert c.asset_id is None


def test_create_requires_title():
    with pytest.raises(ValidationError):
        RequestCreate(title="")


def test_update_is_partial():
    u = RequestUpdate()
    assert u.model_dump(exclude_unset=True) == {}


def test_approve_defaults_empty():
    a = RequestApprove()
    assert a.note == ""
    assert a.assignee_ids == []
    assert a.team_ids == []
    assert a.procedure_id is None
    assert a.primary_user_id is None


def test_reason_requires_nonempty():
    with pytest.raises(ValidationError):
        RequestReason(reason="")
