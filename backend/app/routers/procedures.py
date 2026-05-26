"""程序路由（api-specification §5.2）。Phase 3 = 基础 CRUD + 多版本骨架。

静态子路径（library / batch-*）须在 `/{procedure_id}` 之前声明。
PUT 与 transition 走乐观锁（If-Match → revision），其余写操作不需 If-Match。
"""

from __future__ import annotations

import math
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Header, Query, Response, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.deps import RequestMeta, get_db, get_request_meta
from app.schemas.common import BatchDeleteResult, Page
from app.schemas.node import ApplyMarksResult
from app.schemas.parse import AssetUploadResult, ImportRequest
from app.schemas.pdf import PdfLayoutOut
from app.schemas.procedure import (
    BatchMoveIn,
    BatchMoveResult,
    CopyIn,
    DiscardDraftResult,
    ProcedureBatchDeleteIn,
    ProcedureCreate,
    ProcedureDeleteIn,
    ProcedureDetail,
    ProcedureMeta,
    ProcedureOut,
    ProcedureSaveIn,
    ProcedureSaveResult,
    ReasonIn,
    RestoreIn,
    RestorePreviewOut,
    RollbackIn,
    TransitionIn,
)
from app.services import (
    asset_service,
    editor_service,
    import_service,
    mark_service,
    pdf,
    procedure_service,
    source_docx_service,
    version_flow_service,
)
from app.services.optimistic_lock import ensure_if_match

router = APIRouter(prefix="/api/v1/procedures", tags=["procedures"])


