"""Forecast IIP growth for one month, next to the naive baselines, and write the pre-registration file.

The model is fixed in advance (see MODEL below), so the forecast cannot be tuned after seeing results:
  * equal-weight z-score index of the 7 core indicators, fitted on every earlier complete month, mapped to
    IIP growth by a one-variable regression (the 'zscore_index' model of the backtest);
  * baselines: the average of the last 12 known IIP growth values, and the last known value;
  * intervals: empirical quantiles of that model's own rolling-origin errors (80% = 10th-90th, 90% = 5th-95th).

Modes
  --draft            write docs/forecasts/DRAFT_forecast_v<N>.md with whatever is available. Safe to repeat.
  --final            write docs/forecasts/forecast_v<N>.md and append a row to docs/forecasts/forecast_log.csv.
                     Refuses unless: every indicator for the target month is published, the git working tree is
                     clean (so the recorded commit hash is the code and data that produced the forecast), and the
                     file does not exist yet. A published forecast file is never edited; a correction is a new
                     version (--version 2, one clearly labelled forecast_v2.md).

Usage
  python src/analysis/forecast.py --target 2026-10 --draft
  python src/analysis/forecast.py --target 2026-10 --final
"""
import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pulse  # noqa: E402

ROOT = pulse.ROOT
FORECASTS = ROOT / "docs" / "forecasts"
LOG_CSV = FORECASTS / "forecast_log.csv"
MODEL = "zscore_index"
FEATURES = pulse.CORE
Q80, Q90 = (0.10, 0.90), (0.05, 0.95)
SOURCES = {  # label -> (table, month column, filter)
    "UPI": ("fact_upi", "month", ""), "GST (national)": ("fact_gst_national", "month", ""),
    "Fuel (PPAC)": ("fact_fuel", "month", ""), "E-way bills": ("fact_ewaybill_national", "month", ""),
    "IIP (base 2022-23)": ("fact_iip", "month", "WHERE base_year = '2022-23'"),
    "GDP (quarter start)": ("fact_gdp", "quarter_start", ""),
}
RAW_PREFIX = {"UPI": "upi_", "GST (national)": "gst_", "Fuel (PPAC)": "ppac_", "E-way bills": "ewaybill_",
              "IIP (base 2022-23)": "iip_2022-23_", "GDP (quarter start)": "gdp_"}


class MissingData(Exception):
    """Raised when an indicator for the target month has not been published yet."""


# --------------------------------------------------------------------------- helpers
def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def data_cutoff() -> pd.DataFrame:
    """Latest month in each source table, and the newest download date in the raw file names."""
    import sqlite3
    con = sqlite3.connect(pulse.DB)
    rows = []
    for label, (table, col, where) in SOURCES.items():
        latest = con.execute(f"SELECT MAX({col}) FROM {table} {where}").fetchone()[0]
        dl = ""
        if label in RAW_PREFIX:
            dates = [d for f in (ROOT / "data" / "raw").glob(f"{RAW_PREFIX[label]}*")
                     for d in re.findall(r"\d{4}-\d{2}-\d{2}", f.name)[-1:]]
            dl = max(dates) if dates else ""
        rows.append({"source": label, "latest period": latest[:7], "newest file downloaded": dl})
    con.close()
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- IIP forecast
def backtest_errors(panel: pd.DataFrame, target: pd.Timestamp) -> pd.DataFrame:
    """Rolling-origin results using only months before the target."""
    return pulse.rolling_origin(panel[panel.index < target], FEATURES)


def build_forecast(panel: pd.DataFrame, target: pd.Timestamp) -> dict:
    iip = panel[pulse.TARGET].dropna()
    prior = iip[iip.index < target]
    out = {"target": target, "last_known_iip_month": prior.index.max(), "last_known_iip": float(prior.iloc[-1]),
           "baseline_mean12": float(prior.tail(12).mean()), "baseline_last": float(prior.iloc[-1]),
           "baseline_mean12_window": (prior.tail(12).index.min(), prior.tail(12).index.max())}
    res = backtest_errors(panel, target)
    out["n_backtest"] = int(res["month"].nunique())
    err = {m: (g["actual"] - g["forecast"]).to_numpy() for m, g in res.groupby("model")}
    out["err"] = {m: {"q80": np.quantile(e, Q80), "q90": np.quantile(e, Q90)} for m, e in err.items()}
    summ = pulse.summarise(res)
    out["backtest"] = summ
    wide = res.pivot(index="month", columns="model", values="abs_error")
    out["win_rate"] = float((wide[MODEL] < wide["naive_mean12"]).mean() * 100)
    # the indicators for the target month
    x_t = panel.reindex([target])[FEATURES]
    missing = [c for c in FEATURES if x_t[c].isna().iloc[0]]
    out["missing"] = missing
    if missing:
        return out
    train = pulse.complete_rows(panel, FEATURES)
    train = train[train.index < target]
    s_tr, s_t = pulse.zscore_index(train[FEATURES], x_t)
    fit = pulse._fit_map(s_tr, train[pulse.TARGET].to_numpy())
    point = float(fit.predict(s_t.reshape(-1, 1))[0])
    out.update(point=point, n_train=len(train), train_range=(train.index.min(), train.index.max()),
               index_value=float(s_t[0]), slope=float(fit.coef_[0]), intercept=float(fit.intercept_),
               indicators={c: float(x_t[c].iloc[0]) for c in FEATURES})
    return out


