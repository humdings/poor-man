#!/usr/bin/env python3
"""Fetch the public series behind Poor Man's Bailout and write data/series.json.

No API key. FRED is read from the public CSV endpoint

    https://fred.stlouisfed.org/graph/fredgraph.csv?id=SERIES

If that endpoint does not respond, the script uses the Board of Governors
release FRED republishes (H.6 for M2, the monetary base, and currency in
circulation; H.4.1 for the balance sheet) and says so in the file. Public
debt prefers the Treasury's Debt to the Penny file, with the Historical
Debt Outstanding annual series (from 1790) and FRED GFDEBTN quarterly
history spliced in front of it. Bitcoin is Coin Metrics' community
API (PriceUSD and CapMrktCurUSD), with Blockchain.com charts as a fallback.

Run from anywhere:

    python3 scripts/fetch_data.py
"""

from __future__ import annotations

import csv
import io
import json
import sys
import time
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from metric import compute_bailout  # noqa: E402
from share_card import write_share_card  # noqa: E402
from sources import parse_fred_csv, parse_frb_series, splice_before  # noqa: E402

OUT = ROOT / "data" / "series.json"
USER_AGENT = "poor-man-bailout/1.0 (+https://github.com/humdings/poor-man)"

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
H6_ZIP = "https://www.federalreserve.gov/releases/h6/data/FRB_h6_xml.zip"
H41_ZIP = "https://www.federalreserve.gov/releases/h41/data/FRB_h41_xml.zip"
H6_PAGE = "https://www.federalreserve.gov/releases/h6/current/default.htm"
H41_PAGE = "https://www.federalreserve.gov/releases/h41/current/"
DEBT_DAILY_URL = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"
    "v2/accounting/od/debt_to_penny"
)
DEBT_ANNUAL_URL = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"
    "v2/accounting/od/debt_outstanding"
)
DEBT_PAGE = "https://fiscaldata.treasury.gov/datasets/debt-to-the-penny/debt-to-the-penny"
DEBT_ANNUAL_PAGE = (
    "https://fiscaldata.treasury.gov/datasets/historical-debt-outstanding/"
    "historical-debt-outstanding"
)
# Same Treasury series, used only when fiscaldata.treasury.gov does not respond.
# First print checked below: 1790-01-01, $71,060,508.50.
DEBT_ANNUAL_MIRROR = "https://everydebtclock.com/data/us-debt-annual.csv"
COIN_METRICS = (
    "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
    "?assets=btc&metrics=PriceUSD,CapMrktCurUSD&frequency=1d"
    "&page_size=10000&start_time=2009-01-01"
)
COIN_METRICS_DOCS = "https://docs.coinmetrics.io/api/v4/"
BLOCKCHAIN_CAP = (
    "https://api.blockchain.info/charts/market-cap?timespan=all&format=json&sampled=false"
)
BLOCKCHAIN_PRICE = (
    "https://api.blockchain.info/charts/market-price?timespan=all&format=json&sampled=false"
)

# Published units, checked against the Board release (UNIT_MULT) and the
# well-known first prints. The CSV endpoint does not carry a unit field.
FRED_MULTIPLIER = {
    "M2SL": 1_000_000_000,  # billions
    "BOGMBASE": 1_000_000_000,  # billions
    "MBCURRCIR": 1_000_000_000,  # billions
    "WALCL": 1_000_000,  # millions
    "GFDEBTN": 1_000_000,  # millions
    "GDP": 1_000_000_000,  # billions
    "CPIAUCSL": 1,  # index, 1982-84=100
    "CPIAUCNS": 1,  # same index, not seasonally adjusted, from 1913
}

# CPI moves by fractions of an index point. Rounding to an integer would
# erase a typical month. Dollar stocks stay whole dollars.
FRED_INTEGRAL = {
    "CPIAUCSL": False,
    "CPIAUCNS": False,
}


def get_bytes(url: str, timeout: int = 60, retries: int = 3) -> bytes:
    last = None
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
            with urlopen(req, timeout=timeout) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last = exc
            time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"GET failed for {url}: {last}")


