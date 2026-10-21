# PulseIQ analytics workspace

## Run the ETL

Use Python 3.11 or newer from this folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r starter\requirements.txt
python etl.py
```

The starter-compatible entry point also works:

```powershell
python starter\load_to_duckdb.py
```

The pipeline reads every CSV in `data\raw` and the root `readme.csv`, and
creates `pulseiq.duckdb`. It can be rerun safely: each run replaces the
source, validated, quarantine, and summary tables. Run it a second time to
confirm stable counts. Every successful load also runs the 14-check data
quality gate against the untouched `raw` inputs. Critical failures are
recorded, printed, and make the command exit nonzero so a scheduler or
downstream step can block publication; warning checks do not block it.

## Where the data goes

- `raw`: every input CSV loaded as text, preserving original field values.
- `validated`: rows that pass the available contracts and data dictionary.
- `quarantine`: rejected rows, source row number, JSON copy of the row, and
  human-readable reason.
- `etl.summary`: per-input row counts and schema warnings.
- `etl.run_log`, `etl.dq_runs`, `etl.dq_results`, and `etl.dq_findings`:
  timestamped ETL and quality-gate history.
- `etl_summary.csv`: the same summary, convenient for a report.
- `dq_results.csv` and `dq_findings.csv`: latest run's manager summary and
  row-level check findings.
- `dq_self_test_results.csv`: evidence from the isolated tests described in
  [the Task 3 guide](docs/dq-gate.md).

For every input, `rows_in = rows_passed + rows_quarantined` is asserted before
the run completes. Unexpected columns warn and are retained; missing
contracted columns fail the run. See [CONTRACT_NOTES.md](CONTRACT_NOTES.md)
for the notes on the anomaly, attrition-risk, forecast, and task contracts.

Run the isolated test suite to prove every DQ query catches a deliberately
bad row. It copies relevant source tables into separate in-memory databases,
adds the test row there, and never modifies the production `raw` tables:

```powershell
python dq_gate.py --self-test
```

## Useful DuckDB checks

```sql
SELECT * FROM etl.summary ORDER BY table_name;

SELECT table_name, rows_in, rows_passed, rows_quarantined,
       rows_in = rows_passed + rows_quarantined AS reconciles
FROM etl.summary
ORDER BY table_name;

SELECT source_row_number, reason, row_data
FROM quarantine.fact_task
LIMIT 20;
```

## Build the Task 2 warehouse

After the Task 1 ETL completes, build the star-schema warehouse:

```powershell
python warehouse.py
```

The script builds the `warehouse` schema from `validated` rows and verifies
fact reconciliation and dimensional orphans. See [the warehouse guide](docs/warehouse.md)
and [the Mermaid ER diagram](docs/star-schema.md). The run creates
`warehouse_reconciliation.csv` and `warehouse_orphan_checks.csv` as report
evidence; see the [Task 2 evidence summary](docs/task2-evidence.md).

See the [Task 3 DQ guide](docs/dq-gate.md) for plain-language check meanings,
stop-versus-warn decisions, the planted-issue coverage, and evidence outputs.

## Build the Task 4 governed metric layer

After rebuilding the Task 1 inputs and Task 2 warehouse, run:

```powershell
python metrics.py
```

This creates 28 reusable views in the DuckDB `metrics` schema, plus
`metrics.metric_catalog`. Every official view uses the same aggregate output
shape and applies its catalog minimum group size before returning rows.
Payroll views use the validated warehouse and a helper that excludes unknown
employee keys and collapses exact duplicate payroll records; raw and Task 1
quarantine data remain unchanged.

Generated evidence includes `metric_catalog.csv` and
`metric_hand_checks.csv`, plus `metric_view_validation.csv` with view row counts
and small-group audit results. See [the Task 4 metric-layer guide](docs/task4-metric-layer.md)
for formulas, the small-group policy, hand-check arithmetic, and the
attrition-denominator decision.
