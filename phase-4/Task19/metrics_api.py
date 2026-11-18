"""FastAPI service for five governed PulseIQ metrics."""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


ROOT = Path(__file__).resolve().parents[2]
DATABASE = Path(os.environ.get("PULSEIQ_DATABASE", ROOT / "pulseiq.duckdb"))

EXPOSED_METRICS: dict[str, dict[str, str]] = {
    "M01": {"slug": "headcount", "view": "m01_headcount"},
    "M04": {"slug": "monthly-attrition", "view": "m04_attrition_rate_monthly"},
    "M09": {"slug": "employer-payroll-cost", "view": "m09_employer_payroll_cost"},
    "M17": {"slug": "net-profit", "view": "m17_net_profit"},
    "M20": {"slug": "days-sales-outstanding", "view": "m20_days_sales_outstanding"},
}
LOOKUP = {
    key: key for key in EXPOSED_METRICS
} | {
    details["slug"]: key for key, details in EXPOSED_METRICS.items()
}

LINEAGE: dict[str, dict[str, Any]] = {
    "M01": {
        "raw_table": "fact_headcount_monthly.csv",
        "raw_columns": ["employee_id", "hire_date", "exit_date", "department_id"],
        "etl": "etl.py validates the feed; warehouse.py builds the monthly headcount fact.",
        "warehouse_table": "warehouse.fact_headcount_monthly",
        "metric_view": "metrics.m01_headcount",
        "dashboard": "dashboard.py workforce KPI and headcount trend",
    },
    "M04": {
        "raw_table": "fact_headcount_monthly.csv",
        "raw_columns": ["department_id", "month_start_date", "exits", "headcount_start", "headcount_end"],
        "etl": "etl.py validates the feed; warehouse.py builds the monthly headcount fact.",
        "warehouse_table": "warehouse.fact_headcount_monthly",
        "metric_view": "metrics.m04_attrition_rate_monthly",
        "dashboard": "dashboard.py workforce movement KPI",
    },
    "M09": {
        "raw_table": "fact_payroll.csv",
        "raw_columns": ["employee_id", "period_end_date", "department_id", "employer_cost"],
        "etl": "etl.py validates and cleans payroll; warehouse.py builds the payroll fact.",
        "warehouse_table": "warehouse.fact_payroll",
        "metric_view": "metrics.m09_employer_payroll_cost",
        "dashboard": "dashboard.py payroll-cost consumers and report pack",
    },
    "M17": {
        "raw_table": "fact_ledger.csv",
        "raw_columns": ["posting_date", "account_code", "signed_amount"],
        "etl": "etl.py validates ledger rows; warehouse.py builds the ledger fact.",
        "warehouse_table": "warehouse.fact_ledger",
        "metric_view": "metrics.m17_net_profit",
        "dashboard": "pages/7_Profit_Loss.py net-profit KPI",
    },
    "M20": {
        "raw_table": "fact_invoice.csv and fact_ledger.csv",
        "raw_columns": ["fact_invoice.balance_due", "fact_invoice.due_date", "fact_ledger.signed_amount"],
        "etl": "etl.py validates invoice and ledger feeds; warehouse.py builds both facts.",
        "warehouse_table": "warehouse.fact_invoice + warehouse.fact_ledger",
        "metric_view": "metrics.m20_days_sales_outstanding",
        "dashboard": "pages/8_Receivables_Cash.py DSO KPI",
    },
}


class Freshness(BaseModel):
    data_cutoff: str
    refreshed_at: str
    statement: str


class MetricResponse(BaseModel):
    metric_id: str
    metric_name: str
    period_start: str
    value: float | None
    unit: str
    group_size: int | None
    numerator: float | None
    denominator: float | None
    data_status: str
    definition: dict[str, Any]
    source: dict[str, Any]
    last_refresh: Freshness


class MetricSummary(BaseModel):
    metric_id: str
    slug: str
    metric_name: str
    unit: str


app = FastAPI(
    title="PulseIQ Metrics API",
    version="1.0.0",
    description="Read-only access to five governed metrics and their data lineage.",
)


def _connection() -> duckdb.DuckDBPyConnection:
    if not DATABASE.exists():
        raise HTTPException(status_code=503, detail=f"Database not found: {DATABASE}")
    try:
        return duckdb.connect(str(DATABASE), read_only=True)
    except duckdb.Error as exc:
        raise HTTPException(status_code=503, detail="Metric database is unavailable") from exc


