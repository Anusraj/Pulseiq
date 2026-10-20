"""Build and reconcile the PulseIQ dimensional warehouse from Task 1 outputs."""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

try:
    import duckdb
except ImportError as exc:
    raise SystemExit(
        "DuckDB is required. Activate the project virtual environment and run "
        "`python -m pip install -r starter\\requirements.txt`."
    ) from exc


ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "pulseiq.duckdb"
RECONCILIATION_FILE = ROOT / "warehouse_reconciliation.csv"
ORPHAN_FILE = ROOT / "warehouse_orphan_checks.csv"

DIMENSION_SOURCES = (
    "dim_account",
    "dim_client",
    "dim_date",
    "dim_department",
    "dim_employee",
    "dim_leave_type",
    "dim_location",
    "dim_role",
    "dim_sprint",
    "dim_team",
    "dim_vendor",
)

FACT_SOURCES = (
    "fact_payroll",
    "fact_attendance_monthly",
    "fact_leave",
    "fact_headcount_monthly",
    "fact_ledger",
    "fact_invoice",
    "fact_invoice_payment",
    "fact_expense",
    "fact_task",
    "fact_anomaly",
    "fact_attrition_risk",
    "fact_forecast",
)

FACT_PRIMARY_KEYS = {
    "fact_payroll": ("payroll_item_id",),
    "fact_attendance_monthly": ("attendance_fact_id",),
    "fact_leave": ("leave_request_id",),
    "fact_headcount_monthly": ("date_key", "department_key"),
    "fact_ledger": ("line_id",),
    "fact_invoice": ("invoice_id",),
    "fact_invoice_payment": ("payment_id",),
    "fact_expense": ("expense_id",),
    "fact_task": ("task_id",),
    "fact_anomaly": ("result_id",),
    "fact_attrition_risk": ("prediction_id",),
    "fact_forecast": ("forecast_id",),
}


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def target_type(source_type: str) -> str:
    value = source_type.strip().lower()
    if value in {"text", "string", "varchar", "char(1)"}:
        return "VARCHAR"
    if value in {"integer", "int", "smallint", "bigint"}:
        return "BIGINT"
    if value in {"decimal", "numeric"} or value.startswith(("decimal(", "numeric(")):
        return "DOUBLE"
    if value == "date":
        return "DATE"
    if value in {"timestamp", "datetime"}:
        return "TIMESTAMP"
    raise ValueError(f"Unsupported dictionary type {source_type!r}")


def typed_expression(column: str, source_type: str) -> str:
    identifier = quote_identifier(column)
    sql_type = target_type(source_type)
    if sql_type == "VARCHAR":
        return f"NULLIF({identifier}, '')::VARCHAR AS {identifier}"
    cleaned = f"NULLIF(REPLACE({identifier}, ',', ''), '')"
    return f"TRY_CAST({cleaned} AS {sql_type}) AS {identifier}"


def create_typed_views(connection: Any) -> dict[str, list[str]]:
    dictionary: dict[str, dict[str, str]] = {}
    for table, column, data_type in connection.execute(
        'SELECT lower("sheet"), "column", lower(data_type) '
        "FROM validated.data_dictionary"
    ).fetchall():
        dictionary.setdefault(table, {})[column] = data_type

    schemas: dict[str, list[str]] = {}
    for table in (*DIMENSION_SOURCES, *FACT_SOURCES):
        columns = [
            row[0]
            for row in connection.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'validated' AND table_name = ? "
                "ORDER BY ordinal_position",
                [table],
            ).fetchall()
        ]
        if not columns:
            raise ValueError(f"Task 1 output is missing validated.{table}")
        missing_types = sorted(set(columns) - set(dictionary.get(table, {})))
        if missing_types:
            raise ValueError(
                f"data_dictionary.csv is missing {table} columns: {', '.join(missing_types)}"
            )
        expressions = ", ".join(
            typed_expression(column, dictionary[table][column]) for column in columns
        )
        connection.execute(
            f"CREATE OR REPLACE TEMP VIEW {quote_identifier('src_' + table)} "
            f"AS SELECT {expressions} FROM validated.{quote_identifier(table)}"
        )
        schemas[table] = columns
    return schemas


