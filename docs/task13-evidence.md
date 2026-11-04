# Task 13: cross-department impact view

## Grain and join order

The combined view is `metrics.dashboard_department_impact` at exactly one row
per department and month. Each source is aggregated independently to that grain
before joining:

1. `fact_headcount_monthly` supplies headcount, hires, exits and attrition.
2. Clean payroll supplies paid employees, employer cost, gross pay, overtime
   pay/hours, cost per head and overtime share.
3. `fact_attendance_monthly` supplies attendance, late arrivals and overtime
   hours.
4. Approved `fact_leave` is grouped by leave start month and effective employee
   department, supplying leave days and leave days per head.

Aggregating first prevents payroll rows from being multiplied by attendance or
leave rows.

## Reference reconciliation

`metrics.dashboard_department_impact_reconciliation` compares the combined
department-month view with `raw.reference_summary_dept_month` for every
comparable field. Leave metrics are dashboard additions because the reference
file has no leave columns. The page shows the selected month's differences for
employer cost, gross pay, overtime pay, attendance, attrition, cost per head
and overtime share.

The validation-vault unlock file `unlock_PQ-13` was not present in the
repository workspace, so no additional vault-only adjustment was applied.
The source reference table remains the comparison authority.

The current reconciliation results are:

- Employer cost, gross pay, overtime pay, attrition, and overtime share match
  the reference at the displayed precision.
- Attendance differs by at most 0.27 percentage points. This is retained as a
  visible difference because the supplied attendance feed contains the planted
  post-exit attendance issue; no source row is silently removed here.
- Cost per head has a maximum displayed difference of ₹0.01 from rounding.
- The reference has 198 department-month rows (11 departments × 18 months).
  The combined view has 891 headcount department-month rows across the full
  2020–2026 headcount history; months without payroll/attendance facts remain
  null for those measures rather than being imputed.

## Comparison table

This is the September 2026 department comparison table shown by the page
(employer cost is the chart's bar length; attrition is the chart label/colour):

| Department | Headcount | Paid employees | Employer cost (INR) | Overtime pay (INR) | Attrition (%) | Attendance (%) | Leave days/head |
|---|---:|---:|---:|---:|---:|---:|---:|
| Engineering | 167 | 169 | 21,001,404.24 | 0.00 | 1.25 | 96.18 | 0.48 |
| Sales | 46 | 47 | 11,159,004.22 | 0.00 | 2.17 | 97.54 | 0.24 |
| Data & AI | 52 | 52 | 6,424,889.62 | 0.00 | 0.00 | 94.43 | 0.73 |
| Product & Design | 26 | 26 | 4,176,418.79 | 0.00 | 0.00 | 95.33 | 0.35 |
| Customer Support | 59 | 59 | 2,920,847.37 | 71,516.60 | 0.00 | 92.43 | 0.73 |
| Finance & Accounts | 17 | 17 | 2,424,967.77 | 30,566.35 | 0.00 | 88.87 | 0.18 |
| Operations & IT | 29 | 29 | 2,327,018.88 | 61,686.66 | 0.00 | 95.95 | 0.52 |
| Human Resources | 20 | 20 | 1,635,278.81 | 29,226.82 | 0.00 | 95.81 | 0.65 |
| Legal & Compliance | 11 | 11 | 1,563,384.45 | 0.00 | 0.00 | 93.29 | 0.27 |
| Marketing | 13 | 13 | 1,381,169.72 | 0.00 | 0.00 | 96.15 | 0.38 |
| Executive Office | 1 | 1 | 505,238.00 | 0.00 | 0.00 | 100.00 | 0.00 |

## Difference notes

- **Employer cost, gross pay, overtime pay, attrition and overtime share:** no
  material difference from the reference at displayed precision.
- **Attendance:** maximum difference is 0.27 percentage points. This remains
  visible because the supplied attendance feed contains the planted post-exit
  attendance issue; no source record was silently removed.
- **Cost per head:** maximum difference is ₹0.01 from rounding.
- **Leave:** leave days and leave days per head are new additions and cannot be
  reconciled to the reference because `reference_summary_dept_month` has no
  leave columns.

## Interpretation

The department comparison chart ranks employer cost as horizontal bars, labels
each bar with attrition, and uses a clear attrition colour scale. Hover details
show overtime pay/hours, attendance, paid employees, and leave per head. High
overtime and attrition are correlated signals, not proof of causation.
Understaffing, seasonal workload, difficult projects, manager or role mix, and
reverse causality (attrition causing overtime) are alternative explanations.

## Validation and evidence

- `python metrics.py` rebuilt the metric layer successfully.
- `python -m py_compile pages/9_Department_Impact.py` passed.
- Streamlit AppTest rendered the page with no application exceptions.
- The reconciliation table is included on the page as evidence.
- Capture the page in an approved Streamlit environment for screenshot evidence.
