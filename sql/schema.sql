-- India Economic Pulse: star schema (SQLite).
-- Every monthly fact joins to dim_date on the first day of the month (text, ISO yyyy-mm-dd).
-- Units are kept as published and named in the column: _mn = millions, _cr = Rs crore, _kt = thousand tonnes.
-- Re-running this file is safe (IF NOT EXISTS); data is loaded by src/load_db.py with upserts.

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

-- One row per load so check 4 can compare row counts with the source files.
CREATE TABLE IF NOT EXISTS load_log (
    table_name TEXT PRIMARY KEY,
    source_csv TEXT NOT NULL,
    csv_rows   INTEGER NOT NULL,
    loaded_at  TEXT NOT NULL
);
