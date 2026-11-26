# Poor Man's Bailout

**Bitcoin is more American than the Dollar!**

Washington, Madison, and Jefferson treated paper money as a standing danger, and the Constitution told the states to keep gold and silver as tender. Bitcoin is the hard-money side of that argument.

To a bitcoiner, debasement is a slow-motion bailout. A bailout used to need a vote. Now it just needs time. Fewer days means the printer is outrunning bitcoin; more days means bitcoin is outrunning the printer.

How many days of monetary expansion equal the entire bitcoin market cap.

Money spends the same, so expansion in any form counts as expansion. M2, the monetary base, currency in circulation, public debt, and the Fed balance sheet all count. Debt spends the same as cash: one person's debt is another's asset.

**[humdings.github.io/poor-man](https://humdings.github.io/poor-man/)**

![Poor Man's Bailout. Bitcoin is more American than the Dollar. US M2, 12-month trailing change: 345.8 days.](docs/preview.png)

On a date *t*, over a window that starts at *s* and spans *N* calendar days:

```
d(t) = C(t) / g(t)     when g(t) > 0
```

*C* is the bitcoin market cap in dollars. *g* is the pace of the chosen measure, in dollars per day. The default is US M2 and a 12-month trailing change, `(M(t) − M(s)) / N`.

## In their words

Verbatim. Spellings and punctuation are the source's.

> And I sincerely believe with you, that banking establishments are more dangerous than standing armies; & that the principle of spending money to be paid by posterity, under the name of funding, is but swindling futurity on a large scale

Thomas Jefferson to John Taylor, 28 May 1816. [Founders Online](https://founders.archives.gov/documents/Jefferson/03-10-02-0053).

> Bank-paper must be suppressed, and the circulating medium must be restored to the nation to whom it belongs.

Thomas Jefferson to John Wayles Eppes, 11 September 1813. [Founders Online](https://founders.archives.gov/documents/Jefferson/03-06-02-0388).

> No State shall enter into any Treaty, Alliance, or Confederation; grant Letters of Marque and Reprisal; coin Money; emit Bills of Credit; make any Thing but gold and silver Coin a Tender in Payment of Debts; pass any Bill of Attainder, ex post facto Law, or Law impairing the Obligation of Contracts, or grant any Title of Nobility.

United States Constitution, Article I, Section 10. [National Archives transcript](https://www.archives.gov/founding-docs/constitution-transcript).

> The loss which America has sustained since the peace, from the pestilent effects of paper money on the necessary confidence between man and man, on the necessary confidence in the public councils, on the industry and morals of the people, and on the character of republican government, constitutes an enormous debt against the States chargeable with this unadvised measure, which must long remain unsatisfied; or rather an accumulation of guilt, which can be expiated no otherwise than by a voluntary sacrifice on the altar of justice, of the power which has been the instrument of it.

James Madison, Federalist No. 44, New York Packet, 25 January 1788. [Avalon Project](https://avalon.law.yale.edu/18th_century/fed44.asp).

> Paper money has had the effect in your State that it ever will have, to ruin commerce—oppress the honest, and open a door to every species of fraud and injustice.

George Washington to Jabez Bowen, 9 January 1787. [Founders Online](https://founders.archives.gov/documents/Washington/04-04-02-0428).

> I think they've made the biggest financial mess that any government's ever made in this country for a very long time, and Socialist governments traditionally do make a financial mess. They always run out of other people's money. It's quite a characteristic of them.

Margaret Thatcher, Thames TV *This Week*, 5 February 1976. [Thatcher Foundation](https://www.margaretthatcher.org/document/102953).

> It follows from the propositions I have so far stated that inflation is always and everywhere a monetary phenomenon in the sense that it is and can be produced only by a more rapid increase in the quantity of money than in output.

Milton Friedman, “The Counter-Revolution in Monetary Theory,” 16 September 1970. [Hoover Institution](https://miltonfriedman.hoover.org/internal/media/dispatcher/214480/full).

## Headline

Default view in the snapshot generated **2026-11-26**: 12-month trailing change, normalization off. Headline date **2026-11-25**. Bitcoin market cap that day: **$1.21 trillion**.

The live page replaces this table whenever the nightly job commits a new snapshot.

| Measure | Days | Pace | Level in effect |
| --- | ---: | ---: | --- |
| US M2 | 345.8 | $3.51 billion a day | $23.53 trillion, print 2026-10-01, carried forward |
| Monetary base | 2,799 | $433.15 million a day | $5.46 trillion, print 2026-10-01, carried forward |
| Currency in circulation | 6,958 | $174.25 million a day | $2.49 trillion, print 2026-10-01, carried forward |
| Public debt | 181.9 | $6.66 billion a day | $40.79 trillion, through 2026-11-24 |
| Fed balance sheet | 2,377 | $510.05 million a day | $6.74 trillion, through 2026-11-18 |

The Fed balance sheet is last in the toggle and stays off the comparison strip. It is still monetary expansion.

## Measures

Levels are stored in dollars. No API key.

| Measure | Source | History in this snapshot | Published unit |
| --- | --- | --- | --- |
| US M2, the default | [FRED M2SL](https://fred.stlouisfed.org/series/M2SL) | 1959-01-01 → 2026-10-01 | billions, monthly, seasonally adjusted, × 1e9 |
| Monetary base | [FRED BOGMBASE](https://fred.stlouisfed.org/series/BOGMBASE) | 1959-01-01 → 2026-10-01 | billions, monthly, × 1e9 |
| Currency in circulation | [FRED MBCURRCIR](https://fred.stlouisfed.org/series/MBCURRCIR) | 1959-01-01 → 2026-10-01 | billions, monthly, × 1e9 |
| Public debt | [Debt to the Penny](https://fiscaldata.treasury.gov/datasets/debt-to-the-penny/debt-to-the-penny) `tot_pub_debt_out_amt` | daily from 1993-04-01 → 2026-11-24 | dollars |
| Public debt, earlier history | [FRED GFDEBTN](https://fred.stlouisfed.org/series/GFDEBTN) | 1966-01-01, spliced strictly before 1993-04-01 | millions, quarterly, × 1e6 |
| Fed balance sheet | [FRED WALCL](https://fred.stlouisfed.org/series/WALCL) | 2002-12-18 → 2026-11-18 | millions, Wednesday level, × 1e6 |
| Bitcoin market cap and price | [Coin Metrics](https://docs.coinmetrics.io/api/v4/) `CapMrktCurUSD`, `PriceUSD` | 2010-07-18 → 2026-11-25 | dollars, daily |

M2 is the seasonally adjusted monthly series only. The weekly not-seasonally-adjusted series [WM2NS](https://fred.stlouisfed.org/series/WM2NS) is left out, so the join does not add a seasonal jump. Currency in circulation is MBCURRCIR, the currency component of the monetary base, for the full history that series has.

Optional deflators, used only when normalization is on:

| Deflator | Source | History | What is stored |
| --- | --- | --- | --- |
| Nominal GDP | [FRED GDP](https://fred.stlouisfed.org/series/GDP) | 1947-01-01 → 2026-07-01 | dollars. The series is an annual rate; only the ratio is used, so the annualization cancels |
| CPI | [FRED CPIAUCSL](https://fred.stlouisfed.org/series/CPIAUCSL) | 1947-01-01 → 2026-10-01 | the index, including fractions of a point |

If Coin Metrics does not respond, bitcoin falls back to the Blockchain.com market-cap and market-price charts. If the FRED CSV endpoint does not respond, M2, the monetary base, and currency come from the Board's [H.6](https://www.federalreserve.gov/releases/h6/current/default.htm) release, the balance sheet from [H.4.1](https://www.federalreserve.gov/releases/h41/current/), and debt before 1993-04-01 from the Treasury [Historical Debt Outstanding](https://fiscaldata.treasury.gov/datasets/historical-debt-outstanding/historical-debt-outstanding) annual file. `data/series.json` records which path was used.

Each level is stepped forward to every calendar day and held until the next print. Bitcoin's market cap and price on a day are the observations on that day, or the latest on or before it. The headline date is the later of the money print and the bitcoin print.

## Assumptions and options

The panel beside the headline lists the choices in force. The same choices are the query string, so a link is the view:

`?measure=m2&window=12&unit=m&method=trailing&log=1&norm=0`

| Choice | Default | Options |
| --- | --- | --- |
| Series | M2 | Monetary base, currency in circulation, public debt, Fed balance sheet |
| Smoothing | 12 months | None, 3 months, 5 years, 10 years, or a custom number of months or years |
| Averaging | Trailing change | Regression, or CAGR pace. Disabled when smoothing is off |
| Normalization | Off | Excess of nominal GDP, or excess of CPI |
| Fixed bitcoin | Shown under the headline | Days at the window-start price, and at the window-start coin count |
| Contraction | A gap in the day count | The pace chart still draws a decrease |
| Scale | Log on the day-count charts | Linear |

**Smoothing.** The window and the averaging method smooth the pace. Trailing change is `(M(t) − M(s)) / N`. Regression is the ordinary least-squares slope of the daily forward-filled level. CAGR pace is `M(t) × ((M(t) / M(s))^(1/N) − 1)`, the compound rate at today's level. **None** (`window=0`) uses the change between the print in effect and the print before it, held until the next print. A down print stays a decrease.

**Normalization.** Off unless the box is checked. The pace is then money growth in excess of the deflator over the same interval:

```
trailing, and no smoothing
    g* = g − M(s) × (D(t) − D(s)) / (N × D(s))
CAGR
    g* = M(t) × (r(M) − r(D))
regression
    g* = slope(M) − M(t) × slope(ln D)
```

A flat deflator leaves the pace unchanged. If money grew at the same percentage rate as the deflator, the trailing and CAGR excess is zero and the day count pauses.

**Fixed bitcoin.** The change in days since the start of the window splits into three parts that add up: money growth moves first, then the bitcoin price, then coins outstanding. Days at a fixed price hold the price from the start of the window. Days at a fixed coin count hold the number of coins. A longer bailout at a high price is the point: it is a higher valuation relative to monetary expansion.

When the pace is zero or negative, the day count is left blank. A negative or infinite day count is never drawn. The pace chart keeps the decrease, including M2 in 2022–23.

## Run it locally

Python standard library only. Node is used by the parity tests.

```bash
python3 -m unittest discover -s tests -v
python3 scripts/fetch_data.py
python3 -m http.server 8000
```

Open `http://127.0.0.1:8000/`. The page reads `data/series.json` and does not call FRED, Treasury, or Coin Metrics itself.

The tests include hand-worked cases for the day count, the split into money growth, bitcoin price, and new coins, excess growth over a deflator, and an unsmoothed decrease, plus JavaScript parity with the Python implementation.

## Nightly data and GitHub Pages

`.github/workflows/pages.yml` does both jobs.

- Every push to `main` runs the tests and deploys the site.
- A schedule at 09:17 UTC, and **Run workflow** by hand, fetch a new `data/series.json`, commit it, and deploy. The data commit deploys again and does not fetch a second time.

Before the first deploy, in the repository settings:

1. Pages → Build and deployment → Source: **GitHub Actions**.
2. Actions → General → Workflow permissions: **Read and write**, so the nightly job can commit the snapshot.

The site is [https://humdings.github.io/poor-man/](https://humdings.github.io/poor-man/).

## License

[MIT](LICENSE).
