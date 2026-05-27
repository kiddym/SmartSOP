"""一次性脚本：3 份 QMS 抽样 (doc05/15/25) → extract_qms_gt → 写 review-list。

用户 ack 后，把 .eval-reports/_draft/template_gt_draft.json 拆成 3 份
tests/fixtures/eval_gt/template_ack/<stem>.json。
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
sys.path.insert(0, str(_ROOT))

from scripts.eval.gt import extract_qms_gt  # noqa: E402

SAMPLED = [
    "docs/reference doc/typical word doc/extra doc/05-基础设施控制程序.docx",
    "docs/reference doc/typical word doc/extra doc/15-标识和可追溯性控制程序.docx",
    "docs/reference doc/typical word doc/extra doc/25-各级人员质量职责和权限规定.docx",
]


def main() -> int:
    out_dir = _ROOT / ".eval-reports" / "_draft"
    out_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Tier 3 Template GT — 请 ack（3 份 QMS 抽样）",
        "",
        "**审阅要点**：抽取器是独立于 parser 的正则（^[1-7]\\.?\\s\\* / N.N / N.N.N + L1 需粗体+短段）",
        "对应 spec §2 Tier 3 第 2 步。检查每份的 chapter 列表是否覆盖所有真章节、没有混入正文。",
        "回复格式：`ack 全部` 或 `修改 <docname>: <说明>`。",
        "",
    ]
    drafts: dict[str, list[dict]] = {}

    for rel in SAMPLED:
        docx = _ROOT / rel
        gt = extract_qms_gt(docx)
        # title 字段：normalize 后存（与 fixture 一致；原文用 source_idx 反查更可靠，但 review 看就行）
        chs = [
            {"title": c.title, "level": c.level, "source_idx": c.source_idx}
            for c in gt.chapters
        ]
        drafts[docx.stem] = chs

        lines.append(f"## {docx.name}（{len(chs)} chapters）\n")
        lines.append("| # | source_idx | level | title (normalize 后) |")
        lines.append("|---:|---:|---:|---|")
        for i, c in enumerate(chs, 1):
            t = c["title"][:60].replace("|", "\\|")
            lines.append(f"| {i} | {c['source_idx']} | {c['level']} | {t} |")
        lines.append("")

    review = out_dir / "template_gt_review.md"
    review.write_text("\n".join(lines), encoding="utf-8")
    draft_json = out_dir / "template_gt_draft.json"
    draft_json.write_text(json.dumps(drafts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"review markdown → {review}")
    print(f"draft json     → {draft_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
