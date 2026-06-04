"""程序版本族路由（api-specification §版本管理）。

GET /procedure-groups/{group_id}/versions —— 同 group 版本列表（§22.2）。
DELETE /procedure-groups/{group_id} —— v1-DRAFT 整组硬删（Q177 / §22.13）。
Router 提交事务。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.billing.catalog import Feature
from app.deps import RequestMeta, get_db, get_request_meta, require_feature
from app.schemas.procedure import ProcedureDeleteIn, VersionListItem, VersionListOut
from app.services import version_flow_service

router = APIRouter(
    prefix="/api/v1/procedure-groups",
    tags=["procedure-groups"],
    dependencies=[Depends(require_feature(Feature.sop))],
)

_PREVIEW_CHARS = 100


@router.get("/{group_id}/versions", response_model=VersionListOut)
def list_versions(
    group_id: str,
    db: Session = Depends(get_db),
    count_only: bool = Query(default=False),
) -> VersionListOut:
    rows, count = version_flow_service.list_group_versions(db, group_id, count_only)
    items = [
        VersionListItem(
            id=r.id,
            version=r.version,
            status=r.status,
            is_current=r.is_current,
            version_update_notes=r.version_update_notes,
            version_update_notes_preview=r.version_update_notes[:_PREVIEW_CHARS],
            created_at=r.created_at,
            archived_at=r.archived_at,
        )
        for r in rows
    ]
    return VersionListOut(count=count, items=items)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: str,
    payload: ProcedureDeleteIn,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    version_flow_service.delete_group(db, group_id, payload.reason, meta)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
