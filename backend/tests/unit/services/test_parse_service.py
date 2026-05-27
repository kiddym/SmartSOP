"""parse_service 单测（M6.4）：超时 / 解析异常 / 方法列表。"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.config import settings
from app.parser.result import ParseMetadata, ParseResult
from app.services import parse_service, upload_service
from tests.unit.parser._docx_builder import styled_sop


def test_list_methods() -> None:
    keys = {m.key for m in parse_service.list_methods()}
    assert keys == {"standard", "smart"}


def test_parse_timeout(storage_tmp: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    token = upload_service.save_upload(styled_sop(), "a.docx").upload_token
    monkeypatch.setattr(settings, "parse_timeout_seconds", 1)

    def _slow(_data: bytes, _mode: str) -> ParseResult:
        time.sleep(3)
        raise AssertionError("不应返回")

    monkeypatch.setattr(parse_service, "parse_docx", _slow)
    with pytest.raises(HTTPException) as exc:
        parse_service.parse(token, "smart")
    assert exc.value.status_code == 504
    assert exc.value.detail["code"] == "PARSE_TIMEOUT"  # type: ignore[index]


def test_parse_failed_wraps_exception(storage_tmp: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    token = upload_service.save_upload(styled_sop(), "a.docx").upload_token

    def _boom(_data: bytes, _mode: str) -> ParseResult:
        raise RuntimeError("xml broken")

    monkeypatch.setattr(parse_service, "parse_docx", _boom)
    with pytest.raises(HTTPException) as exc:
        parse_service.parse(token, "standard")
    assert exc.value.detail["code"] == "PARSE_FAILED"  # type: ignore[index]


def test_parse_unknown_mode(storage_tmp: Path) -> None:
    token = upload_service.save_upload(styled_sop(), "a.docx").upload_token
    with pytest.raises(HTTPException) as exc:
        parse_service.parse(token, "turbo")
    assert exc.value.detail["code"] == "PARSE_FAILED"  # type: ignore[index]


def test_no_headings_smart(storage_tmp: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    token = upload_service.save_upload(styled_sop(), "a.docx").upload_token

    def _empty(_data: bytes, _mode: str) -> ParseResult:
        return ParseResult(
            metadata=ParseMetadata(
                total_chapters=0,
                image_count=0,
                table_count=0,
                body_start_index=0,
                body_start_detected_by="cover_skip",
            ),
            chapters=[],
            parse_method="smart",
        )

    monkeypatch.setattr(parse_service, "parse_docx", _empty)
    with pytest.raises(HTTPException) as exc:
        parse_service.parse(token, "smart")
    assert exc.value.detail["code"] == "PARSE_NO_HEADINGS"  # type: ignore[index]
