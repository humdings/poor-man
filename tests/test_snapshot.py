"""Checks on the committed snapshot: units, coverage, and the 2022–23 gap."""

import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "series.json"
sys.path.insert(0, str(ROOT / "scripts"))

from metric import compute_bailout, trailing_cpi_half_life  # noqa: E402


def load():
    return json.loads(DATA.read_text(encoding="utf-8"))


@unittest.skipUnless(DATA.exists(), "snapshot not built yet")
class SnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = load()

    def test_measure_order_and_groups(self):
        ids = [m["id"] for m in self.doc["measures"]]
        self.assertEqual(ids, ["m2", "base", "currency", "debt", "fed"])
        groups = {m["id"]: m["group"] for m in self.doc["measures"]}
        self.assertEqual(groups["fed"], "secondary")
        self.assertTrue(all(groups[i] == "primary" for i in ids if i != "fed"))

    def test_m2_starts_in_1959_in_dollars(self):
        m2 = self.doc["measures"][0]
        self.assertEqual(m2["start"], "1959-01-01")
        self.assertEqual(m2["fred_id"], "M2SL")
        self.assertEqual(m2["multiplier"], 1_000_000_000)
        first = m2["points"][0][1]
        self.assertGreater(first, 2.5e11)
        self.assertLess(first, 3.2e11)

    def test_monetary_base_and_currency_units(self):
        base = next(m for m in self.doc["measures"] if m["id"] == "base")
        currency = next(m for m in self.doc["measures"] if m["id"] == "currency")
        self.assertEqual(base["fred_id"], "BOGMBASE")
        self.assertEqual(currency["fred_id"], "MBCURRCIR")
        self.assertGreater(base["points"][0][1], 4e10)
        self.assertLess(base["points"][0][1], 8e10)
        self.assertGreater(currency["points"][0][1], 2e10)
        self.assertLess(currency["points"][0][1], 5e10)
        # Currency in the monetary base is smaller than the base itself.
        self.assertLess(currency["points"][-1][1], base["points"][-1][1])

    def test_fed_balance_sheet_wednesday_dollars(self):
        fed = next(m for m in self.doc["measures"] if m["id"] == "fed")
        self.assertEqual(fed["start"], "2002-12-18")
        self.assertEqual(fed["fred_id"], "WALCL")
        self.assertEqual(fed["multiplier"], 1_000_000)
        self.assertGreater(fed["points"][0][1], 5e11)
        self.assertLess(fed["points"][0][1], 1.2e12)

    def test_debt_splices_history_in_front_of_april_1993(self):
        debt = next(m for m in self.doc["measures"] if m["id"] == "debt")
        days = [row[0] for row in debt["points"]]
        self.assertLess(days[0], "1993-04-01")
        self.assertIn("1993-04-01", days)
        joined = dict(debt["points"])
        # Debt to the Penny opens just above $4.2 trillion.
        self.assertGreater(joined["1993-04-01"], 4e12)
        self.assertLess(joined["1993-04-01"], 4.5e12)
        self.assertGreater(debt["points"][-1][1], 3e13)

    def test_bitcoin_market_cap_starts_in_2010(self):
        btc = self.doc["btc"]
        self.assertLessEqual(btc["start"], "2010-08-01")
        self.assertGreater(btc["start"], "2008-01-01")
        self.assertGreater(btc["points"][0][1], 0)
        self.assertGreater(btc["points"][-1][1], 1e10)
        self.assertIn("Coin Metrics", btc["source_name"] + btc["retrieval"])

    def test_default_headline_matches_the_library_and_shows_the_2022_gap(self):
        m2 = next(m for m in self.doc["measures"] if m["id"] == "m2")
        money = [(date.fromisoformat(d), v) for d, v in m2["points"]]
        btc = [(date.fromisoformat(row[0]), row[1]) for row in self.doc["btc"]["points"]]
        series = compute_bailout(money, btc, 12, "month", "trailing")
        latest = series[-1]
        stored = next(row for row in self.doc["headlines_default"] if row["id"] == "m2")
        self.assertEqual(stored["state"], latest["state"])
        self.assertEqual(stored["date"], latest["date"])
        if latest["days"] is None:
            self.assertIsNone(stored["days"])
        else:
            self.assertAlmostEqual(stored["days"], latest["days"], places=4)
        self.assertTrue(
            any(
                p["state"] == "contracting" and "2022-01-01" <= p["date"] <= "2023-12-31"
                for p in series
            )
        )
        self.assertTrue(all(p["days"] is None or p["days"] > 0 for p in series))

    def test_deflators_are_public_fred_series(self):
        gdp = self.doc["deflators"]["gdp"]
        cpi = self.doc["deflators"]["cpi"]
        self.assertEqual(gdp["fred_id"], "GDP")
        self.assertEqual(cpi["fred_id"], "CPIAUCSL")
        self.assertLess(gdp["start"], "1948-01-01")
        self.assertLess(cpi["start"], "1948-01-01")
        self.assertGreater(gdp["points"][-1][1], 1.5e13)
        self.assertLess(gdp["points"][-1][1], 8e13)
        self.assertGreater(cpi["points"][-1][1], 200)
        self.assertLess(cpi["points"][-1][1], 500)
        # A monthly CPI change has to survive in the file. Integer rounding would
        # pin many recent months to the same point.
        recent = [row[1] for row in cpi["points"][-6:]]
        self.assertGreater(len(set(recent)), 1)
        self.assertIn("normalization", self.doc["bailout"])
        self.assertIn("axiom", self.doc["bailout"])

    def test_latest_cpi_half_life_is_a_human_span(self):
        series = trailing_cpi_half_life(self.doc["deflators"]["cpi"]["points"])
        latest = next(row for row in reversed(series) if row["years"] is not None)
        self.assertGreater(latest["years"], 5)
        self.assertLess(latest["years"], 80)


if __name__ == "__main__":
    unittest.main()
