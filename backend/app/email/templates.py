"""邮件文案模板（Phase 5B）。type + params → (subject, body)，纯函数。

文案用 default_locale（zh-CN）。params 来自 5A notify() 的结构化负载。
未知类型走通用回退（防御性，不抛）。
"""
from __future__ import annotations


def render(type_: str, params: dict) -> tuple[str, str]:
    fn = _TEMPLATES.get(type_, _fallback)
    return fn(params)


def _g(params: dict, key: str, default: str = "") -> str:
    v = params.get(key, default)
    return str(v) if v is not None else default


def _wo_assigned(p: dict) -> tuple[str, str]:
    cid, title = _g(p, "custom_id"), _g(p, "title")
    return (f"[工单] 已指派给你：{cid}",
            f"工单 {cid}「{title}」已指派给你，请及时处理。")


def _wo_status_changed(p: dict) -> tuple[str, str]:
    cid = _g(p, "custom_id")
    return (f"[工单] 状态变更：{cid}",
            f"工单 {cid} 状态由 {_g(p, 'from_status')} 变为 {_g(p, 'to_status')}。")


def _wo_auto_generated(p: dict) -> tuple[str, str]:
    cid, title = _g(p, "custom_id"), _g(p, "title")
    return (f"[工单] 自动生成：{cid}", f"系统自动生成工单 {cid}「{title}」。")


def _wo_due_soon(p: dict) -> tuple[str, str]:
    cid = _g(p, "custom_id")
    return (f"[工单] 即将到期：{cid}",
            f"工单 {cid}「{_g(p, 'title')}」将于 {_g(p, 'due_date')} 到期。")


def _wo_overdue(p: dict) -> tuple[str, str]:
    cid = _g(p, "custom_id")
    return (f"[工单] 已逾期：{cid}",
            f"工单 {cid}「{_g(p, 'title')}」已于 {_g(p, 'due_date')} 逾期。")


def _request_submitted(p: dict) -> tuple[str, str]:
    cid, title = _g(p, "custom_id"), _g(p, "title")
    return (f"[请求] 待审批：{cid}", f"请求 {cid}「{title}」已提交，等待审批。")


def _po_submitted(p: dict) -> tuple[str, str]:
    cid = _g(p, "custom_id")
    return (f"[采购单] 待审批：{cid}", f"采购单 {cid} 已提交，等待审批。")


def _po_approved(p: dict) -> tuple[str, str]:
    cid = _g(p, "custom_id")
    return (f"[采购单] 已审批：{cid}", f"采购单 {cid} 已审批通过。")


def _part_low_stock(p: dict) -> tuple[str, str]:
    cid, name = _g(p, "custom_id"), _g(p, "name")
    return (f"[库存] 低库存告警：{name}（{cid}）",
            f"备件 {name}（{cid}）当前库存 {_g(p, 'quantity')}，"
            f"低于最小库存 {_g(p, 'min_quantity')}。")


def _fallback(p: dict) -> tuple[str, str]:
    return ("[通知] 你有一条新通知", f"详情：{p}")


_TEMPLATES = {
    "WO_ASSIGNED": _wo_assigned,
    "WO_STATUS_CHANGED": _wo_status_changed,
    "WO_AUTO_GENERATED": _wo_auto_generated,
    "WO_DUE_SOON": _wo_due_soon,
    "WO_OVERDUE": _wo_overdue,
    "REQUEST_SUBMITTED": _request_submitted,
    "PO_SUBMITTED": _po_submitted,
    "PO_APPROVED": _po_approved,
    "PART_LOW_STOCK": _part_low_stock,
}
