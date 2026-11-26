"""Parsers and unit conversions. Levels are stored in dollars."""

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sources import (  # noqa: E402
    parse_fred_csv,
    parse_frb_series,
    splice_before,
)


FRED_M2 = """\
observation_date,M2SL
1959-01-01,286.6
1959-02-01,287.7
1959-03-01,.
1959-04-01,290.0
"""

H6_MONTHLY = """\
<kf:Series ADJUSTED="SA" CURRENCY="USD" FREQ="129" SERIES_NAME="M2.M" UNIT="Currency" UNIT_MULT="1e+09">
  <frb:Obs OBS_STATUS="A" OBS_VALUE="286.6" TIME_PERIOD="1959-01-31" />
  <frb:Obs OBS_STATUS="A" OBS_VALUE="ND" TIME_PERIOD="1959-02-28" />
  <frb:Obs OBS_STATUS="A" OBS_VALUE="287.7" TIME_PERIOD="1959-03-31" />
</kf:Series>
"""

H41_WEEKLY = """\
<kf:Series FREQ="19" SERIES_NAME="RESPPMA_N.WW" UNIT="Currency" UNIT_MULT="1000000">
  <frb:Obs OBS_STATUS="A" OBS_VALUE="719542" TIME_PERIOD="2002-12-18" />
  <frb:Obs OBS_STATUS="A" OBS_VALUE="732059" TIME_PERIOD="2002-12-25" />
</kf:Series>
"""


class FredCsvTests(unittest.TestCase):
    def test_billions_to_dollars_and_skips_missing(self):
        rows = parse_fred_csv(FRED_M2, multiplier=1_000_000_000)
        self.assertEqual(
            rows,
            [
                (date(1959, 1, 1), 286_600_000_000),
                (date(1959, 2, 1), 287_700_000_000),
                (date(1959, 4, 1), 290_000_000_000),
            ],
        )

    def test_cpi_keeps_fractional_index_points(self):
        text = "observation_date,CPIAUCSL\n2024-01-01,308.417\n2024-02-01,310.326\n"
        rows = parse_fred_csv(text, multiplier=1, integral=False)
        self.assertEqual(rows, [(date(2024, 1, 1), 308.417), (date(2024, 2, 1), 310.326)])

    def test_millions_to_dollars(self):
        text = "observation_date,WALCL\n2002-12-18,719542\n"
        rows = parse_fred_csv(text, multiplier=1_000_000)
        self.assertEqual(rows, [(date(2002, 12, 18), 719_542_000_000)])


class FrbXmlTests(unittest.TestCase):
    def test_monthly_billions_shift_to_fred_month_start(self):
        rows = parse_frb_series(H6_MONTHLY, "M2.M", month_start=True)
        self.assertEqual(
            rows,
            [
                (date(1959, 1, 1), 286_600_000_000),
                (date(1959, 3, 1), 287_700_000_000),
            ],
        )

    def test_weekly_millions_keep_the_wednesday(self):
        rows = parse_frb_series(H41_WEEKLY, "RESPPMA_N.WW", month_start=False)
        self.assertEqual(rows[0], (date(2002, 12, 18), 719_542_000_000))
        self.assertEqual(rows[1][0], date(2002, 12, 25))


class SpliceTests(unittest.TestCase):
    def test_keeps_early_history_strictly_before_daily_start(self):
        early = [
            (date(1966, 1, 1), 320_000_000_000),
            (date(1993, 1, 1), 4_000_000_000_000),
            (date(1993, 4, 1), 4_200_000_000_000),
        ]
        daily = [
            (date(1993, 4, 1), 4_225_873_987_843),
            (date(1993, 4, 2), 4_226_000_000_000),
        ]
        spliced = splice_before(early, daily)
        self.assertEqual(
            [d for d, _ in spliced],
            [date(1966, 1, 1), date(1993, 1, 1), date(1993, 4, 1), date(1993, 4, 2)],
        )
        # The daily print wins on the overlap date.
        self.assertEqual(spliced[2][1], 4_225_873_987_843)


if __name__ == "__main__":
    unittest.main()
