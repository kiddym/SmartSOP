"""存储路径助手（Q342 / Q371）。

集中派生永久 asset 目录、附件目录与临时上传目录，运行时从 settings 读取（测试可
monkeypatch ``settings.storage_dir``）。永久 asset 落 ``{storage}/asset/{sha[:2]}/{sha}.{ext}``，
附件落 ``{storage}/attachment/{uid[:2]}/{uid}{ext}``（不去重，Q119），
临时上传落 ``{storage}/tmp/uploads/{token}/``。
"""

from __future__ import annotations

from pathlib import Path

from app.config import settings


def storage_root() -> Path:
    return Path(settings.storage_dir)


def asset_root() -> Path:
    return storage_root() / "asset"


def tmp_upload_root() -> Path:
    return storage_root() / "tmp" / "uploads"


def asset_path(sha256: str, ext: str) -> Path:
    """永久 asset 物理路径：按 sha256 前 2 位分桶。"""
    ext = ext if ext.startswith(".") else f".{ext}"
    return asset_root() / sha256[:2] / f"{sha256}{ext}"


def attachment_root() -> Path:
    return storage_root() / "attachment"


def attachment_path(uid: str, ext: str) -> Path:
    """附件物理路径：按 uid 前 2 位分桶（不去重，每次上传独立，Q119/Q371）。"""
    if ext and not ext.startswith("."):
        ext = f".{ext}"
    return attachment_root() / uid[:2] / f"{uid}{ext}"


def token_dir(token: str) -> Path:
    return tmp_upload_root() / token


def token_media_dir(token: str) -> Path:
    return token_dir(token) / "media"


def source_docx_root() -> Path:
    return storage_root() / "source_docx"


def source_docx_path(procedure_group_id: str) -> Path:
    """原始源 docx 物理路径：按 procedure_group 一份。"""
    return source_docx_root() / procedure_group_id / "source.docx"


def batch_root() -> Path:
    return storage_root() / "batch"


def batch_job_dir(job_id: str) -> Path:
    return batch_root() / job_id


def batch_item_dir(job_id: str, item_id: str) -> Path:
    return batch_job_dir(job_id) / item_id


def batch_docx_path(job_id: str, item_id: str) -> Path:
    return batch_item_dir(job_id, item_id) / "source.docx"


def batch_blob_path(job_id: str, item_id: str) -> Path:
    return batch_item_dir(job_id, item_id) / "parse.json"


def batch_media_dir(job_id: str, item_id: str) -> Path:
    return batch_item_dir(job_id, item_id) / "media"
