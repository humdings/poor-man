"""Poor Man's Bailout: days for a money stock to grow by one bitcoin market cap.

See tests/test_metric.py for the hand-worked definition. Levels are dollars.
"""

from __future__ import annotations

import calendar
import math
from datetime import date, timedelta


def shift_months(d: date, months: int) -> date:
    """Move a calendar date by a whole number of months. The day clamps."""
    month_index = d.year * 12 + (d.month - 1) + months
    year = month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def regression_slope(values, start: int = 0, end: int | None = None) -> float | None:
    """OLS slope of values[start:end] (end inclusive) against 0..n-1.

    The slope is in value-units per step. Steps are days when the input is
    a daily forward-filled series.
    """
    if end is None:
        end = len(values) - 1
    n = end - start + 1
    if n < 2:
        return None
    sum_t = (n - 1) * n / 2
    sum_t2 = (n - 1) * n * (2 * n - 1) / 6
    sum_y = 0.0
    sum_ty = 0.0
    for i in range(n):
        y = values[start + i]
        sum_y += y
        sum_ty += i * y
    denom = n * sum_t2 - sum_t * sum_t
    if denom == 0:
        return None
    return (n * sum_ty - sum_t * sum_y) / denom


def _as_date(value) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def normalize(points) -> list[tuple[date, float]]:
    dedup: dict[date, float] = {}
    for row in points:
        d = _as_date(row[0])
        raw = row[1]
        if raw is None:
            continue
        dedup[d] = float(raw)
    return sorted(dedup.items())


def forward_fill(points: list[tuple[date, float]], start: date, end: date) -> list[float | None]:
    """Daily levels from start through end. The last print carries forward."""
    n = (end - start).days + 1
    out: list[float | None] = [None] * n
    cursor = 0
    current = None
    for i in range(n):
        day = start + timedelta(days=i)
        while cursor < len(points) and points[cursor][0] <= day:
            current = points[cursor][1]
            cursor += 1
        out[i] = current
    return out


def _months(amount: int, unit: str) -> int:
    if amount <= 0:
        raise ValueError("window must be a positive number of months or years")
    if unit in ("month", "months", "m"):
        return amount
    if unit in ("year", "years", "y"):
        return amount * 12
    raise ValueError(f"unknown window unit {unit!r}")


def _growth(method, levels, start_i, end_i, level_start, level, n_days):
    if method == "trailing":
        return (level - level_start) / n_days
    if method == "cagr":
        if level_start <= 0 or level <= 0:
            return None
        return level * ((level / level_start) ** (1 / n_days) - 1)
    if method == "regression":
        return regression_slope(levels, start_i, end_i)
    raise ValueError(f"unknown averaging method {method!r}")


def _classify(growth, mcap):
    if growth is None or mcap is None or mcap <= 0:
        return "insufficient", None
    if growth <= 0:
        return "contracting", None
    days = mcap / growth
    if not math.isfinite(days) or days <= 0:
        return "insufficient", None
    return "expanding", days


def compute_bailout(money, btc, amount: int, unit: str, method: str) -> list[dict]:
    """One point per calendar day from the first day both series exist.

    The series runs through the later of the two last prints. Whichever
    series ended first is carried forward to that date. Bitcoin's market
    cap on a day is the last print on or before that day, and the money
    level is the same kind of step.
    """
    money = normalize(money)
    btc = normalize(btc)
    if not money or not btc:
        return []
    months = _months(int(amount), unit)
    m0 = money[0][0]
    b0 = btc[0][0]
    end = max(money[-1][0], btc[-1][0])
    eval_start = max(m0, b0)
    if eval_start > end:
        return []

    m_levels = forward_fill(money, m0, end)
    c_levels = forward_fill(btc, b0, end)
    points = []
    day = eval_start
    while day <= end:
        level = m_levels[(day - m0).days]
        mcap = c_levels[(day - b0).days]
        start = shift_months(day, -months)
        n_days = (day - start).days
        if start < m0 or n_days <= 0 or level is None or mcap is None:
            points.append(_point(day, "insufficient", None, None, level, None, mcap))
        else:
            start_i = (start - m0).days
            level_start = m_levels[start_i]
            end_i = (day - m0).days
            growth = _growth(method, m_levels, start_i, end_i, level_start, level, n_days)
            state, days = _classify(growth, mcap)
            points.append(_point(day, state, days, growth, level, level_start, mcap))
        day += timedelta(days=1)
    return points


def _point(day, state, days, growth, level, level_start, mcap) -> dict:
    return {
        "date": day.isoformat(),
        "state": state,
        "days": days,
        "growth_per_day": growth,
        "level": level,
        "level_start": level_start,
        "mcap": mcap,
    }


def to_chart_data(points) -> list[dict]:
    """Line points for an expanding stretch. Contraction opens a gap.

    A whitespace point (no value) is inserted at the first day of each
    non-expanding run so the line does not connect across it. Leading
    undefined days are omitted. The last day is kept as whitespace when
    the series ends in a gap, so the axis reaches the latest date.
    """
    rows = []
    gap_open = False
    for point in points:
        expanding = (
            point.get("state") == "expanding"
            and point.get("days") is not None
            and point["days"] > 0
            and math.isfinite(point["days"])
        )
        if expanding:
            rows.append({"time": point["date"], "value": point["days"]})
            gap_open = False
            continue
        if rows and not gap_open:
            rows.append({"time": point["date"]})
            gap_open = True
    if points and points[-1].get("state") != "expanding" and rows:
        if rows[-1]["time"] != points[-1]["date"]:
            rows.append({"time": points[-1]["date"]})
    return rows
