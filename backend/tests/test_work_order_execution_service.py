import pytest
from fastapi import HTTPException

from app import tenant
from app.models.company import Company
from app.models.node import ProcedureNode
from app.models.procedure import Procedure
from app.models.work_order_status import WorkOrderStatus
from app.schemas.work_order import (
    StepResultUpdate, WorkOrderCreate, WorkOrderTransition,
)
from app.services import work_order_execution_service as exe
from app.services import work_order_service as wos


def _company(db, slug):
    c = Company(name=slug, slug=slug)
    db.add(c)
    db.commit()
    return c


def _published_procedure(db, company_id, *, with_required=False):
    """建一个 PUBLISHED 程序：1 章节 + 2 步骤（第二步可带 required 字段）。"""
    p = Procedure(
        procedure_group_id="grp-1", folder_id="f1", code="SOP-1", name="换泵程序",
        version=1, level_of_use="reference", status="PUBLISHED", company_id=company_id,
    )
    db.add(p)
    db.flush()
    chapter = ProcedureNode(
        procedure_id=p.id, sort_order=0, heading_level=1, kind="node",
        body="准备阶段", code="C1", company_id=company_id,
    )
    step1 = ProcedureNode(
        procedure_id=p.id, sort_order=1, heading_level=None, kind="step",
        body="关闭阀门", code="S1", input_schema={}, company_id=company_id,
    )
    schema2 = {"required": ["torque"]} if with_required else {}
    step2 = ProcedureNode(
        procedure_id=p.id, sort_order=2, heading_level=None, kind="step",
        body="紧固螺栓", code="S2", input_schema=schema2, company_id=company_id,
    )
    db.add_all([chapter, step1, step2])
    db.commit()
    return p


def test_attach_generates_step_rows_only(db):
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    p = _published_procedure(db, c.id)
    wo = wos.create_work_order(db, WorkOrderCreate(title="t"), c.id, None)
    exe.attach_procedure(db, wo, p.id, c.id, actor_user_id=None)
    view = exe.execution_view(db, wo)
    assert view["procedure"]["code"] == "SOP-1"
    assert len(view["outline"]) == 3          # 章节 + 2 步骤都在 outline
    assert len(view["steps"]) == 2            # 仅 step 生成执行行
    assert {s["node_code"] for s in view["steps"]} == {"S1", "S2"}


def test_attach_requires_published(db):
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    p = _published_procedure(db, c.id)
    p.status = "DRAFT"
    db.commit()
    wo = wos.create_work_order(db, WorkOrderCreate(title="t"), c.id, None)
    with pytest.raises(HTTPException) as exc:
        exe.attach_procedure(db, wo, p.id, c.id, actor_user_id=None)
    assert exc.value.status_code == 400


def test_double_attach_conflict(db):
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    p = _published_procedure(db, c.id)
    wo = wos.create_work_order(db, WorkOrderCreate(title="t"), c.id, None)
    exe.attach_procedure(db, wo, p.id, c.id, None)
    with pytest.raises(HTTPException) as exc:
        exe.attach_procedure(db, wo, p.id, c.id, None)
    assert exc.value.status_code == 409


def test_fill_step_requires_in_progress(db):
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    p = _published_procedure(db, c.id)
    wo = wos.create_work_order(db, WorkOrderCreate(title="t"), c.id, None)
    exe.attach_procedure(db, wo, p.id, c.id, None)
    sr = exe.list_step_results(db, wo.id)[0]
    with pytest.raises(HTTPException) as exc:  # OPEN 不可填
        exe.update_step(db, wo, sr, StepResultUpdate(is_done=True), c.id, actor_user_id=None)
    assert exc.value.status_code == 400


def test_required_field_missing_blocks_done(db):
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    p = _published_procedure(db, c.id, with_required=True)
    wo = wos.create_work_order(db, WorkOrderCreate(title="t"), c.id, None)
    exe.attach_procedure(db, wo, p.id, c.id, None)
    wos.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.IN_PROGRESS), c.id, None)
    s2 = [s for s in exe.list_step_results(db, wo.id) if s.node_code == "S2"][0]
    with pytest.raises(HTTPException) as exc:  # 缺 torque
        exe.update_step(db, wo, s2, StepResultUpdate(is_done=True), c.id, actor_user_id=None)
    assert exc.value.status_code == 400
    # 填上后可完成
    exe.update_step(db, wo, s2, StepResultUpdate(response={"torque": 40}, is_done=True),
                    c.id, actor_user_id="u1")
    db.refresh(s2)
    assert s2.is_done is True and s2.done_by_user_id == "u1"


