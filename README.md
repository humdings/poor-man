# Poor Man's Bailout

How many days of money-printing equal the entire bitcoin market cap.

On a date *t*, with a window that starts at *s* and contains *N* calendar days:

```
d(t) = C(t) / g(t)     when g(t) > 0
```

*C(t)* is the bitcoin market cap in dollars. *g(t)* is the average growth per day of the selected money stock, also in dollars. The default is US M2 and a 12-month trailing change:

```
g(t) = (M(t) − M(s)) / N
```

Two other averages are on the page:

- **Regression.** Ordinary least-squares slope of the daily forward-filled level from *s* through *t*.
- **CAGR pace.** `M(t) × ((M(t) / M(s))^(1/N) − 1)`, the compound rate restated as dollars per day at today's level.

When *g(t)* is zero or negative the day count is undefined. The chart leaves a gap. Negative and infinite values are never plotted. That is what a contraction looks like, including M2 in 2022–23 and stretches of quantitative tightening.

The page states the assumptions in force: series, window, averaging method, contraction rule, daily alignment, and units. Those choices are also the query string, so a link is reproducible (`?measure=m2&window=12&unit=m&method=trailing`).

## Series

Levels are stored in dollars. Published units are scaled by the multiplier below.

| Order | Measure | Series | Published unit | Scale | Frequency |
| --- | --- | --- | --- | --- | --- |
| 1, default | US M2 | [FRED M2SL](https://fred.stlouisfed.org/series/M2SL) | billions | × 1e9 | monthly, seasonally adjusted, from 1959 |
| 2 | Monetary base | [FRED BOGMBASE](https://fred.stlouisfed.org/series/BOGMBASE) | billions | × 1e9 | monthly, not seasonally adjusted |
| 3 | Currency in circulation | [FRED MBCURRCIR](https://fred.stlouisfed.org/series/MBCURRCIR) | billions | × 1e9 | monthly, not seasonally adjusted |
| 4 | Public debt | [Debt to the Penny](https://fiscaldata.treasury.gov/datasets/debt-to-the-penny/debt-to-the-penny) `tot_pub_debt_out_amt`, daily from 1993-04-01 | dollars | × 1 | daily |
| 4, earlier history | Public debt | [FRED GFDEBTN](https://fred.stlouisfed.org/series/GFDEBTN) | millions | × 1e6 | quarterly, spliced strictly before the daily file |
| 5, secondary | Fed balance sheet | [FRED WALCL](https://fred.stlouisfed.org/series/WALCL) | millions | × 1e6 | weekly Wednesday level, from 2002-12-18 |

The Fed balance sheet stays last and is left off the comparison strip.

M2 is the seasonally adjusted monthly series only. Weekly not-seasonally-adjusted M2 ([WM2NS](https://fred.stlouisfed.org/series/WM2NS)) is not spliced on, because that would put a seasonal jump at the join.

Currency in circulation is MBCURRCIR, the currency component of the monetary base, not the older CURRCIR series. The snapshot uses the full history that series actually has.

Bitcoin market cap and price are Coin Metrics community series `CapMrktCurUSD` and `PriceUSD`, daily, no API key, from the first print in 2010. If that API does not respond, the fetch falls back to the Blockchain.com market-cap and market-price charts.

### Alignment

Money prints are carried forward to every calendar day until the next print. Bitcoin's market cap on that day is the observation dated that day, or the latest one on or before it. The headline date is the later of the two last prints, and the page says when a series was carried. Monthly observations taken from the Board of Governors H.6 file are dated on the first of the month, matching FRED. Dollar amounts are rounded to the nearest dollar.

### If FRED does not answer

The fetch always tries the public CSV endpoint first:

```
https://fred.stlouisfed.org/graph/fredgraph.csv?id=SERIES
```

When that endpoint does not respond, M2, the monetary base, and currency in circulation are read from the Board's [H.6](https://www.federalreserve.gov/releases/h6/current/default.htm) release (the source FRED republishes), and the balance sheet from [H.4.1](https://www.federalreserve.gov/releases/h41/current/). If GFDEBTN is unreachable, debt history before 1993-04-01 comes from the Treasury [Historical Debt Outstanding](https://fiscaldata.treasury.gov/datasets/historical-debt-outstanding/historical-debt-outstanding) annual series instead of the quarterly FRED file. `data/series.json` records which path produced the snapshot.

## Run it

Python standard library only. Node is used by one parity test.

```bash
python3 -m unittest discover -s tests -v
python3 scripts/fetch_data.py
python3 -m http.server 8000
```

Open `http://127.0.0.1:8000/`. The page reads `data/series.json` and does not call FRED, Treasury, or Coin Metrics itself.

## GitHub Pages

After this lands on `main`:

1. Settings → Pages → Build and deployment → Source: **GitHub Actions**.
2. Settings → Actions → General → Workflow permissions: **Read and write**. The nightly job commits a new `data/series.json`, and the default token can only do that when the repository allows it.

The workflow `.github/workflows/pages.yml` deploys on every push to `main`, refreshes the data nightly at 09:17 UTC, and can be run by hand with **workflow_dispatch**. A data commit does not fetch again, so the push does not loop. The site is served at <https://humdings.github.io/poor-man/>.

## License

MIT. See [LICENSE](LICENSE).
