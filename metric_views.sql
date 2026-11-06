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

CREATE OR REPLACE VIEW metrics.dashboard_payroll_department_month AS
SELECT DATE_TRUNC('month', gross.period_start)::DATE AS period_start,
       gross.department_id, department.department_name,
       gross.group_size, gross.metric_value AS gross_pay,
       net.metric_value AS net_pay, cost.metric_value AS employer_cost,
       cost_per_head.metric_value AS cost_per_employee
FROM metrics.m07_gross_pay gross
JOIN metrics.m08_net_pay net
  ON net.period_start = gross.period_start
 AND net.department_id = gross.department_id
JOIN metrics.m09_employer_payroll_cost cost
  ON cost.period_start = gross.period_start
 AND cost.department_id = gross.department_id
JOIN metrics.m10_cost_per_head cost_per_head
  ON cost_per_head.period_start = gross.period_start
 AND cost_per_head.department_id = gross.department_id
JOIN warehouse.dim_department department
  ON department.department_id = gross.department_id;

CREATE OR REPLACE VIEW metrics.dashboard_payroll_monthly_total AS
WITH payroll AS (
    SELECT DATE_TRUNC('month', period_end_date)::DATE AS period_start,
           COUNT(DISTINCT employee_id)::BIGINT AS group_size,
           ROUND(SUM(gross_pay), 2) AS gross_pay,
           ROUND(SUM(net_pay), 2) AS net_pay,
           ROUND(SUM(employer_cost), 2) AS employer_cost,
           ROUND(SUM(employer_cost) / NULLIF(COUNT(DISTINCT employee_id), 0), 2)
               AS cost_per_employee
    FROM metrics.payroll_eligible
    GROUP BY 1
)
SELECT payroll.period_start, payroll.group_size, payroll.gross_pay,
       payroll.net_pay, payroll.employer_cost, payroll.cost_per_employee,
       ledger.numerator AS ledger_salary_related_expense,
       ROUND(payroll.employer_cost - ledger.numerator, 2) AS reconciliation_difference
FROM payroll
JOIN metrics.m19_payroll_as_percent_of_revenue ledger
  ON ledger.period_start = payroll.period_start
WHERE payroll.group_size >= (
    SELECT minimum_group_size_numeric
    FROM metrics.metric_catalog WHERE metric_id = 'M09'
);

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

CREATE OR REPLACE VIEW metrics.dashboard_team_sprint_productivity AS
WITH task_groups AS (
    SELECT t.team_id, t.sprint_id, s.start_date AS period_start,
           s.end_date AS sprint_end, s.working_days,
           COUNT(*) FILTER (WHERE LOWER(t.status) <> 'cancelled')::BIGINT AS planned_tasks,
           COUNT(*) FILTER (WHERE LOWER(t.status) = 'cancelled')::BIGINT AS cancelled_tasks,
           STRING_AGG(DISTINCT t.task_type, ', ' ORDER BY t.task_type) FILTER (
               WHERE LOWER(t.status) <> 'cancelled'
           ) AS task_types,
           COUNT(*) FILTER (WHERE LOWER(t.status) = 'blocked')::BIGINT AS blocked_tasks,
           COUNT(*) FILTER (
               WHERE LOWER(t.status) <> 'cancelled' AND COALESCE(t.reopened_count, 0) > 0
           )::BIGINT AS reopened_tasks,
           SUM(COALESCE(t.reopened_count, 0)) FILTER (
               WHERE LOWER(t.status) <> 'cancelled'
           )::BIGINT AS reopen_events
    FROM warehouse.fact_task t
    JOIN warehouse.dim_sprint s ON s.sprint_id = t.sprint_id
    GROUP BY 1, 2, 3, 4, 5
)
SELECT g.team_id, tm.team_name, tm.active_members, tm.planning_cadence,
       g.task_types, g.sprint_id, s.sprint_name,
       g.period_start, g.sprint_end, g.working_days,
       g.planned_tasks, g.cancelled_tasks, g.blocked_tasks,
       g.reopened_tasks, g.reopen_events,
       completion.metric_value AS completion_rate,
       on_time.metric_value AS on_time_rate,
       velocity.metric_value AS velocity_points,
       cycle.metric_value AS average_cycle_days
FROM task_groups g
JOIN warehouse.dim_team tm ON tm.team_id = g.team_id
JOIN warehouse.dim_sprint s ON s.sprint_id = g.sprint_id
LEFT JOIN metrics.m22_task_completion_rate completion
  ON completion.period_start = g.period_start
 AND completion.breakdown_id = g.team_id || '/' || g.sprint_id
LEFT JOIN metrics.m23_on_time_delivery_rate on_time
  ON on_time.period_start = g.period_start
 AND on_time.breakdown_id = g.team_id || '/' || g.sprint_id
LEFT JOIN metrics.m24_velocity velocity
  ON velocity.period_start = g.period_start
 AND velocity.breakdown_id = g.team_id || '/' || g.sprint_id
LEFT JOIN metrics.m25_average_cycle_time cycle
  ON cycle.period_start = g.period_start
 AND cycle.breakdown_id = g.team_id || '/' || g.sprint_id
WHERE g.planned_tasks >= (
    SELECT minimum_group_size_numeric
    FROM metrics.metric_catalog WHERE metric_id = 'M22'
);

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

