# app/storage_backends/s3.py
"""S3 / S3-兼容（MinIO 等）对象存储后端（Phase 5B）。

key 即 bucket 内 object key（= DB 相对 storage_path）。client 可注入以便测试。
"""

from __future__ import annotations

from typing import Any, cast

from botocore.exceptions import ClientError

from app.config import settings

_NOT_FOUND_CODES = {"NoSuchKey", "404", "NoSuchBucket"}


class S3Backend:
    def __init__(self, client: Any | None = None, bucket: str | None = None) -> None:
        self._bucket = bucket if bucket is not None else settings.s3_bucket
        self._client = client if client is not None else self._make_client()

    def _make_client(self) -> Any:  # pragma: no cover — 真实 client，不在单测覆盖
        import boto3

        kwargs: dict[str, Any] = {}
        if settings.s3_endpoint_url:
            kwargs["endpoint_url"] = settings.s3_endpoint_url
        if settings.s3_region:
            kwargs["region_name"] = settings.s3_region
        if settings.s3_access_key:
            kwargs["aws_access_key_id"] = settings.s3_access_key
            kwargs["aws_secret_access_key"] = settings.s3_secret_key
        return boto3.client("s3", **kwargs)

    def write(self, key: str, data: bytes) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data)

    def read(self, key: str) -> bytes:
        try:
            resp = self._client.get_object(Bucket=self._bucket, Key=key)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in _NOT_FOUND_CODES:
                raise FileNotFoundError(key) from e
            raise
        return cast(bytes, resp["Body"].read())

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)  # S3 delete 本身幂等

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in _NOT_FOUND_CODES:
                return False
            raise
        return True
