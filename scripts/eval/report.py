"""Eval 报告生成：summary.md 红绿灯 + summary.json 留档 + diff_vs_baseline.md。

主线指标按 Tier1 + Tier2（reviewed=True 且 tier∈{style, manual}）算，对照
spec §3.4 严强阈值出红绿灯；Tier3 单独分档报，不进达标判定。
expected_empty 文档（如程序文件目录.docx）不入主线分母（spec §3.5）。
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from scripts.eval.models import DocResult, EvalReport

# 严强阈值（spec §3.4）
TH_P = 0.98
TH_R = 0.85
TH_R_PER_DOC = 0.60
TH_HIERARCHY = 0.95
TH_COV = 0.98


def _micro(docs: list[DocResult], field: str) -> float:
    """按 TP+FN / TP+FP / TP 加权 micro。"""
    if not docs:
        return 1.0
    if field == "title_p":
        tp = sum(d.title.tp for d in docs)
        fp = sum(d.title.fp for d in docs)
        return tp / (tp + fp) if (tp + fp) > 0 else 1.0
    if field == "title_r":
        tp = sum(d.title.tp for d in docs)
        fn = sum(d.title.fn for d in docs)
        return tp / (tp + fn) if (tp + fn) > 0 else 1.0
    if field == "title_f1":
        p = _micro(docs, "title_p")
        r = _micro(docs, "title_r")
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    if field == "hierarchy":
        has_tp = [d for d in docs if d.hierarchy_acc is not None]
        total_tp = sum(d.title.tp for d in has_tp)
        if total_tp == 0:
            return 1.0
        return sum((d.hierarchy_acc or 0) * d.title.tp for d in has_tp) / total_tp
    if field == "content_cov":
        # 用各文档 cov 的算术平均（cov 已是比例，3-gram 集大小差异不大）
        return sum(d.content_cov for d in docs) / len(docs)
    raise ValueError(f"unknown micro field: {field}")


def _macro(docs: list[DocResult], field: str) -> float:
    if not docs:
        return 1.0
    if field == "title_p":
        return sum(d.title.precision for d in docs) / len(docs)
    if field == "title_r":
        return sum(d.title.recall for d in docs) / len(docs)
    if field == "title_f1":
        return sum(d.title.f1 for d in docs) / len(docs)
    if field == "hierarchy":
        vals = [d.hierarchy_acc for d in docs if d.hierarchy_acc is not None]
        return sum(vals) / len(vals) if vals else 1.0
    if field == "content_cov":
        return sum(d.content_cov for d in docs) / len(docs)
    raise ValueError(f"unknown macro field: {field}")


def _light(value: float, threshold: float, *, lower_bound: bool = True) -> str:
    """红绿灯：lower_bound=True 表示 value ≥ threshold 才通过。"""
    if lower_bound:
        return "✅" if value >= threshold else "❌"
    return "✅" if value <= threshold else "❌"


def _docresult_to_dict(d: DocResult) -> dict:
    return {
        "docx_path": str(d.docx_path),
        "tier": d.tier,
        "expected_empty": d.expected_empty,
        "reviewed": d.reviewed,
        "title": asdict(d.title),
        "hierarchy_acc": d.hierarchy_acc,
        "content_cov": d.content_cov,
        "fp_titles": d.fp_titles,
        "fn_titles": d.fn_titles,
        "level_mismatches": d.level_mismatches,
        "body_start_detected_by": d.body_start_detected_by,
        "warnings": d.warnings,
    }


def write_summary(report: EvalReport, out_dir: Path) -> None:
    """写 summary.md（红绿灯 + per-doc 表 + Tier 分档汇总）+ summary.json + per_doc/<name>.json。"""
    out_dir.mkdir(parents=True, exist_ok=True)

    # 排除 expected_empty 进入达标分母
    eligible = [d for d in report.docs if not d.expected_empty]
    # 主线 = Tier1 + Tier2（reviewed=True 且 tier ∈ {style, manual}）
    mainline = [d for d in eligible if d.reviewed and d.tier in ("style", "manual")]

    p_micro = _micro(mainline, "title_p")
    r_micro = _micro(mainline, "title_r")
    f1_micro = _micro(mainline, "title_f1")
    h_micro = _micro(mainline, "hierarchy")
    c_micro = _micro(mainline, "content_cov")
    min_r_doc = min(mainline, key=lambda d: d.title.recall, default=None)
    min_r = min_r_doc.title.recall if min_r_doc else 1.0
    min_r_name = min_r_doc.docx_path.name if min_r_doc else "-"

    lines: list[str] = [
        f"# Eval Report — {report.timestamp} ({report.mode}, subset={report.subset})",
        "",
        "## 严强阈值（主线 = Tier1 + Tier2，必须全 ✅ 才算闭环结束）",
        "",
        f"- [{_light(p_micro, TH_P)}] title_P_micro ≥ {TH_P}     当前: {p_micro:.4f}",
        f"- [{_light(r_micro, TH_R)}] title_R_micro ≥ {TH_R}     当前: {r_micro:.4f}",
        f"- [{_light(min_r, TH_R_PER_DOC)}] no_doc_with_R < {TH_R_PER_DOC}    最低: {min_r_name} (R={min_r:.2f})",
        f"- [{_light(h_micro, TH_HIERARCHY)}] hierarchy_micro ≥ {TH_HIERARCHY}    当前: {h_micro:.4f}",
        f"- [{_light(c_micro, TH_COV)}] content_cov_micro ≥ {TH_COV}  当前: {c_micro:.4f}",
        "",
        f"主线 docs: {len(mainline)} / 合计 docs: {len(report.docs)}",
        "",
        "## Per-Doc",
        "",
        "| 文档 | tier | reviewed | P | R | F1 | hier | cov | body_start_by | FP | FN |",
        "|---|---|:---:|---:|---:|---:|---:|---:|---|---:|---:|",
    ]
    for d in report.docs:
        h_str = f"{d.hierarchy_acc:.2f}" if d.hierarchy_acc is not None else "-"
        rev = "✅" if d.reviewed else "⚠️"
        if d.expected_empty:
            rev = "📂"
        lines.append(
            f"| {d.docx_path.name} | {d.tier} | {rev} | "
            f"{d.title.precision:.2f} | {d.title.recall:.2f} | {d.title.f1:.2f} | "
            f"{h_str} | {d.content_cov:.2f} | {d.body_start_detected_by or '-'} | "
            f"{d.title.fp} | {d.title.fn} |"
        )

    # Tier 分档汇总
    lines.extend(["", "## Tier 分档 micro", ""])
    lines.append("| tier | docs | P_micro | R_micro | F1_micro | hier_micro | cov_macro |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for tier in ("style", "manual", "template"):
        tier_docs = [d for d in eligible if d.tier == tier]
        if not tier_docs:
            continue
        lines.append(
            f"| {tier} | {len(tier_docs)} | "
            f"{_micro(tier_docs, 'title_p'):.4f} | {_micro(tier_docs, 'title_r'):.4f} | "
            f"{_micro(tier_docs, 'title_f1'):.4f} | {_micro(tier_docs, 'hierarchy'):.4f} | "
            f"{_micro(tier_docs, 'content_cov'):.4f} |"
        )
    # Tier 3 未抽样部分单独提示
    unreviewed = [d for d in eligible if d.tier == "template" and not d.reviewed]
    if unreviewed:
        lines.append("")
        lines.append(
            f"⚠️ Tier3 未抽样 ack 的 {len(unreviewed)} 份（reviewed=False）不进主线阈值，"
            "见 spec §2 Tier3 cf R1"
        )

    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # summary.json
    data = {
        "timestamp": report.timestamp,
        "mode": report.mode,
        "subset": report.subset,
        "thresholds": {
            "p_micro": p_micro,
            "r_micro": r_micro,
            "f1_micro": f1_micro,
            "min_r_per_doc": min_r,
            "min_r_doc": min_r_name,
            "hierarchy_micro": h_micro,
            "content_cov_micro": c_micro,
        },
        "docs": [_docresult_to_dict(d) for d in report.docs],
    }
    (out_dir / "summary.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # per_doc/<name>.json
    per_dir = out_dir / "per_doc"
    per_dir.mkdir(exist_ok=True)
    for d in report.docs:
        (per_dir / f"{d.docx_path.stem}.json").write_text(
            json.dumps(_docresult_to_dict(d), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def write_diff(current: EvalReport, baseline: EvalReport, out_dir: Path) -> None:
    """对照 baseline 出每份 doc 的指标 Δ。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    base_by = {d.docx_path.name: d for d in baseline.docs}
    lines: list[str] = [
        f"# Diff vs Baseline ({baseline.timestamp} → {current.timestamp})",
        "",
        "| 文档 | ΔP | ΔR | ΔF1 | Δhier | Δcov | 状态 |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]

    def _fmt_delta(a: float, b_val: float) -> str:
        diff = a - b_val
        if diff > 0.005:
            return f"+{diff:.3f} ↑"
        if diff < -0.005:
            return f"{diff:.3f} ↓ 退化"
        return "="

    for d in current.docs:
        b = base_by.get(d.docx_path.name)
        if b is None:
            lines.append(f"| {d.docx_path.name} | new | - | - | - | - | 新增 |")
            continue
        dp = _fmt_delta(d.title.precision, b.title.precision)
        dr = _fmt_delta(d.title.recall, b.title.recall)
        df = _fmt_delta(d.title.f1, b.title.f1)
        if d.hierarchy_acc is not None and b.hierarchy_acc is not None:
            dh = _fmt_delta(d.hierarchy_acc, b.hierarchy_acc)
        else:
            dh = "-"
        dc = _fmt_delta(d.content_cov, b.content_cov)
        cells = [dp, dr, df, dh, dc]
        regressed = any("退化" in c for c in cells)
        improved = any("↑" in c for c in cells)
        status = "🔴 退化" if regressed else ("🟢 升" if improved else "—")
        lines.append(f"| {d.docx_path.name} | {dp} | {dr} | {df} | {dh} | {dc} | {status} |")

    (out_dir / "diff_vs_baseline.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