# --------------------------------------------------------------------------- GDP call
def gdp_q2_call() -> dict:
    """Is Q2 growth above or below Q1? Uses how Q2's level compares with Q1's in earlier years.

    Growth in Q2 is Q2_level / Q2_level_last_year. If Q2 comes in at the usual seasonal fraction of Q1, growth
    follows. Q2 growth only matches Q1's if the Q2/Q1 ratio equals last year's, so the call compares the typical
    ratio with last year's. Four years of history: weak evidence, reported as low confidence.
    """
    import sqlite3
    con = sqlite3.connect(pulse.DB)
    g = pd.read_sql("SELECT fiscal_year, quarter, gdp_constant_cr AS lvl FROM v_gdp_latest", con)
    con.close()
    p = g.pivot(index="fiscal_year", columns="quarter", values="lvl")
    ratio = (p["Q2"] / p["Q1"]).dropna()
    fy = p.index[p["Q2"].isna() & p["Q1"].notna()][-1]
    prev = p.index[p.index < fy][-1]
    q1_growth = (p.loc[fy, "Q1"] / p.loc[prev, "Q1"] - 1) * 100
    breakeven = float(p.loc[prev, "Q2"] / p.loc[prev, "Q1"])   # Q2 growth == Q1 growth exactly when the ratio equals last year's
    med = float(ratio.median())
    implied = (p.loc[fy, "Q1"] * med / p.loc[prev, "Q2"] - 1) * 100
    return {"fiscal_year": fy, "q1_growth": float(q1_growth), "ratios": ratio.round(4).to_dict(),
            "median_ratio": med, "breakeven_ratio": float(breakeven), "implied_growth": float(implied),
            "call": "BELOW" if med < breakeven else "ABOVE",
            "n_below": int((ratio < breakeven).sum()), "n_years": int(len(ratio))}


