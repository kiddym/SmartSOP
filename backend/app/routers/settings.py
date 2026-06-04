"""全局设置路由（api-specification §5.8）。

端点：
  GET  /api/v1/settings         — 获取单例设置
  GET  /api/v1/settings/current — 同上 alias
  PUT  /api/v1/settings         — 更新（必须带 If-Match，写审计日志）
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.billing.catalog import Feature
from app.deps import RequestMeta, get_db, get_request_meta, require_feature
from app.schemas.settings import SettingsOut, SettingsUpdate
from app.services import settings_service
from app.services.optimistic_lock import ensure_if_match, verify_revision

router = APIRouter(
    prefix="/api/v1",
    tags=["settings"],
    dependencies=[Depends(require_feature(Feature.sop))],
)


@router.get("/settings", response_model=SettingsOut)
@router.get("/settings/current", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db)) -> SettingsOut:
    """获取全局设置单例（§5.8 GET /settings 及 /settings/current alias）。"""
    s = settings_service.get_singleton(db)
    return SettingsOut.model_validate(s)


@router.put("/settings", response_model=SettingsOut)
def update_settings(
    payload: SettingsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> SettingsOut:
    """更新全局设置（§5.8 PUT /settings）。

    必须携带 If-Match 标头（乐观锁）；更新成功后写 settings_update 审计日志。
    """
    expected = ensure_if_match(request.headers.get("if-match"))
    s = settings_service.get_singleton(db)
    verify_revision(s.revision, expected)
    settings_service.update(db, s, payload, meta)
    db.commit()
    db.refresh(s)
    return SettingsOut.model_validate(s)
