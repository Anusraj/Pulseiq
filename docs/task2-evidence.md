# Task 2 warehouse evidence

Built from the Task 1 `validated` tables by `python warehouse.py`.

## Reconciliation

- **12 fact tables**, **57,506 rows** total.
- Every warehouse fact row count equals its Task 1 `rows_passed` value.
- **0 count differences** across the 12 facts.
- The warehouse has **23 primary-key constraints**: one on each of 11
  dimensions and one on each of 12 facts.

See [warehouse_reconciliation.csv](../warehouse_reconciliation.csv) for the
per-fact counts.

## Orphan checks

- **45 key relationships checked**.
- **0 orphan keys** and **0 failed checks**.
- 5,688 ledger rows have no cost-center department key; this field is optional
  for those ledger rows. One team has a legacy team-lead employee ID with no
  current SCD row; its natural ID is retained and the surrogate key is
  optional. These null optional keys are reported, not counted as orphans.

See [warehouse_orphan_checks.csv](../warehouse_orphan_checks.csv) for each
relationship and its result.

## Employee SCD checks

- **6 SCD identity checks**, covering **47,783 fact rows**.
- **0 identity, department, or role mismatches**.
- **23 source rows** are explicitly mapped to the unknown employee dimension
  member (`employee_key = 0`): 2 payroll rows with invalid source key `-1`, and
  21 anomaly rows with no employee SCD version effective on the period end.
  Their source employee identifiers remain in the fact rows.

See [warehouse_employee_scd_checks.csv](../warehouse_employee_scd_checks.csv)
and [warehouse_employee_key_exceptions.csv](../warehouse_employee_key_exceptions.csv).
The SCD check and exception detail are also stored in the DuckDB warehouse
schema.

## SCD rule

Historical facts join on `employee_key`, the surrogate key for the employee
version valid for that fact. Therefore, June pay belongs to the employee
department stored on the June employee version. A department move effective in
July creates a different version for July; it must not rewrite June's cost.