def create_dimensions(connection: Any, schemas: dict[str, list[str]]) -> None:
    connection.execute(
        "CREATE TABLE warehouse.dim_department AS "
        "SELECT row_number() OVER (ORDER BY department_id)::BIGINT AS department_key, d.* "
        "FROM src_dim_department d"
    )
    department_columns = schemas["dim_department"]
    sentinel_columns = ["0::BIGINT", "'ALL'::VARCHAR", "'All departments'::VARCHAR"] + [
        "NULL" for _ in department_columns[2:]
    ]
    connection.execute(
        "INSERT INTO warehouse.dim_department "
        f"SELECT {', '.join(sentinel_columns)}"
    )

    connection.execute(
        "CREATE TABLE warehouse.dim_account AS "
        "SELECT row_number() OVER (ORDER BY account_code)::BIGINT AS account_key, a.* "
        "FROM src_dim_account a"
    )
    connection.execute(
        "CREATE TABLE warehouse.dim_client AS "
        "SELECT row_number() OVER (ORDER BY client_id)::BIGINT AS client_key, c.*, "
        "a.account_key AS primary_service_account_key "
        "FROM src_dim_client c LEFT JOIN warehouse.dim_account a "
        "ON c.primary_service_line = a.account_code"
    )
    connection.execute(
        "CREATE TABLE warehouse.dim_date AS "
        "SELECT d.* FROM src_dim_date d"
    )
    connection.execute(
        "CREATE TABLE warehouse.dim_leave_type AS "
        "SELECT row_number() OVER (ORDER BY leave_type_code)::BIGINT AS leave_type_key, l.* "
        "FROM src_dim_leave_type l"
    )
    connection.execute(
        "CREATE TABLE warehouse.dim_location AS "
        "SELECT row_number() OVER (ORDER BY work_location)::BIGINT AS location_key, l.* "
        "FROM src_dim_location l"
    )
    connection.execute(
        "CREATE TABLE warehouse.dim_role AS "
        "SELECT row_number() OVER (ORDER BY r.role_id)::BIGINT AS role_key, r.*, "
        "d.department_key "
        "FROM src_dim_role r LEFT JOIN warehouse.dim_department d "
        "ON r.department_id = d.department_id"
    )
    connection.execute(
        "CREATE TABLE warehouse.dim_sprint AS "
        "SELECT row_number() OVER (ORDER BY sprint_id)::BIGINT AS sprint_key, s.* "
        "FROM src_dim_sprint s"
    )
    connection.execute(
        "CREATE TABLE warehouse.dim_vendor AS "
        "SELECT row_number() OVER (ORDER BY v.vendor_id)::BIGINT AS vendor_key, v.*, "
        "a.account_key AS primary_expense_account_key "
        "FROM src_dim_vendor v LEFT JOIN warehouse.dim_account a "
        "ON v.primary_expense_account = a.account_code"
    )
    connection.execute(
        "CREATE TABLE warehouse.dim_employee AS "
        "SELECT e.*, d.department_key, r.role_key, l.location_key "
        "FROM src_dim_employee e "
        "LEFT JOIN warehouse.dim_department d ON e.department_id = d.department_id "
        "LEFT JOIN warehouse.dim_role r ON e.role_id = r.role_id "
        "LEFT JOIN warehouse.dim_location l ON e.work_location = l.work_location"
    )
    employee_columns = schemas["dim_employee"] + [
        "department_key",
        "role_key",
        "location_key",
    ]
    unknown_employee = {column: None for column in employee_columns}
    unknown_employee.update(
        {
            "employee_key": 0,
            "employee_id": "UNKNOWN",
            "full_name": "Unknown / inferred employee",
            "employment_status": "Unknown",
            "employment_type": "Unknown",
            "is_current": "N",
        }
    )
    connection.execute(
        "INSERT INTO warehouse.dim_employee "
        f"({', '.join(quote_identifier(column) for column in employee_columns)}) "
        f"VALUES ({', '.join('?' for _ in employee_columns)})",
        [unknown_employee[column] for column in employee_columns],
    )
    connection.execute(
        "CREATE TABLE warehouse.dim_team AS "
        "SELECT row_number() OVER (ORDER BY t.team_id)::BIGINT AS team_key, t.*, "
        "d.department_key, lead.employee_key AS team_lead_employee_key "
        "FROM src_dim_team t "
        "LEFT JOIN warehouse.dim_department d ON t.department_id = d.department_id "
        "LEFT JOIN warehouse.dim_employee lead "
        "ON t.team_lead_employee_id = lead.employee_id AND lead.is_current = 'Y'"
    )


