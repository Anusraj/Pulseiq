"""Load all supplied CSV feeds into DuckDB and validate them against their contracts."""

from __future__ import annotations

import csv
import json
import re
import sys
import tempfile
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from clean_data import prepare_cleaned_data

try:
    import duckdb
except ImportError as exc:
    raise SystemExit(
        "DuckDB is required. Activate the project virtual environment and run "
        "`python -m pip install -r starter/requirements.txt`."
    ) from exc

from dq_gate import record_load_success, run_gate


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
DATABASE = ROOT / "pulseiq.duckdb"
CONTRACT_FILE = RAW_DIR / "data_contracts.csv"
DICTIONARY_FILE = RAW_DIR / "data_dictionary.csv"
SUMMARY_FILE = ROOT / "etl_summary.csv"
DOC_FILES_WITHOUT_HEADERS = {"read_me", "readme"}


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def bulk_insert(connection: Any, table: str, columns: list[str], rows: list[tuple[Any, ...]]) -> None:
    if not rows:
        return
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", suffix=".csv", delete=False
    ) as stream:
        temporary_path = Path(stream.name)
        csv.writer(stream).writerows(rows)
    try:
        column_map = {column: "VARCHAR" for column in columns}
        connection.execute(
            f"INSERT INTO {table} "
            "SELECT * FROM read_csv(?, header=false, all_varchar=true, "
            "nullstr='__ETL_NULL_SENTINEL__', columns=?)",
            [str(temporary_path), column_map],
        )
    finally:
        temporary_path.unlink(missing_ok=True)


def read_csv_file(path: Path) -> tuple[list[str], list[dict[str, str]], list[str]]:
    """Read a CSV, retaining malformed-width rows for quarantine."""
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        first_row = next(reader, [])
        has_header = path.stem.lower() not in DOC_FILES_WITHOUT_HEADERS
        if has_header:
            columns = [name.strip() or f"column_{index + 1}" for index, name in enumerate(first_row)]
            if len(set(columns)) != len(columns):
                raise ValueError(f"{path.name} has duplicate column names.")
        else:
            columns = [f"column_{index + 1}" for index in range(len(first_row))]
        rows: list[dict[str, str]] = []
        width_errors: list[str] = []

        def add_row(values: list[str]) -> None:
            error = ""
            if len(values) != len(columns):
                error = f"row has {len(values)} fields; expected {len(columns)}"
            record = {
                column: values[index] if index < len(values) else ""
                for index, column in enumerate(columns)
            }
            if len(values) > len(columns):
                record["__extra_fields__"] = json.dumps(values[len(columns):])
            rows.append(record)
            width_errors.append(error)

        if not has_header and first_row:
            add_row(first_row)
        for values in reader:
            add_row(values)
    return columns, rows, width_errors


def load_raw_table(
    connection: Any,
    table_name: str,
    columns: list[str],
    rows: list[dict[str, str]],
    path: Path,
    has_header: bool,
    width_errors: list[str],
) -> None:
    table = f"raw.{quote_identifier(table_name)}"
    if not any(width_errors):
        column_map = {column: "VARCHAR" for column in columns}
        connection.execute(
            f"CREATE OR REPLACE TABLE {table} AS "
            "SELECT * FROM read_csv(?, header=?, all_varchar=true, "
            "nullstr='__ETL_NULL_SENTINEL__', columns=?)",
            [str(path), has_header, column_map],
        )
        return

    definitions = ", ".join(f"{quote_identifier(column)} VARCHAR" for column in columns)
    connection.execute(f"CREATE OR REPLACE TABLE {table} ({definitions})")
    if not rows:
        return
    values = [tuple(row.get(column, "") for column in columns) for row in rows]
    bulk_insert(connection, table, columns, values)


