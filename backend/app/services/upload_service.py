"""临时上传服务（Q141 / Q341 / Q342 / Q346）。

upload_token = 纯文件系统（无 DB 表）：docx 落 ``{tmp}/{token}/source.docx``，
解析抽图落 ``{tmp}/{token}/media/``，元信息写同目录 ``meta.json``。双校验
（扩展名 + OPC 嗅探，Q346）。过期清理由 scheduler 任务调用（§53.2）。
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app import storage
from app.config import settings
from app.errors import bad_request, not_found, payload_too_large
from app.models.base import new_uuid, utcnow
from app.parser.ir import ImageRef
from app.parser.utils import images
from app.parser.utils.opc import is_docx_bytes
from app.schemas.parse import ParsedAssetOut, UploadResult
from app.services import asset_service

_SOURCE = "source.docx"
_META = "meta.json"


# --------------------------------------------------------------------------- #
# 上传 / 读取
# --------------------------------------------------------------------------- #
def save_upload(data: bytes, filename: str) -> UploadResult:
    """双校验后落临时区，返回 upload_token + 过期时间。"""
    if len(data) > settings.upload_max_size_mb * 1024 * 1024:
        raise payload_too_large("PARSE_FILE_TOO_LARGE", f"文件超过 {settings.upload_max_size_mb}MB")
    if not filename.lower().endswith(".docx") or not is_docx_bytes(data):
        raise bad_request(
            "PARSE_FILE_INVALID", "仅支持 .docx 格式（需为合法 Word 文档）", field="file"
        )

    token = new_uuid()
    tdir = storage.token_dir(token)
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / _SOURCE).write_bytes(data)

    created = utcnow()
    expires = created + timedelta(hours=settings.temp_upload_ttl_hours)
    (tdir / _META).write_text(
        json.dumps(
            {
                "created_at": created.isoformat(),
                "expires_at": expires.isoformat(),
                "filename": filename,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return UploadResult(upload_token=token, expires_at=expires, filename=filename)


def read_docx(token: str) -> bytes:
    """读取临时 docx；token 不存在 / 已过期 → UPLOAD_TOKEN_INVALID。"""
    tdir = storage.token_dir(token)
    src = tdir / _SOURCE
    if not _is_safe_token(token) or not src.exists() or _is_expired(token, utcnow()):
        raise bad_request("UPLOAD_TOKEN_INVALID", "上传凭证不存在或已过期", field="upload_token")
    return src.read_bytes()


def upload_filename(token: str) -> str:
    meta = _load_meta(token)
    return str(meta.get("filename", "")) if meta else ""


def try_read_source(token: str) -> tuple[bytes, str] | None:
    """读取临时 docx + 原始文件名；不存在/过期/非法 token → None（不抛，供导入降级）。"""
    if not _is_safe_token(token):
        return None
    src = storage.token_dir(token) / _SOURCE
    if not src.exists() or _is_expired(token, utcnow()):
        return None
    return src.read_bytes(), upload_filename(token) or _SOURCE


# --------------------------------------------------------------------------- #
# 临时图：写盘 + 服务
# --------------------------------------------------------------------------- #
def write_temp_media(
    token: str, image_refs: list[ImageRef]
) -> tuple[dict[str, str], list[ParsedAssetOut], set[str]]:
    """把解析抽出的图写入临时 media 目录，返回 placeholder→临时 URL 映射 + asset 描述
    + 转换失败的矢量图 placeholder 集合（failed_vectors，供 parse_service 换占位）。"""
    media = storage.token_media_dir(token)
    media.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, str] = {}
    assets: list[ParsedAssetOut] = []
    failed_vectors: set[str] = set()
    seen: set[str] = set()

    for ref in image_refs:
        if ref.rid in seen:
            continue
        seen.add(ref.rid)
        data, ext = ref.data, ref.ext.lower()
        if ext in images.VECTOR_EXTS:  # emf/wmf → png 以便浏览器预览（Q216）
            png = images.convert_to_png(data, ext)
            if png is None:
                failed_vectors.add(ref.placeholder)
                continue
            data, ext = png, ".png"
        filename = f"{_safe_name(ref.rid)}{ext}"
        (media / filename).write_bytes(data)
        url = asset_service.temp_url(token, filename)
        mapping[ref.placeholder] = url
        width, height = images.dimensions(data)
        assets.append(
            ParsedAssetOut(
                temp_id=ref.rid,
                url=url,
                sha256=images.sha256_hex(data),
                mime=images.mime_for_ext(ext),
                size_bytes=len(data),
                width=width,
                height=height,
            )
        )
    return mapping, assets, failed_vectors


def serve_media(token: str, filename: str) -> tuple[bytes, str]:
    """流式服务临时图（review 阶段预览）。过期 / 路径穿越 / 缺失 → 404。"""
    # Q342：临时图服务端点过期 / 路径穿越 / 缺失统一 404
    if not _is_safe_token(token) or _is_expired(token, utcnow()):
        raise not_found("NOT_FOUND", "上传凭证不存在或已过期")
    media_dir = storage.token_media_dir(token)
    target = media_dir / filename
    if not _is_safe_child(target, media_dir) or not target.exists():
        raise not_found("NOT_FOUND", "临时图片不存在")
    return target.read_bytes(), images.mime_for_ext(target.suffix)


# --------------------------------------------------------------------------- #
# 过期清理（§53.2 由 task 调用）
# --------------------------------------------------------------------------- #
def cleanup_expired(now: datetime) -> int:
    """扫描 tmp/uploads，删除已过期 token 目录，返回删除数量。"""
    root = storage.tmp_upload_root()
    if not root.exists():
        return 0
    removed = 0
    for tdir in root.iterdir():
        if not tdir.is_dir():
            continue
        if _is_expired(tdir.name, now):
            shutil.rmtree(tdir, ignore_errors=True)
            removed += 1
    return removed


# --------------------------------------------------------------------------- #
# 内部
# --------------------------------------------------------------------------- #
def _load_meta(token: str) -> dict[str, object] | None:
    path = storage.token_dir(token) / _META
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (ValueError, OSError):
        return None


def _is_expired(token: str, now: datetime) -> bool:
    """meta 缺失/损坏时回退用目录 mtime + ttl 判定（Q341）。"""
    tdir = storage.token_dir(token)
    if not tdir.exists():
        return True
    meta = _load_meta(token)
    if meta and isinstance(meta.get("expires_at"), str):
        try:
            return now >= datetime.fromisoformat(str(meta["expires_at"]))
        except ValueError:
            pass
    mtime = datetime.fromtimestamp(tdir.stat().st_mtime, UTC).replace(tzinfo=None)
    return now >= mtime + timedelta(hours=settings.temp_upload_ttl_hours)


def _is_safe_token(token: str) -> bool:
    return bool(token) and "/" not in token and "\\" not in token and ".." not in token


def _safe_name(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in ("-", "_")) or "img"


def _is_safe_child(target: Path, base: Path) -> bool:
    try:
        target.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False
