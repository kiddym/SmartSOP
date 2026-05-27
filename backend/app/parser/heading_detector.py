"""启发式标题检测（§25.5 / Q199 / Q200 / Q217，方案 C）。

零样式文档（无 heading 样式、纯编号/纯视觉）靠本模块产出 MEDIUM/LOW 候选
（标 review）。编号分级字典 v4（26 份 QMS 打磨）+ 误报抑制 + 等字号自适应。
启发式封顶 0.84，**永不自动 HIGH**（非标准标题必经人工确认）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.parser.ir import Block
from app.parser.result import DetectedPattern

# 置信度档阈值（§25.5）
HIGH = 0.85
MEDIUM = 0.5
LOW = 0.3
_HEURISTIC_CAP = 0.84
_SHORT_LEN = 30

_CN_NUM = "一二三四五六七八九十百零两"

# list（非标题）：(一)/（1）/N)/N）
_RE_PAREN = re.compile(rf"^[(（]\s*[{_CN_NUM}\d]+\s*[)）]")
_RE_NUM_PAREN = re.compile(r"^\d+[)）]")
_RE_PAGE = re.compile(r"^\d+\s*/\s*\d+$")  # 页码 "1 / 2"
_RE_CN_DUNHAO = re.compile(rf"^[{_CN_NUM}]+、")  # 一、
_RE_DI_ZHANG = re.compile(rf"^第[{_CN_NUM}\d]+章")
_RE_DI_JIE = re.compile(rf"^第[{_CN_NUM}\d]+节")
_RE_DI_TIAO = re.compile(rf"^第[{_CN_NUM}\d]+条")
_RE_LEADING_NUM = re.compile(r"^(\d+(?:\.\d+)*)")
_RE_CJK = re.compile(r"[一-鿿]")


@dataclass
class NumberingMatch:
    kind: str  # heading | weak_heading | list
    level: int
    pattern_key: str


@dataclass
class DocStats:
    font_p85: float | None
    single_font: bool


def classify_numbering(text: str) -> NumberingMatch | None:
    """编号分级字典 v4。返回 None 表示无编号信号。"""
    t = text.strip()
    if not t:
        return None

    # 页码
    if _RE_PAGE.match(t):
        return None

    # list（圆括号 / N)）
    if _RE_PAREN.match(t) or _RE_NUM_PAREN.match(t):
        return NumberingMatch(kind="list", level=0, pattern_key="(N)")

    # 中文编号
    if _RE_CN_DUNHAO.match(t):
        return NumberingMatch(kind="heading", level=1, pattern_key="一、")
    if _RE_DI_ZHANG.match(t):
        return NumberingMatch(kind="heading", level=1, pattern_key="第X章")
    if _RE_DI_JIE.match(t):
        return NumberingMatch(kind="heading", level=2, pattern_key="第X节")
    if _RE_DI_TIAO.match(t):
        return NumberingMatch(kind="weak_heading", level=3, pattern_key="第X条")

    # 阿拉伯编号（带点深度）
    m = _RE_LEADING_NUM.match(t)
    if m:
        num = m.group(1)
        depth = num.count(".") + 1
        level = min(depth, 3)
        rest = t[m.end() :]
        if rest.startswith("、"):  # N、/N.N、 → 顿号歧义 weak（Q217）
            key = "N、" if depth == 1 else "N" + ".N" * (depth - 1) + "、"
            return NumberingMatch(kind="weak_heading", level=level, pattern_key=key)
        if rest.startswith("."):  # 末尾点 "1." → heading
            return NumberingMatch(kind="heading", level=level, pattern_key="N.")
        if rest[:1].isspace():
            tail = rest.strip()
            if tail[:1].isdigit() or tail.startswith("/"):  # "1 2" / "1 / 2" 页码类
                return None
            key = "N 空格" if depth == 1 else "N" + ".N" * (depth - 1)
            return NumberingMatch(kind="heading", level=level, pattern_key=key)
        if rest and _RE_CJK.match(rest):
            # N+CJK 直连：depth>=2 (3.1质量部 / 4.1.1管理类) 是 unambiguous 融合式真子标题 → heading；
            # depth=1 (6相关文件) 仍歧义 → weak_heading 需 bold（Q217 + eval r3）
            if depth >= 2:
                return NumberingMatch(kind="heading", level=level, pattern_key=f"N{'.N' * (depth - 1)}+中文")
            return NumberingMatch(kind="weak_heading", level=level, pattern_key="N+中文")
    return None


def compute_doc_stats(blocks: list[Block]) -> DocStats:
    """全文字号分布：算 85 分位；单一字号时关闭字号信号（等字号自适应）。"""
    fonts = [
        b.max_font_pt
        for b in blocks
        if b.kind == "paragraph" and b.text.strip() and b.max_font_pt is not None
    ]
    distinct = sorted(set(fonts))
    if len(distinct) < 2:
        return DocStats(font_p85=None, single_font=True)
    ordered = sorted(fonts)
    idx = max(0, min(len(ordered) - 1, round(0.85 * (len(ordered) - 1))))
    return DocStats(font_p85=ordered[idx], single_font=False)


def tier_for(score: float) -> str | None:
    """分数 → 置信度档；NONE（< LOW）返回 None（视为 content）。"""
    if score >= HIGH:
        return "high"
    if score >= MEDIUM:
        return "medium"
    if score >= LOW:
        return "low"
    return None


def score_block(block: Block, stats: DocStats) -> tuple[float, int, str]:
    """启发式评分（封顶 0.84）。返回 ``(score, inferred_level, "heuristic")``。"""
    text = block.text.strip()
    if not text:
        return 0.0, 1, "heuristic"

    num = classify_numbering(text)
    # ── list 标记 hard veto：(一)/N) 等列表项即便短+粗+大字号也不能升 heading ──
    # 否则其它信号累积可达 MEDIUM (0.5+)，结构器会误升 chapter。
    # 见 eval-r1 调参：有限空间作业 FP 14/35 是 (一)~(六) 项；危险源 FP 中也有 N) 项。
    if num is not None and num.kind == "list":
        return 0.0, 1, "heuristic"

    is_short = len(text) <= _SHORT_LEN
    score = 0.0
    level = num.level if num else 1

    # 字号相对化（单一字号时归零）
    if (
        not stats.single_font
        and stats.font_p85 is not None
        and block.max_font_pt is not None
        and block.max_font_pt >= stats.font_p85
    ):
        score += 0.25

    # 加粗占比
    if block.bold_ratio >= 0.5:
        score += 0.20

    # 编号信号 + 误报抑制 + 等字号补偿
    num_points = 0.0
    if num is not None and num.kind != "list":
        if num.kind == "heading":
            num_points = 0.25
            # heading depth=1 长段（"1. 我们要遵循所有质量规定..." 假想 body）半额；
            # depth>=2 长段（"3.1质量部..." 融合式真子标题）保留全额（unambiguous 结构信号）
            if not is_short and num.level == 1:
                num_points = 0.125
        elif num.kind == "weak_heading":  # 顿号/无空格歧义：需粗体才计分（Q217）
            num_points = 0.25 if block.bold_ratio >= 0.5 else 0.0
            if not is_short:  # weak_heading depth=1 长段完全 veto（'1、设有消防...' 噪音）
                num_points = 0.0
        if stats.single_font and num_points > 0:  # 等字号自适应：编号补偿
            num_points += 0.10
    score += num_points

    # 短段
    if is_short:
        score += 0.10
    # 特殊对齐
    if block.alignment == "center":
        score += 0.05

    return min(score, _HEURISTIC_CAP), min(level, 3), "heuristic"


@dataclass
class _PatternAcc:
    level: int
    count: int = 0
    samples: list[str] = field(default_factory=list)


def detect_patterns(blocks: list[Block]) -> list[DetectedPattern]:
    """扫描全部正文段（含融合式长段）按编号前缀归组，供前端按组批量提升（Q200）。"""
    groups: dict[str, _PatternAcc] = {}
    for block in blocks:
        if block.kind != "paragraph":
            continue
        text = block.text.strip()
        if not text:
            continue
        num = classify_numbering(text)
        if num is None or num.kind == "list":
            continue
        acc = groups.setdefault(num.pattern_key, _PatternAcc(level=num.level))
        acc.count += 1
        if len(acc.samples) < 3:
            acc.samples.append(text)

    return [
        DetectedPattern(
            pattern=key,
            suggested_level=acc.level,
            count=acc.count,
            sample_titles=list(acc.samples),
        )
        for key, acc in groups.items()
    ]