def fred_csv(series_id: str):
    url = FRED_CSV.format(series_id=series_id)
    try:
        raw = get_bytes(url, timeout=18, retries=2)
    except Exception as exc:
        print(f"  FRED {series_id} did not respond ({exc})")
        return None
    text = raw.decode("utf-8-sig")
    first = text.splitlines()[0] if text else ""
    if "observation_date" not in first:
        print(f"  FRED {series_id} returned something other than CSV")
        return None
    rows = parse_fred_csv(
        text,
        FRED_MULTIPLIER[series_id],
        integral=FRED_INTEGRAL.get(series_id, True),
    )
    if len(rows) < 2:
        print(f"  FRED {series_id} CSV was empty")
        return None
    print(f"  FRED {series_id}: {rows[0][0]} → {rows[-1][0]} ({len(rows)} prints)")
    return rows


def zip_member(url: str, suffix: str) -> str:
    raw = get_bytes(url, timeout=180, retries=2)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        name = next(item for item in archive.namelist() if item.endswith(suffix))
        return archive.read(name).decode("utf-8")


def treasury_pages(url: str, fields: str) -> list[dict]:
    rows = []
    page = 1
    while page < 100:
        query = urlencode(
            {
                "fields": fields,
                "sort": "record_date",
                "page[size]": 10000,
                "page[number]": page,
            }
        )
        payload = json.loads(get_bytes(f"{url}?{query}", timeout=90).decode("utf-8"))
        rows.extend(payload.get("data") or [])
        total = int(payload.get("meta", {}).get("total-pages") or 1)
        if page >= total:
            break
        page += 1
    return rows


def committed_debt():
    """Debt points already in data/series.json, used when a live feed times out."""
    if not OUT.exists():
        return []
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    debt = next(item for item in doc["measures"] if item["id"] == "debt")
    rows = [(date.fromisoformat(day), value) for day, value in debt["points"]]
    rows.sort()
    return rows


def load_debt_daily():
    try:
        return load_debt_daily_live()
    except Exception as exc:
        print(f"  Debt to the Penny did not respond ({exc})")
        rows = [row for row in committed_debt() if row[0] >= date(1993, 4, 1)]
        if not rows:
            raise
        print(f"  Using the committed daily file: {rows[0][0]} → {rows[-1][0]} ({len(rows)} days)")
        return rows


def load_debt_daily_live():
    raw = treasury_pages(DEBT_DAILY_URL, "record_date,tot_pub_debt_out_amt")
    rows = []
    for item in raw:
        rows.append(
            (
                date.fromisoformat(item["record_date"]),
                int(round(float(item["tot_pub_debt_out_amt"]))),
            )
        )
    rows.sort()
    print(f"  Debt to the Penny: {rows[0][0]} → {rows[-1][0]} ({len(rows)} days)")
    return rows


def load_debt_annual():
    try:
        return load_debt_annual_api(), "api"
    except Exception as exc:
        print(f"  Historical debt outstanding API did not respond ({exc})")
        return load_debt_annual_mirror(), "mirror"


def load_debt_annual_api():
    raw = treasury_pages(DEBT_ANNUAL_URL, "record_date,debt_outstanding_amt")
    rows = []
    for item in raw:
        rows.append(
            (
                date.fromisoformat(item["record_date"]),
                int(round(float(item["debt_outstanding_amt"]))),
            )
        )
    rows.sort()
    check_debt_annual(rows)
    print(f"  Historical debt outstanding: {rows[0][0]} → {rows[-1][0]} ({len(rows)})")
    return rows


def load_debt_annual_mirror():
    text = get_bytes(DEBT_ANNUAL_MIRROR, timeout=30).decode("utf-8")
    rows = []
    for item in csv.DictReader(io.StringIO(text)):
        rows.append(
            (
                date.fromisoformat(item["record_date"]),
                int(round(float(item["total_public_debt_outstanding_usd"]))),
            )
        )
    rows.sort()
    check_debt_annual(rows)
    print(f"  Historical debt mirror: {rows[0][0]} → {rows[-1][0]} ({len(rows)})")
    return rows