CREATE OR REPLACE VIEW metrics.dashboard_headcount_by_location_tier AS
WITH snapshots AS (
    SELECT DISTINCT period_start, department_id,
           last_day(period_start)::DATE AS period_end
    FROM metrics.m01_headcount
), employee_snapshots AS (
    SELECT s.period_start, s.department_id, e.employee_id,
           COALESCE(l.city_tier, 'Unknown') AS breakdown_id
    FROM snapshots s
    JOIN warehouse.dim_employee e
      ON e.department_id = s.department_id
     AND e.hire_date <= s.period_end
     AND (e.exit_date IS NULL OR e.exit_date > s.period_end)
     AND e.valid_from <= s.period_end
     AND COALESCE(e.valid_to, DATE '9999-12-31') >= s.period_end
     AND e.employee_key <> 0
    LEFT JOIN warehouse.dim_location l ON l.work_location = e.work_location
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY s.period_start, s.department_id, e.employee_id
        ORDER BY e.valid_from DESC, e.employee_key DESC
    ) = 1
), grouped AS (
    SELECT period_start, department_id, breakdown_id,
           COUNT(DISTINCT employee_id)::BIGINT AS group_size
    FROM employee_snapshots
    GROUP BY 1, 2, 3
)
SELECT period_start, department_id, breakdown_id, group_size,
       group_size::DOUBLE AS numerator, NULL::DOUBLE AS denominator,
       group_size::DOUBLE AS metric_value, 'count'::VARCHAR AS unit,
       'AVAILABLE'::VARCHAR AS data_status
FROM grouped
WHERE group_size >= (
    SELECT minimum_group_size_numeric
    FROM metrics.metric_catalog WHERE metric_id = 'M01'
);

CREATE OR REPLACE VIEW metrics.dashboard_department_lookup AS
SELECT department_id, department_name
FROM warehouse.dim_department
WHERE department_id <> 'D00';

CREATE OR REPLACE VIEW metrics.dashboard_attrition_exits_by_month_department AS
SELECT period_start, department_id, group_size,
       numerator::BIGINT AS exits
FROM metrics.m03_exits
WHERE department_id <> 'D00';

CREATE OR REPLACE VIEW metrics.dashboard_attrition_exit_types AS
WITH grouped AS (
    SELECT department_id,
           SUM(voluntary_exits)::BIGINT AS voluntary_exits,
           SUM(exits - voluntary_exits)::BIGINT AS other_exits
    FROM warehouse.fact_headcount_monthly
    WHERE department_id <> 'D00'
    GROUP BY 1
)
SELECT department_id, 'Voluntary'::VARCHAR AS exit_type,
       voluntary_exits::BIGINT AS exits
FROM grouped
WHERE voluntary_exits >= (
        SELECT minimum_group_size_numeric
        FROM metrics.metric_catalog WHERE metric_id = 'M03'
    )
  AND other_exits >= (
        SELECT minimum_group_size_numeric
        FROM metrics.metric_catalog WHERE metric_id = 'M03'
    )
UNION ALL
SELECT department_id, 'Other'::VARCHAR AS exit_type,
       other_exits::BIGINT AS exits
FROM grouped
WHERE voluntary_exits >= (
        SELECT minimum_group_size_numeric
        FROM metrics.metric_catalog WHERE metric_id = 'M03'
    )
  AND other_exits >= (
        SELECT minimum_group_size_numeric
        FROM metrics.metric_catalog WHERE metric_id = 'M03'
    );

CREATE OR REPLACE VIEW metrics.dashboard_attrition_tenure AS
WITH employee_exits AS (
    SELECT e.employee_id, e.department_id, e.hire_date, e.exit_date
    FROM warehouse.dim_employee e
    WHERE e.exit_date IS NOT NULL
      AND e.hire_date IS NOT NULL
      AND e.department_id <> 'D00'
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY e.employee_id
        ORDER BY
            CASE WHEN e.valid_from <= e.exit_date
                       AND COALESCE(e.valid_to, DATE '9999-12-31') >= e.exit_date
                 THEN 1 ELSE 0 END DESC,
            e.valid_from DESC,
            e.employee_key DESC
    ) = 1
), banded AS (
    SELECT department_id, employee_id,
           CASE
               WHEN exit_date < hire_date + INTERVAL '1 year' THEN '< 1 year'
               WHEN exit_date < hire_date + INTERVAL '3 years' THEN '1-< 3 years'
               WHEN exit_date < hire_date + INTERVAL '5 years' THEN '3-< 5 years'
               ELSE '5+ years'
           END AS tenure_band
    FROM employee_exits
), grouped AS (
    SELECT department_id, tenure_band,
           COUNT(DISTINCT employee_id)::BIGINT AS exits
    FROM banded
    GROUP BY 1, 2
)
SELECT department_id, tenure_band, exits
FROM grouped
WHERE exits >= (
    SELECT minimum_group_size_numeric
    FROM metrics.metric_catalog WHERE metric_id = 'M04'
);

CREATE OR REPLACE VIEW metrics.dashboard_headcount_by_work_mode AS
WITH snapshots AS (
    SELECT DISTINCT period_start, department_id,
           last_day(period_start)::DATE AS period_end
    FROM metrics.m01_headcount
), employee_snapshots AS (
    SELECT s.period_start, s.department_id, e.employee_id,
           COALESCE(NULLIF(TRIM(e.work_mode), ''), 'Unknown') AS breakdown_id
    FROM snapshots s
    JOIN warehouse.dim_employee e
      ON e.department_id = s.department_id
     AND e.hire_date <= s.period_end
     AND (e.exit_date IS NULL OR e.exit_date > s.period_end)
     AND e.valid_from <= s.period_end
     AND COALESCE(e.valid_to, DATE '9999-12-31') >= s.period_end
     AND e.employee_key <> 0
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY s.period_start, s.department_id, e.employee_id
        ORDER BY e.valid_from DESC, e.employee_key DESC
    ) = 1
), grouped AS (
    SELECT period_start, department_id, breakdown_id,
           COUNT(DISTINCT employee_id)::BIGINT AS group_size
    FROM employee_snapshots
    GROUP BY 1, 2, 3
)
SELECT period_start, department_id, breakdown_id, group_size,
       group_size::DOUBLE AS numerator, NULL::DOUBLE AS denominator,
       group_size::DOUBLE AS metric_value, 'count'::VARCHAR AS unit,
       'AVAILABLE'::VARCHAR AS data_status
