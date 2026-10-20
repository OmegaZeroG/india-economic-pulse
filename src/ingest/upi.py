"""Parse a manually downloaded NPCI UPI monthly table into data/clean/fact_upi.csv.

Input: any CSV/XLSX in data/raw named upi_*  with columns resembling
  Month | No. of Banks live on UPI | Volume (in Mn) | Value (in Cr.)
Column names are matched loosely. Output columns:
  month, banks_live, volume_mn, value_cr, avg_daily_volume_mn
Units are kept as published. Missing months are flagged, never filled.

Usage:  python src/ingest/upi.py [path]     (default: every data/raw/upi_* file)
"""
import sys

import pandas as pd

from common import CLEAN, read_any, RAW, log_issue, upsert


def _find(cols, *needles):
    for c in cols:
        low = str(c).lower()
        if all(n in low for n in needles):
            return c
    raise KeyError(f"no column containing {needles} in {list(cols)}")


def parse(path) -> pd.DataFrame:
    df = read_any(path)
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


def main(paths=None) -> None:
    files = [p for p in (paths or sorted(RAW.glob("upi_*"))) ]
    if not files:
        sys.exit("No upi_* file in data/raw. Download the NPCI table and name it upi_YYYY-MM-DD.csv")
    frames = [parse(p) for p in files]
    new = pd.concat(frames)
    n = upsert(new, CLEAN / "fact_upi.csv", ["month"])
    full = pd.date_range(new["month"].min(), new["month"].max(), freq="MS").strftime("%Y-%m-%d")
    missing = sorted(set(full) - set(new["month"]))
    if missing:
        log_issue("UPI", f"missing months {missing}", "flagged, not filled", str(len(missing)))
    bad = new[(new["volume_mn"] <= 0) | (new["value_cr"] <= 0) | new[["volume_mn", "value_cr"]].isna().any(axis=1)]
    if len(bad):
        log_issue("UPI", "non-positive or unparseable values", "left as is, see rows", str(len(bad)))
    print(f"UPI: {len(new)} rows read, table now {n} rows, {len(missing)} gaps, {len(bad)} bad rows")


if __name__ == "__main__":
    main(sys.argv[1:] or None)
