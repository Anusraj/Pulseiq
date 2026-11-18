"""Re-check live reconciliation, metric, and data-quality evidence for Task 20."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import duckdb


ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "pulseiq.duckdb"
OUTPUT = Path(__file__).resolve().parent / "release_checks.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def run_checks() -> dict[str, Any]:
    reconciliation = read_csv(ROOT / "warehouse_reconciliation.csv")
    metric_validation = read_csv(ROOT / "metric_view_validation.csv")
    dq_results = read_csv(ROOT / "dq_results.csv")

    connection = duckdb.connect(str(DATABASE), read_only=True)
    try:
        warehouse_reconciliation = connection.execute(
            "SELECT COUNT(*) FROM warehouse.reconciliation WHERE status <> 'PASS'"
        ).fetchone()[0]
        metric_views = connection.execute(
            "SELECT COUNT(*) FROM information_schema.views WHERE table_schema = 'metrics'"
        ).fetchone()[0]
        catalog_metrics = connection.execute(
            "SELECT COUNT(*) FROM metrics.metric_catalog"
        ).fetchone()[0]
        latest_metric_period = connection.execute(
            "SELECT MAX(period_start) FROM metrics.m01_headcount"
        ).fetchone()[0]
    finally:
        connection.close()

    critical_failures = [
        {
            "check_id": row["check_id"],
            "check_name": row["check_name"],
            "bad_rows": int(row["bad_rows"]),
            "sample_findings": row["sample_findings"],
        }
        for row in dq_results
        if row["severity"] == "Critical" and row["status"] != "PASS"
    ]
    warnings = [
        {
            "check_id": row["check_id"],
            "check_name": row["check_name"],
            "bad_rows": int(row["bad_rows"]),
        }
        for row in dq_results
        if row["severity"] == "Warning" and row["status"] != "PASS"
    ]
    reconciliation_pass = (
        warehouse_reconciliation == 0
        and all(row["status"] == "PASS" and row["difference"] == "0" for row in reconciliation)
    )
    metrics_pass = (
        len(metric_validation) == catalog_metrics
        and all(row["status"] == "PASS" and row["below_minimum_groups"] == "0" for row in metric_validation)
    )
    status = "PASS" if reconciliation_pass and metrics_pass and not critical_failures else "CONDITIONAL_PASS"
    result = {
        "status": status,
        "database": str(DATABASE),
        "latest_headcount_period": str(latest_metric_period),
        "reconciliation": {
            "status": "PASS" if reconciliation_pass else "FAIL",
            "tables_checked": len(reconciliation),
            "warehouse_non_pass_rows": warehouse_reconciliation,
        },
        "metric_layer": {
            "status": "PASS" if metrics_pass else "FAIL",
            "catalog_metrics": catalog_metrics,
            "metric_views_in_schema": metric_views,
            "validated_views": len(metric_validation),
        },
        "data_quality": {
            "status": "PASS" if not critical_failures else "CONDITIONAL",
            "critical_failures": critical_failures,
            "warning_checks": warnings,
        },
        "decision_note": (
            "Do not approve payroll or cost decisions until DQ-C01 reconciles June 2026."
            if critical_failures
            else "No critical live-data quality failures were found."
        ),
    }
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    report = run_checks()
    print(json.dumps(report, indent=2))
