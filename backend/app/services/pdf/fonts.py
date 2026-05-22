"""PDF 字体注册（pdf-rendering §8 / Q55 / §59.1·Q359）。

逻辑字体（渲染层只引用访问器返回的名字，不关心来源）：

| 访问器 | 主字体（assets/fonts 内置 Noto，OFL）| 缺失回退（reportlab 内置 CID）|
|--------|--------------------------------------|------------------------------|
| `song()` 宋体正文 | NotoSerifSC（衬线，默认 Regular 母版）| STSong-Light |
| `hei()` 黑体标题/加粗 | NotoSansSC（无衬线）| STSong-Light |
| `mono()` 等宽代码 | reportlab 内置 Courier | Courier |

reportlab 只接受 TrueType(glyf) 静态字体；Noto 可变字体内嵌其默认母版（=Regular），
英文/数字复用 Noto（含 Latin），不单独内嵌 Times。`registerFontFamily` 让正文 `<b>`
自动切黑体（满足「加粗中文=黑体」）。注册全程幂等；任一 TTF 缺失即回退 CID，保证
字体未就位时 PDF 生成不崩、测试离线确定性。
"""

from __future__ import annotations

import logging
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont

from app.config import settings

logger = logging.getLogger("app.services.pdf")

# 回退 CID 字体（Adobe-GB1 简体衬线，reportlab 自带，无需二进制）
_CID_FALLBACK = "STSong-Light"
_MONO = "Courier"  # reportlab 内置 Type1，等宽

# 注册后填充的逻辑名 → 实际 reportlab 字体名
_state: dict[str, str] = {}


def _font_dir() -> Path:
    """解析字体目录：绝对路径直用；相对路径相对 backend 根（app 包父级）。"""
    configured = Path(settings.pdf_font_dir)
    if configured.is_absolute():
        return configured
    backend_root = Path(__file__).resolve().parents[3]  # …/backend
    return backend_root / configured


def _register_ttf(name: str, path: Path) -> str | None:
    """注册 TTF；不存在或解析失败返回 None（触发 CID 回退）。"""
    if name in pdfmetrics.getRegisteredFontNames():
        return name
    if not path.exists():
        return None
    try:
        pdfmetrics.registerFont(TTFont(name, str(path)))
    except Exception as exc:  # 字体损坏/可变格式不兼容 → 回退
        logger.warning("pdf font load failed name=%s path=%s err=%s", name, path, exc)
        return None
    return name


def _register_cid(name: str = _CID_FALLBACK) -> str:
    """注册 reportlab 内置 CID 字体（幂等）。"""
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(name))
    return name


def register_fonts() -> None:
    """注册全部逻辑字体（幂等）。优先 Noto TTF，缺失回退 CID。"""
    if _state:
        return
    font_dir = _font_dir()
    song_name = _register_ttf("SmartSong", font_dir / "NotoSerifSC.ttf") or _register_cid()
    hei_name = _register_ttf("SmartHei", font_dir / "NotoSansSC.ttf") or _register_cid()

    _register_cid(_CID_FALLBACK)  # 确保回退字体始终在册

    # 加粗中文 = 黑体（§8）：正文家族 bold 成员指向黑体；标题样式直接用黑体。
    pdfmetrics.registerFontFamily(
        song_name, normal=song_name, bold=hei_name, italic=song_name, boldItalic=hei_name
    )
    pdfmetrics.registerFontFamily(
        hei_name, normal=hei_name, bold=hei_name, italic=hei_name, boldItalic=hei_name
    )

    _state.update(
        song=song_name,
        hei=hei_name,
        song_bold=hei_name,  # 宋体加粗渲染为黑体（中文加粗惯例）
        hei_bold=hei_name,
        mono=_MONO,
    )
    using_ttf = song_name == "SmartSong" and hei_name == "SmartHei"
    if using_ttf:
        logger.info("pdf fonts registered song=%s hei=%s ttf=True", song_name, hei_name)
    else:
        # 生产应内置 Noto 子集；回退 CID 仅作兜底（字形覆盖窄、加粗中文≠黑体）。
        logger.warning(
            "pdf fonts fell back to CID (assets/fonts missing TTF) song=%s hei=%s dir=%s; "
            "PDF 字体已降级，加粗中文将无法显示为黑体，请确认部署内置了 Noto 子集",
            song_name,
            hei_name,
            _font_dir(),
        )


def _get(key: str) -> str:
    if not _state:
        register_fonts()
    return _state[key]


def song() -> str:
    """宋体正文。"""
    return _get("song")


def song_bold() -> str:
    """宋体加粗（=黑体）。"""
    return _get("song_bold")


def hei() -> str:
    """黑体（标题 / 加粗）。"""
    return _get("hei")


def hei_bold() -> str:
    """黑体加粗。"""
    return _get("hei_bold")


def mono() -> str:
    """等宽（代码）。"""
    return _get("mono")
