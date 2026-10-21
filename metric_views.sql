CREATE OR REPLACE VIEW metrics.payroll_eligible AS
SELECT *
FROM warehouse.fact_payroll
WHERE COALESCE(employee_key, 0) > 0
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY employee_id, run_id, period_end_date, department_id, role_id,
                 payable_days, lop_days, overtime_hours_paid, variable_pay_type,
                 monthly_fixed_gross, basic, hra, conveyance, medical,
                 special_allowance, earned_fixed_pay, overtime_pay, variable_pay,
                 gross_pay, pf_employee, esi_employee, professional_tax, tds,
                 other_deductions, total_deductions, net_pay, pf_employer,
                 esi_employer, employer_cost, headcount_flag
    ORDER BY payroll_item_id
) = 1;

CREATE OR REPLACE VIEW metrics.m01_headcount AS
SELECT month_start_date AS period_start, department_id, NULL::VARCHAR AS breakdown_id,
       headcount_end::BIGINT AS group_size, headcount_end::DOUBLE AS numerator,
       NULL::DOUBLE AS denominator, headcount_end::DOUBLE AS metric_value,
       'count'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM warehouse.fact_headcount_monthly
WHERE headcount_end >= (SELECT minimum_group_size_numeric FROM metrics.metric_catalog WHERE metric_id = 'M01');

CREATE OR REPLACE VIEW metrics.m02_hires AS
SELECT month_start_date AS period_start, department_id, NULL::VARCHAR AS breakdown_id,
       headcount_end::BIGINT AS group_size, hires::DOUBLE AS numerator,
       NULL::DOUBLE AS denominator, hires::DOUBLE AS metric_value,
       'count'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM warehouse.fact_headcount_monthly
WHERE headcount_end >= (SELECT minimum_group_size_numeric FROM metrics.metric_catalog WHERE metric_id = 'M02');

CREATE OR REPLACE VIEW metrics.m03_exits AS
SELECT month_start_date AS period_start, department_id, NULL::VARCHAR AS breakdown_id,
       headcount_end::BIGINT AS group_size, exits::DOUBLE AS numerator,
       NULL::DOUBLE AS denominator, exits::DOUBLE AS metric_value,
       'count'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM warehouse.fact_headcount_monthly
WHERE headcount_end >= (SELECT minimum_group_size_numeric FROM metrics.metric_catalog WHERE metric_id = 'M03');

CREATE OR REPLACE VIEW metrics.m04_attrition_rate_monthly AS
WITH monthly AS (
    SELECT month_start_date AS period_start, department_id, exits,
           (headcount_start + headcount_end) / 2.0 AS average_headcount
    FROM warehouse.fact_headcount_monthly
)
SELECT period_start, department_id, NULL::VARCHAR AS breakdown_id,
       FLOOR(average_headcount)::BIGINT AS group_size, exits::DOUBLE AS numerator,
       average_headcount::DOUBLE AS denominator,
       ROUND(100.0 * exits / NULLIF(average_headcount, 0), 2) AS metric_value,
       'percent'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM monthly
WHERE average_headcount >= (SELECT minimum_group_size_numeric FROM metrics.metric_catalog WHERE metric_id = 'M04');

CREATE OR REPLACE VIEW metrics.m05_attrition_rate_rolling_12m AS
WITH rolling AS (
    SELECT month_start_date AS period_start, department_id,
           SUM(exits) OVER w AS exits_12m,
           AVG(headcount_end) OVER w AS average_headcount_12m,
           COUNT(*) OVER w AS months_in_window
    FROM warehouse.fact_headcount_monthly
    WINDOW w AS (PARTITION BY department_id ORDER BY month_start_date ROWS BETWEEN 11 PRECEDING AND CURRENT ROW)
)
SELECT period_start, department_id, NULL::VARCHAR AS breakdown_id,
       FLOOR(average_headcount_12m)::BIGINT AS group_size, exits_12m::DOUBLE AS numerator,
       average_headcount_12m::DOUBLE AS denominator,
       ROUND(100.0 * exits_12m / NULLIF(average_headcount_12m, 0), 2) AS metric_value,
       'percent'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM rolling
WHERE months_in_window = 12
  AND average_headcount_12m >= (SELECT minimum_group_size_numeric FROM metrics.metric_catalog WHERE metric_id = 'M05');