def month_end_daily(rows, daily_from):
    """Keep sparse history as published, and thin the daily file to month-ends.

    One bar per print is how the chart spaces time, so 8,000 daily points
    would hide 1790–1993 in a sliver. The first daily print and the latest
    print stay, so the splice date and the headline level do not move.
    """
    early = [row for row in rows if row[0] < daily_from]
    daily = [row for row in rows if row[0] >= daily_from]
    if len(daily) < 3:
        return rows
    # The last 400 days stay daily so a 12-month window still sees the same days.
    cutoff = daily[-1][0] - timedelta(days=400)
    older = [row for row in daily if row[0] < cutoff]
    recent = [row for row in daily if row[0] >= cutoff]
    kept = []
    last_key = None
    for day, value in older:
        key = (day.year, day.month)
        if day == daily_from or not kept or key != last_key or kept[-1][0] == daily_from:
            kept.append((day, value))
            last_key = key
        else:
            kept[-1] = (day, value)
    print(
        f"  Debt to the Penny thinned to month-ends before {cutoff}: "
        f"{len(daily)} days → {len(kept) + len(recent)} prints"
    )
    return early + kept + recent


def check_debt_annual(rows):
    if not rows or rows[0][0] != date(1790, 1, 1):
        raise RuntimeError(f"historical debt does not start 1790-01-01 (got {rows[:1]})")
    if not 71_000_000 <= rows[0][1] <= 71_100_000:
        raise RuntimeError(f"1790 debt {rows[0][1]} is not the published $71,060,508.50")


def load_bitcoin():
    try:
        return load_bitcoin_coinmetrics()
    except Exception as exc:
        print(f"  Coin Metrics failed ({exc}); trying Blockchain.com charts")
        return load_bitcoin_blockchain()


def load_bitcoin_coinmetrics():
    url = COIN_METRICS
    rows = []
    pages = 0
    while url and pages < 20:
        payload = json.loads(get_bytes(url, timeout=90).decode("utf-8"))
        for item in payload.get("data") or []:
            cap = item.get("CapMrktCurUSD")
            if cap is None:
                continue
            price = item.get("PriceUSD")
            rows.append(
                (
                    item["time"][:10],
                    round(float(cap), 2),
                    round(float(price), 8) if price is not None else None,
                )
            )
        url = payload.get("next_page_url") or ""
        pages += 1
    dedup = {}
    for day, cap, price in rows:
        if cap > 0:
            dedup[day] = (cap, price)
    points = [(day, cap, price) for day, (cap, price) in sorted(dedup.items())]
    if not points:
        raise RuntimeError("Coin Metrics returned no bitcoin market cap")
    print(f"  Coin Metrics BTC: {points[0][0]} → {points[-1][0]} ({len(points)} days)")
    return {
        "points": points,
        "source_name": "Coin Metrics community API",
        "source_url": COIN_METRICS_DOCS,
        "request_url": COIN_METRICS,
        "series": "CapMrktCurUSD and PriceUSD",
        "retrieval": (
            "Coin Metrics community API, no key. "
            "Metrics CapMrktCurUSD (market cap, USD) and PriceUSD, daily."
        ),
    }


def load_bitcoin_blockchain():
    cap_payload = json.loads(get_bytes(BLOCKCHAIN_CAP, timeout=90).decode("utf-8"))
    price_payload = json.loads(get_bytes(BLOCKCHAIN_PRICE, timeout=90).decode("utf-8"))
    prices = {}
    for item in price_payload.get("values") or []:
        day = datetime.fromtimestamp(item["x"], timezone.utc).date().isoformat()
        prices[day] = round(float(item["y"]), 8)
    dedup = {}
    for item in cap_payload.get("values") or []:
        day = datetime.fromtimestamp(item["x"], timezone.utc).date().isoformat()
        cap = round(float(item["y"]), 2)
        if cap > 0:
            dedup[day] = (cap, prices.get(day))
    points = [(day, cap, price) for day, (cap, price) in sorted(dedup.items())]
    if not points:
        raise RuntimeError("Blockchain.com returned no market cap")
    print(f"  Blockchain.com BTC: {points[0][0]} → {points[-1][0]} ({len(points)} days)")
    return {
        "points": points,
        "source_name": "Blockchain.com charts",
        "source_url": "https://www.blockchain.com/charts/market-cap",
        "request_url": BLOCKCHAIN_CAP,
        "series": "market-cap and market-price",
        "retrieval": (
            "Blockchain.com public charts (market-cap and market-price), "
            "used because the Coin Metrics community API did not respond."
        ),
    }


