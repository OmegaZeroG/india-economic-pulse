"""SILVER: monthly IIP (General) from the bronze copies of MoSPI API pulls (one JSON file per base year and day).

`release_date` is the date the file was downloaded (taken from its name), so a value revised between two pulls is
kept as two rows instead of being overwritten. Primary key: (base_year, month, release_date).
Silver output (silver_iip): base_year, month, release_date, index_value, yoy_growth_pct, source_file

Usage:  python src/silver/iip.py       (normally run through src/silver/build_silver.py)
"""
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import MONTHS, bronze_files, bronze_records, connect, log_issue, month_key, replace_table  # noqa: E402


def build(con) -> None:
    files = bronze_files(con, "iip")
    if not files:
        raise SystemExit("No iip files in bronze (run src/bronze/fetch_api.py then src/bronze/load_bronze.py)")
    frames = []
    for fid, name, fdate in files:
        df = pd.DataFrame(bronze_records(con, fid))
        df = df[df["category"] == "General"].copy()
        df["month"] = [month_key(y, MONTHS[m]).date().isoformat() for y, m in zip(df["year"], df["month"])]
        out = pd.DataFrame({
            "month": df["month"], "base_year": df["base_year"], "release_date": fdate,
            "index_value": pd.to_numeric(df["index"]), "yoy_growth_pct": pd.to_numeric(df["growth_rate"]),
            "source_file": name})
        # gap check: never fill a missing month, flag it
        full = pd.date_range(out["month"].min(), out["month"].max(), freq="MS").strftime("%Y-%m-%d")
        missing = sorted(set(full) - set(out["month"]))
        if missing:
            log_issue("IIP", f"missing months {missing}", "left blank, flagged", str(len(missing)))
        frames.append(out)
    allv = pd.concat(frames).drop_duplicates(["base_year", "month", "release_date"], keep="last")
    allv = allv.sort_values(["base_year", "month", "release_date"])
    n = replace_table(con, "silver_iip", allv)
    for base, g in allv.groupby("base_year"):
        print(f"silver_iip {base}: {len(g)} rows ({g['month'].min()} to {g['month'].max()})")
    print(f"silver_iip: {n} rows in all")


if __name__ == "__main__":
    con = connect()
    build(con)
    con.commit()
