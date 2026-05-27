"""章节路由（api-specification §5.4）。

编辑器主保存走 PUT /procedures/{id}（整批脏节点）；本组为细粒度 action API。Router 提交事务。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.deps import RequestMeta, get_db, get_request_meta
from app.schemas.node import (
    ChapterCreate,
    ChapterMoveIn,
    ChapterOut,
    ChapterUpdate,
    ConversionResult,
    MarkStatusIn,
    SplitTitleContentIn,
)
from app.services import chapter_service, conversion_service, mark_service

router = APIRouter(prefix="/api/v1/chapters", tags=["chapters"])


@router.get("", response_model=list[ChapterOut])
def list_chapters(
    db: Session = Depends(get_db),
    procedure_id: str | None = None,
    parent_id: str | None = None,
    mark_status: str | None = None,
) -> list[ChapterOut]:
    rows = chapter_service.list_chapters(
        db,
        procedure_id=procedure_id,
        parent_id=parent_id,
        mark_status=mark_status,
    )
    return [ChapterOut.model_validate(r) for r in rows]


@router.get("/{chapter_id}", response_model=ChapterOut)
def get_chapter(chapter_id: str, db: Session = Depends(get_db)) -> ChapterOut:
    return ChapterOut.model_validate(chapter_service.get_chapter(db, chapter_id))


@router.post("", response_model=ChapterOut, status_code=status.HTTP_201_CREATED)
def create_chapter(
    payload: ChapterCreate,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ChapterOut:
    ch = chapter_service.create_chapter(db, payload, meta)
    db.commit()
    return ChapterOut.model_validate(ch)


@router.put("/{chapter_id}", response_model=ChapterOut)
def update_chapter(
    chapter_id: str,
    payload: ChapterUpdate,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ChapterOut:
    ch = chapter_service.update_chapter(db, chapter_id, payload, meta)
    db.commit()
    return ChapterOut.model_validate(ch)


@router.delete("/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chapter(
    chapter_id: str,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    chapter_service.delete_chapter(db, chapter_id, meta)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{chapter_id}/move-up", response_model=ChapterOut)
def move_up(
    chapter_id: str, db: Session = Depends(get_db), meta: RequestMeta = Depends(get_request_meta)
) -> ChapterOut:
    ch = chapter_service.move_up(db, chapter_id, meta)
    db.commit()
    return ChapterOut.model_validate(ch)


@router.post("/{chapter_id}/move-down", response_model=ChapterOut)
def move_down(
    chapter_id: str, db: Session = Depends(get_db), meta: RequestMeta = Depends(get_request_meta)
) -> ChapterOut:
    ch = chapter_service.move_down(db, chapter_id, meta)
    db.commit()
    return ChapterOut.model_validate(ch)


@router.post("/{chapter_id}/move", response_model=ChapterOut)
def move_chapter(
    chapter_id: str,
    payload: ChapterMoveIn,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ChapterOut:
    ch = chapter_service.move_chapter(db, chapter_id, payload, meta)
    db.commit()
    return ChapterOut.model_validate(ch)


@router.post("/{chapter_id}/toggle-skip-numbering", response_model=ChapterOut)
def toggle_skip(
    chapter_id: str, db: Session = Depends(get_db), meta: RequestMeta = Depends(get_request_meta)
) -> ChapterOut:
    ch = chapter_service.toggle_skip_numbering(db, chapter_id, meta)
    db.commit()
    return ChapterOut.model_validate(ch)


@router.post("/{chapter_id}/mark-status", response_model=ChapterOut)
def set_mark_status(
    chapter_id: str,
    payload: MarkStatusIn,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ChapterOut:
    ch = mark_service.set_mark_status(db, chapter_id, payload.mark_status, meta)
    db.commit()
    return ChapterOut.model_validate(ch)


@router.post("/{chapter_id}/convert-to-step", response_model=ConversionResult)
def convert_to_step(
    chapter_id: str, db: Session = Depends(get_db), meta: RequestMeta = Depends(get_request_meta)
) -> ConversionResult:
    result = conversion_service.convert_to_step(db, chapter_id, meta)
    db.commit()
    return result


@router.post("/{chapter_id}/convert-root-to-step", response_model=ConversionResult)
def convert_root_to_step(
    chapter_id: str, db: Session = Depends(get_db), meta: RequestMeta = Depends(get_request_meta)
) -> ConversionResult:
    result = conversion_service.convert_root_to_step(db, chapter_id, meta)
    db.commit()
    return result


@router.post("/{chapter_id}/convert-to-content", response_model=ConversionResult)
def convert_to_content(
    chapter_id: str, db: Session = Depends(get_db), meta: RequestMeta = Depends(get_request_meta)
) -> ConversionResult:
    result = conversion_service.convert_to_content(db, chapter_id, meta)
    db.commit()
    return result


@router.post("/{chapter_id}/split-title-content", response_model=ConversionResult)
def split_title_content(
    chapter_id: str,
    payload: SplitTitleContentIn,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ConversionResult:
    result = conversion_service.split_title_content(db, chapter_id, payload.cursor_offset, meta)
    db.commit()
    return result


