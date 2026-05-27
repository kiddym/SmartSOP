"""Eval harness 共享类型定义。

设计：所有评测产物（per-doc / 汇总报告）的字段都在此处定义，
runner / report / CLI 各自只依赖这个类型层。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Tier = Literal["style", "manual", "template"]


@dataclass(frozen=True)
class GtChapter:
    """单条 GT 章节项（normalize 后的扁平形式）。"""

    title: str           # normalize 后的标题文本（去全/半空白 + 小写）
    level: int           # 1 | 2 | 3
    source_idx: int      # 原 docx 段落顺序索引（用于稳定排序 / 对齐）


@dataclass(frozen=True)
class GroundTruth:
    """一份 docx 的完整 GT 信息。"""

    docx_path: Path
    tier: Tier
    chapters: tuple[GtChapter, ...]  # 扁平有序
    body_text: str                   # 拼接正文段落（不含标题/页眉/页脚）
    expected_empty: bool = False     # True 时该文档不进 P/R 分子分母（如目录文件）
    reviewed: bool = True            # Tier3 未抽样部分置 False，summary 用 ⚠️ 标识


@dataclass
class TitleMetrics:
    """单份文档的标题 P/R/F1 + 计数。"""

    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float


@dataclass
class DocResult:
    """单份文档的完整评测结果。"""

    docx_path: Path
    tier: Tier
    expected_empty: bool
    reviewed: bool
    title: TitleMetrics
    hierarchy_acc: float | None      # None 表示 TP=0 算不出
    content_cov: float
    fp_titles: list[str] = field(default_factory=list)
    fn_titles: list[str] = field(default_factory=list)
    level_mismatches: list[tuple[str, int, int]] = field(default_factory=list)  # (title, gt_lvl, pred_lvl)
    body_start_detected_by: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class EvalReport:
    """一轮评测的总报告（每份 docx 一个 DocResult，汇总在 report.py 算）。"""

    timestamp: str
    mode: Literal["standard", "smart"]
    subset: str
    docs: list[DocResult]