def _page(items: list[ProcedureOut], total: int, page: int, page_size: int) -> Page[ProcedureOut]:
    return Page[ProcedureOut](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.get("", response_model=Page[ProcedureOut])
def list_procedures(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = "-updated_at",
    search: str | None = None,
    folder_id: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
) -> Page[ProcedureOut]:
    items, total = procedure_service.list_procedures(
        db,
        page=page,
        page_size=page_size,
        sort=sort,
        search=search,
        folder_id=folder_id,
        status=status_filter,
    )
    return _page(items, total, page, page_size)


@router.get("/library", response_model=Page[ProcedureOut])
def list_library(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = "-updated_at",
    search: str | None = None,
    folder_id: str | None = None,
) -> Page[ProcedureOut]:
    items, total = procedure_service.list_library(
        db, page=page, page_size=page_size, sort=sort, search=search, folder_id=folder_id
    )
    return _page(items, total, page, page_size)


@router.post("/batch-delete", response_model=BatchDeleteResult)
def batch_delete(
    payload: ProcedureBatchDeleteIn,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> BatchDeleteResult:
    result = procedure_service.batch_delete(db, payload.ids, payload.reason, meta)
    db.commit()
    return result


@router.post("/batch-move", response_model=BatchMoveResult)
def batch_move(
    payload: BatchMoveIn,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> BatchMoveResult:
    result = procedure_service.batch_move(db, payload, meta)
    db.commit()
    return result


@router.post("/import", response_model=ProcedureMeta, status_code=status.HTTP_201_CREATED)
def import_procedure(
    payload: ImportRequest,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ProcedureMeta:
    """导入解析结果创建新程序（§9.1 parse→import 第二步）。"""
    proc = import_service.import_procedure(
        db,
        name=payload.name,
        folder_id=payload.folder_id,
        description=payload.description,
        chapters=payload.chapters,
        upload_token=payload.upload_token,
        meta=meta,
    )
    db.commit()
    return procedure_service.to_meta(db, proc)


@router.get("/{procedure_id}", response_model=ProcedureDetail)
def get_procedure(procedure_id: str, db: Session = Depends(get_db)) -> ProcedureDetail:
    return procedure_service.get_detail(db, procedure_id)


@router.post(
    "/{procedure_id}/assets",
    response_model=AssetUploadResult,
    status_code=status.HTTP_201_CREATED,
)
async def upload_asset(
    procedure_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> AssetUploadResult:
    """编辑器图片直传（Q214）：sha256 去重入库，返回 asset URL。"""
    data = await file.read()
    asset = asset_service.store_from_upload(db, procedure_id, data, file.filename or "")
    db.commit()
    return AssetUploadResult(
        asset_id=asset.id,
        url=asset_service.asset_url(procedure_id, asset.id),
        width=asset.width,
        height=asset.height,
    )


@router.get("/{procedure_id}/assets/{asset_id}")
def serve_asset(procedure_id: str, asset_id: str, db: Session = Depends(get_db)) -> Response:
    """图片资源服务（§25.2）：流式返回 asset 原始字节。"""
    data, mime = asset_service.get_asset(db, asset_id)
    return Response(content=data, media_type=mime)


@router.get("/{procedure_id}/source-docx")
def serve_source_docx(procedure_id: str, db: Session = Depends(get_db)) -> FileResponse:
    """流式返回导入程序的原始 .docx（预览栏渲染 / 追溯）。无 → 404。"""
    path, mime, filename = source_docx_service.get_for_procedure(db, procedure_id)
    ascii_fallback = filename.encode("ascii", "ignore").decode() or "source.docx"
    return FileResponse(
        path,
        media_type=mime,
        headers={
            "Content-Disposition": (
                f"inline; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"
            )
        },
    )


# --------------------------------------------------------------------------- #
# PDF（Phase 8，pdf-rendering.md / §34 / §59）
# --------------------------------------------------------------------------- #
@router.get("/{procedure_id}/pdf-layout", response_model=PdfLayoutOut)
def pdf_layout(procedure_id: str, db: Session = Depends(get_db)) -> PdfLayoutOut:
    """分页计算（前端预览逐页复刻据此渲染，与下载版页码一致，Q235/§59.2）。"""
    return pdf.get_layout(db, procedure_id)


@router.get("/{procedure_id}/pdf-download")
def pdf_download(
    procedure_id: str,
    db: Session = Depends(get_db),
    debug: int = Query(default=0),
) -> Response:
    """下载 ReportLab 静态 PDF；`?debug=1` 返回第一遍 dry-run 的 toc_data（§14/§59.4）。"""
    pdf_bytes, layout_out, filename = pdf.generate_pdf(db, procedure_id, debug=bool(debug))
    if debug:
        return JSONResponse(content=layout_out.model_dump())
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("", response_model=ProcedureMeta, status_code=status.HTTP_201_CREATED)
def create_procedure(
    payload: ProcedureCreate,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ProcedureMeta:
    proc = procedure_service.create_procedure(db, payload, meta)
    db.commit()
    return procedure_service.to_meta(db, proc)


@router.put("/{procedure_id}", response_model=ProcedureSaveResult)
def save_procedure(
    procedure_id: str,
    payload: ProcedureSaveIn,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> ProcedureSaveResult:
    """编辑器整批保存：程序元字段 + 脏节点 upsert + 删除（§17.2）。返回新 revision + id 映射。"""
    expected = ensure_if_match(if_match)
    proc, id_map = editor_service.save_procedure(db, procedure_id, payload, expected, meta)
    db.commit()
    return ProcedureSaveResult(**procedure_service.to_meta(db, proc).model_dump(), id_map=id_map)


@router.post("/{procedure_id}/transition", response_model=ProcedureMeta)
def transition(
    procedure_id: str,
    payload: TransitionIn,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> ProcedureMeta:
    expected = ensure_if_match(if_match)
    proc = procedure_service.transition(db, procedure_id, payload, expected, meta)
    db.commit()
    return procedure_service.to_meta(db, proc)


@router.post("/{procedure_id}/apply-marks", response_model=ApplyMarksResult)
def apply_marks(
    procedure_id: str,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ApplyMarksResult:
    result = mark_service.apply_marks(db, procedure_id, meta)
    db.commit()
    return result


@router.delete("/{procedure_id}", response_model=None)
def delete_procedure(
    procedure_id: str,
    payload: ProcedureDeleteIn,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response | DiscardDraftResult:
    """软删单版本；DRAFT 当前版本(v>1) 走丢弃路径返 200 + {deleted_id, new_current_*}（§22.11）。"""
    result = procedure_service.delete_procedure(db, procedure_id, payload.reason, meta)
    db.commit()
    if result is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return result


# --------------------------------------------------------------------------- #
# 版本管理（Phase 7）
# --------------------------------------------------------------------------- #
@router.post("/{procedure_id}/upgrade-version", response_model=ProcedureMeta)
def upgrade_version(
    procedure_id: str,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ProcedureMeta:
    proc = version_flow_service.upgrade_version(db, procedure_id, meta)
    db.commit()
    return procedure_service.to_meta(db, proc)


@router.post("/{procedure_id}/rollback", response_model=ProcedureMeta)
def rollback(
    procedure_id: str,
    payload: RollbackIn,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ProcedureMeta:
    proc = version_flow_service.rollback(
        db, procedure_id, payload.target_version, payload.reason, meta
    )
    db.commit()
    return procedure_service.to_meta(db, proc)


@router.post("/{procedure_id}/deprecate", response_model=ProcedureMeta)
def deprecate(
    procedure_id: str,
    payload: ReasonIn,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ProcedureMeta:
    proc = version_flow_service.deprecate(db, procedure_id, payload.reason, meta)
    db.commit()
    return procedure_service.to_meta(db, proc)

@router.post("/{procedure_id}/archive", response_model=ProcedureMeta)
def archive(
    procedure_id: str,
    payload: ReasonIn,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ProcedureMeta:
    proc = version_flow_service.archive_group(db, procedure_id, payload.reason, meta)
    db.commit()
    return procedure_service.to_meta(db, proc)


@router.get("/{procedure_id}/restore-preview", response_model=RestorePreviewOut)
def restore_preview(procedure_id: str, db: Session = Depends(get_db)) -> RestorePreviewOut:
    return RestorePreviewOut.model_validate(version_flow_service.restore_preview(db, procedure_id))


@router.post("/{procedure_id}/restore", response_model=ProcedureMeta)
def restore(
    procedure_id: str,
    payload: RestoreIn,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ProcedureMeta:
    proc = version_flow_service.restore(
        db, procedure_id, payload.reason, payload.target_folder_id, meta
    )
    db.commit()
    return procedure_service.to_meta(db, proc)


@router.post(
    "/{procedure_id}/copy", response_model=ProcedureMeta, status_code=status.HTTP_201_CREATED
)
def copy_procedure(
    procedure_id: str,
    payload: CopyIn,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ProcedureMeta:
    proc = version_flow_service.copy_procedure(
        db, procedure_id, payload.target_folder_id, payload.name, meta
    )
    db.commit()
    return procedure_service.to_meta(db, proc)


@router.get("/{procedure_id}/version-history")
def version_history(procedure_id: str, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    """本版本的 version_change_log（5 类里程碑时间线，§13.6）。"""
    proc = procedure_service.get_or_404(db, procedure_id)
    return proc.version_change_log
