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
        if y is None:
            return None
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


def normalize_btc(points):
    """Bitcoin rows are (date, market cap) or (date, market cap, price)."""
    dedup: dict[date, tuple[float, float | None]] = {}
    for row in points:
        observed = _as_date(row[0])
        raw = row[1]
        if raw is None or raw == "":
            continue
        price = None
        if len(row) > 2 and row[2] is not None and row[2] != "":
            price = float(row[2])
        dedup[observed] = (float(raw), price)
    rows = sorted(dedup.items())
    caps = [(observed, pair[0]) for observed, pair in rows]
    prices = [(observed, pair[1]) for observed, pair in rows if pair[1] is not None]
    return caps, prices


def _at(levels, origin: date | None, day: date):
    if not levels or origin is None or day < origin:
        return None, None
    idx = (day - origin).days
    if idx < 0 or idx >= len(levels):
        return None, None
    return levels[idx], idx


def half_life_years(rate: float) -> float | None:
    """Years for a price level growing at `rate` to double.

    Purchasing power halves when prices double:
    half-life = ln(2) / ln(1 + rate), with rate a decimal.
    A rate at or below zero does not halve purchasing power.
    """
    if isinstance(rate, bool) or not isinstance(rate, (int, float)):
        return None
    if not math.isfinite(rate) or rate <= 0:
        return None
    growth = math.log(1.0 + rate)
    if growth <= 0 or not math.isfinite(growth):
        return None
    return math.log(2.0) / growth


def trailing_cpi_half_life(points) -> list[dict]:
    """Half-life implied by trailing 12-month CPI.

    Inflation on a print is that index divided by the index twelve months
    earlier, minus one. A missing prior print is skipped until the series
    has started, and then left as a gap. A rate at or below zero is a gap.
    """
    series = normalize(points)
    levels = {day: level for day, level in series}
    out: list[dict] = []
    started = False
    for day, level in series:
        prior = levels.get(shift_months(day, -12))
        if prior is None or prior <= 0 or level <= 0:
            if started:
                out.append({"date": day.isoformat(), "rate": None, "years": None})
            continue
        rate = level / prior - 1.0
        out.append({"date": day.isoformat(), "rate": rate, "years": half_life_years(rate)})
        started = True
    return out


# Cumulative changes, January 2000 through June 2026, from Mark J. Perry's
# BLS chart of selected consumer prices and wages. The June 2026 AEI post
# was not found, so the page credits him without a link. Decimals, not percent.
PERRY_SPAN_YEARS = 26.5
PERRY_CUMULATIVE = (
    ("overall", "Overall inflation", 0.964, "baseline"),
    ("hospital", "Hospital Services", 2.911, "preset"),
    ("tuition", "College Tuition and Fees", 1.998, "preset"),
    ("textbooks", "College Textbooks", 1.819, "preset"),
    ("daycare", "Day Care and Preschool", 1.624, "preset"),
    ("medical", "Medical Care Services", 1.505, "preset"),
    ("wages", "Average Hourly Wages", 1.357, "reference"),
    ("housing", "Housing", 1.153, "preset"),
    ("food", "Food and Beverages", 1.085, "preset"),
)


def annualized_from_cumulative(change: float, years: float = PERRY_SPAN_YEARS) -> float | None:
    """Annual rate that compounds to `change` over `years`.

    (1 + change) ** (1 / years) - 1. `change` is a decimal cumulative change.
    """
    if isinstance(change, bool) or not isinstance(change, (int, float)):
        return None
    if isinstance(years, bool) or not isinstance(years, (int, float)):
        return None
    if not math.isfinite(change) or change <= -1:
        return None
    if not math.isfinite(years) or years <= 0:
        return None
    rate = (1.0 + change) ** (1.0 / years) - 1.0
    if not math.isfinite(rate):
        return None
    return rate


def perry_table() -> list[dict]:
    """Annualized rate and the gap over overall CPI, in decimal rate points.

    A preset adds that gap to trailing CPI. Wages is a reference, not a preset.
    The gap is an illustrative assumption, not measured real inflation.
    """
    overall = annualized_from_cumulative(0.964)
    rows: list[dict] = []
    for key, name, change, role in PERRY_CUMULATIVE:
        rate = annualized_from_cumulative(change)
        gap = None if rate is None or overall is None else rate - overall
        rows.append({
            "key": key,
            "name": name,
            "cumulative": change,
            "annualized": rate,
            "gap": gap,
            "role": role,
        })
    return rows


def half_life_with_gap(rate: float | None, gap: float | None) -> float | None:
    """Half-life at `rate` plus `gap`. Both are decimals. A non-positive sum is a gap."""
    if rate is None or gap is None:
        return None
    if isinstance(rate, bool) or not isinstance(rate, (int, float)):
        return None
    if isinstance(gap, bool) or not isinstance(gap, (int, float)):
        return None
    if not math.isfinite(rate) or not math.isfinite(gap):
        return None
    return half_life_years(rate + gap)


