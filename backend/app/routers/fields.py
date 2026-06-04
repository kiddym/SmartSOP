"""自定义字段路由（api-specification §5.7 / §38 / Q253-Q258 / Q325 / Q367）。

端点一览：
  GET    /procedure-fields               — 列表（field_type / status 过滤）
  GET    /procedure-fields/options       — active 字段 + 非归档选项（供表单渲染）
  GET    /procedure-fields/{id}          — 详情
  POST   /procedure-fields               — 创建（201）
  PUT    /procedure-fields/{id}          — 更新（key / field_type 不可改）
  DELETE /procedure-fields/{id}          — 软删（204）
  POST   /procedure-fields/update-status — 批量改 status
  POST   /procedure-fields/batch-delete  — 批量软删（原子，≤100）
  POST   /procedure-fields/reorder       — 重新排序

事务边界：service 层只 flush，本路由在每个写操作末尾 commit。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.billing.catalog import Feature
from app.deps import get_db, require_feature
from app.schemas.common import BatchDeleteResult
from app.schemas.field import (
    FieldBatchDeleteIn,
    FieldCreate,
    FieldDetailOut,
    FieldOptionsOut,
    FieldReorderIn,
    FieldStatusBatchIn,
    FieldStatusBatchResult,
    FieldUpdate,
)
from app.services import field_service

router = APIRouter(
    prefix="/api/v1",
    tags=["fields"],
    dependencies=[Depends(require_feature(Feature.sop))],
)


# --------------------------------------------------------------------------- #
# 读操作
# --------------------------------------------------------------------------- #


@router.get("/procedure-fields/options", response_model=list[FieldOptionsOut])
def get_field_options(db: Session = Depends(get_db)) -> list[FieldOptionsOut]:
    """返回 active 字段 + 非归档选项，供表单渲染（GET /procedure-fields/options）。

    注意：此路由必须在 /procedure-fields/{id} 之前注册，避免 'options' 被当成 id。
    """
    fields = field_service.options_data(db)
    return [
        FieldOptionsOut(
            id=f.id,
            key=f.key,
            name=f.name,
            field_type=f.field_type,
            required=f.required,
            options=field_service.active_options(f),
        )
        for f in fields
    ]


@router.get("/procedure-fields", response_model=list[FieldDetailOut])
def list_fields(
    field_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[FieldDetailOut]:
    """列表（GET /procedure-fields），支持 field_type / status 查询参数过滤。"""
    rows = field_service.list_fields(db, field_type=field_type, status=status)
    return [FieldDetailOut.model_validate(r) for r in rows]


@router.get("/procedure-fields/{field_id}", response_model=FieldDetailOut)
def get_field(field_id: str, db: Session = Depends(get_db)) -> FieldDetailOut:
    """详情（GET /procedure-fields/{id}）。"""
    field = field_service.get_or_404(db, field_id)
    return FieldDetailOut.model_validate(field)


# --------------------------------------------------------------------------- #
# 写操作
# --------------------------------------------------------------------------- #


@router.post(
    "/procedure-fields", response_model=FieldDetailOut, status_code=status.HTTP_201_CREATED
)
def create_field(payload: FieldCreate, db: Session = Depends(get_db)) -> FieldDetailOut:
    """创建自定义字段（POST /procedure-fields，201）。"""
    field = field_service.create(db, payload)
    db.commit()
    return FieldDetailOut.model_validate(field)


@router.put("/procedure-fields/{field_id}", response_model=FieldDetailOut)
def update_field(
    field_id: str, payload: FieldUpdate, db: Session = Depends(get_db)
) -> FieldDetailOut:
    """更新字段（PUT /procedure-fields/{id}）。key / field_type 不可改，分别返 400。"""
    field = field_service.update(db, field_id, payload)
    db.commit()
    return FieldDetailOut.model_validate(field)


@router.delete("/procedure-fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_field(field_id: str, db: Session = Depends(get_db)) -> Response:
    """软删字段（DELETE /procedure-fields/{id}，204）。"""
    field_service.delete(db, field_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- #
# 批量操作
# --------------------------------------------------------------------------- #


@router.post("/procedure-fields/update-status", response_model=FieldStatusBatchResult)
def batch_update_status(
    payload: FieldStatusBatchIn, db: Session = Depends(get_db)
) -> FieldStatusBatchResult:
    """批量改 status（POST /procedure-fields/update-status）。"""
    updated_ids = field_service.update_status(db, payload.ids, payload.status)
    db.commit()
    return FieldStatusBatchResult(updated_ids=updated_ids)


@router.post("/procedure-fields/batch-delete", response_model=BatchDeleteResult)
def batch_delete_fields(
    payload: FieldBatchDeleteIn, db: Session = Depends(get_db)
) -> BatchDeleteResult:
    """批量软删（POST /procedure-fields/batch-delete，原子，≤100，Q325）。

    任一 id 不存在则全部不删，returned.failed 列出缺失项。
    """
    result = field_service.batch_delete(db, payload.ids)
    if not result.failed:
        db.commit()
    return result


@router.post("/procedure-fields/reorder", response_model=list[FieldDetailOut])
def reorder_fields(payload: FieldReorderIn, db: Session = Depends(get_db)) -> list[FieldDetailOut]:
    """重新排序（POST /procedure-fields/reorder）。缺失 id 静默跳过，返回新顺序字段列表。"""
    fields = field_service.reorder(db, payload.ordered_ids)
    db.commit()
    return [FieldDetailOut.model_validate(f) for f in fields]