def test_complete_requires_all_steps_done(db):
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    p = _published_procedure(db, c.id)
    wo = wos.create_work_order(db, WorkOrderCreate(title="t"), c.id, None)
    exe.attach_procedure(db, wo, p.id, c.id, None)
    wos.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.IN_PROGRESS), c.id, None)
    with pytest.raises(HTTPException) as exc:  # 有未完成 step
        wos.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.COMPLETE), c.id, None)
    assert exc.value.status_code == 400
    for sr in exe.list_step_results(db, wo.id):
        exe.update_step(db, wo, sr, StepResultUpdate(is_done=True), c.id, actor_user_id=None)
    wos.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.COMPLETE), c.id, None)
    assert wo.status == WorkOrderStatus.COMPLETE


def test_no_sop_work_order_completes_freely(db):
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    wo = wos.create_work_order(db, WorkOrderCreate(title="t"), c.id, None)
    wos.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.IN_PROGRESS), c.id, None)
    wos.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.COMPLETE), c.id, None)
    assert wo.status == WorkOrderStatus.COMPLETE


def test_detach_removes_rows_and_blocked_after_complete(db):
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    p = _published_procedure(db, c.id)
    wo = wos.create_work_order(db, WorkOrderCreate(title="t"), c.id, None)
    exe.attach_procedure(db, wo, p.id, c.id, None)
    assert len(exe.list_step_results(db, wo.id)) == 2
    exe.detach_procedure(db, wo, c.id)
    assert exe.list_step_results(db, wo.id) == []
    assert wo.procedure_id is None
    # 完成态禁止 detach
    exe.attach_procedure(db, wo, p.id, c.id, None)
    wos.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.IN_PROGRESS), c.id, None)
    for sr in exe.list_step_results(db, wo.id):
        exe.update_step(db, wo, sr, StepResultUpdate(is_done=True), c.id, None)
    wos.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.COMPLETE), c.id, None)
    with pytest.raises(HTTPException) as exc:
        exe.detach_procedure(db, wo, c.id)
    assert exc.value.status_code == 400


def test_required_field_zero_value_counts_as_present(db):
    """falsy 但有效的填值（0 / False）不应被判为必填缺失。"""
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    p = _published_procedure(db, c.id, with_required=True)
    wo = wos.create_work_order(db, WorkOrderCreate(title="t"), c.id, None)
    exe.attach_procedure(db, wo, p.id, c.id, None)
    wos.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.IN_PROGRESS), c.id, None)
    s2 = [s for s in exe.list_step_results(db, wo.id) if s.node_code == "S2"][0]
    # torque=0 是有效读数，不应触发 STEP_REQUIRED_MISSING
    exe.update_step(db, wo, s2, StepResultUpdate(response={"torque": 0}, is_done=True),
                    c.id, actor_user_id="u1")
    db.refresh(s2)
    assert s2.is_done is True


def test_set_assignees_writes_assign_activity(db):
    """spec §3.4：set_assignees/set_teams 写 ASSIGN 时间线活动。"""
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    wo = wos.create_work_order(db, WorkOrderCreate(title="t"), c.id, None)
    wos.set_assignees(db, wo, [], c.id, actor_user_id="u7")
    wos.set_teams(db, wo, [], c.id, actor_user_id="u7")
    acts = wos.list_activities(db, wo.id)
    assign_acts = [a for a in acts if a.activity_type == "ASSIGN"]
    assert len(assign_acts) == 2
    assert all(a.actor_user_id == "u7" for a in assign_acts)


def test_step_result_unique_node_constraint(db):
    """同工单同节点唯一：DB 约束兜底（attach 已清旧建新，此处直插重复行验证约束）。"""
    from sqlalchemy.exc import IntegrityError

    from app.models.work_order_step_result import WorkOrderStepResult
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    wo = wos.create_work_order(db, WorkOrderCreate(title="t"), c.id, None)
    db.add(WorkOrderStepResult(work_order_id=wo.id, node_id="n1", node_code="X",
                               node_sort_order=0, response={}, company_id=c.id))
    db.commit()
    db.add(WorkOrderStepResult(work_order_id=wo.id, node_id="n1", node_code="X",
                               node_sort_order=0, response={}, company_id=c.id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_version_pinning_immutable(db):
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    p = _published_procedure(db, c.id)
    wo = wos.create_work_order(db, WorkOrderCreate(title="t"), c.id, None)
    exe.attach_procedure(db, wo, p.id, c.id, None)
    before = len(exe.execution_view(db, wo)["steps"])
    # 程序新增一个 step（模拟编辑/新版）
    db.add(ProcedureNode(procedure_id=p.id, sort_order=3, heading_level=None, kind="step",
                         body="新步骤", code="S3", input_schema={}, company_id=c.id))
    db.commit()
    after = len(exe.list_step_results(db, wo.id))
    assert after == before  # 已生成的执行行不变（钉定不可变）
