"""Parse the manually downloaded PPAC product-wise consumption file into data/clean/fact_fuel.csv.

Input: data/raw/ppac_* (xls/xlsx/csv). PPAC publishes a wide table: one row per
product, month columns grouped under fiscal years. This parser handles the wide
layout where a header row holds the month names and a fiscal-year marker
(e.g. "2025-26") sits above or in a column. Layout is verified against the real
file when it is downloaded; adjust FY_HEADER_ROWS if it differs.

Keeps petrol (MS), diesel (HSD), ATF, LPG and bitumen. Unit: thousand metric tonnes.

Usage:  python src/ingest/ppac.py [path]
"""
import re
import sys

import pandas as pd

from common import CLEAN, MONTHS, RAW, log_issue, upsert

KEEP = {"ms": "Petrol (MS)", "petrol": "Petrol (MS)", "hsd": "Diesel (HSD)", "diesel": "Diesel (HSD)",
        "atf": "ATF", "lpg": "LPG", "bitumen": "Bitumen"}


def _product(name: str):
    low = re.sub(r"[^a-z ]", " ", str(name).lower())
    for key, label in KEEP.items():
        if re.search(rf"\b{key}\b", low):
            return label
    return None


def parse(path) -> pd.DataFrame:
    raw = pd.read_excel(path, header=None) if str(path).lower().endswith(("xls", "xlsx")) \
        else pd.read_csv(path, header=None)
    # locate the header row: the one with the most month names
    hdr = max(range(min(15, len(raw))),
              key=lambda i: sum(str(v).strip().title() in MONTHS for v in raw.iloc[i]))
    # fiscal year labels like 2025-26 anywhere above or on the header row
    fy_at = {}
    for i in range(hdr + 1):
        for j, v in raw.iloc[i].items():
            m = re.search(r"(20\d{2})\s*[-–/]\s*(\d{2,4})", str(v))
            if m:
                fy_at[j] = int(m.group(1))
    rows, fy = [], None
    for j in raw.columns:
        mname = str(raw.iloc[hdr, j]).strip().title()
        fy = fy_at.get(j, fy)
        if mname not in MONTHS or fy is None:
            continue
        mnum = MONTHS[mname]
        year = fy if mnum >= 4 else fy + 1  # fiscal year April-March
        for i in range(hdr + 1, len(raw)):
            prod = _product(raw.iloc[i, 0])
            val = pd.to_numeric(str(raw.iloc[i, j]).replace(",", ""), errors="coerce")
            if prod and pd.notna(val):
                rows.append({"month": f"{year}-{mnum:02d}-01", "product": prod, "consumption_kt": val})
    return pd.DataFrame(rows)


def main(paths=None) -> None:
    files = paths or sorted(RAW.glob("ppac_*"))
    if not files:
        sys.exit("No ppac_* file in data/raw. Download PPAC consumption and name it ppac_YYYY-MM-DD.xls")
    new = pd.concat([parse(p) for p in files]).drop_duplicates(["month", "product"], keep="last")
    n = upsert(new, CLEAN / "fact_fuel.csv", ["month", "product"])
    log_issue("PPAC", "latest months are provisional and get revised", "re-download each month, upsert",
              str(len(new)))
    print(f"PPAC: {len(new)} rows parsed, table now {n} rows, products: {sorted(new['product'].unique())}")


if __name__ == "__main__":
    main(sys.argv[1:] or None)
