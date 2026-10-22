"""SILVER: quarterly GDP (real, constant prices) from the bronze copies of MoSPI API pulls.

MoSPI publishes levels, not growth, so year-on-year growth is computed here from constant-price GDP versus the
same quarter a year earlier, within the same file (so a revision to last year's level is used consistently).
`release_date` is the date the file was downloaded; every version is kept so a revised quarter is not overwritten.
Primary key: (base_year, quarter_start, release_date).

Fiscal quarters: Q1 = Apr-Jun, Q2 = Jul-Sep, Q3 = Oct-Dec, Q4 = Jan-Mar. `quarter_start` is the first day of the quarter.
Silver output (silver_gdp): base_year, quarter_start, release_date, fiscal_year, quarter, gdp_constant_cr,
gdp_current_cr, yoy_growth_pct, source_file

Usage:  python src/silver/gdp.py       (normally run through src/silver/build_silver.py)
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import bronze_files, bronze_records, connect, log_issue, replace_table  # noqa: E402

Q_START_MONTH = {"Q1": 4, "Q2": 7, "Q3": 10, "Q4": 1}


def quarter_start(fy: str, q: str) -> pd.Timestamp:
    start_year = int(fy[:4])
    month = Q_START_MONTH[q]
    return pd.Timestamp(year=start_year + (1 if q == "Q4" else 0), month=month, day=1)


def build(con) -> None:
    files = bronze_files(con, "gdp")
    if not files:
        raise SystemExit("No gdp files in bronze (run src/bronze/fetch_api.py then src/bronze/load_bronze.py)")
    frames = []
    for fid, name, fdate in files:
        df = pd.DataFrame(bronze_records(con, fid))
        df["quarter_start"] = [quarter_start(fy, q) for fy, q in zip(df["year"], df["quarter"])]
        df = df.sort_values("quarter_start").reset_index(drop=True)
        const = pd.to_numeric(df["constant_price"])
        out = pd.DataFrame({
            "quarter_start": df["quarter_start"].dt.strftime("%Y-%m-%d"),
            "fiscal_year": df["year"], "quarter": df["quarter"], "base_year": df["base_year"],
            "release_date": fdate,
            "gdp_constant_cr": const, "gdp_current_cr": pd.to_numeric(df["current_price"]),
            "yoy_growth_pct": (const / const.shift(4) - 1).mul(100).round(2),
            "source_file": name,
        })
        # never fill: a missing quarter would make shift(4) compare the wrong quarters
        gaps = pd.date_range(df["quarter_start"].min(), df["quarter_start"].max(), freq="QS-JAN").difference(
            pd.DatetimeIndex(df["quarter_start"]))
        calendar_gaps = [d for d in gaps if d.month in (1, 4, 7, 10)]
        if calendar_gaps:
            log_issue("GDP", f"missing quarters {[d.date().isoformat() for d in calendar_gaps]}",
                      "growth not computed across the gap", str(len(calendar_gaps)))
        frames.append(out)
    allv = pd.concat(frames).drop_duplicates(["base_year", "quarter_start", "release_date"], keep="last")
    allv = allv.sort_values(["base_year", "quarter_start", "release_date"])
    n = replace_table(con, "silver_gdp", allv)
    last = allv.dropna(subset=["yoy_growth_pct"]).iloc[-1]
    print(f"silver_gdp: {n} rows, latest {last['fiscal_year']} {last['quarter']} real growth {last['yoy_growth_pct']}%")


if __name__ == "__main__":
    con = connect()
    build(con)
    con.commit()
