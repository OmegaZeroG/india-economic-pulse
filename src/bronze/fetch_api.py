"""Pull the latest IIP and GDP from MoSPI's open eSankhyiki API (no key needed) and save each response as a raw
JSON file in data/raw, named with today's date. This is the only step that touches the network. Bronze loading
(src/bronze/load_bronze.py) then stores the files as they are; silver parses them.

  python src/bronze/fetch_api.py                 IIP and GDP, base 2022-23
  python src/bronze/fetch_api.py iip 2011-12     one source and base year

Each day's pull is a separate file, so a number revised between two pulls is kept as two versions downstream.
api.mospi.gov.in needs legacy TLS renegotiation (OP_LEGACY_SERVER_CONNECT); the adapter applies it to that host only.
"""
import json
import ssl
import sys
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import raw_name  # noqa: E402

IIP_URL = "https://api.mospi.gov.in/api/iip/getIipData"
GDP_URL = "https://api.mospi.gov.in/api/nas/getNasData"


class _LegacySSL(HTTPAdapter):
    def init_poolmanager(self, *a, **k):
        ctx = ssl.create_default_context()
        ctx.options |= 0x4
        k["ssl_context"] = ctx
        super().init_poolmanager(*a, **k)


def _pages(url: str, params: dict) -> list[dict]:
    s = requests.Session()
    s.mount("https://api.mospi.gov.in", _LegacySSL())
    s.headers["User-Agent"] = "Mozilla/5.0 (india-economic-pulse)"
    rows, page = [], 1
    while True:
        r = s.get(url, timeout=40, params={**params, "page": page})
        r.raise_for_status()
        j = r.json()
        rows += j["data"]
        if page >= j["meta_data"]["totalPages"]:
            return rows
        page += 1


def fetch_iip(base_year: str = "2022-23") -> Path:
    rows = _pages(IIP_URL, {"frequency": "Monthly", "base_year": base_year, "type": "General"})
    path = raw_name(f"iip_{base_year}", ".json")
    path.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"IIP {base_year}: {len(rows)} records -> {path.name}")
    return path


def fetch_gdp(base_year: str = "2022-23") -> Path:
    rows = _pages(GDP_URL, {"base_year": base_year, "series": "Current", "frequency_code": 2, "indicator_code": 5})
    path = raw_name(f"gdp_{base_year}", ".json")
    path.write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"GDP {base_year}: {len(rows)} records -> {path.name}")
    return path


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        fetch_iip()
        fetch_gdp()
    elif args[0] == "iip":
        fetch_iip(*args[1:])
    elif args[0] == "gdp":
        fetch_gdp(*args[1:])
    else:
        sys.exit("usage: fetch_api.py [iip|gdp] [base_year]")
