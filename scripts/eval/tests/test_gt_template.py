"""Tier 3 template GT 单测：ack 的 3 份 + 未 ack 的部分行为差异 + 目录文件特例。"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.eval.gt import extract_qms_gt, load_gt_template

REPO_ROOT = Path(__file__).resolve().parents[3]
QMS_DIR = REPO_ROOT / "docs" / "reference doc" / "typical word doc" / "extra doc"

ACKED = [
    ("05-基础设施控制程序.docx", 41),
    ("15-标识和可追溯性控制程序.docx", 29),       # ack 时剔除 row 11/12 噪音
    ("25-各级人员质量职责和权限规定.docx", 51),
]


@pytest.mark.parametrize("name,expected", ACKED)
def test_load_gt_template_acked_returns_reviewed(name, expected):
    gt = load_gt_template(QMS_DIR / name)
    assert gt.tier == "template"
    assert gt.reviewed is True
    assert len(gt.chapters) == expected
    assert all(1 <= c.level <= 3 for c in gt.chapters)


def test_extract_qms_gt_unacked_returns_unreviewed():
    """未抽样的 22 份 QMS SOP 走 extract_qms_gt fallback，reviewed=False。"""
    gt = load_gt_template(QMS_DIR / "10-沟通控制程序.docx")
    assert gt.reviewed is False
    assert len(gt.chapters) > 0


def test_extract_qms_gt_directory_marked_empty():
    """程序文件目录.docx 是非 SOP 目录文件，应被识别为 expected_empty。"""
    gt = load_gt_template(QMS_DIR / "程序文件目录.docx")
    assert gt.expected_empty is True
    assert len(gt.chapters) == 0


def test_extract_qms_gt_independent_from_parser_heading_detector():
    """关键反循环验证：gt.py 不能 import parser.heading_detector（避免循环验证，R1）。"""
    import scripts.eval.gt as gt_mod
    src = Path(gt_mod.__file__).read_text(encoding="utf-8")
    # 仅检查 import 语句，不查 docstring 里的说明文字
    forbidden_imports = [
        "from app.parser.heading_detector",
        "from app.parser import heading_detector",
        "import app.parser.heading_detector",
    ]
    for stmt in forbidden_imports:
        assert stmt not in src, (
            f"GT 抽取器不能 import parser 的 heading_detector（避免循环验证）；"
            f"see spec §2 Tier3 R1，违规：{stmt}"
        )