FROM grouped
WHERE group_size >= (
    SELECT minimum_group_size_numeric
    FROM metrics.metric_catalog WHERE metric_id = 'M01'
);

CREATE OR REPLACE VIEW metrics.dashboard_attendance_overtime AS
WITH grouped AS (
    SELECT period_end_date AS period_start, department_id,
           COUNT(DISTINCT employee_id)::BIGINT AS group_size,
           SUM(overtime_hours)::DOUBLE AS overtime_hours
    FROM warehouse.fact_attendance_monthly
    GROUP BY 1, 2
)
SELECT period_start, department_id, NULL::VARCHAR AS breakdown_id, group_size,
       overtime_hours AS numerator, NULL::DOUBLE AS denominator,
       ROUND(overtime_hours, 2) AS metric_value,
       'hours'::VARCHAR AS unit, 'AVAILABLE'::VARCHAR AS data_status
FROM grouped
WHERE group_size >= (
    SELECT minimum_group_size_numeric
    FROM metrics.metric_catalog WHERE metric_id = 'M13'
);

CREATE OR REPLACE VIEW metrics.dashboard_leave_days_by_type AS
WITH grouped AS (
    SELECT LAST_DAY(DATE_TRUNC('month', l.start_date))::DATE AS period_start,
           e.department_id, t.leave_type_code AS breakdown_id,
           t.leave_type_name, COUNT(DISTINCT l.employee_id)::BIGINT AS group_size,
           SUM(l.days)::DOUBLE AS leave_days
    FROM warehouse.fact_leave l
    JOIN warehouse.dim_employee e
      ON e.employee_key = l.employee_key
     AND e.employee_key <> 0
    JOIN warehouse.dim_leave_type t ON t.leave_type_key = l.leave_type_key
    WHERE LOWER(TRIM(l.status)) = 'approved'
    GROUP BY 1, 2, 3, 4
)
SELECT period_start, department_id, breakdown_id, group_size,
       leave_days AS numerator, NULL::DOUBLE AS denominator,
       ROUND(leave_days, 2) AS metric_value, 'days'::VARCHAR AS unit,
       'AVAILABLE'::VARCHAR AS data_status, leave_type_name
FROM grouped
WHERE group_size >= (
    SELECT minimum_group_size_numeric
    FROM metrics.metric_catalog WHERE metric_id = 'M13'
);

CREATE OR REPLACE VIEW metrics.dashboard_attendance_calendar AS
SELECT LAST_DAY(date)::DATE AS period_start,
       COUNT(*) FILTER (WHERE UPPER(is_holiday) = 'Y')::BIGINT AS holiday_count,
       STRING_AGG(CAST(date AS VARCHAR), ', ' ORDER BY date)
           FILTER (WHERE UPPER(is_holiday) = 'Y') AS holiday_dates,
       COUNT(*) FILTER (
           WHERE UPPER(is_holiday) = 'Y' AND DAYOFWEEK(date) IN (1, 5)
       )::BIGINT AS long_weekend_holiday_count,
       STRING_AGG(CAST(date AS VARCHAR), ', ' ORDER BY date)
           FILTER (WHERE UPPER(is_holiday) = 'Y' AND DAYOFWEEK(date) IN (1, 5))
           AS long_weekend_holiday_dates
FROM warehouse.dim_date
GROUP BY 1;

CREATE OR REPLACE VIEW metrics.m29_net_hiring AS
SELECT h.period_start, h.department_id, NULL::VARCHAR AS breakdown_id,
       LEAST(h.group_size, e.group_size)::BIGINT AS group_size,
       h.metric_value - e.metric_value AS numerator,
       NULL::DOUBLE AS denominator,
       h.metric_value - e.metric_value AS metric_value,
       'count'::VARCHAR AS unit,
       'AVAILABLE'::VARCHAR AS data_status
FROM metrics.m02_hires h
JOIN metrics.m03_exits e USING (period_start, department_id)
WHERE LEAST(h.group_size, e.group_size) >= (
    SELECT minimum_group_size_numeric
    FROM metrics.metric_catalog WHERE metric_id = 'M29'
);

CREATE OR REPLACE VIEW metrics.dashboard_budget_vs_actual AS
WITH comparison AS (
    SELECT DATE_TRUNC('month', budget.month)::DATE AS period_start,
           budget.department_id, department.department_name,
           actual.group_size, budget.budget_payroll_cost,
           actual.metric_value AS actual_payroll_cost,
           actual.metric_value - budget.budget_payroll_cost AS variance,
           100.0 * (actual.metric_value - budget.budget_payroll_cost)
               / NULLIF(budget.budget_payroll_cost, 0) AS variance_pct
    FROM warehouse.budget_payroll_dept_month budget
    JOIN warehouse.dim_department department
      ON department.department_id = budget.department_id
    LEFT JOIN metrics.m09_employer_payroll_cost actual
      ON actual.department_id = budget.department_id
     AND DATE_TRUNC('month', actual.period_start)::DATE = budget.month
    WHERE actual.group_size >= (
        SELECT minimum_group_size_numeric
        FROM metrics.metric_catalog WHERE metric_id = 'M09'
    )
)
SELECT period_start, department_id, department_name, group_size,
       budget_payroll_cost, actual_payroll_cost,
       ROUND(variance, 2) AS variance,
       ROUND(variance_pct, 2) AS variance_pct,
       RANK() OVER (
           PARTITION BY period_start
           ORDER BY variance DESC NULLS LAST
       )::BIGINT AS overspend_rank,
       CASE
           WHEN variance <= 0 THEN 'GREEN'
           WHEN variance_pct <= 5 THEN 'AMBER'
           ELSE 'RED'
       END::VARCHAR AS traffic_light