def effective_gap(gap: float | None) -> float:
    """Gap added to trailing CPI, as a decimal rate. The slider applies it at once."""
    if isinstance(gap, bool) or not isinstance(gap, (int, float)):
        return 0.0
    if not math.isfinite(gap):
        return 0.0
    return float(gap)


def _positive(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def log_slope(levels, start: int, end: int) -> float | None:
    """OLS slope of ln(level). A nonpositive level has no log-slope."""
    if start is None or end is None or start < 0:
        return None
    n = end - start + 1
    if n < 2:
        return None
    logs = []
    for i in range(start, end + 1):
        value = levels[i]
        if value is None or value <= 0:
            return None
        logs.append(math.log(value))
    return regression_slope(logs)


def _growth(method, levels, start_i, end_i, level_start, level, n_days):
    if level is None or level_start is None or n_days <= 0:
        return None
    if method == "trailing":
        return (level - level_start) / n_days
    if method == "cagr":
        if level_start <= 0 or level <= 0:
            return None
        return level * ((level / level_start) ** (1 / n_days) - 1)
    if method == "regression":
        return regression_slope(levels, start_i, end_i)
    raise ValueError(f"unknown averaging method {method!r}")


def proportional_rate(method, levels, start_i, end_i, level_start, level, n_days):
    """Daily proportional rate of a deflator, using the same method as the money pace.

    Trailing and the unsmoothed print-to-print pace use the two endpoints.
    CAGR uses the compound endpoint rate. Regression uses the slope of the
    log level on every forward-filled day in the window.
    """
    if n_days <= 0 or level_start is None or level is None:
        return None
    if method in ("trailing", "none"):
        if level_start <= 0:
            return None
        return (level - level_start) / (n_days * level_start)
    if method == "cagr":
        if level_start <= 0 or level <= 0:
            return None
        return (level / level_start) ** (1 / n_days) - 1
    if method == "regression":
        return log_slope(levels, start_i, end_i)
    raise ValueError(f"unknown averaging method {method!r}")


def excess_growth(method, growth, level, level_start, rate):
    """Money growth per day minus the deflator's rate, in dollars of the money stock.

    Trailing and print-to-print scale the deflator by the money level at the
    start of the window, so equal percentage growth is an excess of zero and
    a flat deflator leaves the pace unchanged. CAGR and regression scale by
    today's money level, which is the level those paces are already stated at.
    """
    if growth is None or rate is None or level is None or level_start is None:
        return None
    base = level_start if method in ("trailing", "none") else level
    return growth - base * rate


def _classify(growth, mcap):
    if growth is None or mcap is None or mcap <= 0:
        return "insufficient", None
    if growth <= 0:
        return "contracting", None
    days = mcap / growth
    if not math.isfinite(days) or days <= 0:
        return "insufficient", None
    return "expanding", days


def compute_bailout(money, btc, amount: int, unit: str, method: str, deflator=None) -> list[dict]:
    """One point per calendar day from the first day both series exist.

    The series runs through the later of the two last prints. Whichever
    series ended first is carried forward to that date. Bitcoin's market
    cap on a day is the last print on or before that day, and the money
    level is the same kind of step.

    amount <= 0 turns smoothing off. The pace is then the change between the
    money print in effect and the print before it, held until the next print.
    A decrease stays negative and is classified as contracting.

    Passing a deflator turns normalization on. The pace becomes money growth
    in excess of that deflator over the same interval. Coverage gaps in the
    deflator make the day count insufficient rather than falling back to the
    unadjusted pace.
    """
    money = normalize(money)
    caps, prices = normalize_btc(btc)
    normalizing = deflator is not None
    deflator_points = normalize(deflator) if normalizing else []
    if not money or not caps:
        return []
    smooth = int(amount) > 0
    if smooth:
        months = _months(int(amount), unit)
        if method not in ("trailing", "cagr", "regression"):
            raise ValueError(f"unknown averaging method {method!r}")
    else:
        months = 0
        method = "none"

    m0 = money[0][0]
    b0 = caps[0][0]
    end = max(money[-1][0], caps[-1][0])
    eval_start = max(m0, b0)
    if eval_start > end:
        return []

    m_levels = forward_fill(money, m0, end)
    c_levels = forward_fill(caps, b0, end)
    if prices:
        p0 = prices[0][0]
        p_levels = forward_fill(prices, p0, end)
    else:
        p0 = None
        p_levels = []
    if deflator_points:
        d0 = deflator_points[0][0]
        d_levels = forward_fill(deflator_points, d0, end)
    else:
        d0 = None
        d_levels = []

    points = []
    print_index = -1
    day = eval_start
    while day <= end:
        while print_index + 1 < len(money) and money[print_index + 1][0] <= day:
            print_index += 1
        level = m_levels[(day - m0).days]
        mcap = c_levels[(day - b0).days]
        price, _price_i = _at(p_levels, p0, day)
        supply = mcap / price if _positive(price) and _positive(mcap) else None

        if smooth:
            start = shift_months(day, -months)
            growth_end = day
            n_days = (day - start).days
        elif print_index >= 1:
            growth_end = money[print_index][0]
            start = money[print_index - 1][0]
            n_days = (growth_end - start).days
        else:
            start = None
            growth_end = None
            n_days = 0

        ref_date = start.isoformat() if start is not None and start >= eval_start else None
        if start is None or start < m0 or n_days <= 0 or level is None or mcap is None:
            points.append(
                _point(day, "insufficient", None, None, None, level, None, mcap, price, supply, ref_date)
            )
        else:
            start_i = (start - m0).days
            end_i = (growth_end - m0).days
            level_start = m_levels[start_i]
            level_end = m_levels[end_i]
            growth_method = "trailing" if method == "none" else method
            raw = _growth(growth_method, m_levels, start_i, end_i, level_start, level_end, n_days)
            growth = raw
            if normalizing:
                d_start, d_start_i = _at(d_levels, d0, start)
                d_end, d_end_i = _at(d_levels, d0, growth_end)
                rate = proportional_rate(
                    growth_method, d_levels, d_start_i, d_end_i, d_start, d_end, n_days
                )
                growth = excess_growth(method, raw, level_end, level_start, rate)
            state, days = _classify(growth, mcap)
            points.append(
                _point(
                    day, state, days, growth, raw, level, level_start, mcap, price, supply, ref_date
                )
            )
        day += timedelta(days=1)
    return annotate_counters(points)


def _point(day, state, days, growth, growth_unadjusted, level, level_start, mcap, price, supply, ref_date) -> dict:
    return {
        "date": day.isoformat(),
        "state": state,
        "days": days,
        "growth_per_day": growth,
        "growth_unadjusted": growth_unadjusted,
        "level": level,
        "level_start": level_start,
        "mcap": mcap,
        "price": price,
        "supply": supply,
        "ref_date": ref_date,
        "fixed_price_days": None,
        "fixed_units_days": None,
    }


def annotate_counters(points) -> list[dict]:
    """Days at the reference bitcoin price, and days at the reference coin count.

    The reference is the start of the window, or the previous money print when
    smoothing is off. Both counters use today's pace, so they can be compared
    with today's bailout.
    """
    by_date = {point["date"]: point for point in points}
    for point in points:
        point["fixed_price_days"] = None
        point["fixed_units_days"] = None
        ref = by_date.get(point.get("ref_date") or "")
        growth = point.get("growth_per_day")
        if ref is None or not _positive(growth):
            continue
        if _positive(ref.get("price")) and _positive(point.get("supply")):
            point["fixed_price_days"] = ref["price"] * point["supply"] / growth
        if _positive(point.get("price")) and _positive(ref.get("supply")):
            point["fixed_units_days"] = point["price"] * ref["supply"] / growth
    return points


def decompose(start: dict, end: dict) -> dict | None:
    """Split end days minus start days into money growth, bitcoin price, and new coins.

    Order, which adds up exactly: money growth moves first, with bitcoin's
    price and the coins outstanding held at the reference date. Price moves
    next, coins still held. Coins outstanding move last.

    fixed_price_days holds today's coin count at the reference price.
    fixed_units_days holds today's price at the reference coin count.
    """
    g0 = start.get("growth_per_day")
    g1 = end.get("growth_per_day")
    p0 = start.get("price")
    p1 = end.get("price")
    s0 = start.get("supply")
    s1 = end.get("supply")
    if not all(_positive(value) for value in (g0, g1, p0, p1, s0, s1)):
        return None
    days_start = p0 * s0 / g0
    after_money = p0 * s0 / g1
    after_price = p1 * s0 / g1
    days_end = p1 * s1 / g1
    return {
        "days_start": days_start,
        "days_end": days_end,
        "from_money": after_money - days_start,
        "from_price": after_price - after_money,
        "from_supply": days_end - after_price,
        "fixed_price_days": p0 * s1 / g1,
        "fixed_units_days": p1 * s0 / g1,
        "change": days_end - days_start,
    }


def _days_chart(points) -> list[dict]:
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


def _series_chart(points, key: str, positive_only: bool) -> list[dict]:
    """Same gap rule as the day count, for a numeric field on each point.

    The pace chart sets positive_only False so a decrease is drawn below zero
    instead of being dropped.
    """
    rows = []
    gap_open = False
    last_ok = False
    for point in points:
        value = point.get(key)
        ok = _positive(value) if positive_only else (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        )
        if ok:
            rows.append({"time": point["date"], "value": value})
            gap_open = False
            last_ok = True
            continue
        last_ok = False
        if rows and not gap_open:
            rows.append({"time": point["date"]})
            gap_open = True
    if points and not last_ok and rows and rows[-1]["time"] != points[-1]["date"]:
        rows.append({"time": points[-1]["date"]})
    return rows


def to_chart_data(points, key: str = "days") -> list[dict]:
    if key == "days":
        return _days_chart(points)
    return _series_chart(points, key, positive_only=(key != "growth_per_day"))
