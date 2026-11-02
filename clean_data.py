"""Prepare reproducible cleaned feeds without changing the supplied source files."""

from __future__ import annotations

import csv
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
CLEANED_DIR = ROOT / "data" / "cleaned"
PAYROLL_SOURCE = RAW_DIR / "fact_payroll.csv"
EMPLOYEE_SOURCE = RAW_DIR / "dim_employee.csv"
DQ_CATALOG_SOURCE = RAW_DIR / "dq_checks_catalog.csv"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError(f"{path} has no header row.")
        return reader.fieldnames, list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="raise")
            writer.writeheader()
            writer.writerows(rows)
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def clean_payroll(
    fieldnames: list[str],
    rows: list[dict[str, str]],
    employee_ids: set[str],
) -> tuple[list[dict[str, str]], list[dict[str, str]], int, int]:
    required = {"payroll_item_id", "employee_id", "run_id"}
    if not required.issubset(fieldnames):
        raise ValueError(f"Payroll feed is missing required columns: {', '.join(sorted(required - set(fieldnames)))}")

    seen: dict[tuple[str, str], tuple[dict[str, str], int]] = {}
    cleaned: list[dict[str, str]] = []
    report: list[dict[str, str]] = []
    duplicate_count = 0
    orphan_count = 0
    for line_number, row in enumerate(rows, start=2):
        employee_id = (row.get("employee_id") or "").strip()
        run_id = (row.get("run_id") or "").strip()
        record_id = row.get("payroll_item_id", "")
        if employee_id and employee_id not in employee_ids:
            orphan_count += 1
            report.append(
                {
                    "action": "excluded",
                    "table": "fact_payroll",
                    "record_id": record_id,
                    "reason": f"employee_id {employee_id} is absent from dim_employee",
                }
            )
            continue

        key = (employee_id, run_id)
        if employee_id and run_id and key in seen:
            previous, previous_line = seen[key]
            differs = [
                column for column in fieldnames
                if column != "payroll_item_id"
                and row.get(column) != previous.get(column)
            ]
            if differs:
                raise ValueError(
                    f"Conflicting duplicate payroll employee/run {key!r} "
                    f"at lines {previous_line} and {line_number}; "
                    f"different columns: {', '.join(differs)}. No cleaned feed was written."
                )
            duplicate_count += 1
            report.append(
                {
                    "action": "deduplicated",
                    "table": "fact_payroll",
                    "record_id": record_id,
                    "reason": f"identical employee/run record; retained {previous.get('payroll_item_id', '')}",
                }
            )
            continue

        if employee_id and run_id:
            seen[key] = (row, line_number)
        cleaned.append(row)
    return cleaned, report, duplicate_count, orphan_count


def clean_employee_history(
    fieldnames: list[str], rows: list[dict[str, str]]
) -> tuple[list[dict[str, str]], list[dict[str, str]], int]:
    required = {"employee_id", "employee_key", "valid_from", "valid_to"}
    if not required.issubset(fieldnames):
        raise ValueError(
            f"Employee feed is missing required columns: {', '.join(sorted(required - set(fieldnames)))}"
        )

    cleaned = [dict(row) for row in rows]
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in cleaned:
        grouped.setdefault(row.get("employee_id", ""), []).append(row)

    report: list[dict[str, str]] = []
    corrections = 0
    for employee_id, versions in grouped.items():
        versions.sort(key=lambda row: date.fromisoformat(row["valid_from"]))
        for current, following in zip(versions, versions[1:]):
            current_start = date.fromisoformat(current["valid_from"])
            next_start = date.fromisoformat(following["valid_from"])
            if current_start >= next_start:
                raise ValueError(
                    f"Ambiguous employee history for {employee_id}: multiple versions "
                    f"start on or before {next_start}."
                )
            current_end = date.fromisoformat(current["valid_to"]) if current.get("valid_to") else None
            if current_end is None or current_end >= next_start:
                corrected_end = next_start - timedelta(days=1)
                previous_end = current.get("valid_to", "")
                current["valid_to"] = corrected_end.isoformat()
                corrections += 1
                report.append(
                    {
                        "action": "corrected_interval",
                        "table": "dim_employee",
                        "record_id": f"{employee_id}/{current.get('employee_key', '')}",
                        "reason": f"valid_to {previous_end or 'open'} changed to {corrected_end.isoformat()} to precede next version",
                    }
                )
            elif current_end < current_start:
                raise ValueError(
                    f"Invalid employee history for {employee_id}/{current.get('employee_key')}: "
                    f"valid_to precedes valid_from."
                )
    return cleaned, report, corrections


def prepare_cleaned_data() -> tuple[dict[str, Path], dict[str, int]]:
    employee_fields, employee_rows = read_csv(EMPLOYEE_SOURCE)
    employee_ids = {row.get("employee_id", "").strip() for row in employee_rows}

    payroll_fields, payroll_rows = read_csv(PAYROLL_SOURCE)
    payroll_clean, report, duplicate_count, orphan_count = clean_payroll(
        payroll_fields, payroll_rows, employee_ids
    )
    employee_clean, employee_report, overlap_count = clean_employee_history(
        employee_fields, employee_rows
    )
    report.extend(employee_report)

    catalog_fields, catalog_rows = read_csv(DQ_CATALOG_SOURCE)
    catalog_changed = 0
    if "check_id" not in catalog_fields or "severity" not in catalog_fields:
        raise ValueError(f"{DQ_CATALOG_SOURCE} is missing check_id or severity.")
    for row in catalog_rows:
        if row.get("check_id") == "DQ-C14":
            if row.get("severity", "").strip().lower() == "critical":
                row["severity"] = "Warning"
                catalog_changed = 1
            report.append(
                {
                    "action": "reclassified",
                    "table": "dq_checks_catalog",
                    "record_id": "DQ-C14",
                    "reason": "small source groups are checked again against published metric views by metrics.py",
                }
            )
            break
    else:
        raise ValueError("DQ-C14 is missing from dq_checks_catalog.csv.")

    outputs = {
        "fact_payroll": CLEANED_DIR / "fact_payroll.csv",
        "dim_employee": CLEANED_DIR / "dim_employee.csv",
        "dq_checks_catalog": CLEANED_DIR / "dq_checks_catalog.csv",
        "cleaning_report": CLEANED_DIR / "cleaning_report.csv",
    }
    write_csv(outputs["fact_payroll"], payroll_fields, payroll_clean)
    write_csv(outputs["dim_employee"], employee_fields, employee_clean)
    write_csv(outputs["dq_checks_catalog"], catalog_fields, catalog_rows)
    write_csv(
        outputs["cleaning_report"],
        ["action", "table", "record_id", "reason"],
        report,
    )
    return outputs, {
        "duplicate_payroll_rows_removed": duplicate_count,
        "orphan_payroll_rows_excluded": orphan_count,
        "employee_intervals_corrected": overlap_count,
        "dq_c14_reclassified": catalog_changed,
    }


def main() -> int:
    outputs, counts = prepare_cleaned_data()
    print("Cleaned feeds:")
    for name in ("fact_payroll", "dim_employee", "dq_checks_catalog"):
        print(f"- {outputs[name].relative_to(ROOT)}")
    for name, count in counts.items():
        print(f"- {name.replace('_', ' ')}: {count}")
    print(f"- cleaning report: {outputs['cleaning_report'].relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Data cleaning failed: {error}", file=sys.stderr)
        raise