def normalized_type(data_type: str) -> str:
    value = data_type.strip().lower()
    if value.startswith(("decimal", "numeric", "number")):
        return "decimal"
    if value in {"int", "integer", "smallint", "bigint"}:
        return "integer"
    if value in {"string", "text", "varchar", "char(1)"}:
        return "text"
    if value == "date":
        return "date"
    if value in {"timestamp", "datetime"}:
        return "timestamp"
    raise ValueError(f"Unsupported contract data type: {data_type}")


def type_error(value: str, data_type: str) -> str | None:
    kind = normalized_type(data_type)
    try:
        if kind == "integer":
            int(value)
        elif kind == "decimal":
            if "," in value:
                if not re.fullmatch(r"[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?", value):
                    return f"must be {data_type}"
                value = value.replace(",", "")
            number = Decimal(value)
            if not number.is_finite():
                raise InvalidOperation
            precision_scale = re.fullmatch(r"(?:decimal|numeric)\((\d+),(\d+)\)", data_type, re.IGNORECASE)
            if precision_scale:
                precision, scale = map(int, precision_scale.groups())
                exponent = number.as_tuple().exponent
                fractional_digits = max(-exponent, 0)
                integer_digits = max(len(number.as_tuple().digits) + exponent, 0)
                if fractional_digits > scale or integer_digits + fractional_digits > precision:
                    return f"must fit {data_type}"
        elif kind == "date":
            date.fromisoformat(value)
        elif kind == "timestamp":
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        elif kind == "text" and not value.strip():
            return "must not be blank"
    except (ValueError, InvalidOperation, OverflowError):
        return f"must be {data_type}"
    return None


def parse_contracts() -> dict[str, dict[str, dict[str, str]]]:
    contracts: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    with CONTRACT_FILE.open("r", encoding="utf-8-sig", newline="") as stream:
        for item in csv.DictReader(stream):
            match = re.search(r"\(([^()]+)\)", item["feed"])
            if not match:
                raise ValueError(f"Cannot determine table name from contract feed: {item['feed']}")
            table = match.group(1).strip().lower()
            column = item["column_name"].strip()
            if column == "top_reason_1..3":
                for number in range(1, 4):
                    contracts[table][f"top_reason_{number}"] = item
            else:
                contracts[table][column] = item
    return contracts


def parse_dictionary() -> dict[str, dict[str, dict[str, str]]]:
    dictionary: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    with DICTIONARY_FILE.open("r", encoding="utf-8-sig", newline="") as stream:
        for item in csv.DictReader(stream):
            table = item["sheet"].strip().lower()
            column = item["column"].strip()
            dictionary[table][column] = item
    return dictionary


def is_empty(value: str | None) -> bool:
    return value is None or not value.strip()


def contract_rule_error(
    table: str, column: str, value: str, rule: str
) -> str | None:
    lower_rule = rule.lower()
    if column in {"result_id", "prediction_id", "forecast_id", "task_id"}:
        match = re.search(r"format\s+([A-Z]+)-n+", rule, flags=re.IGNORECASE)
        if match:
            prefix = match.group(1)
            if not re.fullmatch(rf"{re.escape(prefix)}-\d+", value):
                return f"must match {prefix}-number format"
            digit_count = len(rule.rsplit("-", 1)[1].strip())
            if len(value.rsplit("-", 1)[1]) != digit_count:
                return f"must have {digit_count} digits after {prefix}-"

    allowed_values = re.search(r"^\s*([^|]+(?:\|[^|]+)+)\s*$", rule)
    if allowed_values and not any(marker in lower_rule for marker in ("top_reason",)):
        choices = [choice.strip() for choice in rule.split("|")]
        if value not in choices:
            return f"must be one of {', '.join(choices)}"
    elif re.fullmatch(r"Y\s+or\s+N", rule, flags=re.IGNORECASE) and value not in {"Y", "N"}:
        return "must be Y or N"
    elif column == "priority" and not re.fullmatch(r"P[1-4]", value):
        return "must be P1, P2, P3, or P4"
    elif column == "story_points" and value not in {"1", "2", "3", "5", "8", "13"}:
        return "must be one of 1, 2, 3, 5, 8, 13"

    if column in {"anomaly_score", "risk_score_12m"}:
        if not Decimal("0") <= Decimal(value.replace(",", "")) <= Decimal("1"):
            return "must be between 0 and 1"
    if column in {"forecast_value", "lower_80", "upper_80"} and Decimal(value.replace(",", "")) < 0:
        return "must be at least 0"
    if table == "fact_forecast":
        if column == "forecast_month" and date.fromisoformat(value).day != 1:
            return "must be the first day of its month"
        if column == "trained_through" and not re.fullmatch(r"\d{4}-\d{2}", value):
            return "must use YYYY-MM format"
    if table == "fact_anomaly" and column == "scored_at":
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is not None and parsed.utcoffset().total_seconds() != 0:
            return "must be a UTC timestamp"
    return None


