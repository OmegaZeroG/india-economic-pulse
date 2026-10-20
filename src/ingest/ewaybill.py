"""Load e-way bill statistics (optional indicator) from the GST portal's E-Way Bill Excel files.

Input:  data/raw/ewaybill_FY*_*.xlsx, one sheet per financial year, one row per state per month,
        three column groups: WITHIN-STATE, OUTGOING TO OTHER STATES, INCOMING FROM OTHER STATES,
        each with number of suppliers, number of e-way bills and assessable value (Rs crore).
Output: data/clean/fact_ewaybill_state.csv
          month, state_code, state, {within,out,in}_{suppliers,ewb,value_cr}
        data/clean/fact_ewaybill_national.csv
          month, ewb_count, value_cr   (within-state + outgoing; incoming is the same bills seen from
          the receiving state, so adding it would double count)

Check: total outgoing e-way bills across states vs total incoming; the gap is logged.

Usage:  python src/ingest/ewaybill.py
"""
import pandas as pd

from common import CLEAN, RAW, log_issue, upsert

GROUPS = {"within": 4, "out": 7, "in": 10}  # first column of each group in the sheet


def parse(path) -> pd.DataFrame:
    sheet = pd.read_excel(path, header=None, sheet_name=0)
    rows = []
    for i in range(len(sheet)):
        code = pd.to_numeric(sheet.iloc[i, 0], errors="coerce")
        year, month = pd.to_numeric(sheet.iloc[i, 2], errors="coerce"), pd.to_numeric(sheet.iloc[i, 3], errors="coerce")
        if pd.isna(code) or pd.isna(year) or pd.isna(month):
            continue
        rec = {"month": f"{int(year)}-{int(month):02d}-01", "state_code": int(code),
               "state": str(sheet.iloc[i, 1]).strip().title().replace(" And ", " and ")}
        for g, c in GROUPS.items():
            rec[f"{g}_suppliers"], rec[f"{g}_ewb"], rec[f"{g}_value_cr"] = (
                pd.to_numeric(sheet.iloc[i, c + k], errors="coerce") for k in range(3))
        rows.append(rec)
    return pd.DataFrame(rows)


def main() -> None:
    files = sorted(RAW.glob("ewaybill_FY*.xlsx"))
    if not files:
        raise SystemExit("No ewaybill_FY*.xlsx in data/raw")
    st = pd.concat([parse(p) for p in files]).drop_duplicates(["month", "state_code"], keep="last")
    n1 = upsert(st, CLEAN / "fact_ewaybill_state.csv", ["month", "state_code"])
    nat = st.groupby("month").agg(
        ewb_count=("within_ewb", "sum"), out_ewb=("out_ewb", "sum"), in_ewb=("in_ewb", "sum"),
        within_value=("within_value_cr", "sum"), out_value=("out_value_cr", "sum")).reset_index()
    gap = ((nat["out_ewb"] - nat["in_ewb"]).abs() / nat["out_ewb"]).max()
    nat["ewb_count"] = nat["ewb_count"] + nat["out_ewb"]
    nat["value_cr"] = nat["within_value"] + nat["out_value"]
    n2 = upsert(nat[["month", "ewb_count", "value_cr"]], CLEAN / "fact_ewaybill_national.csv", ["month"])
    log_issue("E-way bill", f"outgoing vs incoming bill counts differ by up to {gap:.1%} in a month",
              "kept both; national total uses within-state + outgoing only", str(len(nat)))
    print(f"fact_ewaybill_state.csv {n1} rows, fact_ewaybill_national.csv {n2} rows "
          f"({nat['month'].min()} to {nat['month'].max()}); max out/in gap {gap:.1%}")


if __name__ == "__main__":
    main()