CREATE OR REPLACE VIEW metrics.m06_voluntary_attrition_rate AS
WITH rolling AS (
    SELECT month_start_date AS period_start, department_id,
           SUM(voluntary_exits) OVER w AS voluntary_exits_12m,
           AVG(headcount_end) OVER w AS average_headcount_12m,
           COUNT(*) OVER w AS months_in_window
    FROM warehouse.fact_headcount_monthly
    WINDOW w AS (PARTITION BY department_id ORDER BY month_start_date ROWS BETWEEN 11 PRECEDING AND CURRENT ROW)
)
SELECT period_start, department_id, NULL::VARCHAR AS breakdown_id,
       FLOOR(average_headcount_12m)::BIGINT AS group_size,
       voluntary_exits_12m::DOUBLE AS numerator, average_headcount_12m::DOUBLE AS denominator,
       ROUND(100.0 * voluntary_exits_12m / NULLIF(average_headcount_12m, 0), 2) AS metric_value,
       'percent'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM rolling
WHERE months_in_window = 12
  AND average_headcount_12m >= (SELECT minimum_group_size_numeric FROM metrics.metric_catalog WHERE metric_id = 'M06');

CREATE OR REPLACE VIEW metrics.m07_gross_pay AS
WITH grouped AS (
    SELECT period_end_date AS period_start, department_id, COUNT(DISTINCT employee_id) AS group_size,
           SUM(gross_pay) AS numerator
    FROM metrics.payroll_eligible GROUP BY 1, 2
)
SELECT period_start, department_id, NULL::VARCHAR AS breakdown_id, group_size,
       numerator, NULL::DOUBLE AS denominator, ROUND(numerator, 2) AS metric_value,
       'INR'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM grouped
WHERE group_size >= (SELECT minimum_group_size_numeric FROM metrics.metric_catalog WHERE metric_id = 'M07');

CREATE OR REPLACE VIEW metrics.m08_net_pay AS
WITH grouped AS (
    SELECT period_end_date AS period_start, department_id, COUNT(DISTINCT employee_id) AS group_size,
           SUM(net_pay) AS numerator
    FROM metrics.payroll_eligible GROUP BY 1, 2
)
SELECT period_start, department_id, NULL::VARCHAR AS breakdown_id, group_size,
       numerator, NULL::DOUBLE AS denominator, ROUND(numerator, 2) AS metric_value,
       'INR'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM grouped
WHERE group_size >= (SELECT minimum_group_size_numeric FROM metrics.metric_catalog WHERE metric_id = 'M08');

CREATE OR REPLACE VIEW metrics.m09_employer_payroll_cost AS
WITH grouped AS (
    SELECT period_end_date AS period_start, department_id, COUNT(DISTINCT employee_id) AS group_size,
           SUM(employer_cost) AS numerator
    FROM metrics.payroll_eligible GROUP BY 1, 2
)
SELECT period_start, department_id, NULL::VARCHAR AS breakdown_id, group_size,
       numerator, NULL::DOUBLE AS denominator, ROUND(numerator, 2) AS metric_value,
       'INR'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM grouped
WHERE group_size >= (SELECT minimum_group_size_numeric FROM metrics.metric_catalog WHERE metric_id = 'M09');

CREATE OR REPLACE VIEW metrics.m10_cost_per_head AS
WITH grouped AS (
    SELECT period_end_date AS period_start, department_id, COUNT(DISTINCT employee_id) AS group_size,
           SUM(employer_cost) AS total_cost
    FROM metrics.payroll_eligible GROUP BY 1, 2
)
SELECT period_start, department_id, NULL::VARCHAR AS breakdown_id, group_size,
       total_cost AS numerator, group_size::DOUBLE AS denominator,
       ROUND(total_cost / NULLIF(group_size, 0), 2) AS metric_value,
       'INR'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM grouped
WHERE group_size >= (SELECT minimum_group_size_numeric FROM metrics.metric_catalog WHERE metric_id = 'M10');

CREATE OR REPLACE VIEW metrics.m11_overtime_share AS
WITH grouped AS (
    SELECT period_end_date AS period_start, department_id, COUNT(DISTINCT employee_id) AS group_size,
           SUM(overtime_pay) AS overtime_pay, SUM(employer_cost) AS employer_cost
    FROM metrics.payroll_eligible GROUP BY 1, 2
)
SELECT period_start, department_id, NULL::VARCHAR AS breakdown_id, group_size,
       overtime_pay AS numerator, employer_cost AS denominator,
       ROUND(100.0 * overtime_pay / NULLIF(employer_cost, 0), 2) AS metric_value,
       'percent'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM grouped
