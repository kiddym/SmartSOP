"""分析服务共享纯函数：时间窗口解析、时长、停机区间裁剪。

跨方言安全：所有时长用 Python timedelta 计算（不用 SQL 日期函数）。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from app.models.base import utcnow

DEFAULT_WINDOW_DAYS = 90


def resolve_window(
    date_from: date | None, date_to: date | None
) -> tuple[datetime, datetime, date, date]:
    """把 [date_from, date_to]（含端点）解析为半开 datetime 边界 [start, end_excl)。

    两者都省略时默认最近 DEFAULT_WINDOW_DAYS 天（以今日为含端点的窗末）。
    返回 (start, end_excl, date_from, date_to)。
    """
    today = utcnow().date()
    if date_to is None:
        date_to = today
    if date_from is None:
        date_from = date_to - timedelta(days=DEFAULT_WINDOW_DAYS)
    start = datetime(date_from.year, date_from.month, date_from.day)
    end_excl = datetime(date_to.year, date_to.month, date_to.day) + timedelta(days=1)
    return start, end_excl, date_from, date_to


def hours_between(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 3600.0


def clip_interval(
    start: datetime, end: datetime | None, win_start: datetime, win_end: datetime
) -> tuple[datetime, datetime] | None:
    """把停机区间 [start, end) 裁剪到窗口 [win_start, win_end)。

    end 为 None 表示进行中，按 win_end 处理。无重叠返回 None。
    """
    eff_end = end if end is not None else win_end
    lo = max(start, win_start)
    hi = min(eff_end, win_end)
    if hi <= lo:
        return None
    return lo, hi
