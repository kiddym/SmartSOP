"""GroundTruth 加载：Tier1 style（自动）/ Tier2 manual（fixtures）/ Tier3 template。

Tier 划分见 spec §2。Tier1 复用 parser 的 styles 反查（不接入启发式）。
Tier2 从 tests/fixtures/eval_gt/manual/<basename>.json 加载（由 Task 4 落盘）。
Tier3 用独立于 parser.classify_numbering 的正则抽取（QMS 同模板归纳）。
"""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

from lxml import etree

from app.parser import styles as styles_mod
from app.parser import synonyms as synonyms_mod
from scripts.eval.metrics import normalize_title
from scripts.eval.models import GroundTruth, GtChapter

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
_FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "eval_gt"
_MAX_LEVEL = 3


def _qn(tag: str) -> str:
    """w:p → {full-uri}p。"""
    p, local = tag.split(":")
    return f"{{{NS[p]}}}{local}"


def _load_styles_index(zf: zipfile.ZipFile) -> styles_mod.StyleIndex:
    """从 docx zip 加载 styles.xml → StyleIndex。"""
    try:
        with zf.open("word/styles.xml") as f:
            xml = f.read()
    except KeyError:
        return styles_mod.build_style_index(None)
    root = etree.fromstring(xml)
    return styles_mod.build_style_index(root)


def _iter_body_paragraphs(zf: zipfile.ZipFile):
    """按 child order yield body 段落 (idx, element, text)。仅 yield w:p（跳过 w:tbl 等）。

    idx 是 body iterchildren 的全局序号（含非 p 元素），方便和 parser 对齐。
    """
    with zf.open("word/document.xml") as f:
        tree = etree.parse(f)
    body = tree.getroot().find(_qn("w:body"))
    if body is None:
        return
    idx = 0
    for child in body.iterchildren():
        local = etree.QName(child).localname
        if local == "p":
            texts = child.xpath(".//w:t/text()", namespaces=NS)
            text = "".join(texts).strip()
            yield idx, child, text
        idx += 1


def _pstyle_id(p: etree._Element) -> str | None:
    """读 paragraph 的 pStyle val。"""
    pstyle = p.find(f"{_qn('w:pPr')}/{_qn('w:pStyle')}")
    if pstyle is None:
        return None
    return pstyle.get(_qn("w:val"))


def _paragraph_bold_ratio(p: etree._Element) -> float:
    """读 paragraph runs 的加粗占比（按字符数加权）。Tier 3 抽取器用。"""
    runs = p.findall(_qn("w:r"))
    total = 0
    bold_chars = 0
    for r in runs:
        text = "".join(r.xpath(".//w:t/text()", namespaces=NS))
        n = len(text)
        if n == 0:
            continue
        total += n
        rpr = r.find(_qn("w:rPr"))
        if rpr is not None:
            b = rpr.find(_qn("w:b"))
            if b is not None and b.get(_qn("w:val")) != "0":
                bold_chars += n
    return (bold_chars / total) if total > 0 else 0.0


# ───────────────────────── Tier 1: style 派生 ─────────────────────────


def load_gt_style(docx_path: Path) -> GroundTruth:
    """Tier 1：直接遍历 document.xml，对每段调 styles.classify_with_source 反查；
    level 4-6 压到 3。0 命中则抛 ValueError（应改用 Tier2/3）。

    同义词词典加载 parser 默认配置（章节标题 / 节标题 等中文自定义样式名 → level），
    这是"配置静态知识"不是启发式，per spec §2 Tier1 第 2 步。
    """
    syn = synonyms_mod.load_default_synonyms()
    with zipfile.ZipFile(docx_path) as zf:
        styles_index = _load_styles_index(zf)
        chapters: list[GtChapter] = []
        body_parts: list[str] = []
        first_chapter_seen = False  # body_text 只收 first chapter 之后的（对齐 parser body_start）

        for idx, p, text in _iter_body_paragraphs(zf):
            sid = _pstyle_id(p)
            level, _src = styles_mod.classify_with_source(
                sid, styles_index, synonyms=syn, style_overrides={}
            )
            if level is not None and text:
                first_chapter_seen = True
                chapters.append(
                    GtChapter(
                        title=normalize_title(text),
                        level=min(level, _MAX_LEVEL),
                        source_idx=idx,
                    )
                )
            elif text and first_chapter_seen:
                body_parts.append(text)

    if not chapters:
        raise ValueError(
            f"non-style document (0 styled headings): {docx_path.name}; "
            "should use Tier2 (manual) or Tier3 (template) GT"
        )

    return GroundTruth(
        docx_path=docx_path,
        tier="style",
        chapters=tuple(chapters),
        body_text="\n".join(body_parts),
        expected_empty=False,
        reviewed=True,
    )


