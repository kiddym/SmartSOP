"""PM 调度频率单位（Phase 2B）。"""

from __future__ import annotations

from enum import StrEnum


class PMFrequencyUnit(StrEnum):
    DAY = "DAY"
    WEEK = "WEEK"
    MONTH = "MONTH"
