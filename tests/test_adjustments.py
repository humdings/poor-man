"""Hand-worked tests for the split, the excess-growth adjustment, and smoothing.

Decomposition, sequential and exact:

    d = price × supply / growth
    money moves first, price and supply held at the reference
    price moves next, supply still held
    supply moves last
    from_money + from_price + from_supply = d(end) − d(start)

    fixed_price_days = price(start) × supply(end) / growth(end)
    fixed_units_days = price(end) × supply(start) / growth(end)

Normalization. g is the unadjusted pace. D is the deflator.

    trailing and no smoothing:
        g* = g − M(start) × (D(end) − D(start)) / (N × D(start))
    cagr:
        g* = M(end) × (r(M) − r(D))
        r(X) = (X(end) / X(start))^(1/N) − 1
    regression:
        g* = slope(M) − M(end) × slope(ln D)

    A flat deflator leaves g* = g. Equal percentage growth makes the
    trailing and CAGR excess zero. g* <= 0 is contracting, and the day
    count stays blank.

No smoothing. p is the money print in effect, q the print before it.

    g = (M(p) − M(q)) / days(q, p)

    held until the next print. A lower print is a negative pace and a
    blank day count, not an average that can hide the decrease.
"""

import json
import math
import subprocess
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from metric import compute_bailout, decompose, to_chart_data  # noqa: E402


def D(iso):
    y, m, d = (int(part) for part in iso.split("-"))
    return date(y, m, d)


def pts(*rows):
    return [(D(a), b) for a, b in rows]


class DecompositionTests(unittest.TestCase):
    def test_hand_worked_split_adds_up(self):
        # g 2 → 4, price 10 → 20, supply 5 → 6.
        # d_start = 10*5/2 = 25. d_end = 20*6/4 = 30.
        start = {"growth_per_day": 2, "price": 10, "supply": 5}
        end = {"growth_per_day": 4, "price": 20, "supply": 6}
        split = decompose(start, end)
        self.assertAlmostEqual(split["days_start"], 25, places=9)
        self.assertAlmostEqual(split["days_end"], 30, places=9)
        self.assertAlmostEqual(split["from_money"], 10 * 5 / 4 - 25, places=9)
        self.assertAlmostEqual(split["from_price"], 20 * 5 / 4 - 10 * 5 / 4, places=9)
        self.assertAlmostEqual(split["from_supply"], 30 - 20 * 5 / 4, places=9)
        self.assertAlmostEqual(
            split["from_money"] + split["from_price"] + split["from_supply"],
            split["change"],
            places=9,
        )
        self.assertAlmostEqual(split["change"], 5, places=9)
        self.assertAlmostEqual(split["fixed_price_days"], 10 * 6 / 4, places=9)
        self.assertAlmostEqual(split["fixed_units_days"], 20 * 5 / 4, places=9)

    def test_split_from_a_series_matches_the_same_arithmetic(self):
        # 1-month window. 2019-02-01 looks back to Jan 1 (31 days).
        # 2019-03-01 looks back to Feb 1 (28 days).
        money = pts(("2019-01-01", 1000), ("2019-02-01", 1100), ("2019-03-01", 1400))
        btc = [
            (D("2019-01-01"), 100, 10),
            (D("2019-02-01"), 100, 10),
            (D("2019-03-01"), 240, 20),
        ]
        out = compute_bailout(money, btc, 1, "month", "trailing")
        by_date = {row["date"]: row for row in out}
        feb = by_date["2019-02-01"]
        mar = by_date["2019-03-01"]
        self.assertEqual(mar["ref_date"], "2019-02-01")
        self.assertAlmostEqual(feb["growth_per_day"], 100 / 31, places=9)
        self.assertAlmostEqual(mar["growth_per_day"], 300 / 28, places=9)
        self.assertAlmostEqual(mar["days"], 240 * 28 / 300, places=9)
        self.assertAlmostEqual(feb["supply"], 10, places=9)
        self.assertAlmostEqual(mar["supply"], 12, places=9)
        split = decompose(feb, mar)
        g1 = 300 / 28
        self.assertAlmostEqual(split["from_money"], 100 / g1 - 31, places=9)
        self.assertAlmostEqual(split["from_price"], 100 / g1, places=9)
        self.assertAlmostEqual(split["from_supply"], 240 / g1 - 200 / g1, places=9)
        self.assertAlmostEqual(
            split["from_money"] + split["from_price"] + split["from_supply"],
            split["days_end"] - split["days_start"],
            places=9,
        )
        self.assertAlmostEqual(mar["fixed_price_days"], 10 * 12 / g1, places=9)
        self.assertAlmostEqual(mar["fixed_units_days"], 20 * 10 / g1, places=9)
        self.assertAlmostEqual(split["fixed_price_days"], mar["fixed_price_days"], places=9)

    def test_no_split_when_the_pace_is_not_positive(self):
        self.assertIsNone(
            decompose(
                {"growth_per_day": -1, "price": 10, "supply": 5},
                {"growth_per_day": 4, "price": 20, "supply": 6},
            )
        )


