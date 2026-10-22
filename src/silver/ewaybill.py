"""SILVER: e-way bill statistics (optional indicator), built from the bronze copies of the GST portal's Excel files.

Bronze input: first sheet of each ewaybill_* file, one row per state per month, three column groups:
WITHIN-STATE, OUTGOING TO OTHER STATES, INCOMING FROM OTHER STATES, each with number of suppliers, number of
e-way bills and assessable value (Rs crore).
Silver output (silver_ewaybill_state):
  month, state_code, state, {within,out,in}_{suppliers,ewb,value_cr}, source_file
The national total (within-state plus outgoing, since incoming is the same bills seen from the receiving state)
is computed in SQL when gold is built.

Check: total outgoing e-way bills across states vs total incoming; the gap is logged.

Usage:  python src/silver/ewaybill.py       (normally run through src/silver/build_silver.py)
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import bronze_files, bronze_sheets, connect, log_issue, replace_table  # noqa: E402

# FY2018-19 workbooks say INTRA STATE / Inter State Outward / Inter State Inward; later ones WITHIN-STATE / OUTGOING / INCOMING
GROUP_WORDS = {"within": ("within", "intra"), "out": ("outgoing", "outward"), "in": ("incoming", "inward")}


def _group_columns(sheet: pd.DataFrame) -> dict:
    """First column of each group (suppliers, bills, value), found from the header text so that
    older workbooks with another column order or without a group still load (missing group = blank)."""
    cols = {}
    for g, word in GROUP_WORDS.items():
        for i in range(min(8, len(sheet))):
            hit = [j for j, v in sheet.iloc[i].items() if any(w in str(v).lower() for w in word)]
            if hit:
                cols[g] = hit[0]
                break
    return cols


def parse(sheet: pd.DataFrame) -> pd.DataFrame:
    groups = _group_columns(sheet)
    rows = []
    for i in range(len(sheet)):
        code = pd.to_numeric(sheet.iloc[i, 0], errors="coerce")
        year, month = pd.to_numeric(sheet.iloc[i, 2], errors="coerce"), pd.to_numeric(sheet.iloc[i, 3], errors="coerce")
        if pd.isna(code) or pd.isna(year) or pd.isna(month):
            continue
        rec = {"month": f"{int(year)}-{int(month):02d}-01", "state_code": int(code),
               "state": str(sheet.iloc[i, 1]).strip().title().replace(" And ", " and ")}
        for g in GROUP_WORDS:
            c = groups.get(g)
            vals = [pd.to_numeric(sheet.iloc[i, c + k], errors="coerce") for k in range(3)] if c is not None else [float("nan")] * 3
            rec[f"{g}_suppliers"], rec[f"{g}_ewb"], rec[f"{g}_value_cr"] = vals
        rows.append(rec)
    return pd.DataFrame(rows)


def build(con) -> None:
    files = bronze_files(con, "ewaybill")
    if not files:
        raise SystemExit("No ewaybill files in bronze (run src/bronze/load_bronze.py)")
    frames = []
    for fid, name, _ in files:
        f = parse(next(iter(bronze_sheets(con, fid).values())))
        f["source_file"] = name
        frames.append(f)
    st = pd.concat(frames).drop_duplicates(["month", "state_code"], keep="last").sort_values(["month", "state_code"])
    n = replace_table(con, "silver_ewaybill_state", st)
    tot = st.groupby("month")[["out_ewb", "in_ewb"]].sum()
    gap = ((tot["out_ewb"] - tot["in_ewb"]).abs() / tot["out_ewb"]).max()
    log_issue("E-way bill", f"outgoing vs incoming bill counts differ by up to {gap:.1%} in a month",
              "kept both; national total uses within-state + outgoing only", str(len(tot)))
    print(f"silver_ewaybill_state: {n} rows ({st['month'].min()} to {st['month'].max()}); max out/in gap {gap:.1%}")


if __name__ == "__main__":
    con = connect()
    build(con)
    con.commit()