FROM comparison;

CREATE OR REPLACE VIEW metrics.dashboard_kpi_target_status AS
WITH task_actual AS (
    SELECT team.department_id,
           DATE_TRUNC('month', sprint.start_date)::DATE AS period_start,
           COUNT(*) FILTER (WHERE LOWER(task.status) <> 'cancelled')::BIGINT AS group_size,
           100.0 * COUNT(*) FILTER (WHERE LOWER(task.status) = 'done')
               / NULLIF(COUNT(*) FILTER (WHERE LOWER(task.status) <> 'cancelled'), 0)
               AS actual_value
    FROM warehouse.fact_task task
    JOIN warehouse.dim_team team ON team.team_id = task.team_id
    JOIN warehouse.dim_sprint sprint ON sprint.sprint_id = task.sprint_id
    WHERE team.department_id IS NOT NULL
    GROUP BY 1, 2
    HAVING COUNT(*) FILTER (WHERE LOWER(task.status) <> 'cancelled') >= (
        SELECT minimum_group_size_numeric
        FROM metrics.metric_catalog WHERE metric_id = 'M22'
    )
),
target_actual AS (
    SELECT DATE_TRUNC('month', target.month)::DATE AS period_start,
           target.department_id, department.department_name,
           'Attendance rate'::VARCHAR AS kpi_name,
           attendance.group_size,
           100.0 * attendance.metric_value AS actual_value,
           100.0 * target.attendance_rate_target AS target_value,
           '%'::VARCHAR AS unit,
           'HIGHER'::VARCHAR AS good_direction,
           target.attendance_rate_target IS NOT NULL AS target_available
    FROM warehouse.kpi_targets target
    JOIN warehouse.dim_department department
      ON department.department_id = target.department_id
    LEFT JOIN metrics.m13_attendance_rate attendance
      ON attendance.department_id = target.department_id
     AND DATE_TRUNC('month', attendance.period_start)::DATE = target.month

    UNION ALL

    SELECT DATE_TRUNC('month', target.month)::DATE,
           target.department_id, department.department_name,
           'Overtime share', overtime.group_size,
           overtime.metric_value, target.overtime_share_target_pct,
           '%', 'LOWER',
           target.overtime_share_target_pct IS NOT NULL
    FROM warehouse.kpi_targets target
    JOIN warehouse.dim_department department
      ON department.department_id = target.department_id
    LEFT JOIN metrics.m11_overtime_share overtime
      ON overtime.department_id = target.department_id
     AND DATE_TRUNC('month', overtime.period_start)::DATE = target.month

    UNION ALL

    SELECT DATE_TRUNC('month', target.month)::DATE,
           target.department_id, department.department_name,
           'Monthly attrition', attrition.group_size,
           attrition.metric_value, target.attrition_monthly_target_pct,
           '%', 'LOWER',
           target.attrition_monthly_target_pct IS NOT NULL
    FROM warehouse.kpi_targets target
    JOIN warehouse.dim_department department
      ON department.department_id = target.department_id
    LEFT JOIN metrics.m04_attrition_rate_monthly attrition
      ON attrition.department_id = target.department_id
     AND DATE_TRUNC('month', attrition.period_start)::DATE = target.month

    UNION ALL

    SELECT DATE_TRUNC('month', target.month)::DATE,
           target.department_id, department.department_name,
           'Task completion', task.group_size,
           task.actual_value, target.task_completion_target_pct,
           '%', 'HIGHER',
           target.task_completion_target_pct IS NOT NULL
    FROM warehouse.kpi_targets target
    JOIN warehouse.dim_department department
      ON department.department_id = target.department_id
    LEFT JOIN task_actual task
      ON task.department_id = target.department_id
     AND task.period_start = target.month
)
SELECT period_start, department_id, department_name, kpi_name,
       group_size, ROUND(actual_value, 2) AS actual_value,
       ROUND(target_value, 2) AS target_value,
       ROUND(actual_value - target_value, 2) AS variance_to_target,
       unit, good_direction,
       CASE
           WHEN NOT target_available THEN 'NO_TARGET'
           WHEN actual_value IS NULL THEN 'NO_REPORTABLE_ACTUAL'
           WHEN (good_direction = 'HIGHER' AND actual_value >= target_value)
             OR (good_direction = 'LOWER' AND actual_value <= target_value)
               THEN 'GREEN'
           ELSE 'RED'
       END::VARCHAR AS traffic_light
FROM target_actual;

