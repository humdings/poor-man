"""Hand-worked tests for the Poor Man's Bailout day count.

The spec, written out so the implementation has to match it:

    s = t shifted back by the window (calendar months or years, day clamped)
    N = number of calendar days from s to t
    M is the money level, forward-filled: the last observation on or before the day
    C is the bitcoin market cap, same matching rule

    trailing:    g = (M(t) - M(s)) / N
    cagr:        g = M(t) * ((M(t) / M(s)) ** (1/N) - 1)
                 when M(s) > 0 and M(t) > 0
    regression:  g = OLS slope of the daily forward-filled level on time,
                 in dollars per day, over the days s through t inclusive

    d = C(t) / g when g > 0
    when g <= 0 the point is "contracting" and d is None
    a day count is never negative, never zero from a non-positive pace,
    and never infinite
"""

import json
import math
import subprocess
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from metric import (  # noqa: E402
    annualized_from_cumulative,
    compute_bailout,
    effective_gap,
    half_life_with_gap,
    half_life_years,
    perry_table,
    regression_slope,
    shift_months,
    to_chart_data,
    trailing_cpi_half_life,
)


def D(iso):
    y, m, d = (int(p) for p in iso.split("-"))
    return date(y, m, d)


def pts(*rows):
    return [(D(a), b) for a, b in rows]


class ShiftMonthsTests(unittest.TestCase):
    def test_clamps_to_month_end(self):
        self.assertEqual(shift_months(D("2024-03-31"), -1), D("2024-02-29"))
        self.assertEqual(shift_months(D("2023-03-31"), -1), D("2023-02-28"))

    def test_leap_day_forward(self):
        self.assertEqual(shift_months(D("2020-02-29"), 12), D("2021-02-28"))

    def test_full_years_and_across_year_boundary(self):
        self.assertEqual(shift_months(D("2024-01-31"), -12), D("2023-01-31"))
        self.assertEqual(shift_months(D("2024-05-15"), -5), D("2023-12-15"))
        self.assertEqual(shift_months(D("2019-06-01"), -60), D("2014-06-01"))


class RegressionSlopeTests(unittest.TestCase):
    def test_exact_line(self):
        self.assertEqual(regression_slope([0, 10, 20]), 10)

    def test_exact_decline(self):
        self.assertEqual(regression_slope([20, 10, 0]), -10)

    def test_window_not_starting_at_zero(self):
        # Levels 100, 100, 110, 120. The last three days are a line of slope 10.
        self.assertAlmostEqual(regression_slope([100, 100, 110, 120], start=1), 10)

    def test_flat_is_zero(self):
        self.assertEqual(regression_slope([5, 5, 5, 5]), 0)


