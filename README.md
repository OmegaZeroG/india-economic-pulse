# India Economic Pulse

> Early-read index of Indian economic activity from UPI, GST and fuel data, tested against official IIP growth.

**Status:** Week 2 - SQL schema, growth views and data checks done (started 20 Oct 2026). UPI, fuel, GST, e-way bill and IIP all load from raw files. Headline result, backtest table and forecast link will be added as the project progresses.

## Scope decision
Minimum project: UPI + GST + fuel (petrol, diesel, ATF, LPG, bitumen) vs IIP. **E-way bills: kept** (usable monthly Excel file, 41 months, updated by the GST portal). **Electricity: dropped** unless a live feed turns up; the core index does not need it.

## Run it
```bash
pip install -r requirements.txt
python src/load_db.py        # builds data/pulse.db from data/clean and runs the five SQL checks
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
