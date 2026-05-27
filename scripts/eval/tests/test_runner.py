"""runner 集成测：discover_docs + 端到端 standard subset 跑通。"""
from __future__ import annotations

from pathlib import Path

from scripts.eval.runner import discover_docs, run_eval

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_discover_docs_standard_subset_finds_5():
    docs = discover_docs(REPO_ROOT, subset="standard")
    assert len(docs) == 5
    assert all(d.name.endswith(".docx") for d in docs)


def test_discover_docs_unstyled_subset_finds_5():
    docs = discover_docs(REPO_ROOT, subset="unstyled")
    assert len(docs) == 5


def test_discover_docs_qms_subset_finds_26():
    """26 = 25 SOP + 1 程序文件目录.docx。"""
    docs = discover_docs(REPO_ROOT, subset="qms")
    assert len(docs) == 26


def test_discover_docs_all_subset_finds_36():
    docs = discover_docs(REPO_ROOT, subset="all")
    assert len(docs) == 36


def test_run_eval_standard_smart_mode_smoke():
    """5 份标准 SOP 在 smart 模式下端到端，所有 DocResult 字段都有值。"""
    report = run_eval(REPO_ROOT, subset="standard", mode="smart")
    assert len(report.docs) == 5
    assert all(d.tier == "style" for d in report.docs)
    assert all(d.title.precision >= 0 for d in report.docs)
    assert all(d.content_cov >= 0 for d in report.docs)