def _freshness(connection: duckdb.DuckDBPyConnection) -> Freshness:
    try:
        try:
            cutoff_row = connection.execute(
                "SELECT value FROM release_metadata WHERE key = 'data_cutoff'"
            ).fetchone()
        except duckdb.CatalogException:
            cutoff_row = None
        if cutoff_row:
            cutoff = str(cutoff_row[0])
        else:
            latest_periods = [
                connection.execute(
                    f"SELECT MAX(period_start) FROM metrics.{details['view']}"
                ).fetchone()[0]
                for details in EXPOSED_METRICS.values()
            ]
            cutoff = str(max(period for period in latest_periods if period is not None))
    except duckdb.Error as exc:
        raise HTTPException(status_code=503, detail="Could not read metric freshness") from exc

    refreshed_at = datetime.fromtimestamp(
        DATABASE.stat().st_mtime, tz=timezone.utc
    ).isoformat()
    return Freshness(
        data_cutoff=cutoff,
        refreshed_at=refreshed_at,
        statement=(
            f"Values are available through {cutoff}; the database file was last "
            f"refreshed at {refreshed_at}. Refresh the ETL and metric views before "
            "using a newer reporting period."
        ),
    )


def _metric_id(metric_key: str) -> str:
    metric_id = LOOKUP.get(metric_key) or LOOKUP.get(metric_key.upper())
    if not metric_id:
        raise HTTPException(
            status_code=404,
            detail=f"Metric '{metric_key}' is not exposed. Use /api/v1/metrics.",
        )
    return metric_id


def _definition(connection: duckdb.DuckDBPyConnection, metric_id: str) -> dict[str, Any]:
    try:
        row = connection.execute(
            """
            SELECT metric_name, business_definition, formula, source_table, grain,
                   time_period, owner_team, unit, good_direction, caveat
            FROM metrics.metric_catalog
            WHERE metric_id = ?
            """,
            [metric_id],
        ).fetchone()
    except duckdb.Error as exc:
        raise HTTPException(status_code=503, detail="Metric catalog is unavailable") from exc
    if not row:
        raise HTTPException(status_code=503, detail=f"Catalog entry missing for {metric_id}")
    columns = [
        "metric_name", "business_definition", "formula", "source_table", "grain",
        "time_period", "owner_team", "unit", "good_direction", "caveat",
    ]
    return dict(zip(columns, row))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "pulseiq-metrics-api"}


@app.get("/api/v1/freshness", response_model=Freshness)
def freshness() -> Freshness:
    connection = _connection()
    try:
        return _freshness(connection)
    finally:
        connection.close()


@app.get("/api/v1/metrics", response_model=list[MetricSummary])
def list_metrics() -> list[MetricSummary]:
    connection = _connection()
    try:
        result = []
        for metric_id, details in EXPOSED_METRICS.items():
            definition = _definition(connection, metric_id)
            result.append(
                MetricSummary(
                    metric_id=metric_id,
                    slug=details["slug"],
                    metric_name=definition["metric_name"],
                    unit=definition["unit"],
                )
            )
        return result
    finally:
        connection.close()


@app.get("/api/v1/metrics/{metric_key}", response_model=MetricResponse)
def get_metric(
    metric_key: str,
    period: date | None = None,
    department_id: str | None = None,
) -> MetricResponse:
    metric_id = _metric_id(metric_key)
    details = EXPOSED_METRICS[metric_id]
    connection = _connection()
    try:
        definition = _definition(connection, metric_id)
        freshness_data = _freshness(connection)
        query = f"""
            SELECT period_start, metric_value, unit, group_size, numerator,
                   denominator, data_status
            FROM metrics.{details["view"]}
            WHERE data_status = 'AVAILABLE'
              AND (? IS NULL OR period_start = ?)
              AND (? IS NULL OR department_id = ?)
            ORDER BY period_start DESC, department_id NULLS LAST
            LIMIT 1
        """
        try:
            row = connection.execute(
                query,
                [period, period, department_id, department_id],
            ).fetchone()
        except duckdb.Error as exc:
            raise HTTPException(status_code=503, detail="Metric view is unavailable") from exc
        if not row:
            raise HTTPException(status_code=404, detail="No available value matches the filters")

        lineage = LINEAGE[metric_id]
        return MetricResponse(
            metric_id=metric_id,
            metric_name=definition["metric_name"],
            period_start=str(row[0]),
            value=float(row[1]) if row[1] is not None else None,
            unit=row[2],
            group_size=int(row[3]) if row[3] is not None else None,
            numerator=float(row[4]) if row[4] is not None else None,
            denominator=float(row[5]) if row[5] is not None else None,
            data_status=row[6],
            definition=definition,
            source={
                "raw_table": lineage["raw_table"],
                "etl": lineage["etl"],
                "warehouse_table": lineage["warehouse_table"],
                "metric_view": lineage["metric_view"],
                "dashboard": lineage["dashboard"],
                "raw_columns": lineage["raw_columns"],
            },
            last_refresh=freshness_data,
        )
    finally:
        connection.close()

