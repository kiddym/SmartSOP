"""OPC（Open Packaging Conventions）包遍历层。

直接以 zip + lxml 读取 .docx 内部 XML part，**不走 ``doc.paragraphs``**——按
``word/document.xml`` 的 ``<w:body>`` child order 流式遍历，保证顺序保真
（word-parser-solution §3.2 / DPMS 重构建议 P1）。
"""

from __future__ import annotations

import io
import zipfile
from typing import Final

from lxml import etree

# OOXML 命名空间
NS: Final[dict[str, str]] = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "v": "urn:schemas-microsoft-com:vml",
    "o": "urn:schemas-microsoft-com:office:office",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
}

_DOCUMENT_PART: Final = "word/document.xml"
_STYLES_PART: Final = "word/styles.xml"
_NUMBERING_PART: Final = "word/numbering.xml"
_RELS_PART: Final = "word/_rels/document.xml.rels"


def qn(tag: str) -> str:
    """``"w:p"`` → ``"{namespace}p"``（Clark notation）。"""
    prefix, _, name = tag.partition(":")
    return f"{{{NS[prefix]}}}{name}"


def local(tag: str) -> str:
    """剥离命名空间，返回本地标签名（``"{ns}tbl"`` → ``"tbl"``）。"""
    return tag.rpartition("}")[2] if "}" in tag else tag


def is_docx_bytes(data: bytes) -> bool:
    """OPC 嗅探（Q346）：是合法 zip 且含 ``word/document.xml``。"""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            return _DOCUMENT_PART in zf.namelist()
    except (zipfile.BadZipFile, OSError):
        return False


class DocxPackage:
    """已打开的 .docx 包，惰性解析各 XML part。"""

    def __init__(self, data: bytes) -> None:
        self._zip = zipfile.ZipFile(io.BytesIO(data))
        self._names = set(self._zip.namelist())
        self._cache: dict[str, etree._Element | None] = {}
        self._rels: dict[str, str] | None = None

    @classmethod
    def from_path(cls, path: str) -> DocxPackage:
        with open(path, "rb") as fh:
            return cls(fh.read())

    def has(self, name: str) -> bool:
        return name in self._names

    def read(self, name: str) -> bytes | None:
        if name not in self._names:
            return None
        return self._zip.read(name)

    def parse(self, name: str) -> etree._Element | None:
        if name in self._cache:
            return self._cache[name]
        raw = self.read(name)
        root = etree.fromstring(raw) if raw is not None else None
        self._cache[name] = root
        return root

    @property
    def document(self) -> etree._Element | None:
        return self.parse(_DOCUMENT_PART)

    @property
    def body(self) -> etree._Element | None:
        doc = self.document
        if doc is None:
            return None
        return doc.find(qn("w:body"))

    @property
    def styles(self) -> etree._Element | None:
        return self.parse(_STYLES_PART)

    @property
    def numbering(self) -> etree._Element | None:
        return self.parse(_NUMBERING_PART)

    def document_rels(self) -> dict[str, str]:
        """``rId`` → target（相对 ``word/`` 的路径，已规整为 zip 内全路径）。"""
        if self._rels is not None:
            return self._rels
        rels: dict[str, str] = {}
        root = self.parse(_RELS_PART)
        if root is not None:
            for rel in root:
                rid = rel.get("Id")
                target = rel.get("Target")
                if rid and target:
                    rels[rid] = _normalize_target(target)
        self._rels = rels
        return rels

    def media_part_for_rid(self, rid: str) -> str | None:
        target = self.document_rels().get(rid)
        if target and self.has(target):
            return target
        return None

    def read_media(self, rid: str) -> bytes | None:
        part = self.media_part_for_rid(rid)
        return self.read(part) if part else None

    def media_names(self) -> list[str]:
        return sorted(n for n in self._names if n.startswith("word/media/"))

    def discarded_parts(self) -> list[str]:
        """返回已存在且**非空**的 header*/footer*/footnotes/endnotes/comments part 名。

        normalizer 不读这些 part（设计如此），本方法用于在 ParseResult 出口推一条
        ``discarded_by_design`` warning，让前端能展示"已忽略 N 处页眉/页脚/..."。
        判定"非空"= part XML 含至少一个 ``<w:p>`` —— 避免空 stub 触发噪音 warning。
        """
        discarded: list[str] = []
        for name in sorted(self._names):
            if not name.startswith("word/"):
                continue
            tail = name[len("word/") :]
            # 匹配 header*.xml / footer*.xml / footnotes.xml / endnotes.xml / comments.xml
            if not (
                (tail.startswith("header") and tail.endswith(".xml"))
                or (tail.startswith("footer") and tail.endswith(".xml"))
                or tail in ("footnotes.xml", "endnotes.xml", "comments.xml")
            ):
                continue
            root = self.parse(name)
            if root is None:
                continue
            # 非空判定：含至少一个 w:p
            if root.find(".//" + qn("w:p")) is not None:
                discarded.append(name)
        return discarded


def _normalize_target(target: str) -> str:
    """把 rels 里相对 ``word/`` 的 Target 规整为 zip 内全路径。"""
    if target.startswith("/"):
        return target.lstrip("/")
    # 关系 Target 形如 "media/image1.png"，相对 word/document.xml 所在目录
    return f"word/{target}"
