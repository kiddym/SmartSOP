from app.models.company import Company
from app.models.work_order import WorkOrder
from app.models.work_order_status import WorkOrderPriority, WorkOrderStatus


def test_work_order_defaults(db):
    c = Company(name="Acme", slug="acme")
    db.add(c)
    db.commit()
    wo = WorkOrder(custom_id="WO000001", title="换轴承", company_id=c.id)
    db.add(wo)
    db.commit()
    db.refresh(wo)
    assert wo.status == WorkOrderStatus.OPEN
    assert wo.priority == WorkOrderPriority.NONE
    assert wo.is_active is True
    assert wo.procedure_id is None
    assert wo.id is not None and len(wo.id) == 36


def test_step_result_and_activity_importable(db):
    from app.models.work_order_activity import WorkOrderActivity
    from app.models.work_order_step_result import WorkOrderStepResult

    c = Company(name="Acme", slug="acme")
    db.add(c)
    db.commit()
    wo = WorkOrder(custom_id="WO000001", title="t", company_id=c.id)
    db.add(wo)
    db.commit()
    sr = WorkOrderStepResult(
        work_order_id=wo.id, node_id="n1", node_code="S1", node_sort_order=0, company_id=c.id
    )
    act = WorkOrderActivity(
        work_order_id=wo.id, activity_type="COMMENT", comment="hi", company_id=c.id
    )
    db.add_all([sr, act])
    db.commit()
    assert sr.is_done is False
    assert act.activity_type == "COMMENT"