WHERE group_size >= (SELECT minimum_group_size_numeric FROM metrics.metric_catalog WHERE metric_id = 'M11');

CREATE OR REPLACE VIEW metrics.m12_variable_pay_share AS
WITH grouped AS (
    SELECT period_end_date AS period_start, department_id, COUNT(DISTINCT employee_id) AS group_size,
           SUM(variable_pay) AS variable_pay, SUM(gross_pay) AS gross_pay
    FROM metrics.payroll_eligible GROUP BY 1, 2
)
SELECT period_start, department_id, NULL::VARCHAR AS breakdown_id, group_size,
       variable_pay AS numerator, gross_pay AS denominator,
       ROUND(100.0 * variable_pay / NULLIF(gross_pay, 0), 2) AS metric_value,
       'percent'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM grouped
WHERE group_size >= (SELECT minimum_group_size_numeric FROM metrics.metric_catalog WHERE metric_id = 'M12');

CREATE OR REPLACE VIEW metrics.m13_attendance_rate AS
WITH grouped AS (
    SELECT period_end_date AS period_start, department_id, COUNT(DISTINCT employee_id) AS group_size,
           SUM(present_days) + 0.5 * SUM(half_days_unpaid) AS attendance_days,
           SUM(scheduled_days) AS scheduled_days
    FROM warehouse.fact_attendance_monthly GROUP BY 1, 2
)
SELECT period_start, department_id, NULL::VARCHAR AS breakdown_id, group_size,
       attendance_days AS numerator, scheduled_days AS denominator,
       ROUND(attendance_days / NULLIF(scheduled_days, 0), 4) AS metric_value,
       'ratio'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM grouped
WHERE group_size >= (SELECT minimum_group_size_numeric FROM metrics.metric_catalog WHERE metric_id = 'M13');

CREATE OR REPLACE VIEW metrics.m14_late_arrival_rate AS
WITH grouped AS (
    SELECT period_end_date AS period_start, department_id, COUNT(DISTINCT employee_id) AS group_size,
           SUM(late_arrivals) AS late_arrivals, SUM(present_days) AS present_days
    FROM warehouse.fact_attendance_monthly GROUP BY 1, 2
)
SELECT period_start, department_id, NULL::VARCHAR AS breakdown_id, group_size,
       late_arrivals AS numerator, present_days AS denominator,
       ROUND(late_arrivals / NULLIF(present_days, 0), 4) AS metric_value,
       'ratio'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM grouped
WHERE group_size >= (SELECT minimum_group_size_numeric FROM metrics.metric_catalog WHERE metric_id = 'M14');

CREATE OR REPLACE VIEW metrics.m15_leave_without_pay_days AS
WITH grouped AS (
    SELECT period_end_date AS period_start, department_id, COUNT(DISTINCT employee_id) AS group_size,
           SUM(lop_days) AS numerator
    FROM metrics.payroll_eligible GROUP BY 1, 2
)
SELECT period_start, department_id, NULL::VARCHAR AS breakdown_id, group_size,
       numerator, NULL::DOUBLE AS denominator, ROUND(numerator, 2) AS metric_value,
       'days'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM grouped
WHERE group_size >= (SELECT minimum_group_size_numeric FROM metrics.metric_catalog WHERE metric_id = 'M15');

CREATE OR REPLACE VIEW metrics.m16_revenue AS
SELECT CAST(posting_period || '-01' AS DATE) AS period_start, NULL::VARCHAR AS department_id,
       account_code AS breakdown_id, COUNT(*)::BIGINT AS group_size,
       -SUM(signed_amount_debit_positive) AS numerator, NULL::DOUBLE AS denominator,
       ROUND(-SUM(signed_amount_debit_positive), 2) AS metric_value,
       'INR'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM warehouse.fact_ledger
WHERE TRY_CAST(account_code AS INTEGER) BETWEEN 4001 AND 4004
GROUP BY 1, 3;