CREATE OR REPLACE VIEW metrics.dashboard_executive_scorecard AS
WITH actuals AS (
    SELECT DATE_TRUNC('month', period_start)::DATE AS period_start,
           'M01'::VARCHAR AS kpi_id, 'Headcount'::VARCHAR AS kpi_name,
           SUM(metric_value) AS metric_value, 'count'::VARCHAR AS unit,
           'CONTEXT'::VARCHAR AS good_direction,
           'metrics.m01_headcount'::VARCHAR AS source_view,
           'pages/1_Workforce.py'::VARCHAR AS detail_page
    FROM metrics.m01_headcount
    GROUP BY 1
    UNION ALL
    SELECT DATE_TRUNC('month', period_start)::DATE, 'M04', 'Monthly attrition',
           100.0 * SUM(numerator) / NULLIF(SUM(denominator), 0),
           '%', 'LOWER', 'metrics.m04_attrition_rate_monthly',
           'pages/3_Attrition.py'
    FROM metrics.m04_attrition_rate_monthly
    GROUP BY 1
    UNION ALL
    SELECT DATE_TRUNC('month', period_start)::DATE, 'M11', 'Overtime share',
           100.0 * SUM(numerator) / NULLIF(SUM(denominator), 0),
           '%', 'LOWER', 'metrics.m11_overtime_share',
           'pages/5_Payroll_Cost.py'
    FROM metrics.m11_overtime_share
    GROUP BY 1
    UNION ALL
    SELECT DATE_TRUNC('month', period_start)::DATE, 'M13', 'Attendance rate',
           100.0 * SUM(numerator) / NULLIF(SUM(denominator), 0),
           '%', 'HIGHER', 'metrics.m13_attendance_rate',
           'pages/2_Attendance.py'
    FROM metrics.m13_attendance_rate
    GROUP BY 1
    UNION ALL
    SELECT DATE_TRUNC('month', period_start)::DATE, 'M16', 'Revenue', SUM(metric_value),
           'INR', 'HIGHER', 'metrics.m16_revenue',
           'pages/7_Profit_Loss.py'
    FROM metrics.m16_revenue
    GROUP BY 1
    UNION ALL
    SELECT DATE_TRUNC('month', period_start)::DATE, 'M17', 'Net profit', SUM(metric_value),
           'INR', 'HIGHER', 'metrics.m17_net_profit',
           'pages/7_Profit_Loss.py'
    FROM metrics.m17_net_profit
    GROUP BY 1
    UNION ALL
    SELECT DATE_TRUNC('month', period_start)::DATE, 'M18', 'Operating margin', metric_value,
           '%', 'HIGHER', 'metrics.m18_operating_margin',
           'pages/7_Profit_Loss.py'
    FROM metrics.m18_operating_margin
    UNION ALL
    SELECT DATE_TRUNC('month', period_start)::DATE, 'M29', 'Net hiring', SUM(metric_value),
           'count', 'CONTEXT', 'metrics.m29_net_hiring',
           'pages/1_Workforce.py'
    FROM metrics.m29_net_hiring
    GROUP BY 1
),
targets AS (
    SELECT period_start, kpi_name,
           AVG(target_value) FILTER (WHERE target_value IS NOT NULL) AS target_value,
           MAX(good_direction) AS target_direction
    FROM metrics.dashboard_kpi_target_status
    WHERE kpi_name IN ('Monthly attrition', 'Overtime share', 'Attendance rate')
    GROUP BY 1, 2
)
SELECT actual.period_start, actual.kpi_id, actual.kpi_name,
       ROUND(actual.metric_value, 2) AS metric_value,
       ROUND(target.target_value, 2) AS target_value,
       actual.unit,
       COALESCE(target.target_direction, actual.good_direction) AS good_direction,
       CASE
           WHEN target.target_value IS NULL THEN 'NO_TARGET'
           WHEN (COALESCE(target.target_direction, actual.good_direction) = 'HIGHER'
                 AND actual.metric_value >= target.target_value)
             OR (COALESCE(target.target_direction, actual.good_direction) = 'LOWER'
                 AND actual.metric_value <= target.target_value)
               THEN 'GREEN'
           ELSE 'RED'
       END::VARCHAR AS traffic_light,
       actual.source_view, actual.detail_page
FROM actuals actual
LEFT JOIN targets target
  ON target.period_start = actual.period_start
 AND target.kpi_name = actual.kpi_name;

CREATE OR REPLACE VIEW metrics.dashboard_pnl_monthly AS
WITH monthly AS (
    SELECT CAST(l.posting_period || '-01' AS DATE) AS period_start,
           SUM(CASE
                   WHEN a.account_type = 'INCOME' AND a.is_group = 'N'
                   THEN -l.signed_amount_debit_positive ELSE 0
               END) AS revenue,
           SUM(CASE
                   WHEN a.account_type = 'EXPENSE' AND a.is_group = 'N'
                   THEN l.signed_amount_debit_positive ELSE 0
               END) AS expenses,
           SUM(CASE
                   WHEN a.account_type = 'INCOME' AND a.is_group = 'N'
                        AND TRY_CAST(a.account_code AS INTEGER) BETWEEN 4001 AND 4004
                   THEN -l.signed_amount_debit_positive ELSE 0
               END) AS operating_revenue,
           SUM(CASE
                   WHEN a.account_code = '4900' AND a.is_group = 'N'
                   THEN -l.signed_amount_debit_positive ELSE 0
               END) AS other_income,
           COUNT(*)::BIGINT AS ledger_lines
    FROM warehouse.fact_ledger l
    JOIN warehouse.dim_account a ON a.account_code = l.account_code
    WHERE a.statement = 'Profit & Loss' AND a.is_group = 'N'
    GROUP BY 1
)
SELECT period_start, ledger_lines,
       ROUND(revenue, 2) AS revenue,
       ROUND(operating_revenue, 2) AS operating_revenue,
       ROUND(other_income, 2) AS other_income,
       ROUND(expenses, 2) AS expenses,
       ROUND(revenue - expenses, 2) AS net_profit,
       ROUND(100.0 * (revenue - expenses) / NULLIF(revenue, 0), 2) AS operating_margin
FROM monthly;

CREATE OR REPLACE VIEW metrics.dashboard_expense_category_monthly AS
SELECT DATE_TRUNC('month', e.expense_date)::DATE AS period_start,
       a.account_code AS category_account,
       a.account_name AS category,
       COUNT(*)::BIGINT AS bill_count,
       ROUND(SUM(e.amount_excl_gst), 2) AS spend_excl_gst
FROM warehouse.fact_expense e
JOIN warehouse.dim_account a ON a.account_key = e.account_key
WHERE a.statement = 'Profit & Loss'
  AND a.account_type = 'EXPENSE'
  AND a.is_group = 'N'
GROUP BY 1, 2, 3;

