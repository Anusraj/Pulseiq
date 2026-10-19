# Data contract notes

`data/raw/data_contracts.csv` is the authoritative contract for the four
sample/AI feeds below. Types are checked as supplied (the local `raw` and
`validated` copies retain the original CSV text). For the other source tables,
the ETL checks every column against `data_dictionary.csv` for type. Only
explicit `nullable` promises in `data_contracts.csv` are enforced as required
or optional; observed null counts in the dictionary are descriptive, not a
promise that future blanks are invalid.

## `fact_anomaly` — AI anomaly results

| Column(s) | Type | Empty? | Allowed values / rule |
|---|---|---:|---|
| `result_id` | string | No | Unique `AN-` plus four digits |
| `source_dataset` | string | No | `attendance_monthly_features` or `payroll_monthly_features` |
| `record_id`, `employee_id` | string | No | Source record and employee must exist |
| `period` | date | No | Month start or month end |
| `anomaly_score` | decimal(4,3) | No | 0 through 1 |
| `flagged` | char(1) | No | `Y` or `N` |
| `reason_code`, `reason_text`, `model_version` | string | No | Published code, plain-English reason, semantic version |
| `money_at_risk` | decimal(14,2) | Yes | Blank for attendance; required for payroll |
| `scored_at` | timestamp | No | UTC; offset-less source timestamps are interpreted as UTC |

The feed also contains `period_key`, which has dictionary type integer and is
retained. It is not dropped just because it is outside the current feed contract.

## `fact_attrition_risk` — AI attrition risk

| Column(s) | Type | Empty? | Allowed values / rule |
|---|---|---:|---|
| `prediction_id` | string | No | Unique `AR-` plus four digits |
| `employee_id` | string | No | Must identify an employee active on `as_of_date` |
| `department_id` | string | No | Must exist in `dim_department` |
| `as_of_date` | date | No | Batch date; rows more than 7 days before the latest feed date are quarantined |
| `risk_score_12m` | decimal(4,3) | No | 0 through 1 |
| `risk_band` | string | No | `Low`, `Medium`, or `High` |
| `top_reason_1`, `top_reason_2`, `top_reason_3` | string | Yes | Plain-English drivers |
| `model_version` | string | No | Text |

`as_of_date_key`, `model_note`, and `employee_key` are additional dictionary-
documented columns; they are retained and type-checked.

## `fact_forecast` — AI forecast

| Column(s) | Type | Empty? | Allowed values / rule |
|---|---|---:|---|
| `forecast_id` | string | No | Unique `FC-` plus four digits |
| `metric` | string | No | `headcount_end` or `attrition_rate_monthly_pct` |
| `department_id` | string | No | Department id or `ALL` |
| `forecast_month` | date | No | First day of the month |
| `forecast_value` | decimal | No | At least 0 |
| `lower_80` | decimal | No | At least 0 and no greater than forecast |
| `upper_80` | decimal | No | At least forecast |
| `method` | string | No | Text |
| `trained_through` | string | No | `YYYY-MM` |

`model_version` and `forecast_month_key` are additional dictionary-documented
columns; they are retained and type-checked.

## `fact_task` — task board

Types and nullability follow `data_contracts.csv`; allowed values are `Feature`,
`Bug`, `Chore`, or `Spike` for `task_type`; `P1`–`P4` for `priority`; 1, 2, 3,
5, 8, or 13 for `story_points`; and `Done`, `In Progress`, `Blocked`, `To Do`,
or `Cancelled` for `status`. Team, sprint, and assignee references must exist;
the due date must be the sprint end date; created/started/completed date
relationships are checked. Additional columns use their data dictionary types
and nullability.

Numeric columns accept standard thousands separators (for example,
`144,460.00`) as valid numeric text; validation parses separators without
rewriting the source values in `raw` or `validated`.

## Unexpected columns

An unexpected column produces a visible schema warning, is retained in `raw`
and `validated`, and is checked against the data dictionary when one is
available. This forward-compatible **warn and retain** policy prevents
otherwise valid rows from being silently lost; the warning is included in
`etl_summary.csv` and the DuckDB summary. A missing contracted column is an
ETL error because validation would otherwise be incomplete.