class TrailingHandWorkedTests(unittest.TestCase):
    def test_leap_year_window(self):
        # 2020-01-01 -> 2021-01-01 is 366 days. Level 1000 -> 1460.
        # Market cap on the end date is 100.
        # d = 100 / ((1460-1000)/366) = 100 * 366 / 460.
        money = pts(("2020-01-01", 1000), ("2021-01-01", 1460))
        btc = pts(("2021-01-01", 100))
        out = compute_bailout(money, btc, 12, "month", "trailing")
        self.assertGreaterEqual(len(out), 1)
        last = out[-1]
        self.assertEqual(last["date"], "2021-01-01")
        self.assertEqual(last["state"], "expanding")
        self.assertAlmostEqual(last["days"], 100 * 366 / 460, places=9)
        self.assertAlmostEqual(last["growth_per_day"], 460 / 366, places=9)
        self.assertEqual(last["level"], 1460)
        self.assertEqual(last["level_start"], 1000)
        self.assertEqual(last["mcap"], 100)

    def test_contraction_is_not_a_negative_day_count(self):
        money = pts(("2020-01-01", 1000), ("2021-01-01", 800))
        btc = pts(("2021-01-01", 100))
        last = compute_bailout(money, btc, 12, "month", "trailing")[-1]
        self.assertEqual(last["state"], "contracting")
        self.assertIsNone(last["days"])
        self.assertLess(last["growth_per_day"], 0)

    def test_flat_level_is_contracting_not_infinite(self):
        money = pts(("2020-01-01", 1000), ("2021-01-01", 1000))
        btc = pts(("2021-01-01", 100))
        last = compute_bailout(money, btc, 12, "month", "trailing")[-1]
        self.assertEqual(last["state"], "contracting")
        self.assertIsNone(last["days"])
        self.assertEqual(last["growth_per_day"], 0)
        self.assertFalse(math.isinf(last["growth_per_day"]))

    def test_insufficient_history(self):
        # One month of history cannot fill a 12-month window.
        money = pts(("2020-06-01", 1000), ("2021-01-01", 1100))
        btc = pts(("2021-01-01", 100))
        last = compute_bailout(money, btc, 12, "month", "trailing")[-1]
        self.assertEqual(last["date"], "2021-01-01")
        self.assertEqual(last["state"], "insufficient")
        self.assertIsNone(last["days"])

    def test_forward_fill_and_calendar_window(self):
        # Observations on the 1st. On the 10th the February print is in effect,
        # and the lookback (one month earlier) still carries January.
        # Jan 10 -> Feb 10 is 31 days. 1600 - 1000 = 600. Cap is 200.
        # d = 200 * 31 / 600.
        money = pts(("2020-01-01", 1000), ("2020-02-01", 1600))
        btc = pts(("2020-02-10", 200))
        last = compute_bailout(money, btc, 1, "month", "trailing")[-1]
        self.assertEqual(last["date"], "2020-02-10")
        self.assertEqual(last["level"], 1600)
        self.assertEqual(last["level_start"], 1000)
        self.assertEqual(last["state"], "expanding")
        self.assertAlmostEqual(last["days"], 200 * 31 / 600, places=9)

    def test_btc_uses_latest_print_on_or_before_the_day(self):
        # Money is carried to the later bitcoin date. Bitcoin on Jan 10 is
        # matched to itself; there is no print on Jan 11, so Jan 11 keeps 50
        # only if we evaluated it. The series ends on the later of the two
        # last prints, which here is the money date Jan 20, and the cap is
        # the Jan 10 print carried forward.
        money = pts(("2019-01-01", 100), ("2020-01-20", 500))
        btc = pts(("2020-01-10", 80))
        out = compute_bailout(money, btc, 12, "month", "trailing")
        by_date = {p["date"]: p for p in out}
        self.assertIn("2020-01-10", by_date)
        self.assertEqual(by_date["2020-01-10"]["mcap"], 80)
        self.assertEqual(out[-1]["date"], "2020-01-20")
        self.assertEqual(out[-1]["mcap"], 80)
        self.assertEqual(out[-1]["level"], 500)

    def test_year_window_uses_calendar_years(self):
        money = pts(("2015-06-01", 1000), ("2020-06-01", 2000))
        btc = pts(("2020-06-01", 365))
        last = compute_bailout(money, btc, 5, "year", "trailing")[-1]
        # 2015-06-01 to 2020-06-01 is 1827 days (2016 and 2020 are leap years).
        self.assertEqual((D("2020-06-01") - D("2015-06-01")).days, 1827)
        self.assertAlmostEqual(last["days"], 365 * 1827 / 1000, places=9)
        self.assertEqual(last["state"], "expanding")


