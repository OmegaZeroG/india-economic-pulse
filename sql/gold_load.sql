-- Build the GOLD fact tables from silver, in SQL. Full refresh: each fact is emptied and refilled, so gold always
-- equals what silver holds. dim_date is filled first (src/gold/build_gold.py) because every fact points at it.
-- Analysis outputs (index_monthly, backtest_results, forecast_log) are written by the analysis step, not here.

DELETE FROM fact_upi;
INSERT INTO fact_upi (month, banks_live, volume_mn, value_cr, avg_daily_volume_mn)
SELECT month, banks_live, volume_mn, value_cr, avg_daily_volume_mn FROM silver_upi;

DELETE FROM fact_gst_national;
INSERT INTO fact_gst_national
SELECT month, cgst_cr, sgst_cr, igst_cr, cess_cr, gross_cr, refunds_cr, net_cr,
       domestic_ex_cess_cr, gross_ex_cess_cr, refunds_ex_cess_cr, net_ex_cess_cr
FROM silver_gst_national;

DELETE FROM fact_gst_state;
INSERT INTO fact_gst_state (month, state_code, state, cgst_cr, sgst_cr, igst_cr, gross_cr, refunds_cr, net_cr)
SELECT month, state_code, state, cgst_cr, sgst_cr, igst_cr, gross_cr, refunds_cr, net_cr FROM silver_gst_state;

DELETE FROM fact_fuel;
INSERT INTO fact_fuel (month, product, consumption_kt)
SELECT month, product, consumption_kt FROM silver_fuel;

DELETE FROM fact_ewaybill_state;
INSERT INTO fact_ewaybill_state
SELECT month, state_code, state, within_suppliers, within_ewb, within_value_cr,
       out_suppliers, out_ewb, out_value_cr, in_suppliers, in_ewb, in_value_cr
FROM silver_ewaybill_state;

-- National e-way bills: within-state plus outgoing. Incoming is the same bills seen from the receiving
-- state, so adding it would count them twice.
DELETE FROM fact_ewaybill_national;
INSERT INTO fact_ewaybill_national (month, ewb_count, value_cr)
SELECT month,
       COALESCE(SUM(within_ewb), 0) + COALESCE(SUM(out_ewb), 0),
       COALESCE(SUM(within_value_cr), 0) + COALESCE(SUM(out_value_cr), 0)
FROM silver_ewaybill_state
GROUP BY month;

DELETE FROM fact_iip;
INSERT INTO fact_iip (base_year, month, release_date, index_value, yoy_growth_pct)
SELECT base_year, month, release_date, index_value, yoy_growth_pct FROM silver_iip;

DELETE FROM fact_gdp;
INSERT INTO fact_gdp (base_year, quarter_start, release_date, fiscal_year, quarter, gdp_constant_cr, gdp_current_cr, yoy_growth_pct)
SELECT base_year, quarter_start, release_date, fiscal_year, quarter, gdp_constant_cr, gdp_current_cr, yoy_growth_pct FROM silver_gdp;
