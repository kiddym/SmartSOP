"""存储后端工厂（Phase 5B）。按 settings.storage_backend 返回单例。

测试可 monkeypatch settings.storage_backend，并调用 reset_storage_backend() 清缓存；
local 后端的物理根由 settings.storage_dir 决定（沿用 storage_tmp fixture）。
"""
from __future__ import annotations

from app.config import settings
from app.storage_backends.base import StorageBackend

_backend: StorageBackend | None = None


def get_storage_backend() -> StorageBackend:
    global _backend
    if _backend is None:
        _backend = _build()
    return _backend


def reset_storage_backend() -> None:
    """测试钩子：丢弃缓存单例，下次按当前 settings 重建。"""
    global _backend
    _backend = None


def _build() -> StorageBackend:
    if settings.storage_backend == "s3":
        from app.storage_backends.s3 import S3Backend

        return S3Backend()
    from app.storage_backends.local import LocalBackend

    return LocalBackend()