class NormalizationTests(unittest.TestCase):
    def test_trailing_excess_over_a_rising_deflator(self):
        # 1000 → 1500 and 100 → 110 over the 365 days from 2019-01-01.
        # g* = 500/365 − 1000 × 10/(365 × 100) = 400/365.
        # cap 80, so days = 80 × 365 / 400 = 73.
        money = pts(("2019-01-01", 1000), ("2020-01-01", 1500))
        btc = pts(("2020-01-01", 80))
        deflator = pts(("2019-01-01", 100), ("2020-01-01", 110))
        last = compute_bailout(money, btc, 12, "month", "trailing", deflator)[-1]
        self.assertEqual(last["state"], "expanding")
        self.assertAlmostEqual(last["growth_unadjusted"], 500 / 365, places=9)
        self.assertAlmostEqual(last["growth_per_day"], 400 / 365, places=9)
        self.assertAlmostEqual(last["days"], 73, places=9)

    def test_equal_percentage_growth_is_not_excess(self):
        money = pts(("2019-01-01", 1000), ("2020-01-01", 1100))
        btc = pts(("2020-01-01", 80))
        deflator = pts(("2019-01-01", 100), ("2020-01-01", 110))
        last = compute_bailout(money, btc, 12, "month", "trailing", deflator)[-1]
        self.assertEqual(last["state"], "contracting")
        self.assertIsNone(last["days"])
        self.assertAlmostEqual(last["growth_per_day"], 0, places=9)

    def test_flat_deflator_leaves_the_trailing_pace_unchanged(self):
        money = pts(("2020-01-01", 1000), ("2021-01-01", 1460))
        btc = pts(("2021-01-01", 100))
        flat = pts(("2020-01-01", 50), ("2021-01-01", 50))
        plain = compute_bailout(money, btc, 12, "month", "trailing")[-1]
        adjusted = compute_bailout(money, btc, 12, "month", "trailing", flat)[-1]
        self.assertAlmostEqual(adjusted["days"], plain["days"], places=9)
        self.assertAlmostEqual(adjusted["days"], 100 * 366 / 460, places=9)

    def test_trailing_uses_the_deflator_endpoints_not_a_midpoint_spike(self):
        money = pts(("2019-01-01", 1000), ("2020-01-01", 1500))
        btc = pts(("2020-01-01", 80))
        deflator = pts(
            ("2019-01-01", 100),
            ("2019-07-01", 999),
            ("2020-01-01", 110),
        )
        last = compute_bailout(money, btc, 12, "month", "trailing", deflator)[-1]
        self.assertAlmostEqual(last["days"], 73, places=9)

    def test_cagr_excess(self):
        # 100 → 121 and 100 → 110 over 365 days. Cap 50.
        money = pts(("2019-01-01", 100), ("2020-01-01", 121))
        btc = pts(("2020-01-01", 50))
        deflator = pts(("2019-01-01", 100), ("2020-01-01", 110))
        n = 365
        r_m = 1.21 ** (1 / n) - 1
        r_d = 1.10 ** (1 / n) - 1
        g = 121 * (r_m - r_d)
        last = compute_bailout(money, btc, 12, "month", "cagr", deflator)[-1]
        self.assertAlmostEqual(last["growth_per_day"], g, places=12)
        self.assertAlmostEqual(last["days"], 50 / g, places=8)

    def test_regression_subtracts_the_log_slope_at_todays_level(self):
        # Money rises by 20 a day. ln(deflator) rises by 0.01 a day.
        # 2020-01-01 through 2020-02-01 is 32 points, i = 0..31.
        # Ending money level = 1620. g* = 20 − 1620 × 0.01 = 3.8. Cap 38 → 10 days.
        start = D("2020-01-01")
        money = [(start + timedelta(days=i), 1000 + 20 * i) for i in range(32)]
        deflator = [(start + timedelta(days=i), math.exp(0.01 * i)) for i in range(32)]
        btc = [(start + timedelta(days=31), 38)]
        last = compute_bailout(money, btc, 1, "month", "regression", deflator)[-1]
        self.assertEqual(last["date"], "2020-02-01")
        self.assertAlmostEqual(last["growth_unadjusted"], 20, places=8)
        self.assertAlmostEqual(last["growth_per_day"], 3.8, places=6)
        self.assertAlmostEqual(last["days"], 10, places=6)

    def test_flat_deflator_leaves_the_regression_slope_unchanged(self):
        start = D("2020-01-01")
        money = [(start + timedelta(days=i), 1000 + 20 * i) for i in range(32)]
        deflator = [(start, 100), (start + timedelta(days=31), 100)]
        btc = [(start + timedelta(days=31), 38)]
        last = compute_bailout(money, btc, 1, "month", "regression", deflator)[-1]
        self.assertAlmostEqual(last["growth_per_day"], 20, places=8)
        self.assertAlmostEqual(last["days"], 38 / 20, places=8)

    def test_missing_deflator_history_does_not_silently_use_the_raw_pace(self):
        money = pts(("2019-01-01", 1000), ("2020-01-01", 1500))
        btc = pts(("2020-01-01", 80))
        deflator = pts(("2020-06-01", 100), ("2020-12-01", 110))
        last = compute_bailout(money, btc, 12, "month", "trailing", deflator)[-1]
        self.assertEqual(last["state"], "insufficient")
        self.assertIsNone(last["days"])


