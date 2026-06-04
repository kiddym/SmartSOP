"""套餐 catalog：硬编码三档常量 + 有效功能/座席纯函数（Phase 6 门控骨架）。

订阅"生效"(active/trialing)→解锁所购档位功能；失效→降级到 free 功能集。
纯函数接受 plan/status 字符串（不依赖 ORM 对象），便于单测与复用。
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class Plan(enum.StrEnum):
    free = "free"
    pro = "pro"
    enterprise = "enterprise"


class Feature(enum.StrEnum):
    preventive_maintenance = "preventive_maintenance"
    meters = "meters"
    purchasing = "purchasing"
    analytics = "analytics"
    sop = "sop"


# 订阅生效状态：解锁所购档位功能；其余状态降级到 free。
ACTIVE_STATUSES = frozenset({"active", "trialing"})
ALL_STATUSES = frozenset({"active", "trialing", "past_due", "canceled", "suspended"})

_PRO_FEATURES = frozenset(
    {
        Feature.preventive_maintenance,
        Feature.meters,
        Feature.purchasing,
        Feature.analytics,
        Feature.sop,
    }
)


@dataclass(frozen=True)
class PlanSpec:
    seat_limit: int | None  # None = 无限
    features: frozenset[Feature]


PLAN_CATALOG: dict[Plan, PlanSpec] = {
    Plan.free: PlanSpec(seat_limit=3, features=frozenset()),
    Plan.pro: PlanSpec(seat_limit=15, features=_PRO_FEATURES),
    Plan.enterprise: PlanSpec(seat_limit=None, features=_PRO_FEATURES),
}


def _resolve_plan(plan: str | None) -> Plan:
    """未知/空 plan 视为 free（容错，不抛）。"""
    try:
        return Plan(plan) if plan else Plan.free
    except ValueError:
        return Plan.free


def effective_features(plan: str | None, status: str | None) -> frozenset[Feature]:
    if status not in ACTIVE_STATUSES:
        return PLAN_CATALOG[Plan.free].features
    return PLAN_CATALOG[_resolve_plan(plan)].features


def effective_seat_limit(plan: str | None, status: str | None) -> int | None:
    if status not in ACTIVE_STATUSES:
        return PLAN_CATALOG[Plan.free].seat_limit
    return PLAN_CATALOG[_resolve_plan(plan)].seat_limit
