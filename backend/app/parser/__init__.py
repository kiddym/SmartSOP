"""Word→结构化 SOP 解析器（Phase 6，DPMS document_parser 的 §19 重构移植）。

三阶段管线（word-parser-solution §2）：
- Stage 1 Normalizer：OPC 遍历 → IR 顺序块流（顺序保真 + 内联图 + 表格 + SDT）。
- Stage 2 Structurer：标题识别（standard 仅样式 / smart 样式+启发式置信度）→ 章节树。
- Stage 3 序列化：§19 每非 heading 块 → 独立 content 子节点（在 structurer 内完成）。

`standard` 与 `smart` 是同一管线的两个模式（方案 A = 方案 C 全 HIGH 退化情形，§25.5）。
图片在解析期为 ``media:{rid}`` 占位，由 asset 阶段（parse_service）改写为临时/永久 URL。
"""

from __future__ import annotations

from app.parser import normalizer, structurer, synonyms
from app.parser.result import ParseResult
from app.parser.utils.opc import DocxPackage

VALID_MODES = ("standard", "smart")


def parse_docx(
    data: bytes,
    mode: str = "smart",
    *,
    style_overrides: dict[str, int] | None = None,
    numbering_overrides: dict[str, tuple[str, int | None]] | None = None,
) -> ParseResult:
    """解析 .docx 字节流为 ParseResult（不落库、不做文件 I/O）。

    ``numbering_overrides``（M4b 编号体例）：{pattern_key: (kind, level)}，覆盖内置编号判定。
    """
    pkg = DocxPackage(data)
    syn = synonyms.load_default_synonyms()
    overrides = style_overrides or {}
    nd = normalizer.normalize(pkg, synonyms=syn, style_overrides=overrides)
    return structurer.structure(
        nd,
        pkg=pkg,
        mode=mode,
        synonyms=syn,
        style_overrides=overrides,
        numbering_overrides=numbering_overrides or {},
    )


__all__ = ["VALID_MODES", "parse_docx"]
