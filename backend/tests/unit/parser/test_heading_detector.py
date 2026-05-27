"""启发式标题检测 + 编号词典单测（M6.2，§25.5 / Q200 / Q217）。"""

from __future__ import annotations

from app.parser import heading_detector as hd
from app.parser.ir import Block


def _para(text: str, *, bold: float = 0.0, font: float | None = None) -> Block:
    return Block(kind="paragraph", source_index=0, text=text, bold_ratio=bold, max_font_pt=font)


# --------------------------------------------------------------------------- #
# 编号词典（v4）
# --------------------------------------------------------------------------- #
def test_numbering_dot_depth_to_level() -> None:
    assert hd.classify_numbering("1. 目的").level == 1
    assert hd.classify_numbering("1.1 厂内").level == 2
    assert hd.classify_numbering("1.1.1 细则").level == 3


def test_numbering_space_form() -> None:
    m = hd.classify_numbering("1 目的")
    assert m is not None and m.kind == "heading" and m.level == 1


def test_page_number_not_heading() -> None:
    # "1 / 2" 页码不应判为标题
    assert hd.classify_numbering("1 / 2") is None
    assert hd.classify_numbering("3 / 12") is None


def test_chinese_numerals_and_chapters() -> None:
    assert hd.classify_numbering("一、目的").level == 1
    assert hd.classify_numbering("第3章 总则").level == 1
    assert hd.classify_numbering("第2节 范围").level == 2
    cond = hd.classify_numbering("第5条 权责")
    assert cond is not None and cond.kind == "weak_heading" and cond.level == 3


def test_dunhao_is_weak_heading() -> None:
    # Q217：N、改 weak_heading（需粗体/上下文）
    m = hd.classify_numbering("1、目的")
    assert m is not None and m.kind == "weak_heading"


def test_paren_numbering_is_list() -> None:
    for t in ["(一) 子项", "（1）子项", "1) 子项", "1）子项"]:
        m = hd.classify_numbering(t)
        assert m is not None and m.kind == "list"


# --------------------------------------------------------------------------- #
# 启发式评分
# --------------------------------------------------------------------------- #
def test_bold_numbered_short_is_medium_heading() -> None:
    stats = hd.DocStats(font_p85=None, single_font=True)
    score, level, _ = hd.score_block(_para("1 目的", bold=1.0), stats)
    assert score >= 0.5  # MEDIUM
    assert level == 1


def test_plain_body_text_is_content() -> None:
    stats = hd.DocStats(font_p85=None, single_font=True)
    score, _level, _ = hd.score_block(_para("规定记录控制的方法和要求。", bold=0.0), stats)
    assert score < 0.3  # NONE → content


def test_dunhao_bold_short_scores_but_nonbold_long_does_not() -> None:
    stats = hd.DocStats(font_p85=None, single_font=True)
    qms = _para("1、目的", bold=1.0)
    hazard = _para("1、设有消防设施并按规定维护保养确保完好有效随时可用于灭火处置。", bold=0.0)
    s_qms, lvl_qms, _ = hd.score_block(qms, stats)
    s_haz, _, _ = hd.score_block(hazard, stats)
    assert s_qms >= 0.5  # QMS 章节（粗短）→ 标题
    assert lvl_qms == 1
    assert s_haz < 0.5  # 危险源条款（长非粗）→ 不自动升


def test_heuristic_never_reaches_high() -> None:
    stats = hd.DocStats(font_p85=12.0, single_font=False)
    blk = _para("1 目的", bold=1.0, font=22.0)
    score, _, _ = hd.score_block(blk, stats)
    assert score <= 0.84  # 启发式封顶，永不自动 HIGH


def test_fused_subheading_heading_kind_keeps_half_credit() -> None:
    """eval r3：融合式 'N.N xxx 正文长段' (heading kind) 保留半额 num_points 0.125
    + single_font 补偿 0.10 → score >= LOW，可被 r2 'LOW + heading num' 规则升 chapter。
    """
    stats = hd.DocStats(font_p85=None, single_font=True)  # 02记录这类
    text = "3.1质量部是记录的归口管理部门,负责组织全公司记录表格的编制和校审。"
    blk = _para(text, bold=0.0)
    score, level, _ = hd.score_block(blk, stats)
    assert score >= hd.LOW  # 至少 LOW，才能被结构器升
    assert score < hd.MEDIUM  # 但不要直接 MEDIUM（避免覆盖 heuristic）
    assert level == 2