CREATE OR REPLACE VIEW metrics.m17_net_profit AS
SELECT CAST(posting_period || '-01' AS DATE) AS period_start, NULL::VARCHAR AS department_id,
       NULL::VARCHAR AS breakdown_id, COUNT(*)::BIGINT AS group_size,
       -SUM(signed_amount_debit_positive) AS numerator, NULL::DOUBLE AS denominator,
       ROUND(-SUM(signed_amount_debit_positive), 2) AS metric_value,
       'INR'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM warehouse.fact_ledger
WHERE TRY_CAST(account_code AS INTEGER) BETWEEN 4000 AND 5999
GROUP BY 1;

CREATE OR REPLACE VIEW metrics.m18_operating_margin AS
WITH monthly AS (
    SELECT CAST(posting_period || '-01' AS DATE) AS period_start,
           SUM(CASE WHEN TRY_CAST(account_code AS INTEGER) BETWEEN 4001 AND 4004
                    THEN -signed_amount_debit_positive ELSE 0 END) AS revenue,
           -SUM(CASE WHEN TRY_CAST(account_code AS INTEGER) BETWEEN 4000 AND 5999
                     THEN signed_amount_debit_positive ELSE 0 END) AS net_profit
    FROM warehouse.fact_ledger GROUP BY 1
)
SELECT period_start, NULL::VARCHAR AS department_id, NULL::VARCHAR AS breakdown_id,
       0::BIGINT AS group_size, net_profit AS numerator, revenue AS denominator,
       ROUND(100.0 * net_profit / NULLIF(revenue, 0), 2) AS metric_value,
       'percent'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM monthly;

CREATE OR REPLACE VIEW metrics.m19_payroll_as_percent_of_revenue AS
WITH monthly AS (
    SELECT CAST(posting_period || '-01' AS DATE) AS period_start,
           SUM(CASE WHEN TRY_CAST(account_code AS INTEGER) BETWEEN 5001 AND 5005
                    THEN signed_amount_debit_positive ELSE 0 END) AS payroll_cost,
           SUM(CASE WHEN TRY_CAST(account_code AS INTEGER) BETWEEN 4001 AND 4004
                    THEN -signed_amount_debit_positive ELSE 0 END) AS revenue
    FROM warehouse.fact_ledger GROUP BY 1
)
SELECT period_start, NULL::VARCHAR AS department_id, NULL::VARCHAR AS breakdown_id,
       0::BIGINT AS group_size, payroll_cost AS numerator, revenue AS denominator,
       ROUND(100.0 * payroll_cost / NULLIF(revenue, 0), 2) AS metric_value,
       'percent'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM monthly;

CREATE OR REPLACE VIEW metrics.m20_days_sales_outstanding AS
WITH cutoff AS (
    SELECT MAX(invoice_date) AS as_of_date FROM warehouse.fact_invoice
),
receivables AS (
    SELECT SUM(i.balance_due) AS amount
    FROM warehouse.fact_invoice i CROSS JOIN cutoff c
    WHERE i.invoice_date <= c.as_of_date
      AND UPPER(i.status) NOT IN ('DRAFT', 'CANCELLED')
),
sales_90d AS (
    SELECT SUM(i.total_amount) AS amount
    FROM warehouse.fact_invoice i CROSS JOIN cutoff c
    WHERE i.invoice_date > c.as_of_date - INTERVAL 90 DAY
      AND i.invoice_date <= c.as_of_date
      AND UPPER(i.status) NOT IN ('DRAFT', 'CANCELLED')
)
SELECT c.as_of_date AS period_start, NULL::VARCHAR AS department_id, NULL::VARCHAR AS breakdown_id,
       (SELECT COUNT(*) FROM warehouse.fact_invoice)::BIGINT AS group_size,
       r.amount AS numerator, s.amount AS denominator,
       ROUND(90.0 * r.amount / NULLIF(s.amount, 0), 2) AS metric_value,
       'days'::VARCHAR AS unit,
       CASE WHEN s.amount IS NULL OR s.amount = 0 THEN 'NO_90_DAY_SALES' ELSE 'AVAILABLE' END::VARCHAR AS data_status
FROM cutoff c CROSS JOIN receivables r CROSS JOIN sales_90d s;