def extend_date_dimension(connection: Any) -> int:
    min_needed, current_max = connection.execute(
        "SELECT max(strptime(CAST(forecast_month_key AS VARCHAR), '%Y%m%d')::DATE), "
        "(SELECT max(date) FROM warehouse.dim_date) "
        "FROM src_fact_forecast"
    ).fetchone()
    if min_needed is None or current_max is None or min_needed <= current_max:
        return 0
    connection.execute(
        "INSERT INTO warehouse.dim_date "
        "SELECT d::DATE AS date, "
        "CAST(strftime(d, '%Y%m%d') AS BIGINT) AS date_key, "
        "year(d)::BIGINT AS year, quarter(d)::BIGINT AS quarter, "
        "month(d)::BIGINT AS month_number, strftime(d, '%B') AS month_name, "
        "strftime(d, '%Y-%m') AS year_month, week(d)::BIGINT AS week_of_year, "
        "strftime(d, '%A') AS day_of_week, "
        "CASE WHEN dayofweek(d) IN (0, 6) THEN 'Y' ELSE 'N' END AS is_weekend, "
        "'N'::VARCHAR AS is_holiday, "
        "CASE WHEN dayofweek(d) IN (0, 6) THEN 'N' ELSE 'Y' END AS is_working_day, "
        "CASE WHEN month(d) >= 4 "
        "THEN concat('FY', year(d), '-', lpad(CAST((year(d) + 1) % 100 AS VARCHAR), 2, '0')) "
        "ELSE concat('FY', year(d) - 1, '-', lpad(CAST(year(d) % 100 AS VARCHAR), 2, '0')) "
        "END AS financial_year, "
        "CASE WHEN month(d) IN (4, 5, 6) THEN 'Q1' "
        "WHEN month(d) IN (7, 8, 9) THEN 'Q2' "
        "WHEN month(d) IN (10, 11, 12) THEN 'Q3' ELSE 'Q4' END AS fiscal_quarter, "
        "((month(d) + 8) % 12 + 1)::BIGINT AS fiscal_month_number, "
        "CASE WHEN d = last_day(d) THEN 'Y' ELSE 'N' END AS is_month_end, "
        "date_trunc('month', d)::DATE AS month_start_date, "
        "last_day(d)::DATE AS month_end_date "
        "FROM generate_series(?::DATE + INTERVAL 1 DAY, ?::DATE, INTERVAL 1 DAY) AS days(d)",
        [current_max, min_needed],
    )
    return connection.execute(
        "SELECT count(*) FROM warehouse.dim_date WHERE date > ?::DATE", [current_max]
    ).fetchone()[0]


