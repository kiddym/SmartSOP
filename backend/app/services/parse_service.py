"""解析编排（§9.1 / §25 / Q345）。

读取临时 docx → 线程执行器跑解析（30s 超时 → PARSE_TIMEOUT）→ 抽临时图改写
占位 → 组装响应。standard 模板 error → PARSE_TEMPLATE_INVALID；空树 →
PARSE_NO_HEADINGS（standard 已由模板 error 拦截，此处主要覆盖 smart 零命中）。
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.errors import app_error, bad_request
from app.parser import VALID_MODES, parse_docx
from app.parser.result import ParsedNode, ParseResult, ParseWarning, ValidationReport
from app.schemas.parse import ParseMethodOut, ParseResponse, build_parse_response
from app.services import heading_rule_service, numbering_profile_service, upload_service

_METHODS = [
    ParseMethodOut(
        key="standard",
        label="标准模式",
        description="仅依赖 Word 标题样式；模板规范的文档识别最准，违规即拒绝。",
    ),
    ParseMethodOut(
        key="smart",
        label="智能模式",
        description="样式 + 启发式置信度分级；覆盖零样式/不规范文档，低置信项标 review 待确认。",
    ),
]


def list_methods() -> list[ParseMethodOut]:
    return _METHODS


def parse(token: str, mode: str, *, db: Session | None = None) -> ParseResponse:
    if mode not in VALID_MODES:
        raise bad_request("PARSE_FAILED", f"未知解析模式：{mode}", field="parse_mode")
    data = upload_service.read_docx(token)

    # 动态标题字典：读 active 样式规则 + 编号体例注入解析（M1 + M4b）。
    style_overrides = heading_rule_service.active_style_overrides(db) if db is not None else {}
    numbering_overrides = (
        numbering_profile_service.active_numbering_overrides(db) if db is not None else {}
    )

    start = time.monotonic()
    try:
        result = _run_with_timeout(data, mode, style_overrides, numbering_overrides)
    except FuturesTimeout as exc:
        raise app_error(
            status.HTTP_504_GATEWAY_TIMEOUT, "PARSE_TIMEOUT", "解析超时（超过 30 秒）"
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:  # 解析任何异常归一为 PARSE_FAILED
        raise bad_request("PARSE_FAILED", f"解析失败：{exc}") from exc

    if mode == "standard" and result.validation is not None and result.validation.level == "error":
        raise _template_invalid(result.validation)
    if result.metadata.total_chapters == 0:
        raise bad_request("PARSE_NO_HEADINGS", "未识别到任何标题，无法生成章节树")

    mapping, assets, failed_vectors = upload_service.write_temp_media(token, result.image_refs)
    _rewrite_placeholders(result, mapping)
    n_failed = _swap_failed_vectors(result, failed_vectors)
    if n_failed:
        result.warnings.append(
            ParseWarning(
                stage="image",
                message=f"本环境无法转换 {n_failed} 张矢量图（EMF/WMF），将以占位符导入",
                severity="blocking",
            )
        )
    parse_time_ms = int((time.monotonic() - start) * 1000)
    return build_parse_response(result, assets, parse_time_ms)


def _run_with_timeout(
    data: bytes,
    mode: str,
    style_overrides: dict[str, int] | None = None,
    numbering_overrides: dict[str, tuple[str, int | None]] | None = None,
) -> ParseResult:
    """线程执行器跑 CPU 密集解析；超时抛 FuturesTimeout（孤儿线程允许跑完，Q345）。"""
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        parse_docx, data, mode,
        style_overrides=style_overrides, numbering_overrides=numbering_overrides,
    )
    try:
        return future.result(timeout=settings.parse_timeout_seconds)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _rewrite_placeholders(result: ParseResult, mapping: dict[str, str]) -> None:
    def rewrite_html(value: str) -> str:
        if not value or not mapping:
            return value
        out = value
        for placeholder, url in mapping.items():
            out = out.replace(f'"{placeholder}"', f'"{url}"')
        return out

    def walk(nodes: list[ParsedNode]) -> None:
        for node in nodes:
            node.rich_content = rewrite_html(node.rich_content)
            walk(node.children)

    walk(result.chapters)


_VECTOR_PLACEHOLDER = '<div class="sop-ph" data-ph="vector">[矢量图无法转换]</div>'


def _swap_failed_vectors(result: ParseResult, failed_vectors: set[str]) -> int:
    """把失败矢量图的 <img src="media:rid"/> 换成可见占位，含占位的节点标 review。
    返回实际被替换的不同矢量图张数（去重，供告警文案）。"""
    if not failed_vectors:
        return 0
    swapped: set[str] = set()

    def walk(nodes: list[ParsedNode]) -> None:
        for node in nodes:
            node_swapped = False
            for placeholder in failed_vectors:
                target = f'<img src="{placeholder}"/>'
                if target in node.rich_content:
                    node.rich_content = node.rich_content.replace(target, _VECTOR_PLACEHOLDER)
                    swapped.add(placeholder)
                    node_swapped = True
            if node_swapped:
                node.mark_status = "review"
            walk(node.children)

    walk(result.chapters)
    return len(swapped)


def _template_invalid(report: ValidationReport) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "code": "PARSE_TEMPLATE_INVALID",
            "message": report.summary,
            "validation": {
                "passed": report.passed,
                "level": report.level,
                "summary": report.summary,
                "rules": [
                    {"code": r.code, "level": r.level, "passed": r.passed, "message": r.message}
                    for r in report.rules
                ],
            },
        },
    )