CREATE OR REPLACE VIEW metrics.dashboard_expense_vendor_monthly AS
SELECT DATE_TRUNC('month', e.expense_date)::DATE AS period_start,
       v.vendor_id, v.vendor_name,
       COUNT(*)::BIGINT AS bill_count,
       ROUND(SUM(e.amount_excl_gst), 2) AS spend_excl_gst
FROM warehouse.fact_expense e
JOIN warehouse.dim_vendor v ON v.vendor_key = e.vendor_key
JOIN warehouse.dim_account a ON a.account_key = e.account_key
WHERE a.statement = 'Profit & Loss'
  AND a.account_type = 'EXPENSE'
  AND a.is_group = 'N'
GROUP BY 1, 2, 3;

CREATE OR REPLACE VIEW metrics.dashboard_pnl_tieout AS
SELECT p.period_start, p.revenue, p.expenses, p.net_profit,
       TRY_CAST(REPLACE(r.ledger_revenue, ',', '') AS DOUBLE) AS headline_revenue,
       TRY_CAST(REPLACE(r.ledger_total_expense, ',', '') AS DOUBLE) AS headline_expenses,
       TRY_CAST(REPLACE(r.ledger_net_profit, ',', '') AS DOUBLE) AS headline_net_profit,
       ROUND(p.revenue - TRY_CAST(REPLACE(r.ledger_revenue, ',', '') AS DOUBLE), 2) AS revenue_difference,
       ROUND(p.expenses - TRY_CAST(REPLACE(r.ledger_total_expense, ',', '') AS DOUBLE), 2) AS expense_difference,
       ROUND(p.net_profit - TRY_CAST(REPLACE(r.ledger_net_profit, ',', '') AS DOUBLE), 2) AS profit_difference
FROM metrics.dashboard_pnl_monthly p
JOIN raw.reconciliation_answer_key r
  ON TRY_CAST(r.month AS DATE) = p.period_start;

CREATE OR REPLACE VIEW metrics.dashboard_receivables_ageing AS
WITH cutoff AS (
    SELECT MAX(invoice_date) AS as_of_date
    FROM warehouse.fact_invoice
),
open_invoices AS (
    SELECT i.invoice_id, i.client_id, i.balance_due,
           GREATEST(DATE_DIFF('day', i.due_date, c.as_of_date), 0)::BIGINT AS days_past_due,
           CASE
               WHEN GREATEST(DATE_DIFF('day', i.due_date, c.as_of_date), 0) <= 30
                   THEN '0-30 days'
               WHEN DATE_DIFF('day', i.due_date, c.as_of_date) <= 60
                   THEN '31-60 days'
               WHEN DATE_DIFF('day', i.due_date, c.as_of_date) <= 90
                   THEN '61-90 days'
               ELSE '90+ days'
           END::VARCHAR AS ageing_bucket
    FROM warehouse.fact_invoice i
    CROSS JOIN cutoff c
    WHERE UPPER(i.status) IN ('SENT', 'OVERDUE', 'PARTIALLY_PAID')
      AND i.balance_due > 0
),
buckets AS (
    SELECT * FROM (VALUES
        ('0-30 days', 1),
        ('31-60 days', 2),
        ('61-90 days', 3),
        ('90+ days', 4)
    ) AS b(ageing_bucket, sort_order)
),
aggregated AS (
    SELECT ageing_bucket, COUNT(*)::BIGINT AS invoice_count,
           ROUND(SUM(balance_due), 2) AS open_receivables,
           MAX(days_past_due)::BIGINT AS oldest_days_past_due
    FROM open_invoices
    GROUP BY 1
)
SELECT b.ageing_bucket,
       COALESCE(a.invoice_count, 0)::BIGINT AS invoice_count,
       COALESCE(a.open_receivables, 0)::DOUBLE AS open_receivables,
       COALESCE(a.oldest_days_past_due, 0)::BIGINT AS oldest_days_past_due
FROM buckets b
LEFT JOIN aggregated a USING (ageing_bucket)
ORDER BY b.sort_order;

CREATE OR REPLACE VIEW metrics.dashboard_receivables_summary AS
WITH cutoff AS (
    SELECT MAX(invoice_date) AS as_of_date
    FROM warehouse.fact_invoice
)
SELECT c.as_of_date,
       COUNT(*)::BIGINT AS open_invoice_count,
       ROUND(SUM(i.balance_due), 2) AS total_open_receivables
FROM warehouse.fact_invoice i
CROSS JOIN cutoff c
WHERE UPPER(i.status) IN ('SENT', 'OVERDUE', 'PARTIALLY_PAID')
  AND i.balance_due > 0
GROUP BY 1;

CREATE OR REPLACE VIEW metrics.dashboard_overdue_clients AS
WITH cutoff AS (
    SELECT MAX(invoice_date) AS as_of_date
    FROM warehouse.fact_invoice
)
SELECT i.client_id, c.client_name,
       COUNT(*)::BIGINT AS overdue_invoice_count,
       ROUND(SUM(i.balance_due), 2) AS overdue_receivables,
       MAX(DATE_DIFF('day', i.due_date, cutoff.as_of_date))::BIGINT AS oldest_days_past_due
FROM warehouse.fact_invoice i
JOIN warehouse.dim_client c ON c.client_key = i.client_key
CROSS JOIN cutoff
WHERE UPPER(i.status) IN ('SENT', 'OVERDUE', 'PARTIALLY_PAID')
  AND i.balance_due > 0
  AND i.due_date < cutoff.as_of_date
GROUP BY 1, 2;