def create_facts(connection: Any) -> None:
    sql_by_fact = {
        "fact_payroll": (
            "LEFT JOIN warehouse.dim_employee e ON b.employee_key = e.employee_key "
            "LEFT JOIN warehouse.dim_department d ON b.department_id = d.department_id "
            "LEFT JOIN warehouse.dim_role r ON b.role_id = r.role_id",
            "b.employee_key AS source_employee_key, "
            "coalesce(e.employee_key, 0)::BIGINT AS employee_key, "
            "CASE WHEN e.employee_key IS NULL THEN "
            "'UNKNOWN_SOURCE_EMPLOYEE_KEY' ELSE 'MATCHED_SCD_EMPLOYEE_KEY' "
            "END AS employee_key_resolution, d.department_key, r.role_key",
        ),
        "fact_attendance_monthly": (
            "LEFT JOIN warehouse.dim_department d ON b.department_id = d.department_id",
            "d.department_key",
        ),
        "fact_leave": (
            "LEFT JOIN warehouse.dim_leave_type l ON b.leave_type_code = l.leave_type_code",
            "l.leave_type_key",
        ),
        "fact_headcount_monthly": (
            "LEFT JOIN warehouse.dim_department d ON b.department_id = d.department_id",
            "d.department_key",
        ),
        "fact_ledger": (
            "LEFT JOIN warehouse.dim_account a ON b.account_code = a.account_code "
            "LEFT JOIN warehouse.dim_department d "
            "ON b.cost_center_department_id = d.department_id",
            "a.account_key, d.department_key",
        ),
        "fact_invoice": (
            "LEFT JOIN warehouse.dim_client c ON b.client_id = c.client_id "
            "LEFT JOIN warehouse.dim_account a ON b.service_line_account = a.account_code",
            "c.client_key, a.account_key",
        ),
        "fact_invoice_payment": (
            "LEFT JOIN warehouse.fact_invoice i ON b.invoice_id = i.invoice_id",
            "i.client_key, i.account_key",
        ),
        "fact_expense": (
            "LEFT JOIN warehouse.dim_vendor v ON b.vendor_id = v.vendor_id "
            "LEFT JOIN warehouse.dim_account a ON b.category_account = a.account_code "
            "LEFT JOIN warehouse.dim_department d ON b.department_id = d.department_id",
            "v.vendor_key, a.account_key, d.department_key",
        ),
        "fact_task": (
            "LEFT JOIN warehouse.dim_team t ON b.team_id = t.team_id "
            "LEFT JOIN warehouse.dim_sprint s ON b.sprint_id = s.sprint_id",
            "t.team_key, s.sprint_key, "
            "(SELECT e.employee_key FROM warehouse.dim_employee e "
            "WHERE e.employee_id = b.assignee_employee_id AND e.is_current = 'Y' "
            "ORDER BY e.valid_from DESC, e.employee_key DESC LIMIT 1) AS assignee_employee_key",
        ),
        "fact_anomaly": (
            "",
            "CAST(b.period_key AS BIGINT) AS date_key, "
            "coalesce((SELECT e.employee_key FROM warehouse.dim_employee e "
            "WHERE e.employee_id = b.employee_id "
            "AND strptime(CAST(b.period_key AS VARCHAR), '%Y%m%d')::DATE "
            "BETWEEN e.valid_from AND coalesce(e.valid_to, DATE '9999-12-31') "
            "ORDER BY e.valid_from DESC, e.employee_key DESC LIMIT 1), 0)::BIGINT "
            "AS employee_key, "
            "CASE WHEN EXISTS (SELECT 1 FROM warehouse.dim_employee e "
            "WHERE e.employee_id = b.employee_id "
            "AND strptime(CAST(b.period_key AS VARCHAR), '%Y%m%d')::DATE "
            "BETWEEN e.valid_from AND coalesce(e.valid_to, DATE '9999-12-31')) "
            "THEN 'MATCHED_SCD_VERSION' ELSE 'UNKNOWN_NO_VERSION_AT_PERIOD_END' "
            "END AS employee_key_resolution",
        ),
        "fact_attrition_risk": ("", "CAST(b.as_of_date_key AS BIGINT) AS date_key"),
        "fact_forecast": ("", "CAST(b.forecast_month_key AS BIGINT) AS forecast_date_key"),
    }
    for fact in FACT_SOURCES:
        joins, additional = sql_by_fact[fact]
        additions = f", {additional}" if additional else ""
        base_select = "b.*"
        if fact == "fact_payroll":
            base_select = "b.* EXCLUDE (employee_key)"
        connection.execute(
            f"CREATE TABLE warehouse.{quote_identifier(fact)} AS "
            f"SELECT {base_select}{additions} "
            f"FROM {quote_identifier('src_' + fact)} b {joins}"
        )


def add_primary_keys(connection: Any) -> None:
    keys = {
        "dim_account": ("account_key",),
        "dim_client": ("client_key",),
        "dim_date": ("date_key",),
        "dim_department": ("department_key",),
        "dim_employee": ("employee_key",),
        "dim_leave_type": ("leave_type_key",),
        "dim_location": ("location_key",),
        "dim_role": ("role_key",),
        "dim_sprint": ("sprint_key",),
        "dim_team": ("team_key",),
        "dim_vendor": ("vendor_key",),
        **FACT_PRIMARY_KEYS,
    }
    for table, columns in keys.items():
        primary_key = ", ".join(quote_identifier(column) for column in columns)
        connection.execute(
            f"ALTER TABLE warehouse.{quote_identifier(table)} "
            f"ADD PRIMARY KEY ({primary_key})"
        )


