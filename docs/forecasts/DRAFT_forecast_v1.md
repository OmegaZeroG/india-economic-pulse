# Forecast v1: October 2026 IIP growth  (DRAFT, NOT PRE-REGISTERED)

> **DRAFT: an illustration of the method, not a published forecast.** October 2026 indicators were not available when this was generated, so the model forecast is pending; the baseline, intervals, success rule and GDP call are real. To produce a final file once the data exists: `python src/analysis/forecast.py --target 2026-10 --final` (refused unless every indicator is published, the git tree is clean and no earlier file exists).

## 1. When and with what

- **Made on:** 2026-10-22 23:44 India Standard Time
- **Model version (git commit):** `4384828`  (working tree has uncommitted changes)
- **Target:** year-on-year growth of the Index of Industrial Production for October 2026, base 2022-23, first release by MoSPI (expected around the 28th of November 2026; check the calendar for a shifted date).
- **Data available when this was made:**

| Source | Latest period | Newest file downloaded |
|---|---|---|
| UPI | 2026-09 | 2026-10-22 |
| GST (national) | 2026-08 | 2026-10-22 |
| Fuel (PPAC) | 2026-09 | 2026-10-21 |
| E-way bills | 2026-08 | 2026-10-22 |
| IIP (base 2022-23) | 2026-08 | 2026-10-20 |
| GDP (quarter start) | 2026-04 | 2026-10-21 |

Last known IIP value: **8.0%** for August 2026.

## 2. Forecast

| | Point | 80% interval | 90% interval |
|---|---|---|---|
| **Index model** | **pending** (indicators for the target month not yet published) | point forecast -3.5 to +2.3 | point forecast -4.9 to +2.6 |
| Baseline: average of last 12 months (Sep 2025 to Aug 2026) | 5.4% | 2.0% to 7.9% | 0.1% to 8.2% |
| Baseline: last known value | 8.0% | n/a | n/a |

Intervals are the 10th-90th and 5th-95th percentiles of each model's own out-of-sample errors over 29 backtested months (Apr 2024 onward), added to the point forecast. With so few errors the interval edges are rough.

Waiting for: upi_daily_volume_mn, upi_value_cr, gst_net_ex_cess_cr, fuel_diesel_kt, fuel_bitumen_kt, fuel_atf_kt, fuel_petrol_kt.

**Known distortion:** Diwali was on 20 Oct 2025 and falls on 8 Nov 2026, so October 2026 is a Diwali-shift month. Its year-on-year comparison is against a festive October, and indicators and IIP are both affected. The model has no festival term.

## 3. What the backtest says about trusting it

Over 29 out-of-sample months the index model's mean absolute error was **1.98** points against **1.88** for the 12-month-average baseline (-5.3%). It was closer than the baseline in 55% of months. Direction vs the previous month was right in 75% of months. On a longer 2019-26 sample (old IIP base) the index beat the baseline during the large 2020-22 swings but not in calm periods. **So the baseline is a serious rival, and the most likely outcome is that it is as close as the model or closer.** Full evidence: `notebooks/03_index_and_backtest.ipynb`.

## 4. Rule for calling it a success (fixed before the data exist)

1. **Main rule:** the index model's point forecast is closer to the actual October 2026 IIP growth than the 12-month-average baseline forecast.
2. **Also reported:** whether the actual falls inside the 80% interval, and whether the sign of the move from the previous month was called correctly.
3. The result goes into `docs/forecasts/scoring.md` whether it is a hit or a miss. The forecast file is never edited after publication.

## 5. Q2 FY2026-27 GDP: above or below Q1?

**Call: BELOW.** Q2 FY27 real GDP growth (MoSPI first estimate, expected 30 Nov 2026) will be below Q1 FY27's 7.82% (compared with Q1 as published in the same release, in case it is revised). **Confidence: low.**

Reasoning: Q2 growth is Q2's level against last year's Q2. Q2's level as a fraction of Q1's was FY2022-23 0.981, FY2023-24 0.990, FY2024-25 0.988, FY2025-26 0.999; to match Q1's growth, Q2 FY27 would need 0.9993, the highest of the four years. At the typical ratio (0.9887) growth would be about 6.7%. In 3 of 4 years the ratio was below the break-even. Only four years of history, so this is a weak basis. A test of whether IIP growth predicts the direction of GDP growth found no relationship (signs agreed in 7 of 12 quarters), so IIP is not used for this call.

