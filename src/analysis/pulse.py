"""Activity index and backtest for India Economic Pulse.

Everything here works on year-on-year (YoY) growth rates, not levels, so seasonality and trend drop out
and indicators are comparable. The target is monthly IIP growth (MoSPI, base 2022-23 by default).

Pieces
  load_panel         monthly YoY panel from data/pulse.db plus Diwali-shift and COVID flags
  naive baselines    last month's IIP growth, and the mean of the last 12 months (fixed BEFORE any model)
  lag_tests          correlation of each indicator with IIP at lags 0, 1, 2 (with / without COVID,
                     and with nearby sample start dates)
  index methods      equal-weight z-score average, first principal component, small regression
  rolling_origin     for each month: fit only on earlier months, forecast that month, move forward

Timing assumption: the indicators for month t (UPI, GST, fuel) are all published before IIP for month t,
so the model may use x[t]. The last IIP value known when forecasting month t is that of month t-1.
"""
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import LinearRegression, Ridge

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "pulse.db"

CORE = ["upi_daily_volume_mn", "upi_value_cr", "gst_net_ex_cess_cr", "fuel_diesel_kt",
        "fuel_bitumen_kt", "fuel_atf_kt", "fuel_petrol_kt"]
# Long-history sample (old IIP base): net GST only exists from Apr 2020 (no refund data before FY2020-21), so
# gross GST (CGST+SGST+IGST, ex-cess) stands in for net GST there. E-way bills (from Apr 2018) join as the 8th.
CORE_LONG = [("gst_gross_ex_cess_cr" if c == "gst_net_ex_cess_cr" else c) for c in CORE]
WITH_EWAYBILL = CORE + ["ewaybill_value_cr"]
TARGET = "iip"
MODELS = ["naive_last", "naive_mean12", "zscore_index", "pca_index", "regression"]
BASELINES = ["naive_last", "naive_mean12"]


# --------------------------------------------------------------------------- data
LONG_START = "2019-04-01"   # long-history sample: Apr 2018 is the first normal base month (GST began Jul 2017 with near-empty first months)
NO_UPI = [c for c in CORE_LONG if not c.startswith("upi_")]


def load_panel(base_year: str = "2022-23", db: Path = DB, start: str | None = None) -> pd.DataFrame:
    """Monthly YoY growth (%) for every indicator, the IIP target, and calendar flags. `start` trims early months."""
    con = sqlite3.connect(db)
    g = pd.read_sql("SELECT month, indicator, yoy_pct FROM v_growth_monthly", con, parse_dates=["month"])
    iip = pd.read_sql("SELECT month, yoy_growth_pct AS iip FROM v_iip_latest WHERE base_year = ?",
                      con, params=(base_year,), parse_dates=["month"]).set_index("month")
    cal = pd.read_sql("SELECT month_start AS month, is_diwali_month, is_covid_month FROM dim_date",
                      con, parse_dates=["month"]).set_index("month")
    con.close()
    panel = g.pivot(index="month", columns="indicator", values="yoy_pct").join(iip, how="outer")
    # Diwali moves between October and November, which distorts YoY in those two months:
    # flag a month when Diwali fell in it this year but not a year earlier, or the other way round.
    cal["diwali_shift"] = (cal["is_diwali_month"] != cal["is_diwali_month"].shift(12)) & (cal.index.month.isin([10, 11]))
    panel = panel.join(cal[["is_covid_month", "diwali_shift"]], how="left")
    # Apr-Jun 2020 is the COVID shock (plan flag). Apr-Jun 2021 compares against that shock, so its YoY is
    # a base effect: both stretches are treated as "COVID-affected" when COVID is excluded.
    base_effect = (panel.index >= "2021-04-01") & (panel.index <= "2021-06-01")
    panel["covid_affected"] = (panel["is_covid_month"].fillna(0) == 1) | base_effect
    panel = panel.loc[panel[[TARGET] + CORE].notna().any(axis=1)].sort_index()
    return panel.loc[start:] if start else panel


