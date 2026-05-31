"""仪表触发比较符（Phase 2C）。"""
from __future__ import annotations

from enum import Enum


class MeterComparator(str, Enum):
    LESS_THAN = "LESS_THAN"
    MORE_THAN = "MORE_THAN"