# --------------------------------------------------------------------------- document
def render(f: dict, gdp: dict, cutoff: pd.DataFrame, version: int, status: str, commit: str, dirty: bool) -> str:
    t = f["target"]
    tm = f"{t:%B %Y}"
    e = f["err"][MODEL]
    eb = f["err"]["naive_mean12"]
    b = f["backtest"]
    have = "point" in f
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    pt = f"{f['point']:.1f}%" if have else "**pending** (indicators for the target month not yet published)"
    lines = [f"# Forecast v{version}: {tm} IIP growth" + ("  (DRAFT, NOT PRE-REGISTERED)" if status == "DRAFT" else ""), ""]
    if status == "DRAFT":
        lines += ["> **DRAFT: an illustration of the method, not a published forecast.** October 2026 indicators were not available "
                  "when this was generated, so the model forecast is pending; the baseline, intervals, success rule and GDP call are real. "
                  "To produce a final file once the data exists: `python src/analysis/forecast.py --target " + f"{t:%Y-%m}" + " --final` "
                  "(refused unless every indicator is published, the git tree is clean and no earlier file exists).", ""]
    lines += ["## 1. When and with what", "",
              f"- **Made on:** {now}",
              f"- **Model version (git commit):** `{commit}`" + ("  (working tree has uncommitted changes)" if dirty else ""),
              f"- **Target:** year-on-year growth of the Index of Industrial Production for {tm}, base 2022-23, first release by MoSPI (expected around the 28th of {(t + pd.DateOffset(months=1)):%B %Y}; check the calendar for a shifted date).",
              "- **Data available when this was made:**", "",
              "| Source | Latest period | Newest file downloaded |", "|---|---|---|"]
    lines += [f"| {r['source']} | {r['latest period']} | {r['newest file downloaded']} |" for _, r in cutoff.iterrows()]
    lines += ["", f"Last known IIP value: **{f['last_known_iip']:.1f}%** for {f['last_known_iip_month']:%B %Y}.", ""]
    lines += ["## 2. Forecast", "", "| | Point | 80% interval | 90% interval |", "|---|---|---|---|"]
    if have:
        lines += [f"| **Index model** (equal-weight z-score index, 7 indicators) | **{f['point']:.1f}%** | "
                  f"{f['point'] + e['q80'][0]:.1f}% to {f['point'] + e['q80'][1]:.1f}% | {f['point'] + e['q90'][0]:.1f}% to {f['point'] + e['q90'][1]:.1f}% |"]
    else:
        lines += [f"| **Index model** | {pt} | point forecast {e['q80'][0]:+.1f} to {e['q80'][1]:+.1f} | point forecast {e['q90'][0]:+.1f} to {e['q90'][1]:+.1f} |"]
    m12 = f["baseline_mean12"]
    lines += [f"| Baseline: average of last 12 months ({f['baseline_mean12_window'][0]:%b %Y} to {f['baseline_mean12_window'][1]:%b %Y}) | {m12:.1f}% | "
              f"{m12 + eb['q80'][0]:.1f}% to {m12 + eb['q80'][1]:.1f}% | {m12 + eb['q90'][0]:.1f}% to {m12 + eb['q90'][1]:.1f}% |",
              f"| Baseline: last known value | {f['baseline_last']:.1f}% | n/a | n/a |", "",
              f"Intervals are the 10th-90th and 5th-95th percentiles of each model's own out-of-sample errors over {f['n_backtest']} backtested months "
              "(Apr 2024 onward), added to the point forecast. With so few errors the interval edges are rough.", ""]
    if have:
        lines += [f"Fitted on {f['n_train']} complete months ({f['train_range'][0]:%b %Y} to {f['train_range'][1]:%b %Y}). "
                  f"Index value for {tm}: {f['index_value']:+.2f}; IIP growth = {f['intercept']:.2f} + {f['slope']:.2f} x index.", "",
                  "| Indicator (YoY growth, %) | " + tm + " |", "|---|---|"]
        lines += [f"| {k} | {v:.1f} |" for k, v in f["indicators"].items()]
        lines.append("")
    else:
        lines += [f"Waiting for: {', '.join(f['missing'])}.", ""]
    lines += ["**Known distortion:** Diwali was on 20 Oct 2025 and falls on 8 Nov 2026, so October 2026 is a Diwali-shift month. "
              "Its year-on-year comparison is against a festive October, and indicators and IIP are both affected. The model has no festival term.", ""]
    lines += ["## 3. What the backtest says about trusting it", "",
              f"Over {f['n_backtest']} out-of-sample months the index model's mean absolute error was **{b.loc[MODEL, 'mae']:.2f}** points against "
              f"**{b.loc['naive_mean12', 'mae']:.2f}** for the 12-month-average baseline ({b.loc[MODEL, 'mae_improvement_vs_best_baseline_pct']:+.1f}%). "
              f"It was closer than the baseline in {f['win_rate']:.0f}% of months. Direction vs the previous month was right in {b.loc[MODEL, 'direction_hit_pct']:.0f}% of months. "
              "On a longer 2019-26 sample (old IIP base) the index beat the baseline during the large 2020-22 swings but not in calm periods. "
              "**So the baseline is a serious rival, and the most likely outcome is that it is as close as the model or closer.** "
              "Full evidence: `notebooks/03_index_and_backtest.ipynb`.", ""]
    lines += ["## 4. Rule for calling it a success (fixed before the data exist)", "",
              f"1. **Main rule:** the index model's point forecast is closer to the actual {tm} IIP growth than the 12-month-average baseline forecast.",
              "2. **Also reported:** whether the actual falls inside the 80% interval, and whether the sign of the move from the previous month was called correctly.",
              "3. The result goes into `docs/forecasts/scoring.md` whether it is a hit or a miss. The forecast file is never edited after publication.", ""]
    lines += ["## 5. Q2 FY2026-27 GDP: above or below Q1?", "",
              f"**Call: {gdp['call']}.** Q2 FY27 real GDP growth (MoSPI first estimate, expected 30 Nov 2026) will be {gdp['call'].lower()} Q1 FY27's "
              f"{gdp['q1_growth']:.2f}% (compared with Q1 as published in the same release, in case it is revised). **Confidence: low.**", "",
              f"Reasoning: Q2 growth is Q2's level against last year's Q2. Q2's level as a fraction of Q1's was {', '.join(f'FY{k} {v:.3f}' for k, v in gdp['ratios'].items())}; "
              f"to match Q1's growth, Q2 FY27 would need {gdp['breakeven_ratio']:.4f}, the highest of the four years. "
              f"At the typical ratio ({gdp['median_ratio']:.4f}) growth would be about {gdp['implied_growth']:.1f}%. In {gdp['n_below']} of {gdp['n_years']} years the ratio was below the break-even. "
              "Only four years of history, so this is a weak basis. A test of whether IIP growth predicts the direction of GDP growth found no relationship (signs agreed in 7 of 12 quarters), so IIP is not used for this call.", ""]
    if status == "FINAL":
        lines += ["---", "Pre-registered forecasts are not edited. A later correction is a separately named `forecast_v2.md`."]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True, help="month to forecast, e.g. 2026-10")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--draft", action="store_true")
    mode.add_argument("--final", action="store_true")
    ap.add_argument("--version", type=int, default=1)
    a = ap.parse_args()
    target = pd.Timestamp(a.target + "-01")

    panel = pulse.load_panel()
    f = build_forecast(panel, target)
    gdp = gdp_q2_call()
    cutoff = data_cutoff()
    commit = git("rev-parse", "--short", "HEAD")
    dirty = bool(git("status", "--porcelain"))
    FORECASTS.mkdir(parents=True, exist_ok=True)

    if a.draft:
        path = FORECASTS / f"DRAFT_forecast_v{a.version}.md"
        path.write_text(render(f, gdp, cutoff, a.version, "DRAFT", commit, dirty), encoding="utf-8")
        print(f"draft written: {path.relative_to(ROOT)}")
        print("model forecast:", f"{f['point']:.2f}%" if "point" in f else f"pending ({', '.join(f['missing'])})")
        print(f"baseline (12-month average): {f['baseline_mean12']:.2f}%   last known: {f['baseline_last']:.2f}%")
        return 0

    path = FORECASTS / f"forecast_v{a.version}.md"
    problems = []
    if path.exists():
        problems.append(f"{path.name} already exists; published forecasts are never edited (use --version {a.version + 1} for a clearly labelled correction)")
    if f["missing"]:
        problems.append(f"indicators not yet published for {target:%B %Y}: {', '.join(f['missing'])}")
    if dirty:
        problems.append("git working tree has uncommitted changes; commit data and code first so the recorded commit hash is exact")
    if a.version > 1 and not (FORECASTS / "forecast_v1.md").exists():
        problems.append("forecast_v1.md must exist before a v2")
    if problems:
        print("REFUSING to write a final forecast:\n  - " + "\n  - ".join(problems))
        return 1
    path.write_text(render(f, gdp, cutoff, a.version, "FINAL", commit, False), encoding="utf-8")
    row = pd.DataFrame([{"target_month": f"{target:%Y-%m-%d}", "version": a.version,
                         "made_on": datetime.now().astimezone().isoformat(timespec="seconds"), "git_commit": commit,
                         "model": MODEL, "point_pct": round(f["point"], 3),
                         "lo80_pct": round(f["point"] + f["err"][MODEL]["q80"][0], 3), "hi80_pct": round(f["point"] + f["err"][MODEL]["q80"][1], 3),
                         "lo90_pct": round(f["point"] + f["err"][MODEL]["q90"][0], 3), "hi90_pct": round(f["point"] + f["err"][MODEL]["q90"][1], 3),
                         "baseline_mean12_pct": round(f["baseline_mean12"], 3), "baseline_last_pct": round(f["baseline_last"], 3),
                         "gdp_call": gdp["call"], "gdp_threshold_pct": round(gdp["q1_growth"], 2), "actual_pct": np.nan}])
    if LOG_CSV.exists():
        row = pd.concat([pd.read_csv(LOG_CSV), row]).drop_duplicates(["target_month", "version"], keep="last")
    row.sort_values(["target_month", "version"]).to_csv(LOG_CSV, index=False)
    print(f"FINAL forecast written: {path.relative_to(ROOT)} (commit {commit})\nNext: git add docs/forecasts; "
          f"git commit; git tag forecast-v{a.version}; git push --follow-tags")
    return 0


if __name__ == "__main__":
    sys.exit(main())
