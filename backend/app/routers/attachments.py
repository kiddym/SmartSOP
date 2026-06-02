"""附件路由：通用 /attachments（认证 + 动态 RBAC）+ procedure 别名（无认证，兼容）。"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.deps import RequestMeta, get_current_user, get_db, get_request_meta
from app.models.user import User
from app.schemas.attachment import AttachmentOut, AttachmentUpdate
from app.services import attachment_service

router = APIRouter(prefix="/api/v1", tags=["attachments"])


def _content_disposition(disposition: str, file_name: str) -> str:
    """构造含 RFC 5987 编码的 Content-Disposition（兼容中文文件名，下载强制 attachment 防 XSS）。"""
    ascii_fallback = file_name.encode("ascii", "ignore").decode() or "download"
    return f"{disposition}; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(file_name)}"


# --------------------------------------------------------------------------- #
# 通用 /attachments（认证 + 动态 RBAC）
# --------------------------------------------------------------------------- #
@router.get("/attachments", response_model=list[AttachmentOut])
def list_attachments_generic(
    entity_type: str = Query(...),
    entity_id: str = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AttachmentOut]:
    rows = attachment_service.list_for(db, user, entity_type, entity_id)
    return [AttachmentOut.model_validate(r) for r in rows]


@router.post(
    "/attachments", response_model=AttachmentOut, status_code=status.HTTP_201_CREATED
)
async def upload_attachment_generic(
    entity_type: str = Form(...),
    entity_id: str = Form(...),
    file: UploadFile = File(...),
    description: str = Form(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    meta: RequestMeta = Depends(get_request_meta),
) -> AttachmentOut:
    data = await file.read()
    att = attachment_service.upload_for(
        db, user, entity_type, entity_id, data, file.filename or "",
        content_type=file.content_type, description=description, meta=meta,
    )
    db.commit()
    return AttachmentOut.model_validate(att)


@router.get("/attachments/{attachment_id}/download")
def download_attachment(
    attachment_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    data, mime, file_name = attachment_service.download_for(db, user, attachment_id)
    return Response(
        content=data, media_type=mime,
        headers={"Content-Disposition": _content_disposition("attachment", file_name)},
    )


@router.get("/attachments/{attachment_id}/preview")
def preview_attachment(
    attachment_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    data, mime = attachment_service.preview_for(db, user, attachment_id)
    return Response(content=data, media_type=mime, headers={"Content-Disposition": "inline"})


@router.put("/attachments/{attachment_id}", response_model=AttachmentOut)
def update_attachment(
    attachment_id: str,
    payload: AttachmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    meta: RequestMeta = Depends(get_request_meta),
) -> AttachmentOut:
    att = attachment_service.update_for(
        db, user, attachment_id,
        description=payload.description, sort_order=payload.sort_order, meta=meta,
    )
    db.commit()
    return AttachmentOut.model_validate(att)


@router.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(
    attachment_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    attachment_service.delete_for(db, user, attachment_id, meta=meta)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- #
# procedure 兼容别名（无认证，行为同既有；前端 SOP 零改）
# --------------------------------------------------------------------------- #
@router.get("/procedures/{procedure_id}/attachments", response_model=list[AttachmentOut])
def list_procedure_attachments(
    procedure_id: str, db: Session = Depends(get_db)
) -> list[AttachmentOut]:
    rows = attachment_service.list_for(db, None, "procedure", procedure_id)
    return [AttachmentOut.model_validate(r) for r in rows]


@router.post(
    "/procedures/{procedure_id}/attachments",
    response_model=list[AttachmentOut],
    status_code=status.HTTP_201_CREATED,
)
async def upload_procedure_attachments(
    procedure_id: str,
    files: list[UploadFile] = File(...),
    description: str = Form(default=""),
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> list[AttachmentOut]:
    created = []
    for f in files:
        data = await f.read()
        att = attachment_service.upload_for(
            db, None, "procedure", procedure_id, data, f.filename or "",
            content_type=f.content_type, description=description, meta=meta,
        )
        created.append(att)
    db.commit()
    return [AttachmentOut.model_validate(a) for a in created]
