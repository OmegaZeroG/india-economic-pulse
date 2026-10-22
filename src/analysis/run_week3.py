"""Run the Week 3 analysis and save results.

Writes to data/pulse.db: index_monthly, backtest_results (and the v_backtest_summary view reads them).
Writes to docs/results/: lag_tests.csv, backtest_summary.csv, robustness.csv, pca_weights.csv.

Usage:  python src/analysis/run_week3.py     (run src/gold/build_gold.py first so the database is current)
"""
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pulse  # noqa: E402

ROOT, DB, OUT = pulse.ROOT, pulse.DB, pulse.ROOT / "docs" / "results"


def robustness(panel22: pd.DataFrame) -> pd.DataFrame:
    """Re-score under different choices, to show the result does not hinge on one of them."""
    rows = []

    def add(label, res, scored=None):
        r = res if scored is None else res[res["month"].isin(scored)]
        s = pulse.summarise(r)
        for m in pulse.MODELS:
            rows.append({"variant": label, "model": m, "n_months": int(s.loc[m, "n_months"]),
                         "mae": s.loc[m, "mae"], "direction_hit_pct": s.loc[m, "direction_hit_pct"],
                         "mae_improvement_vs_best_baseline_pct": s.loc[m, "mae_improvement_vs_best_baseline_pct"]})

    base = pulse.rolling_origin(panel22, pulse.CORE)
    add("main: 7 indicators, base 2022-23, 12-month minimum training", base)
    add("8 indicators (adds e-way bills)", pulse.rolling_origin(panel22, pulse.WITH_EWAYBILL))
    add("minimum training 10 months", pulse.rolling_origin(panel22, pulse.CORE, min_train=10))
    add("minimum training 15 months", pulse.rolling_origin(panel22, pulse.CORE, min_train=15))
    shift = panel22.index[panel22["diwali_shift"].fillna(False).astype(bool)]
    add("excluding Diwali-shift months from scoring", base, scored=base["month"][~base["month"].isin(shift)].unique())
    # old IIP base: same predictors; with longer UPI/GST/e-way history this sample is much larger and
    # contains the COVID shock, so score it with and without the COVID-affected months.
    p11 = pulse.load_panel("2011-12", start=pulse.LONG_START)
    if len(pulse.complete_rows(p11, pulse.CORE_LONG)) > 15:
        add("IIP base 2011-12 (robustness series), COVID months included", pulse.rolling_origin(p11, pulse.CORE_LONG))
        add("IIP base 2011-12, COVID-affected months excluded", pulse.rolling_origin(p11, pulse.CORE_LONG, drop_covid=True))
        add("IIP base 2011-12, COVID excluded, without UPI (5 indicators)", pulse.rolling_origin(p11, pulse.NO_UPI, drop_covid=True))
        # Does the edge survive in calm conditions? Same long-sample models, scored only on later months.
        calm = pulse.rolling_origin(p11, pulse.NO_UPI, drop_covid=True)
        for since, label in (("2022-04-01", "post-rebound, scored from Apr 2022"), ("2023-04-01", "calm period, scored from Apr 2023")):
            add(f"IIP base 2011-12, no UPI, COVID excluded, {label}", calm, scored=calm["month"][calm["month"] >= since].unique())
    return pd.DataFrame(rows)


def save_sql(index: pd.DataFrame, res: pd.DataFrame, panel: pd.DataFrame) -> None:
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    schema = (ROOT / "sql" / "gold_schema.sql").read_text(encoding="utf-8")
    con.executescript(schema)
    con.execute("DELETE FROM index_monthly")
    con.execute("DELETE FROM backtest_results")
    idx = index.join(panel[[pulse.TARGET, "diwali_shift"]])
    con.executemany("INSERT INTO index_monthly VALUES (?,?,?,?,?,?)", [
        (m.strftime("%Y-%m-%d"), float(r.zscore_index), float(r.pca_index), int(r.n_indicators),
         float(r.iip), int(bool(r.diwali_shift))) for m, r in idx.iterrows()])
    con.executemany("INSERT INTO backtest_results VALUES (?,?,?,?,?,?,?)", [
        (r.month.strftime("%Y-%m-%d"), r.model, r.forecast, r.actual, r.prev_actual, r.abs_error,
         None if pd.isna(r.direction_correct) else float(r.direction_correct)) for r in res.itertuples()])
    con.executescript((ROOT / "sql" / "views.sql").read_text(encoding="utf-8"))
    con.commit()
    con.close()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    panel = pulse.load_panel()
    sample = pulse.complete_rows(panel, pulse.CORE)
    res = pulse.rolling_origin(panel, pulse.CORE)
    summary = pulse.summarise(res)
    index = pulse.full_sample_indices(panel, pulse.CORE)
    lags = pulse.lag_tests(panel, pulse.CORE, lags=(-1, 0, 1, 2))  # -1 = indicator one month AFTER the IIP month
    rob = robustness(panel)

    # long-history sample on the old IIP base (only large once UPI/GST/e-way bill history is extended)
    p11 = pulse.load_panel("2011-12", start=pulse.LONG_START)
    n11 = len(pulse.complete_rows(p11, pulse.CORE_LONG))
    lags11 = pulse.lag_tests(p11, pulse.CORE_LONG, lags=(-1, 0, 1, 2))
    lags11.to_csv(OUT / "lag_tests_old_base.csv", index=False)
    if n11 > 15:
        for label, kw in (("covid_included", {}), ("covid_excluded", {"drop_covid": True})):
            pulse.summarise(pulse.rolling_origin(p11, pulse.CORE_LONG, **kw)).to_csv(OUT / f"backtest_summary_old_base_{label}.csv")
    print(f"old-base (2011-12) sample: {n11} complete months")

    save_sql(index, res, panel)
    summary.to_csv(OUT / "backtest_summary.csv")
    lags.to_csv(OUT / "lag_tests.csv", index=False)
    rob.to_csv(OUT / "robustness.csv", index=False)
    index.attrs["pca_weights"].round(3).rename("weight").to_csv(OUT / "pca_weights.csv")

    test_months = pd.DatetimeIndex(res["month"].unique())
    print(f"sample: {len(sample)} complete months ({sample.index.min():%Y-%m} to {sample.index.max():%Y-%m}); "
          f"backtested {len(test_months)} months ({test_months.min():%Y-%m} to {test_months.max():%Y-%m})")
    print(summary.to_string())
    print(f"direction reference (repeat last move): {pulse.momentum_hit_rate(panel, test_months):.1f}%")
    print(f"PCA: first component explains {index.attrs['pca_explained_variance']:.0%} of variance; weights\n"
          f"{index.attrs['pca_weights'].round(2).to_string()}")
    best = lags[(~lags.exclude_covid) & (lags.start_shift_months == 0)].sort_values("corr", key=abs, ascending=False).iloc[0]
    print(f"best single lag: {best.indicator} at lag {best.lag_months}, r={best['corr']}, n={best.n_months}")


if __name__ == "__main__":
    main()
