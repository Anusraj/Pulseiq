# Task 9: payroll cost and reconciliation

## Dashboard and metric rules

The **Payroll cost** page is available from Streamlit's multipage navigation.
It uses the governed M07 gross-pay, M08 net-pay, M09 employer-cost and M10
cost-per-head views for department/month reporting. The company-wide monthly
aggregate uses the same cleaned payroll metric source, and its payroll-to-ledger
comparison uses M19's salary-related ledger total (accounts 5001-5005).

- Gross pay is earnings before employee deductions.
- Net pay is take-home pay after employee deductions.
- Employer cost is gross pay plus employer contributions, as defined by M09.
- Cost per paid employee is employer cost divided by distinct paid employees
  for that reportable group, as defined by M10.
- Department/month groups below the five-person M07-M10 minimum are suppressed.
  The company-wide values are shown only as an aggregate with more than five
  employees. Department totals can be lower than the company total because a
  small department group is not shown.
- The page displays only aggregate totals, paid headcounts and averages; it
  does not query or display employee-level payroll amounts.

## Answer-key reconciliation

The cleaned payroll totals were compared with the local reconciliation answer
key for April 2025 through September 2026. Paid employee counts and employer
cost match the key in every month. Gross and net pay also match the answer key
to the cent in all 18 months.

| Month | Employees (key / actual) | Employer cost (key / actual, INR) | Payroll minus key (INR) | Ledger salary expense actual (INR) | Payroll minus ledger (INR) |
|---|---:|---:|---:|---:|---:|
| 2025-04 | 386 / 386 | 53,363,392.08 / 53,363,392.08 | 0.00 | 53,363,392.08 | 0.00 |
| 2025-05 | 386 / 386 | 40,655,815.02 / 40,655,815.02 | 0.00 | 40,655,815.02 | 0.00 |
| 2025-06 | 392 / 392 | 45,894,752.35 / 45,894,752.35 | 0.00 | 45,894,752.35 | 0.00 |
| 2025-07 | 394 / 394 | 42,007,407.81 / 42,007,407.81 | 0.00 | 42,007,407.81 | 0.00 |
| 2025-08 | 399 / 399 | 42,379,943.75 / 42,379,943.75 | 0.00 | 42,379,943.75 | 0.00 |
| 2025-09 | 397 / 397 | 47,109,100.73 / 47,109,100.73 | 0.00 | 47,109,100.73 | 0.00 |
| 2025-10 | 403 / 403 | 45,106,613.42 / 45,106,613.42 | 0.00 | 45,106,613.42 | 0.00 |
| 2025-11 | 399 / 399 | 42,835,467.20 / 42,835,467.20 | 0.00 | 42,835,467.20 | 0.00 |
| 2025-12 | 403 / 403 | 47,322,486.26 / 47,322,486.26 | 0.00 | 47,322,486.26 | 0.00 |
| 2026-01 | 406 / 406 | 43,356,745.90 / 43,356,745.90 | 0.00 | 43,356,745.90 | 0.00 |
| 2026-02 | 414 / 414 | 44,044,038.71 / 44,044,038.71 | 0.00 | 44,044,038.71 | 0.00 |
| 2026-03 | 414 / 414 | 49,088,022.23 / 49,088,022.23 | 0.00 | 49,088,022.23 | 0.00 |
| 2026-04 | 413 / 413 | 62,168,025.50 / 62,168,025.50 | 0.00 | 62,168,025.50 | 0.00 |
| 2026-05 | 413 / 413 | 47,694,768.74 / 47,694,768.74 | 0.00 | 47,694,768.74 | 0.00 |
| 2026-06 | 421 / 421 | 54,664,233.35 / 54,664,233.35 | 0.00 | 54,682,683.35 | -18,450.00 |
| 2026-07 | 427 / 427 | 48,980,037.26 / 48,980,037.26 | 0.00 | 48,980,037.26 | 0.00 |
| 2026-08 | 429 / 429 | 49,395,920.24 / 49,395,920.24 | 0.00 | 49,395,920.24 | 0.00 |
| 2026-09 | 444 / 444 | 55,519,621.87 / 55,519,621.87 | 0.00 | 55,519,621.87 | 0.00 |

### Remaining ledger difference

The remaining variance is not in the cleaned payroll totals: June 2026 payroll
employer cost equals the answer key at ₹54,664,233.35, while ledger accounts
5001-5005 total ₹54,682,683.35, or ₹18,450.00 more. The known issue is
`DQ-04` in `data/raw/dq_known_issues.csv` and names journal `JE-002094`
(ledger lines `JL-005614` and `JL-005643`). The full journal entry balances;
the available evidence does not establish a safe correction to an individual
ledger line. The dashboard flags that month, the sources remain unchanged, and
no balancing adjustment is fabricated.

## Payroll rows excluded from the cleaned reporting feed

| Payroll item | Treatment | Reason |
|---|---|---|
| `PI-X0001` | Deduplicated; retained `PI-004059` | Exact duplicate employee/run record. |
| `PI-X0002` | Deduplicated; retained `PI-000761` | Exact duplicate employee/run record. |
| `PI-X0003` | Excluded | Employee ID is absent from `dim_employee`; the payroll fact cannot be attributed to a valid employee dimension record. |
| `PI-X0004` | Excluded | Employee ID is absent from `dim_employee`; the payroll fact cannot be attributed to a valid employee dimension record. |

The raw input is preserved. These four exceptions are recorded in
`data/cleaned/cleaning_report.csv`; identical duplicate rows are removed and
orphan payroll rows are excluded from the clean feed rather than guessed or
rewritten.

## Calm explanation for Finance

We found four payroll rows that should not be counted: two exact duplicate employee/run rows and two records whose employee IDs do not exist in the employee dimension.
We retained the original feed, deduplicated the exact repeats, and excluded only unresolved employee records from the cleaned reporting data; the excluded payroll item IDs and reasons are listed above.
After those exclusions, monthly headcount, gross pay, net pay and employer cost agree with the answer key for all 18 months, while a separate June 2026 ledger difference of ₹18,450.00 remains documented and unaltered.

## Validation

- `python metrics.py` rebuilt all 29 official metric views and passed the
  metric privacy checks and six metric hand checks.
- All 18 monthly employee counts and gross, net and employer payroll totals
  matched the answer key; the June payroll-to-ledger difference remains
  explicitly flagged.
- Department rows are sourced only from M07-M10 and the minimum group size
  observed in the department view is five.
- `python -m py_compile pages/5_Payroll_Cost.py` passed.
- Streamlit `AppTest` checked the default page, month and department filters,
  trend charts, exclusion table and the June variance warning.