def complete_rows(panel: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """Months with the target and every feature present (the usable modelling sample)."""
    return panel.dropna(subset=features + [TARGET])


# --------------------------------------------------------------------------- lag tests
def _fisher_ci(r: float, n: int) -> tuple[float, float]:
    if n <= 3 or abs(r) >= 1:
        return (np.nan, np.nan)
    z, se = np.arctanh(r), 1 / np.sqrt(n - 3)
    return float(np.tanh(z - 1.96 * se)), float(np.tanh(z + 1.96 * se))


def lag_tests(panel: pd.DataFrame, features: list[str], lags=(0, 1, 2), start_shifts=(0, 3, 6)) -> pd.DataFrame:
    """Correlation of indicator growth at t-k with IIP growth at t, for k in `lags`.

    Variants: all months vs excluding COVID months (Apr-Jun 2020), and the sample start moved later by
    0 / 3 / 6 months to see whether the result depends on the chosen start date.
    """
    rows = []
    first = complete_rows(panel, features).index.min()
    for feat in features:
        for k in lags:
            x = panel[feat].shift(k)
            both = pd.concat([x, panel[TARGET], panel["covid_affected"]], axis=1, keys=["x", "y", "covid"]).dropna(subset=["x", "y"])
            for covid_ex in (False, True):
                for shift in start_shifts:
                    d = both[both.index >= first + pd.DateOffset(months=shift)]
                    if covid_ex:
                        d = d[~d["covid"].astype(bool)]
                    if len(d) < 6:
                        continue
                    r = float(np.corrcoef(d["x"], d["y"])[0, 1])
                    lo, hi = _fisher_ci(r, len(d))
                    rows.append({"indicator": feat, "lag_months": k, "exclude_covid": covid_ex,
                                 "start_shift_months": shift, "start": d.index.min().strftime("%Y-%m"),
                                 "n_months": len(d), "corr": round(r, 3), "ci95_low": round(lo, 3),
                                 "ci95_high": round(hi, 3)})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- index methods
def _standardise(train: pd.DataFrame, x_new: pd.DataFrame | pd.Series):
    mu, sd = train.mean(), train.std(ddof=0).replace(0, 1)
    return (train - mu) / sd, (x_new - mu) / sd


def _fit_map(score_train: np.ndarray, y_train: np.ndarray) -> LinearRegression:
    """Map an index score to IIP growth with a one-variable regression (fitted on training months only)."""
    return LinearRegression().fit(score_train.reshape(-1, 1), y_train)


def zscore_index(train_x: pd.DataFrame, x_new: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    ztr, znew = _standardise(train_x, x_new)
    return ztr.mean(axis=1).to_numpy(), znew.mean(axis=1).to_numpy()


def pca_index(train_x: pd.DataFrame, x_new: pd.DataFrame, train_y: np.ndarray):
    """First principal component of the standardised indicators. Sign is fixed so the index rises with IIP."""
    ztr, znew = _standardise(train_x, x_new)
    pca = PCA(n_components=1).fit(ztr)
    s_tr, s_new = pca.transform(ztr).ravel(), pca.transform(znew).ravel()
    if np.corrcoef(s_tr, train_y)[0, 1] < 0:
        s_tr, s_new = -s_tr, -s_new
        sign = -1
    else:
        sign = 1
    weights = pd.Series(sign * pca.components_[0], index=train_x.columns)
    return s_tr, s_new, weights, float(pca.explained_variance_ratio_[0])


def small_regression(train_x: pd.DataFrame, train_y: np.ndarray, x_new: pd.DataFrame, k: int = 2):
    """Ridge on the k indicators most correlated with IIP in the TRAINING months only (selection cannot peek)."""
    corr = train_x.apply(lambda c: abs(np.corrcoef(c, train_y)[0, 1])).fillna(0)
    chosen = list(corr.sort_values(ascending=False).index[:k])
    ztr, znew = _standardise(train_x[chosen], x_new[chosen])
    model = Ridge(alpha=1.0).fit(ztr, train_y)
    return model.predict(znew), chosen


# --------------------------------------------------------------------------- backtest
def rolling_origin(panel: pd.DataFrame, features: list[str], min_train: int = 12,
                   drop_covid: bool = False) -> pd.DataFrame:
    """For each month t after `min_train` complete months: fit on earlier months only and forecast t.

    Baselines use the full IIP history before t (they are allowed every number a forecaster would know).
    With drop_covid=True the COVID-affected months (see load_panel) are removed from training, scoring and
    the baselines' history. Returns one row per month and model with forecast, actual and last known IIP growth.
    """
    if drop_covid:
        panel = panel[~panel["covid_affected"].astype(bool)]
    sample = complete_rows(panel, features)
    iip = panel[TARGET].dropna()
    out = []
    for i in range(min_train, len(sample)):
        t = sample.index[i]
        train = sample.iloc[:i]
        prior = iip[iip.index < t]
        y_prev = float(prior.iloc[-1])
        x_t = sample[features].iloc[[i]]
        fc = {"naive_last": y_prev, "naive_mean12": float(prior.tail(12).mean())}
        s_tr, s_t = zscore_index(train[features], x_t)
        fc["zscore_index"] = float(_fit_map(s_tr, train[TARGET].to_numpy()).predict(s_t.reshape(-1, 1))[0])
        s_tr, s_t, _, _ = pca_index(train[features], x_t, train[TARGET].to_numpy())
        fc["pca_index"] = float(_fit_map(s_tr, train[TARGET].to_numpy()).predict(s_t.reshape(-1, 1))[0])
        pred, _ = small_regression(train[features], train[TARGET].to_numpy(), x_t)
        fc["regression"] = float(pred[0])
        actual = float(sample[TARGET].iloc[i])
        for m, f in fc.items():
            out.append({"month": t, "model": m, "forecast": f, "actual": actual, "prev_actual": y_prev})
    res = pd.DataFrame(out)
    res["abs_error"] = (res["forecast"] - res["actual"]).abs()
    # direction: did the model call the move from last month's IIP growth correctly? (undefined for 'no change')
    pred_move, true_move = np.sign(res["forecast"] - res["prev_actual"]), np.sign(res["actual"] - res["prev_actual"])
    res["direction_correct"] = np.where((pred_move == 0) | (true_move == 0), np.nan, (pred_move == true_move).astype(float))
    return res


def summarise(res: pd.DataFrame) -> pd.DataFrame:
    """MAE, RMSE, direction hit rate per model, and MAE improvement over the best baseline (%)."""
    g = res.groupby("model")
    s = pd.DataFrame({
        "n_months": g.size(),
        "mae": g["abs_error"].mean(),
        "rmse": g.apply(lambda d: float(np.sqrt(((d["forecast"] - d["actual"]) ** 2).mean())), include_groups=False),
        "direction_hit_pct": g["direction_correct"].mean() * 100,
    }).reindex(MODELS)
    best = s.loc[BASELINES, "mae"].min()
    s["mae_improvement_vs_best_baseline_pct"] = (best - s["mae"]) / best * 100
    return s.round(3)


def momentum_hit_rate(panel: pd.DataFrame, months: pd.DatetimeIndex) -> float:
    """Reference for the direction hit rate: repeat last month's direction of change."""
    iip = panel[TARGET].dropna()
    d = iip.diff()
    hits = []
    for t in months:
        prev, last_move, move = iip.shift(1).get(t), d.shift(1).get(t), d.get(t)
        if pd.notna(move) and pd.notna(last_move) and move != 0 and last_move != 0:
            hits.append(float(np.sign(move) == np.sign(last_move)))
    return float(np.mean(hits) * 100) if hits else float("nan")


def full_sample_indices(panel: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """Index values for display (standardised on the whole sample; NOT used for scoring)."""
    s = complete_rows(panel, features)
    z, _ = _standardise(s[features], s[features])
    zs = z.mean(axis=1)
    p_tr, _, weights, evr = pca_index(s[features], s[features], s[TARGET].to_numpy())
    out = pd.DataFrame({"zscore_index": zs, "pca_index": p_tr}, index=s.index)
    out["n_indicators"] = len(features)
    out.attrs["pca_weights"] = weights
    out.attrs["pca_explained_variance"] = evr
    return out
