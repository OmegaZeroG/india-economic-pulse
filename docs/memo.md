# Memo: can UPI, GST and fuel data give an early read on Indian industrial output?

**To:** a finance, consulting or research team lead  **Data through:** Sep 2026 (UPI, fuel), Aug 2026 (GST, IIP)

**Question.** Can monthly UPI, GST and fuel data tell us whether Indian industrial output is speeding up or slowing down before the official Index of Industrial Production (IIP) is published about 28 days after month end?

**Answer.** Partly. Fuel and GST growth move closely with IIP when activity swings widely, and a simple index built from them cut forecast error by 18 to 21% against a naive baseline over 2019 to 2026. In calm periods, which is where we are now, the index did **not** beat a plain 12-month average.

**Evidence**
- **Fuel and GST track IIP.** Over Apr 2019 to Mar 2026 (83 months, old IIP series) year-on-year growth in diesel correlates 0.85 with IIP growth, petrol 0.86, gross GST 0.84. With the COVID months removed it is still 0.83, 0.71 and 0.64. UPI growth correlates only 0.1, because it reflects adoption, not activity.
- **The index beats the baseline when scored over the whole 2019-26 span** (UPI left out). Rolling forecasts (each month predicted using only earlier months) over 66 months had a mean absolute error of 2.7 to 2.8 points against 3.4 for the 12-month average, and called the direction of change right in 67 to 69% of months.
- **The edge is gone in calm conditions.** Scored from Apr 2022, every index version was worse than the baseline (6 to 20%). On the current IIP series (base 2022-23, 29 scored months) the baseline had an error of 1.88 points against 1.98 for the best index version (5% worse).

**Current reading.** IIP growth was 8.0% in Aug 2026 (12-month average 5.4%). Latest indicators: diesel +5.6% and petrol +8.0% year on year in Sep, gross GST (ex-cess) +14.8% in Aug, UPI value +18.0% in Sep. The index itself reads about average (-0.21) while IIP is high, so the two disagree.

**Forecast and confidence.** No live forecast is published. The code to produce one is in `src/analysis/forecast.py` and a draft for Oct 2026 is in `docs/forecasts/`. Given the backtest, confidence in a point forecast from this index over the 12-month average is **low**; its direction signal is modest. For GDP, Q2 FY27 growth is more likely below Q1's 7.82% (low confidence), based on how Q2 has compared with Q1 in four earlier years.

**Limits**
- Short history: the current IIP series starts Apr 2023, and it correlates only 0.40 with the old series over 36 overlapping months, so they cannot be joined.
- Many results rest on 29 to 66 monthly points; differences of a few percent are within noise.
- Recent GST and fuel figures are provisional and get revised. October 2026 is a Diwali-shift month (Diwali moved from 20 Oct 2025 to 8 Nov 2026), which distorts year-on-year comparisons.
- The data is refreshed by hand, not live.

**Recommendation.** Use the indicators as an early warning for large changes in activity, checked against IIP when it is published. Do not use the index in place of a 12-month average for small month-to-month moves. If this were extended: add a festival adjustment, use state-level data, and test again once more than 60 months of the new IIP series exist.