class CagrTests(unittest.TestCase):
    def test_hand_worked_compound_pace(self):
        # 100 -> 121 over the 365 days from 2019-01-01 to 2020-01-01.
        # g = 121 * (1.21 ** (1/365) - 1)
        # cap = 50.
        money = pts(("2019-01-01", 100), ("2020-01-01", 121))
        btc = pts(("2020-01-01", 50))
        n = (D("2020-01-01") - D("2019-01-01")).days
        self.assertEqual(n, 365)
        g = 121 * (1.21 ** (1 / n) - 1)
        last = compute_bailout(money, btc, 12, "month", "cagr")[-1]
        self.assertEqual(last["state"], "expanding")
        self.assertAlmostEqual(last["growth_per_day"], g, places=12)
        self.assertAlmostEqual(last["days"], 50 / g, places=9)

    def test_cagr_decline_is_contracting(self):
        money = pts(("2019-01-01", 121), ("2020-01-01", 100))
        btc = pts(("2020-01-01", 50))
        last = compute_bailout(money, btc, 12, "month", "cagr")[-1]
        self.assertEqual(last["state"], "contracting")
        self.assertIsNone(last["days"])


class RegressionMethodTests(unittest.TestCase):
    def test_daily_line_over_a_short_explicit_slope(self):
        # Three daily prints, perfectly linear, and the window is checked
        # through regression_slope. The series method is covered by parity
        # plus a case whose slope we recompute independently below.
        self.assertEqual(regression_slope([0, 10, 20]), 10)

    def test_series_regression_matches_independent_fit(self):
        money = pts(
            ("2020-01-01", 1000),
            ("2020-02-01", 1100),
            ("2020-03-01", 1300),
        )
        btc = pts(("2020-03-01", 90))
        last = compute_bailout(money, btc, 2, "month", "regression")[-1]
        # Independent ordinary-least-squares fit, not the helper under test.
        levels = []
        cur = None
        prints = {D("2020-01-01"): 1000, D("2020-02-01"): 1100, D("2020-03-01"): 1300}
        day = D("2020-01-01")
        while day <= D("2020-03-01"):
            if day in prints:
                cur = prints[day]
            levels.append(cur)
            day = date.fromordinal(day.toordinal() + 1)
        n = len(levels)
        sum_t = (n - 1) * n / 2
        sum_t2 = (n - 1) * n * (2 * n - 1) / 6
        sum_y = sum(levels)
        sum_ty = sum(i * y for i, y in enumerate(levels))
        slope = (n * sum_ty - sum_t * sum_y) / (n * sum_t2 - sum_t ** 2)
        self.assertAlmostEqual(last["growth_per_day"], slope, places=9)
        self.assertEqual(last["state"], "expanding")
        self.assertAlmostEqual(last["days"], 90 / slope, places=8)
        self.assertGreater(last["days"], 0)


class ChartGapTests(unittest.TestCase):
    def test_contraction_becomes_a_gap_and_never_a_negative_value(self):
        points = [
            {"date": "2020-01-01", "state": "expanding", "days": 10},
            {"date": "2020-01-02", "state": "expanding", "days": 12},
            {"date": "2020-01-03", "state": "contracting", "days": None},
            {"date": "2020-01-04", "state": "contracting", "days": None},
            {"date": "2020-01-05", "state": "expanding", "days": 9},
        ]
        chart = to_chart_data(points)
        values = [row.get("value") for row in chart]
        self.assertEqual(values, [10, 12, None, 9])
        self.assertTrue(all(v is None or v > 0 for v in values))
        self.assertNotIn(float("inf"), values)

    def test_full_series_never_emits_nonpositive_days(self):
        # Rise, then a long decline, then a rise. Every plotted day count stays positive.
        money = pts(
            ("2019-01-01", 1000),
            ("2020-01-01", 1500),
            ("2021-01-01", 900),
            ("2022-01-01", 1600),
        )
        btc = pts(("2020-06-01", 40), ("2022-01-01", 80))
        out = compute_bailout(money, btc, 12, "month", "trailing")
        self.assertTrue(any(p["state"] == "contracting" for p in out))
        for p in out:
            if p["state"] == "expanding":
                self.assertIsNotNone(p["days"])
                self.assertGreater(p["days"], 0)
                self.assertTrue(math.isfinite(p["days"]))
            else:
                self.assertIsNone(p["days"])


