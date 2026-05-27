"""Eval runner：发现文档 → 加 GT → 调 parser → 算指标 → 装配 DocResult。

直接调 `app.parser.parse_docx(data: bytes, mode)`，不走 HTTP（spec §1 关键决定）。
GT 路由：path 在无格式 dir 或属 manual GT 名单 → load_gt_manual；
       path 在 extra doc → load_gt_template（ack 优先，否则 extract_qms_gt）；
       否则 → load_gt_style；style 失败兜底 load_gt_manual（应在名单里）。
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from lxml import html

from app.parser import parse_docx
from app.parser.result import ParsedNode
from scripts.eval.gt import (
    load_gt_manual,
    load_gt_style,
    load_gt_template,
)
from scripts.eval.metrics import (
    align_chapters,
    content_cov_3gram,
    hierarchy_acc,
    lcs_align,
    normalize_title,
    title_prf,
)
from scripts.eval.models import DocResult, EvalReport, GroundTruth, GtChapter

Subset = Literal["all", "standard", "unstyled", "qms"]
Mode = Literal["standard", "smart"]

_STANDARD_DIR = Path("docs/reference doc/typical word doc")
_UNSTYLED_DIR = _STANDARD_DIR / "无格式标题word"
_QMS_DIR = _STANDARD_DIR / "extra doc"

# Tier 2 manual GT 名单（5 unstyled + QMS doc01）
_MANUAL_GT_BASENAMES = {
    "3.危险源监控措施",
    "02记录控制程序",
    "05人力资源控制程序",
    "CW-WI-7.4-01外发作业指导书及质量控制程序",
    "有限空间作业管理办法",
    "01-公司环境分析控制程序",
}


def discover_docs(repo_root: Path, subset: Subset) -> list[Path]:
    """枚举 docx；不递归 backend/var/。"""
    standard_dir = repo_root / _STANDARD_DIR
    unstyled_dir = repo_root / _UNSTYLED_DIR
    qms_dir = repo_root / _QMS_DIR

    out: list[Path] = []
    if subset in ("all", "standard"):
        # standard 目录下的 .docx，不递归（即不含子目录的 unstyled / extra doc）
        out.extend(sorted(p for p in standard_dir.glob("*.docx")))
    if subset in ("all", "unstyled"):
        out.extend(sorted(unstyled_dir.glob("*.docx")))
    if subset in ("all", "qms"):
        out.extend(sorted(qms_dir.glob("*.docx")))
    return out


def _select_loader(docx_path: Path) -> GroundTruth:
    """根据路径 + Tier 2 名单选 loader。"""
    if docx_path.stem in _MANUAL_GT_BASENAMES:
        return load_gt_manual(docx_path)
    if "extra doc" in docx_path.parts:
        return load_gt_template(docx_path)
    # 默认尝试 style；style 失败时退到 manual（应在名单里）
    try:
        return load_gt_style(docx_path)
    except ValueError:
        return load_gt_manual(docx_path)


def _flatten_chapters(nodes: list[ParsedNode]) -> list[GtChapter]:
    """ParseResult.chapters 树 → 扁平 GtChapter 序列（DFS，按文档顺序）。

    source_idx 用 enumerate 计数（仅用于排序稳定性，title_prf 不依赖此字段）。
    """
    out: list[GtChapter] = []
    counter = [0]

    def visit(n: ParsedNode) -> None:
        if n.content_type == "chapter":
            out.append(
                GtChapter(
                    title=normalize_title(n.title or ""),
                    level=n.level,
                    source_idx=counter[0],
                )
            )
        counter[0] += 1
        for c in n.children:
            visit(c)

    for n in nodes:
        visit(n)
    return out


def _strip_html(text: str) -> str:
    """lxml 安全去标签。空字符串保护。"""
    if not text or not text.strip():
        return ""
    try:
        el = html.fragment_fromstring(text, create_parent="div")
        return el.text_content()
    except Exception:
        # 回退：解析失败时按原文返回（极少见，rich_content 应是合法 HTML）
        return text


def _collect_parsed_body_text(nodes: list[ParsedNode]) -> str:
    """递归收集所有 content_type='content' 节点的 rich_content（去 HTML 标签后）。"""
    parts: list[str] = []

    def visit(n: ParsedNode) -> None:
        if n.content_type == "content" and n.rich_content:
            parts.append(_strip_html(n.rich_content))
        for c in n.children:
            visit(c)

    for n in nodes:
        visit(n)
    return "\n".join(parts)


def _eval_one(docx_path: Path, mode: Mode) -> DocResult:
    """单份评测：GT 加载 + parser 调用 + 指标计算 + FP/FN 诊断字段。"""
    gt = _select_loader(docx_path)
    parsed = parse_docx(docx_path.read_bytes(), mode=mode)
    pred_chapters = _flatten_chapters(parsed.chapters)
    pred_body = _collect_parsed_body_text(parsed.chapters)

    title_m = title_prf(list(gt.chapters), pred_chapters)
    aligned = align_chapters(list(gt.chapters), pred_chapters)
    h_acc = hierarchy_acc(aligned)

    # FP / FN 摘要（用 normalize 后的标题，便于人读）
    gt_norm = [normalize_title(c.title) for c in gt.chapters]
    pred_norm = [normalize_title(c.title) for c in pred_chapters]
    pairs = lcs_align(gt_norm, pred_norm)
    aligned_gt_idx = {i for i, _ in pairs}
    aligned_pred_idx = {j for _, j in pairs}
    fn_titles = [
        gt.chapters[i].title for i in range(len(gt.chapters)) if i not in aligned_gt_idx
    ]
    fp_titles = [
        pred_chapters[j].title
        for j in range(len(pred_chapters))
        if j not in aligned_pred_idx
    ]
    level_mm = [(g.title, g.level, p.level) for g, p in aligned if g.level != p.level]

    cov = content_cov_3gram(gt.body_text, pred_body)

    return DocResult(
        docx_path=docx_path,
        tier=gt.tier,
        expected_empty=gt.expected_empty,
        reviewed=gt.reviewed,
        title=title_m,
        hierarchy_acc=h_acc,
        content_cov=cov,
        fp_titles=fp_titles,
        fn_titles=fn_titles,
        level_mismatches=level_mm,
        body_start_detected_by=parsed.metadata.body_start_detected_by,
        warnings=[w.message for w in parsed.warnings],
    )


def run_eval(
    repo_root: Path,
    *,
    subset: Subset = "all",
    mode: Mode = "smart",
) -> EvalReport:
    docs = discover_docs(repo_root, subset)
    results = [_eval_one(d, mode) for d in docs]
    return EvalReport(
        timestamp=datetime.now(UTC).strftime("%Y-%m-%d-%H%M%S"),
        mode=mode,
        subset=subset,
        docs=results,
    )
