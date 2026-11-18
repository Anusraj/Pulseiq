# Task 19: Metrics API and data lineage

Task 19 exposes five governed metrics from the existing DuckDB metric layer:
M01 headcount, M04 monthly attrition, M09 employer payroll cost, M17 net
profit, and M20 days sales outstanding.

## Run locally

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r phase4\task-19\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn metrics_api:app --app-dir phase4\task-19 --reload
```

The API is then available at `http://127.0.0.1:8000`. Interactive OpenAPI
documentation is at `/docs`.

## Endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Service health |
| `GET /api/v1/metrics` | The five exposed metrics |
| `GET /api/v1/metrics/{metric_id_or_slug}` | Latest value, definition, source, lineage, and refresh |
| `GET /api/v1/freshness` | Data cut-off, database refresh time, and plain-language statement |

Examples:

```powershell
curl http://127.0.0.1:8000/api/v1/metrics/M01
curl "http://127.0.0.1:8000/api/v1/metrics/headcount?period=2026-09-01&department_id=D01"
curl http://127.0.0.1:8000/api/v1/freshness
```

An individual response has this shape:

```json
{
  "metric_id": "M01",
  "metric_name": "Headcount",
  "period_start": "2026-09-01",
  "value": 42.0,
  "unit": "count",
  "definition": {
    "business_definition": "Active employees on the last day of the month",
    "formula": "COUNT(DISTINCT employee_id) ..."
  },
  "source": {
    "raw_table": "fact_headcount_monthly.csv",
    "etl": "etl.py validates the feed",
    "warehouse_table": "warehouse.fact_headcount_monthly",
    "metric_view": "metrics.m01_headcount",
    "dashboard": "dashboard.py workforce KPI and headcount trend"
  },
  "last_refresh": {
    "data_cutoff": "2026-09-30",
    "refreshed_at": "2026-11-17T...",
    "statement": "Values are available through 2026-09-30; ..."
  }
}
```

The API is read-only and uses parameterized filters. It never queries raw
tables directly; values come from the governed `metrics` views.

## Freshness in the app

The existing Streamlit workforce app already shows the published data cut-off
and selected reporting period below its filters (`dashboard.py`). Task 19
uses the same `release_metadata.data_cutoff` value in the API, so the app and
API make the same freshness claim. The API additionally reports the UTC
database-file refresh timestamp and a plain-language freshness statement.

## Deployment

The dashboard remains deployed as the Streamlit service. Deploy this API as a
second service from the same GitHub repository (for example, a Render web
service) with:

- Root directory: repository root
- Build command: `python -m pip install -r phase4\task-19\requirements.txt`
- Start command: `uvicorn metrics_api:app --app-dir phase4\task-19 --host 0.0.0.0 --port $PORT`
- Health check path: `/health`

The service must include the repository's `pulseiq.duckdb` (or set
`PULSEIQ_DATABASE` to an equivalent read-only database path). Streamlit Cloud
and the API host are separate services because the dashboard host does not run
an ASGI process alongside Streamlit.

## Evidence

- [lineage.md](lineage.md) contains five end-to-end diagrams and raw-column
  rename impact analysis.
- [evidence.md](evidence.md) records live example responses and validation.
- `test_metrics_api.py` checks all five endpoints, metadata, freshness, and
  explicit unknown-metric errors.
