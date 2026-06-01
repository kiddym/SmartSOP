from datetime import date, datetime, timedelta

from app.services.analytics._common import (
    clip_interval,
    hours_between,
    resolve_window,
)


def test_resolve_window_explicit_inclusive_end():
    start, end_excl, df, dt = resolve_window(date(2026, 1, 1), date(2026, 1, 31))
    assert start == datetime(2026, 1, 1, 0, 0, 0)
    assert end_excl == datetime(2026, 2, 1, 0, 0, 0)  # date_to 含当日 -> +1 天开区间
    assert df == date(2026, 1, 1) and dt == date(2026, 1, 31)


def test_resolve_window_defaults_last_90_days():
    _start, end_excl, df, dt = resolve_window(None, None)
    assert (dt - df) == timedelta(days=90)
    assert end_excl == datetime(dt.year, dt.month, dt.day) + timedelta(days=1)


def test_resolve_window_only_from():
    _start, _end_excl, df, dt = resolve_window(date(2026, 3, 1), None)
    assert df == date(2026, 3, 1)
    assert dt >= df


def test_hours_between():
    assert hours_between(datetime(2026, 1, 1, 0), datetime(2026, 1, 1, 6)) == 6.0
    assert hours_between(datetime(2026, 1, 1, 0), datetime(2026, 1, 2, 0)) == 24.0


def test_clip_interval_fully_inside():
    win_s, win_e = datetime(2026, 1, 1), datetime(2026, 2, 1)
    assert clip_interval(datetime(2026, 1, 10), datetime(2026, 1, 12), win_s, win_e) == (
        datetime(2026, 1, 10),
        datetime(2026, 1, 12),
    )


def test_clip_interval_ongoing_uses_window_end():
    win_s, win_e = datetime(2026, 1, 1), datetime(2026, 2, 1)
    assert clip_interval(datetime(2026, 1, 20), None, win_s, win_e) == (
        datetime(2026, 1, 20),
        datetime(2026, 2, 1),
    )


def test_clip_interval_clamped_to_window():
    win_s, win_e = datetime(2026, 1, 10), datetime(2026, 1, 20)
    assert clip_interval(datetime(2026, 1, 5), datetime(2026, 1, 25), win_s, win_e) == (
        datetime(2026, 1, 10),
        datetime(2026, 1, 20),
    )


def test_clip_interval_no_overlap_returns_none():
    win_s, win_e = datetime(2026, 1, 10), datetime(2026, 1, 20)
    assert clip_interval(datetime(2026, 1, 1), datetime(2026, 1, 5), win_s, win_e) is None
