-- Growth views. Year-on-year growth removes seasonality and trend (see README).
-- LAG(x, 12) is only valid when the row 12 positions back is exactly 12 months earlier, so every
-- view guards with  LAG(month, 12) = date(month, '-12 months')  and returns NULL otherwise.
-- A missing month therefore shows up as NULL growth instead of a wrong comparison.

DROP VIEW IF EXISTS v_growth_monthly;
DROP VIEW IF EXISTS v_iip_latest;
DROP VIEW IF EXISTS v_iip_target;
DROP VIEW IF EXISTS v_gdp_latest;
DROP VIEW IF EXISTS v_backtest_summary;

-- Latest observed version of every IIP month (revisions are kept in fact_iip, never overwritten).
CREATE VIEW v_iip_latest AS
SELECT i.base_year, i.month, i.release_date, i.index_value, i.yoy_growth_pct
FROM fact_iip i
WHERE i.release_date = (SELECT MAX(release_date) FROM fact_iip j
                        WHERE j.base_year = i.base_year AND j.month = i.month);

-- The series the forecast is scored against: base 2022-23, published growth.
CREATE VIEW v_iip_target AS
SELECT month, index_value, yoy_growth_pct AS iip_yoy_pct, release_date
FROM v_iip_latest WHERE base_year = '2022-23';

CREATE VIEW v_gdp_latest AS
SELECT g.* FROM fact_gdp g
WHERE g.release_date = (SELECT MAX(release_date) FROM fact_gdp h
                        WHERE h.base_year = g.base_year AND h.quarter_start = g.quarter_start);

-- Long format: one row per month per indicator with its level and YoY growth.
CREATE VIEW v_growth_monthly AS
WITH base AS (
    SELECT month, 'upi_daily_volume_mn' AS indicator, avg_daily_volume_mn AS value FROM fact_upi
    UNION ALL SELECT month, 'upi_value_cr',        value_cr          FROM fact_upi
    UNION ALL SELECT month, 'gst_net_ex_cess_cr',  net_ex_cess_cr    FROM fact_gst_national
    UNION ALL SELECT month, 'gst_gross_ex_cess_cr', gross_ex_cess_cr FROM fact_gst_national
    UNION ALL SELECT month, 'fuel_' || CASE product
                 WHEN 'Petrol (MS)' THEN 'petrol' WHEN 'Diesel (HSD)' THEN 'diesel'
                 WHEN 'ATF' THEN 'atf' WHEN 'LPG' THEN 'lpg' WHEN 'Bitumen' THEN 'bitumen' END || '_kt',
                 consumption_kt FROM fact_fuel
    UNION ALL SELECT month, 'ewaybill_value_cr',   value_cr          FROM fact_ewaybill_national
)
SELECT month, indicator, value,
       CASE WHEN LAG(month, 12) OVER w = date(month, '-12 months')
            THEN 100.0 * (value / LAG(value, 12) OVER w - 1) END AS yoy_pct
FROM base
WINDOW w AS (PARTITION BY indicator ORDER BY month);

-- Backtest scorecard: MAE, direction hit rate and MAE improvement over the better naive baseline.
CREATE VIEW v_backtest_summary AS
WITH m AS (
    SELECT model, COUNT(*) AS n_months, AVG(abs_error) AS mae, 100.0 * AVG(direction_correct) AS direction_hit_pct
    FROM backtest_results GROUP BY model
)
SELECT model, n_months, ROUND(mae, 3) AS mae, ROUND(direction_hit_pct, 1) AS direction_hit_pct,
       ROUND(100.0 * ((SELECT MIN(mae) FROM m WHERE model LIKE 'naive%') - mae)
             / (SELECT MIN(mae) FROM m WHERE model LIKE 'naive%'), 1) AS mae_improvement_vs_best_baseline_pct
FROM m;
