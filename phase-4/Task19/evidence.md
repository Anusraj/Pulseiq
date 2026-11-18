# Task 19 evidence

Generated from the local `pulseiq.duckdb` snapshot on 2026-11-17.

## API examples

The captured response evidence is in
[api_examples.json](api_examples.json). It contains a real response excerpt
for every exposed metric and the freshness endpoint. Each metric response
includes the numeric value, catalog definition, raw/ETL/warehouse/view/
dashboard source, and refresh metadata.

Representative response:

```json
{
  "metric_id": "M01",
  "metric_name": "Headcount",
  "period_start": "2026-09-01",
  "value": 167.0,
  "unit": "count",
  "definition": {
    "business_definition": "Active employees on the last day of the month (permanent and contract)."
  },
  "source": {
    "raw_table": "fact_headcount_monthly.csv",
    "etl": "etl.py validates the feed; warehouse.py builds the monthly headcount fact.",
    "warehouse_table": "warehouse.fact_headcount_monthly",
    "metric_view": "metrics.m01_headcount",
    "dashboard": "dashboard.py workforce KPI and headcount trend"
  },
  "last_refresh": {
    "data_cutoff": "2026-09-30",
    "refreshed_at": "2026-11-16T03:56:41.216614+00:00"
  }
}
```

The focused test suite exercised:

- `GET /api/v1/metrics` -> HTTP 200 with exactly five metrics.
- `GET /api/v1/metrics/M01` -> HTTP 200 with `value`, `definition`,
  `source`, and `last_refresh`.
- `GET /api/v1/metrics/M04` -> HTTP 200 with the monthly attrition definition
  and `metrics.m04_attrition_rate_monthly` source.
- `GET /api/v1/metrics/M09` -> HTTP 200 with payroll source lineage.
- `GET /api/v1/metrics/M17` -> HTTP 200 with ledger source lineage.
- `GET /api/v1/metrics/M20` -> HTTP 200 with invoice and ledger source lineage.
- `GET /api/v1/freshness` -> HTTP 200 with a data cut-off and plain-language
  freshness statement.
- `GET /api/v1/metrics/M99` -> HTTP 404, not a success-shaped fallback.

The endpoint commands are in [README.md](README.md); the complete captured
examples are in [api_examples.json](api_examples.json).

## Lineage evidence

[lineage.md](lineage.md) is the lineage diagram evidence. It contains five
Mermaid diagrams: one each for M01, M04, M09, M17, and M20. Every diagram has
the required path `raw table -> ETL -> warehouse table -> metric view ->
dashboard`. Its final table lists the exposed metrics affected by raw-column
renames.

## Checklist

| Requirement | Evidence |
| --- | --- |
| Each endpoint returns a definition and source | `api_examples.json`, all five metric response objects |
| Lineage covers five metrics end to end | `lineage.md`, five Mermaid diagrams |
| Freshness is stated | `GET /api/v1/freshness` in `api_examples.json`; `last_refresh` in every metric response |
| Examples work | Live Uvicorn smoke test plus `test_metrics_api.py` |

## Validation command

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s phase-4\Task19 -p "test_*.py" -v
```
