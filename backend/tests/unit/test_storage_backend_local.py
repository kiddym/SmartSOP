"""LocalBackend：等价现有磁盘行为，key=相对路径。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.storage_backends import get_storage_backend
from app.storage_backends.local import LocalBackend


def test_write_read_roundtrip(storage_tmp: Path):
    b = LocalBackend()
    b.write("asset/ab/x.bin", b"hello")
    assert b.read("asset/ab/x.bin") == b"hello"
    assert (storage_tmp / "asset/ab/x.bin").read_bytes() == b"hello"


def test_exists(storage_tmp: Path):
    b = LocalBackend()
    assert b.exists("a/b.txt") is False
    b.write("a/b.txt", b"1")
    assert b.exists("a/b.txt") is True


def test_read_missing_raises(storage_tmp: Path):
    with pytest.raises(FileNotFoundError):
        LocalBackend().read("nope/x")


def test_delete_idempotent(storage_tmp: Path):
    b = LocalBackend()
    b.write("d/x", b"1")
    b.delete("d/x")
    assert b.exists("d/x") is False
    b.delete("d/x")  # 再删不报错


def test_factory_returns_local_by_default(storage_tmp: Path):
    assert isinstance(get_storage_backend(), LocalBackend)
