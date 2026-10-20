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
confirm stable counts.

## Where the data goes

- `raw`: every input CSV loaded as text, preserving original field values.
- `validated`: rows that pass the available contracts and data dictionary.
- `quarantine`: rejected rows, source row number, JSON copy of the row, and
  human-readable reason.
- `etl.summary`: per-input row counts and schema warnings.
- `etl_summary.csv`: the same summary, convenient for a report.

For every input, `rows_in = rows_passed + rows_quarantined` is asserted before
the run completes. Unexpected columns warn and are retained; missing
contracted columns fail the run. See [CONTRACT_NOTES.md](CONTRACT_NOTES.md)
for the notes on the anomaly, attrition-risk, forecast, and task contracts.

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
