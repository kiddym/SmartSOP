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

    def _slow(_data: bytes, _mode: str, **_kw: object) -> ParseResult:
        time.sleep(3)
        raise AssertionError("不应返回")

    monkeypatch.setattr(parse_service, "parse_docx", _slow)
    with pytest.raises(HTTPException) as exc:
        parse_service.parse(token, "smart")
    assert exc.value.status_code == 504
    assert exc.value.detail["code"] == "PARSE_TIMEOUT"  # type: ignore[index]


def test_parse_failed_wraps_exception(storage_tmp: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    token = upload_service.save_upload(styled_sop(), "a.docx").upload_token

    def _boom(_data: bytes, _mode: str, **_kw: object) -> ParseResult:
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


def test_swap_failed_vectors_inserts_placeholder_and_review() -> None:
    from app.parser.result import ParsedNode
    content = ParsedNode(
        id="n1", title="", level=2, content_type="content",
        rich_content='<p>前<img src="media:rId9"/>后</p>',
    )
    chapter = ParsedNode(id="c1", title="目的", level=1, content_type="chapter", children=[content])
    result = ParseResult(
        metadata=ParseMetadata(total_chapters=1, image_count=1, table_count=0,
                               body_start_index=0, body_start_detected_by="x"),
        chapters=[chapter], parse_method="smart",
    )
    n = parse_service._swap_failed_vectors(result, {"media:rId9"})
    assert n == 1
    assert 'data-ph="vector"' in content.rich_content
    assert "矢量图无法转换" in content.rich_content
    assert 'media:rId9' not in content.rich_content
    assert content.mark_status == "review"


def test_swap_failed_vectors_counts_distinct_images_not_occurrences() -> None:
    from app.parser.result import ParsedNode
    # 同一张失败矢量图 media:rId9 在一个节点里被引用两次
    content = ParsedNode(
        id="n1", title="", level=2, content_type="content",
        rich_content='<p><img src="media:rId9"/>和<img src="media:rId9"/></p>',
    )
    chapter = ParsedNode(id="c1", title="目的", level=1, content_type="chapter", children=[content])
    result = ParseResult(
        metadata=ParseMetadata(total_chapters=1, image_count=2, table_count=0,
                               body_start_index=0, body_start_detected_by="x"),
        chapters=[chapter], parse_method="smart",
    )
    n = parse_service._swap_failed_vectors(result, {"media:rId9"})
    assert n == 1  # 1 张不同的图（虽被引用 2 次），不是 2
    assert content.rich_content.count('data-ph="vector"') == 2  # 两处占位都换了
    assert content.mark_status == "review"


def test_parse_appends_blocking_warning_for_failed_vectors(
    storage_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.parser.result import ParsedNode
    token = upload_service.save_upload(styled_sop(), "a.docx").upload_token

    def _fake_parse(_data: bytes, _mode: str, **_kw: object) -> ParseResult:
        content = ParsedNode(id="n1", title="", level=2, content_type="content",
                             rich_content='<p><img src="media:rId9"/></p>')
        chapter = ParsedNode(id="c1", title="目的", level=1, content_type="chapter",
                            children=[content])
        return ParseResult(
            metadata=ParseMetadata(total_chapters=1, image_count=1, table_count=0,
                                   body_start_index=0, body_start_detected_by="x"),
            chapters=[chapter], parse_method="smart",
        )

    monkeypatch.setattr(parse_service, "parse_docx", _fake_parse)
    monkeypatch.setattr(
        upload_service, "write_temp_media", lambda *_a, **_k: ({}, [], {"media:rId9"})
    )
    resp = parse_service.parse(token, "smart")
    blocking = [w for w in resp.warnings if w.severity == "blocking" and "矢量图" in w.message]
    assert len(blocking) == 1


def test_no_headings_smart(storage_tmp: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    token = upload_service.save_upload(styled_sop(), "a.docx").upload_token

    def _empty(_data: bytes, _mode: str, **_kw: object) -> ParseResult:
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
