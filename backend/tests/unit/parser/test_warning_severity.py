"""ParseWarning.severity：blocking/info 正交轴（A 项强确认地基）。"""

from __future__ import annotations

from app.parser.ir import Block, ImageRef, NormalizedDoc
from app.parser.result import ParseResult, ParseMetadata, ParseWarning
from app.parser.structurer import _append_completeness_warnings
from app.schemas.parse import build_parse_response


def test_parsewarning_defaults_to_info() -> None:
    """页眉页脚 / 首标题前丢弃等不传 severity 的 warning 默认 info。"""
    assert ParseWarning(stage="discarded_by_design", message="x").severity == "info"
    assert ParseWarning(stage="boundary", message="x").severity == "info"


def test_completeness_warnings_are_blocking() -> None:
    """C001 图片不匹配 → 追加的 warning severity == blocking。"""
    body_blocks = [
        Block(
            kind="paragraph",
            source_index=0,
            raw_image_count=2,
            images=[ImageRef(rid="a", part_name="word/media/x.png", data=b"x", ext=".png")],
        )
    ]
    nd = NormalizedDoc(blocks=body_blocks, raw_paragraph_count=1)
    warnings: list[ParseWarning] = []
    _append_completeness_warnings(body_blocks, nd, warnings)
    assert warnings, "图片不匹配应至少产出一条 warning"
    assert all(w.severity == "blocking" for w in warnings)


def test_build_parse_response_transports_severity() -> None:
    """build_parse_response 把 severity 透传到 ParseWarningOut。"""
    result = ParseResult(
        metadata=ParseMetadata(
            total_chapters=1, image_count=0, table_count=0,
            body_start_index=0, body_start_detected_by="x",
        ),
        chapters=[],
        parse_method="smart",
        warnings=[
            ParseWarning(stage="completeness", message="缺图", severity="blocking"),
            ParseWarning(stage="discarded_by_design", message="忽略页眉"),
        ],
    )
    resp = build_parse_response(result, assets=[], parse_time_ms=1)
    assert [w.severity for w in resp.warnings] == ["blocking", "info"]
