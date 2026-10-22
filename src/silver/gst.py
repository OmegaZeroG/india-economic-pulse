"""SILVER: GST tables, built from the bronze copies of the Excel files downloaded from the GST portal.

Bronze sources:
  gst_national  monthly sheets (Apr-24 ... Aug-26) with this year and the same month a year earlier, so one file
                covers Apr 2023 - Aug 2026. Includes CESS.
  gst_state     one workbook per financial year: All-India, state-wise collection, state-wise refund.

Silver outputs:
  silver_gst_national  month, cgst_cr, sgst_cr, igst_cr, cess_cr, gross_cr, refunds_cr, net_cr,
                       domestic_ex_cess_cr, gross_ex_cess_cr, refunds_ex_cess_cr, net_ex_cess_cr, source_file
                       (gross = domestic + imports, *_cr includes cess; *_ex_cess_cr is CGST+SGST+IGST
                       only, the consistent series across the Mar 2026 end of compensation cess)
  silver_gst_state     month, state_code, state, cgst_cr, sgst_cr, igst_cr, gross_cr, refunds_cr, net_cr, source_file
                       DOMESTIC collections EXCLUDING cess: the state workbooks stopped publishing
                       cess after FY2024-25 (compensation cess was being phased out), so cess is left
                       out of every state month to keep the series consistent.

Checks written to docs/data_quality_log.md (tolerance 0.5 per cent):
  1. sum of state rows equals the All-India domestic row of the same workbook
  2. national series (national workbook) equals the All-India gross, ex-cess, of the state workbook
  3. gross - refunds = net in the national series

Usage:  python src/silver/gst.py       (normally run through src/silver/build_silver.py)
"""
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import bronze_files, bronze_sheets, connect, log_issue, replace_table  # noqa: E402

TOL = 0.005
STATE_FIX = {"CBIC": "OIDAR"}  # state code 99 was labelled CBIC in FY2023-24, OIDAR afterwards
NAT_COLS = {"total gross gst revenue": "gross_cr", "total refund": "refunds_cr",
            "total net gst revenue": "net_cr"}


# ----------------------------------------------------------------------------- national workbook
def _sheet_month(name: str) -> pd.Timestamp | None:
    m = re.match(r"([A-Za-z]{3})[-_ ](\d{2})$", name.strip())
    return pd.to_datetime(f"{m.group(1)} 20{m.group(2)}", format="%b %Y") if m else None


def _cur_prev_cols(sheet: pd.DataFrame) -> tuple[int, int]:
    """Columns holding this month and the same month a year earlier.

    Normal sheets: B = last year, C = this year. The Jan-25 sheet has an extra 'Daily'
    column, so there this-month is the 'MTD' column for 2025 and last-year the one for 2024.
    """
    head = " ".join(str(v).lower() for v in sheet.iloc[1:3].to_numpy().ravel())
    if "daily" in head:
        return 4, 3
    return 2, 1


