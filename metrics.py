"""Build and verify the governed Task 4 metric views."""

from __future__ import annotations

import csv
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

try:
    import duckdb
except ImportError as exc:
    raise SystemExit(
        "DuckDB is required. Activate the project virtual environment and run "
        "`python -m pip install -r starter/requirements.txt`."
    ) from exc


ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "pulseiq.duckdb"
SQL_FILE = ROOT / "metric_views.sql"
CATALOG_FILE = ROOT / "metric_catalog.csv"
HAND_CHECK_FILE = ROOT / "metric_hand_checks.csv"
VALIDATION_FILE = ROOT / "metric_view_validation.csv"

METRIC_VIEWS = {
    "M01": "m01_headcount",
    "M02": "m02_hires",
    "M03": "m03_exits",
    "M04": "m04_attrition_rate_monthly",
    "M05": "m05_attrition_rate_rolling_12m",
    "M06": "m06_voluntary_attrition_rate",
    "M07": "m07_gross_pay",
    "M08": "m08_net_pay",
    "M09": "m09_employer_payroll_cost",
    "M10": "m10_cost_per_head",
    "M11": "m11_overtime_share",
    "M12": "m12_variable_pay_share",
    "M13": "m13_attendance_rate",
    "M14": "m14_late_arrival_rate",
    "M15": "m15_leave_without_pay_days",
    "M16": "m16_revenue",
    "M17": "m17_net_profit",
    "M18": "m18_operating_margin",
    "M19": "m19_payroll_as_percent_of_revenue",
    "M20": "m20_days_sales_outstanding",
    "M21": "m21_overdue_receivables",
    "M22": "m22_task_completion_rate",
    "M23": "m23_on_time_delivery_rate",
    "M24": "m24_velocity",
    "M25": "m25_average_cycle_time",
    "M26": "m26_anomaly_flag_rate",
    "M27": "m27_high_risk_share",
    "M28": "m28_forecast_error_mape",
    "M29": "m29_net_hiring",
}

def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"No report rows to write to {path.name}")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def create_catalog(connection: Any) -> None:
    mapping = ", ".join(
        f"('{metric_id}', '{view_name}')"
        for metric_id, view_name in METRIC_VIEWS.items()
    )
    connection.execute(f"""
        CREATE SCHEMA IF NOT EXISTS metrics;
        CREATE OR REPLACE VIEW metrics.metric_catalog AS
        SELECT d.metric_id, d.metric_name, d.business_definition,
               CASE
                   WHEN d.metric_id = 'M04'
                   THEN 'Exits / ((headcount_start + headcount_end) / 2) x 100'
                   ELSE d.formula
               END AS formula,
               d.formula AS dictionary_formula,
               d.source_table, d.grain, d.time_period, d.owner_team, d.unit,
               d.good_direction, d.caveat, d.minimum_group_size,
               COALESCE(
                   TRY_CAST(REGEXP_EXTRACT(d.minimum_group_size, '^[0-9]+', 0) AS INTEGER),
                   0
               ) AS minimum_group_size_numeric,
               v.view_name,
               CASE
                   WHEN COALESCE(
                       TRY_CAST(REGEXP_EXTRACT(d.minimum_group_size, '^[0-9]+', 0) AS INTEGER),
                       0
                   ) > 0 THEN 'Suppress groups below minimum_group_size_numeric'
                   ELSE 'No minimum group-size threshold specified'
               END AS privacy_rule
        FROM raw.metric_dictionary d
        JOIN (VALUES {mapping}) AS v(metric_id, view_name) USING (metric_id)
    """)


def create_metric_views(connection: Any) -> None:
    sql_text = SQL_FILE.read_text(encoding="utf-8")
    for statement in sql_text.split(";"):
        statement = statement.strip()
        if statement:
            connection.execute(statement)


