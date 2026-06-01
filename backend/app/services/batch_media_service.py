"""解析图写入批次 media 目录 + 占位 URL 改写（审阅预览用，不提升永久 asset）。

落库阶段（Plan 2）才从这里提升为永久 ProcedureAsset。
"""

from __future__ import annotations

from app import storage
from app.parser.result import ParsedNode, ParseResult
from app.parser.utils import images

_API_PREFIX = "/api/v1"


def _media_url(job_id: str, item_id: str, filename: str) -> str:
    return f"{_API_PREFIX}/batch-imports/{job_id}/items/{item_id}/media/{filename}"


def _safe_name(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in ("-", "_")) or "img"


def stage_media_and_rewrite(result: ParseResult, *, job_id: str, item_id: str) -> None:
    """把 result.image_refs 写入批次 media 目录，并就地改写 chapters 里的占位 URL。"""
    media = storage.batch_media_dir(job_id, item_id)
    media.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, str] = {}
    seen: set[str] = set()

    for ref in result.image_refs:
        if ref.rid in seen:
            continue
        seen.add(ref.rid)
        data, ext = ref.data, ref.ext.lower()
        if ext in images.VECTOR_EXTS:
            png = images.convert_to_png(data, ext)
            if png is not None:
                data, ext = png, ".png"
        filename = f"{_safe_name(ref.rid)}{ext}"
        (media / filename).write_bytes(data)
        mapping[ref.placeholder] = _media_url(job_id, item_id, filename)

    _rewrite(result.chapters, mapping)


def _rewrite(nodes: list[ParsedNode], mapping: dict[str, str]) -> None:
    if not mapping:
        return
    for node in nodes:
        value = node.rich_content
        if value:
            for placeholder, url in mapping.items():
                value = value.replace(f'"{placeholder}"', f'"{url}"')
            node.rich_content = value
        _rewrite(node.children, mapping)
