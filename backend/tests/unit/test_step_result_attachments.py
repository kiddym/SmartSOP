"""执行态步骤附件：宿主软删 + 注册 + 计数 + 完成校验。"""

from app.models.work_order_step_result import WorkOrderStepResult


def test_step_result_has_soft_delete_columns():
    # SoftDeleteMixin 提供 is_active / deleted_at
    cols = set(WorkOrderStepResult.__table__.columns.keys())
    assert "is_active" in cols
    assert "deleted_at" in cols