CREATE OR REPLACE VIEW metrics.m21_overdue_receivables AS
WITH cutoff AS (
    SELECT MAX(invoice_date) AS as_of_date FROM warehouse.fact_invoice
)
SELECT c.as_of_date AS period_start, NULL::VARCHAR AS department_id,
       i.client_id AS breakdown_id, COUNT(*)::BIGINT AS group_size,
       SUM(i.balance_due) AS numerator, NULL::DOUBLE AS denominator,
       ROUND(SUM(i.balance_due), 2) AS metric_value, 'INR'::VARCHAR AS unit,
       'AVAILABLE'::VARCHAR AS data_status
FROM warehouse.fact_invoice i CROSS JOIN cutoff c
WHERE i.due_date < c.as_of_date
  AND i.balance_due > 0
  AND UPPER(i.status) NOT IN ('DRAFT', 'CANCELLED')
GROUP BY 1, 3;

CREATE OR REPLACE VIEW metrics.m22_task_completion_rate AS
WITH grouped AS (
    SELECT t.team_id, t.sprint_id, s.start_date AS period_start,
           COUNT(*) FILTER (WHERE LOWER(t.status) <> 'cancelled')::BIGINT AS group_size,
           COUNT(*) FILTER (WHERE LOWER(t.status) = 'done')::DOUBLE AS numerator,
           COUNT(*) FILTER (WHERE LOWER(t.status) <> 'cancelled')::DOUBLE AS denominator
    FROM warehouse.fact_task t
    LEFT JOIN warehouse.dim_sprint s ON s.sprint_id = t.sprint_id
    GROUP BY 1, 2, 3
)
SELECT period_start, NULL::VARCHAR AS department_id,
       team_id || '/' || sprint_id AS breakdown_id, group_size, numerator, denominator,
       ROUND(100.0 * numerator / NULLIF(denominator, 0), 2) AS metric_value,
       'percent'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM grouped
WHERE group_size >= (SELECT minimum_group_size_numeric FROM metrics.metric_catalog WHERE metric_id = 'M22');

CREATE OR REPLACE VIEW metrics.m23_on_time_delivery_rate AS
WITH grouped AS (
    SELECT t.team_id, t.sprint_id, s.start_date AS period_start,
           COUNT(*) FILTER (WHERE LOWER(t.status) = 'done')::BIGINT AS group_size,
           COUNT(*) FILTER (WHERE LOWER(t.status) = 'done' AND UPPER(t.completed_on_time) = 'Y')::DOUBLE AS numerator,
           COUNT(*) FILTER (WHERE LOWER(t.status) = 'done')::DOUBLE AS denominator
    FROM warehouse.fact_task t
    LEFT JOIN warehouse.dim_sprint s ON s.sprint_id = t.sprint_id
    GROUP BY 1, 2, 3
)
SELECT period_start, NULL::VARCHAR AS department_id,
       team_id || '/' || sprint_id AS breakdown_id, group_size, numerator, denominator,
       ROUND(100.0 * numerator / NULLIF(denominator, 0), 2) AS metric_value,
       'percent'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM grouped
WHERE group_size >= (SELECT minimum_group_size_numeric FROM metrics.metric_catalog WHERE metric_id = 'M23');

CREATE OR REPLACE VIEW metrics.m24_velocity AS
SELECT s.start_date AS period_start, NULL::VARCHAR AS department_id,
       t.team_id || '/' || t.sprint_id AS breakdown_id,
       COUNT(*) FILTER (WHERE LOWER(t.status) = 'done')::BIGINT AS group_size,
       SUM(t.story_points) FILTER (WHERE LOWER(t.status) = 'done')::DOUBLE AS numerator,
       NULL::DOUBLE AS denominator,
       SUM(t.story_points) FILTER (WHERE LOWER(t.status) = 'done')::DOUBLE AS metric_value,
       'points'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM warehouse.fact_task t
LEFT JOIN warehouse.dim_sprint s ON s.sprint_id = t.sprint_id
GROUP BY 1, 3;

