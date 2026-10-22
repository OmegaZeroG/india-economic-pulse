-- SILVER layer: cleaned and conformed. One typed row per month (and state, product or IIP version), units as
-- published and named in the column (_mn millions, _cr Rs crore, _kt thousand tonnes), first-of-month date keys,
-- state names conformed by state code, missing months left missing. Every row records the bronze file it came from.
-- Rebuilt in full from bronze by src/silver/build_silver.py.

CREATE TABLE IF NOT EXISTS silver_upi (
    month               TEXT PRIMARY KEY,
    banks_live          INTEGER,
    volume_mn           REAL,
    value_cr            REAL,
    avg_daily_volume_mn REAL,                    -- volume / days in month
    source_file         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS silver_fuel (
    month          TEXT NOT NULL,
    product        TEXT NOT NULL,
    consumption_kt REAL,
    source_file    TEXT NOT NULL,
    PRIMARY KEY (month, product)
);

CREATE TABLE IF NOT EXISTS silver_gst_national (
    month TEXT PRIMARY KEY,
    cgst_cr REAL, sgst_cr REAL, igst_cr REAL, cess_cr REAL,
    gross_cr REAL, refunds_cr REAL, net_cr REAL,
    domestic_ex_cess_cr REAL, gross_ex_cess_cr REAL, refunds_ex_cess_cr REAL, net_ex_cess_cr REAL,
    source_file TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS silver_gst_state (
    month TEXT NOT NULL, state_code INTEGER NOT NULL, state TEXT NOT NULL,
    cgst_cr REAL, sgst_cr REAL, igst_cr REAL, gross_cr REAL, refunds_cr REAL, net_cr REAL,
    source_file TEXT NOT NULL,
    PRIMARY KEY (month, state_code)
);

CREATE TABLE IF NOT EXISTS silver_ewaybill_state (
    month TEXT NOT NULL, state_code INTEGER NOT NULL, state TEXT NOT NULL,
    within_suppliers REAL, within_ewb REAL, within_value_cr REAL,
    out_suppliers REAL, out_ewb REAL, out_value_cr REAL,
    in_suppliers REAL, in_ewb REAL, in_value_cr REAL,
    source_file TEXT NOT NULL,
    PRIMARY KEY (month, state_code)
);

-- IIP and GDP keep every version of a number; release_date is the date the file was downloaded.
CREATE TABLE IF NOT EXISTS silver_iip (
    base_year TEXT NOT NULL, month TEXT NOT NULL, release_date TEXT NOT NULL,
    index_value REAL, yoy_growth_pct REAL,
    source_file TEXT NOT NULL,
    PRIMARY KEY (base_year, month, release_date)
);

CREATE TABLE IF NOT EXISTS silver_gdp (
    base_year TEXT NOT NULL, quarter_start TEXT NOT NULL, release_date TEXT NOT NULL,
    fiscal_year TEXT NOT NULL, quarter TEXT NOT NULL,
    gdp_constant_cr REAL, gdp_current_cr REAL, yoy_growth_pct REAL,
    source_file TEXT NOT NULL,
    PRIMARY KEY (base_year, quarter_start, release_date)
);
