"""PM 调度频率单位（Phase 2B）。"""
from __future__ import annotations

from enum import Enum


class PMFrequencyUnit(str, Enum):
    DAY = "DAY"
    WEEK = "WEEK"
    MONTH = "MONTH"
