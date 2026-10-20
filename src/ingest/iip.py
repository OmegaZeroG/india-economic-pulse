"""Ingest monthly IIP (General) from MoSPI's open eSankhyiki API (no key needed).

Saves the raw JSON with today's date in data/raw, then upserts into
data/clean/iip_versions.csv. Every pull stores `release_date` (the date we
observed the value), so revisions are kept as separate rows instead of
overwritten. Primary key: (base_year, month, release_date).

Usage:  python src/ingest/iip.py [base_year]      (default 2022-23)
"""
import json
import ssl
import sys

import pandas as pd
import requests
from requests.adapters import HTTPAdapter

from common import CLEAN, MONTHS, log_issue, month_key, raw_name, today, upsert

URL = "https://api.mospi.gov.in/api/iip/getIipData"


class _LegacySSL(HTTPAdapter):
    """api.mospi.gov.in needs legacy TLS renegotiation (OP_LEGACY_SERVER_CONNECT)."""

    def init_poolmanager(self, *a, **k):
        ctx = ssl.create_default_context()
        ctx.options |= 0x4
        k["ssl_context"] = ctx
        super().init_poolmanager(*a, **k)


def fetch(base_year: str) -> list[dict]:
    s = requests.Session()
    s.mount("https://api.mospi.gov.in", _LegacySSL())
    s.headers["User-Agent"] = "Mozilla/5.0 (india-economic-pulse)"
    rows, page = [], 1
    while True:
        r = s.get(URL, timeout=40, params={
            "frequency": "Monthly", "base_year": base_year, "type": "General", "page": page})
        r.raise_for_status()
        j = r.json()
        rows += j["data"]
        if page >= j["meta_data"]["totalPages"]:
            return rows
        page += 1


def main(base_year: str = "2022-23") -> None:
    rows = fetch(base_year)
    raw_name(f"iip_{base_year}", ".json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    df = pd.DataFrame(rows)
    df = df[df["category"] == "General"].copy()
    df["month"] = [month_key(y, MONTHS[m]).date().isoformat() for y, m in zip(df["year"], df["month"])]
    out = pd.DataFrame({
        "month": df["month"], "base_year": df["base_year"],
        "release_date": today(),
        "index_value": pd.to_numeric(df["index"]),
        "yoy_growth_pct": pd.to_numeric(df["growth_rate"]),
    })
    n = upsert(out, CLEAN / "iip_versions.csv", ["base_year", "month", "release_date"])

    # gap check: never fill a missing month, flag it
    full = pd.date_range(out["month"].min(), out["month"].max(), freq="MS").strftime("%Y-%m-%d")
    missing = sorted(set(full) - set(out["month"]))
    if missing:
        log_issue("IIP", f"missing months {missing}", "left blank, flagged", str(len(missing)))
    print(f"IIP {base_year}: {len(out)} months fetched "
          f"({out['month'].min()} to {out['month'].max()}), table now {n} rows, "
          f"{len(missing)} gaps")


if __name__ == "__main__":
    main(*sys.argv[1:])
