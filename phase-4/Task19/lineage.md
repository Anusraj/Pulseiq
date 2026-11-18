# Task 19 metric lineage

Each diagram traces the value returned by the API from the raw feed through
ETL, the warehouse, the governed metric view, and the consuming dashboard.
The API response repeats the same source fields so a caller does not need to
open this document to understand a number.

## M01 Headcount

```mermaid
flowchart LR
  raw["fact_headcount_monthly.csv<br/>employee_id, hire_date, exit_date, department_id"]
  etl["etl.py + data-quality gate"]
  warehouse["warehouse.fact_headcount_monthly"]
  metric["metrics.m01_headcount<br/>COUNT DISTINCT active employees"]
  dashboard["dashboard.py<br/>headcount KPI and trend"]
  raw --> etl --> warehouse --> metric --> dashboard
```

## M04 Monthly attrition

```mermaid
flowchart LR
  raw["fact_headcount_monthly.csv<br/>department_id, month_start_date, exits, headcount_start, headcount_end"]
  etl["etl.py + data-quality gate"]
  warehouse["warehouse.fact_headcount_monthly"]
  metric["metrics.m04_attrition_rate_monthly<br/>exits / average headcount x 100"]
  dashboard["dashboard.py<br/>movement KPI"]
  raw --> etl --> warehouse --> metric --> dashboard
```

## M09 Employer payroll cost

```mermaid
flowchart LR
  raw["fact_payroll.csv<br/>employee_id, period_end_date, department_id, employer_cost"]
  etl["etl.py + payroll cleaning"]
  warehouse["warehouse.fact_payroll"]
  metric["metrics.m09_employer_payroll_cost<br/>SUM employer_cost"]
  dashboard["dashboard.py / report pack<br/>payroll cost"]
  raw --> etl --> warehouse --> metric --> dashboard
```

## M17 Net profit

```mermaid
flowchart LR
  raw["fact_ledger.csv<br/>posting_date, account_code, signed_amount"]
  etl["etl.py + data-quality gate"]
  warehouse["warehouse.fact_ledger"]
  metric["metrics.m17_net_profit<br/>revenue less expenses"]
  dashboard["pages/7_Profit_Loss.py<br/>net-profit KPI"]
  raw --> etl --> warehouse --> metric --> dashboard
```

## M20 Days sales outstanding

```mermaid
flowchart LR
  raw["fact_invoice.csv + fact_ledger.csv<br/>balance_due, due_date, signed_amount"]
  etl["etl.py + data-quality gate"]
  warehouse["warehouse.fact_invoice + warehouse.fact_ledger"]
  metric["metrics.m20_days_sales_outstanding<br/>receivables / credit sales x 90"]
  dashboard["pages/8_Receivables_Cash.py<br/>DSO KPI"]
  raw --> etl --> warehouse --> metric --> dashboard
```

## Raw-column rename impact

The following exposed metrics would break or change if the named raw columns
were renamed without updating the ETL contracts and downstream SQL:

| Raw column change | Metrics affected |
| --- | --- |
| `employee_id`, `hire_date`, `exit_date`, or `department_id` in headcount feed | M01, M04 |
| `month_start_date`, `exits`, `headcount_start`, or `headcount_end` | M04 |
| `employee_id`, `period_end_date`, `department_id`, or `employer_cost` in payroll feed | M09 |
| `posting_date`, `account_code`, or `signed_amount` in ledger feed | M17 and M20 |
| `balance_due` or `due_date` in invoice feed | M20 |

These are schema dependencies, not guesses: they are the columns declared in
the API's `source.raw_columns` field and in each diagram.