CREATE OR REPLACE VIEW metrics.m25_average_cycle_time AS
WITH grouped AS (
    SELECT t.team_id, t.sprint_id, s.start_date AS period_start,
           COUNT(*) FILTER (
               WHERE LOWER(t.status) = 'done' AND t.started_date IS NOT NULL AND t.completed_date IS NOT NULL
           )::BIGINT AS group_size,
           SUM(DATE_DIFF('day', t.started_date, t.completed_date)) FILTER (
               WHERE LOWER(t.status) = 'done' AND t.started_date IS NOT NULL AND t.completed_date IS NOT NULL
           )::DOUBLE AS total_cycle_days,
           AVG(DATE_DIFF('day', t.started_date, t.completed_date)) FILTER (
               WHERE LOWER(t.status) = 'done' AND t.started_date IS NOT NULL AND t.completed_date IS NOT NULL
           ) AS average_cycle_days
    FROM warehouse.fact_task t
    LEFT JOIN warehouse.dim_sprint s ON s.sprint_id = t.sprint_id
    GROUP BY 1, 2, 3
)
SELECT period_start, NULL::VARCHAR AS department_id,
       team_id || '/' || sprint_id AS breakdown_id, group_size, total_cycle_days AS numerator,
       group_size::DOUBLE AS denominator, ROUND(average_cycle_days, 2) AS metric_value,
       'days'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM grouped
WHERE group_size >= (SELECT minimum_group_size_numeric FROM metrics.metric_catalog WHERE metric_id = 'M25');

CREATE OR REPLACE VIEW metrics.m26_anomaly_flag_rate AS
WITH grouped AS (
    SELECT DATE_TRUNC('month', period)::DATE AS period_start, source_dataset AS breakdown_id,
           COUNT(*)::BIGINT AS group_size,
           COUNT(*) FILTER (WHERE UPPER(flagged) = 'Y')::DOUBLE AS numerator,
           COUNT(*)::DOUBLE AS denominator
    FROM warehouse.fact_anomaly GROUP BY 1, 2
)
SELECT period_start, NULL::VARCHAR AS department_id, breakdown_id, group_size, numerator, denominator,
       ROUND(100.0 * numerator / NULLIF(denominator, 0), 2) AS metric_value,
       'percent'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM grouped;

CREATE OR REPLACE VIEW metrics.m27_high_risk_share AS
WITH latest AS (
    SELECT MAX(as_of_date) AS period_start FROM warehouse.fact_attrition_risk
),
grouped AS (
    SELECT r.department_id, COUNT(DISTINCT r.employee_id)::BIGINT AS group_size,
           COUNT(DISTINCT r.employee_id) FILTER (WHERE LOWER(r.risk_band) = 'high')::DOUBLE AS numerator
    FROM warehouse.fact_attrition_risk r CROSS JOIN latest l
    WHERE r.as_of_date = l.period_start
    GROUP BY 1
)
SELECT l.period_start, g.department_id, NULL::VARCHAR AS breakdown_id, g.group_size,
       g.numerator, g.group_size::DOUBLE AS denominator,
       ROUND(100.0 * g.numerator / NULLIF(g.group_size, 0), 2) AS metric_value,
       'percent'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM grouped g CROSS JOIN latest l
WHERE g.group_size >= (SELECT minimum_group_size_numeric FROM metrics.metric_catalog WHERE metric_id = 'M27');

CREATE OR REPLACE VIEW metrics.m28_forecast_error_mape AS
WITH actuals AS (
    SELECT month_start_date AS forecast_month, department_id, headcount_end::DOUBLE AS actual
    FROM warehouse.fact_headcount_monthly
),
company_actuals AS (
    SELECT forecast_month, SUM(actual) AS actual
    FROM actuals GROUP BY 1
),
forecast_actuals AS (
    SELECT f.forecast_month, f.department_id, f.forecast_value,
           CASE WHEN f.department_id = 'ALL' THEN ca.actual ELSE a.actual END AS actual
    FROM warehouse.fact_forecast f
    LEFT JOIN actuals a ON a.department_id = f.department_id AND a.forecast_month = f.forecast_month
    LEFT JOIN company_actuals ca ON ca.forecast_month = f.forecast_month
    WHERE LOWER(f.metric) = 'headcount_end'
)
SELECT forecast_month AS period_start, department_id, NULL::VARCHAR AS breakdown_id,
       0::BIGINT AS group_size, ABS(actual - forecast_value) AS numerator, actual AS denominator,
       ROUND(100.0 * ABS(actual - forecast_value) / NULLIF(actual, 0), 2) AS metric_value,
       'percent'::VARCHAR AS unit,
       CASE WHEN actual IS NULL THEN 'AWAITING_ACTUAL' ELSE 'AVAILABLE' END::VARCHAR AS data_status
FROM forecast_actuals;