class SmoothingTests(unittest.TestCase):
    def test_no_smoothing_is_the_raw_print_to_print_change(self):
        # 2020-01-01 → 2021-01-01 is 366 days and +460.
        # The pace is held after that print. Cap 100 → days = 100 × 366 / 460.
        money = pts(("2020-01-01", 1000), ("2021-01-01", 1460), ("2022-01-01", 1360))
        btc = pts(("2021-01-01", 100), ("2021-06-01", 100))
        out = compute_bailout(money, btc, 0, "month", "trailing")
        by_date = {row["date"]: row for row in out}
        held = by_date["2021-06-01"]
        self.assertEqual(held["state"], "expanding")
        self.assertAlmostEqual(held["growth_per_day"], 460 / 366, places=9)
        self.assertAlmostEqual(held["days"], 100 * 366 / 460, places=9)
        self.assertEqual(held["level"], 1460)
        self.assertEqual(held["level_start"], 1000)

    def test_a_decrease_is_kept_when_smoothing_is_off(self):
        # The April print falls from 2000 to 1900. A 12-month trailing window
        # still looks back to a much lower level and stays positive. No
        # smoothing reports the decrease itself.
        money = pts(
            ("2018-01-01", 800),
            ("2019-01-01", 1000),
            ("2020-01-01", 2000),
            ("2020-04-01", 1900),
            ("2021-01-01", 2500),
        )
        btc = pts(("2020-04-01", 50), ("2021-01-01", 80))
        raw = compute_bailout(money, btc, 0, "month", "trailing")
        smoothed = compute_bailout(money, btc, 12, "month", "trailing")
        raw_dip = next(row for row in raw if row["date"] == "2020-04-01")
        smooth_dip = next(row for row in smoothed if row["date"] == "2020-04-01")
        self.assertEqual(raw_dip["state"], "contracting")
        self.assertLess(raw_dip["growth_per_day"], 0)
        self.assertIsNone(raw_dip["days"])
        self.assertAlmostEqual(raw_dip["growth_per_day"], (1900 - 2000) / (D("2020-04-01") - D("2020-01-01")).days, places=9)
        self.assertEqual(smooth_dip["state"], "expanding")
        self.assertGreater(smooth_dip["days"], 0)

        pace = [row.get("value") for row in to_chart_data(raw, "growth_per_day")]
        days = [row.get("value") for row in to_chart_data(raw)]
        self.assertTrue(any(value is not None and value < 0 for value in pace))
        self.assertTrue(all(value is None or value > 0 for value in days))

    def test_first_print_has_no_unsmoothed_pace(self):
        money = pts(("2020-01-01", 1000), ("2021-01-01", 1100))
        btc = pts(("2020-06-01", 40))
        out = compute_bailout(money, btc, 0, "month", "trailing")
        first = next(row for row in out if row["date"] == "2020-06-01")
        self.assertEqual(first["state"], "insufficient")
        self.assertIsNone(first["days"])


