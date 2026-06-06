"""表单字段配置 API（/api/v1/field-configurations/{form_key}）。

读：任意认证用户（前端表单渲染需要）；写：COMPANY_SETTINGS 权限。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_current_user, get_db, require_permission
from app.errors import not_found
from app.models.form_field_config import FormFieldConfig
from app.models.user import User
from app.schemas.form_field_config import FieldConfigItem, FieldConfigRead
from app.services import form_field_config_service as svc

router = APIRouter(prefix="/api/v1/field-configurations", tags=["field-configurations"])


def _check_form(form_key: str) -> None:
    if not svc.is_known_form(form_key):
        raise not_found("FORM_NOT_FOUND", "未知表单")


@router.get("/{form_key}", response_model=list[FieldConfigRead])
def get_config(
    form_key: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[FormFieldConfig]:
    _check_form(form_key)
    return svc.get_config(db, user.company_id, form_key)


@router.put("/{form_key}", response_model=list[FieldConfigRead])
def update_config(
    form_key: str,
    payload: list[FieldConfigItem],
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(permissions.COMPANY_SETTINGS)),
) -> list[FormFieldConfig]:
    _check_form(form_key)
    valid = svc.known_field_names(form_key)
    unknown = [item.field_name for item in payload if item.field_name not in valid]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"未知字段: {', '.join(unknown)}",
        )
    rows = svc.update_config(db, user.company_id, form_key, payload)
    db.commit()
    return rows
