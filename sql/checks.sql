-- Seven data checks across the layers (silver-to-gold, gold content, bronze loading, lineage), run after every build by src/run_checks.py.
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

-- CHECK row_counts_match_silver: every gold table holds exactly the rows of the silver table it was built from
SELECT COUNT(*) AS failures FROM (
    SELECT 'upi' AS t FROM (SELECT (SELECT COUNT(*) FROM silver_upi) AS s, (SELECT COUNT(*) FROM fact_upi) AS g) WHERE s <> g
    UNION ALL SELECT 'gst_national' FROM (SELECT (SELECT COUNT(*) FROM silver_gst_national) AS s, (SELECT COUNT(*) FROM fact_gst_national) AS g) WHERE s <> g
    UNION ALL SELECT 'gst_state' FROM (SELECT (SELECT COUNT(*) FROM silver_gst_state) AS s, (SELECT COUNT(*) FROM fact_gst_state) AS g) WHERE s <> g
    UNION ALL SELECT 'fuel' FROM (SELECT (SELECT COUNT(*) FROM silver_fuel) AS s, (SELECT COUNT(*) FROM fact_fuel) AS g) WHERE s <> g
    UNION ALL SELECT 'ewaybill_state' FROM (SELECT (SELECT COUNT(*) FROM silver_ewaybill_state) AS s, (SELECT COUNT(*) FROM fact_ewaybill_state) AS g) WHERE s <> g
    UNION ALL SELECT 'ewaybill_national' FROM (SELECT (SELECT COUNT(DISTINCT month) FROM silver_ewaybill_state) AS s, (SELECT COUNT(*) FROM fact_ewaybill_national) AS g) WHERE s <> g
    UNION ALL SELECT 'iip' FROM (SELECT (SELECT COUNT(*) FROM silver_iip) AS s, (SELECT COUNT(*) FROM fact_iip) AS g) WHERE s <> g
    UNION ALL SELECT 'gdp' FROM (SELECT (SELECT COUNT(*) FROM silver_gdp) AS s, (SELECT COUNT(*) FROM fact_gdp) AS g) WHERE s <> g
);

-- CHECK growth_in_plausible_range: YoY growth stays between -60% and +100% in the project window (from Apr 2023)
SELECT COUNT(*) AS failures FROM v_growth_monthly
WHERE month >= '2023-04-01' AND yoy_pct IS NOT NULL AND yoy_pct NOT BETWEEN -60 AND 100;

-- CHECK bronze_files_fully_loaded: every bronze file stored at least one record and exactly the number it reports
SELECT COUNT(*) AS failures FROM bronze_files f
WHERE f.n_records = 0
   OR f.n_records <> (SELECT COUNT(*) FROM bronze_cells c WHERE c.file_id = f.file_id)
                   + (SELECT COUNT(*) FROM bronze_api a WHERE a.file_id = f.file_id);

-- CHECK silver_rows_traceable: every silver row names a bronze file that exists
SELECT COUNT(*) AS failures FROM (
    SELECT source_file FROM silver_upi
    UNION ALL SELECT source_file FROM silver_fuel
    UNION ALL SELECT source_file FROM silver_gst_national
    UNION ALL SELECT source_file FROM silver_gst_state
    UNION ALL SELECT source_file FROM silver_ewaybill_state
    UNION ALL SELECT source_file FROM silver_iip
    UNION ALL SELECT source_file FROM silver_gdp
) WHERE source_file NOT IN (SELECT file_name FROM bronze_files);
