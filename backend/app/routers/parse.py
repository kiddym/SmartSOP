"""上传 / 解析路由（api-specification §5.3）。

POST /uploads（multipart）→ upload_token；GET /uploads/{token}/media/{filename}
临时图服务（review 预览，Q342）；GET /parse/methods；POST /parse。
解析不落库（parse→import 两步式，§9.1）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.orm import Session

from app.billing.catalog import Feature
from app.deps import get_db, require_feature
from app.schemas.parse import ParseMethodOut, ParseRequest, ParseResponse, UploadResult
from app.services import parse_service, upload_service

router = APIRouter(
    prefix="/api/v1",
    tags=["parse"],
    dependencies=[Depends(require_feature(Feature.sop))],
)


@router.post("/uploads", response_model=UploadResult)
async def upload(file: UploadFile = File(...)) -> UploadResult:
    data = await file.read()
    return upload_service.save_upload(data, file.filename or "")


@router.get("/uploads/{token}/media/{filename}")
def serve_temp_media(token: str, filename: str) -> Response:
    data, mime = upload_service.serve_media(token, filename)
    return Response(content=data, media_type=mime)


@router.get("/parse/methods", response_model=list[ParseMethodOut])
def parse_methods() -> list[ParseMethodOut]:
    return parse_service.list_methods()


@router.post("/parse", response_model=ParseResponse)
def parse(payload: ParseRequest, db: Session = Depends(get_db)) -> ParseResponse:
    return parse_service.parse(payload.upload_token, payload.parse_mode, db=db)
