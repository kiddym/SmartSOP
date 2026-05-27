"""report 单测：summary.md 红绿灯 + summary.json 可读 + diff 检测退化。"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.models import DocResult, EvalReport, TitleMetrics
from scripts.eval.report import write_diff, write_summary


def _mk_result(name: str, p: float, r: float, h: float | None, cov: float, tier: str = "style"):
    return DocResult(
        docx_path=Path(f"/tmp/{name}.docx"),
        tier=tier,
        expected_empty=False,
        reviewed=True,
        title=TitleMetrics(
            tp=8,
            fp=0,
            fn=2,
            precision=p,
            recall=r,
            f1=(2 * p * r / (p + r)) if (p + r) > 0 else 0.0,
        ),
        hierarchy_acc=h,
        content_cov=cov,
    )


def test_write_summary_creates_files(tmp_path):
    report = EvalReport(
        timestamp="2026-05-27-120000",
        mode="smart",
        subset="all",
        docs=[
            _mk_result("a", 1.0, 0.8, 0.95, 0.99),
            _mk_result("b", 1.0, 0.7, 0.90, 0.96, tier="manual"),
        ],
    )
    write_summary(report, tmp_path)
    assert (tmp_path / "summary.md").exists()
    assert (tmp_path / "summary.json").exists()
    md = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # 红绿灯五行
    assert "title_P_micro" in md
    assert "title_R_micro" in md
    assert "hierarchy_micro" in md
    assert "content_cov_micro" in md
    # JSON 可读回
    data = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert data["mode"] == "smart"
    assert len(data["docs"]) == 2
    # per_doc 目录有内容
    assert (tmp_path / "per_doc").is_dir()
    assert len(list((tmp_path / "per_doc").glob("*.json"))) == 2


def test_write_diff_detects_regression(tmp_path):
    baseline = EvalReport(
        timestamp="t0",
        mode="smart",
        subset="all",
        docs=[_mk_result("a", 1.0, 0.9, 0.95, 0.99)],
    )
    current = EvalReport(
        timestamp="t1",
        mode="smart",
        subset="all",
        docs=[_mk_result("a", 1.0, 0.8, 0.95, 0.99)],  # R 退了 0.1
    )
    write_diff(current, baseline, tmp_path)
    diff_md = (tmp_path / "diff_vs_baseline.md").read_text(encoding="utf-8")
    assert "a.docx" in diff_md
    assert "退化" in diff_md or "↓" in diff_md


def test_write_summary_excludes_expected_empty_from_thresholds(tmp_path):
    """expected_empty=True 的文档不进达标判定（spec §3.5）。"""
    report = EvalReport(
        timestamp="t",
        mode="smart",
        subset="all",
        docs=[
            _mk_result("real", 1.0, 1.0, 1.0, 1.0),
            DocResult(
                docx_path=Path("/tmp/directory.docx"),
                tier="template",
                expected_empty=True,
                reviewed=True,
                title=TitleMetrics(tp=0, fp=0, fn=0, precision=0.0, recall=0.0, f1=0.0),
                hierarchy_acc=None,
                content_cov=0.0,
            ),
        ],
    )
    write_summary(report, tmp_path)
    md = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # 主线只算 real.docx：R=1.0 → 应红绿灯全 ✅
    assert "1.0000" in md
    # expected_empty 文档标记 📂
    assert "📂" in md
