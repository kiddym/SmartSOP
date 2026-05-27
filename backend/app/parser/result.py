"""解析结果数据结构（内部 dataclass，snake_case）。

parse_service 经 schemas/parse.py 将其映射为 HTTP 响应 schema（同为 snake_case，
Q350，对齐既有 API）。对齐 api-specification.md `POST /parse` 响应。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.parser.ir import ImageRef


@dataclass
class ParsedNode:
    """解析出的章节树节点（chapter 或 content）。"""

    id: str
    title: str
    level: int
    content_type: str  # "chapter" | "content"
    rich_content: str = ""
    skip_numbering: bool = False
    confidence: float = 1.0
    confidence_tier: str = "high"  # high | medium | low
    mark_status: str = "unmarked"  # unmarked | review
    heading_source: str | None = None  # style|synonym|outline|based_on|heuristic
    children: list[ParsedNode] = field(default_factory=list)


@dataclass
class DetectedPattern:
    """零样式文档的编号模式建议（Q200，前端按组选择性批量提升）。"""

    pattern: str
    suggested_level: int
    count: int
    sample_titles: list[str]


@dataclass
class ValidationRule:
    code: str
    level: str  # pass | warning | error
    passed: bool
    message: str


@dataclass
class ValidationReport:
    passed: bool
    level: str  # pass | warning | error
    rules: list[ValidationRule]
    summary: str


@dataclass
class ParseWarning:
    stage: str  # boundary | completeness | image | structure
    message: str


@dataclass
class ParseMetadata:
    total_chapters: int
    image_count: int
    table_count: int
    body_start_index: int
    body_start_detected_by: str
    fmt: str = "docx"


@dataclass
class ParseResult:
    metadata: ParseMetadata
    chapters: list[ParsedNode]
    parse_method: str  # standard | smart
    detected_patterns: list[DetectedPattern] = field(default_factory=list)
    validation: ValidationReport | None = None
    warnings: list[ParseWarning] = field(default_factory=list)
    review_required: int = 0
    image_refs: list[ImageRef] = field(default_factory=list)  # 供 asset 阶段抽图