def parse_national(sheets: dict) -> pd.DataFrame:
    rows = {}
    for name, sh in sheets.items():
        month = _sheet_month(name)
        if month is None:
            continue
        cur, prev = _cur_prev_cols(sh)
        lab = sh.iloc[:, 0].astype(str).str.strip()
        low = lab.str.lower()
        a3 = low[low.str.startswith("a.3")].index[0]
        sec = {k: low[low.str.startswith(k)].index[0] for k in ("a.3", "b.3", "c.3")}
        # the Dec-25 sheet lacks its "A.1. Domestic" heading: the domestic block then starts at the first CGST row
        h = low[low.str.startswith("a.1")]
        sec["a.1"] = h.index[0] if len(h) else low[low == "cgst"].index[0] - 1

        def ex_cess(start: int, col: int) -> float:
            """CGST + SGST + IGST rows directly under a section heading (cess excluded)."""
            vals = {}
            for k in range(start + 1, min(start + 6, len(low))):
                if low.iloc[k] in ("cgst", "sgst", "igst"):
                    vals[low.iloc[k]] = pd.to_numeric(sh.iloc[k, col])
            return sum(vals.values())

        for col, m in ((cur, month), (prev, month - pd.DateOffset(years=1))):
            rec = {"cess_cr": 0.0}
            for k in range(a3 + 1, min(a3 + 6, len(low))):                       # CGST, SGST, IGST, [CESS] then total
                l = low.iloc[k]
                if l in ("cgst", "sgst", "igst", "cess"):
                    rec[f"{l}_cr"] = pd.to_numeric(sh.iloc[k, col])
            for key, out in NAT_COLS.items():
                rec[out] = pd.to_numeric(sh.loc[low.str.startswith(key), col].iloc[0])
            rec["domestic_ex_cess_cr"] = ex_cess(sec["a.1"], col)
            rec["gross_ex_cess_cr"] = ex_cess(sec["a.3"], col)
            rec["refunds_ex_cess_cr"] = ex_cess(sec["b.3"], col)
            rec["net_ex_cess_cr"] = ex_cess(sec["c.3"], col)
            key = m.strftime("%Y-%m-%d")
            # a month's own sheet (current column) outranks the later 'last year' column
            if key not in rows or col == cur:
                rows[key] = {"month": key, **rec}
    df = pd.DataFrame(rows.values()).sort_values("month").reset_index(drop=True)
    return df[["month", "cgst_cr", "sgst_cr", "igst_cr", "cess_cr", "gross_cr", "refunds_cr", "net_cr",
               "domestic_ex_cess_cr", "gross_ex_cess_cr", "refunds_ex_cess_cr", "net_ex_cess_cr"]]


# ----------------------------------------------------------------------------- state workbooks
_MONTH_TEXT = re.compile(r"^([A-Za-z]{3})[a-z]*[-' ](\d{2}|\d{4})$")


def _as_month(v) -> pd.Timestamp | None:
    """A month header cell: a real date, or text like 'Apr-18' / 'April 2018'. Anything else is None."""
    if hasattr(v, "year"):
        return pd.Timestamp(v).to_period("M").to_timestamp()
    m = _MONTH_TEXT.match(str(v).strip())
    if not m:
        return None
    y = int(m.group(2))
    return pd.to_datetime(f"{m.group(1)} {y + 2000 if y < 100 else y}", format="%b %Y")


def _blocks(sheet: pd.DataFrame):
    """Return (header_row, {month: {label: column}}) using the CGST/SGST/IGST/[CESS]/TOTAL sub-header."""
    for i in range(min(12, len(sheet) - 1)):
        below = sheet.iloc[i + 1].astype(str).str.strip().str.upper()
        starts = {_as_month(v): j for j, v in sheet.iloc[i].items()
                  if _as_month(v) is not None and below.iloc[j] == "CGST"}
        if starts:
            sub = sheet.iloc[i + 1].astype(str).str.strip().str.upper()
            out = {}
            for m, c in starts.items():
                cols = {}
                for j in range(c, c + 5):
                    if sub.iloc[j] in ("CGST", "SGST", "IGST", "CESS", "TOTAL"):
                        cols[sub.iloc[j]] = j
                    if sub.iloc[j] == "TOTAL":
                        break
                out[m] = cols
            return i, out
    raise ValueError("no month header row found")


def _num(sheet, i, col):
    return pd.to_numeric(sheet.iloc[i, col], errors="coerce")


def _find_sheet(book: dict, *needles: str, exclude: tuple = ()) -> pd.DataFrame:
    """Pick the sheet whose lower-case name contains every needle (older workbooks name sheets differently)."""
    for name, sh in book.items():
        low = name.lower()
        if all(n in low for n in needles) and not any(e in low for e in exclude):
            return sh
    raise KeyError(f"no sheet with {needles} in {list(book)}")


