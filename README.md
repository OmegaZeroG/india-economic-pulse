# India Economic Pulse

> Early-read index of Indian economic activity from UPI, GST and fuel data, tested against official IIP growth.

**Status:** Week 1 - data access (started 20 Oct 2026). Headline result, backtest table and forecast link will be added as the project progresses.

## Scope decision
Minimum project: UPI + GST + fuel (petrol, diesel, ATF, LPG, bitumen) vs IIP. E-way bills and electricity: *TBD at end of Week 1.*

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
