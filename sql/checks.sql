-- Five data checks, run after every load by src/run_checks.py.
-- Each block starts with "-- CHECK <name>: <what it proves>" and is one query returning a single
-- number: how many rows break the rule. 0 = pass. Failures are written to docs/data_quality_log.md.

-- CHECK no_missing_months: every monthly table has a row for each month between its first and last
SELECT COUNT(*) AS failures FROM (
    SELECT 'upi' AS t, d.month_start FROM dim_date d
      WHERE d.month_start BETWEEN (SELECT MIN(month) FROM fact_upi) AND (SELECT MAX(month) FROM fact_upi)
        AND d.month_start NOT IN (SELECT month FROM fact_upi)
    UNION ALL
    SELECT 'gst_national', d.month_start FROM dim_date d
      WHERE d.month_start BETWEEN (SELECT MIN(month) FROM fact_gst_national) AND (SELECT MAX(month) FROM fact_gst_national)
        AND d.month_start NOT IN (SELECT month FROM fact_gst_national)
    UNION ALL
    SELECT 'gst_state', month FROM fact_gst_national
      WHERE month NOT IN (SELECT month FROM fact_gst_state)
    UNION ALL
    SELECT 'ewaybill', d.month_start FROM dim_date d
      WHERE d.month_start BETWEEN (SELECT MIN(month) FROM fact_ewaybill_national) AND (SELECT MAX(month) FROM fact_ewaybill_national)
        AND d.month_start NOT IN (SELECT month FROM fact_ewaybill_national)
    UNION ALL
    SELECT 'fuel ' || p.product, d.month_start FROM dim_date d
      JOIN (SELECT product, MIN(month) AS lo, MAX(month) AS hi FROM fact_fuel GROUP BY product) p
        ON d.month_start BETWEEN p.lo AND p.hi
      WHERE NOT EXISTS (SELECT 1 FROM fact_fuel f WHERE f.product = p.product AND f.month = d.month_start)
    UNION ALL
    SELECT 'iip ' || b.base_year, d.month_start FROM dim_date d
      JOIN (SELECT base_year, MIN(month) AS lo, MAX(month) AS hi FROM fact_iip GROUP BY base_year) b
        ON d.month_start BETWEEN b.lo AND b.hi
      WHERE NOT EXISTS (SELECT 1 FROM fact_iip i WHERE i.base_year = b.base_year AND i.month = d.month_start)
);

-- CHECK no_negative_values: volumes, values, collections and refunds are never negative
SELECT COUNT(*) AS failures FROM (
    SELECT month FROM fact_upi WHERE volume_mn < 0 OR value_cr < 0 OR avg_daily_volume_mn < 0
    UNION ALL SELECT month FROM fact_gst_national WHERE gross_cr < 0 OR refunds_cr < 0 OR net_cr < 0 OR cess_cr < 0
    UNION ALL SELECT month FROM fact_gst_state WHERE gross_cr < 0 OR refunds_cr < 0
    UNION ALL SELECT month FROM fact_fuel WHERE consumption_kt < 0
    UNION ALL SELECT month FROM fact_ewaybill_national WHERE ewb_count < 0 OR value_cr < 0
    UNION ALL SELECT month FROM fact_ewaybill_state WHERE within_ewb < 0 OR out_ewb < 0 OR in_ewb < 0
    UNION ALL SELECT quarter_start FROM fact_gdp WHERE gdp_constant_cr < 0
);

-- CHECK state_totals_equal_national: state rows add up to the national domestic total within 0.5 per cent
SELECT COUNT(*) AS failures FROM (
    SELECT n.month
    FROM fact_gst_national n
    JOIN (SELECT month, SUM(gross_cr) AS state_sum FROM fact_gst_state GROUP BY month) s USING (month)
    WHERE ABS(s.state_sum - n.domestic_ex_cess_cr) > 0.005 * n.domestic_ex_cess_cr
);

-- CHECK row_counts_match_source: rows loaded into each table equal the rows in its clean CSV
SELECT COUNT(*) AS failures FROM (
    SELECT l.table_name FROM load_log l
    JOIN (SELECT 'fact_upi' AS t, COUNT(*) AS n FROM fact_upi
          UNION ALL SELECT 'fact_gst_national', COUNT(*) FROM fact_gst_national
          UNION ALL SELECT 'fact_gst_state', COUNT(*) FROM fact_gst_state
          UNION ALL SELECT 'fact_fuel', COUNT(*) FROM fact_fuel
          UNION ALL SELECT 'fact_ewaybill_national', COUNT(*) FROM fact_ewaybill_national
          UNION ALL SELECT 'fact_ewaybill_state', COUNT(*) FROM fact_ewaybill_state
          UNION ALL SELECT 'fact_iip', COUNT(*) FROM fact_iip
          UNION ALL SELECT 'fact_gdp', COUNT(*) FROM fact_gdp) c ON c.t = l.table_name
    WHERE c.n <> l.csv_rows
);

-- CHECK growth_in_plausible_range: YoY growth stays between -60% and +100% in the project window (from Apr 2023)
SELECT COUNT(*) AS failures FROM v_growth_monthly
WHERE month >= '2023-04-01' AND yoy_pct IS NOT NULL AND yoy_pct NOT BETWEEN -60 AND 100;
