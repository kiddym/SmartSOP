"""本地磁盘后端：等价 Phase 0–4 现有落盘行为。"""

from __future__ import annotations

from pathlib import Path

from app import storage


class LocalBackend:
    def _path(self, key: str) -> Path:
        return storage.storage_root() / key

    def write(self, key: str, data: bytes) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()  # 不存在自然抛 FileNotFoundError

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._path(key).exists()
