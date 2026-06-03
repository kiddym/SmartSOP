"""权限目录（只读）：分组 + 中文 label，供前端角色表单渲染。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app import permissions
from app.deps import require_permission
from app.models.user import User
from app.permission_labels import PERMISSION_GROUPS, PERMISSION_LABELS

router = APIRouter(prefix="/api/v1/permissions", tags=["permissions"])


@router.get("")
def list_permissions(
    current_user: User = Depends(require_permission(permissions.ROLE_VIEW)),
) -> list[dict[str, Any]]:
    return [
        {
            "group": group,
            "permissions": [{"code": c, "label": PERMISSION_LABELS[c]} for c in codes],
        }
        for group, codes in PERMISSION_GROUPS
    ]
