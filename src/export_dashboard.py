"""Prepare the small, labelled data files behind the web dashboard (powerbi/dashboard_data/*.csv).

Reads data/pulse.db and docs/results; adds readable labels, drops empty rows and computes the correlation table
(indicator vs IIP growth, lag 0) for four periods. Re-run after `python src/run_all.py`.

Usage:  python src/export_dashboard.py
"""
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent / "analysis"))
import pulse  # noqa: E402

ROOT = pulse.ROOT
OUT = ROOT / "powerbi" / "dashboard_data"
INDICATORS = {
    "upi_daily_volume_mn": "UPI daily volume", "upi_value_cr": "UPI value", "gst_net_ex_cess_cr": "GST net (ex-cess)",
    "gst_gross_ex_cess_cr": "GST gross (ex-cess)", "fuel_diesel_kt": "Diesel", "fuel_petrol_kt": "Petrol",
    "fuel_atf_kt": "Jet fuel (ATF)", "fuel_lpg_kt": "LPG", "fuel_bitumen_kt": "Bitumen",
    "ewaybill_value_cr": "E-way bill value",
}
MODELS = {"naive_last": "Last month's value", "naive_mean12": "12-month average", "zscore_index": "Z-score index",
          "pca_index": "PCA index", "regression": "Regression"}


def correlations() -> pd.DataFrame:
    """Lag-0 correlation of each indicator's growth with old-base IIP growth, four periods, COVID months removed
    except in the first column."""
    p = pulse.load_panel("2011-12", start=pulse.LONG_START)
    ok = p[~p["covid_affected"].astype(bool)]
    cols = {"All months, Apr 2019 - Mar 2026": p, "COVID months removed": ok,
            "Since Apr 2022": ok[ok.index >= "2022-04-01"], "Since Apr 2023 (calm)": ok[ok.index >= "2023-04-01"]}
    rows = []
    for key, label in INDICATORS.items():
        if key not in pulse.CORE_LONG:
            continue
        rec = {"indicator": key, "label": label}
        for name, d in cols.items():
            c = d[[key, "iip"]].dropna()
            rec[name] = round(float(c[key].corr(c["iip"])), 2)
        rec["months_covid_removed"] = int(ok[[key, "iip"]].dropna().shape[0])
        rows.append(rec)
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(pulse.DB)

    g = pd.read_sql("SELECT month, indicator, yoy_pct FROM v_growth_monthly WHERE yoy_pct IS NOT NULL", con)
    g["label"] = g["indicator"].map(INDICATORS)
    g["yoy_pct"] = g["yoy_pct"].round(2)
    g[["month", "indicator", "label", "yoy_pct"]].to_csv(OUT / "growth.csv", index=False)

    s = pd.read_sql("SELECT month, state, gross_cr FROM fact_gst_state", con)
    s["gross_cr"] = s["gross_cr"].round(1)
    s.to_csv(OUT / "gst_state.csv", index=False)

    i = pd.read_sql("SELECT month, zscore_index, iip_yoy_pct FROM index_monthly ORDER BY month", con)
    i["zscore_index"] = i["zscore_index"].round(3)
    i.to_csv(OUT / "index_monthly.csv", index=False)

    b = pd.read_sql("SELECT month, model, forecast, actual, abs_error FROM backtest_results ORDER BY month", con)
    b["label"] = b["model"].map(MODELS)
    b[["forecast", "actual", "abs_error"]] = b[["forecast", "actual", "abs_error"]].round(3)
    b.to_csv(OUT / "backtest_results.csv", index=False)

    sm = pd.read_sql("SELECT * FROM v_backtest_summary", con)
    sm["label"] = sm["model"].map(MODELS)
    sm.to_csv(OUT / "backtest_summary.csv", index=False)
    con.close()

    r = pd.read_csv(ROOT / "docs" / "results" / "robustness.csv")
    r["label"] = r["model"].map(MODELS)
    r.to_csv(OUT / "robustness.csv", index=False)
    correlations().to_csv(OUT / "correlations.csv", index=False)
    for f in sorted(OUT.glob("*.csv")):
        print(f"  {f.name:<22}{sum(1 for _ in open(f, encoding='utf-8')) - 1:>6} rows  {f.stat().st_size / 1024:>7.1f} KB")


if __name__ == "__main__":
    main()
