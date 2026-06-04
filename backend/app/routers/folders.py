"""文件夹路由（api-specification §5.1）。

静态子路径（tree / options / check-*）须在 `/{folder_id}` 之前声明，避免被路径参数捕获。
写操作由本层提交事务（service 仅 flush）。文件夹**不走乐观锁**，无 If-Match。
"""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.billing.catalog import Feature
from app.deps import RequestMeta, get_db, get_request_meta, require_feature
from app.schemas.common import Page
from app.schemas.folder import (
    BatchDeleteIn,
    BatchDeleteResult,
    CheckResult,
    FolderCreate,
    FolderOption,
    FolderOut,
    FolderTreeNode,
    FolderUpdate,
)
from app.services import folder_service

router = APIRouter(
    prefix="/api/v1/folders",
    tags=["folders"],
    dependencies=[Depends(require_feature(Feature.sop))],
)


@router.get("", response_model=Page[FolderOut])
def list_folders(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = "-created_at",
    search: str | None = None,
) -> Page[FolderOut]:
    rows, total = folder_service.list_folders(
        db, page=page, page_size=page_size, sort=sort, search=search
    )
    return Page[FolderOut](
        items=[FolderOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.get("/tree", response_model=list[FolderTreeNode])
def folder_tree(db: Session = Depends(get_db)) -> list[FolderTreeNode]:
    return [FolderTreeNode.model_validate(n) for n in folder_service.get_tree(db)]


@router.get("/options", response_model=list[FolderOption])
def folder_options(db: Session = Depends(get_db)) -> list[FolderOption]:
    return [FolderOption.model_validate(f) for f in folder_service.list_options(db)]


@router.get("/check-name", response_model=CheckResult)
def check_name(
    name: str = Query(..., min_length=1, max_length=100),
    parent_id: str | None = None,
    exclude_id: str | None = None,
    db: Session = Depends(get_db),
) -> CheckResult:
    available = folder_service.check_name(db, parent_id, name, exclude_id=exclude_id)
    return CheckResult(
        available=available,
        message=None if available else "同一父目录下已存在该名称的文件夹",
    )


@router.get("/check-prefix", response_model=CheckResult)
def check_prefix(
    prefix: str = Query(..., max_length=20),
    exclude_id: str | None = None,
    db: Session = Depends(get_db),
) -> CheckResult:
    available = folder_service.check_prefix(db, prefix, exclude_id=exclude_id)
    return CheckResult(
        available=available,
        message=None if available else "前缀已被占用，含历史程序使用过的前缀",
    )


@router.post("/batch-delete", response_model=BatchDeleteResult)
def batch_delete(
    payload: BatchDeleteIn,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> BatchDeleteResult:
    result = folder_service.batch_delete(db, payload.ids, meta)
    db.commit()
    return result


@router.get("/{folder_id}", response_model=FolderOut)
def get_folder(folder_id: str, db: Session = Depends(get_db)) -> FolderOut:
    return FolderOut.model_validate(folder_service.get_folder(db, folder_id))


@router.post("", response_model=FolderOut, status_code=status.HTTP_201_CREATED)
def create_folder(
    payload: FolderCreate,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> FolderOut:
    folder = folder_service.create_folder(db, payload, meta)
    db.commit()
    return FolderOut.model_validate(folder)


@router.put("/{folder_id}", response_model=FolderOut)
def update_folder(
    folder_id: str,
    payload: FolderUpdate,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> FolderOut:
    folder = folder_service.update_folder(db, folder_id, payload, meta)
    db.commit()
    return FolderOut.model_validate(folder)


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(
    folder_id: str,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    folder_service.delete_folder(db, folder_id, meta)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