class HalfLifeTests(unittest.TestCase):
    """Years for prices growing at a constant rate to double.

    half-life = ln(2) / ln(1 + rate). Worked by hand to one decimal:
    ln(2) / ln(1.02) = 35.0028… → 35.0 years
    ln(2) / ln(1.07) = 10.2448… → 10.2 years
    A rate at or below zero does not halve purchasing power.
    """

    def test_two_percent_is_35_years(self):
        self.assertEqual(round(half_life_years(0.02), 1), 35.0)

    def test_seven_percent_is_10_2_years(self):
        self.assertEqual(round(half_life_years(0.07), 1), 10.2)

    def test_non_positive_rates_are_a_gap(self):
        self.assertIsNone(half_life_years(0))
        self.assertIsNone(half_life_years(-0.01))
        self.assertIsNone(half_life_years(float("-inf")))

    def test_trailing_cpi_uses_the_print_twelve_months_earlier(self):
        series = trailing_cpi_half_life([
            ("2020-01-01", 100.0),
            ("2020-06-01", 110.0),
            ("2021-01-01", 102.0),
        ])
        self.assertEqual([row["date"] for row in series], ["2021-01-01"])
        self.assertAlmostEqual(series[0]["rate"], 0.02)
        self.assertEqual(round(series[0]["years"], 1), 35.0)

    def test_a_decline_is_a_gap_on_the_chart(self):
        series = trailing_cpi_half_life([
            ("2020-01-01", 100.0),
            ("2021-01-01", 102.0),
            ("2022-01-01", 101.0),
        ])
        self.assertEqual(round(series[0]["years"], 1), 35.0)
        self.assertLess(series[1]["rate"], 0)
        self.assertIsNone(series[1]["years"])
        rows = to_chart_data(series, "years")
        self.assertAlmostEqual(rows[0]["value"], series[0]["years"])
        self.assertEqual(rows[1], {"time": "2022-01-01"})
        self.assertNotIn("value", rows[1])

    def test_the_page_states_the_formula_and_the_two_percent_value(self):
        page = (ROOT / "index.html").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for text in (page, readme):
            self.assertIn("ln(2)", text)
            self.assertIn("35.0", text)
            self.assertIn("10.2", text)
            self.assertIn("CPIAUCSL", text)
        self.assertIn('id="chart-halflife"', page)

    def test_perry_gaps_are_the_hand_checked_values(self):
        """Annualize Jan 2000–June 2026 cumulative changes over 26.5 years.

        Worked from the published cumulatives, not from the helper's output:

            overall  (1.964) ** (1/26.5) - 1 = 0.025798223883
            hospital (3.911) ** (1/26.5) - 1 = 0.052811169022
            gap = (0.052811169022 - 0.025798223883) * 100 = 2.70129451 pp

        The same subtraction, rounded to 4 decimal percentage points:
        tuition 1.6504, textbooks 1.4085, day care 1.1276, medical 0.9462,
        wages 0.7085, housing 0.3563, food 0.2317.
        A 2% rate plus the hospital gap halves in 15.0877 years.
        Wage growth's own half-life is 21.4236 years.
        """
        span = 26.5
        overall = (1.964) ** (1 / span) - 1
        hospital = (3.911) ** (1 / span) - 1
        self.assertAlmostEqual(overall, 0.025798223883, places=9)
        self.assertAlmostEqual(hospital, 0.052811169022, places=9)
        self.assertAlmostEqual((hospital - overall) * 100, 2.70129451, places=6)
        self.assertAlmostEqual(annualized_from_cumulative(0.964), overall, places=12)
        self.assertAlmostEqual(annualized_from_cumulative(2.911), hospital, places=12)

        expected_pp = {
            "hospital": 2.7013,
            "tuition": 1.6504,
            "textbooks": 1.4085,
            "daycare": 1.1276,
            "medical": 0.9462,
            "wages": 0.7085,
            "housing": 0.3563,
            "food": 0.2317,
        }
        rows = {row["key"]: row for row in perry_table()}
        self.assertAlmostEqual(rows["overall"]["gap"], 0.0, places=12)
        self.assertEqual(rows["overall"]["role"], "baseline")
        self.assertEqual(rows["wages"]["role"], "reference")
        for key, gap_pp in expected_pp.items():
            self.assertAlmostEqual(rows[key]["gap"] * 100, gap_pp, places=4)
            self.assertAlmostEqual(
                (1 + rows[key]["annualized"]) ** span - 1,
                rows[key]["cumulative"],
                places=9,
            )
            if key != "wages":
                self.assertEqual(rows[key]["role"], "preset")
        self.assertAlmostEqual(half_life_with_gap(0.02, rows["hospital"]["gap"]), 15.0877, places=4)
        self.assertAlmostEqual(half_life_years(rows["wages"]["annualized"]), 21.4236, places=4)
        self.assertIsNone(half_life_with_gap(0.02, -0.02))
        self.assertIsNone(half_life_with_gap(0.02, -0.03))
        self.assertEqual(round(half_life_with_gap(0.02, 0.0), 1), 35.0)

    def test_the_adjuster_is_labeled_as_an_assumption(self):
        page = (ROOT / "index.html").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for text in (page, readme):
            self.assertIn("Bullshit adjuster", text)
            self.assertIn("illustrative assumptions, not measured real inflation", text)
            self.assertIn("Mark J. Perry, BLS data", text)
            self.assertIn("Jan. 2000-June 2026", text)
        self.assertIn('id="bs-gap"', page)
        self.assertIn('id="bs-gap-num"', page)
        self.assertNotIn("aei.org", page)
        self.assertNotIn("<img", page[page.find("Bullshit adjuster"):page.find("Years at a steady")])

    def test_the_gap_applies_immediately(self):
        """A 5 percentage point gap changes the half-life with no checkbox."""
        rate = 0.037
        applied = effective_gap(0.05)
        self.assertEqual(applied, 0.05)
        self.assertEqual(effective_gap(None), 0.0)
        self.assertEqual(effective_gap(float("nan")), 0.0)
        moved = half_life_with_gap(rate, applied)
        self.assertAlmostEqual(moved, half_life_years(rate + 0.05), places=9)
        self.assertNotEqual(round(moved, 4), round(half_life_years(rate), 4))

    def test_the_disclaimer_sits_under_the_slider(self):
        page = (ROOT / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "js" / "app.js").read_text(encoding="utf-8")
        adjuster = page[page.find("Bullshit adjuster"):page.find('id="bs-presets"')]
        self.assertLess(adjuster.index('id="bs-gap"'), adjuster.index("bs-caption"))
        self.assertIn(
            '<p class="bs-caption">In the real world, you can\'t turn this bullshit off.</p>',
            adjuster,
        )
        self.assertNotIn("Turn off the bullshit", page)
        self.assertNotIn('id="honest"', page)
        self.assertNotIn('id="ack"', page)
        self.assertNotIn("I acknowledge that in the real world", page)
        self.assertNotIn("Adjusting...", page)
        self.assertNotIn("dig to the bottom of the page", page)
        self.assertNotIn("readGate", app)
        self.assertNotIn('q.set("honest"', app)
        self.assertNotIn('q.set("ack"', app)
        self.assertIn("Pmb.effectiveGap(state.gap / 100)", app)
        self.assertIn('q.set("gap"', app)

    def test_javascript_matches(self):
        code = (
            "const Pmb = require(" + json.dumps(str(ROOT / "js" / "metric.js")) + ");\n"
            "const points = ["
            '["2020-01-01", 100], ["2021-01-01", 102], ["2022-01-01", 101]'
            "];\n"
            "console.log(JSON.stringify({"
            "two: Pmb.halfLifeYears(0.02),"
            "seven: Pmb.halfLifeYears(0.07),"
            "zero: Pmb.halfLifeYears(0),"
            "neg: Pmb.halfLifeYears(-0.02),"
            "series: Pmb.trailingCpiHalfLife(points),"
            "perry: Pmb.perryTable(),"
            "bumped: Pmb.halfLifeWithGap(0.02, Pmb.perryTable().filter(function (row) { return row.key === 'hospital'; })[0].gap),"
            "applied: Pmb.effectiveGap(0.05),"
            "missing: Pmb.effectiveGap(null),"
            "bad: Pmb.effectiveGap(NaN)"
            "}));"
        )
        raw = subprocess.check_output(["node", "-e", code], text=True)
        js = json.loads(raw)
        self.assertEqual(round(js["two"], 1), 35.0)
        self.assertEqual(round(js["seven"], 1), 10.2)
        self.assertIsNone(js["zero"])
        self.assertIsNone(js["neg"])
        py = trailing_cpi_half_life([
            ("2020-01-01", 100.0),
            ("2021-01-01", 102.0),
            ("2022-01-01", 101.0),
        ])
        self.assertEqual(len(js["series"]), len(py))
        for left, right in zip(js["series"], py):
            self.assertEqual(left["date"], right["date"])
            if right["years"] is None:
                self.assertIsNone(left["years"])
            else:
                self.assertAlmostEqual(left["years"], right["years"], places=9)
        py_rows = perry_table()
        self.assertEqual(len(js["perry"]), len(py_rows))
        for left, right in zip(js["perry"], py_rows):
            self.assertEqual(left["key"], right["key"])
            self.assertEqual(left["role"], right["role"])
            self.assertAlmostEqual(left["gap"], right["gap"], places=9)
            self.assertAlmostEqual(left["annualized"], right["annualized"], places=9)
        self.assertAlmostEqual(js["bumped"], half_life_with_gap(0.02, py_rows[1]["gap"]), places=9)
        self.assertAlmostEqual(js["applied"], effective_gap(0.05), places=9)
        self.assertEqual(js["missing"], 0)
        self.assertEqual(js["bad"], 0)


