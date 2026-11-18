"""Focused privacy and role-policy tests for Task 18."""

from __future__ import annotations

import unittest

import pandas as pd

from kpi_explorer import (
    MINIMUM_PRIVACY_GROUP_SIZE,
    ROLE_RULES,
    TEAM_METRICS,
    _aggregate_company,
    _allowed_metrics,
    _minimum_group_size,
    _latest_groups,
)


class KpiExplorerTests(unittest.TestCase):
    def test_privacy_floor_never_drops_below_five(self) -> None:
        self.assertEqual(_minimum_group_size("n/a"), MINIMUM_PRIVACY_GROUP_SIZE)
        self.assertEqual(_minimum_group_size("3 tasks"), MINIMUM_PRIVACY_GROUP_SIZE)
        self.assertEqual(_minimum_group_size("10"), 10)

    def test_roles_have_distinct_metric_and_dimension_permissions(self) -> None:
        self.assertEqual(ROLE_RULES["MANAGER"]["metrics"], TEAM_METRICS)
        self.assertEqual(ROLE_RULES["MANAGER"]["dimensions"], {"Team"})
        self.assertNotIn("M07", ROLE_RULES["MANAGER"]["metrics"])
        self.assertEqual(ROLE_RULES["EXECUTIVE"]["dimensions"], {"Company"})

    def test_allowed_metrics_filters_catalog_by_role(self) -> None:
        catalog = pd.DataFrame({"metric_id": ["M01", "M07", "M22"], "metric_name": ["Headcount", "Pay", "Delivery"]})
        hr = _allowed_metrics("HR", catalog)
        manager = _allowed_metrics("MANAGER", catalog)
        self.assertEqual(hr["metric_id"].tolist(), ["M01", "M07"])
        self.assertEqual(manager["metric_id"].tolist(), ["M22"])

    def test_company_aggregation_uses_latest_period_and_sums_counts(self) -> None:
        rows = pd.DataFrame([
            {"period_start": "2026-08-01", "group_size": 5, "numerator": 5, "denominator": None, "metric_value": 5, "unit": "count"},
            {"period_start": "2026-09-01", "group_size": 6, "numerator": 6, "denominator": None, "metric_value": 6, "unit": "count"},
        ])
        result = _aggregate_company(rows)
        self.assertEqual(result.iloc[0]["period_start"], "2026-09-01")
        self.assertEqual(result.iloc[0]["group_size"], 6)
        self.assertEqual(result.iloc[0]["metric_value"], 6)

    def test_latest_groups_keeps_only_last_period_per_group(self) -> None:
        rows = pd.DataFrame([
            {"period_start": "2026-08-01", "department_id": "D01", "group_size": 5, "metric_value": 10},
            {"period_start": "2026-09-01", "department_id": "D01", "group_size": 6, "metric_value": 12},
        ])
        result = _latest_groups(rows, "Department", {"D01": "Engineering"})
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["metric_value"], 12)


if __name__ == "__main__":
    unittest.main()
