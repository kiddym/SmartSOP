"""PDF 渲染常量（pdf-rendering.md §1/§3.2/§7/§3.4/§5.2/§6.3）。"""

from __future__ import annotations

from reportlab.lib.colors import Color
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

# --------------------------------------------------------------------------- #
# 页面（§1）
# --------------------------------------------------------------------------- #
PAGE_SIZE = A4  # (width, height)
PAGE_MARGIN_TOP = 1.27 * cm
PAGE_MARGIN_BOTTOM = 1.27 * cm
PAGE_MARGIN_LEFT = 2.03 * cm
PAGE_MARGIN_RIGHT = 2.03 * cm
LINE_HEIGHT = 1.5  # 行距倍数
HEADER_HEIGHT = 1.6 * cm  # 页眉占高（正文 / 前置页）
# 正文可用宽度（页宽 - 左右边距）= ~17cm（§9.1）
CONTENT_WIDTH = A4[0] - PAGE_MARGIN_LEFT - PAGE_MARGIN_RIGHT

# --------------------------------------------------------------------------- #
# 风险 / 质量等级色块（§3.2 / Q52）
# --------------------------------------------------------------------------- #
RISK_LABELS: dict[int, str] = {1: "低", 2: "中-低", 3: "中", 4: "中-高", 5: "高"}
RISK_COLORS: dict[int, Color] = {
    1: Color(16 / 255, 185 / 255, 129 / 255),
    2: Color(132 / 255, 204 / 255, 22 / 255),
    3: Color(234 / 255, 179 / 255, 8 / 255),
    4: Color(249 / 255, 115 / 255, 22 / 255),
    5: Color(220 / 255, 38 / 255, 38 / 255),
}

# --------------------------------------------------------------------------- #
# 用途级别（§3.1 / Q182）
# --------------------------------------------------------------------------- #
LEVEL_OF_USE_LABELS: dict[str, tuple[str, str]] = {
    "reference": ("参考使用", "Reference Use"),
    "continuous": ("连续使用", "Continuous Use"),
    "information": ("信息使用", "Information Use"),
}

# --------------------------------------------------------------------------- #
# 警示三色（ANSI Z535，§7.1-7.3）
# --------------------------------------------------------------------------- #
NOTE_BG = Color(204 / 255, 229 / 255, 255 / 255)
NOTE_BORDER = Color(13 / 255, 71 / 255, 161 / 255)
CAUTION_BG = Color(255 / 255, 217 / 255, 102 / 255)
CAUTION_BORDER = Color(0, 0, 0)
WARNING_BG = Color(255 / 255, 205 / 255, 210 / 255)
WARNING_BORDER = Color(220 / 255, 38 / 255, 38 / 255)
HOLD_BORDER = Color(220 / 255, 38 / 255, 38 / 255)

ALERT_SPECS: dict[str, dict[str, object]] = {
    # 图标用 GB2312 子集确有的字形（ℹ/⛔/◈/☐ 在 Noto SC 缺失，§59.1 验证后替换）
    "note": {
        "bg": NOTE_BG,
        "border": NOTE_BORDER,
        "title": "ⓘ 注意 NOTE",
        "title_color": NOTE_BORDER,
    },
    "caution": {
        "bg": CAUTION_BG,
        "border": CAUTION_BORDER,
        "title": "⚠ 小心 CAUTION",
        "title_color": Color(0, 0, 0),
    },
    "warning": {
        "bg": WARNING_BG,
        "border": WARNING_BORDER,
        "title": "‼ 警告 WARNING",
        "title_color": WARNING_BORDER,
    },
}
# content 节点内嵌 class → 警示类型（§7）
BLOCK_CLASS_TO_ALERT: dict[str, str] = {
    "note-block": "note",
    "caution-block": "caution",
    "warning-block": "warning",
}
ALERT_ORDER = ("note", "caution", "warning")  # 递进顺序（§7.0）

# --------------------------------------------------------------------------- #
# 水印 / 状态标识（§3.4 / Q225）
# --------------------------------------------------------------------------- #
WATERMARK: dict[str, dict[str, object]] = {
    "DRAFT": {"text": "草稿 DRAFT", "color": Color(200 / 255, 200 / 255, 200 / 255), "alpha": 0.30},
    "ARCHIVED": {
        "text": "已作废 SUPERSEDED",
        "color": Color(230 / 255, 150 / 255, 150 / 255),
        "alpha": 0.35,
    },
}

# --------------------------------------------------------------------------- #
# 修订记录 change_type 翻译（§5.2）；仅里程碑进修订页（§5.1）
# --------------------------------------------------------------------------- #
CHANGE_TYPE_LABELS: dict[str, str] = {
    "publish": "发布",
    "rollback": "回退",
    "deprecate": "废弃",
    "restore": "恢复",
}
REVISION_CHANGE_TYPES = frozenset(CHANGE_TYPE_LABELS)

# --------------------------------------------------------------------------- #
# 步骤附件标记 kind 中文（§6.3 / Q203）
# 注：编辑器实际存 kind='document'（StepDetailPanel ATTACH_KINDS），兼容文档的 'doc'。
# --------------------------------------------------------------------------- #
ATTACHMENT_KIND_LABELS: dict[str, str] = {
    "video": "视频",
    "image": "图片",
    "document": "文档",
    "doc": "文档",
    "audio": "音频",
    "other": "其他",
}
ATTACHMENT_MARK_PREFIX = "▶ 附件:"  # 📎(emoji) 在 CJK 字体缺失 → 用三角符（§59.1）

# --------------------------------------------------------------------------- #
# 执行表单 12 型纸质占位符（§6.3 / Q262）
# --------------------------------------------------------------------------- #
DEFAULT_PASS_LABEL = "通过"
DEFAULT_FAIL_LABEL = "不通过"
# 勾选/单选字形：☐(2610)/☑(2611) 在 Noto SC 缺失 → 用 □(25A1)/○(25CB)（下载版恒空框）
CHECKBOX_GLYPH = "□"
RADIO_GLYPH = "○"

# 附件章节名（§6.6.2）
ATTACHMENT_CHAPTER_NAMES = ("附件", "Attachments")
ATTACHMENT_CHAPTER_TITLE = "附件 / Attachments"