CREATE OR REPLACE VIEW metrics.dashboard_client_days_to_pay AS
SELECT i.client_id, c.client_name, c.payment_terms_days,
       c.payment_behaviour,
       COUNT(*)::BIGINT AS paid_invoice_count,
       ROUND(AVG(i.days_to_pay), 2) AS average_days_to_pay,
       ROUND(AVG(i.days_to_pay - c.payment_terms_days), 2) AS average_days_over_terms
FROM warehouse.fact_invoice i
JOIN warehouse.dim_client c ON c.client_key = i.client_key
WHERE UPPER(i.status) = 'PAID'
  AND i.days_to_pay IS NOT NULL
GROUP BY 1, 2, 3, 4;

CREATE OR REPLACE VIEW metrics.dashboard_cash_flow_monthly AS
WITH cash_in AS (
    SELECT DATE_TRUNC('month', payment_date)::DATE AS period_start,
           SUM(amount) AS cash_in
    FROM warehouse.fact_invoice_payment
    GROUP BY 1
),
cash_out AS (
    SELECT DATE_TRUNC('month', paid_date)::DATE AS period_start,
           SUM(total_amount) AS cash_out
    FROM warehouse.fact_expense
    WHERE UPPER(status) = 'PAID'
      AND paid_date IS NOT NULL
    GROUP BY 1
)
SELECT COALESCE(i.period_start, o.period_start) AS period_start,
       ROUND(COALESCE(i.cash_in, 0), 2) AS cash_in,
       ROUND(COALESCE(o.cash_out, 0), 2) AS cash_out,
       ROUND(COALESCE(i.cash_in, 0) - COALESCE(o.cash_out, 0), 2) AS net_cash_flow
FROM cash_in i
FULL OUTER JOIN cash_out o USING (period_start);

CREATE OR REPLACE VIEW metrics.dashboard_department_impact AS
WITH headcount AS (
    SELECT month_start_date AS period_start, department_id,
           headcount_end, hires, exits,
           attrition_rate_monthly_pct AS attrition_rate
    FROM warehouse.fact_headcount_monthly
),
payroll AS (
    SELECT DATE_TRUNC('month', period_end_date)::DATE AS period_start, department_id,
           COUNT(DISTINCT employee_id)::BIGINT AS employees_paid,
           ROUND(SUM(employer_cost), 2) AS employer_cost,
           ROUND(SUM(gross_pay), 2) AS gross_pay,
           ROUND(SUM(overtime_pay), 2) AS overtime_pay,
           ROUND(SUM(overtime_hours_paid), 2) AS overtime_hours,
           ROUND(SUM(employer_cost) / NULLIF(COUNT(DISTINCT employee_id), 0), 2)
               AS cost_per_head,
           ROUND(100.0 * SUM(overtime_pay) / NULLIF(SUM(employer_cost), 0), 2)
               AS overtime_share_pct
    FROM metrics.payroll_eligible
    GROUP BY 1, 2
),
attendance AS (
    SELECT DATE_TRUNC('month', period_end_date)::DATE AS period_start, department_id,
           COUNT(DISTINCT employee_id)::BIGINT AS attendance_employees,
           ROUND(SUM(present_days) + 0.5 * SUM(half_days_unpaid), 2)
               AS attendance_days,
           ROUND(SUM(scheduled_days), 2) AS scheduled_days,
           ROUND(SUM(overtime_hours), 2) AS attendance_overtime_hours,
           ROUND(SUM(late_arrivals), 2) AS late_arrivals,
           ROUND(
               100.0 * (SUM(present_days) + 0.5 * SUM(half_days_unpaid))
               / NULLIF(SUM(scheduled_days), 0), 2
           ) AS attendance_rate_pct
    FROM warehouse.fact_attendance_monthly
    GROUP BY 1, 2
),
leave AS (
    SELECT DATE_TRUNC('month', l.start_date)::DATE AS period_start,
           e.department_id,
           ROUND(SUM(l.days), 2) AS approved_leave_days
    FROM warehouse.fact_leave l
    JOIN warehouse.dim_employee e ON e.employee_key = l.employee_key
    WHERE LOWER(TRIM(l.status)) = 'approved'
      AND e.employee_key <> 0
    GROUP BY 1, 2
)
SELECT h.period_start, h.department_id, d.department_name,
       h.headcount_end, h.hires, h.exits, ROUND(h.attrition_rate, 2) AS attrition_rate,
       p.employees_paid, p.employer_cost, p.gross_pay, p.overtime_pay,
       p.overtime_hours, p.cost_per_head, p.overtime_share_pct,
       a.attendance_employees, a.attendance_days, a.scheduled_days,
       a.attendance_overtime_hours, a.late_arrivals, a.attendance_rate_pct,
       COALESCE(l.approved_leave_days, 0)::DOUBLE AS approved_leave_days,
       ROUND(COALESCE(l.approved_leave_days, 0) / NULLIF(h.headcount_end, 0), 2)
           AS approved_leave_days_per_head,
       ROUND(p.overtime_pay / NULLIF(p.employees_paid, 0), 2) AS overtime_cost_per_paid_head
FROM headcount h
JOIN warehouse.dim_department d ON d.department_id = h.department_id
LEFT JOIN payroll p
  ON p.period_start = h.period_start AND p.department_id = h.department_id
LEFT JOIN attendance a
  ON a.period_start = h.period_start AND a.department_id = h.department_id
LEFT JOIN leave l
  ON l.period_start = h.period_start AND l.department_id = h.department_id;

