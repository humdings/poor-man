"""Read public money and bitcoin series into dated dollar levels."""

from __future__ import annotations

import re
from datetime import date


def parse_fred_csv(text: str, multiplier: float) -> list[tuple[date, int]]:
    """FRED graph CSV. Missing prints are '.'. Multiplier converts to dollars."""
    rows = []
    for line in text.splitlines()[1:]:
        line = line.strip()
        if not line or "," not in line:
            continue
        date_s, val = line.split(",", 1)
        val = val.strip()
        if val in {"", "."}:
            continue
        rows.append(
            (date.fromisoformat(date_s.strip()), int(round(float(val) * multiplier)))
        )
    return rows


def parse_frb_series(xml_text: str, series_name: str, month_start: bool = False) -> list[tuple[date, int]]:
    """One series from a Board of Governors SDMX package.

    UNIT_MULT on the series is the published scale (1e9 billions, 1e6 millions).
    Monthly H.6 dates are month-end; month_start restamps them to the first of
    that month so they line up with FRED's monthly convention.
    """
    token = f'SERIES_NAME="{series_name}"'
    found = xml_text.find(token)
    if found < 0:
        raise ValueError(f"series {series_name} not in release")
    start = xml_text.rfind("<kf:Series", 0, found)
    end = xml_text.find("</kf:Series>", found)
    if start < 0 or end < 0:
        raise ValueError(f"could not isolate {series_name}")
    block = xml_text[start:end]
    opening = block[: block.find(">")]
    mult_match = re.search(r'UNIT_MULT="([^"]+)"', opening)
    if not mult_match:
        raise ValueError(f"{series_name} has no UNIT_MULT")
    multiplier = float(mult_match.group(1))
    dedup: dict[date, int] = {}
    for obs in re.finditer(r"<frb:Obs\b([^>]*)/?>", block):
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', obs.group(1)))
        raw = attrs.get("OBS_VALUE", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        observed = date.fromisoformat(attrs["TIME_PERIOD"])
        if month_start:
            observed = observed.replace(day=1)
        dedup[observed] = int(round(value * multiplier))
    return sorted(dedup.items())


def splice_before(early, later):
    """Keep early observations strictly before the first later observation.

    On an overlapping date the later series wins. Used to attach quarterly
    or annual debt history in front of the daily Debt to the Penny file.
    """
    if not later:
        return list(early)
    cutoff = later[0][0]
    return [row for row in early if row[0] < cutoff] + list(later)