def require_range(name, rows, last_low, last_high, fresh_days):
    if len(rows) < 8:
        raise SystemExit(f"{name} has too few observations ({len(rows)})")
    last_day, last_value = rows[-1][0], rows[-1][1]
    if not last_low <= last_value <= last_high:
        raise SystemExit(
            f"{name} latest value {last_value} is outside {last_low}–{last_high}. "
            "Refusing to write a snapshot that looks like a unit error."
        )
    age = (date.today() - last_day).days
    if age > fresh_days:
        raise SystemExit(f"{name} latest print {last_day} is {age} days old")
    if any(value <= 0 for _, value in rows):
        raise SystemExit(f"{name} has a non-positive level")


def measure_record(**kwargs):
    points = kwargs.pop("points")
    return dict(kwargs, start=points[0][0].isoformat(), end=points[-1][0].isoformat(), count=len(points), points=[[d.isoformat(), v] for d, v in points])


def load_deflators() -> dict:
    """Nominal GDP and CPI, the two public deflators the page can subtract.

    No API key. Both are FRED CSV. CPI is stored as the index, because the
    normalization uses ratios. GDP is stored in dollars; the annualized rate
    cancels in the ratio.
    """
    print("Deflators…")
    specs = [
        (
            "gdp",
            "GDP",
            "Nominal GDP",
            "quarterly",
            "Seasonally adjusted annual rate",
            "Billions of dollars",
            1_000_000_000,
            "https://fred.stlouisfed.org/series/GDP",
            "Gross Domestic Product. Only the ratio of levels is used, so the annualized rate cancels.",
            date(1948, 1, 1),
            1.5e13,
            8e13,
        ),
        (
            "cpi",
            "CPIAUCSL",
            "CPI",
            "monthly",
            "Seasonally adjusted",
            "Index 1982-84=100",
            1,
            "https://fred.stlouisfed.org/series/CPIAUCSL",
            "Consumer Price Index for All Urban Consumers, all items. Stored as the index.",
            date(1948, 1, 1),
            200,
            500,
        ),
    ]
    out = {}
    for (
        key,
        series_id,
        name,
        frequency,
        seasonal,
        published_units,
        multiplier,
        url,
        role,
        start_before,
        latest_low,
        latest_high,
    ) in specs:
        rows = fred_csv(series_id)
        if not rows:
            raise SystemExit(
                f"{series_id} is required for the normalization option and the FRED CSV endpoint did not respond."
            )
        if rows[0][0] > start_before:
            raise SystemExit(f"{series_id} starts too late ({rows[0][0]})")
        latest = rows[-1][1]
        if not latest_low <= latest <= latest_high:
            raise SystemExit(f"{series_id} latest value {latest} failed the unit check")
        extra = {}
        if series_id == "CPIAUCSL":
            nsa = fred_csv("CPIAUCNS")
            if nsa and nsa[0][0] < rows[0][0]:
                early = [row for row in nsa if row[0] < rows[0][0]]
                # Same 1982-84 index. Keep the seasonally adjusted print on the overlap.
                rows = early + rows
                extra = {
                    "history_fred_id": "CPIAUCNS",
                    "history_url": "https://fred.stlouisfed.org/series/CPIAUCNS",
                    "seasonal_from": "1947-01-01",
                }
                role = (
                    "CPIAUCNS (not seasonally adjusted) before 1947-01-01, then CPIAUCSL. "
                    "Both are the 1982-84 index. The latest half-life uses the seasonally adjusted print."
                )
        out[key] = measure_record(
            points=rows,
            id=key,
            name=name,
            fred_id=series_id,
            fred_url=url,
            frequency=frequency,
            seasonal=seasonal,
            published_units=published_units,
            multiplier=multiplier,
            role=role,
            retrieval=(
                f"FRED CSV for {series_id}, no API key. {role}"
            ),
            **extra,
        )
    return out


