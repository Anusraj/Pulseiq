# Task 4: governed metric layer

## Build

Build the validated input and warehouse, then create the metric views:

```powershell
python etl.py
python warehouse.py
python metrics.py
```

The SQL source is `metric_views.sql`; the builder registers the 29 official
views, supporting views, and `metrics.metric_catalog` in `pulseiq.duckdb`. Each official view has
the columns `period_start`, `department_id`, `breakdown_id`, `group_size`,
`numerator`, `denominator`, `metric_value`, `unit`, and `data_status`.
Consumers should use `metric_value` and preserve the view's grain and output
keys rather than recomputing a formula from fact columns.

The three worked statements in `starter/metric_views_examples.sql` were run
in an isolated in-memory DuckDB using typed copies of the warehouse facts.
They returned 891 headcount rows, 81 company attrition rows, and 198 payroll
cost rows. The typed copies are intentional: the ETL `raw` tables preserve
their original CSV values as text, while the examples expect numeric/date
columns.

The catalog is sourced from `raw.metric_dictionary`, with the reusable view
name and normalized numeric minimum added. It includes the metric name,
business definition, formula, source table, grain, period, owner, unit,
direction, caveat, and privacy rule.

## Official views

| ID | View | Calculation grain |
|---|---|---|
| M01 | `metrics.m01_headcount` | Department/month |
| M02 | `metrics.m02_hires` | Department/month |
| M03 | `metrics.m03_exits` | Department/month |
| M04 | `metrics.m04_attrition_rate_monthly` | Department/month |
| M05 | `metrics.m05_attrition_rate_rolling_12m` | Department/month, complete trailing 12-month window |
| M06 | `metrics.m06_voluntary_attrition_rate` | Department/month, complete trailing 12-month window |
| M07 | `metrics.m07_gross_pay` | Department/pay period |
| M08 | `metrics.m08_net_pay` | Department/pay period |
| M09 | `metrics.m09_employer_payroll_cost` | Department/pay period |
| M10 | `metrics.m10_cost_per_head` | Department/pay period |
| M11 | `metrics.m11_overtime_share` | Department/pay period |
| M12 | `metrics.m12_variable_pay_share` | Department/pay period |
| M13 | `metrics.m13_attendance_rate` | Department/month |
| M14 | `metrics.m14_late_arrival_rate` | Department/month |
| M15 | `metrics.m15_leave_without_pay_days` | Department/pay period |
| M16 | `metrics.m16_revenue` | Account/month |
| M17 | `metrics.m17_net_profit` | Company/month |
| M18 | `metrics.m18_operating_margin` | Company/month |
| M19 | `metrics.m19_payroll_as_percent_of_revenue` | Company/month |
| M20 | `metrics.m20_days_sales_outstanding` | One latest-source-date snapshot |
| M21 | `metrics.m21_overdue_receivables` | Client/latest-source-date snapshot |
| M22 | `metrics.m22_task_completion_rate` | Team/sprint |
| M23 | `metrics.m23_on_time_delivery_rate` | Team/sprint |
| M24 | `metrics.m24_velocity` | Team/sprint |
| M25 | `metrics.m25_average_cycle_time` | Team/sprint |
| M26 | `metrics.m26_anomaly_flag_rate` | Anomaly source/month |
| M27 | `metrics.m27_high_risk_share` | Department/latest scoring date |
| M28 | `metrics.m28_forecast_error_mape` | Forecast department/month |
| M29 | `metrics.m29_net_hiring` | Department/month |

## Governed input and privacy rules

Metrics are built on Task 2's `warehouse` facts, which come from Task 1
validated rows; the source `raw` feeds and quarantine are not changed. All
outputs are aggregated. For each dictionary minimum, the view filters out a
group whose `group_size` is below that minimum. The builder independently
checks that no official view returns an undersized group.

Payroll has two seeded data-quality problems that would inflate financial
metrics. The helper view `metrics.payroll_eligible` excludes rows with the
unknown employee surrogate key and collapses exact duplicate employee/run
records to one copy. It does not alter the source or warehouse facts. Other
inconsistent duplicate groups remain visible to the DQ gate; a critical DQ
failure must be resolved before business users treat any metrics as publishable.

For metrics without a minimum in the dictionary (`n/a`), the metric layer does
not invent a privacy threshold. The catalog makes that explicit. The M27
high-risk metric is only a department aggregate for the latest scoring date;
no employee-level risk scores are exposed.

M20 uses the latest invoice date as a reproducible report cutoff and calculates
closing eligible invoice balances divided by invoice totals (including GST)
from the preceding 90 days, multiplied by 90. M21 uses that same latest-source
date as its report date and excludes draft/cancelled invoices.

M28 returns forecast rows even when actual headcount is not yet available.
Those rows are labelled `AWAITING_ACTUAL` and have a null `metric_value`;
they are not presented as a zero forecast error. This supplied dataset's 66
forecast rows are all awaiting actuals, consistent with the catalog caveat.

## Six hand checks

`metric_hand_checks.csv` records the inputs, hand calculation, view output,
difference, and pass status. The six independently checked values are:

| Metric | Grain | Hand-calculated value | View value |
|---|---|---:|---:|
| M04 monthly attrition | 2020-01 / D01 | 3.31% | 3.31% |
| M07 gross pay | 2025-04-30 / D01 | ₹21,189,054.97 | ₹21,189,054.97 |
| M09 employer payroll cost | 2025-04-30 / D01 | ₹21,428,108.75 | ₹21,428,108.75 |
| M16 revenue | 2025-04 / account 4001 | ₹41,824,400.00 | ₹41,824,400.00 |
| M22 task completion | 2025-04-07 / T01 / SP-01 | 50 / 55 × 100 = 90.91% | 90.91% |
| M29 net hires | 2020-01 / D01 | 1 hire - 2 exits = -1 | -1 |

### Attrition denominator decision

The metric dictionary's M04 formula says exits divided by starting headcount.
The worked SQL example instead uses average starting and ending headcount.
This layer explicitly chooses the average, which is less sensitive to the
month-boundary headcount change and matches the provided worked pattern. The
catalog's governed `formula` records the chosen formula and its
`dictionary_formula` column preserves the original dictionary wording for
traceability.

For the hand-checked D01 January 2020 group, there were 2 exits, starting
headcount was 61, and ending headcount was 60:

| Denominator choice | Calculation | Rate |
|---|---:|---:|
| Starting headcount | 2 / 61 × 100 | 3.28% |
| Average headcount | 2 / ((61 + 60) / 2) × 100 | 3.31% |
| Ending headcount | 2 / 60 × 100 | 3.33% |

## Evidence and verification

- `metric_catalog.csv`: all 29 metric definitions and view mappings.
- `metric_hand_checks.csv`: six hand calculations matching the views.
- `metric_view_validation.csv`: the 29 view names, row counts, status, and
  below-minimum group audit.
- Running `python metrics.py` reports the row count of each view and fails if a
  view is missing, returns no rows, omits a catalog entry, or leaks a group
  below its minimum.

Useful SQL:

```sql
SELECT metric_id, metric_name, formula, source_table, owner_team,
       minimum_group_size, view_name
FROM metrics.metric_catalog
ORDER BY metric_id;

SELECT *
FROM metrics.m07_gross_pay
ORDER BY period_start, department_id;
```
