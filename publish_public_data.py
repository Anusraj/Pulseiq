"""Publish privacy-safe governed metric outputs for the hosted dashboard."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parent
SOURCE_DATABASE = ROOT / "pulseiq.duckdb"
TARGET_DATABASE = ROOT / "data" / "pulseiq_public.duckdb"


def publish() -> None:
    if not SOURCE_DATABASE.is_file():
        raise FileNotFoundError(
            f"{SOURCE_DATABASE.name} is missing; run etl.py, warehouse.py, and metrics.py first."
        )

    temporary_database = TARGET_DATABASE.with_suffix(".duckdb.tmp")
    temporary_database.unlink(missing_ok=True)
    target = duckdb.connect(str(temporary_database))
    try:
        source_path = str(SOURCE_DATABASE).replace("'", "''")
        target.execute(f"ATTACH '{source_path}' AS source (READ_ONLY)")
        target.execute("CREATE SCHEMA metrics")
        target.execute("CREATE SCHEMA warehouse")
        metric_tables = [
            row[0]
            for row in target.execute(
                """
                SELECT table_name
                FROM duckdb_tables()
                WHERE database_name = 'source' AND schema_name = 'metrics'
                UNION ALL
                SELECT view_name
                FROM duckdb_views()
                WHERE database_name = 'source' AND schema_name = 'metrics'
                ORDER BY table_name
                """
            ).fetchall()
            if row[0] != "payroll_eligible"
        ]
        for table_name in metric_tables:
            target.execute(
                f'CREATE TABLE metrics."{table_name}" AS '
                f'SELECT * FROM source.metrics."{table_name}"'
            )
        target.execute(
            """
            CREATE TABLE warehouse.dim_team AS
            SELECT team_id, team_name, department_id, active_members, planning_cadence
            FROM source.warehouse.dim_team
            """
        )

        cutoff = target.execute(
            "SELECT MAX(period_start) FROM source.metrics.m01_headcount"
        ).fetchone()[0]
        target.execute(
            """
            CREATE TABLE release_metadata (
                key VARCHAR PRIMARY KEY,
                value VARCHAR NOT NULL
            )
            """
        )
        target.executemany(
            "INSERT INTO release_metadata VALUES (?, ?)",
            [
                ("data_cutoff", cutoff.isoformat()),
                ("generated_at", datetime.now(timezone.utc).isoformat()),
                ("contents", "Governed metric aggregates only; raw and employee-level tables excluded"),
            ],
        )
    finally:
        target.close()

    temporary_database.replace(TARGET_DATABASE)
    print(
        f"Published {len(metric_tables)} governed metric tables to "
        f"{TARGET_DATABASE.relative_to(ROOT)} ({TARGET_DATABASE.stat().st_size:,} bytes)."
    )


if __name__ == "__main__":
    publish()
