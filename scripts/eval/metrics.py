"""标题 P/R/F1（LCS 对齐）+ hierarchy + 3-gram content coverage。

设计参考：spec 2026-05-27-word-parser-polish-design.md §3。
- LCS 对齐保证顺序敏感，避免集合对齐遮蔽错位；
- hierarchy 仅在 TP 上算，FP/FN 不参与；
- content_cov 用 3-gram 集合 IoU，分母用 GT grams（"GT 里有多少被覆盖"）。
"""
from __future__ import annotations

import re
import unicodedata

from scripts.eval.models import GtChapter, TitleMetrics

_SPACE_RE = re.compile(r"\s+")


def normalize_title(s: str) -> str:
    """标题 normalize：NFKC（全→半）+ 去所有空白 + 小写。"""
    s = unicodedata.normalize("NFKC", s)
    s = _SPACE_RE.sub("", s)
    return s.lower()


def normalize_body(s: str) -> str:
    """正文 normalize：NFKC + 去所有空白 + 小写；保留标点（cell 边界信号）。"""
    s = unicodedata.normalize("NFKC", s)
    s = _SPACE_RE.sub("", s)
    return s.lower()


def lcs_align(gt: list[str], pred: list[str]) -> list[tuple[int, int]]:
    """LCS 对齐：返回 (gt_idx, pred_idx) 配对列表，i/j 双单调（保顺序）。"""
    m, n = len(gt), len(pred)
    if m == 0 or n == 0:
        return []
    # DP 表
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m):
        for j in range(n):
            if gt[i] == pred[j]:
                dp[i + 1][j + 1] = dp[i][j] + 1
            else:
                dp[i + 1][j + 1] = max(dp[i + 1][j], dp[i][j + 1])
    # 回溯配对
    pairs: list[tuple[int, int]] = []
    i, j = m, n
    while i > 0 and j > 0:
        if gt[i - 1] == pred[j - 1]:
            pairs.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    return list(reversed(pairs))


def title_prf(gt: list[GtChapter], pred: list[GtChapter]) -> TitleMetrics:
    """P/R/F1：标题文本 normalize 后 LCS 对齐计 TP/FP/FN。"""
    gt_norm = [normalize_title(c.title) for c in gt]
    pred_norm = [normalize_title(c.title) for c in pred]
    pairs = lcs_align(gt_norm, pred_norm)
    tp = len(pairs)
    fn = len(gt) - tp
    fp = len(pred) - tp
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return TitleMetrics(tp=tp, fp=fp, fn=fn, precision=p, recall=r, f1=f1)


def align_chapters(
    gt: list[GtChapter], pred: list[GtChapter]
) -> list[tuple[GtChapter, GtChapter]]:
    """对齐 GT 与预测 chapters，返回 (gt, pred) 对，供 hierarchy_acc / FP·FN 摘要用。"""
    gt_norm = [normalize_title(c.title) for c in gt]
    pred_norm = [normalize_title(c.title) for c in pred]
    return [(gt[i], pred[j]) for i, j in lcs_align(gt_norm, pred_norm)]


def hierarchy_acc(aligned: list[tuple[GtChapter, GtChapter]]) -> float | None:
    """仅在 TP 上算 level 匹配率；TP=0 返回 None（无法判定）。"""
    if not aligned:
        return None
    hits = sum(1 for g, p in aligned if g.level == p.level)
    return hits / len(aligned)


def content_cov_3gram(gt_text: str, pred_text: str) -> float:
    """3-gram 字符集 IoU，分母用 GT grams（"GT 里有多少被覆盖"）。"""
    g = normalize_body(gt_text)
    p = normalize_body(pred_text)
    if len(g) < 3:
        return 1.0  # 防御：GT 不足以形成 3-gram，视为满分
    gt_grams = set(zip(g, g[1:], g[2:], strict=False))
    if not gt_grams:
        return 1.0
    pred_grams = set(zip(p, p[1:], p[2:], strict=False)) if len(p) >= 3 else set()
    return len(gt_grams & pred_grams) / len(gt_grams)
