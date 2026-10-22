"""GOLD: build the star schema from silver, then the growth views, then run the data checks.

1. Apply sql/gold_schema.sql (dimension, fact and analysis tables, created if missing).
2. Fill dim_date: one row per month with fiscal year and quarter, Diwali, festive-season and COVID flags.
3. Run sql/gold_load.sql: every fact table is emptied and refilled from silver with plain SQL (full refresh).
4. Create the views in sql/views.sql (year-on-year growth with LAG over twelve months, latest IIP, scorecard).
5. Load forecast_log from docs/forecasts/forecast_log.csv if a forecast has been pre-registered.
6. Run the checks in sql/checks.sql (src/run_checks.py).

Usage:  python src/gold/build_gold.py       (run after src/silver/build_silver.py)
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT, connect, run_sql_file  # noqa: E402

FORECAST_LOG = ROOT / "docs" / "forecasts" / "forecast_log.csv"

# Month in which Diwali (Lakshmi Puja) falls. Dates taken from the published Hindu festival
# calendar; 2024 is the 31 Oct / 1 Nov edge case (31 Oct in most of India). VERIFY against
# a calendar you cite in the README before relying on it.
DIWALI_MONTH = {2012: 11, 2013: 11, 2014: 10, 2015: 11, 2016: 10, 2017: 10, 2018: 11, 2019: 10,
                2020: 11, 2021: 11, 2022: 10, 2023: 11, 2024: 10, 2025: 10, 2026: 11, 2027: 10}


def build_dim_date(start="2000-01-01", end="2028-12-01") -> pd.DataFrame:
    d = pd.DataFrame({"month_start": pd.date_range(start, end, freq="MS")})
    d["year"], d["month"] = d["month_start"].dt.year, d["month_start"].dt.month
    d["month_name"] = d["month_start"].dt.month_name()
    d["days_in_month"] = d["month_start"].dt.days_in_month
    fy = d["year"].where(d["month"] >= 4, d["year"] - 1)
    d["fiscal_year"] = "FY" + fy.astype(str) + "-" + ((fy + 1) % 100).astype(str).str.zfill(2)
    d["fiscal_quarter"] = ((d["month"] - 4) % 12) // 3 + 1
    d["is_diwali_month"] = [int(DIWALI_MONTH.get(y) == m) for y, m in zip(d["year"], d["month"])]
    d["is_festive_season"] = d["month"].isin([10, 11]).astype(int)
    d["is_covid_month"] = ((d["month_start"] >= "2020-04-01") & (d["month_start"] <= "2020-06-01")).astype(int)
    d["month_start"] = d["month_start"].dt.strftime("%Y-%m-%d")
    return d


def upsert(con, table: str, df: pd.DataFrame) -> None:
    """INSERT ... ON CONFLICT DO UPDATE using the table's own primary key (facts point at dim_date, so it is never emptied)."""
    info = con.execute(f"PRAGMA table_info({table})").fetchall()
    pk = [r[1] for r in info if r[5] > 0]
    cols = [c for c in df.columns if c in {r[1] for r in info}]
    rest = [c for c in cols if c not in pk]
    sql = (f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
           f"ON CONFLICT({', '.join(pk)}) DO UPDATE SET " + ", ".join(f"{c}=excluded.{c}" for c in rest))
    con.executemany(sql, df[cols].astype(object).where(df[cols].notna(), None).values.tolist())


def main() -> int:
    con = connect()
    run_sql_file(con, "gold_schema.sql")
    upsert(con, "dim_date", build_dim_date())
    run_sql_file(con, "gold_load.sql")
    run_sql_file(con, "views.sql")
    if FORECAST_LOG.exists():
        df = pd.read_csv(FORECAST_LOG)
        df["target_month"] = df["target_month"].astype(str)
        upsert(con, "forecast_log", df)
        print(f"  forecast_log: {len(df)} pre-registered forecast(s)")
    else:
        print("  forecast_log: no forecast pre-registered yet")
    con.commit()
    for t in ("dim_date", "fact_upi", "fact_gst_national", "fact_gst_state", "fact_fuel", "fact_ewaybill_national",
              "fact_ewaybill_state", "fact_iip", "fact_gdp"):
        print(f"  {t:<24}{con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:>7} rows")
    con.close()
    print("Gold built. Running checks...")
    from run_checks import run
    return run()


if __name__ == "__main__":
    sys.exit(main())