def create_employee_key_exceptions(connection: Any) -> list[dict[str, Any]]:
    connection.execute(
        "CREATE TABLE warehouse.employee_key_exceptions AS "
        "SELECT 'fact_payroll'::VARCHAR AS source_table, "
        "payroll_item_id::VARCHAR AS record_id, employee_id::VARCHAR AS employee_id, "
        "CAST(source_employee_key AS VARCHAR) AS source_employee_key, "
        "CAST(period_end_date AS VARCHAR) AS event_date, "
        "employee_key AS mapped_employee_key, employee_key_resolution AS explanation "
        "FROM warehouse.fact_payroll WHERE employee_key_resolution <> 'MATCHED_SCD_EMPLOYEE_KEY' "
        "UNION ALL "
        "SELECT 'fact_anomaly'::VARCHAR, result_id::VARCHAR, employee_id::VARCHAR, "
        "NULL::VARCHAR, CAST(period AS VARCHAR), employee_key, employee_key_resolution "
        "FROM warehouse.fact_anomaly "
        "WHERE employee_key_resolution <> 'MATCHED_SCD_VERSION'"
    )
    return [
        {
            "source_table": row[0],
            "record_id": row[1],
            "employee_id": row[2],
            "source_employee_key": row[3],
            "event_date": row[4],
            "mapped_employee_key": row[5],
            "explanation": row[6],
        }
        for row in connection.execute(
            "SELECT source_table, record_id, employee_id, source_employee_key, "
            "event_date, mapped_employee_key, explanation "
            "FROM warehouse.employee_key_exceptions ORDER BY source_table, record_id"
        ).fetchall()
    ]


def run_employee_scd_checks(connection: Any) -> list[dict[str, Any]]:
    checks = [
        (
            "fact_payroll_employee_version",
            "SELECT count(*), count(*) FILTER (WHERE "
            "e.employee_id IS DISTINCT FROM f.employee_id OR "
            "e.department_id IS DISTINCT FROM f.department_id OR "
            "e.role_id IS DISTINCT FROM f.role_id) "
            "FROM warehouse.fact_payroll f JOIN warehouse.dim_employee e "
            "ON f.employee_key = e.employee_key WHERE f.employee_key <> 0",
        ),
        (
            "fact_attendance_employee_version",
            "SELECT count(*), count(*) FILTER (WHERE "
            "e.employee_id IS DISTINCT FROM f.employee_id OR "
            "e.department_id IS DISTINCT FROM f.department_id) "
            "FROM warehouse.fact_attendance_monthly f JOIN warehouse.dim_employee e "
            "ON f.employee_key = e.employee_key",
        ),
        (
            "fact_leave_employee_version",
            "SELECT count(*), count(*) FILTER (WHERE "
            "e.employee_id IS DISTINCT FROM f.employee_id) "
            "FROM warehouse.fact_leave f JOIN warehouse.dim_employee e "
            "ON f.employee_key = e.employee_key",
        ),
        (
            "fact_attrition_employee_version",
            "SELECT count(*), count(*) FILTER (WHERE "
            "e.employee_id IS DISTINCT FROM f.employee_id OR "
            "e.department_id IS DISTINCT FROM f.department_id) "
            "FROM warehouse.fact_attrition_risk f JOIN warehouse.dim_employee e "
            "ON f.employee_key = e.employee_key",
        ),
        (
            "fact_task_current_assignee",
            "SELECT count(*), count(*) FILTER (WHERE "
            "e.employee_id IS DISTINCT FROM f.assignee_employee_id OR e.is_current <> 'Y') "
            "FROM warehouse.fact_task f JOIN warehouse.dim_employee e "
            "ON f.assignee_employee_key = e.employee_key",
        ),
        (
            "fact_anomaly_employee_at_period_end",
            "SELECT count(*), count(*) FILTER (WHERE "
            "e.employee_id IS DISTINCT FROM f.employee_id OR "
            "strptime(CAST(f.date_key AS VARCHAR), '%Y%m%d')::DATE "
            "NOT BETWEEN e.valid_from AND coalesce(e.valid_to, DATE '9999-12-31')) "
            "FROM warehouse.fact_anomaly f JOIN warehouse.dim_employee e "
            "ON f.employee_key = e.employee_key WHERE f.employee_key <> 0",
        ),
    ]
    results: list[dict[str, Any]] = []
    for name, query in checks:
        checked, mismatches = connection.execute(query).fetchone()
        results.append(
            {
                "check_name": name,
                "rows_checked": checked,
                "mismatch_rows": mismatches,
                "status": "PASS" if mismatches == 0 else "FAIL",
            }
        )
    connection.execute(
        "CREATE TABLE warehouse.employee_scd_checks "
        "(check_name VARCHAR, rows_checked BIGINT, mismatch_rows BIGINT, status VARCHAR)"
    )
    connection.executemany(
        "INSERT INTO warehouse.employee_scd_checks VALUES (?, ?, ?, ?)",
        [tuple(row.values()) for row in results],
    )
    return results