def main() -> int:
    print("Probing FRED CSV (M2SL)…")
    m2_fred = fred_csv("M2SL")
    fred_up = m2_fred is not None

    h6_xml = None
    h41_xml = None

    def h6():
        nonlocal h6_xml
        if h6_xml is None:
            print("Downloading Board H.6 release…")
            h6_xml = zip_member(H6_ZIP, "H6_data.xml")
        return h6_xml

    def h41():
        nonlocal h41_xml
        if h41_xml is None:
            print("Downloading Board H.4.1 release…")
            h41_xml = zip_member(H41_ZIP, "H41_data.xml")
        return h41_xml

    def from_fred_or_board(series_id, fred_rows, loader, page, blurb):
        if fred_rows is not None:
            return fred_rows, (
                f"FRED CSV for {series_id}. {blurb}",
                f"https://fred.stlouisfed.org/series/{series_id}",
            )
        if fred_up:
            fred_rows = fred_csv(series_id)
            if fred_rows is not None:
                return fred_rows, (
                    f"FRED CSV for {series_id}. {blurb}",
                    f"https://fred.stlouisfed.org/series/{series_id}",
                )
        rows = loader()
        return rows, (
            f"Board of Governors release, the source FRED republishes as {series_id}. "
            f"The FRED CSV endpoint did not respond when this snapshot was built. {blurb}",
            page,
        )

    print("US M2…")
    m2_points, (m2_retrieval, m2_source) = from_fred_or_board(
        "M2SL",
        m2_fred,
        lambda: parse_frb_series(h6(), "M2.M", month_start=True),
        H6_PAGE,
        "Billions of dollars, seasonally adjusted, monthly, converted to dollars × 1e9. "
        "Weekly not-seasonally-adjusted M2 (FRED WM2NS) is not spliced on, because mixing it with seasonally adjusted M2 would add a seasonal jump.",
    )
    require_range("M2", m2_points, 5e12, 8e13, 120)
    if m2_points[0][0] != date(1959, 1, 1):
        raise SystemExit(f"M2 does not start on 1959-01-01 (got {m2_points[0][0]})")
    if not 2.5e11 <= m2_points[0][1] <= 3.2e11:
        raise SystemExit(f"M2 first print {m2_points[0][1]} is not the 1959 level in dollars")

    print("Monetary base…")
    base_points, (base_retrieval, base_source) = from_fred_or_board(
        "BOGMBASE",
        None,
        lambda: parse_frb_series(h6(), "RESMO14A_N.M", month_start=True),
        H6_PAGE,
        "Billions of dollars, not seasonally adjusted, monthly, converted to dollars × 1e9. Full history of the series.",
    )
    require_range("Monetary base", base_points, 5e11, 3e13, 120)
    if not 4e10 <= base_points[0][1] <= 8e10:
        raise SystemExit(f"Monetary base first print {base_points[0][1]} failed the unit check")

    print("Currency in circulation…")
    currency_points, (currency_retrieval, currency_source) = from_fred_or_board(
        "MBCURRCIR",
        None,
        lambda: parse_frb_series(h6(), "RESMOC14A_N.M", month_start=True),
        H6_PAGE,
        "Billions of dollars, not seasonally adjusted, monthly, converted to dollars × 1e9. "
        "This is FRED MBCURRCIR (monetary base; currency in circulation), not the older CURRCIR series. Full history of MBCURRCIR.",
    )
    require_range("Currency in circulation", currency_points, 5e11, 2e13, 120)
    if not 2e10 <= currency_points[0][1] <= 5e10:
        raise SystemExit(f"Currency first print {currency_points[0][1]} failed the unit check")

    print("Fed balance sheet…")
    fed_points, (fed_retrieval, fed_source) = from_fred_or_board(
        "WALCL",
        None,
        lambda: parse_frb_series(h41(), "RESPPMA_N.WW", month_start=False),
        H41_PAGE,
        "Millions of dollars, Wednesday level, not seasonally adjusted, converted to dollars × 1e6. "
        "Total assets less eliminations from consolidation.",
    )
    require_range("Fed balance sheet", fed_points, 5e11, 3e13, 45)
    if fed_points[0][0] != date(2002, 12, 18):
        raise SystemExit(f"Fed series does not start 2002-12-18 (got {fed_points[0][0]})")
    if not 5e11 <= fed_points[0][1] <= 1.2e12:
        raise SystemExit(f"Fed first print {fed_points[0][1]} failed the unit check")

    print("Public debt…")
    daily = load_debt_daily()
    quarterly = None
    if fred_up:
        quarterly = fred_csv("GFDEBTN")
    else:
        print("  Skipping FRED GFDEBTN because the CSV endpoint did not respond")
    try:
        annual, annual_via = load_debt_annual()
    except Exception as exc:
        print(f"  Historical debt outstanding did not respond ({exc})")
        annual, annual_via = None, None
    if not quarterly:
        earlier = [row for row in committed_debt() if row[0] < daily[0][0]]
        if earlier:
            quarterly = earlier
            print(f"  Using committed debt before {daily[0][0]}: {earlier[0][0]} → {earlier[-1][0]}")
    # Annual (from 1790) in front of quarterly GFDEBTN in front of daily Debt to the Penny.
    # splice_before keeps the later series on any overlap.
    history = quarterly or []
    if annual:
        history = splice_before(annual, history) if history else annual
    if not history:
        raise SystemExit("Public debt is missing its pre-1993 history")
    if annual and quarterly:
        mirror_note = (
            " This snapshot read that annual file from a public mirror of the same Treasury series "
            "because fiscaldata.treasury.gov did not respond."
            if annual_via == "mirror" else ""
        )
        early_note = (
            "History before the daily file is the Treasury Historical Debt Outstanding series "
            "(fiscal-year annual, dollars, from 1790-01-01), "
            "then FRED GFDEBTN (millions of dollars, quarterly, converted to dollars × 1e6) "
            "through the day before Debt to the Penny." + mirror_note
        )
        early_url = DEBT_ANNUAL_PAGE
    elif quarterly:
        early_note = (
            "History before the daily file is FRED GFDEBTN (Federal Debt: Total Public Debt), "
            "millions of dollars, quarterly, converted to dollars × 1e6. "
            "The Treasury annual file did not respond for this snapshot."
        )
        early_url = "https://fred.stlouisfed.org/series/GFDEBTN"
    else:
        early_note = (
            "History before the daily file is the Treasury Historical Debt Outstanding series "
            "(fiscal-year annual, dollars). FRED GFDEBTN quarterly was not available for this snapshot."
        )
        early_url = DEBT_ANNUAL_PAGE
    debt_points = month_end_daily(splice_before(history, daily), date(1993, 4, 1))
    require_range("Public debt", debt_points, 5e12, 2e14, 14)
    if debt_points[0][0] >= date(1993, 4, 1):
        raise SystemExit("Public debt is missing its pre-1993 history")
    if annual and debt_points[0][0] != date(1790, 1, 1):
        raise SystemExit(f"Public debt did not keep the 1790 annual print (got {debt_points[0][0]})")
    if not any(day == date(1993, 4, 1) for day, _ in debt_points):
        raise SystemExit("Debt to the Penny start 1993-04-01 is missing")

    print("Bitcoin…")
    btc = load_bitcoin()
    btc_days = [date.fromisoformat(row[0]) for row in btc["points"]]
    if btc_days[0] > date(2010, 8, 1):
        raise SystemExit(f"Bitcoin history starts too late ({btc_days[0]})")
    latest_cap = btc["points"][-1][1]
    if not 1e10 <= latest_cap <= 1e14:
        raise SystemExit(f"Bitcoin market cap {latest_cap} failed the unit check")
    if (date.today() - btc_days[-1]).days > 10:
        raise SystemExit(f"Bitcoin market cap is stale ({btc_days[-1]})")

    measures = [
        measure_record(
            points=m2_points,
            id="m2",
            name="US M2",
            short="M2",
            group="primary",
            fred_id="M2SL",
            fred_url="https://fred.stlouisfed.org/series/M2SL",
            source_url=m2_source,
            frequency="monthly",
            seasonal="Seasonally adjusted",
            published_units="Billions of dollars",
            multiplier=1_000_000_000,
            retrieval=m2_retrieval,
        ),
        measure_record(
            points=base_points,
            id="base",
            name="Monetary base",
            short="Monetary base",
            group="primary",
            fred_id="BOGMBASE",
            fred_url="https://fred.stlouisfed.org/series/BOGMBASE",
            source_url=base_source,
            frequency="monthly",
            seasonal="Not seasonally adjusted",
            published_units="Billions of dollars",
            multiplier=1_000_000_000,
            retrieval=base_retrieval,
        ),
        measure_record(
            points=currency_points,
            id="currency",
            name="Currency in circulation",
            short="Currency",
            group="primary",
            fred_id="MBCURRCIR",
            fred_url="https://fred.stlouisfed.org/series/MBCURRCIR",
            source_url=currency_source,
            frequency="monthly",
            seasonal="Not seasonally adjusted",
            published_units="Billions of dollars",
            multiplier=1_000_000_000,
            retrieval=currency_retrieval,
        ),
        measure_record(
            points=debt_points,
            id="debt",
            name="Public debt",
            short="Public debt",
            group="primary",
            fred_id="GFDEBTN",
            fred_url="https://fred.stlouisfed.org/series/GFDEBTN",
            source_url=DEBT_PAGE,
            history_url=early_url,
            frequency="annual, then quarterly, then month-end, latest daily print kept",
            seasonal="Not seasonally adjusted",
            published_units="Dollars (Debt to the Penny). Earlier history converted to dollars.",
            multiplier=1,
            retrieval=(
                "Treasury Fiscal Data Debt to the Penny, field tot_pub_debt_out_amt, "
                "from 1993-04-01, already in dollars. Prints before the last 400 days are the "
                "last print of each month, so the earlier years stay visible on the chart. " + early_note +
                " Counted as monetary expansion: debt spends the same as cash, and one person's debt is another's asset."
            ),
        ),
        measure_record(
            points=fed_points,
            id="fed",
            name="Fed balance sheet",
            short="Fed balance sheet",
            group="secondary",
            fred_id="WALCL",
            fred_url="https://fred.stlouisfed.org/series/WALCL",
            source_url=fed_source,
            frequency="weekly",
            seasonal="Not seasonally adjusted",
            published_units="Millions of dollars",
            multiplier=1_000_000,
            retrieval=fed_retrieval,
        ),
    ]

    btc_pairs = [(date.fromisoformat(day), cap) for day, cap, _price in btc["points"]]
    print("Checking the 2022–23 M2 contraction and default headlines…")
    headlines = []
    for measure in measures:
        rows = [(date.fromisoformat(d), v) for d, v in measure["points"]]
        series = compute_bailout(rows, btc_pairs, 12, "month", "trailing")
        latest = series[-1] if series else None
        headlines.append(
            {
                "id": measure["id"],
                "name": measure["name"],
                "date": latest["date"] if latest else None,
                "state": latest["state"] if latest else None,
                "days": latest["days"] if latest else None,
                "growth_per_day": latest["growth_per_day"] if latest else None,
                "level": latest["level"] if latest else None,
                "mcap": latest["mcap"] if latest else None,
            }
        )
        if measure["id"] == "m2":
            gap = [
                point
                for point in series
                if point["state"] == "contracting" and "2022-01-01" <= point["date"] <= "2023-12-31"
            ]
            if not gap:
                raise SystemExit(
                    "12-month trailing M2 shows no contraction in 2022–23. "
                    "The snapshot was not written."
                )
            print(f"  M2 contracting days inside 2022–23: {len(gap)}")

    document = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bailout": {
            "name": "Poor Man's Bailout",
            "default_measure": "m2",
            "default_window": {"amount": 12, "unit": "month"},
            "default_method": "trailing",
            "definition": (
                "Days for the selected money stock to grow by one bitcoin market cap. "
                "On a date t, with window start s and N calendar days between them, "
                "d(t) = C(t) / g(t) when the average growth per day g(t) is positive. "
                "C is the bitcoin market cap in dollars."
            ),
            "methods": {
                "trailing": "(M(t) − M(s)) / N",
                "regression": "OLS slope of the daily forward-filled level from s through t, dollars per day",
                "cagr": "M(t) × ((M(t) / M(s))^(1/N) − 1), the compound pace at today's level",
            },
            "alignment": (
                "Each money series is stepped forward to every calendar day: the last print stays in effect until the next one. "
                "The bitcoin market cap is the print on that calendar day, or the latest print on or before it. "
                "The series is evaluated through the later of the two last prints, so the older one is carried forward. "
                "Monthly Board dates are restamped to the first of the month when the snapshot comes from H.6, matching FRED."
            ),
            "contraction": (
                "If g(t) is zero or negative the day count is undefined. "
                "It is not plotted, and it is never stored as a negative or infinite number."
            ),
            "axiom": "Money spends the same, so expansion in any form counts as expansion.",
            "smoothing": (
                "A window and an averaging method smooth the pace. No smoothing uses the change "
                "between the money print in effect and the print before it, held until the next print. "
                "A decrease stays a decrease: the pace is negative and the day count is left blank."
            ),
            "normalization": (
                "Off by default. When on, the pace is money growth in excess of nominal GDP (FRED GDP) "
                "or CPI (FRED CPIAUCSL) over the same interval the averaging method already uses. "
                "Trailing and print-to-print: g* = g − M(start) × (D(end) − D(start)) / (N × D(start)). "
                "CAGR: g* = M(end) × (r(M) − r(D)), with r the compound daily rate. "
                "Regression: g* = slope(M) − M(end) × slope(ln D). "
                "A flat deflator leaves the pace unchanged. Equal percentage growth has excess zero "
                "for the trailing and CAGR paces. GDP is a seasonally adjusted annual rate; only the "
                "ratio of levels is used, so the annualization cancels."
            ),
            "decomposition": (
                "The change in the day count splits exactly into money growth, then the bitcoin price, "
                "then coins outstanding. Money growth moves first, with price and supply held at the "
                "start of the window. Days at a fixed bitcoin price hold that starting price and use "
                "today's coin count and pace. A longer bailout at a high price is a higher valuation "
                "relative to monetary expansion."
            ),
        },
        "btc": {
            "name": "Bitcoin market cap",
            "source_name": btc["source_name"],
            "source_url": btc["source_url"],
            "request_url": btc["request_url"],
            "series": btc["series"],
            "retrieval": btc["retrieval"],
            "start": btc["points"][0][0],
            "end": btc["points"][-1][0],
            "count": len(btc["points"]),
            "points": btc["points"],
        },
        "headlines_default": headlines,
        "measures": measures,
        "deflators": load_deflators(),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(document, separators=(",", ":")) + "\n", encoding="utf-8")
    card = write_share_card(document)
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")
    print(f"Wrote share card: {card['days_label']} days, half-life {card['half_label']} years")
    print("HEADLINES 12-month trailing change")
    for row in headlines:
        days = "undefined" if row["days"] is None else f"{row['days']:.2f}"
        print(
            f"  {row['id']}: {row['state']} {days} days on {row['date']} "
            f"(level {row['level']}, cap {row['mcap']}, g/day {row['growth_per_day']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
