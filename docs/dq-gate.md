# Task 3: data-quality gatekeeper

## Run and evidence

The normal command runs the full ETL and then all 14 data-quality checks:

```powershell
python etl.py
```

Checks read the untouched `raw` source tables, rather than only the rows that
passed Task 1 contracts. That lets the gate catch business-quality problems
even when a row was also quarantined for a separate contract failure. The raw
feeds are retained and check findings are persisted; a critical failure makes
the process exit nonzero so a scheduler or downstream publication step can
stop. The loader does not discard or rewrite a source row to make a check pass.

Prove each SQL check works with the isolated test command:

```powershell
python dq_gate.py --self-test
```

For each check this creates an in-memory copy of the relevant source table(s),
injects a uniquely marked bad row, and executes the same SQL used by the
production gate. It verifies that the result contains the injected marker.
These tests do not write to the live `raw` tables.

Evidence created by the latest ETL run:

- `dq_results.csv`: one manager-readable row per check, with severity, number
  of returned bad rows, status, runtime, and up to five sample findings.
- `dq_findings.csv`: every returned record and its reason/detail.
- `dq_self_test_results.csv`: isolated test result and proof for each check.
- DuckDB history tables `etl.dq_runs`, `etl.dq_results`, and `etl.dq_findings`.
- `etl.run_log`: successful source-load timestamps used by the freshness check.

The CSV summaries represent the latest run; the DuckDB tables retain run
history. A check with bad rows is `FAIL` when critical and `WARN` when warning.
The overall result is `BLOCKED` if any critical check fails, `WARN` if only
warnings fail, and `PASS` otherwise.

## What each check protects

| Check | Plain-language risk caught | Severity | Decision |
|---|---|---|---|
| DQ-C01 Payroll equals ledger | Payroll employer cost does not reconcile to salary-related ledger accounts 5001-5005 by month (tolerance ₹0.01). | Critical | Block publication; the mismatch makes financial totals untrustworthy. |
| DQ-C02 Ledger balanced | Journal-entry debits and credits differ by more than ₹0.005. | Critical | Block publication; an unbalanced journal is not a valid posting. |
| DQ-C03 Unique payroll rows | An employee appears more than once in the same payroll run. | Critical | Block publication; duplicates can overstate compensation. |
| DQ-C04 No orphan employees | A payroll employee ID has no employee-dimension record. | Critical | Block publication; payroll cannot be attributed reliably. |
| DQ-C05 No attendance after exit | An attendance month occurs after the employee's exit month. | Warning | Retain and report; HR must confirm exit timing before attendance reporting. |
| DQ-C06 Unpaid leave deducted | Unpaid attendance absence exceeds payroll LOP by more than 0.5 days. | Warning | Retain and report; confirm leave mapping with Payroll. |
| DQ-C07 Invoice arithmetic | Amount paid exceeds total or balance due is negative by more than ₹0.01. | Warning | Retain and report; Finance must correct the receivable before using it. |
| DQ-C08 Expense arithmetic | Expense total differs from pre-GST amount plus GST by more than ₹0.01. | Warning | Retain and report; correct the bill before expense analysis. |
| DQ-C09 Task dates sensible | Completion predates start, or a Done task has no completion date. | Warning | Retain and report; Engineering Ops should correct task history. |
| DQ-C10 Leave dates sensible | Leave end date is earlier than its start date. | Warning | Retain and report; HR should correct the leave request. |
| DQ-C11 AI feeds are fresh | Attrition scores are more than seven days behind the latest batch, or anomaly scoring is older than 24 hours at load time. | Warning | Retain and report; stale model output should not be presented as current. |
| DQ-C12 Dimension history does not overlap | Two employee SCD versions cover the same date. | Critical | Block publication; one fact can otherwise join to two employee versions. |
| DQ-C13 Pipeline freshness | No successful ETL run exists, or the latest successful load is older than 24 hours. | Critical | Block publication; consumers must not assume stale data is current. |
| DQ-C14 Minimum group size | A manager-facing department/month/metric aggregate has fewer members than its metric-dictionary minimum. | Critical | Block publication of affected cells; suppress or combine small groups. |

Critical failures gate publication, not source capture: ingesting and retaining
the raw data and the failure evidence is necessary for audit and repair.
Warnings do not make the entire load unavailable, but the report identifies
the rows that require an owner to review them.

## Seeded-issue comparison

The supplied `data/raw/dq_known_issues.csv` lists 11 planted issues. All 11
are represented in the current raw-feed findings:

| Seeded issue | Expected check | Result |
|---|---|---|
| DQ-01 attendance after exit | DQ-C05 | Detected (4 attendance rows) |
| DQ-02 duplicate payroll | DQ-C03 | Detected (2 employee/run groups) |
| DQ-03 payroll employees missing from dimension | DQ-C04 | Detected (2 payroll rows) |
| DQ-04 June payroll/ledger mismatch | DQ-C01 | Detected (June variance ₹18,450) |
| DQ-05 overpaid invoice | DQ-C07 | Detected (1 invoice) |
| DQ-06 completion before task start | DQ-C09 | Detected (12 tasks) |
| DQ-07 Done task without completion date | DQ-C09 | Detected (8 tasks) |
| DQ-08 leave end before start | DQ-C10 | Detected (2 requests) |
| DQ-09 stale attrition predictions | DQ-C11 | Detected (5 predictions) |
| DQ-10 expense total mismatch | DQ-C08 | Detected (1 expense) |
| DQ-11 overlapping employee SCD versions | DQ-C12 | Detected (1 employee-version pair) |

**Known-issue misses: 0 of 11.** This comparison is against the supplied
`dq_known_issues.csv`. The separate `04_Validation_Vault/unlock_PQ-03` answer
key was not present in this repository or local project files, so it could
not be opened. No claim is made about additional issues that may be listed
only in that unavailable vault.

Other findings are reported rather than silently ignored. For example, the
ledger check also reveals month-level mismatches attributable to the duplicate
and orphan payroll rows, the leave-deduction check finds an additional
employee-month discrepancy, and the minimum-group-size check identifies
aggregate cells that must be suppressed. Stale anomaly scores are also
included by the AI-feed freshness check.
