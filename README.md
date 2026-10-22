# India Economic Pulse

> Early-read index of Indian economic activity from UPI, GST and fuel data, tested against official IIP growth.

**Status:** Week 3 - history extended to 2017-18 and index and backtest rebuilt (started 20 Oct 2026). Forecast, report and memo come next.

**Result so far (honest):** the index does **not** beat a simple 12-month-average baseline on the current IIP series (41 months, 29 scored: -5% to -24% depending on the index version). Over 2019 to 2026 on the old IIP series it does (+16% to +21% lower error, 66 scored months, direction right in about 65-69%), but only because that span contains the big 2020-22 swings; scored from 2022 onward every version is worse than the baseline. So the index is an early-read signal for large changes in activity, not a more precise forecaster in a calm period. Fuel and gross GST track IIP strongly over 2019-26 (diesel r = 0.85, gross GST 0.84); UPI growth carries no signal (r = 0.1) because it reflects adoption. An earlier 29-month result (+2% for the regression, diesel r = 0.48) did not survive more history, and is documented as such. Details: `notebooks/03_index_and_backtest.ipynb`, `docs/results/`.

## Scope decision
Minimum project: UPI + GST + fuel (petrol, diesel, ATF, LPG, bitumen) vs IIP. **E-way bills: kept** (usable monthly Excel file, 41 months, updated by the GST portal). **Electricity: dropped** unless a live feed turns up; the core index does not need it.

## Run it
```bash
pip install -r requirements.txt
python src/load_db.py        # builds data/pulse.db from data/clean and runs the five SQL checks
python src/analysis/run_week3.py   # index, lag tests and backtest; writes index_monthly and backtest_results
```
Ingestion scripts in `src/ingest` (`iip.py`, `gdp.py`, `upi.py`, `ppac.py`, `gst.py`, `ewaybill.py`) turn the raw downloads in `data/raw` into `data/clean`. UPI, PPAC and GST files are downloaded by hand because those sites block scripts; IIP and GDP come from MoSPI's open API.

## Folder map
| Folder | Contents |
|---|---|
| `data/raw` | Downloaded files, never edited, download date in the file name |
| `data/clean` | Cleaned tables produced by `src/ingest` |
| `src/ingest` | One script per source |
| `sql` | Schema, growth views, data-quality checks |
| `notebooks` | Index, lag tests, backtest |
| `powerbi` | Report file, PDF export, screenshots |
| `docs` | Data inventory, data-quality log, memo, forecasts |
