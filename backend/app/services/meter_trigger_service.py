"""仪表触发器服务：边沿评估纯函数、触发器 CRUD、按 trigger 生单。

读数提交时由 meter_service 调用：_condition_met 判定阈值，_decide 给出
FIRE/REARM/NOOP；FIRE 走 generate_from_trigger 复用工单服务。
工单服务在函数内 import 避免循环依赖。
"""
from __future__ import annotations

from decimal import Decimal

from app.models.meter_comparator import MeterComparator


def _condition_met(comparator: MeterComparator, value: Decimal, threshold: Decimal) -> bool:
    """严格不等：MORE_THAN→value>threshold；LESS_THAN→value<threshold。相等不算满足。"""
    if comparator == MeterComparator.MORE_THAN:
        return value > threshold
    return value < threshold


def _decide(*, is_armed: bool, met: bool) -> str:
    """边沿状态机：满足且武装→FIRE；未满足且已解武装→REARM；其余 NOOP。"""
    if met and is_armed:
        return "FIRE"
    if (not met) and (not is_armed):
        return "REARM"
    return "NOOP"
