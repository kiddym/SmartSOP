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


def test_build_parse_response_includes_import_blocks() -> None:
    from app.parser.result import ParsedImportBlock
    from app.schemas.parse import build_parse_response

    result = ParseResult(
        metadata=ParseMetadata(
            total_chapters=1,
            image_count=0,
            table_count=0,
            body_start_index=5,
            body_start_detected_by="first_styled_heading",
        ),
        chapters=[],
        parse_method="smart",
        import_blocks=[
            ParsedImportBlock(
                id="block-5",
                source_index=5,
                raw_text="目的",
                display_text="目的",
                clean_text="目的",
                rich_content="<p>目的</p>",
                block_type="paragraph",
                has_word_numbering=True,
                word_number=None,
                word_number_level=None,
                style_name="Heading 1",
                suggested_type="chapter",
                suggested_level=1,
                confidence_tier="high",
                mark_status="unmarked",
            )
        ],
    )

    response = build_parse_response(result, assets=[], parse_time_ms=12)

    assert len(response.import_blocks) == 1
    block = response.import_blocks[0]
    assert block.id == "block-5"
    assert block.source_index == 5
    assert block.clean_text == "目的"
    assert block.has_word_numbering is True
    assert block.word_number is None
    assert block.suggested_type == "chapter"
    assert block.suggested_level == 1


def test_rewrite_placeholders_updates_import_blocks() -> None:
    from app.parser.result import ParsedImportBlock, ParsedNode

    result = ParseResult(
        metadata=ParseMetadata(
            total_chapters=1,
            image_count=1,
            table_count=0,
            body_start_index=0,
            body_start_detected_by="first_styled_heading",
        ),
        chapters=[
            ParsedNode(
                id="n1",
                title="目的",
                level=1,
                content_type="content",
                rich_content='<p><img src="media:rId1"/></p>',
            )
        ],
        parse_method="smart",
        import_blocks=[
            ParsedImportBlock(
                id="block-1",
                source_index=1,
                raw_text="图",
                display_text="图",
                clean_text="图",
                rich_content='<p><img src="media:rId1"/></p>',
                block_type="paragraph",
            )
        ],
    )

    parse_service._rewrite_placeholders(result, {"media:rId1": "/api/v1/uploads/t/media/a.png"})

    assert result.chapters[0].rich_content == '<p><img src="/api/v1/uploads/t/media/a.png"/></p>'
    assert result.import_blocks[0].rich_content == '<p><img src="/api/v1/uploads/t/media/a.png"/></p>'


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
