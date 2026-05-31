"""Word 上传 / 解析 / 导入 schema（api-specification §5.3 解析与导入）。

字段统一 snake_case，与既有已落地 API（ProcedureOut 等）一致（Q350——api-spec
示例的 camelCase 仅为文档书写，实现以项目 snake_case 约定为准）。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.parser.result import ParseResult
from app.schemas.procedure import LevelOfUse


# --------------------------------------------------------------------------- #
# 上传
# --------------------------------------------------------------------------- #
class UploadResult(BaseModel):
    upload_token: str
    expires_at: datetime
    filename: str


# --------------------------------------------------------------------------- #
# 解析
# --------------------------------------------------------------------------- #
class ParseRequest(BaseModel):
    upload_token: str
    parse_mode: str = "smart"


class ParseMethodOut(BaseModel):
    key: str
    label: str
    description: str


class ParsedNodeOut(BaseModel):
    id: str
    title: str
    level: int
    order: int
    parent_id: str | None
    content_type: str
    rich_content: str
    skip_numbering: bool
    confidence: float
    confidence_tier: str
    mark_status: str
    heading_source: str | None
    source_style_name: str | None = None
    source_numbering_pattern: str | None = None
    children: list[ParsedNodeOut] = Field(default_factory=list)


class ParsedAssetOut(BaseModel):
    temp_id: str
    url: str
    sha256: str
    mime: str
    size_bytes: int
    width: int | None
    height: int | None


class DetectedPatternOut(BaseModel):
    pattern: str
    suggested_level: int
    count: int
    sample_titles: list[str]


class ValidationRuleOut(BaseModel):
    code: str
    level: str
    passed: bool
    message: str


class ValidationReportOut(BaseModel):
    passed: bool
    level: str
    rules: list[ValidationRuleOut]
    summary: str


class ParseWarningOut(BaseModel):
    stage: str
    message: str


class ParseMetadataOut(BaseModel):
    total_chapters: int
    image_count: int
    table_count: int
    body_start_index: int
    body_start_detected_by: str
    format: str
    parse_time_ms: int


class ParseResponse(BaseModel):
    metadata: ParseMetadataOut
    chapters: list[ParsedNodeOut]
    assets: list[ParsedAssetOut]
    detected_patterns: list[DetectedPatternOut]
    validation: ValidationReportOut | None
    warnings: list[ParseWarningOut]
    review_required: int
    parse_method: str


# --------------------------------------------------------------------------- #
# 导入
# --------------------------------------------------------------------------- #
class ImportNodeIn(BaseModel):
    """导入树节点（复用 /parse 返回的 chapters，用户可在向导中调整）。"""

    title: str = ""
    content_type: str = "chapter"
    rich_content: str = ""
    skip_numbering: bool = False
    mark_status: str = "unmarked"
    # 来源样式名（动态标题字典方案 M2）：随 /parse 响应回传，导入时落到 ProcedureNode，
    # 供编辑器「记住此样式」反查归因（None=零样式编号标题或正文）。
    source_style_name: str | None = None
    children: list[ImportNodeIn] = Field(default_factory=list)


class ImportRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    folder_id: str
    description: str = Field(default="", max_length=10000)
    level_of_use: LevelOfUse = "reference"
    upload_token: str | None = None
    chapters: list[ImportNodeIn] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# 编辑器图片直传（Q214）
# --------------------------------------------------------------------------- #
class AssetUploadResult(BaseModel):
    asset_id: str
    url: str
    width: int | None
    height: int | None


def build_parse_response(
    result: ParseResult, assets: list[ParsedAssetOut], parse_time_ms: int
) -> ParseResponse:
    """ParseResult dataclass → HTTP 响应 schema。"""

    def node(n: object, order: int, parent_id: str | None) -> ParsedNodeOut:
        from app.parser.result import ParsedNode

        assert isinstance(n, ParsedNode)
        return ParsedNodeOut(
            id=n.id,
            title=n.title,
            level=n.level,
            order=order,
            parent_id=parent_id,
            content_type=n.content_type,
            rich_content=n.rich_content,
            skip_numbering=n.skip_numbering,
            confidence=n.confidence,
            confidence_tier=n.confidence_tier,
            mark_status=n.mark_status,
            heading_source=n.heading_source,
            source_style_name=n.source_style_name,
            source_numbering_pattern=n.source_numbering_pattern,
            children=[node(c, i, n.id) for i, c in enumerate(n.children)],
        )

    m = result.metadata
    validation = None
    if result.validation is not None:
        validation = ValidationReportOut(
            passed=result.validation.passed,
            level=result.validation.level,
            rules=[
                ValidationRuleOut(code=r.code, level=r.level, passed=r.passed, message=r.message)
                for r in result.validation.rules
            ],
            summary=result.validation.summary,
        )
    return ParseResponse(
        metadata=ParseMetadataOut(
            total_chapters=m.total_chapters,
            image_count=m.image_count,
            table_count=m.table_count,
            body_start_index=m.body_start_index,
            body_start_detected_by=m.body_start_detected_by,
            format=m.fmt,
            parse_time_ms=parse_time_ms,
        ),
        chapters=[node(c, i, None) for i, c in enumerate(result.chapters)],
        assets=assets,
        detected_patterns=[
            DetectedPatternOut(
                pattern=p.pattern,
                suggested_level=p.suggested_level,
                count=p.count,
                sample_titles=p.sample_titles,
            )
            for p in result.detected_patterns
        ],
        validation=validation,
        warnings=[ParseWarningOut(stage=w.stage, message=w.message) for w in result.warnings],
        review_required=result.review_required,
        parse_method=result.parse_method,
    )
