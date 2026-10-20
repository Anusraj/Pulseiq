# PulseIQ star-schema warehouse

## Build and verify

Run Task 1 first, then build Task 2 from the validated outputs:

```powershell
python etl.py
python warehouse.py
```

`warehouse.py` rebuilds the `warehouse` DuckDB schema without modifying
`raw`, `validated`, or `quarantine`. It casts source values using
`data_dictionary.csv`, assigns surrogate keys to dimensions, preserves the
employee SCD Type 2 `employee_key`, and adds primary keys to every dimension
and fact. `employee_key = 0` is a named inferred/unknown employee member for
passed fact rows with a missing or unavailable SCD key; their original employee
identifiers and source keys are retained in the fact and exceptions evidence.
The `ALL` department uses reserved `department_key = 0` for company-wide
forecasts. The calendar is extended through the forecast horizon so the
forecast date keys resolve.

Each fact row is loaded from its Task 1 `validated` table. Row totals are
compared with `etl.summary.rows_passed`; the build reports failure if any
fact count differs or if any populated key has no matching dimension row.

## Fact-to-dimension map

| Fact | Dimension joins |
|---|---|
| `fact_payroll` | employee version, date (month end), department, role |
| `fact_attendance_monthly` | employee version, date (month end), department |
| `fact_leave` | employee version, leave type, start date, end date |
| `fact_headcount_monthly` | department, date (month end) |
| `fact_ledger` | account, department/cost center (optional), date |
| `fact_invoice` | client, account/service line, invoice date |
| `fact_invoice_payment` | client, account, date (payment date), resolved through `invoice_id` to its invoice fact |
| `fact_expense` | vendor, account/category, department, expense date |
| `fact_task` | team, sprint, current assignee employee version |
| `fact_anomaly` | employee version effective at period end, period date |
| `fact_attrition_risk` | employee version, department, as-of date |
| `fact_forecast` | department (including `ALL`), forecast-month date |

The Mermaid ER diagram is in [star-schema.md](./star-schema.md).

## Employee history rule

Use the fact's `employee_key` to join to `dim_employee.employee_key`; do not
join historical payroll or attendance to the employee dimension by
`employee_id`. Each employee version has its own `employee_key` and
`valid_from` / `valid_to` dates. A June payroll row therefore joins to the
version valid for June, so June pay belongs to the employee's June department.
A July move to Support affects July's version and pay, not June's.

The task-board feed has no event date for its assignee; its assigned employee
key is resolved to the current employee version. Anomaly rows use the employee
version valid on the month-end date indicated by their period key. Attrition
rows already carry the versioned employee key.

## Evidence files

After a successful build:

- `warehouse_reconciliation.csv` lists every fact's Task 1 passed count,
  warehouse row count, difference, and status.
- `warehouse_orphan_checks.csv` lists each checked dimension relationship,
  source/checked row counts, orphan count, nullable-key count, and status.
- `warehouse_employee_scd_checks.csv` checks that fact employee keys preserve
  employee identity (and department/role where the source provides them).
- `warehouse_employee_key_exceptions.csv` lists passed fact rows that could
  not resolve to a real employee version and were mapped to the explicit
  unknown member rather than discarded.

The reconciliation and orphan outputs are also persisted as
`warehouse.reconciliation` and `warehouse.orphan_checks` in `pulseiq.duckdb`.
A blank ledger cost center is an
optional source key; it is reported separately from orphans. `fact_invoice_payment`
keeps `invoice_id` as its business key to the corresponding invoice fact.
The task-board team-lead field also has one legacy employee reference without
a current SCD row; its natural id remains in `dim_team` and its optional
surrogate key is null.

The supplied payroll feed contains two Task 1-passed rows with
`employee_key = -1` and nonexistent employee IDs. The anomaly feed has 21 rows
whose employee has no SCD version covering that anomaly's period end. Those 23
rows are retained and linked to the explicit unknown member (`employee_key =
0`); the source employee IDs/keys stay on the fact rows and each mapping is
listed in `warehouse_employee_key_exceptions.csv`. These are explained
unknown-member mappings, not silently dropped rows or unresolved dimension
orphans.

The calendar is extended 90 days beyond the source calendar to cover all
forecast dates. Public holiday flags for those generated future days are `N`
because no future holiday feed was supplied.
