# Task 18: Self-service KPI explorer with privacy

Task 18 provides a governed Streamlit explorer for aggregate KPIs. It uses
the catalog's minimum group size and a hard privacy floor of five records
before any result is rendered.

## Run locally

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m streamlit run pages\12_KPI_Explorer.py
```

The page wrapper loads [kpi_explorer.py](kpi_explorer.py). The explorer reads
only the published aggregate DuckDB snapshot and never queries raw employee,
payroll-detail, or salary-level tables.

## Role and dimension policy

| Demo user | Role | Metrics | Dimensions |
| --- | --- | --- | --- |
| `admin.demo` | ADMIN | All governed explorer metrics | Company, Department, Team |
| `hr.demo` | HR | People, payroll, attendance, and risk aggregates | Company, Department |
| `manager.demo` | MANAGER | M22-M25 delivery metrics | Team |
| `exec.demo` | EXECUTIVE | Company-level workforce and finance KPIs | Company |

These are demonstration identities, not authentication. Production access
must be supplied by the hosting platform or SSO.

## Privacy behavior

- Every query applies `max(catalog minimum, 5)` before rendering.
- Suppressed groups are filtered from the result table, not merely masked.
- Team drill-down is restricted to M22-M25.
- The manager view is restricted to the first demonstration team and displays
  no value when that team's reportable group is below five.
- Company aggregation uses the latest period and the metric numerator and
  denominator rather than averaging already-derived percentages.

## Break-it checks

1. A manager cannot select payroll or company-only metrics.
2. A manager cannot select Department or Company drill levels.
3. Team selection for a non-team metric stops with a clear warning.
4. A small manager team returns an empty result and a privacy explanation.
5. HR and executive roles do not receive unavailable dimensions.

## Evidence and validation

See [evidence.md](evidence.md) for the tested role matrix and privacy
outcomes. Run the focused tests with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s phase4\task-18 -p "test_*.py" -v
```
