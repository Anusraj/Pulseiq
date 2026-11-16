# Task 16: Automated report builder and release candidate

## Monthly pack

`python phase4/task-16/build_report.py --month 2026-09` creates
`phase4/task-16/reports/pulseiq-2026-09.pdf` with five report surfaces:

1. Executive KPI scorecard.
2. P&L summary.
3. Payroll by department.
4. Budget versus actual payroll, including an actual-cost chart.
5. Team productivity, including a completion-rate chart.

The header stamps the complete reporting date range, the latest data cut-off
used by the selected governed views, and the generation timestamp. The
department and team tables are data-driven; there is no hard-coded department
list.

## Scheduling and setup

Dependencies are pinned in `requirements.txt`. A clean machine can follow the
PowerShell setup in [README.md](../../README.md), rebuild the ETL/warehouse/metric
layer, and run the one-command report builder. GitHub Actions runs
`.github/workflows/monthly-report.yml` at 06:00 UTC on the first day of each
month for the previous month. It also supports a manually supplied `YYYY-MM`.

PyArrow is explicitly pinned to `17.0.0` because Streamlit's dataframe
renderer loads its native `pyarrow.lib` extension. This version was imported
successfully in the project environment after Windows Application Control
blocked the unpinned newer wheel.

## Validation and clean-machine evidence

- `python -m unittest discover -s phase4/task-16/tests -p "test_*.py" -v`: passed.
- `python phase4/task-16/build_report.py --month 2026-09`: passed and produced the sample PDF.
- The report test uses a fresh temporary DuckDB containing a new
  **New Department** and verifies that the PDF builds successfully. This
  demonstrates that a new department does not break the report or require a
  code edit.
- The pinned dependency set was checked against the project virtual
  environment before release.

## Release candidate

Release candidate tag: `v1.0.0-rc1`.
