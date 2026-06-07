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