def parse_all_india(sheet: pd.DataFrame) -> pd.DataFrame:
    """National monthly series from the All-India sheet of a state workbook.

    Same columns as the national workbook gives (see module docstring). Used for the checks and for months
    the national workbook does not cover (before Apr 2023). cess_cr is NaN where the sheet has no CESS column.
    """
    hdr, blocks = _blocks(sheet)
    lab = sheet.iloc[:, 0].astype(str).str.strip().str.lower()

    def find(*prefixes):
        for p in prefixes:
            hit = lab[lab.str.startswith(p)]
            if len(hit):
                return hit.index[0]
        return None

    # FY2020-21 onward has an All-India sheet with refunds and net. FY2017-18 to FY2019-20 workbooks only
    # have the collections sheet, whose bottom rows give domestic (Grand Total) and gross; no refunds exist.
    row = {"domestic": find("domestic", "grand total"), "gross": find("gross revenue"),
           "refunds": find("total refund"), "net": find("net gst revenue")}
    nan = float("nan")
    rows = []
    for m, c in blocks.items():
        ex = lambda r: nan if r is None else sum(_num(sheet, r, c[k]) for k in ("CGST", "SGST", "IGST"))
        tot = lambda r: nan if r is None else _num(sheet, r, c["TOTAL"])
        rows.append({
            "month": m.strftime("%Y-%m-%d"),
            "cgst_cr": _num(sheet, row["gross"], c["CGST"]), "sgst_cr": _num(sheet, row["gross"], c["SGST"]),
            "igst_cr": _num(sheet, row["gross"], c["IGST"]),
            "cess_cr": _num(sheet, row["gross"], c["CESS"]) if "CESS" in c else nan,
            "gross_cr": tot(row["gross"]), "refunds_cr": tot(row["refunds"]), "net_cr": tot(row["net"]),
            "domestic_ex_cess_cr": ex(row["domestic"]), "gross_ex_cess_cr": ex(row["gross"]),
            "refunds_ex_cess_cr": ex(row["refunds"]), "net_ex_cess_cr": ex(row["net"])})
    return pd.DataFrame(rows)


def parse_states(sheet: pd.DataFrame, name: str) -> pd.DataFrame:
    """State rows are the ones with a numeric state code in column 0. Values exclude cess."""
    hdr, blocks = _blocks(sheet)
    out = []
    for i in range(hdr + 2, len(sheet)):
        code, st = pd.to_numeric(sheet.iloc[i, 0], errors="coerce"), sheet.iloc[i, 1]
        if pd.isna(code) or pd.isna(st):
            continue
        st = STATE_FIX.get(str(st).strip(), str(st).strip())
        for m, c in blocks.items():
            cg, sg, ig = (_num(sheet, i, c[k]) for k in ("CGST", "SGST", "IGST"))
            out.append({"month": m.strftime("%Y-%m-%d"), "state_code": int(code), "state": st,
                        "cgst_cr": cg, "sgst_cr": sg, "igst_cr": ig, name: cg + sg + ig})
    return pd.DataFrame(out)


def load_state_year(x: dict):
    coll = _find_sheet(x, "collection")
    col = parse_states(coll, "gross_cr")
    try:
        ref = parse_states(_find_sheet(x, "refund", exclude=("india",)), "refunds_cr")[["month", "state_code", "refunds_cr"]]
        st = col.merge(ref, on=["month", "state_code"], how="left")
    except KeyError:                       # FY2017-18 to FY2019-20: no refund sheet, left blank (never filled)
        st = col.assign(refunds_cr=float("nan"))
    st["net_cr"] = st["gross_cr"] - st["refunds_cr"]
    try:
        national = parse_all_india(_find_sheet(x, "india"))
    except KeyError:
        national = parse_all_india(coll)
    return national, st


# ----------------------------------------------------------------------------- checks
def _rel(a, b) -> float:
    return abs(a - b) / abs(b) if b else float("inf")


