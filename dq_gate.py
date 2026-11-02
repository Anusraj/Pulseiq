"""Run and test the 14 catalogued data-quality checks."""

from __future__ import annotations

import argparse
import csv
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import duckdb
except ImportError as exc:
    raise SystemExit(
        "DuckDB is required. Activate the project virtual environment and run "
        "`python -m pip install -r starter/requirements.txt`."
    ) from exc


from clean_data import CLEANED_DIR


ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "pulseiq.duckdb"
CATALOG = CLEANED_DIR / "dq_checks_catalog.csv"
RESULTS_CSV = ROOT / "dq_results.csv"
FINDINGS_CSV = ROOT / "dq_findings.csv"
SELF_TEST_CSV = ROOT / "dq_self_test_results.csv"


CHECKS: list[dict[str, str]] = [
    {
        "check_id": "DQ-C01",
        "name": "Payroll equals ledger",
        "source_tables": "fact_payroll, fact_ledger",
        "sql": """
            WITH payroll AS (
                SELECT strftime(TRY_CAST(period_end_date AS DATE), '%Y-%m') AS month_key,
                       SUM(TRY_CAST(REPLACE(employer_cost, ',', '') AS DOUBLE)) AS payroll_cost
                FROM raw.fact_payroll
                GROUP BY 1
            ),
            ledger AS (
                SELECT posting_period AS month_key,
                       SUM(TRY_CAST(REPLACE(signed_amount_debit_positive, ',', '') AS DOUBLE)) AS ledger_cost
                FROM raw.fact_ledger
                WHERE TRY_CAST(account_code AS INTEGER) BETWEEN 5001 AND 5005
                GROUP BY 1
            )
            SELECT COALESCE(p.month_key, l.month_key) AS record_id,
                   'payroll=' || COALESCE(CAST(p.payroll_cost AS VARCHAR), '0') ||
                   '; ledger=' || COALESCE(CAST(l.ledger_cost AS VARCHAR), '0') ||
                   '; difference=' || CAST(COALESCE(p.payroll_cost, 0) - COALESCE(l.ledger_cost, 0) AS VARCHAR) AS detail
            FROM payroll p
            FULL OUTER JOIN ledger l USING (month_key)
            WHERE ABS(COALESCE(p.payroll_cost, 0) - COALESCE(l.ledger_cost, 0)) > 0.01
        """,
    },
    {
        "check_id": "DQ-C02",
        "name": "Ledger balanced",
        "source_tables": "fact_ledger",
        "sql": """
            SELECT entry_id AS record_id,
                   'debits=' || CAST(SUM(TRY_CAST(REPLACE(debit, ',', '') AS DOUBLE)) AS VARCHAR) ||
                   '; credits=' || CAST(SUM(TRY_CAST(REPLACE(credit, ',', '') AS DOUBLE)) AS VARCHAR) AS detail
            FROM raw.fact_ledger
            GROUP BY entry_id
            HAVING ABS(SUM(TRY_CAST(REPLACE(debit, ',', '') AS DOUBLE)) -
                       SUM(TRY_CAST(REPLACE(credit, ',', '') AS DOUBLE))) > 0.005
        """,
    },
    {
        "check_id": "DQ-C03",
        "name": "Unique payroll rows",
        "source_tables": "fact_payroll",
        "sql": """
            SELECT employee_id || '/' || run_id AS record_id,
                   'duplicate rows=' || CAST(COUNT(*) AS VARCHAR) AS detail
            FROM raw.fact_payroll
            GROUP BY employee_id, run_id
            HAVING COUNT(*) > 1
        """,
    },
    {
        "check_id": "DQ-C04",
        "name": "No orphan employees",
        "source_tables": "fact_payroll, dim_employee",
        "sql": """
            SELECT p.payroll_item_id AS record_id,
                   'employee_id=' || p.employee_id || ' is absent from dim_employee' AS detail
            FROM raw.fact_payroll p
            WHERE NOT EXISTS (
                SELECT 1 FROM raw.dim_employee d WHERE d.employee_id = p.employee_id
            )
        """,
    },
    {
        "check_id": "DQ-C05",
        "name": "No attendance after exit",
        "source_tables": "fact_attendance_monthly, dim_employee",
        "sql": """
            SELECT a.attendance_fact_id AS record_id,
                   'attendance=' || a.period_end_date || '; exit=' || d.exit_date AS detail
            FROM raw.fact_attendance_monthly a
            JOIN raw.dim_employee d
              ON a.employee_id = d.employee_id AND d.is_current = 'Y'
            WHERE NULLIF(TRIM(d.exit_date), '') IS NOT NULL
              AND DATE_TRUNC('month', TRY_CAST(a.period_end_date AS DATE)) >
                  DATE_TRUNC('month', TRY_CAST(d.exit_date AS DATE))
        """,
    },
    {
        "check_id": "DQ-C06",
        "name": "Unpaid leave deducted",
        "source_tables": "fact_attendance_monthly, fact_payroll",
        "sql": """
            WITH attendance AS (
                SELECT employee_id,
                       strftime(TRY_CAST(period_end_date AS DATE), '%Y-%m') AS month_key,
                       SUM(TRY_CAST(unpaid_absence_days AS DOUBLE)) AS unpaid_days
                FROM raw.fact_attendance_monthly
                GROUP BY 1, 2
            ),
            payroll AS (
                SELECT employee_id,
                       strftime(TRY_CAST(period_end_date AS DATE), '%Y-%m') AS month_key,
                       SUM(TRY_CAST(lop_days AS DOUBLE)) AS lop_days
                FROM raw.fact_payroll
                GROUP BY 1, 2
            )
            SELECT a.employee_id || '/' || a.month_key AS record_id,
                   'unpaid_absence_days=' || CAST(a.unpaid_days AS VARCHAR) ||
                   '; lop_days=' || CAST(COALESCE(p.lop_days, 0) AS VARCHAR) AS detail
            FROM attendance a
            LEFT JOIN payroll p USING (employee_id, month_key)
            WHERE a.unpaid_days > 0.5
              AND COALESCE(p.lop_days, 0) < a.unpaid_days - 0.5
        """,
    },
    {
        "check_id": "DQ-C07",
        "name": "Invoice arithmetic",
        "source_tables": "fact_invoice",
        "sql": """
            SELECT invoice_id AS record_id,
                   'paid=' || amount_paid || '; total=' || total_amount ||
                   '; balance=' || balance_due AS detail
            FROM raw.fact_invoice
            WHERE TRY_CAST(REPLACE(amount_paid, ',', '') AS DOUBLE) >
                      TRY_CAST(REPLACE(total_amount, ',', '') AS DOUBLE) + 0.01
               OR TRY_CAST(REPLACE(balance_due, ',', '') AS DOUBLE) < -0.01
        """,
    },
    {
        "check_id": "DQ-C08",
        "name": "Expense arithmetic",
        "source_tables": "fact_expense",
        "sql": """
            SELECT expense_id AS record_id,
                   'total=' || total_amount || '; excl_gst=' || amount_excl_gst ||
                   '; gst=' || gst_amount AS detail
            FROM raw.fact_expense
            WHERE ABS(
                TRY_CAST(REPLACE(total_amount, ',', '') AS DOUBLE) -
                TRY_CAST(REPLACE(amount_excl_gst, ',', '') AS DOUBLE) -
                TRY_CAST(REPLACE(gst_amount, ',', '') AS DOUBLE)
            ) > 0.01
        """,
    },
    {
        "check_id": "DQ-C09",
        "name": "Task dates sensible",
        "source_tables": "fact_task",
        "sql": """
            SELECT task_id AS record_id,
                   'status=' || status || '; started=' || COALESCE(started_date, '') ||
                   '; completed=' || COALESCE(completed_date, '') AS detail
            FROM raw.fact_task
            WHERE (
                NULLIF(TRIM(completed_date), '') IS NOT NULL
                AND NULLIF(TRIM(started_date), '') IS NOT NULL
                AND TRY_CAST(completed_date AS DATE) < TRY_CAST(started_date AS DATE)
            ) OR (
                LOWER(TRIM(status)) = 'done'
                AND NULLIF(TRIM(completed_date), '') IS NULL
            )
        """,
    },
    {
        "check_id": "DQ-C10",
        "name": "Leave dates sensible",
        "source_tables": "fact_leave",
        "sql": """
            SELECT leave_request_id AS record_id,
                   'start=' || start_date || '; end=' || end_date AS detail
            FROM raw.fact_leave
            WHERE TRY_CAST(end_date AS DATE) < TRY_CAST(start_date AS DATE)
        """,
    },
    {
        "check_id": "DQ-C11",
        "name": "AI feeds are fresh",
        "source_tables": "fact_attrition_risk, fact_anomaly",
        "sql": """
            WITH newest AS (
                SELECT MAX(TRY_CAST(as_of_date AS DATE)) AS latest_date
                FROM raw.fact_attrition_risk
            ),
            stale_predictions AS (
                SELECT prediction_id AS record_id,
                       'as_of_date=' || as_of_date || '; latest=' || CAST(newest.latest_date AS VARCHAR) AS detail
                FROM raw.fact_attrition_risk CROSS JOIN newest
                WHERE TRY_CAST(as_of_date AS DATE) < newest.latest_date - INTERVAL 7 DAY
            ),
            stale_anomalies AS (
                SELECT result_id AS record_id,
                       'scored_at=' || scored_at || '; older than 24 hours at load' AS detail
                FROM raw.fact_anomaly
                WHERE TRY_CAST(scored_at AS TIMESTAMP) < CURRENT_TIMESTAMP - INTERVAL 24 HOUR
            )
            SELECT * FROM stale_predictions
            UNION ALL
            SELECT * FROM stale_anomalies
        """,
    },
    {
        "check_id": "DQ-C12",
        "name": "Dimension history does not overlap",
        "source_tables": "dim_employee",
        "sql": """
            SELECT a.employee_id || '/' || a.employee_key || '/' || b.employee_key AS record_id,
                   'version intervals overlap: ' || a.valid_from || ' to ' ||
                   COALESCE(a.valid_to, 'open') || ' and ' || b.valid_from || ' to ' ||
                   COALESCE(b.valid_to, 'open') AS detail
            FROM raw.dim_employee a
            JOIN raw.dim_employee b
              ON a.employee_id = b.employee_id
             AND a.employee_key < b.employee_key
             AND TRY_CAST(a.valid_from AS DATE) <=
                 COALESCE(TRY_CAST(b.valid_to AS DATE), DATE '9999-12-31')
             AND TRY_CAST(b.valid_from AS DATE) <=
                 COALESCE(TRY_CAST(a.valid_to AS DATE), DATE '9999-12-31')
        """,
    },
    {
        "check_id": "DQ-C13",
        "name": "Pipeline freshness",
        "source_tables": "etl.run_log",
        "sql": """
            SELECT CAST(run_id AS VARCHAR) AS record_id,
                   'latest successful load finished at ' || CAST(finished_at AS VARCHAR) AS detail
            FROM etl.run_log
            WHERE status = 'SUCCEEDED'
              AND finished_at = (
                  SELECT MAX(finished_at) FROM etl.run_log WHERE status = 'SUCCEEDED'
              )
              AND finished_at < CURRENT_TIMESTAMP - INTERVAL 24 HOUR
            UNION ALL
            SELECT 'NO_SUCCESSFUL_LOAD' AS record_id, 'no successful ETL load is recorded' AS detail
            WHERE NOT EXISTS (SELECT 1 FROM etl.run_log WHERE status = 'SUCCEEDED')
        """,
    },
    {
        "check_id": "DQ-C14",
        "name": "Minimum group size",
        "source_tables": "reference_summary_dept_month, metric_dictionary, fact_attrition_risk",
        "sql": """
            WITH thresholds AS (
                SELECT metric_id, TRY_CAST(REGEXP_EXTRACT(minimum_group_size, '^[0-9]+', 0) AS INTEGER) AS min_size,
                       source_table
                FROM raw.metric_dictionary
                WHERE REGEXP_MATCHES(minimum_group_size, '^[0-9]+')
            ),
            published_groups AS (
                SELECT s.department_id, s.month, t.metric_id, t.min_size,
                       CASE
                         WHEN t.metric_id BETWEEN 'M01' AND 'M06' THEN TRY_CAST(s.headcount_end AS INTEGER)
                         WHEN t.metric_id BETWEEN 'M07' AND 'M15' THEN TRY_CAST(s.employees_paid AS INTEGER)
                         WHEN t.metric_id IN ('M22', 'M23', 'M25') THEN TRY_CAST(s.tasks AS INTEGER)
                         ELSE NULL
                       END AS group_size
                FROM raw.reference_summary_dept_month s
                CROSS JOIN thresholds t
                WHERE (t.metric_id BETWEEN 'M01' AND 'M06'
                       AND t.source_table LIKE 'fact_headcount_monthly%')
                   OR (t.metric_id BETWEEN 'M07' AND 'M12' OR t.metric_id IN ('M15'))
                   OR t.metric_id IN ('M13', 'M14')
                   OR t.metric_id IN ('M22', 'M23', 'M25')
            ),
            small_summary_groups AS (
                SELECT department_id || '/' || month || '/' || metric_id AS record_id,
                       'group size=' || COALESCE(CAST(group_size AS VARCHAR), '0') ||
                       '; minimum=' || CAST(min_size AS VARCHAR) AS detail
                FROM published_groups
                WHERE COALESCE(group_size, 0) > 0 AND group_size < min_size
            ),
            small_attrition_groups AS (
                SELECT r.department_id || '/' ||
                       strftime(TRY_CAST(r.as_of_date AS DATE), '%Y-%m') || '/M27' AS record_id,
                       'group size=' || CAST(COUNT(DISTINCT r.employee_id) AS VARCHAR) ||
                       '; minimum=10' AS detail
                FROM raw.fact_attrition_risk r
                GROUP BY r.department_id, strftime(TRY_CAST(r.as_of_date AS DATE), '%Y-%m')
                HAVING COUNT(DISTINCT r.employee_id) BETWEEN 1 AND 9
            )
            SELECT * FROM small_summary_groups
            UNION ALL
            SELECT * FROM small_attrition_groups
        """,
    },
]


