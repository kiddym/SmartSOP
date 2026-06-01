"""仪表触发比较符（Phase 2C）。"""

from __future__ import annotations

from enum import StrEnum


class MeterComparator(StrEnum):
    LESS_THAN = "LESS_THAN"
    MORE_THAN = "MORE_THAN"
