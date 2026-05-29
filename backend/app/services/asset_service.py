"""图片资源服务（§25.2 / §29 / Q189 / Q193 / Q197 / Q214 / Q333）。

承担：sha256 全库去重落盘、编辑器直传（Q214）、临时图提升为永久 asset（import）、
引用关联表重建（save/import）、asset 服务读取、GC 候选与删除（行 + 文件同删 + grace）。

事务边界：service 只 flush 不 commit（GC 的逐项提交由 task 负责，§53.2）。
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import storage
from app.errors import bad_request, not_found, payload_too_large
from app.models.asset import ProcedureAsset, ProcedureAssetReference
from app.models.base import new_uuid, utcnow
from app.models.procedure import Procedure
from app.models.node import ProcedureNode
from app.parser.utils import images

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10MB（Q207/Q215）

_ASSET_URL_RE = re.compile(r"assets/([0-9a-fA-F-]{36})")
_API_PREFIX = "/api/v1"


# --------------------------------------------------------------------------- #
# URL 助手
# --------------------------------------------------------------------------- #
def asset_url(procedure_id: str, asset_id: str) -> str:
    return f"{_API_PREFIX}/procedures/{procedure_id}/assets/{asset_id}"


def temp_url(token: str, filename: str) -> str:
    return f"{_API_PREFIX}/uploads/{token}/media/{filename}"


def extract_asset_ids(html: str) -> set[str]:
    return set(_ASSET_URL_RE.findall(html or ""))


# --------------------------------------------------------------------------- #
# 落盘 / 去重
# --------------------------------------------------------------------------- #
def _prepare(data: bytes, ext: str) -> tuple[bytes, str, str] | None:
    """归一图片：emf/wmf 转 png。返回 (data, ext, mime)；转换失败返回 None。"""
    norm = ext.lower() if ext.startswith(".") else f".{ext.lower()}"
    if norm in images.VECTOR_EXTS:
        png = images.convert_to_png(data, norm)
        if png is None:
            return None
        return png, ".png", "image/png"
    return data, norm, images.mime_for_ext(norm)


def find_or_create_asset(
    db: Session,
    data: bytes,
    *,
    ext: str,
    source_meta: dict[str, Any] | None = None,
) -> ProcedureAsset:
    """按 sha256 去重落盘并入库（已存在则复用，Q193）。data 须为已归一栅格字节。"""
    sha = images.sha256_hex(data)
    # 行锁与 GC 的 delete_asset_locked 序列化（§53.3c）：import 先到 → count>0 GC 跳过；
    # GC 先到 → 此处查无行 → 用手上字节重建（SQLite 上 FOR UPDATE 为 no-op）。
    existing = db.execute(
        select(ProcedureAsset)
        .where(ProcedureAsset.sha256 == sha, ProcedureAsset.is_active.is_(True))
        .with_for_update()
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    norm_ext = ext.lower() if ext.startswith(".") else f".{ext.lower()}"
    width, height = images.dimensions(data)
    path = storage.asset_path(sha, norm_ext)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    rel = path.relative_to(storage.storage_root()).as_posix()

    asset = ProcedureAsset(
        sha256=sha,
        storage_path=rel,
        mime_type=images.mime_for_ext(norm_ext),
        size_bytes=len(data),
        width=width,
        height=height,
        source_meta=source_meta or {},
    )
    db.add(asset)
    db.flush()
    return asset


def store_from_upload(db: Session, procedure_id: str, data: bytes, filename: str) -> ProcedureAsset:
    """编辑器图片直传（Q214）：校验 → emf/wmf 转 png → sha256 去重入库。"""
    _get_editable_proc(db, procedure_id)
    ext = Path(filename).suffix.lower()
    if not images.is_supported(ext):
        raise bad_request(
            "UNSUPPORTED_IMAGE_FORMAT", f"不支持的图片格式：{ext or '未知'}", field="file"
        )
    if len(data) > MAX_IMAGE_BYTES:
        raise payload_too_large("IMAGE_TOO_LARGE", "单图超过 10MB 上限", field="file")
    prepared = _prepare(data, ext)
    if prepared is None:
        raise bad_request(
            "IMAGE_CONVERT_FAILED", "矢量图（emf/wmf）转换失败，请改用位图", field="file"
        )
    raster, norm_ext, _mime = prepared
    return find_or_create_asset(db, raster, ext=norm_ext, source_meta={"source": "editor"})


def promote_temp(
    db: Session, token: str, filename: str, *, source_meta: dict[str, Any] | None = None
) -> ProcedureAsset | None:
    """import 时把临时图提升为永久 asset；临时文件缺失返回 None（调用方降级）。"""
    media = storage.token_media_dir(token) / filename
    if not _is_safe_child(media, storage.token_media_dir(token)) or not media.exists():
        return None
    data = media.read_bytes()
    prepared = _prepare(data, media.suffix)
    if prepared is None:
        return None
    raster, norm_ext, _mime = prepared
    return find_or_create_asset(db, raster, ext=norm_ext, source_meta=source_meta or {})


# --------------------------------------------------------------------------- #
# 引用追踪（Q197 / Q333）
# --------------------------------------------------------------------------- #
def rebuild_references(db: Session, procedure_id: str) -> None:
    """重建本 procedure 的 asset 引用（先删后插，单事务）；引用集变化的 asset bump updated_at。"""
    referenced = _scan_referenced_asset_ids(db, procedure_id)
    valid = _filter_existing_assets(db, referenced)

    old_rows = list(
        db.execute(
            select(ProcedureAssetReference).where(
                ProcedureAssetReference.procedure_id == procedure_id
            )
        ).scalars()
    )
    old_ids = {r.asset_id for r in old_rows}
    for row in old_rows:
        db.delete(row)
    db.flush()

    for asset_id in valid:
        db.add(
            ProcedureAssetReference(
                id=new_uuid(), asset_id=asset_id, procedure_id=procedure_id, created_at=utcnow()
            )
        )

    # 引用集变化（含归零）→ bump updated_at，供 GC grace 计时（Q333 契约）
    changed = old_ids ^ valid
    if changed:
        now = utcnow()
        for asset in db.execute(
            select(ProcedureAsset).where(ProcedureAsset.id.in_(changed))
        ).scalars():
            asset.updated_at = now
    db.flush()


def ref_count(db: Session, asset_id: str) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(ProcedureAssetReference)
            .where(ProcedureAssetReference.asset_id == asset_id)
        ).scalar_one()
    )


def _scan_referenced_asset_ids(db: Session, procedure_id: str) -> set[str]:
    ids: set[str] = set()
    for (body,) in db.execute(
        select(ProcedureNode.body).where(
            ProcedureNode.procedure_id == procedure_id, ProcedureNode.is_active.is_(True)
        )
    ):
        ids |= extract_asset_ids(body)
    return ids


def _filter_existing_assets(db: Session, asset_ids: set[str]) -> set[str]:
    if not asset_ids:
        return set()
    rows = db.execute(
        select(ProcedureAsset.id).where(
            ProcedureAsset.id.in_(asset_ids), ProcedureAsset.is_active.is_(True)
        )
    ).scalars()
    return set(rows)


# --------------------------------------------------------------------------- #
# 读取服务
# --------------------------------------------------------------------------- #
def get_asset(db: Session, asset_id: str) -> tuple[bytes, str]:
    asset = db.execute(
        select(ProcedureAsset).where(
            ProcedureAsset.id == asset_id, ProcedureAsset.is_active.is_(True)
        )
    ).scalar_one_or_none()
    if asset is None:
        raise not_found("NOT_FOUND", "图片资源不存在")
    path = storage.storage_root() / asset.storage_path
    if not path.exists():
        raise not_found("NOT_FOUND", "图片文件已丢失")
    return path.read_bytes(), asset.mime_type


# --------------------------------------------------------------------------- #
# GC（Q197 / Q333 / §53.3）
# --------------------------------------------------------------------------- #
def gc_candidates(db: Session, *, grace_hours: int, now: datetime) -> list[str]:
    """ref_count=0 且 updated_at 早于 grace 的 asset id 列表。"""
    threshold = now - timedelta(hours=grace_hours)
    referenced = select(ProcedureAssetReference.asset_id).distinct()
    rows = db.execute(
        select(ProcedureAsset.id).where(
            ProcedureAsset.is_active.is_(True),
            ProcedureAsset.updated_at <= threshold,
            ProcedureAsset.id.notin_(referenced),
        )
    ).scalars()
    return list(rows)


def delete_asset_locked(db: Session, asset_id: str, *, grace_hours: int, now: datetime) -> bool:
    """行锁重核 ref_count=0 + grace，先删文件再硬删行（Q333）。返回是否删除。"""
    asset = db.execute(
        select(ProcedureAsset).where(ProcedureAsset.id == asset_id).with_for_update()
    ).scalar_one_or_none()
    if asset is None or not asset.is_active:
        return False
    if ref_count(db, asset_id) != 0:
        return False
    if asset.updated_at > now - timedelta(hours=grace_hours):
        return False
    path = storage.storage_root() / asset.storage_path
    try:
        path.unlink()
    except FileNotFoundError:
        pass  # 文件已不存在视为成功
    except OSError:
        return False  # 保留行，下轮重试自愈
    db.delete(asset)
    db.flush()
    return True


# --------------------------------------------------------------------------- #
# 内部
# --------------------------------------------------------------------------- #
def _get_editable_proc(db: Session, procedure_id: str) -> Procedure:
    proc = db.execute(
        select(Procedure).where(Procedure.id == procedure_id, Procedure.is_active.is_(True))
    ).scalar_one_or_none()
    if proc is None:
        raise not_found("NOT_FOUND", "程序不存在")
    if not (proc.is_current and proc.status == "DRAFT"):
        raise bad_request("PROCEDURE_READONLY", "仅当前版本的草稿可编辑")
    return proc


def _is_safe_child(target: Path, base: Path) -> bool:
    """防路径穿越：target 必须在 base 之内。"""
    try:
        target.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False