def cross_row_error(
    table: str,
    record: dict[str, str],
    references: dict[str, set[str]],
    sprint_end_dates: dict[str, str],
) -> list[str]:
    errors: list[str] = []

    def require_reference(column: str, target: str, label: str | None = None) -> None:
        value = record.get(column, "")
        if not is_empty(value) and value not in references.get(target, set()):
            errors.append(f"{column} references unknown {label or target} value {value!r}")

    if table == "fact_task":
        require_reference("team_id", "dim_team")
        require_reference("sprint_id", "dim_sprint")
        require_reference("assignee_employee_id", "dim_employee", "employee")
        expected_due = sprint_end_dates.get(record.get("sprint_id", ""))
        if expected_due and record.get("due_date") != expected_due:
            errors.append("due_date must match the sprint end_date")
        status = record.get("status", "")
        started = record.get("started_date", "")
        completed = record.get("completed_date", "")
        created = record.get("created_date", "")
        if is_empty(started) and status != "To Do":
            errors.append("started_date may be blank only when status is To Do")
        if status == "Done" and is_empty(completed):
            errors.append("completed_date is required when status is Done")
        if started and created and created > started:
            errors.append("created_date must be on or before started_date")
        if completed and started and completed < started:
            errors.append("completed_date must be on or after started_date")
    elif table == "fact_attrition_risk":
        require_reference("department_id", "dim_department")
        latest_date = references.get("latest_attrition_date")
        as_of = record.get("as_of_date", "")
        if latest_date and as_of:
            age_days = (date.fromisoformat(latest_date) - date.fromisoformat(as_of)).days
            if age_days > 7:
                errors.append("as_of_date is more than 7 days older than the latest prediction")
    elif table == "fact_forecast":
        department_id = record.get("department_id", "")
        if department_id != "ALL" and department_id not in references.get("dim_department", set()):
            errors.append("department_id must be a department id or ALL")
        try:
            forecast = Decimal(record.get("forecast_value", "").replace(",", ""))
            lower = Decimal(record.get("lower_80", "").replace(",", ""))
            upper = Decimal(record.get("upper_80", "").replace(",", ""))
            if lower > forecast:
                errors.append("lower_80 must be less than or equal to forecast_value")
            if upper < forecast:
                errors.append("upper_80 must be greater than or equal to forecast_value")
        except InvalidOperation:
            pass
    elif table == "fact_anomaly":
        require_reference("employee_id", "dim_employee", "employee")
        source = record.get("source_dataset", "")
        id_column = {
            "attendance_monthly_features": "attendance_fact_id",
            "payroll_monthly_features": "payroll_item_id",
        }.get(source)
        if id_column:
            ids = references.get(f"record_ids:{id_column}", set())
            record_id = record.get("record_id", "")
            if source == "attendance_monthly_features" and record_id.startswith("AF-"):
                record_id = "FA-" + record_id[3:]
            if record_id not in ids:
                errors.append("record_id does not exist in the declared source dataset")
        if record.get("source_dataset") == "attendance_monthly_features" and not is_empty(
            record.get("money_at_risk")
        ):
            errors.append("money_at_risk must be blank for attendance rows")
        if record.get("source_dataset") == "payroll_monthly_features" and is_empty(
            record.get("money_at_risk")
        ):
            errors.append("money_at_risk is required for payroll rows")
    return errors


