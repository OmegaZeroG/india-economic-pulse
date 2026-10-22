"""Export the star schema to CSV files for Power BI (Power BI Desktop has no native SQLite connector).

Writes powerbi/data/*.csv from data/pulse.db: the date dimension, one fact table per indicator, the long
growth view, the index, the backtest and the robustness table. Dates are ISO text (yyyy-mm-dd), which Power BI
reads as dates. Re-run after `python src/run_all.py`.

Usage:  python src/export_powerbi.py
"""
import shutil
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "pulse.db"
OUT = ROOT / "powerbi" / "data"

QUERIES = {
    "dim_date": "SELECT * FROM dim_date WHERE month_start BETWEEN '2017-04-01' AND '2026-12-01'",
    "fact_upi": "SELECT * FROM fact_upi",
    "fact_gst_national": "SELECT * FROM fact_gst_national",
    "fact_gst_state": "SELECT * FROM fact_gst_state",
    "fact_fuel": "SELECT * FROM fact_fuel WHERE month >= '2017-04-01'",
    "fact_ewaybill_national": "SELECT * FROM fact_ewaybill_national",
    "fact_iip": "SELECT base_year, month, index_value, yoy_growth_pct FROM v_iip_latest",
    "fact_gdp": "SELECT base_year, quarter_start, fiscal_year, quarter, gdp_constant_cr, yoy_growth_pct FROM v_gdp_latest",
    "growth_monthly": "SELECT * FROM v_growth_monthly WHERE month >= '2017-04-01'",
    "index_monthly": "SELECT * FROM index_monthly",
    "backtest_results": "SELECT * FROM backtest_results",
    "backtest_summary": "SELECT * FROM v_backtest_summary",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    for name, sql in QUERIES.items():
        df = pd.read_sql(sql, con)
        df.to_csv(OUT / f"{name}.csv", index=False)
        print(f"  {name:<24}{len(df):>6} rows")
    con.close()
    shutil.copy(ROOT / "docs" / "results" / "robustness.csv", OUT / "robustness.csv")
    print(f"Wrote {len(QUERIES) + 1} files to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
