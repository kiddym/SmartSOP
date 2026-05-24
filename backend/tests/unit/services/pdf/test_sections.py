"""pdf.sections 单测：15 型占位符 / 封面状态 / 修订过滤 / 附件区段 / 步骤渲染。"""

from __future__ import annotations

from datetime import UTC, datetime

from reportlab.platypus import Paragraph, Table

from app.services.pdf import fonts, sections
from app.services.pdf.context import (
    AttachmentData,
    ChapterData,
    ProcedureData,
    RenderData,
    StepData,
)

fonts.register_fonts()


def _proc(**kw: object) -> ProcedureData:
    base: dict[str, object] = dict(
        id="p1",
        code="QC-00001",
        name="启动 SOP",
        version=1,
        status="DRAFT",
        level_of_use="continuous",
        risk_level=3,
        quality_level=2,
        description="",
        custom_values={},
        version_update_notes="",
        version_change_log=[],
        created_at=datetime(2026, 5, 1, tzinfo=UTC),
        updated_at=datetime(2026, 5, 2, tzinfo=UTC),
        archived_at=None,
        deprecated_at=None,
        folder_full_path="根/质检",
    )
    base.update(kw)
    return ProcedureData(**base)  # type: ignore[arg-type]


def _data(proc, *, chapters=None, steps=None, attachments=None, fields=None) -> RenderData:
    return RenderData(
        procedure=proc,
        root_chapters=chapters or [],
        root_steps=steps or [],
        attachments=attachments or [],
        cover_fields=fields or [],
        assets={},
    )


def _step(**kw: object) -> StepData:
    base: dict[str, object] = dict(
        id="s1",
        code="1.1",
        title="步骤",
        content="",
        skip_numbering=False,
        input_schema={"type": "COMMON"},
        expected_output="",
        attachment_marks=[],
        require_confirmation=False,
    )
    base.update(kw)
    return StepData(**base)  # type: ignore[arg-type]


def _text(flowable: object) -> str:
    return getattr(flowable, "text", "")


# --------------------------------------------------------------------------- #
# 15 型执行占位符（§6.3）
# --------------------------------------------------------------------------- #
def test_form_placeholder_none_returns_none() -> None:
    assert sections._form_placeholder({"type": "NONE"}) is None


def test_form_placeholder_common() -> None:
    assert "已完成" in _text(sections._form_placeholder({"type": "COMMON"}))


def test_form_placeholder_check_default_labels() -> None:
    t = _text(sections._form_placeholder({"type": "CHECK"}))
    assert "通过" in t and "不通过" in t


def test_form_placeholder_check_custom_labels() -> None:
    t = _text(
        sections._form_placeholder({"type": "CHECK", "pass_label": "合格", "fail_label": "返工"})
    )
    assert "合格" in t and "返工" in t


def test_form_placeholder_number_range() -> None:
    t = _text(sections._form_placeholder({"type": "NUMBER", "unit": "MPa", "min": 0, "max": 10}))
    assert "MPa" in t and "0~10" in t


def test_form_placeholder_yesno_meter_signature_date_upload() -> None:
    assert "是" in _text(sections._form_placeholder({"type": "YESNO"}))
    assert "读数" in _text(sections._form_placeholder({"type": "METER", "unit": "A"}))
    assert "签名" in _text(sections._form_placeholder({"type": "SIGNATURE"}))
    assert "日期" in _text(sections._form_placeholder({"type": "DATE"}))
    assert "附件" in _text(sections._form_placeholder({"type": "UPLOAD"}))


def test_form_placeholder_checkbox_radio_options() -> None:
    cb = _text(sections._form_placeholder({"type": "CHECKBOX", "options": ["甲", "乙"]}))
    assert "□ 甲" in cb and "□ 乙" in cb
    rd = _text(
        sections._form_placeholder({"type": "RADIO", "options": [{"label": "A"}, {"label": "B"}]})
    )
    assert "○ A" in rd and "○ B" in rd


def test_form_placeholder_photo_is_table() -> None:
    assert isinstance(sections._form_placeholder({"type": "PHOTO"}), Table)


def test_human_size() -> None:
    assert sections._human_size(512) == "512 B"
    assert sections._human_size(2048) == "2.00 KB"
    assert sections._human_size(5 * 1024 * 1024) == "5.00 MB"


