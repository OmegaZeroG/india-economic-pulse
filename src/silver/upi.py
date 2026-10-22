"""SILVER: UPI monthly table, built from the bronze copies of the NPCI downloads (one per financial year).

Bronze input: first sheet of each upi_* file, with columns resembling
  Month | No. of Banks live on UPI | Volume (in Mn) | Value (in Cr.)
Column names are matched loosely. Silver output (silver_upi):
  month, banks_live, volume_mn, value_cr, avg_daily_volume_mn, source_file
Units are kept as published. Missing months are flagged, never filled. If two files hold the same month,
the later file name wins.

Usage:  python src/silver/upi.py       (normally run through src/silver/build_silver.py)
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import bronze_files, bronze_sheets, connect, log_issue, replace_table  # noqa: E402


def _find(cols, *needles):
    for c in cols:
        low = str(c).lower()
        if all(n in low for n in needles):
            return c
    raise KeyError(f"no column containing {needles} in {list(cols)}")


def parse(sheet: pd.DataFrame) -> pd.DataFrame:
    df = sheet.iloc[1:].copy()
    df.columns = [str(c) for c in sheet.iloc[0]]
    mcol = _find(df.columns, "month")
    out = pd.DataFrame({
        "month": pd.to_datetime(df[mcol], format="mixed", errors="coerce").dt.to_period("M").dt.to_timestamp(),
        "banks_live": pd.to_numeric(df[_find(df.columns, "bank")], errors="coerce"),
        "volume_mn": pd.to_numeric(df[_find(df.columns, "volume")].astype(str).str.replace(",", ""), errors="coerce"),
        "value_cr": pd.to_numeric(df[_find(df.columns, "value")].astype(str).str.replace(",", ""), errors="coerce"),
    }).dropna(subset=["month"])
    out["avg_daily_volume_mn"] = out["volume_mn"] / out["month"].dt.days_in_month
    out["month"] = out["month"].dt.strftime("%Y-%m-%d")
    return out


def build(con) -> None:
    files = bronze_files(con, "upi")
    if not files:
        raise SystemExit("No upi files in bronze (run src/bronze/load_bronze.py)")
    frames = []
    for fid, name, _ in files:
        f = parse(next(iter(bronze_sheets(con, fid).values())))
        f["source_file"] = name
        frames.append(f)
    new = pd.concat(frames)
    full = pd.date_range(new["month"].min(), new["month"].max(), freq="MS").strftime("%Y-%m-%d")
    missing = sorted(set(full) - set(new["month"]))
    if missing:
        log_issue("UPI", f"missing months {missing}", "flagged, not filled", str(len(missing)))
    bad = new[(new["volume_mn"] <= 0) | (new["value_cr"] <= 0) | new[["volume_mn", "value_cr"]].isna().any(axis=1)]
    if len(bad):
        log_issue("UPI", "non-positive or unparseable values", "left as is, see rows", str(len(bad)))
    new = new.drop_duplicates("month", keep="last").sort_values("month")
    n = replace_table(con, "silver_upi", new)
    print(f"silver_upi: {n} rows ({new['month'].min()} to {new['month'].max()}), {len(missing)} gaps, {len(bad)} bad rows")


if __name__ == "__main__":
    con = connect()
    build(con)
    con.commit()