def run_orphan_checks(connection: Any) -> list[dict[str, Any]]:
    checks = [
        ("dim_client.primary_service_account_key", "dim_client", "primary_service_account_key", "dim_account", "account_key", True),
        ("dim_employee.department_key", "dim_employee", "department_key", "dim_department", "department_key", False),
        ("dim_employee.role_key", "dim_employee", "role_key", "dim_role", "role_key", False),
        ("dim_employee.location_key", "dim_employee", "location_key", "dim_location", "location_key", False),
        ("dim_role.department_key", "dim_role", "department_key", "dim_department", "department_key", False),
        ("dim_team.department_key", "dim_team", "department_key", "dim_department", "department_key", False),
        ("dim_team.team_lead_employee_key", "dim_team", "team_lead_employee_key", "dim_employee", "employee_key", True),
        ("dim_vendor.primary_expense_account_key", "dim_vendor", "primary_expense_account_key", "dim_account", "account_key", True),
        ("fact_payroll.employee_key", "fact_payroll", "employee_key", "dim_employee", "employee_key", False),
        ("fact_payroll.date_key", "fact_payroll", "date_key", "dim_date", "date_key", False),
        ("fact_payroll.department_key", "fact_payroll", "department_key", "dim_department", "department_key", False),
        ("fact_payroll.role_key", "fact_payroll", "role_key", "dim_role", "role_key", False),
        ("fact_attendance_monthly.employee_key", "fact_attendance_monthly", "employee_key", "dim_employee", "employee_key", False),
        ("fact_attendance_monthly.date_key", "fact_attendance_monthly", "date_key", "dim_date", "date_key", False),
        ("fact_attendance_monthly.department_key", "fact_attendance_monthly", "department_key", "dim_department", "department_key", False),
        ("fact_leave.employee_key", "fact_leave", "employee_key", "dim_employee", "employee_key", False),
        ("fact_leave.leave_type_key", "fact_leave", "leave_type_key", "dim_leave_type", "leave_type_key", False),
        ("fact_leave.start_date_key", "fact_leave", "start_date_key", "dim_date", "date_key", False),
        ("fact_leave.end_date_key", "fact_leave", "end_date_key", "dim_date", "date_key", False),
        ("fact_headcount_monthly.date_key", "fact_headcount_monthly", "date_key", "dim_date", "date_key", False),
        ("fact_headcount_monthly.department_key", "fact_headcount_monthly", "department_key", "dim_department", "department_key", False),
        ("fact_ledger.date_key", "fact_ledger", "date_key", "dim_date", "date_key", False),
        ("fact_ledger.account_key", "fact_ledger", "account_key", "dim_account", "account_key", False),
        ("fact_ledger.department_key", "fact_ledger", "department_key", "dim_department", "department_key", True),
        ("fact_invoice.client_key", "fact_invoice", "client_key", "dim_client", "client_key", False),
        ("fact_invoice.account_key", "fact_invoice", "account_key", "dim_account", "account_key", False),
        ("fact_invoice.invoice_date_key", "fact_invoice", "invoice_date_key", "dim_date", "date_key", False),
        ("fact_invoice_payment.payment_date_key", "fact_invoice_payment", "payment_date_key", "dim_date", "date_key", False),
        ("fact_invoice_payment.invoice_id", "fact_invoice_payment", "invoice_id", "fact_invoice", "invoice_id", False),
        ("fact_invoice_payment.client_key", "fact_invoice_payment", "client_key", "dim_client", "client_key", False),
        ("fact_invoice_payment.account_key", "fact_invoice_payment", "account_key", "dim_account", "account_key", False),
        ("fact_expense.vendor_key", "fact_expense", "vendor_key", "dim_vendor", "vendor_key", False),
        ("fact_expense.account_key", "fact_expense", "account_key", "dim_account", "account_key", False),
        ("fact_expense.department_key", "fact_expense", "department_key", "dim_department", "department_key", False),
        ("fact_expense.expense_date_key", "fact_expense", "expense_date_key", "dim_date", "date_key", False),
        ("fact_task.team_key", "fact_task", "team_key", "dim_team", "team_key", False),
        ("fact_task.sprint_key", "fact_task", "sprint_key", "dim_sprint", "sprint_key", False),
        ("fact_task.assignee_employee_key", "fact_task", "assignee_employee_key", "dim_employee", "employee_key", False),
        ("fact_anomaly.employee_key", "fact_anomaly", "employee_key", "dim_employee", "employee_key", False),
        ("fact_anomaly.date_key", "fact_anomaly", "date_key", "dim_date", "date_key", False),
        ("fact_attrition_risk.employee_key", "fact_attrition_risk", "employee_key", "dim_employee", "employee_key", False),
        ("fact_attrition_risk.department_id", "fact_attrition_risk", "department_id", "dim_department", "department_id", False),
        ("fact_attrition_risk.date_key", "fact_attrition_risk", "date_key", "dim_date", "date_key", False),
        ("fact_forecast.department_id", "fact_forecast", "department_id", "dim_department", "department_id", False),
        ("fact_forecast.forecast_date_key", "fact_forecast", "forecast_date_key", "dim_date", "date_key", False),
    ]
    results: list[dict[str, Any]] = []
    for name, source, source_column, target, target_column, optional in checks:
        source_column_sql = quote_identifier(source_column)
        target_column_sql = quote_identifier(target_column)
        source_table = f"warehouse.{quote_identifier(source)}"
        target_table = f"warehouse.{quote_identifier(target)}"
        condition = f"s.{source_column_sql} IS NOT NULL"
        meaningful_source = "TRUE"
        if source == "dim_employee" and source_column in {
            "department_key",
            "role_key",
            "location_key",
        }:
            meaningful_source = "s.employee_key <> 0"
        orphan_count, checked_count, null_count = connection.execute(
            f"SELECT "
            f"count(*) FILTER (WHERE {meaningful_source} AND {condition} "
            f"AND t.{target_column_sql} IS NULL), "
            f"count(*) FILTER (WHERE {meaningful_source} AND {condition}), "
            f"count(*) FILTER (WHERE {meaningful_source} AND s.{source_column_sql} IS NULL) "
            f"FROM {source_table} s LEFT JOIN {target_table} t "
            f"ON s.{source_column_sql} = t.{target_column_sql}"
        ).fetchone()
        source_count = connection.execute(
            f"SELECT count(*) FROM {source_table}"
        ).fetchone()[0]
        status = "PASS" if orphan_count == 0 and (optional or null_count == 0) else "FAIL"
        if null_count:
            explanation = (
                "Optional source key is blank; not counted as an orphan."
                if optional
                else "Missing required key; inspect the source row."
            )
        else:
            explanation = "All populated keys resolve to a target row."
        results.append(
            {
                "relationship": name,
                "source_rows": source_count,
                "checked_rows": checked_count,
                "orphan_rows": orphan_count,
                "null_key_rows": null_count,
                "status": status,
                "explanation": explanation,
            }
        )
    connection.execute(
        "CREATE TABLE warehouse.orphan_checks "
        "(relationship VARCHAR, source_rows BIGINT, checked_rows BIGINT, "
        "orphan_rows BIGINT, null_key_rows BIGINT, status VARCHAR, explanation VARCHAR)"
    )
    connection.executemany(
        "INSERT INTO warehouse.orphan_checks VALUES (?, ?, ?, ?, ?, ?, ?)",
        [tuple(row.values()) for row in results],
    )
    return results


