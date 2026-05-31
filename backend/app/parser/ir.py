"""中间表示（IR）：Normalizer 产出的顺序块流。

IR 块流 = 原 docx XML child order 的同构投影（word-parser-solution §6 顺序不变量）。
Structurer 仅在标题位置切分章节，不重排内容块。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.parser.styles import StyleIndex


@dataclass
class ImageRef:
    """块流中的一张图片引用（解析期，未落库）。"""

    rid: str
    part_name: str
    data: bytes
    ext: str
    anchor: bool = False
    placeholder: str = ""  # html 中 <img src> 占位（asset 阶段改写为临时/永久 URL）


@dataclass
class Block:
    """一个正文块：段落或表格。"""

    kind: str  # "paragraph" | "table"
    source_index: int
    html: str = ""
    text: str = ""
    style_id: str | None = None
    style_level: int | None = None  # styles.xml 反查层级（原始 1-9），None=非样式标题
    outline_lvl: int | None = None  # 段落 pPr 直接 outlineLvl（启发式信号）
    bold_ratio: float = 0.0
    max_font_pt: float | None = None
    alignment: str | None = None  # "center" / "right" / None
    is_toc_field: bool = False  # 处于 TOC 字段域内
    has_section_break: bool = False
    numbered: bool = False  # numPr 自动编号
    num_id: str | None = None  # numPr/numId（多级列表实例标识，跨实例不可直接比 ilvl）
    num_ilvl: int | None = None  # numPr/ilvl（0-based 列表嵌套深度，扁平样式下的层级信号）
    images: list[ImageRef] = field(default_factory=list)
    raw_image_count: int = 0  # 源元素内 a:blip 总数（含读取失败者），供 C001 对账
    raw_table_count: int = 0  # 源元素内 w:tbl 总数（含嵌套），供 C002 对账


@dataclass
class NormalizedDoc:
    """Normalizer 的完整产出。"""

    blocks: list[Block]
    total_image_count: int = 0  # 全文 blip 数（含表内、含正文起点之前）
    total_table_count: int = 0
    toc_field_end_index: int | None = None  # 最后一个 TOC 字段域闭合所在 block 索引
    style_index: StyleIndex | None = None
    raw_paragraph_count: int = 0  # body.iter(w:p) 全量计数，供 C003 段落完整性对账