def build_references(tables: dict[str, tuple[list[str], list[dict[str, str]], list[str]]]) -> tuple[dict[str, set[str]], dict[str, str]]:
    references: dict[str, set[str]] = {}
    for table_name, column in (
        ("dim_department", "department_id"),
        ("dim_employee", "employee_id"),
        ("dim_sprint", "sprint_id"),
        ("dim_team", "team_id"),
    ):
        if table_name in tables:
            references[table_name] = {
                record.get(column, "")
                for record in tables[table_name][1]
                if not is_empty(record.get(column))
            }
    sprint_end_dates = {
        record.get("sprint_id", ""): record.get("end_date", "")
        for record in tables.get("dim_sprint", ([], [], []))[1]
    }
    if "fact_attendance_monthly" in tables:
        references["record_ids:attendance_fact_id"] = {
            record.get("attendance_fact_id", "")
            for record in tables["fact_attendance_monthly"][1]
        }
    if "fact_payroll" in tables:
        references["record_ids:payroll_item_id"] = {
            record.get("payroll_item_id", "")
            for record in tables["fact_payroll"][1]
        }
    attrition_dates = [
        record.get("as_of_date", "")
        for record in tables.get("fact_attrition_risk", ([], [], []))[1]
        if not is_empty(record.get("as_of_date"))
    ]
    if attrition_dates:
        references["latest_attrition_date"] = max(attrition_dates)
    return references, sprint_end_dates


def active_on_date(
    employee_id: str, as_of: str, employee_rows: list[dict[str, str]]
) -> bool:
    if not employee_id or not as_of:
        return False
    for employee in employee_rows:
        if employee.get("employee_id") != employee_id:
            continue
        if employee.get("employment_status", "").lower() != "active":
            continue
        start = employee.get("valid_from", "")
        end = employee.get("valid_to", "")
        if start and start <= as_of and (not end or end >= as_of):
            return True
    return False


def insert_validated_and_quarantine(
    connection: Any,
    table: str,
    columns: list[str],
    records: list[dict[str, str]],
    row_errors: list[list[str]],
) -> None:
    definitions = ", ".join(f"{quote_identifier(column)} VARCHAR" for column in columns)
    validated_table = f"validated.{quote_identifier(table)}"
    quarantine_table = f"quarantine.{quote_identifier(table)}"
    connection.execute(f"CREATE OR REPLACE TABLE {validated_table} ({definitions})")
    connection.execute(
        f"CREATE OR REPLACE TABLE {quarantine_table} "
        "(source_row_number BIGINT, reason VARCHAR, row_data JSON)"
    )
    good = [
        tuple(record.get(column, "") for column in columns)
        for record, errors in zip(records, row_errors)
        if not errors
    ]
    if good:
        bulk_insert(connection, validated_table, columns, good)
    bad = [
        (index + 1, "; ".join(errors), json.dumps(record, ensure_ascii=False))
        for index, (record, errors) in enumerate(zip(records, row_errors))
        if errors
    ]
    if bad:
        bulk_insert(connection, quarantine_table,
                    ["source_row_number", "reason", "row_data"], bad)