def test_fused_weak_heading_long_stays_vetoed() -> None:
    """weak_heading（N、）长段保持完全 veto——危险源 '1、设有消防设施...' 等 body 条款不升。"""
    stats = hd.DocStats(font_p85=None, single_font=True)
    text = "1、设有消防设施并按规定维护保养确保完好有效随时可用于灭火处置。"
    blk = _para(text, bold=0.0)
    score, _, _ = hd.score_block(blk, stats)
    assert score < hd.LOW  # 非粗长 weak_heading 应彻底压住


# --------------------------------------------------------------------------- #
# Signal Registry（L1 重构）
# --------------------------------------------------------------------------- #
def test_signal_registry_has_5_entries() -> None:
    """SIGNALS 注册表应含 5 个 signal（font_p85 / bold / numbering / short / center）。"""
    names = [s.name for s in hd.SIGNALS]
    assert set(names) == {"font_p85", "bold", "numbering", "short", "center"}
    assert len(hd.SIGNALS) == 5


def test_signal_breakdown_sums_to_score_block() -> None:
    """每个 signal 独立打分之和（带 cap）= score_block 主入口结果。"""
    stats = hd.DocStats(font_p85=12.0, single_font=False)
    blk = _para("1 目的", bold=1.0, font=22.0)
    ctx = hd.SignalContext(
        block=blk,
        num=hd.classify_numbering("1 目的"),
        stats=stats,
        is_short=True,
    )
    total = sum(sig.score(ctx) for sig in hd.SIGNALS)
    score, _level, _ = hd.score_block(blk, stats)
    assert abs(score - min(total, hd._HEURISTIC_CAP)) < 1e-9


def test_individual_signal_inspectable() -> None:
    """单个 signal 可独立调用做 ablation/调参。"""
    stats = hd.DocStats(font_p85=12.0, single_font=False)
    blk = _para("1 目的", bold=1.0, font=22.0)
    ctx = hd.SignalContext(
        block=blk,
        num=hd.classify_numbering("1 目的"),
        stats=stats,
        is_short=True,
    )
    by_name = {s.name: s for s in hd.SIGNALS}
    # bold ≥ 0.5 → 0.20
    assert abs(by_name["bold"].score(ctx) - 0.20) < 1e-9
    # short ≤ 30 → 0.10
    assert abs(by_name["short"].score(ctx) - 0.10) < 1e-9
    # font 22 ≥ p85 12 + not single_font → 0.25
    assert abs(by_name["font_p85"].score(ctx) - 0.25) < 1e-9


def test_list_marker_is_hard_veto_regardless_of_other_signals() -> None:
    """eval-r1：(一)/(N)/N) list 标记是 hard veto——即便 bold+短+大字号也不能升 heading。

    背景：有限空间作业管理办法.docx 35 个 FP 中 (一)~(六) 等共 ~15 个，
    它们 kind='list' 但其它信号累积仍可达 MEDIUM (0.5+) 被结构器升 chapter。
    """
    stats = hd.DocStats(font_p85=12.0, single_font=False)
    for text in [
        "(一)落实国家法律法规、标准规范对有限空间作业的要求;",
        "（1）子项",
        "1) 子项",
        "1）子项",
    ]:
        # 即便加粗 + 大字号 + 短段全开，list marker 必须 score < LOW
        blk = _para(text, bold=1.0, font=22.0)
        score, _, _ = hd.score_block(blk, stats)
        assert score < hd.LOW, (
            f"list marker {text!r} 应 hard veto (score < {hd.LOW})，实际 {score:.2f}"
        )


# --------------------------------------------------------------------------- #
# detected_patterns（按编号前缀归组）
# --------------------------------------------------------------------------- #
def test_detected_patterns_groups_by_prefix() -> None:
    blocks = [
        _para("1 目的", bold=1.0),
        _para("正文。"),
        _para("2 范围", bold=1.0),
        _para("3 职责", bold=1.0),
        _para("1.1 厂内", bold=1.0),
        _para("1.2 厂外", bold=1.0),
    ]
    patterns = hd.detect_patterns(blocks)
    by_key = {p.pattern: p for p in patterns}
    # N+空格 一级模式应计数 3（目的/范围/职责）
    l1 = next(p for p in patterns if p.suggested_level == 1)
    assert l1.count == 3
    # N.N 二级模式计数 2
    l2 = next(p for p in patterns if p.suggested_level == 2)
    assert l2.count == 2
    assert by_key  # 非空
