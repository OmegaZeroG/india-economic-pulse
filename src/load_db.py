"""Build data/pulse.db (SQLite) from the clean CSVs in data/clean.

Applies sql/schema.sql, fills dim_date, upserts every fact table (primary key = month, plus state/
product/base year where relevant, so re-running never creates duplicates), creates the growth views,
records row counts in load_log and finally runs the five checks in sql/checks.sql.

Usage:  python src/load_db.py            (rebuild/refresh the database, then run checks)
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent / "ingest"))
from common import CLEAN, ROOT  # noqa: E402

DB = ROOT / "data" / "pulse.db"
SQL = ROOT / "sql"

# clean CSV -> table
TABLES = {
    "fact_upi": "fact_upi.csv",
    "fact_gst_national": "fact_gst_national.csv",
    "fact_gst_state": "fact_gst_state.csv",
    "fact_fuel": "fact_fuel.csv",
    "fact_ewaybill_national": "fact_ewaybill_national.csv",
    "fact_ewaybill_state": "fact_ewaybill_state.csv",
    "fact_iip": "iip_versions.csv",
    "fact_gdp": "gdp_versions.csv",
}

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


def upsert(con: sqlite3.Connection, table: str, df: pd.DataFrame) -> None:
    """INSERT ... ON CONFLICT DO UPDATE using the table's own primary key."""
    info = con.execute(f"PRAGMA table_info({table})").fetchall()
    pk = [r[1] for r in info if r[5] > 0]
    cols = [c for c in df.columns if c in {r[1] for r in info}]
    rest = [c for c in cols if c not in pk]
    sql = (f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
           f"ON CONFLICT({', '.join(pk)}) DO UPDATE SET " + ", ".join(f"{c}=excluded.{c}" for c in rest))
    rows = df[cols].astype(object).where(df[cols].notna(), None).values.tolist()
    con.executemany(sql, rows)


def main() -> int:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript((SQL / "schema.sql").read_text(encoding="utf-8"))
    upsert(con, "dim_date", build_dim_date())
    for table, csv in TABLES.items():
        path = CLEAN / csv
        if not path.exists():
            print(f"  skipped {table}: {csv} not found")
            continue
        df = pd.read_csv(path)
        if "month" in df.columns:
            df["month"] = df["month"].astype(str)
        upsert(con, table, df)
        con.execute("INSERT INTO load_log VALUES (?,?,?,?) ON CONFLICT(table_name) DO UPDATE SET "
                    "source_csv=excluded.source_csv, csv_rows=excluded.csv_rows, loaded_at=excluded.loaded_at",
                    (table, csv, len(df), datetime.now().isoformat(timespec="seconds")))
        n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:<24} {n:>6} rows")
    con.executescript((SQL / "views.sql").read_text(encoding="utf-8"))
    con.commit()
    con.close()
    print(f"Loaded {DB.name}. Running checks...")
    from run_checks import run
    return run()


if __name__ == "__main__":
    sys.exit(main())
