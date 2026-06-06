"""工单报告 PDF 生成（全新原创排版，复用 pdf 子包字体/样式基础设施）。

对外入口 `generate_work_order_report(db, wo)` → (bytes, filename)。

布局为单流 story（无封面/页眉迭代分页，与程序导出的多模板引擎正交）：
标题 → 基本信息 → 工时明细 → 附加成本 → 备件消耗 → 成本汇总 → 活动时间线 → SOP 步骤。
缺数据的块显「无」。所有中文经 styles.stylesheet() 走已注册的 Noto/CID 字体，
不另注册字体，避免乱码。
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any

from reportlab.lib.colors import Color, black
from reportlab.platypus import (
    Flowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cost_category import CostCategory
from app.models.location import Location
from app.models.maintenance_asset import Asset
from app.models.node import ProcedureNode
from app.models.part import Part
from app.models.part_consumption import PartConsumption
from app.models.time_category import TimeCategory
from app.models.user import User
from app.models.work_order import WorkOrder
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_additional_cost import WorkOrderAdditionalCost
from app.models.work_order_category import WorkOrderCategory
from app.models.work_order_step_result import WorkOrderStepResult
from app.services import work_order_cost_service as cost_svc
from app.services import work_order_labor_service as labor_svc
from app.services.pdf import styles
from app.services.pdf.constants import (
    CONTENT_WIDTH,
    PAGE_MARGIN_BOTTOM,
    PAGE_MARGIN_LEFT,
    PAGE_MARGIN_RIGHT,
    PAGE_MARGIN_TOP,
    PAGE_SIZE,
)

# 中文枚举标签（报告本地，与全局枚举解耦）
_STATUS_LABELS: dict[str, str] = {
    "OPEN": "待处理",
    "IN_PROGRESS": "进行中",
    "ON_HOLD": "已挂起",
    "COMPLETE": "已完成",
    "CANCELED": "已取消",
}
_PRIORITY_LABELS: dict[str, str] = {
    "NONE": "无",
    "LOW": "低",
    "MEDIUM": "中",
    "HIGH": "高",
}
_ACTIVITY_LABELS: dict[str, str] = {
    "STATUS_CHANGE": "状态变更",
    "COMMENT": "评论",
    "ASSIGN": "指派",
    "SOP_ATTACH": "挂接 SOP",
    "STEP_DONE": "完成步骤",
}

_MUTED = Color(0.45, 0.45, 0.45)
_HEAD_BG = Color(0.93, 0.93, 0.93)


# --------------------------------------------------------------------------- #
# 格式化
# --------------------------------------------------------------------------- #
def _esc(text: Any) -> str:
    s = "" if text is None else str(text)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt_dt(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt is not None else "—"


def _fmt_date(d: date | None) -> str:
    return d.strftime("%Y-%m-%d") if d is not None else "—"


def _fmt_money(v: Decimal) -> str:
    return f"{v:.2f}"


def _fmt_hours(seconds: int) -> str:
    return f"{seconds / 3600:.2f} h"


# --------------------------------------------------------------------------- #
# 数据装载
# --------------------------------------------------------------------------- #
def _user_name(db: Session, user_id: str | None) -> str:
    if user_id is None:
        return "—"
    u = db.get(User, user_id)
    return u.name if u is not None else "—"


# --------------------------------------------------------------------------- #
# 通用表格
# --------------------------------------------------------------------------- #
def _grid_style() -> TableStyle:
    return TableStyle(
        [
            ("GRID", (0, 0), (-1, -1), 0.5, black),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, 0), _HEAD_BG),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]
    )


def _data_table(headers: list[str], rows: list[list[str]], widths: list[float]) -> Table:
    head = styles.s("table_head")
    cell = styles.s("table_cell")
    body: list[list[Any]] = [[Paragraph(_esc(h), head) for h in headers]]
    for r in rows:
        body.append([Paragraph(_esc(c), cell) for c in r])
    t = Table(body, colWidths=widths, repeatRows=1)
    t.setStyle(_grid_style())
    return t


def _section_title(text: str) -> Paragraph:
    return Paragraph(_esc(text), styles.s("h2"))


def _empty(text: str = "无") -> Paragraph:
    style = styles.s("body").clone("wo_empty", textColor=_MUTED)
    return Paragraph(text, style)


# --------------------------------------------------------------------------- #
# 各区段
# --------------------------------------------------------------------------- #
def _title_block(wo: WorkOrder) -> list[Flowable]:
    title = f"工单报告 · {_esc(wo.custom_id)}"
    out: list[Flowable] = [Paragraph(title, styles.s("cover_title"))]
    out.append(Paragraph(_esc(wo.title), styles.s("h3")))
    out.append(Spacer(1, 6))
    return out


def _info_block(db: Session, wo: WorkOrder) -> list[Flowable]:
    asset = db.get(Asset, wo.asset_id) if wo.asset_id else None
    location = db.get(Location, wo.location_id) if wo.location_id else None
    category = db.get(WorkOrderCategory, wo.category_id) if wo.category_id else None
    pairs: list[tuple[str, str]] = [
        ("状态", _STATUS_LABELS.get(str(wo.status.value), str(wo.status.value))),
        ("优先级", _PRIORITY_LABELS.get(str(wo.priority.value), str(wo.priority.value))),
        ("紧急", "是" if wo.urgent else "否"),
        ("资产", asset.name if asset is not None else "—"),
        ("位置", location.name if location is not None else "—"),
        ("分类", category.name if category is not None else "—"),
        ("负责人", _user_name(db, wo.primary_user_id)),
        ("截止日期", _fmt_date(wo.due_date)),
        ("创建时间", _fmt_dt(wo.created_at)),
        ("完成时间", _fmt_dt(wo.completed_at)),
    ]
    head = styles.s("table_head")
    cell = styles.s("table_cell")
    rows: list[list[Any]] = [[Paragraph(_esc(k), head), Paragraph(_esc(v), cell)] for k, v in pairs]
    t = Table(rows, colWidths=[CONTENT_WIDTH * 0.28, CONTENT_WIDTH * 0.72])
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, -1), _HEAD_BG),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    out: list[Flowable] = [_section_title("基本信息"), t]
    if wo.description:
        out.append(Spacer(1, 4))
        out.append(Paragraph("描述：", styles.s("table_head")))
        out.append(Paragraph(_esc(wo.description).replace("\n", "<br/>"), styles.s("body")))
    return out


def _labor_block(db: Session, wo: WorkOrder) -> list[Flowable]:
    out: list[Flowable] = [_section_title("工时明细")]
    rows_data = labor_svc.list_labor(db, wo.id)
    if not rows_data:
        out.append(_empty())
        return out
    cat_names = {
        c.id: c.name
        for c in db.execute(
            select(TimeCategory).where(TimeCategory.company_id == wo.company_id)
        ).scalars()
    }
    rows: list[list[str]] = []
    for r in rows_data:
        rows.append(
            [
                cat_names.get(r.time_category_id, "—") if r.time_category_id else "—",
                _user_name(db, r.user_id),
                _fmt_hours(r.duration_seconds),
                _fmt_money(r.hourly_rate),
                _fmt_money(labor_svc.compute_cost(r)),
            ]
        )
    widths = [CONTENT_WIDTH * w for w in (0.22, 0.22, 0.16, 0.18, 0.22)]
    out.append(_data_table(["时间分类", "人员", "工时", "费率", "小计"], rows, widths))
    return out


def _additional_cost_block(db: Session, wo: WorkOrder) -> list[Flowable]:
    out: list[Flowable] = [_section_title("附加成本")]
    rows_data = (
        db.execute(
            select(WorkOrderAdditionalCost)
            .where(WorkOrderAdditionalCost.work_order_id == wo.id)
            .order_by(WorkOrderAdditionalCost.created_at, WorkOrderAdditionalCost.id)
        )
        .scalars()
        .all()
    )
    if not rows_data:
        out.append(_empty())
        return out
    cat_names = {
        c.id: c.name
        for c in db.execute(
            select(CostCategory).where(CostCategory.company_id == wo.company_id)
        ).scalars()
    }
    rows: list[list[str]] = []
    for r in rows_data:
        rows.append(
            [
                r.title,
                cat_names.get(r.cost_category_id, "—") if r.cost_category_id else "—",
                r.description or "—",
                _fmt_money(r.amount),
            ]
        )
    widths = [CONTENT_WIDTH * w for w in (0.28, 0.22, 0.32, 0.18)]
    out.append(_data_table(["项目", "成本分类", "说明", "金额"], rows, widths))
    return out


def _part_block(db: Session, wo: WorkOrder) -> list[Flowable]:
    out: list[Flowable] = [_section_title("备件消耗")]
    rows_data = (
        db.execute(
            select(PartConsumption)
            .where(PartConsumption.work_order_id == wo.id)
            .order_by(PartConsumption.consumed_at, PartConsumption.id)
        )
        .scalars()
        .all()
    )
    if not rows_data:
        out.append(_empty())
        return out
    rows: list[list[str]] = []
    for r in rows_data:
        part = db.get(Part, r.part_id)
        rows.append(
            [
                part.custom_id if part is not None else "—",
                part.name if part is not None else "—",
                f"{r.quantity:.2f}",
                _fmt_money(r.unit_cost),
                _fmt_money(r.quantity * r.unit_cost),
            ]
        )
    widths = [CONTENT_WIDTH * w for w in (0.16, 0.30, 0.16, 0.18, 0.20)]
    out.append(_data_table(["备件编号", "名称", "数量", "单价", "小计"], rows, widths))
    return out


def _cost_summary_block(db: Session, wo: WorkOrder) -> list[Flowable]:
    summary = cost_svc.cost_summary(db, wo.id)
    head = styles.s("table_head")
    cell = styles.s("table_cell")
    pairs = [
        ("工时合计", summary["labor_total"]),
        ("备件合计", summary["parts_total"]),
        ("附加合计", summary["additional_total"]),
    ]
    rows: list[list[Any]] = [
        [Paragraph(_esc(k), cell), Paragraph(_fmt_money(v), cell)] for k, v in pairs
    ]
    rows.append([Paragraph("总计", head), Paragraph(_fmt_money(summary["total"]), head)])
    t = Table(rows, colWidths=[CONTENT_WIDTH * 0.5, CONTENT_WIDTH * 0.5])
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, -1), (-1, -1), _HEAD_BG),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return [_section_title("成本汇总"), t]


def _activity_block(db: Session, wo: WorkOrder) -> list[Flowable]:
    out: list[Flowable] = [_section_title("活动时间线")]
    rows_data = (
        db.execute(
            select(WorkOrderActivity)
            .where(WorkOrderActivity.work_order_id == wo.id)
            .order_by(WorkOrderActivity.created_at, WorkOrderActivity.id)
        )
        .scalars()
        .all()
    )
    if not rows_data:
        out.append(_empty())
        return out
    rows: list[list[str]] = []
    for a in rows_data:
        detail = a.comment or ""
        if a.activity_type == "STATUS_CHANGE" and a.from_status and a.to_status:
            transition = (
                f"{_STATUS_LABELS.get(a.from_status, a.from_status)} → "
                f"{_STATUS_LABELS.get(a.to_status, a.to_status)}"
            )
            detail = f"{transition}{('  ' + detail) if detail else ''}"
        rows.append(
            [
                _fmt_dt(a.created_at),
                _ACTIVITY_LABELS.get(a.activity_type, a.activity_type),
                _user_name(db, a.actor_user_id),
                detail or "—",
            ]
        )
    widths = [CONTENT_WIDTH * w for w in (0.22, 0.16, 0.18, 0.44)]
    out.append(_data_table(["时间", "类型", "操作人", "详情"], rows, widths))
    return out


def _step_result_block(db: Session, wo: WorkOrder) -> list[Flowable]:
    if wo.procedure_id is None:
        return []
    rows_data = (
        db.execute(
            select(WorkOrderStepResult)
            .where(WorkOrderStepResult.work_order_id == wo.id)
            .order_by(WorkOrderStepResult.node_sort_order, WorkOrderStepResult.id)
        )
        .scalars()
        .all()
    )
    out: list[Flowable] = [_section_title("SOP 执行结果")]
    if not rows_data:
        out.append(_empty())
        return out
    rows: list[list[str]] = []
    for sr in rows_data:
        node = db.get(ProcedureNode, sr.node_id)
        title = (node.body if node is not None else "") or sr.node_code or "（步骤）"
        rows.append(
            [
                sr.node_code or "—",
                title,
                "已完成" if sr.is_done else "未完成",
                _user_name(db, sr.done_by_user_id),
                sr.notes or "—",
            ]
        )
    widths = [CONTENT_WIDTH * w for w in (0.12, 0.34, 0.14, 0.16, 0.24)]
    out.append(_data_table(["编号", "步骤", "状态", "完成人", "备注"], rows, widths))
    return out


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #
def _build_story(db: Session, wo: WorkOrder) -> list[Flowable]:
    styles.stylesheet()  # 预热字体 + 样式注册
    story: list[Flowable] = []
    story += _title_block(wo)
    story += _info_block(db, wo)
    story.append(Spacer(1, 10))
    story += _labor_block(db, wo)
    story.append(Spacer(1, 10))
    story += _additional_cost_block(db, wo)
    story.append(Spacer(1, 10))
    story += _part_block(db, wo)
    story.append(Spacer(1, 10))
    story += _cost_summary_block(db, wo)
    story.append(Spacer(1, 10))
    story += _activity_block(db, wo)
    step_block = _step_result_block(db, wo)
    if step_block:
        story.append(Spacer(1, 10))
        story += step_block
    return story


def generate_work_order_report(db: Session, wo: WorkOrder) -> tuple[bytes, str]:
    """生成工单报告 PDF：返回 (bytes, filename)。"""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=PAGE_SIZE,
        leftMargin=PAGE_MARGIN_LEFT,
        rightMargin=PAGE_MARGIN_RIGHT,
        topMargin=PAGE_MARGIN_TOP,
        bottomMargin=PAGE_MARGIN_BOTTOM,
        title=f"WO-{wo.custom_id}",
    )
    doc.build(_build_story(db, wo))
    filename = f"WO-{wo.custom_id}.pdf"
    return buf.getvalue(), filename