# --------------------------------------------------------------------------- #
# 步骤渲染（§6.3）
# --------------------------------------------------------------------------- #
def test_step_renders_content_marks_confirmation() -> None:
    """COMMON 步骤：正文渲染 + 附件标记 + 确认行 + 执行占位符。"""
    step = _step(
        content="<p>正文</p>",
        # 编辑器真实字段形态：filename + kind=video
        attachment_marks=[{"filename": "demo.mp4", "kind": "video", "note": ""}],
        require_confirmation=True,
        input_schema={"type": "CHECK"},
    )
    out: list = []
    sections._render_step(step, _data(_proc()), out)
    texts = " ".join(_text(f) for f in out if isinstance(f, Paragraph))
    assert "demo.mp4" in texts and "视频" in texts
    assert "已确认完成" in texts


def test_attachment_mark_kind_document() -> None:
    # 编辑器默认 kind='document' → 文档
    text = sections._attachment_mark_text({"filename": "spec.docx", "kind": "document"})
    assert "spec.docx" in text and "文档" in text


def test_skip_numbering_step_no_code() -> None:
    step = _step(code="1.1", skip_numbering=True, title="无编号步骤")
    out: list = []
    sections._render_step(step, _data(_proc()), out)
    title = _text(out[0])
    assert "无编号步骤" in title and "1.1" not in title


# --------------------------------------------------------------------------- #
# 封面（§3.1-3.4）
# --------------------------------------------------------------------------- #
def test_cover_draft_status() -> None:
    out = sections.build_cover(_data(_proc(status="DRAFT")))
    assert any("草稿 DRAFT" in _text(f) for f in out)


def test_cover_archived_status_with_date() -> None:
    out = sections.build_cover(
        _data(_proc(status="ARCHIVED", archived_at=datetime(2026, 5, 3, tzinfo=UTC)))
    )
    assert any("已作废 SUPERSEDED" in _text(f) and "2026-05-03" in _text(f) for f in out)


def test_cover_level_of_use_and_levels() -> None:
    out = sections.build_cover(_data(_proc(level_of_use="continuous")))
    texts = " ".join(_text(f) for f in out)
    assert "连续使用" in texts and "Continuous Use" in texts
    assert "风险等级" in texts and "质量等级" in texts


# --------------------------------------------------------------------------- #
# 修订记录过滤（§5.1）
# --------------------------------------------------------------------------- #
def test_revision_filters_milestones() -> None:
    log = [
        {"version": 1, "change_type": "create", "changed_at": "2026-05-01T00:00:00Z"},
        {"version": 1, "change_type": "update", "changed_at": "2026-05-01T00:00:00Z"},
        {
            "version": 1,
            "change_type": "publish",
            "changed_at": "2026-05-02T00:00:00Z",
            "description": "发布",
        },
        {
            "version": 1,
            "change_type": "deprecate",
            "changed_at": "2026-05-03T00:00:00Z",
            "reason": "停用",
        },
    ]
    out = sections.build_revision(_data(_proc(version_change_log=log)))
    table = next(f for f in out if isinstance(f, Table))
    assert len(table._cellvalues) == 3  # 表头 + publish + deprecate（create/update 不入）


def test_revision_empty_placeholder() -> None:
    out = sections.build_revision(_data(_proc(version_change_log=[])))
    assert any("无修订记录" in _text(f) for f in out)


def test_esc_multiline_converts_newline_to_br() -> None:
    # 修订说明多行 → <br/>（§5.2 / Q366·L6）；同时正确转义
    assert sections._esc_multiline("a\nb") == "a<br/>b"
    assert sections._esc_multiline("<x>\ny") == "&lt;x&gt;<br/>y"


# --------------------------------------------------------------------------- #
# 附件区段（§6.6）
# --------------------------------------------------------------------------- #
def _attach() -> AttachmentData:
    return AttachmentData(
        id="a1",
        file_name="图.pdf",
        size_bytes=2048,
        mime_type="application/pdf",
        created_at=datetime(2026, 5, 1, tzinfo=UTC),
        description="",
        sort_order=0,
    )


