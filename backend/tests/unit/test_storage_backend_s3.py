"""S3Backend：用手写 fake boto3 client 验证 key 映射与语义，不连真 S3。"""
from __future__ import annotations

import pytest
from botocore.exceptions import ClientError

from app.storage_backends.s3 import S3Backend


class _FakeS3:
    """最小内存 fake：put/get/delete/head_object。"""

    def __init__(self):
        self.store: dict[tuple[str, str], bytes] = {}

    def put_object(self, *, Bucket, Key, Body):
        self.store[(Bucket, Key)] = Body

    def get_object(self, *, Bucket, Key):
        if (Bucket, Key) not in self.store:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": _Body(self.store[(Bucket, Key)])}

    def delete_object(self, *, Bucket, Key):
        self.store.pop((Bucket, Key), None)

    def head_object(self, *, Bucket, Key):
        if (Bucket, Key) not in self.store:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
        return {}


class _Body:
    def __init__(self, data): self._data = data
    def read(self): return self._data


def _backend():
    return S3Backend(client=_FakeS3(), bucket="b")


def test_write_read_roundtrip():
    b = _backend()
    b.write("asset/ab/x.bin", b"hello")
    assert b.read("asset/ab/x.bin") == b"hello"


def test_read_missing_raises_filenotfound():
    with pytest.raises(FileNotFoundError):
        _backend().read("missing/x")


def test_exists():
    b = _backend()
    assert b.exists("a/x") is False
    b.write("a/x", b"1")
    assert b.exists("a/x") is True


def test_delete_idempotent():
    b = _backend()
    b.write("d/x", b"1")
    b.delete("d/x")
    assert b.exists("d/x") is False
    b.delete("d/x")  # 不报错
