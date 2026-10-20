"""Ingest quarterly GDP (real, constant prices) from MoSPI's open eSankhyiki API (no key needed).

Saves the raw JSON with today's date in data/raw and upserts into data/clean/gdp_versions.csv.
MoSPI publishes levels, not growth, so year-on-year growth is computed here from constant-price
GDP versus the same quarter a year earlier, within the same pull (so a revision to last year's
level is used consistently). `release_date` is the date we observed the value; keep every
version so a revised quarter is not overwritten. Primary key: (base_year, quarter_start, release_date).

Fiscal quarters: Q1 = Apr-Jun, Q2 = Jul-Sep, Q3 = Oct-Dec, Q4 = Jan-Mar. `quarter_start` is the
first day of the quarter.

Usage:  python src/ingest/gdp.py [base_year]      (default 2022-23)
"""
import json
import sys

import pandas as pd
import requests

from common import CLEAN, log_issue, raw_name, today, upsert
from iip import _LegacySSL

URL = "https://api.mospi.gov.in/api/nas/getNasData"
Q_START_MONTH = {"Q1": 4, "Q2": 7, "Q3": 10, "Q4": 1}


def fetch(base_year: str) -> list[dict]:
    s = requests.Session()
    s.mount("https://api.mospi.gov.in", _LegacySSL())
    s.headers["User-Agent"] = "Mozilla/5.0 (india-economic-pulse)"
    rows, page = [], 1
    while True:
        r = s.get(URL, timeout=40, params={"base_year": base_year, "series": "Current",
                                           "frequency_code": 2, "indicator_code": 5, "page": page})
        r.raise_for_status()
        j = r.json()
        rows += j["data"]
        if page >= j["meta_data"]["totalPages"]:
            return rows
        page += 1


def quarter_start(fy: str, q: str) -> pd.Timestamp:
    start_year = int(fy[:4])
    month = Q_START_MONTH[q]
    return pd.Timestamp(year=start_year + (1 if q == "Q4" else 0), month=month, day=1)


def main(base_year: str = "2022-23") -> None:
    rows = fetch(base_year)
    raw_name(f"gdp_{base_year}", ".json").write_text(json.dumps(rows, indent=1, ensure_ascii=False),
                                                     encoding="utf-8")
    df = pd.DataFrame(rows)
    df["quarter_start"] = [quarter_start(fy, q) for fy, q in zip(df["year"], df["quarter"])]
    df = df.sort_values("quarter_start").reset_index(drop=True)
    const = pd.to_numeric(df["constant_price"])
    out = pd.DataFrame({
        "quarter_start": df["quarter_start"].dt.strftime("%Y-%m-%d"),
        "fiscal_year": df["year"], "quarter": df["quarter"], "base_year": df["base_year"],
        "release_date": today(),
        "gdp_constant_cr": const, "gdp_current_cr": pd.to_numeric(df["current_price"]),
        "yoy_growth_pct": (const / const.shift(4) - 1).mul(100).round(2),
    })
    # never fill: a missing quarter would make shift(4) compare the wrong quarters
    gaps = pd.date_range(df["quarter_start"].min(), df["quarter_start"].max(), freq="QS-JAN").difference(
        pd.DatetimeIndex(df["quarter_start"]))
    calendar_gaps = [d for d in gaps if d.month in (1, 4, 7, 10)]
    if calendar_gaps:
        log_issue("GDP", f"missing quarters {[d.date().isoformat() for d in calendar_gaps]}",
                  "growth not computed across the gap", str(len(calendar_gaps)))
    n = upsert(out, CLEAN / "gdp_versions.csv", ["base_year", "quarter_start", "release_date"])
    last = out.dropna(subset=["yoy_growth_pct"]).iloc[-1]
    print(f"GDP {base_year}: {len(out)} quarters ({out['quarter_start'].iloc[0]} to "
          f"{out['quarter_start'].iloc[-1]}), table now {n} rows, "
          f"latest {last['fiscal_year']} {last['quarter']} real growth {last['yoy_growth_pct']}%")


if __name__ == "__main__":
    main(*sys.argv[1:])
