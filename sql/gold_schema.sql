-- GOLD layer: the star schema reporting reads (SQLite). Built from the silver tables by sql/gold_load.sql.
-- India Economic Pulse star schema.
-- Every monthly fact joins to dim_date on the first day of the month (text, ISO yyyy-mm-dd).
-- Units are kept as published and named in the column: _mn = millions, _cr = Rs crore, _kt = thousand tonnes.
-- Re-running this file is safe (IF NOT EXISTS); facts are refilled from silver by sql/gold_load.sql (src/gold/build_gold.py).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS dim_date (
    month_start       TEXT PRIMARY KEY,          -- first day of month
    year              INTEGER NOT NULL,
    month             INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    month_name        TEXT    NOT NULL,
    days_in_month     INTEGER NOT NULL,
    fiscal_year       TEXT    NOT NULL,          -- April-March, e.g. FY2026-27
    fiscal_quarter    INTEGER NOT NULL CHECK (fiscal_quarter BETWEEN 1 AND 4),
    is_diwali_month   INTEGER NOT NULL DEFAULT 0,-- month containing Diwali (Lakshmi Puja)
    is_festive_season INTEGER NOT NULL DEFAULT 0,-- October-November
    is_covid_month    INTEGER NOT NULL DEFAULT 0 -- Apr-Jun 2020, excluded in sensitivity tests
);

CREATE TABLE IF NOT EXISTS fact_upi (
    month               TEXT PRIMARY KEY REFERENCES dim_date(month_start),
    banks_live          INTEGER,
    volume_mn           REAL,                    -- millions of transactions
    value_cr            REAL,                    -- Rs crore
    avg_daily_volume_mn REAL                     -- volume / days in month (February is shorter)
);

CREATE TABLE IF NOT EXISTS fact_gst_national (
    month               TEXT PRIMARY KEY REFERENCES dim_date(month_start),
    cgst_cr             REAL, sgst_cr REAL, igst_cr REAL,
    cess_cr             REAL,                    -- 0 from Apr 2026 (compensation cess ended)
    gross_cr            REAL,                    -- domestic + imports, includes cess
    refunds_cr          REAL,
    net_cr              REAL,
    domestic_ex_cess_cr REAL,                    -- CGST+SGST+IGST, domestic only
    gross_ex_cess_cr    REAL,                    -- CGST+SGST+IGST, consistent across the cess break
    refunds_ex_cess_cr  REAL,
    net_ex_cess_cr      REAL
);

CREATE TABLE IF NOT EXISTS fact_gst_state (
    month      TEXT    NOT NULL REFERENCES dim_date(month_start),
    state_code INTEGER NOT NULL,
    state      TEXT    NOT NULL,
    cgst_cr REAL, sgst_cr REAL, igst_cr REAL,    -- domestic, excluding cess
    gross_cr   REAL,
    refunds_cr REAL,                             -- NULL where the state has no refund row (not filled)
    net_cr     REAL,
    PRIMARY KEY (month, state_code)
);

CREATE TABLE IF NOT EXISTS fact_fuel (
    month          TEXT NOT NULL REFERENCES dim_date(month_start),
    product        TEXT NOT NULL,                -- Petrol (MS), Diesel (HSD), ATF, LPG, Bitumen
    consumption_kt REAL,                         -- thousand metric tonnes; latest months provisional
    PRIMARY KEY (month, product)
);

CREATE TABLE IF NOT EXISTS fact_ewaybill_national (
    month     TEXT PRIMARY KEY REFERENCES dim_date(month_start),
    ewb_count REAL,                              -- within-state + outgoing bills
    value_cr  REAL
);

CREATE TABLE IF NOT EXISTS fact_ewaybill_state (
    month      TEXT    NOT NULL REFERENCES dim_date(month_start),
    state_code INTEGER NOT NULL,
    state      TEXT    NOT NULL,
    within_suppliers REAL, within_ewb REAL, within_value_cr REAL,
    out_suppliers    REAL, out_ewb    REAL, out_value_cr    REAL,
    in_suppliers     REAL, in_ewb     REAL, in_value_cr     REAL,
    PRIMARY KEY (month, state_code)
);

-- IIP and GDP keep every version of a number: release_date is the date we observed the value.
CREATE TABLE IF NOT EXISTS fact_iip (
    base_year      TEXT NOT NULL,                -- 2022-23 (main) or 2011-12 (robustness)
    month          TEXT NOT NULL REFERENCES dim_date(month_start),
    release_date   TEXT NOT NULL,
    index_value    REAL,
    yoy_growth_pct REAL,                         -- as published by MoSPI
    PRIMARY KEY (base_year, month, release_date)
);

CREATE TABLE IF NOT EXISTS fact_gdp (
    base_year       TEXT NOT NULL,
    quarter_start   TEXT NOT NULL REFERENCES dim_date(month_start),
    release_date    TEXT NOT NULL,
    fiscal_year     TEXT NOT NULL,
    quarter         TEXT NOT NULL,               -- Q1 = Apr-Jun
    gdp_constant_cr REAL,                        -- real GDP, Rs crore
    gdp_current_cr  REAL,
    yoy_growth_pct  REAL,                        -- computed from constant prices vs same quarter last year
    PRIMARY KEY (base_year, quarter_start, release_date)
);

-- Week 3 outputs, written by src/analysis/run_week3.py.
-- Index values for display (standardised on the whole sample; backtest forecasts never use these).
CREATE TABLE IF NOT EXISTS index_monthly (
    month          TEXT PRIMARY KEY REFERENCES dim_date(month_start),
    zscore_index   REAL,                         -- equal-weight average of standardised YoY growth
    pca_index      REAL,                         -- first principal component, signed to rise with IIP
    n_indicators   INTEGER,
    iip_yoy_pct    REAL,                         -- target, base 2022-23
    diwali_shift   INTEGER                       -- 1 if Diwali moved in or out of this month vs a year earlier
);

-- Rolling-origin backtest: each row is a forecast made using only earlier months.
CREATE TABLE IF NOT EXISTS backtest_results (
    month            TEXT NOT NULL REFERENCES dim_date(month_start),
    model            TEXT NOT NULL,              -- naive_last, naive_mean12, zscore_index, pca_index, regression
    forecast         REAL,
    actual           REAL,
    prev_actual      REAL,                       -- last IIP growth known when the forecast was made
    abs_error        REAL,
    direction_correct REAL,                      -- 1 / 0, NULL if either move was zero
    PRIMARY KEY (month, model)
);

-- Pre-registered forecasts, written by src/analysis/forecast.py --final. One row per target month and version.
-- actual_pct stays empty until the official release, then is filled by the scoring step (the forecast file itself is never edited).
CREATE TABLE IF NOT EXISTS forecast_log (
    target_month        TEXT NOT NULL REFERENCES dim_date(month_start),
    version             INTEGER NOT NULL,
    made_on             TEXT NOT NULL,
    git_commit          TEXT NOT NULL,
    model               TEXT NOT NULL,
    point_pct           REAL,
    lo80_pct REAL, hi80_pct REAL, lo90_pct REAL, hi90_pct REAL,
    baseline_mean12_pct REAL,
    baseline_last_pct   REAL,
    gdp_call            TEXT,                    -- BELOW / ABOVE the previous quarter's growth
    gdp_threshold_pct   REAL,
    actual_pct          REAL,
    PRIMARY KEY (target_month, version)
);
