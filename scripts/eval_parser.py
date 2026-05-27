#!/usr/bin/env python
"""Word 解析器评测 harness CLI（spec §1）。

Usage:
    backend/.venv/bin/python scripts/eval_parser.py
    backend/.venv/bin/python scripts/eval_parser.py --subset standard
    backend/.venv/bin/python scripts/eval_parser.py --baseline .eval-reports/baseline/summary.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "backend"))

from scripts.eval.models import DocResult, EvalReport, TitleMetrics  # noqa: E402
from scripts.eval.report import write_diff, write_summary  # noqa: E402
from scripts.eval.runner import run_eval  # noqa: E402


def _load_eval_report(data: dict) -> EvalReport:
    """从 summary.json data 反序列化 EvalReport（baseline diff 用）。"""
    docs = [
        DocResult(
            docx_path=Path(d["docx_path"]),
            tier=d["tier"],
            expected_empty=d["expected_empty"],
            reviewed=d["reviewed"],
            title=TitleMetrics(**d["title"]),
            hierarchy_acc=d["hierarchy_acc"],
            content_cov=d["content_cov"],
            fp_titles=d.get("fp_titles", []),
            fn_titles=d.get("fn_titles", []),
            level_mismatches=d.get("level_mismatches", []),
            body_start_detected_by=d.get("body_start_detected_by"),
            warnings=d.get("warnings", []),
        )
        for d in data["docs"]
    ]
    return EvalReport(
        timestamp=data["timestamp"], mode=data["mode"], subset=data["subset"], docs=docs
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Word parser evaluation harness")
    ap.add_argument(
        "--subset",
        choices=["all", "standard", "unstyled", "qms"],
        default="all",
        help="docx 子集（默认 all = 36 份）",
    )
    ap.add_argument("--mode", choices=["standard", "smart"], default="smart")
    ap.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="path to a previous summary.json for diff",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output dir (default .eval-reports/<ts>/)",
    )
    args = ap.parse_args(argv)

    ts = datetime.now(UTC).strftime("%Y-%m-%d-%H%M%S")
    out = args.out or (_ROOT / ".eval-reports" / ts)
    out.mkdir(parents=True, exist_ok=True)

    print(f"[eval] subset={args.subset} mode={args.mode} → {out}")
    report = run_eval(_ROOT, subset=args.subset, mode=args.mode)
    write_summary(report, out)

    if args.baseline:
        baseline_data = json.loads(args.baseline.read_text(encoding="utf-8"))
        baseline = _load_eval_report(baseline_data)
        write_diff(report, baseline, out)
        print(f"[eval] diff vs baseline → {out / 'diff_vs_baseline.md'}")

    # 终端简报：主线 P/R + 总文档数
    eligible = [
        d
        for d in report.docs
        if not d.expected_empty and d.reviewed and d.tier in ("style", "manual")
    ]
    tp = sum(d.title.tp for d in eligible)
    fp = sum(d.title.fp for d in eligible)
    fn = sum(d.title.fn for d in eligible)
    p = tp / (tp + fp) if (tp + fp) else 1.0
    r = tp / (tp + fn) if (tp + fn) else 1.0
    print(f"[eval] mainline P={p:.4f} R={r:.4f} ({len(eligible)} docs in mainline / {len(report.docs)} total)")
    print(f"[eval] full report → {out / 'summary.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
