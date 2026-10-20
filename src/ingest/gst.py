"""Extract state-wise GST tables from monthly release PDFs into data/clean/fact_gst_state.csv.

Input: data/raw/gst_YYYY-MM_*.pdf  (the month in the file name is the data month,
e.g. gst_2026-09_downloaded-2026-10-21.pdf). Uses pdfplumber to read every table
and keeps rows whose first cell is a state/UT name followed by numbers.

Output columns: month, state, <numeric columns as published, in order>.
The numeric column order differs between releases, so the script prints the
header it found; map it to cgst/sgst/igst/cess/gross/refunds/net in COLUMN_MAP
once checked against the real PDF.

Reconciliation: state rows are summed and compared with the TOTAL row of the
same table; mismatches over 0.5% are written to the data-quality log.

Usage:  python src/ingest/gst.py [pdf ...]
"""
import re
import sys

import pandas as pd
import pdfplumber

from common import CLEAN, RAW, log_issue, upsert

STATE_FIX = {"jammu and kashmir": "Jammu & Kashmir", "andaman and nicobar islands": "Andaman & Nicobar Islands",
             "dadra and nagar haveli and daman and diu": "Dadra & Nagar Haveli and Daman & Diu",
             "orissa": "Odisha", "uttrakhand": "Uttarakhand", "pondicherry": "Puducherry"}
COLUMN_MAP = None  # e.g. ["cgst", "sgst", "igst", "cess", "gross", "refunds", "net"] after checking the PDF


def _num(x):
    s = re.sub(r"[,\s]", "", str(x))
    return pd.to_numeric(s, errors="coerce")


def tidy_state(name: str) -> str:
    n = re.sub(r"\s+", " ", str(name)).strip()
    return STATE_FIX.get(n.lower(), n.title().replace(" And ", " & "))


def parse(pdf_path) -> pd.DataFrame:
    m = re.search(r"gst_(\d{4}-\d{2})", str(pdf_path))
    if not m:
        raise ValueError(f"{pdf_path}: file name must contain gst_YYYY-MM")
    month = f"{m.group(1)}-01"
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for r in table:
                    cells = [c for c in r if c not in (None, "")]
                    if len(cells) < 3 or pd.notna(_num(cells[0])):
                        continue  # skip header rows and rows starting with a serial number
                    nums = [_num(c) for c in cells[1:]]
                    nums = [x for x in nums if pd.notna(x)]
                    if len(nums) >= 2:
                        rows.append([month, tidy_state(cells[0]), *nums])
    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError(f"{pdf_path}: no table rows found; layout may have changed")
    width = df.shape[1] - 2
    names = COLUMN_MAP if COLUMN_MAP and len(COLUMN_MAP) == width else [f"col{i + 1}" for i in range(width)]
    df.columns = ["month", "state", *names]
    return df


def reconcile(df: pd.DataFrame) -> None:
    total = df[df["state"].str.contains("total", case=False)]
    states = df[~df["state"].str.contains("total", case=False)]
    if total.empty:
        log_issue("GST", f"{df['month'].iloc[0]}: no TOTAL row found to reconcile", "check PDF by eye")
        return
    col = df.columns[-1]
    diff = abs(states[col].sum() - total[col].iloc[0]) / max(abs(total[col].iloc[0]), 1)
    if diff > 0.005:
        log_issue("GST", f"{df['month'].iloc[0]}: state rows differ from total by {diff:.2%}",
                  "inspect extraction", str(len(states)))


def main(paths=None) -> None:
    files = paths or sorted(RAW.glob("gst_*.pdf"))
    if not files:
        sys.exit("No gst_YYYY-MM_*.pdf files in data/raw")
    for p in files:
        df = parse(p)
        print(f"{p}: {len(df)} rows; columns {list(df.columns[2:])}")
        reconcile(df)
        states = df[~df["state"].str.contains("total", case=False)]
        n = upsert(states, CLEAN / "fact_gst_state.csv", ["month", "state"])
        print(f"  fact_gst_state.csv now {n} rows")


if __name__ == "__main__":
    main(sys.argv[1:] or None)
