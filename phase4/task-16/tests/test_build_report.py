import unittest
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb

from build_report import generate_report, parse_month


def create_fixture(path: Path) -> None:
    connection = duckdb.connect(str(path))
    connection.execute("CREATE SCHEMA metrics")
    connection.execute("CREATE TABLE metrics.dashboard_executive_scorecard (period_start DATE, kpi_id VARCHAR, kpi_name VARCHAR, metric_value DOUBLE, target_value DOUBLE, unit VARCHAR, traffic_light VARCHAR)")
    connection.execute("INSERT INTO metrics.dashboard_executive_scorecard VALUES ('2026-09-01', 'M01', 'Headcount', 10, NULL, 'count', 'NO_TARGET')")
    connection.execute("CREATE TABLE metrics.dashboard_pnl_monthly (period_start DATE, revenue DOUBLE, operating_revenue DOUBLE, expenses DOUBLE, net_profit DOUBLE, operating_margin DOUBLE)")
    connection.execute("INSERT INTO metrics.dashboard_pnl_monthly VALUES ('2026-09-01', 100, 90, 50, 50, 50)")
    connection.execute("CREATE TABLE metrics.dashboard_payroll_department_month (period_start DATE, department_name VARCHAR, group_size BIGINT, gross_pay DOUBLE, employer_cost DOUBLE, cost_per_employee DOUBLE)")
    connection.execute("INSERT INTO metrics.dashboard_payroll_department_month VALUES ('2026-09-01', 'New Department', 2, 20, 25, 12.5)")
    connection.execute("CREATE TABLE metrics.dashboard_budget_vs_actual (period_start DATE, department_name VARCHAR, budget_payroll_cost DOUBLE, actual_payroll_cost DOUBLE, variance DOUBLE, variance_pct DOUBLE, traffic_light VARCHAR)")
    connection.execute("INSERT INTO metrics.dashboard_budget_vs_actual VALUES ('2026-09-01', 'New Department', 20, 25, 5, 25, 'RED')")
    connection.execute("CREATE TABLE metrics.dashboard_team_sprint_productivity (team_name VARCHAR, period_start DATE, sprint_end DATE, planned_tasks BIGINT, completion_rate DOUBLE, on_time_rate DOUBLE, velocity_points DOUBLE, average_cycle_days DOUBLE)")
    connection.execute("INSERT INTO metrics.dashboard_team_sprint_productivity VALUES ('New Department team', '2026-09-01', '2026-09-30', 4, 75, 100, 4, 2)")
    connection.close()


class BuildReportTests(unittest.TestCase):
    def test_report_accepts_new_department(self):
        database = self._testMethodName + ".duckdb"
        output = self._testMethodName + ".pdf"
        try:
            create_fixture(Path(database))
            result = generate_report(Path(database), date(2026, 9, 1), Path(output), datetime(2026, 10, 1, tzinfo=timezone.utc))
            self.assertTrue(result.exists())
            self.assertGreater(result.stat().st_size, 1000)
        finally:
            Path(database).unlink(missing_ok=True)
            Path(output).unlink(missing_ok=True)

    def test_month_parser(self):
        self.assertEqual(parse_month("2026-09"), (date(2026, 9, 1), date(2026, 9, 30)))