class JavascriptAdjustmentParityTests(unittest.TestCase):
    def test_node_matches_python_on_the_new_paths(self):
        cases = [
            {
                "money": [["2019-01-01", 1000], ["2020-01-01", 1500]],
                "btc": [["2020-01-01", 80, 8]],
                "deflator": [["2019-01-01", 100], ["2020-01-01", 110]],
                "amount": 12,
                "unit": "month",
                "method": "trailing",
            },
            {
                "money": [["2019-01-01", 100], ["2020-01-01", 121]],
                "btc": [["2020-01-01", 50, 5]],
                "deflator": [["2019-01-01", 100], ["2020-01-01", 110]],
                "amount": 12,
                "unit": "month",
                "method": "cagr",
            },
            {
                "money": [["2020-01-01", 1000], ["2021-01-01", 1460], ["2022-01-01", 1000]],
                "btc": [["2021-01-01", 100, 10], ["2022-01-01", 120, 12]],
                "amount": 0,
                "unit": "month",
                "method": "trailing",
            },
            {
                "money": [["2019-01-01", 1000], ["2019-02-01", 1100], ["2019-03-01", 1400]],
                "btc": [["2019-01-01", 100, 10], ["2019-02-01", 100, 10], ["2019-03-01", 240, 20]],
                "amount": 1,
                "unit": "month",
                "method": "trailing",
            },
        ]
        runner = ROOT / "tests" / "parity.mjs"
        for case in cases:
            with self.subTest(method=case["method"], amount=case["amount"]):
                raw = subprocess.check_output(
                    ["node", str(runner), json.dumps(case)],
                    text=True,
                )
                js = json.loads(raw)
                money = [(D(row[0]), row[1]) for row in case["money"]]
                btc = [(D(row[0]), row[1], row[2]) for row in case["btc"]]
                deflator = None
                if case.get("deflator"):
                    deflator = [(D(row[0]), row[1]) for row in case["deflator"]]
                series = compute_bailout(
                    money, btc, case["amount"], case["unit"], case["method"], deflator
                )
                py_last = series[-1]
                self.assertEqual(js["state"], py_last["state"])
                self.assertEqual(js["date"], py_last["date"])
                if py_last["days"] is None:
                    self.assertIsNone(js["days"])
                else:
                    self.assertAlmostEqual(js["days"], py_last["days"], places=6)
                if py_last["growth_per_day"] is None:
                    self.assertIsNone(js["growth"])
                else:
                    self.assertAlmostEqual(js["growth"], py_last["growth_per_day"], places=6)
                ref = next((row for row in series if row["date"] == py_last["ref_date"]), None)
                py_split = decompose(ref, py_last) if ref else None
                if py_split is None:
                    self.assertIsNone(js["split"])
                else:
                    self.assertAlmostEqual(js["split"]["from_money"], py_split["from_money"], places=6)
                    self.assertAlmostEqual(js["split"]["from_price"], py_split["from_price"], places=6)
                    self.assertAlmostEqual(js["split"]["from_supply"], py_split["from_supply"], places=6)
                    self.assertAlmostEqual(js["split"]["change"], py_split["change"], places=6)
                    self.assertAlmostEqual(
                        js["fixed_price_days"], py_last["fixed_price_days"], places=6
                    )


if __name__ == "__main__":
    unittest.main()
