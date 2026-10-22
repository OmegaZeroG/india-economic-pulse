# Power BI report: build guide

The data is ready as CSV files in `powerbi/data` (rebuild with `python src/run_all.py` then `python src/export_powerbi.py`).
Power BI Desktop is Windows-only. Plan on 60 to 90 minutes. Save the file as `powerbi/india_economic_pulse.pbix`.

## 1. Load and model
1. **Get data > Text/CSV**, load all files in `powerbi/data`. Set `month`, `month_start` and `quarter_start` columns to **Date** type.
2. **Model view.** Relationships, all one-to-many, single direction, no two-way filters:
   `dim_date[month_start]` to `month` in `fact_upi`, `fact_gst_national`, `fact_gst_state`, `fact_fuel`, `fact_ewaybill_national`, `fact_iip`, `growth_monthly`, `index_monthly`, `backtest_results`; and to `quarter_start` in `fact_gdp`.
3. Right-click `dim_date` > **Mark as date table** > `month_start`.
4. `fact_iip` holds two IIP series. Always filter `base_year = "2022-23"` (the measures do).
5. Paste the measures from `measures.dax`. Check each one; the file says which names to adjust.

## 2. Three pages, at most five visuals each
Design rules: one colour per meaning (**blue = actual IIP, orange = the index model, grey = baseline**), no pie or 3D charts, every title states the conclusion.

**Page 1: headline**
Title: *"Fuel and GST growth follow official industrial output through big swings, but the index adds little in calm months"*
- Line chart: `index_monthly[iip_yoy_pct]` (blue) and `index_monthly[zscore_index]` on a secondary axis (orange), by month.
- Cards: `Latest Index Value`, `Index Direction`, `Latest IIP Growth %`.
- Text box: "Data through Sep 2026. Refreshed by hand, not live."

**Page 2: indicator drill-down**
Title: *"Diesel, petrol and gross GST track IIP; UPI growth does not (it measures adoption)"*
- Slicer: `growth_monthly[indicator]`.
- Line chart: `Selected Indicator YoY %` by month (add `Selected Indicator 3M Avg YoY %` as a second line).
- Bar chart: top 15 states by `GST Gross (ex cess), Rs crore` for the latest month (slicer or filter on `fact_gst_state[state]`).
- Optional table: month, indicator, value, yoy_pct.

**Page 3: backtest scorecard**
Title: *"No index version beat a 12-month average over the last 29 months"*
- Bar chart: `Backtest MAE` by `backtest_results[model]` (baselines grey, index versions orange).
- Line chart: `backtest_results[actual]` (blue) vs `[forecast]` (orange) by month, with a `model` slicer set to `zscore_index`.
- Table from `robustness.csv`: variant, model, `mae_improvement_vs_best_baseline_pct`. Shows the edge appears only in the 2019-22 swing period.
- Cards: `MAE Improvement vs Best Baseline %`, `Direction Hit Rate`.

## 3. Publish or export
Publishing online often needs a work or school account. If it is refused: save the `.pbix` in `powerbi/`, export a PDF (File > Export > PDF), save a screenshot of each page into `powerbi/screenshots/`, and put the headline screenshot in the README.