def run_checks(nat: pd.DataFrame, st: pd.DataFrame, allindia: pd.DataFrame) -> int:
    bad, n = 0, 0
    tot = st.groupby("month")["gross_cr"].sum()
    for _, r in allindia.iterrows():
        n += 2
        d = _rel(tot.get(r["month"], float("nan")), r["domestic_ex_cess_cr"])
        if not d <= TOL:
            bad += 1
            log_issue("GST", f"{r['month'][:7]}: state rows differ from All-India domestic by {d:.2%}",
                      "inspect source workbook")
        nr = nat[nat["month"] == r["month"]]
        if len(nr):
            x = nr.iloc[0]
            d2 = _rel(x["cgst_cr"] + x["sgst_cr"] + x["igst_cr"], r["gross_ex_cess_cr"])
            if not d2 <= TOL:
                bad += 1
                log_issue("GST", f"{r['month'][:7]}: national workbook vs state workbook gross (ex-cess) "
                          f"differ by {d2:.2%}", "check revision between releases")
    for _, r in nat.iterrows():
        n += 1
        if pd.notna(r["net_cr"]) and _rel(r["gross_cr"] - r["refunds_cr"], r["net_cr"]) > TOL:
            bad += 1
            log_issue("GST", f"{r['month'][:7]}: gross - refunds != net", "inspect source workbook")
    print(f"checks: {n} comparisons, {bad} outside {TOL:.1%}")
    return bad


def build(con) -> None:
    nat_files = bronze_files(con, "gst_national")
    st_files = bronze_files(con, "gst_state")
    if not nat_files or not st_files:
        raise SystemExit("Need gst_national and gst_state files in bronze (run src/bronze/load_bronze.py)")
    nat_parts = []
    for fid, name, _ in nat_files:
        d = parse_national(bronze_sheets(con, fid))
        d["source_file"] = name
        nat_parts.append(d)
    nat = pd.concat(nat_parts).drop_duplicates("month", keep="last")
    all_parts, st_parts = [], []
    for fid, name, _ in st_files:
        national, st_year = load_state_year(bronze_sheets(con, fid))
        national["source_file"], st_year["source_file"] = name, name
        all_parts.append(national)
        st_parts.append(st_year)
    allindia, st = pd.concat(all_parts), pd.concat(st_parts)
    # The national workbook only reaches back to Apr 2023. Earlier months come from the All-India sheet of the
    # state workbooks, which carries the same rows (checked on overlapping months in docs/data_quality_log.md).
    older = allindia[~allindia["month"].isin(nat["month"])]
    if len(older):
        first = nat["month"].min()[:7]
        nat = pd.concat([nat, older]).sort_values("month").reset_index(drop=True)
        log_issue("GST", f"national months before {first} come from the All-India sheet of the state workbooks "
                  f"(the national workbook starts {first})",
                  "same row definitions; cess_cr blank where the sheet has no CESS column", str(len(older)))
    names = st.sort_values("month").drop_duplicates("state_code", keep="last").set_index("state_code")["state"]
    st["state"] = st["state_code"].map(names)
    failed = run_checks(nat, st, allindia)
    nat_cols = ["month", "cgst_cr", "sgst_cr", "igst_cr", "cess_cr", "gross_cr", "refunds_cr", "net_cr",
                "domestic_ex_cess_cr", "gross_ex_cess_cr", "refunds_ex_cess_cr", "net_ex_cess_cr", "source_file"]
    n1 = replace_table(con, "silver_gst_national", nat[nat_cols])
    n2 = replace_table(con, "silver_gst_state", st)
    print(f"silver_gst_national: {n1} rows ({nat['month'].min()} to {nat['month'].max()})")
    print(f"silver_gst_state: {n2} rows, {st['state_code'].nunique()} states/territories, "
          f"{st['month'].nunique()} months; failed checks: {failed}")


if __name__ == "__main__":
    con = connect()
    build(con)
    con.commit()
