"""附件路由（api-specification §5.5 / Q113-Q120 / Q228 / Q371）。

两组路径：`/procedures/{id}/attachments`（list / upload）与 `/attachments/{id}`
（download / preview / PUT / DELETE）。下载一律强制 attachment（防 XSS，Q226），
预览仅白名单类型 inline（Q229）。
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.deps import RequestMeta, get_db, get_request_meta
from app.schemas.attachment import AttachmentOut, AttachmentUpdate
from app.services import attachment_service

router = APIRouter(prefix="/api/v1", tags=["attachments"])


def _content_disposition(disposition: str, file_name: str) -> str:
    """构造含 RFC 5987 编码的 Content-Disposition（兼容中文文件名）。"""
    ascii_fallback = file_name.encode("ascii", "ignore").decode() or "download"
    return f"{disposition}; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(file_name)}"


@router.get("/procedures/{procedure_id}/attachments", response_model=list[AttachmentOut])
def list_attachments(procedure_id: str, db: Session = Depends(get_db)) -> list[AttachmentOut]:
    rows = attachment_service.list_attachments(db, procedure_id)
    return [AttachmentOut.model_validate(r) for r in rows]


@router.post(
    "/procedures/{procedure_id}/attachments",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    procedure_id: str,
    file: UploadFile = File(...),
    description: str = Form(default=""),
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> AttachmentOut:
    data = await file.read()
    att = attachment_service.upload(
        db,
        procedure_id,
        data,
        file.filename or "",
        content_type=file.content_type,
        description=description,
        meta=meta,
    )
    db.commit()
    return AttachmentOut.model_validate(att)


@router.get("/attachments/{attachment_id}/download")
def download_attachment(attachment_id: str, db: Session = Depends(get_db)) -> Response:
    data, mime, file_name = attachment_service.download(db, attachment_id)
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": _content_disposition("attachment", file_name)},
    )


@router.get("/attachments/{attachment_id}/preview")
def preview_attachment(attachment_id: str, db: Session = Depends(get_db)) -> Response:
    data, mime = attachment_service.preview(db, attachment_id)
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": "inline"},
    )


@router.put("/attachments/{attachment_id}", response_model=AttachmentOut)
def update_attachment(
    attachment_id: str,
    payload: AttachmentUpdate,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> AttachmentOut:
    att = attachment_service.update(
        db,
        attachment_id,
        description=payload.description,
        sort_order=payload.sort_order,
        meta=meta,
    )
    db.commit()
    return AttachmentOut.model_validate(att)


@router.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(
    attachment_id: str,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    attachment_service.delete(db, attachment_id, meta)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