class JavascriptParityTests(unittest.TestCase):
    def test_node_matches_python(self):
        cases = [
            {
                "money": [["2020-01-01", 1000], ["2021-01-01", 1460]],
                "btc": [["2021-01-01", 100]],
                "amount": 12,
                "unit": "month",
                "method": "trailing",
            },
            {
                "money": [["2020-01-01", 1000], ["2021-01-01", 800]],
                "btc": [["2021-01-01", 100]],
                "amount": 12,
                "unit": "month",
                "method": "trailing",
            },
            {
                "money": [["2019-01-01", 100], ["2020-01-01", 121]],
                "btc": [["2020-01-01", 50]],
                "amount": 12,
                "unit": "month",
                "method": "cagr",
            },
            {
                "money": [["2020-01-01", 1000], ["2020-02-01", 1600]],
                "btc": [["2020-02-10", 200]],
                "amount": 1,
                "unit": "month",
                "method": "trailing",
            },
            {
                "money": [["2019-01-01", 1000], ["2019-06-01", 1200], ["2020-01-01", 1500]],
                "btc": [["2020-01-01", 100]],
                "amount": 12,
                "unit": "month",
                "method": "regression",
            },
        ]
        runner = ROOT / "tests" / "parity.mjs"
        for case in cases:
            with self.subTest(case=case["method"]):
                raw = subprocess.check_output(
                    ["node", str(runner), json.dumps(case)],
                    text=True,
                )
                js = json.loads(raw)
                money = pts(*case["money"])
                btc = pts(*case["btc"])
                py_last = compute_bailout(
                    money, btc, case["amount"], case["unit"], case["method"]
                )[-1]
                self.assertEqual(js["state"], py_last["state"])
                self.assertEqual(js["date"], py_last["date"])
                if py_last["days"] is None:
                    self.assertIsNone(js["days"])
                else:
                    self.assertAlmostEqual(js["days"], py_last["days"], places=6)


if __name__ == "__main__":
    unittest.main()