CREATE OR REPLACE VIEW metrics.dashboard_department_impact_reconciliation AS
SELECT v.period_start, v.department_id, v.department_name,
       v.employer_cost, TRY_CAST(REPLACE(r.employer_cost, ',', '') AS DOUBLE)
           AS reference_employer_cost,
       ROUND(v.employer_cost - TRY_CAST(REPLACE(r.employer_cost, ',', '') AS DOUBLE), 2)
           AS employer_cost_difference,
       v.gross_pay, TRY_CAST(REPLACE(r.gross_pay, ',', '') AS DOUBLE)
           AS reference_gross_pay,
       ROUND(v.gross_pay - TRY_CAST(REPLACE(r.gross_pay, ',', '') AS DOUBLE), 2)
           AS gross_pay_difference,
       v.overtime_pay, TRY_CAST(REPLACE(r.overtime_pay, ',', '') AS DOUBLE)
           AS reference_overtime_pay,
       ROUND(v.overtime_pay - TRY_CAST(REPLACE(r.overtime_pay, ',', '') AS DOUBLE), 2)
           AS overtime_pay_difference,
       v.employees_paid, TRY_CAST(r.employees_paid AS BIGINT) AS reference_employees_paid,
       v.overtime_hours, TRY_CAST(r.overtime_hours AS DOUBLE) AS reference_overtime_hours,
       v.attendance_rate_pct,
       100.0 * TRY_CAST(r.attendance_rate AS DOUBLE) AS reference_attendance_rate_pct,
       ROUND(v.attendance_rate_pct - 100.0 * TRY_CAST(r.attendance_rate AS DOUBLE), 2)
           AS attendance_rate_difference,
       v.headcount_end, TRY_CAST(r.headcount_end AS BIGINT) AS reference_headcount_end,
       v.hires, TRY_CAST(r.hires AS BIGINT) AS reference_hires,
       v.exits, TRY_CAST(r.exits AS BIGINT) AS reference_exits,
       v.attrition_rate,
       TRY_CAST(REPLACE(r.attrition_rate_monthly_pct, ',', '') AS DOUBLE)
           AS reference_attrition_rate,
       ROUND(v.attrition_rate -
             TRY_CAST(REPLACE(r.attrition_rate_monthly_pct, ',', '') AS DOUBLE), 2)
           AS attrition_rate_difference,
       v.cost_per_head,
       TRY_CAST(REPLACE(r.cost_per_head, ',', '') AS DOUBLE) AS reference_cost_per_head,
       ROUND(v.cost_per_head -
             TRY_CAST(REPLACE(r.cost_per_head, ',', '') AS DOUBLE), 2)
           AS cost_per_head_difference,
       v.overtime_share_pct,
       TRY_CAST(r.overtime_share_pct AS DOUBLE) AS reference_overtime_share_pct,
       ROUND(v.overtime_share_pct -
             TRY_CAST(r.overtime_share_pct AS DOUBLE), 2)
           AS overtime_share_difference
FROM metrics.dashboard_department_impact v
JOIN raw.reference_summary_dept_month r
  ON r.department_id = v.department_id
 AND TRY_CAST(r.month AS DATE) = v.period_start;

CREATE OR REPLACE VIEW metrics.dashboard_ai_anomaly_summary AS
SELECT reason_code,
       COUNT(*)::BIGINT AS anomaly_count,
       ROUND(SUM(COALESCE(money_at_risk, 0)), 2) AS money_at_risk,
       ROUND(AVG(anomaly_score), 3) AS average_anomaly_score,
       MAX(period)::DATE AS latest_period,
       MIN(reason_text) AS example_reason
FROM warehouse.fact_anomaly
WHERE UPPER(flagged) = 'Y'
GROUP BY reason_code;

CREATE OR REPLACE VIEW metrics.dashboard_ai_forecast AS
WITH actuals AS (
    SELECT month_start_date AS period_start,
           department_id,
           headcount_end::DOUBLE AS actual
    FROM warehouse.fact_headcount_monthly
),
company_actuals AS (
    SELECT period_start, SUM(actual) AS actual
    FROM actuals
    GROUP BY 1
)
SELECT f.forecast_id, f.forecast_month AS period_start, f.metric,
       f.department_id, f.forecast_value, f.lower_80, f.upper_80,
       f.method, f.trained_through, f.model_version,
       CASE WHEN f.department_id = 'ALL' THEN ca.actual ELSE a.actual END AS actual,
       CASE
           WHEN CASE WHEN f.department_id = 'ALL' THEN ca.actual ELSE a.actual END IS NULL
               THEN 'AWAITING_ACTUAL'
           ELSE 'ACTUAL_KNOWN'
       END AS actual_status,
       CASE
           WHEN CASE WHEN f.department_id = 'ALL' THEN ca.actual ELSE a.actual END IS NULL
               THEN NULL
           ELSE ABS(
               f.forecast_value
               - CASE WHEN f.department_id = 'ALL' THEN ca.actual ELSE a.actual END
           )
       END AS absolute_error,
       CASE
           WHEN CASE WHEN f.department_id = 'ALL' THEN ca.actual ELSE a.actual END IS NULL
               THEN NULL
           ELSE ROUND(
               100.0 * ABS(
                   f.forecast_value
                   - CASE WHEN f.department_id = 'ALL' THEN ca.actual ELSE a.actual END
               ) / NULLIF(
                   CASE WHEN f.department_id = 'ALL' THEN ca.actual ELSE a.actual END,
                   0
               ),
               2
           )
       END AS error_pct
FROM warehouse.fact_forecast f
LEFT JOIN actuals a
  ON a.department_id = f.department_id
 AND a.period_start = f.forecast_month
LEFT JOIN company_actuals ca
  ON ca.period_start = f.forecast_month
WHERE LOWER(f.metric) = 'headcount_end';

CREATE OR REPLACE VIEW metrics.dashboard_ai_attrition_risk_summary AS
SELECT as_of_date,
       risk_band,
       COUNT(*)::BIGINT AS employee_count,
       ROUND(AVG(risk_score_12m) * 100, 2) AS average_risk_pct
FROM warehouse.fact_attrition_risk
GROUP BY as_of_date, risk_band;