def main() -> int:
    if not RAW_DIR.is_dir():
        raise FileNotFoundError(f"Raw data folder not found: {RAW_DIR}")
    csv_files = sorted(RAW_DIR.glob("*.csv"))
    root_readme = ROOT / "readme.csv"
    if root_readme.is_file():
        csv_files.append(root_readme)
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {RAW_DIR}")

    contracts = parse_contracts()
    dictionary = parse_dictionary()
    cleaned_sources, cleaning_counts = prepare_cleaned_data()
    print(
        "Using cleaned feeds: "
        f"{cleaning_counts['duplicate_payroll_rows_removed']} duplicate payroll rows removed, "
        f"{cleaning_counts['orphan_payroll_rows_excluded']} orphan payroll rows excluded, "
        f"{cleaning_counts['employee_intervals_corrected']} employee intervals corrected.",
        flush=True,
    )
    loaded: dict[str, tuple[list[str], list[dict[str, str]], list[str]]] = {}
    sources: dict[str, Path] = {}
    for path in csv_files:
        name = path.stem.lower()
        if name in loaded:
            raise ValueError(f"Two source files map to table {name!r}")
        source = cleaned_sources.get(name, path)
        print(f"Reading {source.name}...", flush=True)
        loaded[name] = read_csv_file(source)
        sources[name] = source
        print(f"  {len(loaded[name][1]):,} data rows", flush=True)

    print("Building reference lookups...", flush=True)
    references, sprint_end_dates = build_references(loaded)
    employee_rows = loaded.get("dim_employee", ([], [], []))[1]
    print("Opening DuckDB...", flush=True)
    connection = duckdb.connect(str(DATABASE))
    run_id = uuid.uuid4().hex
    run_started_at = datetime.now(timezone.utc)
    try:
        for schema in ("raw", "validated", "quarantine", "etl"):
            connection.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

        summary: list[dict[str, Any]] = []
        warnings_to_print: list[str] = []
        for table, (columns, records, width_errors) in loaded.items():
            print(f"Loading and validating {table} ({len(records):,} rows)...", flush=True)
            load_raw_table(
                connection,
                table,
                columns,
                records,
                sources[table],
                sources[table].stem.lower() not in DOC_FILES_WITHOUT_HEADERS,
                width_errors,
            )
            contract = contracts.get(table, {})
            table_dictionary = dictionary.get(table, {})
            contract_columns = set(contract)
            missing_contract_columns = sorted(contract_columns - set(columns))
            if missing_contract_columns:
                raise ValueError(
                    f"{table} is missing contracted columns: {', '.join(missing_contract_columns)}"
                )
            unexpected = sorted(set(columns) - contract_columns) if contract else []
            schema_warning_parts: list[str] = []
            if unexpected:
                schema_warning_parts.append(
                    "unexpected columns (warn and retain): " + ", ".join(unexpected)
                )
            if not contract and not table_dictionary:
                schema_warning_parts.append("no column dictionary; loaded and shape-checked only")
            row_errors: list[list[str]] = []
            unique_counts: dict[str, Counter[str]] = {}
            for column, spec in contract.items():
                if "unique" in spec["rule_or_allowed_values"].lower():
                    unique_counts[column] = Counter(
                        record.get(column, "") for record in records if not is_empty(record.get(column))
                    )
            for row_index, record in enumerate(records):
                if table == "fact_task" and row_index and row_index % 5000 == 0:
                    print(f"  validated {row_index:,}/{len(records):,} task rows...", flush=True)
                errors: list[str] = []
                if width_errors[row_index]:
                    errors.append(width_errors[row_index])
                for column in columns:
                    value = record.get(column, "")
                    explicit = contract.get(column)
                    dictionary_spec = table_dictionary.get(column)
                    spec_type = explicit["data_type"] if explicit else (
                        dictionary_spec.get("data_type") if dictionary_spec else None
                    )
                    nullable = explicit["nullable"].strip().lower() == "yes" if explicit else True
                    if is_empty(value):
                        if not nullable:
                            errors.append(f"{column} must not be empty")
                        continue
                    problem = None
                    if spec_type:
                        problem = type_error(value, spec_type)
                        if problem:
                            errors.append(f"{column} {problem}")
                    if explicit and not problem:
                        problem = contract_rule_error(
                            table, column, value, explicit["rule_or_allowed_values"]
                        )
                        if problem:
                            errors.append(f"{column} {problem}")
                    if column in unique_counts and unique_counts[column][value] > 1:
                        errors.append(f"{column} must be unique; duplicate value {value!r}")
                if table in contracts and not errors:
                    errors.extend(cross_row_error(table, record, references, sprint_end_dates))
                    if table == "fact_attrition_risk" and not active_on_date(
                        record.get("employee_id", ""), record.get("as_of_date", ""), employee_rows
                    ):
                        errors.append("employee_id must be active on as_of_date")
                row_errors.append(errors)

            insert_validated_and_quarantine(
                connection, table, columns, records, row_errors
            )
            count_in = len(records)
            count_passed = sum(not errors for errors in row_errors)
            count_quarantined = count_in - count_passed
            if count_in != count_passed + count_quarantined:
                raise AssertionError(f"Row reconciliation failed for {table}")
            raw_count = connection.execute(
                f"SELECT COUNT(*) FROM raw.{quote_identifier(table)}"
            ).fetchone()[0]
            if raw_count != count_in:
                raise AssertionError(
                    f"Raw load count mismatch for {table}: parsed {count_in}, loaded {raw_count}"
                )
            warning = "; ".join(schema_warning_parts)
            if warning:
                warnings_to_print.append(f"{table}: {warning}")
            summary.append(
                {
                    "table_name": table,
                    "source_file": str(sources[table].relative_to(ROOT)),
                    "rows_in": count_in,
                    "rows_passed": count_passed,
                    "rows_quarantined": count_quarantined,
                    "contract_columns": len(contract),
                    "schema_warning": warning,
                }
            )
            print(
                f"  {count_in:,} in; {count_passed:,} passed; "
                f"{count_quarantined:,} quarantined",
                flush=True,
            )

        connection.execute(
            "CREATE OR REPLACE TABLE etl.summary AS "
            "SELECT * FROM (VALUES "
            + ", ".join("(?, ?, ?, ?, ?, ?, ?)" for _ in summary)
            + ") AS s(table_name, source_file, rows_in, rows_passed, "
            "rows_quarantined, contract_columns, schema_warning)",
            [
                value
                for row in summary
                for value in (
                    row["table_name"],
                    row["source_file"],
                    row["rows_in"],
                    row["rows_passed"],
                    row["rows_quarantined"],
                    row["contract_columns"],
                    row["schema_warning"],
                )
            ],
        )
        with SUMMARY_FILE.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(summary[0]))
            writer.writeheader()
            writer.writerows(summary)

        print(f"ETL complete: {DATABASE.name}")
        print(f"{'table':32} {'in':>9} {'passed':>9} {'quarantined':>12}")
        for row in summary:
            print(
                f"{row['table_name']:32} {row['rows_in']:9,} "
                f"{row['rows_passed']:9,} {row['rows_quarantined']:12,}"
            )
        print(
            f"{'TOTAL':32} {sum(r['rows_in'] for r in summary):9,} "
            f"{sum(r['rows_passed'] for r in summary):9,} "
            f"{sum(r['rows_quarantined'] for r in summary):12,}"
        )
        print(f"Summary CSV: {SUMMARY_FILE.name}")
        if warnings_to_print:
            print("\nSchema/contract warnings (columns are retained):")
            for warning in warnings_to_print:
                print(f"- {warning}")
        if any(row["rows_quarantined"] for row in summary):
            print("\nQuarantine counts by table:")
            for row in summary:
                if row["rows_quarantined"]:
                    print(f"- quarantine.{row['table_name']}: {row['rows_quarantined']:,}")
        record_load_success(connection, run_id, run_started_at)
        dq_report = run_gate(connection, run_id)
        print("\nData quality gate")
        print(f"{'check':10} {'severity':10} {'bad rows':>9} {'status':8} check name")
        for row in dq_report["results"]:
            print(
                f"{row['check_id']:10} {row['severity']:10} {row['bad_rows']:9,} "
                f"{row['status']:8} {row['check_name']}"
            )
        print(
            f"Overall DQ status: {dq_report['overall_status']} "
            f"({dq_report['critical_failures']} critical failures, "
            f"{dq_report['warning_failures']} warnings)"
        )
        print(f"DQ results: dq_results.csv; findings: dq_findings.csv")
        return 1 if dq_report["critical_failures"] else 0
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ETL failed: {error}", file=sys.stderr)
        raise