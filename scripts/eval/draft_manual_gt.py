"""一次性脚本：6 份 docx → 推断 level 的 GT JSON 草稿 → 写 .eval-reports/_draft/。

来源：
- 5 份无格式 SOP：复用 scripts/validate_unstyled_v3.py 顶端的 GROUND_TRUTH dict
- QMS doc01（01-公司环境分析控制程序.docx）：用 1-7 编号开头作 prefix

推断 level 规则（per spec §2 Tier 2）：
- `N.N.N` 开头 → L3
- `N.N` 开头 → L2
- `N.` / `N+空格` / `第X章` / `一、` / 中文数字+顿号 → L1
- 无编号但加粗短段 → 默认 L1
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
sys.path.insert(0, str(_ROOT))

from scripts.eval.gt import _iter_body_paragraphs  # noqa: E402

# ── 5 份无格式 SOP 的真实标题前缀（迁自 scripts/validate_unstyled_v3.py 的 GT dict）──
UNSTYLED_GT: dict[str, list[str]] = {
    "3.危险源监控措施.docx": [
        "一、危险源", "二、危险源", "三、危险源", "四、危险源", "五、危险源",
    ],
    "有限空间作业管理办法.docx": [
        "第一章", "第二章", "第三章", "第四章", "第五章", "第九章",
    ],
    "02记录控制程序.docx": [
        "1 目的", "2 范围", "3 职责和权限", "4 工作程序", "5 记录",
        "3.1 ", "3.2 ", "3.3 ", "3.4 ",
        "4.1 记录", "4.2记录", "4.3 记录",
        "4.4 记录的保管", "4.4 记录的查阅", "4.5 记录",
        "4.1.1", "4.1.2", "4.2.1", "4.3.2", "4.4.1", "4.4.2",
    ],
    "05人力资源控制程序.docx": [
        "1 目的", "2 范围", "3 职责", "4 工作程序", "5记录",
        "3.1 质量部", "3.2 各部门", "3.3 总经理",
        "4.1 人员安排", "4.2 能力",
        "4.3 培训计划", "4.4 培训实施", "4.5评价",
        "5.1", "5.2 ",
        "4.2.1 ", "4.2.2", "4.2.3", "4.2.4", "4.2.5", "4.2.6", "4.2.7",
    ],
    "CW-WI-7.4-01外发作业指导书及质量控制程序.docx": [
        "1.目的", "2.适用范围", "3.管理单位", "4.权责", "5.作业程序",
        "4.1 物控", "4.2 品质", "4.3工程",
        "5.9外发", "5.9.1",
    ],
}

# ── QMS doc01：用 1-7 顶级 + N.N 二级前缀（同模板会捕到大量 L1/L2，由用户 ack 时筛 ）──
QMS_DOC01_PREFIXES = [
    "1.", "2.", "3.", "4.", "5.", "6.", "7.",
    "1 ", "2 ", "3 ", "4 ", "5 ", "6 ", "7 ",
    "1、", "2、", "3、", "4、", "5、", "6、", "7、",
]

# 路径表：basename → relative
SOURCES = {
    **{
        f"docs/reference doc/typical word doc/无格式标题word/{name}": prefixes
        for name, prefixes in UNSTYLED_GT.items()
    },
    "docs/reference doc/typical word doc/extra doc/01-公司环境分析控制程序.docx": QMS_DOC01_PREFIXES,
}

_RE_L3 = re.compile(r"^\d+\.\d+\.\d+")
# N.N 后允许接 CJK / 空格 / 中文标点（不接 . 或数字）—— Python 的 \b 在 CJK 上无效
_RE_L2 = re.compile(r"^\d+\.\d+(?![.\d])")
_RE_L1_ARABIC_DOT = re.compile(r"^\d+[\s.、]")  # 1./1 /1、
_RE_L1_CN = re.compile(r"^[一二三四五六七八九十]+[、.]|^第[一二三四五六七八九十\d]+[章节]")


def infer_level(text: str) -> int:
    t = text.strip()
    if _RE_L3.match(t):
        return 3
    if _RE_L2.match(t):
        return 2
    if _RE_L1_ARABIC_DOT.match(t) or _RE_L1_CN.match(t):
        return 1
    return 1  # 默认


def locate_in_docx(docx_path: Path, prefixes: list[str]) -> list[dict]:
    """对每个 prefix 在 docx body 段落中找首个匹配段；返回 [{title, level, source_idx}]。

    每个 source_idx 只用一次，避免 prefix 重复匹配同一段。
    """
    out: list[dict] = []
    used_idxs: set[int] = set()
    with zipfile.ZipFile(docx_path) as zf:
        paragraphs = [(idx, text) for idx, _p, text in _iter_body_paragraphs(zf)]
    for prefix in prefixes:
        for idx, text in paragraphs:
            if idx in used_idxs:
                continue
            if text.strip().startswith(prefix.strip()):
                out.append({
                    "title": text.strip(),
                    "level": infer_level(text),
                    "source_idx": idx,
                })
                used_idxs.add(idx)
                break
    # 按 source_idx 重排，保证文档顺序
    out.sort(key=lambda c: c["source_idx"])
    return out


def main() -> int:
    out_dir = _ROOT / ".eval-reports" / "_draft"
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Tier 2 Manual GT — 请 ack（6 份）",
        "",
        "**审阅要点**：检查每份的 chapter 列表是否完整、level 是否对、有没有 prefix 该去掉。",
        "回复格式：`ack <docname>` 或 `修改 <docname>: <说明>`。",
        "",
    ]

    json_drafts: dict[str, list[dict]] = {}
    for rel, prefixes in SOURCES.items():
        docx = _ROOT / rel
        chapters = locate_in_docx(docx, prefixes)
        json_drafts[docx.stem] = chapters
        lines.append(f"## {docx.name}\n")
        lines.append("| # | source_idx | level | title (前 60 字) |")
        lines.append("|---:|---:|---:|---|")
        for i, c in enumerate(chapters, 1):
            t = c["title"][:60].replace("|", "\\|")
            lines.append(f"| {i} | {c['source_idx']} | {c['level']} | {t} |")
        lines.append("")

    review = out_dir / "manual_gt_review.md"
    review.write_text("\n".join(lines), encoding="utf-8")

    # 同时落一份机器可读的 draft JSON，方便 ack 后直接搬到 tests/fixtures/
    import json
    draft_json = out_dir / "manual_gt_draft.json"
    draft_json.write_text(json.dumps(json_drafts, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"review markdown → {review}")
    print(f"draft json     → {draft_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
