# Task 10: budget versus actual and KPI targets

## Data and metric layer

The supplied `budget_payroll_dept_month.csv` (198 rows) and `kpi_targets.csv`
(180 rows) are stored with the source feeds in `data/raw/`. The ETL validates
their documented column types, the warehouse loads them as
`warehouse.budget_payroll_dept_month` and `warehouse.kpi_targets` with
department dimension keys, and warehouse composite keys enforce one
department/month row per source.

The **Budget versus actual** page is `pages/6_Budget_KPI.py`. It uses
`metrics.dashboard_budget_vs_actual` and
`metrics.dashboard_kpi_target_status`. Payroll actual is governed M09
employer payroll cost; KPI actuals use M13 attendance, M11 overtime share,
M04 monthly attrition, and a department/sprint-start-month task completion
rollup.

## Sign and traffic-light rules

- **Payroll variance = actual employer cost − approved budget.** Positive is
  overspend; negative is underspend. Variance percent is
  `(actual − budget) / budget × 100`.
- Payroll status is **green** at or under budget, **amber** for an overspend
  up to and including 5%, and **red** above 5%. The source includes budget
  values but no tolerance bands, so the 5% amber band is explicitly a
  dashboard review convention rather than a source-provided rule.
- KPI targets are compared in the target's unit. Attendance and task
  completion are green when actual is at or above target. Overtime share and
  attrition are green when actual is at or below target. The target file has
  no tolerance bands, so KPI status is binary green/red; missing target or
  suppressed actual is shown as a separate gray state.
- Task completion is Done tasks divided by non-cancelled tasks, grouped by the
  department owning the team and the sprint's start month. Cancelled tasks
  are excluded and task groups below five are suppressed.
- Department payroll rows are sourced from M09 and suppress groups below
  five paid employees. D00 has one paid employee and is omitted. Therefore
  reportable department sums intentionally do not claim to be the full
  company-wide payroll total.

## Three department/month hand checks

For September 2026, the budget values were read directly from the budget CSV.
Actual cost was independently summed from the cleaned payroll feed for the
department and payroll month, using distinct paid employees for the displayed
group size. The dashboard calculation was checked against these arithmetic
results.

| Department | Paid employees | Budget (INR) | Actual employer cost (INR) | Actual − budget (INR) | Variance (%) | Status |
|---|---:|---:|---:|---:|---:|---|
| Engineering (D01) | 169 | 20,787,000.00 | 21,001,404.24 | 214,404.24 | 1.03 | Amber |
| Data & AI (D03) | 52 | 6,394,000.00 | 6,424,889.62 | 30,889.62 | 0.48 | Amber |
| Sales (D04) | 47 | 11,597,000.00 | 11,159,004.22 | -437,995.78 | -3.78 | Green |

Example: Engineering variance is `21,001,404.24 − 20,787,000.00 =
214,404.24`; variance percent is `214,404.24 / 20,787,000.00 × 100 =
1.03%`, which falls in the dashboard's amber band.

## Mini challenge: trace one dashboard number in five lines

1. **Raw actual:** each eligible row in `data/raw/fact_payroll.csv` is one payroll item; keep September 2026 Engineering (D01) rows and sum `employer_cost` without exposing employee-level values.
2. **Clean/warehouse:** exact duplicate employee/run rows and unresolved employee IDs are removed from the reporting feed, then the remaining rows are loaded into `warehouse.fact_payroll`.
3. **Governed metric:** M09 in `metric_views.sql` groups by department/month, counts distinct paid employees, and sums employer cost; D01 has 169 paid employees and actual cost ₹21,001,404.24.
4. **Budget comparison:** `metrics.dashboard_budget_vs_actual` joins that M09 value to the D01 September budget of ₹20,787,000.00, then calculates actual minus budget = ₹214,404.24 (1.03%, amber, rank 1).
5. **Chart:** `pages/6_Budget_KPI.py` reads the comparison view and plots the D01 variance bar; the September ranking table and hover values come from the same view.

**Hand proof:** ₹21,001,404.24 − ₹20,787,000.00 = **₹214,404.24**. Divide by the budget and multiply by 100: ₹214,404.24 ÷ ₹20,787,000.00 × 100 = **1.03%**. That is positive, so it is an overspend; under the dashboard's explicitly stated convention, an overspend of up to 5% is amber. The hand-summed actual, M09, and chart source value are all ₹21,001,404.24.

## Reconciliation and variance in plain language

**Reconciliation** means checking that two independently produced records of
the same amount agree—for example, payroll employer cost against the approved
answer key or the related ledger total. A zero difference agrees; the known
June 2026 payroll/ledger difference of ₹18,450 does not, so it stays visible
for Finance to investigate rather than being silently adjusted.

**Variance** means the gap between what happened and what was planned. On this
page, actual minus budget is the rule: a positive amount means spending went
over plan, and a negative amount means spending came in under plan. It is a
comparison, not by itself proof that a team spent carelessly; an approved
budget can become outdated after a hiring freeze or other plan change.

## KPI hand check: Engineering (D01), September 2026

| KPI | Hand calculation | Actual | Target | Status |
|---|---|---:|---:|---|
| Attendance | 3,309.5 attendance days ÷ 3,441 scheduled days × 100 | 96.18% | 94.00% | Green |
| Overtime share | ₹0.00 overtime pay ÷ ₹21,001,404.24 employer cost × 100 | 0.00% | 0.50% | Green |
| Monthly attrition | 2 exits ÷ ((160 start + 167 end headcount) ÷ 2) × 100 | 1.22% | 1.00% | Red |
| Task completion | 257 Done ÷ 295 non-cancelled tasks × 100 | 87.12% | 80.00% | Green |

Task target periods align to sprint start month. The D10 task completion target
is blank in the source, so that target is shown as **No target**, not as a
failed KPI.

## Recommendations (default month: September 2026)

1. **Engineering (D01), rank 1:** ₹214,404 (1.03%) over budget with 169 paid
   employees. Reconcile paid headcount and joiner timing to the approved plan,
   then inspect overtime and one-off payroll components before deciding whether
   to update the forecast.
2. **Data & AI (D03), rank 2:** ₹30,890 (0.48%) over budget with 52 paid
   employees. Confirm department allocation and hiring/start-date assumptions,
   then track the next payroll close before taking corrective action; the
   current variance is within the dashboard's amber review band.

If a hiring freeze began after budget approval, keep the approved baseline
unchanged, annotate the freeze date and owner, and show a separately versioned
revised forecast. This distinguishes execution against the original plan from
the current operating outlook.

## Screenshot and validation

The page was rendered and its month/department controls were tested with
Streamlit `AppTest`. A browser screenshot is not included because this Windows
environment blocks the Streamlit executable through Application Control;
capture `docs/task10-budget-kpi.png` in an organization-approved Streamlit
environment if a screenshot is required.

- `python etl.py` loaded 198 budget rows and 180 target rows with zero
  quarantined rows for either feed. The ETL still reports the previously known
  June 2026 payroll/ledger mismatch as a critical failure; it is not repaired
  or concealed by this task.
- `python warehouse.py` reconciled 198/198 budget rows and 180/180 target
  rows, with no department-key orphans.
- `python metrics.py` rebuilt all 29 official metric views and passed their
  small-group checks and six hand checks.
- The payroll hand calculations for three department/months and the four
  Engineering KPI calculations match the metric-view values and target
  statuses.
- Python compilation, Streamlit `AppTest` for default/month/department
  filters, and `git diff --check` passed.
