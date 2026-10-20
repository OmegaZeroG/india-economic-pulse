"""Load GST tables from the Excel files downloaded from the GST portal's Statistics page.

Inputs (data/raw):
  gst_national_FY*_*.xlsx  monthly sheets (Apr-24 ... Aug-26) with this year and the same month a
                           year earlier, so one file covers Apr 2023 - Aug 2026. Includes CESS.
  gst_state_FY*_*.xlsx     one per financial year: All-India, state-wise collection, state-wise refund.

Outputs (data/clean):
  fact_gst_national.csv  month, cgst_cr, sgst_cr, igst_cr, cess_cr, gross_cr, refunds_cr, net_cr,
                         domestic_ex_cess_cr, gross_ex_cess_cr, refunds_ex_cess_cr, net_ex_cess_cr
                         (gross = domestic + imports, *_cr includes cess; *_ex_cess_cr is CGST+SGST+IGST
                         only, the consistent series across the Mar 2026 end of compensation cess)
  fact_gst_state.csv     month, state_code, state, cgst_cr, sgst_cr, igst_cr, gross_cr, refunds_cr, net_cr
                         DOMESTIC collections EXCLUDING cess: the state workbooks stopped publishing
                         cess after FY2024-25 (compensation cess was being phased out), so cess is left
                         out of every state month to keep the series consistent.

Checks written to docs/data_quality_log.md (tolerance 0.5 per cent):
  1. sum of state rows equals the All-India domestic row of the same workbook
  2. national series (national workbook) equals the All-India gross, ex-cess, of the state workbook
  3. gross - refunds = net in the national series

Usage:  python src/ingest/gst.py
"""
import re

import pandas as pd

from common import CLEAN, RAW, log_issue, upsert

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


def parse_national(path) -> pd.DataFrame:
    rows = {}
    for name, sh in pd.read_excel(path, header=None, sheet_name=None).items():
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
def _blocks(sheet: pd.DataFrame):
    """Return (header_row, {month: {label: column}}) using the CGST/SGST/IGST/[CESS]/TOTAL sub-header."""
    for i in range(min(12, len(sheet))):
        starts = {pd.Timestamp(v).to_period("M").to_timestamp(): j
                  for j, v in sheet.iloc[i].items() if hasattr(v, "year")}
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


def parse_all_india_domestic_gross(sheet: pd.DataFrame) -> pd.DataFrame:
    """Per month: cgst+sgst+igst of 'Domestic' and of 'Gross Revenue' (ex-cess), from the All-India sheet."""
    hdr, blocks = _blocks(sheet)
    lab = sheet.iloc[:, 0].astype(str).str.strip().str.lower()
    dom, gross = lab[lab == "domestic"].index[0], lab[lab == "gross revenue"].index[0]
    return pd.DataFrame([{
        "month": m.strftime("%Y-%m-%d"),
        "domestic_exc_cess": sum(_num(sheet, dom, c[k]) for k in ("CGST", "SGST", "IGST")),
        "gross_exc_cess": sum(_num(sheet, gross, c[k]) for k in ("CGST", "SGST", "IGST"))}
        for m, c in blocks.items()])


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


def load_state_year(path):
    x = pd.read_excel(path, header=None, sheet_name=None)
    col = parse_states(x["Collections-Statewise"], "gross_cr")
    ref = parse_states(x["Refund-Statewise"], "refunds_cr")[["month", "state_code", "refunds_cr"]]
    st = col.merge(ref, on=["month", "state_code"], how="left")
    st["net_cr"] = st["gross_cr"] - st["refunds_cr"]
    return parse_all_india_domestic_gross(x["GST_Revenue-All_India"]), st


# ----------------------------------------------------------------------------- checks
def _rel(a, b) -> float:
    return abs(a - b) / abs(b) if b else float("inf")


def run_checks(nat: pd.DataFrame, st: pd.DataFrame, allindia: pd.DataFrame) -> int:
    bad, n = 0, 0
    tot = st.groupby("month")["gross_cr"].sum()
    for _, r in allindia.iterrows():
        n += 2
        d = _rel(tot.get(r["month"], float("nan")), r["domestic_exc_cess"])
        if not d <= TOL:
            bad += 1
            log_issue("GST", f"{r['month'][:7]}: state rows differ from All-India domestic by {d:.2%}",
                      "inspect source workbook")
        nr = nat[nat["month"] == r["month"]]
        if len(nr):
            x = nr.iloc[0]
            d2 = _rel(x["cgst_cr"] + x["sgst_cr"] + x["igst_cr"], r["gross_exc_cess"])
            if not d2 <= TOL:
                bad += 1
                log_issue("GST", f"{r['month'][:7]}: national workbook vs state workbook gross (ex-cess) "
                          f"differ by {d2:.2%}", "check revision between releases")
    for _, r in nat.iterrows():
        n += 1
        if _rel(r["gross_cr"] - r["refunds_cr"], r["net_cr"]) > TOL:
            bad += 1
            log_issue("GST", f"{r['month'][:7]}: gross - refunds != net", "inspect source workbook")
    print(f"checks: {n} comparisons, {bad} outside {TOL:.1%}")
    return bad


def main() -> None:
    nat_files = sorted(RAW.glob("gst_national_FY*.xlsx"))
    st_files = sorted(RAW.glob("gst_state_FY*.xlsx"))
    if not nat_files or not st_files:
        raise SystemExit("Need gst_national_FY*.xlsx and gst_state_FY*.xlsx in data/raw")
    nat = pd.concat([parse_national(p) for p in nat_files]).drop_duplicates("month", keep="last")
    parts = [load_state_year(p) for p in st_files]
    allindia = pd.concat([a for a, _ in parts])
    st = pd.concat([s for _, s in parts])
    names = st.sort_values("month").drop_duplicates("state_code", keep="last").set_index("state_code")["state"]
    st["state"] = st["state_code"].map(names)
    failed = run_checks(nat, st, allindia)
    n1 = upsert(nat, CLEAN / "fact_gst_national.csv", ["month"])
    n2 = upsert(st, CLEAN / "fact_gst_state.csv", ["month", "state_code"])
    print(f"fact_gst_national.csv: {n1} rows ({nat['month'].min()} to {nat['month'].max()})")
    print(f"fact_gst_state.csv: {n2} rows, {st['state_code'].nunique()} states/territories, "
          f"{st['month'].nunique()} months; failed checks: {failed}")


if __name__ == "__main__":
    main()
