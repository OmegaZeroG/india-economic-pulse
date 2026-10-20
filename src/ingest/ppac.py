"""Parse the manually downloaded PPAC product-wise consumption file into data/clean/fact_fuel.csv.

Input: data/raw/ppac_* (xls/xlsx). Files: the Historical Report (one sheet per fiscal year,
rows = products, columns APR..MAR) and the Current Report (this FY, provisional).
Files are processed in name order, so ppac_current_* overrides older values.
Sheets before FY2016-17 use another layout and are skipped.

Keeps petrol (MS), diesel (HSD), ATF, LPG and bitumen. Unit: thousand metric tonnes.

Usage:  python src/ingest/ppac.py [path]
"""
import re
import sys

import pandas as pd

from common import CLEAN, MONTHS, RAW, read_any, log_issue, upsert

KEEP = {"ms": "Petrol (MS)", "petrol": "Petrol (MS)", "hsd": "Diesel (HSD)", "diesel": "Diesel (HSD)",
        "atf": "ATF", "lpg": "LPG", "bitumen": "Bitumen"}


def _product(name: str):
    low = re.sub(r"[^a-z ]", " ", str(name).lower())
    for key, label in KEEP.items():
        if re.search(rf"\b{key}\b", low):
            return label
    return None


def _fy_start(sheet: pd.DataFrame, sheet_name: str) -> int:
    """Fiscal-year start from the 'Period : April 2025-March 2026' / 'April-26 to Sept-26' cell."""
    for v in map(str, sheet.iloc[:8, 0]):
        m = re.search(r"Period\s*:?\s*([A-Za-z]+)[\s-]*(20\d{2}|\d{2})", v)
        if m:
            y = int(m.group(2))
            return y + 2000 if y < 100 else y
    m = re.match(r"(20\d{2})-\d{2}$", sheet_name)
    if m:
        return int(m.group(1))
    raise ValueError(f"cannot find fiscal year in sheet {sheet_name!r}")


def parse(path) -> pd.DataFrame:
    """One workbook = one sheet per fiscal year (+ an annual summary sheet, skipped)."""
    sheets = pd.read_excel(path, header=None, sheet_name=None)
    rows = []
    for name, raw in sheets.items():
        if not (re.match(r"20\d{2}-\d{2}$", name) or name == "Consumption"):
            continue  # 'Historical (year-wise)' is annual totals
        hdr = next((i for i in range(len(raw)) if str(raw.iloc[i, 0]).strip().upper() == "PRODUCTS"), None)
        if hdr is None:
            continue  # pre-2016 sheets with other layouts are outside our window
        fy = _fy_start(raw, name)
        for j in range(1, raw.shape[1]):
            mname = str(raw.iloc[hdr, j]).strip().title()[:3]
            mnum = next((n for full, n in MONTHS.items() if full[:3] == mname), None)
            if mnum is None:
                continue
            year = fy if mnum >= 4 else fy + 1  # fiscal year April-March
            for i in range(hdr + 1, len(raw)):
                prod = _product(raw.iloc[i, 0])
                val = pd.to_numeric(str(raw.iloc[i, j]).replace(",", ""), errors="coerce")
                if prod and pd.notna(val):
                    rows.append({"month": f"{year}-{mnum:02d}-01", "product": prod,
                                 "consumption_kt": round(float(val), 3)})
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
