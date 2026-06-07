"""执行态步骤附件：宿主软删 + 注册 + 计数 + 完成校验。"""

from app.models.work_order_step_result import WorkOrderStepResult


def test_step_result_has_soft_delete_columns():
    # SoftDeleteMixin 提供 is_active / deleted_at
    cols = set(WorkOrderStepResult.__table__.columns.keys())
    assert "is_active" in cols
    assert "deleted_at" in cols


def test_registry_has_step_result():
    from app import permissions
    from app.services.attachment_entities import ENTITY_REGISTRY

    spec = ENTITY_REGISTRY["work_order_step_result"]
    assert spec.model is WorkOrderStepResult
    assert spec.scoped is True
    # 上传/删除步骤附件 = 执行动作，写权限用 WORK_ORDER_EXECUTE
    assert spec.edit_perm == permissions.WORK_ORDER_EXECUTE
    assert spec.view_perm == permissions.WORK_ORDER_VIEW


def test_count_active_helpers(db):
    from app.models.attachment import Attachment
    from app.services import attachment_service

    db.add(
        Attachment(
            entity_type="work_order_step_result",
            entity_id="sr1",
            file_name="a.png",
            mime_type="image/png",
            file_type="image",
            storage_path="x/a.png",
            size_bytes=1,
            company_id="c1",
        )
    )
    db.add(
        Attachment(
            entity_type="work_order_step_result",
            entity_id="sr1",
            file_name="b.png",
            mime_type="image/png",
            file_type="image",
            storage_path="x/b.png",
            size_bytes=1,
            company_id="c1",
        )
    )
    db.commit()
    assert attachment_service.count_active(db, "work_order_step_result", "sr1") == 2
    assert attachment_service.count_active(db, "work_order_step_result", "sr2") == 0
    m = attachment_service.count_active_by_entity_ids(db, "work_order_step_result", ["sr1", "sr2"])
    assert m == {"sr1": 2}


def test_required_upload_step_blocks_done_without_attachment(db):
    import pytest
    from fastapi import HTTPException

    from app import tenant
    from app.models.attachment import Attachment
    from app.models.company import Company
    from app.models.node import ProcedureNode
    from app.models.procedure import Procedure
    from app.models.work_order_status import WorkOrderStatus
    from app.schemas.work_order import StepResultUpdate, WorkOrderCreate, WorkOrderTransition
    from app.services import work_order_execution_service as exe
    from app.services import work_order_service as wos

    c = Company(name="ea", slug="ea")
    db.add(c)
    db.commit()
    tenant.set_current_company_id(c.id)
    p = Procedure(
        procedure_group_id="g",
        folder_id="f",
        code="S",
        name="P",
        version=1,
        level_of_use="reference",
        status="PUBLISHED",
        company_id=c.id,
    )
    db.add(p)
    db.flush()
    db.add(
        ProcedureNode(
            procedure_id=p.id,
            sort_order=1,
            heading_level=None,
            kind="step",
            body="传图",
            code="S1",
            input_schema={"type": "UPLOAD", "required": True},
            company_id=c.id,
        )
    )
    db.commit()
    wo = wos.create_work_order(db, WorkOrderCreate(title="T"), c.id, actor_user_id=None)
    exe.attach_procedure(db, wo, p.id, c.id, actor_user_id=None)
    wos.transition(
        db, wo, WorkOrderTransition(to_status=WorkOrderStatus.IN_PROGRESS), c.id, actor_user_id=None
    )
    sr = exe.list_step_results(db, wo.id)[0]
    # 无附件 → is_done=True 应 422
    with pytest.raises(HTTPException) as ei:
        exe.update_step(db, wo, sr, StepResultUpdate(is_done=True), c.id, actor_user_id=None)
    assert ei.value.status_code == 422
    # 加一个该步骤附件后可完成
    db.add(
        Attachment(
            entity_type="work_order_step_result",
            entity_id=sr.id,
            file_name="a.png",
            mime_type="image/png",
            file_type="image",
            storage_path="x/a.png",
            size_bytes=1,
            company_id=c.id,
        )
    )
    db.commit()
    exe.update_step(db, wo, sr, StepResultUpdate(is_done=True), c.id, actor_user_id=None)
    assert sr.is_done is True