def check_metrics(connection: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    catalog = connection.execute(
        "SELECT * FROM metrics.metric_catalog ORDER BY metric_id"
    ).fetchdf()
    catalog_rows = catalog.to_dict(orient="records")
    if len(catalog_rows) != len(METRIC_VIEWS) or {row["metric_id"] for row in catalog_rows} != set(METRIC_VIEWS):
        raise AssertionError(
            f"Expected exactly {len(METRIC_VIEWS)} catalog entries; found {len(catalog_rows)}"
        )
    write_csv(CATALOG_FILE, catalog_rows)

    view_results: list[dict[str, Any]] = []
    for metric_id, view_name in METRIC_VIEWS.items():
        view_exists = connection.execute(
            """
            SELECT COUNT(*) FROM information_schema.views
            WHERE table_schema = 'metrics' AND table_name = ?
            """,
            [view_name],
        ).fetchone()[0]
        if view_exists != 1:
            raise AssertionError(f"Metric view metrics.{view_name} was not created")
        rows = connection.execute(f"SELECT COUNT(*) FROM metrics.{view_name}").fetchone()[0]
        privacy_violations = connection.execute(
            f"""
            SELECT COUNT(*) FROM metrics.{view_name}
            WHERE group_size < (
                SELECT minimum_group_size_numeric
                FROM metrics.metric_catalog WHERE metric_id = ?
            )
            """,
            [metric_id],
        ).fetchone()[0]
        if rows == 0:
            raise AssertionError(f"Metric view metrics.{view_name} returned no rows")
        if privacy_violations:
            raise AssertionError(
                f"Metric view metrics.{view_name} exposes {privacy_violations} "
                "below-minimum groups"
            )
        view_results.append(
            {
                "metric_id": metric_id,
                "view_name": f"metrics.{view_name}",
                "rows_returned": rows,
                "below_minimum_groups": privacy_violations,
                "status": "PASS",
            }
        )
    write_csv(VALIDATION_FILE, view_results)
    return catalog_rows, view_results


def decimal_value(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def round_metric(value: Decimal, digits: int) -> Decimal:
    quantum = Decimal(1).scaleb(-digits)
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def hand_check_rows(connection: Any) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    row = connection.execute("""
        SELECT period_start, department_id, metric_value
        FROM metrics.m04_attrition_rate_monthly
        ORDER BY period_start, department_id
        LIMIT 1
    """).fetchone()
    period, department, view_value = row
    source_value = connection.execute(
        """
        SELECT exits, headcount_start, headcount_end FROM warehouse.fact_headcount_monthly
        WHERE month_start_date = ? AND department_id = ?
        """,
        [period, department],
    ).fetchone()
    exits, headcount_start, headcount_end = map(decimal_value, source_value)
    average_headcount = (headcount_start + headcount_end) / Decimal(2)
    by_start = round_metric(Decimal(100) * exits / headcount_start, 2)
    by_average = round_metric(Decimal(100) * exits / average_headcount, 2)
    by_end = round_metric(Decimal(100) * exits / headcount_end, 2)
    checks.append(
        hand_check(
            "M04", "Monthly attrition rate", f"{period} / {department}",
            f"exits={exits}; start headcount={headcount_start}; "
            f"end headcount={headcount_end}; average={(headcount_start + headcount_end) / 2}",
            exits, average_headcount, Decimal(view_value), 2,
            calculated_override=by_average,
            denominator_comparison=(
                f"start={by_start}%; average={by_average}%; end={by_end}%"
            ),
        )
    )

    payroll_row = connection.execute("""
        SELECT period_start, department_id, metric_value
        FROM metrics.m07_gross_pay
        ORDER BY period_start, department_id
        LIMIT 1
    """).fetchone()
    period, department, view_value = payroll_row
    payroll_inputs = connection.execute(
        """
        SELECT gross_pay FROM metrics.payroll_eligible
        WHERE period_end_date = ? AND department_id = ?
        """,
        [period, department],
    ).fetchall()
    gross_total = sum((decimal_value(item[0]) for item in payroll_inputs), Decimal(0))
    checks.append(
        hand_check(
            "M07", "Gross pay", f"{period} / {department}",
            f"sum of {len(payroll_inputs)} validated gross_pay values",
            gross_total, Decimal(1), Decimal(view_value), 2,
        )
    )

    payroll_row = connection.execute("""
        SELECT period_start, department_id, metric_value
        FROM metrics.m09_employer_payroll_cost
        ORDER BY period_start, department_id
        LIMIT 1
    """).fetchone()
    period, department, view_value = payroll_row
    payroll_inputs = connection.execute(
        """
        SELECT employer_cost FROM metrics.payroll_eligible
        WHERE period_end_date = ? AND department_id = ?
        """,
        [period, department],
    ).fetchall()
    employer_total = sum((decimal_value(item[0]) for item in payroll_inputs), Decimal(0))
    checks.append(
        hand_check(
            "M09", "Employer payroll cost", f"{period} / {department}",
            f"sum of {len(payroll_inputs)} validated employer_cost values",
            employer_total, Decimal(1), Decimal(view_value), 2,
        )
    )

    ledger_row = connection.execute("""
        SELECT period_start, breakdown_id, metric_value
        FROM metrics.m16_revenue
        ORDER BY period_start, breakdown_id
        LIMIT 1
    """).fetchone()
    period, account_code, view_value = ledger_row
    ledger_inputs = connection.execute(
        """
        SELECT signed_amount_debit_positive FROM warehouse.fact_ledger
        WHERE posting_period = strftime(?, '%Y-%m') AND account_code = ?
        """,
        [period, account_code],
    ).fetchall()
    revenue_total = -sum(
        (decimal_value(item[0]) for item in ledger_inputs), Decimal(0)
    )
    checks.append(
        hand_check(
            "M16", "Revenue", f"{period} / account {account_code}",
            f"negative of {len(ledger_inputs)} ledger signed amounts",
            revenue_total, Decimal(1), Decimal(view_value), 2,
        )
    )

    task_row = connection.execute("""
        SELECT period_start, breakdown_id, numerator, denominator, metric_value
        FROM metrics.m22_task_completion_rate
        ORDER BY period_start, breakdown_id
        LIMIT 1
    """).fetchone()
    period, breakdown, _, _, view_value = task_row
    team_id, sprint_id = breakdown.split("/", 1)
    task_inputs = connection.execute(
        """
        SELECT status FROM warehouse.fact_task
        WHERE team_id = ? AND sprint_id = ? AND LOWER(status) <> 'cancelled'
        """,
        [team_id, sprint_id],
    ).fetchall()
    planned = Decimal(len(task_inputs))
    done = Decimal(sum(1 for item in task_inputs if item[0].lower() == "done"))
    completion = round_metric(Decimal(100) * done / planned, 2)
    checks.append(
        hand_check(
            "M22", "Task completion rate", f"{period} / {team_id} / {sprint_id}",
            f"{int(done)} done / {int(planned)} non-cancelled tasks x 100",
            done, planned, Decimal(view_value), 2, calculated_override=completion,
        )
    )

    net_hiring_row = connection.execute("""
        SELECT period_start, department_id, metric_value
        FROM metrics.m29_net_hiring
        ORDER BY period_start, department_id
        LIMIT 1
    """).fetchone()
    period, department, view_value = net_hiring_row
    hires, exits = connection.execute(
        """
        SELECT hires, exits FROM warehouse.fact_headcount_monthly
        WHERE month_start_date = ? AND department_id = ?
        """,
        [period, department],
    ).fetchone()
    net_hires = decimal_value(hires) - decimal_value(exits)
    checks.append(
        hand_check(
            "M29", "Net hires", f"{period} / {department}",
            f"fact_headcount_monthly source row: hires={hires} - exits={exits}",
            net_hires, Decimal(1), Decimal(view_value), 0,
        )
    )
    return checks


def hand_check(
    metric_id: str,
    metric_name: str,
    grain: str,
    inputs: str,
    numerator: Decimal,
    denominator: Decimal,
    view_value: Decimal,
    digits: int,
    calculated_override: Decimal | None = None,
    denominator_comparison: str = "",
) -> dict[str, Any]:
    calculated = calculated_override
    if calculated is None:
        calculated = numerator if denominator == 1 else numerator / denominator
    if metric_id == "M16":
        calculated = round_metric(calculated, digits)
    if metric_id in {"M07", "M09"}:
        calculated = round_metric(calculated, digits)
    view_rounded = round_metric(view_value, digits)
    difference = calculated - view_rounded
    if abs(difference) > Decimal("0.01"):
        raise AssertionError(
            f"Hand-check mismatch for {metric_id}: calculator {calculated}, "
            f"view {view_rounded}"
        )
    return {
        "metric_id": metric_id,
        "metric_name": metric_name,
        "grain": grain,
        "manual_inputs": inputs,
        "numerator": str(numerator),
        "denominator": str(denominator),
        "hand_calculated_value": str(calculated),
        "view_value": str(view_rounded),
        "difference": str(difference),
        "denominator_comparison": denominator_comparison,
        "status": "PASS",
    }


def main() -> int:
    if not DATABASE.is_file():
        raise FileNotFoundError(
            f"{DATABASE.name} not found. Run python etl.py and python warehouse.py first."
        )
    if not SQL_FILE.is_file():
        raise FileNotFoundError(f"Metric view SQL file not found: {SQL_FILE}")
    connection = duckdb.connect(str(DATABASE))
    try:
        required = connection.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'warehouse' AND table_name = 'fact_headcount_monthly'
        """).fetchone()[0]
        if required != 1:
            raise ValueError("Task 2 warehouse is missing. Run python warehouse.py first.")
        if not connection.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = 'raw' AND table_name = 'metric_dictionary'"
        ).fetchone()[0]:
            raise ValueError("raw.metric_dictionary is missing. Run python etl.py first.")
        create_catalog(connection)
        create_metric_views(connection)
        catalog_rows, view_results = check_metrics(connection)
        hand_checks = hand_check_rows(connection)
        write_csv(HAND_CHECK_FILE, hand_checks)
        print("Metric layer build complete.")
        print(f"Catalog entries: {len(catalog_rows)} ({CATALOG_FILE.name})")
        print(f"{'metric':8} {'rows':>8} {'below min':>10} {'status':>8} view")
        for row in view_results:
            print(
                f"{row['metric_id']:8} {row['rows_returned']:8,} "
                f"{row['below_minimum_groups']:10,} {row['status']:>8} {row['view_name']}"
            )
        print("\nHand-check evidence:")
        for row in hand_checks:
            print(
                f"- {row['metric_id']} {row['metric_name']}: "
                f"{row['hand_calculated_value']} = {row['view_value']} ({row['status']})"
            )
        print(
            f"Evidence: {CATALOG_FILE.name}, {HAND_CHECK_FILE.name}, "
            f"{VALIDATION_FILE.name}"
        )
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Metric layer build failed: {error}", file=sys.stderr)
        raise
