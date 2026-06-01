"""upload_service 单测（M6.4）：双校验 + token 文件系统 + 临时图 + 过期清理。"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException

from app import storage
from app.models.base import utcnow
from app.parser.ir import ImageRef
from app.services import upload_service
from tests.unit.parser._docx_builder import styled_sop, tiny_png


def test_save_upload_valid_docx(storage_tmp: Path) -> None:
    res = upload_service.save_upload(styled_sop(), "我的程序.docx")
    assert res.filename == "我的程序.docx"
    token_dir = storage.token_dir(res.upload_token)
    assert (token_dir / "source.docx").exists()
    assert (token_dir / "meta.json").exists()


def test_save_upload_rejects_non_docx_bytes(storage_tmp: Path) -> None:
    with pytest.raises(HTTPException) as exc:
        upload_service.save_upload(b"not a docx", "x.docx")
    assert exc.value.detail["code"] == "PARSE_FILE_INVALID"  # type: ignore[index]


def test_save_upload_rejects_wrong_extension(storage_tmp: Path) -> None:
    with pytest.raises(HTTPException) as exc:
        upload_service.save_upload(styled_sop(), "x.doc")
    assert exc.value.detail["code"] == "PARSE_FILE_INVALID"  # type: ignore[index]


def test_read_docx_roundtrip(storage_tmp: Path) -> None:
    data = styled_sop()
    res = upload_service.save_upload(data, "a.docx")
    assert upload_service.read_docx(res.upload_token) == data


def test_read_docx_invalid_token(storage_tmp: Path) -> None:
    with pytest.raises(HTTPException) as exc:
        upload_service.read_docx("no-such-token")
    assert exc.value.detail["code"] == "UPLOAD_TOKEN_INVALID"  # type: ignore[index]


def test_expired_token_rejected_and_cleaned(storage_tmp: Path) -> None:
    res = upload_service.save_upload(styled_sop(), "a.docx")
    # 把 meta.json 的 expires_at 改为过去
    meta_path = storage.token_dir(res.upload_token) / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["expires_at"] = (utcnow() - timedelta(hours=1)).isoformat()
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    with pytest.raises(HTTPException):
        upload_service.read_docx(res.upload_token)

    removed = upload_service.cleanup_expired(utcnow())
    assert removed == 1
    assert not storage.token_dir(res.upload_token).exists()


def test_cleanup_keeps_fresh_token(storage_tmp: Path) -> None:
    res = upload_service.save_upload(styled_sop(), "a.docx")
    assert upload_service.cleanup_expired(utcnow()) == 0
    assert storage.token_dir(res.upload_token).exists()


def test_write_temp_media_and_serve(storage_tmp: Path) -> None:
    res = upload_service.save_upload(styled_sop(), "a.docx")
    png = tiny_png(size=12)
    refs = [
        ImageRef(
            rid="rId7",
            part_name="word/media/image1.png",
            data=png,
            ext=".png",
            placeholder="media:rId7",
        )
    ]
    mapping, assets, failed = upload_service.write_temp_media(res.upload_token, refs)
    assert "media:rId7" in mapping
    assert len(assets) == 1
    assert assets[0].width == 12
    assert failed == set()

    # serve 回读
    filename = mapping["media:rId7"].rsplit("/", 1)[1]
    data, mime = upload_service.serve_media(res.upload_token, filename)
    assert data == png
    assert mime == "image/png"


def test_write_temp_media_vector_conversion_failure(
    storage_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """无 soffice / 转换失败：EMF 矢量图进 failed_vectors、不入 assets、不写盘。"""
    monkeypatch.setattr(upload_service.images, "convert_to_png", lambda *_a, **_k: None)
    res = upload_service.save_upload(styled_sop(), "a.docx")
    refs = [
        ImageRef(
            rid="rId9",
            part_name="word/media/image1.emf",
            data=b"\x01\x00\x00\x00emf-bytes",
            ext=".emf",
            placeholder="media:rId9",
        )
    ]
    mapping, assets, failed = upload_service.write_temp_media(res.upload_token, refs)
    assert "media:rId9" in failed
    assert assets == []
    assert mapping == {}
    from app import storage
    media_dir = storage.token_media_dir(res.upload_token)
    assert not any(p.suffix == ".emf" for p in media_dir.iterdir()) if media_dir.exists() else True