def ensure_result_tables(connection: Any) -> None:
    connection.execute("CREATE SCHEMA IF NOT EXISTS etl")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS etl.run_log (
            run_id VARCHAR PRIMARY KEY,
            started_at TIMESTAMP NOT NULL,
            finished_at TIMESTAMP NOT NULL,
            status VARCHAR NOT NULL
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS etl.dq_runs (
            run_id VARCHAR PRIMARY KEY,
            started_at TIMESTAMP NOT NULL,
            finished_at TIMESTAMP NOT NULL,
            overall_status VARCHAR NOT NULL,
            critical_failures INTEGER NOT NULL,
            warning_failures INTEGER NOT NULL
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS etl.dq_results (
            run_id VARCHAR NOT NULL,
            check_id VARCHAR NOT NULL,
            check_name VARCHAR NOT NULL,
            source_tables VARCHAR NOT NULL,
            severity VARCHAR NOT NULL,
            bad_rows BIGINT NOT NULL,
            status VARCHAR NOT NULL,
            run_time TIMESTAMP NOT NULL,
            runtime_ms DOUBLE NOT NULL,
            sample_findings VARCHAR NOT NULL,
            PRIMARY KEY (run_id, check_id)
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS etl.dq_findings (
            run_id VARCHAR NOT NULL,
            check_id VARCHAR NOT NULL,
            record_id VARCHAR NOT NULL,
            detail VARCHAR NOT NULL
        )
    """)


def record_load_success(connection: Any, run_id: str, started_at: datetime) -> None:
    ensure_result_tables(connection)
    connection.execute(
        "INSERT INTO etl.run_log VALUES (?, ?, ?, 'SUCCEEDED')",
        [run_id, started_at.replace(tzinfo=None), datetime.now(timezone.utc).replace(tzinfo=None)],
    )


def run_gate(connection: Any, run_id: str) -> dict[str, Any]:
    ensure_result_tables(connection)
    started_at = datetime.now(timezone.utc).replace(tzinfo=None)
    with CATALOG.open("r", encoding="utf-8-sig", newline="") as stream:
        catalog = {row["check_id"]: row for row in csv.DictReader(stream)}
    result_rows: list[dict[str, Any]] = []
    findings: list[dict[str, str]] = []
    critical_failures = warning_failures = 0
    for check in CHECKS:
        metadata = catalog.get(check["check_id"])
        if metadata is None:
            raise ValueError(f"{check['check_id']} is missing from {CATALOG.name}")
        severity = metadata["severity"].strip().title()
        if severity not in {"Critical", "Warning"}:
            raise ValueError(f"Unsupported severity for {check['check_id']}: {severity}")
        check_started = time.perf_counter()
        rows = connection.execute(check["sql"]).fetchall()
        runtime_ms = (time.perf_counter() - check_started) * 1000
        bad_rows = len(rows)
        status = "PASS" if not bad_rows else ("FAIL" if severity == "Critical" else "WARN")
        if status == "FAIL":
            critical_failures += 1
        elif status == "WARN":
            warning_failures += 1
        encoded_rows = [
            (str(row[0]), str(row[1])) for row in rows
        ]
        findings.extend(
            {
                "run_id": run_id,
                "check_id": check["check_id"],
                "record_id": record_id,
                "detail": detail,
            }
            for record_id, detail in encoded_rows
        )
        result_rows.append(
            {
                "run_id": run_id,
                "check_id": check["check_id"],
                "check_name": check["name"],
                "source_tables": check["source_tables"],
                "severity": severity,
                "bad_rows": bad_rows,
                "status": status,
                "run_time": datetime.now(timezone.utc).replace(tzinfo=None),
                "runtime_ms": round(runtime_ms, 3),
                "sample_findings": json.dumps(encoded_rows[:5], ensure_ascii=False),
            }
        )
    finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
    overall_status = "BLOCKED" if critical_failures else ("WARN" if warning_failures else "PASS")
    connection.execute("BEGIN TRANSACTION")
    try:
        connection.executemany(
            "INSERT INTO etl.dq_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row["run_id"], row["check_id"], row["check_name"], row["source_tables"],
                    row["severity"], row["bad_rows"], row["status"], row["run_time"],
                    row["runtime_ms"], row["sample_findings"],
                )
                for row in result_rows
            ],
        )
        if findings:
            connection.executemany(
                "INSERT INTO etl.dq_findings VALUES (?, ?, ?, ?)",
                [
                    (row["run_id"], row["check_id"], row["record_id"], row["detail"])
                    for row in findings
                ],
            )
        connection.execute(
            "INSERT INTO etl.dq_runs VALUES (?, ?, ?, ?, ?, ?)",
            [run_id, started_at, finished_at, overall_status, critical_failures, warning_failures],
        )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    export_csv(RESULTS_CSV, result_rows)
    export_csv(FINDINGS_CSV, findings, ["run_id", "check_id", "record_id", "detail"])
    return {
        "run_id": run_id,
        "overall_status": overall_status,
        "critical_failures": critical_failures,
        "warning_failures": warning_failures,
        "results": result_rows,
        "findings": findings,
    }


def export_csv(path: Path, rows: list[Any], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def copy_raw_tables(connection: Any, table_names: list[str]) -> None:
    connection.execute("CREATE SCHEMA raw")
    for table in table_names:
        connection.execute(
            f"CREATE TABLE raw.{table} AS SELECT * FROM source.raw.{table}"
        )


def clone_and_insert(
    connection: Any,
    table: str,
    where: str,
    changes: dict[str, Any],
) -> None:
    columns = [row[0] for row in connection.execute(f"DESCRIBE raw.{table}").fetchall()]
    row = connection.execute(f"SELECT * FROM raw.{table} WHERE {where} LIMIT 1").fetchone()
    if row is None:
        raise AssertionError(f"Cannot find baseline row in raw.{table} for self-test")
    values = dict(zip(columns, row))
    values.update(changes)
    insert_columns = list(values)
    placeholders = ", ".join("?" for _ in insert_columns)
    connection.execute(
        f"INSERT INTO raw.{table} ({', '.join(insert_columns)}) VALUES ({placeholders})",
        [values[column] for column in insert_columns],
    )


SELF_TESTS: dict[str, tuple[list[str], Any]] = {
    "DQ-C01": (
        ["fact_payroll", "fact_ledger"],
        lambda c: clone_and_insert(
            c, "fact_payroll", "payroll_item_id IS NOT NULL",
            {"payroll_item_id": "DQTEST-C01", "run_id": "DQTEST-C01",
             "period_end_date": "2027-01-31", "employer_cost": "123.45"},
        ),
    ),
    "DQ-C02": (
        ["fact_ledger"],
        lambda c: clone_and_insert(
            c, "fact_ledger", "line_id IS NOT NULL",
            {"line_id": "DQTEST-C02", "entry_id": "DQTEST-C02", "debit": "100",
             "credit": "0"},
        ),
    ),
    "DQ-C03": (
        ["fact_payroll"],
        lambda c: inject_duplicate_payroll(c),
    ),
    "DQ-C04": (
        ["fact_payroll", "dim_employee"],
        lambda c: clone_and_insert(
            c, "fact_payroll", "payroll_item_id IS NOT NULL",
            {"payroll_item_id": "DQTEST-C04", "employee_id": "DQTEST-ORPHAN"},
        ),
    ),
    "DQ-C05": (
        ["fact_attendance_monthly", "dim_employee"],
        lambda c: clone_and_insert(
            c, "fact_attendance_monthly", "attendance_fact_id = 'FA-X0001'",
            {"attendance_fact_id": "DQTEST-C05"},
        ),
    ),
    "DQ-C06": (
        ["fact_attendance_monthly", "fact_payroll"],
        lambda c: clone_and_insert(
            c, "fact_attendance_monthly", "attendance_fact_id IS NOT NULL",
            {"attendance_fact_id": "DQTEST-C06", "period_end_date": "2099-01-31",
             "employee_id": "DQTEST-C06", "unpaid_absence_days": "3"},
        ),
    ),
    "DQ-C07": (
        ["fact_invoice"],
        lambda c: clone_and_insert(
            c, "fact_invoice", "invoice_id IS NOT NULL",
            {"invoice_id": "DQTEST-C07", "amount_paid": "200", "total_amount": "100",
             "balance_due": "-100"},
        ),
    ),
    "DQ-C08": (
        ["fact_expense"],
        lambda c: clone_and_insert(
            c, "fact_expense", "expense_id IS NOT NULL",
            {"expense_id": "DQTEST-C08", "amount_excl_gst": "100", "gst_amount": "18",
             "total_amount": "150"},
        ),
    ),
    "DQ-C09": (
        ["fact_task"],
        lambda c: clone_and_insert(
            c, "fact_task", "task_id IS NOT NULL",
            {"task_id": "DQTEST-C09", "started_date": "2026-01-20",
             "completed_date": "2026-01-10", "status": "Done"},
        ),
    ),
    "DQ-C10": (
        ["fact_leave"],
        lambda c: clone_and_insert(
            c, "fact_leave", "leave_request_id = 'LR-000025'",
            {"leave_request_id": "DQTEST-C10"},
        ),
    ),
    "DQ-C11": (
        ["fact_attrition_risk", "fact_anomaly"],
        lambda c: clone_and_insert(
            c, "fact_attrition_risk", "prediction_id IS NOT NULL",
            {"prediction_id": "DQTEST-C11", "as_of_date": "1900-01-01"},
        ),
    ),
    "DQ-C12": (
        ["dim_employee"],
        lambda c: clone_and_insert(
            c, "dim_employee", "employee_key = '100000'",
            {"employee_key": "DQTEST-C12", "valid_from": "2020-01-01",
             "valid_to": "9999-12-31"},
        ),
    ),
    "DQ-C13": (
        [],
        lambda c: (
            c.execute("CREATE SCHEMA etl"),
            c.execute("""
                CREATE TABLE etl.run_log (
                    run_id VARCHAR, started_at TIMESTAMP, finished_at TIMESTAMP, status VARCHAR
                )
            """),
            c.execute("""
                INSERT INTO etl.run_log
                VALUES ('DQTEST-C13', CURRENT_TIMESTAMP - INTERVAL 26 HOUR,
                        CURRENT_TIMESTAMP - INTERVAL 25 HOUR, 'SUCCEEDED')
            """),
        ),
    ),
    "DQ-C14": (
        ["reference_summary_dept_month", "metric_dictionary", "fact_attrition_risk"],
        lambda c: c.execute("""
            INSERT INTO raw.reference_summary_dept_month
            SELECT 'DQTEST-C14', '2099-01', employer_cost, gross_pay, overtime_pay,
                   '1', overtime_hours, late_arrivals, attendance_rate, '1', hires, exits,
                   attrition_rate_monthly_pct, tasks, tasks_done, story_points_done,
                   task_completion_rate_pct, cost_per_head, overtime_share_pct
            FROM raw.reference_summary_dept_month LIMIT 1
        """),
    ),
}

SELF_TEST_TOKENS = {
    "DQ-C01": "2027-01",
    "DQ-C02": "DQTEST-C02",
    "DQ-C03": "DQTEST-C03",
    "DQ-C04": "DQTEST-C04",
    "DQ-C05": "DQTEST-C05",
    "DQ-C06": "DQTEST-C06",
    "DQ-C07": "DQTEST-C07",
    "DQ-C08": "DQTEST-C08",
    "DQ-C09": "DQTEST-C09",
    "DQ-C10": "DQTEST-C10",
    "DQ-C11": "DQTEST-C11",
    "DQ-C12": "DQTEST-C12",
    "DQ-C13": "DQTEST-C13",
    "DQ-C14": "DQTEST-C14",
}


def inject_duplicate_payroll(connection: Any) -> None:
    for suffix in ("A", "B"):
        clone_and_insert(
            connection,
            "fact_payroll",
            "payroll_item_id IS NOT NULL",
            {
                "payroll_item_id": f"DQTEST-C03-{suffix}",
                "employee_id": "DQTEST-C03",
                "run_id": "DQTEST-C03",
            },
        )


def run_self_tests() -> list[dict[str, Any]]:
    if not CATALOG.is_file() or not DATABASE.is_file():
        raise FileNotFoundError("Run the ETL once before running DQ self-tests.")
    results: list[dict[str, Any]] = []
    escaped_database = str(DATABASE).replace("'", "''")
    for check in CHECKS:
        check_id = check["check_id"]
        connection = duckdb.connect(":memory:")
        try:
            connection.execute(f"ATTACH '{escaped_database}' AS source (READ_ONLY)")
            tables, inject = SELF_TESTS[check_id]
            if tables:
                copy_raw_tables(connection, tables)
            inject(connection)
            rows = connection.execute(check["sql"]).fetchall()
            test_id = SELF_TEST_TOKENS[check_id]
            matched_rows = [row for row in rows if test_id in str(row)]
            passed = bool(matched_rows)
            results.append(
                {
                    "check_id": check_id,
                    "check_name": check["name"],
                    "test_record_id": test_id,
                    "bad_rows_returned": len(rows),
                    "test_status": "PASS" if passed else "FAIL",
                    "proof": json.dumps(matched_rows[:3], default=str, ensure_ascii=False),
                }
            )
        finally:
            connection.close()
    export_csv(SELF_TEST_CSV, results)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="inject one deliberate bad row into an in-memory copy for each check",
    )
    args = parser.parse_args()
    if not args.self_test:
        parser.error("use --self-test; the production gate is run automatically by etl.py")
    results = run_self_tests()
    print(f"{'check':10} {'status':8} {'bad rows':>9} proof")
    for row in results:
        print(
            f"{row['check_id']:10} {row['test_status']:8} "
            f"{row['bad_rows_returned']:9,} {row['test_record_id']}"
        )
    print(f"Self-tests: {sum(r['test_status'] == 'PASS' for r in results)}/{len(results)} passed")
    print(f"Evidence: {SELF_TEST_CSV.name}")
    return 0 if len(results) == len(CHECKS) and all(r["test_status"] == "PASS" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