# ───────────────────────── Tier 2: manual 复用 ─────────────────────────


def load_gt_manual(docx_path: Path) -> GroundTruth:
    """Tier 2：从 tests/fixtures/eval_gt/manual/<basename>.json 加载 + lxml 拼 body_text。

    JSON 由 Task 4 的 draft_manual_gt.py 生成 + 用户 ack 后落盘。
    """
    fixture = _FIXTURES_ROOT / "manual" / f"{docx_path.stem}.json"
    if not fixture.exists():
        raise FileNotFoundError(f"manual GT not found for {docx_path.name}: {fixture}")
    data = json.loads(fixture.read_text(encoding="utf-8"))
    chapters = tuple(
        GtChapter(
            title=normalize_title(c["title"]),
            level=int(c["level"]),
            source_idx=int(c.get("source_idx", i)),
        )
        for i, c in enumerate(data["chapters"])
    )
    # body_text 用 lxml 拼，但去掉与 chapter title 同行的段；同时只收 first chapter 之后的（对齐 parser body_start）
    with zipfile.ZipFile(docx_path) as zf:
        title_idxs = {c.source_idx for c in chapters}
        first_chapter_idx = min(title_idxs) if title_idxs else 0
        parts = [
            text
            for idx, _p, text in _iter_body_paragraphs(zf)
            if text and idx not in title_idxs and idx >= first_chapter_idx
        ]
    return GroundTruth(
        docx_path=docx_path,
        tier="manual",
        chapters=chapters,
        body_text="\n".join(parts),
    )


# ───────────────────────── Tier 3: template 归纳 ─────────────────────────

# 独立的 QMS 编号正则（不复用 parser.classify_numbering，避免循环验证）
_QMS_L3 = re.compile(r"^\d+\.\d+\.\d+")
_QMS_L2 = re.compile(r"^\d+\.\d+\b")
_QMS_L1 = re.compile(r"^[1-7]\s*[、.]?\s*\S")
_DIRECTORY_HINT = "目录"


def extract_qms_gt(docx_path: Path, *, require_bold_for_l1: bool = True) -> GroundTruth:
    """Tier 3：QMS 模板归纳 GT 抽取器（独立于 parser）。

    L1 必须粗体短段（避免吞 "1、xxx" 的列表正文）；L2/L3 仅看编号深度。
    """
    chapters: list[GtChapter] = []
    body_parts: list[str] = []
    first_chapter_seen = False  # 对齐 parser body_start
    with zipfile.ZipFile(docx_path) as zf:
        for idx, p, text in _iter_body_paragraphs(zf):
            if not text:
                continue
            level: int | None = None
            if _QMS_L3.match(text):
                level = 3
            elif _QMS_L2.match(text):
                level = 2
            elif _QMS_L1.match(text) and len(text) <= 30:
                bold = _paragraph_bold_ratio(p) if require_bold_for_l1 else 1.0
                if bold >= 0.5:
                    level = 1
            if level is not None:
                first_chapter_seen = True
                chapters.append(
                    GtChapter(
                        title=normalize_title(text),
                        level=level,
                        source_idx=idx,
                    )
                )
            elif first_chapter_seen:
                body_parts.append(text)
    expected_empty = len(chapters) == 0 and _DIRECTORY_HINT in docx_path.name
    return GroundTruth(
        docx_path=docx_path,
        tier="template",
        chapters=tuple(chapters),
        body_text="\n".join(body_parts),
        expected_empty=expected_empty,
        reviewed=False,  # 默认未 ack；ack 的 3 份在 load_gt_template 里改 True
    )


def load_gt_template(docx_path: Path) -> GroundTruth:
    """Tier 3 入口：优先读 fixture（已 ack）；否则走 extract_qms_gt（reviewed=False）。"""
    fixture = _FIXTURES_ROOT / "template_ack" / f"{docx_path.stem}.json"
    if fixture.exists():
        data = json.loads(fixture.read_text(encoding="utf-8"))
        chapters = tuple(
            GtChapter(
                title=normalize_title(c["title"]),
                level=int(c["level"]),
                source_idx=int(c.get("source_idx", i)),
            )
            for i, c in enumerate(data["chapters"])
        )
        # body_text 用 extract_qms_gt 的方式拼（保持口径一致）
        extracted = extract_qms_gt(docx_path)
        return GroundTruth(
            docx_path=docx_path,
            tier="template",
            chapters=chapters,
            body_text=extracted.body_text,
            expected_empty=extracted.expected_empty,
            reviewed=True,
        )
    return extract_qms_gt(docx_path)