def reconcile_facts(connection: Any) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for table in FACT_SOURCES:
        passed = connection.execute(
            "SELECT rows_passed FROM etl.summary WHERE table_name = ?", [table]
        ).fetchone()
        if passed is None:
            raise ValueError(f"Task 1 summary does not contain {table}")
        warehouse_count = connection.execute(
            f"SELECT count(*) FROM warehouse.{quote_identifier(table)}"
        ).fetchone()[0]
        results.append(
            {
                "fact_table": table,
                "task1_rows_passed": passed[0],
                "warehouse_rows": warehouse_count,
                "difference": warehouse_count - passed[0],
                "status": "PASS" if warehouse_count == passed[0] else "FAIL",
            }
        )
    connection.execute(
        "CREATE TABLE warehouse.reconciliation "
        "(fact_table VARCHAR, task1_rows_passed BIGINT, warehouse_rows BIGINT, "
        "difference BIGINT, status VARCHAR)"
    )
    connection.executemany(
        "INSERT INTO warehouse.reconciliation VALUES (?, ?, ?, ?, ?)",
        [tuple(row.values()) for row in results],
    )
    return results


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"No evidence rows to write to {path.name}")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    if not DATABASE.exists():
        raise FileNotFoundError(
            f"{DATABASE.name} not found. Run the Task 1 pipeline first: python etl.py"
        )
    connection = duckdb.connect(str(DATABASE))
    try:
        summary_exists = connection.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'etl' AND table_name = 'summary'"
        ).fetchone()[0]
        if not summary_exists:
            raise ValueError("Task 1 output etl.summary is missing; run python etl.py first.")
        connection.execute("DROP SCHEMA IF EXISTS warehouse CASCADE")
        connection.execute("CREATE SCHEMA warehouse")
        schemas = create_typed_views(connection)
        create_dimensions(connection, schemas)
        extended_days = extend_date_dimension(connection)
        create_facts(connection)
        add_primary_keys(connection)
        employee_exceptions = create_employee_key_exceptions(connection)
        reconciliation = reconcile_facts(connection)
        employee_scd_checks = run_employee_scd_checks(connection)
        orphan_checks = run_orphan_checks(connection)
        write_csv(RECONCILIATION_FILE, reconciliation)
        write_csv(ORPHAN_FILE, orphan_checks)
        exception_file = ROOT / "warehouse_employee_key_exceptions.csv"
        scd_file = ROOT / "warehouse_employee_scd_checks.csv"
        if employee_exceptions:
            write_csv(exception_file, employee_exceptions)
        elif exception_file.exists():
            exception_file.unlink()
        write_csv(scd_file, employee_scd_checks)

        print("Warehouse build complete.")
        if extended_days:
            print(f"Extended dim_date by {extended_days:,} days for forecast coverage.")
        print("\nFact row reconciliation (Task 1 passed vs warehouse):")
        print(f"{'fact table':32} {'Task 1':>10} {'warehouse':>10} {'diff':>8} {'status':>8}")
        for row in reconciliation:
            print(
                f"{row['fact_table']:32} {row['task1_rows_passed']:10,} "
                f"{row['warehouse_rows']:10,} {row['difference']:8,} {row['status']:>8}"
            )
        print("\nDimension/fact key checks:")
        print(f"{'relationship':48} {'orphans':>8} {'null keys':>10} {'status':>8}")
        for row in orphan_checks:
            print(
                f"{row['relationship']:48} {row['orphan_rows']:8,} "
                f"{row['null_key_rows']:10,} {row['status']:>8}"
            )
            if row["null_key_rows"]:
                print(f"  Note: {row['explanation']}")
        print("\nEmployee SCD key checks:")
        for row in employee_scd_checks:
            print(
                f"- {row['check_name']}: {row['rows_checked']:,} checked, "
                f"{row['mismatch_rows']:,} mismatches ({row['status']})"
            )
        print(f"\nEmployee SCD/unknown-key exceptions: {len(employee_exceptions):,}")
        for row in employee_exceptions:
            print(
                f"- {row['source_table']} {row['record_id']} ({row['employee_id']}): "
                f"{row['explanation']}; mapped to employee_key "
                f"{row['mapped_employee_key']}."
            )
        print(
            f"\nEvidence: {RECONCILIATION_FILE.name}, {ORPHAN_FILE.name}, "
            f"{exception_file.name if employee_exceptions else 'no employee exceptions'}, "
            f"{scd_file.name}"
        )

        failures = [
            row for row in reconciliation if row["status"] != "PASS"
        ] + [row for row in orphan_checks if row["status"] != "PASS"] + [
            row for row in employee_scd_checks if row["status"] != "PASS"
        ]
        if failures:
            print(f"\nWarehouse checks failed: {len(failures)} item(s).", file=sys.stderr)
            return 1
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Warehouse build failed: {error}", file=sys.stderr)
        raise