def test_virtual_attachment_chapter_when_no_user_chapter() -> None:
    ch = ChapterData(
        id="c1",
        content_type="chapter",
        title="操作",
        code="1",
        level=1,
        skip_numbering=False,
        rich_content="",
    )
    out, has_attach = sections.build_content(_data(_proc(), chapters=[ch], attachments=[_attach()]))
    assert has_attach
    assert any("2.0" in _text(f) and "附件" in _text(f) for f in out if isinstance(f, Paragraph))


def test_user_attachment_chapter_holds_table() -> None:
    ch = ChapterData(
        id="c1",
        content_type="chapter",
        title="附件",
        code="1",
        level=1,
        skip_numbering=False,
        rich_content="",
    )
    out, has_attach = sections.build_content(_data(_proc(), chapters=[ch], attachments=[_attach()]))
    assert has_attach
    titles = [_text(f) for f in out if isinstance(f, Paragraph)]
    assert not any("Attachments" in t for t in titles)
    assert any(isinstance(f, Table) for f in out)


def test_empty_content_placeholder() -> None:
    out, has_attach = sections.build_content(_data(_proc()))
    assert not has_attach
    assert any("程序无内容" in _text(f) for f in out)


# --------------------------------------------------------------------------- #
# 警示型步骤渲染（§6.3 / Q261/§40.1）
# --------------------------------------------------------------------------- #
def test_warning_type_step_renders_alert_box() -> None:
    """WARNING 类型步骤：content 以 alert_box 渲染，返回 Table（警示框）。"""
    step = _step(
        content="<p>危险</p>",
        input_schema={"type": "WARNING"},
    )
    out: list = []
    sections._render_step(step, _data(_proc()), out)
    tables = [f for f in out if isinstance(f, Table)]
    # 应有一个 alert box（Table），且无普通正文段落（content 走 alert 渲染路径）
    assert len(tables) == 1


def test_note_type_step_renders_alert_box() -> None:
    """NOTE 类型步骤：content 以 alert_box 渲染，不渲染普通正文。"""
    step = _step(
        content="<p>提示内容</p>",
        input_schema={"type": "NOTE"},
    )
    out: list = []
    sections._render_step(step, _data(_proc()), out)
    tables = [f for f in out if isinstance(f, Table)]
    assert len(tables) == 1


def test_number_type_step_hides_content() -> None:
    """NUMBER 类型步骤：content 隐藏（数据型不渲染正文），仅渲染表单占位符。"""
    step = _step(
        content="<p>这段文字应被隐藏</p>",
        input_schema={"type": "NUMBER", "label": "压力", "unit": "MPa"},
    )
    out: list = []
    sections._render_step(step, _data(_proc()), out)
    # 不应出现来自 content 的文字段落
    texts = " ".join(_text(f) for f in out if isinstance(f, Paragraph))
    assert "这段文字应被隐藏" not in texts
    # 应有 NUMBER 占位符
    assert "压力" in texts


def test_warning_type_step_no_form_placeholder() -> None:
    """WARNING 类型步骤：不渲染执行表单占位符。"""
    step = _step(
        content="<p>危险操作</p>",
        input_schema={"type": "WARNING"},
    )
    out: list = []
    sections._render_step(step, _data(_proc()), out)
    # 没有「已完成」占位文字
    texts = " ".join(_text(f) for f in out if isinstance(f, Paragraph))
    assert "已完成" not in texts


def test_caution_type_step_renders_alert_box() -> None:
    """CAUTION 类型步骤：content 以 alert_box 渲染，返回 Table（警示框）。"""
    step = _step(
        content="<p>小心操作</p>",
        input_schema={"type": "CAUTION"},
    )
    out: list = []
    sections._render_step(step, _data(_proc()), out)
    tables = [f for f in out if isinstance(f, Table)]
    # 应有一个 alert box（Table），且无普通正文段落（content 走 alert 渲染路径）
    assert len(tables) == 1


def test_common_type_step_renders_content_body() -> None:
    """COMMON 类型步骤：content 正文文字出现在渲染输出中（正向断言正文被渲染）。"""
    step = _step(
        content="<p>正文渲染验证</p>",
        input_schema={"type": "COMMON"},
    )
    out: list = []
    sections._render_step(step, _data(_proc()), out)
    texts = " ".join(_text(f) for f in out if isinstance(f, Paragraph))
    assert "正文渲染验证" in texts
